# Changelog v0.0.23 (Pre-Release)

**Release Date**: 2026-01-04  
**Type**: Pre-Release (Beta)

---

## 🎨 Major UI Redesign - Enterprise-Grade Dashboard

Complete visual overhaul to look professional and enterprise-ready.

### UI Improvements
- ✨ **Professional SVG Icons** - Replaced all emoji icons with Material Design-style SVG icons
- 🎯 **Enterprise Logo** - New shield/clock icon for professional branding
- 📊 **Tab Icons** - Clean, scalable vector icons for all navigation tabs
- 🎨 **Consistent Styling** - Unified icon sizing, colors, and hover effects
- 💼 **Enterprise Appearance** - Dashboard now looks like Grafana/Datadog/New Relic

### Icon Changes
| Component | Old | New |
|-----------|-----|-----|
| Logo | ⚡ Lightning emoji | Shield/clock SVG |
| Deployments | 📊 Emoji | Grid layout SVG |
| Cluster | 🖥️ Emoji | Server rack SVG |
| FinOps | 💰 Emoji | Dollar sign SVG |
| AI Insights | 🧠 Emoji | User/brain SVG |
| Timeline | 📈 Emoji | Trending line SVG |
| Predictions | 🔮 Emoji | Chart arrow SVG |
| Alerts | 🔔 Emoji | Bell SVG |
| HPA Analysis | 🛡️ Emoji | Shield SVG |
| Config | ⚙️ Emoji | Settings gear SVG |

---

## 🤖 GenAI Integration (Experimental)

**Status**: Pre-release / Experimental  
**Note**: This feature is in early development and may change significantly.

### Multi-Provider Support (NEW)
- ✅ **OpenAI Integration** - GPT-4, GPT-4o-mini, GPT-3.5-turbo support
- ✅ **Google Gemini Integration** - Gemini 1.5 Flash support
- ✅ **Anthropic Claude Integration** - Claude 3 Haiku, Sonnet, Opus support
- 🔄 **Auto-detection** - Automatically detects available API keys
- 🎯 **Priority**: OpenAI > Gemini > Claude > Mock
- 🛡️ **Graceful Fallback** - Works without any API keys (mock mode)

### Dashboard Integration (NEW)
- 💡 **Activation Guide** - Shows helpful setup instructions when GenAI is disabled
- ✅ **Provider Status** - Displays which GenAI provider is active
- 🔍 **Event Details Modal** - Click scaling events to see detailed information
  - Shows namespace, deployment, action, pod count, HPA target
  - Professional modal design with keyboard shortcuts (Escape to close)
  - Background click to dismiss
- 🚫 **No Errors** - Dashboard works perfectly without GenAI configured
- 📚 **Step-by-step Guide** - Clear instructions with API key links

### Configuration (NEW)
```bash
# Enable GenAI features
ENABLE_GENAI=true

# Choose ONE provider:
OPENAI_API_KEY=sk-...              # OpenAI
GEMINI_API_KEY=AIza...             # Google Gemini
ANTHROPIC_API_KEY=sk-ant-...       # Anthropic Claude

# Optional model selection:
OPENAI_MODEL=gpt-4o-mini           # Fast and cheap
CLAUDE_MODEL=claude-3-haiku-20240307  # Fast and cheap
```

### Planned Features (Coming Soon)
- 🤖 AI-powered scaling recommendations using LLM
- 💬 Natural language queries for metrics
- 📝 Automated incident reports
- 🔍 Intelligent anomaly explanations
- 📊 Auto-generated optimization reports

**Current Status**: Multi-provider foundation complete, advanced features in development.

---

## 📚 Documentation Improvements

### New Documentation
- **[docs/SCALING_CONFIGURATION.md](../docs/SCALING_CONFIGURATION.md)** - How to configure 100+ deployments (ConfigMap size limits)
- **[docs/STARTUP_FILTER.md](../docs/STARTUP_FILTER.md)** - Comprehensive guide for Java/JVM startup spike handling
- **[docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)** - Visual architecture diagrams and examples
- **[GETTING_STARTED.md](../GETTING_STARTED.md)** - 60-second quick start guide

### New Tools
- **[scripts/generate-helm-values.py](../scripts/generate-helm-values.py)** - Auto-generate Helm values from CSV or kubectl
- **[scripts/release.sh](../scripts/release.sh)** - Automated release script for quick version bumps

### Example Files
- **[examples/configmap-simple.yaml](../examples/configmap-simple.yaml)** - Ready-to-use ConfigMap template
- **[examples/hpa-simple.yaml](../examples/hpa-simple.yaml)** - Ready-to-use HPA manifest
- **[examples/helm-values-many-deployments.yaml](../examples/helm-values-many-deployments.yaml)** - Template for 10+ deployments

---

## ⚙️ Configuration Updates

### Cost Ratio Update
- Changed CPU:Memory cost ratio from **1:10 to 1:8** (more accurate for modern cloud pricing)
- `COST_PER_VCPU_HOUR`: 0.04 (unchanged)
- `COST_PER_GB_MEMORY_HOUR`: 0.004 → **0.005** (updated)

### Updated Files
- `helm/smart-autoscaler/values.yaml`
- `src/config_loader.py`
- `.env.example`
- `k8s/configmap.yaml`
- All example files

---

## 🐛 Bug Fixes

- Fixed version display in dashboard header (was showing v0.0.18, now shows v0.0.23)
- Improved icon rendering on high-DPI displays
- Better hover states for navigation tabs
- Fixed GenAI integration tests to handle service unavailable (503) gracefully
- **Fixed Scaling Timeline initialization** - Timeline now properly initializes without JavaScript errors
- **Fixed GenAI error handling** - No errors when GenAI is not configured, shows helpful activation guide instead

---

## 🛠️ Developer Experience

### Build Script Improvements (NEW)
- ✅ **macOS Compatibility** - `build-base-image.sh` now works on macOS
- 🔧 **Auto-detection** - Detects OS and architecture automatically
- 🍎 **shasum Fallback** - Uses macOS-native `shasum` when `sha256sum` not available
- 🏗️ **Single-arch Builds** - Fast local builds for development
- 📤 **Optional Push** - Use `--push` flag to upload to registry
- 📖 **Clear Documentation** - Usage instructions and multi-arch guidance

```bash
# Local build (single architecture)
./scripts/build-base-image.sh

# Build and push to registry
./scripts/build-base-image.sh --push

# Multi-arch builds use GitHub Actions automatically
```

---

## 📦 Breaking Changes

None - This is a visual update only. All APIs and configurations remain backward compatible.

---

## 🚀 Upgrade Instructions

### From v0.0.22

```bash
# Pull latest image
docker pull ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:v0.0.23

# Or using Helm
helm upgrade smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  --set image.tag=v0.0.23

# Or using kubectl
kubectl set image deployment/smart-autoscaler \
  smart-autoscaler=ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:v0.0.23 \
  -n autoscaler-system
```

### Update Cost Configuration (Optional)

If you want to use the new 1:8 cost ratio:

```bash
kubectl edit configmap smart-autoscaler-config -n autoscaler-system
```

Change:
```yaml
COST_PER_GB_MEMORY_HOUR: "0.005"  # Was 0.004
```

---

## 📊 What's Next (v0.0.24)

- 🤖 Full GenAI integration with LLM-powered recommendations
- 🏷️ Label-based auto-discovery (no manual deployment configuration)
- 📱 Mobile-responsive dashboard
- 🔐 RBAC and authentication
- 📧 Email notifications
- 🌐 Multi-cluster support

---

## 🙏 Acknowledgments

Special thanks to the community for feedback on the UI design!

---

## 📝 Notes

This is a **pre-release** version. The UI redesign is stable, but GenAI features are experimental and under active development. Use in production at your own discretion.

For production use, we recommend v0.0.22-v3 (stable).

---

## 📖 Full Documentation

- [README.md](../README.md) - Project overview
- [QUICKSTART.md](../QUICKSTART.md) - 5-minute setup
- [GETTING_STARTED.md](../GETTING_STARTED.md) - 60-second setup
- [docs/](../docs/) - Complete documentation

---

**Version**: v0.0.23  
**Status**: Pre-Release  
**Stability**: Beta  
**Recommended for**: Testing and evaluation
