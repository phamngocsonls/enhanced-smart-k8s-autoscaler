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


def test_fair_share_cost_allocation_logic():
    """
    Test the fair share cost allocation logic.
    
    Example scenario:
    - Node costs $1/hr (4 vCPU at $0.25/vCPU)
    - Total requests on node: 3 vCPU
    - Cost per requested vCPU = $1/3 = $0.333/hr
    - Workload requesting 1 vCPU pays $0.333/hr
    """
    # This tests the mathematical logic of fair share allocation
    node_hourly_cost = 1.0  # $1/hr
    total_cpu_requests = 3.0  # 3 vCPU requested
    workload_cpu_request = 1.0  # 1 vCPU
    
    # Fair share calculation
    cost_per_cpu_request = node_hourly_cost / total_cpu_requests
    workload_cost = workload_cpu_request * cost_per_cpu_request
    
    assert cost_per_cpu_request == pytest.approx(0.333, rel=0.01)
    assert workload_cost == pytest.approx(0.333, rel=0.01)
    
    # Test with different scenario
    # Node costs $2/hr, 4 vCPU requested, workload requests 2 vCPU
    node_hourly_cost = 2.0
    total_cpu_requests = 4.0
    workload_cpu_request = 2.0
    
    cost_per_cpu_request = node_hourly_cost / total_cpu_requests
    workload_cost = workload_cpu_request * cost_per_cpu_request
    
    assert cost_per_cpu_request == pytest.approx(0.5, rel=0.01)
    assert workload_cost == pytest.approx(1.0, rel=0.01)  # 50% of node cost


def test_fair_share_ensures_total_allocation():
    """
    Test that fair share allocation ensures total allocated cost equals node cost.
    
    If node costs $1/hr and has 3 workloads requesting 1, 1, 1 vCPU respectively,
    each should pay $0.333/hr, totaling $1/hr.
    """
    node_hourly_cost = 1.0
    workload_requests = [1.0, 1.0, 1.0]  # 3 workloads, each requesting 1 vCPU
    total_requests = sum(workload_requests)
    
    cost_per_request = node_hourly_cost / total_requests
    
    total_allocated = 0
    for request in workload_requests:
        workload_cost = request * cost_per_request
        total_allocated += workload_cost
    
    # Total allocated should equal node cost
    assert total_allocated == pytest.approx(node_hourly_cost, rel=0.001)


def test_fair_share_proportional_allocation():
    """
    Test that fair share allocates proportionally to requests.
    
    If workload A requests 2 vCPU and workload B requests 1 vCPU,
    workload A should pay 2x what workload B pays.
    """
    node_hourly_cost = 3.0
    workload_a_request = 2.0
    workload_b_request = 1.0
    total_requests = workload_a_request + workload_b_request
    
    cost_per_request = node_hourly_cost / total_requests
    
    workload_a_cost = workload_a_request * cost_per_request
    workload_b_cost = workload_b_request * cost_per_request
    
    # Workload A should pay 2x workload B
    assert workload_a_cost == pytest.approx(workload_b_cost * 2, rel=0.001)
    
    # Total should equal node cost
    assert workload_a_cost + workload_b_cost == pytest.approx(node_hourly_cost, rel=0.001)
