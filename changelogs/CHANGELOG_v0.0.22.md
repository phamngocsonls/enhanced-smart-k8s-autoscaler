# Changelog v0.0.22

**Release Date:** 2026-01-03

## 🛡️ HPA Behavior Analysis & Safe Scaling

### New Dashboard Tab: HPA Analysis
- Visual display of current HPA behavior config
- Scale-up and scale-down settings breakdown
- Scaling frequency monitoring (events per hour/day)
- Flapping detection indicator
- Risk level assessment (low/medium/high)
- Issues and recommendations display
- Ready-to-copy YAML snippet for safe scaling config

### New API Endpoint
- `/api/deployment/<ns>/<dep>/hpa-analysis` - Comprehensive HPA behavior analysis
  - Reads HPA `behavior.scaleUp` and `behavior.scaleDown` config
  - Analyzes stabilization windows and scaling policies
  - Detects flapping (high scaling frequency)
  - Provides risk assessment (low/medium/high)
  - Generates ready-to-apply YAML for safe scaling

### Analysis Features
- **Flapping Detection**: Alerts when >5 scale events/hour or >20 events/24h
- **Stabilization Analysis**: Checks if windows are appropriate for workload pattern
- **Policy Analysis**: Identifies aggressive scale-up/down policies
- **Missing Behavior Detection**: Warns when no behavior config (uses risky K8s defaults)
- **Low CPU + Low Target Warning**: Detects unstable combinations

## 🔔 Enhanced Alert System

### New Alert Types
| Alert Type | Severity | Description |
|------------|----------|-------------|
| `cpu_spike` | warning/critical | Unusual CPU increase (>3 std dev) |
| `scaling_thrashing` | warning | Too many scale events (>15 in 30min) |
| `high_memory` | warning/critical | Memory utilization >90% (OOM risk) |
| `low_efficiency` | info | Resource efficiency <20% (wasted resources) |
| `low_confidence` | info | Prediction confidence <50% |

### Dashboard Improvements
- Alert types legend in Alerts tab
- Color-coded severity indicators
- Detailed alert cards with metrics

## 📊 Pattern Detector HPA Target Updates

Raised default HPA targets across all patterns for better stability with low CPU requests:

| Pattern | Old Target | New Target |
|---------|------------|------------|
| BURSTY | 60% | 70% |
| EVENT_DRIVEN | 60% | 70% |
| GROWING | 65% | 75% |
| MONTHLY_SEASONAL | 65% | 75% |
| WEEKLY_SEASONAL | 68% | 75% |
| STEADY | 70% | 75% |
| PERIODIC | 70% | 75% |
| UNKNOWN | 70% | 75% |
| DECLINING | 75% | 80% |

**Rationale**: Lower targets (60-65%) with low CPU requests (<150m) cause frequent scaling on small fluctuations. The 70-80% range provides better stability while still being responsive.

## Files Changed
- `src/__init__.py` - Version bump to 0.0.21
- `src/dashboard.py` - Added HPA analysis endpoint and helper methods
- `src/intelligence.py` - Added new alert types (high_memory, low_efficiency, low_confidence)
- `src/pattern_detector.py` - Updated HPA targets for all patterns
- `templates/dashboard.html` - Added HPA Analysis tab, alert types legend

## API Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/deployment/<ns>/<dep>/hpa-analysis` | GET | HPA behavior analysis with recommendations |
