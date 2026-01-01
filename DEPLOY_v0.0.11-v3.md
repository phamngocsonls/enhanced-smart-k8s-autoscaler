# Deploy v0.0.11-v3 - Cluster Monitoring Debug Enhancement

## Quick Deploy

```bash
# 1. Commit changes
git add .
git commit -m "Hotfix v0.0.11-v3: Enhanced cluster monitoring debug logging"

# 2. Merge to main
git checkout main
git merge dev

# 3. Push to main
git push origin main

# 4. Create and push tag
git tag -a v0.0.11-v3 -m "Hotfix v0.0.11-v3: Enhanced cluster monitoring debug logging

🔍 Debug Enhancements:
- Added comprehensive [CLUSTER] logging to cluster metrics
- Created test_cluster_api.py for quick API testing
- Created debug_cluster_metrics.sh for automated debugging
- Added CLUSTER_METRICS_DEBUG_GUIDE.md with troubleshooting steps

🎯 Purpose:
- Diagnose why cluster monitoring shows 0 nodes
- Identify Prometheus connectivity issues
- Debug query failures

See changelogs/CHANGELOG_v0.0.11-v3.md for details"

git push origin v0.0.11-v3

# 5. Return to dev
git checkout dev
```

## After Deploy

### 1. Update the deployment
```bash
# If using kubectl
kubectl set image deployment/smart-autoscaler \
  smart-autoscaler=your-registry/smart-autoscaler:v0.0.11-v3

# Or rebuild and redeploy
docker build -t your-registry/smart-autoscaler:v0.0.11-v3 .
docker push your-registry/smart-autoscaler:v0.0.11-v3
kubectl rollout restart deployment/smart-autoscaler
```

### 2. Check the logs
```bash
# Get pod name
POD_NAME=$(kubectl get pods -l app=smart-autoscaler -o jsonpath='{.items[0].metadata.name}')

# Watch for cluster logs
kubectl logs $POD_NAME -f | grep CLUSTER
```

### 3. Test the cluster metrics
```bash
# Port forward if not already done
kubectl port-forward $POD_NAME 5000:5000

# In another terminal, check the API
curl http://localhost:5000/api/cluster/metrics | python3 -m json.tool
```

### 4. Look for these log messages

**Success:**
```
[CLUSTER] Querying nodes with: kube_node_info
[CLUSTER] Prometheus URL: http://prometheus-server.monitoring:80
[CLUSTER] Found 1 nodes
[CLUSTER] Processing node: orbstack
Node orbstack: CPU capacity = 8.0 cores
```

**Failure (will help us fix it):**
```
[CLUSTER] Querying nodes with: kube_node_info
[CLUSTER] Prometheus URL: http://prometheus-server.monitoring:80
[CLUSTER] Query result: None
[CLUSTER] Invalid result structure
```

## What This Version Does

This is a **debug enhancement** release. It doesn't fix the cluster monitoring issue yet, but it gives us the tools to:

1. **See what's happening** - Comprehensive logging shows every step
2. **Test quickly** - Scripts to test the API and check connectivity
3. **Diagnose issues** - Detailed error messages when things fail

Once you deploy and check the logs, we'll know exactly what's wrong and can fix it in the next version.

## Files to Check After Deploy

1. **Operator logs** - Look for `[CLUSTER]` messages
2. **Dashboard** - Go to http://localhost:5000 and check Cluster tab
3. **API response** - `curl http://localhost:5000/api/cluster/metrics`

## Common Issues We're Looking For

1. **Prometheus URL wrong** - Logs will show the URL being used
2. **Query returns None** - Connection issue
3. **Query returns empty** - Metric not found
4. **Exception thrown** - Will see full stack trace

## Next Steps After Deploy

Share the output of:
```bash
kubectl logs $POD_NAME --tail=200 | grep CLUSTER
```

This will tell us exactly what's wrong and we can fix it immediately!
