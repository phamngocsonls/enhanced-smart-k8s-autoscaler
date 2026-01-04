"""
Tests for Reporting Module
"""

import pytest
from unittest.mock import Mock, MagicMock
from src.reporting import ReportGenerator


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
    operator.watched_deployments = {
        'default/app1': {
            'namespace': 'default',
            'deployment': 'app1',
            'hpa_name': 'app1-hpa'
        }
    }
    return operator


@pytest.fixture
def mock_cost_allocator():
    """Mock cost allocator"""
    allocator = Mock()
    
    # Mock team costs
    allocator.get_team_costs.return_value = {
        'platform': {
            'deployments': [],
            'total_cost': 100.0,
            'cpu_cost': 60.0,
            'memory_cost': 40.0,
            'deployment_count': 5
        }
    }
    
    # Mock cost trends
    allocator.get_cost_trends.return_value = {
        'trends': [
            {'date': '2024-01-01', 'total_cost': 95.0, 'deployment_count': 5},
            {'date': '2024-01-02', 'total_cost': 100.0, 'deployment_count': 5},
            {'date': '2024-01-03', 'total_cost': 105.0, 'deployment_count': 5}
        ],
        'days': 30,
        'total_period_cost': 3000.0
    }
    
    # Mock anomalies
    allocator.detect_cost_anomalies.return_value = []
    
    # Mock idle resources
    allocator.get_idle_resources.return_value = [
        {
            'namespace': 'default',
            'deployment': 'app1',
            'cpu_utilization': 15.0,
            'memory_utilization': 20.0,
            'daily_cost': 10.0,
            'wasted_cost': 8.0,
            'monthly_waste': 240.0
        }
    ]
    
    return allocator


@pytest.fixture
def report_generator(mock_db, mock_operator, mock_cost_allocator):
    """Create report generator instance"""
    return ReportGenerator(mock_db, mock_operator, mock_cost_allocator)


def test_generate_executive_summary(report_generator, mock_db):
    """Test generating executive summary"""
    # Mock scaling events
    mock_cursor = Mock()
    mock_cursor.fetchone.return_value = (50, 30, 20)  # total, scale_ups, scale_downs
    mock_db.conn.cursor.return_value = mock_cursor
    
    report = report_generator.generate_executive_summary(days=30)
    
    assert 'generated_at' in report
    assert 'summary' in report
    assert report['summary']['total_deployments'] == 1
    assert report['summary']['daily_cost'] == 100.0
    assert report['summary']['monthly_cost'] == 3000.0
    assert 'cost_breakdown' in report
    assert 'alerts' in report
    assert 'scaling_activity' in report
    assert 'recommendations' in report


def test_generate_team_report(report_generator, mock_db):
    """Test generating team-specific report"""
    # Mock deployment metrics
    mock_cursor = Mock()
    mock_cursor.fetchone.return_value = (0.5, 1.0, 2, 1, 3)  # avg_cpu, avg_mem, avg_replicas, min, max
    mock_db.conn.cursor.return_value = mock_cursor
    
    report = report_generator.generate_team_report('platform', days=30)
    
    assert report['team'] == 'platform'
    assert 'summary' in report
    assert report['summary']['deployment_count'] == 5
    assert report['summary']['daily_cost'] == 100.0
    assert 'deployments' in report


def test_generate_team_report_not_found(report_generator):
    """Test generating report for non-existent team"""
    report = report_generator.generate_team_report('nonexistent', days=30)
    
    assert 'error' in report
    assert 'not found' in report['error'].lower()


def test_generate_cost_forecast(report_generator, mock_cost_allocator):
    """Test generating cost forecast"""
    # Mock trends with upward trend
    mock_cost_allocator.get_cost_trends.return_value = {
        'trends': [
            {'date': f'2024-01-{i:02d}', 'total_cost': 90 + i, 'deployment_count': 5}
            for i in range(1, 31)
        ],
        'days': 30
    }
    
    forecast = report_generator.generate_cost_forecast(days_ahead=90)
    
    assert 'forecasts' in forecast
    assert len(forecast['forecasts']) == 90
    assert 'trend' in forecast
    assert forecast['trend'] in ['increasing', 'decreasing', 'stable']
    assert 'totals' in forecast
    assert '30_day' in forecast['totals']
    assert '60_day' in forecast['totals']
    assert '90_day' in forecast['totals']


def test_generate_cost_forecast_insufficient_data(report_generator, mock_cost_allocator):
    """Test forecast with insufficient data"""
    mock_cost_allocator.get_cost_trends.return_value = {
        'trends': [
            {'date': '2024-01-01', 'total_cost': 100.0, 'deployment_count': 5}
        ],
        'days': 1
    }
    
    forecast = report_generator.generate_cost_forecast(days_ahead=90)
    
    assert 'error' in forecast


def test_generate_roi_report(report_generator, mock_cost_allocator):
    """Test generating ROI report"""
    report = report_generator.generate_roi_report()
    
    assert 'current_monthly_cost' in report
    assert 'potential_monthly_savings' in report
    assert 'potential_annual_savings' in report
    assert 'savings_percentage' in report
    assert 'optimization_breakdown' in report
    assert 'top_opportunities' in report
    
    # Check calculations
    assert report['potential_monthly_savings'] == 240.0  # From mock idle resources
    assert report['potential_annual_savings'] == 240.0 * 12


def test_generate_trend_analysis(report_generator, mock_cost_allocator):
    """Test generating trend analysis"""
    # Mock trends with enough data for WoW and MoM
    trends = []
    for i in range(1, 61):
        trends.append({
            'date': f'2024-01-{i:02d}' if i <= 31 else f'2024-02-{i-31:02d}',
            'total_cost': 100.0 + (i * 0.5),  # Increasing trend
            'deployment_count': 5
        })
    
    mock_cost_allocator.get_cost_trends.return_value = {
        'trends': trends,
        'days': 60
    }
    
    analysis = report_generator.generate_trend_analysis(days=60)
    
    assert 'cost_trends' in analysis
    assert 'week_over_week_change' in analysis['cost_trends']
    assert 'month_over_month_change' in analysis['cost_trends']
    assert 'trend_direction' in analysis['cost_trends']
    assert analysis['cost_trends']['trend_direction'] in ['up', 'down', 'stable']


def test_calculate_efficiency_score(report_generator, mock_cost_allocator):
    """Test calculating efficiency score"""
    score = report_generator._calculate_efficiency_score()
    
    # With mock data: 15% CPU + 20% memory = 35% / 2 = 17.5%
    assert 0 <= score <= 100
    assert score == 17  # int(17.5)


def test_calculate_efficiency_score_no_data(report_generator, mock_cost_allocator):
    """Test efficiency score with no idle resources"""
    mock_cost_allocator.get_idle_resources.return_value = []
    
    score = report_generator._calculate_efficiency_score()
    
    assert score == 100  # Perfect efficiency when no idle resources


def test_generate_recommendations(report_generator):
    """Test generating recommendations"""
    idle_resources = [
        {
            'namespace': 'default',
            'deployment': 'app1',
            'cpu_utilization': 10.0,
            'monthly_waste': 200.0
        }
    ]
    anomalies = [
        {'date': '2024-01-01', 'cost': 500.0, 'severity': 'high'}
    ]
    
    recommendations = report_generator._generate_recommendations(idle_resources, anomalies)
    
    assert len(recommendations) > 0
    assert any('Right-size' in r for r in recommendations)
    assert any('anomalies' in r for r in recommendations)
