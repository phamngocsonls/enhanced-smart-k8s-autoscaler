"""
Tests for Cost Allocation Module
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.cost_allocation import CostAllocator


@pytest.fixture
def mock_db():
    """Mock database"""
    db = Mock()
    db.conn = Mock()
    return db


@pytest.fixture
def mock_operator():
    """Mock operator"""
    operator = Mock()
    operator.config = {
        'cost_per_vcpu_hour': 0.04,
        'cost_per_gb_memory_hour': 0.005
    }
    operator.watched_deployments = {
        'default/app1': {
            'namespace': 'default',
            'deployment': 'app1',
            'hpa_name': 'app1-hpa'
        },
        'production/app2': {
            'namespace': 'production',
            'deployment': 'app2',
            'hpa_name': 'app2-hpa'
        }
    }
    
    # Mock apps_v1 API
    operator.apps_v1 = Mock()
    
    return operator


@pytest.fixture
def cost_allocator(mock_db, mock_operator):
    """Create cost allocator instance"""
    return CostAllocator(mock_db, mock_operator)


def test_extract_cost_tags(cost_allocator):
    """Test extracting cost tags from labels"""
    labels = {
        'team': 'platform',
        'app': 'api-gateway',
        'env': 'production',
        'cost-center': 'engineering'
    }
    
    tags = cost_allocator.extract_cost_tags(labels)
    
    assert tags['team'] == 'platform'
    assert tags['project'] == 'api-gateway'
    assert tags['environment'] == 'production'
    assert tags['cost_center'] == 'engineering'


def test_extract_cost_tags_alternative_keys(cost_allocator):
    """Test extracting cost tags with alternative label keys"""
    labels = {
        'owner': 'backend-team',
        'application': 'user-service',
        'stage': 'staging'
    }
    
    tags = cost_allocator.extract_cost_tags(labels)
    
    assert tags['team'] == 'backend-team'
    assert tags['project'] == 'user-service'
    assert tags['environment'] == 'staging'


def test_calculate_deployment_cost(cost_allocator, mock_operator):
    """Test calculating deployment cost"""
    # Mock deployment
    mock_dep = Mock()
    mock_dep.spec.replicas = 3
    
    # Mock container with resources
    mock_container = Mock()
    mock_container.resources.requests = {
        'cpu': '500m',
        'memory': '1Gi'
    }
    mock_dep.spec.template.spec.containers = [mock_container]
    
    mock_operator.apps_v1.read_namespaced_deployment.return_value = mock_dep
    
    # Calculate cost for 24 hours
    cost = cost_allocator.calculate_deployment_cost('default', 'app1', hours=24)
    
    # Expected: 3 replicas * 0.5 CPU * 24 hours * $0.045 = $1.62
    # Expected: 3 replicas * 1 GB * 24 hours * $0.006 = $0.432
    # Total: $2.052
    assert cost['cpu_cost'] == pytest.approx(1.62, rel=0.01)
    assert cost['memory_cost'] == pytest.approx(0.432, rel=0.01)
    assert cost['total_cost'] == pytest.approx(2.052, rel=0.01)
    assert cost['replicas'] == 3


def test_calculate_deployment_cost_zero_replicas(cost_allocator, mock_operator):
    """Test calculating cost for deployment with zero replicas"""
    mock_dep = Mock()
    mock_dep.spec.replicas = 0
    
    mock_operator.apps_v1.read_namespaced_deployment.return_value = mock_dep
    
    cost = cost_allocator.calculate_deployment_cost('default', 'app1', hours=24)
    
    assert cost['total_cost'] == 0
    assert cost['replicas'] == 0


def test_get_team_costs(cost_allocator, mock_operator):
    """Test getting costs grouped by team"""
    # Mock deployment with labels
    mock_dep = Mock()
    mock_dep.metadata.labels = {'team': 'platform'}
    mock_dep.spec.replicas = 2
    
    mock_container = Mock()
    mock_container.resources.requests = {
        'cpu': '1000m',
        'memory': '2Gi'
    }
    mock_dep.spec.template.spec.containers = [mock_container]
    
    mock_operator.apps_v1.read_namespaced_deployment.return_value = mock_dep
    
    team_costs = cost_allocator.get_team_costs(hours=24)
    
    assert 'platform' in team_costs
    assert team_costs['platform']['deployment_count'] == 2
    assert team_costs['platform']['total_cost'] > 0


def test_get_namespace_costs(cost_allocator, mock_operator):
    """Test getting costs grouped by namespace"""
    mock_dep = Mock()
    mock_dep.spec.replicas = 1
    
    mock_container = Mock()
    mock_container.resources.requests = {
        'cpu': '500m',
        'memory': '1Gi'
    }
    mock_dep.spec.template.spec.containers = [mock_container]
    
    mock_operator.apps_v1.read_namespaced_deployment.return_value = mock_dep
    
    namespace_costs = cost_allocator.get_namespace_costs(hours=24)
    
    assert 'default' in namespace_costs
    assert 'production' in namespace_costs
    assert namespace_costs['default']['deployment_count'] == 1
    assert namespace_costs['production']['deployment_count'] == 1


def test_detect_cost_anomalies_insufficient_data(cost_allocator, mock_db):
    """Test anomaly detection with insufficient data"""
    # Mock cursor with minimal data
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = [
        ('2024-01-01', 'default/app1', 2, 0.5, 1.0),
        ('2024-01-02', 'default/app1', 2, 0.5, 1.0)
    ]
    mock_db.conn.cursor.return_value = mock_cursor
    
    anomalies = cost_allocator.detect_cost_anomalies()
    
    # Should return empty list with insufficient data
    assert anomalies == []


def test_get_idle_resources(cost_allocator, mock_db, mock_operator):
    """Test identifying idle resources"""
    # Mock database query
    mock_cursor = Mock()
    mock_cursor.fetchone.return_value = (0.1, 0.5, 2)  # 10% CPU, 50% memory, 2 replicas
    mock_db.conn.cursor.return_value = mock_cursor
    
    # Mock deployment
    mock_dep = Mock()
    mock_dep.spec.replicas = 2
    
    mock_container = Mock()
    mock_container.resources.requests = {
        'cpu': '1000m',
        'memory': '2Gi'
    }
    mock_dep.spec.template.spec.containers = [mock_container]
    
    mock_operator.apps_v1.read_namespaced_deployment.return_value = mock_dep
    
    idle_resources = cost_allocator.get_idle_resources(utilization_threshold=0.2)
    
    # Should identify app1 as idle (10% CPU < 20% threshold)
    assert len(idle_resources) > 0
    assert idle_resources[0]['cpu_utilization'] == 10.0
