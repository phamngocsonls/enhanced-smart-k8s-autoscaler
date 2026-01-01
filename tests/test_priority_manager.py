"""
Tests for Priority Manager
"""

import pytest
from unittest.mock import Mock
from src.priority_manager import PriorityManager, Priority, PRIORITY_CONFIGS


@pytest.fixture
def mock_db():
    """Mock database"""
    return Mock()


@pytest.fixture
def priority_manager(mock_db):
    """Create priority manager instance"""
    return PriorityManager(mock_db)


def test_set_and_get_priority(priority_manager):
    """Test setting and getting priority"""
    priority_manager.set_priority("test-deployment", "high")
    assert priority_manager.get_priority("test-deployment") == Priority.HIGH
    
    priority_manager.set_priority("test-deployment-2", "critical")
    assert priority_manager.get_priority("test-deployment-2") == Priority.CRITICAL


def test_default_priority(priority_manager):
    """Test default priority is medium"""
    assert priority_manager.get_priority("unknown-deployment") == Priority.MEDIUM


def test_invalid_priority_defaults_to_medium(priority_manager):
    """Test invalid priority defaults to medium"""
    priority_manager.set_priority("test-deployment", "invalid")
    assert priority_manager.get_priority("test-deployment") == Priority.MEDIUM


def test_get_config(priority_manager):
    """Test getting priority configuration"""
    priority_manager.set_priority("test-deployment", "critical")
    config = priority_manager.get_config("test-deployment")
    
    assert config.level == Priority.CRITICAL
    assert config.weight == 1.0
    assert config.target_adjustment == -15
    assert config.can_preempt is True
    assert config.can_be_preempted is False


def test_sort_deployments_by_priority(priority_manager):
    """Test sorting deployments by priority"""
    priority_manager.set_priority("low-dep", "low")
    priority_manager.set_priority("high-dep", "high")
    priority_manager.set_priority("critical-dep", "critical")
    priority_manager.set_priority("medium-dep", "medium")
    
    deployments = [
        {'deployment': 'low-dep'},
        {'deployment': 'high-dep'},
        {'deployment': 'critical-dep'},
        {'deployment': 'medium-dep'}
    ]
    
    sorted_deps = priority_manager.sort_deployments_by_priority(deployments)
    
    # Should be sorted: critical, high, medium, low
    assert sorted_deps[0]['deployment'] == 'critical-dep'
    assert sorted_deps[1]['deployment'] == 'high-dep'
    assert sorted_deps[2]['deployment'] == 'medium-dep'
    assert sorted_deps[3]['deployment'] == 'low-dep'


def test_calculate_target_adjustment_normal_pressure(priority_manager):
    """Test target adjustment under normal pressure"""
    priority_manager.set_priority("test-deployment", "high")
    
    adjusted = priority_manager.calculate_target_adjustment(
        deployment="test-deployment",
        base_target=70,
        node_pressure=50.0,
        cluster_pressure=50.0
    )
    
    # High priority gets -10 adjustment: 70 - 10 = 60
    assert adjusted == 60


def test_calculate_target_adjustment_high_pressure(priority_manager):
    """Test target adjustment under high pressure"""
    priority_manager.set_priority("critical-dep", "critical")
    priority_manager.set_priority("low-dep", "low")
    
    # Critical should get MORE headroom under pressure
    critical_adjusted = priority_manager.calculate_target_adjustment(
        deployment="critical-dep",
        base_target=70,
        node_pressure=90.0,
        cluster_pressure=90.0
    )
    
    # Low should get LESS headroom under pressure
    low_adjusted = priority_manager.calculate_target_adjustment(
        deployment="low-dep",
        base_target=70,
        node_pressure=90.0,
        cluster_pressure=90.0
    )
    
    # Critical should have lower target (more headroom)
    assert critical_adjusted < 60
    # Low should have higher target (less headroom)
    assert low_adjusted > 80


def test_calculate_target_adjustment_low_pressure(priority_manager):
    """Test target adjustment under low pressure (cost optimization)"""
    priority_manager.set_priority("low-dep", "low")
    
    adjusted = priority_manager.calculate_target_adjustment(
        deployment="low-dep",
        base_target=70,
        node_pressure=30.0,
        cluster_pressure=30.0
    )
    
    # Low priority should optimize for cost under low pressure
    # Base: 70, adjustment: +10, low pressure: +5 = 85
    assert adjusted >= 80


def test_should_preempt_high_pressure(priority_manager):
    """Test preemption under high pressure"""
    priority_manager.set_priority("critical-dep", "critical")
    priority_manager.set_priority("low-dep", "low")
    
    # Critical can preempt low under high pressure
    can_preempt = priority_manager.should_preempt(
        requesting_deployment="critical-dep",
        target_deployment="low-dep",
        cluster_pressure=85.0
    )
    
    assert can_preempt is True


def test_should_not_preempt_low_pressure(priority_manager):
    """Test no preemption under low pressure"""
    priority_manager.set_priority("critical-dep", "critical")
    priority_manager.set_priority("low-dep", "low")
    
    # Should not preempt under low pressure
    can_preempt = priority_manager.should_preempt(
        requesting_deployment="critical-dep",
        target_deployment="low-dep",
        cluster_pressure=50.0
    )
    
    assert can_preempt is False


def test_should_not_preempt_same_priority(priority_manager):
    """Test no preemption between same priority"""
    priority_manager.set_priority("high-dep-1", "high")
    priority_manager.set_priority("high-dep-2", "high")
    
    can_preempt = priority_manager.should_preempt(
        requesting_deployment="high-dep-1",
        target_deployment="high-dep-2",
        cluster_pressure=90.0
    )
    
    assert can_preempt is False


def test_should_not_preempt_protected(priority_manager):
    """Test cannot preempt protected deployments"""
    priority_manager.set_priority("low-dep", "low")
    priority_manager.set_priority("critical-dep", "critical")
    
    # Low cannot preempt critical
    can_preempt = priority_manager.should_preempt(
        requesting_deployment="low-dep",
        target_deployment="critical-dep",
        cluster_pressure=90.0
    )
    
    assert can_preempt is False


def test_get_scale_speed_multiplier(priority_manager):
    """Test scale speed multipliers"""
    priority_manager.set_priority("critical-dep", "critical")
    priority_manager.set_priority("low-dep", "low")
    
    # Critical scales up faster
    critical_up = priority_manager.get_scale_speed_multiplier("critical-dep", "up")
    assert critical_up == 2.0
    
    # Critical scales down slower
    critical_down = priority_manager.get_scale_speed_multiplier("critical-dep", "down")
    assert critical_down == 0.25
    
    # Low scales up slower
    low_up = priority_manager.get_scale_speed_multiplier("low-dep", "up")
    assert low_up == 0.5
    
    # Low scales down faster
    low_down = priority_manager.get_scale_speed_multiplier("low-dep", "down")
    assert low_down == 2.0


def test_get_priority_stats(priority_manager):
    """Test getting priority statistics"""
    priority_manager.set_priority("critical-dep", "critical")
    priority_manager.set_priority("high-dep-1", "high")
    priority_manager.set_priority("high-dep-2", "high")
    priority_manager.set_priority("low-dep", "low")
    
    stats = priority_manager.get_priority_stats()
    
    assert stats['critical']['count'] == 1
    assert stats['high']['count'] == 2
    assert stats['low']['count'] == 1
    assert 'critical-dep' in stats['critical']['deployments']
    assert 'high-dep-1' in stats['high']['deployments']


def test_auto_detect_priority_payment(priority_manager):
    """Test auto-detection for payment service"""
    priority = priority_manager.auto_detect_priority(
        deployment_name="payment-service",
        labels={},
        annotations={}
    )
    
    assert priority == Priority.CRITICAL


def test_auto_detect_priority_api(priority_manager):
    """Test auto-detection for API service"""
    priority = priority_manager.auto_detect_priority(
        deployment_name="api-gateway",
        labels={},
        annotations={}
    )
    
    assert priority == Priority.HIGH


def test_auto_detect_priority_worker(priority_manager):
    """Test auto-detection for worker"""
    priority = priority_manager.auto_detect_priority(
        deployment_name="email-worker",
        labels={},
        annotations={}
    )
    
    assert priority == Priority.LOW


def test_auto_detect_priority_from_label(priority_manager):
    """Test auto-detection from label"""
    priority = priority_manager.auto_detect_priority(
        deployment_name="some-service",
        labels={'priority': 'high'},
        annotations={}
    )
    
    assert priority == Priority.HIGH


def test_auto_detect_priority_from_annotation(priority_manager):
    """Test auto-detection from annotation"""
    priority = priority_manager.auto_detect_priority(
        deployment_name="some-service",
        labels={},
        annotations={'autoscaler.k8s.io/priority': 'critical'}
    )
    
    assert priority == Priority.CRITICAL


def test_auto_detect_priority_default(priority_manager):
    """Test auto-detection defaults to medium"""
    priority = priority_manager.auto_detect_priority(
        deployment_name="random-service",
        labels={},
        annotations={}
    )
    
    assert priority == Priority.MEDIUM


def test_priority_configs_exist():
    """Test all priority configs are defined"""
    assert Priority.CRITICAL in PRIORITY_CONFIGS
    assert Priority.HIGH in PRIORITY_CONFIGS
    assert Priority.MEDIUM in PRIORITY_CONFIGS
    assert Priority.LOW in PRIORITY_CONFIGS
    assert Priority.BEST_EFFORT in PRIORITY_CONFIGS


def test_priority_weights_ordered():
    """Test priority weights are properly ordered"""
    weights = [PRIORITY_CONFIGS[p].weight for p in Priority]
    assert weights == sorted(weights, reverse=True)


def test_min_headroom_requirements():
    """Test minimum headroom requirements"""
    assert PRIORITY_CONFIGS[Priority.CRITICAL].min_headroom >= 30
    assert PRIORITY_CONFIGS[Priority.HIGH].min_headroom >= 20
    assert PRIORITY_CONFIGS[Priority.MEDIUM].min_headroom >= 10
    assert PRIORITY_CONFIGS[Priority.LOW].min_headroom >= 5
    assert PRIORITY_CONFIGS[Priority.BEST_EFFORT].min_headroom >= 0
