"""
Workload Pattern Detection
Detects different workload patterns and provides adaptive scaling strategies
"""

import logging
import statistics
from typing import List, Dict, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)


class WorkloadPattern(Enum):
    """Types of workload patterns"""
    STEADY = "steady"  # Consistent load with low variance
    BURSTY = "bursty"  # Frequent spikes and drops
    PERIODIC = "periodic"  # Daily/weekly patterns
    GROWING = "growing"  # Steadily increasing trend
    DECLINING = "declining"  # Steadily decreasing trend
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


class PatternDetector:
    """
    Detect workload patterns and provide adaptive scaling strategies.
    
    Analyzes historical metrics to identify:
    - Steady workloads (low variance)
    - Bursty workloads (high variance, frequent spikes)
    - Periodic workloads (daily/weekly patterns)
    - Growing workloads (upward trend)
    - Declining workloads (downward trend)
    """
    
    def __init__(self, db):
        """
        Initialize pattern detector.
        
        Args:
            db: TimeSeriesDatabase instance
        """
        self.db = db
        
        # Pattern strategies
        self.strategies = {
            WorkloadPattern.STEADY: PatternStrategy(
                hpa_target=70.0,
                scale_up_stabilization=120,
                scale_down_stabilization=300,
                enable_predictive=False,
                confidence_threshold=0.7,
                description="Consistent load - standard scaling"
            ),
            WorkloadPattern.BURSTY: PatternStrategy(
                hpa_target=60.0,  # Lower target for faster response
                scale_up_stabilization=30,  # Quick scale up
                scale_down_stabilization=600,  # Slow scale down to handle next burst
                enable_predictive=False,  # Predictions don't work well for random bursts
                confidence_threshold=0.8,  # Higher threshold to avoid false positives
                description="Frequent spikes - aggressive scale up, conservative scale down"
            ),
            WorkloadPattern.PERIODIC: PatternStrategy(
                hpa_target=70.0,
                scale_up_stabilization=60,
                scale_down_stabilization=300,
                enable_predictive=True,  # Predictive works great for periodic patterns
                confidence_threshold=0.6,  # Can be more aggressive with predictions
                description="Daily/weekly patterns - predictive scaling enabled"
            ),
            WorkloadPattern.GROWING: PatternStrategy(
                hpa_target=65.0,  # Slightly lower for headroom
                scale_up_stabilization=60,
                scale_down_stabilization=600,  # Cautious scale down
                enable_predictive=True,
                confidence_threshold=0.7,
                description="Upward trend - maintain headroom, cautious scale down"
            ),
            WorkloadPattern.DECLINING: PatternStrategy(
                hpa_target=75.0,  # Higher target to save costs
                scale_up_stabilization=120,
                scale_down_stabilization=180,  # Faster scale down to save costs
                enable_predictive=False,
                confidence_threshold=0.7,
                description="Downward trend - optimize for cost savings"
            ),
            WorkloadPattern.UNKNOWN: PatternStrategy(
                hpa_target=70.0,
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
        pattern = self._classify_pattern(cpu_values, mean, std, cv)
        
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
        values: List[float],
        mean: float,
        std: float,
        cv: float
    ) -> WorkloadPattern:
        """
        Classify workload pattern based on statistical analysis.
        
        Args:
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
        
        # 3. Check for periodic pattern (daily/weekly cycles)
        if self._has_periodic_pattern(values):
            logger.debug("Pattern: PERIODIC (detected cycles)")
            return WorkloadPattern.PERIODIC
        
        # 4. Check for trend (growing or declining)
        trend = self._detect_trend(values)
        if trend == "growing":
            logger.debug("Pattern: GROWING (upward trend)")
            return WorkloadPattern.GROWING
        elif trend == "declining":
            logger.debug("Pattern: DECLINING (downward trend)")
            return WorkloadPattern.DECLINING
        
        # 5. Default to steady if no clear pattern
        logger.debug("Pattern: STEADY (default)")
        return WorkloadPattern.STEADY
    
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
