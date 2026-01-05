"""
Advanced Cost Allocation Module
Provides team/project/namespace-based cost tracking and chargeback/showback reports

Supports two cost allocation models:
1. Fixed pricing: Uses fixed $/vCPU/hr and $/GB/hr rates
2. Fair share (proportional): Allocates actual node costs based on resource requests
   - Node cost is divided by total requests on that node
   - Each workload pays proportionally to their requests
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
        
        # Cache for node costs (refreshed periodically)
        self._node_cost_cache = {}
        self._node_cache_time = None
    
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
    
    # ============================================
    # Fair Share Cost Allocation (Proportional)
    # ============================================
    
    def _get_node_hourly_cost(self, node_name: str) -> Dict:
        """
        Get hourly cost for a specific node based on its instance type.
        Returns: {'cpu_cost': float, 'memory_cost': float, 'total_cost': float, 'vcpu': int, 'memory_gb': float}
        """
        try:
            from src.cloud_pricing import CloudPricingDetector
            
            # Get core_v1 from operator
            if hasattr(self.operator, 'controller'):
                core_v1 = self.operator.controller.core_v1
            elif hasattr(self.operator, 'core_v1'):
                core_v1 = self.operator.core_v1
            else:
                raise Exception("Cannot access Kubernetes API")
            
            node = core_v1.read_node(node_name)
            labels = node.metadata.labels or {}
            
            # Get node capacity
            capacity = node.status.capacity
            vcpu = int(capacity.get('cpu', '0'))
            memory_ki = capacity.get('memory', '0')
            
            # Convert memory to GB
            if memory_ki.endswith('Ki'):
                memory_gb = float(memory_ki[:-2]) / (1024 * 1024)
            elif memory_ki.endswith('Mi'):
                memory_gb = float(memory_ki[:-2]) / 1024
            elif memory_ki.endswith('Gi'):
                memory_gb = float(memory_ki[:-2])
            else:
                memory_gb = float(memory_ki) / (1024 * 1024 * 1024)
            
            # Calculate node cost using detected pricing
            cpu_cost = vcpu * self.cost_per_vcpu_hour
            memory_cost = memory_gb * self.cost_per_gb_memory_hour
            
            return {
                'cpu_cost': cpu_cost,
                'memory_cost': memory_cost,
                'total_cost': cpu_cost + memory_cost,
                'vcpu': vcpu,
                'memory_gb': round(memory_gb, 2),
                'node_name': node_name
            }
            
        except Exception as e:
            logger.warning(f"Failed to get node cost for {node_name}: {e}")
            return {
                'cpu_cost': 0,
                'memory_cost': 0,
                'total_cost': 0,
                'vcpu': 0,
                'memory_gb': 0,
                'node_name': node_name,
                'error': str(e)
            }
    
    def _get_node_resource_requests(self, node_name: str) -> Dict:
        """
        Get total resource requests for all pods on a node.
        Returns: {'total_cpu_requests': float (cores), 'total_memory_requests': float (GB), 'pods': list}
        """
        try:
            # Get core_v1 from operator
            if hasattr(self.operator, 'controller'):
                core_v1 = self.operator.controller.core_v1
            elif hasattr(self.operator, 'core_v1'):
                core_v1 = self.operator.core_v1
            else:
                raise Exception("Cannot access Kubernetes API")
            
            # Get all pods on this node
            pods = core_v1.list_pod_for_all_namespaces(
                field_selector=f'spec.nodeName={node_name},status.phase=Running'
            )
            
            total_cpu_requests = 0.0  # in cores
            total_memory_requests = 0.0  # in GB
            pod_details = []
            
            for pod in pods.items:
                pod_cpu = 0.0
                pod_memory = 0.0
                
                for container in pod.spec.containers:
                    if container.resources and container.resources.requests:
                        # CPU
                        cpu_req = container.resources.requests.get('cpu', '0')
                        if isinstance(cpu_req, str):
                            if cpu_req.endswith('m'):
                                pod_cpu += float(cpu_req[:-1]) / 1000
                            else:
                                pod_cpu += float(cpu_req)
                        
                        # Memory
                        mem_req = container.resources.requests.get('memory', '0')
                        if isinstance(mem_req, str):
                            if mem_req.endswith('Gi'):
                                pod_memory += float(mem_req[:-2])
                            elif mem_req.endswith('Mi'):
                                pod_memory += float(mem_req[:-2]) / 1024
                            elif mem_req.endswith('G'):
                                pod_memory += float(mem_req[:-1])
                            elif mem_req.endswith('M'):
                                pod_memory += float(mem_req[:-1]) / 1024
                            elif mem_req.endswith('Ki'):
                                pod_memory += float(mem_req[:-2]) / (1024 * 1024)
                
                total_cpu_requests += pod_cpu
                total_memory_requests += pod_memory
                
                pod_details.append({
                    'namespace': pod.metadata.namespace,
                    'name': pod.metadata.name,
                    'cpu_request': round(pod_cpu, 3),
                    'memory_request_gb': round(pod_memory, 3),
                    'owner': self._get_pod_owner(pod)
                })
            
            return {
                'total_cpu_requests': round(total_cpu_requests, 3),
                'total_memory_requests': round(total_memory_requests, 3),
                'pod_count': len(pod_details),
                'pods': pod_details
            }
            
        except Exception as e:
            logger.warning(f"Failed to get resource requests for node {node_name}: {e}")
            return {
                'total_cpu_requests': 0,
                'total_memory_requests': 0,
                'pod_count': 0,
                'pods': [],
                'error': str(e)
            }
    
    def _get_pod_owner(self, pod) -> Dict:
        """Get the owner reference (deployment/statefulset/etc) of a pod"""
        try:
            if pod.metadata.owner_references:
                owner = pod.metadata.owner_references[0]
                return {
                    'kind': owner.kind,
                    'name': owner.name
                }
        except:
            pass
        return {'kind': 'unknown', 'name': 'unknown'}
    
    def calculate_fair_share_cost(self, namespace: str, deployment: str, hours: int = 24) -> Dict:
        """
        Calculate cost using fair share allocation model.
        
        Logic:
        1. Get node cost (e.g., $1/hr for a 4 vCPU node)
        2. Get total resource requests on node (e.g., 3 vCPU requested)
        3. Cost per requested CPU = node_cost / total_requests = $1/3 per vCPU
        4. Workload cost = workload_request × (node_cost / total_requests)
        
        This ensures:
        - Total allocated cost = actual node cost
        - Each workload pays proportionally to their requests
        - No over/under allocation
        """
        try:
            # Get core_v1 from operator
            if hasattr(self.operator, 'controller'):
                core_v1 = self.operator.controller.core_v1
            elif hasattr(self.operator, 'core_v1'):
                core_v1 = self.operator.core_v1
            else:
                raise Exception("Cannot access Kubernetes API")
            
            # Get deployment info
            dep = self.operator.apps_v1.read_namespaced_deployment(deployment, namespace)
            
            if not dep.spec.replicas or dep.spec.replicas == 0:
                return {
                    'cpu_cost': 0,
                    'memory_cost': 0,
                    'total_cost': 0,
                    'hours': hours,
                    'replicas': 0,
                    'allocation_model': 'fair_share'
                }
            
            # Get pods for this deployment
            label_selector = ','.join([f'{k}={v}' for k, v in (dep.spec.selector.match_labels or {}).items()])
            pods = core_v1.list_namespaced_pod(namespace, label_selector=label_selector)
            
            if not pods.items:
                # Fallback to fixed pricing if no pods found
                return self.calculate_deployment_cost(namespace, deployment, hours)
            
            total_cpu_cost = 0.0
            total_memory_cost = 0.0
            node_allocations = []
            
            for pod in pods.items:
                if pod.status.phase != 'Running' or not pod.spec.node_name:
                    continue
                
                node_name = pod.spec.node_name
                
                # Get node cost
                node_cost = self._get_node_hourly_cost(node_name)
                if node_cost.get('error'):
                    continue
                
                # Get total requests on this node
                node_requests = self._get_node_resource_requests(node_name)
                if node_requests.get('error') or node_requests['total_cpu_requests'] == 0:
                    continue
                
                # Calculate cost per requested unit on this node
                # Fair share: node_cost / total_requests
                cost_per_cpu_request = node_cost['cpu_cost'] / node_requests['total_cpu_requests'] if node_requests['total_cpu_requests'] > 0 else 0
                cost_per_memory_request = node_cost['memory_cost'] / node_requests['total_memory_requests'] if node_requests['total_memory_requests'] > 0 else 0
                
                # Get this pod's requests
                pod_cpu = 0.0
                pod_memory = 0.0
                
                for container in pod.spec.containers:
                    if container.resources and container.resources.requests:
                        cpu_req = container.resources.requests.get('cpu', '0')
                        if isinstance(cpu_req, str):
                            if cpu_req.endswith('m'):
                                pod_cpu += float(cpu_req[:-1]) / 1000
                            else:
                                pod_cpu += float(cpu_req)
                        
                        mem_req = container.resources.requests.get('memory', '0')
                        if isinstance(mem_req, str):
                            if mem_req.endswith('Gi'):
                                pod_memory += float(mem_req[:-2])
                            elif mem_req.endswith('Mi'):
                                pod_memory += float(mem_req[:-2]) / 1024
                            elif mem_req.endswith('G'):
                                pod_memory += float(mem_req[:-1])
                            elif mem_req.endswith('M'):
                                pod_memory += float(mem_req[:-1]) / 1024
                
                # Calculate this pod's fair share cost
                pod_cpu_cost = pod_cpu * cost_per_cpu_request * hours
                pod_memory_cost = pod_memory * cost_per_memory_request * hours
                
                total_cpu_cost += pod_cpu_cost
                total_memory_cost += pod_memory_cost
                
                node_allocations.append({
                    'node': node_name,
                    'pod': pod.metadata.name,
                    'pod_cpu_request': round(pod_cpu, 3),
                    'pod_memory_request_gb': round(pod_memory, 3),
                    'node_total_cpu_requests': node_requests['total_cpu_requests'],
                    'node_total_memory_requests': node_requests['total_memory_requests'],
                    'node_hourly_cost': round(node_cost['total_cost'], 4),
                    'cost_per_cpu_request': round(cost_per_cpu_request, 4),
                    'cost_per_memory_request': round(cost_per_memory_request, 4),
                    'pod_cpu_cost': round(pod_cpu_cost, 4),
                    'pod_memory_cost': round(pod_memory_cost, 4)
                })
            
            return {
                'cpu_cost': round(total_cpu_cost, 4),
                'memory_cost': round(total_memory_cost, 4),
                'total_cost': round(total_cpu_cost + total_memory_cost, 4),
                'hours': hours,
                'replicas': len([p for p in pods.items if p.status.phase == 'Running']),
                'allocation_model': 'fair_share',
                'node_allocations': node_allocations,
                'explanation': 'Cost allocated proportionally based on resource requests relative to total node requests'
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate fair share cost for {namespace}/{deployment}: {e}")
            # Fallback to fixed pricing
            return self.calculate_deployment_cost(namespace, deployment, hours)
    
    def get_cluster_cost_summary(self) -> Dict:
        """
        Get cluster-wide cost summary showing node costs and allocation.
        """
        try:
            # Get core_v1 from operator
            if hasattr(self.operator, 'controller'):
                core_v1 = self.operator.controller.core_v1
            elif hasattr(self.operator, 'core_v1'):
                core_v1 = self.operator.core_v1
            else:
                raise Exception("Cannot access Kubernetes API")
            
            nodes = core_v1.list_node()
            
            total_node_cost = 0.0
            total_vcpu = 0
            total_memory_gb = 0.0
            total_cpu_requests = 0.0
            total_memory_requests = 0.0
            node_details = []
            
            for node in nodes.items:
                node_name = node.metadata.name
                
                # Get node cost
                node_cost = self._get_node_hourly_cost(node_name)
                
                # Get requests on this node
                node_requests = self._get_node_resource_requests(node_name)
                
                total_node_cost += node_cost.get('total_cost', 0)
                total_vcpu += node_cost.get('vcpu', 0)
                total_memory_gb += node_cost.get('memory_gb', 0)
                total_cpu_requests += node_requests.get('total_cpu_requests', 0)
                total_memory_requests += node_requests.get('total_memory_requests', 0)
                
                # Calculate utilization
                cpu_util = (node_requests['total_cpu_requests'] / node_cost['vcpu'] * 100) if node_cost.get('vcpu', 0) > 0 else 0
                mem_util = (node_requests['total_memory_requests'] / node_cost['memory_gb'] * 100) if node_cost.get('memory_gb', 0) > 0 else 0
                
                node_details.append({
                    'node_name': node_name,
                    'vcpu': node_cost.get('vcpu', 0),
                    'memory_gb': node_cost.get('memory_gb', 0),
                    'hourly_cost': round(node_cost.get('total_cost', 0), 4),
                    'cpu_requests': round(node_requests.get('total_cpu_requests', 0), 3),
                    'memory_requests_gb': round(node_requests.get('total_memory_requests', 0), 3),
                    'cpu_utilization_percent': round(cpu_util, 1),
                    'memory_utilization_percent': round(mem_util, 1),
                    'pod_count': node_requests.get('pod_count', 0)
                })
            
            # Calculate cluster-wide metrics
            cluster_cpu_util = (total_cpu_requests / total_vcpu * 100) if total_vcpu > 0 else 0
            cluster_mem_util = (total_memory_requests / total_memory_gb * 100) if total_memory_gb > 0 else 0
            
            return {
                'total_nodes': len(nodes.items),
                'total_vcpu': total_vcpu,
                'total_memory_gb': round(total_memory_gb, 2),
                'total_hourly_cost': round(total_node_cost, 4),
                'total_daily_cost': round(total_node_cost * 24, 2),
                'total_monthly_cost': round(total_node_cost * 24 * 30, 2),
                'total_cpu_requests': round(total_cpu_requests, 3),
                'total_memory_requests_gb': round(total_memory_requests, 3),
                'cluster_cpu_utilization_percent': round(cluster_cpu_util, 1),
                'cluster_memory_utilization_percent': round(cluster_mem_util, 1),
                'pricing': {
                    'vcpu_per_hour': self.cost_per_vcpu_hour,
                    'memory_gb_per_hour': self.cost_per_gb_memory_hour
                },
                'nodes': node_details
            }
            
        except Exception as e:
            logger.error(f"Failed to get cluster cost summary: {e}")
            return {'error': str(e)}

    # ============================================
    # Original Methods (Fixed Pricing Model)
    # ============================================
    
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
