# Changelog v0.0.34

## Release Date: 2026-01-10

## 🚀 New Features: Autopilot Dashboard Tab & Webhook Notifications

This release adds a dedicated Autopilot dashboard tab and webhook notifications for autopilot actions.

### Autopilot Dashboard Tab

New dedicated tab in the dashboard showing:
- **Status Cards**: Enabled/disabled status, automation level, recommendations count, actions count
- **Configuration Display**: Min observation days, confidence threshold, max change %, cooldown hours
- **Recommendations Table**: Current recommendations with Apply buttons for manual application
- **Actions History**: All applied changes with timestamps and rollback status
- **Cooldown Status**: Shows deployments currently in cooldown period

### Webhook Notifications

Autopilot now sends notifications to configured webhooks when:
- **Apply**: Resource requests are automatically updated
- **Rollback**: Changes are rolled back

Supported channels:
- Slack
- Microsoft Teams
- Discord
- Generic webhook

### Configuration

Webhooks are configured via existing environment variables:
```bash
SLACK_WEBHOOK=https://hooks.slack.com/services/...
TEAMS_WEBHOOK=https://...
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
GENERIC_WEBHOOK=https://your-webhook.com/...
```

### Files Changed

#### Modified Files
- `src/autopilot.py` - Added `alert_manager` parameter and `_send_notification()` method
- `src/integrated_operator.py` - Pass `alert_manager` to `AutopilotManager`
- `templates/dashboard.html` - Added Autopilot tab with full UI
  - Status cards
  - Configuration display
  - Recommendations table with Apply buttons
  - Actions history table
  - Cooldown status
  - JavaScript functions: `loadAutopilotData()`, `applyAutopilotRec()`, `rollbackAutopilot()`

### Test Results

- **Total Tests**: 278 passing
- **Coverage**: 34% (above 25% minimum)

### Upgrade Notes

1. No configuration changes required
2. Webhooks use existing `SLACK_WEBHOOK`, `TEAMS_WEBHOOK`, etc. environment variables
3. Access the new Autopilot tab from the dashboard navigation
