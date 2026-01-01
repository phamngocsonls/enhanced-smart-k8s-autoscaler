#!/usr/bin/env python3
"""
Quick test script to check cluster metrics API
"""

import json
import sys

try:
    import requests
except ImportError:
    print("❌ requests library not found")
    print("Install it with: pip3 install requests")
    sys.exit(1)

def test_cluster_metrics():
    """Test the cluster metrics API endpoint"""
    
    print("=== Testing Cluster Metrics API ===\n")
    
    # Test API endpoint
    url = "http://localhost:5000/api/cluster/metrics"
    
    try:
        print(f"Calling: {url}")
        response = requests.get(url, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print()
        
        if response.status_code == 200:
            data = response.json()
            
            print("=== Response Data ===")
            print(f"Node Count: {data.get('node_count', 0)}")
            print(f"Nodes: {len(data.get('nodes', []))}")
            
            if data.get('nodes'):
                print("\nNode Details:")
                for node in data['nodes']:
                    print(f"  - {node['name']}")
                    print(f"    CPU: {node['cpu_capacity']} cores (allocatable: {node['cpu_allocatable']})")
                    print(f"    Memory: {node['memory_capacity_gb']} GB (allocatable: {node['memory_allocatable_gb']})")
            else:
                print("\n❌ No nodes found!")
                print("\nFull response:")
                print(json.dumps(data, indent=2))
            
            # Check summary
            if 'summary' in data:
                print("\n=== Cluster Summary ===")
                cpu = data['summary']['cpu']
                mem = data['summary']['memory']
                print(f"CPU: {cpu['capacity']} cores capacity, {cpu['allocatable']} allocatable")
                print(f"     {cpu['requests']} cores requested ({cpu['requests_percent']}%)")
                print(f"     {cpu['usage']} cores used ({cpu['usage_percent']}%)")
                print(f"Memory: {mem['capacity_gb']} GB capacity, {mem['allocatable_gb']} GB allocatable")
                print(f"        {mem['requests_gb']} GB requested ({mem['requests_percent']}%)")
                print(f"        {mem['usage_gb']} GB used ({mem['usage_percent']}%)")
            
            if data.get('error'):
                print(f"\n⚠️  Error in response: {data['error']}")
                return False
            
            if data.get('node_count', 0) == 0:
                print("\n❌ ISSUE: Node count is 0")
                print("\nNext steps:")
                print("1. Check operator logs: kubectl logs <pod-name> --tail=200")
                print("2. Look for 'Querying nodes with: kube_node_info'")
                print("3. Look for any error messages")
                print("4. Run: ./debug_cluster_metrics.sh")
                return False
            
            print("\n✅ Cluster metrics working correctly!")
            return True
            
        else:
            print(f"❌ API returned error status: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to dashboard at localhost:5000")
        print("\nMake sure:")
        print("1. Dashboard is running")
        print("2. Port forward is active: kubectl port-forward <pod-name> 5000:5000")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_cluster_metrics()
    sys.exit(0 if success else 1)
