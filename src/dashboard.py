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

try:
    from src.genai_analyzer import GenAIAnalyzer
except ImportError:
    GenAIAnalyzer = None

try:
    from src.cost_allocation import CostAllocator
except ImportError:
    CostAllocator = None

try:
    from src.reporting import ReportGenerator
except ImportError:
    ReportGenerator = None

try:
    from src.realtime_cost import RealtimeCostTracker
except ImportError:
    RealtimeCostTracker = None

try:
    from src.cost_alerting import CostAlerting
except ImportError:
    CostAlerting = None

try:
    from src.advanced_predictor import AdvancedPredictor, PredictiveScaler
except ImportError:
    AdvancedPredictor = None
    PredictiveScaler = None

try:
    from src.prescale_manager import PreScaleManager, PreScaleState
except ImportError:
    PreScaleManager = None
    PreScaleState = None

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

        # Initialize GenAI Analyzer
        self.enable_genai = os.getenv('ENABLE_GENAI', 'false').lower() == 'true'
        if GenAIAnalyzer and self.enable_genai:
            self.genai_analyzer = GenAIAnalyzer(db)
        else:
            self.genai_analyzer = None
        
        # Initialize Cost Allocator
        if CostAllocator:
            self.cost_allocator = CostAllocator(db, operator)
        else:
            self.cost_allocator = None
        
        # Initialize Report Generator
        if ReportGenerator and self.cost_allocator:
            self.report_generator = ReportGenerator(db, operator, self.cost_allocator)
        else:
            self.report_generator = None
        
        # Initialize Real-time Cost Tracker
        if RealtimeCostTracker and self.cost_allocator:
            self.realtime_cost = RealtimeCostTracker(
                operator,
                cost_per_vcpu_hour=self.cost_allocator.cost_per_vcpu_hour,
                cost_per_gb_memory_hour=self.cost_allocator.cost_per_gb_memory_hour
            )
        else:
            self.realtime_cost = None
        
        # Initialize Cost Alerting
        if CostAlerting and self.realtime_cost:
            self.cost_alerting = CostAlerting(self.realtime_cost, operator)
        else:
            self.cost_alerting = None
        
        # Initialize Advanced Predictor
        if AdvancedPredictor:
            self.advanced_predictor = AdvancedPredictor(db)
            self.predictive_scaler = PredictiveScaler(self.advanced_predictor) if PredictiveScaler else None
        else:
            self.advanced_predictor = None
            self.predictive_scaler = None
        
        # Reference to alert_manager from operator
        self.alert_manager = getattr(operator, 'alert_manager', None)
        
        self._setup_routes()
    
    def _reload_alert_manager_webhooks(self):
        """Reload alert manager webhooks from database + environment"""
        if not self.alert_manager:
            return
        
        import os
        webhooks = {}
        
        # Load from environment first
        if os.getenv('SLACK_WEBHOOK'):
            webhooks['slack'] = os.getenv('SLACK_WEBHOOK')
        if os.getenv('TEAMS_WEBHOOK'):
            webhooks['teams'] = os.getenv('TEAMS_WEBHOOK')
        if os.getenv('DISCORD_WEBHOOK'):
            webhooks['discord'] = os.getenv('DISCORD_WEBHOOK')
        if os.getenv('GENERIC_WEBHOOK'):
            webhooks['generic'] = os.getenv('GENERIC_WEBHOOK')
        
        # Load from database (enabled providers only)
        try:
            providers = self.db.get_notification_providers()
            for p in providers:
                if p.get('enabled'):
                    # Use provider name as key to allow multiple of same type
                    webhooks[p['name']] = p['webhook_url_full']
        except Exception as e:
            logger.warning(f"Failed to load notification providers from DB: {e}")
        
        # Update alert manager
        self.alert_manager.webhooks = webhooks
        logger.info(f"Reloaded alert manager webhooks: {list(webhooks.keys())}")
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.after_request
        def add_cache_headers(response):
            """Add headers to prevent browser caching of HTML"""
            if response.content_type and 'text/html' in response.content_type:
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
            return response
        
        @self.app.route('/')
        def index():
            """Main dashboard page"""
            return render_template('dashboard.html')
        
        @self.app.route('/api/debug')
        def debug_info():
            """Debug endpoint to check system status"""
            return jsonify({
                'cost_allocator_available': self.cost_allocator is not None,
                'report_generator_available': self.report_generator is not None,
                'health_checker_available': self.health_checker is not None,
                'genai_analyzer_available': self.genai_analyzer is not None,
                'cache_available': self.cache is not None,
                'watched_deployments': len(self.operator.watched_deployments),
                'deployment_list': list(self.operator.watched_deployments.keys()),
                'cost_allocator_class': str(CostAllocator),
                'report_generator_class': str(ReportGenerator),
            })
        
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
                # Import version
                try:
                    from src import __version__
                except ImportError:
                    __version__ = "0.0.18"
                
                config_loader = self.operator.config_loader
                
                if not config_loader:
                    return jsonify({
                        'hot_reload_enabled': False,
                        'message': 'Hot reload not configured',
                        'current_config': {
                            'version': __version__
                        }
                    })
                
                config = config_loader.get_config()
                
                return jsonify({
                    'hot_reload_enabled': True,
                    'config_version': config_loader.get_config_version(),
                    'last_reload': config_loader.get_last_reload_time().isoformat(),
                    'namespace': config_loader.namespace,
                    'configmap_name': config_loader.configmap_name,
                    'current_config': {
                        'version': __version__,
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
                    
                    # Add disk status
                    try:
                        flat_health['disk'] = self.db.get_disk_status()
                    except Exception:
                        flat_health['disk'] = {'status': 'unknown'}
                    
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
        
        @self.app.route('/api/database/status')
        def database_status():
            """Get database and disk status for monitoring"""
            try:
                disk_status = self.db.get_disk_status()
                
                # Get row counts
                metrics_count = self.db.conn.execute("SELECT COUNT(*) FROM metrics_history").fetchone()[0]
                predictions_count = self.db.conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
                anomalies_count = self.db.conn.execute("SELECT COUNT(*) FROM anomalies").fetchone()[0]
                
                # Get database file size
                db_size_mb = os.path.getsize(self.db.db_path) / (1024 * 1024) if os.path.exists(self.db.db_path) else 0
                
                return jsonify({
                    'disk': disk_status,
                    'database': {
                        'size_mb': round(db_size_mb, 2),
                        'metrics_count': metrics_count,
                        'predictions_count': predictions_count,
                        'anomalies_count': anomalies_count
                    },
                    'retention': {
                        'metrics_days': self.db.metrics_retention_days,
                        'predictions_days': self.db.predictions_retention_days,
                        'anomalies_days': self.db.anomalies_retention_days
                    },
                    'auto_healing': {
                        'enabled': True,
                        'warning_threshold': f"{self.db.disk_warning_threshold * 100:.0f}%",
                        'critical_threshold': f"{self.db.disk_critical_threshold * 100:.0f}%",
                        'emergency_threshold': f"{self.db.disk_emergency_threshold * 100:.0f}%"
                    }
                })
            except Exception as e:
                logger.error(f"Error getting database status: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/health')
        @self.app.route('/healthz')
        def simple_health():
            """Simple health check for K8s probes - fast, no external calls"""
            return jsonify({
                'status': 'ok',
                'timestamp': datetime.now().isoformat()
            }), 200
        
        @self.app.route('/api/ai/explain', methods=['POST'])
        def explain_event():
            """Get AI explanation for an event or query"""
            if not self.genai_analyzer:
                return jsonify({
                    'error': 'GenAI feature is not enabled',
                    'help': 'To enable GenAI features, set ENABLE_GENAI=true and configure one of: OPENAI_API_KEY, GEMINI_API_KEY, or ANTHROPIC_API_KEY',
                    'docs': 'See .env.example for configuration examples'
                }), 503
            
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'Missing JSON body'}), 400
                
                deployment = data.get('deployment')
                query = data.get('query')
                
                if not deployment or not query:
                    return jsonify({'error': 'Missing deployment or query'}), 400
                
                explanation = self.genai_analyzer.analyze_event(deployment, query)
                
                return jsonify({
                    'deployment': deployment,
                    'query': query,
                    'explanation': explanation,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Error in explain endpoint: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/ai/insights/<deployment>')
        def get_ai_insights(deployment):
            """Get AI insights - patterns, learning progress, predictions accuracy"""
            try:
                insights = {
                    'deployment': deployment,
                    'genai_enabled': self.genai_analyzer is not None,
                    'genai_provider': getattr(self.genai_analyzer, 'provider', None) if self.genai_analyzer else None,
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
                        SELECT timestamp, action_taken, hpa_target, confidence, pod_count, namespace
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
                            'pod_count': row[4],
                            'namespace': row[5],
                            'deployment': deployment
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
                    SELECT timestamp, action_taken, hpa_target, pod_count, confidence, node_utilization, pod_cpu_usage, namespace
                    FROM metrics_history
                    WHERE deployment = ?
                    ORDER BY timestamp DESC
                    LIMIT 500
                """, (deployment,))
                
                events = []
                prev_pods = None
                prev_target = None
                namespace = None
                
                for row in cursor.fetchall():
                    action = row[1]
                    pods = row[3]
                    target = row[2]
                    if namespace is None and len(row) > 7:
                        namespace = row[7]
                    
                    # Detect actual scaling events
                    if prev_pods is not None and pods != prev_pods:
                        events.append({
                            'timestamp': row[0],
                            'type': 'scale_up' if pods > prev_pods else 'scale_down',
                            'from_pods': prev_pods,
                            'to_pods': pods,
                            'hpa_target': target,
                            'cpu_usage': round((row[6] or 0) * 100, 1),
                            'confidence': row[4],
                            'namespace': namespace,
                            'deployment': deployment
                        })
                    
                    # Detect HPA target changes
                    if prev_target is not None and target != prev_target:
                        events.append({
                            'timestamp': row[0],
                            'type': 'target_change',
                            'from_target': prev_target,
                            'to_target': target,
                            'reason': action,
                            'namespace': namespace,
                            'deployment': deployment
                        })
                    
                    prev_pods = pods
                    prev_target = target
                
                return jsonify({
                    'deployment': deployment,
                    'namespace': namespace,
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
                            
                            # Get CPU usage - Try multiple query approaches with extensive fallbacks
                            cpu_usage = 0
                            cpu_queries = [
                                # Try 1: node_exporter with instance label
                                (f'sum(rate(node_cpu_seconds_total{{mode!="idle",instance=~".*{node_name}.*"}}[5m]))', "node_exporter (instance)"),
                                # Try 2: node_exporter with node label
                                (f'sum(rate(node_cpu_seconds_total{{mode!="idle",node="{node_name}"}}[5m]))', "node_exporter (node)"),
                                # Try 3: container metrics by node
                                (f'sum(rate(container_cpu_usage_seconds_total{{node="{node_name}",container!="",container!="POD"}}[5m]))', "container (node)"),
                                # Try 4: container metrics by instance
                                (f'sum(rate(container_cpu_usage_seconds_total{{instance=~".*{node_name}.*",container!="",container!="POD"}}[5m]))', "container (instance)"),
                                # Try 5: Simple node CPU without rate
                                (f'sum(node_cpu_seconds_total{{mode!="idle",instance=~".*{node_name}.*"}}) / 100', "node_exporter (no rate)"),
                            ]
                            
                            for query, source in cpu_queries:
                                try:
                                    cpu_usage_result = analyzer._query_prometheus(query)
                                    if cpu_usage_result and len(cpu_usage_result) > 0:
                                        cpu_usage = float(cpu_usage_result[0]['value'][1])
                                        if cpu_usage > 0:  # Only accept non-zero values
                                            logger.info(f"Node {node_name}: CPU usage = {cpu_usage} cores (source: {source})")
                                            break
                                except Exception as e:
                                    logger.debug(f"CPU query failed ({source}): {e}")
                                    continue
                            
                            if cpu_usage == 0:
                                logger.warning(f"Node {node_name}: Could not get CPU usage from any source")
                            
                            # Get memory usage - Try multiple approaches with extensive fallbacks
                            mem_usage = 0
                            mem_queries = [
                                # Try 1: node_memory with instance label
                                (f'node_memory_MemTotal_bytes{{instance=~".*{node_name}.*"}} - node_memory_MemAvailable_bytes{{instance=~".*{node_name}.*"}}', "node_exporter (instance)"),
                                # Try 2: node_memory with node label
                                (f'node_memory_MemTotal_bytes{{node="{node_name}"}} - node_memory_MemAvailable_bytes{{node="{node_name}"}}', "node_exporter (node)"),
                                # Try 3: container memory by node
                                (f'sum(container_memory_working_set_bytes{{node="{node_name}",container!="",container!="POD"}})', "container (node)"),
                                # Try 4: container memory by instance
                                (f'sum(container_memory_working_set_bytes{{instance=~".*{node_name}.*",container!="",container!="POD"}})', "container (instance)"),
                                # Try 5: Simple node memory usage
                                (f'node_memory_Active_bytes{{instance=~".*{node_name}.*"}}', "node_exporter (active)"),
                            ]
                            
                            for query, source in mem_queries:
                                try:
                                    mem_usage_result = analyzer._query_prometheus(query)
                                    if mem_usage_result and len(mem_usage_result) > 0:
                                        mem_usage = float(mem_usage_result[0]['value'][1]) / (1024**3)  # Convert to GB
                                        if mem_usage > 0:  # Only accept non-zero values
                                            logger.info(f"Node {node_name}: Memory usage = {mem_usage:.2f} GB (source: {source})")
                                            break
                                except Exception as e:
                                    logger.debug(f"Memory query failed ({source}): {e}")
                                    continue
                            
                            if mem_usage == 0:
                                logger.warning(f"Node {node_name}: Could not get memory usage from any source")
                            
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
                total_pod_count = 0
                
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
                    
                    # Total running pods
                    pod_count_query = 'sum(kube_pod_status_phase{phase="Running"})'
                    pod_count_result = analyzer._query_prometheus(pod_count_query)
                    if pod_count_result and len(pod_count_result) > 0:
                        total_pod_count = int(float(pod_count_result[0]['value'][1]))
                    logger.info(f"[CLUSTER] Total running pods: {total_pod_count}")
                
                except Exception as e:
                    logger.warning(f"Error querying resource requests: {e}")
                
                # Calculate total usage from node metrics (already collected above)
                # This is more reliable than querying again with different label formats
                total_cpu_usage = sum(node['cpu_usage'] for node in all_nodes)
                total_memory_usage = sum(node['memory_usage_gb'] for node in all_nodes)
                logger.info(f"[CLUSTER] Total usage: CPU={total_cpu_usage:.2f} cores, Memory={total_memory_usage:.2f} GB")
                
                return jsonify({
                    'nodes': all_nodes,
                    'node_count': len(all_nodes),
                    'pod_count': total_pod_count,
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
                    'namespaces': sorted(list(namespaces)),
                    'cloud_provider': self._detect_cloud_provider_info(all_nodes),
                    'kubernetes_version': self._get_kubernetes_version()
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
                        SUM(pod_cpu_usage * 1000) as total_cpu_usage_millicores,
                        SUM(memory_request) as total_memory_request_mb,
                        SUM(memory_usage) as total_memory_usage_mb
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
                        'total_cpu_usage_millicores': round(row[4] or 0, 0),
                        'total_memory_request_mb': round(row[5] or 0, 0),
                        'total_memory_usage_mb': round(row[6] or 0, 0)
                    })
                
                return jsonify({
                    'history': history,
                    'hours': hours
                })
            
            except Exception as e:
                logger.error(f"Error getting cluster history: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/finops/summary')
        def get_finops_summary():
            """
            Get FinOps recommendations for ALL deployments, sorted by priority.
            
            Returns a list of all deployments with their recommendations,
            sorted from high priority to optimal.
            """
            try:
                hours = request.args.get('hours', 168, type=int)
                
                # Priority order for sorting
                priority_order = {'high': 0, 'medium': 1, 'low': 2, 'optimal': 3}
                
                all_recommendations = []
                
                for key, config in self.operator.watched_deployments.items():
                    deployment = config['deployment']
                    namespace = config['namespace']
                    
                    try:
                        recommendations = self.operator.cost_optimizer.calculate_resource_recommendations(
                            deployment, 
                            hours=hours
                        )
                        
                        if recommendations:
                            # Add namespace and key info
                            recommendations['namespace'] = namespace
                            recommendations['key'] = key
                            recommendations['updated_at'] = datetime.now().isoformat()
                            
                            # Get memory leak detection
                            memory_leak = self.operator.cost_optimizer.detect_memory_leak(deployment, hours=24)
                            if memory_leak:
                                recommendations['memory_leak'] = memory_leak
                            
                            all_recommendations.append(recommendations)
                        else:
                            # Add placeholder for deployments without enough data
                            all_recommendations.append({
                                'deployment': deployment,
                                'namespace': namespace,
                                'key': key,
                                'recommendation_level': 'unknown',
                                'recommendation_text': 'Insufficient data for recommendations',
                                'updated_at': datetime.now().isoformat(),
                                'error': 'Need at least 100 data points'
                            })
                    except Exception as e:
                        logger.warning(f"Error getting recommendations for {deployment}: {e}")
                        all_recommendations.append({
                            'deployment': deployment,
                            'namespace': namespace,
                            'key': key,
                            'recommendation_level': 'unknown',
                            'recommendation_text': 'Error analyzing deployment',
                            'updated_at': datetime.now().isoformat(),
                            'error': str(e)
                        })
                
                # Sort by priority (high -> medium -> low -> optimal -> unknown)
                all_recommendations.sort(
                    key=lambda x: priority_order.get(x.get('recommendation_level', 'unknown'), 4)
                )
                
                # Calculate summary stats
                summary = {
                    'total_deployments': len(all_recommendations),
                    'high_priority': sum(1 for r in all_recommendations if r.get('recommendation_level') == 'high'),
                    'medium_priority': sum(1 for r in all_recommendations if r.get('recommendation_level') == 'medium'),
                    'low_priority': sum(1 for r in all_recommendations if r.get('recommendation_level') == 'low'),
                    'optimal': sum(1 for r in all_recommendations if r.get('recommendation_level') == 'optimal'),
                    'unknown': sum(1 for r in all_recommendations if r.get('recommendation_level') == 'unknown'),
                    'total_monthly_savings': sum(
                        r.get('savings', {}).get('monthly_savings_usd', 0) 
                        for r in all_recommendations if r.get('savings')
                    ),
                    'memory_leaks_detected': sum(
                        1 for r in all_recommendations 
                        if r.get('memory_leak', {}).get('is_leak_detected', False)
                    )
                }
                
                return jsonify({
                    'recommendations': all_recommendations,
                    'summary': summary,
                    'generated_at': datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Error getting FinOps summary: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/finops/enriched')
        def get_finops_enriched():
            """
            Get FinOps recommendations enriched with real-time waste data from Prometheus.
            
            Combines:
            - Resource right-sizing recommendations (from historical data)
            - Real-time waste tracking (from Prometheus)
            
            This provides a complete picture: what to optimize AND current waste.
            """
            try:
                hours = request.args.get('hours', 168, type=int)
                
                # Get FinOps recommendations
                priority_order = {'high': 0, 'medium': 1, 'low': 2, 'optimal': 3}
                all_recommendations = []
                
                for key, config in self.operator.watched_deployments.items():
                    deployment = config['deployment']
                    namespace = config['namespace']
                    
                    try:
                        recommendations = self.operator.cost_optimizer.calculate_resource_recommendations(
                            deployment, hours=hours
                        )
                        
                        if recommendations:
                            recommendations['namespace'] = namespace
                            recommendations['key'] = key
                            recommendations['updated_at'] = datetime.now().isoformat()
                            
                            # Get memory leak detection
                            memory_leak = self.operator.cost_optimizer.detect_memory_leak(deployment, hours=24)
                            if memory_leak:
                                recommendations['memory_leak'] = memory_leak
                            
                            all_recommendations.append(recommendations)
                        else:
                            all_recommendations.append({
                                'deployment': deployment,
                                'namespace': namespace,
                                'key': key,
                                'recommendation_level': 'unknown',
                                'recommendation_text': 'Insufficient data for recommendations',
                                'updated_at': datetime.now().isoformat(),
                                'error': 'Need at least 100 data points'
                            })
                    except Exception as e:
                        logger.warning(f"Error getting recommendations for {deployment}: {e}")
                        all_recommendations.append({
                            'deployment': deployment,
                            'namespace': namespace,
                            'key': key,
                            'recommendation_level': 'unknown',
                            'recommendation_text': 'Error analyzing deployment',
                            'updated_at': datetime.now().isoformat(),
                            'error': str(e)
                        })
                
                # Get real-time waste data from Prometheus
                realtime_waste = {}
                if self.realtime_cost:
                    try:
                        costs = self.realtime_cost.calculate_realtime_costs()
                        for w in costs.get('workloads', []):
                            # Create key from namespace/pod, extract deployment name
                            pod_name = w.get('pod', '')
                            ns = w.get('namespace', '')
                            # Match pods to deployments (pod name usually starts with deployment name)
                            for rec in all_recommendations:
                                if rec['namespace'] == ns and pod_name.startswith(rec['deployment']):
                                    if rec['key'] not in realtime_waste:
                                        realtime_waste[rec['key']] = {
                                            'pods': [],
                                            'total_cpu_request': 0,
                                            'total_cpu_usage': 0,
                                            'total_cost_hourly': 0,
                                            'total_waste_hourly': 0
                                        }
                                    realtime_waste[rec['key']]['pods'].append(w)
                                    realtime_waste[rec['key']]['total_cpu_request'] += w.get('cpu_request', 0)
                                    realtime_waste[rec['key']]['total_cpu_usage'] += w.get('cpu_usage', 0)
                                    realtime_waste[rec['key']]['total_cost_hourly'] += w.get('total_cost_hourly', 0)
                                    realtime_waste[rec['key']]['total_waste_hourly'] += w.get('total_waste_hourly', 0)
                                    break
                    except Exception as e:
                        logger.warning(f"Error getting real-time waste: {e}")
                
                # Enrich recommendations with real-time data
                for rec in all_recommendations:
                    key = rec.get('key')
                    if key in realtime_waste:
                        rt = realtime_waste[key]
                        rec['realtime'] = {
                            'pod_count': len(rt['pods']),
                            'cpu_request': round(rt['total_cpu_request'], 3),
                            'cpu_usage': round(rt['total_cpu_usage'], 3),
                            'cpu_utilization_percent': round(rt['total_cpu_usage'] / rt['total_cpu_request'] * 100, 1) if rt['total_cpu_request'] > 0 else 0,
                            'cost_hourly': round(rt['total_cost_hourly'], 4),
                            'cost_daily': round(rt['total_cost_hourly'] * 24, 2),
                            'cost_monthly': round(rt['total_cost_hourly'] * 24 * 30, 2),
                            'waste_hourly': round(rt['total_waste_hourly'], 4),
                            'waste_daily': round(rt['total_waste_hourly'] * 24, 2),
                            'waste_monthly': round(rt['total_waste_hourly'] * 24 * 30, 2),
                            'waste_percent': round(rt['total_waste_hourly'] / rt['total_cost_hourly'] * 100, 1) if rt['total_cost_hourly'] > 0 else 0
                        }
                
                # Sort by priority
                all_recommendations.sort(
                    key=lambda x: priority_order.get(x.get('recommendation_level', 'unknown'), 4)
                )
                
                # Calculate summary stats
                total_realtime_waste = sum(
                    rec.get('realtime', {}).get('waste_monthly', 0) 
                    for rec in all_recommendations
                )
                total_potential_savings = sum(
                    rec.get('savings', {}).get('monthly_savings_usd', 0) 
                    for rec in all_recommendations if rec.get('savings')
                )
                
                summary = {
                    'total_deployments': len(all_recommendations),
                    'high_priority': sum(1 for r in all_recommendations if r.get('recommendation_level') == 'high'),
                    'medium_priority': sum(1 for r in all_recommendations if r.get('recommendation_level') == 'medium'),
                    'low_priority': sum(1 for r in all_recommendations if r.get('recommendation_level') == 'low'),
                    'optimal': sum(1 for r in all_recommendations if r.get('recommendation_level') == 'optimal'),
                    'unknown': sum(1 for r in all_recommendations if r.get('recommendation_level') == 'unknown'),
                    'total_monthly_savings': round(total_potential_savings, 2),
                    'total_realtime_waste_monthly': round(total_realtime_waste, 2),
                    'memory_leaks_detected': sum(
                        1 for r in all_recommendations 
                        if r.get('memory_leak', {}).get('is_leak_detected', False)
                    ),
                    'has_realtime_data': bool(realtime_waste)
                }
                
                return jsonify({
                    'recommendations': all_recommendations,
                    'summary': summary,
                    'generated_at': datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Error getting enriched FinOps data: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/deployment/<namespace>/<deployment>/memory-leak')
        def get_memory_leak_detection(namespace, deployment):
            """
            Get memory leak detection results for a deployment.
            
            Analyzes memory usage trends to detect potential memory leaks.
            """
            try:
                hours = request.args.get('hours', 24, type=int)
                
                result = self.operator.cost_optimizer.detect_memory_leak(deployment, hours=hours)
                
                if not result:
                    return jsonify({
                        'deployment': deployment,
                        'namespace': namespace,
                        'error': 'Insufficient data for memory leak detection',
                        'suggestion': 'Need at least 30 data points with memory metrics'
                    }), 404
                
                result['namespace'] = namespace
                return jsonify(result)
            except Exception as e:
                logger.error(f"Error detecting memory leak: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cluster/node-efficiency')
        def get_node_efficiency():
            """
            Get cluster-wide node efficiency analysis.
            
            Returns comprehensive report on node utilization, bin-packing efficiency,
            and optimization opportunities.
            """
            try:
                # Import node efficiency analyzer
                from src.node_efficiency import NodeEfficiencyAnalyzer
                
                # Get core_v1 and custom_api from the controller
                # The operator passed to dashboard is IntegratedOperator which has a controller attribute
                if hasattr(self.operator, 'controller'):
                    core_v1 = self.operator.controller.core_v1
                    custom_api = self.operator.controller.custom_api
                elif hasattr(self.operator, 'core_v1'):
                    # Direct access if operator is EnhancedSmartAutoscaler
                    core_v1 = self.operator.core_v1
                    custom_api = self.operator.custom_api
                else:
                    return jsonify({
                        'error': 'Kubernetes API clients not available',
                        'suggestion': 'Check operator initialization',
                        'help': 'The operator object does not have core_v1 or custom_api attributes'
                    }), 500
                
                # Create analyzer
                analyzer = NodeEfficiencyAnalyzer(core_v1, custom_api)
                
                # Analyze cluster
                report = analyzer.analyze_cluster_efficiency()
                
                if not report:
                    return jsonify({
                        'error': 'Unable to analyze cluster efficiency',
                        'suggestion': 'Ensure metrics-server is installed: kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml',
                        'details': 'No nodes found or metrics unavailable. Check RBAC permissions and metrics-server status.'
                    }), 404
                
                # Convert to dict
                from dataclasses import asdict
                report_dict = asdict(report)
                
                # Convert datetime to ISO format
                report_dict['timestamp'] = report.timestamp.isoformat()
                
                return jsonify(report_dict)
            except Exception as e:
                logger.error(f"Error analyzing node efficiency: {e}", exc_info=True)
                error_msg = str(e)
                suggestion = None
                
                # Provide helpful suggestions based on error type
                if 'Forbidden' in error_msg or '403' in error_msg:
                    suggestion = 'RBAC permissions issue. Ensure the service account has permissions to list nodes and pods.'
                elif 'NotFound' in error_msg or '404' in error_msg:
                    suggestion = 'metrics-server not found. Install it with: kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml'
                elif 'Unauthorized' in error_msg or '401' in error_msg:
                    suggestion = 'Authentication issue. Check kubeconfig or service account token.'
                elif 'Connection' in error_msg or 'Timeout' in error_msg:
                    suggestion = 'Network connectivity issue. Check if Kubernetes API server is accessible.'
                else:
                    suggestion = 'Check application logs for detailed error information.'
                
                return jsonify({
                    'error': error_msg,
                    'suggestion': suggestion,
                    'help': 'Node Efficiency requires: 1) metrics-server installed, 2) RBAC permissions to list nodes/pods, 3) Network connectivity to K8s API'
                }), 500
        
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
        
        @self.app.route('/api/predictions/accuracy/<deployment>')
        def get_prediction_accuracy_history(deployment):
            """
            Get prediction accuracy history for charts.
            Returns predicted vs actual CPU over time.
            """
            try:
                hours = request.args.get('hours', 168, type=int)  # Default 7 days
                
                cursor = self.db.conn.execute("""
                    SELECT timestamp, predicted_cpu, actual_cpu, accuracy, recommended_action, validated
                    FROM predictions
                    WHERE deployment = ?
                    AND validated = 1
                    AND actual_cpu IS NOT NULL
                    AND predicted_cpu IS NOT NULL
                    AND timestamp >= datetime('now', '-' || ? || ' hours')
                    ORDER BY timestamp ASC
                """, (deployment, hours))
                
                history = []
                for row in cursor.fetchall():
                    history.append({
                        'timestamp': row[0],
                        'predicted': round(row[1], 1) if row[1] else None,
                        'actual': round(row[2], 1) if row[2] else None,
                        'accuracy': round(row[3], 2) if row[3] else None,
                        'action': row[4],
                        'validated': bool(row[5])
                    })
                
                # Get accuracy stats
                accuracy_stats = self.db.get_prediction_accuracy(deployment)
                
                # Calculate daily accuracy
                daily_accuracy = {}
                for item in history:
                    if item['accuracy'] is not None:
                        day = item['timestamp'][:10] if item['timestamp'] else None
                        if day:
                            if day not in daily_accuracy:
                                daily_accuracy[day] = []
                            daily_accuracy[day].append(item['accuracy'])
                
                daily_summary = [
                    {'date': day, 'accuracy': round(sum(accs) / len(accs) * 100, 1), 'count': len(accs)}
                    for day, accs in sorted(daily_accuracy.items())
                ]
                
                return jsonify({
                    'deployment': deployment,
                    'history': history,
                    'daily_summary': daily_summary,
                    'stats': accuracy_stats,
                    'total_validated': len(history)
                })
            except Exception as e:
                logger.error(f"Error getting prediction accuracy history: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/finops/cost-trends')
        def get_all_cost_trends():
            """
            Get cost trends for all deployments.
            Returns daily cost data for the last 30 days.
            """
            try:
                days = request.args.get('days', 30, type=int)
                cost_per_vcpu = float(os.getenv('COST_PER_VCPU_HOUR', '0.04'))
                cost_per_gb_memory = float(os.getenv('COST_PER_GB_MEMORY_HOUR', '0.005'))
                
                # Get daily costs per deployment
                cursor = self.db.conn.execute("""
                    SELECT 
                        deployment,
                        strftime('%Y-%m-%d', timestamp) as day,
                        AVG(pod_count) as avg_pods,
                        AVG(cpu_request) as avg_cpu_request,
                        AVG(memory_request) as avg_memory_request,
                        AVG(pod_cpu_usage) as avg_cpu_usage,
                        AVG(memory_usage) as avg_memory_usage,
                        COUNT(*) as samples
                    FROM metrics_history
                    WHERE timestamp >= datetime('now', '-' || ? || ' days')
                    GROUP BY deployment, day
                    ORDER BY day ASC, deployment
                """, (days,))
                
                # Organize by deployment
                deployment_trends = {}
                daily_totals = {}
                
                for row in cursor.fetchall():
                    dep = row[0]
                    day = row[1]
                    pods = row[2] or 1
                    cpu_req = (row[3] or 100) / 1000  # cores
                    mem_req = (row[4] or 512) / 1024  # GB
                    cpu_usage = row[5] or 0
                    mem_usage = (row[6] or 0) / 1024  # GB
                    
                    # Calculate daily cost (24 hours)
                    daily_cpu_cost = pods * cpu_req * cost_per_vcpu * 24
                    daily_mem_cost = pods * mem_req * cost_per_gb_memory * 24
                    daily_total = daily_cpu_cost + daily_mem_cost
                    
                    # Calculate actual usage cost
                    actual_cpu_cost = pods * cpu_usage * cost_per_vcpu * 24
                    actual_mem_cost = pods * mem_usage * cost_per_gb_memory * 24
                    actual_total = actual_cpu_cost + actual_mem_cost
                    
                    wasted = max(0, daily_total - actual_total)
                    
                    if dep not in deployment_trends:
                        deployment_trends[dep] = []
                    
                    deployment_trends[dep].append({
                        'date': day,
                        'cost': round(daily_total, 2),
                        'actual': round(actual_total, 2),
                        'wasted': round(wasted, 2),
                        'pods': round(pods, 1)
                    })
                    
                    # Aggregate daily totals
                    if day not in daily_totals:
                        daily_totals[day] = {'cost': 0, 'actual': 0, 'wasted': 0}
                    daily_totals[day]['cost'] += daily_total
                    daily_totals[day]['actual'] += actual_total
                    daily_totals[day]['wasted'] += wasted
                
                # Format daily totals
                daily_summary = [
                    {
                        'date': day,
                        'cost': round(data['cost'], 2),
                        'actual': round(data['actual'], 2),
                        'wasted': round(data['wasted'], 2)
                    }
                    for day, data in sorted(daily_totals.items())
                ]
                
                # Calculate totals
                total_cost = sum(d['cost'] for d in daily_summary)
                total_wasted = sum(d['wasted'] for d in daily_summary)
                
                return jsonify({
                    'deployment_trends': deployment_trends,
                    'daily_summary': daily_summary,
                    'summary': {
                        'total_cost': round(total_cost, 2),
                        'total_wasted': round(total_wasted, 2),
                        'efficiency': round((1 - total_wasted / total_cost) * 100, 1) if total_cost > 0 else 100,
                        'days_analyzed': len(daily_summary),
                        'monthly_projection': round(total_cost / max(1, len(daily_summary)) * 30, 2)
                    }
                })
            except Exception as e:
                logger.error(f"Error getting cost trends: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/alerts/recent')
        def get_recent_alerts():
            """
            Get recent anomalies and alerts.
            """
            try:
                hours = request.args.get('hours', 24, type=int)
                
                cursor = self.db.conn.execute("""
                    SELECT timestamp, deployment, anomaly_type, severity, description,
                           current_value, expected_value, deviation_percent
                    FROM anomalies
                    WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                    ORDER BY timestamp DESC
                    LIMIT 100
                """, (hours,))
                
                alerts = []
                for row in cursor.fetchall():
                    alerts.append({
                        'timestamp': row[0],
                        'deployment': row[1],
                        'type': row[2],
                        'severity': row[3],
                        'description': row[4],
                        'current_value': round(row[5], 2) if row[5] else None,
                        'expected_value': round(row[6], 2) if row[6] else None,
                        'deviation_percent': round(row[7], 1) if row[7] else None
                    })
                
                # Count by severity
                severity_counts = {'critical': 0, 'warning': 0, 'info': 0}
                for alert in alerts:
                    sev = alert['severity'].lower() if alert['severity'] else 'info'
                    if sev in severity_counts:
                        severity_counts[sev] += 1
                
                return jsonify({
                    'alerts': alerts,
                    'summary': {
                        'total': len(alerts),
                        'critical': severity_counts['critical'],
                        'warning': severity_counts['warning'],
                        'info': severity_counts['info']
                    }
                })
            except Exception as e:
                logger.error(f"Error getting recent alerts: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        # Notification Provider API Endpoints
        @self.app.route('/api/notification-providers')
        def get_notification_providers():
            """Get all notification providers (from DB + env vars)"""
            try:
                # Get providers from database
                db_providers = self.db.get_notification_providers()
                
                # Get providers from environment variables (read-only)
                env_providers = []
                import os
                if os.getenv('SLACK_WEBHOOK'):
                    env_providers.append({
                        'id': 'env_slack',
                        'name': 'Slack (env)',
                        'provider_type': 'slack',
                        'webhook_url': os.getenv('SLACK_WEBHOOK')[:30] + '...',
                        'enabled': True,
                        'source': 'environment',
                        'readonly': True
                    })
                if os.getenv('TEAMS_WEBHOOK'):
                    env_providers.append({
                        'id': 'env_teams',
                        'name': 'Teams (env)',
                        'provider_type': 'teams',
                        'webhook_url': os.getenv('TEAMS_WEBHOOK')[:30] + '...',
                        'enabled': True,
                        'source': 'environment',
                        'readonly': True
                    })
                if os.getenv('DISCORD_WEBHOOK'):
                    env_providers.append({
                        'id': 'env_discord',
                        'name': 'Discord (env)',
                        'provider_type': 'discord',
                        'webhook_url': os.getenv('DISCORD_WEBHOOK')[:30] + '...',
                        'enabled': True,
                        'source': 'environment',
                        'readonly': True
                    })
                if os.getenv('GENERIC_WEBHOOK'):
                    env_providers.append({
                        'id': 'env_generic',
                        'name': 'Generic (env)',
                        'provider_type': 'generic',
                        'webhook_url': os.getenv('GENERIC_WEBHOOK')[:30] + '...',
                        'enabled': True,
                        'source': 'environment',
                        'readonly': True
                    })
                
                # Mark DB providers
                for p in db_providers:
                    p['source'] = 'dashboard'
                    p['readonly'] = False
                
                return jsonify({
                    'providers': env_providers + db_providers,
                    'env_count': len(env_providers),
                    'db_count': len(db_providers)
                })
            except Exception as e:
                logger.error(f"Error getting notification providers: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/notification-providers', methods=['POST'])
        def add_notification_provider():
            """Add a new notification provider"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'No data provided'}), 400
                
                name = data.get('name')
                provider_type = data.get('provider_type')
                webhook_url = data.get('webhook_url')
                enabled = data.get('enabled', True)
                alert_types = data.get('alert_types')  # List of alert types or None for all
                
                if not name or not provider_type or not webhook_url:
                    return jsonify({'error': 'name, provider_type, and webhook_url are required'}), 400
                
                if provider_type not in ['slack', 'teams', 'discord', 'generic']:
                    return jsonify({'error': 'Invalid provider_type. Must be: slack, teams, discord, or generic'}), 400
                
                result = self.db.add_notification_provider(name, provider_type, webhook_url, enabled, alert_types)
                
                if result['success']:
                    # Reload alert manager webhooks
                    self._reload_alert_manager_webhooks()
                    return jsonify(result)
                return jsonify(result), 400
            except Exception as e:
                logger.error(f"Error adding notification provider: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/notification-providers/<int:provider_id>', methods=['PUT'])
        def update_notification_provider(provider_id):
            """Update a notification provider"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'No data provided'}), 400
                
                result = self.db.update_notification_provider(
                    provider_id,
                    name=data.get('name'),
                    provider_type=data.get('provider_type'),
                    webhook_url=data.get('webhook_url'),
                    enabled=data.get('enabled'),
                    alert_types=data.get('alert_types')
                )
                
                if result['success']:
                    self._reload_alert_manager_webhooks()
                    return jsonify(result)
                return jsonify(result), 400
            except Exception as e:
                logger.error(f"Error updating notification provider: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/notification-providers/<int:provider_id>', methods=['DELETE'])
        def delete_notification_provider(provider_id):
            """Delete a notification provider"""
            try:
                result = self.db.delete_notification_provider(provider_id)
                
                if result['success']:
                    self._reload_alert_manager_webhooks()
                    return jsonify(result)
                return jsonify(result), 400
            except Exception as e:
                logger.error(f"Error deleting notification provider: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/notification-providers/<int:provider_id>/test', methods=['POST'])
        def test_notification_provider(provider_id):
            """Test a notification provider by sending a test message"""
            try:
                provider_info = self.db.test_notification_provider(provider_id)
                
                if 'error' in provider_info:
                    return jsonify(provider_info), 404
                
                # Send test message
                try:
                    # Create temporary alert manager with just this provider
                    test_webhooks = {provider_info['provider_type']: provider_info['webhook_url']}
                    from src.intelligence import AlertManager
                    test_manager = AlertManager(test_webhooks)
                    test_manager.send_alert(
                        title="🧪 Test Notification",
                        message="This is a test message from Smart Autoscaler dashboard. If you see this, your webhook is configured correctly!",
                        severity="info",
                        fields={
                            "Provider": provider_info['name'], 
                            "Type": provider_info['provider_type'],
                            "Status": "✅ Working"
                        }
                    )
                    return jsonify({'success': True, 'message': f'Test message sent to {provider_info["name"]}'})
                except Exception as e:
                    logger.error(f"Failed to send test notification: {e}", exc_info=True)
                    return jsonify({'success': False, 'error': f'Failed to send test: {str(e)}'}), 500
            except Exception as e:
                logger.error(f"Error testing notification provider: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/notification-providers/test-webhook', methods=['POST'])
        def test_webhook_direct():
            """Test a webhook URL directly without saving it first"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'No data provided'}), 400
                
                provider_type = data.get('provider_type')
                webhook_url = data.get('webhook_url')
                
                if not provider_type or not webhook_url:
                    return jsonify({'error': 'provider_type and webhook_url are required'}), 400
                
                if provider_type not in ['slack', 'teams', 'discord', 'googlechat', 'generic']:
                    return jsonify({'error': 'Invalid provider_type. Must be: slack, teams, discord, googlechat, or generic'}), 400
                
                # Send test message
                try:
                    test_webhooks = {provider_type: webhook_url}
                    from src.intelligence import AlertManager
                    test_manager = AlertManager(test_webhooks)
                    test_manager.send_alert(
                        title="🧪 Webhook Test",
                        message="This is a test message from Smart Autoscaler. If you see this, your webhook URL is correct!",
                        severity="info",
                        fields={
                            "Type": provider_type.title(),
                            "Status": "✅ Connection successful",
                            "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                    )
                    return jsonify({'success': True, 'message': f'Test message sent to {provider_type.title()}! Check your channel.'})
                except Exception as e:
                    logger.error(f"Failed to send test to webhook: {e}", exc_info=True)
                    return jsonify({'success': False, 'error': f'Failed to send: {str(e)}'}), 500
            except Exception as e:
                logger.error(f"Error testing webhook: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/deployment/<namespace>/<deployment>/detail')
        def get_deployment_detail(namespace, deployment):
            """
            Get comprehensive deployment detail for detail view.
            Combines current state, history, predictions, costs, and patterns.
            """
            try:
                # Get current state
                recent = self.db.get_recent_metrics(deployment, hours=1)
                current = None
                if recent:
                    latest = recent[0]
                    current = {
                        'timestamp': latest.timestamp.isoformat(),
                        'node_utilization': latest.node_utilization,
                        'pod_count': latest.pod_count,
                        'pod_cpu_usage': latest.pod_cpu_usage,
                        'memory_usage': latest.memory_usage if hasattr(latest, 'memory_usage') else 0,
                        'hpa_target': latest.hpa_target,
                        'confidence': latest.confidence,
                        'cpu_request': latest.cpu_request,
                        'memory_request': latest.memory_request if hasattr(latest, 'memory_request') else 0
                    }
                
                # Get pattern
                pattern = 'unknown'
                pattern_confidence = 0
                try:
                    if hasattr(self.operator, 'pattern_detector'):
                        pattern_result = self.operator.pattern_detector.detect_pattern(deployment)
                        if pattern_result:
                            pattern = pattern_result.pattern.value
                            pattern_confidence = pattern_result.confidence
                except:
                    pass
                
                # Get prediction accuracy
                accuracy_stats = self.db.get_prediction_accuracy(deployment)
                
                # Get optimal target
                optimal_target = self.db.get_optimal_target(deployment)
                
                # Get cost metrics
                cost_metrics = None
                try:
                    cost_data = self.operator.cost_optimizer.analyze_costs(deployment, hours=168)
                    if cost_data:
                        cost_metrics = {
                            'monthly_cost': round(cost_data.estimated_monthly_cost, 2),
                            'wasted_percent': round(cost_data.wasted_capacity_percent, 1),
                            'optimization_potential': round(cost_data.optimization_potential, 2),
                            'cpu_utilization': round(cost_data.cpu_utilization_percent, 1),
                            'memory_utilization': round(cost_data.memory_utilization_percent, 1)
                        }
                except:
                    pass
                
                # Get recommendations
                recommendations = None
                try:
                    recommendations = self.operator.cost_optimizer.calculate_resource_recommendations(deployment, hours=168)
                except:
                    pass
                
                # Get memory leak detection
                memory_leak = None
                try:
                    memory_leak = self.operator.cost_optimizer.detect_memory_leak(deployment, hours=24)
                except:
                    pass
                
                # Get recent scaling events
                cursor = self.db.conn.execute("""
                    SELECT timestamp, action_taken, hpa_target, pod_count, confidence
                    FROM metrics_history
                    WHERE deployment = ? AND action_taken != 'maintain'
                    ORDER BY timestamp DESC
                    LIMIT 10
                """, (deployment,))
                
                scaling_events = []
                for row in cursor.fetchall():
                    scaling_events.append({
                        'timestamp': row[0],
                        'action': row[1],
                        'hpa_target': row[2],
                        'pod_count': row[3],
                        'confidence': row[4]
                    })
                
                # Get recent anomalies
                cursor = self.db.conn.execute("""
                    SELECT timestamp, anomaly_type, severity, description
                    FROM anomalies
                    WHERE deployment = ?
                    ORDER BY timestamp DESC
                    LIMIT 5
                """, (deployment,))
                
                anomalies = []
                for row in cursor.fetchall():
                    anomalies.append({
                        'timestamp': row[0],
                        'type': row[1],
                        'severity': row[2],
                        'description': row[3]
                    })
                
                return jsonify({
                    'deployment': deployment,
                    'namespace': namespace,
                    'current': current,
                    'pattern': {
                        'type': pattern,
                        'confidence': pattern_confidence
                    },
                    'prediction_accuracy': accuracy_stats,
                    'optimal_target': optimal_target,
                    'cost': cost_metrics,
                    'recommendations': recommendations,
                    'memory_leak': memory_leak,
                    'scaling_events': scaling_events,
                    'anomalies': anomalies
                })
            except Exception as e:
                logger.error(f"Error getting deployment detail: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/deployment/<namespace>/<deployment>/hpa-analysis')
        def get_hpa_analysis(namespace, deployment):
            """
            Analyze HPA behavior config and provide scaling safety recommendations.
            
            Reads the HPA's behavior.scaleUp and behavior.scaleDown settings,
            analyzes them against the workload pattern, and provides recommendations
            for safe scaling.
            """
            try:
                # Get HPA name from watched deployments
                key = f"{namespace}/{deployment}"
                config = self.operator.watched_deployments.get(key)
                if not config:
                    return jsonify({'error': 'Deployment not found'}), 404
                
                hpa_name = config['hpa_name']
                
                # Read HPA from Kubernetes
                try:
                    from kubernetes import client
                    # Handle both operator types - EnhancedSmartAutoscaler uses controller.autoscaling_v2
                    if hasattr(self.operator, 'autoscaling_v2'):
                        autoscaling_api = self.operator.autoscaling_v2
                    elif hasattr(self.operator, 'controller') and hasattr(self.operator.controller, 'autoscaling_v2'):
                        autoscaling_api = self.operator.controller.autoscaling_v2
                    else:
                        return jsonify({'error': 'Kubernetes API not available'}), 500
                    
                    hpa = autoscaling_api.read_namespaced_horizontal_pod_autoscaler(
                        hpa_name, namespace
                    )
                except Exception as e:
                    return jsonify({'error': f'Failed to read HPA: {e}'}), 500
                
                # Extract current HPA config
                hpa_config = {
                    'name': hpa_name,
                    'min_replicas': hpa.spec.min_replicas,
                    'max_replicas': hpa.spec.max_replicas,
                    'current_replicas': hpa.status.current_replicas if hpa.status else None,
                    'target_cpu_percent': None,
                    'behavior': {
                        'scale_up': None,
                        'scale_down': None
                    }
                }
                
                # Get target CPU utilization
                if hpa.spec.metrics:
                    for metric in hpa.spec.metrics:
                        if metric.resource and metric.resource.name == 'cpu':
                            hpa_config['target_cpu_percent'] = metric.resource.target.average_utilization
                            break
                
                # Extract behavior config
                if hpa.spec.behavior:
                    if hpa.spec.behavior.scale_up:
                        su = hpa.spec.behavior.scale_up
                        policies = []
                        if su.policies:
                            for p in su.policies:
                                policies.append({
                                    'type': p.type,
                                    'value': p.value,
                                    'period_seconds': p.period_seconds
                                })
                        hpa_config['behavior']['scale_up'] = {
                            'stabilization_window_seconds': su.stabilization_window_seconds,
                            'select_policy': su.select_policy,
                            'policies': policies
                        }
                    
                    if hpa.spec.behavior.scale_down:
                        sd = hpa.spec.behavior.scale_down
                        policies = []
                        if sd.policies:
                            for p in sd.policies:
                                policies.append({
                                    'type': p.type,
                                    'value': p.value,
                                    'period_seconds': p.period_seconds
                                })
                        hpa_config['behavior']['scale_down'] = {
                            'stabilization_window_seconds': sd.stabilization_window_seconds,
                            'select_policy': sd.select_policy,
                            'policies': policies
                        }
                
                # Get workload pattern
                pattern = 'unknown'
                if hasattr(self.operator, 'pattern_detector'):
                    try:
                        pattern_result = self.operator.pattern_detector.detect_pattern(deployment)
                        if pattern_result:
                            pattern = pattern_result.pattern.value
                    except:
                        pass
                
                # Get recent metrics for analysis
                recent = self.db.get_recent_metrics(deployment, hours=24)
                
                # Calculate scaling event frequency
                cursor = self.db.conn.execute("""
                    SELECT COUNT(*) FROM metrics_history
                    WHERE deployment = ? 
                    AND action_taken != 'maintain'
                    AND timestamp >= datetime('now', '-24 hours')
                """, (deployment,))
                scale_events_24h = cursor.fetchone()[0]
                
                cursor = self.db.conn.execute("""
                    SELECT COUNT(*) FROM metrics_history
                    WHERE deployment = ? 
                    AND action_taken != 'maintain'
                    AND timestamp >= datetime('now', '-1 hour')
                """, (deployment,))
                scale_events_1h = cursor.fetchone()[0]
                
                # Analyze and generate recommendations
                analysis = self._analyze_hpa_behavior(
                    hpa_config, 
                    pattern, 
                    scale_events_24h, 
                    scale_events_1h,
                    recent
                )
                
                return jsonify({
                    'deployment': deployment,
                    'namespace': namespace,
                    'hpa_config': hpa_config,
                    'pattern': pattern,
                    'scaling_frequency': {
                        'events_24h': scale_events_24h,
                        'events_1h': scale_events_1h,
                        'is_flapping': scale_events_1h > 5 or scale_events_24h > 20
                    },
                    'analysis': analysis
                })
            except Exception as e:
                logger.error(f"Error analyzing HPA: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        # ============================================
        # Real-time Cost Tracking APIs (Prometheus-based)
        # ============================================
        
        @self.app.route('/api/cost/realtime')
        def get_realtime_costs():
            """
            Get real-time costs for all workloads using Prometheus.
            No local storage - all data queried live from Prometheus.
            
            Query params:
                namespace: Filter by namespace (optional)
            
            Returns:
                - Per-workload cost (hourly, daily, monthly)
                - Waste tracking (requested vs actual usage)
                - Cluster totals
            """
            if not self.realtime_cost:
                return jsonify({'error': 'Real-time cost tracking not available'}), 503
            
            namespace = request.args.get('namespace')
            
            try:
                costs = self.realtime_cost.calculate_realtime_costs(namespace)
                return jsonify(costs)
            except Exception as e:
                logger.error(f"Error getting real-time costs: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cost/realtime/<namespace>/<deployment>')
        def get_realtime_deployment_cost(namespace, deployment):
            """
            Get real-time cost for a specific deployment.
            
            Returns:
                - Aggregated cost for all pods in deployment
                - CPU/memory utilization
                - Waste calculation
            """
            if not self.realtime_cost:
                return jsonify({'error': 'Real-time cost tracking not available'}), 503
            
            try:
                cost = self.realtime_cost.get_deployment_realtime_cost(namespace, deployment)
                return jsonify(cost)
            except Exception as e:
                logger.error(f"Error getting deployment real-time cost: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cost/realtime/cluster')
        def get_realtime_cluster_summary():
            """
            Get real-time cluster cost summary.
            
            Returns:
                - Total cluster cost (hourly, daily, monthly, yearly)
                - Per-node breakdown
                - Resource utilization
            """
            if not self.realtime_cost:
                return jsonify({'error': 'Real-time cost tracking not available'}), 503
            
            try:
                summary = self.realtime_cost.get_cluster_realtime_summary()
                return jsonify(summary)
            except Exception as e:
                logger.error(f"Error getting cluster real-time summary: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cost/realtime/waste')
        def get_realtime_waste():
            """
            Get real-time waste analysis.
            Shows resources that are requested but not used.
            
            Query params:
                namespace: Filter by namespace (optional)
                min_waste_percent: Minimum waste percentage to include (default: 50)
            
            Returns:
                - Workloads with high waste
                - Total waste cost (hourly, daily, monthly)
            """
            if not self.realtime_cost:
                return jsonify({'error': 'Real-time cost tracking not available'}), 503
            
            namespace = request.args.get('namespace')
            min_waste_percent = request.args.get('min_waste_percent', 50, type=float)
            
            try:
                all_costs = self.realtime_cost.calculate_realtime_costs(namespace)
                
                # Filter workloads with high waste
                high_waste = [
                    w for w in all_costs['workloads']
                    if w['total_cost_hourly'] > 0 and 
                    (w['total_waste_hourly'] / w['total_cost_hourly'] * 100) >= min_waste_percent
                ]
                
                # Sort by waste amount
                high_waste.sort(key=lambda x: x['waste_monthly'], reverse=True)
                
                total_waste_hourly = sum(w['total_waste_hourly'] for w in high_waste)
                
                return jsonify({
                    'timestamp': all_costs['timestamp'],
                    'min_waste_percent': min_waste_percent,
                    'high_waste_workloads': high_waste,
                    'summary': {
                        'workload_count': len(high_waste),
                        'total_waste_hourly': round(total_waste_hourly, 4),
                        'total_waste_daily': round(total_waste_hourly * 24, 2),
                        'total_waste_monthly': round(total_waste_hourly * 24 * 30, 2),
                    }
                })
            except Exception as e:
                logger.error(f"Error getting waste analysis: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        # ============================================
        # Cost Alerting APIs
        # ============================================
        
        @self.app.route('/api/cost/alerting/config', methods=['GET'])
        def get_alerting_config():
            """Get current alerting configuration"""
            if not self.cost_alerting:
                return jsonify({'error': 'Cost alerting not available'}), 503
            
            return jsonify(self.cost_alerting.get_config())
        
        @self.app.route('/api/cost/alerting/config', methods=['POST'])
        def set_alerting_config():
            """
            Configure cost alerting settings.
            
            Body params:
                enabled: bool - Enable/disable daily reports
                webhook_url: str - Generic webhook URL
                slack_webhook_url: str - Slack webhook URL
                alert_time: str - Time to send daily report (HH:MM format)
            """
            if not self.cost_alerting:
                return jsonify({'error': 'Cost alerting not available'}), 503
            
            try:
                data = request.get_json() or {}
                
                config = self.cost_alerting.configure(
                    enabled=data.get('enabled'),
                    webhook_url=data.get('webhook_url'),
                    slack_webhook_url=data.get('slack_webhook_url'),
                    alert_time=data.get('alert_time')
                )
                
                return jsonify({
                    'success': True,
                    'config': config
                })
            except Exception as e:
                logger.error(f"Error configuring alerting: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cost/alerting/test', methods=['POST'])
        def test_alerting():
            """Send a test alert to verify configuration"""
            if not self.cost_alerting:
                return jsonify({'error': 'Cost alerting not available'}), 503
            
            try:
                result = self.cost_alerting.test_alert()
                return jsonify(result)
            except Exception as e:
                logger.error(f"Error sending test alert: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cost/alerting/send-now', methods=['POST'])
        def send_report_now():
            """Manually trigger sending the daily cost report"""
            if not self.cost_alerting:
                return jsonify({'error': 'Cost alerting not available'}), 503
            
            try:
                result = self.cost_alerting.send_daily_report()
                return jsonify(result)
            except Exception as e:
                logger.error(f"Error sending report: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        # ============================================
        # Advanced Cost Allocation & Reporting APIs
        # ============================================
        
        @self.app.route('/api/cost/cluster-summary')
        def get_cluster_cost_summary():
            """Get cluster-wide cost summary with node breakdown"""
            if not self.cost_allocator:
                return jsonify({'error': 'Cost allocation not available'}), 503
            
            try:
                summary = self.cost_allocator.get_cluster_cost_summary()
                return jsonify(summary)
            except Exception as e:
                logger.error(f"Error getting cluster cost summary: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cost/fair-share/<namespace>/<deployment>')
        def get_fair_share_cost(namespace, deployment):
            """
            Get cost using fair share allocation model.
            
            This allocates actual node costs proportionally based on resource requests:
            - Node cost is divided by total requests on that node
            - Each workload pays proportionally to their requests
            
            Example: Node costs $1/hr, has 3 vCPU requested out of 4 vCPU capacity
            - Cost per requested vCPU = $1/3 = $0.33/hr
            - Workload requesting 1 vCPU pays $0.33/hr
            """
            if not self.cost_allocator:
                return jsonify({'error': 'Cost allocation not available'}), 503
            
            hours = request.args.get('hours', 24, type=int)
            try:
                cost = self.cost_allocator.calculate_fair_share_cost(namespace, deployment, hours)
                return jsonify(cost)
            except Exception as e:
                logger.error(f"Error calculating fair share cost: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cost/workloads')
        def get_all_workload_costs():
            """
            Get costs for all watched workloads using fair share allocation.
            Shows both fixed pricing and fair share costs for comparison.
            """
            if not self.cost_allocator:
                return jsonify({'error': 'Cost allocation not available'}), 503
            
            hours = request.args.get('hours', 24, type=int)
            model = request.args.get('model', 'fair_share')  # 'fair_share' or 'fixed'
            
            try:
                workloads = []
                total_cost = 0.0
                
                for key, config in self.operator.watched_deployments.items():
                    namespace = config['namespace']
                    deployment = config['deployment']
                    
                    if model == 'fair_share':
                        cost = self.cost_allocator.calculate_fair_share_cost(namespace, deployment, hours)
                    else:
                        cost = self.cost_allocator.calculate_deployment_cost(namespace, deployment, hours)
                    
                    workloads.append({
                        'namespace': namespace,
                        'deployment': deployment,
                        'cpu_cost': cost.get('cpu_cost', 0),
                        'memory_cost': cost.get('memory_cost', 0),
                        'total_cost': cost.get('total_cost', 0),
                        'replicas': cost.get('replicas', 0),
                        'allocation_model': cost.get('allocation_model', 'fixed')
                    })
                    total_cost += cost.get('total_cost', 0)
                
                # Sort by cost descending
                workloads.sort(key=lambda x: x['total_cost'], reverse=True)
                
                return jsonify({
                    'workloads': workloads,
                    'total_cost': round(total_cost, 4),
                    'hours': hours,
                    'allocation_model': model,
                    'workload_count': len(workloads)
                })
            except Exception as e:
                logger.error(f"Error getting workload costs: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cost/allocation/team')
        def get_team_costs():
            """Get costs grouped by team"""
            if not self.cost_allocator:
                return jsonify({'error': 'Cost allocation not available'}), 503
            
            hours = request.args.get('hours', 24, type=int)
            try:
                costs = self.cost_allocator.get_team_costs(hours=hours)
                return jsonify(costs)
            except Exception as e:
                logger.error(f"Error getting team costs: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cost/pricing-info')
        def get_pricing_info():
            """Get detected pricing information"""
            if not self.cost_allocator:
                return jsonify({'error': 'Cost allocation not available'}), 503
            
            try:
                from src.cloud_pricing import CloudPricingDetector
                
                # Get core_v1 from operator
                if hasattr(self.operator, 'controller'):
                    core_v1 = self.operator.controller.core_v1
                elif hasattr(self.operator, 'core_v1'):
                    core_v1 = self.operator.core_v1
                else:
                    return jsonify({'error': 'Kubernetes API not available'}), 500
                
                detector = CloudPricingDetector(core_v1)
                detector.auto_detect_pricing()
                pricing_info = detector.get_pricing_info()
                
                # Add current configured pricing
                pricing_info['configured_vcpu_price'] = self.cost_allocator.cost_per_vcpu_hour
                pricing_info['configured_memory_gb_price'] = self.cost_allocator.cost_per_gb_memory_hour
                
                return jsonify(pricing_info)
            except Exception as e:
                logger.error(f"Error getting pricing info: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cost/allocation/namespace')
        def get_namespace_costs():
            """Get costs grouped by namespace"""
            if not self.cost_allocator:
                return jsonify({'error': 'Cost allocation not available'}), 503
            
            hours = request.args.get('hours', 24, type=int)
            try:
                costs = self.cost_allocator.get_namespace_costs(hours=hours)
                return jsonify(costs)
            except Exception as e:
                logger.error(f"Error getting namespace costs: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cost/allocation/project')
        def get_project_costs():
            """Get costs grouped by project"""
            if not self.cost_allocator:
                return jsonify({'error': 'Cost allocation not available'}), 503
            
            hours = request.args.get('hours', 24, type=int)
            try:
                costs = self.cost_allocator.get_project_costs(hours=hours)
                return jsonify(costs)
            except Exception as e:
                logger.error(f"Error getting project costs: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cost/anomalies')
        def get_cost_anomalies():
            """Detect cost anomalies"""
            if not self.cost_allocator:
                return jsonify({'error': 'Cost allocation not available'}), 503
            
            try:
                anomalies = self.cost_allocator.detect_cost_anomalies()
                return jsonify({'anomalies': anomalies})
            except Exception as e:
                logger.error(f"Error detecting cost anomalies: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cost/idle-resources')
        def get_idle_resources():
            """Get idle/underutilized resources"""
            if not self.cost_allocator:
                return jsonify({'error': 'Cost allocation not available'}), 503
            
            threshold = request.args.get('threshold', 0.2, type=float)
            try:
                idle = self.cost_allocator.get_idle_resources(utilization_threshold=threshold)
                return jsonify({'idle_resources': idle})
            except Exception as e:
                logger.error(f"Error getting idle resources: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/reports/executive-summary')
        def get_executive_summary():
            """Generate executive summary report"""
            if not self.report_generator:
                return jsonify({'error': 'Reporting not available'}), 503
            
            days = request.args.get('days', 30, type=int)
            try:
                report = self.report_generator.generate_executive_summary(days=days)
                return jsonify(report)
            except Exception as e:
                logger.error(f"Error generating executive summary: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/reports/status')
        def get_reports_status():
            """Get reporting system status for debugging"""
            try:
                status = {
                    'report_generator_available': self.report_generator is not None,
                    'cost_allocator_available': self.cost_allocator is not None,
                    'watched_deployments': len(self.operator.watched_deployments),
                    'deployment_list': list(self.operator.watched_deployments.keys()),
                }
                
                # Try to get basic metrics
                if self.db:
                    cursor = self.db.conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM metrics")
                    status['metrics_count'] = cursor.fetchone()[0]
                
                return jsonify(status)
            except Exception as e:
                logger.error(f"Error getting reports status: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/reports/team/<team>')
        def get_team_report(team):
            """Generate team-specific report"""
            if not self.report_generator:
                return jsonify({'error': 'Reporting not available'}), 503
            
            days = request.args.get('days', 30, type=int)
            try:
                report = self.report_generator.generate_team_report(team, days=days)
                return jsonify(report)
            except Exception as e:
                logger.error(f"Error generating team report: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/reports/forecast')
        def get_cost_forecast():
            """Generate cost forecast"""
            if not self.report_generator:
                return jsonify({'error': 'Reporting not available'}), 503
            
            days_ahead = request.args.get('days', 90, type=int)
            try:
                forecast = self.report_generator.generate_cost_forecast(days_ahead=days_ahead)
                return jsonify(forecast)
            except Exception as e:
                logger.error(f"Error generating forecast: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/reports/roi')
        def get_roi_report():
            """Generate ROI report"""
            if not self.report_generator:
                return jsonify({'error': 'Reporting not available'}), 503
            
            try:
                report = self.report_generator.generate_roi_report()
                return jsonify(report)
            except Exception as e:
                logger.error(f"Error generating ROI report: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/reports/trends')
        def get_trend_analysis():
            """Generate trend analysis report"""
            if not self.report_generator:
                return jsonify({'error': 'Reporting not available'}), 503
            
            days = request.args.get('days', 30, type=int)
            try:
                trends = self.report_generator.generate_trend_analysis(days=days)
                return jsonify(trends)
            except Exception as e:
                logger.error(f"Error generating trend analysis: {e}")
                return jsonify({'error': str(e)}), 500
        
        # Setup advanced prediction routes
        self._setup_advanced_prediction_routes()
        
        # Setup pre-scale management routes
        self._setup_prescale_routes()
    
    def _analyze_hpa_behavior(self, hpa_config: dict, pattern: str, 
                               events_24h: int, events_1h: int, 
                               recent_metrics: list) -> dict:
        """
        Analyze HPA behavior config and generate safety recommendations.
        """
        issues = []
        recommendations = []
        risk_level = 'low'
        
        target_cpu = hpa_config.get('target_cpu_percent', 70)
        scale_up = hpa_config['behavior'].get('scale_up')
        scale_down = hpa_config['behavior'].get('scale_down')
        
        # Check for flapping
        if events_1h > 5:
            issues.append({
                'type': 'flapping',
                'severity': 'high',
                'message': f'High scaling frequency: {events_1h} events in last hour'
            })
            risk_level = 'high'
        elif events_24h > 20:
            issues.append({
                'type': 'flapping',
                'severity': 'medium',
                'message': f'Elevated scaling frequency: {events_24h} events in 24h'
            })
            risk_level = 'medium'
        
        # Analyze scale-up behavior
        if scale_up:
            stabilization = scale_up.get('stabilization_window_seconds', 0)
            
            # Check if stabilization is too low for pattern
            if pattern in ['steady', 'periodic'] and stabilization < 60:
                issues.append({
                    'type': 'scale_up_too_fast',
                    'severity': 'medium',
                    'message': f'Scale-up stabilization ({stabilization}s) is low for {pattern} pattern'
                })
                recommendations.append({
                    'type': 'increase_scale_up_stabilization',
                    'current': stabilization,
                    'recommended': 60,
                    'reason': f'{pattern} patterns benefit from 60s+ stabilization to avoid reacting to noise'
                })
            
            # Check policies
            if scale_up.get('policies'):
                for policy in scale_up['policies']:
                    if policy['type'] == 'Percent' and policy['value'] > 100:
                        if pattern not in ['bursty', 'event_driven']:
                            issues.append({
                                'type': 'aggressive_scale_up',
                                'severity': 'low',
                                'message': f'Scale-up policy allows {policy["value"]}% increase per {policy["period_seconds"]}s'
                            })
        else:
            # No scale-up behavior configured
            recommendations.append({
                'type': 'add_scale_up_behavior',
                'current': None,
                'recommended': {
                    'stabilization_window_seconds': 60 if pattern in ['bursty', 'event_driven'] else 120,
                    'policies': [{'type': 'Percent', 'value': 100, 'period_seconds': 60}],
                    'select_policy': 'Max'
                },
                'reason': 'Adding scale-up behavior prevents over-provisioning during traffic spikes'
            })
        
        # Analyze scale-down behavior
        if scale_down:
            stabilization = scale_down.get('stabilization_window_seconds', 0)
            
            # Check if stabilization is too low
            if stabilization < 300:
                issues.append({
                    'type': 'scale_down_too_fast',
                    'severity': 'high' if stabilization < 60 else 'medium',
                    'message': f'Scale-down stabilization ({stabilization}s) is too low, risk of flapping'
                })
                recommendations.append({
                    'type': 'increase_scale_down_stabilization',
                    'current': stabilization,
                    'recommended': 300,
                    'reason': '5 minute stabilization prevents premature scale-down during temporary traffic dips'
                })
                if risk_level == 'low':
                    risk_level = 'medium'
            
            # Check policies
            if scale_down.get('policies'):
                for policy in scale_down['policies']:
                    if policy['type'] == 'Percent' and policy['value'] > 20:
                        issues.append({
                            'type': 'aggressive_scale_down',
                            'severity': 'medium',
                            'message': f'Scale-down allows {policy["value"]}% decrease per {policy["period_seconds"]}s'
                        })
                        recommendations.append({
                            'type': 'reduce_scale_down_rate',
                            'current': policy['value'],
                            'recommended': 10,
                            'reason': 'Slower scale-down (10% per minute) prevents capacity loss during traffic fluctuations'
                        })
        else:
            # No scale-down behavior configured - this is risky!
            issues.append({
                'type': 'no_scale_down_behavior',
                'severity': 'high',
                'message': 'No scale-down behavior configured - using K8s defaults which can cause flapping'
            })
            recommendations.append({
                'type': 'add_scale_down_behavior',
                'current': None,
                'recommended': {
                    'stabilization_window_seconds': 300,
                    'policies': [
                        {'type': 'Pods', 'value': 1, 'period_seconds': 60},
                        {'type': 'Percent', 'value': 10, 'period_seconds': 60}
                    ],
                    'select_policy': 'Min'
                },
                'reason': 'Conservative scale-down behavior prevents flapping and maintains capacity'
            })
            risk_level = 'high'
        
        # Check HPA target vs CPU request
        if recent_metrics:
            avg_cpu_request = sum(m.cpu_request for m in recent_metrics) / len(recent_metrics)
            if avg_cpu_request <= 150 and target_cpu < 75:
                issues.append({
                    'type': 'low_target_low_cpu',
                    'severity': 'medium',
                    'message': f'Low CPU request ({avg_cpu_request:.0f}m) with low HPA target ({target_cpu}%) causes frequent scaling'
                })
                recommendations.append({
                    'type': 'increase_hpa_target',
                    'current': target_cpu,
                    'recommended': 80,
                    'reason': 'Low CPU requests need higher HPA targets (80%+) to avoid scaling on small fluctuations'
                })
        
        # Generate YAML snippet for recommended config
        yaml_snippet = self._generate_hpa_behavior_yaml(recommendations, hpa_config)
        
        return {
            'risk_level': risk_level,
            'issues': issues,
            'recommendations': recommendations,
            'yaml_snippet': yaml_snippet,
            'summary': self._generate_analysis_summary(risk_level, issues, recommendations)
        }
    
    def _generate_hpa_behavior_yaml(self, recommendations: list, current_config: dict) -> str:
        """Generate YAML snippet for recommended HPA behavior config."""
        
        # Start with current or default values
        scale_up_stab = 60
        scale_up_policies = [{'type': 'Percent', 'value': 100, 'period_seconds': 60}]
        scale_down_stab = 300
        scale_down_policies = [
            {'type': 'Pods', 'value': 1, 'period_seconds': 60},
            {'type': 'Percent', 'value': 10, 'period_seconds': 60}
        ]
        
        # Apply recommendations
        for rec in recommendations:
            if rec['type'] == 'increase_scale_up_stabilization':
                scale_up_stab = rec['recommended']
            elif rec['type'] == 'increase_scale_down_stabilization':
                scale_down_stab = rec['recommended']
            elif rec['type'] == 'add_scale_up_behavior' and rec['recommended']:
                scale_up_stab = rec['recommended'].get('stabilization_window_seconds', 60)
                scale_up_policies = rec['recommended'].get('policies', scale_up_policies)
            elif rec['type'] == 'add_scale_down_behavior' and rec['recommended']:
                scale_down_stab = rec['recommended'].get('stabilization_window_seconds', 300)
                scale_down_policies = rec['recommended'].get('policies', scale_down_policies)
        
        yaml = f"""# Recommended HPA behavior config for safe scaling
behavior:
  scaleUp:
    stabilizationWindowSeconds: {scale_up_stab}
    policies:"""
        
        for p in scale_up_policies:
            yaml += f"""
    - type: {p['type']}
      value: {p['value']}
      periodSeconds: {p['period_seconds']}"""
        
        yaml += f"""
    selectPolicy: Max
  scaleDown:
    stabilizationWindowSeconds: {scale_down_stab}
    policies:"""
        
        for p in scale_down_policies:
            yaml += f"""
    - type: {p['type']}
      value: {p['value']}
      periodSeconds: {p['period_seconds']}"""
        
        yaml += """
    selectPolicy: Min"""
        
        return yaml
    
    def _generate_analysis_summary(self, risk_level: str, issues: list, recommendations: list) -> str:
        """Generate human-readable summary of the analysis."""
        
        if risk_level == 'low' and not issues:
            return "✅ HPA behavior is well-configured for safe scaling."
        
        summary_parts = []
        
        if risk_level == 'high':
            summary_parts.append("🔴 HIGH RISK: HPA configuration may cause scaling instability.")
        elif risk_level == 'medium':
            summary_parts.append("🟡 MEDIUM RISK: HPA configuration could be improved.")
        
        if any(i['type'] == 'flapping' for i in issues):
            summary_parts.append("Frequent scaling detected - consider increasing stabilization windows.")
        
        if any(i['type'] == 'no_scale_down_behavior' for i in issues):
            summary_parts.append("Missing scale-down behavior - add to prevent flapping.")
        
        if any(i['type'] == 'low_target_low_cpu' for i in issues):
            summary_parts.append("Low CPU request with low HPA target - raise target to 80%+.")
        
        if recommendations:
            summary_parts.append(f"{len(recommendations)} recommendation(s) available.")
        
        return " ".join(summary_parts)
    
    def _setup_advanced_prediction_routes(self):
        """Setup advanced prediction API routes"""
        
        @self.app.route('/api/predictions/advanced/<deployment>')
        def get_advanced_predictions(deployment):
            """
            Get advanced ML predictions for a deployment.
            
            Returns predictions from multiple models with confidence intervals.
            """
            if not self.advanced_predictor:
                return jsonify({'error': 'Advanced predictor not available'}), 503
            
            try:
                summary = self.advanced_predictor.get_prediction_summary(deployment)
                return jsonify(summary)
            except Exception as e:
                logger.error(f"Error getting advanced predictions: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/predictions/advanced/<deployment>/<window>')
        def get_prediction_for_window(deployment, window):
            """
            Get prediction for a specific time window.
            
            Windows: 15min, 30min, 1hr, 2hr, 4hr
            """
            if not self.advanced_predictor:
                return jsonify({'error': 'Advanced predictor not available'}), 503
            
            valid_windows = ['15min', '30min', '1hr', '2hr', '4hr']
            if window not in valid_windows:
                return jsonify({'error': f'Invalid window. Use: {valid_windows}'}), 400
            
            try:
                result = self.advanced_predictor.predict(deployment, window)
                return jsonify({
                    'deployment': deployment,
                    'window': window,
                    'predicted_value': round(result.predicted_value, 2),
                    'confidence': round(result.confidence * 100, 1),
                    'lower_bound': round(result.lower_bound, 2),
                    'upper_bound': round(result.upper_bound, 2),
                    'model_used': result.model_used,
                    'reasoning': result.reasoning,
                    'components': result.components
                })
            except Exception as e:
                logger.error(f"Error getting prediction: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/predictions/models/<deployment>')
        def get_model_performance(deployment):
            """
            Get model performance statistics for a deployment.
            
            Shows which prediction models work best for this workload.
            """
            if not self.advanced_predictor:
                return jsonify({'error': 'Advanced predictor not available'}), 503
            
            try:
                perf = self.advanced_predictor.get_model_performance(deployment)
                best_model = self.advanced_predictor.get_best_model(deployment)
                
                return jsonify({
                    'deployment': deployment,
                    'model_performance': perf,
                    'best_model': best_model,
                    'available_models': ['mean', 'trend', 'seasonal', 'holt_winters', 'arima', 'prophet_like', 'ensemble']
                })
            except Exception as e:
                logger.error(f"Error getting model performance: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/predictions/scaling-recommendation/<deployment>')
        def get_scaling_recommendation(deployment):
            """
            Get predictive scaling recommendation.
            
            Returns recommended HPA target adjustments based on predictions.
            """
            if not self.predictive_scaler:
                return jsonify({'error': 'Predictive scaler not available'}), 503
            
            try:
                # Get current CPU and HPA target
                current_cpu = 50.0  # Default
                current_hpa_target = 70.0  # Default
                
                # Try to get actual values from operator
                if hasattr(self.operator, 'deployments'):
                    for dep_config in self.operator.deployments:
                        if dep_config.get('deployment') == deployment:
                            # Get current metrics
                            metrics = self.db.get_recent_metrics(deployment, hours=1)
                            if metrics:
                                current_cpu = metrics[-1].pod_cpu_usage * 100
                                current_hpa_target = metrics[-1].hpa_target or 70.0
                            break
                
                recommendation = self.predictive_scaler.get_scaling_recommendation(
                    deployment, current_cpu, current_hpa_target
                )
                
                return jsonify({
                    'deployment': deployment,
                    'current_cpu': round(current_cpu, 1),
                    'current_hpa_target': round(current_hpa_target, 1),
                    **recommendation
                })
            except Exception as e:
                logger.error(f"Error getting scaling recommendation: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/predictions/validate', methods=['POST'])
        def validate_prediction():
            """
            Validate a prediction with actual value.
            
            Body: {deployment, predicted, actual, model}
            """
            if not self.advanced_predictor:
                return jsonify({'error': 'Advanced predictor not available'}), 503
            
            try:
                data = request.get_json()
                deployment = data.get('deployment')
                predicted = data.get('predicted')
                actual = data.get('actual')
                model = data.get('model', 'unknown')
                
                if not all([deployment, predicted is not None, actual is not None]):
                    return jsonify({'error': 'Missing required fields'}), 400
                
                self.advanced_predictor.validate_prediction(deployment, predicted, actual, model)
                
                return jsonify({
                    'status': 'validated',
                    'deployment': deployment,
                    'error_percent': abs(predicted - actual) / actual * 100 if actual > 0 else 0
                })
            except Exception as e:
                logger.error(f"Error validating prediction: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/predictions/should-enable/<deployment>')
        def should_enable_predictive(deployment):
            """
            Check if predictive scaling should be enabled for a deployment.
            
            Based on historical prediction accuracy.
            """
            if not self.predictive_scaler:
                return jsonify({'error': 'Predictive scaler not available'}), 503
            
            try:
                should_enable, reason = self.predictive_scaler.should_enable_predictive(deployment)
                
                return jsonify({
                    'deployment': deployment,
                    'should_enable': should_enable,
                    'reason': reason
                })
            except Exception as e:
                logger.error(f"Error checking predictive status: {e}")
                return jsonify({'error': str(e)}), 500
    
    def _setup_prescale_routes(self):
        """Setup pre-scale management API routes"""
        
        @self.app.route('/api/prescale/summary')
        def get_prescale_summary():
            """
            Get summary of all pre-scale states.
            
            Returns overview of pre-scaling across all deployments.
            """
            if not hasattr(self.operator, 'prescale_manager'):
                return jsonify({'error': 'Pre-scale manager not available'}), 503
            
            try:
                summary = self.operator.prescale_manager.get_summary()
                return jsonify(summary)
            except Exception as e:
                logger.error(f"Error getting pre-scale summary: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/prescale/profiles')
        def get_prescale_profiles():
            """
            Get all pre-scale profiles.
            
            Returns detailed state for each registered deployment.
            """
            if not hasattr(self.operator, 'prescale_manager'):
                return jsonify({'error': 'Pre-scale manager not available'}), 503
            
            try:
                profiles = self.operator.prescale_manager.get_all_profiles()
                return jsonify({
                    'profiles': [p.to_dict() for p in profiles],
                    'count': len(profiles)
                })
            except Exception as e:
                logger.error(f"Error getting pre-scale profiles: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/prescale/<namespace>/<deployment>')
        def get_prescale_profile(namespace, deployment):
            """
            Get pre-scale profile for a specific deployment.
            
            Shows original minReplicas, current state, and prediction info.
            """
            if not hasattr(self.operator, 'prescale_manager'):
                return jsonify({'error': 'Pre-scale manager not available'}), 503
            
            try:
                profile = self.operator.prescale_manager.get_profile(namespace, deployment)
                if not profile:
                    return jsonify({'error': 'Deployment not registered for pre-scaling'}), 404
                
                return jsonify(profile.to_dict())
            except Exception as e:
                logger.error(f"Error getting pre-scale profile: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/prescale/<namespace>/<deployment>/force', methods=['POST'])
        def force_prescale(namespace, deployment):
            """
            Force pre-scale a deployment.
            
            Body: {new_min_replicas: int, reason: str (optional)}
            """
            if not hasattr(self.operator, 'prescale_manager'):
                return jsonify({'error': 'Pre-scale manager not available'}), 503
            
            try:
                data = request.get_json() or {}
                new_min_replicas = data.get('new_min_replicas')
                reason = data.get('reason', 'Manual pre-scale via API')
                
                if not new_min_replicas:
                    return jsonify({'error': 'new_min_replicas is required'}), 400
                
                result = self.operator.prescale_manager.force_prescale(
                    namespace, deployment, int(new_min_replicas), reason
                )
                
                return jsonify(result)
            except Exception as e:
                logger.error(f"Error forcing pre-scale: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/prescale/<namespace>/<deployment>/rollback', methods=['POST'])
        def force_rollback(namespace, deployment):
            """
            Force rollback a deployment to original minReplicas.
            """
            if not hasattr(self.operator, 'prescale_manager'):
                return jsonify({'error': 'Pre-scale manager not available'}), 503
            
            try:
                result = self.operator.prescale_manager.force_rollback(namespace, deployment)
                return jsonify(result)
            except Exception as e:
                logger.error(f"Error forcing rollback: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/prescale/<namespace>/<deployment>/register', methods=['POST'])
        def register_for_prescale(namespace, deployment):
            """
            Register a deployment for pre-scaling.
            
            Body: {hpa_name: str}
            """
            if not hasattr(self.operator, 'prescale_manager'):
                return jsonify({'error': 'Pre-scale manager not available'}), 503
            
            try:
                data = request.get_json() or {}
                hpa_name = data.get('hpa_name', deployment)
                
                profile = self.operator.prescale_manager.register_deployment(
                    namespace, deployment, hpa_name
                )
                
                if profile:
                    return jsonify({
                        'status': 'registered',
                        'profile': profile.to_dict()
                    })
                else:
                    return jsonify({'error': 'Failed to register deployment'}), 500
            except Exception as e:
                logger.error(f"Error registering for pre-scale: {e}")
                return jsonify({'error': str(e)}), 500
        
        # ============================================
        # Autopilot API Endpoints
        # ============================================
        
        @self.app.route('/api/autopilot/status')
        def get_autopilot_status():
            """
            Get autopilot status and configuration.
            
            Returns:
                - enabled: bool
                - level: str (DISABLED, OBSERVE, RECOMMEND, AUTOPILOT)
                - config: dict of configuration values
                - statistics: dict of action counts and savings
            """
            if not hasattr(self.operator, 'autopilot_manager'):
                return jsonify({'error': 'Autopilot not available'}), 503
            
            try:
                status = self.operator.autopilot_manager.get_status()
                return jsonify(status)
            except Exception as e:
                logger.error(f"Error getting autopilot status: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/autopilot/deployment/<namespace>/<deployment>')
        def get_autopilot_deployment_status(namespace, deployment):
            """
            Get autopilot status for a specific deployment.
            
            Returns:
                - enabled: bool (whether autopilot is enabled for this deployment)
                - annotation: str (the annotation value if set)
                - has_recommendation: bool
                - recommendation: dict (if available)
            """
            if not hasattr(self.operator, 'autopilot_manager'):
                return jsonify({'enabled': False, 'reason': 'Autopilot not available'})
            
            try:
                am = self.operator.autopilot_manager
                
                # Check if globally enabled
                if not am.enabled:
                    return jsonify({
                        'enabled': False,
                        'reason': 'Autopilot globally disabled',
                        'annotation': None,
                        'has_recommendation': False
                    })
                
                # Check deployment-specific status
                is_enabled = am.is_enabled_for_deployment(namespace, deployment)
                
                # Get recommendation if exists
                key = f"{namespace}/{deployment}"
                recommendation = am.recommendations.get(key)
                
                return jsonify({
                    'enabled': is_enabled,
                    'reason': 'Enabled via annotation' if is_enabled else 'Not enabled',
                    'has_recommendation': recommendation is not None,
                    'recommendation': {
                        'cpu': f"{recommendation.current_cpu_request}m → {recommendation.recommended_cpu_request}m",
                        'memory': f"{recommendation.current_memory_request}Mi → {recommendation.recommended_memory_request}Mi",
                        'confidence': recommendation.confidence,
                        'is_safe': recommendation.is_safe
                    } if recommendation else None
                })
            except Exception as e:
                logger.debug(f"Error getting autopilot deployment status: {e}")
                return jsonify({'enabled': False, 'reason': str(e)})
        
        @self.app.route('/api/autopilot/recommendations')
        def get_autopilot_recommendations():
            """
            Get all current autopilot recommendations.
            
            Query params:
                namespace: Filter by namespace (optional)
            
            Returns list of recommendations with:
                - current/recommended CPU and memory requests
                - P95 usage values
                - confidence score
                - safety status
            """
            if not hasattr(self.operator, 'autopilot_manager'):
                return jsonify({'error': 'Autopilot not available'}), 503
            
            try:
                namespace = request.args.get('namespace')
                recommendations = self.operator.autopilot_manager.get_recommendations(namespace)
                return jsonify({
                    'recommendations': recommendations,
                    'count': len(recommendations)
                })
            except Exception as e:
                logger.error(f"Error getting autopilot recommendations: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/autopilot/actions')
        def get_autopilot_actions():
            """
            Get recent autopilot actions (applied changes).
            
            Query params:
                namespace: Filter by namespace (optional)
                deployment: Filter by deployment (optional)
                limit: Max number of actions (default: 50)
            
            Returns list of actions with:
                - action_type: cpu_request, memory_request, rollback
                - old_value, new_value
                - reason, applied_at
                - rolled_back status
            """
            if not hasattr(self.operator, 'autopilot_manager'):
                return jsonify({'error': 'Autopilot not available'}), 503
            
            try:
                namespace = request.args.get('namespace')
                deployment = request.args.get('deployment')
                limit = request.args.get('limit', 50, type=int)
                
                actions = self.operator.autopilot_manager.get_recent_actions(
                    namespace=namespace,
                    deployment=deployment,
                    limit=limit
                )
                return jsonify({
                    'actions': actions,
                    'count': len(actions)
                })
            except Exception as e:
                logger.error(f"Error getting autopilot actions: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/autopilot/<namespace>/<deployment>/apply', methods=['POST'])
        def apply_autopilot_recommendation(namespace, deployment):
            """
            Manually apply an autopilot recommendation.
            
            This allows applying a recommendation even when autopilot level
            is set to RECOMMEND (not AUTOPILOT).
            
            Body: {dry_run: bool} (optional, default: false)
            """
            if not hasattr(self.operator, 'autopilot_manager'):
                return jsonify({'error': 'Autopilot not available'}), 503
            
            try:
                data = request.get_json() or {}
                dry_run = data.get('dry_run', False)
                
                key = f"{namespace}/{deployment}"
                recommendation = self.operator.autopilot_manager.recommendations.get(key)
                
                if not recommendation:
                    return jsonify({'error': 'No recommendation found for this deployment'}), 404
                
                # Temporarily enable autopilot level for manual apply
                original_level = self.operator.autopilot_manager.level
                from src.autopilot import AutopilotLevel
                self.operator.autopilot_manager.level = AutopilotLevel.AUTOPILOT
                
                try:
                    applied = self.operator.autopilot_manager.apply_recommendation(
                        recommendation, dry_run=dry_run
                    )
                finally:
                    self.operator.autopilot_manager.level = original_level
                
                if applied:
                    return jsonify({
                        'status': 'applied' if not dry_run else 'dry_run',
                        'recommendation': {
                            'cpu_request': f"{recommendation.current_cpu_request}m → {recommendation.recommended_cpu_request}m",
                            'memory_request': f"{recommendation.current_memory_request}Mi → {recommendation.recommended_memory_request}Mi",
                            'savings_percent': recommendation.savings_percent
                        }
                    })
                else:
                    return jsonify({
                        'status': 'not_applied',
                        'reason': recommendation.safety_reason or 'Safety check failed'
                    }), 400
            except Exception as e:
                logger.error(f"Error applying autopilot recommendation: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/autopilot/<namespace>/<deployment>/rollback', methods=['POST'])
        def rollback_autopilot(namespace, deployment):
            """
            Rollback the last autopilot action for a deployment.
            
            Body: {reason: str} (optional)
            """
            if not hasattr(self.operator, 'autopilot_manager'):
                return jsonify({'error': 'Autopilot not available'}), 503
            
            try:
                data = request.get_json() or {}
                reason = data.get('reason', 'Manual rollback via API')
                
                success = self.operator.autopilot_manager.rollback_action(
                    namespace, deployment, reason
                )
                
                if success:
                    return jsonify({
                        'status': 'rolled_back',
                        'reason': reason
                    })
                else:
                    return jsonify({
                        'status': 'no_action',
                        'message': 'No actions to rollback'
                    }), 404
            except Exception as e:
                logger.error(f"Error rolling back autopilot: {e}")
                return jsonify({'error': str(e)}), 500
    
    def _detect_cloud_provider_info(self, nodes: list) -> dict:
        """Detect cloud provider from node information"""
        try:
            # Try to use CloudPricingDetector if available
            if hasattr(self.operator, 'cost_allocator') and self.operator.cost_allocator:
                if hasattr(self.operator.cost_allocator, 'pricing_detector'):
                    detector = self.operator.cost_allocator.pricing_detector
                    if detector and detector.detected_provider:
                        region = detector.detect_region() if hasattr(detector, 'detect_region') else None
                        region_name = detector.get_region_display_name(
                            detector.detected_provider, region
                        ) if region else 'Unknown'
                        
                        return {
                            'provider': detector.detected_provider.upper(),
                            'region': region or 'Unknown',
                            'region_name': region_name,
                            'display': f"{detector.detected_provider.upper()} ({region_name})",
                            'detected': True
                        }
            
            # Fallback: Try to detect from node names
            if nodes:
                for node in nodes:
                    node_name = node.get('name', '').lower()
                    
                    # GKE nodes typically have 'gke-' prefix
                    if 'gke-' in node_name:
                        return {
                            'provider': 'GCP',
                            'region': 'Unknown',
                            'region_name': 'Unknown',
                            'display': 'GCP (GKE)',
                            'detected': True
                        }
                    
                    # EKS nodes typically have 'ip-' prefix or 'eks' in name
                    if node_name.startswith('ip-') or 'eks' in node_name:
                        return {
                            'provider': 'AWS',
                            'region': 'Unknown',
                            'region_name': 'Unknown',
                            'display': 'AWS (EKS)',
                            'detected': True
                        }
                    
                    # AKS nodes typically have 'aks-' prefix
                    if 'aks-' in node_name:
                        return {
                            'provider': 'Azure',
                            'region': 'Unknown',
                            'region_name': 'Unknown',
                            'display': 'Azure (AKS)',
                            'detected': True
                        }
                    
                    # OrbStack (local development)
                    if 'orbstack' in node_name:
                        return {
                            'provider': 'Local',
                            'region': 'N/A',
                            'region_name': 'OrbStack',
                            'display': 'Local (OrbStack)',
                            'detected': True
                        }
                    
                    # Minikube
                    if 'minikube' in node_name:
                        return {
                            'provider': 'Local',
                            'region': 'N/A',
                            'region_name': 'Minikube',
                            'display': 'Local (Minikube)',
                            'detected': True
                        }
                    
                    # Kind
                    if 'kind' in node_name:
                        return {
                            'provider': 'Local',
                            'region': 'N/A',
                            'region_name': 'Kind',
                            'display': 'Local (Kind)',
                            'detected': True
                        }
            
            # Default: On-premise
            return {
                'provider': 'On-Premise',
                'region': 'N/A',
                'region_name': 'N/A',
                'display': 'On-Premise / Unknown',
                'detected': False
            }
            
        except Exception as e:
            logger.warning(f"Failed to detect cloud provider: {e}")
            return {
                'provider': 'Unknown',
                'region': 'N/A',
                'region_name': 'N/A',
                'display': 'On-Premise / Unknown',
                'detected': False
            }
    
    def _get_kubernetes_version(self) -> dict:
        """Get Kubernetes cluster version information"""
        try:
            from kubernetes import client, config
            
            # Try to load config
            try:
                config.load_incluster_config()
            except:
                try:
                    config.load_kube_config()
                except:
                    return {
                        'version': 'Unknown',
                        'git_version': 'Unknown',
                        'platform': 'Unknown',
                        'detected': False
                    }
            
            # Get version info from API
            version_api = client.VersionApi()
            version_info = version_api.get_code()
            
            return {
                'version': f"{version_info.major}.{version_info.minor}",
                'git_version': version_info.git_version,
                'platform': version_info.platform,
                'go_version': version_info.go_version,
                'build_date': version_info.build_date,
                'detected': True
            }
            
        except Exception as e:
            logger.warning(f"Failed to get Kubernetes version: {e}")
            return {
                'version': 'Unknown',
                'git_version': 'Unknown',
                'platform': 'Unknown',
                'detected': False
            }
    
    def start(self):
        """Start dashboard server"""
        logger.info(f"Starting web dashboard on port {self.port}")
        self.app.run(host='0.0.0.0', port=self.port, threaded=True)