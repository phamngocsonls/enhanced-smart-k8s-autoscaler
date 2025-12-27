"""
Integrated Smart Autoscaler - Main Entry Point
Combines base operator with intelligence layer
"""

import asyncio
import logging
import os
import signal
import sys
import threading
from datetime import datetime
from typing import Dict

from src.operator import DynamicHPAController
from src.intelligence import (
    TimeSeriesDatabase, AlertManager, PatternRecognizer,
    AnomalyDetector, CostOptimizer, PredictiveScaler, AutoTuner,
    MetricsSnapshot
)
from src.dashboard import WebDashboard
from src.prometheus_exporter import PrometheusExporter
from src.config_validator import ConfigValidator
from src.logging_config import setup_structured_logging, get_logger
from src.memory_monitor import MemoryMonitor

logger = get_logger(__name__)


class EnhancedSmartAutoscaler:
    """Enhanced autoscaler with full intelligence"""
    
    def __init__(
        self,
        prometheus_url: str,
        db_path: str,
        webhooks: Dict[str, str],
        check_interval: int = 60,
        dry_run: bool = False,
        target_node_utilization: float = 70.0,
        enable_predictive: bool = True,
        enable_autotuning: bool = True
    ):
        self.controller = DynamicHPAController(prometheus_url, dry_run)
        self.check_interval = check_interval
        self.target_node_utilization = target_node_utilization
        self.watched_deployments: Dict[str, Dict] = {}
        
        # Intelligence layer
        self.db = TimeSeriesDatabase(db_path)
        self.alert_manager = AlertManager(webhooks)
        self.pattern_recognizer = PatternRecognizer(self.db)
        self.anomaly_detector = AnomalyDetector(self.db, self.alert_manager)
        self.cost_optimizer = CostOptimizer(self.db, self.alert_manager)
        self.predictive_scaler = PredictiveScaler(self.db, self.pattern_recognizer, self.alert_manager)
        self.auto_tuner = AutoTuner(self.db, self.alert_manager)
        
        self.enable_predictive = enable_predictive
        self.enable_autotuning = enable_autotuning
        
        self.last_weekly_report = datetime.now()
        self.last_cost_analysis = {}
        
        # Shutdown event for graceful shutdown
        self.shutdown_event = threading.Event()
        
        # Initialize memory monitor for OOM prevention
        memory_limit_mb = int(os.getenv('MEMORY_LIMIT_MB', '0')) or None
        self.memory_monitor = MemoryMonitor(
            warning_threshold=float(os.getenv('MEMORY_WARNING_THRESHOLD', '0.75')),
            critical_threshold=float(os.getenv('MEMORY_CRITICAL_THRESHOLD', '0.90')),
            check_interval=int(os.getenv('MEMORY_CHECK_INTERVAL', '30')),
            memory_limit_mb=memory_limit_mb
        )
        self.memory_monitor.start_monitoring()
        
        # Initialize observability components
        self.prometheus_exporter = PrometheusExporter(port=8000)
        self.dashboard = WebDashboard(self.db, self, port=5000)
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        # Start Prometheus metrics server in background
        try:
            self.prometheus_exporter.start()
        except Exception as e:
            logger.warning(f"Failed to start Prometheus exporter: {e}")
        
        # Start dashboard server in background thread
        try:
            dashboard_thread = threading.Thread(
                target=self.dashboard.start,
                daemon=True,
                name="dashboard-server"
            )
            dashboard_thread.start()
            logger.info("Dashboard server started in background thread")
        except Exception as e:
            logger.warning(f"Failed to start dashboard server: {e}")
    
    def _setup_signal_handlers(self):
        """Setup graceful shutdown handlers"""
        def handle_signal(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown_event.set()
        
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)
    
    async def _cleanup(self):
        """Cleanup resources on shutdown"""
        logger.info("Cleaning up resources...")
        
        # Stop memory monitoring
        if hasattr(self, 'memory_monitor') and self.memory_monitor:
            self.memory_monitor.stop_monitoring()
        
        # Close database connection
        if hasattr(self, 'db') and self.db:
            self.db.close()
        
        logger.info("Cleanup complete, shutting down")
    
    def add_deployment(self, namespace: str, deployment: str, hpa_name: str = None, startup_filter_minutes: int = 2):
        """Add deployment to watch"""
        key = f"{namespace}/{deployment}"
        self.watched_deployments[key] = {
            'namespace': namespace,
            'deployment': deployment,
            'hpa_name': hpa_name or deployment,
            'startup_filter_minutes': startup_filter_minutes
        }
        logger.info(f"Watching: {key} with intelligence enabled")
    
    async def process_deployment(self, config: Dict):
        """Process single deployment"""
        namespace = config['namespace']
        deployment = config['deployment']
        hpa_name = config['hpa_name']
        key = f"{namespace}/{deployment}"
        
        # Check memory before processing
        memory_usage = self.memory_monitor.check_and_act()
        
        # Update Prometheus memory metrics
        try:
            self.prometheus_exporter.update_memory_metrics(
                memory_mb=memory_usage['memory_mb'],
                memory_limit_mb=memory_usage['memory_limit_mb'],
                memory_percent=memory_usage['memory_percent']
            )
        except Exception as e:
            logger.debug(f"Failed to update memory metrics: {e}")
        
        if memory_usage['status'] == 'critical':
            logger.warning(
                f"Skipping deployment {namespace}/{deployment} due to critical memory usage: "
                f"{memory_usage['memory_percent']:.1f}%"
            )
            return
        
        try:
            # Get base scaling decision
            decision = self.controller.calculate_hpa_target(
                namespace, deployment, hpa_name,
                config['startup_filter_minutes'],
                self.target_node_utilization
            )
            
            if not decision:
                return
            
            # Store metrics
            node_selector = self.controller.analyzer.get_deployment_node_selector(namespace, deployment)
            node_metrics = self.controller.analyzer.get_node_metrics(node_selector)
            cpu_request = self.controller.analyzer.get_deployment_cpu_request(namespace, deployment)
            memory_request = self.controller.analyzer.get_deployment_memory_request(namespace, deployment)
            
            # Get actual pod CPU usage and pod count
            avg_cpu_per_pod, current_replicas = self.controller.analyzer.get_pod_cpu_usage(
                namespace, deployment, config['startup_filter_minutes']
            )
            
            # Get actual pod memory usage
            avg_memory_per_pod = self.controller.analyzer.get_pod_memory_usage(
                namespace, deployment, config['startup_filter_minutes']
            )
            
            snapshot = MetricsSnapshot(
                timestamp=datetime.now(),
                deployment=deployment,
                namespace=namespace,
                node_utilization=node_metrics.utilization_percent,
                pod_count=current_replicas,  # Use actual pod count
                pod_cpu_usage=avg_cpu_per_pod,  # Use actual CPU usage in cores
                hpa_target=decision.current_target,
                confidence=decision.confidence,
                scheduling_spike=decision.scheduling_spike_detected,
                action_taken=decision.action,
                cpu_request=cpu_request,
                memory_request=memory_request,
                memory_usage=avg_memory_per_pod,
                node_selector=str(node_selector)
            )
            
            self.db.store_metrics(snapshot)
            
            # Anomaly detection
            anomalies = self.anomaly_detector.detect_anomalies(deployment, snapshot)
            if anomalies:
                logger.warning(f"{deployment} - {len(anomalies)} anomalies detected")
            
            # Predictive scaling with validation
            if self.enable_predictive:
                prediction = self.predictive_scaler.predict_and_recommend(deployment, decision.current_target)
                if prediction:
                    # Get accuracy stats for logging
                    accuracy_stats = self.db.get_prediction_accuracy(deployment)
                    accuracy_info = ""
                    if accuracy_stats:
                        accuracy_info = f" (accuracy: {accuracy_stats['accuracy_rate']:.1f}%, FP: {accuracy_stats['false_positive_rate']:.1f}%)"
                    
                    logger.info(
                        f"{deployment} - Prediction: {prediction.predicted_cpu:.1f}% "
                        f"(confidence: {prediction.confidence:.0%}, action: {prediction.recommended_action}){accuracy_info}"
                    )
                    
                    # Only apply prediction if confidence is high AND we trust predictions
                    if prediction.confidence > 0.75 and prediction.recommended_action != "maintain":
                        if prediction.recommended_action == "pre_scale_up":
                            # Only scale if we trust predictions (checked in predict_and_recommend)
                            decision.recommended_target = max(50, decision.recommended_target - 5)
                            decision.reason += " + Predictive pre-scaling"
                            logger.info(f"{deployment} - Applying predictive scale-up")
                        elif prediction.recommended_action == "scale_down":
                            decision.recommended_target = min(85, decision.recommended_target + 5)
                            decision.reason += " + Predictive scale-down"
                            logger.info(f"{deployment} - Applying predictive scale-down")
                    else:
                        if prediction.recommended_action == "pre_scale_up":
                            logger.info(
                                f"{deployment} - Prediction suggests scale-up but confidence too low "
                                f"({prediction.confidence:.0%}) or accuracy insufficient - skipping"
                            )
                    
                    # Update prediction metrics
                    try:
                        self.prometheus_exporter.update_prediction_metrics(
                            deployment=deployment,
                            namespace=namespace,
                            predicted_cpu=prediction.predicted_cpu,
                            confidence=prediction.confidence
                        )
                    except Exception as e:
                        logger.debug(f"Failed to update prediction metrics: {e}")
            
            # Auto-tuning
            if self.enable_autotuning:
                optimal = self.auto_tuner.find_optimal_target(deployment)
                if optimal:
                    optimal_target, confidence = optimal
                    if confidence > 0.8 and abs(optimal_target - decision.recommended_target) > 5:
                        logger.info(f"{deployment} - Auto-tuned target: {optimal_target}% (confidence: {confidence:.0%})")
                        decision.recommended_target = optimal_target
                        decision.reason += " + Auto-tuned"
            
            # Apply HPA adjustment
            self.controller.apply_hpa_target(namespace, hpa_name, decision)
            
            # Update prediction accuracy metrics if available
            try:
                accuracy_stats = self.db.get_prediction_accuracy(deployment)
                if accuracy_stats:
                    self.prometheus_exporter.prediction_accuracy.labels(
                        deployment=deployment,
                        namespace=namespace
                    ).set(accuracy_stats['accuracy_rate'])
                    
                    self.prometheus_exporter.prediction_false_positives.labels(
                        deployment=deployment,
                        namespace=namespace
                    ).set(accuracy_stats['false_positives'])
                    
                    self.prometheus_exporter.prediction_false_negatives.labels(
                        deployment=deployment,
                        namespace=namespace
                    ).set(accuracy_stats['false_negatives'])
                    
                    self.prometheus_exporter.prediction_total_validated.labels(
                        deployment=deployment,
                        namespace=namespace
                    ).set(accuracy_stats['total_predictions'])
            except Exception as e:
                logger.debug(f"Failed to update prediction accuracy metrics: {e}")
            
            # Update Prometheus metrics
            try:
                self.prometheus_exporter.update_deployment_metrics(
                    deployment=deployment,
                    namespace=namespace,
                    node_utilization=node_metrics.utilization_percent,
                    hpa_target=decision.recommended_target,
                    pod_count=current_replicas,
                    confidence=decision.confidence,
                    schedulable=node_metrics.schedulable_capacity,
                    node_selector=str(node_selector)
                )
            except Exception as e:
                logger.debug(f"Failed to update Prometheus metrics: {e}")
            
            # Cost analysis (hourly)
            if key not in self.last_cost_analysis or \
               (datetime.now() - self.last_cost_analysis[key]).seconds > 3600:
                cost_metrics = self.cost_optimizer.analyze_costs(deployment)
                if cost_metrics:
                    logger.info(f"{deployment} - Cost: ${cost_metrics.estimated_monthly_cost:.2f}/month, "
                              f"Waste: {cost_metrics.wasted_capacity_percent:.1f}%")
                    
                    # Update cost metrics
                    try:
                        self.prometheus_exporter.update_cost_metrics(
                            deployment=deployment,
                            namespace=namespace,
                            monthly_cost=cost_metrics.estimated_monthly_cost,
                            wasted=cost_metrics.wasted_capacity_percent,
                            savings=cost_metrics.optimization_potential
                        )
                    except Exception as e:
                        logger.debug(f"Failed to update cost metrics: {e}")
                
                self.last_cost_analysis[key] = datetime.now()
        
        except Exception as e:
            logger.error(f"Error processing {key}: {e}", exc_info=True)
    
    async def weekly_report(self):
        """Generate weekly reports"""
        if (datetime.now() - self.last_weekly_report).days >= 7:
            logger.info("Generating weekly cost report...")
            deployments = [config['deployment'] for config in self.watched_deployments.values()]
            self.cost_optimizer.generate_weekly_report(deployments)
            self.last_weekly_report = datetime.now()
    
    async def run(self):
        """Main operator loop"""
        logger.info(
            f"🚀 Enhanced Smart Autoscaler Started\n"
            f"   Features: Historical Learning ✓, Predictive Scaling ✓, "
            f"Anomaly Detection ✓, Cost Optimization ✓, Auto-Tuning ✓\n"
            f"   Alert Channels: {', '.join(self.alert_manager.webhooks.keys())}\n"
            f"   Target Node Utilization: {self.target_node_utilization}%"
        )
        
        # Startup notification
        self.alert_manager.send_alert(
            title="Smart Autoscaler Started",
            message=f"Watching {len(self.watched_deployments)} deployments",
            severity="info",
            fields={
                "Deployments": str(len(self.watched_deployments)),
                "Features": "Predictive, Auto-tuning, Anomaly Detection, Cost Optimization"
            }
        )
        
        iteration = 0
        
        while not self.shutdown_event.is_set():
            try:
                iteration += 1
                logger.info(f"\n{'='*80}")
                logger.info(f"Iteration {iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'='*80}")
                
                # Process each watched deployment
                for key, config in self.watched_deployments.items():
                    if self.shutdown_event.is_set():
                        break
                    await self.process_deployment(config)
                    await asyncio.sleep(2)  # Small delay between deployments
                
                # Weekly reports
                if not self.shutdown_event.is_set():
                    await self.weekly_report()
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
            
            if not self.shutdown_event.is_set():
                logger.info(f"Sleeping for {self.check_interval}s")
                # Check shutdown event with timeout
                if self.shutdown_event.wait(timeout=self.check_interval):
                    break
        
        # Cleanup on shutdown
        await self._cleanup()


def main():
    """Main entry point"""
    # Setup structured logging
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    setup_structured_logging(
        log_level=log_level,
        json_format=os.getenv('LOG_FORMAT', 'json').lower() == 'json',
        extra_fields={
            'component': 'smart-autoscaler',
            'version': '0.0.3'
        }
    )
    
    logger = get_logger(__name__)
    
    # Configuration from environment with validation
    try:
        PROMETHEUS_URL = ConfigValidator.validate_prometheus_url(
            os.getenv("PROMETHEUS_URL", "http://prometheus-server.monitoring:9090")
        )
        DB_PATH = ConfigValidator.validate_db_path(
            os.getenv("DB_PATH", "/data/autoscaler.db")
        )
        CHECK_INTERVAL = ConfigValidator.validate_check_interval(
            os.getenv("CHECK_INTERVAL", "60")
        )
        DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
        TARGET_NODE_UTILIZATION = ConfigValidator.validate_target_utilization(
            os.getenv("TARGET_NODE_UTILIZATION", "70.0")
        )
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        sys.exit(1)
    
    # Feature flags
    ENABLE_PREDICTIVE = os.getenv("ENABLE_PREDICTIVE", "true").lower() == "true"
    ENABLE_AUTOTUNING = os.getenv("ENABLE_AUTOTUNING", "true").lower() == "true"
    
    # Webhook configuration
    webhooks = {}
    if slack_webhook := os.getenv("SLACK_WEBHOOK"):
        webhooks["slack"] = slack_webhook
    if teams_webhook := os.getenv("TEAMS_WEBHOOK"):
        webhooks["teams"] = teams_webhook
    if discord_webhook := os.getenv("DISCORD_WEBHOOK"):
        webhooks["discord"] = discord_webhook
    if generic_webhook := os.getenv("GENERIC_WEBHOOK"):
        webhooks["generic"] = generic_webhook
    
    if not webhooks:
        logger.warning("No alert webhooks configured - alerts will be logged only")
    
    try:
        # Initialize operator
        operator = EnhancedSmartAutoscaler(
            prometheus_url=PROMETHEUS_URL,
            db_path=DB_PATH,
            webhooks=webhooks,
            check_interval=CHECK_INTERVAL,
            dry_run=DRY_RUN,
            target_node_utilization=TARGET_NODE_UTILIZATION,
            enable_predictive=ENABLE_PREDICTIVE,
            enable_autotuning=ENABLE_AUTOTUNING
        )
        
        # Add deployments from environment variables
        i = 0
        deployments_added = 0
        while True:
            namespace = os.getenv(f"DEPLOYMENT_{i}_NAMESPACE")
            if not namespace:
                break
            
            deployment_name = os.getenv(f"DEPLOYMENT_{i}_NAME")
            if not deployment_name:
                logger.warning(f"DEPLOYMENT_{i}_NAME not set, skipping")
                i += 1
                continue
            
            startup_filter_str = os.getenv(f"DEPLOYMENT_{i}_STARTUP_FILTER", "2")
            try:
                startup_filter = ConfigValidator.validate_startup_filter(startup_filter_str)
            except ValueError as e:
                logger.warning(f"Invalid STARTUP_FILTER for deployment {i}: {startup_filter_str}, using default 2. Error: {e}")
                startup_filter = 2
            
            operator.add_deployment(
                namespace=namespace,
                deployment=deployment_name,
                hpa_name=os.getenv(f"DEPLOYMENT_{i}_HPA_NAME", deployment_name),
                startup_filter_minutes=startup_filter
            )
            deployments_added += 1
            i += 1
        
        if deployments_added == 0:
            logger.error("No deployments configured! Set DEPLOYMENT_0_NAMESPACE and DEPLOYMENT_0_NAME")
            return
        
        logger.info(f"Configured to watch {deployments_added} deployment(s)")
        
        # Run operator
        asyncio.run(operator.run())
        
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
        if 'operator' in locals():
            operator.shutdown_event.set()
            try:
                asyncio.run(operator._cleanup())
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
