# Predictive Pre-Scaling

## Overview

Smart Autoscaler includes **intelligent predictive pre-scaling** that learns from historical patterns and scales **before** traffic spikes occur. This is perfect for fintech systems with predictable high-traffic periods (e.g., market open at 8-9 AM).

> 📚 **For detailed ML documentation**, see [ML_PREDICTION_GUIDE.md](./ML_PREDICTION_GUIDE.md)

## 🆕 TRUE Pre-Scaling via HPA minReplicas (v0.0.32)

**The Problem**: Traditional predictive scaling only adjusts HPA target CPU utilization. This makes HPA more sensitive but doesn't guarantee pods will scale up - it only happens when CPU actually increases.

**The Solution**: TRUE pre-scaling directly patches HPA `minReplicas` to force immediate scale-up:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TRUE Pre-Scaling Flow                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. PREDICT    → ML models predict CPU spike in 15-60 minutes          │
│                                                                         │
│  2. STORE      → Save original HPA minReplicas (from Git/ArgoCD)       │
│                                                                         │
│  3. PATCH      → Increase minReplicas to force immediate scale-up      │
│                                                                         │
│  4. READY      → New pods are running BEFORE traffic arrives           │
│                                                                         │
│  5. ROLLBACK   → After peak passes or timeout, restore original        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Pre-Scale Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `ENABLE_PRESCALE` | `true` | Enable/disable pre-scaling |
| `PRESCALE_MIN_CONFIDENCE` | `0.7` | Minimum prediction confidence to act |
| `PRESCALE_THRESHOLD` | `75.0` | CPU % threshold to trigger pre-scale |
| `PRESCALE_ROLLBACK_MINUTES` | `60` | Auto-rollback after this many minutes |
| `PRESCALE_COOLDOWN_MINUTES` | `15` | Cooldown between pre-scale actions |

### Pre-Scale API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/prescale/summary` | Overview of all pre-scale states |
| `GET /api/prescale/profiles` | All registered deployment profiles |
| `GET /api/prescale/<ns>/<dep>` | Pre-scale profile for specific deployment |
| `POST /api/prescale/<ns>/<dep>/force` | Force pre-scale (body: `{new_min_replicas: N}`) |
| `POST /api/prescale/<ns>/<dep>/rollback` | Force rollback to original minReplicas |

### Example: Pre-Scale Profile

```bash
curl http://localhost:5000/api/prescale/default/trading-api | jq
```

```json
{
  "namespace": "default",
  "deployment": "trading-api",
  "hpa_name": "trading-api-hpa",
  "original_min_replicas": 2,
  "original_max_replicas": 10,
  "current_min_replicas": 5,
  "state": "pre_scaling",
  "pre_scale_started": "2026-01-06T07:45:00",
  "pre_scale_reason": "Predicted 85.2% CPU in 30min",
  "predicted_cpu": 85.2,
  "prediction_confidence": 0.82,
  "rollback_at": "2026-01-06T08:45:00",
  "pre_scale_count": 3,
  "successful_predictions": 2
}
```

### ArgoCD Compatibility

If using ArgoCD, configure it to ignore HPA minReplicas changes:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
spec:
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - RespectIgnoreDifferences=true
  ignoreDifferences:
    - group: autoscaling
      kind: HorizontalPodAutoscaler
      jsonPointers:
        - /spec/minReplicas
```

---

## ✅ Already Built-In!

Predictive scaling is **already implemented** and enabled by default. The system:
- ✅ Learns hourly and daily traffic patterns
- ✅ Predicts CPU usage for the next hour
- ✅ Pre-scales up before predicted spikes
- ✅ Validates predictions and learns from accuracy
- ✅ Adapts confidence based on historical accuracy

## 🆕 Advanced ML Predictions (v0.0.32)

The new Advanced Predictor module provides sophisticated ML-based predictions:

### Multiple Prediction Models
| Model | Best For | Description |
|-------|----------|-------------|
| **Mean** | Steady workloads | Historical average with confidence intervals |
| **Trend** | Growing/declining | Linear regression extrapolation |
| **Seasonal** | Daily/weekly patterns | Hour-of-day and day-of-week patterns |
| **Holt-Winters** | Seasonal + trend | Exponential smoothing with seasonality |
| **ARIMA** | Complex patterns | Time series forecasting |
| **Prophet-like** | Multi-seasonal | Trend + weekly + daily decomposition |
| **Ensemble** | Unknown patterns | Weighted combination of all models |

### Multiple Prediction Windows
- **15min** - Immediate response planning
- **30min** - Short-term capacity planning  
- **1hr** - Standard predictive scaling
- **2hr** - Medium-term planning
- **4hr** - Long-term trend analysis

### Adaptive Model Selection
The system automatically selects the best model based on:
- Workload characteristics (steady, bursty, periodic, trending)
- Historical model performance per deployment
- Data availability and quality

### Confidence Intervals
Every prediction includes:
- **Predicted value** - Most likely CPU/memory usage
- **Confidence** - How reliable the prediction is (0-100%)
- **Lower/Upper bounds** - 95% confidence interval

---

## How It Works

### 1. Pattern Learning
The system learns patterns from historical data:
- **Hourly patterns**: CPU usage by hour of day (0-23)
- **Daily patterns**: CPU usage by day of week (Mon-Sun)
- **Seasonal patterns**: Detects periodic cycles (daily/weekly)

### 2. Prediction
Every check interval (default: 60 seconds), the system:
1. Predicts CPU usage for the **next hour**
2. Calculates confidence based on historical variance
3. Adjusts confidence based on prediction accuracy

### 3. Pre-Scaling Decision
If predicted CPU > 80%:
- **Action**: Pre-scale up (lower HPA target by 5-10%)
- **Timing**: Happens **before** the spike
- **Validation**: Only if historical accuracy > 60%

### 4. Adaptive Learning
The system tracks prediction accuracy:
- **Accurate predictions**: Increase confidence
- **False positives**: Reduce confidence for scale-up
- **False negatives**: Adjust thresholds

---

## Configuration

### Enable/Disable Predictive Scaling

**ConfigMap** (`k8s/configmap.yaml`):
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: autoscaler-config
  namespace: autoscaler-system
data:
  ENABLE_PREDICTIVE: "true"  # Enable predictive scaling
  PREDICTION_MIN_ACCURACY: "0.60"  # Require 60% accuracy
  PREDICTION_MIN_SAMPLES: "10"  # Need 10 predictions before trusting
```

**Helm** (`values.yaml`):
```yaml
config:
  enablePredictive: true  # Enable predictive scaling
  predictionMinAccuracy: 0.60  # 60% accuracy threshold
  predictionMinSamples: 10  # Minimum predictions needed
```

### Pattern-Specific Behavior

The system automatically adjusts predictive scaling based on detected patterns:

| Pattern | Predictive Enabled | Reason |
|---------|-------------------|--------|
| **Periodic** | ✅ Yes | Daily/weekly patterns are highly predictable |
| **Growing** | ✅ Yes | Upward trends benefit from pre-scaling |
| **Steady** | ❌ No | Consistent load doesn't need prediction |
| **Bursty** | ❌ No | Random spikes are unpredictable |
| **Declining** | ❌ No | Downward trends don't need pre-scaling |

---

## Fintech Use Case: Market Open (8-9 AM)

### Scenario
Your fintech system experiences high traffic every weekday from 8:00-9:00 AM when markets open.

### How Smart Autoscaler Handles It

#### Phase 1: Learning (First 1-2 Weeks)
```
Day 1-7: System collects data
- Records CPU usage every minute
- Builds hourly patterns (0-23)
- Identifies weekday vs weekend patterns

Day 8-14: Pattern detection
- Detects PERIODIC pattern (daily cycle)
- Identifies 8-9 AM as peak hour
- Calculates average CPU during peak: ~85%
```

#### Phase 2: Prediction (After 2 Weeks)
```
7:50 AM: System predicts next hour
- Historical data: 8-9 AM averages 85% CPU
- Confidence: 80% (based on consistency)
- Decision: Pre-scale up

7:51 AM: Pre-scaling action
- Current HPA target: 70%
- Predicted CPU: 85% > 80% threshold
- Action: Lower target to 60% (pre-scale up)
- Result: Pods scale up BEFORE traffic spike
```

#### Phase 3: Validation & Learning
```
8:50 AM: Validate prediction
- Predicted: 85% CPU
- Actual: 82% CPU
- Error: 3% (very accurate!)
- Update: Increase confidence to 85%

Next day 7:50 AM: Improved prediction
- Confidence now 85% (was 80%)
- More aggressive pre-scaling
- Even better preparation for spike
```

### Expected Timeline

| Time | Action | Result |
|------|--------|--------|
| **7:50 AM** | Prediction: 85% CPU expected | Confidence: 80% |
| **7:51 AM** | Pre-scale: Lower HPA target 70% → 60% | Pods start scaling up |
| **7:55 AM** | Pods ready | 5 minutes before traffic |
| **8:00 AM** | Traffic spike begins | Already scaled! |
| **8:50 AM** | Validation | Accuracy tracked |
| **9:00 AM** | Traffic normalizes | System scales down |

---

## Monitoring Predictions

### API Endpoints

#### 1. Get Basic Predictions
```bash
curl http://localhost:5000/api/deployment/demo/trading-api/predictions | jq
```

Response:
```json
{
  "predictions": [
    {
      "timestamp": "2026-01-01T07:50:00",
      "predicted_cpu": 85.2,
      "confidence": 0.82,
      "action": "pre_scale_up",
      "reasoning": "Predicted 85.2% > 80% - pre-scale up",
      "validated": true,
      "actual_cpu": 82.1,
      "accuracy": 0.97,
      "error": 3.1
    }
  ],
  "accuracy_stats": {
    "total_predictions": 156,
    "accurate_predictions": 142,
    "accuracy_rate": 91.0,
    "false_positives": 8,
    "false_positive_rate": 5.1,
    "false_negatives": 6,
    "avg_accuracy": 0.89
  }
}
```

#### 2. Get Advanced ML Predictions (v0.0.31)
```bash
curl http://localhost:5000/api/predictions/advanced/trading-api | jq
```

Response:
```json
{
  "deployment": "trading-api",
  "predictions": {
    "15min": {
      "predicted": 72.5,
      "confidence": 85.2,
      "lower_bound": 65.3,
      "upper_bound": 79.7,
      "model": "ensemble",
      "reasoning": "Ensemble of 4 models: mean, trend, seasonal, holt_winters"
    },
    "1hr": {
      "predicted": 85.2,
      "confidence": 78.5,
      "lower_bound": 72.1,
      "upper_bound": 98.3,
      "model": "prophet_like",
      "reasoning": "Decomposition: trend=45.2, weekly=25.3, daily=14.7"
    }
  },
  "model_performance": {
    "mean": {"accuracy_rate": 72.5, "total_predictions": 50},
    "prophet_like": {"accuracy_rate": 85.3, "total_predictions": 45}
  },
  "best_model": "prophet_like",
  "prediction_quality": "good",
  "average_confidence": 78.5
}
```

#### 3. Get Prediction for Specific Window
```bash
curl http://localhost:5000/api/predictions/advanced/trading-api/1hr | jq
```

Response:
```json
{
  "deployment": "trading-api",
  "window": "1hr",
  "predicted_value": 85.2,
  "confidence": 78.5,
  "lower_bound": 72.1,
  "upper_bound": 98.3,
  "model_used": "prophet_like",
  "reasoning": "Decomposition: trend=45.2, weekly=25.3, daily=14.7",
  "components": {
    "trend": 45.2,
    "weekly_seasonal": 25.3,
    "daily_seasonal": 14.7,
    "residual_std": 8.2
  }
}
```

#### 4. Get Model Performance
```bash
curl http://localhost:5000/api/predictions/models/trading-api | jq
```

Response:
```json
{
  "deployment": "trading-api",
  "model_performance": {
    "mean": {"accuracy_rate": 72.5, "mape": 12.3, "rmse": 8.5},
    "trend": {"accuracy_rate": 68.2, "mape": 15.1, "rmse": 10.2},
    "prophet_like": {"accuracy_rate": 85.3, "mape": 8.7, "rmse": 5.8}
  },
  "best_model": "prophet_like",
  "available_models": ["mean", "trend", "seasonal", "holt_winters", "arima", "prophet_like", "ensemble"]
}
```

#### 5. Get Scaling Recommendation
```bash
curl http://localhost:5000/api/predictions/scaling-recommendation/trading-api | jq
```

Response:
```json
{
  "deployment": "trading-api",
  "current_cpu": 65.0,
  "current_hpa_target": 70.0,
  "action": "pre_scale_up",
  "reason": "Predicted 85.2% CPU in 1hr (confidence: 78%)",
  "recommended_hpa_target": 60.0,
  "prediction_window": "1hr",
  "predicted_cpu": 85.2,
  "confidence": 0.78,
  "model_used": "prophet_like"
}
```

#### 6. Check if Predictive Should Be Enabled
```bash
curl http://localhost:5000/api/predictions/should-enable/trading-api | jq
```

Response:
```json
{
  "deployment": "trading-api",
  "should_enable": true,
  "reason": "Good prediction accuracy (85% with prophet_like)"
}
```

#### 7. Get AI Insights
```bash
curl http://localhost:5000/api/ai/insights/trading-api | jq
```

Response:
```json
{
  "deployment": "trading-api",
  "patterns": {
    "hourly": [45, 42, 40, 38, 35, 33, 35, 65, 85, 82, 75, ...],
    "peak_hours": [8, 9, 10],
    "low_hours": [0, 1, 2, 3, 4, 5]
  },
  "prediction_accuracy": {
    "accuracy_rate": 91.0,
    "total_predictions": 156
  }
}
```

### Logs

```bash
# Monitor predictive scaling
kubectl logs -n autoscaler-system -l app=smart-autoscaler | grep -i "predict"

# Example output:
# 2026-01-01 07:50:15 INFO - trading-api - Predicted 85.2% > 80% - pre-scale up
# 2026-01-01 07:51:20 INFO - trading-api - Applying predictive scale-up
# 2026-01-01 08:50:30 INFO - trading-api - Prediction accuracy: 91.0% (142/156)
```

---

## Dashboard Visualization

The dashboard shows:
1. **Predictions tab**: Historical predictions with accuracy
2. **AI Insights**: Pattern detection and learning progress
3. **Scaling Timeline**: When pre-scaling occurred
4. **Accuracy Stats**: Prediction performance metrics

Access: `http://localhost:5000` (port-forward the dashboard)

---

## Tuning for Your Use Case

### Aggressive Pre-Scaling (Fintech)
For critical systems where latency matters more than cost:

```yaml
# k8s/configmap.yaml
ENABLE_PREDICTIVE: "true"
PREDICTION_MIN_ACCURACY: "0.50"  # Lower threshold (50%)
PREDICTION_MIN_SAMPLES: "5"      # Trust predictions sooner
TARGET_NODE_UTILIZATION: "30"    # More headroom (was 70%)
```

**Effect**: 
- Pre-scales earlier with less historical data
- More aggressive scaling (40% target vs 70%)
- Better prepared for spikes, slightly higher cost

### Conservative Pre-Scaling (Cost-Sensitive)
For non-critical systems where cost matters:

```yaml
ENABLE_PREDICTIVE: "true"
PREDICTION_MIN_ACCURACY: "0.70"  # Higher threshold (70%)
PREDICTION_MIN_SAMPLES: "20"     # More data needed
TARGET_NODE_UTILIZATION: "70"    # Standard headroom
```

**Effect**:
- Only pre-scales when very confident
- Requires more historical data
- Lower cost, but may scale slightly later

---

## Best Practices

### 1. Give It Time to Learn
- **Week 1**: System collects data, no predictions yet
- **Week 2**: Pattern detection begins, low confidence
- **Week 3+**: High confidence, accurate predictions

### 2. Monitor Accuracy
```bash
# Check prediction accuracy weekly
curl http://localhost:5000/api/deployment/demo/trading-api/predictions | \
  jq '.accuracy_stats'
```

Target: **>80% accuracy** for production use

### 3. Adjust Thresholds
If false positives are high (>20%):
```yaml
PREDICTION_MIN_ACCURACY: "0.70"  # Increase from 0.60
```

If missing spikes (false negatives):
```yaml
PREDICTION_MIN_ACCURACY: "0.50"  # Decrease from 0.60
```

### 4. Combine with Priority
For critical fintech services:
```yaml
deployments:
  - namespace: trading
    deployment: trading-api
    hpa_name: trading-api-hpa
    priority: critical  # Gets resources first
```

---

## Troubleshooting

### Predictions Not Happening

**Check 1**: Is predictive scaling enabled?
```bash
kubectl get cm autoscaler-config -n autoscaler-system -o yaml | grep ENABLE_PREDICTIVE
```

**Check 2**: Is pattern detected?
```bash
curl http://localhost:5000/api/ai/insights/trading-api | jq '.patterns'
```

**Check 3**: Enough historical data?
```bash
# Need at least 20 samples (about 30 minutes)
curl http://localhost:5000/api/deployment/demo/trading-api/history?hours=2 | \
  jq '.timestamps | length'
```

### Low Accuracy

**Cause**: Workload is too random (bursty pattern)

**Solution**: 
1. Check pattern: `curl .../ai/insights/... | jq '.patterns'`
2. If pattern is "bursty", predictive scaling is automatically disabled
3. Consider using priority-based scaling instead

### False Positives

**Cause**: Predictions are too aggressive

**Solution**:
```yaml
PREDICTION_MIN_ACCURACY: "0.70"  # Increase threshold
PREDICTION_MIN_SAMPLES: "20"     # Need more data
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Predictive Scaler                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Pattern Recognizer                                      │
│     ├─ Learn hourly patterns (0-23)                        │
│     ├─ Learn daily patterns (Mon-Sun)                      │
│     └─ Predict next hour CPU                               │
│                                                             │
│  2. Confidence Calculator                                   │
│     ├─ Base confidence (from variance)                     │
│     ├─ Historical accuracy adjustment                      │
│     └─ False positive rate adjustment                      │
│                                                             │
│  3. Decision Engine                                         │
│     ├─ If predicted > 80%: pre_scale_up                    │
│     ├─ If predicted < 50%: scale_down                      │
│     └─ Else: maintain                                      │
│                                                             │
│  4. Validation & Learning                                   │
│     ├─ Compare prediction vs actual                        │
│     ├─ Track accuracy stats                                │
│     └─ Adjust confidence for next prediction               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Example: Full Day Cycle

```
Time    | Predicted | Actual | Action           | Result
--------|-----------|--------|------------------|------------------
00:00   | 35%       | 33%    | maintain         | ✓ Accurate
04:00   | 30%       | 32%    | maintain         | ✓ Accurate
07:50   | 85%       | -      | pre_scale_up     | Pods scaling...
08:00   | -         | 82%    | -                | ✓ Ready for spike!
09:00   | 75%       | 73%    | maintain         | ✓ Accurate
12:00   | 65%       | 68%    | maintain         | ✓ Accurate
17:00   | 45%       | 42%    | scale_down       | ✓ Cost savings
23:00   | 35%       | 36%    | maintain         | ✓ Accurate

Daily Accuracy: 95% (19/20 predictions accurate)
```

---

## Summary

✅ **Predictive pre-scaling is already built-in and enabled**

✅ **Perfect for fintech systems with predictable patterns**

✅ **Learns from historical data automatically**

✅ **Validates predictions and adapts confidence**

✅ **Pre-scales BEFORE traffic spikes**

### Quick Start
1. Deploy Smart Autoscaler with `ENABLE_PREDICTIVE: "true"` (default)
2. Wait 1-2 weeks for pattern learning
3. Monitor predictions: `curl .../predictions`
4. Check accuracy: Should be >80% after 2 weeks
5. Enjoy automatic pre-scaling! 🚀

### For Fintech Systems
- Use `priority: critical` for trading APIs
- Set `TARGET_NODE_UTILIZATION: "30"` for more headroom
- Monitor accuracy weekly
- Combine with auto-tuning for optimal targets

---

**Next Steps**: 
- Deploy v0.0.12 (includes all fixes)
- Enable predictive scaling (already enabled by default)
- Wait for pattern learning (1-2 weeks)
- Monitor dashboard for predictions
