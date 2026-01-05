# Changelog v0.0.29

**Release Date:** January 6, 2026

## Enhanced FinOps & Cost Tracking Integration

This release makes the FinOps and Cost & Reports tabs work smarter together by combining historical analysis with real-time Prometheus data.

### New Features

#### 1. Enriched FinOps API (`/api/finops/enriched`)
New API endpoint that combines:
- Resource right-sizing recommendations (from historical data analysis)
- Real-time waste tracking (from live Prometheus queries)

This provides a complete picture: what to optimize AND current waste in a single view.

#### 2. FinOps Tab Enhancements
- **Real-time waste badge**: Each workload now shows live cost/waste data from Prometheus
- **Combined summary banner**: Shows both potential savings (from right-sizing) and current waste (real-time)
- **Live data indicator**: Shows whether real-time Prometheus data is available
- **Updated header**: "FinOps Resource Right-Sizing + Real-time"

#### 3. Cost & Reports Tab Enhancements
- **30-Day Cluster Cost History Chart**: New chart showing daily cost, actual usage, and waste over 30 days
- **Historical stats**: 30-day total cost, waste, average daily cost, and efficiency percentage
- **Monthly projection**: Estimated monthly cost based on historical data
- **FinOps link banner**: Prompts users to check FinOps tab for optimization recommendations
- **Action column**: High-waste workloads (>30% waste) show "Optimize →" link to FinOps tab
- **Cross-tab navigation**: Easy navigation between Cost & Reports and FinOps tabs

### How It Works

**FinOps Tab** (Resource Right-Sizing):
- Analyzes historical data (P95 + buffer) to recommend optimal resource requests
- Now also shows real-time cost/waste from Prometheus for each workload
- Displays both potential savings AND current waste

**Cost & Reports Tab** (Real-time Cost + History):
- Shows live cost tracking from Prometheus
- **NEW**: 30-day cluster cost history chart with daily breakdown
- Links to FinOps for workloads with high waste
- Provides quick access to optimization recommendations

### API Changes

New endpoint:
```
GET /api/finops/enriched
```

Returns FinOps recommendations enriched with real-time data:
```json
{
  "recommendations": [
    {
      "deployment": "api-server",
      "namespace": "production",
      "recommendation_level": "high",
      "savings": {"monthly_savings_usd": 45.00},
      "realtime": {
        "cost_monthly": 120.50,
        "waste_monthly": 36.15,
        "waste_percent": 30.0,
        "cpu_utilization_percent": 45.2,
        "pod_count": 3
      }
    }
  ],
  "summary": {
    "total_monthly_savings": 150.00,
    "total_realtime_waste_monthly": 85.50,
    "has_realtime_data": true
  }
}
```

Existing endpoint for 30-day history:
```
GET /api/finops/cost-trends?days=30
```

Returns daily cost breakdown:
```json
{
  "daily_summary": [
    {"date": "2026-01-01", "cost": 28.50, "actual": 18.20, "wasted": 10.30},
    ...
  ],
  "summary": {
    "total_cost": 855.00,
    "total_wasted": 309.00,
    "efficiency": 63.9,
    "monthly_projection": 855.00
  }
}
```

### Upgrade Instructions

```bash
# Update to v0.0.29
kubectl set image deployment/smart-autoscaler \
  smart-autoscaler=ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:0.0.29

# Verify the new enriched API
curl http://localhost:5000/api/finops/enriched

# Verify 30-day cost history
curl http://localhost:5000/api/finops/cost-trends?days=30
```

### Testing

All tests pass:
- `tests/test_dashboard.py` - 8 tests passed
- `tests/test_realtime_cost.py` - 7 tests passed
- `tests/test_cost_alerting.py` - 6 tests passed

Coverage: 30% (above 25% minimum)
