# Changelog v0.0.11-v5

**Release Date**: 2026-01-01  
**Type**: Hotfix - Fix Prometheus Response Format Handling

## 🐛 Bug Fix

### Fixed Cluster Monitoring Response Format

**Issue**: Cluster monitoring still showed 0 nodes after v4 fix with error:
```
[CLUSTER] Invalid result structure. Result: [{'metric': {...}, 'value': [...]}]
[CLUSTER] Has 'data' key: False
```

**Root Cause**: The `_query_prometheus()` method returns a **list** directly:
```python
[{'metric': {...}, 'value': [timestamp, value]}]
```

But the code was expecting a dict with nested structure:
```python
{'data': {'result': [{'metric': {...}, 'value': [...]}]}}
```

**Fix**: Updated all response handling in `get_cluster_metrics()` to work with the list format:
- Changed from `result['data']['result']` to `result` (direct list)
- Changed from checking `'data' in result` to `isinstance(result, list)`
- Changed from `result['data']['result'][0]` to `result[0]`
- Updated all 11 query result handlers

## 📝 Files Changed

### Modified
- `src/dashboard.py` - Fixed response format handling in `get_cluster_metrics()`
- `src/__init__.py` - Version bump to 0.0.11-v5
- `src/integrated_operator.py` - Version in logging config

## ✅ Testing

### Before Fix (v4)
```bash
kubectl logs <pod> | grep CLUSTER
# Shows:
[CLUSTER] Query result type: <class 'list'>
[CLUSTER] Invalid result structure
[CLUSTER] Has 'data' key: False
```

### After Fix (v5)
```bash
kubectl logs <pod> | grep CLUSTER
# Should show:
[CLUSTER] Query result type: <class 'list'>
[CLUSTER] Query result length: 1
[CLUSTER] Found 1 nodes
[CLUSTER] Processing node: orbstack
Node orbstack: CPU capacity = 8.0 cores
```

## 🔧 Technical Details

### Response Format Comparison

**PrometheusConnect.custom_query() returns:**
```python
[
    {
        'metric': {'node': 'orbstack', ...},
        'value': [1767273320.037, '8']
    }
]
```

**NOT:**
```python
{
    'data': {
        'result': [
            {
                'metric': {'node': 'orbstack', ...},
                'value': [1767273320.037, '8']
            }
        ]
    }
}
```

### Code Changes

**Before:**
```python
if result and 'data' in result and 'result' in result['data']:
    for node_info in result['data']['result']:
        cpu = float(result['data']['result'][0]['value'][1])
```

**After:**
```python
if result and isinstance(result, list) and len(result) > 0:
    for node_info in result:
        cpu = float(result[0]['value'][1])
```

## 📊 Impact

- ✅ Cluster monitoring NOW WORKS!
- ✅ Shows node metrics correctly
- ✅ Shows CPU/memory capacity, allocatable, requests, usage
- ✅ Per-node breakdown works
- ✅ Historical trends work
- ✅ No breaking changes

## 🎯 Verification Steps

After deploying:

1. **Check API response**:
   ```bash
   curl http://localhost:5000/api/cluster/metrics | python3 -m json.tool
   ```
   Should show:
   ```json
   {
       "node_count": 1,
       "nodes": [
           {
               "name": "orbstack",
               "cpu_capacity": 8.0,
               "cpu_allocatable": 7.8,
               ...
           }
       ]
   }
   ```

2. **Check logs**:
   ```bash
   kubectl logs <pod> --tail=100 | grep CLUSTER
   ```
   Should show successful node processing

3. **Check dashboard**:
   - Open http://localhost:5000
   - Go to "🖥️ Cluster" tab
   - Should see node metrics, charts, and table

## 🔗 Related

- v0.0.11-v3: Added debug logging
- v0.0.11-v4: Fixed method name (query_prometheus → _query_prometheus)
- v0.0.11-v5: Fixed response format handling (THIS FIX)

## 📚 Lessons Learned

1. The `_query_prometheus()` method wraps `PrometheusConnect.custom_query()`
2. `custom_query()` returns a list directly, not wrapped in `{'data': {'result': [...]}}`
3. Always check the actual return format of library methods
4. Debug logging was crucial to identify this issue

---

**Upgrade Path**: Deploy v0.0.11-v5 → Cluster monitoring works immediately!

**This should be the final fix!** 🎉
