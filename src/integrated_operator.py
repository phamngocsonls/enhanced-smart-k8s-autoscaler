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

from src.operator import DynamicHPAController, HPADecision
from src.intelligence import (
    TimeSeriesDatabase, AlertManager, PatternRecognizer,
    AnomalyDetector, CostOptimizer, PredictiveScaler, AutoTuner,
    MetricsSnapshot
)
from src.pattern_detector import PatternDetector, WorkloadPattern
from src.degraded_mode import DegradedModeHandler
from src.dashboard import WebDashboard
from src.prometheus_exporter import PrometheusExporter
from src.config_validator import ConfigValidator
from src.config_loader import ConfigLoader, OperatorConfig
from src.logging_config import setup_structured_logging, get_logger
from src.memory_monitor import MemoryMonitor
from src.priority_manager import PriorityManager

logger = get_logger(__name__)


class EnhancedSmartAutoscaler:
    """Enhanced autoscaler with full intelligence and hot reload support"""
    
    def __init__(
        self,
        config: OperatorConfig,
        db_path: str,
        config_loader: ConfigLoader = None
    ):
        self.config = config
        self.config_loader = config_loader
        self.controller = DynamicHPAController(config.prometheus_url, config.dry_run)
        self.watched_deployments: Dict[str, Dict] = {}
        
        # Intelligence layer
        self.db = TimeSeriesDatabase(db_path)
        self.alert_manager = AlertManager(config.webhooks)
        self.pattern_recognizer = PatternRecognizer(self.db)
        self.pattern_detector = PatternDetector(self.db)
        self.anomaly_detector = AnomalyDetector(self.db, self.alert_manager)
        self.cost_optimizer = CostOptimizer(self.db, self.alert_manager)
        self.predictive_scaler = PredictiveScaler(self.db, self.pattern_recognizer, self.alert_manager)
        self.auto_tuner = AutoTuner(self.db, self.alert_manager)
        self.priority_manager = PriorityManager(self.db)
        
        # Degraded mode handler
        self.degraded_mode = DegradedModeHandler(cache_ttl=300)  # 5-minute cache
        
        self.last_weekly_report = datetime.now()
        self.last_cost_analysis = {}
        
        # Shutdown event for graceful shutdown
        self.shutdown_event = threading.Event()
        
        # Reload lock to prevent concurrent reloads
        self.reload_lock = threading.Lock()
        
        # Initialize memory monitor for OOM prevention
        memory_limit_mb = int(os.getenv('MEMORY_LIMIT_MB', '0')) or None
        self.memory_monitor = MemoryMonitor(
            warning_threshold=config.memory_warning_threshold,
            critical_threshold=config.memory_critical_threshold,
            check_interval=config.memory_check_interval,
            memory_limit_mb=memory_limit_mb
        )
        self.memory_monitor.start_monitoring()
        
        # Initialize observability components
        self.prometheus_exporter = PrometheusExporter(port=8000)
        self.dashboard = WebDashboard(self.db, self, port=5000)
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        # Load initial deployments
        self._load_deployments_from_config(config)
        
        # Register hot reload callback
        if self.config_loader:
            self.config_loader.register_reload_callback(self._on_config_reload)
        
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
    
    def _load_deployments_from_config(self, config: OperatorConfig):
        """Load deployments from configuration"""
        self.watched_deployments.clear()
        
        for dep_config in config.deployments:
            key = f"{dep_config.namespace}/{dep_config.deployment}"
            self.watched_deployments[key] = {
                'namespace': dep_config.namespace,
                'deployment': dep_config.deployment,
                'hpa_name': dep_config.hpa_name,
                'startup_filter_minutes': dep_config.startup_filter_minutes,
                'priority': dep_config.priority
            }
            
            # Set priority in priority manager
            self.priority_manager.set_priority(dep_config.deployment, dep_config.priority)
            
            logger.info(f"Loaded deployment: {key} (priority: {dep_config.priority})")
    
    def _on_config_reload(self, new_config: OperatorConfig):
        """Callback when configuration is reloaded"""
        with self.reload_lock:
            logger.info("🔄 Hot reload triggered - applying new configuration...")
            
            try:
                # Update configuration
                old_config = self.config
                self.config = new_config
                
                # Log changes
                changes = []
                
                if old_config.check_interval != new_config.check_interval:
                    changes.append(f"check_interval: {old_config.check_interval}s → {new_config.check_interval}s")
                
                if old_config.target_node_utilization != new_config.target_node_utilization:
                    changes.append(f"target_node_utilization: {old_config.target_node_utilization}% → {new_config.target_node_utilization}%")
                
                if old_config.enable_predictive != new_config.enable_predictive:
                    changes.append(f"enable_predictive: {old_config.enable_predictive} → {new_config.enable_predictive}")
                
                if old_config.enable_autotuning != new_config.enable_autotuning:
                    changes.append(f"enable_autotuning: {old_config.enable_autotuning} → {new_config.enable_autotuning}")
                
                if old_config.dry_run != new_config.dry_run:
                    changes.append(f"dry_run: {old_config.dry_run} → {new_config.dry_run}")
                    self.controller.dry_run = new_config.dry_run
                
                # Check deployment changes
                old_deps = set(f"{d.namespace}/{d.deployment}" for d in old_config.deployments)
                new_deps = set(f"{d.namespace}/{d.deployment}" for d in new_config.deployments)
                
                added = new_deps - old_deps
                removed = old_deps - new_deps
                
                if added:
                    changes.append(f"deployments added: {', '.join(added)}")
                if removed:
                    changes.append(f"deployments removed: {', '.join(removed)}")
                
                # Reload deployments
                self._load_deployments_from_config(new_config)
                
                # Update rate limiters
                if (old_config.prometheus_rate_limit != new_config.prometheus_rate_limit or
                    old_config.k8s_api_rate_limit != new_config.k8s_api_rate_limit):
                    changes.append(f"rate_limits: Prometheus={new_config.prometheus_rate_limit}/s, K8s={new_config.k8s_api_rate_limit}/s")
                    try:
                        self.controller.analyzer.prometheus_rate_limiter.max_calls = int(new_config.prometheus_rate_limit)
                        self.controller.analyzer.k8s_rate_limiter.max_calls = int(new_config.k8s_api_rate_limit)
                    except Exception as e:
                        logger.warning(f"Failed to update rate limiters dynamically: {e}")
                
                if changes:
                    logger.info("Configuration changes applied:")
                    for change in changes:
                        logger.info(f"  • {change}")
                else:
                    logger.info("No configuration changes detected")
                
                # Send alert
                self.alert_manager.send_alert(
                    title="Configuration Reloaded",
                    message=f"Applied {len(changes)} configuration changes",
                    severity="info",
                    fields={
                        "Changes": "\n".join(changes) if changes else "None",
                        "Deployments": str(len(self.watched_deployments)),
                        "Version": str(self.config_loader.get_config_version())
                    }
                )
                
                logger.info(f"✅ Hot reload completed successfully (version {self.config_loader.get_config_version()})")
            
            except Exception as e:
                logger.error(f"❌ Hot reload failed: {e}", exc_info=True)
                # Revert to old config on error
                self.config = old_config
                self._load_deployments_from_config(old_config)
    
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
        
        # Stop ConfigMap watcher
        if self.config_loader:
            self.config_loader.stop_watching_configmap()
        
        # Stop memory monitoring
        if hasattr(self, 'memory_monitor') and self.memory_monitor:
            self.memory_monitor.stop_monitoring()
        
        # Close database connection
        if hasattr(self, 'db') and self.db:
            self.db.close()
        
        logger.info("Cleanup complete, shutting down")
    
    def add_deployment(self, namespace: str, deployment: str, hpa_name: str = None, startup_filter_minutes: int = 2, priority: str = "medium"):
        """Add deployment to watch"""
        key = f"{namespace}/{deployment}"
        self.watched_deployments[key] = {
            'namespace': namespace,
            'deployment': deployment,
            'hpa_name': hpa_name or deployment,
            'startup_filter_minutes': startup_filter_minutes,
            'priority': priority
        }
        
        # Set priority in priority manager
        self.priority_manager.set_priority(deployment, priority)
        
        logger.info(f"Watching: {key} with intelligence enabled (priority: {priority})")
    
    async def process_deployment(self, config: Dict):
        """Process single deployment"""
        namespace = config['namespace']
        deployment = config['deployment']
        hpa_name = config['hpa_name']
        key = f"{namespace}/{deployment}"
        
        # Check if should skip due to degraded mode
        if self.degraded_mode.should_skip_processing(deployment):
            logger.warning(f"Skipping {deployment} - degraded mode active, no cached data available")
            return
        
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
            decision = self.controller.calculate_hpa_target(
                namespace,
                deployment,
                hpa_name,
                config['startup_filter_minutes'],
                self.config.target_node_utilization
            )

            used_degraded_fallback = False
            cached = None

            if not decision:
                cached = self.degraded_mode.get_cached_metrics(deployment)
                if not cached:
                    safe = self.degraded_mode.get_safe_defaults(deployment)
                    cached = self.degraded_mode.get_cached_metrics(deployment)
                    if not cached:
                        class _TmpCached:
                            def __init__(self, data):
                                self.node_utilization = data['node_utilization']
                                self.pod_count = data['pod_count']
                                self.pod_cpu_usage = data['pod_cpu_usage']
                                self.hpa_target = data['hpa_target']
                                self.timestamp = datetime.now()
                                self.ttl_seconds = 0
                            def age_seconds(self):
                                return 0.0
                        cached = _TmpCached(safe)

                current_target = int(round(cached.hpa_target))
                recommended_target = current_target
                action = "maintain"
                reason = "Degraded mode - fallback decision"

                if cached.node_utilization > 85:
                    recommended_target = max(10, current_target - 5)
                    action = "decrease"
                    reason = "Degraded mode - high utilization"
                elif cached.node_utilization < 40:
                    recommended_target = min(95, current_target + 5)
                    action = "increase"
                    reason = "Degraded mode - low utilization"

                decision = HPADecision(
                    current_target=current_target,
                    recommended_target=int(recommended_target),
                    reason=reason,
                    node_pressure="unknown",
                    action=action,
                    confidence=0.6,
                    scheduling_spike_detected=False
                )
                used_degraded_fallback = True
            
            if used_degraded_fallback:
                try:
                    self.prometheus_exporter.update_deployment_metrics(
                        deployment=deployment,
                        namespace=namespace,
                        node_utilization=float(cached.node_utilization),
                        hpa_target=int(decision.recommended_target),
                        pod_count=int(cached.pod_count),
                        confidence=float(decision.confidence),
                        schedulable=0.0,
                        node_selector=""
                    )
                except Exception as e:
                    logger.debug(f"Failed to update Prometheus metrics (degraded): {e}")

                try:
                    self.prometheus_exporter.cached_metrics_age_seconds.labels(
                        deployment=deployment
                    ).set(float(cached.age_seconds()))
                except Exception as e:
                    logger.debug(f"Failed to update cached metrics age: {e}")

                self.controller.apply_hpa_target(namespace, hpa_name, decision)
                return
            
            self.degraded_mode.record_service_success('prometheus')
            
            # Store metrics
            node_selector = self.controller.analyzer.get_deployment_node_selector(namespace, deployment)
            node_metrics = self.controller.analyzer.get_node_metrics(node_selector)
            cpu_request = self.controller.analyzer.get_deployment_cpu_request(namespace, deployment)
            memory_request = self.controller.analyzer.get_deployment_memory_request(namespace, deployment)
            
            # Detect workload pattern (every hour)
            pattern, strategy = self.pattern_detector.get_pattern_and_strategy(deployment, hours=24)
            logger.info(
                f"{deployment} - Workload pattern: {pattern.value} "
                f"(strategy: {strategy.description})"
            )
            
            # Export pattern metrics
            try:
                self.prometheus_exporter.update_pattern_metrics(
                    deployment=deployment,
                    namespace=namespace,
                    pattern=pattern.value,
                    confidence=1.0
                )
            except Exception as e:
                logger.debug(f"Failed to update pattern metrics: {e}")
            
            min_target = 50 if cpu_request >= 100 else 60
            max_target = 90 if cpu_request < 100 else 85

            # Apply pattern-based adjustments to target
            if pattern != WorkloadPattern.UNKNOWN:
                # Use pattern-specific HPA target if significantly different
                if abs(self.config.target_node_utilization - strategy.hpa_target) > 5:
                    logger.info(
                        f"{deployment} - Applying pattern-based target: "
                        f"{self.config.target_node_utilization}% → {strategy.hpa_target}%"
                    )
                    # Override target for this deployment
                    pattern_target = strategy.hpa_target
                else:
                    pattern_target = self.config.target_node_utilization
            else:
                pattern_target = self.config.target_node_utilization

            pattern_target_int = int(round(pattern_target))
            pattern_target_int = max(min_target, min(max_target, pattern_target_int))
            if abs(pattern_target_int - int(decision.recommended_target)) >= 5:
                decision.recommended_target = pattern_target_int
                if decision.recommended_target < decision.current_target:
                    decision.action = "decrease"
                elif decision.recommended_target > decision.current_target:
                    decision.action = "increase"
                else:
                    decision.action = "maintain"
                decision.reason += " + Pattern strategy"
            
            # Apply priority-based adjustments
            # Calculate cluster pressure (average node utilization across all deployments)
            cluster_utilizations = []
            for watched_config in self.watched_deployments.values():
                try:
                    watched_selector = self.controller.analyzer.get_deployment_node_selector(
                        watched_config['namespace'], watched_config['deployment']
                    )
                    watched_metrics = self.controller.analyzer.get_node_metrics(watched_selector)
                    cluster_utilizations.append(watched_metrics.utilization_percent)
                except:
                    pass
            
            cluster_pressure = sum(cluster_utilizations) / len(cluster_utilizations) if cluster_utilizations else node_metrics.utilization_percent
            
            # Get priority-adjusted target
            priority_adjusted_target = self.priority_manager.calculate_target_adjustment(
                deployment=deployment,
                base_target=decision.recommended_target,
                node_pressure=node_metrics.utilization_percent,
                cluster_pressure=cluster_pressure
            )
            
            if abs(priority_adjusted_target - decision.recommended_target) >= 3:
                priority_config = self.priority_manager.get_config(deployment)
                logger.info(
                    f"{deployment} - Priority adjustment: {decision.recommended_target}% → {priority_adjusted_target}% "
                    f"(priority: {priority_config.level.value}, cluster pressure: {cluster_pressure:.1f}%)"
                )
                decision.recommended_target = priority_adjusted_target
                decision.reason += f" + Priority ({priority_config.level.value})"
            
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
            
            # Cache metrics for degraded mode
            self.degraded_mode.cache_metrics(deployment, {
                'node_utilization': node_metrics.utilization_percent,
                'pod_count': current_replicas,
                'pod_cpu_usage': avg_cpu_per_pod,
                'hpa_target': decision.current_target
            })
            
            # Anomaly detection
            anomalies = self.anomaly_detector.detect_anomalies(deployment, snapshot)
            if anomalies:
                logger.warning(f"{deployment} - {len(anomalies)} anomalies detected")
            
            # Predictive scaling with validation
            if self.config.enable_predictive:
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
                            decision.recommended_target = int(decision.recommended_target) - 5
                            decision.reason += " + Predictive pre-scaling"
                            logger.info(f"{deployment} - Applying predictive scale-up")
                        elif prediction.recommended_action == "scale_down":
                            decision.recommended_target = int(decision.recommended_target) + 5
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
            if self.config.enable_autotuning:
                optimal = self.auto_tuner.find_optimal_target(deployment)
                if optimal:
                    optimal_target, confidence = optimal
                    if confidence > 0.8 and abs(optimal_target - decision.recommended_target) > 5:
                        logger.info(f"{deployment} - Auto-tuned target: {optimal_target}% (confidence: {confidence:.0%})")
                        decision.recommended_target = int(optimal_target)
                        decision.reason += " + Auto-tuned"
                    
                    # Export learning rate metrics
                    try:
                        stats = self.auto_tuner.get_learning_stats(deployment)
                        self.prometheus_exporter.update_learning_metrics(
                            deployment=deployment,
                            namespace=namespace,
                            learning_rate=stats['learning_rate'],
                            variance=stats['avg_variance']
                        )
                    except Exception as e:
                        logger.debug(f"Failed to update learning metrics: {e}")
            
            decision.recommended_target = int(decision.recommended_target)
            decision.recommended_target = max(min_target, min(max_target, decision.recommended_target))

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
            
            # Record service failure for degraded mode
            if "prometheus" in str(e).lower() or "connection" in str(e).lower():
                self.degraded_mode.record_service_failure('prometheus')
                logger.warning(f"Prometheus failure detected for {deployment}")
            elif "kubernetes" in str(e).lower() or "api" in str(e).lower():
                self.degraded_mode.record_service_failure('kubernetes')
                logger.warning(f"Kubernetes API failure detected for {deployment}")
            
            # Try to use cached metrics if available
            cached = self.degraded_mode.get_cached_metrics(deployment)
            if cached:
                logger.info(
                    f"{deployment} - Using cached metrics (age: {cached.age_seconds():.0f}s) "
                    f"due to service failure"
                )
                # Could implement fallback logic here to use cached values
                # For now, just log and skip this iteration
            else:
                logger.warning(f"{deployment} - No cached metrics available, skipping iteration")
    
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
            f"Anomaly Detection ✓, Cost Optimization ✓, Auto-Tuning ✓, Hot Reload ✓\n"
            f"   Alert Channels: {', '.join(self.alert_manager.webhooks.keys())}\n"
            f"   Target Node Utilization: {self.config.target_node_utilization}%\n"
            f"   Check Interval: {self.config.check_interval}s"
        )
        
        # Start ConfigMap watcher for hot reload
        if self.config_loader:
            self.config_loader.start_watching()
        
        # Startup notification
        self.alert_manager.send_alert(
            title="Smart Autoscaler Started",
            message=f"Watching {len(self.watched_deployments)} deployments with hot reload enabled",
            severity="info",
            fields={
                "Deployments": str(len(self.watched_deployments)),
                "Features": "Predictive, Auto-tuning, Anomaly Detection, Cost Optimization, Hot Reload",
                "Config Version": str(self.config_loader.get_config_version()) if self.config_loader else "N/A"
            }
        )
        
        iteration = 0
        
        while not self.shutdown_event.is_set():
            try:
                iteration += 1
                logger.info(f"\n{'='*80}")
                logger.info(f"Iteration {iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'='*80}")
                
                # Update degraded mode metrics
                try:
                    degraded_status = self.degraded_mode.get_status_summary()
                    service_health = {
                        service: info['status']
                        for service, info in degraded_status['services'].items()
                    }
                    self.prometheus_exporter.update_degraded_mode_metrics(
                        is_degraded=degraded_status['is_degraded'],
                        service_health=service_health
                    )
                except Exception as e:
                    logger.debug(f"Failed to update degraded mode metrics: {e}")
                
                # Process each watched deployment (sorted by priority)
                deployment_list = [
                    {'deployment': config['deployment'], **config}
                    for config in self.watched_deployments.values()
                ]
                sorted_deployments = self.priority_manager.sort_deployments_by_priority(deployment_list)
                
                for deployment_info in sorted_deployments:
                    if self.shutdown_event.is_set():
                        break
                    
                    # Reconstruct config dict
                    config = {
                        'namespace': deployment_info['namespace'],
                        'deployment': deployment_info['deployment'],
                        'hpa_name': deployment_info['hpa_name'],
                        'startup_filter_minutes': deployment_info['startup_filter_minutes'],
                        'priority': deployment_info.get('priority', 'medium')
                    }
                    
                    await self.process_deployment(config)
                    await asyncio.sleep(2)  # Small delay between deployments
                
                # Weekly reports
                if not self.shutdown_event.is_set():
                    await self.weekly_report()
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
            
            if not self.shutdown_event.is_set():
                logger.info(f"Sleeping for {self.config.check_interval}s")
                # Check shutdown event with timeout
                if self.shutdown_event.wait(timeout=self.config.check_interval):
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
    
    # Initialize config loader
    namespace = os.getenv('OPERATOR_NAMESPACE', 'autoscaler-system')
    configmap_name = os.getenv('CONFIGMAP_NAME', 'smart-autoscaler-config')
    
    config_loader = ConfigLoader(namespace=namespace, configmap_name=configmap_name)
    
    # Load initial configuration
    try:
        config = config_loader.load_config()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}", exc_info=True)
        sys.exit(1)
    
    if not config.deployments:
        logger.error("No deployments configured! Set DEPLOYMENT_0_NAMESPACE and DEPLOYMENT_0_NAME")
        sys.exit(1)
    
    logger.info(f"Configured to watch {len(config.deployments)} deployment(s)")
    
    # Database path
    db_path = os.getenv("DB_PATH", "/data/autoscaler.db")
    try:
        db_path = ConfigValidator.validate_db_path(db_path)
    except ValueError as e:
        logger.error(f"Invalid DB_PATH: {e}")
        sys.exit(1)
    
    try:
        # Initialize operator with hot reload support
        operator = EnhancedSmartAutoscaler(
            config=config,
            db_path=db_path,
            config_loader=config_loader
        )
        
        logger.info(f"🔥 Hot reload enabled - watching ConfigMap {namespace}/{configmap_name}")
        
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
