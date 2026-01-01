# Smart Kubernetes Autoscaler

🚀 **AI-Powered, Cost-Optimized, Node-Aware HPA Controller with Predictive Scaling**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Kubernetes 1.19+](https://img.shields.io/badge/kubernetes-1.19+-326CE5.svg)](https://kubernetes.io/)
[![Production Ready](https://img.shields.io/badge/production-ready-95%25-green.svg)](PRODUCTION_READINESS.md)
[![Version](https://img.shields.io/badge/version-0.0.6-blue.svg)](CHANGELOG.md)

An intelligent Kubernetes autoscaling operator that goes beyond standard HPA by combining real-time node pressure management with historical learning, predictive scaling, anomaly detection, cost optimization, workload pattern detection, and production-grade reliability features.

---

## 🌟 Why Smart Autoscaler?

Traditional HPA has limitations:
- ❌ Reacts **after** problems occur (too slow)
- ❌ Ignores node capacity (can overwhelm nodes)
- ❌ No learning from history (repeats mistakes)
- ❌ No cost awareness (wastes resources)
- ❌ Manual tuning required (time-consuming)
- ❌ Can't handle Java/JVM startup spikes (false alarms)
- ❌ Conflicts with GitOps tools like ArgoCD

**Smart Autoscaler solves all of these:**
- ✅ **Predicts** spikes before they happen
- ✅ **Tracks** node capacity per deployment
- ✅ **Learns** optimal settings automatically
- ✅ **Tracks** and optimizes costs (CPU + Memory)
- ✅ **Self-tunes** based on performance
- ✅ **Filters** startup CPU bursts intelligently
- ✅ **Production-ready** with health checks, retry logic, and OOM prevention
- ✅ **ArgoCD compatible** with proper ignore annotations

---

## ✨ Key Features

### 🧠 Intelligence Layer

#### 📊 Historical Learning & Pattern Recognition
- Stores 30 days of metrics in SQLite database (WAL mode)
- Identifies daily and weekly patterns
- Learns optimal behavior per deployment
- Confidence-based decision making
- Automatic database cleanup and optimization
- **NEW: Workload Pattern Detection** - Automatically detects 5 pattern types:
  - **Steady**: Consistent load with low variance
  - **Bursty**: Frequent spikes requiring aggressive scaling
  - **Periodic**: Daily/weekly cycles (enables predictive scaling)
  - **Growing**: Upward trend (maintains headroom)
  - **Declining**: Downward trend (optimizes for cost)

#### 🔮 Predictive Pre-Scaling
- Predicts CPU load 1 hour ahead
- Pre-scales **before** traffic spikes
- Uses ensemble ML models (Random Forest, Gradient Boosting, ARIMA, Holt-Winters)
- 75%+ confidence threshold
- Pattern-aware predictions
- **Adaptive to workload patterns** - Enabled automatically for periodic workloads

#### 💰 Advanced Cost Optimization
- **CPU Cost Tracking**: Calculates cost based on CPU requests and utilization
- **Memory Cost Tracking**: Calculates cost based on memory requests and utilization
- **Runtime Hours**: Tracks how long pods have been running
- **Wasted Cost Detection**: Identifies when low utilization but high requests
- **Total Cost**: CPU cost + Memory cost
- **Monthly Projections**: Extrapolates to monthly estimates
- **Optimization Recommendations**: Suggests right-sizing based on actual usage
- **FinOps Recommendation System**: Intelligent resource optimization with adjusted HPA targets
  - Analyzes 1 week of historical data (P95 + 20% buffer)
  - Calculates optimized CPU and memory requests
  - **Automatically adjusts HPA targets** to maintain same scaling behavior
  - Shows monthly cost savings potential
  - Provides implementation YAML snippets
  - Prevents scaling issues when reducing requests
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
- **NEW: Adaptive Learning Rate**:
  - Adjusts learning speed based on workload stability
  - Faster learning (up to 0.3) for stable workloads
  - Slower learning (down to 0.05) for unstable workloads
  - Tracks variance over 20-sample window
  - Self-optimizing based on performance

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

#### Hot Reload Configuration
- **Zero Downtime Updates**: Change configuration without restarting
- **ConfigMap Watch**: Automatically detects ConfigMap changes
- **Dynamic Deployment Management**: Add/remove deployments on the fly
- **Feature Toggles**: Enable/disable features instantly
- **API Control**: Manual reload via REST API (`POST /api/config/reload`)
- **Audit Trail**: All changes logged and alerted
- **Safe Rollback**: Invalid config rejected automatically

#### Degraded Mode & Resilience
- **Degraded Mode**: Continues operating when Prometheus temporarily unavailable
- **Metrics Caching**: 5-minute TTL for last known good metrics
- **Safe Defaults**: Falls back to safe values when no cached data
- **Service Health Tracking**: Monitors Prometheus, Kubernetes API, Database
- **Automatic Recovery**: Seamlessly returns to normal when services recover
- **Circuit Breakers**: Prevents cascading failures

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
- **Health Checks**: Automatic reconnection on failure

#### Resilience & Reliability
- **Retry Logic**: Exponential backoff (3 attempts: 1s, 2s, 4s)
- **Circuit Breaker**: Opens after 5 failures, auto-resets after 60s
- **Rate Limiting**: 
  - Prometheus queries: 10 queries/second (configurable)
  - Kubernetes API: 20 calls/second (configurable)
  - Smart backoff with jitter to prevent thundering herd
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

### Installation

#### Using Pre-built Image (GitHub Container Registry)
```bash
# Pull the latest image (automatically selects correct architecture)
docker pull ghcr.io/<your-org>/enhanced-smart-k8s-autoscaler:latest

# Or use a specific version
docker pull ghcr.io/<your-org>/enhanced-smart-k8s-autoscaler:v0.0.1

# Note: Images are built for both linux/amd64 and linux/arm64
# Docker will automatically pull the correct architecture for your system
# (Apple Silicon Macs will get arm64, Intel Macs/Linux servers get amd64)
```

#### Building from Source
```bash
# Build Docker image
docker build -f Dockerfile.enhanced -t smart-autoscaler:latest .
```
- Python 3.12+ (for local development)

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

#### 6. ArgoCD Integration (If Using GitOps)

If you're using ArgoCD, add ignore annotations to prevent sync conflicts:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-app-hpa
  annotations:
    # Tell ArgoCD to ignore HPA target changes made by Smart Autoscaler
    argocd.argoproj.io/compare-options: IgnoreExtraneous
spec:
  # ... HPA spec ...
```

**Why?** Smart Autoscaler dynamically adjusts HPA targets based on learning. Without ignore annotations, ArgoCD will revert these changes, creating a sync loop.

📖 **See [ArgoCD Integration Guide](docs/ARGOCD_INTEGRATION.md) for complete setup**

---

## ⚙️ Configuration

### Environment Variables

#### Core Configuration
```yaml
PROMETHEUS_URL: "http://prometheus-server.monitoring:9090"
CHECK_INTERVAL: "60"  # seconds (10-3600)
TARGET_NODE_UTILIZATION: "40.0"  # percent (10-95)
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
DEPLOYMENT_0_PRIORITY: "medium"  # critical, high, medium, low, best_effort

# Add more deployments
DEPLOYMENT_1_NAMESPACE: "production"
DEPLOYMENT_1_NAME: "api-service"
DEPLOYMENT_1_PRIORITY: "high"  # High-priority service
# ...
```

#### 🎯 Priority-Based Scaling

Smart Autoscaler supports **5 priority levels** to protect critical services during resource pressure:

| Priority | Use Case | Behavior | HPA Target Adjustment | Scale Speed |
|----------|----------|----------|----------------------|-------------|
| **critical** | Payment, Auth, Billing | Maximum headroom, never preempted | -15% (55% target) | 2x faster up, 4x slower down |
| **high** | APIs, Gateways, Frontend | More headroom, protected | -10% (60% target) | 1.5x faster up, 2x slower down |
| **medium** | Standard workloads | Balanced (default) | 0% (70% target) | Normal speed |
| **low** | Background jobs, Workers | Cost-optimized | +10% (80% target) | 2x slower up, 2x faster down |
| **best_effort** | Reports, Analytics, Cleanup | Maximum cost savings | +15% (85% target) | 4x slower up, 3x faster down |

**Smart Features:**
- **Auto-Detection**: Automatically detects priority from deployment name patterns (payment, auth, api, worker, etc.)
- **Pressure-Aware**: Adjusts targets based on cluster pressure (>85% = aggressive, <40% = optimize costs)
- **Preemptive Scaling**: High-priority can trigger scale-down of low-priority during pressure
- **Processing Order**: Processes high-priority deployments first
- **Cooldown Protection**: 5-minute cooldown between preemptions

**Configuration:**
```yaml
# Explicit priority
DEPLOYMENT_0_PRIORITY: "critical"

# Or use labels (auto-detected)
metadata:
  labels:
    priority: "high"
    workload-priority: "critical"
  annotations:
    autoscaler.k8s.io/priority: "high"
```

**Example Scenarios:**
```yaml
# Payment service - never compromised
DEPLOYMENT_0_NAME: "payment-service"
DEPLOYMENT_0_PRIORITY: "critical"  # Gets 55% HPA target, scales up 2x faster

# API gateway - important but flexible
DEPLOYMENT_1_NAME: "api-gateway"
DEPLOYMENT_1_PRIORITY: "high"  # Gets 60% HPA target

# Background worker - cost-optimized
DEPLOYMENT_2_NAME: "email-worker"
DEPLOYMENT_2_PRIORITY: "low"  # Gets 80% HPA target, can be preempted

# Analytics job - best effort
DEPLOYMENT_3_NAME: "analytics-report"
DEPLOYMENT_3_PRIORITY: "best_effort"  # Gets 85% HPA target, maximum cost savings
```

**Dashboard Display:**
- Priority badges with color coding (critical=red, high=orange, medium=green, low=blue)
- Priority statistics showing deployment count per level
- Real-time pressure indicators

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

### Production HPA with Anti-Flapping (RECOMMENDED)

**Problem**: Default K8s HPA can cause "flapping" - rapid scale up/down cycles that waste resources and cause instability.

**Solution**: Use HPA `behavior` field to control scaling speed:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-service-hpa
  namespace: production
  labels:
    managed-by: smart-autoscaler
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-service
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  
  # CRITICAL: Anti-flapping behavior
  behavior:
    scaleDown:
      # Wait 5 minutes before scaling down (prevents flapping)
      stabilizationWindowSeconds: 300
      policies:
      - type: Pods
        value: 1
        periodSeconds: 60      # Max 1 pod per minute
      - type: Percent
        value: 10
        periodSeconds: 60      # Max 10% per minute
      selectPolicy: Min        # Use least aggressive
    
    scaleUp:
      # React quickly to load (0 = immediate)
      stabilizationWindowSeconds: 0
      policies:
      - type: Pods
        value: 4
        periodSeconds: 15      # Max 4 pods per 15 seconds
      - type: Percent
        value: 100
        periodSeconds: 15      # Max double per 15 seconds
      selectPolicy: Max        # Use most aggressive
```

**Key Settings:**
- `stabilizationWindowSeconds` - How long to wait before acting
  - Scale Down: 300s (5 min) - Be conservative
  - Scale Up: 0s - React fast to load
- `policies` - Control HOW MUCH to scale
  - Pods: Absolute pod count limit
  - Percent: Percentage of current pods
- `selectPolicy` - Which policy to use
  - Min: Slowest (for scale down)
  - Max: Fastest (for scale up)

**Templates Available:**
- `examples/hpa-production.yaml` - Production-ready templates
- `docs/HPA-ANTI-FLAPPING.md` - Detailed guide

**Workload-Specific Recommendations:**

| Workload Type | Scale Down Window | Scale Up Window | Notes |
|---------------|-------------------|-----------------|-------|
| **Stable APIs** | 600s (10 min) | 60s (1 min) | Very conservative |
| **Bursty Jobs** | 180s (3 min) | 0s (immediate) | Fast scale up |
| **Cost-Sensitive** | 180s (3 min) | 30s | Faster scale down |
| **Production Default** | 300s (5 min) | 0s | Balanced |

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

#### FinOps Recommendations (NEW!)
```bash
GET /api/deployment/<namespace>/<deployment>/recommendations?hours=168
```
Returns intelligent resource optimization recommendations with adjusted HPA targets:
```json
{
  "current": {
    "cpu_request_millicores": 1000,
    "hpa_target_percent": 70,
    "scaling_threshold_millicores": 700,
    "monthly_cost_usd": 87.60
  },
  "recommended": {
    "cpu_request_millicores": 696,
    "hpa_target_percent": 101,
    "scaling_threshold_millicores": 700,
    "monthly_cost_usd": 61.32
  },
  "savings": {
    "monthly_savings_usd": 26.28,
    "savings_percent": 30.0
  },
  "implementation": {
    "step1": "Update Deployment: Set CPU request to 696m",
    "step2": "Update HPA: Set target utilization to 101%",
    "yaml_snippet": "..."
  }
}
```

**Key Feature**: Automatically calculates adjusted HPA targets to maintain the same scaling behavior when reducing resource requests. This prevents the common issue where reducing CPU requests causes pods to scale too early.

See [FINOPS_RECOMMENDATIONS.md](FINOPS_RECOMMENDATIONS.md) for detailed guide.

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
