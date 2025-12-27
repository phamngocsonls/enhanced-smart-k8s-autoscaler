# Smart Kubernetes Autoscaler

🚀 **AI-Powered, Cost-Optimized, Node-Aware HPA Controller with Predictive Scaling**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Kubernetes 1.19+](https://img.shields.io/badge/kubernetes-1.19+-326CE5.svg)](https://kubernetes.io/)
[![Production Ready](https://img.shields.io/badge/production-ready-85%25-green.svg)](PRODUCTION_READINESS.md)

An intelligent Kubernetes autoscaling operator that goes beyond standard HPA by combining real-time node pressure management with historical learning, predictive scaling, anomaly detection, cost optimization, and production-grade reliability features.

---

## 🌟 Why Smart Autoscaler?

Traditional HPA has limitations:
- ❌ Reacts **after** problems occur (too slow)
- ❌ Ignores node capacity (can overwhelm nodes)
- ❌ No learning from history (repeats mistakes)
- ❌ No cost awareness (wastes resources)
- ❌ Manual tuning required (time-consuming)
- ❌ Can't handle Java/JVM startup spikes (false alarms)

**Smart Autoscaler solves all of these:**
- ✅ **Predicts** spikes before they happen
- ✅ **Tracks** node capacity per deployment
- ✅ **Learns** optimal settings automatically
- ✅ **Tracks** and optimizes costs (CPU + Memory)
- ✅ **Self-tunes** based on performance
- ✅ **Filters** startup CPU bursts intelligently
- ✅ **Production-ready** with health checks, retry logic, and OOM prevention

---

## ✨ Key Features

### 🧠 Intelligence Layer

#### 📊 Historical Learning & Pattern Recognition
- Stores 30 days of metrics in SQLite database (WAL mode)
- Identifies daily and weekly patterns
- Learns optimal behavior per deployment
- Confidence-based decision making
- Automatic database cleanup and optimization

#### 🔮 Predictive Pre-Scaling
- Predicts CPU load 1 hour ahead
- Pre-scales **before** traffic spikes
- Uses ensemble ML models (Random Forest, Gradient Boosting, ARIMA, Holt-Winters)
- 75%+ confidence threshold
- Pattern-aware predictions

#### 💰 Advanced Cost Optimization
- **CPU Cost Tracking**: Calculates cost based on CPU requests and utilization
- **Memory Cost Tracking**: Calculates cost based on memory requests and utilization
- **Runtime Hours**: Tracks how long pods have been running
- **Wasted Cost Detection**: Identifies when low utilization but high requests
- **Total Cost**: CPU cost + Memory cost
- **Monthly Projections**: Extrapolates to monthly estimates
- **Optimization Recommendations**: Suggests right-sizing based on actual usage
- Weekly cost reports via webhooks

#### 🚨 Anomaly Detection
Detects 4 types of anomalies:
1. **CPU Spike** - Unusual CPU beyond 3σ
2. **Scaling Thrashing** - Too many adjustments
3. **Persistent High CPU** - Consistently >85%
4. **Pattern Deviation** - Unexpected behavior

#### 🎯 Auto-Tuning & Recommendations
- Learns optimal HPA targets over 7 days
- Finds sweet spot (65-75% utilization)
- Auto-applies when confidence >80%
- Tracks performance per target

### 🛡️ Advanced Protection

#### Node-Aware Scaling
- Monitors worker nodes per deployment's `nodeSelector`
- Prevents scheduling failures
- Tracks only relevant nodes for each workload
- Independent optimization per node pool

#### Startup Spike Filtering
- Filters Java/JVM initialization spikes
- Ignores first N minutes of pod lifecycle (configurable)
- Prevents false alarms during deployment
- Configurable window per deployment

#### Multi-Layer Spike Protection
1. **Smoothed Metrics** - 10m baseline + 5m spike (70/30 blend)
2. **Scheduling Detection** - Identifies recent pod starts
3. **Confidence Scoring** - 0-100% per decision
4. **Cooldown Periods** - 5min minimum between changes
5. **Higher Thresholds** - Accounts for temporary overhead
6. **Low CPU Request Handling** - Automatically adjusts targets for workloads with < 50m CPU requests (uses 85-90% instead of 70% to prevent unstable scaling)
7. **Prediction Validation & Adaptive Learning** - Validates predictions against actual usage, tracks accuracy, and adapts confidence to prevent false scaling

### 🔒 Production Features

#### Health Checks & Monitoring
- **Comprehensive Health Endpoint**: `/api/health` checks all components
- **Kubernetes Probes**: Liveness, readiness, and startup probes
- **Component Checks**: Database, Prometheus, Kubernetes API, Deployments
- **Status Reporting**: Detailed health status with HTTP codes

#### Input Validation
- **Config Validator**: Validates all environment variables
- **Range Checks**: Ensures values are within acceptable ranges
- **Type Validation**: Validates data types
- **Fail-Fast**: Exits immediately on invalid config with clear errors

#### Database Management
- **WAL Mode**: Write-Ahead Logging for better concurrency
- **Automatic Cleanup**: Removes data older than 30 days
- **Vacuum**: Reclaims space when >1000 records deleted
- **Connection Management**: Proper connection closing and context managers
- **Schema Migration**: Automatic migration for new fields

#### Resilience & Reliability
- **Retry Logic**: Exponential backoff (3 attempts: 1s, 2s, 4s)
- **Circuit Breaker**: Opens after 5 failures, auto-resets after 60s
- **Rate Limiting**: 
  - Prometheus queries: 10 queries/second (configurable)
  - Kubernetes API: 20 calls/second (configurable)
- **Safe Defaults**: Continues operating with defaults on failure
- **Graceful Shutdown**: SIGTERM/SIGINT handling with cleanup

#### Memory Management & OOM Prevention
- **Memory Monitoring**: Background thread checks every 30 seconds
- **Automatic Detection**: Reads memory limit from cgroups
- **Warning Threshold**: 75% (configurable)
- **Critical Threshold**: 90% (configurable)
- **Automatic GC**: Forces garbage collection on critical
- **Skip Processing**: Skips deployment processing if memory critical
- **Prometheus Metrics**: Exports memory usage metrics

#### Structured Logging
- **JSON Format**: Structured logs for better aggregation
- **Configurable**: Switch between JSON and text format
- **Context Fields**: Includes component, version, and custom fields
- **Log Levels**: DEBUG, INFO, WARNING, ERROR

### 📢 Integrations

#### Multi-Channel Alerts
- **Slack** - Rich formatted messages
- **Microsoft Teams** - Adaptive cards
- **Discord** - Beautiful embeds
- **Generic Webhooks** - PagerDuty, custom endpoints

#### External Tool Integration
- **PagerDuty** - Incident management
- **Datadog** - Metrics and events
- **Grafana** - Annotations
- **Jira** - Ticket creation
- **ServiceNow** - Incident tracking
- **OpsGenie** - Alert management
- **Elasticsearch** - Structured logging

#### Observability
- **Prometheus Metrics** - 25+ custom metrics (port 8000)
- **Web Dashboard** - Real-time UI (port 5000)
- **Structured Logging** - JSON logs (configurable)
- **Health Endpoints** - Kubernetes probes

### 🤖 Machine Learning

#### ML Models
- **Random Forest** - Feature-based prediction
- **Gradient Boosting** - Advanced regression
- **ARIMA** - Time-series forecasting
- **Holt-Winters** - Seasonal patterns
- **Ensemble** - Weighted average of all models

---

## 📊 How It Works

### Decision Flow
```
Every 60 seconds (configurable):
  │
  ├─> Read deployment manifest
  │   ├─> Get CPU request (e.g., 500m)
  │   ├─> Get Memory request (e.g., 512Mi)
  │   └─> Get nodeSelector (e.g., role=api)
  │
  ├─> Find matching nodes
  │   └─> Filter by labels and readiness
  │
  ├─> Query Prometheus metrics (with rate limiting)
  │   ├─> 10-minute smoothed CPU (stable baseline)
  │   ├─> 5-minute spike CPU (recent activity)
  │   ├─> Memory usage (MB)
  │   └─> Blend: 70% smooth + 30% spike
  │
  ├─> Detect recent pod scheduling
  │   └─> Count pods started <3 minutes ago
  │
  ├─> Calculate confidence score
  │   ├─> Start: 100%
  │   ├─> Scheduling spike: ×0.5 = 50%
  │   └─> Skip if confidence <60%
  │
  ├─> Check cooldown period
  │   └─> Skip if adjusted <5 minutes ago
  │
  ├─> Get ML prediction (if enabled)
  │   ├─> Random Forest
  │   ├─> Gradient Boosting
  │   ├─> ARIMA
  │   └─> Ensemble weighted average
  │
  ├─> Get learned optimal target (if available)
  │   └─> From 7+ days of performance data
  │
  ├─> Calculate recommended HPA target
  │   ├─> Node pressure HIGH → Lower target (50-60%)
  │   ├─> Node pressure LOW → Raise target (75-85%)
  │   └─> Apply prediction + auto-tuning adjustments
  │
  ├─> Apply HPA target (if confidence sufficient)
  │   └─> HPA scales pods automatically
  │
  ├─> Store metrics to database
  │   ├─> CPU request, usage, utilization
  │   ├─> Memory request, usage, utilization
  │   └─> For historical learning
  │
  ├─> Calculate costs
  │   ├─> CPU cost = (CPU requested × cost/hour × runtime hours)
  │   ├─> Memory cost = (Memory requested × cost/hour × runtime hours)
  │   ├─> Wasted cost = (Unused resources × cost × hours)
  │   └─> Monthly projections
  │
  ├─> Detect anomalies
  │   └─> Send alerts if found
  │
  └─> Update Prometheus metrics
      └─> Export all metrics for monitoring
```

---

## 🚀 Quick Start

### Prerequisites
- Kubernetes 1.19+
- Prometheus (with node and pod metrics)
- Python 3.11+ (for local development)

### Installation

#### 1. Clone Repository
```bash
git clone <repository-url>
cd enhanced-smart-k8s-autoscaler
```

#### 2. Build Docker Image
```bash
docker build -f Dockerfile.enhanced -t smart-autoscaler:latest .
```

#### 3. Deploy to Kubernetes
```bash
# Create namespace
kubectl create namespace autoscaler-system

# Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/servicemonitor.yaml
```

#### 4. Configure Deployments
Edit `k8s/configmap.yaml` or set environment variables:
```yaml
# Add deployment configuration
DEPLOYMENT_0_NAMESPACE: "default"
DEPLOYMENT_0_NAME: "my-app"
DEPLOYMENT_0_HPA_NAME: "my-app-hpa"
DEPLOYMENT_0_STARTUP_FILTER: "2"  # minutes
```

#### 5. Verify Deployment
```bash
# Check pod status
kubectl get pods -n autoscaler-system

# Check logs
kubectl logs -f deployment/smart-autoscaler -n autoscaler-system

# Check health
kubectl port-forward svc/smart-autoscaler 5000:5000 -n autoscaler-system
curl http://localhost:5000/api/health
```

---

## ⚙️ Configuration

### Environment Variables

#### Core Configuration
```yaml
PROMETHEUS_URL: "http://prometheus-server.monitoring:9090"
CHECK_INTERVAL: "60"  # seconds (10-3600)
TARGET_NODE_UTILIZATION: "70.0"  # percent (10-95)
DRY_RUN: "false"  # true/false
DB_PATH: "/data/autoscaler.db"
```

#### Feature Flags
```yaml
ENABLE_PREDICTIVE: "true"  # Enable predictive scaling
ENABLE_AUTOTUNING: "true"  # Enable auto-tuning
```

#### Cost Configuration
```yaml
COST_PER_VCPU_HOUR: "0.04"  # $0.04 per vCPU per hour
COST_PER_GB_MEMORY_HOUR: "0.004"  # $0.004 per GB memory per hour
```

#### Logging
```yaml
LOG_LEVEL: "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT: "json"  # json or text
```

#### Rate Limiting
```yaml
PROMETHEUS_RATE_LIMIT: "10"  # Queries per second
K8S_API_RATE_LIMIT: "20"  # API calls per second
```

#### Memory Management
```yaml
MEMORY_WARNING_THRESHOLD: "0.75"  # 75% of limit
MEMORY_CRITICAL_THRESHOLD: "0.90"  # 90% of limit
MEMORY_CHECK_INTERVAL: "30"  # Check every 30 seconds
```

#### Webhooks (Optional)
```yaml
SLACK_WEBHOOK: "https://hooks.slack.com/..."
TEAMS_WEBHOOK: "https://outlook.office.com/..."
DISCORD_WEBHOOK: "https://discord.com/..."
GENERIC_WEBHOOK: "https://your-webhook.com/..."
```

#### Deployment Configuration
```yaml
DEPLOYMENT_0_NAMESPACE: "default"
DEPLOYMENT_0_NAME: "my-app"
DEPLOYMENT_0_HPA_NAME: "my-app-hpa"
DEPLOYMENT_0_STARTUP_FILTER: "2"  # minutes

# Add more deployments
DEPLOYMENT_1_NAMESPACE: "production"
DEPLOYMENT_1_NAME: "api-service"
# ...
```

---

## 📖 Usage Examples

### Basic HPA Setup
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-service-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-service
  minReplicas: 2
  maxReplicas: 50
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70  # Operator adjusts this (50-85%)
```

### Node Selector Example
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
spec:
  template:
    spec:
      nodeSelector:
        role: api
        instance-type: compute-optimized
      containers:
      - name: app
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
```

### Startup Filter Configuration
Different applications need different startup windows:
```yaml
# Python/Node.js (fast startup)
DEPLOYMENT_0_STARTUP_FILTER: "1"

# Java/Spring Boot (medium)
DEPLOYMENT_0_STARTUP_FILTER: "2"

# Java/Quarkus native (very fast)
DEPLOYMENT_0_STARTUP_FILTER: "0.5"
```

### Low CPU Request Handling
For workloads with very low CPU requests (< 50m), the operator automatically uses higher HPA targets (85-90%) to prevent unstable scaling:

**Why?** With 20m request at 70% target:
- Threshold = 14m (very sensitive)
- Small changes (1-2m) = large percentage swings
- **Result**: Unstable scaling/thrashing

**Solution**: Automatic adjustment:
- **< 50m request** → Uses 85-90% target (instead of 70%)
- **50-100m request** → Uses 75-85% target
- **Normal requests** → Uses base target (70%)

**Example**:
```yaml
# Workload with 25m CPU request
# Operator automatically uses 85% target
# Prevents thrashing from small CPU usage changes
```

See [LOW_CPU_REQUEST_HANDLING.md](LOW_CPU_REQUEST_HANDLING.md) for details.

### Prediction Validation & Adaptive Learning
The operator validates predictions by comparing them with actual CPU usage and learns from mistakes:

**Problem**: Prediction suggests scale-up, but actual CPU doesn't increase (false positive)

**Solution**:
- ✅ Validates predictions 1 hour after making them
- ✅ Tracks accuracy, false positives, and false negatives
- ✅ Adapts confidence based on historical accuracy
- ✅ Skips predictions if accuracy < 60% or false positive rate > 40%
- ✅ Self-improves over time

**Example**:
```yaml
# After 50 predictions:
# Accuracy: 75%, False positives: 10%
# Result: ✅ Trust predictions, apply scale-up

# After 50 predictions:
# Accuracy: 45%, False positives: 60%
# Result: ❌ Skip predictions, don't scale
```

See [PREDICTION_VALIDATION.md](PREDICTION_VALIDATION.md) for details.

---

## 📊 Dashboard & API

### Web Dashboard
Access the dashboard at `http://localhost:5000` (via port-forward):
```bash
kubectl port-forward svc/smart-autoscaler 5000:5000 -n autoscaler-system
```

**Features:**
- Real-time deployment metrics
- Cost breakdown (CPU + Memory)
- Wasted cost visualization
- Anomaly detection alerts
- Prediction confidence scores
- Historical trends

### API Endpoints

#### Health Check
```bash
GET /api/health
```
Returns comprehensive health status of all components.

#### Deployment Metrics
```bash
GET /api/deployment/<namespace>/<deployment>
```
Returns current state of a deployment.

#### Cost Metrics
```bash
GET /api/deployment/<namespace>/<deployment>/cost?hours=24
```
Returns detailed cost breakdown:
```json
{
  "cpu_cost": 12.50,
  "memory_cost": 8.30,
  "total_cost": 20.80,
  "wasted_cpu_cost": 4.20,
  "wasted_memory_cost": 2.10,
  "total_wasted_cost": 6.30,
  "cpu_utilization_percent": 45.5,
  "memory_utilization_percent": 62.3,
  "estimated_monthly_cost": 632.50,
  "optimization_potential": 191.50,
  "recommendation": "Moderate waste. Could save $191.50/month"
}
```

#### History
```bash
GET /api/deployment/<namespace>/<deployment>/history?hours=24
```
Returns historical metrics.

#### Predictions
```bash
GET /api/deployment/<namespace>/<deployment>/predictions
```
Returns ML predictions.

#### Anomalies
```bash
GET /api/deployment/<namespace>/<deployment>/anomalies?hours=24
```
Returns detected anomalies.

#### Overview
```bash
GET /api/overview
```
Returns overall statistics.

### Prometheus Metrics
Access metrics at `http://localhost:8000/metrics`:
```bash
kubectl port-forward svc/smart-autoscaler 8000:8000 -n autoscaler-system
```

**Key Metrics:**
- `autoscaler_node_utilization_percent` - Node CPU utilization
- `autoscaler_hpa_target_percent` - Current HPA target
- `autoscaler_pod_count` - Number of pods
- `autoscaler_confidence_score` - Decision confidence
- `autoscaler_predicted_cpu_percent` - Predicted CPU
- `autoscaler_monthly_cost_usd` - Monthly cost estimate
- `autoscaler_wasted_capacity_percent` - Wasted capacity
- `autoscaler_memory_usage_mb` - Memory usage
- `autoscaler_memory_usage_percent` - Memory usage percentage
- `autoscaler_rate_limit_delays_total` - Rate limit delays
- And 15+ more metrics...

---

## 🧪 Testing

### Local Development
```bash
# Install dependencies
pip install -r requirements-enhanced.txt

# Run locally with dry-run
export PROMETHEUS_URL=http://localhost:9090
export DRY_RUN=true
export DEPLOYMENT_0_NAMESPACE=default
export DEPLOYMENT_0_NAME=my-app
python -m src.integrated_operator
```

### Load Testing
```bash
# Generate test load
kubectl run load-generator --image=busybox --restart=Never -- \
  /bin/sh -c "while true; do wget -q -O- http://api-service; done"

# Watch operator response
kubectl logs -f deployment/smart-autoscaler -n autoscaler-system | grep -E "Predicted|confidence|Detected"

# Monitor nodes
watch kubectl top nodes

# Monitor HPA targets
watch kubectl get hpa -A
```

### Verify Predictions
```bash
# Check prediction accuracy after 7 days
kubectl exec deployment/smart-autoscaler -n autoscaler-system -- \
  python -c "
from src.intelligence import TimeSeriesDatabase
db = TimeSeriesDatabase('/data/autoscaler.db')
cursor = db.conn.execute('''
  SELECT AVG(confidence) as avg_confidence,
         COUNT(*) as total_predictions
  FROM predictions
  WHERE timestamp >= datetime('now', '-7 days')
''')
print(cursor.fetchone())
"
```

---

## 🐛 Troubleshooting

### Operator not starting
```bash
# Check logs
kubectl logs deployment/smart-autoscaler -n autoscaler-system

# Common issues:
# 1. PVC not bound
kubectl get pvc -n autoscaler-system

# 2. RBAC permissions
kubectl auth can-i patch hpa --as=system:serviceaccount:autoscaler-system:smart-autoscaler

# 3. Prometheus unreachable
kubectl exec deployment/smart-autoscaler -n autoscaler-system -- \
  curl http://prometheus-server.monitoring:9090/api/v1/query?query=up
```

### No predictions being made
```bash
# Check database size (need 24h+ of data)
kubectl exec deployment/smart-autoscaler -n autoscaler-system -- \
  sqlite3 /data/autoscaler.db "SELECT COUNT(*) FROM metrics_history"

# Should be >1440 (24 hours at 1/minute)
```

### Alerts not sending
```bash
# Verify webhook configuration
kubectl get configmap smart-autoscaler-config -o yaml | grep WEBHOOK

# Test webhook manually
curl -X POST $SLACK_WEBHOOK -d '{"text":"Test"}'
```

### High memory usage
```bash
# Check memory metrics
curl http://localhost:8000/metrics | grep autoscaler_memory

# Check memory limit
kubectl exec deployment/smart-autoscaler -n autoscaler-system -- \
  cat /sys/fs/cgroup/memory.max

# Adjust memory limits in deployment.yaml if needed
```

### Rate limiting issues
```bash
# Check rate limit delays
curl http://localhost:8000/metrics | grep rate_limit_delays

# Adjust limits in configmap if needed
PROMETHEUS_RATE_LIMIT: "20"  # Increase if needed
K8S_API_RATE_LIMIT: "30"     # Increase if needed
```

---

## 📈 Performance & Scalability

### Resource Requirements
- **CPU**: 200m request, 1000m limit
- **Memory**: 512Mi request, 1Gi limit
- **Storage**: 10Gi PVC (for 30 days of metrics)

### Scalability
- Handles 50+ deployments simultaneously
- Processes each deployment every 60 seconds
- Database optimized with WAL mode and indexes
- Rate limiting prevents overwhelming services

### Performance Optimizations
- WAL mode for database concurrency
- Connection pooling for Kubernetes API
- Circuit breakers prevent cascading failures
- Automatic database cleanup prevents growth
- Memory monitoring prevents OOM kills

---

## 🔒 Security

### RBAC
The operator requires minimal permissions:
- Read deployments, pods, nodes
- Read and patch HPAs
- Read ConfigMaps and Secrets

See `k8s/rbac.yaml` for full permissions.

### Best Practices
- Use Secrets for webhook URLs (not ConfigMap)
- Run as non-root user (already configured)
- Network policies (recommended)
- Regular security updates

---

## 📚 Architecture

### Components
```
┌─────────────────────────────────────────┐
│     Enhanced Smart Autoscaler           │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────────┐  ┌──────────────┐   │
│  │   Operator   │  │ Intelligence │   │
│  │   (Base)     │  │   Layer      │   │
│  └──────┬───────┘  └──────┬───────┘   │
│         │                  │            │
│  ┌──────▼──────────────────▼──────┐   │
│  │   Integrated Operator           │   │
│  │   - Process deployments         │   │
│  │   - Store metrics               │   │
│  │   - Detect anomalies            │   │
│  │   - Calculate costs             │   │
│  │   - Make predictions            │   │
│  └──────┬──────────────────┬──────┘   │
│         │                  │            │
│  ┌──────▼──────┐  ┌────────▼───────┐  │
│  │ Prometheus  │  │   Dashboard    │  │
│  │  Exporter   │  │   (Flask)      │  │
│  └─────────────┘  └────────────────┘  │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │   Production Features            │  │
│  │   - Health Checks                │  │
│  │   - Input Validation             │  │
│  │   - Retry Logic                  │  │
│  │   - Rate Limiting                │  │
│  │   - Memory Monitoring            │  │
│  │   - Structured Logging           │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### Data Flow
1. **Collection**: Prometheus metrics → Operator
2. **Processing**: Operator → Intelligence Layer
3. **Storage**: Intelligence Layer → SQLite Database
4. **Analysis**: Database → ML Models → Predictions
5. **Action**: Predictions → HPA Target Adjustment
6. **Observability**: All components → Prometheus + Dashboard

---

## 🗺️ Roadmap

### Completed ✅
- ✅ Core operator functionality
- ✅ Intelligence layer (learning, predictions, anomalies)
- ✅ Cost optimization (CPU + Memory)
- ✅ Health checks and probes
- ✅ Input validation
- ✅ Database cleanup
- ✅ Retry logic and circuit breakers
- ✅ Rate limiting
- ✅ OOM prevention
- ✅ Structured logging

### Planned 🟡
- 🟡 Database backup and archival
- 🟡 Leader election for HA
- 🟡 Query optimization and caching
- 🟡 Hot reload configuration
- 🟡 Enhanced operator metrics

---

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Built with:
- Kubernetes Python Client
- Prometheus API Client
- scikit-learn (ML models)
- Flask (Dashboard)
- SQLite (Time-series storage)

---

## 📞 Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) (if available)
- Review [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) for deployment guidance

---

**Made with ❤️ for Kubernetes operators who want intelligent, cost-aware autoscaling**
