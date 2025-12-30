import pytest

def test_imports():
    """Test basic imports"""
    try:
        import src
        assert src.__version__ == "0.0.9"
    except Exception as e:
        pytest.fail(f"Import failed: {e}")

def test_all_modules_importable():
    """Test all core modules can be imported"""
    modules = [
        'src.integrated_operator',
        'src.intelligence',
        'src.pattern_detector',
        'src.config_loader',
        'src.degraded_mode',
        'src.prometheus_exporter',
        'src.dashboard',
    ]
    
    for module_name in modules:
        try:
            __import__(module_name)
        except Exception as e:
            pytest.fail(f"Failed to import {module_name}: {e}")

def test_config_loader():
    """Test configuration loading"""
    from src.config_loader import ConfigLoader
    config_loader = ConfigLoader()
    config = config_loader.load_config()
    
    # Verify essential config attributes
    assert config.check_interval > 0
    assert config.prometheus_url is not None
    assert hasattr(config, 'enable_predictive')
    assert hasattr(config, 'enable_autotuning')
    assert config.target_node_utilization > 0
