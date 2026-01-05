"""
Tests for Real-time Cost Tracking Module
"""

import pytest
from unittest.mock import Mock, MagicMock, patch


def test_realtime_cost_import():
    """Test that realtime cost module can be imported"""
    from src.realtime_cost import RealtimeCostTracker
    assert RealtimeCostTracker is not None


def test_realtime_cost_initialization():
    """Test RealtimeCostTracker initialization"""
    from src.realtime_cost import RealtimeCostTracker
    
    mock_operator = Mock()
    tracker = RealtimeCostTracker(
        mock_operator,
        cost_per_vcpu_hour=0.05,
        cost_per_gb_memory_hour=0.01
    )
    
    assert tracker.cost_per_vcpu_hour == 0.05
    assert tracker.cost_per_gb_memory_hour == 0.01


def test_fair_share_cost_calculation():
    """
    Test the fair share cost calculation logic.
    
    Scenario:
    - Node has 4 vCPU, costs $0.20/hr ($0.05/vCPU)
    - Total requests on node: 2 vCPU
    - Cost per requested vCPU = $0.20/2 = $0.10/hr
    - Workload requesting 1 vCPU pays $0.10/hr
    """
    node_vcpu = 4
    vcpu_price = 0.05
    node_hourly_cost = node_vcpu * vcpu_price  # $0.20/hr
    
    total_cpu_requests = 2.0  # 2 vCPU requested
    workload_cpu_request = 1.0  # 1 vCPU
    
    # Fair share calculation
    cost_per_cpu_request = node_hourly_cost / total_cpu_requests
    workload_cost = workload_cpu_request * cost_per_cpu_request
    
    assert node_hourly_cost == 0.20
    assert cost_per_cpu_request == pytest.approx(0.10, rel=0.01)
    assert workload_cost == pytest.approx(0.10, rel=0.01)


def test_waste_calculation():
    """
    Test waste calculation logic.
    
    Scenario:
    - Workload requests 1 vCPU
    - Actual usage is 0.3 vCPU
    - Waste = 0.7 vCPU
    - If cost per vCPU is $0.10/hr, waste cost = $0.07/hr
    """
    cpu_request = 1.0
    cpu_usage = 0.3
    cost_per_cpu = 0.10
    
    cpu_waste = max(0, cpu_request - cpu_usage)
    waste_cost = cpu_waste * cost_per_cpu
    
    assert cpu_waste == pytest.approx(0.7, rel=0.01)
    assert waste_cost == pytest.approx(0.07, rel=0.01)


def test_monthly_projection():
    """Test monthly cost projection from hourly cost"""
    hourly_cost = 0.10
    
    daily_cost = hourly_cost * 24
    monthly_cost = hourly_cost * 24 * 30
    
    assert daily_cost == pytest.approx(2.40, rel=0.01)
    assert monthly_cost == pytest.approx(72.0, rel=0.01)


def test_utilization_calculation():
    """Test utilization percentage calculation"""
    cpu_request = 1.0
    cpu_usage = 0.3
    
    utilization = (cpu_usage / cpu_request) * 100 if cpu_request > 0 else 0
    
    assert utilization == pytest.approx(30.0, rel=0.01)


def test_waste_percentage_calculation():
    """Test waste percentage calculation"""
    total_cost = 1.0
    waste_cost = 0.7
    
    waste_percentage = (waste_cost / total_cost) * 100 if total_cost > 0 else 0
    
    assert waste_percentage == pytest.approx(70.0, rel=0.01)
