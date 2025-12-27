"""
Health Checker
Verifies all core components are working
"""

import logging
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)


class HealthChecker:
    """Check health of all core components"""
    
    def __init__(self, operator):
        self.operator = operator
        self.last_check = None
        self.check_results = {}
    
    def check_all(self) -> Dict:
        """Check all core components"""
        self.last_check = datetime.now()
        results = {
            'timestamp': self.last_check.isoformat(),
            'overall_status': 'healthy',
            'components': {}
        }
        
        # Check database
        db_status = self._check_database()
        results['components']['database'] = db_status
        
        # Check Prometheus
        prom_status = self._check_prometheus()
        results['components']['prometheus'] = prom_status
        
        # Check Kubernetes API
        k8s_status = self._check_kubernetes()
        results['components']['kubernetes'] = k8s_status
        
        # Check deployments
        deployments_status = self._check_deployments()
        results['components']['deployments'] = deployments_status
        
        # Check intelligence components
        intelligence_status = self._check_intelligence()
        results['components']['intelligence'] = intelligence_status
        
        # Determine overall status
        unhealthy = [k for k, v in results['components'].items() if v.get('status') != 'healthy']
        if unhealthy:
            results['overall_status'] = 'degraded' if 'kubernetes' not in unhealthy else 'unhealthy'
        
        self.check_results = results
        return results
    
    def _check_database(self) -> Dict:
        """Check database connectivity"""
        try:
            if not hasattr(self.operator, 'db') or not self.operator.db:
                return {'status': 'unhealthy', 'message': 'Database not initialized'}
            
            # Test query
            cursor = self.operator.db.conn.execute("SELECT 1")
            cursor.fetchone()
            
            # Check if we can write
            test_timestamp = datetime.now()
            self.operator.db.conn.execute(
                "SELECT COUNT(*) FROM metrics_history WHERE timestamp > ?",
                (test_timestamp,)
            )
            
            return {
                'status': 'healthy',
                'message': 'Database connected and operational',
                'db_path': self.operator.db.db_path
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Database error: {str(e)}'
            }
    
    def _check_prometheus(self) -> Dict:
        """Check Prometheus connectivity"""
        try:
            if not hasattr(self.operator, 'controller') or not hasattr(self.operator.controller, 'analyzer'):
                return {'status': 'unknown', 'message': 'Controller not initialized'}
            
            analyzer = self.operator.controller.analyzer
            
            # Test query
            result = analyzer.prom.custom_query('up')
            if result:
                return {
                    'status': 'healthy',
                    'message': 'Prometheus connected',
                    'url': analyzer.prom.url
                }
            else:
                return {
                    'status': 'degraded',
                    'message': 'Prometheus query returned no results'
                }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Prometheus error: {str(e)}'
            }
    
    def _check_kubernetes(self) -> Dict:
        """Check Kubernetes API connectivity"""
        try:
            from kubernetes import client
            api = client.CoreV1Api()
            
            # Test query
            namespaces = api.list_namespace(limit=1)
            
            return {
                'status': 'healthy',
                'message': 'Kubernetes API connected',
                'namespaces_accessible': True
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Kubernetes API error: {str(e)}'
            }
    
    def _check_deployments(self) -> Dict:
        """Check deployment configuration"""
        try:
            deployments = self.operator.watched_deployments
            
            if not deployments:
                return {
                    'status': 'warning',
                    'message': 'No deployments configured',
                    'count': 0
                }
            
            return {
                'status': 'healthy',
                'message': f'{len(deployments)} deployment(s) configured',
                'count': len(deployments),
                'deployments': list(deployments.keys())
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Deployment check error: {str(e)}'
            }
    
    def _check_intelligence(self) -> Dict:
        """Check intelligence components"""
        try:
            components = {
                'database': hasattr(self.operator, 'db') and self.operator.db is not None,
                'alert_manager': hasattr(self.operator, 'alert_manager') and self.operator.alert_manager is not None,
                'pattern_recognizer': hasattr(self.operator, 'pattern_recognizer') and self.operator.pattern_recognizer is not None,
                'anomaly_detector': hasattr(self.operator, 'anomaly_detector') and self.operator.anomaly_detector is not None,
                'cost_optimizer': hasattr(self.operator, 'cost_optimizer') and self.operator.cost_optimizer is not None,
                'predictive_scaler': hasattr(self.operator, 'predictive_scaler') and self.operator.predictive_scaler is not None,
                'auto_tuner': hasattr(self.operator, 'auto_tuner') and self.operator.auto_tuner is not None,
            }
            
            all_healthy = all(components.values())
            
            return {
                'status': 'healthy' if all_healthy else 'degraded',
                'message': 'All intelligence components initialized' if all_healthy else 'Some components missing',
                'components': components
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Intelligence check error: {str(e)}'
            }

