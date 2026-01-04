# Scripts

Automation scripts for Smart Autoscaler.

## Release Script

**Quick release automation** - Updates versions, creates changelog, commits, and pushes.

### Usage

```bash
# Stable release
./scripts/release.sh 0.0.24 "Fix memory leak in prediction engine"

# Pre-release (beta/alpha/rc)
./scripts/release.sh 0.0.25-beta "New feature (testing)" --pre-release

# Quick fix
./scripts/release.sh 0.0.24-v2 "Hotfix for dashboard crash"
```

### What it does

1. Updates version in `src/__init__.py`
2. Updates version badge in `README.md`
3. Updates Helm chart version (`Chart.yaml`)
4. Creates changelog file (`changelogs/CHANGELOG_vX.X.X.md`)
5. Updates README version history table
6. Commits all changes
7. Pushes to `dev` branch
8. Merges `dev` → `main`
9. Creates and pushes git tag
10. Returns to `dev` branch

### After running

The script will show you the GitHub release URL. Just:
1. Click the link
2. Add release notes (or use the generated changelog)
3. Check "pre-release" if it's a beta
4. Publish

GitHub Actions will automatically build the Docker image.

---

## Generate Helm Values

**Auto-generate Helm values** for many deployments.

### Usage

```bash
# Auto-discover HPAs from cluster
python3 scripts/generate-helm-values.py --auto-discover -o my-values.yaml

# From CSV file
python3 scripts/generate-helm-values.py --csv deployments.csv -o my-values.yaml

# Generate CSV template
python3 scripts/generate-helm-values.py --template > deployments.csv
```

### CSV Format

```csv
namespace,deployment,hpa_name,startup_filter,priority
production,api-gateway,api-gateway-hpa,2,critical
production,auth-service,auth-service-hpa,3,critical
```

Then install:
```bash
helm install smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  --values my-values.yaml
```

---

## Deployment Scripts

### GKE Deployment

```bash
./scripts/deploy-gke.sh
```

Deploys to Google Kubernetes Engine.

### OrbStack Deployment

```bash
./scripts/deploy-orbstack.sh
```

Deploys to local OrbStack Kubernetes.

---

## Tips

### Make scripts executable

```bash
chmod +x scripts/*.sh
```

### Daily workflow

```bash
# Make changes...
# Test...

# Release
./scripts/release.sh 0.0.X "Your changes description"

# Done! 🎉
```

### Version naming

- **Stable**: `0.0.24`
- **Pre-release**: `0.0.24-beta`, `0.0.24-alpha`, `0.0.24-rc1`
- **Hotfix**: `0.0.24-v2`, `0.0.24-v3`

The script auto-detects pre-releases from version name or `--pre-release` flag.
