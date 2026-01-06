"""
Real-time Cost Tracking Module
Uses Prometheus for live cost tracking without storing metrics locally.

Features:
- Real-time cost per workload (Deployment, StatefulSet, DaemonSet)
- Groups pods by owner workload instead of individual pod IDs
- Smart waste tracking - considers optimal utilization targets
- Fair share allocation based on node costs
- No local storage needed - all data from Prometheus

Optimal Utilization Targets:
- CPU: ~25% is optimal (allows burst capacity)
- Memory: ~65% is optimal (allows for growth)
- If utilization is at or above target, no waste is reported
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# Optimal utilization targets - at these levels, there's no waste
OPTIMAL_CPU_UTILIZATION = 25.0  # 25% CPU is optimal
OPTIMAL_MEMORY_UTILIZATION = 65.0  # 65% memory is optimal


class RealtimeCostTracker:
    """
    Real-time cost tracking using Prometheus.
    
    Cost Model (Fair Share):
    - Node cost = node_vcpu × vcpu_price + node_memory_gb × memory_price
    - Cost per requested CPU = node_cpu_cost / total_cpu_requests_on_node
    - Workload cost = workload_request × cost_per_request
    
    Waste Calculation (Smart):
    - If CPU utilization >= 25% → No CPU waste (optimal)
    - If Memory utilization >= 65% → No memory waste (optimal)
    - Waste only counted when utilization is below optimal targets
    """
    
    def __init__(self, operator, cost_per_vcpu_hour: float = 0.045, 
                 cost_per_gb_memory_hour: float = 0.006):
        self.operator = operator
        self.cost_per_vcpu_hour = cost_per_vcpu_hour
        self.cost_per_gb_memory_hour = cost_per_gb_memory_hour
        self.optimal_cpu_util = OPTIMAL_CPU_UTILIZATION
        self.optimal_memory_util = OPTIMAL_MEMORY_UTILIZATION
    
    def _query_prometheus(self, query: str):
        """Query Prometheus via operator's analyzer"""
        try:
            result = self.operator.controller.analyzer._query_prometheus(query)
            logger.debug(f"Prometheus query '{query[:50]}...' returned {len(result) if result else 0} results")
            return result
        except Exception as e:
            logger.warning(f"Prometheus query failed for '{query[:50]}...': {e}")
            return None
    
    # ============================================
    # Real-time Node Cost Queries
    # ============================================
    
    def get_node_costs(self) -> Dict:
        """Get real-time node costs from Prometheus."""
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
        """Get total resource requests per node from Prometheus."""
        nodes = defaultdict(lambda: {'cpu_requests': 0, 'memory_requests_gb': 0, 'pod_count': 0})
        
        cpu_query = 'sum by (node) (kube_pod_container_resource_requests{resource="cpu"})'
        cpu_result = self._query_prometheus(cpu_query)
        
        if cpu_result:
            for item in cpu_result:
                node = item['metric'].get('node', 'unknown')
                cpu_cores = float(item['value'][1])
                nodes[node]['cpu_requests'] = cpu_cores
        
        mem_query = 'sum by (node) (kube_pod_container_resource_requests{resource="memory"})'
        mem_result = self._query_prometheus(mem_query)
        
        if mem_result:
            for item in mem_result:
                node = item['metric'].get('node', 'unknown')
                memory_bytes = float(item['value'][1])
                nodes[node]['memory_requests_gb'] = memory_bytes / (1024 ** 3)
        
        pod_query = 'count by (node) (kube_pod_info)'
        pod_result = self._query_prometheus(pod_query)
        
        if pod_result:
            for item in pod_result:
                node = item['metric'].get('node', 'unknown')
                nodes[node]['pod_count'] = int(float(item['value'][1]))
        
        return dict(nodes)
    
    # ============================================
    # Workload Owner Detection
    # ============================================
    
    def get_pod_owners(self) -> Dict[str, Dict]:
        """
        Get pod owner references (Deployment, StatefulSet, DaemonSet).
        Returns mapping of pod -> owner workload info.
        """
        pod_owners = {}
        
        # Query kube_pod_owner to get ReplicaSet/StatefulSet/DaemonSet owners
        owner_query = 'kube_pod_owner{owner_kind=~"ReplicaSet|StatefulSet|DaemonSet"}'
        owner_result = self._query_prometheus(owner_query)
        
        if owner_result:
            for item in owner_result:
                ns = item['metric'].get('namespace', 'unknown')
                pod = item['metric'].get('pod', 'unknown')
                owner_kind = item['metric'].get('owner_kind', 'unknown')
                owner_name = item['metric'].get('owner_name', 'unknown')
                
                key = f"{ns}/{pod}"
                pod_owners[key] = {
                    'namespace': ns,
                    'pod': pod,
                    'owner_kind': owner_kind,
                    'owner_name': owner_name
                }
        
        # For ReplicaSets, get the Deployment owner
        rs_query = 'kube_replicaset_owner{owner_kind="Deployment"}'
        rs_result = self._query_prometheus(rs_query)
        
        rs_to_deployment = {}
        if rs_result:
            for item in rs_result:
                ns = item['metric'].get('namespace', 'unknown')
                rs_name = item['metric'].get('replicaset', 'unknown')
                deployment = item['metric'].get('owner_name', 'unknown')
                rs_to_deployment[f"{ns}/{rs_name}"] = deployment
        
        # Update pod owners to point to Deployment instead of ReplicaSet
        for key, owner in pod_owners.items():
            if owner['owner_kind'] == 'ReplicaSet':
                rs_key = f"{owner['namespace']}/{owner['owner_name']}"
                if rs_key in rs_to_deployment:
                    owner['workload_kind'] = 'Deployment'
                    owner['workload_name'] = rs_to_deployment[rs_key]
                else:
                    # Orphan ReplicaSet, use RS name
                    owner['workload_kind'] = 'ReplicaSet'
                    owner['workload_name'] = owner['owner_name']
            else:
                owner['workload_kind'] = owner['owner_kind']
                owner['workload_name'] = owner['owner_name']
        
        return pod_owners
    
    # ============================================
    # Workload Resource Queries (Grouped by Owner)
    # ============================================
    
    def get_workload_resources(self, namespace: str = None) -> Dict[str, Dict]:
        """
        Get resource requests and usage grouped by workload (Deployment/StatefulSet/DaemonSet).
        """
        ns_filter = f'namespace="{namespace}"' if namespace else ''
        
        # Get pod owners first
        pod_owners = self.get_pod_owners()
        
        # Get CPU requests per pod
        cpu_req_query = f'sum by (namespace, pod, node) (kube_pod_container_resource_requests{{resource="cpu"{", " + ns_filter if ns_filter else ""}}})'
        cpu_req_result = self._query_prometheus(cpu_req_query)
        
        # Get memory requests per pod
        mem_req_query = f'sum by (namespace, pod, node) (kube_pod_container_resource_requests{{resource="memory"{", " + ns_filter if ns_filter else ""}}})'
        mem_req_result = self._query_prometheus(mem_req_query)
        
        # Get CPU usage per pod
        cpu_usage_query = f'sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{{{ns_filter}}}[5m]))'
        cpu_usage_result = self._query_prometheus(cpu_usage_query)
        
        # Get memory usage per pod
        mem_usage_query = f'sum by (namespace, pod) (container_memory_working_set_bytes{{{ns_filter}}})'
        mem_usage_result = self._query_prometheus(mem_usage_query)
        
        # Build pod data
        pods = {}
        
        if cpu_req_result:
            for item in cpu_req_result:
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
                    'memory_request_gb': 0,
                    'cpu_usage': 0,
                    'memory_usage_gb': 0
                }
        
        if mem_req_result:
            for item in mem_req_result:
                ns = item['metric'].get('namespace', 'unknown')
                pod = item['metric'].get('pod', 'unknown')
                memory_bytes = float(item['value'][1])
                key = f"{ns}/{pod}"
                if key in pods:
                    pods[key]['memory_request_gb'] = memory_bytes / (1024 ** 3)
        
        if cpu_usage_result:
            for item in cpu_usage_result:
                ns = item['metric'].get('namespace', 'unknown')
                pod = item['metric'].get('pod', 'unknown')
                if not pod:
                    continue
                cpu = float(item['value'][1])
                key = f"{ns}/{pod}"
                if key in pods:
                    pods[key]['cpu_usage'] = cpu
        
        if mem_usage_result:
            for item in mem_usage_result:
                ns = item['metric'].get('namespace', 'unknown')
                pod = item['metric'].get('pod', 'unknown')
                if not pod:
                    continue
                memory_bytes = float(item['value'][1])
                key = f"{ns}/{pod}"
                if key in pods:
                    pods[key]['memory_usage_gb'] = memory_bytes / (1024 ** 3)
        
        # Group pods by workload
        workloads = defaultdict(lambda: {
            'namespace': '',
            'workload_kind': 'Unknown',
            'workload_name': 'unknown',
            'pod_count': 0,
            'cpu_request': 0,
            'memory_request_gb': 0,
            'cpu_usage': 0,
            'memory_usage_gb': 0,
            'nodes': set(),
            'pods': []
        })
        
        for pod_key, pod_data in pods.items():
            owner = pod_owners.get(pod_key, {})
            workload_kind = owner.get('workload_kind', 'Unknown')
            workload_name = owner.get('workload_name', self._extract_workload_name(pod_data['pod']))
            ns = pod_data['namespace']
            
            workload_key = f"{ns}/{workload_kind}/{workload_name}"
            
            workloads[workload_key]['namespace'] = ns
            workloads[workload_key]['workload_kind'] = workload_kind
            workloads[workload_key]['workload_name'] = workload_name
            workloads[workload_key]['pod_count'] += 1
            workloads[workload_key]['cpu_request'] += pod_data['cpu_request']
            workloads[workload_key]['memory_request_gb'] += pod_data['memory_request_gb']
            workloads[workload_key]['cpu_usage'] += pod_data['cpu_usage']
            workloads[workload_key]['memory_usage_gb'] += pod_data['memory_usage_gb']
            workloads[workload_key]['nodes'].add(pod_data['node'])
            workloads[workload_key]['pods'].append(pod_data['pod'])
        
        # Convert sets to lists
        for wl in workloads.values():
            wl['nodes'] = list(wl['nodes'])
        
        return dict(workloads)
    
    def _extract_workload_name(self, pod_name: str) -> str:
        """Extract workload name from pod name (fallback when owner info unavailable)."""
        # Pod names typically: deployment-name-replicaset-hash-pod-hash
        # or: statefulset-name-0
        parts = pod_name.rsplit('-', 2)
        if len(parts) >= 3:
            return parts[0]
        parts = pod_name.rsplit('-', 1)
        if len(parts) >= 2:
            return parts[0]
        return pod_name
    
    # ============================================
    # Smart Waste Calculation
    # ============================================
    
    def calculate_smart_waste(self, cpu_request: float, cpu_usage: float,
                               memory_request_gb: float, memory_usage_gb: float,
                               cpu_rate: float, memory_rate: float) -> Dict:
        """
        Calculate waste using smart thresholds.
        
        Optimal utilization:
        - CPU: 25% is optimal (allows burst capacity)
        - Memory: 65% is optimal (allows for growth)
        
        If utilization >= optimal, no waste is reported.
        """
        # Calculate utilization percentages
        cpu_util = (cpu_usage / cpu_request * 100) if cpu_request > 0 else 0
        memory_util = (memory_usage_gb / memory_request_gb * 100) if memory_request_gb > 0 else 0
        
        # CPU waste calculation
        if cpu_util >= self.optimal_cpu_util:
            # At or above optimal - no waste
            cpu_waste = 0
            cpu_waste_cost = 0
            cpu_status = 'optimal'
        else:
            # Below optimal - calculate waste based on gap to optimal
            # Waste = resources needed to reach optimal that are unused
            optimal_usage = cpu_request * (self.optimal_cpu_util / 100)
            cpu_waste = max(0, optimal_usage - cpu_usage)
            cpu_waste_cost = cpu_waste * cpu_rate
            cpu_status = 'underutilized'
        
        # Memory waste calculation
        if memory_util >= self.optimal_memory_util:
            # At or above optimal - no waste
            memory_waste = 0
            memory_waste_cost = 0
            memory_status = 'optimal'
        else:
            # Below optimal - calculate waste based on gap to optimal
            optimal_usage = memory_request_gb * (self.optimal_memory_util / 100)
            memory_waste = max(0, optimal_usage - memory_usage_gb)
            memory_waste_cost = memory_waste * memory_rate
            memory_status = 'underutilized'
        
        total_waste_cost = cpu_waste_cost + memory_waste_cost
        
        return {
            'cpu_utilization_percent': round(cpu_util, 1),
            'memory_utilization_percent': round(memory_util, 1),
            'cpu_status': cpu_status,
            'memory_status': memory_status,
            'cpu_waste_hourly': round(cpu_waste_cost, 4),
            'memory_waste_hourly': round(memory_waste_cost, 4),
            'total_waste_hourly': round(total_waste_cost, 4),
            'is_optimal': cpu_status == 'optimal' and memory_status == 'optimal'
        }
    
    # ============================================
    # Real-time Cost Calculation
    # ============================================
    
    def calculate_realtime_costs(self, namespace: str = None) -> Dict:
        """
        Calculate real-time costs for all workloads grouped by owner.
        
        Returns:
        - Per-workload cost (Deployment/StatefulSet/DaemonSet)
        - Smart waste calculation (considers optimal utilization)
        - Cluster totals
        """
        # Get node costs and requests
        node_costs = self.get_node_costs()
        node_requests = self.get_node_requests()
        
        # Calculate cost per requested unit per node
        node_cost_rates = {}
        for node, costs in node_costs.items():
            requests = node_requests.get(node, {'cpu_requests': 0, 'memory_requests_gb': 0})
            
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
        
        # Get workload resources grouped by owner
        workload_resources = self.get_workload_resources(namespace)
        
        # Calculate costs per workload
        workloads = []
        total_hourly_cost = 0
        total_hourly_waste = 0
        optimal_count = 0
        
        # Use average rates across nodes for simplicity
        avg_cpu_rate = self.cost_per_vcpu_hour
        avg_mem_rate = self.cost_per_gb_memory_hour
        if node_cost_rates:
            avg_cpu_rate = sum(r['cpu_rate_per_core'] for r in node_cost_rates.values()) / len(node_cost_rates)
            avg_mem_rate = sum(r['memory_rate_per_gb'] for r in node_cost_rates.values()) / len(node_cost_rates)
        
        for workload_key, wl_data in workload_resources.items():
            cpu_request = wl_data['cpu_request']
            memory_request = wl_data['memory_request_gb']
            cpu_usage = wl_data['cpu_usage']
            memory_usage = wl_data['memory_usage_gb']
            
            # Calculate costs
            cpu_cost_hourly = cpu_request * avg_cpu_rate
            memory_cost_hourly = memory_request * avg_mem_rate
            total_cost_hourly_wl = cpu_cost_hourly + memory_cost_hourly
            
            # Calculate smart waste
            waste_info = self.calculate_smart_waste(
                cpu_request, cpu_usage,
                memory_request, memory_usage,
                avg_cpu_rate, avg_mem_rate
            )
            
            if waste_info['is_optimal']:
                optimal_count += 1
            
            workloads.append({
                'namespace': wl_data['namespace'],
                'workload_kind': wl_data['workload_kind'],
                'workload_name': wl_data['workload_name'],
                'pod_count': wl_data['pod_count'],
                'nodes': wl_data['nodes'],
                # Requests
                'cpu_request': round(cpu_request, 3),
                'memory_request_gb': round(memory_request, 3),
                # Actual usage
                'cpu_usage': round(cpu_usage, 3),
                'memory_usage_gb': round(memory_usage, 3),
                # Utilization & status
                'cpu_utilization_percent': waste_info['cpu_utilization_percent'],
                'memory_utilization_percent': waste_info['memory_utilization_percent'],
                'cpu_status': waste_info['cpu_status'],
                'memory_status': waste_info['memory_status'],
                'is_optimal': waste_info['is_optimal'],
                # Costs (hourly)
                'cpu_cost_hourly': round(cpu_cost_hourly, 4),
                'memory_cost_hourly': round(memory_cost_hourly, 4),
                'total_cost_hourly': round(total_cost_hourly_wl, 4),
                # Waste (hourly) - smart calculation
                'cpu_waste_hourly': waste_info['cpu_waste_hourly'],
                'memory_waste_hourly': waste_info['memory_waste_hourly'],
                'total_waste_hourly': waste_info['total_waste_hourly'],
                # Projections
                'cost_daily': round(total_cost_hourly_wl * 24, 2),
                'cost_monthly': round(total_cost_hourly_wl * 24 * 30, 2),
                'waste_daily': round(waste_info['total_waste_hourly'] * 24, 2),
                'waste_monthly': round(waste_info['total_waste_hourly'] * 24 * 30, 2),
            })
            
            total_hourly_cost += total_cost_hourly_wl
            total_hourly_waste += waste_info['total_waste_hourly']
        
        # Sort by cost descending
        workloads.sort(key=lambda x: x['total_cost_hourly'], reverse=True)
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'workloads': workloads,
            'summary': {
                'total_workloads': len(workloads),
                'optimal_workloads': optimal_count,
                'total_hourly_cost': round(total_hourly_cost, 4),
                'total_daily_cost': round(total_hourly_cost * 24, 2),
                'total_monthly_cost': round(total_hourly_cost * 24 * 30, 2),
                'total_hourly_waste': round(total_hourly_waste, 4),
                'total_daily_waste': round(total_hourly_waste * 24, 2),
                'total_monthly_waste': round(total_hourly_waste * 24 * 30, 2),
                'waste_percentage': round(total_hourly_waste / total_hourly_cost * 100, 1) if total_hourly_cost > 0 else 0,
                'optimal_targets': {
                    'cpu_percent': self.optimal_cpu_util,
                    'memory_percent': self.optimal_memory_util
                }
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
        """
        all_costs = self.calculate_realtime_costs(namespace)
        
        # Find the deployment workload
        for wl in all_costs['workloads']:
            if (wl['namespace'] == namespace and 
                wl['workload_kind'] == 'Deployment' and 
                wl['workload_name'] == deployment):
                return {
                    'namespace': namespace,
                    'deployment': deployment,
                    'workload_kind': 'Deployment',
                    'timestamp': datetime.utcnow().isoformat(),
                    **wl,
                    'optimal_targets': {
                        'cpu_percent': self.optimal_cpu_util,
                        'memory_percent': self.optimal_memory_util
                    }
                }
        
        # Try fuzzy match (deployment name in workload name)
        for wl in all_costs['workloads']:
            if wl['namespace'] == namespace and deployment in wl['workload_name']:
                return {
                    'namespace': namespace,
                    'deployment': deployment,
                    'workload_kind': wl['workload_kind'],
                    'timestamp': datetime.utcnow().isoformat(),
                    **wl,
                    'optimal_targets': {
                        'cpu_percent': self.optimal_cpu_util,
                        'memory_percent': self.optimal_memory_util
                    }
                }
        
        return {
            'namespace': namespace,
            'deployment': deployment,
            'error': 'No workload found',
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_cluster_realtime_summary(self) -> Dict:
        """Get real-time cluster cost summary."""
        node_costs = self.get_node_costs()
        node_requests = self.get_node_requests()
        
        total_vcpu = sum(n['vcpu'] for n in node_costs.values())
        total_memory_gb = sum(n['memory_gb'] for n in node_costs.values())
        total_hourly_cost = sum(n['total_cost_per_hour'] for n in node_costs.values())
        
        total_cpu_requests = sum(n['cpu_requests'] for n in node_requests.values())
        total_memory_requests = sum(n['memory_requests_gb'] for n in node_requests.values())
        
        # Calculate cluster-level utilization status
        cpu_util = (total_cpu_requests / total_vcpu * 100) if total_vcpu > 0 else 0
        memory_util = (total_memory_requests / total_memory_gb * 100) if total_memory_gb > 0 else 0
        
        cpu_status = 'optimal' if cpu_util >= self.optimal_cpu_util else 'underutilized'
        memory_status = 'optimal' if memory_util >= self.optimal_memory_util else 'underutilized'
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'cluster': {
                'total_nodes': len(node_costs),
                'total_vcpu': total_vcpu,
                'total_memory_gb': round(total_memory_gb, 2),
                'total_cpu_requests': round(total_cpu_requests, 3),
                'total_memory_requests_gb': round(total_memory_requests, 3),
                'cpu_utilization_percent': round(cpu_util, 1),
                'memory_utilization_percent': round(memory_util, 1),
                'cpu_status': cpu_status,
                'memory_status': memory_status,
                'is_optimal': cpu_status == 'optimal' or memory_status == 'optimal',
            },
            'optimal_targets': {
                'cpu_percent': self.optimal_cpu_util,
                'memory_percent': self.optimal_memory_util
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
