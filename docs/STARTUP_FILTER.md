# Startup Filter - Preventing Scaling on Initialization Spikes

## Overview

The **Startup Filter** feature prevents the Smart Autoscaler from making scaling decisions based on temporary CPU spikes that occur during pod initialization. This is especially important for applications with slow startup times like Java/JVM applications.

## The Problem

When a new pod starts, it often experiences high CPU usage due to:
- **JVM initialization** (class loading, JIT compilation)
- **Cache warming** (loading data into memory)
- **Application startup** (dependency injection, connection pooling)
- **Framework initialization** (Spring Boot, Hibernate, etc.)

Without filtering, the autoscaler might:
1. See high CPU usage from new pods
2. Think the deployment needs more capacity
3. Scale up unnecessarily
4. Create more pods that also spike CPU
5. Result in **scaling thrashing** and wasted resources

## How It Works

The startup filter excludes pods younger than a configured threshold from CPU metrics calculations:

```
Current Time: 10:00:00
Startup Filter: 2 minutes

Pod A started at 09:58:30 (age: 1.5 min) → EXCLUDED from metrics
Pod B started at 09:57:00 (age: 3.0 min) → INCLUDED in metrics
Pod C started at 09:55:00 (age: 5.0 min) → INCLUDED in metrics
```

Only "mature" pods (older than the filter threshold) are used for scaling decisions.

## Configuration

### Environment Variables

```bash
# Per-deployment configuration
DEPLOYMENT_0_STARTUP_FILTER=2  # Minutes (default: 2)
DEPLOYMENT_1_STARTUP_FILTER=5  # Higher for Java apps
```

### Helm Values

```yaml
deployments:
  - namespace: production
    name: java-api
    hpaName: java-api-hpa
    startupFilterMinutes: 5  # 5 minutes for Java
    priority: high
  
  - namespace: production
    name: go-service
    hpaName: go-service-hpa
    startupFilterMinutes: 1  # 1 minute for Go
    priority: medium
```

### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: smart-autoscaler-config
  namespace: autoscaler-system
data:
  DEPLOYMENT_0_NAMESPACE: "production"
  DEPLOYMENT_0_NAME: "payment-service"
  DEPLOYMENT_0_HPA_NAME: "payment-service-hpa"
  DEPLOYMENT_0_STARTUP_FILTER: "5"  # 5 minutes
  DEPLOYMENT_0_PRIORITY: "critical"
```

## Recommended Values

| Application Type | Startup Filter | Reason |
|-----------------|----------------|--------|
| **Java/JVM** | 3-5 minutes | Slow JVM initialization, JIT compilation |
| **Spring Boot** | 4-6 minutes | Framework initialization, dependency injection |
| **Node.js** | 1-2 minutes | Moderate startup, module loading |
| **Python** | 1-2 minutes | Module imports, framework setup |
| **Go** | 0-1 minutes | Fast compilation, quick startup |
| **Rust** | 0-1 minutes | Native binary, instant startup |
| **Static sites** | 0 minutes | No initialization needed |

### Validation

- **Minimum**: 0 minutes (no filtering)
- **Maximum**: 60 minutes
- **Default**: 2 minutes

Values outside this range will be rejected by the config validator.

## Implementation Details

### Code Location

The startup filter is implemented in:
- **Configuration**: `src/config_loader.py` - Loads and validates the setting
- **Usage**: `src/operator.py` - `get_pod_cpu_usage()` method
- **Validation**: `src/config_validator.py` - Ensures 0-60 minute range

### Algorithm

```python
def get_pod_cpu_usage(namespace, deployment, startup_window_minutes=2):
    # 1. Query pod start times from Prometheus
    pod_start_query = f'kube_pod_start_time{{namespace="{namespace}",pod=~"{deployment}-.*"}}'
    
    # 2. Filter out young pods
    now = datetime.now().timestamp()
    mature_pods = []
    
    for pod in pods:
        age_minutes = (now - pod.start_time) / 60.0
        if age_minutes > startup_window_minutes:
            mature_pods.append(pod.name)
    
    # 3. Calculate CPU only from mature pods
    if mature_pods:
        cpu_query = f'avg(rate(container_cpu_usage_seconds_total{{pod=~"{mature_pods}"}}[5m]))'
    else:
        # Fallback to all pods if none are mature yet
        cpu_query = f'avg(rate(container_cpu_usage_seconds_total{{pod=~"{deployment}-.*"}}[5m]))'
    
    return avg_cpu
```

## Monitoring

### Logs

The operator logs when startup filtering is active:

```
INFO - payment-service - Detected 2 pods started <2min ago
INFO - payment-service - Using 3 mature pods for CPU calculation (excluded 2 young pods)
```

### Metrics

Prometheus metrics show the effect:

```
# Mature pods used for scaling decisions
autoscaler_mature_pod_count{namespace="production",deployment="payment-service"} 3

# Young pods excluded
autoscaler_excluded_pod_count{namespace="production",deployment="payment-service"} 2
```

## Best Practices

### 1. Measure Your Startup Time

Before configuring, measure how long your pods take to stabilize:

```bash
# Watch pod CPU during startup
kubectl top pod -n production -l app=my-app --watch

# Or use Prometheus
rate(container_cpu_usage_seconds_total{pod="my-app-xyz"}[1m])
```

Set the filter to **1.5x your observed stabilization time** for safety.

### 2. Different Values for Different Environments

Development environments might have slower startup due to debug mode:

```yaml
# Production
DEPLOYMENT_0_STARTUP_FILTER: "3"

# Development (slower startup)
DEPLOYMENT_0_STARTUP_FILTER: "5"
```

### 3. Combine with HPA Behavior

Use startup filter with HPA stabilization windows:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-app-hpa
spec:
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 120  # Wait 2 minutes before scaling up
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
```

This prevents rapid scale-up during startup spikes.

### 4. Monitor for Flapping

If you see scaling thrashing despite the filter, increase the value:

```bash
# Check scaling events
kubectl get events -n production --field-selector involvedObject.name=my-app-hpa

# If you see rapid scale up/down, increase filter
DEPLOYMENT_0_STARTUP_FILTER: "5"  # Increase from 3 to 5
```

## Troubleshooting

### Problem: Pods still scaling up during startup

**Solution**: Increase the startup filter value

```bash
# Current: 2 minutes
DEPLOYMENT_0_STARTUP_FILTER: "2"

# Try: 4 minutes
DEPLOYMENT_0_STARTUP_FILTER: "4"
```

### Problem: Slow response to real load increases

**Solution**: Decrease the startup filter value

```bash
# Current: 5 minutes (too high)
DEPLOYMENT_0_STARTUP_FILTER: "5"

# Try: 3 minutes
DEPLOYMENT_0_STARTUP_FILTER: "3"
```

### Problem: No pods are "mature" yet

**Behavior**: The operator falls back to using all pods

**Solution**: This is expected during initial deployment. The filter only applies when at least one pod is mature.

## Examples

### Java Spring Boot Application

```yaml
# High startup filter for Java
DEPLOYMENT_0_NAMESPACE: "production"
DEPLOYMENT_0_NAME: "spring-api"
DEPLOYMENT_0_HPA_NAME: "spring-api-hpa"
DEPLOYMENT_0_STARTUP_FILTER: "5"  # 5 minutes for Spring Boot
DEPLOYMENT_0_PRIORITY: "high"
```

### Go Microservice

```yaml
# Low startup filter for Go
DEPLOYMENT_1_NAMESPACE: "production"
DEPLOYMENT_1_NAME: "go-service"
DEPLOYMENT_1_HPA_NAME: "go-service-hpa"
DEPLOYMENT_1_STARTUP_FILTER: "1"  # 1 minute for Go
DEPLOYMENT_1_PRIORITY: "medium"
```

### Node.js API

```yaml
# Medium startup filter for Node.js
DEPLOYMENT_2_NAMESPACE: "production"
DEPLOYMENT_2_NAME: "node-api"
DEPLOYMENT_2_HPA_NAME: "node-api-hpa"
DEPLOYMENT_2_STARTUP_FILTER: "2"  # 2 minutes for Node.js
DEPLOYMENT_2_PRIORITY: "high"
```

## Related Features

- **HPA Behavior Analysis**: Analyzes HPA stabilization windows (see [HPA-ANTI-FLAPPING.md](HPA-ANTI-FLAPPING.md))
- **Pattern Detection**: Detects event-driven patterns with spike-decay behavior
- **Smart Alerts**: Alerts on scaling thrashing (flapping detection)

## References

- Configuration: [QUICK_REFERENCE.md](../QUICK_REFERENCE.md)
- Quick Start: [QUICKSTART.md](../QUICKSTART.md)
- HPA Anti-Flapping: [HPA-ANTI-FLAPPING.md](HPA-ANTI-FLAPPING.md)
