# Base Image Strategy

Ultra-fast Docker builds using a pre-built base image with Python dependencies.

---

## 🚀 The Problem

Traditional Docker builds install Python dependencies every time:

```dockerfile
# Slow: Installs dependencies on every build
COPY requirements.txt .
RUN pip install -r requirements.txt  # ← 2-3 minutes every time!
COPY src/ ./src/
```

**Result**: Even code-only changes take 3-5 minutes to build.

---

## ⚡ The Solution

Split into two images:

### 1. Base Image (Rarely Changes)
Contains all Python dependencies:
- Built when `requirements.txt` changes
- Cached and reused
- Takes 5-8 minutes to build
- Built once, used many times

### 2. App Image (Changes Frequently)
Contains only code and templates:
- Uses pre-built base image
- Only copies files
- Takes **10-30 seconds** to build! 🚀
- Rebuilt on every code change

---

## 📊 Build Time Comparison

| Change Type | Old Build | New Build | Speedup |
|-------------|-----------|-----------|---------|
| **Code only** | 3-5 min | **10-30 sec** | 🚀 **10x faster!** |
| **Templates only** | 3-5 min | **10-30 sec** | 🚀 **10x faster!** |
| **Dependencies** | 3-5 min | 5-8 min | Same (rare) |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Base Image (ghcr.io/.../autoscaler-base:latest)        │
│                                                          │
│ • Python 3.12                                           │
│ • All pip dependencies (kubernetes, flask, etc.)       │
│ • System libraries (gcc, sqlite, etc.)                 │
│ • User setup                                            │
│                                                          │
│ Built when: requirements.txt changes                    │
│ Build time: 5-8 minutes                                 │
│ Frequency: Rarely (once per week/month)                │
└─────────────────────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────┐
│ App Image (ghcr.io/.../autoscaler:v0.0.23)             │
│                                                          │
│ FROM base image ↑                                       │
│ COPY src/                                               │
│ COPY templates/                                         │
│                                                          │
│ Built when: Code changes                                │
│ Build time: 10-30 seconds ⚡                            │
│ Frequency: Every commit                                 │
└─────────────────────────────────────────────────────────┘
```

---

## 📝 Files

### Dockerfile.base
Builds the base image with all dependencies:
```dockerfile
FROM python:3.12-slim
COPY requirements-enhanced.txt .
RUN pip install -r requirements-enhanced.txt
# ... system setup ...
```

### Dockerfile.fast
Builds the app using the base image:
```dockerfile
FROM ghcr.io/.../autoscaler-base:latest
COPY src/ ./src/
COPY templates/ ./templates/
# Done! ⚡
```

### Dockerfile.enhanced
Traditional build (fallback):
```dockerfile
FROM python:3.12-slim
# Install everything from scratch
```

---

## 🔄 Workflow

### Automatic (GitHub Actions)

**When requirements.txt changes:**
1. `.github/workflows/build-base.yml` triggers
2. Builds new base image
3. Pushes to `ghcr.io/.../autoscaler-base:HASH`
4. Updates `latest` tag

**When code changes:**
1. `.github/workflows/ci.yml` detects code-only change
2. Uses `Dockerfile.fast` with base image
3. Builds in 10-30 seconds ⚡
4. Pushes app image

### Manual (Local Development)

**Build base image:**
```bash
./scripts/build-base-image.sh
```

**Build app (fast):**
```bash
docker build -f Dockerfile.fast -t myapp:test .
```

---

## 🎯 When to Use Each Dockerfile

| Dockerfile | Use When | Build Time |
|------------|----------|------------|
| **Dockerfile.fast** | Code/template changes | 10-30 sec ⚡ |
| **Dockerfile.enhanced** | Dependencies changed | 3-5 min |
| **Dockerfile.base** | Building base image | 5-8 min |

---

## 🔧 Configuration

### Change Detection

The CI workflow automatically detects what changed:

```yaml
detect-changes:
  outputs:
    requirements-changed: ${{ steps.changes.outputs.requirements }}
    use-fast-build: ${{ steps.changes.outputs.requirements != 'true' }}
```

**Logic:**
- If `requirements.txt` changed → Full build
- If only code changed → Fast build
- If only docs changed → Skip build

### Base Image Versioning

Base images are tagged with:
1. **Hash of requirements.txt** - `base:a1b2c3d4`
2. **Latest** - `base:latest`

This ensures:
- ✅ Reproducible builds
- ✅ Cache hits
- ✅ Easy rollback

---

## 📈 Real-World Example

### Scenario: Fix a bug in src/operator.py

**Old workflow:**
```bash
git commit -m "Fix bug"
git push
# → GitHub Actions builds for 3-5 minutes
# → Installs all dependencies again
# → Finally copies code
```

**New workflow:**
```bash
git commit -m "Fix bug"
git push
# → GitHub Actions detects code-only change
# → Uses Dockerfile.fast with base image
# → Builds in 10-30 seconds ⚡
# → Done!
```

**Time saved**: 2-4 minutes per build!

---

## 🚀 Getting Started

### 1. Build Base Image (One Time)

```bash
# Automatic (push to main)
git add requirements-enhanced.txt
git commit -m "Update dependencies"
git push origin main
# → Base image builds automatically

# Or manual
./scripts/build-base-image.sh
docker push ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler-base:latest
```

### 2. Use Fast Builds

From now on, code changes build in seconds:

```bash
# Make code changes
vim src/operator.py

# Commit and push
git commit -m "Fix bug"
git push
# → Builds in 10-30 seconds! ⚡
```

---

## 🔍 Troubleshooting

### Base image not found

**Error**: `failed to resolve source metadata for ghcr.io/.../autoscaler-base:latest`

**Solution**: Build the base image first:
```bash
./scripts/build-base-image.sh
docker push ghcr.io/.../autoscaler-base:latest
```

### Slow builds despite using fast Dockerfile

**Check**: Is the base image cached?
```bash
docker pull ghcr.io/.../autoscaler-base:latest
```

**Check**: Did requirements.txt change?
```bash
git diff HEAD~1 requirements-enhanced.txt
```

### Want to force full build

Use the enhanced Dockerfile:
```bash
docker build -f Dockerfile.enhanced -t myapp:test .
```

---

## 💡 Tips

### 1. Keep requirements.txt stable

Group dependency updates:
```bash
# Bad: Update one at a time (rebuilds base each time)
pip install package1==1.0
git commit && git push  # Base rebuild
pip install package2==2.0
git commit && git push  # Base rebuild again

# Good: Update together
pip install package1==1.0 package2==2.0
git commit && git push  # Single base rebuild
```

### 2. Use base image hash for reproducibility

```dockerfile
# Pinned to specific requirements
FROM ghcr.io/.../autoscaler-base:a1b2c3d4

# Always latest (may change)
FROM ghcr.io/.../autoscaler-base:latest
```

### 3. Local development

Pull the base image once:
```bash
docker pull ghcr.io/.../autoscaler-base:latest
```

Then use fast builds:
```bash
docker build -f Dockerfile.fast -t test:latest .
# → 10-30 seconds!
```

---

## 📊 Statistics

After implementing base images:

- **Average build time**: 10-30 seconds (was 3-5 minutes)
- **Time saved per build**: 2-4 minutes
- **Builds per day**: ~10-20
- **Total time saved per day**: 20-80 minutes! 🎉

---

## 🔗 Related

- [Fast Builds Guide](FAST_BUILDS.md) - All build optimizations
- [CI/CD Pipeline](.github/workflows/ci.yml) - Workflow configuration
- [Release Guide](../RELEASE_GUIDE.md) - How to release

---

**Result**: Code changes now build in **10-30 seconds** instead of 3-5 minutes! 🚀
