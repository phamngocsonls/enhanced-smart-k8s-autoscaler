#!/usr/bin/env python3
"""
Test script to verify node metrics queries work
"""

import requests
import json

PROMETHEUS_URL = "http://localhost:9090"

def query_prometheus(query):
    """Query Prometheus"""
    try:
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

print("Testing Node Metrics Queries")
print("=" * 60)

# Test 1: Get nodes
print("\n1. Query: kube_node_info")
result = query_prometheus("kube_node_info")
if result and result['status'] == 'success':
    nodes = result['data']['result']
    print(f"   ✅ Found {len(nodes)} node(s)")
    for node in nodes:
        node_name = node['metric'].get('node', 'unknown')
        print(f"   - Node: {node_name}")
        
        # Test 2: Get CPU capacity for this node
        print(f"\n2. Query: kube_node_status_capacity{{node=\"{node_name}\",resource=\"cpu\"}}")
        cpu_result = query_prometheus(f'kube_node_status_capacity{{node="{node_name}",resource="cpu"}}')
        if cpu_result and cpu_result['status'] == 'success' and cpu_result['data']['result']:
            cpu_capacity = float(cpu_result['data']['result'][0]['value'][1])
            print(f"   ✅ CPU Capacity: {cpu_capacity} cores")
        else:
            print(f"   ❌ No CPU capacity data")
            print(f"   Response: {json.dumps(cpu_result, indent=2)}")
        
        # Test 3: Get CPU allocatable
        print(f"\n3. Query: kube_node_status_allocatable{{node=\"{node_name}\",resource=\"cpu\"}}")
        alloc_result = query_prometheus(f'kube_node_status_allocatable{{node="{node_name}",resource="cpu"}}')
        if alloc_result and alloc_result['status'] == 'success' and alloc_result['data']['result']:
            cpu_alloc = float(alloc_result['data']['result'][0]['value'][1])
            print(f"   ✅ CPU Allocatable: {cpu_alloc} cores")
        else:
            print(f"   ❌ No CPU allocatable data")
        
        # Test 4: Get Memory capacity
        print(f"\n4. Query: kube_node_status_capacity{{node=\"{node_name}\",resource=\"memory\"}}")
        mem_result = query_prometheus(f'kube_node_status_capacity{{node="{node_name}",resource="memory"}}')
        if mem_result and mem_result['status'] == 'success' and mem_result['data']['result']:
            mem_capacity = float(mem_result['data']['result'][0]['value'][1]) / (1024**3)
            print(f"   ✅ Memory Capacity: {mem_capacity:.2f} GB")
        else:
            print(f"   ❌ No memory capacity data")
        
        # Test 5: Get Memory allocatable
        print(f"\n5. Query: kube_node_status_allocatable{{node=\"{node_name}\",resource=\"memory\"}}")
        mem_alloc_result = query_prometheus(f'kube_node_status_allocatable{{node="{node_name}",resource="memory"}}')
        if mem_alloc_result and mem_alloc_result['status'] == 'success' and mem_alloc_result['data']['result']:
            mem_alloc = float(mem_alloc_result['data']['result'][0]['value'][1]) / (1024**3)
            print(f"   ✅ Memory Allocatable: {mem_alloc:.2f} GB")
        else:
            print(f"   ❌ No memory allocatable data")

else:
    print("   ❌ Failed to get nodes")
    print(f"   Response: {json.dumps(result, indent=2)}")

print("\n" + "=" * 60)
print("Test complete!")
