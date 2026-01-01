# Debug Dashboard Not Showing Data

## Current Status

✅ **API is working**: Returns correct data
```bash
curl http://localhost:5000/api/cluster/metrics | jq '.summary.cpu.usage'
# Returns: 7.08
```

❌ **Dashboard shows dashes**: JavaScript not displaying the data

## Debug Steps

### Step 1: Hard Refresh Browser (CRITICAL!)

**You MUST do a hard refresh to get the new HTML:**

- **Mac**: `Cmd + Shift + R`
- **Windows/Linux**: `Ctrl + Shift + R`

Or open in **Incognito/Private window**: `http://localhost:5000`

### Step 2: Check Browser Console

1. Open dashboard: `http://localhost:5000`
2. Press `F12` to open DevTools
3. Click "Console" tab
4. Click "Cluster Monitoring" tab in dashboard
5. Look for debug messages:

**Expected console output:**
```
[DEBUG] loadClusterMetrics called
[DEBUG] Cluster metrics data: {nodes: [...], summary: {...}}
[DEBUG] Updated pod count: 0
[DEBUG] Updated CPU usage: 7.08
```

**If you see errors:**
- Share the error message
- It will tell us exactly what's wrong

### Step 3: Check Network Tab

1. Open DevTools (`F12`)
2. Click "Network" tab
3. Click "Cluster Monitoring" tab in dashboard
4. Look for `/api/cluster/metrics` request
5. Click on it and check:
   - **Status**: Should be `200 OK`
   - **Response**: Should show JSON with data

### Step 4: Verify Pod Has New Code

```bash
# Check if pod has debug logging
POD=$(kubectl get pod -n autoscaler-system -l app=smart-autoscaler -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n autoscaler-system $POD -- grep "DEBUG" /app/templates/dashboard.html | head -3

# Should show:
# console.log('[DEBUG] loadClusterMetrics called');
# console.log('[DEBUG] Cluster metrics data:', data);
# console.log('[DEBUG] Updated pod count:', totalPods);
```

## Common Issues

### Issue 1: Browser Cache
**Symptom**: Dashboard shows dashes, no console logs
**Solution**: Hard refresh (`Cmd+Shift+R` or `Ctrl+Shift+R`)

### Issue 2: Old HTML Cached
**Symptom**: Console shows old code, no debug logs
**Solution**: 
1. Clear browser cache completely
2. Or use Incognito/Private window
3. Or try different browser

### Issue 3: JavaScript Error
**Symptom**: Console shows red error message
**Solution**: Share the error message - it will tell us what's wrong

### Issue 4: API Not Called
**Symptom**: No network request to `/api/cluster/metrics`
**Solution**: Click the "Cluster Monitoring" tab to trigger the load

## Quick Test

Open browser console and run this:
```javascript
fetch('/api/cluster/metrics')
  .then(r => r.json())
  .then(d => console.log('CPU:', d.summary.cpu.usage))
  .catch(e => console.error('Error:', e));
```

**Expected output**: `CPU: 7.08`

If this works but dashboard doesn't, it's a browser cache issue.

## Force Clear Cache

### Chrome/Edge
1. Open DevTools (`F12`)
2. Right-click the refresh button
3. Select "Empty Cache and Hard Reload"

### Firefox
1. Open DevTools (`F12`)
2. Click Network tab
3. Check "Disable cache"
4. Refresh page

### Safari
1. Develop menu → Empty Caches
2. Then refresh page

## Still Not Working?

Share these details:
1. Browser console output (any errors?)
2. Network tab - is `/api/cluster/metrics` called?
3. What does this return:
   ```bash
   curl http://localhost:5000/api/cluster/metrics | jq '.summary.cpu.usage'
   ```

---

**Most likely**: You just need to hard refresh the browser! The pod has the new code, the API works, but your browser is showing cached HTML.
