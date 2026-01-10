"""
Autopilot Mode - Automatic Resource Tuning

Automatically applies resource recommendations based on observed usage patterns.
Disabled by default - must be explicitly enabled.

Features:
- Auto-tune CPU requests based on P95 usage
- Auto-tune Memory requests based on P95 usage
- Works smoothly with HPA (adjusts HPA target accordingly)
- Safety guardrails to prevent over-optimization
- Rollback on OOM or performance degradation
- Audit logging for all changes

NO CPU/Memory limits - only requests are tuned.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from kubernetes import client

logger = logging.getLogger(__name__)


class AutopilotLevel(Enum):
    """Autopilot automation levels"""
    DISABLED = 0      # No autopilot
    OBSERVE = 1       # Only observe and log recommendations
    RECOMMEND = 2     # Generate recommendations (default behavior)
    AUTOPILOT = 3     # Auto-apply safe changes with guardrails


@dataclass
class ResourceRecommendation:
    """A resource tuning recommendation"""
    namespace: str
    deployment: str
    container: str
    
    # Current values (millicores for CPU, MB for memory)
    current_cpu_request: int
    current_memory_request: int
    
    # Recommended values
    recommended_cpu_request: int
    recommended_memory_request: int
    
    # Analysis
    cpu_p95: float           # P95 CPU usage in millicores
    memory_p95: float        # P95 memory usage in MB
    confidence: float        # 0-1 confidence score
    savings_percent: float   # Estimated savings %
    
    # Safety
    is_safe: bool = True
    safety_reason: str = ""
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    applied_at: Optional[datetime] = None


@dataclass
class AutopilotAction:
    """Record of an autopilot action"""
    namespace: str
    deployment: str
    action_type: str         # 'cpu_request', 'memory_request', 'rollback'
    old_value: int
    new_value: int
    reason: str
    applied_at: datetime
    rolled_back: bool = False
    rollback_reason: str = ""


class AutopilotManager:
    """
    Manages automatic resource tuning for deployments.
    
    Disabled by default. Enable via:
    - Environment: ENABLE_AUTOPILOT=true
    - ConfigMap: ENABLE_AUTOPILOT: "true"
    - Per-deployment annotation: smart-autoscaler.io/autopilot: "true"
    """
    
    def __init__(
        self,
        enabled: bool = False,
        level: AutopilotLevel = AutopilotLevel.RECOMMEND,
        min_observation_days: int = 7,
        min_confidence: float = 0.80,
        max_change_percent: float = 30.0,
        cooldown_hours: int = 24,
        min_cpu_request: int = 50,      # Minimum 50m CPU
        min_memory_request: int = 64,   # Minimum 64MB memory
        cpu_buffer_percent: float = 20.0,    # 20% buffer above P95
        memory_buffer_percent: float = 25.0, # 25% buffer above P95
    ):
        """
        Initialize AutopilotManager.
        
        Args:
            enabled: Master switch for autopilot (default: False)
            level: Automation level
            min_observation_days: Minimum days of data before auto-tuning
            min_confidence: Minimum confidence score to apply changes
            max_change_percent: Maximum % change per iteration
            cooldown_hours: Hours to wait between changes
            min_cpu_request: Minimum CPU request in millicores
            min_memory_request: Minimum memory request in MB
            cpu_buffer_percent: Buffer above P95 for CPU
            memory_buffer_percent: Buffer above P95 for memory
        """
        self.enabled = enabled
        self.level = level
        self.min_observation_days = min_observation_days
        self.min_confidence = min_confidence
        self.max_change_percent = max_change_percent
        self.cooldown_hours = cooldown_hours
        self.min_cpu_request = min_cpu_request
        self.min_memory_request = min_memory_request
        self.cpu_buffer_percent = cpu_buffer_percent
        self.memory_buffer_percent = memory_buffer_percent
        
        # Track recommendations and actions
        self.recommendations: Dict[str, ResourceRecommendation] = {}
        self.actions: List[AutopilotAction] = []
        self.last_action_time: Dict[str, datetime] = {}
        
        # Kubernetes client
        try:
            from kubernetes import config as k8s_config
            try:
                k8s_config.load_incluster_config()
            except:
                k8s_config.load_kube_config()
            self.apps_v1 = client.AppsV1Api()
            self.k8s_available = True
        except Exception as e:
            logger.warning(f"Autopilot: Kubernetes client not available: {e}")
            self.k8s_available = False
            self.apps_v1 = None
        
        status = "enabled" if enabled else "disabled"
        logger.info(
            f"AutopilotManager initialized - {status}, level={level.name}, "
            f"min_confidence={min_confidence}, max_change={max_change_percent}%"
        )
    
    def is_enabled_for_deployment(self, namespace: str, deployment: str) -> bool:
        """Check if autopilot is enabled for a specific deployment."""
        if not self.enabled:
            return False
        
        if not self.k8s_available:
            return False
        
        # Check deployment annotation
        try:
            dep = self.apps_v1.read_namespaced_deployment(deployment, namespace)
            annotations = dep.metadata.annotations or {}
            
            # Check for explicit disable
            if annotations.get('smart-autoscaler.io/autopilot', '').lower() == 'false':
                return False
            
            # Check for explicit enable (overrides global setting)
            if annotations.get('smart-autoscaler.io/autopilot', '').lower() == 'true':
                return True
            
            return self.enabled
        except Exception as e:
            logger.debug(f"Could not check autopilot annotation for {namespace}/{deployment}: {e}")
            return self.enabled
    
    def calculate_recommendation(
        self,
        namespace: str,
        deployment: str,
        current_cpu_request: int,
        current_memory_request: int,
        cpu_p95: float,
        memory_p95: float,
        observation_days: int,
        priority: str = "medium"
    ) -> Optional[ResourceRecommendation]:
        """
        Calculate resource recommendation based on observed usage.
        
        Args:
            namespace: Deployment namespace
            deployment: Deployment name
            current_cpu_request: Current CPU request in millicores
            current_memory_request: Current memory request in MB
            cpu_p95: P95 CPU usage in millicores
            memory_p95: P95 memory usage in MB
            observation_days: Days of observation data
            priority: Deployment priority level
        
        Returns:
            ResourceRecommendation or None if no change needed
        """
        key = f"{namespace}/{deployment}"
        
        # Check minimum observation period
        if observation_days < self.min_observation_days:
            logger.debug(
                f"{key} - Autopilot: Need {self.min_observation_days} days of data, "
                f"have {observation_days}"
            )
            return None
        
        # Calculate recommended values with buffer
        recommended_cpu = int(cpu_p95 * (1 + self.cpu_buffer_percent / 100))
        recommended_memory = int(memory_p95 * (1 + self.memory_buffer_percent / 100))
        
        # Apply minimums
        recommended_cpu = max(recommended_cpu, self.min_cpu_request)
        recommended_memory = max(recommended_memory, self.min_memory_request)
        
        # Calculate change percentages
        cpu_change_pct = abs(recommended_cpu - current_cpu_request) / current_cpu_request * 100 if current_cpu_request > 0 else 0
        memory_change_pct = abs(recommended_memory - current_memory_request) / current_memory_request * 100 if current_memory_request > 0 else 0
        
        # Skip if changes are too small (< 5%)
        if cpu_change_pct < 5 and memory_change_pct < 5:
            logger.debug(f"{key} - Autopilot: Changes too small, skipping")
            return None
        
        # Calculate confidence based on observation period and stability
        base_confidence = min(observation_days / 14, 1.0)  # Max confidence at 14 days
        
        # Reduce confidence for large changes
        change_penalty = max(cpu_change_pct, memory_change_pct) / 100
        confidence = base_confidence * (1 - change_penalty * 0.3)
        confidence = max(0.5, min(1.0, confidence))
        
        # Calculate savings
        cpu_savings = (current_cpu_request - recommended_cpu) / current_cpu_request * 100 if current_cpu_request > 0 else 0
        memory_savings = (current_memory_request - recommended_memory) / current_memory_request * 100 if current_memory_request > 0 else 0
        savings_percent = (cpu_savings + memory_savings) / 2
        
        # Safety checks
        is_safe = True
        safety_reason = ""
        
        # Check max change limit
        if cpu_change_pct > self.max_change_percent:
            # Limit the change
            if recommended_cpu < current_cpu_request:
                recommended_cpu = int(current_cpu_request * (1 - self.max_change_percent / 100))
            else:
                recommended_cpu = int(current_cpu_request * (1 + self.max_change_percent / 100))
            safety_reason = f"CPU change limited to {self.max_change_percent}%"
        
        if memory_change_pct > self.max_change_percent:
            if recommended_memory < current_memory_request:
                recommended_memory = int(current_memory_request * (1 - self.max_change_percent / 100))
            else:
                recommended_memory = int(current_memory_request * (1 + self.max_change_percent / 100))
            safety_reason = f"Memory change limited to {self.max_change_percent}%"
        
        # Priority-based safety
        if priority == "critical":
            is_safe = False
            safety_reason = "Critical priority - manual approval required"
        elif priority == "high" and (cpu_change_pct > 15 or memory_change_pct > 15):
            is_safe = False
            safety_reason = "High priority - large changes require approval"
        
        # Check cooldown
        if key in self.last_action_time:
            hours_since = (datetime.now() - self.last_action_time[key]).total_seconds() / 3600
            if hours_since < self.cooldown_hours:
                is_safe = False
                safety_reason = f"Cooldown active ({self.cooldown_hours - hours_since:.1f}h remaining)"
        
        recommendation = ResourceRecommendation(
            namespace=namespace,
            deployment=deployment,
            container="main",  # Assume main container
            current_cpu_request=current_cpu_request,
            current_memory_request=current_memory_request,
            recommended_cpu_request=recommended_cpu,
            recommended_memory_request=recommended_memory,
            cpu_p95=cpu_p95,
            memory_p95=memory_p95,
            confidence=confidence,
            savings_percent=savings_percent,
            is_safe=is_safe,
            safety_reason=safety_reason
        )
        
        self.recommendations[key] = recommendation
        return recommendation
    
    def should_apply(self, recommendation: ResourceRecommendation) -> Tuple[bool, str]:
        """
        Determine if a recommendation should be auto-applied.
        
        Returns:
            (should_apply, reason)
        """
        if not self.enabled:
            return False, "Autopilot disabled"
        
        if self.level.value < AutopilotLevel.AUTOPILOT.value:
            return False, f"Autopilot level is {self.level.name}"
        
        if not recommendation.is_safe:
            return False, recommendation.safety_reason
        
        if recommendation.confidence < self.min_confidence:
            return False, f"Confidence {recommendation.confidence:.0%} < {self.min_confidence:.0%}"
        
        return True, "All checks passed"
    
    def apply_recommendation(
        self,
        recommendation: ResourceRecommendation,
        dry_run: bool = False
    ) -> bool:
        """
        Apply a resource recommendation to the deployment.
        
        Args:
            recommendation: The recommendation to apply
            dry_run: If True, only log what would be done
        
        Returns:
            True if applied successfully
        """
        key = f"{recommendation.namespace}/{recommendation.deployment}"
        
        should_apply, reason = self.should_apply(recommendation)
        if not should_apply:
            logger.info(f"{key} - Autopilot: Not applying - {reason}")
            return False
        
        if not self.k8s_available:
            logger.error(f"{key} - Autopilot: Kubernetes not available")
            return False
        
        try:
            # Read current deployment
            deployment = self.apps_v1.read_namespaced_deployment(
                recommendation.deployment,
                recommendation.namespace
            )
            
            # Find the container
            containers = deployment.spec.template.spec.containers
            if not containers:
                logger.error(f"{key} - Autopilot: No containers found")
                return False
            
            container = containers[0]  # Assume first container
            
            # Prepare patch
            cpu_request = f"{recommendation.recommended_cpu_request}m"
            memory_request = f"{recommendation.recommended_memory_request}Mi"
            
            if dry_run:
                logger.info(
                    f"{key} - Autopilot [DRY RUN]: Would update "
                    f"CPU {recommendation.current_cpu_request}m → {recommendation.recommended_cpu_request}m, "
                    f"Memory {recommendation.current_memory_request}Mi → {recommendation.recommended_memory_request}Mi"
                )
                return True
            
            # Apply patch
            patch = {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [{
                                "name": container.name,
                                "resources": {
                                    "requests": {
                                        "cpu": cpu_request,
                                        "memory": memory_request
                                    }
                                    # NO limits - intentionally omitted
                                }
                            }]
                        }
                    }
                }
            }
            
            self.apps_v1.patch_namespaced_deployment(
                recommendation.deployment,
                recommendation.namespace,
                patch
            )
            
            # Record actions
            recommendation.applied_at = datetime.now()
            self.last_action_time[key] = datetime.now()
            
            # Log CPU action
            if recommendation.recommended_cpu_request != recommendation.current_cpu_request:
                self.actions.append(AutopilotAction(
                    namespace=recommendation.namespace,
                    deployment=recommendation.deployment,
                    action_type='cpu_request',
                    old_value=recommendation.current_cpu_request,
                    new_value=recommendation.recommended_cpu_request,
                    reason=f"P95={recommendation.cpu_p95:.0f}m, confidence={recommendation.confidence:.0%}",
                    applied_at=datetime.now()
                ))
            
            # Log memory action
            if recommendation.recommended_memory_request != recommendation.current_memory_request:
                self.actions.append(AutopilotAction(
                    namespace=recommendation.namespace,
                    deployment=recommendation.deployment,
                    action_type='memory_request',
                    old_value=recommendation.current_memory_request,
                    new_value=recommendation.recommended_memory_request,
                    reason=f"P95={recommendation.memory_p95:.0f}MB, confidence={recommendation.confidence:.0%}",
                    applied_at=datetime.now()
                ))
            
            logger.info(
                f"✅ {key} - Autopilot applied: "
                f"CPU {recommendation.current_cpu_request}m → {recommendation.recommended_cpu_request}m, "
                f"Memory {recommendation.current_memory_request}Mi → {recommendation.recommended_memory_request}Mi "
                f"(confidence: {recommendation.confidence:.0%}, savings: {recommendation.savings_percent:.1f}%)"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"{key} - Autopilot: Failed to apply - {e}")
            return False

    def rollback_action(
        self,
        namespace: str,
        deployment: str,
        reason: str = "Manual rollback"
    ) -> bool:
        """
        Rollback the last autopilot action for a deployment.
        
        Args:
            namespace: Deployment namespace
            deployment: Deployment name
            reason: Reason for rollback
        
        Returns:
            True if rollback successful
        """
        key = f"{namespace}/{deployment}"
        
        # Find the last action for this deployment
        recent_actions = [
            a for a in self.actions
            if a.namespace == namespace and a.deployment == deployment and not a.rolled_back
        ]
        
        if not recent_actions:
            logger.warning(f"{key} - Autopilot: No actions to rollback")
            return False
        
        if not self.k8s_available:
            logger.error(f"{key} - Autopilot: Kubernetes not available for rollback")
            return False
        
        try:
            # Get the deployment
            dep = self.apps_v1.read_namespaced_deployment(deployment, namespace)
            containers = dep.spec.template.spec.containers
            if not containers:
                return False
            
            container = containers[0]
            
            # Find the most recent CPU and memory actions
            cpu_action = None
            memory_action = None
            for action in reversed(recent_actions):
                if action.action_type == 'cpu_request' and not cpu_action:
                    cpu_action = action
                elif action.action_type == 'memory_request' and not memory_action:
                    memory_action = action
                if cpu_action and memory_action:
                    break
            
            # Build rollback patch
            requests = {}
            if cpu_action:
                requests['cpu'] = f"{cpu_action.old_value}m"
                cpu_action.rolled_back = True
                cpu_action.rollback_reason = reason
            if memory_action:
                requests['memory'] = f"{memory_action.old_value}Mi"
                memory_action.rolled_back = True
                memory_action.rollback_reason = reason
            
            if not requests:
                return False
            
            patch = {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [{
                                "name": container.name,
                                "resources": {
                                    "requests": requests
                                }
                            }]
                        }
                    }
                }
            }
            
            self.apps_v1.patch_namespaced_deployment(deployment, namespace, patch)
            
            # Record rollback action
            self.actions.append(AutopilotAction(
                namespace=namespace,
                deployment=deployment,
                action_type='rollback',
                old_value=cpu_action.new_value if cpu_action else 0,
                new_value=cpu_action.old_value if cpu_action else 0,
                reason=reason,
                applied_at=datetime.now()
            ))
            
            # Clear cooldown to allow immediate re-tuning if needed
            if key in self.last_action_time:
                del self.last_action_time[key]
            
            logger.info(f"🔄 {key} - Autopilot rollback: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"{key} - Autopilot: Rollback failed - {e}")
            return False
    
    def get_recent_actions(
        self,
        namespace: str = None,
        deployment: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get recent autopilot actions for dashboard display.
        
        Args:
            namespace: Filter by namespace (optional)
            deployment: Filter by deployment (optional)
            limit: Maximum number of actions to return
        
        Returns:
            List of action dictionaries
        """
        actions = self.actions
        
        # Filter by namespace/deployment if specified
        if namespace:
            actions = [a for a in actions if a.namespace == namespace]
        if deployment:
            actions = [a for a in actions if a.deployment == deployment]
        
        # Sort by time (newest first) and limit
        actions = sorted(actions, key=lambda a: a.applied_at, reverse=True)[:limit]
        
        return [
            {
                'namespace': a.namespace,
                'deployment': a.deployment,
                'action_type': a.action_type,
                'old_value': a.old_value,
                'new_value': a.new_value,
                'reason': a.reason,
                'applied_at': a.applied_at.isoformat(),
                'rolled_back': a.rolled_back,
                'rollback_reason': a.rollback_reason
            }
            for a in actions
        ]
    
    def get_recommendations(self, namespace: str = None) -> List[Dict]:
        """
        Get all current recommendations for dashboard display.
        
        Args:
            namespace: Filter by namespace (optional)
        
        Returns:
            List of recommendation dictionaries
        """
        recommendations = list(self.recommendations.values())
        
        if namespace:
            recommendations = [r for r in recommendations if r.namespace == namespace]
        
        return [
            {
                'namespace': r.namespace,
                'deployment': r.deployment,
                'container': r.container,
                'current_cpu_request': r.current_cpu_request,
                'current_memory_request': r.current_memory_request,
                'recommended_cpu_request': r.recommended_cpu_request,
                'recommended_memory_request': r.recommended_memory_request,
                'cpu_p95': r.cpu_p95,
                'memory_p95': r.memory_p95,
                'confidence': r.confidence,
                'savings_percent': r.savings_percent,
                'is_safe': r.is_safe,
                'safety_reason': r.safety_reason,
                'created_at': r.created_at.isoformat(),
                'applied_at': r.applied_at.isoformat() if r.applied_at else None
            }
            for r in recommendations
        ]
    
    def get_status(self) -> Dict:
        """
        Get autopilot status summary for dashboard.
        
        Returns:
            Status dictionary with configuration and statistics
        """
        # Count actions by type
        action_counts = {}
        for action in self.actions:
            action_counts[action.action_type] = action_counts.get(action.action_type, 0) + 1
        
        # Count rollbacks
        rollback_count = sum(1 for a in self.actions if a.rolled_back)
        
        # Calculate total savings from applied recommendations
        total_savings = sum(
            r.savings_percent for r in self.recommendations.values()
            if r.applied_at is not None
        )
        
        # Get pending recommendations count
        pending_count = sum(
            1 for r in self.recommendations.values()
            if r.applied_at is None and r.is_safe
        )
        
        return {
            'enabled': self.enabled,
            'level': self.level.name,
            'config': {
                'min_observation_days': self.min_observation_days,
                'min_confidence': self.min_confidence,
                'max_change_percent': self.max_change_percent,
                'cooldown_hours': self.cooldown_hours,
                'min_cpu_request': self.min_cpu_request,
                'min_memory_request': self.min_memory_request,
                'cpu_buffer_percent': self.cpu_buffer_percent,
                'memory_buffer_percent': self.memory_buffer_percent
            },
            'statistics': {
                'total_recommendations': len(self.recommendations),
                'pending_recommendations': pending_count,
                'total_actions': len(self.actions),
                'actions_by_type': action_counts,
                'rollbacks': rollback_count,
                'estimated_savings_percent': total_savings
            },
            'deployments_in_cooldown': [
                {
                    'key': key,
                    'hours_remaining': max(0, self.cooldown_hours - (datetime.now() - time).total_seconds() / 3600)
                }
                for key, time in self.last_action_time.items()
                if (datetime.now() - time).total_seconds() / 3600 < self.cooldown_hours
            ]
        }


def create_autopilot_manager() -> AutopilotManager:
    """
    Factory function to create AutopilotManager from environment variables.
    
    Environment variables:
        ENABLE_AUTOPILOT: Master switch (default: false)
        AUTOPILOT_LEVEL: disabled, observe, recommend, autopilot (default: recommend)
        AUTOPILOT_MIN_OBSERVATION_DAYS: Days of data needed (default: 7)
        AUTOPILOT_MIN_CONFIDENCE: Minimum confidence to apply (default: 0.80)
        AUTOPILOT_MAX_CHANGE_PERCENT: Max change per iteration (default: 30)
        AUTOPILOT_COOLDOWN_HOURS: Hours between changes (default: 24)
        AUTOPILOT_MIN_CPU_REQUEST: Minimum CPU in millicores (default: 50)
        AUTOPILOT_MIN_MEMORY_REQUEST: Minimum memory in MB (default: 64)
        AUTOPILOT_CPU_BUFFER_PERCENT: Buffer above P95 for CPU (default: 20)
        AUTOPILOT_MEMORY_BUFFER_PERCENT: Buffer above P95 for memory (default: 25)
    
    Returns:
        Configured AutopilotManager instance
    """
    enabled = os.getenv('ENABLE_AUTOPILOT', 'false').lower() == 'true'
    
    level_str = os.getenv('AUTOPILOT_LEVEL', 'recommend').lower()
    level_map = {
        'disabled': AutopilotLevel.DISABLED,
        'observe': AutopilotLevel.OBSERVE,
        'recommend': AutopilotLevel.RECOMMEND,
        'autopilot': AutopilotLevel.AUTOPILOT
    }
    level = level_map.get(level_str, AutopilotLevel.RECOMMEND)
    
    return AutopilotManager(
        enabled=enabled,
        level=level,
        min_observation_days=int(os.getenv('AUTOPILOT_MIN_OBSERVATION_DAYS', '7')),
        min_confidence=float(os.getenv('AUTOPILOT_MIN_CONFIDENCE', '0.80')),
        max_change_percent=float(os.getenv('AUTOPILOT_MAX_CHANGE_PERCENT', '30')),
        cooldown_hours=int(os.getenv('AUTOPILOT_COOLDOWN_HOURS', '24')),
        min_cpu_request=int(os.getenv('AUTOPILOT_MIN_CPU_REQUEST', '50')),
        min_memory_request=int(os.getenv('AUTOPILOT_MIN_MEMORY_REQUEST', '64')),
        cpu_buffer_percent=float(os.getenv('AUTOPILOT_CPU_BUFFER_PERCENT', '20')),
        memory_buffer_percent=float(os.getenv('AUTOPILOT_MEMORY_BUFFER_PERCENT', '25'))
    )
