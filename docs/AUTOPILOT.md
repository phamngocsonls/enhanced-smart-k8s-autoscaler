# Autopilot Mode - Automatic Resource Tuning

Autopilot Mode automatically tunes CPU and memory **requests** based on observed P95 usage patterns. This feature is inspired by StormForge's automatic resource tuning capabilities.

## Key Features

- **Requests Only**: Only tunes resource requests, NOT limits
- **Disabled by Default**: Must be explicitly enabled
- **Safety Guardrails**: Multiple safety checks prevent over-optimization
- **HPA Compatible**: Works smoothly with Horizontal Pod Autoscaler
- **Audit Logging**: All changes are logged for compliance
- **Rollback Support**: Easy rollback if issues occur

## How It Works

1. **Observe**: Collects P95 CPU and memory usage over time
2. **Analyze**: Calculates optimal requests with safety buffers
3. **Recommend**: Generates recommendations visible in dashboard
4. **Apply**: Auto-applies safe changes (when in AUTOPILOT level)

## Configuration

### Environment Variables

```bash
# Master switch (default: false)
ENABLE_AUTOPILOT=false

# Automation level (default: recommend)
# - disabled: No autopilot processing
# - observe: Only observe and log
# - recommend: Generate recommendations (visible in dashboard)
# - autopilot: Auto-apply safe changes
AUTOPILOT_LEVEL=recommend

# Minimum days of data before auto-tuning (default: 7)
AUTOPILOT_MIN_OBSERVATION_DAYS=7

# Minimum confidence to apply changes (default: 0.80)
AUTOPILOT_MIN_CONFIDENCE=0.80

# Maximum % change per iteration (default: 30)
AUTOPILOT_MAX_CHANGE_PERCENT=30

# Hours between changes for same deployment (default: 24)
AUTOPILOT_COOLDOWN_HOURS=24

# Minimum CPU request in millicores (default: 50)
AUTOPILOT_MIN_CPU_REQUEST=50

# Minimum memory request in MB (default: 64)
AUTOPILOT_MIN_MEMORY_REQUEST=64

# Buffer above P95 for CPU (default: 20%)
AUTOPILOT_CPU_BUFFER_PERCENT=20

# Buffer above P95 for memory (default: 25%)
AUTOPILOT_MEMORY_BUFFER_PERCENT=25
```

### Helm Values

```yaml
config:
  enableAutopilot: false
  autopilotLevel: recommend
  autopilotMinConfidence: 0.80
  autopilotMaxChangePercent: 30
  autopilotCooldownHours: 24
```

### Per-Deployment Annotation

Override autopilot for specific deployments:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  annotations:
    # Enable autopilot for this deployment
    smart-autoscaler.io/autopilot: "true"
    
    # Or disable for this deployment
    smart-autoscaler.io/autopilot: "false"
```

## Automation Levels

| Level | Description | Use Case |
|-------|-------------|----------|
| `disabled` | No autopilot processing | Testing, troubleshooting |
| `observe` | Only observe and log | Initial deployment, learning |
| `recommend` | Generate recommendations | Review before applying |
| `autopilot` | Auto-apply safe changes | Production, trusted workloads |

## Safety Guardrails

### 1. Minimum Observation Period
- Requires 7 days of data by default
- Prevents premature optimization

### 2. Confidence Threshold
- Only applies changes with ≥80% confidence
- Confidence based on data stability and observation period

### 3. Maximum Change Limit
- Limits changes to 30% per iteration
- Large changes are split across multiple iterations

### 4. Cooldown Period
- 24-hour cooldown between changes
- Prevents rapid oscillation

### 5. Priority-Based Safety
- Critical priority: Manual approval required
- High priority: Large changes require approval

### 6. Minimum Values
- CPU: Never below 50m
- Memory: Never below 64Mi

## API Endpoints

### Get Status
```bash
curl http://localhost:5000/api/autopilot/status
```

Response:
```json
{
  "enabled": true,
  "level": "RECOMMEND",
  "config": {
    "min_observation_days": 7,
    "min_confidence": 0.80,
    "max_change_percent": 30,
    "cooldown_hours": 24
  },
  "statistics": {
    "total_recommendations": 5,
    "pending_recommendations": 3,
    "total_actions": 2,
    "rollbacks": 0
  }
}
```

### Get Recommendations
```bash
curl http://localhost:5000/api/autopilot/recommendations
```

Response:
```json
{
  "recommendations": [
    {
      "namespace": "default",
      "deployment": "my-app",
      "current_cpu_request": 500,
      "recommended_cpu_request": 300,
      "current_memory_request": 512,
      "recommended_memory_request": 384,
      "cpu_p95": 250.0,
      "memory_p95": 320.0,
      "confidence": 0.85,
      "savings_percent": 35.0,
      "is_safe": true
    }
  ],
  "count": 1
}
```

### Get Actions
```bash
curl http://localhost:5000/api/autopilot/actions
```

### Apply Recommendation Manually
```bash
curl -X POST http://localhost:5000/api/autopilot/default/my-app/apply
```

### Rollback
```bash
curl -X POST http://localhost:5000/api/autopilot/default/my-app/rollback \
  -H "Content-Type: application/json" \
  -d '{"reason": "Performance degradation observed"}'
```

## Recommendation Calculation

```
Recommended CPU = P95 CPU × (1 + CPU_BUFFER_PERCENT / 100)
Recommended Memory = P95 Memory × (1 + MEMORY_BUFFER_PERCENT / 100)
```

With defaults:
- CPU: P95 + 20% buffer
- Memory: P95 + 25% buffer

## Best Practices

### 1. Start with RECOMMEND Level
```bash
ENABLE_AUTOPILOT=true
AUTOPILOT_LEVEL=recommend
```
Review recommendations in dashboard before enabling auto-apply.

### 2. Use Per-Deployment Annotations
Enable autopilot only for trusted, stable workloads:
```yaml
annotations:
  smart-autoscaler.io/autopilot: "true"
```

### 3. Monitor After Changes
- Watch for OOM kills
- Monitor response times
- Check error rates

### 4. Adjust Buffers for Workload Type
- Bursty workloads: Higher buffers (30-40%)
- Stable workloads: Lower buffers (15-20%)

### 5. Set Appropriate Cooldown
- Stable environments: 24 hours
- Dynamic environments: 48-72 hours

## Troubleshooting

### Recommendations Not Appearing
1. Check observation days: Need ≥7 days of data
2. Check change threshold: Changes <5% are skipped
3. Verify autopilot is enabled

### Changes Not Being Applied
1. Check automation level: Must be `autopilot`
2. Check confidence: Must be ≥80%
3. Check cooldown: 24-hour wait between changes
4. Check safety: Critical priority requires manual approval

### Rollback Not Working
1. Verify there are actions to rollback
2. Check Kubernetes connectivity
3. Review logs for errors

## Comparison with VPA

| Feature | Autopilot Mode | VPA |
|---------|---------------|-----|
| Requests | ✅ Tunes | ✅ Tunes |
| Limits | ❌ No limits | ✅ Sets limits |
| HPA Compatible | ✅ Yes | ⚠️ Conflicts possible |
| Safety Guardrails | ✅ Built-in | ⚠️ Basic |
| Rollback | ✅ Easy | ❌ Manual |
| Audit Log | ✅ Yes | ❌ No |

## Example: Enabling Autopilot

### Step 1: Enable in Observe Mode
```bash
# In ConfigMap or environment
ENABLE_AUTOPILOT=true
AUTOPILOT_LEVEL=observe
```

### Step 2: Wait for Data Collection
Wait 7+ days for sufficient observation data.

### Step 3: Review Recommendations
```bash
curl http://localhost:5000/api/autopilot/recommendations
```

### Step 4: Enable Recommend Mode
```bash
AUTOPILOT_LEVEL=recommend
```

### Step 5: Manually Apply Safe Recommendations
```bash
curl -X POST http://localhost:5000/api/autopilot/default/my-app/apply
```

### Step 6: Enable Full Autopilot (Optional)
```bash
AUTOPILOT_LEVEL=autopilot
```
