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
                
                return jsonify({
                    'timestamp': latest.timestamp.isoformat(),
                    'node_utilization': latest.node_utilization,
                    'pod_count': latest.pod_count,
                    'pod_cpu_usage': latest.pod_cpu_usage,
                    'hpa_target': latest.hpa_target,
                    'confidence': latest.confidence,
                    'action_taken': latest.action_taken,
                    'cpu_request': latest.cpu_request
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
    
    def start(self):
        """Start dashboard server"""
        logger.info(f"Starting web dashboard on port {self.port}")
        self.app.run(host='0.0.0.0', port=self.port, threaded=True)