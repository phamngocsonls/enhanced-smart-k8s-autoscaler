# Changelog v0.0.18

**Release Date**: 2026-01-02  
**Type**: Feature Release - Cluster Monitoring Improvements

## ✨ New Features

### Cluster Monitoring Dashboard
- Real-time CPU and memory usage across all nodes
- Total pod count from Prometheus (`kube_pod_status_phase`)
- Health status indicators (Healthy/Warning/Critical)
- 24-hour trend charts with smooth lines
- Per-node resource breakdown table

### Cache-Busting Headers
- Added `no-cache` headers to prevent browser caching HTML
- Dashboard always shows latest data without hard refresh

## 🐛 Bug Fixes

### Fixed Cluster Summary Totals
- Summary CPU/Memory usage now correctly sums node data
- No longer shows 0 when individual nodes have data

### Fixed Progress Bars
- Added CSS classes for `healthy`, `warning`, `critical` states
- Progress bars now show correct colors

### Fixed Total Pods Display
- Now queries Prometheus directly for running pod count
- No longer depends on `state.deployments` being loaded

### Fixed Trend Charts
- Changed from points to smooth lines (`pointRadius: 0`)
- Better visualization of 24-hour trends

## 📊 API Changes

### `/api/cluster/metrics`
Added new field:
```json
{
  "pod_count": 12,  // NEW: Total running pods from Prometheus
  "node_count": 1,
  "nodes": [...],
  "summary": {...}
}
```

## 🔧 Technical Details

### Files Changed
- `src/dashboard.py` - Added pod count query, cache headers
- `templates/dashboard.html` - Fixed JS, CSS, charts
- `src/__init__.py` - Version bump

### Prometheus Queries Added
```promql
# Total running pods
sum(kube_pod_status_phase{phase="Running"})
```

---

## 🚀 Upgrade

```bash
# Update deployment
kubectl set image deployment/smart-autoscaler -n autoscaler-system \
  smart-autoscaler=ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:0.0.18

# Verify
kubectl logs -n autoscaler-system -l app=smart-autoscaler --tail=20
```

---

**Breaking Changes**: None  
**Recommended**: Yes - fixes cluster monitoring display issues
