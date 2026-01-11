# Changelog v0.0.36

## Release Date: 2026-01-11

## 🚀 Highlights

- **Auto-Rollback**: Autopilot now automatically reverts changes if health degrades
- **Smart Feature Coordination**: All features work together intelligently
- **Dashboard Fixes**: Fixed Teams and Google Chat provider icons

---

## New Features

### 🔄 Autopilot Auto-Rollback

Automatic safety net that monitors deployment health after autopilot applies changes:

| Trigger | Default | Description |
|---------|---------|-------------|
| Pod Restarts | +2 | Rollback if restarts increase by more than 2 |
| OOMKills | +1 | Rollback if any OOMKill detected |
| Readiness Drop | 20% | Rollback if ready replicas drop by more than 20% |

**How it works:**
1. Snapshot current state before changes
2. Apply resource changes
3. Monitor health for 10 minutes (configurable)
4. Auto-rollback if issues detected
5. Send webhook notification

### 🧠 Smart Feature Coordination

Features now coordinate intelligently:

| Coordination | Behavior |
|--------------|----------|
| Pre-Scale + Autopilot | Autopilot skips resource reduction during predicted spikes |
| Priority + Pre-Scale | Critical deployments pre-scale at 60% confidence (vs 70%) |
| Priority + Autopilot | Critical/high priority requires manual approval for large changes |

**Priority-based Pre-Scale Confidence:**
```
critical    → 60% (more aggressive)
high        → 65%
medium      → 70% (default)
low         → 75%
best_effort → 80% (more conservative)
```

### 🎨 Dashboard Icon Fixes

- Fixed Microsoft Teams logo (official purple T icon)
- Fixed Google Chat logo in modal (green chat bubble)

---

## Configuration

### New Environment Variables

```bash
# Auto-Rollback (all optional, shown with defaults)
AUTOPILOT_ENABLE_AUTO_ROLLBACK=true
AUTOPILOT_ROLLBACK_MONITOR_MINUTES=10
AUTOPILOT_MAX_RESTART_INCREASE=2
AUTOPILOT_MAX_OOM_INCREASE=1
AUTOPILOT_MAX_READINESS_DROP_PERCENT=20
```

---

## API Updates

### `/api/autopilot/status` - New Fields

```json
{
  "rollback_config": {
    "enabled": true,
    "monitor_minutes": 10,
    "max_restart_increase": 2,
    "max_oom_increase": 1,
    "max_readiness_drop_percent": 20.0
  },
  "statistics": {
    "auto_rollbacks": 0
  },
  "pending_health_monitors": [],
  "recent_auto_rollbacks": []
}
```

---

## Files Changed

| File | Changes |
|------|---------|
| `src/autopilot.py` | Auto-rollback, health monitoring, snapshots |
| `src/integrated_operator.py` | Smart feature coordination |
| `src/prescale_manager.py` | Priority-based confidence adjustment |
| `templates/dashboard.html` | Fixed Teams/Google Chat icons |
| `tests/test_autopilot.py` | +12 new tests |
| `.env.example` | New rollback env vars |
| `docs/AUTOPILOT.md` | Updated documentation |
| `docs/FEATURE_COORDINATION.md` | New documentation |

---

## Test Results

- **291 tests passing** (1 pre-existing failure unrelated)
- **12 new tests** for rollback functionality
- **Coverage: 34%**

---

## Upgrade Notes

1. ✅ Auto-rollback enabled by default - no action needed
2. ✅ Existing configurations continue to work
3. ⚠️ New webhook notifications for auto-rollbacks
4. 📝 Review `AUTOPILOT_MAX_*` thresholds for your environment
