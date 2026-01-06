# Changelog v0.0.30

**Release Date:** January 6, 2026

## Bug Fix: Real-time Cost Tracking

This release fixes a critical bug where the real-time cost tracking API was returning empty data.

### Issue

The `/api/cost/realtime` and related endpoints were returning empty results:
```json
{
  "nodes": {},
  "workloads": [],
  "summary": {
    "total_workloads": 0,
    "total_monthly_cost": 0
  }
}
```

### Root Cause

The `RealtimeCostTracker` class was calling `self.operator._query_prometheus(query)` but the operator (`EnhancedSmartAutoscaler`) doesn't have this method directly.

The correct path is `self.operator.controller.analyzer._query_prometheus(query)` which accesses the `NodeCapacityAnalyzer`'s Prometheus query method.

### Fix

Updated `src/realtime_cost.py` to use the correct Prometheus query path:

```python
# Before (broken)
def _query_prometheus(self, query: str):
    return self.operator._query_prometheus(query)

# After (fixed)
def _query_prometheus(self, query: str):
    return self.operator.controller.analyzer._query_prometheus(query)
```

### Affected Endpoints

All real-time cost endpoints now work correctly:
- `GET /api/cost/realtime` - All workload costs
- `GET /api/cost/realtime/<namespace>/<deployment>` - Specific deployment cost
- `GET /api/cost/realtime/cluster` - Cluster cost summary
- `GET /api/cost/realtime/waste` - Waste analysis

### Upgrade Instructions

```bash
# Update to v0.0.30
kubectl set image deployment/smart-autoscaler \
  smart-autoscaler=ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:0.0.30

# Verify real-time costs are working
curl http://localhost:5000/api/cost/realtime
```

### Testing

All tests pass:
- `tests/test_realtime_cost.py` - 7 tests passed
