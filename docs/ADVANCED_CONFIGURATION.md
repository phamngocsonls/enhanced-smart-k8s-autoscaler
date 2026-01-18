# Advanced Configuration Guide

Complete guide to advanced Smart Autoscaler features: startup filters, anti-flapping, and large-scale deployments.

---

## 📋 Table of Contents

1. [Startup Filter](#startup-filter) - Prevent scaling on pod initialization
2. [HPA Anti-Flapping](#hpa-anti-flapping) - Stop rapid scale up/down cycles
3. [Scaling Large Deployments](#scaling-large-deployments) - Configure 100+ deployments

---

## Startup Filter

### Overview

Prevents scaling decisions based on temporary CPU spikes during pod initialization (JVM startup, cache warming, etc.).

### The Problem

New pods often spike CPU during:
- JVM initialization (class loading, JIT compilation)
- Cache warming
- Application startup
- Framework initialization

Without filtering → unnecessary scale-up → wasted resources

### How It Works

Excludes pods younger than configured threshold from CPU metrics:

```
Current Time: 10:00:00, Filter: 2 minutes

Pod A (age: 1.5 min) → EXCLUDED
Pod B (age: 3.0 min) → INCLUDED
Pod C (age: 5.0 min) → INCLUDED
```

### Configuration

**Environment Variables:**
```bash
DEPLOYMENT_0_STARTUP_FILTER=2  # Minutes (default: 2)
```

**Helm Values:**
```yaml
deployments:
  - namespace: production
    name: java-api
    hpaName: java-api-hpa
    startupFilterMinutes: 5  # 5 minutes for Java
```

### Recommended Values

| Application | Filter | Reason |
|------------|--------|--------|
| Java/JVM | 3-5 min | Slow JVM init, JIT compilation |
| Spring Boot | 4-6 min | Framework initialization |
| Node.js | 1-2 min | Module loading |
| Python | 1-2 min | Module imports |
| Go/Rust | 0-1 min | Fast startup |

**Validation**: 0-60 minutes (enforced by config validator)

### Monitoring

**Logs:**
```
INFO - payment-service - Using 3 mature pods (excluded 2 young pods)
```

**Metrics:**
```
autoscaler_mature_pod_count{deployment="payment-service"} 3
autoscaler_excluded_pod_count{deployment="payment-service"} 2
```

### Best Practices

1. **Measure startup time** before configuring
2. **Set to 1.5x observed stabilization time**
3. **Different values per environment** (dev may be slower)
4. **Combine with HPA stabilization windows**

---

## HPA Anti-Flapping

### The Problem

Default HPA can cause "flapping" - rapid scale up/down cycles that:
- Waste resources
- Cause instability
- Increase costs
- Generate alert fatigue

### Solution: HPA Behavior Configuration

Kubernetes 1.18+ supports `behavior` field to control scaling speed.

### Key Settings

#### 1. stabilizationWindowSeconds
Wait time before acting on metrics.

```yaml
scaleDown:
  stabilizationWindowSeconds: 300  # Wait 5 min
scaleUp:
  stabilizationWindowSeconds: 0    # React immediately
```

**Recommendation:**
- Scale Down: 300-600 seconds (5-10 min)
- Scale Up: 0-60 seconds (react fast)

#### 2. Policies
Control HOW MUCH to scale per period.

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
Choose which policy when multiple match.

- `Max` - Most aggressive (fastest)
- `Min` - Least aggressive (slowest)
- `Disabled` - Disable scaling direction

**Recommendation:**
- Scale Down: `Min` (conservative)
- Scale Up: `Max` (react fast)

### Production HPA Template

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

### Workload-Specific Recommendations

**Stable Workloads (APIs, Databases):**
```yaml
scaleDown:
  stabilizationWindowSeconds: 600  # 10 minutes
  policies:
  - type: Pods
    value: 1
    periodSeconds: 120  # 1 pod per 2 minutes
```

**Bursty Workloads (Event Processing):**
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
```

**Cost-Sensitive:**
```yaml
scaleDown:
  stabilizationWindowSeconds: 180  # 3 minutes
  policies:
  - type: Percent
    value: 25
    periodSeconds: 60  # 25% per minute
  selectPolicy: Max    # Scale down faster
```

### Monitoring Flapping

```bash
# Count scale events in last hour
kubectl get events -n <namespace> --field-selector reason=SuccessfulRescale | wc -l

# Watch HPA status
kubectl get hpa -w
```

If >10 events/hour → increase `stabilizationWindowSeconds`

---

## Scaling Large Deployments

### The ConfigMap Limitation

Kubernetes ConfigMaps have **1MB size limit** (~200-300 deployments max).

### Solution 1: Helm Values (10-100 Deployments)

**Recommended for most users**

```yaml
# values.yaml
deployments:
  - namespace: default
    name: app1
    hpaName: app1-hpa
    startupFilterMinutes: 2
    priority: medium
  
  - namespace: default
    name: app2
    hpaName: app2-hpa
    # ... 100+ more
```

**Pros:**
- ✅ No size limit
- ✅ Clean YAML structure
- ✅ Version controlled
- ✅ GitOps friendly

**Install:**
```bash
helm install smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  --values my-deployments.yaml
```

### Solution 2: Auto-Discovery (100+ Deployments)

**Use HPA annotations**

```yaml
# Enable auto-discovery
config:
  enableAutoDiscovery: true
```

Then annotate your HPAs:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-app-hpa
  annotations:
    smart-autoscaler.io/enabled: "true"
    smart-autoscaler.io/priority: "high"
    smart-autoscaler.io/startup-filter: "5"
```

**Pros:**
- ✅ No size limit
- ✅ Auto-discovery
- ✅ Per-deployment overrides
- ✅ Easy to add new deployments

### Solution 3: Multiple ConfigMaps (Workaround)

Split deployments across multiple ConfigMaps:

```yaml
# configmap-1.yaml
data:
  DEPLOYMENT_0_NAMESPACE: "default"
  DEPLOYMENT_0_NAME: "app1"
  # ... up to ~150 deployments

# configmap-2.yaml
data:
  DEPLOYMENT_150_NAMESPACE: "default"
  DEPLOYMENT_150_NAME: "app151"
  # ... next 150
```

Mount both in deployment.

### Programmatic Generation

**Use provided script:**
```bash
# Auto-discover from cluster
python3 scripts/generate-helm-values.py --auto-discover -o values.yaml

# From CSV
python3 scripts/generate-helm-values.py --csv deployments.csv -o values.yaml
```

**CSV format:**
```csv
namespace,deployment,hpa_name,startup_filter,priority
production,api-gateway,api-gateway-hpa,2,critical
production,auth-service,auth-service-hpa,3,critical
```

### Recommendations by Scale

| Deployments | Solution |
|-------------|----------|
| 1-10 | ConfigMap |
| 10-100 | Helm values |
| 100-500 | Auto-discovery or Helm |
| 500+ | Auto-discovery + programmatic generation |

---

## Summary

### Startup Filter
- ✅ Prevents scaling on pod initialization spikes
- ✅ Configurable per deployment (0-60 minutes)
- ✅ Essential for Java/JVM applications

### HPA Anti-Flapping
- ✅ Prevents rapid scale up/down cycles
- ✅ Uses Kubernetes native `behavior` field
- ✅ Workload-specific configurations

### Large Deployments
- ✅ Helm values for 10-100 deployments
- ✅ Auto-discovery for 100+ deployments
- ✅ Programmatic generation for very large scales

---

## Related Documentation

- [Quick Start](../QUICKSTART.md)
- [Configuration Reference](../QUICK_REFERENCE.md)
- [Auto-Discovery](AUTO_DISCOVERY.md)
- [Helm Guide](HELM_GUIDE.md)
