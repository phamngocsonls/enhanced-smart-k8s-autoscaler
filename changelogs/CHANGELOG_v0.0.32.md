# Changelog v0.0.32

**Release Date:** January 7, 2026

## Advanced Predictive Scaling with ML Models + TRUE Pre-Scaling

This release introduces a sophisticated ML-based prediction system with multiple models, adaptive selection, and confidence intervals. **Most importantly**, it adds TRUE pre-scaling capability by dynamically adjusting HPA minReplicas based on predictions.

### 🚀 Highlight: TRUE Pre-Scaling via HPA minReplicas

Unlike traditional predictive scaling that only adjusts HPA target CPU (which doesn't guarantee more pods), this release implements **TRUE pre-scaling**:

1. **Predict spike** → ML models predict CPU spike in 15-60 minutes
2. **Store original** → Save original HPA minReplicas (from Git/ArgoCD)
3. **Patch HPA** → Increase minReplicas to force immediate scale-up
4. **Pods ready** → New pods are running BEFORE traffic arrives
5. **Auto-rollback** → After peak passes or timeout, restore original minReplicas

**ArgoCD Compatible**: If you disable auto-sync for HPA resources, the operator can safely patch minReplicas without ArgoCD reverting the changes.

### 🖥️ Dashboard Enhancements

#### Cluster Tab Improvements
- **Kubernetes Version Display**: Shows cluster version (e.g., v1.28.5), platform info
- **Cloud Provider Detection**: Automatically detects GCP/AWS/Azure/Local/On-Premise
- **Improved Health Display**: Shows CPU and memory utilization with health badge

### 📚 Documentation

- **NEW**: `docs/ML_PREDICTION_GUIDE.md` - Comprehensive ML prediction documentation
  - Complete architecture overview
  - All 7 prediction models explained with algorithms
  - Model selection logic
  - Workload pattern detection
  - Configuration and tuning guide
  - Troubleshooting section

### 🗄️ Database Auto-Cleanup & Self-Healing

- **Configurable Retention**: Set retention periods via environment variables
  - `METRICS_RETENTION_DAYS` (default: 30)
  - `PREDICTIONS_RETENTION_DAYS` (default: 30)
  - `ANOMALIES_RETENTION_DAYS` (default: 90)
- **Periodic Cleanup**: Automatic cleanup every `DB_CLEANUP_INTERVAL_HOURS` (default: 6)
- **Auto VACUUM**: Reclaims disk space when significant data is deleted
- **Database Stats Logging**: Logs row counts and file size after cleanup

### 🛡️ Disk Space Auto-Healing with Smart Cleanup (NEW)

Automatically detects PVC/disk usage and triggers **smart self-healing cleanup** that preserves prediction patterns:

| Threshold | Level | Action |
|-----------|-------|--------|
| **80%** | Warning | Logs warning, suggests increasing PVC |
| **90%** | Critical | Smart downsample: keep 2-hourly averages for data >14 days |
| **95%** | Emergency | Aggressive smart cleanup: keep 1-hourly averages, preserve 168 weekly pattern slots |

**Smart Cleanup Strategy (preserves ML prediction accuracy):**

1. **Smart Downsampling** (`_smart_downsample_metrics`):
   - Keeps recent data at full granularity
   - Aggregates older data to hourly averages
   - Preserves patterns while reducing volume by 60-90%

2. **Redundant Prediction Cleanup** (`_cleanup_redundant_predictions`):
   - Keeps validated predictions (for accuracy tracking)
   - Keeps one prediction per hour per deployment
   - Removes duplicate/redundant predictions

3. **Aggressive Smart Cleanup** (`_aggressive_smart_cleanup`):
   - Preserves weekly patterns: keeps 4 samples per (day_of_week, hour) slot
   - Ensures 168 minimum slots (7 days × 24 hours) for pattern recognition
   - Keeps all data from last 3 days for recent patterns

**Why Smart Cleanup?**
- Traditional cleanup (delete data >X days) breaks ML predictions
- Predictions need historical patterns for each hour of each day-of-week
- Smart cleanup preserves representative samples while freeing disk space

**Configuration:**
```bash
DISK_WARNING_THRESHOLD=0.80   # 80%
DISK_CRITICAL_THRESHOLD=0.90  # 90%
DISK_EMERGENCY_THRESHOLD=0.95 # 95%
```

**New API Endpoint:**
```bash
GET /api/database/status
```

Response:
```json
{
  "disk": {
    "status": "healthy",
    "percent_used": 45.2,
    "total_gb": 10.0,
    "free_gb": 5.48
  },
  "database": {
    "size_mb": 125.5,
    "metrics_count": 50000,
    "predictions_count": 1200
  },
  "auto_healing": {
    "enabled": true,
    "warning_threshold": "80%",
    "critical_threshold": "90%",
    "emergency_threshold": "95%"
  }
}
```

### New Features

#### 1. Pre-Scale Manager (`src/prescale_manager.py`)

| Feature | Description |
|---------|-------------|
| **Original Storage** | Stores original HPA minReplicas on first read |
| **Smart Patching** | Patches minReplicas when spike is predicted |
| **Auto-Rollback** | Restores original after peak or timeout (default 60min) |
| **Cooldown** | Prevents rapid pre-scale/rollback cycles (default 15min) |
| **Dashboard Visibility** | Shows original vs current minReplicas, state, predictions |

#### 2. Advanced Predictor Module (`src/advanced_predictor.py`)

Multiple prediction models for different workload types:

| Model | Best For | Description |
|-------|----------|-------------|
| **Mean** | Steady workloads | Historical average with confidence intervals |
| **Trend** | Growing/declining | Linear regression extrapolation |
| **Seasonal** | Daily/weekly patterns | Hour-of-day and day-of-week patterns |
| **Holt-Winters** | Seasonal + trend | Exponential smoothing with seasonality |
| **ARIMA** | Complex patterns | Time series forecasting (ARIMA 1,1,1) |
| **Prophet-like** | Multi-seasonal | Trend + weekly + daily decomposition |
| **Ensemble** | Unknown patterns | Weighted combination of all models |

#### 3. Multiple Prediction Windows

- **15min** - Immediate response planning
- **30min** - Short-term capacity planning
- **1hr** - Standard predictive scaling
- **2hr** - Medium-term planning
- **4hr** - Long-term trend analysis

#### 4. Confidence Intervals

Every prediction includes:
- Predicted value
- Confidence score (0-100%)
- Lower/upper bounds (95% confidence interval)
- Model used and reasoning

### New API Endpoints

#### Pre-Scale Management

| Endpoint | Description |
|----------|-------------|
| `GET /api/prescale/summary` | Overview of all pre-scale states |
| `GET /api/prescale/profiles` | All registered deployment profiles |
| `GET /api/prescale/<ns>/<dep>` | Pre-scale profile for specific deployment |
| `POST /api/prescale/<ns>/<dep>/force` | Force pre-scale (body: `{new_min_replicas: N}`) |
| `POST /api/prescale/<ns>/<dep>/rollback` | Force rollback to original minReplicas |
| `POST /api/prescale/<ns>/<dep>/register` | Register deployment for pre-scaling |

#### Advanced Predictions

| Endpoint | Description |
|----------|-------------|
| `GET /api/predictions/advanced/<deployment>` | Get predictions from all windows with model info |
| `GET /api/predictions/advanced/<deployment>/<window>` | Get prediction for specific window |
| `GET /api/predictions/models/<deployment>` | Get model performance statistics |
| `GET /api/predictions/scaling-recommendation/<deployment>` | Get HPA adjustment recommendation |

### Example: Pre-Scale Profile Response

```bash
curl http://localhost:5000/api/prescale/default/my-app | jq
```

```json
{
  "namespace": "default",
  "deployment": "my-app",
  "hpa_name": "my-app-hpa",
  "original_min_replicas": 2,
  "original_max_replicas": 10,
  "current_min_replicas": 5,
  "state": "pre_scaling",
  "pre_scale_started": "2026-01-06T10:30:00",
  "pre_scale_reason": "Predicted 85.2% CPU in 30min",
  "predicted_cpu": 85.2,
  "prediction_confidence": 0.82,
  "prediction_window": "30min",
  "rollback_at": "2026-01-06T11:30:00",
  "pre_scale_count": 3,
  "successful_predictions": 2,
  "failed_predictions": 1
}
```

### Configuration

New environment variables for pre-scale management:

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_PRESCALE` | `true` | Enable/disable pre-scaling |
| `PRESCALE_MIN_CONFIDENCE` | `0.7` | Minimum prediction confidence to act |
| `PRESCALE_THRESHOLD` | `75.0` | CPU % threshold to trigger pre-scale |
| `PRESCALE_ROLLBACK_MINUTES` | `60` | Auto-rollback after this many minutes |
| `PRESCALE_COOLDOWN_MINUTES` | `15` | Cooldown between pre-scale actions |

### Files Added/Modified

**New Files:**
- `src/prescale_manager.py` - Pre-scale management module (500+ lines)
- `src/advanced_predictor.py` - Advanced prediction module (700+ lines)
- `tests/test_prescale_manager.py` - 16 comprehensive tests
- `tests/test_advanced_predictor.py` - 31 comprehensive tests

**Modified Files:**
- `src/integrated_operator.py` - Integrated PreScaleManager
- `src/dashboard.py` - Added 12 new API endpoints
- `docs/PREDICTIVE_SCALING.md` - Updated documentation

### Testing

All tests pass:
```
tests/test_prescale_manager.py - 16 tests PASSED
tests/test_advanced_predictor.py - 31 tests PASSED
```

### Upgrade Instructions

```bash
# Update to v0.0.32
kubectl set image deployment/smart-autoscaler \
  smart-autoscaler=ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:0.0.32

# Test pre-scale status
curl http://localhost:5000/api/prescale/summary

# Test advanced predictions
curl http://localhost:5000/api/predictions/advanced/my-deployment
```

### ArgoCD Integration

If using ArgoCD, you have two options:

1. **Disable auto-sync for HPA** (recommended):
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

2. **Use annotation-based exclusion**:
   ```yaml
   metadata:
     annotations:
       argocd.argoproj.io/sync-options: Prune=false
   ```

### Backward Compatibility

- All existing APIs continue to work unchanged
- New endpoints are additive
- Pre-scaling is enabled by default but can be disabled
- Falls back gracefully if ML libraries not available
