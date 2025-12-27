"""
Integrated Smart Autoscaler - Main Entry Point
Combines base operator with intelligence layer
"""

import asyncio
import logging
import os
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

logger = logging.getLogger(__name__)


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
        
        # Initialize observability components
        self.prometheus_exporter = PrometheusExporter(port=8000)
        self.dashboard = WebDashboard(self.db, self, port=5000)
        
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
            
            # Get actual pod CPU usage and pod count
            avg_cpu_per_pod, current_replicas = self.controller.analyzer.get_pod_cpu_usage(
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
                node_selector=str(node_selector)
            )
            
            self.db.store_metrics(snapshot)
            
            # Anomaly detection
            anomalies = self.anomaly_detector.detect_anomalies(deployment, snapshot)
            if anomalies:
                logger.warning(f"{deployment} - {len(anomalies)} anomalies detected")
            
            # Predictive scaling
            if self.enable_predictive:
                prediction = self.predictive_scaler.predict_and_recommend(deployment, decision.current_target)
                if prediction and prediction.confidence > 0.75:
                    logger.info(f"{deployment} - Prediction: {prediction.predicted_cpu:.1f}% (confidence: {prediction.confidence:.0%})")
                    if prediction.recommended_action == "pre_scale_up":
                        decision.recommended_target = max(50, decision.recommended_target - 5)
                        decision.reason += " + Predictive pre-scaling"
                    
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
        
        while True:
            try:
                iteration += 1
                logger.info(f"\n{'='*80}")
                logger.info(f"Iteration {iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'='*80}")
                
                # Process each watched deployment
                for key, config in self.watched_deployments.items():
                    await self.process_deployment(config)
                    await asyncio.sleep(2)  # Small delay between deployments
                
                # Weekly reports
                await self.weekly_report()
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
            
            logger.info(f"Sleeping for {self.check_interval}s")
            await asyncio.sleep(self.check_interval)


def main():
    """Main entry point"""
    logging.basicConfig(
        level=os.getenv('LOG_LEVEL', 'INFO'),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configuration from environment
    PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus-server.monitoring:9090")
    DB_PATH = os.getenv("DB_PATH", "/data/autoscaler.db")
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
    DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
    TARGET_NODE_UTILIZATION = float(os.getenv("TARGET_NODE_UTILIZATION", "70.0"))
    
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
            
            operator.add_deployment(
                namespace=namespace,
                deployment=deployment_name,
                hpa_name=os.getenv(f"DEPLOYMENT_{i}_HPA_NAME", deployment_name),
                startup_filter_minutes=int(os.getenv(f"DEPLOYMENT_{i}_STARTUP_FILTER", "2"))
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
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
