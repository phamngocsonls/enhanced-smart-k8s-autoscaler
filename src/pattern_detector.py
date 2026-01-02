"""
Workload Pattern Detection
Detects different workload patterns and provides adaptive scaling strategies
"""

import logging
import statistics
from typing import List, Dict, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


class WorkloadPattern(Enum):
    """Types of workload patterns"""
    STEADY = "steady"  # Consistent load with low variance
    BURSTY = "bursty"  # Frequent spikes and drops
    PERIODIC = "periodic"  # Daily/weekly patterns
    GROWING = "growing"  # Steadily increasing trend
    DECLINING = "declining"  # Steadily decreasing trend
    WEEKLY_SEASONAL = "weekly_seasonal"  # Different patterns on weekdays vs weekends
    MONTHLY_SEASONAL = "monthly_seasonal"  # Monthly patterns (e.g., end of month spikes)
    EVENT_DRIVEN = "event_driven"  # Correlated with external events
    UNKNOWN = "unknown"  # Not enough data or unclear pattern


@dataclass
class PatternStrategy:
    """Scaling strategy for a workload pattern"""
    hpa_target: float
    scale_up_stabilization: int  # seconds
    scale_down_stabilization: int  # seconds
    enable_predictive: bool
    confidence_threshold: float
    description: str


@dataclass
class DeploymentCorrelation:
    """Correlation between two deployments"""
    deployment_a: str
    deployment_b: str
    correlation_coefficient: float
    lag_minutes: int  # How many minutes B lags behind A
    confidence: float
    description: str


class PatternDetector:
    """
    Detect workload patterns and provide adaptive scaling strategies.
    
    Analyzes historical metrics to identify:
    - Steady workloads (low variance)
    - Bursty workloads (high variance, frequent spikes)
    - Periodic workloads (daily/weekly patterns)
    - Growing workloads (upward trend)
    - Declining workloads (downward trend)
    - Weekly seasonal patterns (weekday vs weekend)
    - Monthly seasonal patterns (beginning/end of month)
    - Event-driven patterns (correlated with external events)
    - Cross-deployment correlations
    """
    
    def __init__(self, db):
        """
        Initialize pattern detector.
        
        Args:
            db: TimeSeriesDatabase instance
        """
        self.db = db
        
        # Pattern strategies
        # HPA targets raised to 70-80% range for stability with low CPU requests
        # Lower targets (60-65%) cause frequent scaling with small CPU fluctuations
        self.strategies = {
            WorkloadPattern.STEADY: PatternStrategy(
                hpa_target=75.0,  # Raised from 70% for stability
                scale_up_stabilization=120,
                scale_down_stabilization=300,
                enable_predictive=False,
                confidence_threshold=0.7,
                description="Consistent load - standard scaling"
            ),
            WorkloadPattern.BURSTY: PatternStrategy(
                hpa_target=70.0,  # Raised from 60% - still responsive but more stable
                scale_up_stabilization=30,  # Quick scale up
                scale_down_stabilization=600,  # Slow scale down to handle next burst
                enable_predictive=False,  # Predictions don't work well for random bursts
                confidence_threshold=0.8,  # Higher threshold to avoid false positives
                description="Frequent spikes - aggressive scale up, conservative scale down"
            ),
            WorkloadPattern.PERIODIC: PatternStrategy(
                hpa_target=75.0,  # Raised from 70%
                scale_up_stabilization=60,
                scale_down_stabilization=300,
                enable_predictive=True,  # Predictive works great for periodic patterns
                confidence_threshold=0.6,  # Can be more aggressive with predictions
                description="Daily/weekly patterns - predictive scaling enabled"
            ),
            WorkloadPattern.GROWING: PatternStrategy(
                hpa_target=75.0,  # Raised from 65% - headroom via predictive scaling instead
                scale_up_stabilization=60,
                scale_down_stabilization=600,  # Cautious scale down
                enable_predictive=True,
                confidence_threshold=0.7,
                description="Upward trend - maintain headroom, cautious scale down"
            ),
            WorkloadPattern.DECLINING: PatternStrategy(
                hpa_target=80.0,  # Raised from 75% to save more costs
                scale_up_stabilization=120,
                scale_down_stabilization=180,  # Faster scale down to save costs
                enable_predictive=False,
                confidence_threshold=0.7,
                description="Downward trend - optimize for cost savings"
            ),
            WorkloadPattern.WEEKLY_SEASONAL: PatternStrategy(
                hpa_target=75.0,  # Raised from 68%
                scale_up_stabilization=60,
                scale_down_stabilization=300,
                enable_predictive=True,
                confidence_threshold=0.65,
                description="Weekly patterns - different weekday/weekend behavior"
            ),
            WorkloadPattern.MONTHLY_SEASONAL: PatternStrategy(
                hpa_target=75.0,  # Raised from 65%
                scale_up_stabilization=60,
                scale_down_stabilization=300,
                enable_predictive=True,
                confidence_threshold=0.7,
                description="Monthly patterns - end-of-month/beginning-of-month spikes"
            ),
            WorkloadPattern.EVENT_DRIVEN: PatternStrategy(
                hpa_target=70.0,  # Raised from 60% - still fast but more stable
                scale_up_stabilization=30,
                scale_down_stabilization=300,
                enable_predictive=False,  # Events are unpredictable
                confidence_threshold=0.8,
                description="Event-driven - fast response, watch for correlated deployments"
            ),
            WorkloadPattern.UNKNOWN: PatternStrategy(
                hpa_target=75.0,  # Raised from 70% for safety
                scale_up_stabilization=90,
                scale_down_stabilization=300,
                enable_predictive=False,
                confidence_threshold=0.7,
                description="Unknown pattern - conservative defaults"
            )
        }
        
        # Cache detected patterns
        self.pattern_cache: Dict[str, tuple] = {}  # deployment -> (pattern, timestamp)
        self.cache_ttl = 3600  # Re-detect every hour
        
        # Correlation cache
        self.correlation_cache: Dict[str, List[DeploymentCorrelation]] = {}
        self.correlation_cache_ttl = 7200  # Re-calculate every 2 hours
        self.correlation_cache_time: Dict[str, datetime] = {}
        
        # Event detection
        self.event_markers: Dict[str, List[Tuple[datetime, str]]] = {}  # deployment -> [(timestamp, event_type)]
    
    def detect_pattern(self, deployment: str, hours: int = 24) -> WorkloadPattern:
        """
        Detect workload pattern for a deployment.
        
        Args:
            deployment: Deployment name
            hours: Hours of historical data to analyze
        
        Returns:
            Detected WorkloadPattern
        """
        # Check cache
        if deployment in self.pattern_cache:
            pattern, timestamp = self.pattern_cache[deployment]
            age = (datetime.now() - timestamp).total_seconds()
            if age < self.cache_ttl:
                logger.debug(f"{deployment} - Using cached pattern: {pattern.value}")
                return pattern
        
        # Get historical metrics
        metrics = self.db.get_recent_metrics(deployment, hours=hours)
        
        # Lowered from 100 to 20 for faster pattern detection
        if len(metrics) < 20:
            logger.info(f"{deployment} - Learning pattern ({len(metrics)}/20 samples collected)")
            return WorkloadPattern.UNKNOWN
        
        # Extract CPU usage values
        cpu_values = [m.pod_cpu_usage for m in metrics if m.pod_cpu_usage > 0]
        
        # Lowered from 50 to 10
        if len(cpu_values) < 10:
            logger.info(f"{deployment} - Learning pattern ({len(cpu_values)}/10 CPU samples)")
            return WorkloadPattern.UNKNOWN
        
        # Calculate statistics
        mean = statistics.mean(cpu_values)
        std = statistics.stdev(cpu_values) if len(cpu_values) > 1 else 0
        
        # Coefficient of variation (CV)
        cv = std / mean if mean > 0 else 0
        
        logger.info(
            f"{deployment} - Pattern analysis: samples={len(cpu_values)}, mean={mean:.3f}, std={std:.3f}, cv={cv:.3f}"
        )
        
        # Detect pattern based on characteristics
        pattern = self._classify_pattern(deployment, metrics, cpu_values, mean, std, cv)
        
        # Cache result
        self.pattern_cache[deployment] = (pattern, datetime.now())
        
        logger.info(f"{deployment} - Detected pattern: {pattern.value} (confidence: {self._get_pattern_confidence(len(cpu_values))}%)")
        
        return pattern
    
    def _get_pattern_confidence(self, sample_count: int) -> int:
        """
        Calculate confidence in pattern detection based on sample count.
        
        Args:
            sample_count: Number of samples analyzed
        
        Returns:
            Confidence percentage (0-100)
        """
        if sample_count < 20:
            return 30  # Low confidence
        elif sample_count < 50:
            return 60  # Medium confidence
        elif sample_count < 100:
            return 80  # Good confidence
        else:
            return 95  # High confidence
    
    def _classify_pattern(
        self,
        deployment: str,
        metrics: List,
        values: List[float],
        mean: float,
        std: float,
        cv: float
    ) -> WorkloadPattern:
        """
        Classify workload pattern based on statistical analysis.
        
        Args:
            deployment: Deployment name
            metrics: Full metrics list with timestamps
            values: CPU usage values
            mean: Mean CPU usage
            std: Standard deviation
            cv: Coefficient of variation
        
        Returns:
            Classified WorkloadPattern
        """
        # 1. Check for steady pattern (low variance)
        if cv < 0.15:  # Less than 15% variation
            logger.debug("Pattern: STEADY (low variance)")
            return WorkloadPattern.STEADY
        
        # 2. Check for bursty pattern (high variance with spikes)
        if cv > 0.5:  # More than 50% variation
            # Count spikes (values > mean + 2*std)
            spike_threshold = mean + (2 * std)
            spikes = sum(1 for v in values if v > spike_threshold)
            spike_rate = spikes / len(values)
            
            if spike_rate > 0.1:  # More than 10% of time in spike
                logger.debug(f"Pattern: BURSTY (cv={cv:.2f}, spike_rate={spike_rate:.2%})")
                return WorkloadPattern.BURSTY
        
        # 3. Check for weekly seasonal pattern
        if self._has_weekly_pattern(metrics):
            logger.debug("Pattern: WEEKLY_SEASONAL (weekday/weekend difference)")
            return WorkloadPattern.WEEKLY_SEASONAL
        
        # 4. Check for monthly seasonal pattern
        if self._has_monthly_pattern(metrics):
            logger.debug("Pattern: MONTHLY_SEASONAL (monthly cycle detected)")
            return WorkloadPattern.MONTHLY_SEASONAL
        
        # 5. Check for event-driven pattern
        if self._is_event_driven(deployment, metrics):
            logger.debug("Pattern: EVENT_DRIVEN (correlated with events)")
            return WorkloadPattern.EVENT_DRIVEN
        
        # 6. Check for periodic pattern (daily/weekly cycles)
        if self._has_periodic_pattern(values):
            logger.debug("Pattern: PERIODIC (detected cycles)")
            return WorkloadPattern.PERIODIC
        
        # 7. Check for trend (growing or declining)
        trend = self._detect_trend(values)
        if trend == "growing":
            logger.debug("Pattern: GROWING (upward trend)")
            return WorkloadPattern.GROWING
        elif trend == "declining":
            logger.debug("Pattern: DECLINING (downward trend)")
            return WorkloadPattern.DECLINING
        
        # 8. Default to steady if no clear pattern
        logger.debug("Pattern: STEADY (default)")
        return WorkloadPattern.STEADY

    def _has_weekly_pattern(self, metrics: List) -> bool:
        """
        Detect weekly patterns (different behavior on weekdays vs weekends).
        
        Args:
            metrics: List of metrics with timestamps
        
        Returns:
            True if weekly pattern detected
        """
        if len(metrics) < 168:  # Need at least 1 week of data
            return False
        
        try:
            # Group by weekday vs weekend
            weekday_values = []
            weekend_values = []
            
            for m in metrics:
                if m.pod_cpu_usage > 0:
                    day = m.timestamp.weekday()
                    if day < 5:  # Monday-Friday
                        weekday_values.append(m.pod_cpu_usage)
                    else:  # Saturday-Sunday
                        weekend_values.append(m.pod_cpu_usage)
            
            if len(weekday_values) < 20 or len(weekend_values) < 10:
                return False
            
            weekday_mean = statistics.mean(weekday_values)
            weekend_mean = statistics.mean(weekend_values)
            
            # Significant difference (>20%) between weekday and weekend
            diff_ratio = abs(weekday_mean - weekend_mean) / max(weekday_mean, weekend_mean)
            
            if diff_ratio > 0.2:
                logger.debug(f"Weekly pattern: weekday={weekday_mean:.2f}, weekend={weekend_mean:.2f}, diff={diff_ratio:.2%}")
                return True
            
            return False
        
        except Exception as e:
            logger.debug(f"Error detecting weekly pattern: {e}")
            return False
    
    def _has_monthly_pattern(self, metrics: List) -> bool:
        """
        Detect monthly patterns (e.g., end-of-month spikes).
        
        Args:
            metrics: List of metrics with timestamps
        
        Returns:
            True if monthly pattern detected
        """
        if len(metrics) < 720:  # Need at least 30 days of data
            return False
        
        try:
            # Group by day of month
            day_values: Dict[int, List[float]] = defaultdict(list)
            
            for m in metrics:
                if m.pod_cpu_usage > 0:
                    day = m.timestamp.day
                    day_values[day].append(m.pod_cpu_usage)
            
            if len(day_values) < 20:  # Need data for most days
                return False
            
            # Calculate mean for each day
            day_means = {day: statistics.mean(vals) for day, vals in day_values.items() if len(vals) >= 3}
            
            if len(day_means) < 15:
                return False
            
            overall_mean = statistics.mean(day_means.values())
            
            # Check for beginning/end of month patterns
            beginning_days = [day_means.get(d, overall_mean) for d in range(1, 6)]
            end_days = [day_means.get(d, overall_mean) for d in range(26, 32)]
            middle_days = [day_means.get(d, overall_mean) for d in range(10, 21)]
            
            beginning_mean = statistics.mean(beginning_days) if beginning_days else overall_mean
            end_mean = statistics.mean(end_days) if end_days else overall_mean
            middle_mean = statistics.mean(middle_days) if middle_days else overall_mean
            
            # Significant difference between beginning/end and middle
            beginning_diff = abs(beginning_mean - middle_mean) / middle_mean if middle_mean > 0 else 0
            end_diff = abs(end_mean - middle_mean) / middle_mean if middle_mean > 0 else 0
            
            if beginning_diff > 0.25 or end_diff > 0.25:
                logger.debug(f"Monthly pattern: beginning_diff={beginning_diff:.2%}, end_diff={end_diff:.2%}")
                return True
            
            return False
        
        except Exception as e:
            logger.debug(f"Error detecting monthly pattern: {e}")
            return False
    
    def _is_event_driven(self, deployment: str, metrics: List) -> bool:
        """
        Detect if workload is event-driven (sudden spikes followed by decay).
        
        Args:
            deployment: Deployment name
            metrics: List of metrics
        
        Returns:
            True if event-driven pattern detected
        """
        if len(metrics) < 50:
            return False
        
        try:
            values = [m.pod_cpu_usage for m in metrics if m.pod_cpu_usage > 0]
            if len(values) < 30:
                return False
            
            mean = statistics.mean(values)
            std = statistics.stdev(values)
            
            # Count sudden spikes (>3 std from mean)
            spike_threshold = mean + (3 * std)
            
            # Look for spike-decay patterns
            spike_decay_count = 0
            i = 0
            while i < len(values) - 5:
                if values[i] > spike_threshold:
                    # Check if followed by decay
                    decay = True
                    for j in range(1, min(5, len(values) - i)):
                        if values[i + j] > values[i + j - 1]:
                            decay = False
                            break
                    if decay:
                        spike_decay_count += 1
                        i += 5  # Skip past this event
                        continue
                i += 1
            
            # If we see multiple spike-decay patterns, it's event-driven
            event_rate = spike_decay_count / (len(values) / 10)  # Events per 10 samples
            
            if event_rate > 0.3:  # More than 0.3 events per 10 samples
                logger.debug(f"Event-driven pattern: {spike_decay_count} spike-decay events detected")
                return True
            
            return False
        
        except Exception as e:
            logger.debug(f"Error detecting event-driven pattern: {e}")
            return False
    
    def _has_periodic_pattern(self, values: List[float]) -> bool:
        """
        Detect periodic patterns using autocorrelation.
        
        Args:
            values: Time series values
        
        Returns:
            True if periodic pattern detected
        """
        if len(values) < 144:  # Need at least 24 hours of data (at 10min intervals)
            return False
        
        try:
            # Convert to numpy array
            arr = np.array(values)
            
            # Normalize
            arr = (arr - np.mean(arr)) / (np.std(arr) + 1e-10)
            
            # Calculate autocorrelation for different lags
            # Check for daily pattern (144 data points = 24 hours at 10min intervals)
            daily_lag = min(144, len(arr) // 2)
            
            # Simple autocorrelation
            autocorr = np.correlate(arr, arr, mode='full')
            autocorr = autocorr[len(autocorr)//2:]  # Take positive lags only
            autocorr = autocorr / autocorr[0]  # Normalize
            
            # Check if there's a peak around daily lag
            if daily_lag < len(autocorr):
                # Look for peak in range [daily_lag-10, daily_lag+10]
                start = max(1, daily_lag - 10)
                end = min(len(autocorr), daily_lag + 10)
                
                if end > start:
                    peak_corr = max(autocorr[start:end])
                    
                    # If correlation > 0.5, consider it periodic
                    if peak_corr > 0.5:
                        logger.debug(f"Periodic pattern detected: peak_corr={peak_corr:.2f} at lag~{daily_lag}")
                        return True
            
            return False
        
        except Exception as e:
            logger.debug(f"Error detecting periodic pattern: {e}")
            return False
    
    def _detect_trend(self, values: List[float]) -> Optional[str]:
        """
        Detect trend using linear regression.
        
        Args:
            values: Time series values
        
        Returns:
            "growing", "declining", or None
        """
        if len(values) < 50:
            return None
        
        try:
            # Simple linear regression
            x = np.arange(len(values))
            y = np.array(values)
            
            # Calculate slope
            slope = np.polyfit(x, y, 1)[0]
            
            # Calculate relative slope (as percentage of mean)
            mean = np.mean(y)
            relative_slope = (slope * len(values)) / mean if mean > 0 else 0
            
            # Threshold: 20% change over the period
            if relative_slope > 0.2:
                logger.debug(f"Growing trend detected: slope={slope:.6f}, relative={relative_slope:.2%}")
                return "growing"
            elif relative_slope < -0.2:
                logger.debug(f"Declining trend detected: slope={slope:.6f}, relative={relative_slope:.2%}")
                return "declining"
            
            return None
        
        except Exception as e:
            logger.debug(f"Error detecting trend: {e}")
            return None
    
    def detect_correlations(self, deployments: List[str], hours: int = 24) -> List[DeploymentCorrelation]:
        """
        Detect correlations between deployments.
        
        Useful for identifying:
        - Frontend/backend relationships
        - Cascading load patterns
        - Shared resource contention
        
        Args:
            deployments: List of deployment names to analyze
            hours: Hours of historical data
        
        Returns:
            List of DeploymentCorrelation objects
        """
        correlations = []
        
        if len(deployments) < 2:
            return correlations
        
        # Check cache
        cache_key = ",".join(sorted(deployments))
        if cache_key in self.correlation_cache:
            cache_time = self.correlation_cache_time.get(cache_key, datetime.min)
            if (datetime.now() - cache_time).total_seconds() < self.correlation_cache_ttl:
                return self.correlation_cache[cache_key]
        
        try:
            # Get metrics for all deployments
            deployment_metrics: Dict[str, List[Tuple[datetime, float]]] = {}
            
            for dep in deployments:
                metrics = self.db.get_recent_metrics(dep, hours=hours)
                if len(metrics) >= 20:
                    deployment_metrics[dep] = [
                        (m.timestamp, m.pod_cpu_usage) 
                        for m in metrics if m.pod_cpu_usage > 0
                    ]
            
            # Compare each pair
            dep_list = list(deployment_metrics.keys())
            for i in range(len(dep_list)):
                for j in range(i + 1, len(dep_list)):
                    dep_a = dep_list[i]
                    dep_b = dep_list[j]
                    
                    corr = self._calculate_correlation(
                        dep_a, deployment_metrics[dep_a],
                        dep_b, deployment_metrics[dep_b]
                    )
                    
                    if corr and corr.correlation_coefficient > 0.5:
                        correlations.append(corr)
            
            # Cache results
            self.correlation_cache[cache_key] = correlations
            self.correlation_cache_time[cache_key] = datetime.now()
            
            if correlations:
                logger.info(f"Found {len(correlations)} deployment correlations")
            
        except Exception as e:
            logger.warning(f"Error detecting correlations: {e}")
        
        return correlations

    def _calculate_correlation(
        self,
        dep_a: str,
        metrics_a: List[Tuple[datetime, float]],
        dep_b: str,
        metrics_b: List[Tuple[datetime, float]]
    ) -> Optional[DeploymentCorrelation]:
        """
        Calculate correlation between two deployments.
        
        Args:
            dep_a: First deployment name
            metrics_a: Metrics for first deployment
            dep_b: Second deployment name
            metrics_b: Metrics for second deployment
        
        Returns:
            DeploymentCorrelation or None
        """
        try:
            # Align time series (find common timestamps within 1 minute)
            aligned_a = []
            aligned_b = []
            
            for ts_a, val_a in metrics_a:
                for ts_b, val_b in metrics_b:
                    if abs((ts_a - ts_b).total_seconds()) < 60:
                        aligned_a.append(val_a)
                        aligned_b.append(val_b)
                        break
            
            if len(aligned_a) < 20:
                return None
            
            # Calculate Pearson correlation
            arr_a = np.array(aligned_a)
            arr_b = np.array(aligned_b)
            
            # Normalize
            arr_a = (arr_a - np.mean(arr_a)) / (np.std(arr_a) + 1e-10)
            arr_b = (arr_b - np.mean(arr_b)) / (np.std(arr_b) + 1e-10)
            
            # Correlation at lag 0
            corr_0 = np.corrcoef(arr_a, arr_b)[0, 1]
            
            # Check for lagged correlation (B follows A)
            best_lag = 0
            best_corr = abs(corr_0)
            
            for lag in range(1, min(10, len(arr_a) // 4)):
                if lag < len(arr_a):
                    corr_lag = np.corrcoef(arr_a[:-lag], arr_b[lag:])[0, 1]
                    if abs(corr_lag) > best_corr:
                        best_corr = abs(corr_lag)
                        best_lag = lag
            
            if best_corr < 0.5:
                return None
            
            # Determine relationship type
            if best_lag == 0:
                description = f"Simultaneous load pattern (r={best_corr:.2f})"
            else:
                description = f"{dep_b} follows {dep_a} by ~{best_lag} minutes (r={best_corr:.2f})"
            
            # Confidence based on sample count and correlation strength
            sample_conf = min(1.0, len(aligned_a) / 100)
            corr_conf = best_corr
            confidence = sample_conf * 0.4 + corr_conf * 0.6
            
            return DeploymentCorrelation(
                deployment_a=dep_a,
                deployment_b=dep_b,
                correlation_coefficient=best_corr,
                lag_minutes=best_lag,
                confidence=confidence,
                description=description
            )
        
        except Exception as e:
            logger.debug(f"Error calculating correlation: {e}")
            return None
    
    def mark_event(self, deployment: str, event_type: str):
        """
        Mark an external event for correlation analysis.
        
        Args:
            deployment: Deployment name
            event_type: Type of event (e.g., "deployment", "config_change", "external_traffic")
        """
        if deployment not in self.event_markers:
            self.event_markers[deployment] = []
        
        self.event_markers[deployment].append((datetime.now(), event_type))
        
        # Keep only last 100 events
        if len(self.event_markers[deployment]) > 100:
            self.event_markers[deployment] = self.event_markers[deployment][-100:]
        
        logger.info(f"{deployment} - Marked event: {event_type}")
    
    def get_strategy(self, pattern: WorkloadPattern) -> PatternStrategy:
        """
        Get scaling strategy for a pattern.
        
        Args:
            pattern: Detected WorkloadPattern
        
        Returns:
            PatternStrategy for the pattern
        """
        return self.strategies.get(pattern, self.strategies[WorkloadPattern.UNKNOWN])
    
    def get_pattern_and_strategy(self, deployment: str, hours: int = 24) -> tuple:
        """
        Detect pattern and get strategy in one call.
        
        Args:
            deployment: Deployment name
            hours: Hours of historical data
        
        Returns:
            Tuple of (WorkloadPattern, PatternStrategy)
        """
        pattern = self.detect_pattern(deployment, hours)
        strategy = self.get_strategy(pattern)
        return pattern, strategy
    
    def clear_cache(self, deployment: Optional[str] = None):
        """
        Clear pattern cache.
        
        Args:
            deployment: Specific deployment to clear, or None for all
        """
        if deployment:
            if deployment in self.pattern_cache:
                del self.pattern_cache[deployment]
                logger.info(f"Cleared pattern cache for {deployment}")
        else:
            self.pattern_cache.clear()
            self.correlation_cache.clear()
            self.correlation_cache_time.clear()
            logger.info("Cleared all pattern cache")
    
    def get_pattern_summary(self) -> Dict[str, Dict]:
        """Get summary of all detected patterns"""
        summary = {}
        
        for deployment, (pattern, timestamp) in self.pattern_cache.items():
            age = (datetime.now() - timestamp).total_seconds()
            strategy = self.get_strategy(pattern)
            
            summary[deployment] = {
                'pattern': pattern.value,
                'detected_at': timestamp.isoformat(),
                'age_seconds': int(age),
                'strategy': {
                    'hpa_target': strategy.hpa_target,
                    'scale_up_stabilization': strategy.scale_up_stabilization,
                    'scale_down_stabilization': strategy.scale_down_stabilization,
                    'enable_predictive': strategy.enable_predictive,
                    'description': strategy.description
                }
            }
        
        return summary
    
    def get_correlation_summary(self) -> Dict[str, List[Dict]]:
        """Get summary of all detected correlations"""
        summary = {}
        
        for cache_key, correlations in self.correlation_cache.items():
            summary[cache_key] = [
                {
                    'deployment_a': c.deployment_a,
                    'deployment_b': c.deployment_b,
                    'correlation': round(c.correlation_coefficient, 3),
                    'lag_minutes': c.lag_minutes,
                    'confidence': round(c.confidence, 2),
                    'description': c.description
                }
                for c in correlations
            ]
        
        return summary
