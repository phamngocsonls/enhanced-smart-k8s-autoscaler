"""
Real-time Cost Tracking Module
Uses Prometheus for live cost tracking without storing metrics locally.

Features:
- Real-time cost per workload based on resource requests
- Waste tracking (requested vs actual usage)
- Fair share allocation based on node costs
- No local storage needed - all data from Prometheus
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class RealtimeCostTracker:
    """
    Real-time cost tracking using Prometheus.
    
    Cost Model (Fair Share):
    - Node cost = node_vcpu × vcpu_price + node_memory_gb × memory_price
    - Cost per requested CPU = node_cpu_cost / total_cpu_requests_on_node
    - Workload cost = workload_request × cost_per_request
    
    Waste Calculation:
    - Waste = (requested - actual_usage) × cost_per_request
    """
    
    def __init__(self, operator, cost_per_vcpu_hour: float = 0.045, 
                 cost_per_gb_memory_hour: float = 0.006):
        self.operator = operator
        self.cost_per_vcpu_hour = cost_per_vcpu_hour
        self.cost_per_gb_memory_hour = cost_per_gb_memory_hour
    
    def _query_prometheus(self, query: str):
        """Query Prometheus via operator"""
        try:
            return self.operator._query_prometheus(query)
        except Exception as e:
            logger.warning(f"Prometheus query failed: {e}")
            return None
    
    # ============================================
    # Real-time Node Cost Queries
    # ============================================
    
    def get_node_costs(self) -> Dict:
        """
        Get real-time node costs from Prometheus.
        Returns cost per node based on capacity.
        """
        nodes = {}
        
        # Get node CPU capacity
        cpu_query = 'kube_node_status_capacity{resource="cpu"}'
        cpu_result = self._query_prometheus(cpu_query)
        
        if cpu_result:
            for item in cpu_result:
                node = item['metric'].get('node', 'unknown')
                vcpu = float(item['value'][1])
                if node not in nodes:
                    nodes[node] = {'vcpu': 0, 'memory_gb': 0}
                nodes[node]['vcpu'] = vcpu
        
        # Get node memory capacity
        mem_query = 'kube_node_status_capacity{resource="memory"}'
        mem_result = self._query_prometheus(mem_query)
        
        if mem_result:
            for item in mem_result:
                node = item['metric'].get('node', 'unknown')
                memory_bytes = float(item['value'][1])
                memory_gb = memory_bytes / (1024 ** 3)
                if node not in nodes:
                    nodes[node] = {'vcpu': 0, 'memory_gb': 0}
                nodes[node]['memory_gb'] = memory_gb
        
        # Calculate costs
        for node in nodes:
            nodes[node]['cpu_cost_per_hour'] = nodes[node]['vcpu'] * self.cost_per_vcpu_hour
            nodes[node]['memory_cost_per_hour'] = nodes[node]['memory_gb'] * self.cost_per_gb_memory_hour
            nodes[node]['total_cost_per_hour'] = (
                nodes[node]['cpu_cost_per_hour'] + 
                nodes[node]['memory_cost_per_hour']
            )
        
        return nodes
    
    def get_node_requests(self) -> Dict:
        """
        Get total resource requests per node from Prometheus.
        """
        nodes = defaultdict(lambda: {'cpu_requests': 0, 'memory_requests_gb': 0, 'pod_count': 0})
        
        # Get CPU requests per node
        cpu_query = 'sum by (node) (kube_pod_container_resource_requests{resource="cpu"})'
        cpu_result = self._query_prometheus(cpu_query)
        
        if cpu_result:
            for item in cpu_result:
                node = item['metric'].get('node', 'unknown')
                cpu_cores = float(item['value'][1])
                nodes[node]['cpu_requests'] = cpu_cores
        
        # Get memory requests per node
        mem_query = 'sum by (node) (kube_pod_container_resource_requests{resource="memory"})'
        mem_result = self._query_prometheus(mem_query)
        
        if mem_result:
            for item in mem_result:
                node = item['metric'].get('node', 'unknown')
                memory_bytes = float(item['value'][1])
                nodes[node]['memory_requests_gb'] = memory_bytes / (1024 ** 3)
        
        # Get pod count per node
        pod_query = 'count by (node) (kube_pod_info)'
        pod_result = self._query_prometheus(pod_query)
        
        if pod_result:
            for item in pod_result:
                node = item['metric'].get('node', 'unknown')
                nodes[node]['pod_count'] = int(float(item['value'][1]))
        
        return dict(nodes)
    
    # ============================================
    # Real-time Workload Cost Queries
    # ============================================
    
    def get_workload_requests(self, namespace: str = None) -> List[Dict]:
        """
        Get resource requests per workload (deployment/statefulset) from Prometheus.
        """
        workloads = []
        
        # Build namespace filter
        ns_filter = f'namespace="{namespace}"' if namespace else ''
        
        # Get CPU requests per pod with owner info
        cpu_query = f'sum by (namespace, pod, node) (kube_pod_container_resource_requests{{resource="cpu"{", " + ns_filter if ns_filter else ""}}})'
        cpu_result = self._query_prometheus(cpu_query)
        
        # Get memory requests per pod
        mem_query = f'sum by (namespace, pod, node) (kube_pod_container_resource_requests{{resource="memory"{", " + ns_filter if ns_filter else ""}}})'
        mem_result = self._query_prometheus(mem_query)
        
        # Build pod data
        pods = {}
        if cpu_result:
            for item in cpu_result:
                ns = item['metric'].get('namespace', 'unknown')
                pod = item['metric'].get('pod', 'unknown')
                node = item['metric'].get('node', 'unknown')
                cpu = float(item['value'][1])
                
                key = f"{ns}/{pod}"
                pods[key] = {
                    'namespace': ns,
                    'pod': pod,
                    'node': node,
                    'cpu_request': cpu,
                    'memory_request_gb': 0
                }
        
        if mem_result:
            for item in mem_result:
                ns = item['metric'].get('namespace', 'unknown')
                pod = item['metric'].get('pod', 'unknown')
                memory_bytes = float(item['value'][1])
                
                key = f"{ns}/{pod}"
                if key in pods:
                    pods[key]['memory_request_gb'] = memory_bytes / (1024 ** 3)
        
        return list(pods.values())
    
    def get_workload_usage(self, namespace: str = None) -> Dict:
        """
        Get actual CPU/memory usage per workload from Prometheus.
        """
        usage = {}
        
        ns_filter = f'namespace="{namespace}"' if namespace else ''
        
        # Get actual CPU usage (5m rate)
        cpu_query = f'sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{{{ns_filter}}}[5m]))'
        cpu_result = self._query_prometheus(cpu_query)
        
        if cpu_result:
            for item in cpu_result:
                ns = item['metric'].get('namespace', 'unknown')
                pod = item['metric'].get('pod', 'unknown')
                if not pod:  # Skip empty pod names
                    continue
                cpu = float(item['value'][1])
                
                key = f"{ns}/{pod}"
                usage[key] = {'cpu_usage': cpu, 'memory_usage_gb': 0}
        
        # Get actual memory usage
        mem_query = f'sum by (namespace, pod) (container_memory_working_set_bytes{{{ns_filter}}})'
        mem_result = self._query_prometheus(mem_query)
        
        if mem_result:
            for item in mem_result:
                ns = item['metric'].get('namespace', 'unknown')
                pod = item['metric'].get('pod', 'unknown')
                if not pod:
                    continue
                memory_bytes = float(item['value'][1])
                
                key = f"{ns}/{pod}"
                if key in usage:
                    usage[key]['memory_usage_gb'] = memory_bytes / (1024 ** 3)
                else:
                    usage[key] = {'cpu_usage': 0, 'memory_usage_gb': memory_bytes / (1024 ** 3)}
        
        return usage
    
    # ============================================
    # Real-time Cost Calculation
    # ============================================
    
    def calculate_realtime_costs(self, namespace: str = None) -> Dict:
        """
        Calculate real-time costs for all workloads using fair share allocation.
        
        Returns:
        - Per-workload cost (hourly, daily, monthly projection)
        - Waste cost (requested - actual usage)
        - Cluster totals
        """
        # Get node costs and requests
        node_costs = self.get_node_costs()
        node_requests = self.get_node_requests()
        
        # Calculate cost per requested unit per node
        node_cost_rates = {}
        for node, costs in node_costs.items():
            requests = node_requests.get(node, {'cpu_requests': 0, 'memory_requests_gb': 0})
            
            # Fair share: node_cost / total_requests
            cpu_rate = (costs['cpu_cost_per_hour'] / requests['cpu_requests'] 
                       if requests['cpu_requests'] > 0 else self.cost_per_vcpu_hour)
            mem_rate = (costs['memory_cost_per_hour'] / requests['memory_requests_gb']
                       if requests['memory_requests_gb'] > 0 else self.cost_per_gb_memory_hour)
            
            node_cost_rates[node] = {
                'cpu_rate_per_core': cpu_rate,
                'memory_rate_per_gb': mem_rate,
                'node_hourly_cost': costs['total_cost_per_hour'],
                'total_cpu_requests': requests['cpu_requests'],
                'total_memory_requests_gb': requests['memory_requests_gb']
            }
        
        # Get workload requests and usage
        workload_requests = self.get_workload_requests(namespace)
        workload_usage = self.get_workload_usage(namespace)
        
        # Calculate costs per workload
        workloads = []
        total_hourly_cost = 0
        total_hourly_waste = 0
        
        for pod_data in workload_requests:
            ns = pod_data['namespace']
            pod = pod_data['pod']
            node = pod_data['node']
            
            # Get cost rates for this node
            rates = node_cost_rates.get(node, {
                'cpu_rate_per_core': self.cost_per_vcpu_hour,
                'memory_rate_per_gb': self.cost_per_gb_memory_hour
            })
            
            # Calculate request cost
            cpu_request = pod_data['cpu_request']
            memory_request = pod_data['memory_request_gb']
            
            cpu_cost_hourly = cpu_request * rates['cpu_rate_per_core']
            memory_cost_hourly = memory_request * rates['memory_rate_per_gb']
            total_cost_hourly = cpu_cost_hourly + memory_cost_hourly
            
            # Get actual usage
            key = f"{ns}/{pod}"
            usage = workload_usage.get(key, {'cpu_usage': 0, 'memory_usage_gb': 0})
            
            # Calculate waste (requested - actual)
            cpu_waste = max(0, cpu_request - usage['cpu_usage'])
            memory_waste = max(0, memory_request - usage['memory_usage_gb'])
            
            cpu_waste_cost = cpu_waste * rates['cpu_rate_per_core']
            memory_waste_cost = memory_waste * rates['memory_rate_per_gb']
            total_waste_hourly = cpu_waste_cost + memory_waste_cost
            
            # Calculate utilization
            cpu_util = (usage['cpu_usage'] / cpu_request * 100) if cpu_request > 0 else 0
            memory_util = (usage['memory_usage_gb'] / memory_request * 100) if memory_request > 0 else 0
            
            workloads.append({
                'namespace': ns,
                'pod': pod,
                'node': node,
                # Requests
                'cpu_request': round(cpu_request, 3),
                'memory_request_gb': round(memory_request, 3),
                # Actual usage
                'cpu_usage': round(usage['cpu_usage'], 3),
                'memory_usage_gb': round(usage['memory_usage_gb'], 3),
                # Utilization
                'cpu_utilization_percent': round(cpu_util, 1),
                'memory_utilization_percent': round(memory_util, 1),
                # Costs (hourly)
                'cpu_cost_hourly': round(cpu_cost_hourly, 4),
                'memory_cost_hourly': round(memory_cost_hourly, 4),
                'total_cost_hourly': round(total_cost_hourly, 4),
                # Waste (hourly)
                'cpu_waste_hourly': round(cpu_waste_cost, 4),
                'memory_waste_hourly': round(memory_waste_cost, 4),
                'total_waste_hourly': round(total_waste_hourly, 4),
                # Projections
                'cost_daily': round(total_cost_hourly * 24, 2),
                'cost_monthly': round(total_cost_hourly * 24 * 30, 2),
                'waste_daily': round(total_waste_hourly * 24, 2),
                'waste_monthly': round(total_waste_hourly * 24 * 30, 2),
            })
            
            total_hourly_cost += total_cost_hourly
            total_hourly_waste += total_waste_hourly
        
        # Sort by cost descending
        workloads.sort(key=lambda x: x['total_cost_hourly'], reverse=True)
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'workloads': workloads,
            'summary': {
                'total_workloads': len(workloads),
                'total_hourly_cost': round(total_hourly_cost, 4),
                'total_daily_cost': round(total_hourly_cost * 24, 2),
                'total_monthly_cost': round(total_hourly_cost * 24 * 30, 2),
                'total_hourly_waste': round(total_hourly_waste, 4),
                'total_daily_waste': round(total_hourly_waste * 24, 2),
                'total_monthly_waste': round(total_hourly_waste * 24 * 30, 2),
                'waste_percentage': round(total_hourly_waste / total_hourly_cost * 100, 1) if total_hourly_cost > 0 else 0
            },
            'pricing': {
                'vcpu_per_hour': self.cost_per_vcpu_hour,
                'memory_gb_per_hour': self.cost_per_gb_memory_hour,
                'allocation_model': 'fair_share'
            },
            'nodes': node_cost_rates
        }
    
    def get_deployment_realtime_cost(self, namespace: str, deployment: str) -> Dict:
        """
        Get real-time cost for a specific deployment.
        Aggregates all pods belonging to the deployment.
        """
        # Get all costs
        all_costs = self.calculate_realtime_costs(namespace)
        
        # Filter pods for this deployment
        deployment_pods = [
            w for w in all_costs['workloads']
            if w['namespace'] == namespace and deployment in w['pod']
        ]
        
        if not deployment_pods:
            return {
                'namespace': namespace,
                'deployment': deployment,
                'error': 'No pods found for deployment',
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Aggregate
        total_cpu_request = sum(p['cpu_request'] for p in deployment_pods)
        total_memory_request = sum(p['memory_request_gb'] for p in deployment_pods)
        total_cpu_usage = sum(p['cpu_usage'] for p in deployment_pods)
        total_memory_usage = sum(p['memory_usage_gb'] for p in deployment_pods)
        total_cost_hourly = sum(p['total_cost_hourly'] for p in deployment_pods)
        total_waste_hourly = sum(p['total_waste_hourly'] for p in deployment_pods)
        
        return {
            'namespace': namespace,
            'deployment': deployment,
            'replica_count': len(deployment_pods),
            'timestamp': datetime.utcnow().isoformat(),
            # Resources
            'total_cpu_request': round(total_cpu_request, 3),
            'total_memory_request_gb': round(total_memory_request, 3),
            'total_cpu_usage': round(total_cpu_usage, 3),
            'total_memory_usage_gb': round(total_memory_usage, 3),
            # Utilization
            'cpu_utilization_percent': round(total_cpu_usage / total_cpu_request * 100, 1) if total_cpu_request > 0 else 0,
            'memory_utilization_percent': round(total_memory_usage / total_memory_request * 100, 1) if total_memory_request > 0 else 0,
            # Costs
            'cost_hourly': round(total_cost_hourly, 4),
            'cost_daily': round(total_cost_hourly * 24, 2),
            'cost_monthly': round(total_cost_hourly * 24 * 30, 2),
            # Waste
            'waste_hourly': round(total_waste_hourly, 4),
            'waste_daily': round(total_waste_hourly * 24, 2),
            'waste_monthly': round(total_waste_hourly * 24 * 30, 2),
            'waste_percentage': round(total_waste_hourly / total_cost_hourly * 100, 1) if total_cost_hourly > 0 else 0,
            # Pods
            'pods': deployment_pods
        }
    
    def get_cluster_realtime_summary(self) -> Dict:
        """
        Get real-time cluster cost summary.
        """
        node_costs = self.get_node_costs()
        node_requests = self.get_node_requests()
        
        total_vcpu = sum(n['vcpu'] for n in node_costs.values())
        total_memory_gb = sum(n['memory_gb'] for n in node_costs.values())
        total_hourly_cost = sum(n['total_cost_per_hour'] for n in node_costs.values())
        
        total_cpu_requests = sum(n['cpu_requests'] for n in node_requests.values())
        total_memory_requests = sum(n['memory_requests_gb'] for n in node_requests.values())
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'cluster': {
                'total_nodes': len(node_costs),
                'total_vcpu': total_vcpu,
                'total_memory_gb': round(total_memory_gb, 2),
                'total_cpu_requests': round(total_cpu_requests, 3),
                'total_memory_requests_gb': round(total_memory_requests, 3),
                'cpu_utilization_percent': round(total_cpu_requests / total_vcpu * 100, 1) if total_vcpu > 0 else 0,
                'memory_utilization_percent': round(total_memory_requests / total_memory_gb * 100, 1) if total_memory_gb > 0 else 0,
            },
            'costs': {
                'hourly': round(total_hourly_cost, 4),
                'daily': round(total_hourly_cost * 24, 2),
                'monthly': round(total_hourly_cost * 24 * 30, 2),
                'yearly': round(total_hourly_cost * 24 * 365, 2),
            },
            'pricing': {
                'vcpu_per_hour': self.cost_per_vcpu_hour,
                'memory_gb_per_hour': self.cost_per_gb_memory_hour,
            },
            'nodes': [
                {
                    'name': name,
                    'vcpu': data['vcpu'],
                    'memory_gb': round(data['memory_gb'], 2),
                    'hourly_cost': round(data['total_cost_per_hour'], 4),
                    'cpu_requests': round(node_requests.get(name, {}).get('cpu_requests', 0), 3),
                    'memory_requests_gb': round(node_requests.get(name, {}).get('memory_requests_gb', 0), 3),
                    'pod_count': node_requests.get(name, {}).get('pod_count', 0),
                }
                for name, data in node_costs.items()
            ]
        }
