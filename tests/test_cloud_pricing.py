"""
Tests for Cloud Pricing Auto-Detection
"""

import pytest
from unittest.mock import Mock, MagicMock
from src.cloud_pricing import CloudPricingDetector


@pytest.fixture
def mock_core_v1():
    """Mock Kubernetes core_v1 API"""
    return Mock()


@pytest.fixture
def pricing_detector(mock_core_v1):
    """Create pricing detector instance"""
    return CloudPricingDetector(mock_core_v1)


def test_detect_gcp_provider(pricing_detector, mock_core_v1):
    """Test detecting GCP from node labels"""
    # Mock GKE node
    mock_node = Mock()
    mock_node.metadata.labels = {
        'cloud.google.com/gke-nodepool': 'default-pool',
        'beta.kubernetes.io/instance-type': 'n1-standard-4'
    }
    
    mock_nodes = Mock()
    mock_nodes.items = [mock_node]
    mock_core_v1.list_node.return_value = mock_nodes
    
    provider = pricing_detector.detect_cloud_provider()
    
    assert provider == 'gcp'


def test_detect_aws_provider(pricing_detector, mock_core_v1):
    """Test detecting AWS from node labels"""
    # Mock EKS node
    mock_node = Mock()
    mock_node.metadata.labels = {
        'eks.amazonaws.com/nodegroup': 'my-nodegroup',
        'node.kubernetes.io/instance-type': 'm5.xlarge'
    }
    
    mock_nodes = Mock()
    mock_nodes.items = [mock_node]
    mock_core_v1.list_node.return_value = mock_nodes
    
    provider = pricing_detector.detect_cloud_provider()
    
    assert provider == 'aws'


def test_detect_azure_provider(pricing_detector, mock_core_v1):
    """Test detecting Azure from node labels"""
    # Mock AKS node
    mock_node = Mock()
    mock_node.metadata.labels = {
        'kubernetes.azure.com/cluster': 'my-cluster',
        'node.kubernetes.io/instance-type': 'Standard_D4s_v3'
    }
    
    mock_nodes = Mock()
    mock_nodes.items = [mock_node]
    mock_core_v1.list_node.return_value = mock_nodes
    
    provider = pricing_detector.detect_cloud_provider()
    
    assert provider == 'azure'


def test_extract_gcp_instance_family(pricing_detector):
    """Test extracting GCP instance family"""
    family = pricing_detector.extract_instance_family('n1-standard-4', 'gcp')
    assert family == 'n1-standard'
    
    family = pricing_detector.extract_instance_family('n2-highmem-8', 'gcp')
    assert family == 'n2-highmem'
    
    family = pricing_detector.extract_instance_family('c2-standard-16', 'gcp')
    assert family == 'c2-standard'


def test_extract_aws_instance_family(pricing_detector):
    """Test extracting AWS instance family"""
    family = pricing_detector.extract_instance_family('m5.xlarge', 'aws')
    assert family == 'm5'
    
    family = pricing_detector.extract_instance_family('c5.2xlarge', 'aws')
    assert family == 'c5'
    
    family = pricing_detector.extract_instance_family('r5.large', 'aws')
    assert family == 'r5'


def test_extract_azure_instance_family(pricing_detector):
    """Test extracting Azure instance family"""
    family = pricing_detector.extract_instance_family('Standard_D4s_v3', 'azure')
    assert family == 'standard_d'
    
    family = pricing_detector.extract_instance_family('Standard_F8s_v2', 'azure')
    assert family == 'standard_f'
    
    family = pricing_detector.extract_instance_family('Standard_E16s_v3', 'azure')
    assert family == 'standard_e'


def test_get_gcp_pricing(pricing_detector):
    """Test getting GCP pricing"""
    pricing = pricing_detector.get_pricing_for_instance_family('n1-standard', 'gcp')
    
    assert pricing is not None
    assert 'vcpu' in pricing
    assert 'memory_gb' in pricing
    assert pricing['vcpu'] > 0
    assert pricing['memory_gb'] > 0


def test_get_aws_pricing(pricing_detector):
    """Test getting AWS pricing"""
    pricing = pricing_detector.get_pricing_for_instance_family('m5', 'aws')
    
    assert pricing is not None
    assert 'vcpu' in pricing
    assert 'memory_gb' in pricing
    assert pricing['vcpu'] > 0
    assert pricing['memory_gb'] > 0


def test_get_azure_pricing(pricing_detector):
    """Test getting Azure pricing"""
    pricing = pricing_detector.get_pricing_for_instance_family('standard_d', 'azure')
    
    assert pricing is not None
    assert 'vcpu' in pricing
    assert 'memory_gb' in pricing
    assert pricing['vcpu'] > 0
    assert pricing['memory_gb'] > 0


def test_auto_detect_pricing_gcp(pricing_detector, mock_core_v1):
    """Test auto-detecting pricing for GCP"""
    # Mock GKE nodes
    mock_node = Mock()
    mock_node.metadata.name = 'node-1'
    mock_node.metadata.labels = {
        'cloud.google.com/gke-nodepool': 'default-pool',
        'beta.kubernetes.io/instance-type': 'n1-standard-4'
    }
    
    mock_nodes = Mock()
    mock_nodes.items = [mock_node]
    mock_core_v1.list_node.return_value = mock_nodes
    mock_core_v1.read_node.return_value = mock_node
    
    vcpu_price, memory_price = pricing_detector.auto_detect_pricing()
    
    assert vcpu_price > 0
    assert memory_price > 0
    assert pricing_detector.detected_provider == 'gcp'
    assert pricing_detector.detected_pricing is not None


def test_auto_detect_pricing_fallback(pricing_detector, mock_core_v1):
    """Test fallback to default pricing when detection fails"""
    # Mock nodes with no recognizable labels
    mock_node = Mock()
    mock_node.metadata.labels = {}
    
    mock_nodes = Mock()
    mock_nodes.items = [mock_node]
    mock_core_v1.list_node.return_value = mock_nodes
    
    vcpu_price, memory_price = pricing_detector.auto_detect_pricing()
    
    # Should return default pricing
    assert vcpu_price == 0.04
    assert memory_price == 0.005


def test_get_pricing_info(pricing_detector):
    """Test getting pricing info"""
    pricing_detector.detected_provider = 'gcp'
    pricing_detector.detected_pricing = {'vcpu': 0.0475, 'memory_gb': 0.0063}
    
    info = pricing_detector.get_pricing_info()
    
    assert info['provider'] == 'gcp'
    assert info['vcpu_price'] == 0.0475
    assert info['memory_gb_price'] == 0.0063
    assert info['auto_detected'] is True
    assert 'GCP' in info['source']


def test_pricing_values_reasonable(pricing_detector):
    """Test that all pricing values are reasonable"""
    # Check GCP pricing
    for family, pricing in pricing_detector.GCP_PRICING.items():
        assert 0.01 < pricing['vcpu'] < 0.5, f"GCP {family} vCPU price seems unreasonable"
        assert 0.001 < pricing['memory_gb'] < 0.1, f"GCP {family} memory price seems unreasonable"
    
    # Check AWS pricing
    for family, pricing in pricing_detector.AWS_PRICING.items():
        assert 0.01 < pricing['vcpu'] < 0.5, f"AWS {family} vCPU price seems unreasonable"
        assert 0.001 < pricing['memory_gb'] < 0.1, f"AWS {family} memory price seems unreasonable"
    
    # Check Azure pricing
    for family, pricing in pricing_detector.AZURE_PRICING.items():
        assert 0.01 < pricing['vcpu'] < 0.5, f"Azure {family} vCPU price seems unreasonable"
        assert 0.001 < pricing['memory_gb'] < 0.1, f"Azure {family} memory price seems unreasonable"
