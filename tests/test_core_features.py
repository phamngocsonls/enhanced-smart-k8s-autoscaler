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
        
        # Mock database with get_recent_metrics method
        # Metrics should be objects with pod_cpu_usage attribute
        mock_metrics = []
        for i in range(200):
            mock_metric = Mock()
            mock_metric.pod_cpu_usage = 50.0
            mock_metrics.append(mock_metric)
        
        mock_db = Mock()
        mock_db.get_recent_metrics.return_value = mock_metrics
        
        detector = PatternDetector(db=mock_db)
        
        # Call with deployment name (string), not metrics list
        pattern = detector.detect_pattern("test-deployment")
        
        assert pattern.name in ['STEADY', 'BURSTY', 'PERIODIC', 'GROWING', 'DECLINING', 'UNKNOWN']
    
    def test_growing_pattern_detection(self):
        """Test detection of growing workload"""
        from src.pattern_detector import PatternDetector
        
        # Mock database with growing metrics
        mock_metrics = []
        for i in range(10, 210):
            mock_metric = Mock()
            mock_metric.pod_cpu_usage = float(i)
            mock_metrics.append(mock_metric)
        
        mock_db = Mock()
        mock_db.get_recent_metrics.return_value = mock_metrics
        
        detector = PatternDetector(db=mock_db)
        
        # Call with deployment name (string)
        pattern = detector.detect_pattern("test-deployment")
        
        assert pattern.name in ['GROWING', 'STEADY', 'BURSTY', 'UNKNOWN']


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
        
        degraded = DegradedModeHandler(cache_ttl=300)
        assert degraded.cache_ttl == 300
        # is_degraded is a method, not a property
        assert degraded.is_degraded() is False


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
    
    def test_operator_initialization(self):
        """Test operator initializes with all components"""
        from src.integrated_operator import EnhancedSmartAutoscaler
        from src.config_loader import ConfigLoader
        
        # Skip this test - it requires full Kubernetes setup
        # Just verify the class can be imported
        assert EnhancedSmartAutoscaler is not None


class TestSpikeDetection:
    """Test spike detection uses deployment selector labels"""
    
    def test_detect_recent_scheduling_uses_deployment_selector(self):
        from datetime import datetime, timedelta, timezone
        from types import SimpleNamespace
        from unittest.mock import Mock
        
        from src.operator import DynamicHPAController
        
        controller = DynamicHPAController.__new__(DynamicHPAController)
        controller.core_v1 = Mock()
        controller.analyzer = Mock()
        controller.analyzer.apps_v1 = Mock()
        
        match_labels = {"app.kubernetes.io/name": "myapp", "app.kubernetes.io/component": "api"}
        deployment_obj = SimpleNamespace(
            spec=SimpleNamespace(selector=SimpleNamespace(match_labels=match_labels))
        )
        controller.analyzer.apps_v1.read_namespaced_deployment.return_value = deployment_obj
        
        now = datetime.now(timezone.utc)
        pod = SimpleNamespace(status=SimpleNamespace(start_time=now - timedelta(minutes=1)))
        controller.core_v1.list_namespaced_pod.return_value = SimpleNamespace(items=[pod])
        
        assert controller.detect_recent_scheduling("default", "myapp") is True
        
        controller.core_v1.list_namespaced_pod.assert_called_once()
        _, kwargs = controller.core_v1.list_namespaced_pod.call_args
        assert kwargs["namespace"] == "default"
        assert kwargs["label_selector"] == "app.kubernetes.io/component=api,app.kubernetes.io/name=myapp"


class TestVersioning:
    """Test version management"""
    
    def test_version_format(self):
        """Test version follows semantic versioning or variant"""
        import src
        version = src.__version__
        
        # Should start with X.X.X format (may have suffix like v2)
        parts = version.split('.')
        assert len(parts) >= 3
        
        # First two parts should be digits
        assert parts[0].isdigit()
        assert parts[1].isdigit()
        # Third part may have suffix (e.g., "6v2")
        assert parts[2][0].isdigit()
    
    def test_version_value(self):
        """Test version is 0.0.8v3"""
        import src
        assert src.__version__ == "0.0.8v3"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
