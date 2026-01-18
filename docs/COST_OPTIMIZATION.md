# Cost Optimization Guide

**Reduce Kubernetes costs by 30-50% with Smart Autoscaler**

---

## 💰 **Overview**

Smart Autoscaler provides enterprise-grade FinOps capabilities:
- **Auto-Pricing Detection**: Automatically uses GCP/AWS/Azure instance pricing
- **Resource Right-Sizing**: Analyze P95 usage and recommend optimal requests
- **Waste Detection**: Find idle and underutilized resources
- **Cost Allocation**: Team/project/namespace chargeback
- **Forecasting**: Predict future costs with ML

---

## 🎯 **Quick Wins**

### 1. Enable Cost Tracking
```yaml
# helm values.yaml
config:
  costPerVcpuHour: 0.04      # Auto-detected for GCP/AWS/Azure
  costPerGbMemoryHour: 0.005  # Or set manually
```

### 2. Get Recommendations
```bash
# View all optimization opportunities
curl http://localhost:5000/api/finops/recommendations | jq

# Example output:
{
  "total_monthly_savings": "$18,450",
  "recommendations": [
    {
      "deployment": "web-frontend",
      "current_cost": "$1,200/month",
      "optimized_cost": "$720/month",
      "savings": "$480/month (40%)",
      "action": "Reduce CPU request from 500m to 300m"
    }
  ]
}
```

### 3. View Cost Allocation
```bash
# Costs by team
curl http://localhost:5000/api/cost-allocation/by-team | jq

# Costs by namespace
curl http://localhost:5000/api/cost-allocation/by-namespace | jq
```

---

## 📊 **Cost Features**

### Resource Right-Sizing
**Automatically calculate optimal CPU/memory requests**

- **P95 Analysis**: Uses 95th percentile of actual usage
- **Safety Buffer**: Adds 20% + 100m CPU / 50MB memory
- **No Limits**: Avoids OOM kills and CPU throttling
- **HPA Adjustment**: Maintains scaling behavior

```json
{
  "deployment": "api-server",
  "current": {
    "cpu_request": "500m",
    "memory_request": "512Mi",
    "monthly_cost": "$1,200"
  },
  "recommended": {
    "cpu_request": "300m",
    "memory_request": "384Mi",
    "monthly_cost": "$720"
  },
  "savings": {
    "monthly": "$480",
    "annual": "$5,760",
    "percentage": "40%"
  }
}
```

### Cost Allocation
**Track costs by team, project, namespace**

Automatically allocates costs based on Kubernetes labels:
- `team`: Team ownership
- `project`: Project/product
- `environment`: prod, staging, dev
- `cost-center`: Finance cost center

```yaml
# Add labels to your deployments
metadata:
  labels:
    team: "platform"
    project: "api-gateway"
    environment: "production"
    cost-center: "engineering"
```

### Waste Detection
**Find resources burning money**

- **Idle Resources**: <10% CPU/memory usage
- **Underutilized**: <30% usage
- **Over-Provisioned**: Request >> actual usage
- **Zombie Pods**: Not receiving traffic

```json
{
  "idle_deployments": [
    {
      "deployment": "old-api",
      "cpu_usage": "5%",
      "monthly_waste": "$850",
      "recommendation": "Scale down or delete"
    }
  ],
  "total_monthly_waste": "$12,400"
}
```

### Cost Forecasting
**Predict future costs with ML**

- **30/60/90-day forecasts**: Linear regression
- **Trend Analysis**: Week-over-week, month-over-month
- **Anomaly Detection**: Unusual cost spikes
- **Budget Alerts**: Notify when approaching limits

```json
{
  "current_monthly": "$45,000",
  "forecast_30d": "$47,200",
  "forecast_60d": "$49,800",
  "forecast_90d": "$52,100",
  "trend": "increasing",
  "growth_rate": "4.8%/month"
}
```

---

## 🏢 **Enterprise Features**

### Chargeback & Showback
**Automated billing for internal teams**

```bash
# Generate team report
curl http://localhost:5000/api/reports/team/platform | jq

# Output:
{
  "team": "platform",
  "period": "2026-01",
  "total_cost": "$12,450",
  "breakdown": {
    "compute": "$8,200",
    "memory": "$4,250"
  },
  "top_deployments": [
    {"name": "api-gateway", "cost": "$3,200"},
    {"name": "auth-service", "cost": "$2,100"}
  ],
  "trend": "+12% vs last month"
}
```

### Executive Reports
**High-level summaries for leadership**

```bash
curl http://localhost:5000/api/reports/executive | jq

# Output:
{
  "period": "2026-01",
  "total_cost": "$45,000",
  "vs_last_month": "+8%",
  "optimization_potential": "$18,000 (40%)",
  "top_cost_drivers": [
    {"team": "ml-platform", "cost": "$15,200"},
    {"team": "api-services", "cost": "$12,800"}
  ],
  "recommendations": [
    "Right-size ml-platform deployments: $6,200/month savings",
    "Delete 12 idle deployments: $3,400/month savings"
  ]
}
```

### Budget Controls
**Prevent cost overruns**

```yaml
# Set budget alerts
budgets:
  - team: "platform"
    monthly_limit: 15000
    alert_threshold: 0.80  # Alert at 80%
    webhook: "https://slack.com/webhook"
  
  - namespace: "production"
    monthly_limit: 50000
    alert_threshold: 0.90
```

---

## 📈 **Real-World Savings**

### E-Commerce Platform
**Before Smart Autoscaler:**
- Monthly cost: $68,000
- Over-provisioned: 45%
- Idle resources: $12,000/month waste

**After Smart Autoscaler:**
- Monthly cost: $42,000
- Over-provisioned: 8%
- Idle resources: $800/month

**Result**: $26,000/month savings (38%) = **$312,000/year**

### SaaS Company
**Before:**
- 200 microservices
- Manual capacity planning
- No cost visibility

**After:**
- Automatic right-sizing
- Per-team cost allocation
- Continuous optimization

**Result**: $18,000/month savings (32%) = **$216,000/year**

### Fintech Startup
**Before:**
- Trading hours: over-provisioned
- Off-hours: still running full capacity
- No cost tracking

**After:**
- Predictive scaling for trading hours
- Automatic scale-down off-hours
- Real-time cost monitoring

**Result**: $22,000/month savings (41%) = **$264,000/year**

---

## 🎯 **Best Practices**

### 1. Start with Visibility
```bash
# Understand current costs
curl /api/cost-allocation/summary

# Find biggest opportunities
curl /api/finops/recommendations | jq '.[] | select(.savings_percentage > 30)'
```

### 2. Implement Gradually
1. **Week 1**: Enable cost tracking, gather data
2. **Week 2**: Review recommendations, test on dev/staging
3. **Week 3**: Apply to non-critical production services
4. **Week 4**: Roll out to all services

### 3. Monitor Impact
```bash
# Track savings over time
curl /api/reports/savings-history

# Verify no performance degradation
curl /api/deployment/{namespace}/{name}/health
```

### 4. Automate with Autopilot
```yaml
autopilot:
  enabled: true
  level: "autopilot"
  cost_optimization:
    enabled: true
    max_reduction: 0.30  # Max 30% reduction per change
    require_approval_above: 0.20  # Approve if >20% change
```

---

## 🔧 **Configuration**

### Basic Setup
```yaml
config:
  # Pricing (auto-detected for GCP/AWS/Azure)
  costPerVcpuHour: 0.04
  costPerGbMemoryHour: 0.005
  
  # Right-sizing
  rightSizing:
    enabled: true
    percentile: 95  # Use P95 usage
    cpuBuffer: 0.20  # 20% safety buffer
    memoryBuffer: 0.20
    minCpuRequest: 100  # Minimum 100m for HPA
  
  # Waste detection
  wasteDetection:
    enabled: true
    idleThreshold: 0.10  # <10% usage = idle
    underutilizedThreshold: 0.30  # <30% = underutilized
```

### Advanced Setup
```yaml
config:
  # Cost allocation
  costAllocation:
    enabled: true
    labelKeys:
      - team
      - project
      - environment
      - cost-center
  
  # Forecasting
  forecasting:
    enabled: true
    windows: [30, 60, 90]  # days
    anomalyDetection: true
  
  # Budgets
  budgets:
    - name: "platform-team"
      selector:
        team: "platform"
      monthlyLimit: 15000
      alertThreshold: 0.80
      webhook: "${SLACK_WEBHOOK}"
```

---

## 📊 **API Reference**

### Cost Endpoints
```bash
# Current costs
GET /api/cost-allocation/summary
GET /api/cost-allocation/by-team
GET /api/cost-allocation/by-namespace
GET /api/cost-allocation/by-deployment

# Recommendations
GET /api/finops/recommendations
GET /api/finops/waste-analysis
GET /api/finops/right-sizing/{namespace}/{deployment}

# Forecasting
GET /api/finops/forecast?days=30
GET /api/finops/trends
GET /api/finops/anomalies

# Reports
GET /api/reports/executive
GET /api/reports/team/{team}
GET /api/reports/savings-history
```

---

## 🎓 **Learning Resources**

### Tutorials
- [5-Minute Cost Optimization](../examples/cost-optimization-tutorial.md)
- [Setting Up Chargeback](../examples/chargeback-setup.md)
- [Budget Alerts Configuration](../examples/budget-alerts.md)

### Videos
- [Cost Optimization Demo](https://youtube.com/watch?v=xxx)
- [FinOps Best Practices](https://youtube.com/watch?v=xxx)

### Case Studies
- [E-Commerce: $312K Annual Savings](../case-studies/ecommerce.md)
- [SaaS: 32% Cost Reduction](../case-studies/saas.md)
- [Fintech: Optimizing Trading Hours](../case-studies/fintech.md)

---

## 💡 **Tips & Tricks**

### Maximize Savings
1. **Enable Autopilot**: Automatic continuous optimization
2. **Use Predictive Scaling**: Scale down during predicted low traffic
3. **Set Budgets**: Prevent cost overruns
4. **Review Weekly**: Check recommendations every week
5. **Label Everything**: Better cost allocation

### Avoid Common Mistakes
- ❌ Don't reduce requests too aggressively (use safety buffers)
- ❌ Don't ignore HPA target adjustments
- ❌ Don't skip testing in dev/staging first
- ❌ Don't forget to monitor performance after changes
- ✅ Do use gradual rollouts
- ✅ Do enable auto-rollback
- ✅ Do track savings over time

---

## 🚀 **Next Steps**

1. **Enable Cost Tracking**: Add pricing configuration
2. **Review Recommendations**: Check `/api/finops/recommendations`
3. **Test on Dev**: Apply recommendations to dev environment
4. **Monitor Results**: Track savings and performance
5. **Scale to Production**: Roll out gradually
6. **Enable Autopilot**: Automate continuous optimization

---

**Start saving today!** Most users see 30-50% cost reduction within the first month.
