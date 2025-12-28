"""
Configuration Loader with Hot Reload Support
Watches ConfigMap changes and reloads configuration dynamically
"""

import os
import logging
import threading
import time
from typing import Dict, List, Callable, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from kubernetes import client, watch

logger = logging.getLogger(__name__)


@dataclass
class DeploymentConfig:
    """Configuration for a watched deployment"""
    namespace: str
    deployment: str
    hpa_name: str
    startup_filter_minutes: int = 2


@dataclass
class OperatorConfig:
    """Operator configuration"""
    prometheus_url: str
    check_interval: int
    target_node_utilization: float
    dry_run: bool
    enable_predictive: bool
    enable_autotuning: bool
    cost_per_vcpu_hour: float
    cost_per_gb_memory_hour: float
    log_level: str
    log_format: str
    
    # Rate limiting
    prometheus_rate_limit: int
    k8s_api_rate_limit: int
    
    # Memory management
    memory_warning_threshold: float
    memory_critical_threshold: float
    memory_check_interval: int
    
    # Webhooks
    webhooks: Dict[str, str]
    
    # Watched deployments
    deployments: List[DeploymentConfig]


class ConfigLoader:
    """Load and hot-reload configuration from environment and ConfigMap"""
    
    def __init__(self, namespace: str = "autoscaler-system", configmap_name: str = "smart-autoscaler-config"):
        self.namespace = namespace
        self.configmap_name = configmap_name
        self.config: Optional[OperatorConfig] = None
        self.config_version: int = 0
        self.last_reload: datetime = datetime.now()
        
        # Callbacks for configuration changes
        self.reload_callbacks: List[Callable[[OperatorConfig], None]] = []
        
        # Watch thread
        self.watch_thread: Optional[threading.Thread] = None
        self.stop_watching = threading.Event()
        
        # Kubernetes client
        try:
            from kubernetes import config as k8s_config
            try:
                k8s_config.load_incluster_config()
                logger.info("Loaded in-cluster Kubernetes config")
            except:
                k8s_config.load_kube_config()
                logger.info("Loaded local Kubernetes config")
            
            self.core_v1 = client.CoreV1Api()
            self.k8s_available = True
        except Exception as e:
            logger.warning(f"Kubernetes client not available: {e}")
            self.k8s_available = False
            self.core_v1 = None
    
    def load_config(self) -> OperatorConfig:
        """Load configuration from environment variables and ConfigMap"""
        logger.info("Loading configuration...")
        
        # Load from environment first (base configuration)
        env_config = self._load_from_env()
        
        # Try to load from ConfigMap (overrides environment)
        if self.k8s_available:
            try:
                configmap_config = self._load_from_configmap()
                if configmap_config:
                    # Merge ConfigMap values into env config
                    env_config = self._merge_configs(env_config, configmap_config)
                    logger.info("Configuration loaded from ConfigMap")
            except Exception as e:
                logger.warning(f"Failed to load ConfigMap, using environment only: {e}")
        
        self.config = env_config
        self.config_version += 1
        self.last_reload = datetime.now()
        
        logger.info(
            f"Configuration loaded (version {self.config_version}): "
            f"{len(self.config.deployments)} deployments, "
            f"check_interval={self.config.check_interval}s, "
            f"predictive={self.config.enable_predictive}, "
            f"autotuning={self.config.enable_autotuning}"
        )
        
        return self.config
    
    def _load_from_env(self) -> OperatorConfig:
        """Load configuration from environment variables"""
        from src.config_validator import ConfigValidator
        
        # Core settings
        prometheus_url = ConfigValidator.validate_prometheus_url(
            os.getenv("PROMETHEUS_URL", "http://prometheus-server.monitoring:9090")
        )
        check_interval = ConfigValidator.validate_check_interval(
            os.getenv("CHECK_INTERVAL", "60")
        )
        target_node_utilization = ConfigValidator.validate_target_utilization(
            os.getenv("TARGET_NODE_UTILIZATION", "70.0")
        )
        dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
        
        # Feature flags
        enable_predictive = os.getenv("ENABLE_PREDICTIVE", "true").lower() == "true"
        enable_autotuning = os.getenv("ENABLE_AUTOTUNING", "true").lower() == "true"
        
        # Cost settings
        cost_per_vcpu_hour = ConfigValidator.validate_cost_per_vcpu(
            os.getenv("COST_PER_VCPU_HOUR", "0.04")
        )
        cost_per_gb_memory_hour = float(os.getenv("COST_PER_GB_MEMORY_HOUR", "0.004"))
        
        # Logging
        log_level = os.getenv("LOG_LEVEL", "INFO")
        log_format = os.getenv("LOG_FORMAT", "json")
        
        # Rate limiting
        prometheus_rate_limit = int(os.getenv("PROMETHEUS_RATE_LIMIT", "10"))
        k8s_api_rate_limit = int(os.getenv("K8S_API_RATE_LIMIT", "20"))
        
        # Memory management
        memory_warning_threshold = float(os.getenv("MEMORY_WARNING_THRESHOLD", "0.75"))
        memory_critical_threshold = float(os.getenv("MEMORY_CRITICAL_THRESHOLD", "0.90"))
        memory_check_interval = int(os.getenv("MEMORY_CHECK_INTERVAL", "30"))
        
        # Webhooks
        webhooks = {}
        if slack_webhook := os.getenv("SLACK_WEBHOOK"):
            webhooks["slack"] = slack_webhook
        if teams_webhook := os.getenv("TEAMS_WEBHOOK"):
            webhooks["teams"] = teams_webhook
        if discord_webhook := os.getenv("DISCORD_WEBHOOK"):
            webhooks["discord"] = discord_webhook
        if generic_webhook := os.getenv("GENERIC_WEBHOOK"):
            webhooks["generic"] = generic_webhook
        
        # Load deployments
        deployments = []
        i = 0
        while True:
            namespace = os.getenv(f"DEPLOYMENT_{i}_NAMESPACE")
            if not namespace:
                break
            
            deployment_name = os.getenv(f"DEPLOYMENT_{i}_NAME")
            if not deployment_name:
                i += 1
                continue
            
            hpa_name = os.getenv(f"DEPLOYMENT_{i}_HPA_NAME", deployment_name)
            startup_filter_str = os.getenv(f"DEPLOYMENT_{i}_STARTUP_FILTER", "2")
            
            try:
                startup_filter = ConfigValidator.validate_startup_filter(startup_filter_str)
            except ValueError:
                startup_filter = 2
            
            deployments.append(DeploymentConfig(
                namespace=namespace,
                deployment=deployment_name,
                hpa_name=hpa_name,
                startup_filter_minutes=startup_filter
            ))
            i += 1
        
        return OperatorConfig(
            prometheus_url=prometheus_url,
            check_interval=check_interval,
            target_node_utilization=target_node_utilization,
            dry_run=dry_run,
            enable_predictive=enable_predictive,
            enable_autotuning=enable_autotuning,
            cost_per_vcpu_hour=cost_per_vcpu_hour,
            cost_per_gb_memory_hour=cost_per_gb_memory_hour,
            log_level=log_level,
            log_format=log_format,
            prometheus_rate_limit=prometheus_rate_limit,
            k8s_api_rate_limit=k8s_api_rate_limit,
            memory_warning_threshold=memory_warning_threshold,
            memory_critical_threshold=memory_critical_threshold,
            memory_check_interval=memory_check_interval,
            webhooks=webhooks,
            deployments=deployments
        )
    
    def _load_from_configmap(self) -> Optional[Dict[str, Any]]:
        """Load configuration from ConfigMap"""
        if not self.k8s_available:
            return None
        
        try:
            configmap = self.core_v1.read_namespaced_config_map(
                name=self.configmap_name,
                namespace=self.namespace
            )
            
            if not configmap.data:
                return None
            
            # Parse ConfigMap data
            config_data = {}
            
            # Parse deployments from ConfigMap
            deployments = []
            i = 0
            while True:
                namespace = configmap.data.get(f"DEPLOYMENT_{i}_NAMESPACE")
                if not namespace:
                    break
                
                deployment_name = configmap.data.get(f"DEPLOYMENT_{i}_NAME")
                if not deployment_name:
                    i += 1
                    continue
                
                hpa_name = configmap.data.get(f"DEPLOYMENT_{i}_HPA_NAME", deployment_name)
                startup_filter = int(configmap.data.get(f"DEPLOYMENT_{i}_STARTUP_FILTER", "2"))
                
                deployments.append(DeploymentConfig(
                    namespace=namespace,
                    deployment=deployment_name,
                    hpa_name=hpa_name,
                    startup_filter_minutes=startup_filter
                ))
                i += 1
            
            if deployments:
                config_data['deployments'] = deployments
            
            # Parse other settings
            for key, value in configmap.data.items():
                if not key.startswith("DEPLOYMENT_"):
                    config_data[key.lower()] = value
            
            return config_data
        
        except client.exceptions.ApiException as e:
            if e.status == 404:
                logger.debug(f"ConfigMap {self.configmap_name} not found")
            else:
                logger.error(f"Error reading ConfigMap: {e}")
            return None
    
    def _merge_configs(self, base: OperatorConfig, override: Dict[str, Any]) -> OperatorConfig:
        """Merge ConfigMap values into base configuration"""
        # Create a copy of base config
        merged = OperatorConfig(
            prometheus_url=override.get('prometheus_url', base.prometheus_url),
            check_interval=int(override.get('check_interval', base.check_interval)),
            target_node_utilization=float(override.get('target_node_utilization', base.target_node_utilization)),
            dry_run=override.get('dry_run', str(base.dry_run)).lower() == 'true',
            enable_predictive=override.get('enable_predictive', str(base.enable_predictive)).lower() == 'true',
            enable_autotuning=override.get('enable_autotuning', str(base.enable_autotuning)).lower() == 'true',
            cost_per_vcpu_hour=float(override.get('cost_per_vcpu_hour', base.cost_per_vcpu_hour)),
            cost_per_gb_memory_hour=float(override.get('cost_per_gb_memory_hour', base.cost_per_gb_memory_hour)),
            log_level=override.get('log_level', base.log_level),
            log_format=override.get('log_format', base.log_format),
            prometheus_rate_limit=int(override.get('prometheus_rate_limit', base.prometheus_rate_limit)),
            k8s_api_rate_limit=int(override.get('k8s_api_rate_limit', base.k8s_api_rate_limit)),
            memory_warning_threshold=float(override.get('memory_warning_threshold', base.memory_warning_threshold)),
            memory_critical_threshold=float(override.get('memory_critical_threshold', base.memory_critical_threshold)),
            memory_check_interval=int(override.get('memory_check_interval', base.memory_check_interval)),
            webhooks=base.webhooks,  # Webhooks from env only (secrets)
            deployments=override.get('deployments', base.deployments)
        )
        
        return merged
    
    def register_reload_callback(self, callback: Callable[[OperatorConfig], None]):
        """Register a callback to be called when configuration is reloaded"""
        self.reload_callbacks.append(callback)
        logger.info(f"Registered reload callback: {callback.__name__}")
    
    def start_watching(self):
        """Start watching ConfigMap for changes"""
        if not self.k8s_available:
            logger.warning("Kubernetes not available, hot reload disabled")
            return
        
        if self.watch_thread and self.watch_thread.is_alive():
            logger.warning("ConfigMap watch already running")
            return
        
        self.stop_watching.clear()
        self.watch_thread = threading.Thread(
            target=self._watch_configmap,
            daemon=True,
            name="configmap-watcher"
        )
        self.watch_thread.start()
        logger.info(f"Started watching ConfigMap {self.namespace}/{self.configmap_name}")
    
    def stop_watching_configmap(self):
        """Stop watching ConfigMap"""
        if self.watch_thread and self.watch_thread.is_alive():
            logger.info("Stopping ConfigMap watch...")
            self.stop_watching.set()
            self.watch_thread.join(timeout=5)
            logger.info("ConfigMap watch stopped")
    
    def _watch_configmap(self):
        """Watch ConfigMap for changes and reload configuration"""
        w = watch.Watch()
        
        while not self.stop_watching.is_set():
            try:
                logger.info(f"Starting ConfigMap watch on {self.namespace}/{self.configmap_name}")
                
                for event in w.stream(
                    self.core_v1.list_namespaced_config_map,
                    namespace=self.namespace,
                    field_selector=f"metadata.name={self.configmap_name}",
                    timeout_seconds=60
                ):
                    if self.stop_watching.is_set():
                        break
                    
                    event_type = event['type']
                    configmap = event['object']
                    
                    logger.info(f"ConfigMap event: {event_type}")
                    
                    if event_type in ['MODIFIED', 'ADDED']:
                        # Reload configuration
                        logger.info("ConfigMap changed, reloading configuration...")
                        
                        try:
                            new_config = self.load_config()
                            
                            # Notify callbacks
                            for callback in self.reload_callbacks:
                                try:
                                    callback(new_config)
                                except Exception as e:
                                    logger.error(f"Error in reload callback {callback.__name__}: {e}", exc_info=True)
                            
                            logger.info(f"Configuration reloaded successfully (version {self.config_version})")
                        
                        except Exception as e:
                            logger.error(f"Failed to reload configuration: {e}", exc_info=True)
                    
                    elif event_type == 'DELETED':
                        logger.warning(f"ConfigMap {self.configmap_name} was deleted, using environment config only")
            
            except Exception as e:
                if not self.stop_watching.is_set():
                    logger.error(f"Error watching ConfigMap: {e}", exc_info=True)
                    logger.info("Retrying ConfigMap watch in 10 seconds...")
                    time.sleep(10)
        
        logger.info("ConfigMap watch stopped")
    
    def get_config(self) -> OperatorConfig:
        """Get current configuration"""
        if not self.config:
            return self.load_config()
        return self.config
    
    def get_config_version(self) -> int:
        """Get current configuration version"""
        return self.config_version
    
    def get_last_reload_time(self) -> datetime:
        """Get last reload timestamp"""
        return self.last_reload


# Global config loader instance
_config_loader: Optional[ConfigLoader] = None


def get_config_loader(namespace: str = "autoscaler-system", 
                     configmap_name: str = "smart-autoscaler-config") -> ConfigLoader:
    """Get or create global config loader instance"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader(namespace, configmap_name)
    return _config_loader
