"""
Degraded Mode Handler
Allows operator to continue functioning when external services are unavailable
"""

import logging
import time
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class CachedMetrics:
    """Cached metrics for degraded mode"""
    node_utilization: float
    pod_count: int
    pod_cpu_usage: float
    hpa_target: float
    timestamp: datetime
    ttl_seconds: int = 300  # 5 minutes default TTL
    
    def is_expired(self) -> bool:
        """Check if cached data is expired"""
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > self.ttl_seconds
    
    def age_seconds(self) -> float:
        """Get age of cached data in seconds"""
        return (datetime.now() - self.timestamp).total_seconds()


class DegradedModeHandler:
    """
    Handle degraded mode operations when external services are unavailable.
    
    Features:
    - Cache last known good metrics
    - Fallback to safe defaults
    - Automatic recovery when services return
    - Configurable TTL for cached data
    """
    
    def __init__(self, cache_ttl: int = 300):
        """
        Initialize degraded mode handler.
        
        Args:
            cache_ttl: Time-to-live for cached metrics in seconds (default: 5 minutes)
        """
        self.cache_ttl = cache_ttl
        self.metrics_cache: Dict[str, CachedMetrics] = {}
        self.service_status: Dict[str, ServiceStatus] = {
            'prometheus': ServiceStatus.HEALTHY,
            'kubernetes': ServiceStatus.HEALTHY,
            'database': ServiceStatus.HEALTHY
        }
        self.failure_counts: Dict[str, int] = {
            'prometheus': 0,
            'kubernetes': 0,
            'database': 0
        }
        self.last_failure_time: Dict[str, Optional[datetime]] = {
            'prometheus': None,
            'kubernetes': None,
            'database': None
        }
        
        # Thresholds
        self.failure_threshold = 3  # Mark as degraded after 3 failures
        self.recovery_threshold = 2  # Mark as healthy after 2 successes
        self.success_counts: Dict[str, int] = {
            'prometheus': 0,
            'kubernetes': 0,
            'database': 0
        }
    
    def cache_metrics(self, deployment: str, metrics: Dict[str, Any]):
        """
        Cache metrics for a deployment.
        
        Args:
            deployment: Deployment name
            metrics: Metrics dictionary
        """
        cached = CachedMetrics(
            node_utilization=metrics.get('node_utilization', 70.0),
            pod_count=metrics.get('pod_count', 1),
            pod_cpu_usage=metrics.get('pod_cpu_usage', 0.5),
            hpa_target=metrics.get('hpa_target', 70.0),
            timestamp=datetime.now(),
            ttl_seconds=self.cache_ttl
        )
        
        self.metrics_cache[deployment] = cached
        logger.debug(f"Cached metrics for {deployment}")
    
    def get_cached_metrics(self, deployment: str) -> Optional[CachedMetrics]:
        """
        Get cached metrics for a deployment.
        
        Args:
            deployment: Deployment name
        
        Returns:
            Cached metrics if available and not expired, None otherwise
        """
        if deployment not in self.metrics_cache:
            return None
        
        cached = self.metrics_cache[deployment]
        
        if cached.is_expired():
            logger.warning(
                f"Cached metrics for {deployment} expired "
                f"(age: {cached.age_seconds():.0f}s, TTL: {cached.ttl_seconds}s)"
            )
            return None
        
        logger.info(
            f"Using cached metrics for {deployment} "
            f"(age: {cached.age_seconds():.0f}s)"
        )
        return cached
    
    def record_service_failure(self, service: str):
        """
        Record a service failure.
        
        Args:
            service: Service name (prometheus, kubernetes, database)
        """
        if service not in self.failure_counts:
            logger.warning(f"Unknown service: {service}")
            return
        
        self.failure_counts[service] += 1
        self.success_counts[service] = 0  # Reset success count
        self.last_failure_time[service] = datetime.now()
        
        # Update status based on failure count
        if self.failure_counts[service] >= self.failure_threshold:
            old_status = self.service_status[service]
            self.service_status[service] = ServiceStatus.UNAVAILABLE
            
            if old_status != ServiceStatus.UNAVAILABLE:
                logger.error(
                    f"🔴 Service {service} marked as UNAVAILABLE "
                    f"after {self.failure_counts[service]} consecutive failures"
                )
        elif self.failure_counts[service] > 0:
            self.service_status[service] = ServiceStatus.DEGRADED
            logger.warning(
                f"🟡 Service {service} marked as DEGRADED "
                f"({self.failure_counts[service]} failures)"
            )
    
    def record_service_success(self, service: str):
        """
        Record a service success.
        
        Args:
            service: Service name (prometheus, kubernetes, database)
        """
        if service not in self.success_counts:
            logger.warning(f"Unknown service: {service}")
            return
        
        old_status = self.service_status[service]
        self.success_counts[service] += 1
        
        # Recover if we have enough successes
        if self.success_counts[service] >= self.recovery_threshold:
            self.failure_counts[service] = 0
            self.service_status[service] = ServiceStatus.HEALTHY
            
            if old_status != ServiceStatus.HEALTHY:
                logger.info(
                    f"🟢 Service {service} recovered to HEALTHY "
                    f"after {self.success_counts[service]} consecutive successes"
                )
    
    def get_service_status(self, service: str) -> ServiceStatus:
        """Get current status of a service"""
        return self.service_status.get(service, ServiceStatus.UNAVAILABLE)
    
    def is_degraded(self) -> bool:
        """Check if any service is degraded or unavailable"""
        return any(
            status != ServiceStatus.HEALTHY 
            for status in self.service_status.values()
        )
    
    def get_overall_status(self) -> ServiceStatus:
        """Get overall system status"""
        statuses = list(self.service_status.values())
        
        if ServiceStatus.UNAVAILABLE in statuses:
            return ServiceStatus.UNAVAILABLE
        elif ServiceStatus.DEGRADED in statuses:
            return ServiceStatus.DEGRADED
        else:
            return ServiceStatus.HEALTHY
    
    def get_safe_defaults(self, deployment: str) -> Dict[str, Any]:
        """
        Get safe default values when no cached data is available.
        
        Args:
            deployment: Deployment name
        
        Returns:
            Dictionary with safe default values
        """
        logger.warning(
            f"No cached metrics available for {deployment}, "
            f"using safe defaults"
        )
        
        return {
            'node_utilization': 70.0,  # Assume moderate utilization
            'pod_count': 2,  # Assume minimum replicas
            'pod_cpu_usage': 0.5,  # Assume moderate CPU usage
            'hpa_target': 70.0,  # Use standard target
            'confidence': 0.3,  # Low confidence
            'action': 'maintain',  # Don't make changes
            'reason': 'Degraded mode - using safe defaults'
        }
    
    def should_skip_processing(self, deployment: str) -> bool:
        """
        Determine if processing should be skipped for a deployment.
        
        Args:
            deployment: Deployment name
        
        Returns:
            True if processing should be skipped
        """
        # Skip if Prometheus is unavailable and no cached data
        if self.get_service_status('prometheus') == ServiceStatus.UNAVAILABLE:
            cached = self.get_cached_metrics(deployment)
            if not cached:
                logger.warning(
                    f"Skipping {deployment} - Prometheus unavailable and no cached data"
                )
                return True
        
        # Skip if Kubernetes API is unavailable
        if self.get_service_status('kubernetes') == ServiceStatus.UNAVAILABLE:
            logger.warning(
                f"Skipping {deployment} - Kubernetes API unavailable"
            )
            return True
        
        return False
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get summary of degraded mode status"""
        return {
            'overall_status': self.get_overall_status().value,
            'is_degraded': self.is_degraded(),
            'services': {
                service: {
                    'status': status.value,
                    'failure_count': self.failure_counts[service],
                    'success_count': self.success_counts[service],
                    'last_failure': self.last_failure_time[service].isoformat() 
                                   if self.last_failure_time[service] else None
                }
                for service, status in self.service_status.items()
            },
            'cached_deployments': list(self.metrics_cache.keys()),
            'cache_ttl': self.cache_ttl
        }
    
    def clear_cache(self, deployment: Optional[str] = None):
        """
        Clear cached metrics.
        
        Args:
            deployment: Specific deployment to clear, or None to clear all
        """
        if deployment:
            if deployment in self.metrics_cache:
                del self.metrics_cache[deployment]
                logger.info(f"Cleared cache for {deployment}")
        else:
            self.metrics_cache.clear()
            logger.info("Cleared all cached metrics")
