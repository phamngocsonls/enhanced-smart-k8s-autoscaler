#!/bin/bash
# Debug script for cluster metrics issue

echo "=== Cluster Metrics Debug Script ==="
echo ""

# Get pod name
POD_NAME=$(kubectl get pods -l app=smart-autoscaler -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$POD_NAME" ]; then
    echo "❌ Could not find smart-autoscaler pod"
    echo "   Run: kubectl get pods -A | grep autoscaler"
    exit 1
fi

echo "✅ Found pod: $POD_NAME"
echo ""

# Check Prometheus URL
echo "=== 1. Checking Prometheus URL ==="
PROM_URL=$(kubectl exec $POD_NAME -- printenv PROMETHEUS_URL 2>/dev/null)
echo "   PROMETHEUS_URL: $PROM_URL"
echo ""

# Test Prometheus connectivity
echo "=== 2. Testing Prometheus Connectivity ==="
kubectl exec $POD_NAME -- curl -s "$PROM_URL/api/v1/query?query=up" -o /dev/null -w "   HTTP Status: %{http_code}\n" 2>/dev/null
echo ""

# Check if kube_node_info exists
echo "=== 3. Checking kube_node_info metric ==="
NODE_COUNT=$(kubectl exec $POD_NAME -- curl -s "$PROM_URL/api/v1/query?query=kube_node_info" 2>/dev/null | grep -o '"result":\[' | wc -l)
if [ "$NODE_COUNT" -gt 0 ]; then
    echo "   ✅ kube_node_info metric exists"
    kubectl exec $POD_NAME -- curl -s "$PROM_URL/api/v1/query?query=kube_node_info" 2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"   Found {len(data['data']['result'])} nodes\"); [print(f\"   - {r['metric'].get('node', 'unknown')}\") for r in data['data']['result']]" 2>/dev/null
else
    echo "   ❌ kube_node_info metric NOT found"
fi
echo ""

# Check operator logs for cluster metrics
echo "=== 4. Checking Operator Logs (last 100 lines) ==="
echo "   Looking for cluster metrics logs..."
kubectl logs $POD_NAME --tail=100 | grep -i "cluster\|node\|Querying nodes" || echo "   ⚠️  No cluster-related logs found"
echo ""

# Test the API endpoint
echo "=== 5. Testing Dashboard API ==="
echo "   Calling /api/cluster/metrics..."
curl -s http://localhost:5000/api/cluster/metrics 2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"   Node count: {data.get('node_count', 0)}\"); print(f\"   Nodes: {[n['name'] for n in data.get('nodes', [])]}\"); print(f\"   Error: {data.get('error', 'none')}\")" 2>/dev/null || echo "   ❌ API call failed"
echo ""

# Check Python logging level
echo "=== 6. Checking Logging Configuration ==="
kubectl exec $POD_NAME -- python3 -c "import logging; print(f'   Root logger level: {logging.getLogger().level}')" 2>/dev/null
echo ""

echo "=== Recommendations ==="
echo ""
echo "If you see 'Node count: 0':"
echo "  1. Check if operator logs show 'Querying nodes with: kube_node_info'"
echo "  2. If no logs, the function might not be called or logger level is too high"
echo "  3. If logs show errors, check the specific error message"
echo ""
echo "To see full operator logs:"
echo "  kubectl logs $POD_NAME --tail=200"
echo ""
echo "To see real-time logs:"
echo "  kubectl logs $POD_NAME -f"
echo ""
