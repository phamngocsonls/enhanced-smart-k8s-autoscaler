# Auto-Discovery via Annotations

Smart Autoscaler can automatically discover and manage HPAs using Kubernetes annotations. This eliminates the need to manually configure each deployment in the ConfigMap.

## Quick Start

Add the annotation to your HPA:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-app-hpa
  annotations:
    smart-autoscaler.io/enabled: "true"
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  # ... rest of HPA spec
```

That's it! Smart Autoscaler will automatically discover and manage this HPA.

## Supported Annotations

| Annotation | Required | Default | Description |
|------------|----------|---------|-------------|
| `smart-autoscaler.io/enabled` | Yes | - | Set to `"true"` to enable auto-discovery |
| `smart-autoscaler.io/priority` | No | `medium` | Priority level: `critical`, `high`, `medium`, `low`, `best_effort` |
| `smart-autoscaler.io/startup-filter` | No | `2` | Minutes to ignore scaling after pod start |

## Priority Levels

| Priority | Use Case | Behavior |
|----------|----------|----------|
| `critical` | Payment, Auth | Fastest scaling, most headroom, never preempted |
| `high` | API servers | Fast scaling, good headroom |
| `medium` | Standard apps | Balanced scaling (default) |
| `low` | Batch jobs | Slower scaling, less headroom |
| `best_effort` | Dev/Test | Slowest scaling, can be preempted |

## Examples

### High-Priority API Server

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-server-hpa
  namespace: production
  annotations:
    smart-autoscaler.io/enabled: "true"
    smart-autoscaler.io/priority: "high"
    smart-autoscaler.io/startup-filter: "3"
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### Critical Payment Service

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: payment-hpa
  namespace: production
  annotations:
    smart-autoscaler.io/enabled: "true"
    smart-autoscaler.io/priority: "critical"
    smart-autoscaler.io/startup-filter: "5"
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: payment-service
  minReplicas: 3
  maxReplicas: 15
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
```

### Low-Priority Background Worker

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: worker-hpa
  namespace: production
  annotations:
    smart-autoscaler.io/enabled: "true"
    smart-autoscaler.io/priority: "low"
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: background-worker
  minReplicas: 1
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 80
```

## Configuration

### Enable/Disable Auto-Discovery

Auto-discovery is enabled by default. To disable:

**Environment Variable:**
```bash
ENABLE_AUTO_DISCOVERY=false
```

**Helm Values:**
```yaml
config:
  enableAutoDiscovery: false
```

### Combining with ConfigMap

Auto-discovery works alongside ConfigMap-based configuration:

1. **ConfigMap deployments** take precedence over auto-discovered ones
2. If a deployment is in both ConfigMap and has annotations, ConfigMap settings are used
3. Auto-discovered workloads are marked with `source: annotation` internally

## How It Works

1. **Initial Discovery**: On startup, Smart Autoscaler scans all HPAs for the `smart-autoscaler.io/enabled: "true"` annotation
2. **Continuous Watching**: A background watcher monitors HPA changes (create, update, delete)
3. **Dynamic Updates**: When an HPA is annotated or annotation is removed, the workload is automatically added/removed
4. **Alerts**: Notifications are sent when workloads are discovered or removed

## Dashboard Integration

Auto-discovered workloads appear in the dashboard with:
- Source indicator showing "annotation" vs "config"
- All standard metrics and cost tracking
- FinOps recommendations

## API Endpoints

Check discovered workloads via API:

```bash
# List all deployments (includes source info)
curl http://localhost:5000/api/deployments

# Response includes source field
{
  "deployments": [
    {
      "namespace": "production",
      "deployment": "api-server",
      "hpa_name": "api-server-hpa",
      "priority": "high",
      "source": "annotation"
    }
  ]
}
```

## Troubleshooting

### HPA Not Being Discovered

1. Check annotation is exactly `smart-autoscaler.io/enabled: "true"` (case-sensitive)
2. Verify HPA targets a Deployment (StatefulSets not yet supported)
3. Check Smart Autoscaler logs for discovery messages

### Priority Not Applied

1. Verify priority value is one of: `critical`, `high`, `medium`, `low`, `best_effort`
2. Invalid values default to `medium`

### Startup Filter Not Working

1. Value must be a valid integer (minutes)
2. Invalid values default to `2`

## Best Practices

1. **Use annotations for dynamic workloads** that are frequently deployed/updated
2. **Use ConfigMap for stable, critical workloads** that need explicit configuration
3. **Set appropriate priorities** based on business impact
4. **Use startup filters** for services with slow initialization
5. **Monitor alerts** for auto-discovery events

## See Also

- [examples/hpa-auto-discovery.yaml](../examples/hpa-auto-discovery.yaml) - Example HPAs with annotations
- [Priority Manager](./PRIORITY_MANAGER.md) - Priority system documentation
- [Configuration](./SCALING_CONFIGURATION.md) - Full configuration reference
