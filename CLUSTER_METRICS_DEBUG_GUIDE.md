# Cluster Metrics Debug Guide

## Current Status

The cluster monitoring dashboard shows 0 nodes even though Prometheus has the data. I've added comprehensive logging to help diagnose the issue.

## What I Changed

### Enhanced Logging in `src/dashboard.py`

Added detailed logging to the `get_cluster_metrics()` function with `[CLUSTER]` prefix:

1. **Before query**: Logs the query and Prometheus URL
2. **After query**: Logs the result type and full result
3. **Success path**: Logs number of nodes found and each node being processed
4. **Failure path**: Logs detailed error information about what's missing in the response

## How to Debug

### Step 1: Run the Test Script

```bash
python3 test_cluster_api.py
```

This will:
- Call the `/api/cluster/metrics` endpoint
- Show you the response
- Tell you if nodes are found or not

### Step 2: Check Operator Logs

```bash
# Get pod name
kubectl get pods -l app=smart-autoscaler

# Check logs (replace with your pod name)
kubectl logs smart-autoscaler-67f97dc8c5-jbthh --tail=200 | grep CLUSTER
```

Look for these log messages:

```
[CLUSTER] Querying nodes with: kube_node_info
[CLUSTER] Prometheus URL: http://prometheus-server.monitoring:80
[CLUSTER] Query result type: <class 'dict'>
[CLUSTER] Query result: {...}
[CLUSTER] Found X nodes
[CLUSTER] Processing node: orbstack
```

### Step 3: Run the Debug Script

```bash
./debug_cluster_metrics.sh
```

This automated script will:
- Find your operator pod
- Check Prometheus URL
- Test Prometheus connectivity
- Check if kube_node_info metric exists
- Show operator logs
- Test the dashboard API

## Common Issues and Solutions

### Issue 1: No Logs Appear

**Symptom**: No `[CLUSTER]` logs when you call the API

**Possible Causes**:
1. The API endpoint isn't being called
2. The function is crashing before logging
3. Logger level is set too high

**Solution**:
```bash
# Check if dashboard is running
curl http://localhost:5000/health

# Check if API is accessible
curl http://localhost:5000/api/cluster/metrics

# Check operator logs for ANY errors
kubectl logs <pod-name> --tail=200
```

### Issue 2: Query Returns None

**Symptom**: Logs show `Query result: None`

**Possible Causes**:
1. Prometheus URL is wrong
2. Prometheus is not accessible from the pod
3. Network policy blocking traffic

**Solution**:
```bash
# Test from inside the pod
kubectl exec <pod-name> -- curl -s "$PROMETHEUS_URL/api/v1/query?query=up"

# Check if Prometheus service exists
kubectl get svc -n monitoring

# Update Prometheus URL if needed
kubectl edit configmap -n autoscaler-system smart-autoscaler-config
```

### Issue 3: Query Returns Empty Result

**Symptom**: Logs show `Query result: {'data': {'result': []}}`

**Possible Causes**:
1. kube-state-metrics is not running
2. Prometheus is not scraping kube-state-metrics
3. The metric name is wrong

**Solution**:
```bash
# Check if kube-state-metrics is running
kubectl get pods -n monitoring | grep kube-state-metrics

# Test the query directly in Prometheus
# Open http://localhost:9090 and run: kube_node_info

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | grep kube-state-metrics
```

### Issue 4: Invalid Result Structure

**Symptom**: Logs show `Invalid result structure`

**Possible Causes**:
1. Prometheus returned an error
2. The response format is unexpected
3. Rate limiting or timeout

**Solution**:
Check the full result in the logs to see what Prometheus actually returned.

## Expected Log Output (Success)

```
[CLUSTER] Querying nodes with: kube_node_info
[CLUSTER] Prometheus URL: http://prometheus-server.monitoring:80
[CLUSTER] Query result type: <class 'dict'>
[CLUSTER] Query result: {'status': 'success', 'data': {'resultType': 'vector', 'result': [{'metric': {'node': 'orbstack', ...}, 'value': [...]}]}}
[CLUSTER] Found 1 nodes
[CLUSTER] Processing node: orbstack
Node orbstack: CPU capacity = 8.0 cores
```

## Expected Log Output (Failure)

```
[CLUSTER] Querying nodes with: kube_node_info
[CLUSTER] Prometheus URL: http://prometheus-server.monitoring:80
[CLUSTER] Query result type: <class 'NoneType'>
[CLUSTER] Query result: None
[CLUSTER] Invalid result structure. Result: None
[CLUSTER] Has 'data' key: False
[CLUSTER] Error querying node metrics: 'NoneType' object is not subscriptable
```

## Next Steps

1. **Run the test script**: `python3 test_cluster_api.py`
2. **Check the logs**: `kubectl logs <pod-name> --tail=200 | grep CLUSTER`
3. **Share the output**: Copy the log output so we can see what's happening
4. **If no logs appear**: The function might not be called - check if the dashboard is running and accessible

## Quick Fixes

### If Prometheus URL is Wrong

```bash
# Update ConfigMap
kubectl edit configmap -n autoscaler-system smart-autoscaler-config

# Change to correct URL (common options):
# - http://prometheus-server.monitoring:80
# - http://prometheus-server.monitoring.svc.cluster.local:80
# - http://prometheus-kube-prometheus-prometheus.monitoring:9090

# Restart operator
kubectl rollout restart deployment -n autoscaler-system smart-autoscaler
```

### If Running Locally

```bash
# Set correct Prometheus URL
export PROMETHEUS_URL="http://localhost:9090"

# Restart the operator
python3 -m src.integrated_operator
```

## Files Changed

- `src/dashboard.py`: Added comprehensive logging to `get_cluster_metrics()`
- `test_cluster_api.py`: New test script to check the API
- `debug_cluster_metrics.sh`: New automated debug script

## What the Logs Will Tell Us

The enhanced logging will show us:

1. **Is the function being called?** - We'll see the initial log messages
2. **What URL is being used?** - We'll see the Prometheus URL
3. **What does Prometheus return?** - We'll see the full response
4. **Why is it failing?** - We'll see specific error messages

Once you run the test and share the logs, we'll know exactly what's wrong and how to fix it!
