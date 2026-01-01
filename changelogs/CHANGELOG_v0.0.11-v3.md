# Changelog v0.0.11-v3

**Release Date**: 2026-01-01  
**Type**: Hotfix - Cluster Monitoring Debug Enhancement

## 🔍 Debug Enhancements

### Enhanced Cluster Metrics Logging
- Added comprehensive logging to `get_cluster_metrics()` function
- All cluster-related logs now have `[CLUSTER]` prefix for easy filtering
- Logs now show:
  - Prometheus URL being used
  - Query being executed
  - Full query results
  - Detailed error messages when queries fail
  - Node processing steps

### New Debug Tools

**test_cluster_api.py**
- Quick test script to check cluster metrics API
- Shows node count, node details, and cluster summary
- Provides actionable next steps if issues found

**debug_cluster_metrics.sh**
- Automated debug script
- Checks Prometheus connectivity
- Verifies kube_node_info metric availability
- Shows operator logs with cluster-related messages
- Tests dashboard API endpoint

**CLUSTER_METRICS_DEBUG_GUIDE.md**
- Comprehensive troubleshooting guide
- Common issues and solutions
- Expected log patterns for success and failure
- Step-by-step debugging instructions

**NEXT_STEPS.md**
- Quick reference for debugging cluster monitoring
- Three options for testing (test script, logs, automated debug)

## 🐛 Bug Investigation

### Issue
Cluster monitoring dashboard shows 0 nodes even though Prometheus has the data.

### Investigation Approach
Added extensive logging to identify the root cause:
1. Log before and after Prometheus queries
2. Log the full response structure
3. Log detailed errors when queries fail
4. Log each node being processed

### Expected Outcome
The enhanced logging will reveal:
- Whether the function is being called
- What Prometheus URL is being used
- What Prometheus returns
- Why the query might be failing

## 📝 Files Changed

### Modified
- `src/dashboard.py` - Enhanced logging in `get_cluster_metrics()`

### Added
- `test_cluster_api.py` - API test script
- `debug_cluster_metrics.sh` - Automated debug script
- `CLUSTER_METRICS_DEBUG_GUIDE.md` - Troubleshooting guide
- `NEXT_STEPS.md` - Quick reference

## 🔧 Technical Details

### Logging Format
```python
logger.info(f"[CLUSTER] Querying nodes with: {nodes_query}")
logger.info(f"[CLUSTER] Prometheus URL: {self.operator.config.prometheus_url}")
logger.info(f"[CLUSTER] Query result type: {type(result)}")
logger.info(f"[CLUSTER] Query result: {result}")
logger.info(f"[CLUSTER] Found {len(result['data']['result'])} nodes")
logger.error(f"[CLUSTER] Invalid result structure. Result: {result}")
```

### Debug Commands
```bash
# Test API
python3 test_cluster_api.py

# Check logs
kubectl logs <pod-name> --tail=200 | grep CLUSTER

# Automated debug
./debug_cluster_metrics.sh
```

## 🎯 Next Steps

After deploying this version:
1. Check operator logs for `[CLUSTER]` messages
2. Run test scripts to verify cluster metrics
3. Identify and fix the root cause based on log output

## 📊 Compatibility

- ✅ Backward compatible with v0.0.11-v2
- ✅ No breaking changes
- ✅ No configuration changes required
- ✅ Existing deployments will work without modification

## 🔗 Related Issues

- Cluster monitoring showing 0 nodes
- Need better debugging for Prometheus queries
- Namespace filter working (fixed in v0.0.11-v2)

---

**Upgrade Path**: Deploy new version → Check logs → Identify issue → Apply fix

**Rollback**: Safe to rollback to v0.0.11-v2 if needed (no schema changes)
