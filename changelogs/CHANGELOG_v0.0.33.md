# Changelog v0.0.33

## Release Date: 2026-01-10

## 🚀 New Feature: Autopilot Mode - Automatic Resource Tuning

This release introduces **Autopilot Mode**, an enterprise-grade feature for automatic resource tuning inspired by StormForge. Autopilot automatically optimizes CPU and memory **requests** based on observed P95 usage patterns.

### Key Features

- **Requests Only**: Only tunes resource requests, NOT limits (as requested)
- **Disabled by Default**: Must be explicitly enabled for safety
- **4 Automation Levels**: disabled, observe, recommend, autopilot
- **Safety Guardrails**: Multiple safety checks prevent over-optimization
- **HPA Compatible**: Works smoothly with Horizontal Pod Autoscaler
- **Audit Logging**: All changes are tracked for compliance
- **Rollback Support**: Easy rollback if issues occur

### Configuration

```bash
# Enable autopilot (disabled by default)
ENABLE_AUTOPILOT=false

# Automation level
AUTOPILOT_LEVEL=recommend  # disabled, observe, recommend, autopilot

# Safety settings
AUTOPILOT_MIN_CONFIDENCE=0.80      # Min confidence to apply
AUTOPILOT_MAX_CHANGE_PERCENT=30    # Max change per iteration
AUTOPILOT_COOLDOWN_HOURS=24        # Hours between changes
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/autopilot/status` | GET | Get autopilot status and config |
| `/api/autopilot/recommendations` | GET | Get current recommendations |
| `/api/autopilot/actions` | GET | Get applied changes history |
| `/api/autopilot/{ns}/{dep}/apply` | POST | Manually apply recommendation |
| `/api/autopilot/{ns}/{dep}/rollback` | POST | Rollback last change |

### Safety Guardrails

1. **Minimum Observation Period**: 7 days of data required
2. **Confidence Threshold**: Only applies changes with ≥80% confidence
3. **Maximum Change Limit**: Limits changes to 30% per iteration
4. **Cooldown Period**: 24-hour cooldown between changes
5. **Priority-Based Safety**: Critical priority requires manual approval
6. **Minimum Values**: CPU ≥50m, Memory ≥64Mi

### Files Changed

#### New Files
- `src/autopilot.py` - Core autopilot module
- `tests/test_autopilot.py` - 29 unit tests
- `docs/AUTOPILOT.md` - Comprehensive documentation

#### Modified Files
- `src/integrated_operator.py` - Autopilot integration in main loop
- `src/intelligence.py` - Added `get_observation_days()`, `get_p95_metrics()`
- `src/dashboard.py` - Added 5 API endpoints
- `.env.example` - Added autopilot environment variables
- `k8s/configmap.yaml` - Added autopilot config
- `helm/smart-autoscaler/values.yaml` - Added autopilot helm values
- `helm/smart-autoscaler/templates/deployment.yaml` - Added autopilot env vars
- `QUICK_REFERENCE.md` - Added autopilot quick reference
- `tests/test_intelligence.py` - Added tests for new database methods

### Test Results

- **Total Tests**: 278 passing
- **New Tests**: 33 (29 autopilot + 4 intelligence)
- **Coverage**: 34% (above 25% minimum)

### Upgrade Notes

1. This feature is **disabled by default** - no action required for existing deployments
2. To enable, set `ENABLE_AUTOPILOT=true` in your ConfigMap or environment
3. Start with `AUTOPILOT_LEVEL=recommend` to review recommendations before auto-applying
4. See `docs/AUTOPILOT.md` for detailed configuration guide

### Documentation

- [Autopilot Guide](docs/AUTOPILOT.md) - Full documentation
- [Quick Reference](QUICK_REFERENCE.md) - Quick configuration reference
