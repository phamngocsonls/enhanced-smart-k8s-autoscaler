# Advanced Cost Allocation Guide

## Overview

The Advanced Cost Allocation feature provides enterprise-grade cost tracking, chargeback/showback capabilities, and detailed cost analysis across teams, projects, and namespaces.

## Features

### 1. Multi-Dimensional Cost Tracking

Track costs across multiple dimensions:
- **Team**: Group costs by team/squad
- **Project**: Group costs by application/project
- **Namespace**: Group costs by Kubernetes namespace
- **Environment**: Separate dev/staging/production costs

### 2. Cost Anomaly Detection

Automatically detect unusual cost spikes:
- Statistical analysis (2-3 standard deviations)
- Historical baseline comparison
- Severity classification (high/medium)
- Root cause suggestions

### 3. Idle Resource Detection

Identify wasted resources:
- Low CPU utilization (<20%)
- Low memory utilization (<20%)
- Monthly waste calculations
- Prioritized by savings potential

### 4. Cost Trends & Forecasting

Historical analysis and predictions:
- 30/60/90-day cost trends
- Week-over-week comparisons
- Month-over-month growth
- Linear regression forecasting

---

## Configuration

### Label-Based Cost Allocation

Add labels to your deployments for automatic cost allocation:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
  namespace: production
  labels:
    team: backend              # Team ownership
    project: user-api          # Project/application
    environment: production    # Environment
    cost-center: engineering   # Cost center for billing
    department: platform       # Department
spec:
  # ... deployment spec
```

### Supported Label Keys

The system recognizes multiple label patterns:

| Dimension | Label Keys (in priority order) |
|-----------|-------------------------------|
| Team | `team`, `owner`, `squad` |
| Project | `project`, `app`, `application` |
| Environment | `env`, `environment`, `stage` |
| Cost Center | `cost-center`, `costcenter`, `billing` |
| Department | `department`, `dept`, `division` |

### Cost Rates

**Auto-Detection (Recommended):**

The system automatically detects your cloud provider (GCP, AWS, Azure) and uses actual instance pricing based on your node types. No manual configuration needed!

**Pricing Data:**
- Pricing is based on Singapore region (asia-southeast1/ap-southeast-1/southeastasia)
- Pricing data is updated with each release based on official cloud provider pricing pages
- Pricing rarely changes (typically 1-2 times per year)

**Update Pricing (Optional):**

To fetch the latest pricing from cloud provider APIs:

```bash
# Fetch latest Azure pricing (public API, no auth required)
python scripts/update-pricing.py --provider azure --region southeastasia

# Update all providers (requires API access)
python scripts/update-pricing.py --all

# Schedule daily updates (cron)
0 2 * * * /path/to/update-pricing.py --provider azure
```

**Manual Override (Optional):**

If you want to override auto-detected pricing or use custom rates:

```yaml
# In ConfigMap or Helm values
COST_PER_VCPU_HOUR: "0.04"        # $/vCPU/hour
COST_PER_GB_MEMORY_HOUR: "0.005"  # $/GB/hour
```

**Supported Cloud Providers:**
- **GCP**: Auto-detects from GKE node labels and instance types
  - All families: E2, N1, N2, N2D, T2D, T2A, C2, C2D, C3, C3D, M1, M2, M3, A2, A3, G2
  - Pricing: Singapore (asia-southeast1) region
- **AWS**: Auto-detects from EKS node labels and instance types
  - All families: T2, T3, T4g, M5, M6i, M6g, M7g, M7i, C5, C6i, C6g, C7g, C7i, R5, R6i, R6g, R7g, R7i, X1, X2, I3, I4i
  - Pricing: Singapore (ap-southeast-1) region
- **Azure**: Auto-detects from AKS node labels and instance types
  - All families: A, B, D (v2-v5), Dps, F, Fx, E (v3-v5), Eps, M, Mv2, L, NC, ND series
  - Pricing: Southeast Asia (Singapore) region

**Check Detected Pricing:**
```bash
curl http://localhost:5000/api/cost/pricing-info
```

**Common Cloud Pricing (for reference):**
- AWS: ~$0.04/vCPU/hour, ~$0.005/GB/hour
- GCP: ~$0.04/vCPU/hour, ~$0.005/GB/hour
- Azure: ~$0.04/vCPU/hour, ~$0.005/GB/hour

---

## API Endpoints

### Get Team Costs

```bash
GET /api/cost/allocation/team?hours=24
```

**Response:**
```json
{
  "platform": {
    "deployments": [
      {
        "namespace": "production",
        "deployment": "api-gateway",
        "cost": 12.50,
        "cpu_cost": 8.00,
        "memory_cost": 4.50
      }
    ],
    "total_cost": 125.00,
    "cpu_cost": 80.00,
    "memory_cost": 45.00,
    "deployment_count": 10
  },
  "backend": {
    "total_cost": 200.00,
    "deployment_count": 15
  }
}
```

### Get Namespace Costs

```bash
GET /api/cost/allocation/namespace?hours=24
```

**Response:**
```json
{
  "production": {
    "deployments": [...],
    "total_cost": 300.00,
    "deployment_count": 20
  },
  "staging": {
    "total_cost": 50.00,
    "deployment_count": 10
  }
}
```

### Get Project Costs

```bash
GET /api/cost/allocation/project?hours=24
```

### Detect Cost Anomalies

```bash
GET /api/cost/anomalies
```

**Response:**
```json
{
  "anomalies": [
    {
      "date": "2024-01-04",
      "cost": 500.00,
      "expected_cost": 300.00,
      "deviation": 200.00,
      "severity": "high"
    }
  ]
}
```

### Get Idle Resources

```bash
GET /api/cost/idle-resources?threshold=0.2
```

**Response:**
```json
{
  "idle_resources": [
    {
      "namespace": "production",
      "deployment": "old-service",
      "cpu_utilization": 10.5,
      "memory_utilization": 15.0,
      "daily_cost": 25.00,
      "wasted_cost": 21.25,
      "monthly_waste": 637.50
    }
  ]
}
```

### Get Pricing Information

```bash
GET /api/cost/pricing-info
```

**Response:**
```json
{
  "provider": "gcp",
  "vcpu_price": 0.0475,
  "memory_gb_price": 0.0063,
  "auto_detected": true,
  "source": "GCP instance pricing",
  "configured_vcpu_price": 0.0475,
  "configured_memory_gb_price": 0.0063
}
```

---

## Use Cases

### 1. Chargeback/Showback

**Scenario:** Finance needs to bill teams for their infrastructure usage.

**Solution:**
```bash
# Get monthly costs by team
curl http://localhost:5000/api/cost/allocation/team?hours=720

# Export to CSV for billing
curl http://localhost:5000/api/cost/allocation/team?hours=720 | \
  jq -r '.[] | [.team, .total_cost, .deployment_count] | @csv'
```

### 2. Budget Monitoring

**Scenario:** Each team has a monthly budget to track.

**Solution:**
```bash
# Get team costs and compare to budget
TEAM_COST=$(curl -s http://localhost:5000/api/cost/allocation/team?hours=720 | \
  jq '.platform.total_cost')

BUDGET=5000
if (( $(echo "$TEAM_COST > $BUDGET" | bc -l) )); then
  echo "⚠️ Team over budget: \$$TEAM_COST / \$$BUDGET"
fi
```

### 3. Cost Optimization

**Scenario:** Identify and eliminate waste.

**Solution:**
```bash
# Find top 10 idle resources
curl http://localhost:5000/api/cost/idle-resources | \
  jq '.idle_resources[:10]'

# Calculate total potential savings
curl http://localhost:5000/api/cost/idle-resources | \
  jq '[.idle_resources[].monthly_waste] | add'
```

### 4. Anomaly Investigation

**Scenario:** Unexpected cost spike needs investigation.

**Solution:**
```bash
# Check for anomalies
curl http://localhost:5000/api/cost/anomalies

# Get detailed breakdown
curl http://localhost:5000/api/cost/allocation/namespace?hours=24
```

---

## Dashboard Integration

### Cost Allocation Tab

The dashboard includes a "Cost Allocation" tab with:

1. **Team Breakdown**
   - Pie chart of costs by team
   - Top 5 teams by spend
   - Drill-down to deployments

2. **Namespace View**
   - Bar chart of namespace costs
   - Environment comparison (prod vs staging)

3. **Idle Resources**
   - Table of underutilized deployments
   - Potential savings highlighted
   - One-click recommendations

4. **Anomaly Alerts**
   - Recent cost spikes
   - Severity indicators
   - Investigation links

---

## Best Practices

### 1. Consistent Labeling

Establish a labeling standard:

```yaml
# Good: Consistent labels across all deployments
labels:
  team: backend
  project: user-api
  environment: production
  cost-center: engineering

# Bad: Inconsistent or missing labels
labels:
  owner: john  # Use 'team' instead
  # Missing project and cost-center
```

### 2. Regular Reviews

Schedule regular cost reviews:
- **Weekly**: Check for anomalies
- **Monthly**: Review team costs and budgets
- **Quarterly**: Analyze trends and forecast

### 3. Automate Alerts

Set up alerts for cost issues:

```bash
# Example: Daily cost check script
#!/bin/bash
ANOMALIES=$(curl -s http://localhost:5000/api/cost/anomalies | jq '.anomalies | length')

if [ "$ANOMALIES" -gt 0 ]; then
  # Send alert to Slack/Teams
  curl -X POST $SLACK_WEBHOOK \
    -d "{\"text\": \"⚠️ $ANOMALIES cost anomalies detected!\"}"
fi
```

### 4. Right-Size Regularly

Act on idle resource recommendations:

```bash
# Weekly: Get idle resources and create tickets
curl http://localhost:5000/api/cost/idle-resources | \
  jq '.idle_resources[:5]' | \
  # Parse and create Jira tickets
```

---

## Troubleshooting

### Issue: All deployments show "unallocated" team

**Cause:** Missing team labels on deployments

**Fix:**
```bash
# Add team label to deployment
kubectl label deployment api-service team=backend -n production
```

### Issue: Costs seem incorrect

**Cause:** Wrong cost rates configured

**Fix:**
```bash
# Update cost rates in ConfigMap
kubectl edit configmap smart-autoscaler-config -n autoscaler-system

# Update these values:
COST_PER_VCPU_HOUR: "0.04"
COST_PER_GB_MEMORY_HOUR: "0.005"
```

### Issue: No historical data for trends

**Cause:** Database not retaining metrics

**Fix:**
```bash
# Check database size
kubectl exec -it deployment/smart-autoscaler -n autoscaler-system -- \
  du -h /data/autoscaler.db

# Ensure PVC has enough space
kubectl get pvc -n autoscaler-system
```

---

## Integration Examples

### Grafana Dashboard

Create a Grafana dashboard using the API:

```json
{
  "dashboard": {
    "title": "Cost Allocation",
    "panels": [
      {
        "title": "Team Costs",
        "targets": [
          {
            "url": "http://smart-autoscaler:5000/api/cost/allocation/team"
          }
        ]
      }
    ]
  }
}
```

### Slack Bot

Daily cost summary to Slack:

```python
import requests

# Get team costs
response = requests.get('http://smart-autoscaler:5000/api/cost/allocation/team?hours=24')
teams = response.json()

# Format message
message = "📊 Daily Cost Summary:\n"
for team, data in teams.items():
    message += f"• {team}: ${data['total_cost']:.2f}\n"

# Send to Slack
requests.post(SLACK_WEBHOOK, json={'text': message})
```

---

## Next Steps

- [Advanced Reporting](REPORTING.md) - Executive reports and ROI analysis
- [FinOps Guide](../README.md#-cost-optimization--resource-right-sizing) - Resource right-sizing
- [API Reference](../README.md#-api-endpoints) - Complete API documentation
