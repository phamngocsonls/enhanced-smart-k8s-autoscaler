import pytest

def test_imports():
    """Test basic imports"""
    try:
        import src
        assert src.__version__ == "0.0.3"
    except Exception as e:
        pytest.fail(f"Import failed: {e}")

def test_config_loader():
    """Test configuration loading"""
    from src.config_loader import Config
    config = Config()
    assert config.check_interval > 0
