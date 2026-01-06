# Changelog v0.0.30

**Release Date:** January 6, 2026

## v0.0.30-v1 - Auto-Discovery & Smart Cost Tracking

### New Features

#### 1. Auto-Discovery via Annotations
Automatically discover and manage HPAs using Kubernetes annotations - no ConfigMap changes needed!

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-app-hpa
  annotations:
    smart-autoscaler.io/enabled: "true"
    smart-autoscaler.io/priority: "high"
    smart-autoscaler.io/startup-filter: "3"
```

Supported annotations:
- `smart-autoscaler.io/enabled: "true"` - Enable auto-discovery
- `smart-autoscaler.io/priority: "high"` - Set priority (critical/high/medium/low/best_effort)
- `smart-autoscaler.io/startup-filter: "2"` - Startup filter in minutes

See [docs/AUTO_DISCOVERY.md](docs/AUTO_DISCOVERY.md) for full documentation.

#### 2. Workload Grouping
Cost tracking now groups pods by their owner workload (Deployment, StatefulSet, DaemonSet) instead of individual pod IDs. This provides:
- Stable cost tracking across pod restarts
- Aggregated metrics per workload
- Better visibility into actual workload costs

#### 3. Smart Waste Calculation
New waste calculation model based on optimal utilization targets:
- **CPU ≥25%** = Optimal (no waste)
- **Memory ≥65%** = Optimal (no waste)

If utilization is at or above these targets, the workload is considered "optimal" with no waste reported. This reflects real-world Kubernetes best practices where some headroom is necessary.

#### 4. Sortable Cost Report Table
The Cost & Reports dashboard now features:
- Click any column header to sort
- All metrics visible: CPU Req/Use/%, Memory Req/Use/%, Cost, Waste
- Status badges: OK (optimal) or LOW (underutilized)
- Workload type icons: 🚀 Deployment, 📦 StatefulSet, 🔄 DaemonSet

### Configuration Changes

#### Target Node Utilization: 40% → 30%
Default target node CPU utilization reduced from 40% to 30% for more headroom.

Updated in:
- `.env.example`
- `helm/smart-autoscaler/values.yaml`
- `k8s/configmap.yaml`
- All deployment scripts

#### New Environment Variable
```bash
ENABLE_AUTO_DISCOVERY=true  # Enable/disable auto-discovery (default: true)
```

### API Changes

#### Updated `/api/cost/realtime` Response
Now returns workload-grouped data:
```json
{
  "workloads": [
    {
      "namespace": "production",
      "workload_kind": "Deployment",
      "workload_name": "api-server",
      "pod_count": 3,
      "cpu_utilization_percent": 45.2,
      "memory_utilization_percent": 68.5,
      "cpu_status": "optimal",
      "memory_status": "optimal",
      "is_optimal": true,
      "cost_monthly": 125.50,
      "waste_monthly": 0.00
    }
  ],
  "summary": {
    "optimal_workloads": 5,
    "total_workloads": 8,
    "optimal_targets": {
      "cpu_percent": 25,
      "memory_percent": 65
    }
  }
}
```

### Files Added
- `src/auto_discovery.py` - Auto-discovery module
- `docs/AUTO_DISCOVERY.md` - Auto-discovery documentation
- `examples/hpa-auto-discovery.yaml` - Example HPAs with annotations
- `tests/test_auto_discovery.py` - 10 new tests

### Upgrade Instructions

```bash
# Update to v0.0.30-v1
kubectl set image deployment/smart-autoscaler \
  smart-autoscaler=ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:0.0.30-v1

# Add annotations to your HPAs for auto-discovery
kubectl annotate hpa my-app-hpa smart-autoscaler.io/enabled=true
```

### Testing

All 198 tests pass:
- `tests/test_auto_discovery.py` - 10 tests
- `tests/test_realtime_cost.py` - 7 tests
- `tests/test_dashboard.py` - 8 tests

---

## v0.0.30 - Real-time Cost Tracking Fix

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
