"""
Pre-Scale Manager
Manages predictive pre-scaling by temporarily adjusting HPA minReplicas.

Key Features:
- Stores original HPA minReplicas on first read
- Patches minReplicas when spike is predicted
- Auto-rollbacks after peak passes or timeout
- Dashboard visibility of pre-scale state
- Works with ArgoCD if auto-sync disabled for HPA

Flow:
1. On startup: Read HPA minReplicas → store as original
2. Predict spike → Calculate required replicas → Patch HPA minReplicas
3. After peak OR prediction failed OR timeout → Rollback to original
"""

import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import json

logger = logging.getLogger(__name__)


class PreScaleState(Enum):
    """Pre-scale state for a deployment"""
    NORMAL = "normal"           # Using original minReplicas
    PRE_SCALING = "pre_scaling" # minReplicas increased for predicted spike
    ROLLING_BACK = "rolling_back"  # In process of rolling back


@dataclass
class PreScaleProfile:
    """Pre-scale profile for a deployment"""
    namespace: str
    deployment: str
    hpa_name: str
    
    # Original values (from HPA spec)
    original_min_replicas: int
    original_max_replicas: int
    
    # Current state
    state: PreScaleState = PreScaleState.NORMAL
    current_min_replicas: int = 0
    
    # Pre-scale info
    pre_scale_started: Optional[datetime] = None
    pre_scale_reason: str = ""
    predicted_cpu: float = 0.0
    prediction_confidence: float = 0.0
    prediction_window: str = ""
    
    # Rollback info
    rollback_at: Optional[datetime] = None
    auto_rollback_minutes: int = 60  # Default 1 hour
    
    # History
    last_updated: datetime = field(default_factory=datetime.now)
    pre_scale_count: int = 0
    successful_predictions: int = 0
    failed_predictions: int = 0
    
    def __post_init__(self):
        if self.current_min_replicas == 0:
            self.current_min_replicas = self.original_min_replicas
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API response"""
        return {
            'namespace': self.namespace,
            'deployment': self.deployment,
            'hpa_name': self.hpa_name,
            'original_min_replicas': self.original_min_replicas,
            'original_max_replicas': self.original_max_replicas,
            'current_min_replicas': self.current_min_replicas,
            'state': self.state.value,
            'pre_scale_started': self.pre_scale_started.isoformat() if self.pre_scale_started else None,
            'pre_scale_reason': self.pre_scale_reason,
            'predicted_cpu': self.predicted_cpu,
            'prediction_confidence': self.prediction_confidence,
            'prediction_window': self.prediction_window,
            'rollback_at': self.rollback_at.isoformat() if self.rollback_at else None,
            'auto_rollback_minutes': self.auto_rollback_minutes,
            'last_updated': self.last_updated.isoformat(),
            'pre_scale_count': self.pre_scale_count,
            'successful_predictions': self.successful_predictions,
            'failed_predictions': self.failed_predictions
        }


class PreScaleManager:
    """
    Manages predictive pre-scaling by adjusting HPA minReplicas.
    
    This enables TRUE pre-scaling:
    1. Predict CPU spike in 15-60 minutes
    2. Calculate required replicas
    3. Patch HPA minReplicas to force scale-up NOW
    4. Pods are ready before traffic arrives
    5. Auto-rollback after peak passes
    """
    
    def __init__(
        self,
        k8s_client,
        autoscaling_api,
        predictor,
        db,
        enable_prescale: bool = True,
        min_confidence: float = 0.7,
        scale_up_threshold: float = 75.0,
        auto_rollback_minutes: int = 60,
        cooldown_minutes: int = 15
    ):
        """
        Initialize PreScaleManager.
        
        Args:
            k8s_client: Kubernetes client
            autoscaling_api: Kubernetes autoscaling API
            predictor: AdvancedPredictor instance
            db: TimeSeriesDatabase instance
            enable_prescale: Enable/disable pre-scaling
            min_confidence: Minimum prediction confidence to act (0-1)
            scale_up_threshold: CPU % threshold to trigger pre-scale
            auto_rollback_minutes: Auto-rollback after this many minutes
            cooldown_minutes: Cooldown between pre-scale actions
        """
        self.k8s_client = k8s_client
        self.autoscaling_api = autoscaling_api
        self.predictor = predictor
        self.db = db
        
        self.enable_prescale = enable_prescale
        self.min_confidence = min_confidence
        self.scale_up_threshold = scale_up_threshold
        self.auto_rollback_minutes = auto_rollback_minutes
        self.cooldown_minutes = cooldown_minutes
        
        # Storage for profiles
        self.profiles: Dict[str, PreScaleProfile] = {}
        self._lock = threading.Lock()
        
        # Last action tracking for cooldown
        self.last_action: Dict[str, datetime] = {}
        
        logger.info(
            f"PreScaleManager initialized - enabled={enable_prescale}, "
            f"min_confidence={min_confidence}, threshold={scale_up_threshold}%, "
            f"auto_rollback={auto_rollback_minutes}min"
        )
    
    def _get_profile_key(self, namespace: str, deployment: str) -> str:
        """Get unique key for a deployment"""
        return f"{namespace}/{deployment}"
    
    def register_deployment(
        self,
        namespace: str,
        deployment: str,
        hpa_name: str
    ) -> Optional[PreScaleProfile]:
        """
        Register a deployment and read its original HPA values.
        
        Args:
            namespace: Namespace
            deployment: Deployment name
            hpa_name: HPA name
        
        Returns:
            PreScaleProfile or None if failed
        """
        key = self._get_profile_key(namespace, deployment)
        
        # Check if already registered
        with self._lock:
            if key in self.profiles:
                return self.profiles[key]
        
        try:
            # Read HPA to get original values
            hpa = self.autoscaling_api.read_namespaced_horizontal_pod_autoscaler(
                hpa_name, namespace
            )
            
            original_min = hpa.spec.min_replicas or 1
            original_max = hpa.spec.max_replicas or 10
            
            profile = PreScaleProfile(
                namespace=namespace,
                deployment=deployment,
                hpa_name=hpa_name,
                original_min_replicas=original_min,
                original_max_replicas=original_max,
                current_min_replicas=original_min
            )
            
            with self._lock:
                self.profiles[key] = profile
            
            logger.info(
                f"{namespace}/{deployment} - Registered for pre-scaling: "
                f"minReplicas={original_min}, maxReplicas={original_max}"
            )
            
            return profile
            
        except Exception as e:
            logger.error(f"{namespace}/{deployment} - Failed to register: {e}")
            return None
    
    def get_profile(self, namespace: str, deployment: str) -> Optional[PreScaleProfile]:
        """Get profile for a deployment"""
        key = self._get_profile_key(namespace, deployment)
        with self._lock:
            return self.profiles.get(key)
    
    def get_all_profiles(self) -> List[PreScaleProfile]:
        """Get all registered profiles"""
        with self._lock:
            return list(self.profiles.values())
    
    def calculate_required_replicas(
        self,
        current_replicas: int,
        current_cpu: float,
        predicted_cpu: float,
        target_cpu: float,
        min_replicas: int,
        max_replicas: int
    ) -> int:
        """
        Calculate required replicas for predicted load.
        
        Formula: required = current_replicas * (predicted_cpu / target_cpu)
        
        Args:
            current_replicas: Current pod count
            current_cpu: Current CPU %
            predicted_cpu: Predicted CPU %
            target_cpu: HPA target CPU %
            min_replicas: HPA min replicas
            max_replicas: HPA max replicas
        
        Returns:
            Required replica count
        """
        if current_replicas <= 0 or target_cpu <= 0:
            return min_replicas
        
        # Calculate scale factor
        scale_factor = predicted_cpu / target_cpu
        
        # Apply safety limits (max 3x, min 0.5x)
        scale_factor = max(0.5, min(3.0, scale_factor))
        
        # Calculate required
        required = int(current_replicas * scale_factor + 0.5)  # Round
        
        # Respect HPA limits
        required = max(min_replicas, min(max_replicas, required))
        
        return required
    
    def check_and_prescale(
        self,
        namespace: str,
        deployment: str,
        current_replicas: int,
        current_cpu: float,
        target_cpu: float = 70.0
    ) -> Dict:
        """
        Check predictions and pre-scale if needed.
        
        Args:
            namespace: Namespace
            deployment: Deployment name
            current_replicas: Current pod count
            current_cpu: Current CPU %
            target_cpu: HPA target CPU %
        
        Returns:
            Dict with action taken and details
        """
        if not self.enable_prescale:
            return {'action': 'disabled', 'reason': 'Pre-scaling is disabled'}
        
        key = self._get_profile_key(namespace, deployment)
        profile = self.get_profile(namespace, deployment)
        
        if not profile:
            return {'action': 'not_registered', 'reason': 'Deployment not registered'}
        
        # Check cooldown
        if key in self.last_action:
            elapsed = (datetime.now() - self.last_action[key]).total_seconds()
            if elapsed < self.cooldown_minutes * 60:
                remaining = self.cooldown_minutes - (elapsed / 60)
                return {
                    'action': 'cooldown',
                    'reason': f'In cooldown, {remaining:.1f} minutes remaining'
                }
        
        # Get predictions
        try:
            predictions = self.predictor.predict_all_windows(deployment)
        except Exception as e:
            logger.error(f"{namespace}/{deployment} - Prediction failed: {e}")
            return {'action': 'error', 'reason': str(e)}
        
        # Find best prediction above threshold
        best_prediction = None
        best_window = None
        
        for window, result in predictions.items():
            if result.confidence >= self.min_confidence:
                if result.predicted_value > self.scale_up_threshold:
                    if best_prediction is None or result.confidence > best_prediction.confidence:
                        best_prediction = result
                        best_window = window
        
        # If currently pre-scaling, check if we should rollback
        if profile.state == PreScaleState.PRE_SCALING:
            return self._check_rollback(profile, predictions, current_cpu)
        
        # If no spike predicted, maintain normal state
        if not best_prediction:
            return {
                'action': 'maintain',
                'reason': 'No spike predicted above threshold',
                'predictions': {k: {'value': v.predicted_value, 'confidence': v.confidence}
                               for k, v in predictions.items()}
            }
        
        # Calculate required replicas
        required = self.calculate_required_replicas(
            current_replicas=current_replicas,
            current_cpu=current_cpu,
            predicted_cpu=best_prediction.predicted_value,
            target_cpu=target_cpu,
            min_replicas=profile.original_min_replicas,
            max_replicas=profile.original_max_replicas
        )
        
        # Only pre-scale if we need more replicas than original min
        if required <= profile.original_min_replicas:
            return {
                'action': 'maintain',
                'reason': f'Required replicas ({required}) <= original min ({profile.original_min_replicas})',
                'predictions': {k: {'value': v.predicted_value, 'confidence': v.confidence}
                               for k, v in predictions.items()}
            }
        
        # Pre-scale!
        return self._do_prescale(
            profile=profile,
            new_min_replicas=required,
            predicted_cpu=best_prediction.predicted_value,
            confidence=best_prediction.confidence,
            window=best_window,
            reason=f"Predicted {best_prediction.predicted_value:.1f}% CPU in {best_window}"
        )
    
    def _do_prescale(
        self,
        profile: PreScaleProfile,
        new_min_replicas: int,
        predicted_cpu: float,
        confidence: float,
        window: str,
        reason: str
    ) -> Dict:
        """Execute pre-scale by patching HPA minReplicas"""
        try:
            # Patch HPA
            patch = {
                'spec': {
                    'minReplicas': new_min_replicas
                }
            }
            
            self.autoscaling_api.patch_namespaced_horizontal_pod_autoscaler(
                profile.hpa_name,
                profile.namespace,
                patch
            )
            
            # Update profile
            with self._lock:
                profile.state = PreScaleState.PRE_SCALING
                profile.current_min_replicas = new_min_replicas
                profile.pre_scale_started = datetime.now()
                profile.pre_scale_reason = reason
                profile.predicted_cpu = predicted_cpu
                profile.prediction_confidence = confidence
                profile.prediction_window = window
                profile.rollback_at = datetime.now() + timedelta(minutes=self.auto_rollback_minutes)
                profile.pre_scale_count += 1
                profile.last_updated = datetime.now()
            
            # Record action for cooldown
            key = self._get_profile_key(profile.namespace, profile.deployment)
            self.last_action[key] = datetime.now()
            
            logger.info(
                f"{profile.namespace}/{profile.deployment} - PRE-SCALED: "
                f"minReplicas {profile.original_min_replicas} → {new_min_replicas} "
                f"(predicted {predicted_cpu:.1f}% CPU in {window}, confidence {confidence:.0%})"
            )
            
            return {
                'action': 'pre_scaled',
                'reason': reason,
                'original_min_replicas': profile.original_min_replicas,
                'new_min_replicas': new_min_replicas,
                'predicted_cpu': predicted_cpu,
                'confidence': confidence,
                'window': window,
                'rollback_at': profile.rollback_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"{profile.namespace}/{profile.deployment} - Pre-scale failed: {e}")
            return {'action': 'error', 'reason': str(e)}
    
    def _check_rollback(
        self,
        profile: PreScaleProfile,
        predictions: Dict,
        current_cpu: float
    ) -> Dict:
        """Check if we should rollback from pre-scaling state"""
        now = datetime.now()
        
        # Check auto-rollback timeout
        if profile.rollback_at and now >= profile.rollback_at:
            return self._do_rollback(profile, "Auto-rollback timeout reached")
        
        # Check if prediction was wrong (CPU stayed low)
        if profile.pre_scale_started:
            elapsed = (now - profile.pre_scale_started).total_seconds() / 60
            
            # If 30+ minutes passed and CPU is still low, prediction failed
            if elapsed >= 30 and current_cpu < self.scale_up_threshold * 0.7:
                with self._lock:
                    profile.failed_predictions += 1
                return self._do_rollback(
                    profile,
                    f"Prediction failed - CPU stayed at {current_cpu:.1f}% after {elapsed:.0f} minutes"
                )
            
            # If CPU spiked as predicted, mark success
            if current_cpu >= self.scale_up_threshold * 0.9:
                with self._lock:
                    profile.successful_predictions += 1
                logger.info(
                    f"{profile.namespace}/{profile.deployment} - Prediction SUCCESS: "
                    f"CPU reached {current_cpu:.1f}% as predicted"
                )
        
        # Check if all predictions now show low CPU (peak passed)
        all_low = all(
            p.predicted_value < self.scale_up_threshold * 0.7
            for p in predictions.values()
            if p.confidence >= self.min_confidence
        )
        
        if all_low and current_cpu < self.scale_up_threshold * 0.7:
            return self._do_rollback(profile, "Peak passed - all predictions show low CPU")
        
        return {
            'action': 'maintaining_prescale',
            'reason': f"Pre-scaling active, rollback at {profile.rollback_at.isoformat() if profile.rollback_at else 'N/A'}",
            'current_cpu': current_cpu,
            'elapsed_minutes': (now - profile.pre_scale_started).total_seconds() / 60 if profile.pre_scale_started else 0
        }
    
    def _do_rollback(self, profile: PreScaleProfile, reason: str) -> Dict:
        """Rollback to original minReplicas"""
        try:
            # Patch HPA back to original
            patch = {
                'spec': {
                    'minReplicas': profile.original_min_replicas
                }
            }
            
            self.autoscaling_api.patch_namespaced_horizontal_pod_autoscaler(
                profile.hpa_name,
                profile.namespace,
                patch
            )
            
            # Update profile
            with self._lock:
                old_min = profile.current_min_replicas
                profile.state = PreScaleState.NORMAL
                profile.current_min_replicas = profile.original_min_replicas
                profile.pre_scale_started = None
                profile.rollback_at = None
                profile.last_updated = datetime.now()
            
            logger.info(
                f"{profile.namespace}/{profile.deployment} - ROLLBACK: "
                f"minReplicas {old_min} → {profile.original_min_replicas} ({reason})"
            )
            
            return {
                'action': 'rolled_back',
                'reason': reason,
                'original_min_replicas': profile.original_min_replicas,
                'previous_min_replicas': old_min
            }
            
        except Exception as e:
            logger.error(f"{profile.namespace}/{profile.deployment} - Rollback failed: {e}")
            return {'action': 'error', 'reason': str(e)}
    
    def force_rollback(self, namespace: str, deployment: str) -> Dict:
        """Force rollback a deployment to original minReplicas"""
        profile = self.get_profile(namespace, deployment)
        if not profile:
            return {'action': 'error', 'reason': 'Deployment not registered'}
        
        if profile.state == PreScaleState.NORMAL:
            return {'action': 'already_normal', 'reason': 'Already at original minReplicas'}
        
        return self._do_rollback(profile, "Manual force rollback")
    
    def force_prescale(
        self,
        namespace: str,
        deployment: str,
        new_min_replicas: int,
        reason: str = "Manual pre-scale"
    ) -> Dict:
        """Force pre-scale a deployment"""
        profile = self.get_profile(namespace, deployment)
        if not profile:
            return {'action': 'error', 'reason': 'Deployment not registered'}
        
        if new_min_replicas > profile.original_max_replicas:
            return {
                'action': 'error',
                'reason': f'Requested {new_min_replicas} exceeds maxReplicas {profile.original_max_replicas}'
            }
        
        return self._do_prescale(
            profile=profile,
            new_min_replicas=new_min_replicas,
            predicted_cpu=0,
            confidence=1.0,
            window="manual",
            reason=reason
        )
    
    def check_all_rollbacks(self):
        """Check all profiles for auto-rollback (call periodically)"""
        now = datetime.now()
        
        with self._lock:
            profiles_to_check = [
                p for p in self.profiles.values()
                if p.state == PreScaleState.PRE_SCALING
            ]
        
        for profile in profiles_to_check:
            if profile.rollback_at and now >= profile.rollback_at:
                self._do_rollback(profile, "Auto-rollback timeout")
    
    def get_summary(self) -> Dict:
        """Get summary of all pre-scale states"""
        with self._lock:
            profiles = list(self.profiles.values())
        
        normal_count = sum(1 for p in profiles if p.state == PreScaleState.NORMAL)
        prescaling_count = sum(1 for p in profiles if p.state == PreScaleState.PRE_SCALING)
        
        total_prescales = sum(p.pre_scale_count for p in profiles)
        total_success = sum(p.successful_predictions for p in profiles)
        total_failed = sum(p.failed_predictions for p in profiles)
        
        return {
            'enabled': self.enable_prescale,
            'total_deployments': len(profiles),
            'normal': normal_count,
            'pre_scaling': prescaling_count,
            'total_prescale_actions': total_prescales,
            'successful_predictions': total_success,
            'failed_predictions': total_failed,
            'success_rate': (total_success / (total_success + total_failed) * 100) if (total_success + total_failed) > 0 else 0,
            'config': {
                'min_confidence': self.min_confidence,
                'scale_up_threshold': self.scale_up_threshold,
                'auto_rollback_minutes': self.auto_rollback_minutes,
                'cooldown_minutes': self.cooldown_minutes
            }
        }
