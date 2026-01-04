# RBAC Configuration for Metrics Server Access

## Overview

The Node Efficiency Dashboard requires access to the Kubernetes metrics-server API to retrieve actual CPU and memory usage data. This document explains how to configure RBAC permissions.

## Required Permissions

The smart-autoscaler service account needs the following permissions:

```yaml
- apiGroups: ["metrics.k8s.io"]
  resources: ["nodes", "pods"]
  verbs: ["get", "list"]
```

## Quick Fix

### Option 1: Update Existing RBAC (kubectl)

```bash
# Apply updated RBAC configuration
kubectl apply -f k8s/rbac.yaml

# Restart the autoscaler to pick up new permissions
kubectl rollout restart deployment/smart-autoscaler -n autoscaler-system
```

### Option 2: Update Helm Deployment

```bash
# Upgrade with updated Helm chart
helm upgrade smart-autoscaler ./helm/smart-autoscaler \
  --reuse-values

# Permissions are automatically updated
```

## Verify Permissions

Check if the service account has the required permissions:

```bash
# Check if metrics-server API is available
kubectl get apiservices | grep metrics

# Expected output:
# v1beta1.metrics.k8s.io    kube-system/metrics-server   True

# Test permissions (replace namespace if different)
kubectl auth can-i get nodes.metrics.k8s.io \
  --as=system:serviceaccount:autoscaler-system:smart-autoscaler

# Expected output: yes
```

## Troubleshooting

### Error: 403 Forbidden

**Symptom:** Dashboard shows "Unable to load node efficiency data"

**Cause:** Service account lacks permissions to access metrics.k8s.io API

**Fix:**
```bash
# 1. Check current permissions
kubectl describe clusterrole smart-autoscaler-role

# 2. Verify metrics.k8s.io is listed
# If not, apply updated RBAC:
kubectl apply -f k8s/rbac.yaml

# 3. Restart autoscaler
kubectl rollout restart deployment/smart-autoscaler -n autoscaler-system
```

### Error: 404 Not Found

**Symptom:** Logs show "metrics-server not found (404)"

**Cause:** metrics-server not installed in cluster

**Fix:**
```bash
# Install metrics-server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Wait for metrics-server to be ready
kubectl wait --for=condition=ready pod -l k8s-app=metrics-server -n kube-system --timeout=60s

# Verify it's working
kubectl top nodes
```

### Error: 401 Unauthorized

**Symptom:** Authentication errors in logs

**Cause:** Service account token issue or kubeconfig problem

**Fix:**
```bash
# Check service account exists
kubectl get serviceaccount smart-autoscaler -n autoscaler-system

# Check service account token
kubectl get secret -n autoscaler-system | grep smart-autoscaler

# If missing, recreate service account
kubectl delete serviceaccount smart-autoscaler -n autoscaler-system
kubectl apply -f k8s/rbac.yaml
```

## Metrics Server Installation

If metrics-server is not installed in your cluster:

### Standard Installation

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

### For Development/Testing (with TLS disabled)

```bash
# Download the manifest
curl -LO https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Edit to add --kubelet-insecure-tls flag
# Find the args section and add:
#   - --kubelet-insecure-tls

# Apply
kubectl apply -f components.yaml
```

### Verify Installation

```bash
# Check metrics-server is running
kubectl get pods -n kube-system | grep metrics-server

# Test metrics API
kubectl top nodes
kubectl top pods -A
```

## What Happens Without Metrics Server?

The Node Efficiency Dashboard will still work but with limited data:

**Available:**
- ✅ Node count and capacity
- ✅ Resource requests (CPU/memory)
- ✅ Pod counts
- ✅ Request-based utilization
- ✅ Bin-packing efficiency (based on requests)
- ✅ Recommendations

**Not Available:**
- ❌ Actual CPU/memory usage
- ❌ Usage-based utilization percentages
- ❌ Waste detection (requested vs used)

The dashboard will show a warning message explaining that actual usage data is unavailable.

## Security Considerations

### Principle of Least Privilege

The smart-autoscaler only requests `get` and `list` permissions on metrics, not `watch`, `create`, `update`, or `delete`.

### Namespace Isolation

While the ClusterRole grants cluster-wide access to metrics, the autoscaler only reads data and never modifies it.

### Audit Logging

Enable audit logging to track metrics API access:

```yaml
# In kube-apiserver configuration
--audit-log-path=/var/log/kubernetes/audit.log
--audit-policy-file=/etc/kubernetes/audit-policy.yaml
```

## Complete RBAC Example

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: smart-autoscaler
  namespace: autoscaler-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: smart-autoscaler-role
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "watch", "patch"]
- apiGroups: ["autoscaling"]
  resources: ["horizontalpodautoscalers"]
  verbs: ["get", "list", "watch", "patch"]
- apiGroups: [""]
  resources: ["pods", "nodes", "configmaps", "namespaces"]
  verbs: ["get", "list", "watch"]
# Metrics Server API access
- apiGroups: ["metrics.k8s.io"]
  resources: ["nodes", "pods"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: smart-autoscaler-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: smart-autoscaler-role
subjects:
- kind: ServiceAccount
  name: smart-autoscaler
  namespace: autoscaler-system
```

## Testing

After updating RBAC, test the Node Efficiency API:

```bash
# Port forward to dashboard
kubectl port-forward svc/smart-autoscaler -n autoscaler-system 5000:5000

# Test the API
curl http://localhost:5000/api/cluster/node-efficiency | jq .

# Should return node efficiency data or helpful error message
```

## Support

If you continue to have issues:

1. Check application logs:
   ```bash
   kubectl logs -f deployment/smart-autoscaler -n autoscaler-system
   ```

2. Look for detailed error messages with troubleshooting steps

3. Verify all prerequisites:
   - metrics-server installed and running
   - RBAC permissions updated
   - Service account exists
   - Network connectivity to Kubernetes API

## References

- [Kubernetes Metrics Server](https://github.com/kubernetes-sigs/metrics-server)
- [Kubernetes RBAC Documentation](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [metrics.k8s.io API](https://kubernetes.io/docs/tasks/debug-application-cluster/resource-metrics-pipeline/)
