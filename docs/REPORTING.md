# Advanced Reporting Guide

## Overview

The Advanced Reporting feature provides executive-level reports, trend analysis, ROI calculations, and cost forecasting for data-driven decision making.

## Report Types

### 1. Executive Summary
Comprehensive overview for leadership

### 2. Team Reports
Detailed analysis per team

### 3. Cost Forecast
Predict future costs (30/60/90 days)

### 4. ROI Report
Calculate savings from optimizations

### 5. Trend Analysis
Historical patterns and changes

---

## API Endpoints

### Executive Summary

```bash
GET /api/reports/executive-summary?days=30
```

**Response:**
```json
{
  "generated_at": "2024-01-04T10:00:00",
  "period_days": 30,
  "summary": {
    "total_deployments": 50,
    "daily_cost": 500.00,
    "monthly_cost": 15000.00,
    "efficiency_score": 75,
    "potential_monthly_savings": 2000.00,
    "savings_percentage": 13.3
  },
  "cost_breakdown": {
    "by_team": {
      "platform": {
        "total_cost": 200.00,
        "deployment_count": 15
      }
    },
    "trends": [
      {
        "date": "2024-01-01",
        "total_cost": 480.00,
        "deployment_count": 50
      }
    ]
  },
  "alerts": {
    "cost_anomalies": [],
    "idle_resources": [
      {
        "namespace": "production",
        "deployment": "old-service",
        "monthly_waste": 500.00
      }
    ],
    "anomaly_count": 0,
    "idle_resource_count": 10
  },
  "scaling_activity": {
    "total_events": 150,
    "scale_ups": 90,
    "scale_downs": 60,
    "avg_per_day": 5.0
  },
  "recommendations": [
    "Right-size production/old-service to save $500.00/month (currently 10% CPU utilized)",
    "Review top 5 underutilized deployments for potential savings of $1500.00/month"
  ]
}
```

### Team Report

```bash
GET /api/reports/team/platform?days=30
```

**Response:**
```json
{
  "team": "platform",
  "generated_at": "2024-01-04T10:00:00",
  "period_days": 30,
  "summary": {
    "deployment_count": 15,
    "daily_cost": 200.00,
    "monthly_cost": 6000.00,
    "cpu_cost": 120.00,
    "memory_cost": 80.00
  },
  "deployments": [
    {
      "namespace": "production",
      "deployment": "api-gateway",
      "daily_cost": 50.00,
      "monthly_cost": 1500.00,
      "metrics": {
        "avg_cpu": 0.75,
        "avg_memory": 2.5,
        "avg_replicas": 5.0,
        "min_replicas": 3,
        "max_replicas": 10
      }
    }
  ]
}
```

### Cost Forecast

```bash
GET /api/reports/forecast?days=90
```

**Response:**
```json
{
  "generated_at": "2024-01-04T10:00:00",
  "forecast_days": 90,
  "trend": "increasing",
  "daily_change": 2.50,
  "forecasts": [
    {
      "date": "2024-01-05",
      "predicted_cost": 502.50,
      "confidence": "high"
    },
    {
      "date": "2024-01-06",
      "predicted_cost": 505.00,
      "confidence": "high"
    }
  ],
  "totals": {
    "30_day": 15750.00,
    "60_day": 32250.00,
    "90_day": 49500.00
  }
}
```

### ROI Report

```bash
GET /api/reports/roi
```

**Response:**
```json
{
  "generated_at": "2024-01-04T10:00:00",
  "current_monthly_cost": 15000.00,
  "potential_monthly_savings": 2000.00,
  "potential_annual_savings": 24000.00,
  "savings_percentage": 13.3,
  "optimization_breakdown": {
    "right_sizing": {
      "opportunities": 10,
      "monthly_savings": 2000.00,
      "annual_savings": 24000.00
    },
    "total": {
      "monthly_savings": 2000.00,
      "annual_savings": 24000.00,
      "savings_percentage": 13.3
    }
  },
  "top_opportunities": [
    {
      "namespace": "production",
      "deployment": "old-service",
      "monthly_waste": 500.00
    }
  ]
}
```

### Trend Analysis

```bash
GET /api/reports/trends?days=30
```

**Response:**
```json
{
  "generated_at": "2024-01-04T10:00:00",
  "period_days": 30,
  "cost_trends": {
    "week_over_week_change": 5.2,
    "month_over_month_change": 12.5,
    "trend_direction": "up",
    "daily_average": 485.00
  },
  "historical_data": [
    {
      "date": "2024-01-01",
      "total_cost": 480.00,
      "deployment_count": 50
    }
  ]
}
```

---

## Use Cases

### 1. Monthly Executive Report

**Scenario:** CFO needs monthly infrastructure cost report

**Solution:**
```bash
#!/bin/bash
# Generate monthly executive report

REPORT=$(curl -s http://localhost:5000/api/reports/executive-summary?days=30)

# Extract key metrics
MONTHLY_COST=$(echo $REPORT | jq '.summary.monthly_cost')
SAVINGS=$(echo $REPORT | jq '.summary.potential_monthly_savings')
EFFICIENCY=$(echo $REPORT | jq '.summary.efficiency_score')

# Email report
cat <<EOF | mail -s "Monthly Infrastructure Report" cfo@company.com
Monthly Infrastructure Cost Report
==================================

Total Monthly Cost: \$$MONTHLY_COST
Potential Savings: \$$SAVINGS
Efficiency Score: $EFFICIENCY/100

Top Recommendations:
$(echo $REPORT | jq -r '.recommendations[]')

Full report: http://dashboard.company.com/reports
EOF
```

### 2. Team Budget Tracking

**Scenario:** Track team spending against budget

**Solution:**
```bash
#!/bin/bash
# Check team budget

TEAM="platform"
BUDGET=6000

REPORT=$(curl -s http://localhost:5000/api/reports/team/$TEAM?days=30)
ACTUAL=$(echo $REPORT | jq '.summary.monthly_cost')

VARIANCE=$(echo "$ACTUAL - $BUDGET" | bc)
PERCENT=$(echo "scale=1; ($VARIANCE / $BUDGET) * 100" | bc)

if (( $(echo "$ACTUAL > $BUDGET" | bc -l) )); then
  echo "⚠️ Team $TEAM over budget by \$$VARIANCE ($PERCENT%)"
  # Send alert
else
  echo "✅ Team $TEAM within budget: \$$ACTUAL / \$$BUDGET"
fi
```

### 3. Cost Forecasting for Planning

**Scenario:** Plan next quarter's budget

**Solution:**
```bash
# Get 90-day forecast
FORECAST=$(curl -s http://localhost:5000/api/reports/forecast?days=90)

Q1_COST=$(echo $FORECAST | jq '.totals."90_day"')
TREND=$(echo $FORECAST | jq -r '.trend')

echo "Q1 Projected Cost: \$$Q1_COST"
echo "Trend: $TREND"

# Add 10% buffer for planning
BUDGET=$(echo "$Q1_COST * 1.1" | bc)
echo "Recommended Budget: \$$BUDGET"
```

### 4. ROI Justification

**Scenario:** Justify investment in optimization

**Solution:**
```bash
# Get ROI report
ROI=$(curl -s http://localhost:5000/api/reports/roi)

ANNUAL_SAVINGS=$(echo $ROI | jq '.potential_annual_savings')
TOOL_COST=5000  # Annual cost of autoscaler

NET_SAVINGS=$(echo "$ANNUAL_SAVINGS - $TOOL_COST" | bc)
ROI_PERCENT=$(echo "scale=1; ($NET_SAVINGS / $TOOL_COST) * 100" | bc)

cat <<EOF
ROI Analysis
============
Annual Savings: \$$ANNUAL_SAVINGS
Tool Cost: \$$TOOL_COST
Net Savings: \$$NET_SAVINGS
ROI: $ROI_PERCENT%

Payback Period: $(echo "scale=1; $TOOL_COST / ($ANNUAL_SAVINGS / 12)" | bc) months
EOF
```

---

## Automated Reporting

### Daily Summary Email

```python
#!/usr/bin/env python3
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# Get executive summary
response = requests.get('http://smart-autoscaler:5000/api/reports/executive-summary?days=1')
report = response.json()

# Format email
subject = f"Daily Infrastructure Report - {datetime.now().strftime('%Y-%m-%d')}"
body = f"""
Daily Infrastructure Summary
============================

Cost: ${report['summary']['daily_cost']:.2f}
Efficiency: {report['summary']['efficiency_score']}/100
Scaling Events: {report['scaling_activity']['total_events']}

Recommendations:
{chr(10).join('• ' + r for r in report['recommendations'])}

View full report: http://dashboard.company.com
"""

# Send email
msg = MIMEText(body)
msg['Subject'] = subject
msg['From'] = 'autoscaler@company.com'
msg['To'] = 'team@company.com'

smtp = smtplib.SMTP('smtp.company.com')
smtp.send_message(msg)
smtp.quit()
```

### Weekly Trend Report

```python
#!/usr/bin/env python3
import requests
import matplotlib.pyplot as plt
from datetime import datetime

# Get trend data
response = requests.get('http://smart-autoscaler:5000/api/reports/trends?days=30')
trends = response.json()

# Create chart
dates = [t['date'] for t in trends['historical_data']]
costs = [t['total_cost'] for t in trends['historical_data']]

plt.figure(figsize=(12, 6))
plt.plot(dates, costs, marker='o')
plt.title('30-Day Cost Trend')
plt.xlabel('Date')
plt.ylabel('Daily Cost ($)')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('/tmp/cost_trend.png')

# Email chart
# ... (email code)
```

### Monthly Executive Presentation

```python
#!/usr/bin/env python3
import requests
from pptx import Presentation
from pptx.util import Inches

# Get reports
exec_summary = requests.get('http://smart-autoscaler:5000/api/reports/executive-summary?days=30').json()
roi = requests.get('http://smart-autoscaler:5000/api/reports/roi').json()
forecast = requests.get('http://smart-autoscaler:5000/api/reports/forecast?days=90').json()

# Create PowerPoint
prs = Presentation()

# Slide 1: Summary
slide = prs.slides.add_slide(prs.slide_layouts[1])
slide.shapes.title.text = "Monthly Infrastructure Report"
content = slide.placeholders[1].text_frame
content.text = f"""
Monthly Cost: ${exec_summary['summary']['monthly_cost']:,.2f}
Efficiency Score: {exec_summary['summary']['efficiency_score']}/100
Potential Savings: ${exec_summary['summary']['potential_monthly_savings']:,.2f}
"""

# Slide 2: ROI
slide = prs.slides.add_slide(prs.slide_layouts[1])
slide.shapes.title.text = "Return on Investment"
content = slide.placeholders[1].text_frame
content.text = f"""
Annual Savings: ${roi['potential_annual_savings']:,.2f}
Savings Percentage: {roi['savings_percentage']}%
Optimization Opportunities: {roi['optimization_breakdown']['right_sizing']['opportunities']}
"""

# Slide 3: Forecast
slide = prs.slides.add_slide(prs.slide_layouts[1])
slide.shapes.title.text = "90-Day Cost Forecast"
content = slide.placeholders[1].text_frame
content.text = f"""
Trend: {forecast['trend'].upper()}
Q1 Projected: ${forecast['totals']['90_day']:,.2f}
Daily Change: ${forecast['daily_change']:.2f}
"""

prs.save('/tmp/monthly_report.pptx')
```

---

## Dashboard Integration

### Reports Tab

The dashboard includes a "Reports" tab with:

1. **Executive Dashboard**
   - Key metrics cards
   - Cost trend chart
   - Efficiency gauge
   - Top recommendations

2. **Team View**
   - Team selector dropdown
   - Deployment breakdown table
   - Cost allocation pie chart

3. **Forecast View**
   - 30/60/90-day projections
   - Trend line chart
   - Confidence indicators

4. **ROI Calculator**
   - Current vs optimized costs
   - Savings breakdown
   - Payback period

---

## Best Practices

### 1. Regular Cadence

Establish reporting schedule:
- **Daily**: Automated summary emails
- **Weekly**: Trend analysis and team reviews
- **Monthly**: Executive reports and budget reviews
- **Quarterly**: Strategic planning and forecasting

### 2. Actionable Insights

Focus on actionable recommendations:
```bash
# Good: Specific, actionable
"Right-size production/api-service to save $500/month"

# Bad: Vague, not actionable
"Some deployments are inefficient"
```

### 3. Stakeholder-Specific Reports

Tailor reports to audience:
- **Executives**: High-level summary, ROI, trends
- **Team Leads**: Team-specific costs, recommendations
- **Engineers**: Technical details, optimization opportunities
- **Finance**: Chargeback, budget tracking, forecasts

### 4. Track Progress

Monitor optimization impact:
```bash
# Before optimization
BEFORE=$(curl -s http://localhost:5000/api/reports/roi | jq '.current_monthly_cost')

# After optimization (1 month later)
AFTER=$(curl -s http://localhost:5000/api/reports/roi | jq '.current_monthly_cost')

SAVINGS=$(echo "$BEFORE - $AFTER" | bc)
echo "Actual savings: \$$SAVINGS/month"
```

---

## Troubleshooting

### Issue: Forecast shows "insufficient data"

**Cause:** Less than 7 days of historical data

**Fix:** Wait for more data to accumulate, or reduce forecast period

### Issue: ROI report shows zero savings

**Cause:** No idle resources detected

**Fix:** Lower utilization threshold or check if deployments are already optimized

### Issue: Team report returns "not found"

**Cause:** No deployments with that team label

**Fix:** Add team labels to deployments (see [Cost Allocation Guide](COST_ALLOCATION.md))

---

## Next Steps

- [Cost Allocation Guide](COST_ALLOCATION.md) - Team/project cost tracking
- [FinOps Guide](../README.md#-cost-optimization--resource-right-sizing) - Resource optimization
- [API Reference](../README.md#-api-endpoints) - Complete API documentation
