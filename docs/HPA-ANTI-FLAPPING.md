# HPA Anti-Flapping Guide

## The Problem: Noisy Scaling (Flapping)

Default Kubernetes HPA can cause "flapping" - rapid scale up/down cycles that:
- Waste resources (pod startup/shutdown overhead)
- Cause service instability
- Increase costs
- Generate alert fatigue

## Solution: HPA Behavior Configuration

Kubernetes 1.18+ supports `behavior` field in HPA to control scaling speed.

### Key Settings

#### 1. stabilizationWindowSeconds
How long to wait before acting on metrics.

```yaml
scaleDown:
  stabilizationWindowSeconds: 300  # Wait 5 min before scaling down
scaleUp:
  stabilizationWindowSeconds: 0    # React immediately to load
```

**Recommendation:**
- Scale Down: 300-600 seconds (5-10 minutes)
- Scale Up: 0-60 seconds (react fast)

#### 2. Policies
Control HOW MUCH to scale per time period.

```yaml
policies:
- type: Pods
  value: 1
  periodSeconds: 60    # Max 1 pod per minute
- type: Percent
  value: 10
  periodSeconds: 60    # Max 10% per minute
```

#### 3. selectPolicy
Choose which policy to use when multiple match.

- `Max` - Most aggressive (fastest scaling)
- `Min` - Least aggressive (slowest scaling)
- `Disabled` - Disable scaling in this direction

**Recommendation:**
- Scale Down: `Min` (be conservative)
- Scale Up: `Max` (react fast to load)

## Production HPA Template

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Pods
        value: 1
        periodSeconds: 60
      - type: Percent
        value: 10
        periodSeconds: 60
      selectPolicy: Min
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Pods
        value: 4
        periodSeconds: 15
      - type: Percent
        value: 100
        periodSeconds: 15
      selectPolicy: Max
```

## Workload-Specific Recommendations

### Stable Workloads (APIs, Databases)
```yaml
scaleDown:
  stabilizationWindowSeconds: 600  # 10 minutes
  policies:
  - type: Pods
    value: 1
    periodSeconds: 120  # 1 pod per 2 minutes
  selectPolicy: Min
```

### Bursty Workloads (Event Processing, Batch Jobs)
```yaml
scaleUp:
  stabilizationWindowSeconds: 0
  policies:
  - type: Pods
    value: 10
    periodSeconds: 15
  - type: Percent
    value: 200
    periodSeconds: 15
  selectPolicy: Max
```

### Cost-Sensitive Workloads
```yaml
scaleDown:
  stabilizationWindowSeconds: 180  # 3 minutes
  policies:
  - type: Percent
    value: 25
    periodSeconds: 60  # 25% per minute
  selectPolicy: Max    # Scale down faster
```

## Smart Autoscaler Integration

The Smart Autoscaler adjusts HPA `averageUtilization` target dynamically based on:
- Learned patterns
- Prediction accuracy
- Node capacity

The `behavior` settings work WITH the smart autoscaler to prevent flapping while still allowing dynamic target adjustments.

## Monitoring Flapping

Check for flapping with:
```bash
# Count scale events in last hour
kubectl get events -n <namespace> --field-selector reason=SuccessfulRescale | wc -l

# Watch HPA status
kubectl get hpa -w
```

If you see >10 scale events per hour, increase `stabilizationWindowSeconds`.

## References

- [Kubernetes HPA Behavior](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/#configurable-scaling-behavior)
- [HPA Algorithm](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/#algorithm-details)
