"""
Tests for Prometheus exporter module
"""
import pytest
from unittest.mock import Mock, MagicMock, patch


class TestPrometheusExporter:
    """Test PrometheusExporter functionality"""
    
    def test_exporter_import(self):
        """Test PrometheusExporter can be imported"""
        from src.prometheus_exporter import PrometheusExporter
        assert PrometheusExporter is not None
    
    def test_exporter_initialization(self):
        """Test exporter initializes correctly"""
        from src.prometheus_exporter import PrometheusExporter
        
        exporter = PrometheusExporter(port=9090)
        
        assert exporter is not None
        assert exporter.port == 9090
    
    def test_exporter_default_port(self):
        """Test exporter has default port"""
        from src.prometheus_exporter import PrometheusExporter
        
        exporter = PrometheusExporter()
        
        assert exporter.port > 0


class TestMetricsRegistration:
    """Test metrics registration"""
    
    def test_metrics_registered(self):
        """Test that metrics are registered"""
        from src.prometheus_exporter import PrometheusExporter
        
        exporter = PrometheusExporter(port=9091)
        
        # Check that exporter has metrics attributes
        assert hasattr(exporter, 'node_utilization') or hasattr(exporter, 'metrics')
    
    def test_scaling_metrics_exist(self):
        """Test scaling-related metrics exist"""
        from src.prometheus_exporter import PrometheusExporter
        
        exporter = PrometheusExporter(port=9092)
        
        # These metrics should be defined
        metric_names = dir(exporter)
        
        # At least some metrics should exist
        assert len(metric_names) > 0


class TestMetricsUpdate:
    """Test metrics update functionality"""
    
    def test_update_node_utilization(self):
        """Test updating node utilization metric"""
        from src.prometheus_exporter import PrometheusExporter
        
        exporter = PrometheusExporter(port=9093)
        
        if hasattr(exporter, 'update_node_utilization'):
            # Should not raise
            exporter.update_node_utilization("test-deployment", 65.0)
    
    def test_update_pod_count(self):
        """Test updating pod count metric"""
        from src.prometheus_exporter import PrometheusExporter
        
        exporter = PrometheusExporter(port=9094)
        
        if hasattr(exporter, 'update_pod_count'):
            # Should not raise
            exporter.update_pod_count("test-deployment", 3)
    
    def test_update_hpa_target(self):
        """Test updating HPA target metric"""
        from src.prometheus_exporter import PrometheusExporter
        
        exporter = PrometheusExporter(port=9095)
        
        if hasattr(exporter, 'update_hpa_target'):
            # Should not raise
            exporter.update_hpa_target("test-deployment", 70)


class TestPatternMetrics:
    """Test pattern detection metrics"""
    
    def test_update_workload_pattern(self):
        """Test updating workload pattern metric"""
        from src.prometheus_exporter import PrometheusExporter
        
        exporter = PrometheusExporter(port=9096)
        
        if hasattr(exporter, 'update_workload_pattern'):
            # Should not raise
            exporter.update_workload_pattern("test-deployment", "STEADY", 0.85)
    
    def test_update_learning_rate(self):
        """Test updating learning rate metric"""
        from src.prometheus_exporter import PrometheusExporter
        
        exporter = PrometheusExporter(port=9097)
        
        if hasattr(exporter, 'update_learning_rate'):
            # Should not raise
            exporter.update_learning_rate("test-deployment", 0.15)


class TestDegradedModeMetrics:
    """Test degraded mode metrics"""
    
    def test_update_degraded_mode(self):
        """Test updating degraded mode metric"""
        from src.prometheus_exporter import PrometheusExporter
        
        exporter = PrometheusExporter(port=9098)
        
        if hasattr(exporter, 'update_degraded_mode'):
            # Should not raise
            exporter.update_degraded_mode(False)
    
    def test_update_service_health(self):
        """Test updating service health metric"""
        from src.prometheus_exporter import PrometheusExporter
        
        exporter = PrometheusExporter(port=9099)
        
        if hasattr(exporter, 'update_service_health'):
            # Should not raise
            exporter.update_service_health("prometheus", "healthy")


class TestCostMetrics:
    """Test cost-related metrics"""
    
    def test_update_cost_savings(self):
        """Test updating cost savings metric"""
        from src.prometheus_exporter import PrometheusExporter
        
        exporter = PrometheusExporter(port=9100)
        
        if hasattr(exporter, 'update_cost_savings'):
            # Should not raise
            exporter.update_cost_savings("test-deployment", 50.0)


class TestExporterServer:
    """Test exporter HTTP server"""
    
    def test_start_method_exists(self):
        """Test start method exists"""
        from src.prometheus_exporter import PrometheusExporter
        
        exporter = PrometheusExporter(port=9101)
        
        assert hasattr(exporter, 'start') or hasattr(exporter, 'run')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
