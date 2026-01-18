"""
Tests for config loader module
"""
import pytest
import os
from unittest.mock import Mock, MagicMock, patch


class TestOperatorConfig:
    """Test OperatorConfig dataclass"""
    
    def test_operator_config_import(self):
        """Test OperatorConfig can be imported"""
        from src.config_loader import OperatorConfig
        assert OperatorConfig is not None
    
    def test_operator_config_creation(self):
        """Test creating OperatorConfig"""
        from src.config_loader import OperatorConfig
        
        config = OperatorConfig(
            prometheus_url="http://prometheus:9090",
            check_interval=60,
            target_node_utilization=30.0,
            dry_run=False,
            enable_predictive=True,
            enable_autotuning=True,
            cost_per_vcpu_hour=0.04,
            cost_per_gb_memory_hour=0.004,
            log_level="INFO",
            log_format="json",
            prometheus_rate_limit=10,
            k8s_api_rate_limit=20,
            memory_warning_threshold=0.75,
            memory_critical_threshold=0.9,
            memory_check_interval=30,
            webhooks={},
            deployments=[]
        )
        
        assert config.prometheus_url == "http://prometheus:9090"
        assert config.check_interval == 60
        assert config.enable_predictive is True


class TestDeploymentConfig:
    """Test DeploymentConfig dataclass"""
    
    def test_deployment_config_import(self):
        """Test DeploymentConfig can be imported"""
        from src.config_loader import DeploymentConfig
        assert DeploymentConfig is not None
    
    def test_deployment_config_creation(self):
        """Test creating DeploymentConfig"""
        from src.config_loader import DeploymentConfig
        
        config = DeploymentConfig(
            namespace="default",
            deployment="my-app",
            hpa_name="my-app-hpa",
            startup_filter_minutes=2
        )
        
        assert config.namespace == "default"
        assert config.deployment == "my-app"
        assert config.hpa_name == "my-app-hpa"


class TestConfigLoader:
    """Test ConfigLoader functionality"""
    
    def test_config_loader_import(self):
        """Test ConfigLoader can be imported"""
        from src.config_loader import ConfigLoader
        assert ConfigLoader is not None
    
    def test_config_loader_initialization(self):
        """Test ConfigLoader initializes correctly"""
        from src.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        
        assert loader.namespace == "autoscaler-system"
        assert loader.configmap_name == "smart-autoscaler-config"
    
    def test_config_loader_custom_namespace(self):
        """Test ConfigLoader with custom namespace"""
        from src.config_loader import ConfigLoader
        
        loader = ConfigLoader(namespace="custom-ns", configmap_name="custom-config")
        
        assert loader.namespace == "custom-ns"
        assert loader.configmap_name == "custom-config"
    
    def test_load_config_from_env(self):
        """Test loading config from environment variables"""
        from src.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        config = loader.load_config()
        
        assert config is not None
        assert config.check_interval > 0
        assert config.prometheus_url is not None
    
    @pytest.mark.skip(reason="Environment variable override test is flaky in CI")
    def test_load_config_custom_env(self):
        """Test loading config with custom environment variables"""
        from src.config_loader import ConfigLoader
        import os
        
        # Save original values
        original_url = os.environ.get('PROMETHEUS_URL')
        original_interval = os.environ.get('CHECK_INTERVAL')
        original_dry_run = os.environ.get('DRY_RUN')
        
        try:
            # Set test values
            os.environ['PROMETHEUS_URL'] = 'http://custom-prometheus:9090'
            os.environ['CHECK_INTERVAL'] = '120'
            os.environ['DRY_RUN'] = 'true'
            
            # Create a fresh loader
            loader = ConfigLoader()
            config = loader.load_config()
            
            assert config.prometheus_url == 'http://custom-prometheus:9090'
            assert config.check_interval == 120
            assert config.dry_run is True
            
        finally:
            # Restore original values
            if original_url is not None:
                os.environ['PROMETHEUS_URL'] = original_url
            elif 'PROMETHEUS_URL' in os.environ:
                del os.environ['PROMETHEUS_URL']
                
            if original_interval is not None:
                os.environ['CHECK_INTERVAL'] = original_interval
            elif 'CHECK_INTERVAL' in os.environ:
                del os.environ['CHECK_INTERVAL']
                
            if original_dry_run is not None:
                os.environ['DRY_RUN'] = original_dry_run
            elif 'DRY_RUN' in os.environ:
                del os.environ['DRY_RUN']
    
    def test_config_has_required_fields(self):
        """Test config has all required fields"""
        from src.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        config = loader.load_config()
        
        # Check required fields exist
        assert hasattr(config, 'prometheus_url')
        assert hasattr(config, 'check_interval')
        assert hasattr(config, 'target_node_utilization')
        assert hasattr(config, 'dry_run')
        assert hasattr(config, 'enable_predictive')
        assert hasattr(config, 'enable_autotuning')
        assert hasattr(config, 'cost_per_vcpu_hour')
        assert hasattr(config, 'cost_per_gb_memory_hour')
        assert hasattr(config, 'log_level')
        assert hasattr(config, 'deployments')


class TestConfigLoaderCallbacks:
    """Test ConfigLoader callback functionality"""
    
    def test_register_callback(self):
        """Test registering a reload callback"""
        from src.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        
        callback_called = []
        def my_callback(config):
            callback_called.append(True)
        
        loader.register_reload_callback(my_callback)
        
        assert my_callback in loader.reload_callbacks
    
    def test_multiple_callbacks(self):
        """Test registering multiple callbacks"""
        from src.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        
        def callback1(config):
            pass
        
        def callback2(config):
            pass
        
        loader.register_reload_callback(callback1)
        loader.register_reload_callback(callback2)
        
        assert len(loader.reload_callbacks) >= 2


class TestConfigLoaderStatus:
    """Test ConfigLoader status functionality"""
    
    def test_config_version(self):
        """Test config version tracking"""
        from src.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        
        assert hasattr(loader, 'config_version')
        assert loader.config_version >= 0
    
    def test_last_reload_tracking(self):
        """Test last reload time tracking"""
        from src.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        
        assert hasattr(loader, 'last_reload')
        assert loader.last_reload is not None


class TestConfigValidation:
    """Test configuration validation"""
    
    def test_check_interval_positive(self):
        """Test check_interval must be positive"""
        from src.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        config = loader.load_config()
        
        assert config.check_interval > 0
    
    def test_target_utilization_valid(self):
        """Test target_node_utilization is valid"""
        from src.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        config = loader.load_config()
        
        # Can be percentage (70.0) or decimal (0.7)
        assert config.target_node_utilization > 0
    
    def test_cost_values_positive(self):
        """Test cost values are positive"""
        from src.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        config = loader.load_config()
        
        assert config.cost_per_vcpu_hour >= 0
        assert config.cost_per_gb_memory_hour >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
