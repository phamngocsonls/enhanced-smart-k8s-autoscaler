"""
Tests for Pre-Scale Manager
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

from src.prescale_manager import (
    PreScaleManager,
    PreScaleProfile,
    PreScaleState
)


class MockHPA:
    """Mock HPA object"""
    def __init__(self, min_replicas=2, max_replicas=10):
        self.spec = Mock()
        self.spec.min_replicas = min_replicas
        self.spec.max_replicas = max_replicas


class MockPredictionResult:
    """Mock prediction result"""
    def __init__(self, predicted_value, confidence):
        self.predicted_value = predicted_value
        self.confidence = confidence


class MockAutoscalingAPI:
    """Mock Kubernetes autoscaling API"""
    def __init__(self):
        self.hpas = {}
        self.patches = []
    
    def read_namespaced_horizontal_pod_autoscaler(self, name, namespace):
        key = f"{namespace}/{name}"
        if key in self.hpas:
            return self.hpas[key]
        return MockHPA()
    
    def patch_namespaced_horizontal_pod_autoscaler(self, name, namespace, patch):
        self.patches.append({
            'name': name,
            'namespace': namespace,
            'patch': patch
        })
    
    def add_hpa(self, namespace, name, min_replicas=2, max_replicas=10):
        key = f"{namespace}/{name}"
        self.hpas[key] = MockHPA(min_replicas, max_replicas)


class MockPredictor:
    """Mock predictor"""
    def __init__(self, predictions=None):
        self._predictions = predictions or {}
    
    def predict_all_windows(self, deployment):
        return self._predictions
    
    def set_predictions(self, predictions):
        self._predictions = predictions


class TestPreScaleProfile:
    """Tests for PreScaleProfile"""
    
    def test_profile_creation(self):
        """Test profile creation"""
        profile = PreScaleProfile(
            namespace="default",
            deployment="my-app",
            hpa_name="my-app-hpa",
            original_min_replicas=2,
            original_max_replicas=10
        )
        
        assert profile.namespace == "default"
        assert profile.deployment == "my-app"
        assert profile.original_min_replicas == 2
        assert profile.current_min_replicas == 2  # Should default to original
        assert profile.state == PreScaleState.NORMAL
    
    def test_profile_to_dict(self):
        """Test profile serialization"""
        profile = PreScaleProfile(
            namespace="default",
            deployment="my-app",
            hpa_name="my-app-hpa",
            original_min_replicas=2,
            original_max_replicas=10
        )
        
        data = profile.to_dict()
        
        assert data['namespace'] == "default"
        assert data['deployment'] == "my-app"
        assert data['state'] == "normal"
        assert data['original_min_replicas'] == 2


class TestPreScaleManager:
    """Tests for PreScaleManager"""
    
    def test_init(self):
        """Test manager initialization"""
        api = MockAutoscalingAPI()
        predictor = MockPredictor()
        
        manager = PreScaleManager(
            k8s_client=Mock(),
            autoscaling_api=api,
            predictor=predictor,
            db=Mock(),
            enable_prescale=True
        )
        
        assert manager.enable_prescale == True
        assert manager.min_confidence == 0.7
        assert manager.scale_up_threshold == 75.0
    
    def test_register_deployment(self):
        """Test deployment registration"""
        api = MockAutoscalingAPI()
        api.add_hpa("default", "my-app-hpa", min_replicas=2, max_replicas=10)
        predictor = MockPredictor()
        
        manager = PreScaleManager(
            k8s_client=Mock(),
            autoscaling_api=api,
            predictor=predictor,
            db=Mock()
        )
        
        profile = manager.register_deployment("default", "my-app", "my-app-hpa")
        
        assert profile is not None
        assert profile.original_min_replicas == 2
        assert profile.original_max_replicas == 10
        assert profile.state == PreScaleState.NORMAL
    
    def test_register_deployment_already_registered(self):
        """Test registering same deployment twice returns existing profile"""
        api = MockAutoscalingAPI()
        api.add_hpa("default", "my-app-hpa", min_replicas=2, max_replicas=10)
        predictor = MockPredictor()
        
        manager = PreScaleManager(
            k8s_client=Mock(),
            autoscaling_api=api,
            predictor=predictor,
            db=Mock()
        )
        
        profile1 = manager.register_deployment("default", "my-app", "my-app-hpa")
        profile2 = manager.register_deployment("default", "my-app", "my-app-hpa")
        
        assert profile1 is profile2
    
    def test_calculate_required_replicas(self):
        """Test replica calculation"""
        api = MockAutoscalingAPI()
        predictor = MockPredictor()
        
        manager = PreScaleManager(
            k8s_client=Mock(),
            autoscaling_api=api,
            predictor=predictor,
            db=Mock()
        )
        
        # Current: 3 pods, predicted 90% CPU, target 70%
        # Required = 3 * (90/70) = 3.86 → 4
        required = manager.calculate_required_replicas(
            current_replicas=3,
            current_cpu=50,
            predicted_cpu=90,
            target_cpu=70,
            min_replicas=2,
            max_replicas=10
        )
        assert required == 4
        
        # Respect max_replicas
        required = manager.calculate_required_replicas(
            current_replicas=5,
            current_cpu=50,
            predicted_cpu=150,
            target_cpu=70,
            min_replicas=2,
            max_replicas=8
        )
        assert required == 8  # Capped at max
    
    def test_check_and_prescale_disabled(self):
        """Test pre-scale when disabled"""
        api = MockAutoscalingAPI()
        predictor = MockPredictor()
        
        manager = PreScaleManager(
            k8s_client=Mock(),
            autoscaling_api=api,
            predictor=predictor,
            db=Mock(),
            enable_prescale=False
        )
        
        result = manager.check_and_prescale("default", "my-app", 3, 50)
        
        assert result['action'] == 'disabled'
    
    def test_check_and_prescale_not_registered(self):
        """Test pre-scale for unregistered deployment"""
        api = MockAutoscalingAPI()
        predictor = MockPredictor()
        
        manager = PreScaleManager(
            k8s_client=Mock(),
            autoscaling_api=api,
            predictor=predictor,
            db=Mock()
        )
        
        result = manager.check_and_prescale("default", "my-app", 3, 50)
        
        assert result['action'] == 'not_registered'
    
    def test_check_and_prescale_no_spike(self):
        """Test pre-scale when no spike predicted"""
        api = MockAutoscalingAPI()
        api.add_hpa("default", "my-app-hpa", min_replicas=2, max_replicas=10)
        
        # Low predictions
        predictor = MockPredictor({
            '15min': MockPredictionResult(50, 0.8),
            '30min': MockPredictionResult(55, 0.8),
            '1hr': MockPredictionResult(60, 0.8)
        })
        
        manager = PreScaleManager(
            k8s_client=Mock(),
            autoscaling_api=api,
            predictor=predictor,
            db=Mock()
        )
        
        manager.register_deployment("default", "my-app", "my-app-hpa")
        result = manager.check_and_prescale("default", "my-app", 3, 50)
        
        assert result['action'] == 'maintain'
    
    def test_check_and_prescale_spike_predicted(self):
        """Test pre-scale when spike is predicted"""
        api = MockAutoscalingAPI()
        api.add_hpa("default", "my-app-hpa", min_replicas=2, max_replicas=10)
        
        # High prediction
        predictor = MockPredictor({
            '15min': MockPredictionResult(85, 0.8),
            '30min': MockPredictionResult(90, 0.85),
            '1hr': MockPredictionResult(80, 0.75)
        })
        
        manager = PreScaleManager(
            k8s_client=Mock(),
            autoscaling_api=api,
            predictor=predictor,
            db=Mock()
        )
        
        manager.register_deployment("default", "my-app", "my-app-hpa")
        result = manager.check_and_prescale("default", "my-app", 3, 50)
        
        assert result['action'] == 'pre_scaled'
        assert result['new_min_replicas'] > 2
        assert 'rollback_at' in result
        
        # Check HPA was patched
        assert len(api.patches) == 1
        assert api.patches[0]['patch']['spec']['minReplicas'] > 2
    
    def test_check_and_prescale_low_confidence(self):
        """Test pre-scale skipped when confidence is low"""
        api = MockAutoscalingAPI()
        api.add_hpa("default", "my-app-hpa", min_replicas=2, max_replicas=10)
        
        # High prediction but low confidence
        predictor = MockPredictor({
            '15min': MockPredictionResult(90, 0.5),  # Below min_confidence
            '30min': MockPredictionResult(85, 0.4),
            '1hr': MockPredictionResult(80, 0.3)
        })
        
        manager = PreScaleManager(
            k8s_client=Mock(),
            autoscaling_api=api,
            predictor=predictor,
            db=Mock(),
            min_confidence=0.7
        )
        
        manager.register_deployment("default", "my-app", "my-app-hpa")
        result = manager.check_and_prescale("default", "my-app", 3, 50)
        
        assert result['action'] == 'maintain'
    
    def test_force_rollback(self):
        """Test force rollback"""
        api = MockAutoscalingAPI()
        api.add_hpa("default", "my-app-hpa", min_replicas=2, max_replicas=10)
        
        predictor = MockPredictor({
            '15min': MockPredictionResult(90, 0.9),
        })
        
        manager = PreScaleManager(
            k8s_client=Mock(),
            autoscaling_api=api,
            predictor=predictor,
            db=Mock()
        )
        
        manager.register_deployment("default", "my-app", "my-app-hpa")
        
        # Pre-scale first
        manager.check_and_prescale("default", "my-app", 3, 50)
        
        # Force rollback
        result = manager.force_rollback("default", "my-app")
        
        assert result['action'] == 'rolled_back'
        
        # Check profile state
        profile = manager.get_profile("default", "my-app")
        assert profile.state == PreScaleState.NORMAL
        assert profile.current_min_replicas == 2
    
    def test_force_prescale(self):
        """Test force pre-scale"""
        api = MockAutoscalingAPI()
        api.add_hpa("default", "my-app-hpa", min_replicas=2, max_replicas=10)
        
        predictor = MockPredictor()
        
        manager = PreScaleManager(
            k8s_client=Mock(),
            autoscaling_api=api,
            predictor=predictor,
            db=Mock()
        )
        
        manager.register_deployment("default", "my-app", "my-app-hpa")
        
        result = manager.force_prescale("default", "my-app", 5, "Manual test")
        
        assert result['action'] == 'pre_scaled'
        assert result['new_min_replicas'] == 5
        
        profile = manager.get_profile("default", "my-app")
        assert profile.state == PreScaleState.PRE_SCALING
        assert profile.current_min_replicas == 5
    
    def test_cooldown(self):
        """Test cooldown between pre-scale actions"""
        api = MockAutoscalingAPI()
        api.add_hpa("default", "my-app-hpa", min_replicas=2, max_replicas=10)
        
        predictor = MockPredictor({
            '15min': MockPredictionResult(90, 0.9),
        })
        
        manager = PreScaleManager(
            k8s_client=Mock(),
            autoscaling_api=api,
            predictor=predictor,
            db=Mock(),
            cooldown_minutes=15
        )
        
        manager.register_deployment("default", "my-app", "my-app-hpa")
        
        # First pre-scale
        result1 = manager.check_and_prescale("default", "my-app", 3, 50)
        assert result1['action'] == 'pre_scaled'
        
        # Rollback
        manager.force_rollback("default", "my-app")
        
        # Try to pre-scale again immediately - should be in cooldown
        result2 = manager.check_and_prescale("default", "my-app", 3, 50)
        assert result2['action'] == 'cooldown'
    
    def test_get_summary(self):
        """Test getting summary"""
        api = MockAutoscalingAPI()
        api.add_hpa("default", "app1-hpa", min_replicas=2, max_replicas=10)
        api.add_hpa("default", "app2-hpa", min_replicas=3, max_replicas=15)
        
        predictor = MockPredictor()
        
        manager = PreScaleManager(
            k8s_client=Mock(),
            autoscaling_api=api,
            predictor=predictor,
            db=Mock()
        )
        
        manager.register_deployment("default", "app1", "app1-hpa")
        manager.register_deployment("default", "app2", "app2-hpa")
        
        summary = manager.get_summary()
        
        assert summary['total_deployments'] == 2
        assert summary['normal'] == 2
        assert summary['pre_scaling'] == 0
        assert summary['enabled'] == True


class TestPreScaleRollback:
    """Tests for rollback scenarios"""
    
    def test_auto_rollback_timeout(self):
        """Test auto-rollback after timeout"""
        api = MockAutoscalingAPI()
        api.add_hpa("default", "my-app-hpa", min_replicas=2, max_replicas=10)
        
        predictor = MockPredictor({
            '15min': MockPredictionResult(90, 0.9),
        })
        
        manager = PreScaleManager(
            k8s_client=Mock(),
            autoscaling_api=api,
            predictor=predictor,
            db=Mock(),
            auto_rollback_minutes=60
        )
        
        manager.register_deployment("default", "my-app", "my-app-hpa")
        manager.check_and_prescale("default", "my-app", 3, 50)
        
        # Simulate time passing
        profile = manager.get_profile("default", "my-app")
        profile.rollback_at = datetime.now() - timedelta(minutes=1)  # Already past
        
        # Check rollbacks
        manager.check_all_rollbacks()
        
        # Should be rolled back
        assert profile.state == PreScaleState.NORMAL
        assert profile.current_min_replicas == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
