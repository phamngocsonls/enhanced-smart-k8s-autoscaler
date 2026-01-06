# ArgoCD Integration Guide

## Overview

The Smart Autoscaler modifies HPA `targetCPUUtilizationPercentage` dynamically based on workload patterns and predictions. This can conflict with ArgoCD's auto-sync feature, which may revert these changes back to Git values.

## The Conflict

### What Happens
1. **Smart Autoscaler** adjusts HPA target from 80% → 70% based on learning
2. **ArgoCD auto-sync** detects drift and reverts HPA back to 80% (Git value)
3. **Smart Autoscaler** adjusts again to 70%
4. **Cycle repeats** → Constant sync loop

### Impact
- ArgoCD shows constant "OutOfSync" status
- Unnecessary reconciliation loops
- Operator's learning is overridden

## Solution: Ignore HPA Target in ArgoCD

### Option 1: Ignore Specific Field (Recommended)

Add this annotation to your HPA manifest in Git:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: demo-app-hpa
  namespace: demo
  annotations:
    # Tell ArgoCD to ignore the target field that Smart Autoscaler manages
    argocd.argoproj.io/compare-options: IgnoreExtraneous
    argocd.argoproj.io/sync-options: Prune=false
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: demo-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 80  # Initial value, will be adjusted by operator
```

### Option 2: Ignore Entire HPA Resource

If you want ArgoCD to completely ignore the HPA:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: demo-app-hpa
  namespace: demo
  annotations:
    # ArgoCD will not manage this resource at all
    argocd.argoproj.io/sync-options: Prune=false
    argocd.argoproj.io/compare-options: IgnoreExtraneous
```

### Option 3: Use ArgoCD Application-Level Ignore

In your ArgoCD Application manifest:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
spec:
  # ... other config ...
  ignoreDifferences:
  - group: autoscaling
    kind: HorizontalPodAutoscaler
    jsonPointers:
    - /spec/metrics/0/resource/target/averageUtilization
```

This tells ArgoCD to ignore changes to the HPA target field.

## Recommended Setup

### 1. HPA Manifest in Git

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: demo-app-hpa
  namespace: demo
  annotations:
    # Let Smart Autoscaler manage the target
    argocd.argoproj.io/compare-options: IgnoreExtraneous
  labels:
    app: demo-app
    managed-by: smart-autoscaler
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: demo-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 80  # Starting point
```

### 2. Smart Autoscaler ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: smart-autoscaler-config
  namespace: autoscaler-system
data:
  config.yaml: |
    check_interval: 30
    target_node_utilization: 30
    enable_predictive: true
    enable_autotuning: true
    deployments:
      - namespace: demo
        deployment: demo-app
        hpa_name: demo-app-hpa
        priority: medium  # or high, low, critical, best_effort
```

### 3. ArgoCD Application

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: demo-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/your-org/your-repo
    targetRevision: main
    path: k8s/demo-app
  destination:
    server: https://kubernetes.default.svc
    namespace: demo
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
  # Ignore HPA target changes made by Smart Autoscaler
  ignoreDifferences:
  - group: autoscaling
    kind: HorizontalPodAutoscaler
    jsonPointers:
    - /spec/metrics/0/resource/target/averageUtilization
```

## Verification

### 1. Check ArgoCD Status

```bash
# Should show "Synced" even when operator adjusts HPA
argocd app get demo-app
```

### 2. Check HPA Target

```bash
# Watch HPA target change over time
kubectl get hpa demo-app-hpa -n demo -w
```

### 3. Check Operator Logs

```bash
# Should see target adjustments without ArgoCD conflicts
kubectl logs -n autoscaler-system -l app=smart-autoscaler --tail=50 | grep "Optimal target"
```

## Best Practices

### 1. Initial HPA Values in Git

Set conservative initial values in Git:
- **minReplicas**: Minimum safe replica count
- **maxReplicas**: Maximum allowed replicas
- **averageUtilization**: 80% (operator will optimize this)

### 2. Let Operator Learn

- Don't manually adjust HPA targets
- Let the operator learn for 24-48 hours
- Monitor dashboard for optimal target convergence

### 3. Priority-Based Scaling

Use priority levels to control scaling behavior:

```yaml
deployments:
  - namespace: prod
    deployment: critical-api
    hpa_name: critical-api-hpa
    priority: critical  # Aggressive scaling, preemptive

  - namespace: prod
    deployment: web-app
    hpa_name: web-app-hpa
    priority: high  # Fast scaling

  - namespace: prod
    deployment: background-worker
    hpa_name: worker-hpa
    priority: low  # Conservative scaling
```

### 4. Monitor Learning Progress

Check the dashboard at `http://localhost:5000`:
- **AI Insights**: Shows learning progress and confidence
- **Predictions**: Shows accuracy rate
- **Scaling Events**: Shows target adjustments

## Troubleshooting

### Issue: ArgoCD Shows Constant OutOfSync

**Cause**: ArgoCD is not ignoring HPA target changes

**Solution**:
```bash
# Add ignore annotation to HPA
kubectl annotate hpa demo-app-hpa -n demo \
  argocd.argoproj.io/compare-options=IgnoreExtraneous

# Or update ArgoCD Application with ignoreDifferences
```

### Issue: Operator Changes Are Reverted

**Cause**: ArgoCD auto-sync is reverting operator changes

**Solution**:
```bash
# Check ArgoCD Application
argocd app get demo-app

# Add ignoreDifferences to Application manifest
# See "Option 3" above
```

### Issue: HPA Target Not Changing

**Cause**: Operator might not have enough data or confidence

**Solution**:
```bash
# Check operator logs
kubectl logs -n autoscaler-system -l app=smart-autoscaler --tail=100

# Check learning progress
curl http://localhost:5000/api/ai/insights/demo-app | jq '.auto_tuning'

# Wait for more data (typically 2-4 hours)
```

## GitOps Workflow

### 1. Initial Deployment

```bash
# 1. Commit HPA with ignore annotations
git add k8s/demo-app/hpa.yaml
git commit -m "Add HPA with ArgoCD ignore annotations"
git push

# 2. ArgoCD syncs
argocd app sync demo-app

# 3. Operator starts learning
# Check dashboard for progress
```

### 2. Updating Min/Max Replicas

```bash
# Update in Git (operator won't override these)
# Edit k8s/demo-app/hpa.yaml
# Change minReplicas or maxReplicas

git add k8s/demo-app/hpa.yaml
git commit -m "Update HPA replica limits"
git push

# ArgoCD will sync these changes
# Operator respects min/max limits
```

### 3. Changing Priority

```bash
# Update Smart Autoscaler ConfigMap
kubectl edit configmap smart-autoscaler-config -n autoscaler-system

# Change priority level
# Operator will hot-reload and apply new priority
```

## Architecture

```
┌─────────────┐
│   Git Repo  │
│  (HPA with  │
│   ignore    │
│ annotations)│
└──────┬──────┘
       │
       ▼
┌─────────────┐      ┌──────────────────┐
│   ArgoCD    │─────▶│   Kubernetes     │
│  (ignores   │      │   (HPA exists)   │
│ HPA target) │      └────────┬─────────┘
└─────────────┘               │
                              │
                              ▼
                    ┌──────────────────┐
                    │ Smart Autoscaler │
                    │  (adjusts HPA    │
                    │   target based   │
                    │   on learning)   │
                    └──────────────────┘
```

## Summary

✅ **Do**:
- Add ArgoCD ignore annotations to HPA
- Let operator manage HPA target
- Use priority levels for different workloads
- Monitor learning progress in dashboard

❌ **Don't**:
- Manually adjust HPA targets (let operator learn)
- Remove ignore annotations
- Disable auto-tuning without reason
- Expect immediate optimization (needs 24-48h)

## References

- [ArgoCD Sync Options](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/)
- [ArgoCD Ignore Differences](https://argo-cd.readthedocs.io/en/stable/user-guide/diffing/)
- [Smart Autoscaler Priority Feature](../PRIORITY_FEATURE.md)
- [HPA Anti-Flapping](./HPA-ANTI-FLAPPING.md)
