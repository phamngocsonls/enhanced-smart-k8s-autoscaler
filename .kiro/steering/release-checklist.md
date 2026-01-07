# Release Checklist for Smart Autoscaler

Read this checklist before creating a new release.

## Quick Release (using script)

```bash
./scripts/release.sh <version> "<message>"

# Examples:
./scripts/release.sh 0.0.33 "New feature X"
./scripts/release.sh 0.0.33-v1 "Hotfix for bug Y"
```

The script automatically:
1. Updates version in 7 files
2. Runs tests
3. Commits changes
4. Pushes to main
5. Creates and pushes tag

### Files Updated by Script

| File | What Gets Updated |
|------|-------------------|
| `src/__init__.py` | `__version__ = "X.Y.Z"` (base version) |
| `helm/smart-autoscaler/Chart.yaml` | `version: X.Y.Z`, `appVersion: "X.Y.Z"` |
| `helm/smart-autoscaler/values.yaml` | `tag: "X.Y.Z-vN"` (full version) |
| `k8s/deployment.yaml` | `image: ...X.Y.Z-vN` |
| `scripts/deploy-orbstack.sh` | `image: ...X.Y.Z-vN` |
| `README.md` | Version badge + helm examples |
| `QUICKSTART.md` | Helm examples |

---

## Step-by-Step Release Process

### Step 1: Pre-Release Checks

```bash
# 1. Check for uncommitted changes
git status

# 2. Run tests (must pass)
python3 -m pytest tests/ -q

# 3. Check coverage (must be ≥25%)
python3 -m pytest tests/ --cov=src --cov-report=term-missing | grep TOTAL
```

### Step 2: Decide Version Number

| Scenario | Version Format | Example |
|----------|----------------|---------|
| New feature release | `X.Y.Z` | `0.0.33` |
| First release of version | `X.Y.Z` or `X.Y.Z-v1` | `0.0.33` |
| Hotfix/bugfix | `X.Y.Z-vN` | `0.0.33-v2` |

### Step 3: Run Release Script

```bash
./scripts/release.sh 0.0.33 "Description of changes"
```

### Step 4: Verify GitHub Actions

1. Go to: https://github.com/phamngocsonls/enhanced-smart-k8s-autoscaler/actions
2. Check the CI workflow triggered by the tag
3. Wait for Docker image build to complete

### Step 5: Verify Docker Image

```bash
docker pull ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:0.0.33
```

### Step 6: Deploy and Test

```bash
# Update cluster
kubectl set image deployment/smart-autoscaler \
  operator=ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:0.0.33 \
  -n autoscaler-system

# Check logs
kubectl logs -f deployment/smart-autoscaler -n autoscaler-system
```

---

## Version Naming Convention

```
0.0.32      = Base version (src/__init__.py, Chart.yaml)
0.0.32-v1   = Full version with suffix (image tags, deployments)
0.0.32-v2   = Hotfix of same base version
0.0.33      = New release (increment base)
```

---

## Documentation Checklist (for new features)

- [ ] Create changelog: `changelogs/CHANGELOG_vX.Y.Z.md`
- [ ] Update `README.md` version history table
- [ ] Update `QUICK_REFERENCE.md` if config changes
- [ ] Update `.env.example` if new environment variables
- [ ] Create feature docs in `docs/` if needed

---

## CI/CD Tag Patterns

The CI workflow triggers on these tag patterns:
- `v*.*.*` → `v0.0.32`
- `v*.*.*-v*` → `v0.0.32-v1`

---

## Troubleshooting

### Image not building?
```bash
# Check tag format
git tag -l | tail -5

# Verify CI workflow file
cat .github/workflows/ci.yml | grep -A5 "tags:"
```

### Pod crash on startup?
```bash
# Check logs
kubectl logs -f <pod-name> -n autoscaler-system

# Common fix: release hotfix
./scripts/release.sh 0.0.32-v2 "Fix startup error"
```

### Tests failing?
```bash
# Run with verbose output
python3 -m pytest tests/ -v

# Run specific test
python3 -m pytest tests/test_basic.py -v
```

### Wrong version deployed?
```bash
# Check current image
kubectl get deployment smart-autoscaler -n autoscaler-system -o jsonpath='{.spec.template.spec.containers[0].image}'

# Force update
kubectl rollout restart deployment/smart-autoscaler -n autoscaler-system
```
