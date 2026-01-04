"""
Node Efficiency Analyzer
Cluster-level node utilization and bin-packing efficiency analysis
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from kubernetes import client

logger = logging.getLogger(__name__)


@dataclass
class NodeMetrics:
    """Node resource metrics"""
    name: str
    cpu_capacity: float  # cores
    memory_capacity: float  # GB
    cpu_allocatable: float  # cores
    memory_allocatable: float  # GB
    cpu_requests: float  # cores
    memory_requests: float  # GB
    cpu_usage: float  # cores (actual usage)
    memory_usage: float  # GB (actual usage)
    pod_count: int
    pod_capacity: int
    labels: Dict[str, str]
    taints: List[str]
    node_type: str  # general-purpose, compute-optimized, memory-optimized


@dataclass
class NodeEfficiencyReport:
    """Cluster-wide node efficiency report"""
    timestamp: datetime
    total_nodes: int
    total_cpu_capacity: float
    total_memory_capacity: float
    total_cpu_requests: float
    total_memory_requests: float
    total_cpu_usage: float
    total_memory_usage: float
    cpu_request_utilization: float  # % of capacity requested
    memory_request_utilization: float  # % of capacity requested
    cpu_actual_utilization: float  # % of capacity actually used
    memory_actual_utilization: float  # % of capacity actually used
    wasted_cpu_requests: float  # cores requested but not used
    wasted_memory_requests: float  # GB requested but not used
    bin_packing_efficiency: float  # 0-100 score
    underutilized_nodes: List[str]  # nodes with <30% utilization
    overutilized_nodes: List[str]  # nodes with >85% utilization
    node_breakdown: List[NodeMetrics]
    recommendations: List[str]


class NodeEfficiencyAnalyzer:
    """Analyze cluster-wide node efficiency and bin-packing"""
    
    def __init__(self, core_v1: client.CoreV1Api, custom_api: client.CustomObjectsApi):
        self.core_v1 = core_v1
        self.custom_api = custom_api
        
        # Thresholds
        self.underutilized_threshold = 30.0  # %
        self.overutilized_threshold = 85.0  # %
        self.optimal_utilization_range = (60.0, 80.0)  # %
    
    def analyze_cluster_efficiency(self) -> Optional[NodeEfficiencyReport]:
        """
        Analyze cluster-wide node efficiency.
        
        Returns comprehensive report on node utilization, bin-packing efficiency,
        and optimization opportunities.
        """
        try:
            # Get all nodes
            nodes = self.core_v1.list_node()
            if not nodes.items:
                logger.warning("No nodes found in cluster")
                return None
            
            # Get metrics for each node
            node_metrics_list = []
            for node in nodes.items:
                metrics = self._get_node_metrics(node)
                if metrics:
                    node_metrics_list.append(metrics)
            
            if not node_metrics_list:
                logger.warning("No node metrics available")
                return None
            
            # Calculate cluster-wide totals
            total_cpu_capacity = sum(n.cpu_allocatable for n in node_metrics_list)
            total_memory_capacity = sum(n.memory_allocatable for n in node_metrics_list)
            total_cpu_requests = sum(n.cpu_requests for n in node_metrics_list)
            total_memory_requests = sum(n.memory_requests for n in node_metrics_list)
            total_cpu_usage = sum(n.cpu_usage for n in node_metrics_list)
            total_memory_usage = sum(n.memory_usage for n in node_metrics_list)
            
            # Calculate utilization percentages
            cpu_request_util = (total_cpu_requests / total_cpu_capacity * 100) if total_cpu_capacity > 0 else 0
            memory_request_util = (total_memory_requests / total_memory_capacity * 100) if total_memory_capacity > 0 else 0
            cpu_actual_util = (total_cpu_usage / total_cpu_capacity * 100) if total_cpu_capacity > 0 else 0
            memory_actual_util = (total_memory_usage / total_memory_capacity * 100) if total_memory_capacity > 0 else 0
            
            # Calculate waste
            wasted_cpu = total_cpu_requests - total_cpu_usage
            wasted_memory = total_memory_requests - total_memory_usage
            
            # Identify problematic nodes
            underutilized = []
            overutilized = []
            
            for node in node_metrics_list:
                # Calculate node utilization (based on actual usage vs allocatable)
                node_cpu_util = (node.cpu_usage / node.cpu_allocatable * 100) if node.cpu_allocatable > 0 else 0
                node_memory_util = (node.memory_usage / node.memory_allocatable * 100) if node.memory_allocatable > 0 else 0
                avg_util = (node_cpu_util + node_memory_util) / 2
                
                if avg_util < self.underutilized_threshold:
                    underutilized.append(node.name)
                elif avg_util > self.overutilized_threshold:
                    overutilized.append(node.name)
            
            # Calculate bin-packing efficiency score
            bin_packing_score = self._calculate_bin_packing_efficiency(node_metrics_list)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                node_metrics_list,
                cpu_request_util,
                memory_request_util,
                cpu_actual_util,
                memory_actual_util,
                wasted_cpu,
                wasted_memory,
                bin_packing_score,
                underutilized,
                overutilized
            )
            
            return NodeEfficiencyReport(
                timestamp=datetime.now(),
                total_nodes=len(node_metrics_list),
                total_cpu_capacity=total_cpu_capacity,
                total_memory_capacity=total_memory_capacity,
                total_cpu_requests=total_cpu_requests,
                total_memory_requests=total_memory_requests,
                total_cpu_usage=total_cpu_usage,
                total_memory_usage=total_memory_usage,
                cpu_request_utilization=cpu_request_util,
                memory_request_utilization=memory_request_util,
                cpu_actual_utilization=cpu_actual_util,
                memory_actual_utilization=memory_actual_util,
                wasted_cpu_requests=wasted_cpu,
                wasted_memory_requests=wasted_memory,
                bin_packing_efficiency=bin_packing_score,
                underutilized_nodes=underutilized,
                overutilized_nodes=overutilized,
                node_breakdown=node_metrics_list,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error analyzing cluster efficiency: {e}", exc_info=True)
            return None
    
    def _get_node_metrics(self, node) -> Optional[NodeMetrics]:
        """Get metrics for a single node"""
        try:
            node_name = node.metadata.name
            
            # Get capacity and allocatable resources
            capacity = node.status.capacity
            allocatable = node.status.allocatable
            
            cpu_capacity = self._parse_cpu(capacity.get('cpu', '0'))
            memory_capacity = self._parse_memory(capacity.get('memory', '0'))
            cpu_allocatable = self._parse_cpu(allocatable.get('cpu', '0'))
            memory_allocatable = self._parse_memory(allocatable.get('memory', '0'))
            pod_capacity = int(allocatable.get('pods', '0'))
            
            # Get pod requests on this node
            pods = self.core_v1.list_pod_for_all_namespaces(
                field_selector=f'spec.nodeName={node_name}'
            )
            
            cpu_requests = 0.0
            memory_requests = 0.0
            pod_count = len(pods.items)
            
            for pod in pods.items:
                if pod.spec.containers:
                    for container in pod.spec.containers:
                        if container.resources and container.resources.requests:
                            cpu_req = container.resources.requests.get('cpu', '0')
                            mem_req = container.resources.requests.get('memory', '0')
                            cpu_requests += self._parse_cpu(cpu_req)
                            memory_requests += self._parse_memory(mem_req)
            
            # Get actual usage from metrics server
            cpu_usage, memory_usage = self._get_node_usage(node_name)
            
            # Determine node type from labels
            labels = node.metadata.labels or {}
            node_type = self._determine_node_type(labels)
            
            # Get taints
            taints = []
            if node.spec.taints:
                taints = [f"{t.key}={t.value}:{t.effect}" for t in node.spec.taints]
            
            return NodeMetrics(
                name=node_name,
                cpu_capacity=cpu_capacity,
                memory_capacity=memory_capacity,
                cpu_allocatable=cpu_allocatable,
                memory_allocatable=memory_allocatable,
                cpu_requests=cpu_requests,
                memory_requests=memory_requests,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                pod_count=pod_count,
                pod_capacity=pod_capacity,
                labels=labels,
                taints=taints,
                node_type=node_type
            )
            
        except Exception as e:
            logger.error(f"Error getting metrics for node {node.metadata.name}: {e}")
            return None
    
    def _get_node_usage(self, node_name: str) -> Tuple[float, float]:
        """Get actual CPU and memory usage from metrics server"""
        try:
            # Try to get metrics from metrics-server
            metrics = self.custom_api.get_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="nodes",
                name=node_name
            )
            
            cpu_usage = self._parse_cpu(metrics['usage'].get('cpu', '0'))
            memory_usage = self._parse_memory(metrics['usage'].get('memory', '0'))
            
            return cpu_usage, memory_usage
            
        except Exception as e:
            logger.debug(f"Could not get metrics for node {node_name}: {e}")
            # Return 0 if metrics-server not available
            return 0.0, 0.0
    
    def _parse_cpu(self, cpu_str: str) -> float:
        """Parse CPU string to cores (e.g., '2', '500m' -> 0.5)"""
        if not cpu_str:
            return 0.0
        
        cpu_str = str(cpu_str).strip()
        if cpu_str.endswith('m'):
            return float(cpu_str[:-1]) / 1000.0
        elif cpu_str.endswith('n'):
            return float(cpu_str[:-1]) / 1000000000.0
        else:
            return float(cpu_str)
    
    def _parse_memory(self, mem_str: str) -> float:
        """Parse memory string to GB"""
        if not mem_str:
            return 0.0
        
        mem_str = str(mem_str).strip()
        
        # Handle different units
        units = {
            'Ki': 1024,
            'Mi': 1024 ** 2,
            'Gi': 1024 ** 3,
            'Ti': 1024 ** 4,
            'K': 1000,
            'M': 1000 ** 2,
            'G': 1000 ** 3,
            'T': 1000 ** 4,
        }
        
        for unit, multiplier in units.items():
            if mem_str.endswith(unit):
                value = float(mem_str[:-len(unit)])
                return (value * multiplier) / (1024 ** 3)  # Convert to GB
        
        # No unit, assume bytes
        return float(mem_str) / (1024 ** 3)
    
    def _determine_node_type(self, labels: Dict[str, str]) -> str:
        """Determine node type from labels"""
        # Check common cloud provider labels
        instance_type = labels.get('node.kubernetes.io/instance-type', '')
        
        if not instance_type:
            instance_type = labels.get('beta.kubernetes.io/instance-type', '')
        
        # Classify based on instance type patterns
        instance_lower = instance_type.lower()
        
        if any(x in instance_lower for x in ['c5', 'c6', 'compute', 'cpu']):
            return 'compute-optimized'
        elif any(x in instance_lower for x in ['r5', 'r6', 'memory', 'ram']):
            return 'memory-optimized'
        elif any(x in instance_lower for x in ['g4', 'p3', 'gpu']):
            return 'gpu'
        else:
            return 'general-purpose'
    
    def _calculate_bin_packing_efficiency(self, nodes: List[NodeMetrics]) -> float:
        """
        Calculate bin-packing efficiency score (0-100).
        
        Higher score = better bin-packing (resources well-distributed).
        Lower score = poor bin-packing (uneven distribution).
        """
        if not nodes:
            return 0.0
        
        # Calculate variance in node utilization
        utilizations = []
        for node in nodes:
            cpu_util = (node.cpu_requests / node.cpu_allocatable * 100) if node.cpu_allocatable > 0 else 0
            mem_util = (node.memory_requests / node.memory_allocatable * 100) if node.memory_allocatable > 0 else 0
            avg_util = (cpu_util + mem_util) / 2
            utilizations.append(avg_util)
        
        if not utilizations:
            return 0.0
        
        # Calculate standard deviation
        mean_util = sum(utilizations) / len(utilizations)
        variance = sum((x - mean_util) ** 2 for x in utilizations) / len(utilizations)
        std_dev = variance ** 0.5
        
        # Score: lower std_dev = better bin-packing
        # Perfect score (100) when std_dev = 0
        # Score decreases as std_dev increases
        # Normalize: std_dev of 30% = score of 50
        score = max(0, 100 - (std_dev * 100 / 30))
        
        # Bonus points for optimal utilization range
        nodes_in_optimal = sum(1 for u in utilizations if self.optimal_utilization_range[0] <= u <= self.optimal_utilization_range[1])
        optimal_bonus = (nodes_in_optimal / len(nodes)) * 20
        
        return min(100, score + optimal_bonus)
    
    def _generate_recommendations(
        self,
        nodes: List[NodeMetrics],
        cpu_request_util: float,
        memory_request_util: float,
        cpu_actual_util: float,
        memory_actual_util: float,
        wasted_cpu: float,
        wasted_memory: float,
        bin_packing_score: float,
        underutilized: List[str],
        overutilized: List[str]
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Resource request optimization
        if wasted_cpu > 1.0:  # More than 1 core wasted
            recommendations.append(
                f"⚠️ {wasted_cpu:.1f} CPU cores are requested but not used. "
                f"Review pod resource requests to reduce waste."
            )
        
        if wasted_memory > 2.0:  # More than 2GB wasted
            recommendations.append(
                f"⚠️ {wasted_memory:.1f} GB memory is requested but not used. "
                f"Review pod memory requests to reduce waste."
            )
        
        # Cluster utilization
        if cpu_request_util < 50:
            recommendations.append(
                f"💡 Cluster CPU request utilization is low ({cpu_request_util:.1f}%). "
                f"Consider consolidating workloads or reducing cluster size."
            )
        
        if memory_request_util < 50:
            recommendations.append(
                f"💡 Cluster memory request utilization is low ({memory_request_util:.1f}%). "
                f"Consider consolidating workloads or reducing cluster size."
            )
        
        # Bin-packing efficiency
        if bin_packing_score < 60:
            recommendations.append(
                f"📦 Bin-packing efficiency is suboptimal ({bin_packing_score:.0f}/100). "
                f"Workloads are unevenly distributed across nodes."
            )
        
        # Underutilized nodes
        if underutilized:
            if len(underutilized) == 1:
                recommendations.append(
                    f"🔻 Node {underutilized[0]} is underutilized (<30%). "
                    f"Consider draining and removing this node."
                )
            else:
                recommendations.append(
                    f"🔻 {len(underutilized)} nodes are underutilized (<30%). "
                    f"Consider consolidating workloads: {', '.join(underutilized[:3])}"
                )
        
        # Overutilized nodes
        if overutilized:
            if len(overutilized) == 1:
                recommendations.append(
                    f"🔺 Node {overutilized[0]} is overutilized (>85%). "
                    f"Risk of resource contention and performance issues."
                )
            else:
                recommendations.append(
                    f"🔺 {len(overutilized)} nodes are overutilized (>85%). "
                    f"Consider adding capacity: {', '.join(overutilized[:3])}"
                )
        
        # Node type optimization
        node_types = {}
        for node in nodes:
            node_types[node.node_type] = node_types.get(node.node_type, 0) + 1
        
        if len(node_types) > 1:
            # Check if workloads match node types
            for node in nodes:
                if node.node_type == 'compute-optimized':
                    cpu_util = (node.cpu_usage / node.cpu_allocatable * 100) if node.cpu_allocatable > 0 else 0
                    mem_util = (node.memory_usage / node.memory_allocatable * 100) if node.memory_allocatable > 0 else 0
                    if mem_util > cpu_util + 20:  # Memory-heavy on compute node
                        recommendations.append(
                            f"💡 Node {node.name} is compute-optimized but running memory-heavy workloads. "
                            f"Consider using memory-optimized nodes."
                        )
                        break
        
        # If everything looks good
        if not recommendations:
            recommendations.append("✅ Cluster efficiency looks good! No major optimization opportunities detected.")
        
        return recommendations
