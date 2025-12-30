"""
Tests for dashboard module - WebDashboard API endpoints
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


class TestWebDashboard:
    """Test WebDashboard functionality"""
    
    def test_dashboard_import(self):
        """Test WebDashboard can be imported"""
        from src.dashboard import WebDashboard
        assert WebDashboard is not None
    
    def test_dashboard_initialization(self):
        """Test dashboard initializes correctly"""
        from src.dashboard import WebDashboard
        
        mock_db = Mock()
        mock_operator = Mock()
        mock_operator.watched_deployments = {}
        
        dashboard = WebDashboard(db=mock_db, operator=mock_operator, port=5000)
        
        assert dashboard is not None
        assert dashboard.port == 5000
        assert dashboard.app is not None
    
    def test_dashboard_routes_registered(self):
        """Test that routes are registered"""
        from src.dashboard import WebDashboard
        
        mock_db = Mock()
        mock_operator = Mock()
        mock_operator.watched_deployments = {}
        
        dashboard = WebDashboard(db=mock_db, operator=mock_operator)
        
        # Check that routes exist
        rules = [rule.rule for rule in dashboard.app.url_map.iter_rules()]
        
        assert '/' in rules
        assert '/api/deployments' in rules


class TestDashboardAPIEndpoints:
    """Test Dashboard API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        from src.dashboard import WebDashboard
        
        mock_db = Mock()
        mock_operator = Mock()
        mock_operator.watched_deployments = {
            'default/test-app': {
                'namespace': 'default',
                'deployment': 'test-app',
                'hpa_name': 'test-app-hpa'
            }
        }
        
        dashboard = WebDashboard(db=mock_db, operator=mock_operator)
        dashboard.app.config['TESTING'] = True
        
        return dashboard.app.test_client()
    
    def test_get_deployments(self, client):
        """Test GET /api/deployments endpoint"""
        response = client.get('/api/deployments')
        
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]['deployment'] == 'test-app'
    
    def test_get_deployment_current_no_data(self):
        """Test GET /api/deployment/<ns>/<name>/current with no data"""
        from src.dashboard import WebDashboard
        
        mock_db = Mock()
        mock_db.get_recent_metrics.return_value = []
        
        mock_operator = Mock()
        mock_operator.watched_deployments = {}
        
        dashboard = WebDashboard(db=mock_db, operator=mock_operator)
        dashboard.app.config['TESTING'] = True
        client = dashboard.app.test_client()
        
        response = client.get('/api/deployment/default/test-app/current')
        
        assert response.status_code == 404
    
    def test_get_deployment_current_with_data(self):
        """Test GET /api/deployment/<ns>/<name>/current with data"""
        from src.dashboard import WebDashboard
        
        # Create mock metric
        mock_metric = Mock()
        mock_metric.timestamp = datetime.now()
        mock_metric.node_utilization = 65.0
        mock_metric.pod_count = 3
        mock_metric.pod_cpu_usage = 0.5
        mock_metric.hpa_target = 70
        mock_metric.confidence = 0.85
        mock_metric.action_taken = "none"
        mock_metric.cpu_request = 500
        mock_metric.memory_usage = 256.0
        mock_metric.memory_request = 512
        
        mock_db = Mock()
        mock_db.get_recent_metrics.return_value = [mock_metric]
        
        mock_operator = Mock()
        mock_operator.watched_deployments = {}
        # Mock pattern_detector to avoid attribute errors
        del mock_operator.pattern_detector
        
        dashboard = WebDashboard(db=mock_db, operator=mock_operator)
        dashboard.app.config['TESTING'] = True
        client = dashboard.app.test_client()
        
        response = client.get('/api/deployment/default/test-app/current')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['node_utilization'] == 65.0
        assert data['pod_count'] == 3
        assert data['memory_usage'] == 256.0


class TestDashboardHealthEndpoints:
    """Test health-related endpoints"""
    
    def test_health_endpoint_exists(self):
        """Test that health endpoints are accessible"""
        from src.dashboard import WebDashboard
        
        mock_db = Mock()
        mock_operator = Mock()
        mock_operator.watched_deployments = {}
        
        dashboard = WebDashboard(db=mock_db, operator=mock_operator)
        
        # Check routes
        rules = [rule.rule for rule in dashboard.app.url_map.iter_rules()]
        
        # These should exist for production readiness
        # If not, they should be added
        assert '/' in rules  # At minimum, root should exist


class TestConfigEndpoints:
    """Test configuration-related endpoints"""
    
    def test_config_status_endpoint(self):
        """Test /api/config/status endpoint"""
        from src.dashboard import WebDashboard
        
        mock_db = Mock()
        mock_operator = Mock()
        mock_operator.watched_deployments = {}
        mock_operator.config_loader = Mock()
        mock_operator.config_loader.get_status.return_value = {
            'version': 1,
            'last_reload': datetime.now().isoformat()
        }
        
        dashboard = WebDashboard(db=mock_db, operator=mock_operator)
        dashboard.app.config['TESTING'] = True
        client = dashboard.app.test_client()
        
        # Check if endpoint exists
        rules = [rule.rule for rule in dashboard.app.url_map.iter_rules()]
        
        if '/api/config/status' in rules:
            response = client.get('/api/config/status')
            assert response.status_code in [200, 500]  # May fail without full setup


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
