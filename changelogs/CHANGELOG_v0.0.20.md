# Changelog v0.0.20

**Release Date:** 2026-01-02

## 🔮 Prediction System Improvements

### Confidence Threshold Update
- Increased prediction confidence threshold from 0.75 to 0.80
- More conservative predictions to reduce false positives
- Better logging of confidence levels when predictions are skipped

### Prediction Accuracy Visualization
- New prediction vs actual CPU chart (7-day history)
- Daily accuracy trend bar chart with color coding
- Validated predictions list with accuracy percentages
- Real-time accuracy statistics display

### New API Endpoints
- `/api/predictions/accuracy/<deployment>` - Get prediction history with accuracy data
- Returns predicted vs actual values, daily accuracy summary, and validation stats

## 💰 FinOps Enhancements

### Cost Trends Visualization
- New 30-day cost trends stacked bar chart
- Shows actual cost vs wasted cost per day
- Summary stats: total cost, wasted, efficiency percentage
- Monthly projection based on historical data

### New API Endpoints
- `/api/finops/cost-trends` - Get daily cost data for all deployments
- Aggregates by deployment and provides cluster-wide totals
- Includes CPU and memory cost breakdown

## 🔔 Alerts & Anomalies Dashboard

### New Alerts Tab
- Dedicated tab for viewing recent alerts and anomalies
- Summary bar showing critical/warning/info counts
- Detailed alert cards with:
  - Severity indicator (🔴 critical, 🟡 warning, ℹ️ info)
  - Deployment name and anomaly type
  - Description and deviation details
  - Timestamp

### New API Endpoints
- `/api/alerts/recent` - Get recent anomalies (last 24h by default)
- Returns alerts sorted by timestamp with severity counts

## 📊 Dashboard Improvements

### Deployment Detail View
- New comprehensive detail endpoint `/api/deployment/{ns}/{name}/detail`
- Combines: current state, pattern, predictions, costs, recommendations
- Includes memory leak detection and recent scaling events

### UI Updates
- Added Alerts tab to main navigation
- Enhanced Predictions tab with accuracy charts
- Cost trends chart in FinOps tab
- Improved tab switching with proper data loading

## 🔧 Technical Improvements

### Code Quality
- Better error handling in new API endpoints
- Consistent response format across all endpoints
- Improved logging for prediction decisions

## Files Changed
- `src/__init__.py` - Version bump to 0.0.20
- `src/integrated_operator.py` - Updated confidence threshold
- `src/dashboard.py` - Added 5 new API endpoints
- `templates/dashboard.html` - New tabs, charts, and UI improvements

## API Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/predictions/accuracy/<dep>` | GET | Prediction accuracy history |
| `/api/finops/cost-trends` | GET | 30-day cost trends |
| `/api/alerts/recent` | GET | Recent anomalies |
| `/api/deployment/<ns>/<dep>/detail` | GET | Comprehensive deployment detail |
