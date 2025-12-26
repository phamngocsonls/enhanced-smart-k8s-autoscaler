"""
Web Dashboard UI
Real-time monitoring and control interface
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
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
        self.app = Flask(__name__)
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
                recent_anomalies = cursor.fetchone()[0]
                
                # Get predictions accuracy
                cursor = self.db.conn.execute("""
                    SELECT AVG(confidence) FROM predictions
                    WHERE timestamp >= datetime('now', '-7 days')
                """)
                avg_prediction_confidence = cursor.fetchone()[0] or 0
                
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


# HTML Template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Autoscaler Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: transform 0.3s ease;
        }
        .stat-card:hover { transform: translateY(-5px); }
        .stat-label {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .stat-value {
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }
        .stat-value.cost { color: #f59e0b; }
        .stat-value.savings { color: #10b981; }
        .stat-value.anomalies { color: #ef4444; }
        .deployments-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
        }
        .deployment-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .deployment-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }
        .deployment-name {
            font-size: 1.3em;
            font-weight: bold;
            color: #667eea;
        }
        .status-badge {
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: bold;
        }
        .status-healthy { background: #d1fae5; color: #065f46; }
        .status-warning { background: #fef3c7; color: #92400e; }
        .status-critical { background: #fee2e2; color: #991b1b; }
        .metric-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #f0f0f0;
        }
        .metric-label { color: #666; }
        .metric-value { font-weight: bold; }
        .chart-container {
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-top: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .loading {
            text-align: center;
            color: white;
            font-size: 1.5em;
            margin: 50px 0;
        }
        .refresh-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #667eea;
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 50px;
            font-size: 1em;
            cursor: pointer;
            box-shadow: 0 5px 20px rgba(0,0,0,0.3);
            transition: all 0.3s ease;
        }
        .refresh-btn:hover {
            background: #5568d3;
            transform: scale(1.05);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Smart Autoscaler Dashboard</h1>
        
        <div class="stats-grid" id="overview">
            <div class="stat-card">
                <div class="stat-label">Total Deployments</div>
                <div class="stat-value" id="total-deployments">-</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Monthly Cost</div>
                <div class="stat-value cost" id="total-cost">$-</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Savings Potential</div>
                <div class="stat-value savings" id="total-savings">$-</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Anomalies (24h)</div>
                <div class="stat-value anomalies" id="recent-anomalies">-</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Efficiency Score</div>
                <div class="stat-value" id="efficiency-score">-%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Prediction Confidence</div>
                <div class="stat-value" id="prediction-confidence">-%</div>
            </div>
        </div>

        <div class="deployments-grid" id="deployments"></div>
    </div>

    <button class="refresh-btn" onclick="loadData()">🔄 Refresh</button>

    <script>
        async function loadData() {
            try {
                // Load overview
                const overview = await fetch('/api/overview').then(r => r.json());
                document.getElementById('total-deployments').textContent = overview.total_deployments;
                document.getElementById('total-cost').textContent = '$' + overview.total_monthly_cost.toFixed(2);
                document.getElementById('total-savings').textContent = '$' + overview.total_savings_potential.toFixed(2);
                document.getElementById('recent-anomalies').textContent = overview.recent_anomalies_24h;
                document.getElementById('efficiency-score').textContent = overview.efficiency_score + '%';
                document.getElementById('prediction-confidence').textContent = (overview.avg_prediction_confidence * 100).toFixed(0) + '%';

                // Load deployments
                const deployments = await fetch('/api/deployments').then(r => r.json());
                const container = document.getElementById('deployments');
                container.innerHTML = '';

                for (const dep of deployments) {
                    const card = await createDeploymentCard(dep);
                    container.appendChild(card);
                }
            } catch (error) {
                console.error('Error loading data:', error);
            }
        }

        async function createDeploymentCard(deployment) {
            const card = document.createElement('div');
            card.className = 'deployment-card';

            try {
                const current = await fetch(`/api/deployment/${deployment.namespace}/${deployment.deployment}/current`).then(r => r.json());
                const cost = await fetch(`/api/deployment/${deployment.namespace}/${deployment.deployment}/cost`).then(r => r.json());

                const status = current.node_utilization > 80 ? 'critical' : 
                              current.node_utilization > 65 ? 'warning' : 'healthy';
                
                card.innerHTML = `
                    <div class="deployment-header">
                        <div class="deployment-name">${deployment.deployment}</div>
                        <div class="status-badge status-${status}">${status.toUpperCase()}</div>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Node CPU</span>
                        <span class="metric-value">${current.node_utilization.toFixed(1)}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">HPA Target</span>
                        <span class="metric-value">${current.hpa_target}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Pod Count</span>
                        <span class="metric-value">${current.pod_count}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Confidence</span>
                        <span class="metric-value">${(current.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Monthly Cost</span>
                        <span class="metric-value cost">$${cost.estimated_monthly_cost.toFixed(2)}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Potential Savings</span>
                        <span class="metric-value savings">$${cost.optimization_potential.toFixed(2)}</span>
                    </div>
                `;
            } catch (error) {
                card.innerHTML = `
                    <div class="deployment-header">
                        <div class="deployment-name">${deployment.deployment}</div>
                        <div class="status-badge">NO DATA</div>
                    </div>
                    <p>Collecting data...</p>
                `;
            }

            return card;
        }

        // Auto-refresh every 60 seconds
        setInterval(loadData, 60000);
        
        // Initial load
        loadData();
    </script>
</body>
</html>
"""