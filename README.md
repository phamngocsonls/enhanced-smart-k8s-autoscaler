# Smart Kubernetes Autoscaler

🚀 **AI-Powered, Cost-Optimized, Node-Aware HPA Controller with Predictive Scaling**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Kubernetes 1.19+](https://img.shields.io/badge/kubernetes-1.19+-326CE5.svg)](https://kubernetes.io/)
[![Version](https://img.shields.io/badge/version-0.0.18-blue.svg)](changelogs/)

An intelligent Kubernetes autoscaling operator that goes beyond standard HPA by combining real-time node pressure management with historical learning, predictive scaling, anomaly detection, cost optimization, and cluster-wide monitoring.

---

## 🌟 Why Smart Autoscaler?

Traditional HPA has limitations:
- ❌ Reacts **after** problems occur
- ❌ Ignores node capacity
- ❌ No learning from history
- ❌ No cost awareness
- ❌ Manual tuning required

**Smart Autoscaler solves all of these:**
- ✅ **Predicts** spikes before they happen
- ✅ **Tracks** node capacity per deployment
- ✅ **Learns** optimal settings automatically
- ✅ **Optimizes** costs with FinOps recommendations
- ✅ **Self-tunes** based on performance
- ✅ **Monitors** entire cluster in real-time

---

## ✨ Key Features

### 🖥️ Cluster Monitoring (v0.0.18)
- Real-time CPU and memory usage across all nodes
- Total pod count from Prometheus
- Health status indicators (Healthy/Warning/Critical)
- 24-hour trend charts
- Per-node resource breakdown

### 🔮 Predictive Pre-Scaling
- Predicts CPU load 1 hour ahead
- Pre-scales **before** traffic spikes
- Uses ensemble ML models
- Pattern-aware predictions (daily/weekly cycles)

### 💰 Cost Optimization
- CPU and memory cost tracking
- Wasted resource detection
- Monthly cost projections
- FinOps recommendations with adjusted HPA targets

### 🧠 Auto-Tuning
- Learns optimal HPA targets over 7 days
- Adaptive learning rate based on workload stability
- Auto-applies when confidence >80%

### 🎯 Priority-Based Scaling
- 5 priority levels: critical, high, medium, low, best_effort
- Protects critical services during resource pressure
- Auto-detection from deployment names

### 🛡️ Production Features
- Health checks and Kubernetes probes
- Hot reload configuration
- Degraded mode resilience
- Rate limiting and circuit breakers
- Structured JSON logging

---

## 🚀 Quick Start

### Prerequisites
- Kubernetes 1.19+
- Prometheus (with kube-state-metrics)
- Helm 3+ (optional)

### Installation

```bash
# Using Helm (recommended)
helm install smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  --create-namespace \
  --set prometheus.url=http://prometheus-server.monitoring:80

# Or using kubectl
kubectl apply -f k8s/
```

### Access Dashboard

```bash
# Port forward
kubectl port-forward svc/smart-autoscaler -n autoscaler-system 5000:5000

# Open browser
open http://localhost:5000
```

### Configure Deployments

```yaml
# Environment variables or ConfigMap
DEPLOYMENT_0_NAMESPACE: "default"
DEPLOYMENT_0_NAME: "my-app"
DEPLOYMENT_0_HPA_NAME: "my-app-hpa"
DEPLOYMENT_0_PRIORITY: "high"  # critical, high, medium, low, best_effort
```

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [QUICKSTART.md](QUICKSTART.md) | Quick start guide |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | Configuration reference |
| [CI_CD_SETUP.md](CI_CD_SETUP.md) | CI/CD pipeline setup |
| [docs/CLUSTER_MONITORING.md](docs/CLUSTER_MONITORING.md) | Cluster monitoring guide |
| [docs/PREDICTIVE_SCALING.md](docs/PREDICTIVE_SCALING.md) | Predictive scaling guide |
| [docs/HPA-ANTI-FLAPPING.md](docs/HPA-ANTI-FLAPPING.md) | HPA anti-flapping guide |
| [docs/ARGOCD_INTEGRATION.md](docs/ARGOCD_INTEGRATION.md) | ArgoCD integration |

---

## 📊 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Web dashboard |
| `GET /api/health` | Health check |
| `GET /api/cluster/metrics` | Cluster-wide metrics |
| `GET /api/deployments` | List watched deployments |
| `GET /api/deployment/{ns}/{name}/current` | Current deployment state |
| `GET /api/deployment/{ns}/{name}/cost` | Cost breakdown |
| `GET /api/deployment/{ns}/{name}/recommendations` | FinOps recommendations |
| `GET /api/deployment/{ns}/{name}/predictions` | ML predictions |

---

## ⚙️ Configuration

### Core Settings

```yaml
PROMETHEUS_URL: "http://prometheus-server.monitoring:80"
CHECK_INTERVAL: "60"           # seconds
TARGET_NODE_UTILIZATION: "40"  # percent
DRY_RUN: "false"
```

### Feature Flags

```yaml
ENABLE_PREDICTIVE: "true"   # Predictive scaling
ENABLE_AUTOTUNING: "true"   # Auto-tuning
```

### Cost Settings

```yaml
COST_PER_VCPU_HOUR: "0.04"        # $/vCPU/hour
COST_PER_GB_MEMORY_HOUR: "0.004"  # $/GB/hour
```

---

## 📈 Prometheus Metrics

Key metrics exported on port 8000:

```
autoscaler_node_utilization_percent
autoscaler_hpa_target_percent
autoscaler_pod_count
autoscaler_confidence_score
autoscaler_predicted_cpu_percent
autoscaler_monthly_cost_usd
autoscaler_wasted_capacity_percent
```

---

## 🔄 Version History

| Version | Date | Changes |
|---------|------|---------|
| v0.0.18 | 2026-01-02 | Cluster monitoring improvements, Total Pods from Prometheus, chart fixes |
| v0.0.17 | 2026-01-01 | Cache-busting headers, auto-load cluster metrics |
| v0.0.14 | 2026-01-01 | Fixed cluster summary totals |
| v0.0.13 | 2026-01-01 | Enhanced fallback queries for node metrics |
| v0.0.12 | 2026-01-01 | Fixed auto-tuning, pattern detection, node CPU queries |

See [changelogs/](changelogs/) for full history.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `./run_tests.sh`
5. Submit a pull request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- Kubernetes HPA for the foundation
- Prometheus for metrics
- Chart.js for dashboard visualizations
