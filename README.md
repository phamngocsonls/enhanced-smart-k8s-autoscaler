# Smart Kubernetes Autoscaler

🚀 AI-Powered, Cost-Optimized, Node-Aware HPA Controller with Predictive Scaling

## ✨ Features

- 📊 **Historical Learning** - Learns patterns from 30 days of data
- 🔮 **Predictive Pre-Scaling** - Scales before spikes happen
- 💰 **Cost Optimization** - Tracks and optimizes monthly costs
- 🚨 **Anomaly Detection** - Detects 4 types of anomalies
- 🎯 **Auto-Tuning** - Finds optimal HPA targets automatically
- 📢 **Multi-Channel Alerts** - Slack, Teams, Discord, webhooks
- 📊 **Prometheus Metrics** - 20+ custom metrics
- 🖥️ **Web Dashboard** - Beautiful real-time UI
- 🤖 **ML Models** - Random Forest, ARIMA, ensemble predictions
- 🔌 **Integrations** - PagerDuty, Datadog, Grafana, Jira

## 🚀 Quick Start
```bash
# 1. Configure webhooks
kubectl edit configmap smart-autoscaler-config -n autoscaler-system

# 2. Deploy
kubectl apply -f k8s/

# 3. Access Dashboard
kubectl port-forward svc/smart-autoscaler 5000:5000 -n autoscaler-system
# Open http://localhost:5000

# 4. View Metrics
kubectl port-forward svc/smart-autoscaler 8000:8000 -n autoscaler-system
# Open http://localhost:8000/metrics
```

## 📦 Installation

### Prerequisites
- Kubernetes 1.19+
- Prometheus with node-exporter
- kubectl configured
- 10GB persistent storage

### Deploy
```bash
# Build image
docker build -f Dockerfile.enhanced -t smart-autoscaler:latest .

# Push to your registry
docker tag smart-autoscaler:latest your-registry/smart-autoscaler:latest
docker push your-registry/smart-autoscaler:latest

# Update k8s/deployment.yaml with your image

# Deploy
kubectl apply -f k8s/
```

## ⚙️ Configuration

Edit `k8s/configmap.yaml`:
```yaml
PROMETHEUS_URL: "http://prometheus:9090"
CHECK_INTERVAL: "60"
TARGET_NODE_UTILIZATION: "70.0"
SLACK_WEBHOOK: "https://hooks.slack.com/..."
```

## 📊 Monitoring

- **Dashboard**: http://localhost:5000
- **Metrics**: http://localhost:8000/metrics
- **Logs**: `kubectl logs -f deployment/smart-autoscaler -n autoscaler-system`

## 🎯 How It Works

1. Monitors node CPU utilization per deployment's node selector
2. Filters startup CPU spikes (first 2 minutes)
3. Uses 10m smoothed + 5m spike metrics (70/30 blend)
4. Predicts load based on historical patterns
5. Adjusts HPA targets dynamically
6. Detects anomalies and sends alerts
7. Tracks costs and suggests optimizations

## 📝 Example HPA
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-service-hpa
spec:
  scaleTargetRef:
    kind: Deployment
    name: my-service
  minReplicas: 2
  maxReplicas: 50
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70  # Operator adjusts this dynamically
```

## 🤝 Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md)

## 📄 License

MIT License - see [LICENSE](LICENSE)

## 🆘 Support

- Issues: GitHub Issues
- Documentation: `/docs`
- Community: [Slack](https://join.slack.com/...)

---

**Built with ❤️ for SRE teams**
