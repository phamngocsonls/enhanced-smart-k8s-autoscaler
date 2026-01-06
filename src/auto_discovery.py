"""
Auto-Discovery Module
Automatically discovers deployments with HPAs via Kubernetes annotations.

Supported Annotations on HPA or Deployment:
- smart-autoscaler.io/enabled: "true"          # Enable auto-discovery
- smart-autoscaler.io/priority: "high"         # Priority: critical, high, medium, low, best_effort
- smart-autoscaler.io/startup-filter: "2"      # Startup filter in minutes

Example HPA annotation:
  apiVersion: autoscaling/v2
  kind: HorizontalPodAutoscaler
  metadata:
    name: my-app-hpa
    annotations:
      smart-autoscaler.io/enabled: "true"
      smart-autoscaler.io/priority: "high"
  spec:
    scaleTargetRef:
      apiVersion: apps/v1
      kind: Deployment
      name: my-app
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from kubernetes import client, watch

logger = logging.getLogger(__name__)

# Annotation keys
ANNOTATION_PREFIX = "smart-autoscaler.io"
ANNOTATION_ENABLED = f"{ANNOTATION_PREFIX}/enabled"
ANNOTATION_PRIORITY = f"{ANNOTATION_PREFIX}/priority"
ANNOTATION_STARTUP_FILTER = f"{ANNOTATION_PREFIX}/startup-filter"


@dataclass
class DiscoveredWorkload:
    """A workload discovered via annotations"""
    namespace: str
    deployment: str
    hpa_name: str
    priority: str = "medium"
    startup_filter_minutes: int = 2
    source: str = "annotation"  # annotation or config


class AutoDiscovery:
    """
    Auto-discovers deployments with HPAs via Kubernetes annotations.
    
    Watches for:
    1. HPAs with smart-autoscaler.io/enabled: "true" annotation
    2. Deployments with smart-autoscaler.io/enabled: "true" annotation (if HPA exists)
    """
    
    def __init__(self, namespaces: List[str] = None, watch_all_namespaces: bool = True):
        """
        Initialize auto-discovery.
        
        Args:
            namespaces: List of namespaces to watch (if not watching all)
            watch_all_namespaces: If True, watch all namespaces
        """
        self.namespaces = namespaces or []
        self.watch_all_namespaces = watch_all_namespaces
        self.discovered_workloads: Dict[str, DiscoveredWorkload] = {}
        
        # Callbacks for workload changes
        self.on_workload_added: Optional[Callable[[DiscoveredWorkload], None]] = None
        self.on_workload_removed: Optional[Callable[[str], None]] = None
        
        # Watch threads
        self.hpa_watch_thread: Optional[threading.Thread] = None
        self.stop_watching = threading.Event()
        
        # Kubernetes clients
        try:
            from kubernetes import config as k8s_config
            try:
                k8s_config.load_incluster_config()
            except:
                k8s_config.load_kube_config()
            
            self.autoscaling_v2 = client.AutoscalingV2Api()
            self.apps_v1 = client.AppsV1Api()
            self.core_v1 = client.CoreV1Api()
            self.k8s_available = True
            logger.info("Auto-discovery: Kubernetes client initialized")
        except Exception as e:
            logger.warning(f"Auto-discovery: Kubernetes client not available: {e}")
            self.k8s_available = False
            self.autoscaling_v2 = None
            self.apps_v1 = None
            self.core_v1 = None
    
    def discover_all(self) -> List[DiscoveredWorkload]:
        """
        Perform initial discovery of all annotated workloads.
        Returns list of discovered workloads.
        """
        if not self.k8s_available:
            logger.warning("Auto-discovery: Kubernetes not available")
            return []
        
        discovered = []
        
        try:
            # Get all HPAs
            if self.watch_all_namespaces:
                hpas = self.autoscaling_v2.list_horizontal_pod_autoscaler_for_all_namespaces()
            else:
                hpas = []
                for ns in self.namespaces:
                    try:
                        ns_hpas = self.autoscaling_v2.list_namespaced_horizontal_pod_autoscaler(ns)
                        hpas.extend(ns_hpas.items)
                    except Exception as e:
                        logger.warning(f"Failed to list HPAs in namespace {ns}: {e}")
                
                # Convert to object with items attribute for consistency
                class HPAList:
                    def __init__(self, items):
                        self.items = items
                hpas = HPAList(hpas)
            
            for hpa in hpas.items:
                workload = self._check_hpa_annotations(hpa)
                if workload:
                    key = f"{workload.namespace}/{workload.deployment}"
                    self.discovered_workloads[key] = workload
                    discovered.append(workload)
                    logger.info(f"Auto-discovered: {key} (priority: {workload.priority})")
            
            logger.info(f"Auto-discovery complete: {len(discovered)} workloads found")
            
        except Exception as e:
            logger.error(f"Auto-discovery failed: {e}", exc_info=True)
        
        return discovered
    
    def _check_hpa_annotations(self, hpa) -> Optional[DiscoveredWorkload]:
        """Check if HPA has auto-discovery annotations enabled."""
        annotations = hpa.metadata.annotations or {}
        
        # Check if enabled
        enabled = annotations.get(ANNOTATION_ENABLED, "").lower() == "true"
        if not enabled:
            return None
        
        # Get target deployment
        target_ref = hpa.spec.scale_target_ref
        if target_ref.kind != "Deployment":
            logger.debug(f"HPA {hpa.metadata.name} targets {target_ref.kind}, skipping")
            return None
        
        # Get priority (default: medium)
        priority = annotations.get(ANNOTATION_PRIORITY, "medium").lower()
        if priority not in ["critical", "high", "medium", "low", "best_effort"]:
            logger.warning(f"Invalid priority '{priority}' for HPA {hpa.metadata.name}, using 'medium'")
            priority = "medium"
        
        # Get startup filter (default: 2 minutes)
        try:
            startup_filter = int(annotations.get(ANNOTATION_STARTUP_FILTER, "2"))
        except ValueError:
            startup_filter = 2
        
        return DiscoveredWorkload(
            namespace=hpa.metadata.namespace,
            deployment=target_ref.name,
            hpa_name=hpa.metadata.name,
            priority=priority,
            startup_filter_minutes=startup_filter,
            source="annotation"
        )
    
    def _check_deployment_annotations(self, deployment) -> Optional[DiscoveredWorkload]:
        """Check if Deployment has auto-discovery annotations and an HPA."""
        annotations = deployment.metadata.annotations or {}
        
        # Check if enabled
        enabled = annotations.get(ANNOTATION_ENABLED, "").lower() == "true"
        if not enabled:
            return None
        
        namespace = deployment.metadata.namespace
        deployment_name = deployment.metadata.name
        
        # Check if HPA exists for this deployment
        try:
            hpas = self.autoscaling_v2.list_namespaced_horizontal_pod_autoscaler(namespace)
            for hpa in hpas.items:
                target_ref = hpa.spec.scale_target_ref
                if target_ref.kind == "Deployment" and target_ref.name == deployment_name:
                    # Found matching HPA
                    priority = annotations.get(ANNOTATION_PRIORITY, "medium").lower()
                    if priority not in ["critical", "high", "medium", "low", "best_effort"]:
                        priority = "medium"
                    
                    try:
                        startup_filter = int(annotations.get(ANNOTATION_STARTUP_FILTER, "2"))
                    except ValueError:
                        startup_filter = 2
                    
                    return DiscoveredWorkload(
                        namespace=namespace,
                        deployment=deployment_name,
                        hpa_name=hpa.metadata.name,
                        priority=priority,
                        startup_filter_minutes=startup_filter,
                        source="annotation"
                    )
        except Exception as e:
            logger.debug(f"Failed to check HPA for deployment {namespace}/{deployment_name}: {e}")
        
        return None
    
    def start_watching(self):
        """Start watching for HPA changes."""
        if not self.k8s_available:
            logger.warning("Auto-discovery: Cannot start watching, Kubernetes not available")
            return
        
        if self.hpa_watch_thread and self.hpa_watch_thread.is_alive():
            logger.warning("Auto-discovery: Watch already running")
            return
        
        self.stop_watching.clear()
        self.hpa_watch_thread = threading.Thread(
            target=self._watch_hpas,
            daemon=True,
            name="auto-discovery-watcher"
        )
        self.hpa_watch_thread.start()
        logger.info("Auto-discovery: Started watching for HPA changes")
    
    def stop_watching_hpas(self):
        """Stop watching for HPA changes."""
        if self.hpa_watch_thread and self.hpa_watch_thread.is_alive():
            logger.info("Auto-discovery: Stopping watch...")
            self.stop_watching.set()
            self.hpa_watch_thread.join(timeout=5)
            logger.info("Auto-discovery: Watch stopped")
    
    def _watch_hpas(self):
        """Watch HPAs for changes."""
        w = watch.Watch()
        
        while not self.stop_watching.is_set():
            try:
                logger.info("Auto-discovery: Starting HPA watch")
                
                if self.watch_all_namespaces:
                    stream = w.stream(
                        self.autoscaling_v2.list_horizontal_pod_autoscaler_for_all_namespaces,
                        timeout_seconds=60
                    )
                else:
                    # Watch specific namespaces (simplified - just watch first namespace)
                    if self.namespaces:
                        stream = w.stream(
                            self.autoscaling_v2.list_namespaced_horizontal_pod_autoscaler,
                            namespace=self.namespaces[0],
                            timeout_seconds=60
                        )
                    else:
                        time.sleep(60)
                        continue
                
                for event in stream:
                    if self.stop_watching.is_set():
                        break
                    
                    event_type = event['type']
                    hpa = event['object']
                    
                    if event_type in ['ADDED', 'MODIFIED']:
                        workload = self._check_hpa_annotations(hpa)
                        if workload:
                            key = f"{workload.namespace}/{workload.deployment}"
                            is_new = key not in self.discovered_workloads
                            self.discovered_workloads[key] = workload
                            
                            if is_new:
                                logger.info(f"Auto-discovery: New workload {key}")
                                if self.on_workload_added:
                                    try:
                                        self.on_workload_added(workload)
                                    except Exception as e:
                                        logger.error(f"Error in on_workload_added callback: {e}")
                        else:
                            # Check if this HPA was previously discovered and now disabled
                            target_ref = hpa.spec.scale_target_ref
                            if target_ref.kind == "Deployment":
                                key = f"{hpa.metadata.namespace}/{target_ref.name}"
                                if key in self.discovered_workloads:
                                    # Annotation removed, remove from discovered
                                    del self.discovered_workloads[key]
                                    logger.info(f"Auto-discovery: Workload {key} disabled")
                                    if self.on_workload_removed:
                                        try:
                                            self.on_workload_removed(key)
                                        except Exception as e:
                                            logger.error(f"Error in on_workload_removed callback: {e}")
                    
                    elif event_type == 'DELETED':
                        target_ref = hpa.spec.scale_target_ref
                        if target_ref.kind == "Deployment":
                            key = f"{hpa.metadata.namespace}/{target_ref.name}"
                            if key in self.discovered_workloads:
                                del self.discovered_workloads[key]
                                logger.info(f"Auto-discovery: Workload {key} removed (HPA deleted)")
                                if self.on_workload_removed:
                                    try:
                                        self.on_workload_removed(key)
                                    except Exception as e:
                                        logger.error(f"Error in on_workload_removed callback: {e}")
            
            except Exception as e:
                if not self.stop_watching.is_set():
                    logger.error(f"Auto-discovery watch error: {e}")
                    logger.info("Auto-discovery: Retrying in 10 seconds...")
                    time.sleep(10)
        
        logger.info("Auto-discovery: Watch stopped")
    
    def get_discovered_workloads(self) -> Dict[str, DiscoveredWorkload]:
        """Get all discovered workloads."""
        return self.discovered_workloads.copy()
    
    def is_workload_discovered(self, namespace: str, deployment: str) -> bool:
        """Check if a workload was discovered via annotations."""
        key = f"{namespace}/{deployment}"
        return key in self.discovered_workloads
