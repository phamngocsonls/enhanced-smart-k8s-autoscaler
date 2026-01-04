# Changelog v0.0.28

**Release Date:** January 5, 2026

## Critical Bug Fix

### API Routes 404 Fix
Fixed a critical bug where all cost allocation and reporting API endpoints were returning 404 errors.

**Root Cause:** The 11 API routes for cost allocation and reporting were incorrectly placed after a `return` statement inside the `_generate_analysis_summary()` method, making them unreachable code. Flask never registered these routes.

**Fix:** Moved all routes to the correct location inside `_setup_routes()` method, before `_analyze_hpa_behavior()`.

## Working API Endpoints

After this fix, the following endpoints are now accessible:

### Cost Allocation APIs
- `GET /api/cost/allocation/team` - Get costs grouped by team
- `GET /api/cost/allocation/namespace` - Get costs grouped by namespace  
- `GET /api/cost/allocation/project` - Get costs grouped by project
- `GET /api/cost/pricing-info` - Get detected cloud pricing information
- `GET /api/cost/anomalies` - Detect cost anomalies
- `GET /api/cost/idle-resources` - Get idle/underutilized resources

### Reporting APIs
- `GET /api/reports/status` - Get reporting system status
- `GET /api/reports/executive-summary` - Generate executive summary report
- `GET /api/reports/team/<team>` - Generate team-specific report
- `GET /api/reports/forecast` - Generate cost forecast
- `GET /api/reports/roi` - Generate ROI report
- `GET /api/reports/trends` - Generate trend analysis report

## Upgrade Instructions

```bash
# Update to v0.0.28
kubectl set image deployment/smart-autoscaler \
  smart-autoscaler=ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:0.0.28

# Verify APIs work
curl http://localhost:5000/api/reports/status
curl http://localhost:5000/api/cost/pricing-info
```

## Testing

All tests pass:
- `tests/test_dashboard.py` - 8 tests passed
- `tests/test_cost_allocation.py` - 8 tests passed
- `tests/test_reporting.py` - 10 tests passed
