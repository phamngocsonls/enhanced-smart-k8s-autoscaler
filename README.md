# Smart Kubernetes Autoscaler

🚀 **AI-Powered, Cost-Optimized, Node-Aware HPA Controller with Predictive Scaling**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Kubernetes 1.19+](https://img.shields.io/badge/kubernetes-1.19+-326CE5.svg)](https://kubernetes.io/)
[![Version](https://img.shields.io/badge/version-0.0.25-blue.svg)](changelogs/)

An intelligent Kubernetes autoscaling operator that goes beyond standard HPA by combining real-time node pressure management with historical learning, predictive scaling, anomaly detection, cost optimization, GenAI insights, and cluster-wide efficiency monitoring.

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

### 💰 Cost Optimization & Resource Right-Sizing
- **Resource Right-Sizing**: Analyze actual CPU/memory usage (P95 + buffer) and recommend optimal requests
- **No Limits Policy**: Recommendations exclude limits to avoid OOM kills and CPU throttling
- **Recommend Mode Only**: All recommendations are manual - review before applying
- **Smart Buffers**: Base buffer + percentage buffer ensures safety for all workload sizes
- **HPA Target Adjustment**: Automatically calculates adjusted HPA targets to maintain scaling behavior
- CPU and memory cost tracking with detailed breakdown
- Wasted resource detection and monthly cost projections
- Minimum CPU request enforcement (100m) for HPA stability

### 📊 Advanced Cost Allocation (v0.0.25)
- **Auto-Pricing Detection**: Automatically detects cloud provider (GCP/AWS/Azure) and uses actual instance pricing
- **Multi-Dimensional Tracking**: Group costs by team, project, namespace, environment
- **Chargeback/Showback**: Automated cost allocation for billing and budgeting
- **Cost Anomaly Detection**: Statistical analysis to identify unusual cost spikes
- **Idle Resource Detection**: Find underutilized deployments wasting budget
- **Label-Based Allocation**: Automatic cost tagging from Kubernetes labels
- **Historical Trends**: 30/60/90-day cost analysis and comparisons

### 📈 Advanced Reporting (v0.0.25)
- **Executive Summary**: High-level reports for leadership with key metrics and ROI
- **Team Reports**: Detailed cost and performance analysis per team
- **Cost Forecasting**: Predict future costs using linear regression (30/60/90 days)
- **ROI Analysis**: Calculate savings from optimization recommendations
- **Trend Analysis**: Week-over-week and month-over-month comparisons
- **Automated Reports**: API-driven reports for integration with BI tools

### 🖥️ Node Efficiency Dashboard (v0.0.24)
- **Bin-Packing Score**: 0-100 score measuring workload distribution efficiency
- **Resource Waste Analysis**: Track CPU/memory requested vs actually used across cluster
- **Node Classification**: Automatically identify underutilized (<30%), optimal (30-85%), and overutilized (>85%) nodes
- **Node Type Detection**: Classify nodes as compute-optimized, memory-optimized, GPU, or general-purpose
- **Actionable Recommendations**: Specific suggestions for consolidation, capacity planning, and optimization
- **Per-Node Breakdown**: Detailed metrics for every node in the cluster

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
- Startup filter to prevent scaling on JVM/Java startup CPU spikes

### 🔔 Smart Alerts (v0.0.22)
- **CPU Spike Detection** - Alerts when CPU exceeds 3 standard deviations
- **Scaling Thrashing** - Detects excessive scale events (flapping)
- **High Memory Warning** - Alerts before OOM kills occur
- **Low Efficiency** - Identifies wasted resources (<20% utilization)
- **Low Confidence** - Warns when predictions are unreliable

### 🛡️ HPA Behavior Analysis (v0.0.22)
- Reads HPA `behavior.scaleUp` and `behavior.scaleDown` config
- Analyzes stabilization windows and scaling policies
- Detects flapping (>5 events/hour or >20 events/day)
- Risk assessment (low/medium/high)
- Generates ready-to-apply YAML for safe scaling
- Dashboard tab with visual config breakdown

---

## 🚀 Quick Start

**New to Smart Autoscaler?** Start here:

- 🚀 **[60-Second Setup](GETTING_STARTED.md)** - Fastest way to get running
- 📖 **[Quick Start Guide](QUICKSTART.md)** - Step-by-step with explanations
- 📚 **[Full Documentation](#-documentation)** - Deep dive into features

### Installation

```bash
# Using Helm (recommended)
helm install smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  --create-namespace \
  --set config.prometheusUrl=http://prometheus-server.monitoring:9090 \
  --set image.tag=v0.0.24-v5

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

**Quick setup** - Use example files:

```bash
# 1. Edit with your deployment names
vim examples/configmap-simple.yaml

# 2. Apply
kubectl apply -f examples/configmap-simple.yaml

# 3. Create HPA if needed
kubectl apply -f examples/hpa-simple.yaml
```

**⚠️ ConfigMap Limitation**: ConfigMaps have a 1MB size limit (~200-300 deployments max). For more deployments, use [Helm values.yaml](docs/SCALING_CONFIGURATION.md) or see the [Scaling Configuration Guide](docs/SCALING_CONFIGURATION.md).

**Or configure manually**:

```yaml
# Environment variables or ConfigMap
DEPLOYMENT_0_NAMESPACE: "default"
DEPLOYMENT_0_NAME: "my-app"
DEPLOYMENT_0_HPA_NAME: "my-app-hpa"
DEPLOYMENT_0_STARTUP_FILTER: "2"  # Minutes to ignore new pods (default: 2, range: 0-60)
DEPLOYMENT_0_PRIORITY: "high"  # critical, high, medium, low, best_effort
```

**Startup Filter**: Prevents scaling decisions based on CPU spikes during pod startup (JVM initialization, cache warming, etc.). Pods younger than the configured minutes are excluded from CPU metrics. Recommended values:
- Java/JVM apps: 3-5 minutes
- Node.js apps: 1-2 minutes
- Go/Rust apps: 0-1 minutes

### GenAI Integration (Optional)

Enable AI-powered insights and recommendations using cloud GenAI providers:

**Supported Providers:**
- OpenAI (GPT-4, GPT-3.5-turbo)
- Google Gemini (gemini-pro, gemini-1.5-pro)
- Anthropic Claude (claude-3-opus, claude-3-sonnet)

**Configuration:**

```bash
# 1. Enable GenAI
export ENABLE_GENAI=true

# 2. Configure provider (choose one)

# Option A: OpenAI
export OPENAI_API_KEY=sk-...
export GENAI_MODEL=gpt-4  # or gpt-3.5-turbo

# Option B: Google Gemini
export GEMINI_API_KEY=...
export GENAI_MODEL=gemini-pro  # or gemini-1.5-pro

# Option C: Anthropic Claude
export ANTHROPIC_API_KEY=...
export GENAI_MODEL=claude-3-sonnet  # or claude-3-opus

# 3. Deploy with environment variables
helm install smart-autoscaler ./helm/smart-autoscaler \
  --set image.tag=v0.0.24-v5 \
  --set env.ENABLE_GENAI=true \
  --set env.OPENAI_API_KEY=sk-... \
  --set env.GENAI_MODEL=gpt-4
```

**Features:**
- 🧠 **Intelligent Analysis**: AI analyzes scaling patterns and provides insights
- 💡 **Smart Recommendations**: Context-aware suggestions for optimization
- 🔍 **Anomaly Explanation**: Natural language explanations for unusual behavior
- 📊 **Trend Analysis**: AI-powered trend detection and forecasting

**Dashboard Access:**
- Navigate to **AI Insights** tab
- View AI-generated recommendations per deployment
- Get explanations for scaling decisions
- Receive optimization suggestions

**Graceful Degradation:**
- If GenAI is not configured, the dashboard shows activation guide
- All core features work without GenAI
- No errors or failures when GenAI is disabled

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
| [GETTING_STARTED.md](GETTING_STARTED.md) | 60-second setup guide |
| [QUICKSTART.md](QUICKSTART.md) | Step-by-step quick start |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | Configuration reference |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How it works (diagrams & examples) |
| [docs/SCALING_CONFIGURATION.md](docs/SCALING_CONFIGURATION.md) | Configure 100+ deployments |
| [docs/STARTUP_FILTER.md](docs/STARTUP_FILTER.md) | Startup filter for Java/JVM apps |
| [docs/PREDICTIVE_SCALING.md](docs/PREDICTIVE_SCALING.md) | Predictive scaling guide |
| [docs/HPA-ANTI-FLAPPING.md](docs/HPA-ANTI-FLAPPING.md) | HPA anti-flapping guide |
| [docs/CLUSTER_MONITORING.md](docs/CLUSTER_MONITORING.md) | Cluster monitoring guide |
| [docs/NODE_EFFICIENCY.md](docs/NODE_EFFICIENCY.md) | Node efficiency dashboard |
| [docs/COST_ALLOCATION.md](docs/COST_ALLOCATION.md) | Advanced cost allocation & chargeback |
| [docs/REPORTING.md](docs/REPORTING.md) | Executive reports & ROI analysis |
| [docs/ARGOCD_INTEGRATION.md](docs/ARGOCD_INTEGRATION.md) | ArgoCD integration |
| [CI_CD_SETUP.md](CI_CD_SETUP.md) | CI/CD pipeline setup |

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
| `GET /api/deployment/{ns}/{name}/hpa-analysis` | HPA behavior analysis & safe scaling recommendations |
| `GET /api/predictions/accuracy/{dep}` | Prediction accuracy history |
| `GET /api/finops/summary` | All deployment recommendations |
| `GET /api/finops/cost-trends` | 30-day cost trends |
| `GET /api/alerts/recent` | Recent anomalies and alerts |
| `GET /api/correlations` | Cross-deployment correlations |
| `GET /api/cluster/node-efficiency` | Node efficiency analysis |
| **Cost Allocation** | |
| `GET /api/cost/allocation/team` | Costs grouped by team |
| `GET /api/cost/allocation/namespace` | Costs grouped by namespace |
| `GET /api/cost/allocation/project` | Costs grouped by project |
| `GET /api/cost/anomalies` | Detect cost anomalies |
| `GET /api/cost/idle-resources` | Idle/underutilized resources |
| `GET /api/cost/pricing-info` | Auto-detected cloud pricing info |
| **Advanced Reporting** | |
| `GET /api/reports/executive-summary` | Executive summary report |
| `GET /api/reports/team/{team}` | Team-specific report |
| `GET /api/reports/forecast` | Cost forecast (30/60/90 days) |
| `GET /api/reports/roi` | ROI analysis |
| `GET /api/reports/trends` | Trend analysis |

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

### Startup Filter Settings

```yaml
DEPLOYMENT_X_STARTUP_FILTER: "2"  # Minutes to ignore new pods (default: 2)
# Range: 0-60 minutes
# Use higher values (3-5) for Java/JVM apps with slow startup
# Use lower values (0-1) for fast-starting apps like Go/Rust
```

### Cost Settings

```yaml
# Ratio: 1 vCPU : 8 GB memory (typical cloud pricing)
COST_PER_VCPU_HOUR: "0.04"        # $/vCPU/hour
COST_PER_GB_MEMORY_HOUR: "0.005"  # $/GB/hour
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

**Latest Stable Version: v0.0.25** (Recommended for production)

| Version | Date | Changes |
|---------|------|---------|
| v0.0.25 | 2026-01-04 | Advanced Cost Allocation & Reporting, Dashboard Reports tab, 10 new API endpoints |
| v0.0.24-v5 | 2026-01-04 | Fixed Kubernetes client access in node efficiency (IntegratedOperator structure) |
| v0.0.24-v4 | 2026-01-04 | Added metrics.k8s.io RBAC permissions, detailed error logging |
| v0.0.24-v3 | 2026-01-04 | Smart metrics-server auto-discovery (v1beta1/v1), API version caching |
| v0.0.29 | 2026-01-06 | Enhanced FinOps + Real-time integration, 30-day cluster cost history chart, enriched API |
| v0.0.28 | 2026-01-05 | Fixed cost allocation/reporting API routes (404 bug), all endpoints now accessible |
| v0.0.24-v2 | 2026-01-04 | Added custom_api to operator classes, enhanced error messages |
| v0.0.24 | 2026-01-04 | Node Efficiency Dashboard, FinOps Resource Right-Sizing, fast builds with base image |
| v0.0.23 | 2026-01-04 | Professional UI redesign, GenAI integration (pre-release), comprehensive documentation |
| v0.0.22 | 2026-01-03 | HPA Analysis dashboard tab, enhanced alerts (high_memory, low_efficiency, low_confidence), alert types legend |
| v0.0.21 | 2026-01-02 | HPA behavior analysis API, safe scaling recommendations, raised pattern HPA targets (70-80%) |
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
