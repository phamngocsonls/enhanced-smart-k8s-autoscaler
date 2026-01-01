# Changelog v0.0.11-v4

**Release Date**: 2026-01-01  
**Type**: Hotfix - Fix Cluster Monitoring Method Call

## 🐛 Bug Fix

### Fixed Cluster Monitoring Not Showing Nodes

**Issue**: Cluster monitoring dashboard showed 0 nodes with error:
```
AttributeError: 'NodeCapacityAnalyzer' object has no attribute 'query_prometheus'. 
Did you mean: '_query_prometheus'?
```

**Root Cause**: The `get_cluster_metrics()` function was calling `analyzer.query_prometheus()` but the correct method name is `analyzer._query_prometheus()` (private method with underscore prefix).

**Fix**: Updated all 11 calls from `query_prometheus()` to `_query_prometheus()` in `src/dashboard.py`:
- Node info query
- CPU capacity queries (per node)
- CPU allocatable queries (per node)
- Memory capacity queries (per node)
- Memory allocatable queries (per node)
- CPU usage queries (per node)
- Memory usage queries (per node)
- Total CPU requests query
- Total memory requests query
- Total CPU usage query
- Total memory usage query

## 📝 Files Changed

### Modified
- `src/dashboard.py` - Fixed method calls in `get_cluster_metrics()`
- `src/__init__.py` - Version bump to 0.0.11-v4
- `src/integrated_operator.py` - Version in logging config

## ✅ Testing

### Before Fix
```bash
curl http://localhost:5000/api/cluster/metrics
# Returns: {"node_count": 0, "nodes": []}

kubectl logs <pod> | grep CLUSTER
# Shows: AttributeError: 'NodeCapacityAnalyzer' object has no attribute 'query_prometheus'
```

### After Fix
```bash
curl http://localhost:5000/api/cluster/metrics
# Should return: {"node_count": 1, "nodes": [{"name": "orbstack", "cpu_capacity": 8.0, ...}]}

kubectl logs <pod> | grep CLUSTER
# Should show: [CLUSTER] Found 1 nodes, [CLUSTER] Processing node: orbstack
```

## 🔧 Technical Details

The `NodeCapacityAnalyzer` class in `src/operator.py` has a private method `_query_prometheus()` that includes:
- Retry logic with exponential backoff
- Circuit breaker pattern
- Rate limiting
- Error handling

The dashboard was incorrectly trying to call the public version which doesn't exist.

## 📊 Impact

- ✅ Cluster monitoring now works correctly
- ✅ Shows node metrics (CPU, memory capacity/usage)
- ✅ Shows cluster summary (total resources)
- ✅ Historical trends work
- ✅ No breaking changes

## 🎯 Verification Steps

After deploying:

1. **Check API response**:
   ```bash
   curl http://localhost:5000/api/cluster/metrics | python3 -m json.tool
   ```
   Should show `"node_count": 1` and node details

2. **Check logs**:
   ```bash
   kubectl logs <pod> --tail=100 | grep CLUSTER
   ```
   Should show successful queries and node processing

3. **Check dashboard**:
   - Open http://localhost:5000
   - Go to "🖥️ Cluster" tab
   - Should see node metrics and charts

## 🔗 Related

- Fixes issue from v0.0.11-v3 where debug logging was added
- Completes the cluster monitoring feature from v0.0.11
- Namespace filter working (fixed in v0.0.11-v2)

---

**Upgrade Path**: Deploy v0.0.11-v4 → Cluster monitoring works immediately

**Rollback**: Can rollback to v0.0.11-v2 (v3 had the same bug)
