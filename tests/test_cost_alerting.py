"""
Tests for Cost Alerting Module
"""

import pytest
from unittest.mock import Mock, MagicMock, patch


def test_cost_alerting_import():
    """Test that cost alerting module can be imported"""
    from src.cost_alerting import CostAlerting
    assert CostAlerting is not None


def test_cost_alerting_initialization():
    """Test CostAlerting initialization"""
    from src.cost_alerting import CostAlerting
    
    mock_realtime_cost = Mock()
    mock_operator = Mock()
    
    alerting = CostAlerting(mock_realtime_cost, mock_operator)
    
    assert alerting.realtime_cost == mock_realtime_cost
    assert alerting.operator == mock_operator
    assert alerting.enabled == False  # Default disabled


def test_get_config():
    """Test getting alerting configuration"""
    from src.cost_alerting import CostAlerting
    
    mock_realtime_cost = Mock()
    mock_operator = Mock()
    
    alerting = CostAlerting(mock_realtime_cost, mock_operator)
    config = alerting.get_config()
    
    assert 'enabled' in config
    assert 'alert_time' in config
    assert 'scheduler_running' in config


def test_configure():
    """Test configuring alerting settings"""
    from src.cost_alerting import CostAlerting
    
    mock_realtime_cost = Mock()
    mock_operator = Mock()
    
    alerting = CostAlerting(mock_realtime_cost, mock_operator)
    
    # Configure with new settings
    config = alerting.configure(
        enabled=True,
        alert_time='10:00',
        slack_webhook_url='https://hooks.slack.com/test'
    )
    
    assert config['enabled'] == True
    assert config['alert_time'] == '10:00'
    
    # Stop scheduler for cleanup
    alerting.stop_scheduler()


def test_format_slack_message():
    """Test Slack message formatting"""
    from src.cost_alerting import CostAlerting
    
    mock_realtime_cost = Mock()
    mock_operator = Mock()
    
    alerting = CostAlerting(mock_realtime_cost, mock_operator)
    
    report = {
        'timestamp': '2026-01-06T10:00:00',
        'report_date': '2026-01-06',
        'cluster': {
            'total_nodes': 3,
            'total_vcpu': 12,
            'total_memory_gb': 48,
            'cpu_utilization': 45.5,
            'memory_utilization': 62.3,
        },
        'costs': {
            'daily': 28.80,
            'monthly': 864.00,
            'yearly': 10512.00,
        },
        'waste': {
            'daily': 8.64,
            'monthly': 259.20,
            'percentage': 30.0,
        },
        'top_workloads': [],
        'top_wasteful': [],
        'workload_count': 25,
    }
    
    message = alerting.format_slack_message(report)
    
    assert 'blocks' in message
    assert 'text' in message
    assert 'Daily Cost Report' in message['text']


def test_format_slack_message_error():
    """Test Slack message formatting with error"""
    from src.cost_alerting import CostAlerting
    
    mock_realtime_cost = Mock()
    mock_operator = Mock()
    
    alerting = CostAlerting(mock_realtime_cost, mock_operator)
    
    report = {'error': 'Test error'}
    message = alerting.format_slack_message(report)
    
    assert 'text' in message
    assert 'Error' in message['text']
