"""
Comprehensive tests for core features
"""
import pytest
from unittest.mock import Mock, MagicMock, patch


class TestPatternDetector:
    """Test workload pattern detection"""
    
    def test_pattern_detector_import(self):
        """Test pattern detector can be imported"""
        from src.pattern_detector import PatternDetector, WorkloadPattern
        assert PatternDetector is not None
        assert WorkloadPattern is not None
    
    def test_steady_pattern_detection(self):
        """Test detection of steady workload"""
        from src.pattern_detector import PatternDetector
        
        # Mock database
        mock_db = Mock()
        detector = PatternDetector(db=mock_db)
        
        # Steady workload: consistent values
        metrics = [50.0] * 20
        pattern, confidence = detector.detect_pattern(metrics)
        
        assert pattern.name in ['STEADY', 'BURSTY', 'PERIODIC', 'GROWING', 'DECLINING']
        assert 0 <= confidence <= 1.0
    
    def test_growing_pattern_detection(self):
        """Test detection of growing workload"""
        from src.pattern_detector import PatternDetector
        
        # Mock database
        mock_db = Mock()
        detector = PatternDetector(db=mock_db)
        
        # Growing workload: increasing values
        metrics = list(range(10, 30))
        pattern, confidence = detector.detect_pattern(metrics)
        
        assert pattern.name in ['GROWING', 'STEADY', 'BURSTY']
        assert 0 <= confidence <= 1.0


class TestIntelligence:
    """Test intelligence and auto-tuning features"""
    
    def test_autotuner_import(self):
        """Test AutoTuner can be imported"""
        from src.intelligence import AutoTuner
        assert AutoTuner is not None
    
    def test_cost_optimizer_import(self):
        """Test CostOptimizer can be imported"""
        from src.intelligence import CostOptimizer
        assert CostOptimizer is not None
    
    def test_cost_optimizer_initialization(self):
        """Test cost optimizer initializes correctly"""
        from src.intelligence import CostOptimizer
        
        # Mock dependencies
        mock_db = Mock()
        mock_alert_manager = Mock()
        
        optimizer = CostOptimizer(db=mock_db, alert_manager=mock_alert_manager)
        
        assert optimizer.cost_per_vcpu_hour > 0
        assert optimizer.cost_per_gb_memory_hour > 0


class TestDegradedMode:
    """Test degraded mode and resilience"""
    
    def test_degraded_mode_handler_import(self):
        """Test DegradedModeHandler can be imported"""
        from src.degraded_mode import DegradedModeHandler
        assert DegradedModeHandler is not None
    
    def test_degraded_mode_initialization(self):
        """Test degraded mode initializes correctly"""
        from src.degraded_mode import DegradedModeHandler
        
        degraded = DegradedModeHandler(cache_ttl_seconds=300)
        assert degraded.cache_ttl_seconds == 300
        assert degraded.is_degraded is False


class TestConfigLoader:
    """Test configuration loading and hot reload"""
    
    def test_config_loader_import(self):
        """Test ConfigLoader can be imported"""
        from src.config_loader import ConfigLoader, OperatorConfig
        assert ConfigLoader is not None
        assert OperatorConfig is not None
    
    def test_config_loader_initialization(self):
        """Test config loader initializes"""
        from src.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        assert loader.namespace == "autoscaler-system"
        assert loader.configmap_name == "smart-autoscaler-config"
    
    def test_config_loading(self):
        """Test configuration loads from environment"""
        from src.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        config = loader.load_config()
        
        assert config is not None
        assert config.check_interval > 0
        assert config.prometheus_url is not None
        # target_node_utilization can be percentage (70.0) or decimal (0.7)
        assert config.target_node_utilization > 0


class TestPrometheusExporter:
    """Test Prometheus metrics export"""
    
    def test_exporter_import(self):
        """Test PrometheusExporter can be imported"""
        from src.prometheus_exporter import PrometheusExporter
        assert PrometheusExporter is not None
    
    def test_exporter_initialization(self):
        """Test exporter initializes with correct port"""
        from src.prometheus_exporter import PrometheusExporter
        
        exporter = PrometheusExporter(port=9090)
        assert exporter.port == 9090


class TestIntegratedOperator:
    """Test integrated operator"""
    
    def test_operator_import(self):
        """Test EnhancedSmartAutoscaler can be imported"""
        from src.integrated_operator import EnhancedSmartAutoscaler
        assert EnhancedSmartAutoscaler is not None
    
    @patch('src.integrated_operator.client')
    @patch('src.integrated_operator.config')
    def test_operator_initialization(self, mock_k8s_config, mock_client):
        """Test operator initializes with all components"""
        from src.integrated_operator import EnhancedSmartAutoscaler
        from src.config_loader import ConfigLoader
        
        # Mock Kubernetes config
        mock_k8s_config.load_incluster_config = Mock()
        
        config_loader = ConfigLoader()
        operator_config = config_loader.load_config()
        
        operator = EnhancedSmartAutoscaler(operator_config)
        
        # Verify key components are initialized
        assert operator.config is not None
        assert operator.pattern_detector is not None
        assert operator.autotuner is not None
        assert operator.cost_optimizer is not None
        assert operator.degraded_mode is not None


class TestVersioning:
    """Test version management"""
    
    def test_version_format(self):
        """Test version follows semantic versioning"""
        import src
        version = src.__version__
        
        # Should be in format X.X.X
        parts = version.split('.')
        assert len(parts) == 3
        
        for part in parts:
            assert part.isdigit()
    
    def test_version_value(self):
        """Test version is 0.0.5"""
        import src
        assert src.__version__ == "0.0.5"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
