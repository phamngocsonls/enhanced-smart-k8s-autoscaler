"""
Tests for Node Efficiency Analyzer
"""

import pytest
from unittest.mock import Mock, MagicMock
from src.node_efficiency import NodeEfficiencyAnalyzer, NodeMetrics


class TestNodeEfficiencyAnalyzer:
    """Test NodeEfficiencyAnalyzer"""
    
    def test_parse_cpu(self):
        """Test CPU parsing"""
        core_v1 = Mock()
        custom_api = Mock()
        analyzer = NodeEfficiencyAnalyzer(core_v1, custom_api)
        
        assert analyzer._parse_cpu('2') == 2.0
        assert analyzer._parse_cpu('500m') == 0.5
        assert analyzer._parse_cpu('1500m') == 1.5
        assert analyzer._parse_cpu('100m') == 0.1
    
    def test_parse_memory(self):
        """Test memory parsing"""
        core_v1 = Mock()
        custom_api = Mock()
        analyzer = NodeEfficiencyAnalyzer(core_v1, custom_api)
        
        # Test different units
        assert analyzer._parse_memory('1Gi') == pytest.approx(1.0, rel=0.01)
        assert analyzer._parse_memory('512Mi') == pytest.approx(0.5, rel=0.01)
        assert analyzer._parse_memory('2048Mi') == pytest.approx(2.0, rel=0.01)
        # 1024 KiB = 1 MiB = 0.0009765625 GiB (binary units)
        assert analyzer._parse_memory('1024Ki') == pytest.approx(0.0009765625, rel=0.01)
    
    def test_determine_node_type(self):
        """Test node type determination"""
        core_v1 = Mock()
        custom_api = Mock()
        analyzer = NodeEfficiencyAnalyzer(core_v1, custom_api)
        
        assert analyzer._determine_node_type({'node.kubernetes.io/instance-type': 'c5.large'}) == 'compute-optimized'
        assert analyzer._determine_node_type({'node.kubernetes.io/instance-type': 'r5.xlarge'}) == 'memory-optimized'
        assert analyzer._determine_node_type({'node.kubernetes.io/instance-type': 'g4dn.xlarge'}) == 'gpu'
        assert analyzer._determine_node_type({'node.kubernetes.io/instance-type': 't3.medium'}) == 'general-purpose'
    
    def test_calculate_bin_packing_efficiency(self):
        """Test bin-packing efficiency calculation"""
        core_v1 = Mock()
        custom_api = Mock()
        analyzer = NodeEfficiencyAnalyzer(core_v1, custom_api)
        
        # Perfect distribution (all nodes at 70%)
        nodes = [
            NodeMetrics(
                name=f'node-{i}',
                cpu_capacity=4.0,
                memory_capacity=16.0,
                cpu_allocatable=4.0,
                memory_allocatable=16.0,
                cpu_requests=2.8,  # 70%
                memory_requests=11.2,  # 70%
                cpu_usage=2.0,
                memory_usage=8.0,
                pod_count=10,
                pod_capacity=110,
                labels={},
                taints=[],
                node_type='general-purpose'
            )
            for i in range(5)
        ]
        
        score = analyzer._calculate_bin_packing_efficiency(nodes)
        assert score > 90  # Should be high score for perfect distribution
        
        # Poor distribution (one node at 90%, others at 20%)
        nodes[0].cpu_requests = 3.6  # 90%
        nodes[0].memory_requests = 14.4  # 90%
        for i in range(1, 5):
            nodes[i].cpu_requests = 0.8  # 20%
            nodes[i].memory_requests = 3.2  # 20%
        
        score = analyzer._calculate_bin_packing_efficiency(nodes)
        assert score < 70  # Should be lower score for poor distribution
    
    def test_generate_recommendations(self):
        """Test recommendation generation"""
        core_v1 = Mock()
        custom_api = Mock()
        analyzer = NodeEfficiencyAnalyzer(core_v1, custom_api)
        
        nodes = [
            NodeMetrics(
                name='node-1',
                cpu_capacity=4.0,
                memory_capacity=16.0,
                cpu_allocatable=4.0,
                memory_allocatable=16.0,
                cpu_requests=3.0,
                memory_requests=12.0,
                cpu_usage=1.0,  # Only 33% of requests used
                memory_usage=4.0,  # Only 33% of requests used
                pod_count=10,
                pod_capacity=110,
                labels={},
                taints=[],
                node_type='general-purpose'
            )
        ]
        
        recommendations = analyzer._generate_recommendations(
            nodes=nodes,
            cpu_request_util=75.0,
            memory_request_util=75.0,
            cpu_actual_util=25.0,
            memory_actual_util=25.0,
            wasted_cpu=2.0,
            wasted_memory=8.0,
            bin_packing_score=50.0,
            underutilized=[],
            overutilized=[]
        )
        
        assert len(recommendations) > 0
        # Should recommend reducing waste
        assert any('wasted' in rec.lower() or 'waste' in rec.lower() for rec in recommendations)
