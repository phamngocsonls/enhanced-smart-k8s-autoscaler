"""
Cost Alerting Module
Sends daily cost reports to alert channels (Slack, webhook, etc.)
"""

import logging
import threading
import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


class CostAlerting:
    """
    Daily cost report alerting.
    Sends cost summaries to configured alert channels.
    """
    
    def __init__(self, realtime_cost_tracker, operator):
        self.realtime_cost = realtime_cost_tracker
        self.operator = operator
        
        # Alert configuration
        self.enabled = False
        self.webhook_url = os.getenv('COST_ALERT_WEBHOOK_URL', '')
        self.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL', '')
        self.alert_time = os.getenv('COST_ALERT_TIME', '09:00')  # Default 9 AM
        self.timezone_offset = int(os.getenv('COST_ALERT_TIMEZONE_OFFSET', '0'))  # Hours from UTC
        
        # Scheduler
        self._scheduler_thread = None
        self._stop_event = threading.Event()
        self._last_alert_date = None
        
        # Load saved config
        self._load_config()
    
    def _load_config(self):
        """Load configuration from environment or saved state"""
        self.enabled = os.getenv('ENABLE_DAILY_COST_REPORT', 'false').lower() == 'true'
        if self.enabled:
            logger.info(f"Daily cost alerting enabled, will send at {self.alert_time}")
    
    def configure(self, enabled: bool = None, webhook_url: str = None, 
                  slack_webhook_url: str = None, alert_time: str = None) -> Dict:
        """Configure alerting settings"""
        if enabled is not None:
            self.enabled = enabled
        if webhook_url is not None:
            self.webhook_url = webhook_url
        if slack_webhook_url is not None:
            self.slack_webhook_url = slack_webhook_url
        if alert_time is not None:
            self.alert_time = alert_time
        
        # Start or stop scheduler based on enabled state
        if self.enabled:
            self.start_scheduler()
        else:
            self.stop_scheduler()
        
        logger.info(f"Cost alerting configured: enabled={self.enabled}, time={self.alert_time}")
        
        return self.get_config()
    
    def get_config(self) -> Dict:
        """Get current configuration"""
        return {
            'enabled': self.enabled,
            'webhook_url': self.webhook_url[:20] + '...' if self.webhook_url and len(self.webhook_url) > 20 else self.webhook_url,
            'slack_webhook_url': self.slack_webhook_url[:20] + '...' if self.slack_webhook_url and len(self.slack_webhook_url) > 20 else self.slack_webhook_url,
            'alert_time': self.alert_time,
            'timezone_offset': self.timezone_offset,
            'scheduler_running': self._scheduler_thread is not None and self._scheduler_thread.is_alive(),
            'last_alert_date': self._last_alert_date.isoformat() if self._last_alert_date else None
        }
    
    def start_scheduler(self):
        """Start the daily alert scheduler"""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            logger.info("Scheduler already running")
            return
        
        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        logger.info("Cost alert scheduler started")
    
    def stop_scheduler(self):
        """Stop the daily alert scheduler"""
        self._stop_event.set()
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        logger.info("Cost alert scheduler stopped")
    
    def _scheduler_loop(self):
        """Main scheduler loop - checks every minute if it's time to send alert"""
        while not self._stop_event.is_set():
            try:
                from datetime import timezone
                now = datetime.now(timezone.utc) + timedelta(hours=self.timezone_offset)
                current_time = now.strftime('%H:%M')
                current_date = now.date()
                
                # Check if it's time to send and we haven't sent today
                if current_time == self.alert_time and self._last_alert_date != current_date:
                    logger.info("Triggering daily cost report")
                    self.send_daily_report()
                    self._last_alert_date = current_date
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
            
            # Sleep for 60 seconds
            self._stop_event.wait(60)
    
    def generate_cost_report(self) -> Dict:
        """Generate the daily cost report data"""
        try:
            # Get real-time costs
            costs = self.realtime_cost.calculate_realtime_costs()
            cluster = self.realtime_cost.get_cluster_realtime_summary()
            
            # Get top 5 most expensive workloads
            top_workloads = costs['workloads'][:5] if costs.get('workloads') else []
            
            # Get top 5 wasteful workloads
            wasteful = sorted(
                [w for w in costs.get('workloads', []) if w['total_cost_hourly'] > 0],
                key=lambda x: x['waste_monthly'],
                reverse=True
            )[:5]
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'report_date': datetime.utcnow().strftime('%Y-%m-%d'),
                'cluster': {
                    'total_nodes': cluster['cluster']['total_nodes'],
                    'total_vcpu': cluster['cluster']['total_vcpu'],
                    'total_memory_gb': cluster['cluster']['total_memory_gb'],
                    'cpu_utilization': cluster['cluster']['cpu_utilization_percent'],
                    'memory_utilization': cluster['cluster']['memory_utilization_percent'],
                },
                'costs': {
                    'daily': cluster['costs']['daily'],
                    'monthly': cluster['costs']['monthly'],
                    'yearly': cluster['costs']['yearly'],
                },
                'waste': {
                    'daily': costs['summary']['total_daily_waste'],
                    'monthly': costs['summary']['total_monthly_waste'],
                    'percentage': costs['summary']['waste_percentage'],
                },
                'top_workloads': [
                    {
                        'name': f"{w['namespace']}/{w['pod']}",
                        'cost_daily': w['cost_daily'],
                        'cost_monthly': w['cost_monthly'],
                    }
                    for w in top_workloads
                ],
                'top_wasteful': [
                    {
                        'name': f"{w['namespace']}/{w['pod']}",
                        'waste_monthly': w['waste_monthly'],
                        'utilization': f"CPU: {w['cpu_utilization_percent']}%, Mem: {w['memory_utilization_percent']}%",
                    }
                    for w in wasteful
                ],
                'workload_count': costs['summary']['total_workloads'],
            }
        except Exception as e:
            logger.error(f"Error generating cost report: {e}")
            return {'error': str(e)}
    
    def format_slack_message(self, report: Dict) -> Dict:
        """Format report as Slack message"""
        if 'error' in report:
            return {
                'text': f"❌ Cost Report Error: {report['error']}"
            }
        
        # Build Slack blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"💰 Daily Cost Report - {report['report_date']}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Cluster Nodes:* {report['cluster']['total_nodes']}"},
                    {"type": "mrkdwn", "text": f"*Total vCPU:* {report['cluster']['total_vcpu']}"},
                    {"type": "mrkdwn", "text": f"*CPU Utilization:* {report['cluster']['cpu_utilization']}%"},
                    {"type": "mrkdwn", "text": f"*Memory Utilization:* {report['cluster']['memory_utilization']}%"},
                ]
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*💵 Cost Summary*\n• Daily: ${report['costs']['daily']}\n• Monthly: ${report['costs']['monthly']}\n• Yearly: ${report['costs']['yearly']}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🗑️ Waste Summary*\n• Daily Waste: ${report['waste']['daily']}\n• Monthly Waste: ${report['waste']['monthly']}\n• Waste %: {report['waste']['percentage']}%"
                }
            },
        ]
        
        # Add top workloads
        if report.get('top_workloads'):
            top_list = "\n".join([
                f"• {w['name']}: ${w['cost_monthly']}/mo"
                for w in report['top_workloads']
            ])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📊 Top 5 Expensive Workloads*\n{top_list}"
                }
            })
        
        # Add wasteful workloads
        if report.get('top_wasteful'):
            waste_list = "\n".join([
                f"• {w['name']}: ${w['waste_monthly']}/mo waste ({w['utilization']})"
                for w in report['top_wasteful']
            ])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*⚠️ Top 5 Wasteful Workloads*\n{waste_list}"
                }
            })
        
        return {
            "blocks": blocks,
            "text": f"Daily Cost Report - {report['report_date']}: ${report['costs']['daily']}/day, ${report['costs']['monthly']}/month"
        }
    
    def format_webhook_message(self, report: Dict) -> Dict:
        """Format report as generic webhook payload"""
        return {
            'event': 'daily_cost_report',
            'timestamp': report.get('timestamp'),
            'report': report
        }
    
    def send_to_slack(self, message: Dict) -> bool:
        """Send message to Slack webhook"""
        if not self.slack_webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False
        
        try:
            data = json.dumps(message).encode('utf-8')
            req = urllib.request.Request(
                self.slack_webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    logger.info("Successfully sent cost report to Slack")
                    return True
                else:
                    logger.error(f"Slack webhook returned status {response.status}")
                    return False
                    
        except urllib.error.URLError as e:
            logger.error(f"Failed to send to Slack: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending to Slack: {e}")
            return False
    
    def send_to_webhook(self, message: Dict) -> bool:
        """Send message to generic webhook"""
        if not self.webhook_url:
            logger.warning("Webhook URL not configured")
            return False
        
        try:
            data = json.dumps(message).encode('utf-8')
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status in [200, 201, 202, 204]:
                    logger.info("Successfully sent cost report to webhook")
                    return True
                else:
                    logger.error(f"Webhook returned status {response.status}")
                    return False
                    
        except urllib.error.URLError as e:
            logger.error(f"Failed to send to webhook: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending to webhook: {e}")
            return False
    
    def send_daily_report(self) -> Dict:
        """Generate and send the daily cost report"""
        report = self.generate_cost_report()
        
        results = {
            'report_generated': 'error' not in report,
            'slack_sent': False,
            'webhook_sent': False,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if 'error' in report:
            results['error'] = report['error']
            return results
        
        # Send to Slack
        if self.slack_webhook_url:
            slack_message = self.format_slack_message(report)
            results['slack_sent'] = self.send_to_slack(slack_message)
        
        # Send to generic webhook
        if self.webhook_url:
            webhook_message = self.format_webhook_message(report)
            results['webhook_sent'] = self.send_to_webhook(webhook_message)
        
        results['report'] = report
        return results
    
    def test_alert(self) -> Dict:
        """Send a test alert to verify configuration"""
        test_report = {
            'timestamp': datetime.utcnow().isoformat(),
            'report_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'cluster': {
                'total_nodes': 3,
                'total_vcpu': 12,
                'total_memory_gb': 48,
                'cpu_utilization': 45.5,
                'memory_utilization': 62.3,
            },
            'costs': {
                'daily': 28.80,
                'monthly': 864.00,
                'yearly': 10512.00,
            },
            'waste': {
                'daily': 8.64,
                'monthly': 259.20,
                'percentage': 30.0,
            },
            'top_workloads': [
                {'name': 'production/api-server', 'cost_daily': 5.20, 'cost_monthly': 156.00},
                {'name': 'production/worker', 'cost_daily': 3.80, 'cost_monthly': 114.00},
            ],
            'top_wasteful': [
                {'name': 'staging/test-app', 'waste_monthly': 45.00, 'utilization': 'CPU: 15%, Mem: 20%'},
            ],
            'workload_count': 25,
            'is_test': True
        }
        
        results = {
            'test': True,
            'slack_sent': False,
            'webhook_sent': False,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Send to Slack
        if self.slack_webhook_url:
            slack_message = self.format_slack_message(test_report)
            slack_message['text'] = "🧪 TEST: " + slack_message.get('text', '')
            results['slack_sent'] = self.send_to_slack(slack_message)
        
        # Send to generic webhook
        if self.webhook_url:
            webhook_message = self.format_webhook_message(test_report)
            webhook_message['test'] = True
            results['webhook_sent'] = self.send_to_webhook(webhook_message)
        
        return results
