# Smart Autoscaler Documentation

**Version 0.0.38** | [GitHub](https://github.com/phamngocsonls/enhanced-smart-k8s-autoscaler) | [Quick Start](../QUICKSTART.md)

---

## 🚀 Getting Started

New to Smart Autoscaler? Start here:

| Guide | Time | Description |
|-------|------|-------------|
| [Quick Start](../QUICKSTART.md) | 5 min | Get running fast |
| [Getting Started](../GETTING_STARTED.md) | 10 min | Detailed setup |
| [Configuration Reference](../QUICK_REFERENCE.md) | - | All settings |

---

## 📚 Core Features

### AI & Predictions
- [**Predictive Scaling**](PREDICTIVE_SCALING.md) - Scale before spikes happen
- [**ML Prediction Guide**](ML_PREDICTION_GUIDE.md) - Deep dive into 7 ML models
- [**Autopilot Mode**](AUTOPILOT.md) - Fully autonomous operation

### Cost Optimization
- [**Cost Optimization**](COST_OPTIMIZATION.md) - Reduce costs 30-50%
- [**Node Efficiency**](NODE_EFFICIENCY.md) - Cluster-wide optimization

### Installation & Setup
- [**Helm Guide**](HELM_GUIDE.md) - Complete Helm installation
- [**Auto-Discovery**](AUTO_DISCOVERY.md) - Zero-config deployment monitoring
- [**Mimir Integration**](MIMIR_INTEGRATION.md) - Multi-tenancy support (v0.0.38)

### Advanced Configuration
- [**Feature Coordination**](FEATURE_COORDINATION.md) - How features work together
- [**Advanced Configuration**](ADVANCED_CONFIGURATION.md) - Startup filters, anti-flapping, scaling
- [**Architecture**](ARCHITECTURE.md) - System design & data flow

### Integrations
- [**ArgoCD Integration**](ARGOCD_INTEGRATION.md) - GitOps compatibility
- [**Cluster Monitoring**](CLUSTER_MONITORING.md) - Real-time cluster metrics
- [**RBAC & Metrics Server**](RBAC_METRICS_SERVER.md) - Permissions setup

---

## 🎯 By Use Case

### Fintech & Trading
- [Predictive Scaling](PREDICTIVE_SCALING.md) - Pre-scale for market open
- [Priority-Based Scaling](FEATURES.md#priority-based-scaling) - Critical services first

### E-Commerce
- [Cost Optimization](COST_OPTIMIZATION.md) - Handle flash sales efficiently
- [Auto-Discovery](AUTO_DISCOVERY.md) - Manage hundreds of services

### SaaS & Multi-Tenant
- [Mimir Integration](MIMIR_INTEGRATION.md) - Per-tenant isolation
- [Cost Allocation](COST_OPTIMIZATION.md#cost-allocation) - Chargeback & showback

### Enterprise
- [Autopilot Mode](AUTOPILOT.md) - Reduce ops workload 80%
- [Feature Coordination](FEATURE_COORDINATION.md) - Enterprise-grade reliability

---

## 📖 Complete Feature List

[**→ View All Features**](FEATURES.md)

Comprehensive list of all capabilities with examples and business impact.

---

## 🔧 Configuration

| Topic | Document |
|-------|----------|
| All Settings | [Configuration Reference](../QUICK_REFERENCE.md) |
| Helm Values | [Helm Guide](HELM_GUIDE.md) |
| Large Deployments | [Advanced Configuration](ADVANCED_CONFIGURATION.md#scaling-large-deployments) |
| Startup Filters | [Advanced Configuration](ADVANCED_CONFIGURATION.md#startup-filter) |
| Anti-Flapping | [Advanced Configuration](ADVANCED_CONFIGURATION.md#hpa-anti-flapping) |

---

## 🆕 What's New in v0.0.38

- **Grafana Mimir Support**: Multi-tenant metrics with X-Scope-OrgID
- **Multiple Auth Methods**: Basic Auth, Bearer Token, Custom Headers
- **Fallback Compatibility**: Works with standard Prometheus
- **Health Monitoring**: Per-tenant health checks

[View Changelog](../changelogs/CHANGELOG_v0.0.38.md)

---

## 💡 Quick Links

- [GitHub Repository](https://github.com/phamngocsonls/enhanced-smart-k8s-autoscaler)
- [Report Issues](https://github.com/phamngocsonls/enhanced-smart-k8s-autoscaler/issues)
- [Release Notes](../changelogs/)
- [License](../LICENSE)

---

**Need help?** Check the [Quick Start](../QUICKSTART.md) or [report an issue](https://github.com/phamngocsonls/enhanced-smart-k8s-autoscaler/issues).
