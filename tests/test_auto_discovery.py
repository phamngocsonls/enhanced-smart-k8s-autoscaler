"""Tests for auto-discovery module"""

import pytest
from unittest.mock import MagicMock, patch


def test_auto_discovery_import():
    """Test that auto_discovery module can be imported"""
    from src.auto_discovery import AutoDiscovery, DiscoveredWorkload, ANNOTATION_ENABLED
    assert AutoDiscovery is not None
    assert DiscoveredWorkload is not None
    assert ANNOTATION_ENABLED == "smart-autoscaler.io/enabled"


def test_discovered_workload_dataclass():
    """Test DiscoveredWorkload dataclass"""
    from src.auto_discovery import DiscoveredWorkload
    
    workload = DiscoveredWorkload(
        namespace="production",
        deployment="api-server",
        hpa_name="api-server-hpa",
        priority="high",
        startup_filter_minutes=3,
        source="annotation"
    )
    
    assert workload.namespace == "production"
    assert workload.deployment == "api-server"
    assert workload.hpa_name == "api-server-hpa"
    assert workload.priority == "high"
    assert workload.startup_filter_minutes == 3
    assert workload.source == "annotation"


def test_discovered_workload_defaults():
    """Test DiscoveredWorkload default values"""
    from src.auto_discovery import DiscoveredWorkload
    
    workload = DiscoveredWorkload(
        namespace="default",
        deployment="my-app",
        hpa_name="my-app-hpa"
    )
    
    assert workload.priority == "medium"
    assert workload.startup_filter_minutes == 2
    assert workload.source == "annotation"


def test_auto_discovery_initialization():
    """Test AutoDiscovery initialization without k8s"""
    from src.auto_discovery import AutoDiscovery
    
    with patch('src.auto_discovery.client'):
        discovery = AutoDiscovery(watch_all_namespaces=True)
        assert discovery.watch_all_namespaces == True
        assert discovery.discovered_workloads == {}


def test_auto_discovery_with_namespaces():
    """Test AutoDiscovery with specific namespaces"""
    from src.auto_discovery import AutoDiscovery
    
    with patch('src.auto_discovery.client'):
        discovery = AutoDiscovery(
            namespaces=["production", "staging"],
            watch_all_namespaces=False
        )
        assert discovery.namespaces == ["production", "staging"]
        assert discovery.watch_all_namespaces == False


def test_annotation_constants():
    """Test annotation constants are correct"""
    from src.auto_discovery import (
        ANNOTATION_PREFIX,
        ANNOTATION_ENABLED,
        ANNOTATION_PRIORITY,
        ANNOTATION_STARTUP_FILTER
    )
    
    assert ANNOTATION_PREFIX == "smart-autoscaler.io"
    assert ANNOTATION_ENABLED == "smart-autoscaler.io/enabled"
    assert ANNOTATION_PRIORITY == "smart-autoscaler.io/priority"
    assert ANNOTATION_STARTUP_FILTER == "smart-autoscaler.io/startup-filter"


def test_check_hpa_annotations_enabled():
    """Test _check_hpa_annotations with enabled annotation"""
    from src.auto_discovery import AutoDiscovery
    
    with patch('src.auto_discovery.client'):
        discovery = AutoDiscovery()
        
        # Mock HPA object
        mock_hpa = MagicMock()
        mock_hpa.metadata.namespace = "production"
        mock_hpa.metadata.name = "api-hpa"
        mock_hpa.metadata.annotations = {
            "smart-autoscaler.io/enabled": "true",
            "smart-autoscaler.io/priority": "high"
        }
        mock_hpa.spec.scale_target_ref.kind = "Deployment"
        mock_hpa.spec.scale_target_ref.name = "api-server"
        
        workload = discovery._check_hpa_annotations(mock_hpa)
        
        assert workload is not None
        assert workload.namespace == "production"
        assert workload.deployment == "api-server"
        assert workload.hpa_name == "api-hpa"
        assert workload.priority == "high"


def test_check_hpa_annotations_disabled():
    """Test _check_hpa_annotations with disabled annotation"""
    from src.auto_discovery import AutoDiscovery
    
    with patch('src.auto_discovery.client'):
        discovery = AutoDiscovery()
        
        # Mock HPA object without enabled annotation
        mock_hpa = MagicMock()
        mock_hpa.metadata.annotations = {}
        
        workload = discovery._check_hpa_annotations(mock_hpa)
        
        assert workload is None


def test_check_hpa_annotations_non_deployment():
    """Test _check_hpa_annotations with non-Deployment target"""
    from src.auto_discovery import AutoDiscovery
    
    with patch('src.auto_discovery.client'):
        discovery = AutoDiscovery()
        
        # Mock HPA targeting StatefulSet
        mock_hpa = MagicMock()
        mock_hpa.metadata.namespace = "production"
        mock_hpa.metadata.name = "db-hpa"
        mock_hpa.metadata.annotations = {
            "smart-autoscaler.io/enabled": "true"
        }
        mock_hpa.spec.scale_target_ref.kind = "StatefulSet"
        mock_hpa.spec.scale_target_ref.name = "database"
        
        workload = discovery._check_hpa_annotations(mock_hpa)
        
        assert workload is None


def test_is_workload_discovered():
    """Test is_workload_discovered method"""
    from src.auto_discovery import AutoDiscovery, DiscoveredWorkload
    
    with patch('src.auto_discovery.client'):
        discovery = AutoDiscovery()
        
        # Add a workload
        workload = DiscoveredWorkload(
            namespace="production",
            deployment="api-server",
            hpa_name="api-hpa"
        )
        discovery.discovered_workloads["production/api-server"] = workload
        
        assert discovery.is_workload_discovered("production", "api-server") == True
        assert discovery.is_workload_discovered("production", "other-app") == False
        assert discovery.is_workload_discovered("staging", "api-server") == False
