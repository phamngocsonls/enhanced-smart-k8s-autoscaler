"""
Tests for Autopilot Mode - Automatic Resource Tuning
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.autopilot import (
    AutopilotManager,
    AutopilotLevel,
    ResourceRecommendation,
    AutopilotAction,
    ResourceSnapshot,
    HealthCheckResult,
    create_autopilot_manager
)


class TestAutopilotLevel:
    """Test AutopilotLevel enum"""
    
    def test_level_values(self):
        """Test level ordering"""
        assert AutopilotLevel.DISABLED.value == 0
        assert AutopilotLevel.OBSERVE.value == 1
        assert AutopilotLevel.RECOMMEND.value == 2
        assert AutopilotLevel.AUTOPILOT.value == 3
    
    def test_level_comparison(self):
        """Test level comparison"""
        assert AutopilotLevel.AUTOPILOT.value > AutopilotLevel.RECOMMEND.value
        assert AutopilotLevel.RECOMMEND.value > AutopilotLevel.OBSERVE.value


class TestResourceRecommendation:
    """Test ResourceRecommendation dataclass"""
    
    def test_create_recommendation(self):
        """Test creating a recommendation"""
        rec = ResourceRecommendation(
            namespace="default",
            deployment="test-app",
            container="main",
            current_cpu_request=500,
            current_memory_request=512,
            recommended_cpu_request=300,
            recommended_memory_request=384,
            cpu_p95=250.0,
            memory_p95=320.0,
            confidence=0.85,
            savings_percent=35.0
        )
        
        assert rec.namespace == "default"
        assert rec.deployment == "test-app"
        assert rec.current_cpu_request == 500
        assert rec.recommended_cpu_request == 300
        assert rec.confidence == 0.85
        assert rec.is_safe == True
        assert rec.applied_at is None


class TestAutopilotManager:
    """Test AutopilotManager class"""
    
    @pytest.fixture
    def manager(self):
        """Create a test manager"""
        with patch('src.autopilot.client'):
            manager = AutopilotManager(
                enabled=True,
                level=AutopilotLevel.RECOMMEND,
                min_observation_days=7,
                min_confidence=0.80,
                max_change_percent=30,
                cooldown_hours=24
            )
            manager.k8s_available = False  # Disable K8s for unit tests
            return manager
    
    def test_init_disabled(self):
        """Test initialization with disabled state"""
        with patch('src.autopilot.client'):
            manager = AutopilotManager(enabled=False)
            assert manager.enabled == False
            assert manager.level == AutopilotLevel.RECOMMEND
    
    def test_init_enabled(self):
        """Test initialization with enabled state"""
        with patch('src.autopilot.client'):
            manager = AutopilotManager(
                enabled=True,
                level=AutopilotLevel.AUTOPILOT
            )
            assert manager.enabled == True
            assert manager.level == AutopilotLevel.AUTOPILOT
    
    def test_calculate_recommendation_insufficient_data(self, manager):
        """Test recommendation with insufficient observation days"""
        result = manager.calculate_recommendation(
            namespace="default",
            deployment="test-app",
            current_cpu_request=500,
            current_memory_request=512,
            cpu_p95=250.0,
            memory_p95=320.0,
            observation_days=3  # Less than min_observation_days
        )
        
        assert result is None
    
    def test_calculate_recommendation_small_change(self, manager):
        """Test recommendation skipped for small changes"""
        result = manager.calculate_recommendation(
            namespace="default",
            deployment="test-app",
            current_cpu_request=500,
            current_memory_request=512,
            cpu_p95=410.0,  # After buffer: 492, change ~1.6%
            memory_p95=400.0,  # After buffer: 500, change ~2.3%
            observation_days=14
        )
        
        # Small changes (< 5%) should be skipped
        assert result is None
    
    def test_calculate_recommendation_success(self, manager):
        """Test successful recommendation calculation"""
        result = manager.calculate_recommendation(
            namespace="default",
            deployment="test-app",
            current_cpu_request=500,
            current_memory_request=512,
            cpu_p95=300.0,
            memory_p95=350.0,
            observation_days=14
        )
        
        assert result is not None
        assert result.namespace == "default"
        assert result.deployment == "test-app"
        # Recommended should be P95 + buffer, but limited by max_change_percent
        # CPU: 300 * 1.20 = 360, change = 28% (within 30% limit)
        # Memory: 350 * 1.25 = 437.5, change = 14.5% (within 30% limit)
        assert result.recommended_cpu_request == int(300 * 1.20)  # 360
        assert result.recommended_memory_request == int(350 * 1.25)  # 437
        assert result.confidence > 0
        assert result.savings_percent > 0
    
    def test_calculate_recommendation_respects_minimums(self, manager):
        """Test that recommendations respect minimum values"""
        result = manager.calculate_recommendation(
            namespace="default",
            deployment="test-app",
            current_cpu_request=500,
            current_memory_request=512,
            cpu_p95=10.0,  # Very low
            memory_p95=20.0,  # Very low
            observation_days=14
        )
        
        assert result is not None
        assert result.recommended_cpu_request >= manager.min_cpu_request
        assert result.recommended_memory_request >= manager.min_memory_request
    
    def test_calculate_recommendation_limits_change(self, manager):
        """Test that large changes are limited"""
        result = manager.calculate_recommendation(
            namespace="default",
            deployment="test-app",
            current_cpu_request=1000,
            current_memory_request=1024,
            cpu_p95=100.0,  # 90% reduction requested
            memory_p95=100.0,
            observation_days=14
        )
        
        assert result is not None
        # Change should be limited to max_change_percent
        max_reduction = 1000 * (1 - manager.max_change_percent / 100)
        assert result.recommended_cpu_request >= max_reduction
    
    def test_calculate_recommendation_critical_priority(self, manager):
        """Test that critical priority requires manual approval"""
        result = manager.calculate_recommendation(
            namespace="default",
            deployment="test-app",
            current_cpu_request=500,
            current_memory_request=512,
            cpu_p95=200.0,
            memory_p95=256.0,
            observation_days=14,
            priority="critical"
        )
        
        assert result is not None
        assert result.is_safe == False
        assert "critical" in result.safety_reason.lower()
    
    def test_should_apply_disabled(self, manager):
        """Test should_apply when disabled"""
        manager.enabled = False
        rec = ResourceRecommendation(
            namespace="default",
            deployment="test-app",
            container="main",
            current_cpu_request=500,
            current_memory_request=512,
            recommended_cpu_request=300,
            recommended_memory_request=384,
            cpu_p95=250.0,
            memory_p95=320.0,
            confidence=0.90,
            savings_percent=35.0
        )
        
        should_apply, reason = manager.should_apply(rec)
        assert should_apply == False
        assert "disabled" in reason.lower()
    
    def test_should_apply_low_confidence(self, manager):
        """Test should_apply with low confidence"""
        manager.enabled = True
        manager.level = AutopilotLevel.AUTOPILOT
        
        rec = ResourceRecommendation(
            namespace="default",
            deployment="test-app",
            container="main",
            current_cpu_request=500,
            current_memory_request=512,
            recommended_cpu_request=300,
            recommended_memory_request=384,
            cpu_p95=250.0,
            memory_p95=320.0,
            confidence=0.50,  # Below threshold
            savings_percent=35.0
        )
        
        should_apply, reason = manager.should_apply(rec)
        assert should_apply == False
        assert "confidence" in reason.lower()
    
    def test_should_apply_not_safe(self, manager):
        """Test should_apply when not safe"""
        manager.enabled = True
        manager.level = AutopilotLevel.AUTOPILOT
        
        rec = ResourceRecommendation(
            namespace="default",
            deployment="test-app",
            container="main",
            current_cpu_request=500,
            current_memory_request=512,
            recommended_cpu_request=300,
            recommended_memory_request=384,
            cpu_p95=250.0,
            memory_p95=320.0,
            confidence=0.90,
            savings_percent=35.0,
            is_safe=False,
            safety_reason="Critical priority"
        )
        
        should_apply, reason = manager.should_apply(rec)
        assert should_apply == False
        assert "critical" in reason.lower()
    
    def test_should_apply_success(self, manager):
        """Test should_apply success case"""
        manager.enabled = True
        manager.level = AutopilotLevel.AUTOPILOT
        
        rec = ResourceRecommendation(
            namespace="default",
            deployment="test-app",
            container="main",
            current_cpu_request=500,
            current_memory_request=512,
            recommended_cpu_request=300,
            recommended_memory_request=384,
            cpu_p95=250.0,
            memory_p95=320.0,
            confidence=0.90,
            savings_percent=35.0,
            is_safe=True
        )
        
        should_apply, reason = manager.should_apply(rec)
        assert should_apply == True
        assert "passed" in reason.lower()
    
    def test_get_status(self, manager):
        """Test get_status returns correct structure"""
        status = manager.get_status()
        
        assert 'enabled' in status
        assert 'level' in status
        assert 'config' in status
        assert 'statistics' in status
        assert 'deployments_in_cooldown' in status
        
        assert status['enabled'] == True
        assert status['level'] == 'RECOMMEND'
        assert status['config']['min_confidence'] == 0.80
    
    def test_get_recommendations_empty(self, manager):
        """Test get_recommendations when empty"""
        recs = manager.get_recommendations()
        assert recs == []
    
    def test_get_recommendations_with_data(self, manager):
        """Test get_recommendations with data"""
        # Add a recommendation
        manager.calculate_recommendation(
            namespace="default",
            deployment="test-app",
            current_cpu_request=500,
            current_memory_request=512,
            cpu_p95=200.0,
            memory_p95=256.0,
            observation_days=14
        )
        
        recs = manager.get_recommendations()
        assert len(recs) == 1
        assert recs[0]['namespace'] == 'default'
        assert recs[0]['deployment'] == 'test-app'
    
    def test_get_recent_actions_empty(self, manager):
        """Test get_recent_actions when empty"""
        actions = manager.get_recent_actions()
        assert actions == []
    
    def test_cooldown_prevents_changes(self, manager):
        """Test that cooldown prevents rapid changes"""
        # Set a recent action time
        manager.last_action_time["default/test-app"] = datetime.now()
        
        result = manager.calculate_recommendation(
            namespace="default",
            deployment="test-app",
            current_cpu_request=500,
            current_memory_request=512,
            cpu_p95=200.0,
            memory_p95=256.0,
            observation_days=14
        )
        
        assert result is not None
        assert result.is_safe == False
        assert "cooldown" in result.safety_reason.lower()


class TestCreateAutopilotManager:
    """Test factory function"""
    
    def test_create_default(self):
        """Test creating manager with defaults"""
        with patch.dict('os.environ', {}, clear=True):
            with patch('src.autopilot.client'):
                manager = create_autopilot_manager()
                
                assert manager.enabled == False
                assert manager.level == AutopilotLevel.RECOMMEND
                assert manager.min_confidence == 0.80
    
    def test_create_enabled(self):
        """Test creating enabled manager"""
        env = {
            'ENABLE_AUTOPILOT': 'true',
            'AUTOPILOT_LEVEL': 'autopilot',
            'AUTOPILOT_MIN_CONFIDENCE': '0.90'
        }
        with patch.dict('os.environ', env, clear=True):
            with patch('src.autopilot.client'):
                manager = create_autopilot_manager()
                
                assert manager.enabled == True
                assert manager.level == AutopilotLevel.AUTOPILOT
                assert manager.min_confidence == 0.90
    
    def test_create_observe_level(self):
        """Test creating manager with observe level"""
        env = {
            'ENABLE_AUTOPILOT': 'true',
            'AUTOPILOT_LEVEL': 'observe'
        }
        with patch.dict('os.environ', env, clear=True):
            with patch('src.autopilot.client'):
                manager = create_autopilot_manager()
                
                assert manager.level == AutopilotLevel.OBSERVE


class TestAutopilotAction:
    """Test AutopilotAction dataclass"""
    
    def test_create_action(self):
        """Test creating an action"""
        action = AutopilotAction(
            namespace="default",
            deployment="test-app",
            action_type="cpu_request",
            old_value=500,
            new_value=300,
            reason="P95=250m, confidence=85%",
            applied_at=datetime.now()
        )
        
        assert action.namespace == "default"
        assert action.action_type == "cpu_request"
        assert action.old_value == 500
        assert action.new_value == 300
        assert action.rolled_back == False



class TestAutopilotDashboardAPI:
    """Test Autopilot Dashboard API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the dashboard"""
        import tempfile
        import os
        from src.dashboard import WebDashboard
        from src.intelligence import TimeSeriesDatabase
        from src.autopilot import create_autopilot_manager
        from unittest.mock import Mock
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db = TimeSeriesDatabase(os.path.join(tmpdir, 'test.db'))
            
            mock_operator = Mock()
            mock_operator.watched_deployments = {}
            mock_operator.config_loader = None
            mock_operator.autopilot_manager = create_autopilot_manager()
            
            dashboard = WebDashboard(db, mock_operator, port=5099)
            dashboard.app.config['TESTING'] = True
            
            with dashboard.app.test_client() as client:
                yield client
    
    def test_autopilot_status_endpoint(self, client):
        """Test /api/autopilot/status endpoint"""
        response = client.get('/api/autopilot/status')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'enabled' in data
        assert 'level' in data
        assert 'config' in data
        assert 'statistics' in data
    
    def test_autopilot_recommendations_endpoint(self, client):
        """Test /api/autopilot/recommendations endpoint"""
        response = client.get('/api/autopilot/recommendations')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'recommendations' in data
        assert 'count' in data
    
    def test_autopilot_actions_endpoint(self, client):
        """Test /api/autopilot/actions endpoint"""
        response = client.get('/api/autopilot/actions')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'actions' in data
        assert 'count' in data
    
    def test_autopilot_apply_no_recommendation(self, client):
        """Test /api/autopilot/apply with no recommendation"""
        response = client.post(
            '/api/autopilot/default/test-app/apply',
            json={},
            content_type='application/json'
        )
        assert response.status_code == 404
        
        data = response.get_json()
        assert 'error' in data
    
    def test_autopilot_rollback_no_action(self, client):
        """Test /api/autopilot/rollback with no action"""
        response = client.post(
            '/api/autopilot/default/test-app/rollback',
            json={'reason': 'Test rollback'}
        )
        assert response.status_code == 404


# ==================== Rollback & Health Monitoring Tests ====================

class TestResourceSnapshot:
    """Test ResourceSnapshot dataclass"""
    
    def test_create_snapshot(self):
        """Test creating a snapshot"""
        snapshot = ResourceSnapshot(
            namespace="default",
            deployment="test-app",
            container="main",
            cpu_request=500,
            memory_request=512,
            pod_restarts=2,
            oom_kills=0,
            ready_replicas=3,
            total_replicas=3
        )
        
        assert snapshot.namespace == "default"
        assert snapshot.deployment == "test-app"
        assert snapshot.cpu_request == 500
        assert snapshot.memory_request == 512
        assert snapshot.pod_restarts == 2
        assert snapshot.oom_kills == 0
        assert snapshot.ready_replicas == 3
        assert snapshot.expires_at is not None
        assert snapshot.expires_at > snapshot.created_at


class TestHealthCheckResult:
    """Test HealthCheckResult dataclass"""
    
    def test_create_healthy_result(self):
        """Test creating a healthy result"""
        result = HealthCheckResult(
            namespace="default",
            deployment="test-app",
            pod_restarts=2,
            oom_kills=0,
            ready_replicas=3,
            total_replicas=3,
            error_rate=0.0,
            restart_increase=0,
            oom_increase=0,
            readiness_drop=0,
            is_healthy=True,
            issues=[]
        )
        
        assert result.is_healthy == True
        assert len(result.issues) == 0
    
    def test_create_unhealthy_result(self):
        """Test creating an unhealthy result"""
        result = HealthCheckResult(
            namespace="default",
            deployment="test-app",
            pod_restarts=5,
            oom_kills=2,
            ready_replicas=1,
            total_replicas=3,
            error_rate=0.5,
            restart_increase=3,
            oom_increase=2,
            readiness_drop=66,
            is_healthy=False,
            issues=["Pod restarts increased by 3", "OOMKills increased by 2"]
        )
        
        assert result.is_healthy == False
        assert len(result.issues) == 2
        assert "restarts" in result.issues[0].lower()


class TestAutopilotRollback:
    """Test rollback functionality"""
    
    @pytest.fixture
    def manager_with_rollback(self):
        """Create manager with rollback enabled"""
        with patch('src.autopilot.client'):
            manager = AutopilotManager(
                enabled=True,
                level=AutopilotLevel.AUTOPILOT,
                enable_auto_rollback=True,
                rollback_monitor_minutes=10,
                max_restart_increase=2,
                max_oom_increase=1,
                max_readiness_drop_percent=20.0
            )
            return manager
    
    def test_rollback_config_in_status(self, manager_with_rollback):
        """Test rollback config appears in status"""
        status = manager_with_rollback.get_status()
        
        assert 'rollback_config' in status
        assert status['rollback_config']['enabled'] == True
        assert status['rollback_config']['monitor_minutes'] == 10
        assert status['rollback_config']['max_restart_increase'] == 2
        assert status['rollback_config']['max_oom_increase'] == 1
    
    def test_pending_monitors_in_status(self, manager_with_rollback):
        """Test pending monitors appear in status"""
        status = manager_with_rollback.get_status()
        
        assert 'pending_health_monitors' in status
        assert 'recent_auto_rollbacks' in status
    
    def test_get_rollback_history_empty(self, manager_with_rollback):
        """Test get_rollback_history when empty"""
        history = manager_with_rollback.get_rollback_history()
        assert history == []
    
    def test_get_pending_monitors_empty(self, manager_with_rollback):
        """Test get_pending_monitors when empty"""
        monitors = manager_with_rollback.get_pending_monitors()
        assert monitors == []
    
    def test_snapshot_stored(self, manager_with_rollback):
        """Test that snapshots are stored correctly"""
        # Manually add a snapshot
        snapshot = ResourceSnapshot(
            namespace="default",
            deployment="test-app",
            container="main",
            cpu_request=500,
            memory_request=512,
            pod_restarts=0,
            oom_kills=0,
            ready_replicas=3,
            total_replicas=3
        )
        manager_with_rollback.snapshots["default/test-app"] = snapshot
        
        assert "default/test-app" in manager_with_rollback.snapshots
        assert manager_with_rollback.snapshots["default/test-app"].cpu_request == 500
    
    def test_check_health_no_snapshot(self, manager_with_rollback):
        """Test check_health returns None when no snapshot"""
        result = manager_with_rollback.check_health("default", "nonexistent")
        assert result is None


class TestCreateAutopilotManagerWithRollback:
    """Test factory function with rollback config"""
    
    def test_create_with_rollback_defaults(self):
        """Test creating manager with rollback defaults"""
        with patch.dict('os.environ', {}, clear=True):
            with patch('src.autopilot.client'):
                manager = create_autopilot_manager()
                
                # Rollback should be enabled by default
                assert manager.enable_auto_rollback == True
                assert manager.rollback_monitor_minutes == 10
                assert manager.max_restart_increase == 2
                assert manager.max_oom_increase == 1
                assert manager.max_readiness_drop_percent == 20.0
    
    def test_create_with_rollback_disabled(self):
        """Test creating manager with rollback disabled"""
        env = {
            'AUTOPILOT_ENABLE_AUTO_ROLLBACK': 'false',
            'AUTOPILOT_ROLLBACK_MONITOR_MINUTES': '15',
            'AUTOPILOT_MAX_RESTART_INCREASE': '5'
        }
        with patch.dict('os.environ', env, clear=True):
            with patch('src.autopilot.client'):
                manager = create_autopilot_manager()
                
                assert manager.enable_auto_rollback == False
                assert manager.rollback_monitor_minutes == 15
                assert manager.max_restart_increase == 5
    
    def test_create_with_custom_rollback_config(self):
        """Test creating manager with custom rollback config"""
        env = {
            'ENABLE_AUTOPILOT': 'true',
            'AUTOPILOT_ENABLE_AUTO_ROLLBACK': 'true',
            'AUTOPILOT_ROLLBACK_MONITOR_MINUTES': '5',
            'AUTOPILOT_MAX_RESTART_INCREASE': '1',
            'AUTOPILOT_MAX_OOM_INCREASE': '0',
            'AUTOPILOT_MAX_READINESS_DROP_PERCENT': '10'
        }
        with patch.dict('os.environ', env, clear=True):
            with patch('src.autopilot.client'):
                manager = create_autopilot_manager()
                
                assert manager.enabled == True
                assert manager.enable_auto_rollback == True
                assert manager.rollback_monitor_minutes == 5
                assert manager.max_restart_increase == 1
                assert manager.max_oom_increase == 0
                assert manager.max_readiness_drop_percent == 10.0
