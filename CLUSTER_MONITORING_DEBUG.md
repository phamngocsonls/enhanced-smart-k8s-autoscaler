# Cluster Monitoring Debug Guide

## Issue: Dashboard Shows "No Data"

```
Cluster Monitoring:
- Total Pods → None
- Cluster Health → None
- CPU Resources → None, no metrics
- Memory Resources → None, no metrics
- CPU Trend (24h) → No data
- Memory Trend (24h) → No data
- 📦 Nodes Detail → No data
```

---

## Step 1: Check Version

First, verify you're running v0.0.12 (which has the cluster monitoring fix):

```bash
# Check pod version
kubectl logs -n autoscaler-system -l app=smart-autoscaler --tail=5 | grep "version\|v0.0"

# Should show: Smart Autoscaler v0.0.12
```

**If NOT v0.0.12**: Deploy the latest version first!

---

## Step 2: Test Prometheus Connectivity

```bash
# Get into the autoscaler pod
kubectl exec -it -n autoscaler-system deployment/smart-autoscaler -- sh

# Test Prometheus connection (replace with your Prometheus URL)
curl -s "http://prometheus-server.monitoring:80/api/v1/query?query=up" | head -20

# Should return JSON with "status":"success"
```

**If connection fails**: Check Prometheus URL in config

---

## Step 3: Check Prometheus URL in Config

```bash
# Check current config
kubectl get cm autoscaler-config -n autoscaler-system -o yaml | grep PROMETHEUS

# Should show something like:
# PROMETHEUS_URL: "http://prometheus-server.monitoring:80"
```

**Common Prometheus URLs**:
- In-cluster: `http://prometheus-server.monitoring:80`
- Port-forwarded: `http://localhost:9090`
- External: `http://prometheus.example.com`

---

## Step 4: Verify Prometheus Has Metrics

Test if Prometheus has the required metrics:

```bash
# Test node metrics (node_exporter)
curl -s "http://prometheus-server.monitoring:80/api/v1/query?query=kube_node_info" | jq

# Test container metrics (cAdvisor)
curl -s "http://prometheus-server.monitoring:80/api/v1/query?query=container_cpu_usage_seconds_total" | jq

# Test kube-state-metrics
curl -s "http://prometheus-server.monitoring:80/api/v1/query?query=kube_pod_info" | jq
```

**If no results**: Prometheus exporters are not running!

---

## Step 5: Check Operator Logs

```bash
# Check for errors
kubectl logs -n autoscaler-system -l app=smart-autoscaler --tail=100 | grep -i "error\|cluster\|prometheus"

# Look for:
# - "Error querying Prometheus"
# - "Connection refused"
# - "No nodes found"
# - "Query result empty"
```

---

## Step 6: Test API Directly

```bash
# Port forward dashboard
kubectl port-forward svc/smart-autoscaler -n autoscaler-system 5000:5000

# Test cluster metrics API
curl http://localhost:5000/api/cluster/metrics | jq

# Should return:
# {
#   "nodes": [...],
#   "node_count": 1,
#   "summary": {...}
# }
```

**If returns error**: Check the error message

---

## Common Issues & Fixes

### Issue 1: Wrong Prometheus URL

**Symptom**: Connection refused, timeout

**Fix**:
```bash
# Update ConfigMap
kubectl edit cm autoscaler-config -n autoscaler-system

# Change PROMETHEUS_URL to correct value
# For in-cluster Prometheus:
PROMETHEUS_URL: "http://prometheus-server.monitoring:80"

# Restart operator
kubectl rollout restart deployment/smart-autoscaler -n autoscaler-system
```

### Issue 2: Prometheus Not Installed

**Symptom**: No Prometheus service found

**Fix**: Install Prometheus
```bash
# Using Helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install prometheus prometheus-community/prometheus -n monitoring --create-namespace

# Wait for pods
kubectl wait --for=condition=ready pod -l app=prometheus -n monitoring --timeout=300s
```

### Issue 3: Missing Exporters

**Symptom**: Prometheus running but no metrics

**Fix**: Ensure these are running:
```bash
# Check exporters
kubectl get pods -n monitoring

# Should have:
# - prometheus-server
# - prometheus-node-exporter (DaemonSet)
# - prometheus-kube-state-metrics
```

### Issue 4: RBAC Permissions

**Symptom**: "Forbidden" errors in logs

**Fix**: Apply RBAC
```bash
kubectl apply -f k8s/rbac.yaml
```

### Issue 5: Old Version (Not v0.0.12)

**Symptom**: Node CPU showing 0

**Fix**: Deploy v0.0.12
```bash
# Build and push
docker build -t your-registry/smart-autoscaler:v0.0.12 .
docker push your-registry/smart-autoscaler:v0.0.12

# Update deployment
kubectl set image deployment/smart-autoscaler -n autoscaler-system \
  smart-autoscaler=your-registry/smart-autoscaler:v0.0.12

# Verify
kubectl logs -n autoscaler-system -l app=smart-autoscaler --tail=5
```

---

## Quick Fix Script

Run this to diagnose all issues:

```bash
#!/bin/bash
echo "=== Smart Autoscaler Cluster Monitoring Debug ==="

echo -e "\n1. Checking version..."
kubectl logs -n autoscaler-system -l app=smart-autoscaler --tail=5 2>/dev/null | grep -i "version\|v0.0"

echo -e "\n2. Checking Prometheus URL..."
kubectl get cm autoscaler-config -n autoscaler-system -o yaml 2>/dev/null | grep PROMETHEUS_URL

echo -e "\n3. Testing Prometheus connectivity..."
PROM_URL=$(kubectl get cm autoscaler-config -n autoscaler-system -o jsonpath='{.data.PROMETHEUS_URL}' 2>/dev/null)
echo "Prometheus URL: $PROM_URL"

echo -e "\n4. Checking Prometheus pods..."
kubectl get pods -n monitoring 2>/dev/null | grep prometheus

echo -e "\n5. Testing cluster metrics API..."
kubectl port-forward svc/smart-autoscaler -n autoscaler-system 5000:5000 >/dev/null 2>&1 &
PF_PID=$!
sleep 2
curl -s http://localhost:5000/api/cluster/metrics | jq -r '.node_count // "ERROR"'
kill $PF_PID 2>/dev/null

echo -e "\n6. Checking operator logs for errors..."
kubectl logs -n autoscaler-system -l app=smart-autoscaler --tail=50 2>/dev/null | grep -i "error" | tail -5

echo -e "\n=== Debug Complete ==="
```

Save as `debug-cluster-monitoring.sh` and run:
```bash
chmod +x debug-cluster-monitoring.sh
./debug-cluster-monitoring.sh
```

---

## Expected Working Output

When working correctly, you should see:

### API Response
```json
{
  "nodes": [
    {
      "name": "orbstack",
      "cpu_capacity": 8.0,
      "cpu_allocatable": 8.0,
      "cpu_usage": 2.5,
      "memory_capacity_gb": 16.0,
      "memory_allocatable_gb": 15.5,
      "memory_usage_gb": 8.2
    }
  ],
  "node_count": 1,
  "summary": {
    "cpu": {
      "capacity": 8.0,
      "usage": 2.5,
      "usage_percent": 31.3
    },
    "memory": {
      "capacity_gb": 16.0,
      "usage_gb": 8.2,
      "usage_percent": 52.9
    }
  }
}
```

### Dashboard Display
```
Cluster Monitoring:
- Total Pods → 15
- Cluster Health → Healthy
- CPU Resources → 2.5 / 8.0 cores (31%)
- Memory Resources → 8.2 / 16.0 GB (53%)
- CPU Trend (24h) → [chart showing usage]
- Memory Trend (24h) → [chart showing usage]
- 📦 Nodes Detail → orbstack: 2.5 cores, 8.2 GB
```

---

## Still Not Working?

Share the output of:
```bash
# 1. Version
kubectl logs -n autoscaler-system -l app=smart-autoscaler --tail=5

# 2. Config
kubectl get cm autoscaler-config -n autoscaler-system -o yaml

# 3. API test
curl http://localhost:5000/api/cluster/metrics

# 4. Logs
kubectl logs -n autoscaler-system -l app=smart-autoscaler --tail=100
```

I'll help you fix it!
