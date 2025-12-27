# CI/CD Setup Guide

## Overview

This project includes a GitHub Actions workflow that automatically:
- ✅ Detects source code changes in `src/` directory
- ✅ Auto-increments version (starting from v0.0.1)
- ✅ Builds multi-arch Docker images (amd64, arm64)
- ✅ Pushes to GitHub Container Registry (ghcr.io)
- ✅ Creates Git tags for each release

## Workflow File

Location: `.github/workflows/ci.yml`

## How It Works

### 1. **Change Detection**
The workflow triggers when:
- Code is pushed/merged to `main` branch
- Files in `src/` directory change
- Dockerfile or requirements files change

### 2. **Version Management**
- **Starting version**: `v0.0.1` (set in `src/__init__.py`)
- **Auto-increment**: Patch version (0.0.1 → 0.0.2 → 0.0.3)
- **Version source**: `src/__init__.py`

### 3. **Build Process**
1. Detects if source code changed
2. Reads current version from `src/__init__.py`
3. Calculates new version (increments patch)
4. Updates `src/__init__.py` with new version
5. Builds Docker image using `Dockerfile.enhanced`
6. Pushes to `ghcr.io/<owner>/<repo>`
7. Creates Git tag (e.g., `v0.0.2`)

## Setup Instructions

### 1. **Initial Setup**

1. Ensure `src/__init__.py` has version `0.0.1`:
   ```python
   __version__ = "0.0.1"
   ```

2. Push the workflow file to your repository:
   ```bash
   git add .github/workflows/ci.yml
   git commit -m "ci: add GitHub Actions workflow"
   git push origin main
   ```

### 2. **GitHub Container Registry Setup**

The workflow uses `GITHUB_TOKEN` automatically (no setup needed).

**For public repositories**: Images are public by default.

**For private repositories**: 
1. Go to repository → Packages
2. Click on the package
3. Package settings → Change visibility to Public (if needed)

### 3. **Using the Built Images**

#### Pull Image
```bash
docker pull ghcr.io/<your-org>/enhanced-smart-k8s-autoscaler:v0.0.1
```

#### Update Kubernetes Deployment
```yaml
# k8s/deployment.yaml
image: ghcr.io/<your-org>/enhanced-smart-k8s-autoscaler:v0.0.1
```

Replace `<your-org>` with your GitHub username or organization.

## Image Tags

The workflow creates multiple tags:
- `v0.0.1`, `v0.0.2`, etc. (specific versions with 'v' prefix)
- `0.0.1`, `0.0.2`, etc. (specific versions without 'v' prefix)
- `0.0`, `0.1` (major.minor tags)
- `latest` (only on main branch)

## Manual Version Bump

If you need to manually bump version:

```bash
# Bump patch version (0.0.1 → 0.0.2)
./.github/workflows/version-bump.sh patch

# Bump minor version (0.0.1 → 0.1.0)
./.github/workflows/version-bump.sh minor

# Bump major version (0.0.1 → 1.0.0)
./.github/workflows/version-bump.sh major
```

## Workflow Status

Check workflow status:
1. Go to repository → Actions tab
2. View latest workflow run
3. Check build logs and image push status

## Troubleshooting

### Workflow Not Triggering
- Ensure changes are in `src/` directory
- Check that workflow file is in `.github/workflows/`
- Verify you're pushing to `main` branch

### Image Push Fails
- Check repository permissions
- Ensure `GITHUB_TOKEN` has `packages:write` permission
- Verify package visibility settings

### Version Not Updating
- Check `src/__init__.py` format
- Verify workflow has write permissions
- Check workflow logs for errors

## Example Workflow Run

```
1. Developer pushes code to main
2. Workflow detects src/ changes
3. Current version: 0.0.1
4. New version: 0.0.2
5. Updates src/__init__.py
6. Builds Docker image
7. Pushes to ghcr.io/<org>/<repo>:v0.0.2
8. Creates Git tag v0.0.2
9. ✅ Success!
```

## Next Steps

1. **First Run**: Push a change to `src/` directory to trigger first build
2. **Verify**: Check Actions tab to see workflow running
3. **Test**: Pull the image and verify it works
4. **Deploy**: Update Kubernetes deployment to use new image

---

**Note**: Replace `<your-org>` with your actual GitHub username or organization name in all examples.

