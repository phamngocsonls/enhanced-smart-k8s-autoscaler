# Changelog v0.0.34

## Release Date: 2026-01-10

## 🚀 New Features & UI Improvements

### Autopilot Dashboard Tab

New dedicated tab in the dashboard showing:
- **Status Cards**: Enabled/disabled status, automation level, recommendations count, actions count
- **Configuration Display**: Min observation days, confidence threshold, max change %, cooldown hours
- **Recommendations Table**: Current recommendations with Apply buttons for manual application
- **Actions History**: All applied changes with timestamps and rollback status
- **Cooldown Status**: Shows deployments currently in cooldown period

### Per-Deployment Autopilot Status

- **New Column in Deployments Table**: Shows autopilot status for each deployment
  - `OFF` - Autopilot not enabled for this deployment
  - `ON` - Autopilot enabled, waiting for data
  - `✓ REC` - Autopilot enabled with recommendation available
- **New API Endpoint**: `/api/autopilot/deployment/<ns>/<dep>` returns per-deployment autopilot status

### Notification Providers Management (Alerts Tab)

New UI in Alerts tab for managing notification providers:
- **Add/Edit/Delete Providers**: Configure Slack, Teams, Discord, or Generic webhooks via dashboard
- **Alert Type Subscriptions**: Choose which alert types each provider receives:
  - CPU Spike, Scaling Thrashing, High Memory, Low Efficiency
  - HPA Flapping, Cost Optimization, Memory Leak
  - Pre-Scale Events, Autopilot Actions
- **Test Notifications**: Send test messages to verify webhook configuration
- **Environment + Dashboard**: Supports both env vars (read-only) and dashboard-configured providers
- **Persistent Storage**: Dashboard-configured providers stored in database

### Pre-Scale Improvements

- **Immediate Scaling**: Pre-scale and rollback now directly scale deployment replicas for immediate effect
- **Reliable Rollback**: Fixed issue where rollback didn't change actual pod count (only HPA minReplicas)

### Dashboard Layout Improvements

- **Removed Right Sidebar**: System Health, Quick Actions, CPU Trend, Resource Efficiency panels removed
- **Full Width Layout**: Main content now uses full width for better space utilization
- **Cleaner UI**: More space for deployment tables and tab content
- **Pre-Scale Tab Auto-Load**: Pre-Scale tab now automatically loads data when clicked

### Bug Fixes

- **FinOps Deployment Profile**: Fixed issue where Avg CPU, P95 CPU showed `-m` when pod CPU usage data was zero or missing
- **Pre-Scale Rollback**: Now scales deployment directly instead of only patching HPA minReplicas

### API Endpoints Added

- `GET /api/notification-providers` - List all notification providers
- `POST /api/notification-providers` - Add new provider
- `PUT /api/notification-providers/<id>` - Update provider (name, webhook, enabled, alert_types)
- `DELETE /api/notification-providers/<id>` - Delete provider
- `POST /api/notification-providers/<id>/test` - Send test notification

### Database Schema

New table `notification_providers`:
- `id`, `name`, `provider_type`, `webhook_url`, `enabled`, `alert_types`, `created_at`, `updated_at`

### Files Changed

#### Modified Files
- `src/intelligence.py` - Added notification_providers table and CRUD methods
- `src/dashboard.py` - Added notification provider API endpoints, alert_manager reference
- `src/prescale_manager.py` - Improved _do_prescale and _do_rollback to scale deployment directly
- `templates/dashboard.html`:
  - Added Notification Providers section in Alerts tab
  - Added alert type subscription UI
  - Added Autopilot tab with full UI
  - Added Autopilot column to deployments table
  - Removed sidebar, full width layout

### Test Results

- **Total Tests**: 278 passing
- **Coverage**: 34% (above 25% minimum)

### Upgrade Notes

1. No configuration changes required
2. Dashboard now uses full width - no more right sidebar
3. Configure notification providers via Alerts tab or environment variables
4. Alert type subscriptions allow fine-grained control over notifications
5. Pre-scale/rollback now takes effect immediately (scales deployment directly)
