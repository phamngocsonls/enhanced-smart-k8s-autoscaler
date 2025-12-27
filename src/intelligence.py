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
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()
    
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
                reasoning TEXT
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
    
    def store_metrics(self, snapshot: MetricsSnapshot):
        """Store metrics snapshot"""
        self.conn.execute("""
            INSERT INTO metrics_history 
            (timestamp, deployment, namespace, node_utilization, pod_count, 
             pod_cpu_usage, hpa_target, confidence, scheduling_spike, 
             action_taken, cpu_request, node_selector)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot.timestamp, snapshot.deployment, snapshot.namespace,
            snapshot.node_utilization, snapshot.pod_count, snapshot.pod_cpu_usage,
            snapshot.hpa_target, snapshot.confidence, snapshot.scheduling_spike,
            snapshot.action_taken, snapshot.cpu_request, snapshot.node_selector
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
                    node_selector=row[12]
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
            (timestamp, deployment, predicted_cpu, confidence, 
             recommended_action, reasoning)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            prediction.timestamp, prediction.deployment, prediction.predicted_cpu,
            prediction.confidence, prediction.recommended_action, prediction.reasoning
        ))
        self.conn.commit()
    
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
        self.cost_per_vcpu_hour = float(__import__('os').getenv('COST_PER_VCPU_HOUR', '0.04'))
    
    def analyze_costs(self, deployment: str) -> Optional[CostMetrics]:
        """Analyze cost efficiency"""
        recent = self.db.get_recent_metrics(deployment, hours=24)
        
        if len(recent) < 10:
            return None
        
        avg_pod_count = statistics.mean([s.pod_count for s in recent])
        avg_utilization = statistics.mean([s.node_utilization for s in recent])
        avg_cpu_request = statistics.mean([s.cpu_request for s in recent]) / 1000.0
        avg_cpu_usage = statistics.mean([s.pod_cpu_usage for s in recent])
        
        requested_capacity = avg_pod_count * avg_cpu_request
        wasted_capacity = requested_capacity - (avg_pod_count * avg_cpu_usage)
        wasted_percent = (wasted_capacity / requested_capacity * 100) if requested_capacity > 0 else 0
        
        hours_per_month = 730
        monthly_cost = avg_pod_count * avg_cpu_request * self.cost_per_vcpu_hour * hours_per_month
        
        optimal_capacity = avg_pod_count * avg_cpu_usage * 1.2
        optimal_cost = optimal_capacity * self.cost_per_vcpu_hour * hours_per_month / avg_cpu_request
        optimization_potential = monthly_cost - optimal_cost
        
        if wasted_percent > 40:
            recommendation = f"High waste. Consider reducing CPU request from {int(avg_cpu_request*1000)}m to {int(avg_cpu_usage*1000*1.2)}m"
        elif wasted_percent > 25:
            recommendation = f"Moderate waste. Could save ${optimization_potential:.2f}/month"
        elif avg_utilization < 50:
            recommendation = "Low utilization. Consider increasing HPA target"
        else:
            recommendation = "Well-optimized"
        
        metrics = CostMetrics(
            deployment=deployment,
            avg_pod_count=avg_pod_count,
            avg_utilization=avg_utilization,
            wasted_capacity_percent=wasted_percent,
            estimated_monthly_cost=monthly_cost,
            optimization_potential=max(0, optimization_potential),
            recommendation=recommendation
        )
        
        if optimization_potential > 50:
            self.alert_manager.send_alert(
                title=f"Cost Optimization: {deployment}",
                message=recommendation,
                severity="info",
                fields={
                    "Monthly Cost": f"${monthly_cost:.2f}",
                    "Potential Savings": f"${optimization_potential:.2f}",
                    "Wasted Capacity": f"{wasted_percent:.1f}%"
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
    """Predictive scaling"""
    
    def __init__(self, db: TimeSeriesDatabase, pattern_recognizer: PatternRecognizer, alert_manager: AlertManager):
        self.db = db
        self.pattern_recognizer = pattern_recognizer
        self.alert_manager = alert_manager
    
    def predict_and_recommend(self, deployment: str, current_target: int) -> Optional[Prediction]:
        """Predict and recommend"""
        predicted_cpu, confidence = self.pattern_recognizer.predict_next_hour(deployment)
        
        if confidence < 0.5:
            return None
        
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
        
        prediction = Prediction(
            timestamp=datetime.now(),
            deployment=deployment,
            predicted_cpu=predicted_cpu,
            confidence=confidence,
            recommended_action=action,
            reasoning=reasoning
        )
        
        self.db.store_prediction(prediction)
        
        if action == "pre_scale_up" and confidence > 0.7:
            self.alert_manager.send_alert(
                title=f"Predictive Scaling: {deployment}",
                message=reasoning,
                severity="info",
                fields={
                    "Predicted CPU": f"{predicted_cpu:.1f}%",
                    "Confidence": f"{confidence:.0%}",
                    "Recommended": f"{recommended_target}%"
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