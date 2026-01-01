# Quick Start Guide

## 5-Minute Setup

### 1. Prerequisites Check
```bash
kubectl version --client
kubectl get nodes
```

### 2. Deploy Operator
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### 3. Verify
```bash
kubectl get pods -n autoscaler-system
kubectl logs -f deployment/smart-autoscaler -n autoscaler-system
```

### 4. Access UI
```bash
kubectl port-forward svc/smart-autoscaler 5000:5000 8000:8000 -n autoscaler-system
```

Open:
- Dashboard: http://localhost:5000
- Metrics: http://localhost:8000/metrics

### 5. ArgoCD Integration (If Using GitOps)

Add this annotation to your HPA manifests:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-app-hpa
  annotations:
    argocd.argoproj.io/compare-options: IgnoreExtraneous
```

This prevents ArgoCD from reverting Smart Autoscaler's HPA target adjustments.

📖 See [ArgoCD Integration Guide](docs/ARGOCD_INTEGRATION.md) for details.

### 6. Configure Webhooks (Optional)
```bash
kubectl edit configmap smart-autoscaler-config -n autoscaler-system
# Add SLACK_WEBHOOK, TEAMS_WEBHOOK, etc.
kubectl rollout restart deployment/smart-autoscaler -n autoscaler-system
```

Done! 🎉
