# Priority-Based Scaling Feature

## Overview

Smart Autoscaler v0.0.10 introduces **intelligent priority-based scaling** to protect critical services during resource pressure while optimizing costs for low-priority workloads.

## Features

### 5 Priority Levels

| Priority | Use Case | HPA Target | Scale Speed | Preemption |
|----------|----------|------------|-------------|------------|
| **critical** | Payment, Auth, Billing | 55% (-15%) | 2x up, 0.25x down | Can preempt, never preempted |
| **high** | APIs, Gateways, Frontend | 60% (-10%) | 1.5x up, 0.5x down | Can preempt, never preempted |
| **medium** | Standard workloads | 70% (0%) | 1x up, 1x down | Cannot preempt, can be preempted |
| **low** | Background jobs, Workers | 80% (+10%) | 0.5x up, 2x down | Cannot preempt, can be preempted |
| **best_effort** | Reports, Analytics, Cleanup | 85% (+15%) | 0.25x up, 3x down | Cannot preempt, can be preempted |

### Smart Behaviors

1. **Auto-Detection**: Automatically detects priority from:
   - Deployment name patterns (payment, auth, api, worker, report, etc.)
   - Labels: `priority`, `workload-priority`
   - Annotations: `autoscaler.k8s.io/priority`

2. **Pressure-Aware Adjustments**:
   - **Critical Pressure (>85%)**: Critical/High get MORE headroom, Low/Best-effort get LESS
   - **High Pressure (>75%)**: Moderate adjustments
   - **Low Pressure (<40%)**: Cost optimization for low-priority workloads

3. **Preemptive Scaling**:
   - High-priority can trigger scale-down of low-priority during cluster pressure
   - Only when cluster pressure >80%
   - 5-minute cooldown between preemptions
   - Protects critical services from resource starvation

4. **Processing Order**:
   - Deployments processed by priority (highest first)
   - Ensures critical services get resources first during pressure

5. **Historical Learning**:
   - Tracks pressure patterns over last 10 readings
   - Adapts adjustments based on average pressure
   - Learns optimal behavior per priority level

## Configuration

### Environment Variables

```bash
# Set priority for each deployment
DEPLOYMENT_0_PRIORITY=critical
DEPLOYMENT_1_PRIORITY=high
DEPLOYMENT_2_PRIORITY=medium  # default
DEPLOYMENT_3_PRIORITY=low
DEPLOYMENT_4_PRIORITY=best_effort
```

### Kubernetes Labels/Annotations

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-service
  labels:
    priority: critical
  annotations:
    autoscaler.k8s.io/priority: critical
```

### Auto-Detection Patterns

The system automatically detects priority from deployment names:

- **Critical**: payment, auth, billing, checkout
- **High**: api, gateway, frontend, web
- **Low**: worker, job, batch, cron
- **Best-effort**: report, analytics, backup, cleanup
- **Medium**: Everything else (default)

## Implementation Details

### Files Modified

1. **src/priority_manager.py** (NEW)
   - Complete priority management system
   - 5 priority levels with configurations
   - Smart target adjustment based on pressure
   - Preemption logic with cooldown
   - Auto-detection from labels/names

2. **src/config_loader.py**
   - Added `priority` field to `DeploymentConfig`
   - Parse `DEPLOYMENT_X_PRIORITY` from environment
   - Parse priority from ConfigMap

3. **src/integrated_operator.py**
   - Initialize `PriorityManager`
   - Set priority for each deployment
   - Sort deployments by priority before processing
   - Calculate cluster pressure
   - Apply priority-based target adjustments
   - Log priority adjustments

4. **src/dashboard.py**
   - Add priority to deployment current state API
   - Add `/api/priorities/stats` endpoint
   - Return priority statistics

5. **templates/dashboard.html**
   - Add Priority column to deployments table
   - Color-coded priority badges
   - Display priority in deployment rows

6. **README.md**
   - Complete priority documentation
   - Configuration examples
   - Use case scenarios
   - Feature table

7. **.env.example**
   - Priority configuration examples
   - Priority level descriptions

8. **tests/test_priority_manager.py** (NEW)
   - Comprehensive test suite
   - 25+ test cases covering all features

## Usage Examples

### Example 1: E-commerce Platform

```bash
# Payment service - never compromised
DEPLOYMENT_0_NAME=payment-service
DEPLOYMENT_0_PRIORITY=critical

# API gateway - important but flexible
DEPLOYMENT_1_NAME=api-gateway
DEPLOYMENT_1_PRIORITY=high

# Product catalog - standard
DEPLOYMENT_2_NAME=product-catalog
DEPLOYMENT_2_PRIORITY=medium

# Email worker - cost-optimized
DEPLOYMENT_3_NAME=email-worker
DEPLOYMENT_3_PRIORITY=low

# Analytics job - best effort
DEPLOYMENT_4_NAME=analytics-report
DEPLOYMENT_4_PRIORITY=best_effort
```

### Example 2: SaaS Platform

```bash
# Auth service - critical
DEPLOYMENT_0_NAME=auth-service
DEPLOYMENT_0_PRIORITY=critical

# Frontend - high priority
DEPLOYMENT_1_NAME=web-frontend
DEPLOYMENT_1_PRIORITY=high

# Background jobs - low priority
DEPLOYMENT_2_NAME=data-sync-worker
DEPLOYMENT_2_PRIORITY=low
```

## Behavior During Pressure

### Scenario: Cluster at 90% CPU

1. **Critical Services** (payment, auth):
   - HPA target: 55% → 45% (MORE headroom)
   - Scale up 2x faster
   - Never scaled down for others

2. **High Services** (API, gateway):
   - HPA target: 60% → 55% (more headroom)
   - Scale up 1.5x faster
   - Protected from preemption

3. **Medium Services** (standard):
   - HPA target: 70% (unchanged)
   - Normal scaling speed
   - Can be preempted if needed

4. **Low Services** (workers):
   - HPA target: 80% → 95% (LESS headroom)
   - Scale down 2x faster
   - Can be preempted by high-priority

5. **Best-effort Services** (reports):
   - HPA target: 85% → 95% (minimal headroom)
   - Scale down 3x faster
   - First to be preempted

## Dashboard Display

The dashboard shows:
- Priority badge with color coding in deployments table
- Priority statistics via `/api/priorities/stats`
- Real-time pressure indicators
- Preemption events in logs

## Metrics

Priority-related metrics are logged:
- Priority level per deployment
- Target adjustments applied
- Cluster pressure calculations
- Preemption events
- Processing order

## Testing

Run priority manager tests:

```bash
python3.12 -m pytest tests/test_priority_manager.py -v
```

Test coverage includes:
- Priority setting and retrieval
- Configuration management
- Sorting by priority
- Target adjustments under various pressures
- Preemption logic
- Scale speed multipliers
- Auto-detection
- Statistics generation

## Migration Guide

### Existing Deployments

All existing deployments default to `medium` priority. No changes required.

### Adding Priority

1. **Option 1: Environment Variable**
   ```bash
   DEPLOYMENT_0_PRIORITY=high
   ```

2. **Option 2: ConfigMap**
   ```yaml
   DEPLOYMENT_0_PRIORITY: "high"
   ```

3. **Option 3: Deployment Label**
   ```yaml
   labels:
     priority: high
   ```

4. **Option 4: Auto-Detection**
   - Name your deployment with keywords (payment, api, worker, etc.)
   - System automatically assigns appropriate priority

## Best Practices

1. **Start Conservative**: Begin with default (medium) priority for all
2. **Identify Critical**: Mark only truly critical services (payment, auth)
3. **Use High Sparingly**: Reserve for customer-facing services
4. **Optimize Low-Priority**: Use for batch jobs, workers, reports
5. **Monitor Pressure**: Watch cluster pressure and adjust priorities
6. **Test Preemption**: Verify low-priority can be preempted safely
7. **Review Regularly**: Adjust priorities as workload patterns change

## Troubleshooting

### Priority Not Applied

Check:
1. Environment variable set correctly
2. ConfigMap updated (if using ConfigMap)
3. Deployment name matches configuration
4. Logs show priority being set

### Unexpected Preemption

Check:
1. Cluster pressure is >80%
2. Priority difference is sufficient
3. Cooldown period (5 minutes) has passed
4. Target deployment can be preempted

### Target Not Adjusting

Check:
1. Priority is set correctly
2. Cluster pressure is being calculated
3. Adjustment is >3% (minimum threshold)
4. Logs show priority adjustment being applied

## Future Enhancements

Potential improvements:
- [ ] Configurable priority thresholds
- [ ] Custom priority levels
- [ ] Priority-based resource quotas
- [ ] Priority inheritance (namespace-level)
- [ ] Priority-based alerting
- [ ] Historical priority effectiveness metrics
- [ ] Machine learning for optimal priority assignment

## Version

- **Feature Version**: 1.0
- **Smart Autoscaler Version**: 0.0.10
- **Release Date**: 2026-01-01
