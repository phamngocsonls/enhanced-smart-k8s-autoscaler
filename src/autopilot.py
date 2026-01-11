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
- Auto-rollback with health monitoring
- Audit logging for all changes

NO CPU/Memory limits - only requests are tuned.
"""

import logging
import os
import threading
import time as time_module
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
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


@dataclass
class ResourceSnapshot:
    """Snapshot of deployment state before autopilot changes"""
    namespace: str
    deployment: str
    container: str
    
    # Resource values at snapshot time
    cpu_request: int         # millicores
    memory_request: int      # MB
    
    # Health metrics at snapshot time
    pod_restarts: int
    oom_kills: int
    ready_replicas: int
    total_replicas: int
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = None  # Auto-expire after monitoring window
    
    def __post_init__(self):
        if self.expires_at is None:
            # Default: expire after 30 minutes (monitoring window)
            self.expires_at = self.created_at + timedelta(minutes=30)


@dataclass
class HealthCheckResult:
    """Result of health check after autopilot changes"""
    namespace: str
    deployment: str
    
    # Current health metrics
    pod_restarts: int
    oom_kills: int
    ready_replicas: int
    total_replicas: int
    error_rate: float        # 0-1, percentage of failed requests
    
    # Comparison with snapshot
    restart_increase: int
    oom_increase: int
    readiness_drop: int
    
    # Health status
    is_healthy: bool
    issues: List[str] = field(default_factory=list)
    
    # Timestamp
    checked_at: datetime = field(default_factory=datetime.now)


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
        alert_manager = None,           # AlertManager for webhook notifications
        # Rollback configuration
        enable_auto_rollback: bool = True,
        rollback_monitor_minutes: int = 10,
        max_restart_increase: int = 2,
        max_oom_increase: int = 1,
        max_readiness_drop_percent: float = 20.0,
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
            enable_auto_rollback: Enable automatic rollback on health issues
            rollback_monitor_minutes: Minutes to monitor after changes
            max_restart_increase: Max pod restart increase before rollback
            max_oom_increase: Max OOMKill increase before rollback
            max_readiness_drop_percent: Max readiness drop % before rollback
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
        self.alert_manager = alert_manager  # For webhook notifications
        
        # Rollback configuration
        self.enable_auto_rollback = enable_auto_rollback
        self.rollback_monitor_minutes = rollback_monitor_minutes
        self.max_restart_increase = max_restart_increase
        self.max_oom_increase = max_oom_increase
        self.max_readiness_drop_percent = max_readiness_drop_percent
        
        # Track recommendations and actions
        self.recommendations: Dict[str, ResourceRecommendation] = {}
        self.actions: List[AutopilotAction] = []
        self.last_action_time: Dict[str, datetime] = {}
        
        # Rollback tracking
        self.snapshots: Dict[str, ResourceSnapshot] = {}  # key -> snapshot
        self.pending_monitors: Dict[str, datetime] = {}   # key -> monitor_until
        self.rollback_history: List[Dict] = []            # History of auto-rollbacks
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor = threading.Event()
        
        # Kubernetes client
        try:
            from kubernetes import config as k8s_config
            try:
                k8s_config.load_incluster_config()
            except:
                k8s_config.load_kube_config()
            self.apps_v1 = client.AppsV1Api()
            self.core_v1 = client.CoreV1Api()
            self.k8s_available = True
        except Exception as e:
            logger.warning(f"Autopilot: Kubernetes client not available: {e}")
            self.k8s_available = False
            self.apps_v1 = None
            self.core_v1 = None
        
        status = "enabled" if enabled else "disabled"
        rollback_status = "enabled" if enable_auto_rollback else "disabled"
        logger.info(
            f"AutopilotManager initialized - {status}, level={level.name}, "
            f"min_confidence={min_confidence}, max_change={max_change_percent}%, "
            f"auto_rollback={rollback_status}"
        )
    
    def _send_notification(self, title: str, message: str, severity: str = "info", fields: Dict = None):
        """Send notification via AlertManager webhooks (Slack, Teams, Discord, etc.)"""
        if self.alert_manager:
            try:
                self.alert_manager.send_alert(title, message, severity, fields)
            except Exception as e:
                logger.debug(f"Failed to send autopilot notification: {e}")
    
    # ==================== Rollback & Health Monitoring ====================
    
    def create_snapshot(self, namespace: str, deployment: str) -> Optional[ResourceSnapshot]:
        """
        Create a snapshot of deployment state before making changes.
        Used for rollback if health degrades.
        
        Args:
            namespace: Deployment namespace
            deployment: Deployment name
        
        Returns:
            ResourceSnapshot or None if failed
        """
        key = f"{namespace}/{deployment}"
        
        if not self.k8s_available:
            logger.warning(f"{key} - Cannot create snapshot: K8s not available")
            return None
        
        try:
            # Get deployment info
            dep = self.apps_v1.read_namespaced_deployment(deployment, namespace)
            containers = dep.spec.template.spec.containers
            if not containers:
                return None
            
            container = containers[0]
            
            # Parse current resources
            resources = container.resources or client.V1ResourceRequirements()
            requests = resources.requests or {}
            
            cpu_str = requests.get('cpu', '100m')
            memory_str = requests.get('memory', '128Mi')
            
            # Parse CPU (handle both "100m" and "0.1" formats)
            if isinstance(cpu_str, str):
                if cpu_str.endswith('m'):
                    cpu_request = int(cpu_str[:-1])
                else:
                    cpu_request = int(float(cpu_str) * 1000)
            else:
                cpu_request = int(cpu_str * 1000) if cpu_str < 10 else int(cpu_str)
            
            # Parse memory (handle Mi, Gi formats)
            if isinstance(memory_str, str):
                if memory_str.endswith('Gi'):
                    memory_request = int(float(memory_str[:-2]) * 1024)
                elif memory_str.endswith('Mi'):
                    memory_request = int(memory_str[:-2])
                elif memory_str.endswith('Ki'):
                    memory_request = int(float(memory_str[:-2]) / 1024)
                else:
                    memory_request = int(int(memory_str) / (1024 * 1024))
            else:
                memory_request = int(memory_str / (1024 * 1024))
            
            # Get pod health metrics
            pod_restarts, oom_kills = self._get_pod_health_metrics(namespace, deployment)
            
            # Get replica status
            ready_replicas = dep.status.ready_replicas or 0
            total_replicas = dep.status.replicas or 0
            
            snapshot = ResourceSnapshot(
                namespace=namespace,
                deployment=deployment,
                container=container.name,
                cpu_request=cpu_request,
                memory_request=memory_request,
                pod_restarts=pod_restarts,
                oom_kills=oom_kills,
                ready_replicas=ready_replicas,
                total_replicas=total_replicas,
                expires_at=datetime.now() + timedelta(minutes=self.rollback_monitor_minutes)
            )
            
            self.snapshots[key] = snapshot
            logger.info(f"{key} - Snapshot created: CPU={cpu_request}m, Memory={memory_request}Mi, "
                       f"Restarts={pod_restarts}, OOMs={oom_kills}")
            
            return snapshot
            
        except Exception as e:
            logger.error(f"{key} - Failed to create snapshot: {e}")
            return None
    
    def _get_pod_health_metrics(self, namespace: str, deployment: str) -> Tuple[int, int]:
        """
        Get pod health metrics (restarts, OOMKills) for a deployment.
        
        Returns:
            (total_restarts, total_oom_kills)
        """
        if not self.k8s_available or not self.core_v1:
            return 0, 0
        
        try:
            # Get pods for this deployment
            pods = self.core_v1.list_namespaced_pod(
                namespace,
                label_selector=f"app={deployment}"
            )
            
            total_restarts = 0
            total_oom_kills = 0
            
            for pod in pods.items:
                if pod.status.container_statuses:
                    for cs in pod.status.container_statuses:
                        total_restarts += cs.restart_count or 0
                        
                        # Check for OOMKilled
                        if cs.last_state and cs.last_state.terminated:
                            if cs.last_state.terminated.reason == 'OOMKilled':
                                total_oom_kills += 1
            
            return total_restarts, total_oom_kills
            
        except Exception as e:
            logger.debug(f"Failed to get pod health metrics: {e}")
            return 0, 0
    
    def check_health(self, namespace: str, deployment: str) -> Optional[HealthCheckResult]:
        """
        Check deployment health and compare with snapshot.
        
        Args:
            namespace: Deployment namespace
            deployment: Deployment name
        
        Returns:
            HealthCheckResult or None if no snapshot exists
        """
        key = f"{namespace}/{deployment}"
        
        snapshot = self.snapshots.get(key)
        if not snapshot:
            return None
        
        if not self.k8s_available:
            return None
        
        try:
            # Get current deployment status
            dep = self.apps_v1.read_namespaced_deployment(deployment, namespace)
            ready_replicas = dep.status.ready_replicas or 0
            total_replicas = dep.status.replicas or 0
            
            # Get current pod health
            pod_restarts, oom_kills = self._get_pod_health_metrics(namespace, deployment)
            
            # Calculate changes
            restart_increase = pod_restarts - snapshot.pod_restarts
            oom_increase = oom_kills - snapshot.oom_kills
            
            # Calculate readiness drop
            if snapshot.ready_replicas > 0:
                readiness_drop = ((snapshot.ready_replicas - ready_replicas) / snapshot.ready_replicas) * 100
            else:
                readiness_drop = 0 if ready_replicas >= total_replicas else 100
            
            # Determine health status
            issues = []
            is_healthy = True
            
            if restart_increase > self.max_restart_increase:
                issues.append(f"Pod restarts increased by {restart_increase} (max: {self.max_restart_increase})")
                is_healthy = False
            
            if oom_increase > self.max_oom_increase:
                issues.append(f"OOMKills increased by {oom_increase} (max: {self.max_oom_increase})")
                is_healthy = False
            
            if readiness_drop > self.max_readiness_drop_percent:
                issues.append(f"Readiness dropped by {readiness_drop:.1f}% (max: {self.max_readiness_drop_percent}%)")
                is_healthy = False
            
            result = HealthCheckResult(
                namespace=namespace,
                deployment=deployment,
                pod_restarts=pod_restarts,
                oom_kills=oom_kills,
                ready_replicas=ready_replicas,
                total_replicas=total_replicas,
                error_rate=0.0,  # TODO: integrate with metrics
                restart_increase=restart_increase,
                oom_increase=oom_increase,
                readiness_drop=int(readiness_drop),
                is_healthy=is_healthy,
                issues=issues
            )
            
            if not is_healthy:
                logger.warning(f"{key} - Health check failed: {', '.join(issues)}")
            else:
                logger.debug(f"{key} - Health check passed")
            
            return result
            
        except Exception as e:
            logger.error(f"{key} - Health check failed: {e}")
            return None
    
    def start_health_monitor(self, namespace: str, deployment: str):
        """
        Start monitoring deployment health after autopilot changes.
        Will auto-rollback if health degrades.
        
        Args:
            namespace: Deployment namespace
            deployment: Deployment name
        """
        if not self.enable_auto_rollback:
            return
        
        key = f"{namespace}/{deployment}"
        monitor_until = datetime.now() + timedelta(minutes=self.rollback_monitor_minutes)
        self.pending_monitors[key] = monitor_until
        
        logger.info(f"{key} - Health monitoring started for {self.rollback_monitor_minutes} minutes")
        
        # Start background monitor thread if not running
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._stop_monitor.clear()
            self._monitor_thread = threading.Thread(target=self._health_monitor_loop, daemon=True)
            self._monitor_thread.start()
    
    def _health_monitor_loop(self):
        """Background thread that monitors deployment health and triggers rollbacks."""
        logger.info("Autopilot health monitor thread started")
        
        while not self._stop_monitor.is_set():
            try:
                now = datetime.now()
                keys_to_remove = []
                
                for key, monitor_until in list(self.pending_monitors.items()):
                    if now > monitor_until:
                        # Monitoring period ended, remove from pending
                        keys_to_remove.append(key)
                        logger.info(f"{key} - Health monitoring completed successfully")
                        
                        # Clean up snapshot
                        if key in self.snapshots:
                            del self.snapshots[key]
                        continue
                    
                    # Check health
                    namespace, deployment = key.split('/')
                    health = self.check_health(namespace, deployment)
                    
                    if health and not health.is_healthy:
                        # Trigger auto-rollback
                        logger.warning(f"{key} - Health degraded, triggering auto-rollback")
                        reason = f"Auto-rollback: {', '.join(health.issues)}"
                        
                        success = self.auto_rollback(namespace, deployment, reason, health)
                        
                        if success:
                            keys_to_remove.append(key)
                            
                            # Record in rollback history
                            self.rollback_history.append({
                                'key': key,
                                'reason': reason,
                                'issues': health.issues,
                                'timestamp': now.isoformat(),
                                'restart_increase': health.restart_increase,
                                'oom_increase': health.oom_increase,
                                'readiness_drop': health.readiness_drop
                            })
                
                # Remove completed monitors
                for key in keys_to_remove:
                    if key in self.pending_monitors:
                        del self.pending_monitors[key]
                
                # Sleep before next check (every 30 seconds)
                time_module.sleep(30)
                
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                time_module.sleep(30)
        
        logger.info("Autopilot health monitor thread stopped")
    
    def auto_rollback(
        self,
        namespace: str,
        deployment: str,
        reason: str,
        health: HealthCheckResult
    ) -> bool:
        """
        Automatically rollback to snapshot state.
        
        Args:
            namespace: Deployment namespace
            deployment: Deployment name
            reason: Reason for rollback
            health: Health check result that triggered rollback
        
        Returns:
            True if rollback successful
        """
        key = f"{namespace}/{deployment}"
        snapshot = self.snapshots.get(key)
        
        if not snapshot:
            logger.error(f"{key} - Cannot auto-rollback: no snapshot found")
            return False
        
        if not self.k8s_available:
            logger.error(f"{key} - Cannot auto-rollback: K8s not available")
            return False
        
        try:
            # Get current deployment
            dep = self.apps_v1.read_namespaced_deployment(deployment, namespace)
            containers = dep.spec.template.spec.containers
            if not containers:
                return False
            
            container = containers[0]
            
            # Build rollback patch
            patch = {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [{
                                "name": container.name,
                                "resources": {
                                    "requests": {
                                        "cpu": f"{snapshot.cpu_request}m",
                                        "memory": f"{snapshot.memory_request}Mi"
                                    }
                                }
                            }]
                        }
                    }
                }
            }
            
            # Apply rollback
            self.apps_v1.patch_namespaced_deployment(deployment, namespace, patch)
            
            # Mark recent actions as rolled back
            for action in reversed(self.actions):
                if action.namespace == namespace and action.deployment == deployment and not action.rolled_back:
                    action.rolled_back = True
                    action.rollback_reason = reason
            
            # Record rollback action
            self.actions.append(AutopilotAction(
                namespace=namespace,
                deployment=deployment,
                action_type='auto_rollback',
                old_value=0,  # Current value (varies)
                new_value=snapshot.cpu_request,  # Snapshot value
                reason=reason,
                applied_at=datetime.now()
            ))
            
            # Clear cooldown
            if key in self.last_action_time:
                del self.last_action_time[key]
            
            # Clean up snapshot
            if key in self.snapshots:
                del self.snapshots[key]
            
            logger.warning(
                f"⚠️ {key} - AUTO-ROLLBACK executed: "
                f"Restored CPU={snapshot.cpu_request}m, Memory={snapshot.memory_request}Mi. "
                f"Reason: {reason}"
            )
            
            # Send webhook notification
            self._send_notification(
                title=f"⚠️ Autopilot Auto-Rollback: {key}",
                message=f"Resources automatically rolled back due to health issues",
                severity="critical",
                fields={
                    "Deployment": key,
                    "Reason": reason,
                    "Issues": ", ".join(health.issues) if health.issues else "Health degraded",
                    "Restored CPU": f"{snapshot.cpu_request}m",
                    "Restored Memory": f"{snapshot.memory_request}Mi",
                    "Restart Increase": str(health.restart_increase),
                    "OOM Increase": str(health.oom_increase)
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"{key} - Auto-rollback failed: {e}")
            return False
    
    def stop_health_monitor(self):
        """Stop the background health monitor thread."""
        self._stop_monitor.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
    
    def get_rollback_history(self, limit: int = 20) -> List[Dict]:
        """Get recent auto-rollback history."""
        return self.rollback_history[-limit:]
    
    def get_pending_monitors(self) -> List[Dict]:
        """Get list of deployments currently being monitored."""
        now = datetime.now()
        return [
            {
                'key': key,
                'minutes_remaining': max(0, (monitor_until - now).total_seconds() / 60)
            }
            for key, monitor_until in self.pending_monitors.items()
        ]
    
    # ==================== End Rollback & Health Monitoring ====================

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
            # Create snapshot BEFORE making changes (for rollback)
            if self.enable_auto_rollback and not dry_run:
                snapshot = self.create_snapshot(recommendation.namespace, recommendation.deployment)
                if not snapshot:
                    logger.warning(f"{key} - Could not create snapshot, proceeding without rollback protection")
            
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
            
            # Send webhook notification
            self._send_notification(
                title=f"🤖 Autopilot Applied: {key}",
                message=f"Resource requests updated automatically",
                severity="info",
                fields={
                    "Deployment": key,
                    "CPU": f"{recommendation.current_cpu_request}m → {recommendation.recommended_cpu_request}m",
                    "Memory": f"{recommendation.current_memory_request}Mi → {recommendation.recommended_memory_request}Mi",
                    "Confidence": f"{recommendation.confidence:.0%}",
                    "Savings": f"{recommendation.savings_percent:.1f}%",
                    "Auto-Rollback": f"Monitoring for {self.rollback_monitor_minutes} min" if self.enable_auto_rollback else "Disabled"
                }
            )
            
            # Start health monitoring for auto-rollback
            if self.enable_auto_rollback:
                self.start_health_monitor(recommendation.namespace, recommendation.deployment)
            
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
            
            # Send webhook notification
            self._send_notification(
                title=f"🔄 Autopilot Rollback: {key}",
                message=f"Resource requests rolled back",
                severity="warning",
                fields={
                    "Deployment": key,
                    "Reason": reason,
                    "CPU": f"{cpu_action.new_value}m → {cpu_action.old_value}m" if cpu_action else "N/A",
                    "Memory": f"{memory_action.new_value}Mi → {memory_action.old_value}Mi" if memory_action else "N/A"
                }
            )
            
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
        auto_rollback_count = sum(1 for a in self.actions if a.action_type == 'auto_rollback')
        
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
            'rollback_config': {
                'enabled': self.enable_auto_rollback,
                'monitor_minutes': self.rollback_monitor_minutes,
                'max_restart_increase': self.max_restart_increase,
                'max_oom_increase': self.max_oom_increase,
                'max_readiness_drop_percent': self.max_readiness_drop_percent
            },
            'statistics': {
                'total_recommendations': len(self.recommendations),
                'pending_recommendations': pending_count,
                'total_actions': len(self.actions),
                'actions_by_type': action_counts,
                'rollbacks': rollback_count,
                'auto_rollbacks': auto_rollback_count,
                'estimated_savings_percent': total_savings
            },
            'deployments_in_cooldown': [
                {
                    'key': key,
                    'hours_remaining': max(0, self.cooldown_hours - (datetime.now() - time).total_seconds() / 3600)
                }
                for key, time in self.last_action_time.items()
                if (datetime.now() - time).total_seconds() / 3600 < self.cooldown_hours
            ],
            'pending_health_monitors': self.get_pending_monitors(),
            'recent_auto_rollbacks': self.get_rollback_history(limit=5)
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
        AUTOPILOT_ENABLE_AUTO_ROLLBACK: Enable auto-rollback on health issues (default: true)
        AUTOPILOT_ROLLBACK_MONITOR_MINUTES: Minutes to monitor after changes (default: 10)
        AUTOPILOT_MAX_RESTART_INCREASE: Max pod restart increase before rollback (default: 2)
        AUTOPILOT_MAX_OOM_INCREASE: Max OOMKill increase before rollback (default: 1)
        AUTOPILOT_MAX_READINESS_DROP_PERCENT: Max readiness drop % before rollback (default: 20)
    
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
        memory_buffer_percent=float(os.getenv('AUTOPILOT_MEMORY_BUFFER_PERCENT', '25')),
        # Rollback configuration
        enable_auto_rollback=os.getenv('AUTOPILOT_ENABLE_AUTO_ROLLBACK', 'true').lower() == 'true',
        rollback_monitor_minutes=int(os.getenv('AUTOPILOT_ROLLBACK_MONITOR_MINUTES', '10')),
        max_restart_increase=int(os.getenv('AUTOPILOT_MAX_RESTART_INCREASE', '2')),
        max_oom_increase=int(os.getenv('AUTOPILOT_MAX_OOM_INCREASE', '1')),
        max_readiness_drop_percent=float(os.getenv('AUTOPILOT_MAX_READINESS_DROP_PERCENT', '20'))
    )
