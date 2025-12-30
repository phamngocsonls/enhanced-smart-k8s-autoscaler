"""
Smart Kubernetes Autoscaling Operator - Base Layer
Handles node-aware HPA control with spike protection
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from kubernetes import client, config
from prometheus_api_client import PrometheusConnect

try:
    from src.resilience import retry_with_backoff, CircuitBreaker, RateLimiter
except ImportError:
    # Fallback if resilience module not available
    def retry_with_backoff(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    class CircuitBreaker:
        def __init__(self, *args, **kwargs):
            pass
        def call(self, func, *args, **kwargs):
            return func(*args, **kwargs)
    
    class RateLimiter:
        def __init__(self, *args, **kwargs):
            pass
        def acquire(self):
            pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class NodeMetrics:
    """Node capacity and usage metrics"""
    total_capacity_cores: float
    total_allocatable_cores: float
    total_used_cores: float
    total_requested_cores: float
    schedulable_capacity: float
    utilization_percent: float
    pressure_level: str
    tracked_nodes: List[str]
    node_selector: Dict[str, str]


@dataclass
class HPADecision:
    """HPA target adjustment decision"""
    current_target: int
    recommended_target: int
    reason: str
    node_pressure: str
    action: str
    confidence: float
    scheduling_spike_detected: bool


class NodeCapacityAnalyzer:
    """Analyze cluster node capacity and workload"""
    
    def __init__(self, prometheus_url: str):
        self.prom = PrometheusConnect(url=prometheus_url, disable_ssl=True)
        self.apps_v1 = client.AppsV1Api()
        self.core_v1 = client.CoreV1Api()
        
        # Circuit breaker for Prometheus queries
        self.prometheus_circuit = CircuitBreaker(
            failure_threshold=5,
            timeout=60,
            name="prometheus"
        )
        
        # Rate limiter for Prometheus queries (10 queries per second)
        self.prometheus_rate_limiter = RateLimiter(
            max_calls=int(os.getenv('PROMETHEUS_RATE_LIMIT', '10')),
            time_window=1.0
        )
        
        # Rate limiter for Kubernetes API calls (20 calls per second)
        self.k8s_rate_limiter = RateLimiter(
            max_calls=int(os.getenv('K8S_API_RATE_LIMIT', '20')),
            time_window=1.0
        )
    
    def get_deployment_node_selector(self, namespace: str, deployment: str) -> Dict[str, str]:
        """Get node selector from deployment spec"""
        try:
            deployment_obj = self.apps_v1.read_namespaced_deployment(deployment, namespace)
            node_selector = deployment_obj.spec.template.spec.node_selector or {}
            
            if node_selector:
                logger.info(f"{namespace}/{deployment} - Node selector: {node_selector}")
            else:
                logger.info(f"{namespace}/{deployment} - No node selector (any node)")
            
            return node_selector
        except Exception as e:
            logger.error(f"Failed to read node selector: {e}")
            return {}
    
    def get_matching_nodes(self, node_selector: Dict[str, str]) -> List[str]:
        """Get nodes matching the selector"""
        try:
            all_nodes = self.core_v1.list_node()
            matching_nodes = []
            
            for node in all_nodes.items:
                if node.spec.unschedulable:
                    continue
                
                is_ready = False
                if node.status.conditions:
                    for condition in node.status.conditions:
                        if condition.type == "Ready" and condition.status == "True":
                            is_ready = True
                            break
                
                if not is_ready:
                    continue
                
                if not node_selector:
                    matching_nodes.append(node.metadata.name)
                    continue
                
                node_labels = node.metadata.labels or {}
                matches = True
                
                for key, value in node_selector.items():
                    if node_labels.get(key) != value:
                        matches = False
                        break
                
                if matches:
                    matching_nodes.append(node.metadata.name)
            
            return matching_nodes
        except Exception as e:
            logger.error(f"Failed to get matching nodes: {e}")
            return []
    
    def get_deployment_cpu_request(self, namespace: str, deployment: str) -> int:
        """Read CPU request from deployment manifest"""
        try:
            deployment_obj = self.apps_v1.read_namespaced_deployment(deployment, namespace)
            containers = deployment_obj.spec.template.spec.containers
            
            if not containers:
                return 500
            
            container = containers[0]
            
            if not container.resources or not container.resources.requests:
                return 500
            
            cpu_request = container.resources.requests.get('cpu')
            if not cpu_request:
                return 500
            
            cpu_millicores = self._parse_cpu_value(cpu_request)
            logger.info(f"{namespace}/{deployment} - CPU request: {cpu_millicores}m")
            return cpu_millicores
        except Exception as e:
            logger.error(f"Failed to read CPU request: {e}")
            return 500
    
    def get_deployment_memory_request(self, namespace: str, deployment: str) -> int:
        """Read memory request from deployment manifest (returns MB)"""
        try:
            deployment_obj = self.apps_v1.read_namespaced_deployment(deployment, namespace)
            containers = deployment_obj.spec.template.spec.containers
            
            if not containers:
                return 512  # Default 512MB
            
            container = containers[0]
            
            if not container.resources or not container.resources.requests:
                return 512
            
            memory_request = container.resources.requests.get('memory')
            if not memory_request:
                return 512
            
            memory_mb = self._parse_memory_value(memory_request)
            logger.info(f"{namespace}/{deployment} - Memory request: {memory_mb}MB")
            return memory_mb
        except Exception as e:
            logger.error(f"Failed to read memory request: {e}")
            return 512
    
    def _parse_memory_value(self, memory_str: str) -> int:
        """Parse K8s memory value to MB"""
        if isinstance(memory_str, (int, float)):
            return int(memory_str / (1024 * 1024))  # Assume bytes, convert to MB
        
        memory_str = str(memory_str).strip()
        
        # Handle different units
        if memory_str.endswith('Ki'):
            return int(float(memory_str[:-2]) / 1024)
        elif memory_str.endswith('Mi'):
            return int(float(memory_str[:-2]))
        elif memory_str.endswith('Gi'):
            return int(float(memory_str[:-2]) * 1024)
        elif memory_str.endswith('Ti'):
            return int(float(memory_str[:-2]) * 1024 * 1024)
        elif memory_str.endswith('K'):
            return int(float(memory_str[:-1]) / 1000)
        elif memory_str.endswith('M'):
            return int(float(memory_str[:-1]))
        elif memory_str.endswith('G'):
            return int(float(memory_str[:-1]) * 1000)
        elif memory_str.endswith('T'):
            return int(float(memory_str[:-1]) * 1000 * 1000)
        else:
            # Try to parse as bytes
            try:
                bytes_val = int(memory_str)
                return bytes_val // (1024 * 1024)
            except ValueError:
                return 512  # Default
    
    def _parse_cpu_value(self, cpu_str: str) -> int:
        """Parse K8s CPU value to millicores"""
        if isinstance(cpu_str, (int, float)):
            return int(cpu_str * 1000)
        
        cpu_str = str(cpu_str).strip()
        
        if cpu_str.endswith('m'):
            return int(cpu_str[:-1])
        
        try:
            cores = float(cpu_str)
            return int(cores * 1000)
        except ValueError:
            return 500
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, exceptions=(Exception,))
    def _query_prometheus(self, query: str):
        """Query Prometheus with retry, circuit breaker, and rate limiting"""
        # Acquire rate limit permission
        self.prometheus_rate_limiter.acquire()
        
        def _execute_query():
            return self.prom.custom_query(query)
        
        return self.prometheus_circuit.call(_execute_query)
    
    def get_node_metrics(self, node_selector: Dict[str, str] = None) -> NodeMetrics:
        """Get node metrics with spike protection"""
        tracked_nodes = self.get_matching_nodes(node_selector or {})
        
        if not tracked_nodes:
            return NodeMetrics(0, 0, 0, 0, 0, 0, 'unknown', [], node_selector or {})
        
        node_filter = '|'.join(tracked_nodes)
        
        try:
            # Get capacity
            capacity_query = f'sum(kube_node_status_capacity{{resource="cpu",node=~"{node_filter}"}})'
            capacity_result = self._query_prometheus(capacity_query)
            total_capacity = float(capacity_result[0]['value'][1]) if capacity_result else 0
            
            # Get allocatable
            allocatable_query = f'sum(kube_node_status_allocatable{{resource="cpu",node=~"{node_filter}"}})'
            allocatable_result = self._query_prometheus(allocatable_query)
            total_allocatable = float(allocatable_result[0]['value'][1]) if allocatable_result else 0
            
            # Get usage with smoothing (10m baseline)
            usage_query = f'sum(rate(node_cpu_seconds_total{{mode!="idle",instance=~"({node_filter}):.*"}}[10m]))'
            usage_result = self._query_prometheus(usage_query)
            total_used = float(usage_result[0]['value'][1]) if usage_result else 0
            
            # Get spike (5m window)
            spike_query = f'sum(rate(node_cpu_seconds_total{{mode!="idle",instance=~"({node_filter}):.*"}}[5m]))'
            spike_result = self._query_prometheus(spike_query)
            spike_used = float(spike_result[0]['value'][1]) if spike_result else total_used
            
            # Blend: 70% smoothed + 30% spike
            blended_used = (total_used * 0.7) + (spike_used * 0.3)
            
            # Get requested
            requested_query = f'sum(kube_pod_container_resource_requests{{resource="cpu",node=~"{node_filter}"}})'
            requested_result = self._query_prometheus(requested_query)
            total_requested = float(requested_result[0]['value'][1]) if requested_result else 0
        except Exception as e:
            logger.error(f"Error querying Prometheus for node metrics: {e}")
            # Return safe defaults on error
            return NodeMetrics(0, 0, 0, 0, 0, 0, 'unknown', tracked_nodes, node_selector or {})
        
        schedulable_capacity = total_allocatable - total_requested
        utilization_percent = (blended_used / total_allocatable * 100) if total_allocatable > 0 else 0
        
        # Determine pressure
        if utilization_percent < 65 and schedulable_capacity > total_allocatable * 0.3:
            pressure_level = 'safe'
        elif utilization_percent < 80 and schedulable_capacity > total_allocatable * 0.15:
            pressure_level = 'warning'
        else:
            pressure_level = 'critical'
        
        return NodeMetrics(
            total_capacity_cores=total_capacity,
            total_allocatable_cores=total_allocatable,
            total_used_cores=blended_used,
            total_requested_cores=total_requested,
            schedulable_capacity=schedulable_capacity,
            utilization_percent=utilization_percent,
            pressure_level=pressure_level,
            tracked_nodes=tracked_nodes,
            node_selector=node_selector or {}
        )
    
    def get_pod_cpu_usage(self, namespace: str, deployment: str, startup_window_minutes: int = 2) -> Tuple[float, int]:
        """Get pod CPU usage filtering startup spikes"""
        try:
            replica_query = f'kube_deployment_spec_replicas{{namespace="{namespace}",deployment="{deployment}"}}'
            replica_result = self._query_prometheus(replica_query)
            current_replicas = int(float(replica_result[0]['value'][1])) if replica_result else 1
            
            pod_start_query = f'kube_pod_start_time{{namespace="{namespace}",pod=~"{deployment}-.*"}}'
            pod_start_result = self._query_prometheus(pod_start_query)
            
            now = datetime.now().timestamp()
            mature_pods = []
            
            if pod_start_result:
                for pod_data in pod_start_result:
                    pod_name = pod_data['metric'].get('pod', '')
                    start_time = float(pod_data['value'][1])
                    if start_time > 0:
                        age_minutes = (now - start_time) / 60.0
                        if age_minutes > startup_window_minutes:
                            mature_pods.append(pod_name)
            
            if mature_pods:
                pod_filter = '|'.join(mature_pods)
                cpu_query = f'avg(rate(container_cpu_usage_seconds_total{{namespace="{namespace}",pod=~"{pod_filter}",container!=""}}[5m]))'
            else:
                cpu_query = f'avg(rate(container_cpu_usage_seconds_total{{namespace="{namespace}",pod=~"{deployment}-.*",container!=""}}[5m]))'
            
            cpu_result = self._query_prometheus(cpu_query)
            avg_cpu = float(cpu_result[0]['value'][1]) if cpu_result else 0
            
            return avg_cpu, current_replicas
        except Exception as e:
            logger.error(f"Error getting pod CPU usage: {e}")
            # Return safe defaults
            return 0.0, 1
    
    def get_pod_memory_usage(self, namespace: str, deployment: str, startup_window_minutes: int = 2) -> float:
        """Get pod memory usage in MB, filtering startup spikes"""
        try:
            pod_start_query = f'kube_pod_start_time{{namespace="{namespace}",pod=~"{deployment}-.*"}}'
            pod_start_result = self._query_prometheus(pod_start_query)
            
            now = datetime.now().timestamp()
            mature_pods = []
            
            if pod_start_result:
                for pod_data in pod_start_result:
                    pod_name = pod_data['metric'].get('pod', '')
                    start_time = float(pod_data['value'][1])
                    if start_time > 0:
                        age_minutes = (now - start_time) / 60.0
                        if age_minutes > startup_window_minutes:
                            mature_pods.append(pod_name)
            
            if mature_pods:
                pod_filter = '|'.join(mature_pods)
                memory_query = f'avg(container_memory_working_set_bytes{{namespace="{namespace}",pod=~"{pod_filter}",container!=""}})'
            else:
                memory_query = f'avg(container_memory_working_set_bytes{{namespace="{namespace}",pod=~"{deployment}-.*",container!=""}})'
            
            memory_result = self._query_prometheus(memory_query)
            avg_memory_bytes = float(memory_result[0]['value'][1]) if memory_result else 0
            
            # Convert bytes to MB
            return avg_memory_bytes / (1024 * 1024)
        except Exception as e:
            logger.error(f"Error getting pod memory usage: {e}")
            return 0.0


class DynamicHPAController:
    """Controls HPA targets dynamically"""
    
    def __init__(self, prometheus_url: str, dry_run: bool = False):
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
        
        self.autoscaling_v2 = client.AutoscalingV2Api()
        self.core_v1 = client.CoreV1Api()
        self.analyzer = NodeCapacityAnalyzer(prometheus_url)
        self.dry_run = dry_run
        self.last_decisions: Dict[str, HPADecision] = {}
        self.last_adjustment_time: Dict[str, datetime] = {}
    
    def detect_recent_scheduling(self, namespace: str, deployment: str) -> bool:
        """Detect recent pod scheduling"""
        try:
            label_selector = self._get_deployment_label_selector(namespace, deployment)
            pods = self.core_v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=label_selector
            )
            
            if not pods.items:
                return False
            
            now = datetime.now(pods.items[0].status.start_time.tzinfo) if pods.items[0].status.start_time else datetime.now()
            recent_threshold = timedelta(minutes=3)
            
            recent_pods = 0
            for pod in pods.items:
                if pod.status.start_time:
                    age = now - pod.status.start_time
                    if age < recent_threshold:
                        recent_pods += 1
            
            if recent_pods > 0:
                logger.info(f"{deployment} - Detected {recent_pods} pods started <3min ago")
                return True
            
            return False
        except Exception as e:
            logger.debug(f"Could not detect scheduling: {e}")
            return False
    
    def _get_deployment_label_selector(self, namespace: str, deployment: str) -> str:
        try:
            deployment_obj = self.analyzer.apps_v1.read_namespaced_deployment(deployment, namespace)
            match_labels = {}
            if deployment_obj and deployment_obj.spec and deployment_obj.spec.selector:
                match_labels = deployment_obj.spec.selector.match_labels or {}
            if match_labels:
                parts = [f"{k}={match_labels[k]}" for k in sorted(match_labels.keys())]
                return ",".join(parts)
        except Exception as e:
            logger.debug(f"Failed to get deployment selector labels: {e}")
        return f"app={deployment}"

    def _adjust_target_for_cpu_request(self, cpu_request_millicores: int, base_target: float) -> float:
        """
        Adjust HPA target based on CPU request size to prevent unstable scaling
        
        For very low CPU requests (< 50m), use higher targets to reduce sensitivity.
        Small absolute changes in CPU usage cause large percentage swings with tiny requests.
        
        Args:
            cpu_request_millicores: CPU request in millicores
            base_target: Base target percentage (e.g., 70%)
        
        Returns:
            Adjusted target percentage
        """
        if cpu_request_millicores < 50:
            # Very low requests (20-50m): Use high target (85-90%) to reduce sensitivity
            # At 20m request, 70% = 14m threshold, which is too sensitive
            # At 20m request, 85% = 17m threshold, more stable
            adjusted = min(90.0, base_target + 15.0)
            logger.debug(
                f"Low CPU request ({cpu_request_millicores}m): "
                f"Adjusting target from {base_target:.0f}% to {adjusted:.0f}% "
                f"to prevent unstable scaling"
            )
            return adjusted
        elif cpu_request_millicores < 100:
            # Low requests (50-100m): Use medium-high target (75-85%)
            adjusted = min(85.0, base_target + 10.0)
            logger.debug(
                f"Low CPU request ({cpu_request_millicores}m): "
                f"Adjusting target from {base_target:.0f}% to {adjusted:.0f}%"
            )
            return adjusted
        elif cpu_request_millicores < 200:
            # Small requests (100-200m): Use slightly higher target (70-80%)
            adjusted = min(80.0, base_target + 5.0)
            return adjusted
        elif cpu_request_millicores > 2000:
            # Very high requests (> 2000m): Can use lower target (60-70%)
            # Large requests are less sensitive to small changes
            adjusted = max(60.0, base_target - 5.0)
            return adjusted
        else:
            # Normal requests (200-2000m): Use base target
            return base_target
    
    def calculate_hpa_target(self, namespace: str, deployment: str, hpa_name: str,
                            startup_filter_minutes: int = 2, 
                            target_node_utilization: float = 40.0) -> Optional[HPADecision]:
        """Calculate optimal HPA target"""
        
        cpu_request_millicores = self.analyzer.get_deployment_cpu_request(namespace, deployment)
        node_selector = self.analyzer.get_deployment_node_selector(namespace, deployment)
        
        # Adjust base target based on CPU request size
        adjusted_base_target = self._adjust_target_for_cpu_request(
            cpu_request_millicores, 
            target_node_utilization
        )
        
        try:
            hpa = self.autoscaling_v2.read_namespaced_horizontal_pod_autoscaler(hpa_name, namespace)
            if not hpa.spec.metrics or len(hpa.spec.metrics) == 0:
                logger.error(f"HPA {hpa_name} has no metrics configured")
                return None
            current_target = hpa.spec.metrics[0].resource.target.average_utilization
        except Exception as e:
            logger.error(f"Failed to read HPA: {e}")
            return None
        
        node_metrics = self.analyzer.get_node_metrics(node_selector)
        avg_cpu_per_pod, current_replicas = self.analyzer.get_pod_cpu_usage(
            namespace, deployment, startup_filter_minutes
        )
        
        cpu_request_cores = cpu_request_millicores / 1000.0
        pod_cpu_utilization = (avg_cpu_per_pod / cpu_request_cores * 100) if cpu_request_cores > 0 else 0
        
        scheduling_spike_detected = self.detect_recent_scheduling(namespace, deployment)
        
        logger.info(f"{deployment} - Tracking {len(node_metrics.tracked_nodes)} nodes")
        logger.info(
            f"{deployment} - Node: {node_metrics.utilization_percent:.1f}%, "
            f"Pod CPU: {avg_cpu_per_pod:.3f} cores ({pod_cpu_utilization:.1f}% of {cpu_request_millicores}m request), "
            f"Pressure: {node_metrics.pressure_level}"
            f"{' [SPIKE]' if scheduling_spike_detected else ''}"
        )
        
        recommended_target = current_target
        reason = ""
        action = "maintain"
        confidence = 1.0
        
        # Check cooldown
        key = f"{namespace}/{deployment}"
        if key in self.last_adjustment_time:
            time_since = (datetime.now() - self.last_adjustment_time[key]).total_seconds()
            if time_since < 300:
                return HPADecision(current_target, current_target, 
                                 f"Cooldown active ({time_since:.0f}s ago)",
                                 node_metrics.pressure_level, "maintain", 1.0, False)
        
        if scheduling_spike_detected:
            confidence *= 0.5
        
        # Calculate min/max targets based on adjusted base target
        # For low CPU requests, we allow higher targets (up to 90%)
        min_target = 50 if cpu_request_millicores >= 100 else 60
        max_target = 90 if cpu_request_millicores < 100 else 85
        
        if node_metrics.pressure_level == 'critical':
            if scheduling_spike_detected:
                recommended_target = max(min_target, current_target - 5)
                reason = "Critical but spike detected - conservative"
            else:
                recommended_target = max(min_target, current_target - 10)
                reason = f"Critical pressure ({node_metrics.utilization_percent:.1f}%)"
            action = "decrease"
        elif node_metrics.pressure_level == 'warning':
            if node_metrics.utilization_percent > adjusted_base_target:
                recommended_target = max(min_target + 5, current_target - 5)
                reason = f"Above target ({node_metrics.utilization_percent:.1f}% > {adjusted_base_target:.0f}%)"
                action = "decrease"
            elif node_metrics.utilization_percent < adjusted_base_target - 10:
                recommended_target = min(max_target - 5, current_target + 5)
                reason = "Below target - can optimize"
                action = "increase"
            else:
                reason = "In acceptable range"
        else:
            if pod_cpu_utilization > 80:
                reason = f"Nodes safe but pods at {pod_cpu_utilization:.1f}%"
            elif node_metrics.schedulable_capacity > node_metrics.total_allocatable_cores * 0.4:
                recommended_target = min(max_target, current_target + 5)
                reason = "Low pressure, ample capacity"
                action = "increase"
            else:
                reason = "Safe zone"
        
        # Clamp to allowed range based on CPU request size
        recommended_target = max(min_target, min(max_target, recommended_target))
        
        # Log adjustment if different from base
        if adjusted_base_target != target_node_utilization:
            logger.info(
                f"{deployment} - CPU request {cpu_request_millicores}m: "
                f"Using adjusted target {adjusted_base_target:.0f}% "
                f"(base: {target_node_utilization:.0f}%) to prevent unstable scaling"
            )
        
        decision = HPADecision(
            current_target=current_target,
            recommended_target=recommended_target,
            reason=reason,
            node_pressure=node_metrics.pressure_level,
            action=action,
            confidence=confidence,
            scheduling_spike_detected=scheduling_spike_detected
        )
        
        self.last_decisions[key] = decision
        return decision
    
    def apply_hpa_target(self, namespace: str, hpa_name: str, decision: HPADecision):
        """Apply HPA target"""
        
        if decision.current_target == decision.recommended_target:
            logger.info(f"{hpa_name} - No change needed")
            return
        
        if decision.confidence < 0.6:
            logger.info(f"{hpa_name} - Low confidence ({decision.confidence:.0%}), skipping")
            return
        
        try:
            hpa = self.autoscaling_v2.read_namespaced_horizontal_pod_autoscaler(hpa_name, namespace)
            if not hpa.spec.metrics or len(hpa.spec.metrics) == 0:
                logger.error(f"HPA {hpa_name} has no metrics configured, cannot update")
                return
            hpa.spec.metrics[0].resource.target.average_utilization = decision.recommended_target
            
            if not hpa.spec.behavior:
                hpa.spec.behavior = client.V2HorizontalPodAutoscalerBehavior()
            
            if decision.node_pressure == 'critical' and not decision.scheduling_spike_detected:
                scale_up_stabilization = 30
                scale_up_percent = 100
            elif decision.node_pressure == 'warning':
                scale_up_stabilization = 60
                scale_up_percent = 50
            else:
                scale_up_stabilization = 120
                scale_up_percent = 30
            
            hpa.spec.behavior.scale_up = client.V2HPAScalingRules(
                stabilization_window_seconds=scale_up_stabilization,
                policies=[client.V2HPAScalingPolicy(type="Percent", value=scale_up_percent, period_seconds=60)]
            )
            
            hpa.spec.behavior.scale_down = client.V2HPAScalingRules(
                stabilization_window_seconds=300,
                policies=[client.V2HPAScalingPolicy(type="Percent", value=10, period_seconds=60)]
            )
            
            if not self.dry_run:
                self.autoscaling_v2.patch_namespaced_horizontal_pod_autoscaler(hpa_name, namespace, hpa)
                key = f"{namespace}/{hpa_name.replace('-hpa', '')}"
                self.last_adjustment_time[key] = datetime.now()
                logger.info(f"✓ Updated {hpa_name}: {decision.current_target}% -> {decision.recommended_target}% "
                          f"(Confidence: {decision.confidence:.0%}, {decision.reason})")
            else:
                logger.info(f"[DRY RUN] Would update {hpa_name}: {decision.current_target}% -> {decision.recommended_target}%")
        except Exception as e:
            logger.error(f"Failed to update HPA: {e}")
