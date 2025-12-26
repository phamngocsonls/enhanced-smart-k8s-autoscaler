"""
Configuration loader for Smart Autoscaler
"""
import os
import yaml
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class Config:
    def __init__(self, config_path: str = "/app/config/config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        if os.path.exists(self.config_path):
            logger.info(f"Loading config from {self.config_path}")
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        
        logger.info("Loading config from environment variables")
        return {
            'prometheus_url': os.getenv('PROMETHEUS_URL', 'http://prometheus-server.monitoring:9090'),
            'check_interval': int(os.getenv('CHECK_INTERVAL', '60')),
            'dry_run': os.getenv('DRY_RUN', 'false').lower() == 'true',
            'deployments': self._load_deployments_from_env()
        }
    
    def _load_deployments_from_env(self) -> List[Dict]:
        deployments = []
        i = 0
        while True:
            namespace = os.getenv(f'DEPLOYMENT_{i}_NAMESPACE')
            if not namespace:
                break
            
            deployment = {
                'namespace': namespace,
                'deployment': os.getenv(f'DEPLOYMENT_{i}_NAME'),
                'hpa_name': os.getenv(f'DEPLOYMENT_{i}_HPA_NAME'),
                'startup_filter_minutes': int(os.getenv(f'DEPLOYMENT_{i}_STARTUP_FILTER', '2'))
            }
            deployments.append(deployment)
            i += 1
        
        return deployments
    
    @property
    def prometheus_url(self) -> str:
        return self.config.get('prometheus_url')
    
    @property
    def check_interval(self) -> int:
        return self.config.get('check_interval', 60)
    
    @property
    def dry_run(self) -> bool:
        return self.config.get('dry_run', False)
    
    @property
    def deployments(self) -> List[Dict]:
        return self.config.get('deployments', [])
