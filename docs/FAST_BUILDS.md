# Fast Docker Builds

How the CI/CD pipeline is optimized for speed.

---

## ⚡ Speed Optimizations

### 1. **Smart Platform Selection**

**Pre-releases (beta/alpha/rc)**: Build only `linux/amd64` (2-3x faster!)
```yaml
platforms: linux/amd64  # ~3-5 minutes
```

**Stable releases**: Build multi-arch `linux/amd64,linux/arm64`
```yaml
platforms: linux/amd64,linux/arm64  # ~8-12 minutes
```

### 2. **GitHub Actions Cache**

Uses GitHub Actions cache for Docker layers:
```yaml
cache-from: type=gha
cache-to: type=gha,mode=max
```

**Result**: Subsequent builds reuse layers → 50-70% faster!

### 3. **BuildKit Optimizations**

```yaml
driver-opts: |
  image=moby/buildkit:latest
  network=host
build-args: |
  BUILDKIT_INLINE_CACHE=1
```

**Benefits**:
- Parallel layer builds
- Better caching
- Faster image pushes

### 4. **Change Detection**

Only builds when source code changes:
```yaml
detect-changes:
  outputs:
    src-changed: ${{ steps.changes.outputs.src }}
    should-build: ${{ steps.changes.outputs.src == 'true' }}
```

**Result**: Doc-only changes skip Docker build!

### 5. **Python Dependency Caching**

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: '3.12'
    cache: 'pip'  # Caches pip packages
```

**Result**: Test setup 2-3x faster!

---

## 📊 Build Times

| Scenario | Time | Platforms |
|----------|------|-----------|
| **Pre-release (beta)** | ~3-5 min | amd64 only |
| **Stable release** | ~8-12 min | amd64 + arm64 |
| **Main branch** | ~3-5 min | amd64 only |
| **Cached build** | ~2-3 min | Any |
| **Doc-only change** | ~1 min | No build |

---

## 🎯 How It Works

### Pre-Release (Fast)

```bash
# Tag with beta/alpha/rc
git tag v0.0.23-beta

# Workflow detects pre-release
# → Builds only amd64
# → Skips latest tag
# → Marks as pre-release on GitHub
```

**Build time**: ~3-5 minutes ⚡

### Stable Release (Complete)

```bash
# Tag without suffix
git tag v0.0.24

# Workflow detects stable
# → Builds amd64 + arm64
# → Updates latest tag
# → Marks as stable on GitHub
```

**Build time**: ~8-12 minutes 🏗️

---

## 💡 Tips for Faster Builds

### 1. Use Pre-Releases for Testing

```bash
# Fast iteration
./scripts/release.sh 0.0.23-beta "Testing new feature" --pre-release
# → 3-5 min build

# When stable
./scripts/release.sh 0.0.24 "Stable release"
# → 8-12 min build with multi-arch
```

### 2. Group Changes

Instead of:
```bash
git commit -m "Fix bug 1"
git push  # Build triggered
git commit -m "Fix bug 2"
git push  # Build triggered again
```

Do:
```bash
git commit -m "Fix bug 1"
git commit -m "Fix bug 2"
git push  # Single build
```

### 3. Use Draft Releases

```bash
# Push tag
git push origin v0.0.24

# Build starts automatically
# While building, prepare release notes
# Publish when ready
```

### 4. Skip CI for Docs

```bash
git commit -m "Update docs [skip ci]"
git push
# No build triggered
```

---

## 🔧 Advanced: Local Multi-Arch Builds

If you need to test multi-arch locally:

```bash
# Setup buildx
docker buildx create --name multiarch --use

# Build multi-arch
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t myimage:test \
  -f Dockerfile.enhanced \
  --push \
  .
```

**Note**: This is slow locally. Use CI for multi-arch builds.

---

## 📈 Optimization Results

**Before optimizations**:
- Every build: 10-15 minutes
- Multi-arch always
- No caching
- No change detection

**After optimizations**:
- Pre-release: 3-5 minutes (60% faster!)
- Stable: 8-12 minutes (20% faster)
- Cached: 2-3 minutes (80% faster!)
- Doc changes: Skip build (100% faster!)

---

## 🎯 Summary

| Build Type | Speed | Use When |
|------------|-------|----------|
| **Pre-release** | ⚡⚡⚡ Fast | Daily testing, beta features |
| **Stable** | ⚡⚡ Medium | Production releases |
| **Cached** | ⚡⚡⚡ Fast | No dependency changes |
| **Doc-only** | ⚡⚡⚡⚡ Instant | Documentation updates |

**Recommendation**: Use pre-releases (beta) for daily work, stable releases for production!

---

## 🔍 Monitoring Builds

Check build status:
- https://github.com/phamngocsonls/enhanced-smart-k8s-autoscaler/actions

View build logs:
- Click on workflow run
- Expand "Build and push Docker image"
- See layer caching in action!

---

## 🚀 Next Steps

Want even faster builds?

1. **Use Docker layer caching** in Dockerfile
2. **Minimize dependencies** in requirements.txt
3. **Use smaller base image** (alpine vs debian)
4. **Pre-build base images** with common dependencies

See [Dockerfile.enhanced](../Dockerfile.enhanced) for current optimizations.
