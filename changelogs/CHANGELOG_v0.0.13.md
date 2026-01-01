# Changelog v0.0.13

**Release Date**: 2026-01-01  
**Type**: Hotfix - Enhanced Cluster Monitoring Fallbacks

## 🔧 Cluster Monitoring Enhancement

### Issue
Cluster monitoring showing `cpu_usage: 0` and `memory_usage_gb: 0` even though Prometheus is accessible.

**Root Cause**: Limited fallback queries - only tried 2 metric sources, but different Prometheus setups use different metric names and label formats.

### Fix
Added **extensive fallback queries** with 5 different approaches for both CPU and memory:

#### CPU Usage Queries (tries in order):
1. `node_cpu_seconds_total` with `instance` label (node_exporter standard)
2. `node_cpu_seconds_total` with `node` label (alternative format)
3. `container_cpu_usage_seconds_total` with `node` label (cAdvisor by node)
4. `container_cpu_usage_seconds_total` with `instance` label (cAdvisor by instance)
5. `node_cpu_seconds_total` without rate() (fallback for missing rate data)

#### Memory Usage Queries (tries in order):
1. `node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes` with `instance` label
2. `node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes` with `node` label
3. `container_memory_working_set_bytes` with `node` label
4. `container_memory_working_set_bytes` with `instance` label
5. `node_memory_Active_bytes` with `instance` label

### Impact
- ✅ Works with more Prometheus configurations
- ✅ Tries 5 different query formats instead of 2
- ✅ Better logging to show which source worked
- ✅ Only accepts non-zero values (skips empty results)
- ✅ More resilient to different metric naming conventions

---

## 📝 Technical Details

### Before (v0.0.12)
```python
# Only 2 attempts
cpu_usage_query = f'sum(rate(node_cpu_seconds_total{{mode!="idle",instance=~".*{node_name}.*"}}[5m]))'
# If fails, try:
cpu_usage_query_fallback = f'sum(rate(container_cpu_usage_seconds_total{{node="{node_name}",container!="",container!="POD"}}[5m]))'
# If both fail: cpu_usage = 0
```

### After (v0.0.13)
```python
# 5 attempts with different label formats
cpu_queries = [
    (f'sum(rate(node_cpu_seconds_total{{mode!="idle",instance=~".*{node_name}.*"}}[5m]))', "node_exporter (instance)"),
    (f'sum(rate(node_cpu_seconds_total{{mode!="idle",node="{node_name}"}}[5m]))', "node_exporter (node)"),
    (f'sum(rate(container_cpu_usage_seconds_total{{node="{node_name}",container!="",container!="POD"}}[5m]))', "container (node)"),
    (f'sum(rate(container_cpu_usage_seconds_total{{instance=~".*{node_name}.*",container!="",container!="POD"}}[5m]))', "container (instance)"),
    (f'sum(node_cpu_seconds_total{{mode!="idle",instance=~".*{node_name}.*"}}) / 100', "node_exporter (no rate)"),
]

# Try each until one returns non-zero value
for query, source in cpu_queries:
    result = analyzer._query_prometheus(query)
    if result and result[0]['value'][1] > 0:
        cpu_usage = float(result[0]['value'][1])
        logger.info(f"CPU usage = {cpu_usage} cores (source: {source})")
        break
```

---

## 🚀 Deployment

### Quick Update
```bash
# 1. Pull latest code
git pull origin dev

# 2. Build new image
docker build -t your-registry/smart-autoscaler:v0.0.13 .
docker push your-registry/smart-autoscaler:v0.0.13

# 3. Update deployment
kubectl set image deployment/smart-autoscaler -n autoscaler-system \
  smart-autoscaler=your-registry/smart-autoscaler:v0.0.13

# 4. Verify
kubectl logs -n autoscaler-system -l app=smart-autoscaler --tail=20
```

### Test Cluster Monitoring
```bash
# Port forward dashboard
kubectl port-forward svc/smart-autoscaler -n autoscaler-system 5000:5000

# Test API
curl http://localhost:5000/api/cluster/metrics | jq '.nodes[0]'

# Should now show:
# {
#   "name": "orbstack",
#   "cpu_usage": 2.5,        # ✅ Non-zero!
#   "memory_usage_gb": 8.2   # ✅ Non-zero!
# }
```

---

## 📊 Expected Results

### Before v0.0.13
```json
{
  "name": "orbstack",
  "cpu_usage": 0,           // ❌ Always zero
  "memory_usage_gb": 0      // ❌ Always zero
}
```

### After v0.0.13
```json
{
  "name": "orbstack",
  "cpu_usage": 2.5,         // ✅ Actual usage!
  "memory_usage_gb": 8.2    // ✅ Actual usage!
}
```

### Logs
```
INFO - Node orbstack: CPU usage = 2.5 cores (source: container (node))
INFO - Node orbstack: Memory usage = 8.2 GB (source: container (node))
```

---

## 🔗 Related

- v0.0.11: Added cluster monitoring
- v0.0.11-v5: Fixed response format
- v0.0.12: Added fallback queries (2 attempts)
- v0.0.13: Enhanced fallbacks (5 attempts) - THIS RELEASE

---

**Upgrade Path**: v0.0.12 → v0.0.13 (hotfix for cluster monitoring)

**Breaking Changes**: None

**Recommended**: Yes - fixes cluster monitoring for more Prometheus setups
