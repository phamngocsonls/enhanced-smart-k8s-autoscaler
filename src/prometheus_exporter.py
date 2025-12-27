"""
Prometheus Metrics Exporter
Exposes operator metrics for monitoring and alerting
"""

from prometheus_client import start_http_server, Gauge, Counter, Histogram, Info
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class PrometheusExporter:
    """Export operator metrics to Prometheus"""
    
    def __init__(self, port: int = 8000):
        self.port = port
        
        # Operator info
        self.operator_info = Info(
            'autoscaler_operator',
            'Smart Autoscaler operator information'
        )
        
        # Current state metrics
        self.node_utilization = Gauge(
            'autoscaler_node_utilization_percent',
            'Node CPU utilization percentage',
            ['deployment', 'namespace', 'node_selector']
        )
        
        self.hpa_target = Gauge(
            'autoscaler_hpa_target_percent',
            'Current HPA target percentage',
            ['deployment', 'namespace']
        )
        
        self.pod_count = Gauge(
            'autoscaler_pod_count',
            'Current number of pods',
            ['deployment', 'namespace']
        )
        
        self.confidence_score = Gauge(
            'autoscaler_confidence_score',
            'Decision confidence score (0-1)',
            ['deployment', 'namespace']
        )
        
        self.schedulable_capacity = Gauge(
            'autoscaler_schedulable_capacity_cores',
            'Schedulable CPU capacity in cores',
            ['deployment', 'namespace']
        )
        
        # Prediction metrics
        self.predicted_cpu = Gauge(
            'autoscaler_predicted_cpu_percent',
            'Predicted CPU for next hour',
            ['deployment', 'namespace']
        )
        
        self.prediction_confidence = Gauge(
            'autoscaler_prediction_confidence',
            'Prediction confidence (0-1)',
            ['deployment', 'namespace']
        )
        
        # Cost metrics
        self.monthly_cost = Gauge(
            'autoscaler_monthly_cost_usd',
            'Estimated monthly cost in USD',
            ['deployment', 'namespace']
        )
        
        self.wasted_capacity = Gauge(
            'autoscaler_wasted_capacity_percent',
            'Wasted capacity percentage',
            ['deployment', 'namespace']
        )
        
        self.savings_potential = Gauge(
            'autoscaler_savings_potential_usd',
            'Potential monthly savings in USD',
            ['deployment', 'namespace']
        )
        
        # Action counters
        self.adjustments_total = Counter(
            'autoscaler_adjustments_total',
            'Total number of HPA adjustments',
            ['deployment', 'namespace', 'action']
        )
        
        self.anomalies_detected = Counter(
            'autoscaler_anomalies_detected_total',
            'Total anomalies detected',
            ['deployment', 'namespace', 'anomaly_type', 'severity']
        )
        
        self.predictions_made = Counter(
            'autoscaler_predictions_made_total',
            'Total predictions made',
            ['deployment', 'namespace']
        )
        
        self.alerts_sent = Counter(
            'autoscaler_alerts_sent_total',
            'Total alerts sent',
            ['channel', 'severity']
        )
        
        # Performance metrics
        self.decision_duration = Histogram(
            'autoscaler_decision_duration_seconds',
            'Time to make scaling decision',
            ['deployment', 'namespace']
        )
        
        self.prediction_accuracy = Gauge(
            'autoscaler_prediction_accuracy_percent',
            'Prediction accuracy over last 24h',
            ['deployment', 'namespace']
        )
        
        # Prediction validation metrics
        self.prediction_false_positives = Gauge(
            'autoscaler_prediction_false_positives_total',
            'Total false positive predictions',
            ['deployment', 'namespace']
        )
        self.prediction_false_negatives = Gauge(
            'autoscaler_prediction_false_negatives_total',
            'Total false negative predictions',
            ['deployment', 'namespace']
        )
        self.prediction_total_validated = Gauge(
            'autoscaler_prediction_total_validated',
            'Total validated predictions',
            ['deployment', 'namespace']
        )
        
        # Auto-tuning metrics
        self.optimal_target = Gauge(
            'autoscaler_optimal_target_percent',
            'Learned optimal HPA target',
            ['deployment', 'namespace']
        )
        
        self.optimal_target_confidence = Gauge(
            'autoscaler_optimal_target_confidence',
            'Confidence in optimal target',
            ['deployment', 'namespace']
        )
        
        # Database metrics
        self.database_size = Gauge(
            'autoscaler_database_size_bytes',
            'Size of SQLite database'
        )
        
        self.metrics_stored = Counter(
            'autoscaler_metrics_stored_total',
            'Total metrics stored in database'
        )
        
        # Memory metrics
        self.memory_usage_mb = Gauge(
            'autoscaler_memory_usage_mb',
            'Current memory usage in MB'
        )
        self.memory_limit_mb = Gauge(
            'autoscaler_memory_limit_mb',
            'Memory limit in MB'
        )
        self.memory_usage_percent = Gauge(
            'autoscaler_memory_usage_percent',
            'Memory usage percentage'
        )
        
        # Rate limiting metrics
        self.rate_limit_delays = Counter(
            'autoscaler_rate_limit_delays_total',
            'Total number of rate limit delays',
            ['service']
        )
        
    def start(self):
        """Start Prometheus metrics server"""
        try:
            start_http_server(self.port)
            logger.info(f"Prometheus metrics server started on port {self.port}")
            
            # Set operator info
            self.operator_info.info({
                'version': '0.0.3',
                'features': 'predictive,auto-tuning,anomaly-detection,cost-optimization'
            })
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")
    
    def update_deployment_metrics(self, deployment: str, namespace: str, 
                                  node_utilization: float, hpa_target: int,
                                  pod_count: int, confidence: float,
                                  schedulable: float, node_selector: str):
        """Update current state metrics for deployment"""
        labels = {'deployment': deployment, 'namespace': namespace}
        
        self.node_utilization.labels(
            deployment=deployment, 
            namespace=namespace,
            node_selector=node_selector
        ).set(node_utilization)
        
        self.hpa_target.labels(**labels).set(hpa_target)
        self.pod_count.labels(**labels).set(pod_count)
        self.confidence_score.labels(**labels).set(confidence)
        self.schedulable_capacity.labels(**labels).set(schedulable)
    
    def update_prediction_metrics(self, deployment: str, namespace: str,
                                  predicted_cpu: float, confidence: float):
        """Update prediction metrics"""
        labels = {'deployment': deployment, 'namespace': namespace}
        
        self.predicted_cpu.labels(**labels).set(predicted_cpu)
        self.prediction_confidence.labels(**labels).set(confidence)
        self.predictions_made.labels(**labels).inc()
    
    def update_cost_metrics(self, deployment: str, namespace: str,
                           monthly_cost: float, wasted: float, savings: float):
        """Update cost metrics"""
        labels = {'deployment': deployment, 'namespace': namespace}
        
        self.monthly_cost.labels(**labels).set(monthly_cost)
        self.wasted_capacity.labels(**labels).set(wasted)
        self.savings_potential.labels(**labels).set(savings)
    
    def record_adjustment(self, deployment: str, namespace: str, action: str):
        """Record HPA adjustment"""
        self.adjustments_total.labels(
            deployment=deployment,
            namespace=namespace,
            action=action
        ).inc()
    
    def record_anomaly(self, deployment: str, namespace: str,
                      anomaly_type: str, severity: str):
        """Record anomaly detection"""
        self.anomalies_detected.labels(
            deployment=deployment,
            namespace=namespace,
            anomaly_type=anomaly_type,
            severity=severity
        ).inc()
    
    def record_alert(self, channel: str, severity: str):
        """Record alert sent"""
        self.alerts_sent.labels(
            channel=channel,
            severity=severity
        ).inc()
    
    def record_decision_time(self, deployment: str, namespace: str, duration: float):
        """Record time taken to make decision"""
        self.decision_duration.labels(
            deployment=deployment,
            namespace=namespace
        ).observe(duration)
    
    def update_optimal_target(self, deployment: str, namespace: str,
                             target: int, confidence: float):
        """Update learned optimal target"""
        labels = {'deployment': deployment, 'namespace': namespace}
        
        self.optimal_target.labels(**labels).set(target)
        self.optimal_target_confidence.labels(**labels).set(confidence)
    
    def update_database_metrics(self, size_bytes: int, total_records: int):
        """Update database metrics"""
        self.database_size.set(size_bytes)
        # Use set_function instead of inc for total
    
    def record_metric_stored(self):
        """Increment stored metrics counter"""
        self.metrics_stored.inc()
    
    def update_memory_metrics(self, memory_mb: float, memory_limit_mb: float, memory_percent: float):
        """Update memory usage metrics"""
        self.memory_usage_mb.set(memory_mb)
        self.memory_limit_mb.set(memory_limit_mb)
        self.memory_usage_percent.set(memory_percent)
    
    def record_rate_limit_delay(self, service: str):
        """Record a rate limit delay event"""
        self.rate_limit_delays.labels(service=service).inc()