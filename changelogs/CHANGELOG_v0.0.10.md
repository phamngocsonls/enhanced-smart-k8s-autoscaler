# Changelog - Version 0.0.10

## Release Date: 2026-01-01

## 🎯 Major Feature: Priority-Based Scaling

### Overview
Introduced intelligent priority-based scaling to protect critical services during resource pressure while optimizing costs for low-priority workloads.

### New Features

#### 1. Priority Manager (`src/priority_manager.py`)
- **5 Priority Levels**: critical, high, medium, low, best_effort
- **Smart Target Adjustments**: Automatic HPA target adjustments based on priority and cluster pressure
- **Preemptive Scaling**: High-priority can trigger scale-down of low-priority during pressure
- **Auto-Detection**: Automatically detects priority from deployment names, labels, and annotations
- **Pressure-Aware**: Adapts behavior based on cluster pressure (>85% = aggressive, <40% = optimize)
- **Processing Order**: Processes deployments by priority (highest first)
- **Scale Speed Multipliers**: Different scaling speeds per priority level
- **Cooldown Protection**: 5-minute cooldown between preemptions

#### 2. Configuration Support
- **Environment Variables**: `DEPLOYMENT_X_PRIORITY` configuration
- **ConfigMap Support**: Priority in ConfigMap hot-reload
- **Labels/Annotations**: Auto-detection from Kubernetes metadata
- **Default Priority**: All deployments default to "medium" (backward compatible)

#### 3. Dashboard Integration
- **Priority Column**: Added to deployments table with color-coded badges
- **Priority API**: New `/api/priorities/stats` endpoint
- **Priority Display**: Shows priority in deployment current state
- **Color Coding**: Critical=red, High=orange, Medium=green, Low=blue

#### 4. Documentation
- **README.md**: Complete priority documentation with examples
- **PRIORITY_FEATURE.md**: Detailed feature documentation
- **.env.example**: Priority configuration examples
- **Demo Script**: `examples/priority-demo.py` for testing

#### 5. Testing
- **Comprehensive Tests**: 25+ test cases in `tests/test_priority_manager.py`
- **Coverage**: All priority manager features tested
- **Syntax Validation**: All files pass syntax checks

### Priority Configurations

| Priority | HPA Target | Scale Up | Scale Down | Use Case |
|----------|------------|----------|------------|----------|
| critical | 55% (-15%) | 2x faster | 4x slower | Payment, Auth, Billing |
| high | 60% (-10%) | 1.5x faster | 2x slower | APIs, Gateways, Frontend |
| medium | 70% (0%) | Normal | Normal | Standard workloads (default) |
| low | 80% (+10%) | 2x slower | 2x faster | Background jobs, Workers |
| best_effort | 85% (+15%) | 4x slower | 3x faster | Reports, Analytics, Cleanup |

### Smart Behaviors

1. **Pressure-Based Adjustments**:
   - Critical pressure (>85%): Critical/High get MORE headroom, Low/Best-effort get LESS
   - High pressure (>75%): Moderate adjustments
   - Low pressure (<40%): Cost optimization for low-priority

2. **Preemption Logic**:
   - Only when cluster pressure >80%
   - High-priority can preempt low-priority
   - 5-minute cooldown between preemptions
   - Protects critical services from resource starvation

3. **Auto-Detection Patterns**:
   - Critical: payment, auth, billing, checkout
   - High: api, gateway, frontend, web
   - Low: worker, job, batch, cron
   - Best-effort: report, analytics, backup, cleanup

### Files Modified

1. **src/priority_manager.py** (NEW) - Complete priority management system
2. **src/config_loader.py** - Added priority field to DeploymentConfig
3. **src/integrated_operator.py** - Integrated PriorityManager
4. **src/dashboard.py** - Added priority API endpoints
5. **templates/dashboard.html** - Added priority column and badges
6. **README.md** - Priority documentation
7. **.env.example** - Priority configuration examples
8. **tests/test_priority_manager.py** (NEW) - Comprehensive test suite
9. **examples/priority-demo.py** (NEW) - Interactive demo script
10. **PRIORITY_FEATURE.md** (NEW) - Detailed feature documentation

### Configuration Examples

```bash
# Critical payment service
DEPLOYMENT_0_NAME=payment-service
DEPLOYMENT_0_PRIORITY=critical

# High-priority API
DEPLOYMENT_1_NAME=api-gateway
DEPLOYMENT_1_PRIORITY=high

# Standard workload (default)
DEPLOYMENT_2_NAME=web-app
DEPLOYMENT_2_PRIORITY=medium

# Background worker
DEPLOYMENT_3_NAME=email-worker
DEPLOYMENT_3_PRIORITY=low

# Analytics job
DEPLOYMENT_4_NAME=analytics-report
DEPLOYMENT_4_PRIORITY=best_effort
```

### Backward Compatibility

- ✅ All existing deployments default to "medium" priority
- ✅ No configuration changes required for existing setups
- ✅ Priority is optional - system works without it
- ✅ Auto-detection provides sensible defaults

### Testing

Run the demo:
```bash
python3 examples/priority-demo.py
```

Run tests:
```bash
python3.12 -m pytest tests/test_priority_manager.py -v
```

### Performance Impact

- Minimal overhead: Priority checks are O(1) lookups
- Cluster pressure calculation: O(n) where n = number of deployments
- Sorting: O(n log n) but only done once per iteration
- No impact on existing features

### Migration Guide

1. **No action required** - All deployments default to medium priority
2. **Optional**: Add priority to critical services
3. **Optional**: Use auto-detection by naming deployments appropriately
4. **Optional**: Add labels/annotations for explicit priority

### Known Limitations

- Preemption only works when cluster pressure >80%
- 5-minute cooldown between preemptions (configurable in future)
- Priority adjustments require ≥3% difference to apply
- No priority inheritance (namespace-level) yet

### Future Enhancements

- [ ] Configurable priority thresholds
- [ ] Custom priority levels
- [ ] Priority-based resource quotas
- [ ] Priority inheritance (namespace-level)
- [ ] Priority-based alerting
- [ ] Historical priority effectiveness metrics
- [ ] Machine learning for optimal priority assignment

### Version Bump

- Previous: 0.0.9
- Current: 0.0.10

### Contributors

- Smart Autoscaler Team

---

## Summary

Version 0.0.10 introduces a powerful priority-based scaling system that intelligently manages resources across workloads. Critical services get maximum protection and headroom, while low-priority workloads are optimized for cost. The system is smart, adaptive, and fully backward compatible.
