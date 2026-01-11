# Changelog v0.0.37

## Release Date: 2026-01-11

## 🚀 Highlights

- **Learning Mode**: Autopilot now observes new deployments before making recommendations
- **Per-Deployment Learning**: Each deployment has its own learning profile with progress tracking
- **Dashboard Visibility**: Shows "Learning: Day X of Y" for each deployment

---

## New Features

### 📚 Autopilot Learning Mode

New deployments now enter a learning phase before autopilot makes recommendations:

| Feature | Description |
|---------|-------------|
| Per-Deployment Tracking | Each deployment has its own learning profile |
| Progress Visibility | Dashboard shows "Learning: Day 3 of 7 (42%)" |
| Baseline Calculation | P95 baselines calculated from collected samples |
| Auto-Graduate | Automatically moves to recommendations after learning |
| Webhook Notifications | Alerts when learning starts and completes |

**How it works:**
1. New deployment detected → Learning starts automatically
2. Metrics collected during learning period (default: 7 days)
3. Baselines calculated from samples
4. Deployment graduates to active recommendations
5. Webhook notification sent

### Learning States

| State | Description |
|-------|-------------|
| `NOT_STARTED` | Learning not yet started |
| `LEARNING` | Currently collecting metrics |
| `COMPLETED` | Learning finished, baselines calculated |
| `GRADUATED` | Ready for active recommendations |

---

## Configuration

### New Environment Variables

```bash
# Learning Mode (all optional, shown with defaults)
AUTOPILOT_ENABLE_LEARNING_MODE=true
AUTOPILOT_LEARNING_DAYS=7
AUTOPILOT_AUTO_GRADUATE=true
```

---

## API Updates

### New Endpoint: `/api/autopilot/learning`

```json
{
  "enabled": true,
  "learning_days": 7,
  "auto_graduate": true,
  "deployments": [
    {
      "namespace": "default",
      "deployment": "my-app",
      "state": "LEARNING",
      "days_in_learning": 3,
      "days_remaining": 4,
      "progress_percent": 42.8,
      "samples_collected": 72,
      "baseline_cpu_p95": null,
      "baseline_memory_p95": null
    }
  ],
  "summary": {
    "total": 1,
    "learning": 1,
    "completed": 0,
    "graduated": 0
  }
}
```

### New Endpoint: `/api/autopilot/<namespace>/<deployment>/reset-learning`

Reset learning for a deployment to start over.

### `/api/autopilot/status` - New Fields

```json
{
  "learning_mode": {
    "enabled": true,
    "learning_days": 7,
    "auto_graduate": true,
    "deployments_learning": 1,
    "deployments_completed": 0,
    "deployments_graduated": 0
  },
  "learning_deployments": [...]
}
```

---

## Files Changed

| File | Changes |
|------|---------|
| `src/autopilot.py` | Learning mode implementation |
| `src/dashboard.py` | Learning API endpoints |
| `tests/test_autopilot.py` | +22 new tests for learning mode |
| `.env.example` | New learning env vars |
| `docs/AUTOPILOT.md` | Learning mode documentation |

---

## Test Results

- **313 tests passing** (1 pre-existing failure unrelated)
- **22 new tests** for learning mode functionality
- **Coverage: 33%**

---

## Upgrade Notes

1. ✅ Learning mode enabled by default - no action needed
2. ✅ Existing deployments will start learning on first metric collection
3. ⚠️ Recommendations blocked during learning phase (7 days default)
4. 📝 Set `AUTOPILOT_ENABLE_LEARNING_MODE=false` to disable if needed
