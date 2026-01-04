# Docker Build Strategy

## Overview

We provide multiple Dockerfile options optimized for different use cases:

| Dockerfile | Size | Build Time | Use Case |
|------------|------|------------|----------|
| `Dockerfile.minimal` | ~200-300MB | 1-2 min | Production (no ML/AI) |
| `Dockerfile.fast` | ~400-500MB | 10-30 sec | Development (with base image) |
| `Dockerfile.enhanced` | ~400-500MB | 3-5 min | Production (full features) |
| `Dockerfile.base` | ~350-400MB | 2-3 min | Base image (dependencies only) |

## Quick Start

### Option 1: Minimal Build (Recommended for Production)
**Smallest image, no ML/AI features**

```bash
docker build -f Dockerfile.minimal -t smart-autoscaler:minimal .
```

**Features:**
- ✅ Core autoscaling
- ✅ HPA management
- ✅ Cost optimization
- ✅ Dashboard
- ❌ Predictive scaling (no ML)
- ❌ GenAI features

**Image size:** ~200-300MB

### Option 2: Fast Build (Recommended for Development)
**Fastest builds using pre-built base image**

```bash
# First time: Build base image
./scripts/build-base-image.sh

# Daily: Fast builds (10-30 seconds!)
docker build -f Dockerfile.fast -t smart-autoscaler:latest .
```

**Features:**
- ✅ All features included
- ✅ 10x faster builds
- ✅ Perfect for development
- ⚠️ Requires base image

**Build time:** 10-30 seconds (after base image built)

### Option 3: Enhanced Build (Full Features)
**Complete build with all features**

```bash
docker build -f Dockerfile.enhanced -t smart-autoscaler:enhanced .
```

**Features:**
- ✅ All features included
- ✅ Predictive scaling (ML)
- ✅ GenAI support (optional)
- ✅ No base image needed

**Build time:** 3-5 minutes

## Dependency Management

### Core Dependencies (Always Included)
```
kubernetes==29.0.0          # K8s API client
prometheus-api-client==0.5.5 # Metrics
flask==3.0.0                # Dashboard
numpy==1.26.4               # Math operations
psutil==5.9.8               # System monitoring
```

### ML Dependencies (Optional - Enhanced/Fast only)
```
scikit-learn==1.3.2         # Predictive scaling
scipy==1.11.4               # Statistical analysis
statsmodels==0.14.1         # Time series
```

**Size impact:** +200-300MB

### GenAI Dependencies (Optional - Install separately)
```
openai>=1.0.0               # OpenAI GPT
google-generativeai>=0.5.0  # Google Gemini
anthropic>=0.18.0           # Anthropic Claude
```

**Size impact:** +100-200MB per provider

## Build Optimization Techniques

### 1. Multi-Stage Builds
All Dockerfiles use multi-stage builds to separate build and runtime:

```dockerfile
# Build stage - includes compilers
FROM python:3.12-slim AS builder
RUN apt-get install build-essential gcc g++
RUN pip install --prefix=/install -r requirements.txt

# Runtime stage - minimal
FROM python:3.12-slim
COPY --from=builder /install /usr/local
```

**Benefit:** Removes build tools from final image (~100-150MB savings)

### 2. Layer Caching
Dependencies are installed before copying code:

```dockerfile
COPY requirements.txt .
RUN pip install -r requirements.txt  # Cached layer
COPY src/ ./src/                     # Changes frequently
```

**Benefit:** Faster rebuilds when only code changes

### 3. Base Image Strategy
Pre-build dependencies once, reuse many times:

```bash
# Build base (once per week)
docker build -f Dockerfile.base -t base:latest .

# Build app (many times per day)
docker build -f Dockerfile.fast --build-arg BASE_IMAGE=base:latest .
```

**Benefit:** 10x faster daily builds

### 4. Minimal Runtime Dependencies
Only install what's needed at runtime:

```dockerfile
# ❌ Don't include
build-essential gcc g++ python3-dev

# ✅ Do include
sqlite3 curl ca-certificates
```

**Benefit:** Smaller image, fewer security vulnerabilities

## Image Size Comparison

### Before Optimization
```
smart-autoscaler:old    850MB
├── Python base         150MB
├── Build tools         200MB (unnecessary!)
├── ML libraries        400MB
└── Application         100MB
```

### After Optimization (Minimal)
```
smart-autoscaler:minimal    250MB
├── Python base             150MB
├── Core dependencies        80MB
└── Application              20MB
```

### After Optimization (Enhanced)
```
smart-autoscaler:enhanced   450MB
├── Python base             150MB
├── Core dependencies        80MB
├── ML libraries            200MB
└── Application              20MB
```

**Savings:** 400-600MB (47-70% reduction)

## Security Best Practices

### 1. Non-Root User
All images run as non-root user:

```dockerfile
RUN groupadd -r operator && \
    useradd -r -g operator -u 1000 operator
USER operator
```

### 2. Minimal Attack Surface
Only essential packages installed:

```dockerfile
RUN apt-get install -y --no-install-recommends \
    sqlite3 curl ca-certificates
```

### 3. No Build Tools in Production
Build tools removed from final image:

```dockerfile
# Build stage only
FROM python:3.12-slim AS builder
RUN apt-get install build-essential

# Runtime stage - no build tools
FROM python:3.12-slim
COPY --from=builder /install /usr/local
```

## CI/CD Integration

### GitHub Actions (Recommended)

```yaml
# .github/workflows/docker-build.yml
- name: Build minimal image
  run: docker build -f Dockerfile.minimal -t $IMAGE:minimal .

- name: Build enhanced image
  run: docker build -f Dockerfile.enhanced -t $IMAGE:enhanced .
```

### Local Development

```bash
# Use fast builds
./scripts/build-base-image.sh
docker build -f Dockerfile.fast -t dev:latest .
```

## Troubleshooting

### Issue: "Base image not found"
**Solution:** Build base image first:
```bash
./scripts/build-base-image.sh
```

### Issue: "Image too large"
**Solution:** Use minimal build:
```bash
docker build -f Dockerfile.minimal -t app:minimal .
```

### Issue: "Missing ML dependencies"
**Solution:** Use enhanced build:
```bash
docker build -f Dockerfile.enhanced -t app:enhanced .
```

### Issue: "Slow builds"
**Solution:** Use fast build with base image:
```bash
./scripts/build-base-image.sh
docker build -f Dockerfile.fast -t app:latest .
```

## Recommendations

### For Production
- ✅ Use `Dockerfile.minimal` if you don't need ML/AI
- ✅ Use `Dockerfile.enhanced` if you need all features
- ✅ Enable multi-arch builds (linux/amd64, linux/arm64)
- ✅ Scan images for vulnerabilities
- ✅ Use specific version tags (not `latest`)

### For Development
- ✅ Use `Dockerfile.fast` with base image
- ✅ Build base image weekly
- ✅ Use local single-arch builds
- ✅ Enable BuildKit for faster builds

### For CI/CD
- ✅ Build base image when requirements change
- ✅ Use fast builds for code changes
- ✅ Cache Docker layers
- ✅ Use GitHub Actions for multi-arch builds

## Performance Metrics

### Build Times (M1 MacBook Pro)
- Minimal: 1-2 minutes
- Enhanced: 3-5 minutes
- Fast (after base): 10-30 seconds
- Base image: 2-3 minutes

### Image Sizes
- Minimal: 250-300MB
- Enhanced: 400-500MB
- Base: 350-400MB

### Startup Times
- All variants: 2-5 seconds
- No significant difference

## Future Improvements

- [ ] Alpine-based images (even smaller)
- [ ] Distroless images (maximum security)
- [ ] ARM64 native builds
- [ ] Layer compression optimization
- [ ] Dependency vendoring

## References

- [Docker Multi-Stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Python Docker Images](https://hub.docker.com/_/python)
