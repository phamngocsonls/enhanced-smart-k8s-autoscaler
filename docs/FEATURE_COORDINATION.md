# Feature Coordination - Smart Integration

This document explains how all Smart Autoscaler features work together intelligently.

## Feature Overview

| Feature | What It Does | Scope |
|---------|--------------|-------|
| **Pattern Detection** | Identifies workload patterns (steady, bursty, periodic) | HPA target adjustment |
| **Priority Manager** | Adjusts scaling based on deployment importance | HPA target, pre-scale aggressiveness |
| **Predictive Scaling** | Predicts future CPU/memory usage | HPA target hints |
| **Pre-Scale** | Adjusts HPA minReplicas before predicted spikes | HPA minReplicas |
| **Autopilot** | Auto-tunes container resource requests | Pod requests (CPU/Memory) |
| **Auto-Rollback** | Reverts changes if health degrades | Autopilot safety net |

## Smart Coordination

### 1. Priority → Pre-Scale Coordination

Pre-scale aggressiveness is adjusted based on deployment priority:

```
Priority Level    Confidence Adjustment    Effective Threshold
─────────────────────────────────────────────────────────────
critical          -10%                     60% (more aggressive)
high              -5%                      65%
medium            0%                       70% (default)
low               +5%                      75%
best_effort       +10%                     80% (more conservative)
```

**Why?** Critical deployments should pre-scale earlier to ensure availability, while best-effort workloads can wait for higher confidence to save costs.

### 2. Pre-Scale → Autopilot Coordination

Autopilot checks if pre-scale is active before reducing resources:

```
IF pre-scale is active for deployment:
    IF autopilot wants to REDUCE resources:
        → SKIP reduction (predicted spike in progress)
    ELSE IF autopilot wants to INCREASE resources:
        → ALLOW increase (helps handle spike)
```

**Why?** Reducing CPU/memory requests during a predicted traffic spike could cause throttling or OOMs.

### 3. Priority → Autopilot Coordination

Autopilot respects priority levels for safety:

```
Priority Level    Autopilot Behavior
─────────────────────────────────────
critical          Manual approval required for all changes
high              Manual approval for changes >15%
medium            Auto-apply safe changes
low               Auto-apply safe changes
best_effort       Auto-apply safe changes
```

**Why?** Critical workloads (payment, auth) need human oversight before resource changes.

### 4. Pattern → HPA Target Coordination

Pattern detection adjusts HPA targets based on workload behavior:

```
Pattern     HPA Target    Scale Speed    Description
────────────────────────────────────────────────────
steady      70%           Normal         Consistent load
bursty      60%           Fast           Unpredictable spikes
periodic    65%           Normal         Regular patterns
growing     65%           Normal         Trending up
unknown     70%           Normal         Default behavior
```

### 5. Autopilot → Auto-Rollback Coordination

After autopilot applies changes, health monitoring kicks in:

```
Timeline:
0 min   → Snapshot current state
0 min   → Apply resource changes
0-10min → Monitor health every 30 seconds
        → Check: pod restarts, OOMKills, readiness
        → If unhealthy: AUTO-ROLLBACK to snapshot
10 min  → Monitoring complete, changes confirmed
```

## Processing Order

Each cycle processes features in this order:

```
1. Collect Metrics
   └─ Node utilization, pod CPU/memory, replica count

2. Pattern Detection
   └─ Identify workload pattern (steady, bursty, etc.)
   └─ Adjust HPA target based on pattern

3. Priority Adjustment
   └─ Get deployment priority (critical → best_effort)
   └─ Adjust HPA target based on priority + cluster pressure

4. Pre-Scale Check
   └─ Get predictions from ML model
   └─ Apply priority-based confidence adjustment
   └─ Pre-scale if spike predicted with sufficient confidence
   └─ Or rollback if spike didn't materialize

5. Predictive Scaling
   └─ Fine-tune HPA target based on predictions
   └─ Only apply if confidence > 80%

6. Autopilot (if enabled)
   └─ Check if pre-scale is active
   └─ Calculate resource recommendations
   └─ Skip reductions if pre-scale active
   └─ Apply safe changes with health monitoring

7. Apply HPA Decision
   └─ Update HPA target utilization
```

## Example Scenarios

### Scenario 1: Critical Payment Service Before Peak

```
Deployment: payment-service (priority: critical)
Pattern: periodic (daily peak at 9 AM)
Current time: 8:45 AM

1. Pattern detector: "periodic pattern, peak expected"
2. Priority manager: "critical priority, lower HPA target to 55%"
3. Pre-scale: "spike predicted at 85% confidence (threshold: 60% for critical)"
   → Pre-scale activated: minReplicas 3 → 5
4. Autopilot: "recommendation to reduce CPU 500m → 400m"
   → SKIPPED: pre-scale active, don't reduce during predicted spike
```

### Scenario 2: Best-Effort Analytics Job

```
Deployment: analytics-worker (priority: best_effort)
Pattern: bursty
Current time: 2 PM

1. Pattern detector: "bursty pattern"
2. Priority manager: "best_effort, raise HPA target to 85%"
3. Pre-scale: "spike predicted at 75% confidence (threshold: 80% for best_effort)"
   → NOT triggered: confidence below threshold
4. Autopilot: "recommendation to reduce CPU 1000m → 600m"
   → APPLIED: no pre-scale active, safe to optimize
   → Health monitoring started for 10 minutes
```

### Scenario 3: Autopilot Causes Issues

```
Deployment: api-gateway (priority: high)
Time: T+0

1. Autopilot applies: CPU 500m → 350m, Memory 512Mi → 384Mi
2. Snapshot saved, health monitoring started

Time: T+3 minutes
3. Health check: pod restarts increased by 3 (threshold: 2)
4. AUTO-ROLLBACK triggered
5. Resources restored: CPU 350m → 500m, Memory 384Mi → 512Mi
6. Webhook notification sent to Slack/Teams
```

## Configuration Tips

### For Maximum Safety (Production)
```bash
# Conservative autopilot
AUTOPILOT_LEVEL=recommend  # Review before applying
AUTOPILOT_MIN_CONFIDENCE=0.90
AUTOPILOT_MAX_CHANGE_PERCENT=20

# Aggressive rollback
AUTOPILOT_ENABLE_AUTO_ROLLBACK=true
AUTOPILOT_ROLLBACK_MONITOR_MINUTES=15
AUTOPILOT_MAX_RESTART_INCREASE=1
AUTOPILOT_MAX_OOM_INCREASE=0
```

### For Cost Optimization (Non-Critical)
```bash
# Aggressive autopilot
AUTOPILOT_LEVEL=autopilot
AUTOPILOT_MIN_CONFIDENCE=0.75
AUTOPILOT_MAX_CHANGE_PERCENT=40

# Relaxed rollback
AUTOPILOT_ROLLBACK_MONITOR_MINUTES=5
AUTOPILOT_MAX_RESTART_INCREASE=3
```

## Monitoring Integration

All features emit Prometheus metrics:

```
# Pattern detection
smart_autoscaler_pattern_type{deployment="api"} 2  # 2=bursty

# Pre-scale
smart_autoscaler_prescale_active{deployment="api"} 1
smart_autoscaler_prescale_min_replicas{deployment="api"} 5

# Autopilot
smart_autoscaler_autopilot_recommendations_total 15
smart_autoscaler_autopilot_applied_total 8
smart_autoscaler_autopilot_rollbacks_total 1

# Priority
smart_autoscaler_priority_level{deployment="api"} 4  # 4=high
```

## Webhook Notifications

All significant events send webhook notifications:

- Pre-scale activated/rolled back
- Autopilot changes applied
- Auto-rollback triggered
- Health issues detected

Configure webhooks in `.env`:
```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...
```
