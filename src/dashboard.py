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
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            """Main dashboard page"""
            return render_template('dashboard.html')
        
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
            """Get predictions for deployment"""
            try:
                cursor = self.db.conn.execute("""
                    SELECT timestamp, predicted_cpu, confidence, 
                           recommended_action, reasoning
                    FROM predictions
                    WHERE deployment = ?
                    ORDER BY timestamp DESC
                    LIMIT 100
                """, (deployment,))
                
                predictions = []
                for row in cursor.fetchall():
                    predictions.append({
                        'timestamp': row[0],
                        'predicted_cpu': row[1],
                        'confidence': row[2],
                        'action': row[3],
                        'reasoning': row[4]
                    })
                
                return jsonify(predictions)
            except Exception as e:
                logger.error(f"Error getting predictions: {e}")
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
            """Get cost metrics for deployment"""
            try:
                cost_metrics = self.operator.cost_optimizer.analyze_costs(deployment)
                
                if not cost_metrics:
                    return jsonify({'error': 'No cost data'}), 404
                
                return jsonify({
                    'avg_pod_count': cost_metrics.avg_pod_count,
                    'avg_utilization': cost_metrics.avg_utilization,
                    'wasted_capacity_percent': cost_metrics.wasted_capacity_percent,
                    'estimated_monthly_cost': cost_metrics.estimated_monthly_cost,
                    'optimization_potential': cost_metrics.optimization_potential,
                    'recommendation': cost_metrics.recommendation
                })
            except Exception as e:
                logger.error(f"Error getting cost metrics: {e}")
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
        
        @self.app.route('/api/health')
        def health_check():
            """Health check endpoint"""
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'database': 'connected' if self.db.conn else 'disconnected'
            })
    
    def start(self):
        """Start dashboard server"""
        logger.info(f"Starting web dashboard on port {self.port}")
        self.app.run(host='0.0.0.0', port=self.port, threaded=True)