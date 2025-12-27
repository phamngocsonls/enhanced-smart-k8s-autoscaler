"""
Intelligence Layer for Smart Autoscaler
Historical learning, predictions, anomaly detection, cost optimization
"""

import sqlite3
import logging
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import statistics
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MetricsSnapshot:
    """Single point-in-time metrics snapshot"""
    timestamp: datetime
    deployment: str
    namespace: str
    node_utilization: float
    pod_count: int
    pod_cpu_usage: float
    hpa_target: int
    confidence: float
    scheduling_spike: bool
    action_taken: str
    cpu_request: int
    memory_request: int  # in MB
    memory_usage: float  # in MB
    node_selector: str


@dataclass
class CostMetrics:
    """Cost-related metrics"""
    deployment: str
    avg_pod_count: float
    avg_utilization: float
    wasted_capacity_percent: float
    estimated_monthly_cost: float
    optimization_potential: float
    recommendation: str
    # Detailed cost breakdown
    cpu_cost: float = 0.0
    memory_cost: float = 0.0
    total_cost: float = 0.0
    wasted_cpu_cost: float = 0.0
    wasted_memory_cost: float = 0.0
    total_wasted_cost: float = 0.0
    cpu_utilization_percent: float = 0.0
    memory_utilization_percent: float = 0.0
    runtime_hours: float = 0.0


@dataclass
class AnomalyAlert:
    """Anomaly detection alert"""
    timestamp: datetime
    deployment: str
    anomaly_type: str
    severity: str
    description: str
    current_value: float
    expected_value: float
    deviation_percent: float


@dataclass
class Prediction:
    """Scaling prediction"""
    timestamp: datetime
    deployment: str
    predicted_cpu: float
    confidence: float
    recommended_action: str
    reasoning: str


class TimeSeriesDatabase:
    """SQLite-based time-series database"""
    
    def __init__(self, db_path: str = "/data/autoscaler.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Enable WAL mode for better concurrency and performance
        self.conn = sqlite3.connect(
            db_path, 
            check_same_thread=False,
            timeout=30.0  # Connection timeout
        )
        # Optimize SQLite settings
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")  # Balance safety/speed
        self.conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=30000")  # 30s busy timeout
        
        self._init_schema()
        self._migrate_schema()  # Migrate existing databases
        self._cleanup_old_data()
    
    def _init_schema(self):
        """Initialize database schema"""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS metrics_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                deployment TEXT,
                namespace TEXT,
                node_utilization REAL,
                pod_count INTEGER,
                pod_cpu_usage REAL,
                hpa_target INTEGER,
                confidence REAL,
                scheduling_spike BOOLEAN,
                action_taken TEXT,
                cpu_request INTEGER,
                memory_request INTEGER,
                memory_usage REAL,
                node_selector TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_metrics_deployment_time 
            ON metrics_history(deployment, timestamp);
            
            CREATE TABLE IF NOT EXISTS cost_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                deployment TEXT,
                avg_pod_count REAL,
                avg_utilization REAL,
                wasted_capacity_percent REAL,
                estimated_monthly_cost REAL,
                optimization_potential REAL,
                recommendation TEXT
            );
            
            CREATE TABLE IF NOT EXISTS anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                deployment TEXT,
                anomaly_type TEXT,
                severity TEXT,
                description TEXT,
                current_value REAL,
                expected_value REAL,
                deviation_percent REAL
            );
            
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                deployment TEXT,
                predicted_cpu REAL,
                confidence REAL,
                recommended_action TEXT,
                reasoning TEXT,
                actual_cpu REAL,
                validated BOOLEAN DEFAULT 0,
                accuracy REAL
            );
            
            CREATE TABLE IF NOT EXISTS prediction_accuracy (
                deployment TEXT PRIMARY KEY,
                total_predictions INTEGER DEFAULT 0,
                accurate_predictions INTEGER DEFAULT 0,
                false_positives INTEGER DEFAULT 0,
                false_negatives INTEGER DEFAULT 0,
                avg_accuracy REAL DEFAULT 0.0,
                last_updated DATETIME
            );
            
            CREATE TABLE IF NOT EXISTS optimal_targets (
                deployment TEXT PRIMARY KEY,
                optimal_target INTEGER,
                confidence REAL,
                samples_count INTEGER,
                last_updated DATETIME
            );
        """)
        self.conn.commit()
    
    def _cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old data to prevent database growth"""
        try:
            # Delete metrics older than retention period
            cursor = self.conn.execute("""
                DELETE FROM metrics_history 
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """, (days_to_keep,))
            deleted_count = cursor.rowcount
            
            # Delete old anomalies (keep 90 days)
            cursor = self.conn.execute("""
                DELETE FROM anomalies 
                WHERE timestamp < datetime('now', '-90 days')
            """)
            deleted_anomalies = cursor.rowcount
            
            # Delete old predictions (keep 30 days)
            cursor = self.conn.execute("""
                DELETE FROM predictions 
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """, (days_to_keep,))
            deleted_predictions = cursor.rowcount
            
            self.conn.commit()
            
            if deleted_count > 0 or deleted_anomalies > 0 or deleted_predictions > 0:
                logger.info(
                    f"Cleaned up old data: {deleted_count} metrics, "
                    f"{deleted_anomalies} anomalies, {deleted_predictions} predictions"
                )
            
            # Vacuum database periodically to reclaim space
            # Only do this if significant data was deleted
            if deleted_count > 1000:
                logger.info("Running VACUUM to reclaim database space...")
                self.conn.execute("VACUUM")
                self.conn.commit()
        except Exception as e:
            logger.warning(f"Error during database cleanup: {e}")
    
    def close(self):
        """Close database connection properly"""
        if hasattr(self, 'conn') and self.conn:
            try:
                # Final cleanup before closing
                self._cleanup_old_data()
                self.conn.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    def store_metrics(self, snapshot: MetricsSnapshot):
        """Store metrics snapshot"""
        self.conn.execute("""
            INSERT INTO metrics_history 
            (timestamp, deployment, namespace, node_utilization, pod_count, 
             pod_cpu_usage, hpa_target, confidence, scheduling_spike, action_taken, 
             cpu_request, memory_request, memory_usage, node_selector)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot.timestamp, snapshot.deployment, snapshot.namespace,
            snapshot.node_utilization, snapshot.pod_count, snapshot.pod_cpu_usage,
            snapshot.hpa_target, snapshot.confidence, snapshot.scheduling_spike,
            snapshot.action_taken, snapshot.cpu_request, 
            snapshot.memory_request, snapshot.memory_usage, snapshot.node_selector
        ))
        self.conn.commit()
    
    def get_historical_pattern(self, deployment: str, hour: int, day_of_week: int, days_back: int = 30) -> List[float]:
        """Get historical CPU patterns for specific time"""
        cursor = self.conn.execute("""
            SELECT node_utilization 
            FROM metrics_history
            WHERE deployment = ?
            AND strftime('%H', timestamp) = ?
            AND strftime('%w', timestamp) = ?
            AND timestamp >= datetime('now', ? || ' days')
            ORDER BY timestamp DESC
        """, (deployment, f"{hour:02d}", str(day_of_week), f"-{days_back}"))
        
        return [row[0] for row in cursor.fetchall()]
    
    def get_recent_metrics(self, deployment: str, hours: int = 24) -> List[MetricsSnapshot]:
        """Get recent metrics for deployment"""
        cursor = self.conn.execute("""
            SELECT * FROM metrics_history
            WHERE deployment = ?
            AND timestamp >= datetime('now', ? || ' hours')
            ORDER BY timestamp DESC
        """, (deployment, f"-{hours}"))
        
        snapshots = []
        for row in cursor.fetchall():
            try:
                # Handle both string and datetime timestamp formats
                if isinstance(row[1], str):
                    timestamp = datetime.fromisoformat(row[1])
                else:
                    timestamp = row[1]
                
                # Handle old records without memory fields (default to 0)
                memory_request = row[12] if len(row) > 12 else 0
                memory_usage = row[13] if len(row) > 13 else 0.0
                node_selector = row[14] if len(row) > 14 else (row[12] if len(row) > 12 else "")
                
                snapshots.append(MetricsSnapshot(
                    timestamp=timestamp,
                    deployment=row[2],
                    namespace=row[3],
                    node_utilization=row[4],
                    pod_count=row[5],
                    pod_cpu_usage=row[6],
                    hpa_target=row[7],
                    confidence=row[8],
                    scheduling_spike=bool(row[9]),
                    action_taken=row[10],
                    cpu_request=row[11],
                    memory_request=memory_request,
                    memory_usage=memory_usage,
                    node_selector=node_selector
                ))
            except (ValueError, IndexError, TypeError) as e:
                logger.warning(f"Error parsing metrics row: {e}, skipping")
                continue
        
        return snapshots
    
    def store_anomaly(self, anomaly: AnomalyAlert):
        """Store anomaly"""
        self.conn.execute("""
            INSERT INTO anomalies 
            (timestamp, deployment, anomaly_type, severity, description, 
             current_value, expected_value, deviation_percent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            anomaly.timestamp, anomaly.deployment, anomaly.anomaly_type,
            anomaly.severity, anomaly.description, anomaly.current_value,
            anomaly.expected_value, anomaly.deviation_percent
        ))
        self.conn.commit()
    
    def store_prediction(self, prediction: Prediction):
        """Store prediction"""
        self.conn.execute("""
            INSERT INTO predictions 
            (timestamp, deployment, predicted_cpu, confidence, recommended_action, reasoning, validated)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (
            prediction.timestamp, prediction.deployment, prediction.predicted_cpu,
            prediction.confidence, prediction.recommended_action, prediction.reasoning
        ))
        self.conn.commit()
    
    def validate_predictions(self, deployment: str, hours_back: int = 2):
        """Validate predictions by comparing with actual CPU usage"""
        # Get predictions from last N hours that haven't been validated
        cursor = self.conn.execute("""
            SELECT id, timestamp, predicted_cpu, recommended_action
            FROM predictions
            WHERE deployment = ?
            AND validated = 0
            AND timestamp >= datetime('now', '-' || ? || ' hours')
            ORDER BY timestamp DESC
        """, (deployment, hours_back))
        
        predictions_to_validate = cursor.fetchall()
        
        for pred_id, pred_timestamp, predicted_cpu, action in predictions_to_validate:
            # Get actual CPU usage at the time prediction was for (1 hour after prediction)
            if isinstance(pred_timestamp, str):
                validation_time = datetime.fromisoformat(pred_timestamp)
            else:
                validation_time = pred_timestamp
            validation_time = validation_time + timedelta(hours=1)  # Check 1 hour after prediction
            
            # Get actual CPU usage around validation time (±15 minutes)
            cursor = self.conn.execute("""
                SELECT AVG(pod_cpu_usage), AVG(pod_count)
                FROM metrics_history
                WHERE deployment = ?
                AND timestamp >= datetime(?, '-15 minutes')
                AND timestamp <= datetime(?, '+15 minutes')
            """, (deployment, validation_time.isoformat(), validation_time.isoformat()))
            
            result = cursor.fetchone()
            if result and result[0] is not None:
                actual_avg_cpu = result[0]
                actual_pod_count = result[1] or 1
                
                # Calculate actual CPU utilization percentage
                # Need CPU request to calculate percentage
                cursor = self.conn.execute("""
                    SELECT AVG(cpu_request)
                    FROM metrics_history
                    WHERE deployment = ?
                    AND timestamp >= datetime(?, '-15 minutes')
                    AND timestamp <= datetime(?, '+15 minutes')
                """, (deployment, validation_time.isoformat(), validation_time.isoformat()))
                
                cpu_request_result = cursor.fetchone()
                if cpu_request_result and cpu_request_result[0]:
                    cpu_request_cores = (cpu_request_result[0] / 1000.0) * actual_pod_count
                    actual_cpu_percent = (actual_avg_cpu / cpu_request_cores * 100) if cpu_request_cores > 0 else 0
                    
                    # Calculate accuracy (how close was prediction)
                    error = abs(predicted_cpu - actual_cpu_percent)
                    accuracy = max(0.0, 1.0 - (error / 100.0))  # 100% if exact, 0% if 100% off
                    
                    # Mark as validated
                    self.conn.execute("""
                        UPDATE predictions
                        SET actual_cpu = ?, validated = 1, accuracy = ?
                        WHERE id = ?
                    """, (actual_cpu_percent, accuracy, pred_id))
                    
                    # Update accuracy tracking
                    self._update_prediction_accuracy(deployment, predicted_cpu, actual_cpu_percent, action)
        
        self.conn.commit()
    
    def _update_prediction_accuracy(self, deployment: str, predicted: float, actual: float, action: str):
        """Update prediction accuracy statistics"""
        # Get current stats
        cursor = self.conn.execute("""
            SELECT total_predictions, accurate_predictions, false_positives, false_negatives, avg_accuracy
            FROM prediction_accuracy
            WHERE deployment = ?
        """, (deployment,))
        
        result = cursor.fetchone()
        if result:
            total, accurate, fp, fn, avg_acc = result
        else:
            total, accurate, fp, fn, avg_acc = 0, 0, 0, 0, 0.0
        
        total += 1
        
        # Determine if prediction was accurate
        error = abs(predicted - actual)
        is_accurate = error < 15.0  # Within 15% is considered accurate
        
        if is_accurate:
            accurate += 1
        else:
            # Check for false positive/negative
            if action == "pre_scale_up" and actual < predicted - 20:
                # Predicted high but actual was low - false positive
                fp += 1
            elif action == "scale_down" and actual > predicted + 20:
                # Predicted low but actual was high - false negative
                fn += 1
        
        # Update average accuracy
        accuracy_value = max(0.0, 1.0 - (error / 100.0))
        if avg_acc == 0:
            new_avg = accuracy_value
        else:
            new_avg = (avg_acc * (total - 1) + accuracy_value) / total
        
        # Store updated stats
        self.conn.execute("""
            INSERT OR REPLACE INTO prediction_accuracy
            (deployment, total_predictions, accurate_predictions, false_positives, 
             false_negatives, avg_accuracy, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (deployment, total, accurate, fp, fn, new_avg, datetime.now()))
    
    def get_prediction_accuracy(self, deployment: str) -> Optional[Dict]:
        """Get prediction accuracy statistics"""
        cursor = self.conn.execute("""
            SELECT total_predictions, accurate_predictions, false_positives, 
                   false_negatives, avg_accuracy
            FROM prediction_accuracy
            WHERE deployment = ?
        """, (deployment,))
        
        result = cursor.fetchone()
        if result and result[0] and result[0] > 0:
            total, accurate, fp, fn, avg_acc = result
            accuracy_rate = (accurate / total * 100) if total > 0 else 0
            false_positive_rate = (fp / total * 100) if total > 0 else 0
            
            return {
                'total_predictions': total,
                'accurate_predictions': accurate,
                'accuracy_rate': accuracy_rate,
                'false_positives': fp,
                'false_positive_rate': false_positive_rate,
                'false_negatives': fn,
                'avg_accuracy': avg_acc
            }
        return None
    
    def get_optimal_target(self, deployment: str) -> Optional[int]:
        """Get learned optimal target"""
        cursor = self.conn.execute("""
            SELECT optimal_target, confidence 
            FROM optimal_targets
            WHERE deployment = ?
        """, (deployment,))
        
        row = cursor.fetchone()
        return row[0] if row and row[1] > 0.7 else None
    
    def update_optimal_target(self, deployment: str, target: int, confidence: float):
        """Update optimal target"""
        self.conn.execute("""
            INSERT OR REPLACE INTO optimal_targets
            (deployment, optimal_target, confidence, samples_count, last_updated)
            VALUES (?, ?, ?, 
                    COALESCE((SELECT samples_count FROM optimal_targets WHERE deployment = ?), 0) + 1,
                    ?)
        """, (deployment, target, confidence, deployment, datetime.now()))
        self.conn.commit()


class AlertManager:
    """Manage alerts to various channels"""
    
    def __init__(self, webhooks: Dict[str, str]):
        self.webhooks = webhooks
    
    def send_alert(self, title: str, message: str, severity: str = "info", fields: Dict = None):
        """Send alert to all channels"""
        for channel, webhook_url in self.webhooks.items():
            try:
                if channel == "slack":
                    self._send_slack(webhook_url, title, message, severity, fields)
                elif channel == "teams":
                    self._send_teams(webhook_url, title, message, severity, fields)
                elif channel == "discord":
                    self._send_discord(webhook_url, title, message, severity, fields)
                elif channel == "generic":
                    self._send_generic(webhook_url, title, message, severity, fields)
            except Exception as e:
                logger.error(f"Failed to send alert to {channel}: {e}")
    
    def _send_slack(self, webhook_url: str, title: str, message: str, severity: str, fields: Dict):
        """Send to Slack"""
        color = {"info": "#36a64f", "warning": "#ff9900", "critical": "#ff0000"}.get(severity, "#36a64f")
        
        payload = {
            "attachments": [{
                "color": color,
                "title": f"{self._get_emoji(severity)} {title}",
                "text": message,
                "fields": [{"title": k, "value": str(v), "short": True} for k, v in (fields or {}).items()],
                "footer": "Smart Autoscaler",
                "ts": int(datetime.now().timestamp())
            }]
        }
        
        requests.post(webhook_url, json=payload, timeout=5)
    
    def _send_teams(self, webhook_url: str, title: str, message: str, severity: str, fields: Dict):
        """Send to Teams"""
        color = {"info": "00FF00", "warning": "FFA500", "critical": "FF0000"}.get(severity, "00FF00")
        
        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "themeColor": color,
            "title": f"{self._get_emoji(severity)} {title}",
            "text": message,
            "sections": [{
                "facts": [{"name": k, "value": str(v)} for k, v in (fields or {}).items()]
            }]
        }
        
        requests.post(webhook_url, json=payload, timeout=5)
    
    def _send_discord(self, webhook_url: str, title: str, message: str, severity: str, fields: Dict):
        """Send to Discord"""
        color = {"info": 3066993, "warning": 16763904, "critical": 16711680}.get(severity, 3066993)
        
        payload = {
            "embeds": [{
                "title": f"{self._get_emoji(severity)} {title}",
                "description": message,
                "color": color,
                "fields": [{"name": k, "value": str(v), "inline": True} for k, v in (fields or {}).items()],
                "footer": {"text": "Smart Autoscaler"},
                "timestamp": datetime.utcnow().isoformat()
            }]
        }
        
        requests.post(webhook_url, json=payload, timeout=5)
    
    def _send_generic(self, webhook_url: str, title: str, message: str, severity: str, fields: Dict):
        """Send to generic webhook"""
        payload = {
            "title": title,
            "message": message,
            "severity": severity,
            "fields": fields or {},
            "timestamp": datetime.now().isoformat()
        }
        
        requests.post(webhook_url, json=payload, timeout=5)
    
    def _get_emoji(self, severity: str) -> str:
        return {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(severity, "ℹ️")


class PatternRecognizer:
    """Learn patterns from historical data"""
    
    def __init__(self, db: TimeSeriesDatabase):
        self.db = db
    
    def learn_daily_pattern(self, deployment: str) -> Dict[int, float]:
        """Learn average CPU by hour"""
        pattern = {}
        for hour in range(24):
            values = []
            for day in range(7):
                historical = self.db.get_historical_pattern(deployment, hour, day, days_back=30)
                values.extend(historical)
            
            if values:
                pattern[hour] = statistics.mean(values)
        
        return pattern
    
    def predict_next_hour(self, deployment: str) -> Tuple[float, float]:
        """Predict CPU for next hour"""
        now = datetime.now()
        next_hour = (now.hour + 1) % 24
        day_of_week = now.weekday()
        
        historical = self.db.get_historical_pattern(deployment, next_hour, day_of_week, days_back=30)
        
        if len(historical) < 3:
            return 0.0, 0.0
        
        predicted = statistics.mean(historical)
        stddev = statistics.stdev(historical) if len(historical) > 1 else 0
        confidence = max(0.3, min(0.95, 1 - (stddev / (predicted + 0.001))))
        
        return predicted, confidence


class AnomalyDetector:
    """Detect anomalies in metrics"""
    
    def __init__(self, db: TimeSeriesDatabase, alert_manager: AlertManager):
        self.db = db
        self.alert_manager = alert_manager
    
    def detect_anomalies(self, deployment: str, current_snapshot: MetricsSnapshot) -> List[AnomalyAlert]:
        """Detect anomalies"""
        anomalies = []
        recent = self.db.get_recent_metrics(deployment, hours=24)
        
        if len(recent) < 10:
            return anomalies
        
        # CPU spike anomaly
        recent_cpu = [s.node_utilization for s in recent[-20:]]
        avg_cpu = statistics.mean(recent_cpu)
        stddev_cpu = statistics.stdev(recent_cpu) if len(recent_cpu) > 1 else 0
        
        if current_snapshot.node_utilization > avg_cpu + (3 * stddev_cpu):
            deviation = ((current_snapshot.node_utilization - avg_cpu) / avg_cpu * 100)
            anomaly = AnomalyAlert(
                timestamp=datetime.now(),
                deployment=deployment,
                anomaly_type="cpu_spike",
                severity="warning" if deviation < 50 else "critical",
                description=f"Unusual CPU spike detected",
                current_value=current_snapshot.node_utilization,
                expected_value=avg_cpu,
                deviation_percent=deviation
            )
            anomalies.append(anomaly)
            self.db.store_anomaly(anomaly)
            
            self.alert_manager.send_alert(
                title=f"CPU Anomaly: {deployment}",
                message=f"CPU spiked to {current_snapshot.node_utilization:.1f}% (expected {avg_cpu:.1f}%)",
                severity=anomaly.severity,
                fields={
                    "Deployment": deployment,
                    "Current CPU": f"{current_snapshot.node_utilization:.1f}%",
                    "Expected CPU": f"{avg_cpu:.1f}%",
                    "Deviation": f"+{deviation:.1f}%"
                }
            )
        
        # Scaling thrashing
        recent_actions = [s.action_taken for s in recent[-30:]]
        adjust_count = sum(1 for a in recent_actions if a in ['increase', 'decrease'])
        
        if adjust_count > 15:
            anomaly = AnomalyAlert(
                timestamp=datetime.now(),
                deployment=deployment,
                anomaly_type="scaling_thrashing",
                severity="warning",
                description=f"Excessive scaling activity ({adjust_count} adjustments)",
                current_value=adjust_count,
                expected_value=5.0,
                deviation_percent=(adjust_count - 5) / 5 * 100
            )
            anomalies.append(anomaly)
            self.db.store_anomaly(anomaly)
            
            self.alert_manager.send_alert(
                title=f"Scaling Thrashing: {deployment}",
                message=f"Detected {adjust_count} adjustments in 30 minutes",
                severity="warning",
                fields={"Deployment": deployment, "Adjustments": str(adjust_count)}
            )
        
        return anomalies


class CostOptimizer:
    """Analyze and optimize costs"""
    
    def __init__(self, db: TimeSeriesDatabase, alert_manager: AlertManager):
        self.db = db
        self.alert_manager = alert_manager
        
        # Validate cost per vCPU
        import os
        cost_str = os.getenv('COST_PER_VCPU_HOUR', '0.04')
        try:
            from src.config_validator import ConfigValidator
            self.cost_per_vcpu_hour = ConfigValidator.validate_cost_per_vcpu(cost_str)
        except (ImportError, ValueError) as e:
            # Fallback if validator not available or invalid value
            try:
                val = float(cost_str)
                if val < 0 or val > 100:
                    raise ValueError(f"Cost out of range: {val}")
                self.cost_per_vcpu_hour = val
            except (ValueError, TypeError):
                logger.warning(f"Invalid COST_PER_VCPU_HOUR: {cost_str}, using default 0.04. Error: {e}")
                self.cost_per_vcpu_hour = 0.04
        
        # Cost per GB memory per hour (default: $0.004/GB-hour, typical cloud pricing)
        memory_cost_str = os.getenv('COST_PER_GB_MEMORY_HOUR', '0.004')
        try:
            self.cost_per_gb_memory_hour = float(memory_cost_str)
        except (ValueError, TypeError):
            logger.warning(f"Invalid COST_PER_GB_MEMORY_HOUR: {memory_cost_str}, using default 0.004")
            self.cost_per_gb_memory_hour = 0.004
    
    def analyze_costs(self, deployment: str, hours: int = 24) -> Optional[CostMetrics]:
        """Analyze cost efficiency with detailed CPU and memory breakdown"""
        recent = self.db.get_recent_metrics(deployment, hours=hours)
        
        if len(recent) < 10:
            return None
        
        # Calculate averages
        avg_pod_count = statistics.mean([s.pod_count for s in recent])
        avg_utilization = statistics.mean([s.node_utilization for s in recent])
        avg_cpu_request = statistics.mean([s.cpu_request for s in recent]) / 1000.0  # Convert to cores
        avg_cpu_usage = statistics.mean([s.pod_cpu_usage for s in recent])  # Already in cores
        avg_memory_request = statistics.mean([s.memory_request for s in recent if s.memory_request > 0]) or 512  # MB
        avg_memory_usage = statistics.mean([s.memory_usage for s in recent if s.memory_usage > 0]) or 0.0  # MB
        
        # Calculate runtime hours (based on data points and check interval)
        # Assuming metrics are collected every CHECK_INTERVAL seconds
        import os
        check_interval = int(os.getenv('CHECK_INTERVAL', '60'))
        runtime_hours = (len(recent) * check_interval) / 3600.0  # Convert to hours
        
        # CPU cost calculation
        cpu_requested_cores = avg_pod_count * avg_cpu_request
        cpu_used_cores = avg_pod_count * avg_cpu_usage
        cpu_cost = cpu_requested_cores * self.cost_per_vcpu_hour * runtime_hours
        
        # Memory cost calculation (convert MB to GB)
        memory_requested_gb = (avg_pod_count * avg_memory_request) / 1024.0
        memory_used_gb = (avg_pod_count * avg_memory_usage) / 1024.0
        memory_cost = memory_requested_gb * self.cost_per_gb_memory_hour * runtime_hours
        
        # Total cost
        total_cost = cpu_cost + memory_cost
        
        # Calculate utilization percentages
        cpu_utilization_percent = (cpu_used_cores / cpu_requested_cores * 100) if cpu_requested_cores > 0 else 0
        memory_utilization_percent = (memory_used_gb / memory_requested_gb * 100) if memory_requested_gb > 0 else 0
        
        # Wasted cost calculation (when low utilization but high request)
        wasted_cpu_cores = max(0, cpu_requested_cores - cpu_used_cores)
        wasted_memory_gb = max(0, memory_requested_gb - memory_used_gb)
        
        wasted_cpu_cost = wasted_cpu_cores * self.cost_per_vcpu_hour * runtime_hours
        wasted_memory_cost = wasted_memory_gb * self.cost_per_gb_memory_hour * runtime_hours
        total_wasted_cost = wasted_cpu_cost + wasted_memory_cost
        
        # Overall wasted capacity percentage
        requested_capacity = cpu_requested_cores
        wasted_capacity = wasted_cpu_cores
        wasted_percent = (wasted_capacity / requested_capacity * 100) if requested_capacity > 0 else 0
        
        # Monthly projections (extrapolate from runtime hours)
        hours_per_month = 730
        monthly_cpu_cost = cpu_requested_cores * self.cost_per_vcpu_hour * hours_per_month
        monthly_memory_cost = memory_requested_gb * self.cost_per_gb_memory_hour * hours_per_month
        monthly_cost = monthly_cpu_cost + monthly_memory_cost
        
        # Optimization potential
        optimal_cpu_cores = cpu_used_cores * 1.2  # 20% buffer
        optimal_memory_gb = memory_used_gb * 1.2
        optimal_cpu_cost = optimal_cpu_cores * self.cost_per_vcpu_hour * hours_per_month
        optimal_memory_cost = optimal_memory_gb * self.cost_per_gb_memory_hour * hours_per_month
        optimal_total_cost = optimal_cpu_cost + optimal_memory_cost
        optimization_potential = monthly_cost - optimal_total_cost
        
        # Generate recommendation
        if wasted_percent > 40 or cpu_utilization_percent < 30:
            recommendation = (
                f"High waste detected. CPU utilization: {cpu_utilization_percent:.1f}%, "
                f"Memory utilization: {memory_utilization_percent:.1f}%. "
                f"Consider reducing CPU request from {int(avg_cpu_request*1000)}m to {int(avg_cpu_usage*1000*1.2)}m, "
                f"and memory from {int(avg_memory_request)}MB to {int(avg_memory_usage*1.2)}MB"
            )
        elif wasted_percent > 25 or cpu_utilization_percent < 50:
            recommendation = (
                f"Moderate waste. CPU: {cpu_utilization_percent:.1f}%, Memory: {memory_utilization_percent:.1f}%. "
                f"Could save ${optimization_potential:.2f}/month"
            )
        elif avg_utilization < 50:
            recommendation = "Low node utilization. Consider increasing HPA target"
        else:
            recommendation = "Well-optimized"
        
        metrics = CostMetrics(
            deployment=deployment,
            avg_pod_count=avg_pod_count,
            avg_utilization=avg_utilization,
            wasted_capacity_percent=wasted_percent,
            estimated_monthly_cost=monthly_cost,
            optimization_potential=max(0, optimization_potential),
            recommendation=recommendation,
            cpu_cost=cpu_cost,
            memory_cost=memory_cost,
            total_cost=total_cost,
            wasted_cpu_cost=wasted_cpu_cost,
            wasted_memory_cost=wasted_memory_cost,
            total_wasted_cost=total_wasted_cost,
            cpu_utilization_percent=cpu_utilization_percent,
            memory_utilization_percent=memory_utilization_percent,
            runtime_hours=runtime_hours
        )
        
        if optimization_potential > 50:
            self.alert_manager.send_alert(
                title=f"Cost Optimization: {deployment}",
                message=recommendation,
                severity="info",
                fields={
                    "Monthly Cost": f"${monthly_cost:.2f}",
                    "Potential Savings": f"${optimization_potential:.2f}",
                    "Wasted Capacity": f"{wasted_percent:.1f}%",
                    "CPU Utilization": f"{cpu_utilization_percent:.1f}%",
                    "Memory Utilization": f"{memory_utilization_percent:.1f}%"
                }
            )
        
        return metrics
    
    def generate_weekly_report(self, deployments: List[str]):
        """Generate weekly cost report"""
        total_cost = 0
        total_savings = 0
        report_lines = ["📊 Weekly Cost Report\n"]
        
        for deployment in deployments:
            metrics = self.analyze_costs(deployment)
            if metrics:
                total_cost += metrics.estimated_monthly_cost
                total_savings += metrics.optimization_potential
                report_lines.append(f"• {deployment}: ${metrics.estimated_monthly_cost:.2f}/month (save ${metrics.optimization_potential:.2f})")
        
        report_lines.append(f"\n💰 Total: ${total_cost:.2f}")
        report_lines.append(f"💡 Savings: ${total_savings:.2f}")
        
        self.alert_manager.send_alert(
            title="Weekly Cost Report",
            message="\n".join(report_lines),
            severity="info",
            fields={"Total Cost": f"${total_cost:.2f}", "Savings": f"${total_savings:.2f}"}
        )


class PredictiveScaler:
    """Predictive scaling with validation and adaptive learning"""
    
    def __init__(self, db: TimeSeriesDatabase, pattern_recognizer: PatternRecognizer, alert_manager: AlertManager):
        self.db = db
        self.pattern_recognizer = pattern_recognizer
        self.alert_manager = alert_manager
        self.min_accuracy_threshold = float(os.getenv('PREDICTION_MIN_ACCURACY', '0.60'))  # 60% accuracy required
        self.min_predictions_for_trust = int(os.getenv('PREDICTION_MIN_SAMPLES', '10'))  # Need 10 predictions
    
    def get_adaptive_confidence(self, deployment: str, base_confidence: float) -> float:
        """
        Adjust confidence based on historical prediction accuracy
        Reduces confidence if predictions have been inaccurate
        """
        accuracy_stats = self.db.get_prediction_accuracy(deployment)
        
        if not accuracy_stats:
            # No history yet, use base confidence but reduce it slightly
            return base_confidence * 0.9
        
        accuracy_rate = accuracy_stats['accuracy_rate'] / 100.0
        false_positive_rate = accuracy_stats['false_positive_rate'] / 100.0
        total = accuracy_stats['total_predictions']
        
        # Need minimum samples before trusting
        if total < self.min_predictions_for_trust:
            return base_confidence * 0.8  # Reduce confidence until we have enough data
        
        # Adjust confidence based on accuracy
        # If accuracy is low, reduce confidence significantly
        if accuracy_rate < self.min_accuracy_threshold:
            adjusted = base_confidence * accuracy_rate
            logger.warning(
                f"{deployment} - Low prediction accuracy ({accuracy_rate:.0%}), "
                f"reducing confidence from {base_confidence:.0%} to {adjusted:.0%}"
            )
            return adjusted
        
        # If false positive rate is high, reduce confidence for scale-up predictions
        if false_positive_rate > 0.3:  # More than 30% false positives
            adjusted = base_confidence * (1.0 - false_positive_rate * 0.5)
            logger.warning(
                f"{deployment} - High false positive rate ({false_positive_rate:.0%}), "
                f"reducing confidence to {adjusted:.0%}"
            )
            return adjusted
        
        # Good accuracy, use base confidence
        return base_confidence
    
    def should_trust_prediction(self, deployment: str, action: str) -> bool:
        """
        Determine if we should trust this prediction based on historical accuracy
        """
        accuracy_stats = self.db.get_prediction_accuracy(deployment)
        
        if not accuracy_stats:
            # No history, be conservative
            return False
        
        total = accuracy_stats['total_predictions']
        accuracy_rate = accuracy_stats['accuracy_rate'] / 100.0
        false_positive_rate = accuracy_stats['false_positive_rate'] / 100.0
        
        # Need minimum samples
        if total < self.min_predictions_for_trust:
            return False
        
        # Don't trust if accuracy is too low
        if accuracy_rate < self.min_accuracy_threshold:
            return False
        
        # Don't trust scale-up predictions if false positive rate is high
        if action == "pre_scale_up" and false_positive_rate > 0.4:
            logger.warning(
                f"{deployment} - High false positive rate ({false_positive_rate:.0%}), "
                "skipping predictive scale-up"
            )
            return False
        
        return True
    
    def predict_and_recommend(self, deployment: str, current_target: int) -> Optional[Prediction]:
        """Predict and recommend with adaptive learning"""
        # Validate previous predictions first
        self.db.validate_predictions(deployment, hours_back=2)
        
        predicted_cpu, base_confidence = self.pattern_recognizer.predict_next_hour(deployment)
        
        if base_confidence < 0.5:
            return None
        
        # Get adaptive confidence based on historical accuracy
        adaptive_confidence = self.get_adaptive_confidence(deployment, base_confidence)
        
        # Determine action
        if predicted_cpu > 80:
            action = "pre_scale_up"
            reasoning = f"Predicted {predicted_cpu:.1f}% > 80% - pre-scale up"
            recommended_target = max(50, current_target - 10)
        elif predicted_cpu < 50:
            action = "scale_down"
            reasoning = f"Predicted {predicted_cpu:.1f}% < 50% - scale down"
            recommended_target = min(80, current_target + 10)
        else:
            action = "maintain"
            reasoning = f"Predicted {predicted_cpu:.1f}% in normal range"
            recommended_target = current_target
        
        # Check if we should trust this prediction
        if action == "pre_scale_up" and not self.should_trust_prediction(deployment, action):
            logger.info(
                f"{deployment} - Prediction suggests scale-up but historical accuracy is low, "
                "skipping to prevent false positive"
            )
            # Still store prediction for learning, but don't act on it
            action = "maintain"
            reasoning = f"Predicted {predicted_cpu:.1f}% but low historical accuracy - maintaining"
            recommended_target = current_target
        
        prediction = Prediction(
            timestamp=datetime.now(),
            deployment=deployment,
            predicted_cpu=predicted_cpu,
            confidence=adaptive_confidence,  # Use adaptive confidence
            recommended_action=action,
            reasoning=reasoning
        )
        
        self.db.store_prediction(prediction)
        
        # Log accuracy stats if available
        accuracy_stats = self.db.get_prediction_accuracy(deployment)
        if accuracy_stats:
            logger.debug(
                f"{deployment} - Prediction accuracy: {accuracy_stats['accuracy_rate']:.1f}% "
                f"({accuracy_stats['accurate_predictions']}/{accuracy_stats['total_predictions']}), "
                f"False positives: {accuracy_stats['false_positive_rate']:.1f}%"
            )
        
        if action == "pre_scale_up" and adaptive_confidence > 0.7:
            self.alert_manager.send_alert(
                title=f"Predictive Scaling: {deployment}",
                message=reasoning,
                severity="info",
                fields={
                    "Predicted CPU": f"{predicted_cpu:.1f}%",
                    "Confidence": f"{adaptive_confidence:.0%}",
                    "Recommended": f"{recommended_target}%",
                    "Historical Accuracy": f"{accuracy_stats['accuracy_rate']:.1f}%" if accuracy_stats else "N/A"
                }
            )
        
        return prediction


class AutoTuner:
    """Auto-tune HPA targets"""
    
    def __init__(self, db: TimeSeriesDatabase, alert_manager: AlertManager):
        self.db = db
        self.alert_manager = alert_manager
    
    def find_optimal_target(self, deployment: str) -> Optional[Tuple[int, float]]:
        """Find optimal HPA target"""
        recent = self.db.get_recent_metrics(deployment, hours=168)
        
        if len(recent) < 100:
            return None
        
        target_performance = defaultdict(list)
        
        for snapshot in recent:
            if not snapshot.scheduling_spike:
                target_performance[snapshot.hpa_target].append({
                    'utilization': snapshot.node_utilization,
                    'confidence': snapshot.confidence
                })
        
        best_target = None
        best_score = -1
        
        for target, samples in target_performance.items():
            if len(samples) < 10:
                continue
            
            avg_util = statistics.mean([s['utilization'] for s in samples])
            avg_conf = statistics.mean([s['confidence'] for s in samples])
            util_stddev = statistics.stdev([s['utilization'] for s in samples])
            
            target_score = 65
            util_penalty = abs(avg_util - target_score)
            stability_bonus = max(0, 10 - util_stddev)
            confidence_bonus = avg_conf * 10
            
            score = 100 - util_penalty + stability_bonus + confidence_bonus
            
            if score > best_score:
                best_score = score
                best_target = target
        
        if best_target:
            confidence = best_score / 100.0
            self.db.update_optimal_target(deployment, best_target, confidence)
            logger.info(f"{deployment} - Optimal target: {best_target}% (confidence: {confidence:.0%})")
            return best_target, confidence
        
        return None