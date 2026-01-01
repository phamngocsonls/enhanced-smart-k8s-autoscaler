# Quick Reference Guide

## Version 0.0.11

### 🚀 Quick Start

```bash
# Deploy to Kubernetes
kubectl apply -f k8s/

# Port forward dashboard
kubectl port-forward -n autoscaler-system svc/smart-autoscaler 5000:5000

# Access dashboard
open http://localhost:5000
```

### 🎯 Priority Configuration

```bash
# Environment variables
DEPLOYMENT_0_PRIORITY=critical  # payment, auth
DEPLOYMENT_1_PRIORITY=high      # api, gateway
DEPLOYMENT_2_PRIORITY=medium    # standard (default)
DEPLOYMENT_3_PRIORITY=low       # workers, jobs
DEPLOYMENT_4_PRIORITY=best_effort  # analytics, reports
```

### 🖥️ Dashboard Tabs

| Tab | Description | Key Metrics |
|-----|-------------|-------------|
| 📊 Deployments | Watched deployments | CPU, Memory, Pods, HPA, Priority, Pattern |
| 🖥️ Cluster | Cluster monitoring | Nodes, CPU, Memory, Health |
| 🧠 AI Insights | AI analysis | Efficiency, Tuning, Accuracy, Patterns |
| 📈 Timeline | Scaling events | Scale up/down events, HPA changes |
| 💰 Costs | Cost analysis | Hourly costs, waste, trends |
| 🔮 Predictions | AI predictions | Predicted CPU, confidence, accuracy |
| ⚙️ Config | Configuration | Hot reload, version, settings |

### 📊 Cluster Metrics

#### CPU Dashboard
- **Capacity**: Total CPU cores available
- **Allocatable**: CPU available for scheduling
- **Requests**: Sum of pod CPU requests
- **Usage**: Actual CPU usage
- **Thresholds**: >70% warning, >85% critical

#### Memory Dashboard
- **Capacity**: Total memory (GB) available
- **Allocatable**: Memory available for scheduling
- **Requests**: Sum of pod memory requests
- **Usage**: Actual memory usage
- **Thresholds**: >70% warning, >85% critical

### 🎨 Color Coding

| Color | Status | Threshold | Action |
|-------|--------|-----------|--------|
| 🟢 Green | Healthy | < 70% | Normal |
| 🟡 Yellow | Warning | 70-85% | Monitor |
| 🔴 Red | Critical | > 85% | Act now |

### 🔧 API Endpoints

```bash
# Deployments
GET /api/deployments
GET /api/deployment/{ns}/{name}/current
GET /api/deployment/{ns}/{name}/history?hours=24

# Cluster
GET /api/cluster/metrics
GET /api/cluster/history?hours=24

# Priority
GET /api/priorities/stats

# AI
GET /api/ai/insights/{deployment}
GET /api/scaling/timeline/{deployment}
GET /api/cost/trends/{deployment}

# Health
GET /health
GET /api/health

# Config
GET /api/config/status
POST /api/config/reload
```

### 📈 Prometheus Queries

```promql
# Node metrics
kube_node_status_capacity{resource="cpu"}
kube_node_status_allocatable{resource="cpu"}
node_cpu_seconds_total{mode!="idle"}

# Pod metrics
kube_pod_container_resource_requests{resource="cpu"}
container_cpu_usage_seconds_total
container_memory_working_set_bytes

# Cluster totals
sum(kube_pod_container_resource_requests{resource="cpu"})
sum(rate(container_cpu_usage_seconds_total[5m]))
```

### 🎯 Priority Levels

| Priority | HPA Target | Scale Up | Scale Down | Use Case |
|----------|------------|----------|------------|----------|
| critical | 55% | 2x faster | 4x slower | Payment, Auth |
| high | 60% | 1.5x faster | 2x slower | APIs, Gateways |
| medium | 70% | Normal | Normal | Standard (default) |
| low | 80% | 2x slower | 2x faster | Workers, Jobs |
| best_effort | 85% | 4x slower | 3x faster | Analytics, Reports |

### 🔍 Namespace Filter

```javascript
// Select namespace from dropdown
document.getElementById('namespace-filter').value = 'production';

// Filter applies to all tabs
// Select "All Namespaces" to reset
```

### 📝 Configuration Files

```bash
# Kubernetes
k8s/configmap.yaml      # Configuration
k8s/deployment.yaml     # Deployment
k8s/rbac.yaml          # Permissions

# Helm
helm/smart-autoscaler/values.yaml  # Helm values

# Environment
.env.example           # Environment variables template
```

### 🧪 Testing

```bash
# Run all tests
./run_tests.sh

# Run specific tests
python3.12 -m pytest tests/test_priority_manager.py -v

# Run priority demo
python3 examples/priority-demo.py
```

### 📚 Documentation

```bash
# Feature guides
PRIORITY_FEATURE.md              # Priority-based scaling
docs/CLUSTER_MONITORING.md       # Cluster monitoring
docs/HPA-ANTI-FLAPPING.md       # HPA configuration

# Changelogs
changelogs/CHANGELOG_v0.0.11.md  # Latest changes
changelogs/CHANGELOG_v0.0.10.md  # Priority feature

# Main docs
README.md                        # Complete overview
FEATURES_SUMMARY.md              # Features summary
QUICKSTART.md                    # Quick start
```

### 🔧 Troubleshooting

#### No Cluster Metrics
```bash
# Check Prometheus
kubectl port-forward -n monitoring svc/prometheus-server 9090:9090

# Check kube-state-metrics
kubectl get pods -n kube-system | grep kube-state-metrics

# Check node-exporter
kubectl get pods -n kube-system | grep node-exporter
```

#### Priority Not Applied
```bash
# Check logs
kubectl logs -n autoscaler-system <pod> | grep priority

# Verify config
kubectl get configmap -n autoscaler-system smart-autoscaler-config -o yaml
```

#### Dashboard Not Loading
```bash
# Check pod status
kubectl get pods -n autoscaler-system

# Check logs
kubectl logs -n autoscaler-system <pod>

# Port forward
kubectl port-forward -n autoscaler-system svc/smart-autoscaler 5000:5000
```

### 💡 Best Practices

1. **Priority**: Start with medium, adjust based on criticality
2. **Monitoring**: Check cluster tab daily
3. **Capacity**: Maintain 20-30% headroom
4. **Costs**: Review weekly, optimize monthly
5. **Namespace**: Use filter for multi-tenant clusters

### 🎯 Common Tasks

#### Add New Deployment
```bash
# Add to ConfigMap
DEPLOYMENT_X_NAMESPACE: "production"
DEPLOYMENT_X_NAME: "new-app"
DEPLOYMENT_X_HPA_NAME: "new-app-hpa"
DEPLOYMENT_X_PRIORITY: "high"

# Reload config
curl -X POST http://localhost:5000/api/config/reload
```

#### Change Priority
```bash
# Update ConfigMap
kubectl edit configmap -n autoscaler-system smart-autoscaler-config

# Or update environment variable
DEPLOYMENT_0_PRIORITY=critical

# Config reloads automatically
```

#### View Cluster Health
```bash
# Open dashboard
open http://localhost:5000

# Click "Cluster" tab
# Check summary cards and progress bars
```

#### Filter by Namespace
```bash
# Select namespace from dropdown at top
# Filter applies to all tabs
# Select "All Namespaces" to reset
```

### 📊 Metrics Thresholds

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| CPU Usage % | 70% | 85% | Scale up or add nodes |
| Memory Usage % | 70% | 85% | Scale up or add nodes |
| CPU Request % | 80% | 90% | Add nodes |
| Memory Request % | 80% | 90% | Add nodes |
| Cluster Health | Yellow | Red | Investigate immediately |

### 🔄 Auto-Refresh

- Dashboard refreshes every 30 seconds
- Countdown shown in navbar
- Click "🔄 Refresh" to update immediately
- Cluster metrics load on tab activation

### 📱 Responsive Design

- Desktop: Full grid layout
- Tablet: 2-column layout
- Mobile: Single column layout
- All features accessible on all devices

### 🎨 Visual Indicators

- **Progress Bars**: Show utilization with color coding
- **Badges**: Priority, pattern, status indicators
- **Charts**: Historical trends with Chart.js
- **Cards**: Summary metrics with icons

### 🔐 Security

- RBAC with minimal permissions
- Read-only Prometheus access
- Service account: `smart-autoscaler`
- No secrets in ConfigMap

### 📦 Dependencies

```bash
# Python packages
pip install kubernetes prometheus-api-client flask flask-cors scikit-learn statsmodels

# Kubernetes components
- Prometheus with kube-state-metrics
- node-exporter
- cAdvisor (built into kubelet)
- metrics-server
```

### 🚀 Deployment Checklist

- [ ] Prometheus installed and accessible
- [ ] kube-state-metrics running
- [ ] node-exporter running
- [ ] metrics-server running
- [ ] RBAC configured
- [ ] ConfigMap created
- [ ] PVC created (for database)
- [ ] Deployment created
- [ ] Service created
- [ ] Port forward or Ingress configured
- [ ] Dashboard accessible
- [ ] Cluster tab showing metrics
- [ ] Namespace filter populated

### 📞 Support

- **Logs**: `kubectl logs -n autoscaler-system <pod>`
- **Docs**: See `/docs` directory
- **Examples**: See `/examples` directory
- **Issues**: GitHub Issues

---

## Quick Commands

```bash
# Deploy
kubectl apply -f k8s/

# Access
kubectl port-forward -n autoscaler-system svc/smart-autoscaler 5000:5000

# Logs
kubectl logs -n autoscaler-system -l app=smart-autoscaler -f

# Config
kubectl edit configmap -n autoscaler-system smart-autoscaler-config

# Reload
curl -X POST http://localhost:5000/api/config/reload

# Test
./run_tests.sh

# Demo
python3 examples/priority-demo.py
```
