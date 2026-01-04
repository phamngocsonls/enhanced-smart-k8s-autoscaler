"""
Advanced Cost Allocation Module
Provides team/project/namespace-based cost tracking and chargeback/showback reports
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


class CostAllocator:
    """Advanced cost allocation and tracking"""
    
    def __init__(self, db, operator):
        self.db = db
        self.operator = operator
        
        # Try to auto-detect pricing from cloud provider
        self.cost_per_vcpu_hour = None
        self.cost_per_gb_memory_hour = None
        self._auto_detect_pricing()
    
    def _auto_detect_pricing(self):
        """Auto-detect pricing from cloud provider or use manual config"""
        try:
            from src.cloud_pricing import CloudPricingDetector
            
            # Get core_v1 from operator
            if hasattr(self.operator, 'controller'):
                core_v1 = self.operator.controller.core_v1
            elif hasattr(self.operator, 'core_v1'):
                core_v1 = self.operator.core_v1
            else:
                raise Exception("Cannot access Kubernetes API")
            
            # Auto-detect pricing
            detector = CloudPricingDetector(core_v1)
            vcpu_price, memory_price = detector.auto_detect_pricing()
            
            # Check if manual config overrides auto-detection
            manual_vcpu = getattr(self.operator.config, 'cost_per_vcpu_hour', None)
            manual_memory = getattr(self.operator.config, 'cost_per_gb_memory_hour', None)
            
            if manual_vcpu and manual_memory:
                # Use manual configuration
                self.cost_per_vcpu_hour = float(manual_vcpu)
                self.cost_per_gb_memory_hour = float(manual_memory)
                logger.info(f"Using manual pricing: ${self.cost_per_vcpu_hour}/vCPU/hr, ${self.cost_per_gb_memory_hour}/GB/hr")
            else:
                # Use auto-detected pricing
                self.cost_per_vcpu_hour = vcpu_price
                self.cost_per_gb_memory_hour = memory_price
                
                pricing_info = detector.get_pricing_info()
                logger.info(f"Auto-detected pricing from {pricing_info['provider'].upper()}: "
                          f"${self.cost_per_vcpu_hour}/vCPU/hr, ${self.cost_per_gb_memory_hour}/GB/hr")
            
        except Exception as e:
            logger.warning(f"Failed to auto-detect pricing, using defaults: {e}")
            # Fallback to manual config or defaults
            try:
                manual_vcpu = getattr(self.operator.config, 'cost_per_vcpu_hour', 0.045)
                manual_memory = getattr(self.operator.config, 'cost_per_gb_memory_hour', 0.006)
                # Handle case where config returns Mock or non-numeric values
                self.cost_per_vcpu_hour = float(manual_vcpu) if isinstance(manual_vcpu, (int, float, str)) else 0.045
                self.cost_per_gb_memory_hour = float(manual_memory) if isinstance(manual_memory, (int, float, str)) else 0.006
            except (TypeError, ValueError, AttributeError):
                # Final fallback if conversion fails
                self.cost_per_vcpu_hour = 0.045
                self.cost_per_gb_memory_hour = 0.006
    
    def get_deployment_labels(self, namespace: str, deployment: str) -> Dict[str, str]:
        """Get labels from deployment for cost allocation"""
        try:
            dep = self.operator.apps_v1.read_namespaced_deployment(deployment, namespace)
            return dep.metadata.labels or {}
        except Exception as e:
            logger.warning(f"Failed to get labels for {namespace}/{deployment}: {e}")
            return {}
    
    def extract_cost_tags(self, labels: Dict[str, str]) -> Dict[str, str]:
        """Extract cost allocation tags from labels"""
        tags = {}
        
        # Common label patterns for cost allocation
        tag_mappings = {
            'team': ['team', 'owner', 'squad'],
            'project': ['project', 'app', 'application'],
            'environment': ['env', 'environment', 'stage'],
            'cost_center': ['cost-center', 'costcenter', 'billing'],
            'department': ['department', 'dept', 'division']
        }
        
        for tag_name, possible_keys in tag_mappings.items():
            for key in possible_keys:
                if key in labels:
                    tags[tag_name] = labels[key]
                    break
        
        return tags
    
    def calculate_deployment_cost(self, namespace: str, deployment: str, 
                                  hours: int = 24) -> Dict:
        """Calculate cost for a deployment over specified hours"""
        try:
            # Get current resource usage
            dep = self.operator.apps_v1.read_namespaced_deployment(deployment, namespace)
            
            if not dep.spec.replicas:
                return {
                    'cpu_cost': 0,
                    'memory_cost': 0,
                    'total_cost': 0,
                    'hours': hours,
                    'replicas': 0
                }
            
            replicas = dep.spec.replicas
            containers = dep.spec.template.spec.containers
            
            # Calculate resource requests
            total_cpu_cores = 0
            total_memory_gb = 0
            
            for container in containers:
                if container.resources and container.resources.requests:
                    # CPU
                    cpu_req = container.resources.requests.get('cpu', '0')
                    if isinstance(cpu_req, str):
                        if cpu_req.endswith('m'):
                            total_cpu_cores += float(cpu_req[:-1]) / 1000
                        else:
                            total_cpu_cores += float(cpu_req)
                    
                    # Memory
                    mem_req = container.resources.requests.get('memory', '0')
                    if isinstance(mem_req, str):
                        if mem_req.endswith('Gi'):
                            total_memory_gb += float(mem_req[:-2])
                        elif mem_req.endswith('Mi'):
                            total_memory_gb += float(mem_req[:-2]) / 1024
                        elif mem_req.endswith('G'):
                            total_memory_gb += float(mem_req[:-1])
                        elif mem_req.endswith('M'):
                            total_memory_gb += float(mem_req[:-1]) / 1024
            
            # Calculate costs
            cpu_cost = total_cpu_cores * replicas * hours * self.cost_per_vcpu_hour
            memory_cost = total_memory_gb * replicas * hours * self.cost_per_gb_memory_hour
            
            return {
                'cpu_cost': round(cpu_cost, 4),
                'memory_cost': round(memory_cost, 4),
                'total_cost': round(cpu_cost + memory_cost, 4),
                'cpu_cores': round(total_cpu_cores * replicas, 2),
                'memory_gb': round(total_memory_gb * replicas, 2),
                'hours': hours,
                'replicas': replicas
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate cost for {namespace}/{deployment}: {e}")
            return {
                'cpu_cost': 0,
                'memory_cost': 0,
                'total_cost': 0,
                'hours': hours,
                'error': str(e)
            }
    
    def get_team_costs(self, hours: int = 24) -> Dict[str, Dict]:
        """Get costs grouped by team"""
        team_costs = defaultdict(lambda: {
            'deployments': [],
            'total_cost': 0,
            'cpu_cost': 0,
            'memory_cost': 0,
            'deployment_count': 0
        })
        
        for key, config in self.operator.watched_deployments.items():
            namespace = config['namespace']
            deployment = config['deployment']
            
            # Get labels and extract team
            labels = self.get_deployment_labels(namespace, deployment)
            tags = self.extract_cost_tags(labels)
            team = tags.get('team', 'unallocated')
            
            # Calculate cost
            cost = self.calculate_deployment_cost(namespace, deployment, hours)
            
            # Aggregate
            team_costs[team]['deployments'].append({
                'namespace': namespace,
                'deployment': deployment,
                'cost': cost['total_cost'],
                'cpu_cost': cost['cpu_cost'],
                'memory_cost': cost['memory_cost']
            })
            team_costs[team]['total_cost'] += cost['total_cost']
            team_costs[team]['cpu_cost'] += cost['cpu_cost']
            team_costs[team]['memory_cost'] += cost['memory_cost']
            team_costs[team]['deployment_count'] += 1
        
        # Round totals
        for team in team_costs:
            team_costs[team]['total_cost'] = round(team_costs[team]['total_cost'], 2)
            team_costs[team]['cpu_cost'] = round(team_costs[team]['cpu_cost'], 2)
            team_costs[team]['memory_cost'] = round(team_costs[team]['memory_cost'], 2)
        
        return dict(team_costs)
    
    def get_namespace_costs(self, hours: int = 24) -> Dict[str, Dict]:
        """Get costs grouped by namespace"""
        namespace_costs = defaultdict(lambda: {
            'deployments': [],
            'total_cost': 0,
            'cpu_cost': 0,
            'memory_cost': 0,
            'deployment_count': 0
        })
        
        for key, config in self.operator.watched_deployments.items():
            namespace = config['namespace']
            deployment = config['deployment']
            
            # Calculate cost
            cost = self.calculate_deployment_cost(namespace, deployment, hours)
            
            # Aggregate
            namespace_costs[namespace]['deployments'].append({
                'deployment': deployment,
                'cost': cost['total_cost'],
                'cpu_cost': cost['cpu_cost'],
                'memory_cost': cost['memory_cost']
            })
            namespace_costs[namespace]['total_cost'] += cost['total_cost']
            namespace_costs[namespace]['cpu_cost'] += cost['cpu_cost']
            namespace_costs[namespace]['memory_cost'] += cost['memory_cost']
            namespace_costs[namespace]['deployment_count'] += 1
        
        # Round totals
        for ns in namespace_costs:
            namespace_costs[ns]['total_cost'] = round(namespace_costs[ns]['total_cost'], 2)
            namespace_costs[ns]['cpu_cost'] = round(namespace_costs[ns]['cpu_cost'], 2)
            namespace_costs[ns]['memory_cost'] = round(namespace_costs[ns]['memory_cost'], 2)
        
        return dict(namespace_costs)
    
    def get_project_costs(self, hours: int = 24) -> Dict[str, Dict]:
        """Get costs grouped by project"""
        project_costs = defaultdict(lambda: {
            'deployments': [],
            'total_cost': 0,
            'cpu_cost': 0,
            'memory_cost': 0,
            'deployment_count': 0
        })
        
        for key, config in self.operator.watched_deployments.items():
            namespace = config['namespace']
            deployment = config['deployment']
            
            # Get labels and extract project
            labels = self.get_deployment_labels(namespace, deployment)
            tags = self.extract_cost_tags(labels)
            project = tags.get('project', 'unallocated')
            
            # Calculate cost
            cost = self.calculate_deployment_cost(namespace, deployment, hours)
            
            # Aggregate
            project_costs[project]['deployments'].append({
                'namespace': namespace,
                'deployment': deployment,
                'cost': cost['total_cost'],
                'cpu_cost': cost['cpu_cost'],
                'memory_cost': cost['memory_cost']
            })
            project_costs[project]['total_cost'] += cost['total_cost']
            project_costs[project]['cpu_cost'] += cost['cpu_cost']
            project_costs[project]['memory_cost'] += cost['memory_cost']
            project_costs[project]['deployment_count'] += 1
        
        # Round totals
        for proj in project_costs:
            project_costs[proj]['total_cost'] = round(project_costs[proj]['total_cost'], 2)
            project_costs[proj]['cpu_cost'] = round(project_costs[proj]['cpu_cost'], 2)
            project_costs[proj]['memory_cost'] = round(project_costs[proj]['memory_cost'], 2)
        
        return dict(project_costs)
    
    def get_cost_trends(self, days: int = 30) -> Dict:
        """Get historical cost trends from database"""
        try:
            # Query historical data
            cursor = self.db.conn.cursor()
            
            # Get daily costs for the past N days
            query = """
                SELECT 
                    DATE(timestamp) as date,
                    deployment_key,
                    AVG(replicas) as avg_replicas,
                    AVG(cpu_usage) as avg_cpu,
                    AVG(memory_usage) as avg_memory
                FROM metrics
                WHERE timestamp >= datetime('now', '-{} days')
                GROUP BY DATE(timestamp), deployment_key
                ORDER BY date DESC
            """.format(days)
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Aggregate by date
            daily_costs = defaultdict(lambda: {'total': 0, 'deployments': {}})
            
            for row in rows:
                date, dep_key, avg_replicas, avg_cpu, avg_memory = row
                
                # Estimate cost (simplified - assumes constant resource requests)
                # In production, you'd want to track actual resource requests over time
                daily_cost = (avg_cpu * 24 * self.cost_per_vcpu_hour + 
                             avg_memory * 24 * self.cost_per_gb_memory_hour)
                
                daily_costs[date]['total'] += daily_cost
                daily_costs[date]['deployments'][dep_key] = round(daily_cost, 2)
            
            # Convert to list and round
            trends = []
            for date in sorted(daily_costs.keys()):
                trends.append({
                    'date': date,
                    'total_cost': round(daily_costs[date]['total'], 2),
                    'deployment_count': len(daily_costs[date]['deployments'])
                })
            
            return {
                'trends': trends,
                'days': days,
                'total_period_cost': round(sum(t['total_cost'] for t in trends), 2)
            }
            
        except Exception as e:
            logger.error(f"Failed to get cost trends: {e}")
            return {'trends': [], 'error': str(e)}
    
    def detect_cost_anomalies(self, threshold_std: float = 2.0) -> List[Dict]:
        """Detect unusual cost spikes"""
        anomalies = []
        
        try:
            # Get recent cost data
            trends = self.get_cost_trends(days=30)
            if not trends.get('trends'):
                return []
            
            costs = [t['total_cost'] for t in trends['trends']]
            
            if len(costs) < 7:
                return []  # Need at least a week of data
            
            mean_cost = statistics.mean(costs)
            std_cost = statistics.stdev(costs)
            
            # Find anomalies
            for trend in trends['trends'][-7:]:  # Last 7 days
                if trend['total_cost'] > mean_cost + (threshold_std * std_cost):
                    anomalies.append({
                        'date': trend['date'],
                        'cost': trend['total_cost'],
                        'expected_cost': round(mean_cost, 2),
                        'deviation': round(trend['total_cost'] - mean_cost, 2),
                        'severity': 'high' if trend['total_cost'] > mean_cost + (3 * std_cost) else 'medium'
                    })
            
        except Exception as e:
            logger.error(f"Failed to detect cost anomalies: {e}")
        
        return anomalies
    
    def get_idle_resources(self, utilization_threshold: float = 0.2) -> List[Dict]:
        """Identify deployments with low resource utilization (wasted cost)"""
        idle_resources = []
        
        for key, config in self.operator.watched_deployments.items():
            namespace = config['namespace']
            deployment = config['deployment']
            
            try:
                # Get recent metrics
                cursor = self.db.conn.cursor()
                cursor.execute("""
                    SELECT AVG(cpu_usage), AVG(memory_usage), AVG(replicas)
                    FROM metrics
                    WHERE deployment_key = ? AND timestamp >= datetime('now', '-24 hours')
                """, (key,))
                
                row = cursor.fetchone()
                if not row or not row[0]:
                    continue
                
                avg_cpu, avg_memory, avg_replicas = row
                
                # Get resource requests
                dep = self.operator.apps_v1.read_namespaced_deployment(deployment, namespace)
                containers = dep.spec.template.spec.containers
                
                total_cpu_req = 0
                total_mem_req = 0
                
                for container in containers:
                    if container.resources and container.resources.requests:
                        cpu_req = container.resources.requests.get('cpu', '0')
                        if isinstance(cpu_req, str) and cpu_req.endswith('m'):
                            total_cpu_req += float(cpu_req[:-1]) / 1000
                        
                        mem_req = container.resources.requests.get('memory', '0')
                        if isinstance(mem_req, str):
                            if mem_req.endswith('Gi'):
                                total_mem_req += float(mem_req[:-2])
                            elif mem_req.endswith('Mi'):
                                total_mem_req += float(mem_req[:-2]) / 1024
                
                # Calculate utilization
                cpu_util = avg_cpu / total_cpu_req if total_cpu_req > 0 else 0
                mem_util = avg_memory / total_mem_req if total_mem_req > 0 else 0
                
                if cpu_util < utilization_threshold or mem_util < utilization_threshold:
                    cost = self.calculate_deployment_cost(namespace, deployment, 24)
                    wasted_cost = cost['total_cost'] * (1 - max(cpu_util, mem_util))
                    
                    idle_resources.append({
                        'namespace': namespace,
                        'deployment': deployment,
                        'cpu_utilization': round(cpu_util * 100, 1),
                        'memory_utilization': round(mem_util * 100, 1),
                        'daily_cost': cost['total_cost'],
                        'wasted_cost': round(wasted_cost, 2),
                        'monthly_waste': round(wasted_cost * 30, 2)
                    })
                
            except Exception as e:
                logger.warning(f"Failed to check idle resources for {namespace}/{deployment}: {e}")
        
        # Sort by wasted cost
        idle_resources.sort(key=lambda x: x['wasted_cost'], reverse=True)
        return idle_resources
