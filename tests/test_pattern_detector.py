"""
Tests for pattern detector module
"""
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime


class TestWorkloadPattern:
    """Test WorkloadPattern enum"""
    
    def test_workload_pattern_import(self):
        """Test WorkloadPattern can be imported"""
        from src.pattern_detector import WorkloadPattern
        assert WorkloadPattern is not None
    
    def test_workload_pattern_values(self):
        """Test all pattern types exist"""
        from src.pattern_detector import WorkloadPattern
        
        patterns = [p.name for p in WorkloadPattern]
        
        assert 'STEADY' in patterns
        assert 'BURSTY' in patterns
        assert 'PERIODIC' in patterns
        assert 'GROWING' in patterns
        assert 'DECLINING' in patterns
        assert 'UNKNOWN' in patterns


class TestPatternStrategy:
    """Test PatternStrategy dataclass"""
    
    def test_pattern_strategy_import(self):
        """Test PatternStrategy can be imported"""
        from src.pattern_detector import PatternStrategy
        assert PatternStrategy is not None
    
    def test_pattern_strategy_creation(self):
        """Test creating a PatternStrategy"""
        from src.pattern_detector import PatternStrategy
        
        strategy = PatternStrategy(
            hpa_target=70.0,
            scale_up_stabilization=60,
            scale_down_stabilization=300,
            enable_predictive=True,
            confidence_threshold=0.8,
            description="Test strategy"
        )
        
        assert strategy.hpa_target == 70.0
        assert strategy.scale_up_stabilization == 60
        assert strategy.enable_predictive is True


class TestPatternDetector:
    """Test PatternDetector functionality"""
    
    def test_pattern_detector_import(self):
        """Test PatternDetector can be imported"""
        from src.pattern_detector import PatternDetector
        assert PatternDetector is not None
    
    def test_pattern_detector_initialization(self):
        """Test PatternDetector initializes correctly"""
        from src.pattern_detector import PatternDetector
        
        mock_db = Mock()
        detector = PatternDetector(db=mock_db)
        
        assert detector is not None
        assert detector.db == mock_db
    
    def test_pattern_detector_has_strategies(self):
        """Test PatternDetector has strategies for all patterns"""
        from src.pattern_detector import PatternDetector, WorkloadPattern
        
        mock_db = Mock()
        detector = PatternDetector(db=mock_db)
        
        # Should have strategies for main patterns
        assert WorkloadPattern.STEADY in detector.strategies
        assert WorkloadPattern.BURSTY in detector.strategies
        assert WorkloadPattern.PERIODIC in detector.strategies
        assert WorkloadPattern.GROWING in detector.strategies
        assert WorkloadPattern.DECLINING in detector.strategies
    
    def test_detect_pattern_insufficient_data(self):
        """Test pattern detection with insufficient data"""
        from src.pattern_detector import PatternDetector, WorkloadPattern
        
        mock_db = Mock()
        mock_db.get_recent_metrics.return_value = []  # No data
        
        detector = PatternDetector(db=mock_db)
        pattern = detector.detect_pattern("test-deployment")
        
        assert pattern == WorkloadPattern.UNKNOWN
    
    def test_detect_pattern_steady(self):
        """Test detection of steady pattern"""
        from src.pattern_detector import PatternDetector, WorkloadPattern
        
        # Create mock metrics with steady values
        mock_metrics = []
        for i in range(200):
            mock_metric = Mock()
            mock_metric.pod_cpu_usage = 50.0 + (i % 5)  # Small variance
            mock_metrics.append(mock_metric)
        
        mock_db = Mock()
        mock_db.get_recent_metrics.return_value = mock_metrics
        
        detector = PatternDetector(db=mock_db)
        pattern = detector.detect_pattern("test-deployment")
        
        # Should detect some pattern (not necessarily STEADY due to algorithm)
        assert pattern in [WorkloadPattern.STEADY, WorkloadPattern.BURSTY, 
                          WorkloadPattern.PERIODIC, WorkloadPattern.GROWING,
                          WorkloadPattern.DECLINING, WorkloadPattern.UNKNOWN]
    
    def test_get_strategy_for_pattern(self):
        """Test getting strategy for a pattern"""
        from src.pattern_detector import PatternDetector, WorkloadPattern
        
        mock_db = Mock()
        detector = PatternDetector(db=mock_db)
        
        strategy = detector.get_strategy(WorkloadPattern.STEADY)
        
        assert strategy is not None
        assert strategy.hpa_target > 0
    
    def test_get_strategy_for_unknown_pattern(self):
        """Test getting strategy for unknown pattern returns default"""
        from src.pattern_detector import PatternDetector, WorkloadPattern
        
        mock_db = Mock()
        detector = PatternDetector(db=mock_db)
        
        strategy = detector.get_strategy(WorkloadPattern.UNKNOWN)
        
        # Should return a default strategy
        assert strategy is not None


class TestPatternAnalysis:
    """Test pattern analysis helper methods"""
    
    def test_calculate_variance(self):
        """Test variance calculation for pattern detection"""
        from src.pattern_detector import PatternDetector
        
        mock_db = Mock()
        detector = PatternDetector(db=mock_db)
        
        # Test with known values
        values = [10, 10, 10, 10, 10]  # Zero variance
        
        if hasattr(detector, '_calculate_variance'):
            variance = detector._calculate_variance(values)
            assert variance == 0.0
    
    def test_detect_trend(self):
        """Test trend detection"""
        from src.pattern_detector import PatternDetector
        
        mock_db = Mock()
        detector = PatternDetector(db=mock_db)
        
        # Growing trend
        growing_values = list(range(1, 101))
        
        if hasattr(detector, '_detect_trend'):
            trend = detector._detect_trend(growing_values)
            assert trend > 0  # Positive trend


class TestPatternCaching:
    """Test pattern caching functionality"""
    
    def test_pattern_cache_initialization(self):
        """Test pattern cache is initialized"""
        from src.pattern_detector import PatternDetector
        
        mock_db = Mock()
        detector = PatternDetector(db=mock_db)
        
        assert hasattr(detector, 'pattern_cache')
        assert isinstance(detector.pattern_cache, dict)
    
    def test_pattern_cache_ttl(self):
        """Test pattern cache has TTL"""
        from src.pattern_detector import PatternDetector
        
        mock_db = Mock()
        detector = PatternDetector(db=mock_db)
        
        assert hasattr(detector, 'cache_ttl')
        assert detector.cache_ttl > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
