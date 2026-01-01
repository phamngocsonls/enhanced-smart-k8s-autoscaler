# Fix Node Metrics Not Showing

## Problem
The cluster monitoring dashboard shows 0 nodes even though Prometheus has the data.

## Root Cause
The operator is likely using the wrong Prometheus URL or there's a connection issue.

## Verification

### 1. Check Prometheus has the data ✅
```bash
curl -s 'http://localhost:9090/api/v1/query?query=kube_node_info' | python3 -m json.tool
# Should show node "orbstack" with 8 CPU cores
```

**Result**: ✅ Prometheus HAS the data!

### 2. Check what URL the operator is using
```bash
# Check environment variable
echo $PROMETHEUS_URL

# Or check config
kubectl get configmap -n autoscaler-system smart-autoscaler-config -o yaml | grep PROMETHEUS_URL
```

## Solutions

### Solution 1: Update Prometheus URL (Most Likely Fix)

If your operator is running in Kubernetes but Prometheus is port-forwarded:

```bash
# Update the ConfigMap
kubectl edit configmap -n autoscaler-system smart-autoscaler-config

# Change PROMETHEUS_URL to:
PROMETHEUS_URL: "http://prometheus-server.monitoring:80"
# or
PROMETHEUS_URL: "http://prometheus-server.monitoring.svc.cluster.local:80"
```

### Solution 2: Port Forward Prometheus to the Operator

If operator is running locally:

```bash
# Port forward Prometheus
kubectl port-forward -n monitoring svc/prometheus-server 9090:80

# Update .env or environment
export PROMETHEUS_URL="http://localhost:9090"
```

### Solution 3: Check Prometheus Service Name

```bash
# Find the correct Prometheus service
kubectl get svc -n monitoring

# Common names:
# - prometheus-server
# - prometheus-kube-prometheus-prometheus
# - prometheus-operated
# - prometheus

# Update URL accordingly
```

### Solution 4: Restart the Operator

After updating the URL:

```bash
# If running in Kubernetes
kubectl rollout restart deployment -n autoscaler-system smart-autoscaler

# If running locally
# Stop and restart the Python process
```

## Quick Test

After fixing, test the API:

```bash
# Should now show nodes
curl -s http://localhost:5000/api/cluster/metrics | python3 -m json.tool

# Should show:
# "node_count": 1,
# "nodes": [{"name": "orbstack", "cpu_capacity": 8.0, ...}]
```

## Expected Result

Once fixed, you'll see:

### Cluster Tab
- **Nodes**: 1
- **CPU Capacity**: 8.0 cores
- **CPU Allocatable**: ~7.8 cores
- **Memory Capacity**: ~16 GB
- **Memory Allocatable**: ~14 GB

### Nodes Table
| Node | CPU Capacity | CPU Usage | Memory Capacity | Memory Usage | Status |
|------|--------------|-----------|-----------------|--------------|--------|
| orbstack | 8.0 cores | X.X cores | 16.0 GB | X.X GB | Healthy |

## Debug Steps

### 1. Check operator logs
```bash
kubectl logs -n autoscaler-system -l app=smart-autoscaler --tail=50
```

Look for:
- "Querying nodes with: kube_node_info"
- "Found X nodes"
- "Processing node: orbstack"
- Any error messages

### 2. Test Prometheus connectivity from operator pod
```bash
kubectl exec -n autoscaler-system <pod-name> -- curl -s http://prometheus-server.monitoring:80/api/v1/query?query=up
```

### 3. Check if rate limiting is blocking
```bash
# Check if too many requests
kubectl logs -n autoscaler-system -l app=smart-autoscaler | grep "rate limit"
```

## Common Issues

### Issue 1: Wrong Prometheus Port
- ❌ `http://prometheus-server.monitoring:9090` (wrong port)
- ✅ `http://prometheus-server.monitoring:80` (correct for most setups)

### Issue 2: Wrong Service Name
- Check actual service name with `kubectl get svc -n monitoring`

### Issue 3: Network Policy Blocking
- Check if network policies allow traffic from autoscaler namespace to monitoring namespace

### Issue 4: Prometheus Not Scraping kube-state-metrics
```bash
# Check if Prometheus is scraping kube-state-metrics
curl -s 'http://localhost:9090/api/v1/targets' | grep kube-state-metrics
```

## Immediate Fix (If Running Locally)

If you're running the dashboard locally for testing:

```bash
# 1. Stop the current process
# 2. Set correct Prometheus URL
export PROMETHEUS_URL="http://localhost:9090"

# 3. Restart
python3 -m src.integrated_operator
```

## Verification Commands

```bash
# 1. Check Prometheus has node data
curl -s 'http://localhost:9090/api/v1/query?query=kube_node_info' | jq '.data.result | length'
# Should return: 1

# 2. Check CPU capacity
curl -s 'http://localhost:9090/api/v1/query?query=kube_node_status_capacity{resource="cpu"}' | jq '.data.result[0].value[1]'
# Should return: "8"

# 3. Check dashboard API
curl -s http://localhost:5000/api/cluster/metrics | jq '.node_count'
# Should return: 1 (after fix)
```

## Next Steps

1. Identify your Prometheus URL
2. Update the operator configuration
3. Restart the operator
4. Refresh the dashboard
5. Check the Cluster tab - should now show node metrics!

---

**TL;DR**: The operator is probably using the wrong Prometheus URL. Update `PROMETHEUS_URL` in your config to point to the correct Prometheus service, then restart the operator.
