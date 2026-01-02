# Changelog v0.0.21

**Release Date:** 2026-01-02

## 🛡️ HPA Behavior Analysis & Safe Scaling

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

### Response Structure
```json
{
  "hpa_config": {
    "name": "demo-app-hpa",
    "min_replicas": 2,
    "max_replicas": 20,
    "target_cpu_percent": 75,
    "behavior": {
      "scale_up": { "stabilization_window_seconds": 60, ... },
      "scale_down": { "stabilization_window_seconds": 300, ... }
    }
  },
  "scaling_frequency": {
    "events_24h": 15,
    "events_1h": 2,
    "is_flapping": false
  },
  "analysis": {
    "risk_level": "low",
    "issues": [],
    "recommendations": [],
    "yaml_snippet": "# Ready-to-apply YAML...",
    "summary": "✅ HPA behavior is well-configured for safe scaling."
  }
}
```

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
- `src/pattern_detector.py` - Updated HPA targets for all patterns

## API Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/deployment/<ns>/<dep>/hpa-analysis` | GET | HPA behavior analysis with recommendations |
