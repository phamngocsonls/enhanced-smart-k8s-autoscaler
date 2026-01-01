"""
Web Dashboard UI
Real-time monitoring and control interface
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List
import logging

try:
    from src.health_checker import HealthChecker
except ImportError:
    # Fallback if health_checker not available
    HealthChecker = None

try:
    from src.cache import get_cache, QueryCache
except ImportError:
    # Fallback if cache not available
    get_cache = None
    QueryCache = None

logger = logging.getLogger(__name__)


class WebDashboard:
    """Web-based dashboard for monitoring and control"""
    
    def __init__(self, db, operator, port: int = 5000):
        self.db = db
        self.operator = operator
        self.port = port
        # Configure Flask to find templates directory
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
        self.app = Flask(__name__, template_folder=template_dir)
        CORS(self.app)
        
        # Initialize cache
        self.cache = get_cache() if get_cache else None
        
        # Initialize health checker if available
        if HealthChecker:
            self.health_checker = HealthChecker(operator)
        else:
            self.health_checker = None
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            """Main dashboard page"""
            return render_template('dashboard.html')
        
        @self.app.route('/api/cache/stats')
        def cache_stats():
            """Get cache statistics"""
            if self.cache:
                return jsonify(self.cache.stats)
            return jsonify({'error': 'Cache not available'}), 404
        
        @self.app.route('/api/deployments')
        def get_deployments():
            """Get list of watched deployments"""
            deployments = []
            for key, config in self.operator.watched_deployments.items():
                deployments.append({
                    'key': key,
                    'namespace': config['namespace'],
                    'deployment': config['deployment'],
                    'hpa_name': config['hpa_name']
                })
            return jsonify(deployments)
        
        @self.app.route('/api/deployment/<namespace>/<deployment>/current')
        def get_deployment_current(namespace, deployment):
            """Get current state of deployment"""
            try:
                # Get latest metrics
                recent = self.db.get_recent_metrics(deployment, hours=1)
                if not recent:
                    return jsonify({'error': 'No data'}), 404
                
                latest = recent[0]
                
                # Get pattern if available
                pattern = 'unknown'
                try:
                    if hasattr(self.operator, 'pattern_detector'):
                        pattern_result = self.operator.pattern_detector.detect_pattern(deployment)
                        if pattern_result:
                            pattern = pattern_result.pattern.value
                except:
                    pass
                
                return jsonify({
                    'timestamp': latest.timestamp.isoformat(),
                    'node_utilization': latest.node_utilization,
                    'pod_count': latest.pod_count,
                    'pod_cpu_usage': latest.pod_cpu_usage,
                    'memory_usage': latest.memory_usage if hasattr(latest, 'memory_usage') else 0,
                    'hpa_target': latest.hpa_target,
                    'confidence': latest.confidence,
                    'action_taken': latest.action_taken,
                    'cpu_request': latest.cpu_request,
                    'memory_request': latest.memory_request if hasattr(latest, 'memory_request') else 0,
                    'pattern': pattern,
                    'priority': self.operator.watched_deployments.get(f"{namespace}/{deployment}", {}).get('priority', 'medium')
                })
            except Exception as e:
                logger.error(f"Error getting current state: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/deployment/<namespace>/<deployment>/history')
        def get_deployment_history(namespace, deployment):
            """Get historical data for deployment"""
            hours = request.args.get('hours', 24, type=int)
            
            try:
                metrics = self.db.get_recent_metrics(deployment, hours=hours)
                
                data = {
                    'timestamps': [m.timestamp.isoformat() for m in metrics],
                    'node_utilization': [m.node_utilization for m in metrics],
                    'pod_cpu_usage': [(m.pod_cpu_usage or 0) * 100 for m in metrics],  # Convert to percentage
                    'pod_count': [m.pod_count for m in metrics],
                    'hpa_target': [m.hpa_target for m in metrics],
                    'confidence': [m.confidence for m in metrics]
                }
                
                return jsonify(data)
            except Exception as e:
                logger.error(f"Error getting history: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/deployment/<namespace>/<deployment>/predictions')
        def get_predictions(namespace, deployment):
            """Get predictions with validation"""
            try:
                cursor = self.db.conn.execute("""
                    SELECT timestamp, predicted_cpu, confidence, recommended_action, reasoning,
                           actual_cpu, validated, accuracy
                    FROM predictions
                    WHERE deployment = ?
                    ORDER BY timestamp DESC
                    LIMIT 100
                """, (deployment,))
                
                predictions = []
                for row in cursor.fetchall():
                    pred = {
                        'timestamp': row[0],
                        'predicted_cpu': row[1],
                        'confidence': row[2],
                        'action': row[3],
                        'reasoning': row[4],
                        'validated': bool(row[6]) if len(row) > 6 else False
                    }
                    
                    # Add validation data if available
                    if len(row) > 5 and row[5] is not None:
                        pred['actual_cpu'] = row[5]
                        pred['accuracy'] = row[7] if len(row) > 7 else None
                        pred['error'] = abs(row[1] - row[5]) if row[5] else None
                    
                    predictions.append(pred)
                
                # Get accuracy statistics
                accuracy_stats = self.db.get_prediction_accuracy(deployment)
                
                return jsonify({
                    'predictions': predictions,
                    'accuracy_stats': accuracy_stats
                })
            except Exception as e:
                logger.error(f"Error getting predictions: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/deployment/<namespace>/<deployment>/anomalies')
        def get_anomalies(namespace, deployment):
            """Get anomalies for deployment"""
            try:
                cursor = self.db.conn.execute("""
                    SELECT timestamp, anomaly_type, severity, description,
                           current_value, expected_value, deviation_percent
                    FROM anomalies
                    WHERE deployment = ?
                    ORDER BY timestamp DESC
                    LIMIT 50
                """, (deployment,))
                
                anomalies = []
                for row in cursor.fetchall():
                    anomalies.append({
                        'timestamp': row[0],
                        'type': row[1],
                        'severity': row[2],
                        'description': row[3],
                        'current': row[4],
                        'expected': row[5],
                        'deviation': row[6]
                    })
                
                return jsonify(anomalies)
            except Exception as e:
                logger.error(f"Error getting anomalies: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/deployment/<namespace>/<deployment>/cost')
        def get_cost_metrics(namespace, deployment):
            """Get detailed cost metrics for deployment"""
            try:
                hours = request.args.get('hours', 24, type=int)
                cost_metrics = self.operator.cost_optimizer.analyze_costs(deployment, hours=hours)
                if not cost_metrics:
                    return jsonify({'error': 'No cost data available. Need at least 10 data points.'}), 404
                
                return jsonify({
                    'deployment': cost_metrics.deployment,
                    'avg_pod_count': round(cost_metrics.avg_pod_count, 2),
                    'avg_utilization': round(cost_metrics.avg_utilization, 2),
                    'runtime_hours': round(cost_metrics.runtime_hours, 2),
                    
                    # Cost breakdown
                    'cpu_cost': round(cost_metrics.cpu_cost, 2),
                    'memory_cost': round(cost_metrics.memory_cost, 2),
                    'total_cost': round(cost_metrics.total_cost, 2),
                    
                    # Wasted cost
                    'wasted_cpu_cost': round(cost_metrics.wasted_cpu_cost, 2),
                    'wasted_memory_cost': round(cost_metrics.wasted_memory_cost, 2),
                    'total_wasted_cost': round(cost_metrics.total_wasted_cost, 2),
                    
                    # Utilization
                    'cpu_utilization_percent': round(cost_metrics.cpu_utilization_percent, 2),
                    'memory_utilization_percent': round(cost_metrics.memory_utilization_percent, 2),
                    'wasted_capacity_percent': round(cost_metrics.wasted_capacity_percent, 2),
                    
                    # Monthly projections
                    'estimated_monthly_cost': round(cost_metrics.estimated_monthly_cost, 2),
                    'optimization_potential': round(cost_metrics.optimization_potential, 2),
                    'recommendation': cost_metrics.recommendation
                })
            except Exception as e:
                logger.error(f"Error getting cost metrics: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/deployment/<namespace>/<deployment>/recommendations')
        def get_resource_recommendations(namespace, deployment):
            """
            Get FinOps resource optimization recommendations.
            
            This endpoint provides intelligent recommendations for right-sizing
            CPU and memory requests while automatically calculating the adjusted
            HPA targets needed to maintain the same scaling behavior.
            
            Query params:
                hours: Analysis period in hours (default: 168 = 1 week)
            """
            try:
                hours = request.args.get('hours', 168, type=int)
                recommendations = self.operator.cost_optimizer.calculate_resource_recommendations(
                    deployment, 
                    hours=hours
                )
                
                if not recommendations:
                    return jsonify({
                        'error': 'Insufficient data for recommendations. Need at least 100 data points.',
                        'suggestion': 'Wait for more historical data to accumulate (typically 2-3 hours).'
                    }), 404
                
                return jsonify(recommendations)
            except Exception as e:
                logger.error(f"Error getting recommendations: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/deployment/<namespace>/<deployment>/optimal')
        def get_optimal_target(namespace, deployment):
            """Get learned optimal target"""
            try:
                optimal = self.db.get_optimal_target(deployment)
                
                if not optimal:
                    return jsonify({'optimal_target': None})
                
                cursor = self.db.conn.execute("""
                    SELECT optimal_target, confidence, samples_count, last_updated
                    FROM optimal_targets
                    WHERE deployment = ?
                """, (deployment,))
                
                row = cursor.fetchone()
                if row:
                    return jsonify({
                        'optimal_target': row[0],
                        'confidence': row[1],
                        'samples': row[2],
                        'last_updated': row[3]
                    })
                
                return jsonify({'optimal_target': None})
            except Exception as e:
                logger.error(f"Error getting optimal target: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/overview')
        def get_overview():
            """Get cluster overview"""
            try:
                total_deployments = len(self.operator.watched_deployments)
                
                # Get total costs
                total_cost = 0
                total_savings = 0
                
                for config in self.operator.watched_deployments.values():
                    cost_metrics = self.operator.cost_optimizer.analyze_costs(
                        config['deployment']
                    )
                    if cost_metrics:
                        total_cost += cost_metrics.estimated_monthly_cost
                        total_savings += cost_metrics.optimization_potential
                
                # Get recent anomalies count
                cursor = self.db.conn.execute("""
                    SELECT COUNT(*) FROM anomalies
                    WHERE timestamp >= datetime('now', '-24 hours')
                """)
                row = cursor.fetchone()
                recent_anomalies = row[0] if row else 0
                
                # Get predictions accuracy
                cursor = self.db.conn.execute("""
                    SELECT AVG(confidence) FROM predictions
                    WHERE timestamp >= datetime('now', '-7 days')
                """)
                row = cursor.fetchone()
                avg_prediction_confidence = row[0] if row and row[0] is not None else 0
                
                return jsonify({
                    'total_deployments': total_deployments,
                    'total_monthly_cost': round(total_cost, 2),
                    'total_savings_potential': round(total_savings, 2),
                    'recent_anomalies_24h': recent_anomalies,
                    'avg_prediction_confidence': round(avg_prediction_confidence, 3),
                    'efficiency_score': round((1 - total_savings / total_cost) * 100, 1) if total_cost > 0 else 0
                })
            except Exception as e:
                logger.error(f"Error getting overview: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/config/status')
        def get_config_status():
            """Get configuration status and hot reload info"""
            try:
                config_loader = self.operator.config_loader
                
                if not config_loader:
                    return jsonify({
                        'hot_reload_enabled': False,
                        'message': 'Hot reload not configured'
                    })
                
                config = config_loader.get_config()
                
                return jsonify({
                    'hot_reload_enabled': True,
                    'config_version': config_loader.get_config_version(),
                    'last_reload': config_loader.get_last_reload_time().isoformat(),
                    'namespace': config_loader.namespace,
                    'configmap_name': config_loader.configmap_name,
                    'current_config': {
                        'check_interval': config.check_interval,
                        'target_node_utilization': config.target_node_utilization,
                        'dry_run': config.dry_run,
                        'enable_predictive': config.enable_predictive,
                        'enable_autotuning': config.enable_autotuning,
                        'deployments_count': len(config.deployments),
                        'prometheus_rate_limit': config.prometheus_rate_limit,
                        'k8s_api_rate_limit': config.k8s_api_rate_limit
                    }
                })
            except Exception as e:
                logger.error(f"Error getting config status: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/config/reload', methods=['POST'])
        def trigger_reload():
            """Manually trigger configuration reload"""
            try:
                config_loader = self.operator.config_loader
                
                if not config_loader:
                    return jsonify({
                        'success': False,
                        'message': 'Hot reload not configured'
                    }), 400
                
                logger.info("Manual configuration reload triggered via API")
                
                # Reload configuration
                new_config = config_loader.load_config()
                
                # Trigger reload callback
                if hasattr(self.operator, '_on_config_reload'):
                    self.operator._on_config_reload(new_config)
                
                return jsonify({
                    'success': True,
                    'message': 'Configuration reloaded successfully',
                    'config_version': config_loader.get_config_version(),
                    'deployments_count': len(new_config.deployments)
                })
            except Exception as e:
                logger.error(f"Error reloading config: {e}", exc_info=True)
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        @self.app.route('/api/health')
        def health_check():
            """Comprehensive health check endpoint"""
            try:
                if self.health_checker:
                    health_results = self.health_checker.check_all()
                    
                    # Transform to flat structure for dashboard
                    components = health_results.get('components', {})
                    flat_health = {
                        'prometheus': components.get('prometheus', {}).get('status', 'unknown'),
                        'kubernetes': components.get('kubernetes', {}).get('status', 'unknown'),
                        'database': components.get('database', {}).get('status', 'unknown'),
                        'degraded': health_results.get('overall_status') == 'degraded',
                        'overall_status': health_results.get('overall_status', 'unknown'),
                        'components': components,  # Keep full details too
                        'timestamp': health_results.get('timestamp')
                    }
                    
                    # Determine HTTP status code
                    if health_results['overall_status'] == 'healthy':
                        status_code = 200
                    elif health_results['overall_status'] == 'degraded':
                        status_code = 200
                    else:
                        status_code = 503
                    
                    return jsonify(flat_health), status_code
                else:
                    # No health checker available
                    return jsonify({
                        'prometheus': 'unknown',
                        'kubernetes': 'unknown', 
                        'database': 'unknown',
                        'degraded': False,
                        'overall_status': 'unknown'
                    }), 200
            except Exception as e:
                logger.error(f"Health check error: {e}", exc_info=True)
                return jsonify({
                    'prometheus': 'unknown',
                    'kubernetes': 'unknown',
                    'database': 'unknown',
                    'degraded': False,
                    'error': str(e)
                }), 503
        
        @self.app.route('/health')
        @self.app.route('/healthz')
        def simple_health():
            """Simple health check for K8s probes - fast, no external calls"""
            return jsonify({
                'status': 'ok',
                'timestamp': datetime.now().isoformat()
            }), 200
        
        @self.app.route('/api/ai/insights/<deployment>')
        def get_ai_insights(deployment):
            """Get AI insights - patterns, learning progress, predictions accuracy"""
            try:
                insights = {
                    'deployment': deployment,
                    'patterns': None,
                    'auto_tuning': None,
                    'prediction_accuracy': None,
                    'scaling_events': [],
                    'efficiency': None
                }
                
                # Get pattern recognition data
                if hasattr(self.operator, 'pattern_recognizer'):
                    try:
                        patterns = self.operator.pattern_recognizer.get_patterns(deployment)
                        if patterns:
                            insights['patterns'] = {
                                'hourly': patterns.get('hourly_pattern', []),
                                'daily': patterns.get('daily_pattern', []),
                                'peak_hours': patterns.get('peak_hours', []),
                                'low_hours': patterns.get('low_hours', [])
                            }
                    except:
                        pass
                
                # Get auto-tuning progress
                if hasattr(self.operator, 'auto_tuner'):
                    try:
                        tuner = self.operator.auto_tuner
                        insights['auto_tuning'] = {
                            'learning_rate': getattr(tuner, 'learning_rate', 0.1),
                            'samples_collected': getattr(tuner, 'samples_count', 0),
                            'current_optimal': self.db.get_optimal_target(deployment),
                            'tuning_enabled': True
                        }
                    except:
                        pass
                
                # Get prediction accuracy stats
                try:
                    accuracy = self.db.get_prediction_accuracy(deployment)
                    if accuracy:
                        insights['prediction_accuracy'] = accuracy
                except:
                    pass
                
                # Get recent scaling events
                try:
                    cursor = self.db.conn.execute("""
                        SELECT timestamp, action_taken, hpa_target, confidence, pod_count
                        FROM metrics_history
                        WHERE deployment = ? AND action_taken != 'maintain'
                        ORDER BY timestamp DESC
                        LIMIT 20
                    """, (deployment,))
                    
                    for row in cursor.fetchall():
                        insights['scaling_events'].append({
                            'timestamp': row[0],
                            'action': row[1],
                            'hpa_target': row[2],
                            'confidence': row[3],
                            'pod_count': row[4]
                        })
                except:
                    pass
                
                # Calculate efficiency
                try:
                    recent = self.db.get_recent_metrics(deployment, hours=24)
                    if recent and len(recent) > 10:
                        avg_cpu = sum(m.pod_cpu_usage or 0 for m in recent) / len(recent) * 100
                        avg_request = sum(m.cpu_request or 100 for m in recent) / len(recent)
                        efficiency = min(100, (avg_cpu / (avg_request / 1000 * 100)) * 100) if avg_request > 0 else 0
                        insights['efficiency'] = {
                            'cpu_efficiency': round(efficiency, 1),
                            'avg_cpu_usage': round(avg_cpu, 1),
                            'avg_cpu_request': round(avg_request, 0),
                            'data_points': len(recent)
                        }
                except:
                    pass
                
                return jsonify(insights)
            except Exception as e:
                logger.error(f"Error getting AI insights: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/scaling/timeline/<deployment>')
        def get_scaling_timeline(deployment):
            """Get scaling events timeline"""
            try:
                hours = request.args.get('hours', 24, type=int)
                
                cursor = self.db.conn.execute("""
                    SELECT timestamp, action_taken, hpa_target, pod_count, confidence, node_utilization, pod_cpu_usage
                    FROM metrics_history
                    WHERE deployment = ?
                    ORDER BY timestamp DESC
                    LIMIT 500
                """, (deployment,))
                
                events = []
                prev_pods = None
                prev_target = None
                
                for row in cursor.fetchall():
                    action = row[1]
                    pods = row[3]
                    target = row[2]
                    
                    # Detect actual scaling events
                    if prev_pods is not None and pods != prev_pods:
                        events.append({
                            'timestamp': row[0],
                            'type': 'scale_up' if pods > prev_pods else 'scale_down',
                            'from_pods': prev_pods,
                            'to_pods': pods,
                            'hpa_target': target,
                            'cpu_usage': round((row[6] or 0) * 100, 1),
                            'confidence': row[4]
                        })
                    
                    # Detect HPA target changes
                    if prev_target is not None and target != prev_target:
                        events.append({
                            'timestamp': row[0],
                            'type': 'target_change',
                            'from_target': prev_target,
                            'to_target': target,
                            'reason': action
                        })
                    
                    prev_pods = pods
                    prev_target = target
                
                return jsonify({
                    'deployment': deployment,
                    'events': events[:50],  # Last 50 events
                    'total_events': len(events)
                })
            except Exception as e:
                logger.error(f"Error getting scaling timeline: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/priorities/stats')
        def get_priority_stats():
            """Get priority statistics"""
            try:
                if hasattr(self.operator, 'priority_manager'):
                    stats = self.operator.priority_manager.get_priority_stats()
                    return jsonify(stats)
                else:
                    return jsonify({'error': 'Priority manager not available'}), 404
            except Exception as e:
                logger.error(f"Error getting priority stats: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cluster/metrics')
        def get_cluster_metrics():
            """Get comprehensive cluster metrics"""
            try:
                from src.operator import NodeCapacityAnalyzer
                
                # Get all unique namespaces
                namespaces = set()
                for config in self.operator.watched_deployments.values():
                    namespaces.add(config['namespace'])
                
                # Initialize analyzer
                analyzer = NodeCapacityAnalyzer(self.operator.config.prometheus_url)
                
                # Get all nodes metrics
                all_nodes = []
                total_cpu_capacity = 0
                total_cpu_allocatable = 0
                total_memory_capacity = 0
                total_memory_allocatable = 0
                
                try:
                    # Query all nodes
                    nodes_query = 'kube_node_info'
                    logger.info(f"[CLUSTER] Querying nodes with: {nodes_query}")
                    logger.info(f"[CLUSTER] Prometheus URL: {self.operator.config.prometheus_url}")
                    
                    result = analyzer._query_prometheus(nodes_query)
                    logger.info(f"[CLUSTER] Query result type: {type(result)}")
                    logger.info(f"[CLUSTER] Query result length: {len(result) if result else 0}")
                    
                    if result and isinstance(result, list) and len(result) > 0:
                        logger.info(f"[CLUSTER] Found {len(result)} nodes")
                        for node_info in result:
                            node_name = node_info['metric'].get('node', 'unknown')
                            logger.info(f"[CLUSTER] Processing node: {node_name}")
                            
                            # Get node capacity
                            cpu_capacity_query = f'kube_node_status_capacity{{node="{node_name}",resource="cpu"}}'
                            logger.debug(f"CPU capacity query: {cpu_capacity_query}")
                            cpu_capacity_result = analyzer._query_prometheus(cpu_capacity_query)
                            cpu_capacity = 0
                            if cpu_capacity_result and len(cpu_capacity_result) > 0:
                                cpu_capacity = float(cpu_capacity_result[0]['value'][1])
                                logger.info(f"Node {node_name}: CPU capacity = {cpu_capacity} cores")
                            else:
                                logger.warning(f"Node {node_name}: CPU capacity query returned empty result")
                            
                            # Get node allocatable
                            cpu_allocatable_query = f'kube_node_status_allocatable{{node="{node_name}",resource="cpu"}}'
                            cpu_allocatable_result = analyzer._query_prometheus(cpu_allocatable_query)
                            cpu_allocatable = 0
                            if cpu_allocatable_result and len(cpu_allocatable_result) > 0:
                                cpu_allocatable = float(cpu_allocatable_result[0]['value'][1])
                            
                            # Get memory capacity (in bytes)
                            mem_capacity_query = f'kube_node_status_capacity{{node="{node_name}",resource="memory"}}'
                            mem_capacity_result = analyzer._query_prometheus(mem_capacity_query)
                            mem_capacity = 0
                            if mem_capacity_result and len(mem_capacity_result) > 0:
                                mem_capacity = float(mem_capacity_result[0]['value'][1]) / (1024**3)  # Convert to GB
                            
                            # Get memory allocatable
                            mem_allocatable_query = f'kube_node_status_allocatable{{node="{node_name}",resource="memory"}}'
                            mem_allocatable_result = analyzer._query_prometheus(mem_allocatable_query)
                            mem_allocatable = 0
                            if mem_allocatable_result and len(mem_allocatable_result) > 0:
                                mem_allocatable = float(mem_allocatable_result[0]['value'][1]) / (1024**3)  # Convert to GB
                            
                            # Get CPU usage
                            cpu_usage_query = f'sum(rate(node_cpu_seconds_total{{mode!="idle",instance=~".*{node_name}.*"}}[5m]))'
                            cpu_usage_result = analyzer._query_prometheus(cpu_usage_query)
                            cpu_usage = 0
                            if cpu_usage_result and len(cpu_usage_result) > 0:
                                cpu_usage = float(cpu_usage_result[0]['value'][1])
                            
                            # Get memory usage
                            mem_usage_query = f'node_memory_MemTotal_bytes{{instance=~".*{node_name}.*"}} - node_memory_MemAvailable_bytes{{instance=~".*{node_name}.*"}}'
                            mem_usage_result = analyzer._query_prometheus(mem_usage_query)
                            mem_usage = 0
                            if mem_usage_result and len(mem_usage_result) > 0:
                                mem_usage = float(mem_usage_result[0]['value'][1]) / (1024**3)  # Convert to GB
                            
                            all_nodes.append({
                                'name': node_name,
                                'cpu_capacity': round(cpu_capacity, 2),
                                'cpu_allocatable': round(cpu_allocatable, 2),
                                'cpu_usage': round(cpu_usage, 2),
                                'memory_capacity_gb': round(mem_capacity, 2),
                                'memory_allocatable_gb': round(mem_allocatable, 2),
                                'memory_usage_gb': round(mem_usage, 2)
                            })
                            
                            total_cpu_capacity += cpu_capacity
                            total_cpu_allocatable += cpu_allocatable
                            total_memory_capacity += mem_capacity
                            total_memory_allocatable += mem_allocatable
                    else:
                        logger.error(f"[CLUSTER] No nodes found or invalid result. Result type: {type(result)}, Length: {len(result) if result else 0}")
                
                except Exception as e:
                    logger.error(f"[CLUSTER] Error querying node metrics: {e}", exc_info=True)
                
                # Get total CPU requests across all pods
                total_cpu_requests = 0
                total_memory_requests = 0
                total_cpu_usage = 0
                total_memory_usage = 0
                
                try:
                    # Total CPU requests
                    cpu_requests_query = 'sum(kube_pod_container_resource_requests{resource="cpu"})'
                    cpu_requests_result = analyzer._query_prometheus(cpu_requests_query)
                    if cpu_requests_result and len(cpu_requests_result) > 0:
                        total_cpu_requests = float(cpu_requests_result[0]['value'][1])
                    
                    # Total memory requests (convert to GB)
                    mem_requests_query = 'sum(kube_pod_container_resource_requests{resource="memory"})'
                    mem_requests_result = analyzer._query_prometheus(mem_requests_query)
                    if mem_requests_result and len(mem_requests_result) > 0:
                        total_memory_requests = float(mem_requests_result[0]['value'][1]) / (1024**3)
                    
                    # Total CPU usage
                    cpu_usage_query = 'sum(rate(container_cpu_usage_seconds_total{container!="",container!="POD"}[5m]))'
                    cpu_usage_result = analyzer._query_prometheus(cpu_usage_query)
                    if cpu_usage_result and len(cpu_usage_result) > 0:
                        total_cpu_usage = float(cpu_usage_result[0]['value'][1])
                    
                    # Total memory usage
                    mem_usage_query = 'sum(container_memory_working_set_bytes{container!="",container!="POD"})'
                    mem_usage_result = analyzer._query_prometheus(mem_usage_query)
                    if mem_usage_result and len(mem_usage_result) > 0:
                        total_memory_usage = float(mem_usage_result[0]['value'][1]) / (1024**3)
                
                except Exception as e:
                    logger.warning(f"Error querying resource metrics: {e}")
                
                return jsonify({
                    'nodes': all_nodes,
                    'node_count': len(all_nodes),
                    'summary': {
                        'cpu': {
                            'capacity': round(total_cpu_capacity, 2),
                            'allocatable': round(total_cpu_allocatable, 2),
                            'requests': round(total_cpu_requests, 2),
                            'usage': round(total_cpu_usage, 2),
                            'requests_percent': round((total_cpu_requests / total_cpu_allocatable * 100) if total_cpu_allocatable > 0 else 0, 1),
                            'usage_percent': round((total_cpu_usage / total_cpu_allocatable * 100) if total_cpu_allocatable > 0 else 0, 1)
                        },
                        'memory': {
                            'capacity_gb': round(total_memory_capacity, 2),
                            'allocatable_gb': round(total_memory_allocatable, 2),
                            'requests_gb': round(total_memory_requests, 2),
                            'usage_gb': round(total_memory_usage, 2),
                            'requests_percent': round((total_memory_requests / total_memory_allocatable * 100) if total_memory_allocatable > 0 else 0, 1),
                            'usage_percent': round((total_memory_usage / total_memory_allocatable * 100) if total_memory_allocatable > 0 else 0, 1)
                        }
                    },
                    'namespaces': sorted(list(namespaces))
                })
            
            except Exception as e:
                logger.error(f"Error getting cluster metrics: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cluster/history')
        def get_cluster_history():
            """Get historical cluster metrics"""
            try:
                hours = request.args.get('hours', 24, type=int)
                
                # Query historical data from database
                cursor = self.db.conn.execute("""
                    SELECT 
                        strftime('%Y-%m-%d %H:%M', timestamp) as time,
                        SUM(pod_count) as total_pods,
                        AVG(node_utilization) as avg_node_util,
                        SUM(cpu_request) as total_cpu_request,
                        SUM(pod_cpu_usage * 1000) as total_cpu_usage_millicores
                    FROM metrics_history
                    WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                    GROUP BY time
                    ORDER BY time ASC
                """, (hours,))
                
                history = []
                for row in cursor.fetchall():
                    history.append({
                        'timestamp': row[0],
                        'total_pods': row[1] or 0,
                        'avg_node_utilization': round(row[2] or 0, 1),
                        'total_cpu_request_millicores': round(row[3] or 0, 0),
                        'total_cpu_usage_millicores': round(row[4] or 0, 0)
                    })
                
                return jsonify({
                    'history': history,
                    'hours': hours
                })
            
            except Exception as e:
                logger.error(f"Error getting cluster history: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cost/trends/<deployment>')
        def get_cost_trends(deployment):
            """Get cost trends over time"""
            try:
                # Get hourly cost data
                cursor = self.db.conn.execute("""
                    SELECT 
                        strftime('%Y-%m-%d %H:00', timestamp) as hour,
                        AVG(pod_count) as avg_pods,
                        AVG(cpu_request) as avg_cpu_request,
                        AVG(pod_cpu_usage) as avg_cpu_usage
                    FROM metrics_history
                    WHERE deployment = ?
                    GROUP BY hour
                    ORDER BY hour DESC
                    LIMIT 168
                """, (deployment,))
                
                cost_per_vcpu = float(os.getenv('COST_PER_VCPU_HOUR', '0.04'))
                
                trends = []
                for row in cursor.fetchall():
                    pods = row[1] or 1
                    cpu_request = (row[2] or 100) / 1000  # Convert to cores
                    cpu_usage = row[3] or 0
                    
                    hourly_cost = pods * cpu_request * cost_per_vcpu
                    actual_cost = pods * cpu_usage * cost_per_vcpu
                    wasted = hourly_cost - actual_cost
                    
                    trends.append({
                        'hour': row[0],
                        'cost': round(hourly_cost, 3),
                        'actual_cost': round(actual_cost, 3),
                        'wasted': round(max(0, wasted), 3),
                        'pods': round(pods, 1)
                    })
                
                # Calculate totals
                total_cost = sum(t['cost'] for t in trends)
                total_wasted = sum(t['wasted'] for t in trends)
                
                return jsonify({
                    'deployment': deployment,
                    'trends': list(reversed(trends)),
                    'summary': {
                        'total_cost': round(total_cost, 2),
                        'total_wasted': round(total_wasted, 2),
                        'efficiency': round((1 - total_wasted / total_cost) * 100, 1) if total_cost > 0 else 100,
                        'hours_analyzed': len(trends)
                    }
                })
            except Exception as e:
                logger.error(f"Error getting cost trends: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
    
    def start(self):
        """Start dashboard server"""
        logger.info(f"Starting web dashboard on port {self.port}")
        self.app.run(host='0.0.0.0', port=self.port, threaded=True)