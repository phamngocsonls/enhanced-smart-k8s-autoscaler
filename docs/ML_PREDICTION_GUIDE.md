# Machine Learning Prediction Guide

## Overview

Smart Autoscaler uses a sophisticated multi-layer ML prediction system to forecast CPU/memory usage and enable TRUE pre-scaling. This guide covers the complete ML architecture.

## ML Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ML PREDICTION ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Layer 1: DATA COLLECTION                                                   │
│  ├─ TimeSeriesDatabase (SQLite)                                            │
│  ├─ Metrics: CPU, Memory, Pod Count, HPA Target                            │
│  └─ Historical patterns by hour/day/week                                   │
│                                                                             │
│  Layer 2: PATTERN DETECTION                                                 │
│  ├─ PatternDetector (src/pattern_detector.py)                              │
│  │   ├─ Steady, Bursty, Periodic, Growing, Declining                       │
│  │   ├─ Weekly/Monthly seasonality                                         │
│  │   └─ Cross-deployment correlations                                      │
│  └─ PatternRecognizer (src/intelligence.py)                                │
│      ├─ Workload type classification                                       │
│      └─ Model weight selection                                             │
│                                                                             │
│  Layer 3: PREDICTION MODELS                                                 │
│  ├─ AdvancedPredictor (src/advanced_predictor.py) - PRIMARY                │
│  │   ├─ Mean Model (steady workloads)                                      │
│  │   ├─ Trend Model (linear regression)                                    │
│  │   ├─ Seasonal Model (hour/day patterns)                                 │
│  │   ├─ Holt-Winters (exponential smoothing)                               │
│  │   ├─ ARIMA (time series forecasting)                                    │
│  │   ├─ Prophet-like (trend + multi-seasonality)                           │
│  │   └─ Ensemble (weighted combination)                                    │
│  └─ MLPredictor (src/ml_models.py) - ADVANCED                              │
│      ├─ Random Forest                                                       │
│      └─ Gradient Boosting                                                   │
│                                                                             │
│  Layer 4: SCALING DECISIONS                                                 │
│  ├─ PredictiveScaler (src/advanced_predictor.py)                           │
│  │   ├─ Calculate required replicas                                        │
│  │   └─ Scaling recommendations                                            │
│  └─ PreScaleManager (src/prescale_manager.py)                              │
│      ├─ TRUE pre-scaling via HPA minReplicas                               │
│      └─ Auto-rollback after peak                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Prediction Models Explained

### 1. Mean Model
Best for: **Steady workloads** with low variance (CV < 15%)

```python
# Algorithm:
predicted = mean(historical_values)
confidence = 1 - (std / mean)  # Higher if consistent
margin = 1.96 * std / sqrt(n)  # 95% confidence interval
```

**When used**: Workloads with consistent load patterns (e.g., internal APIs, batch processors)

### 2. Trend Model (Linear Regression)
Best for: **Growing/Declining workloads** with clear directional trends

```python
# Algorithm:
slope, intercept = linear_regression(x=time, y=cpu_values)
predicted = intercept + slope * future_time
confidence = R² * (1 - window_penalty)
```

**When used**: Services experiencing growth or decline over time

### 3. Seasonal Model
Best for: **Periodic workloads** with daily/weekly patterns

```python
# Algorithm:
patterns[day_of_week][hour] = mean(historical_values_at_same_time)
predicted = patterns[target_day][target_hour]
confidence = sample_count / 10  # More samples = higher confidence
```

**When used**: Business applications with predictable daily cycles (e.g., 9-5 traffic)

### 4. Holt-Winters (Exponential Smoothing)
Best for: **Seasonal + Trend** workloads

```python
# Algorithm (statsmodels):
model = ExponentialSmoothing(
    data,
    seasonal_periods=24,  # Daily or 168 for weekly
    trend='add',
    seasonal='add',
    damped_trend=True
)
predicted = model.forecast(steps)
confidence = 1 - (RMSE / mean)
```

**When used**: Complex workloads with both trend and seasonality

### 5. ARIMA (AutoRegressive Integrated Moving Average)
Best for: **Complex time series** patterns

```python
# Algorithm (statsmodels):
model = ARIMA(data, order=(1, 1, 1))  # AR=1, I=1, MA=1
predicted = model.forecast(steps)
confidence = based on AIC score
```

**When used**: Workloads with autocorrelation and complex dependencies

### 6. Prophet-like Decomposition
Best for: **Multi-seasonal** workloads (daily + weekly patterns)

```python
# Algorithm:
# 1. Extract trend using moving average
trend = moving_average(data, window=24)

# 2. Extract weekly seasonality
weekly_seasonal[dow][hour] = mean(detrended[same_dow_hour])

# 3. Extract daily seasonality  
daily_seasonal[hour] = mean(detrended[same_hour] - weekly)

# 4. Combine for prediction
predicted = trend + weekly_seasonal + daily_seasonal
```

**When used**: Enterprise applications with both daily and weekly patterns

### 7. Ensemble Model
Best for: **Unknown patterns** or when no single model dominates

```python
# Algorithm:
predictions = [mean_pred, trend_pred, seasonal_pred, ...]
weights = [historical_accuracy * confidence for each model]
ensemble = weighted_average(predictions, weights)
```

**When used**: Default for complex or unclear workload patterns

## Model Selection Logic

The system automatically selects the best model based on:

```python
def select_best_model(deployment, values, timestamps):
    n_samples = len(values)
    cv = std / mean  # Coefficient of variation
    
    # Check historical performance first
    if best_historical_model and accuracy > 70%:
        return best_historical_model
    
    # Analyze data characteristics
    if n_samples < 20:
        return MEAN  # Not enough data
    
    if cv < 0.1:  # Very steady
        return MEAN
    
    if has_weekly_seasonality or has_daily_seasonality:
        if n_samples >= 168:
            return PROPHET_LIKE
        elif n_samples >= 48:
            return HOLT_WINTERS
        else:
            return SEASONAL
    
    if has_trend:
        if n_samples >= 100:
            return ARIMA
        else:
            return TREND
    
    if n_samples >= 50:
        return ENSEMBLE
    
    return TREND
```

## Prediction Windows

| Window | Minutes | Use Case |
|--------|---------|----------|
| **15min** | 15 | Immediate response, fast-changing workloads |
| **30min** | 30 | Short-term capacity planning |
| **1hr** | 60 | Standard predictive scaling (default) |
| **2hr** | 120 | Medium-term planning |
| **4hr** | 240 | Long-term trend analysis |

## Confidence Calculation

Confidence is calculated based on multiple factors:

```python
base_confidence = min(0.9, sample_count / 100)
window_penalty = 1 - (minutes_ahead / 480)  # Longer = less confident
model_accuracy = historical_accurate / historical_total
final_confidence = base_confidence * window_penalty * model_accuracy
```

## Workload Pattern Detection

### Pattern Types

| Pattern | CV Range | Characteristics | Strategy |
|---------|----------|-----------------|----------|
| **Steady** | < 15% | Consistent load | Mean model, conservative scaling |
| **Bursty** | > 50% | Frequent spikes | Recent average, fast scale-up |
| **Periodic** | 15-50% | Daily/weekly cycles | Seasonal model, predictive enabled |
| **Growing** | - | Upward trend > 20% | Trend model, maintain headroom |
| **Declining** | - | Downward trend > 20% | Trend model, optimize costs |
| **Weekly Seasonal** | - | Weekday ≠ Weekend | Weekly patterns, predictive enabled |
| **Monthly Seasonal** | - | Month-end spikes | Monthly patterns, predictive enabled |
| **Event-Driven** | - | Spike-decay patterns | Fast response, no prediction |

### Detection Algorithm

```python
def detect_pattern(deployment, hours=24):
    metrics = get_recent_metrics(deployment, hours)
    cpu_values = [m.pod_cpu_usage for m in metrics]
    
    mean = statistics.mean(cpu_values)
    std = statistics.stdev(cpu_values)
    cv = std / mean
    
    # 1. Check for steady (low variance)
    if cv < 0.15:
        return STEADY
    
    # 2. Check for bursty (high variance with spikes)
    if cv > 0.5:
        spike_rate = count_spikes(cpu_values, threshold=mean + 2*std)
        if spike_rate > 10%:
            return BURSTY
    
    # 3. Check for weekly pattern
    if has_weekday_weekend_difference(metrics, threshold=20%):
        return WEEKLY_SEASONAL
    
    # 4. Check for monthly pattern
    if has_month_end_spikes(metrics, threshold=25%):
        return MONTHLY_SEASONAL
    
    # 5. Check for event-driven
    if has_spike_decay_patterns(metrics):
        return EVENT_DRIVEN
    
    # 6. Check for periodic (autocorrelation)
    if autocorrelation_at_daily_lag > 0.5:
        return PERIODIC
    
    # 7. Check for trend
    trend = detect_trend(cpu_values)
    if trend == "growing":
        return GROWING
    elif trend == "declining":
        return DECLINING
    
    return STEADY  # Default
```

## TRUE Pre-Scaling

Unlike traditional predictive scaling that only adjusts HPA targets, TRUE pre-scaling directly patches HPA minReplicas:

```python
def calculate_required_replicas(current_replicas, current_cpu, predicted_cpu, target_cpu):
    """
    Formula: required = current_replicas * (predicted_cpu / target_cpu)
    
    Example:
    - Current: 3 pods at 50% CPU, target 70%
    - Predicted: 90% CPU in 1 hour
    - Required: 3 * (90 / 70) = 3.86 → 4 pods
    """
    scale_factor = predicted_cpu / target_cpu
    scale_factor = clamp(scale_factor, min=0.5, max=3.0)  # Safety limits
    required = ceil(current_replicas * scale_factor)
    return clamp(required, min_replicas, max_replicas)
```

## Model Performance Tracking

The system tracks performance for each model:

```python
class ModelPerformance:
    total_predictions: int
    accurate_predictions: int  # Within 15% error
    mape: float  # Mean Absolute Percentage Error
    rmse: float  # Root Mean Square Error
    last_updated: datetime

def validate_prediction(deployment, predicted, actual, model_used):
    error = abs(predicted - actual)
    pct_error = error / actual * 100
    
    perf = model_performance[deployment][model_used]
    perf.total_predictions += 1
    
    if pct_error < 15:  # Accurate if within 15%
        perf.accurate_predictions += 1
    
    # Update rolling MAPE
    perf.mape = rolling_average(perf.mape, pct_error)
    
    # Update rolling RMSE
    perf.rmse = sqrt(rolling_average(perf.rmse², error²))
```

## API Endpoints

### Get Advanced Predictions
```bash
GET /api/predictions/advanced/{deployment}
```

Response:
```json
{
  "deployment": "trading-api",
  "predictions": {
    "15min": {"predicted": 72.5, "confidence": 85.2, "model": "ensemble"},
    "30min": {"predicted": 78.3, "confidence": 80.1, "model": "prophet_like"},
    "1hr": {"predicted": 85.2, "confidence": 78.5, "model": "prophet_like"},
    "2hr": {"predicted": 82.1, "confidence": 65.3, "model": "trend"},
    "4hr": {"predicted": 75.8, "confidence": 52.1, "model": "trend"}
  },
  "best_model": "prophet_like",
  "prediction_quality": "good"
}
```

### Get Model Performance
```bash
GET /api/predictions/models/{deployment}
```

Response:
```json
{
  "model_performance": {
    "mean": {"accuracy_rate": 72.5, "mape": 12.3, "rmse": 8.5},
    "prophet_like": {"accuracy_rate": 85.3, "mape": 8.7, "rmse": 5.8}
  },
  "best_model": "prophet_like"
}
```

### Get Scaling Recommendation
```bash
GET /api/predictions/scaling-recommendation/{deployment}
```

Response:
```json
{
  "action": "pre_scale_up",
  "current_replicas": 3,
  "recommended_replicas": 5,
  "reason": "Predicted 85.2% CPU in 1hr. Pre-scaling from 3 to 5 pods NOW.",
  "predicted_cpu": 85.2,
  "confidence": 78.5
}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_PREDICTIVE` | `true` | Enable predictive scaling |
| `PREDICTION_MIN_ACCURACY` | `0.60` | Minimum accuracy to trust predictions |
| `PREDICTION_MIN_SAMPLES` | `10` | Minimum predictions before trusting |
| `ENABLE_PRESCALE` | `true` | Enable TRUE pre-scaling |
| `PRESCALE_MIN_CONFIDENCE` | `0.7` | Minimum confidence to pre-scale |
| `PRESCALE_THRESHOLD` | `75.0` | CPU % threshold to trigger pre-scale |

### Tuning for Your Workload

**Fintech (Low Latency Critical)**:
```yaml
ENABLE_PREDICTIVE: "true"
PREDICTION_MIN_ACCURACY: "0.50"  # Trust predictions sooner
PRESCALE_MIN_CONFIDENCE: "0.6"   # More aggressive pre-scaling
PRESCALE_THRESHOLD: "70.0"       # Lower threshold
```

**Cost-Sensitive**:
```yaml
ENABLE_PREDICTIVE: "true"
PREDICTION_MIN_ACCURACY: "0.75"  # Higher accuracy required
PRESCALE_MIN_CONFIDENCE: "0.8"   # Conservative pre-scaling
PRESCALE_THRESHOLD: "80.0"       # Higher threshold
```

## Best Practices

### 1. Data Collection Period
- **Week 1**: System collects data, no predictions
- **Week 2**: Pattern detection begins, low confidence
- **Week 3+**: High confidence, accurate predictions

### 2. Monitor Accuracy
```bash
# Check weekly
curl /api/predictions/models/my-deployment | jq '.model_performance'
```

Target: **>80% accuracy** for production use

### 3. Model Selection
- Let the system auto-select models initially
- Monitor which models perform best for your workload
- The system will automatically favor better-performing models

### 4. Confidence Thresholds
- Start with defaults (70% confidence)
- If too many false positives: increase threshold
- If missing spikes: decrease threshold

## Troubleshooting

### Low Prediction Accuracy

**Cause**: Workload is too random or data is insufficient

**Solution**:
1. Check pattern type: `curl /api/ai/insights/{deployment}`
2. If "bursty", predictions may not work well
3. Wait for more data (2+ weeks)
4. Consider using priority-based scaling instead

### Predictions Not Triggering

**Cause**: Confidence below threshold

**Solution**:
1. Check confidence: `curl /api/predictions/advanced/{deployment}`
2. Lower `PRESCALE_MIN_CONFIDENCE` if needed
3. Ensure enough historical data exists

### Wrong Model Selected

**Cause**: Workload characteristics changed

**Solution**:
1. Clear pattern cache: The system will re-detect
2. Check model performance: `curl /api/predictions/models/{deployment}`
3. The system will adapt over time

## Summary

The ML prediction system provides:

✅ **7 prediction models** for different workload types
✅ **Automatic model selection** based on workload characteristics
✅ **5 prediction windows** (15min to 4hr)
✅ **Confidence intervals** for all predictions
✅ **Performance tracking** and adaptive learning
✅ **TRUE pre-scaling** via HPA minReplicas
✅ **ArgoCD compatible** with proper configuration

The system learns and improves over time, automatically selecting the best models for each deployment based on historical accuracy.
