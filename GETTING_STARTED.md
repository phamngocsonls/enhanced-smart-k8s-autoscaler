# Getting Started in 60 Seconds ⚡

The absolute fastest way to get Smart Autoscaler running!

## 1. Install (10 seconds)

```bash
kubectl apply -f https://raw.githubusercontent.com/phamngocsonls/enhanced-smart-k8s-autoscaler/main/k8s/namespace.yaml
kubectl apply -f https://raw.githubusercontent.com/phamngocsonls/enhanced-smart-k8s-autoscaler/main/k8s/rbac.yaml
kubectl apply -f https://raw.githubusercontent.com/phamngocsonls/enhanced-smart-k8s-autoscaler/main/k8s/pvc.yaml
kubectl apply -f https://raw.githubusercontent.com/phamngocsonls/enhanced-smart-k8s-autoscaler/main/k8s/configmap.yaml
kubectl apply -f https://raw.githubusercontent.com/phamngocsonls/enhanced-smart-k8s-autoscaler/main/k8s/deployment.yaml
kubectl apply -f https://raw.githubusercontent.com/phamngocsonls/enhanced-smart-k8s-autoscaler/main/k8s/service.yaml
```

## 2. Configure (30 seconds)

```bash
kubectl edit configmap smart-autoscaler-config -n autoscaler-system
```

Change these lines:
```yaml
data:
  PROMETHEUS_URL: "http://YOUR-PROMETHEUS:9090"  # ← Your Prometheus URL
  DEPLOYMENT_0_NAME: "YOUR-APP"                  # ← Your deployment name
  DEPLOYMENT_0_HPA_NAME: "YOUR-APP-hpa"          # ← Your HPA name
```

Save and exit (`:wq` in vim)

## 3. Restart (10 seconds)

```bash
kubectl rollout restart deployment/smart-autoscaler -n autoscaler-system
```

## 4. View Dashboard (10 seconds)

```bash
kubectl port-forward svc/smart-autoscaler 5000:5000 -n autoscaler-system
```

Open: **http://localhost:5000** 🎉

---

## Done! ✅

You should now see:
- 📊 Your cluster metrics
- 🔮 CPU predictions
- 💰 Cost analysis
- 🎯 Scaling recommendations

---

## Troubleshooting

**Can't connect to Prometheus?**
```bash
# Check Prometheus URL
kubectl get svc -A | grep prometheus
```

**Don't have an HPA?**
```bash
# Create one
kubectl autoscale deployment YOUR-APP --cpu-percent=70 --min=2 --max=10
```

**Need more help?**
- 📖 [Full Quick Start Guide](QUICKSTART.md)
- 📚 [Complete Documentation](README.md)

---

## What's Next?

### For Java/JVM Apps
Add this to prevent scaling on startup spikes:
```yaml
DEPLOYMENT_0_STARTUP_FILTER: "5"  # Wait 5 minutes
```

### For Critical Services
Set priority to protect during resource pressure:
```yaml
DEPLOYMENT_0_PRIORITY: "critical"  # Gets resources first
```

### For Cost Optimization
Set your cloud costs for accurate FinOps:
```yaml
COST_PER_VCPU_HOUR: "0.04"        # Your CPU cost
COST_PER_GB_MEMORY_HOUR: "0.004"  # Your memory cost
```

---

**That's it!** You're running an AI-powered autoscaler! 🚀
