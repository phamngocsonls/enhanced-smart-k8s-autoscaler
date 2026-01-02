# Quick Start Guide

Get Smart Autoscaler running in **5 minutes**! 🚀

---

## Step 1: Check Prerequisites

You need:
- ✅ Kubernetes cluster (1.19+)
- ✅ Prometheus with kube-state-metrics
- ✅ kubectl configured

```bash
# Quick check
kubectl version --client
kubectl get nodes
```

---

## Step 2: Install (Choose One Method)

### Option A: Using Helm (Recommended) ⭐

```bash
# Clone repo
git clone https://github.com/phamngocsonls/enhanced-smart-k8s-autoscaler.git
cd enhanced-smart-k8s-autoscaler

# Install with Helm
helm install smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  --create-namespace \
  --set config.prometheusUrl=http://prometheus-server.monitoring:9090
```

### Option B: Using kubectl

```bash
# Clone repo
git clone https://github.com/phamngocsonls/enhanced-smart-k8s-autoscaler.git
cd enhanced-smart-k8s-autoscaler

# Apply manifests
kubectl apply -f k8s/
```

---

## Step 3: Configure Your Deployments

Edit the ConfigMap to tell the autoscaler which deployments to watch:

```bash
kubectl edit configmap smart-autoscaler-config -n autoscaler-system
```

Add your deployments:

```yaml
data:
  # First deployment
  DEPLOYMENT_0_NAMESPACE: "default"
  DEPLOYMENT_0_NAME: "my-app"
  DEPLOYMENT_0_HPA_NAME: "my-app-hpa"
  
  # Second deployment (optional)
  DEPLOYMENT_1_NAMESPACE: "production"
  DEPLOYMENT_1_NAME: "api-service"
  DEPLOYMENT_1_HPA_NAME: "api-service-hpa"
```

**Important**: Replace `my-app` with your actual deployment name!

**Or use the example file**:
```bash
# Edit examples/configmap-simple.yaml with your deployment names
kubectl apply -f examples/configmap-simple.yaml
```

Restart to apply:
```bash
kubectl rollout restart deployment/smart-autoscaler -n autoscaler-system
```

---

## Step 4: Access Dashboard

```bash
kubectl port-forward svc/smart-autoscaler 5000:5000 -n autoscaler-system
```

Open in browser: **http://localhost:5000** 🎉

You should see:
- 📊 Cluster metrics
- 🔮 Predictions
- 💰 Cost analysis
- 🎯 Recommendations

---

## Step 5: Verify It's Working

Check the logs:

```bash
kubectl logs -f deployment/smart-autoscaler -n autoscaler-system
```

You should see:
```
INFO - Configuration loaded: 2 deployments
INFO - my-app - Node: 45.2%, Pod CPU: 0.234 cores, Pressure: safe
INFO - Predictive scaling enabled
```

---

## Common Issues

### ❌ "Failed to connect to Prometheus"

**Fix**: Update Prometheus URL in ConfigMap:

```bash
kubectl edit configmap smart-autoscaler-config -n autoscaler-system
```

Change:
```yaml
data:
  PROMETHEUS_URL: "http://your-prometheus-url:9090"
```

### ❌ "No deployments configured"

**Fix**: Add deployments to ConfigMap (see Step 3)

### ❌ "HPA not found"

**Fix**: Make sure your HPA exists:

```bash
kubectl get hpa -A
```

If missing, create one:

```bash
# Use the example file
kubectl apply -f examples/hpa-simple.yaml
```

Or create manually:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-app-hpa
  namespace: default
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## Next Steps

### 🔧 Fine-Tune Settings

**For Java/JVM apps** (slow startup):
```yaml
DEPLOYMENT_0_STARTUP_FILTER: "5"  # Wait 5 min before using pod metrics
```

**Set priority** (critical services get resources first):
```yaml
DEPLOYMENT_0_PRIORITY: "critical"  # critical, high, medium, low, best_effort
```

**Adjust costs** (for accurate FinOps):
```yaml
COST_PER_VCPU_HOUR: "0.04"        # Your cloud provider's CPU cost
COST_PER_GB_MEMORY_HOUR: "0.004"  # Your cloud provider's memory cost
```

### 📚 Learn More

- **Java/JVM apps?** → [Startup Filter Guide](docs/STARTUP_FILTER.md)
- **Using ArgoCD?** → [ArgoCD Integration](docs/ARGOCD_INTEGRATION.md)
- **Scaling issues?** → [HPA Anti-Flapping](docs/HPA-ANTI-FLAPPING.md)
- **All settings** → [Configuration Reference](QUICK_REFERENCE.md)

### 🔔 Optional: Add Alerts

Get notified on Slack/Teams:

```bash
kubectl edit configmap smart-autoscaler-config -n autoscaler-system
```

Add:
```yaml
data:
  SLACK_WEBHOOK: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

---

## Quick Reference

| What | Command |
|------|---------|
| View logs | `kubectl logs -f deployment/smart-autoscaler -n autoscaler-system` |
| Restart | `kubectl rollout restart deployment/smart-autoscaler -n autoscaler-system` |
| Edit config | `kubectl edit configmap smart-autoscaler-config -n autoscaler-system` |
| Check status | `kubectl get pods -n autoscaler-system` |
| Access dashboard | `kubectl port-forward svc/smart-autoscaler 5000:5000 -n autoscaler-system` |
| View metrics | `kubectl port-forward svc/smart-autoscaler 8000:8000 -n autoscaler-system` |

---

## Need Help?

- 📖 [Full Documentation](README.md)
- 🐛 [Report Issues](https://github.com/phamngocsonls/enhanced-smart-k8s-autoscaler/issues)
- 💬 Check logs: `kubectl logs -f deployment/smart-autoscaler -n autoscaler-system`

**That's it!** You're now running an AI-powered autoscaler! 🎉
