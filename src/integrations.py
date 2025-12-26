"""
Integrations with External Tools
PagerDuty, Datadog, Grafana, Jira, ServiceNow, etc.
"""

import requests
import json
from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class PagerDutyIntegration:
    """PagerDuty incident management"""
    
    def __init__(self, api_key: str, service_id: str):
        self.api_key = api_key
        self.service_id = service_id
        self.base_url = "https://api.pagerduty.com"
    
    def create_incident(self, title: str, description: str, severity: str = "warning"):
        """Create PagerDuty incident"""
        try:
            headers = {
                "Authorization": f"Token token={self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/vnd.pagerduty+json;version=2"
            }
            
            payload = {
                "incident": {
                    "type": "incident",
                    "title": title,
                    "service": {
                        "id": self.service_id,
                        "type": "service_reference"
                    },
                    "body": {
                        "type": "incident_body",
                        "details": description
                    },
                    "urgency": "high" if severity == "critical" else "low"
                }
            }
            
            response = requests.post(
                f"{self.base_url}/incidents",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 201:
                logger.info(f"PagerDuty incident created: {title}")
                return response.json()
            else:
                logger.error(f"Failed to create PagerDuty incident: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"PagerDuty integration error: {e}")
            return None


class DatadogIntegration:
    """Datadog metrics and events"""
    
    def __init__(self, api_key: str, app_key: str):
        self.api_key = api_key
        self.app_key = app_key
        self.base_url = "https://api.datadoghq.com/api/v1"
    
    def send_metric(self, metric_name: str, value: float, tags: list = None):
        """Send metric to Datadog"""
        try:
            payload = {
                "series": [{
                    "metric": f"autoscaler.{metric_name}",
                    "points": [[int(datetime.now().timestamp()), value]],
                    "tags": tags or [],
                    "type": "gauge"
                }]
            }
            
            response = requests.post(
                f"{self.base_url}/series",
                headers={"DD-API-KEY": self.api_key},
                json=payload,
                timeout=10
            )
            
            if response.status_code == 202:
                logger.debug(f"Datadog metric sent: {metric_name}={value}")
            else:
                logger.error(f"Failed to send Datadog metric: {response.text}")
                
        except Exception as e:
            logger.error(f"Datadog integration error: {e}")
    
    def send_event(self, title: str, text: str, tags: list = None, alert_type: str = "info"):
        """Send event to Datadog"""
        try:
            payload = {
                "title": title,
                "text": text,
                "tags": tags or [],
                "alert_type": alert_type,
                "source_type_name": "smart-autoscaler"
            }
            
            response = requests.post(
                f"{self.base_url}/events",
                headers={"DD-API-KEY": self.api_key},
                json=payload,
                timeout=10
            )
            
            if response.status_code == 202:
                logger.info(f"Datadog event sent: {title}")
            else:
                logger.error(f"Failed to send Datadog event: {response.text}")
                
        except Exception as e:
            logger.error(f"Datadog integration error: {e}")


class GrafanaIntegration:
    """Grafana annotations"""
    
    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip('/')
        self.api_key = api_key
    
    def create_annotation(self, dashboard_id: int, text: str, tags: list = None):
        """Create Grafana annotation"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "dashboardId": dashboard_id,
                "time": int(datetime.now().timestamp() * 1000),
                "tags": tags or ["autoscaler"],
                "text": text
            }
            
            response = requests.post(
                f"{self.url}/api/annotations",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Grafana annotation created: {text}")
            else:
                logger.error(f"Failed to create Grafana annotation: {response.text}")
                
        except Exception as e:
            logger.error(f"Grafana integration error: {e}")


class JiraIntegration:
    """Jira ticket creation"""
    
    def __init__(self, url: str, username: str, api_token: str, project_key: str):
        self.url = url.rstrip('/')
        self.auth = (username, api_token)
        self.project_key = project_key
    
    def create_issue(self, summary: str, description: str, issue_type: str = "Task"):
        """Create Jira issue"""
        try:
            payload = {
                "fields": {
                    "project": {"key": self.project_key},
                    "summary": summary,
                    "description": description,
                    "issuetype": {"name": issue_type}
                }
            }
            
            response = requests.post(
                f"{self.url}/rest/api/2/issue",
                auth=self.auth,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=10
            )
            
            if response.status_code == 201:
                issue_key = response.json().get('key')
                logger.info(f"Jira issue created: {issue_key}")
                return issue_key
            else:
                logger.error(f"Failed to create Jira issue: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Jira integration error: {e}")
            return None


class ServiceNowIntegration:
    """ServiceNow incident management"""
    
    def __init__(self, instance: str, username: str, password: str):
        self.instance = instance
        self.auth = (username, password)
        self.base_url = f"https://{instance}.service-now.com/api/now"
    
    def create_incident(self, short_description: str, description: str, 
                       urgency: int = 3, impact: int = 3):
        """Create ServiceNow incident"""
        try:
            payload = {
                "short_description": short_description,
                "description": description,
                "urgency": urgency,
                "impact": impact,
                "caller_id": "smart-autoscaler",
                "category": "Infrastructure"
            }
            
            response = requests.post(
                f"{self.base_url}/table/incident",
                auth=self.auth,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=10
            )
            
            if response.status_code == 201:
                incident_number = response.json().get('result', {}).get('number')
                logger.info(f"ServiceNow incident created: {incident_number}")
                return incident_number
            else:
                logger.error(f"Failed to create ServiceNow incident: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"ServiceNow integration error: {e}")
            return None


class OpsGenieIntegration:
    """OpsGenie alert management"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.opsgenie.com/v2"
    
    def create_alert(self, message: str, description: str, priority: str = "P3", 
                    tags: list = None):
        """Create OpsGenie alert"""
        try:
            headers = {
                "Authorization": f"GenieKey {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "message": message,
                "description": description,
                "priority": priority,
                "tags": tags or ["autoscaler"],
                "source": "Smart Autoscaler"
            }
            
            response = requests.post(
                f"{self.base_url}/alerts",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 202:
                request_id = response.json().get('requestId')
                logger.info(f"OpsGenie alert created: {request_id}")
                return request_id
            else:
                logger.error(f"Failed to create OpsGenie alert: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"OpsGenie integration error: {e}")
            return None


class ElasticsearchIntegration:
    """Elasticsearch logging"""
    
    def __init__(self, url: str, index: str = "autoscaler-logs"):
        self.url = url.rstrip('/')
        self.index = index
    
    def log_event(self, event_type: str, data: dict):
        """Log event to Elasticsearch"""
        try:
            document = {
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": event_type,
                **data
            }
            
            response = requests.post(
                f"{self.url}/{self.index}/_doc",
                headers={"Content-Type": "application/json"},
                json=document,
                timeout=10
            )
            
            if response.status_code == 201:
                logger.debug(f"Event logged to Elasticsearch: {event_type}")
            else:
                logger.error(f"Failed to log to Elasticsearch: {response.text}")
                
        except Exception as e:
            logger.error(f"Elasticsearch integration error: {e}")


class IntegrationManager:
    """Manage all integrations"""
    
    def __init__(self, config: Dict):
        self.integrations = {}
        
        # PagerDuty
        if config.get('pagerduty_api_key') and config.get('pagerduty_service_id'):
            self.integrations['pagerduty'] = PagerDutyIntegration(
                config['pagerduty_api_key'],
                config['pagerduty_service_id']
            )
            logger.info("PagerDuty integration enabled")
        
        # Datadog
        if config.get('datadog_api_key') and config.get('datadog_app_key'):
            self.integrations['datadog'] = DatadogIntegration(
                config['datadog_api_key'],
                config['datadog_app_key']
            )
            logger.info("Datadog integration enabled")
        
        # Grafana
        if config.get('grafana_url') and config.get('grafana_api_key'):
            self.integrations['grafana'] = GrafanaIntegration(
                config['grafana_url'],
                config['grafana_api_key']
            )
            logger.info("Grafana integration enabled")
        
        # Jira
        if all(k in config for k in ['jira_url', 'jira_username', 'jira_api_token', 'jira_project_key']):
            self.integrations['jira'] = JiraIntegration(
                config['jira_url'],
                config['jira_username'],
                config['jira_api_token'],
                config['jira_project_key']
            )
            logger.info("Jira integration enabled")
        
        # ServiceNow
        if all(k in config for k in ['servicenow_instance', 'servicenow_username', 'servicenow_password']):
            self.integrations['servicenow'] = ServiceNowIntegration(
                config['servicenow_instance'],
                config['servicenow_username'],
                config['servicenow_password']
            )
            logger.info("ServiceNow integration enabled")
        
        # OpsGenie
        if config.get('opsgenie_api_key'):
            self.integrations['opsgenie'] = OpsGenieIntegration(
                config['opsgenie_api_key']
            )
            logger.info("OpsGenie integration enabled")
        
        # Elasticsearch
        if config.get('elasticsearch_url'):
            self.integrations['elasticsearch'] = ElasticsearchIntegration(
                config['elasticsearch_url'],
                config.get('elasticsearch_index', 'autoscaler-logs')
            )
            logger.info("Elasticsearch integration enabled")
    
    def notify_critical_anomaly(self, deployment: str, anomaly: str, severity: str):
        """Send critical anomaly to incident management systems"""
        title = f"Critical Anomaly: {deployment}"
        description = f"Anomaly detected: {anomaly}\nSeverity: {severity}"
        
        # PagerDuty
        if 'pagerduty' in self.integrations and severity == 'critical':
            self.integrations['pagerduty'].create_incident(title, description, severity)
        
        # OpsGenie
        if 'opsgenie' in self.integrations:
            priority = "P1" if severity == "critical" else "P3"
            self.integrations['opsgenie'].create_alert(title, description, priority)
        
        # ServiceNow
        if 'servicenow' in self.integrations and severity == 'critical':
            urgency = 1 if severity == "critical" else 3
            self.integrations['servicenow'].create_incident(title, description, urgency, urgency)
    
    def log_scaling_event(self, deployment: str, action: str, details: Dict):
        """Log scaling event to monitoring systems"""
        
        # Datadog
        if 'datadog' in self.integrations:
            tags = [f"deployment:{deployment}", f"action:{action}"]
            self.integrations['datadog'].send_event(
                f"Scaling Event: {deployment}",
                f"Action: {action}\nDetails: {json.dumps(details)}",
                tags=tags,
                alert_type="info"
            )
        
        # Grafana
        if 'grafana' in self.integrations:
            self.integrations['grafana'].create_annotation(
                dashboard_id=1,  # Configure as needed
                text=f"{deployment}: {action}",
                tags=[deployment, action]
            )
        
        # Elasticsearch
        if 'elasticsearch' in self.integrations:
            self.integrations['elasticsearch'].log_event(
                'scaling_event',
                {
                    'deployment': deployment,
                    'action': action,
                    **details
                }
            )
    
    def send_metrics(self, metrics: Dict):
        """Send metrics to monitoring systems"""
        
        if 'datadog' not in self.integrations:
            return
        
        datadog = self.integrations['datadog']
        
        for deployment, data in metrics.items():
            tags = [f"deployment:{deployment}"]
            
            datadog.send_metric('node_utilization', data.get('node_utilization', 0), tags)
            datadog.send_metric('hpa_target', data.get('hpa_target', 0), tags)
            datadog.send_metric('confidence', data.get('confidence', 0), tags)
            datadog.send_metric('monthly_cost', data.get('monthly_cost', 0), tags)
    
    def create_optimization_ticket(self, deployment: str, savings: float, recommendation: str):
        """Create ticket for cost optimization opportunity"""
        
        if 'jira' not in self.integrations:
            return
        
        summary = f"Cost Optimization: {deployment} - Save ${savings:.2f}/month"
        description = f"""
Cost optimization opportunity detected:

Deployment: {deployment}
Potential Savings: ${savings:.2f}/month
Recommendation: {recommendation}

Action required: Review and implement the recommendation.
        """.strip()
        
        self.integrations['jira'].create_issue(
            summary=summary,
            description=description,
            issue_type="Task"
        )