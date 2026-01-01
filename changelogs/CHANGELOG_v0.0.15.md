# Changelog v0.0.15

**Release Date**: 2026-01-01  
**Type**: Hotfix - Dashboard JavaScript Error

## 🐛 Bug Fix: Dashboard Not Displaying Cluster Metrics

### Issue
After v0.0.14 deployment:
- ✅ API returns correct data: `{"summary": {"cpu": {"usage": 7.08}}}`
- ❌ Dashboard shows dashes (`-`) for all values
- ❌ JavaScript error prevents data from displaying

**Root Cause**: JavaScript error in `loadClusterMetrics()` function when trying to calculate total pods. The code tried to access `state.deployments.reduce()` before `state.deployments` was initialized, causing the function to crash and stop executing.

### Error Details
```javascript
// Line 1037-1040 (v0.0.14)
document.getElementById('cluster-pod-count').textContent = state.deployments.reduce((sum, d) => {
    const current = state.current[`${d.namespace}/${d.deployment}`];
    return sum + (current?.pod_count || 0);
}, 0);
```

**Problem**: If user clicks "Cluster Monitoring" tab before deployments are loaded, `state.deployments` is `undefined`, causing:
```
TypeError: Cannot read property 'reduce' of undefined
```

This error stops the entire function, so **no cluster metrics are displayed**.

### Fix
Added null-safety check before accessing `state.deployments`:

```javascript
// v0.0.15 - Safe version
let totalPods = 0;
if (state.deployments && state.deployments.length > 0) {
    totalPods = state.deployments.reduce((sum, d) => {
        const current = state.current[`${d.namespace}/${d.deployment}`];
        return sum + (current?.pod_count || 0);
    }, 0);
}
document.getElementById('cluster-pod-count').textContent = totalPods || '-';
```

### Impact
- ✅ Dashboard now displays cluster metrics even if deployments aren't loaded yet
- ✅ No JavaScript errors
- ✅ All cluster monitoring data shows correctly
- ✅ Total Pods shows `-` if deployments not loaded, or actual count if loaded

---

## 📊 Expected Results

### Before v0.0.15
```
Dashboard Display:
├─ Nodes: 1 active nodes          ✅ Works
├─ Total Pods: -                  ❌ Causes error, stops execution
├─ Cluster Health: -              ❌ Not displayed (error stopped execution)
├─ CPU Usage: - cores             ❌ Not displayed (error stopped execution)
└─ Memory Usage: - GB             ❌ Not displayed (error stopped execution)

Browser Console:
❌ TypeError: Cannot read property 'reduce' of undefined
```

### After v0.0.15
```
Dashboard Display:
├─ Nodes: 1 active nodes          ✅ Works
├─ Total Pods: - (or actual count)✅ Works (safe fallback)
├─ Cluster Health: Warning        ✅ Works
├─ CPU Usage: 7.1 cores (88.5%)   ✅ Works
└─ Memory Usage: 2.2 GB (28.6%)   ✅ Works

Browser Console:
✅ No errors
```

---

## 🚀 Deployment

### Quick Update
```bash
# 1. Commit changes
git add .
git commit -m "fix: dashboard JavaScript error for cluster metrics (v0.0.15)"

# 2. Merge to main and tag
git checkout main
git merge dev
git push origin main
git tag v0.0.15
git push origin v0.0.15

# 3. Restart pod to pick up new HTML
kubectl delete pod -n autoscaler-system -l app=smart-autoscaler

# 4. Wait for pod to restart
kubectl wait --for=condition=ready pod -n autoscaler-system -l app=smart-autoscaler --timeout=60s

# 5. Hard refresh browser (Cmd+Shift+R or Ctrl+Shift+R)
```

### Verify Fix
```bash
# 1. Open dashboard
open http://localhost:5000

# 2. Click "Cluster Monitoring" tab

# 3. Should now see:
# ✅ CPU Usage: 7.1 cores (88.5%)
# ✅ Memory Usage: 2.2 GB (28.6%)
# ✅ Cluster Health: Warning
# ✅ Progress bars showing usage
# ✅ Nodes table with data

# 4. Check browser console (F12) - should have NO errors
```

---

## 🔍 Technical Details

### File Changed
- `templates/dashboard.html` (lines 1037-1045)

### Code Change
**Before**:
```javascript
document.getElementById('cluster-pod-count').textContent = state.deployments.reduce(...);
// ❌ Crashes if state.deployments is undefined
```

**After**:
```javascript
let totalPods = 0;
if (state.deployments && state.deployments.length > 0) {
    totalPods = state.deployments.reduce(...);
}
document.getElementById('cluster-pod-count').textContent = totalPods || '-';
// ✅ Safe - handles undefined state.deployments
```

### Why This Happened
1. User opens dashboard
2. User clicks "Cluster Monitoring" tab immediately
3. `loadClusterMetrics()` is called
4. But `state.deployments` hasn't been loaded yet (async)
5. JavaScript error stops execution
6. No cluster metrics are displayed

### Why It Works Now
1. Check if `state.deployments` exists before using it
2. If not, use fallback value (`-`)
3. Rest of function continues executing
4. Cluster metrics display correctly

---

## 🔗 Related

- v0.0.13: Enhanced node metrics with 5 fallback queries
- v0.0.14: Fixed cluster summary totals calculation
- v0.0.15: Fixed dashboard JavaScript error - THIS RELEASE

---

**Upgrade Path**: v0.0.14 → v0.0.15 (hotfix for dashboard display)

**Breaking Changes**: None

**Recommended**: Yes - fixes dashboard not showing cluster metrics

**Note**: This is a frontend-only fix. No backend changes. Just restart the pod to pick up the new HTML file.
