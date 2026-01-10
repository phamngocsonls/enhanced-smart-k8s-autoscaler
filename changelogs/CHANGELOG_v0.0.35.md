# Changelog v0.0.35

## Release Date: 2026-01-10

## 🎯 Summary
Dashboard UX improvements with consolidated tabs, smart notification provider modal, and Google Chat webhook support.

## ✨ New Features

### Dashboard Tab Consolidation
- Reduced 13 tabs to 7 main tabs with sub-tabs for better navigation
- **Main tabs**: Deployments, Cluster, FinOps, Scaling, Alerts, Autopilot, Config
- **Scaling sub-tabs**: Predictions, Pre-Scale, HPA Analysis, Timeline
- **Cluster sub-tabs**: Overview, Node Efficiency
- **FinOps sub-tabs**: Recommendations, Cost & Reports

### Smart Notification Provider Modal
- Replaced ugly `prompt()` dialogs with proper modal form
- Visual provider type selection with branded cards (Slack, Teams, Discord, Google Chat, Generic)
- Provider-specific webhook URL placeholders and hints
- Checkbox-based alert type selection (no more comma-separated text!)
- Test button with loading state and detailed feedback
- Provider cards with custom colors per provider type

### Google Chat Webhook Support
- Added Google Chat as notification provider option
- Proper Google Chat Card format for webhook payloads
- Correct payload structure: `cards[].header`, `cards[].sections[].widgets`

### Provider-Specific Webhook Formats
Each provider now uses its native webhook format:
- **Slack**: `attachments` with `color`, `fields` array
- **Teams**: `MessageCard` with `@type`, `themeColor`, `facts`
- **Discord**: `embeds` with integer `color`, `fields` with `inline`
- **Google Chat**: `cards` with `header`, `sections.widgets.textParagraph`
- **Generic**: Simple JSON with `title`, `message`, `severity`, `fields`

## 🔧 Improvements

### UI/UX
- Provider cards show masked webhook URLs for security
- Custom border colors per provider type (Slack purple, Teams blue, Discord indigo, Google Chat green)
- Better alert type icons with emoji indicators
- Test webhook button shows loading spinner and detailed results

### Code Quality
- Cleaner tab navigation JavaScript with sub-tab support
- Modular provider type selection function
- Better error handling in webhook test endpoint

## 📁 Files Changed
- `templates/dashboard.html` - Tab consolidation, modal dialog, provider cards
- `src/intelligence.py` - Added `_send_googlechat()` method
- `src/dashboard.py` - Updated test-webhook endpoint for Google Chat

## 🧪 Testing
- 278 tests passing
- Coverage: 34%
