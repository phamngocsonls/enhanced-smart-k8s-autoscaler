# Smart Kubernetes Autoscaler

🚀 **AI-Powered, Cost-Optimized, Node-Aware HPA Controller with Predictive Scaling**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Kubernetes 1.19+](https://img.shields.io/badge/kubernetes-1.19+-326CE5.svg)](https://kubernetes.io/)
[![Version](https://img.shields.io/badge/version-0.0.20-blue.svg)](changelogs/)

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
- Multiple prediction windows: 15min, 30min, 1hr, 2hr
- Model selection based on workload type (steady, bursty, periodic, growing)
- Ensemble ML predictions combining mean, trend, and seasonal models
- Pattern-aware predictions with weekly pattern recognition
- Adaptive confidence based on historical accuracy

### 💰 Cost Optimization
- CPU and memory cost tracking
- Wasted resource detection
- Monthly cost projections
- FinOps recommendations with adjusted HPA targets
- Minimum CPU request enforcement (100m) for HPA stability
- Resource change detection with automatic HPA adjustment

### 🧠 Auto-Tuning
- Learns optimal HPA targets over 7 days
- Bayesian optimization for faster initial learning
- Per-hour optimal targets (different for peak vs off-peak hours)
- Adaptive learning rate based on workload stability
- Auto-applies when confidence >80%

### 📊 Pattern Detection
- 9 workload pattern types detected automatically
- Weekly seasonal patterns (weekday vs weekend behavior)
- Monthly seasonal patterns (beginning/end of month spikes)
- Event-driven pattern detection (spike-decay analysis)
- Cross-deployment correlation detection
- Automatic strategy selection per pattern type

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

## 🧠 Core Intelligence Features

### Multi-Window Predictions

The autoscaler predicts CPU load across multiple time windows:

| Window | Use Case |
|--------|----------|
| 15min | Immediate response planning |
| 30min | Short-term capacity planning |
| 1hr | Standard predictive scaling |
| 2hr | Long-term trend analysis |

Each prediction uses an ensemble of models weighted by workload type:
- **Mean model**: Historical average for the time slot
- **Trend model**: Linear regression for growth/decline
- **Seasonal model**: Weekly pattern recognition
- **Recent model**: Short-term average for bursty workloads

### Bayesian Auto-Tuning

Faster learning with Bayesian optimization:
- Balances exploration (trying new targets) vs exploitation (using known good targets)
- Converges to optimal HPA target 3x faster than traditional methods
- Per-hour optimal targets for different peak/off-peak behavior
- Automatic learning rate adjustment based on workload stability

### Advanced Pattern Detection

9 workload patterns detected automatically:

| Pattern | Description | Strategy |
|---------|-------------|----------|
| `steady` | Low variance, consistent load | Standard scaling |
| `bursty` | High variance, frequent spikes | Aggressive scale-up |
| `periodic` | Daily/weekly cycles | Predictive enabled |
| `growing` | Upward trend | Maintain headroom |
| `declining` | Downward trend | Cost optimization |
| `weekly_seasonal` | Weekday vs weekend | Weekly predictions |
| `monthly_seasonal` | Beginning/end of month | Monthly predictions |
| `event_driven` | Spike-decay patterns | Fast response |
| `unknown` | Insufficient data | Conservative defaults |

### Correlation Detection

Automatically detects relationships between deployments:
- Frontend/backend load correlation
- Cascading load patterns (A triggers B)
- Shared resource contention
- Lag detection (B follows A by N minutes)

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
| `GET /api/deployment/{ns}/{name}/predictions` | ML predictions (all windows) |
| `GET /api/deployment/{ns}/{name}/pattern` | Detected workload pattern |
| `GET /api/deployment/{ns}/{name}/memory-leak` | Memory leak detection |
| `GET /api/deployment/{ns}/{name}/detail` | Comprehensive deployment detail |
| `GET /api/predictions/accuracy/{dep}` | Prediction accuracy history |
| `GET /api/finops/summary` | All deployment recommendations |
| `GET /api/finops/cost-trends` | 30-day cost trends |
| `GET /api/alerts/recent` | Recent anomalies and alerts |
| `GET /api/correlations` | Cross-deployment correlations |

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
ENABLE_CORRELATIONS: "true" # Cross-deployment correlation detection
```

### Prediction Settings

```yaml
PREDICTION_MIN_ACCURACY: "0.60"  # Minimum accuracy threshold (60%)
PREDICTION_MIN_SAMPLES: "10"     # Samples needed before trusting predictions
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
# Core metrics
autoscaler_node_utilization_percent
autoscaler_hpa_target_percent
autoscaler_pod_count
autoscaler_confidence_score

# Prediction metrics
autoscaler_predicted_cpu_percent
autoscaler_prediction_confidence
autoscaler_prediction_accuracy_rate

# Cost metrics
autoscaler_monthly_cost_usd
autoscaler_wasted_capacity_percent

# Learning metrics
autoscaler_learning_rate
autoscaler_bayesian_best_score
autoscaler_hourly_targets_learned
```

---

## 🔄 Version History

| Version | Date | Changes |
|---------|------|---------|
| v0.0.20 | 2026-01-02 | Prediction accuracy charts, cost trends visualization, alerts dashboard, improved confidence threshold |
| v0.0.19 | 2026-01-02 | Grafana-style dashboard, multi-window predictions, Bayesian auto-tuning, enhanced pattern detection, FinOps improvements |
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
