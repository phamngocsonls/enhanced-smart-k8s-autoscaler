# Release v0.0.23 - Professional UI & GenAI Integration (Pre-Release)

## 🚀 Quick Release (Use This!)

```bash
# One command to do everything:
./scripts/release.sh 0.0.23 "Professional UI redesign, GenAI integration (pre-release)" --pre-release
```

That's it! The script will:
1. ✅ Update version in `src/__init__.py`
2. ✅ Update version badge in `README.md`
3. ✅ Update Helm chart version
4. ✅ Create changelog file
5. ✅ Update README version history
6. ✅ Commit changes
7. ✅ Push to dev → merge to main
8. ✅ Create and push git tag

Then just create the GitHub release manually (link provided by script).

---

## 📝 For Future Releases

```bash
# Stable release
./scripts/release.sh 0.0.24 "Fix memory leak in prediction engine"

# Pre-release
./scripts/release.sh 0.0.25-beta "New feature (testing)" --pre-release

# Quick fix
./scripts/release.sh 0.0.24-v2 "Hotfix for dashboard crash"
```

---

## 🎨 Major UI Redesign

Complete visual overhaul with professional, enterprise-grade appearance:

- **Professional SVG Icons** - Replaced all emoji icons with Material Design-style vectors
- **Enterprise Logo** - New shield/clock icon for professional branding  
- **Clean Navigation** - Scalable icons with smooth hover effects
- **Grafana-Inspired** - Dashboard now looks like enterprise monitoring tools

## 🤖 GenAI Integration (Experimental)

Foundation work for AI-powered features:
- LLM-powered scaling recommendations (coming soon)
- Natural language queries (in development)
- Automated incident reports (planned)

**Status**: Pre-release / Beta

## 📚 Comprehensive Documentation

New guides for easy onboarding:
- **60-second setup** guide
- **Helm publishing** guide  
- **Scaling configuration** for 100+ deployments
- **Startup filter** for Java/JVM apps
- **Architecture** diagrams and examples

## ⚙️ Configuration Updates

- Updated CPU:Memory cost ratio from 1:10 to **1:8** (more accurate)
- New example files and templates
- Auto-generation scripts for Helm values

## 🚀 Git Release Commands

```bash
# 1. Commit all changes
git add -A
git commit -m "v0.0.23: Professional UI redesign, GenAI integration (pre-release), comprehensive docs"

# 2. Push to dev
git push origin dev

# 3. Merge to main
git checkout main
git merge dev
git push origin main

# 4. Create pre-release tag
git tag -a v0.0.23-beta -m "v0.0.23: Professional UI & GenAI Integration (Pre-Release)"
git push origin v0.0.23-beta

# 5. Go back to dev
git checkout dev
```

## 📦 GitHub Release

Create a pre-release on GitHub:

1. Go to: https://github.com/phamngocsonls/enhanced-smart-k8s-autoscaler/releases/new
2. Tag: `v0.0.23-beta`
3. Title: `v0.0.23 - Professional UI & GenAI Integration (Pre-Release)`
4. Description: Copy from `changelogs/CHANGELOG_v0.0.23.md`
5. ✅ Check "This is a pre-release"
6. Publish

## 🐳 Docker Build

The GitHub Actions workflow will automatically build and push:
- `ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:v0.0.23-beta`
- `ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:latest` (not updated for pre-release)

## 📊 What's Included

### UI Changes
- ✨ Professional SVG icons throughout
- 🎯 Enterprise-grade appearance
- 💼 Consistent styling and branding

### Documentation
- 📚 5 new comprehensive guides
- 🛠️ 2 automation scripts
- 📝 3 ready-to-use example files

### Configuration
- ⚙️ Updated cost ratios (1:8)
- 📦 Better Helm chart metadata
- 🔧 Improved defaults

## ⚠️ Pre-Release Notice

This is a **beta/pre-release** version:
- ✅ UI redesign is stable and production-ready
- ⚠️ GenAI features are experimental
- 📝 Documentation is complete

**For production**: Use v0.0.22-v3 (stable) or test v0.0.23-beta first.

## 🔄 Upgrade Path

From v0.0.22:
```bash
# Update image tag
kubectl set image deployment/smart-autoscaler \
  smart-autoscaler=ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:v0.0.23-beta \
  -n autoscaler-system

# Or with Helm
helm upgrade smart-autoscaler ./helm/smart-autoscaler \
  --set image.tag=v0.0.23-beta
```

## 📖 Documentation

- [CHANGELOG_v0.0.23.md](changelogs/CHANGELOG_v0.0.23.md) - Full changelog
- [README.md](README.md) - Updated with v0.0.23
- [GETTING_STARTED.md](GETTING_STARTED.md) - 60-second setup
- [docs/](docs/) - All new guides

---

**Ready to release!** 🚀
