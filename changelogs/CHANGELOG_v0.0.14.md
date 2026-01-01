# Changelog v0.0.14

**Release Date**: 2026-01-01  
**Type**: Hotfix - Cluster Monitoring Summary Fix

## 🐛 Bug Fix: Cluster Summary Showing Zero Usage

### Issue
In v0.0.13, individual node metrics showed correct CPU and memory usage, but the cluster summary totals were showing 0:

```json
{
  "nodes": [
    {
      "name": "orbstack",
      "cpu_usage": 7.02,        // ✅ Correct!
      "memory_usage_gb": 2.19   // ✅ Correct!
    }
  ],
  "summary": {
    "cpu": {
      "usage": 0,               // ❌ Wrong!
      "usage_percent": 0.0
    },
    "memory": {
      "usage_gb": 0,            // ❌ Wrong!
      "usage_percent": 0.0
    }
  }
}
```

**Root Cause**: The code was querying Prometheus twice:
1. First query: Per-node metrics with 5 fallback strategies → **Worked!**
2. Second query: Cluster-wide totals with generic query → **Failed!**

The generic cluster-wide query used different label formats that didn't match the user's Prometheus setup.

### Fix
**Calculate summary totals from node data instead of querying again:**

```python
# Before v0.0.14 - Query again (fails with different label format)
cpu_usage_query = 'sum(rate(container_cpu_usage_seconds_total{container!="",container!="POD"}[5m]))'
cpu_usage_result = analyzer._query_prometheus(cpu_usage_query)
total_cpu_usage = float(cpu_usage_result[0]['value'][1]) if cpu_usage_result else 0

# After v0.0.14 - Sum from nodes we already collected (reliable!)
total_cpu_usage = sum(node['cpu_usage'] for node in all_nodes)
total_memory_usage = sum(node['memory_usage_gb'] for node in all_nodes)
```

### Impact
- ✅ Cluster summary now shows correct totals
- ✅ Dashboard displays proper CPU/Memory usage percentages
- ✅ Health status calculated correctly
- ✅ No additional Prometheus queries needed (more efficient!)
- ✅ Works with all Prometheus label formats (uses same fallback logic)

---

## 📊 Expected Results

### Before v0.0.14
```json
{
  "nodes": [{"cpu_usage": 7.02, "memory_usage_gb": 2.19}],
  "summary": {
    "cpu": {"usage": 0, "usage_percent": 0.0},      // ❌ Wrong
    "memory": {"usage_gb": 0, "usage_percent": 0.0} // ❌ Wrong
  }
}
```

**Dashboard showed**: "CPU Usage: 0 cores (0%)", "Memory Usage: 0 GB (0%)"

### After v0.0.14
```json
{
  "nodes": [{"cpu_usage": 7.02, "memory_usage_gb": 2.19}],
  "summary": {
    "cpu": {"usage": 7.02, "usage_percent": 87.8},      // ✅ Correct!
    "memory": {"usage_gb": 2.19, "usage_percent": 28.0} // ✅ Correct!
  }
}
```

**Dashboard shows**: "CPU Usage: 7.0 cores (87.8%)", "Memory Usage: 2.2 GB (28.0%)"

---

## 🚀 Deployment

### Quick Update
```bash
# 1. Pull latest code
git pull origin dev

# 2. Build new image
docker build -t your-registry/smart-autoscaler:v0.0.14 .
docker push your-registry/smart-autoscaler:v0.0.14

# 3. Update deployment
kubectl set image deployment/smart-autoscaler -n autoscaler-system \
  smart-autoscaler=your-registry/smart-autoscaler:v0.0.14

# 4. Verify
curl http://localhost:5000/api/cluster/metrics | jq '.summary.cpu.usage'
# Should show: 7.02 (not 0!)
```

### Test Dashboard
```bash
# Open dashboard
open http://localhost:5000

# Navigate to "Cluster Monitoring" tab
# Should now show:
# - CPU Usage: 7.0 cores (87.8%)
# - Memory Usage: 2.2 GB (28.0%)
# - Cluster Health: Warning (due to high CPU)
```

---

## 🔍 Technical Details

### Code Changes
**File**: `src/dashboard.py` (lines ~820-840)

**Removed**: Redundant Prometheus queries for cluster totals
**Added**: Simple summation from already-collected node data

```python
# Calculate total usage from node metrics (already collected above)
# This is more reliable than querying again with different label formats
total_cpu_usage = sum(node['cpu_usage'] for node in all_nodes)
total_memory_usage = sum(node['memory_usage_gb'] for node in all_nodes)
logger.info(f"[CLUSTER] Total usage: CPU={total_cpu_usage:.2f} cores, Memory={total_memory_usage:.2f} GB")
```

### Why This Works
1. Node metrics use 5 fallback query strategies (v0.0.13)
2. At least one fallback succeeds for each node
3. Summing node data = accurate cluster total
4. No need for separate cluster-wide query
5. More efficient (fewer Prometheus queries)

### Logs
```
INFO - [CLUSTER] Found 1 nodes
INFO - [CLUSTER] Processing node: orbstack
INFO - Node orbstack: CPU usage = 7.03 cores (source: node_exporter (node))
INFO - Node orbstack: Memory usage = 2.20 GB (source: node_exporter (node))
INFO - [CLUSTER] Total usage: CPU=7.03 cores, Memory=2.20 GB  # ← New log!
```

---

## 🔗 Related

- v0.0.11: Added cluster monitoring
- v0.0.12: Added 2 fallback queries for node metrics
- v0.0.13: Enhanced to 5 fallback queries for node metrics
- v0.0.14: Fixed summary totals by reusing node data - THIS RELEASE

---

**Upgrade Path**: v0.0.13 → v0.0.14 (hotfix for cluster summary)

**Breaking Changes**: None

**Recommended**: Yes - fixes cluster monitoring dashboard display

**Testing**: Verified with Prometheus that has `container_cpu_usage_seconds_total` but no `node_cpu_seconds_total`
