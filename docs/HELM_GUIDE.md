# Helm Installation Guide

Complete guide to installing Smart Autoscaler with Helm.

## Quick Start (5 minutes)

### 1. Clone the Repository

```bash
git clone https://github.com/phamngocsonls/enhanced-smart-k8s-autoscaler.git
cd enhanced-smart-k8s-autoscaler
```

### 2. Install with Minimal Config

```bash
helm install smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  --create-namespace \
  --set config.prometheusUrl=http://prometheus-server.monitoring:9090
```

### 3. Access Dashboard

```bash
kubectl port-forward svc/smart-autoscaler 5000:5000 -n autoscaler-system
# Open http://localhost:5000
```

That's it! 🎉

---

## Installation Options

### Option 1: Using --set (Quick)

```bash
helm install smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  --create-namespace \
  --set config.prometheusUrl=http://prometheus-server.monitoring:9090 \
  --set config.dryRun=true
```

### Option 2: Using Values File (Recommended)

```bash
# Use the simple example
helm install smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  --create-namespace \
  -f examples/helm-values-simple.yaml

# Or the production example
helm install smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  --create-namespace \
  -f examples/helm-values-production.yaml
```

### Option 3: Custom Values File

Create your own `my-values.yaml`:

```yaml
config:
  prometheusUrl: "http://my-prometheus:9090"
  dryRun: false
  enableAutoDiscovery: true

deployments:
  - namespace: default
    name: my-app
    hpaName: my-app-hpa
    priority: medium
```

Install:
```bash
helm install smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  --create-namespace \
  -f my-values.yaml
```

---

## Common Configurations

### Minimal (Testing)

```yaml
config:
  prometheusUrl: "http://prometheus-server.monitoring:9090"
  dryRun: true
  enableAutoDiscovery: true
```

### Standard (Most Users)

```yaml
config:
  prometheusUrl: "http://prometheus-server.monitoring:9090"
  dryRun: false
  enableAutoDiscovery: true
  enablePredictive: true
  enableAutopilot: false

webhooks:
  slack: "https://hooks.slack.com/services/xxx/yyy/zzz"
```

### Production (Full Features)

```yaml
config:
  prometheusUrl: "http://prometheus-server.monitoring:9090"
  dryRun: false
  enableAutoDiscovery: true
  enablePredictive: true
  enablePrescale: true
  
  # Autopilot with learning
  enableAutopilot: true
  autopilotLevel: recommend
  autopilotEnableLearning: true
  autopilotLearningDays: 7
  autopilotEnableRollback: true

deployments:
  - namespace: production
    name: api-gateway
    hpaName: api-gateway-hpa
    priority: critical
    startupFilterMinutes: 2

webhooks:
  slack: "https://hooks.slack.com/services/xxx/yyy/zzz"

resources:
  requests:
    cpu: 200m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 1Gi

persistence:
  enabled: true
  size: 20Gi
```

---

## Configuration Reference

### Required Settings

| Setting | Description | Example |
|---------|-------------|---------|
| `config.prometheusUrl` | Your Prometheus URL | `http://prometheus-server.monitoring:9090` |

### Core Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `config.dryRun` | `false` | Test mode (no actual scaling) |
| `config.checkInterval` | `60` | Seconds between checks |
| `config.logLevel` | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `config.enableAutoDiscovery` | `true` | Auto-find HPAs with annotation |
| `config.enablePredictive` | `true` | Predict traffic spikes |
| `config.enablePrescale` | `true` | Pre-scale before spikes |

### Autopilot Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `config.enableAutopilot` | `false` | Enable autopilot mode |
| `config.autopilotLevel` | `recommend` | disabled/observe/recommend/autopilot |
| `config.autopilotMinConfidence` | `0.80` | Min confidence to apply |
| `config.autopilotMaxChangePercent` | `30` | Max % change per iteration |
| `config.autopilotCooldownHours` | `24` | Hours between changes |
| `config.autopilotEnableLearning` | `true` | Enable learning phase |
| `config.autopilotLearningDays` | `7` | Days to learn |
| `config.autopilotEnableRollback` | `true` | Auto-rollback on issues |

### Deployment Settings

```yaml
deployments:
  - namespace: default        # Required
    name: my-app              # Required
    hpaName: my-app-hpa       # Required
    startupFilterMinutes: 2   # Optional (default: 2)
    priority: medium          # Optional (default: medium)
```

**Priority Levels:**
| Priority | HPA Target | Use Case |
|----------|------------|----------|
| `critical` | 55% | Payment, Auth |
| `high` | 60% | APIs, Gateways |
| `medium` | 70% | Standard workloads |
| `low` | 80% | Background jobs |
| `best_effort` | 85% | Reports, Analytics |

**Startup Filter (minutes):**
| App Type | Recommended |
|----------|-------------|
| Go/Rust | 0-1 |
| Node.js | 1-2 |
| Python | 2-3 |
| Java/JVM | 3-5 |

### Webhook Settings

```yaml
webhooks:
  slack: "https://hooks.slack.com/services/xxx/yyy/zzz"
  teams: "https://outlook.office.com/webhook/xxx"
  discord: "https://discord.com/api/webhooks/xxx/yyy"
  googleChat: "https://chat.googleapis.com/v1/spaces/xxx/messages"
```

---

## Upgrade

```bash
# Update values
helm upgrade smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  -f my-values.yaml

# Or update specific setting
helm upgrade smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  --reuse-values \
  --set config.enableAutopilot=true
```

---

## Uninstall

```bash
helm uninstall smart-autoscaler --namespace autoscaler-system
kubectl delete namespace autoscaler-system
```

---

## Troubleshooting

### Check Status

```bash
kubectl get pods -n autoscaler-system
kubectl logs -f deployment/smart-autoscaler -n autoscaler-system
```

### Common Issues

**"Failed to connect to Prometheus"**
```bash
# Check Prometheus URL
kubectl get svc -A | grep prometheus
# Update with correct URL
helm upgrade smart-autoscaler ./helm/smart-autoscaler \
  --reuse-values \
  --set config.prometheusUrl=http://correct-url:9090
```

**"No deployments found"**
- If using auto-discovery: Add annotation to your HPAs
  ```yaml
  annotations:
    smart-autoscaler.io/enabled: "true"
  ```
- If listing deployments: Check your values file

**Pod keeps restarting**
```bash
kubectl describe pod -l app.kubernetes.io/name=smart-autoscaler -n autoscaler-system
kubectl logs -f deployment/smart-autoscaler -n autoscaler-system --previous
```

---

## Example Values Files

| File | Use Case |
|------|----------|
| `examples/helm-values-simple.yaml` | Beginners, testing |
| `examples/helm-values-production.yaml` | Production with all features |
| `examples/helm-values-many-deployments.yaml` | 10+ deployments |

---

## Next Steps

- [QUICKSTART.md](../QUICKSTART.md) - Quick start guide
- [QUICK_REFERENCE.md](../QUICK_REFERENCE.md) - All configuration options
- [docs/AUTOPILOT.md](AUTOPILOT.md) - Autopilot mode details
- [docs/FEATURE_COORDINATION.md](FEATURE_COORDINATION.md) - How features work together
