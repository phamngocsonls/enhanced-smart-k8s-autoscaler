"""
Tests for intelligence module - TimeSeriesDatabase, AutoTuner, CostOptimizer
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta


class TestTimeSeriesDatabase:
    """Test TimeSeriesDatabase functionality"""
    
    def test_database_import(self):
        """Test TimeSeriesDatabase can be imported"""
        from src.intelligence import TimeSeriesDatabase
        assert TimeSeriesDatabase is not None
    
    def test_database_initialization(self):
        """Test database initializes with temp file"""
        from src.intelligence import TimeSeriesDatabase
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = TimeSeriesDatabase(db_path=db_path)
            
            assert db is not None
            assert os.path.exists(db_path)
    
    def test_store_and_retrieve_metrics(self):
        """Test storing and retrieving metrics"""
        from src.intelligence import TimeSeriesDatabase, MetricsSnapshot
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = TimeSeriesDatabase(db_path=db_path)
            
            # Create a metrics snapshot
            snapshot = MetricsSnapshot(
                timestamp=datetime.now(),
                deployment="test-deployment",
                namespace="default",
                node_utilization=65.0,
                pod_count=3,
                pod_cpu_usage=0.5,
                hpa_target=70,
                confidence=0.85,
                scheduling_spike=False,
                action_taken="none",
                cpu_request=500,
                memory_request=512,
                memory_usage=256.0,
                node_selector=""
            )
            
            # Store the snapshot
            db.store_metrics(snapshot)
            
            # Retrieve metrics
            metrics = db.get_recent_metrics("test-deployment", hours=1)
            
            assert len(metrics) >= 1
            assert metrics[0].deployment == "test-deployment"
    
    def test_get_recent_metrics_empty(self):
        """Test getting metrics when none exist"""
        from src.intelligence import TimeSeriesDatabase
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = TimeSeriesDatabase(db_path=db_path)
            
            metrics = db.get_recent_metrics("nonexistent-deployment", hours=1)
            
            assert metrics == []


class TestMetricsSnapshot:
    """Test MetricsSnapshot dataclass"""
    
    def test_metrics_snapshot_creation(self):
        """Test creating a MetricsSnapshot"""
        from src.intelligence import MetricsSnapshot
        
        snapshot = MetricsSnapshot(
            timestamp=datetime.now(),
            deployment="test",
            namespace="default",
            node_utilization=70.0,
            pod_count=2,
            pod_cpu_usage=0.6,
            hpa_target=70,
            confidence=0.9,
            scheduling_spike=False,
            action_taken="scale_up",
            cpu_request=1000,
            memory_request=1024,
            memory_usage=512.0,
            node_selector=""
        )
        
        assert snapshot.deployment == "test"
        assert snapshot.node_utilization == 70.0
        assert snapshot.pod_count == 2


class TestCostMetrics:
    """Test CostMetrics dataclass"""
    
    def test_cost_metrics_creation(self):
        """Test creating CostMetrics"""
        from src.intelligence import CostMetrics
        
        cost = CostMetrics(
            deployment="test",
            avg_pod_count=3.5,
            avg_utilization=65.0,
            wasted_capacity_percent=35.0,
            estimated_monthly_cost=150.0,
            optimization_potential=50.0,
            recommendation="Reduce CPU request by 20%"
        )
        
        assert cost.deployment == "test"
        assert cost.avg_pod_count == 3.5
        assert cost.wasted_capacity_percent == 35.0


class TestAutoTuner:
    """Test AutoTuner functionality"""
    
    def test_autotuner_import(self):
        """Test AutoTuner can be imported"""
        from src.intelligence import AutoTuner
        assert AutoTuner is not None
    
    def test_autotuner_initialization(self):
        """Test AutoTuner initializes correctly"""
        from src.intelligence import AutoTuner, AlertManager
        
        mock_db = Mock()
        mock_alert_manager = Mock()
        tuner = AutoTuner(db=mock_db, alert_manager=mock_alert_manager)
        
        assert tuner is not None
        assert tuner.db == mock_db
    
    def test_learning_rate_bounds(self):
        """Test learning rate stays within bounds"""
        from src.intelligence import AutoTuner
        
        mock_db = Mock()
        mock_alert_manager = Mock()
        tuner = AutoTuner(db=mock_db, alert_manager=mock_alert_manager)
        
        # Learning rate should be between 0.05 and 0.3
        assert 0.05 <= tuner.learning_rate <= 0.3


class TestCostOptimizer:
    """Test CostOptimizer functionality"""
    
    def test_cost_optimizer_import(self):
        """Test CostOptimizer can be imported"""
        from src.intelligence import CostOptimizer
        assert CostOptimizer is not None
    
    def test_cost_optimizer_initialization(self):
        """Test CostOptimizer initializes with correct defaults"""
        from src.intelligence import CostOptimizer
        
        mock_db = Mock()
        mock_alert_manager = Mock()
        
        optimizer = CostOptimizer(db=mock_db, alert_manager=mock_alert_manager)
        
        assert optimizer.cost_per_vcpu_hour > 0
        assert optimizer.cost_per_gb_memory_hour > 0
    
    @patch.dict(os.environ, {'COST_PER_VCPU_HOUR': '0.05'})
    def test_cost_optimizer_custom_cost(self):
        """Test CostOptimizer with custom cost settings"""
        from src.intelligence import CostOptimizer
        
        mock_db = Mock()
        mock_alert_manager = Mock()
        
        optimizer = CostOptimizer(db=mock_db, alert_manager=mock_alert_manager)
        
        assert optimizer.cost_per_vcpu_hour == 0.05


class TestAnomalyAlert:
    """Test AnomalyAlert dataclass"""
    
    def test_anomaly_alert_creation(self):
        """Test creating an AnomalyAlert"""
        from src.intelligence import AnomalyAlert
        
        alert = AnomalyAlert(
            timestamp=datetime.now(),
            deployment="test",
            anomaly_type="cpu_spike",
            severity="warning",
            description="CPU usage spike detected",
            current_value=95.0,
            expected_value=70.0,
            deviation_percent=35.7
        )
        
        assert alert.anomaly_type == "cpu_spike"
        assert alert.severity == "warning"
        assert alert.deviation_percent == 35.7


class TestPrediction:
    """Test Prediction dataclass"""
    
    def test_prediction_creation(self):
        """Test creating a Prediction"""
        from src.intelligence import Prediction
        
        pred = Prediction(
            timestamp=datetime.now(),
            deployment="test",
            predicted_cpu=85.0,
            confidence=0.8,
            recommended_action="scale_up",
            reasoning="Historical pattern suggests increased load"
        )
        
        assert pred.predicted_cpu == 85.0
        assert pred.confidence == 0.8
        assert pred.recommended_action == "scale_up"


class TestAlertManager:
    """Test AlertManager functionality"""
    
    def test_alert_manager_import(self):
        """Test AlertManager can be imported"""
        from src.intelligence import AlertManager
        assert AlertManager is not None
    
    def test_alert_manager_initialization(self):
        """Test AlertManager initializes correctly"""
        from src.intelligence import AlertManager
        
        # AlertManager takes webhooks dict, not db
        manager = AlertManager(webhooks={})
        
        assert manager is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
