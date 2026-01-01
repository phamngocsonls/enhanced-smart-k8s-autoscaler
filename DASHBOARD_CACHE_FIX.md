# Dashboard Not Showing Data - Cache Issue

## 🎯 Problem

The API is returning correct data:
```json
{
  "summary": {
    "cpu": {"usage": 7.08, "usage_percent": 88.5},  ✅
    "memory": {"usage_gb": 2.23, "usage_percent": 28.6}  ✅
  }
}
```

But the dashboard shows dashes (`-`) instead of values.

## 🔍 Root Cause

**Browser cache** - Your browser is serving the old HTML/JavaScript files that don't have the updated code.

## ✅ Solutions

### Solution 1: Hard Refresh Browser (Quickest)

**Chrome/Edge (Windows/Linux)**:
- Press `Ctrl + Shift + R`
- Or `Ctrl + F5`

**Chrome/Edge (Mac)**:
- Press `Cmd + Shift + R`

**Firefox (Windows/Linux)**:
- Press `Ctrl + Shift + R`
- Or `Ctrl + F5`

**Firefox (Mac)**:
- Press `Cmd + Shift + R`

**Safari (Mac)**:
- Press `Cmd + Option + R`
- Or hold `Shift` and click the refresh button

### Solution 2: Clear Browser Cache

1. Open browser DevTools (F12)
2. Right-click the refresh button
3. Select "Empty Cache and Hard Reload"

### Solution 3: Restart the Pod (Forces new connection)

```bash
# Delete the pod (it will restart automatically)
kubectl delete pod -n autoscaler-system -l app=smart-autoscaler

# Wait for it to come back
kubectl wait --for=condition=ready pod -n autoscaler-system -l app=smart-autoscaler --timeout=60s

# Verify it's running
kubectl get pods -n autoscaler-system
```

Then refresh your browser (hard refresh).

### Solution 4: Use Incognito/Private Window

Open the dashboard in an incognito/private window:
```
http://localhost:5000
```

This bypasses all cache.

## 🧪 Verify It's Working

After hard refresh, you should see:

### Cluster Monitoring Tab
```
🖥️ Cluster Monitoring

Nodes: 1 active nodes
Total Pods: [number]
Cluster Health: Warning (or Critical/Healthy)

💻 CPU Resources
Capacity: 8.0 cores
Allocatable: 8.0 cores
Requested: 0.8 cores (9.4% of allocatable)
Usage: 7.1 cores (88.5% of allocatable)  ← Should show actual value!
[████████████████████████████████████░░░░] 88.5%

🧠 Memory Resources
Capacity: 7.8 GB
Allocatable: 7.8 GB
Requested: 9.2 GB (117.2% of allocatable)
Usage: 2.2 GB (28.6% of allocatable)  ← Should show actual value!
[████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 28.6%

📦 Nodes Detail
┌──────────┬──────────┬───────┬──────┬──────────┬────────┬──────┬────────┐
│ Node     │ CPU Cap  │ Usage │ %    │ Mem Cap  │ Usage  │ %    │ Status │
├──────────┼──────────┼───────┼──────┼──────────┼────────┼──────┼────────┤
│ orbstack │ 8.0 cores│ 7.08  │ 88.5%│ 7.8 GB   │ 2.2 GB │ 28.6%│Warning │
└──────────┴──────────┴───────┴──────┴──────────┴────────┴──────┴────────┘
```

## 🔍 Debug Steps

If hard refresh doesn't work:

### 1. Check Browser Console
1. Open DevTools (F12)
2. Go to Console tab
3. Look for JavaScript errors (red text)
4. Share any errors you see

### 2. Check Network Tab
1. Open DevTools (F12)
2. Go to Network tab
3. Click "Cluster Monitoring" tab in dashboard
4. Look for `/api/cluster/metrics` request
5. Click on it and check:
   - Status: Should be `200 OK`
   - Response: Should show JSON with data

### 3. Test API Directly
```bash
# Should return data with non-zero values
curl http://localhost:5000/api/cluster/metrics | jq '.summary'
```

Expected:
```json
{
  "cpu": {
    "usage": 7.08,           ← Non-zero!
    "usage_percent": 88.5    ← Non-zero!
  },
  "memory": {
    "usage_gb": 2.23,        ← Non-zero!
    "usage_percent": 28.6    ← Non-zero!
  }
}
```

### 4. Check Pod Version
```bash
# Check logs for version
kubectl logs -n autoscaler-system -l app=smart-autoscaler --tail=100 | grep "Smart Autoscaler"

# Should show v0.0.14 or see the new log message:
kubectl logs -n autoscaler-system -l app=smart-autoscaler --tail=100 | grep "Total usage"
# Should show: [CLUSTER] Total usage: CPU=7.08 cores, Memory=2.23 GB
```

## 🎯 Most Likely Solution

**Just do a hard refresh**: `Cmd + Shift + R` (Mac) or `Ctrl + Shift + R` (Windows/Linux)

This will force your browser to reload all files from the server instead of using cached versions.

---

**Note**: Browser caching is normal and helps performance, but when you update the application, you need to clear the cache to see the changes.
