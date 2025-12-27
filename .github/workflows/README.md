# CI/CD Workflow

## Overview

This workflow automatically builds and pushes Docker images to GitHub Container Registry (ghcr.io) when:
- Code is merged to `main` branch
- Source code in `src/` directory changes
- Dockerfile or requirements files change

## Versioning

- **Starting version**: `v0.0.1`
- **Auto-increment**: Patch version (0.0.1 → 0.0.2 → 0.0.3)
- **Version source**: `src/__init__.py`

## Workflow Steps

1. **Detect Changes**: Checks if source code or Dockerfile changed
2. **Get Current Version**: Reads version from `src/__init__.py`
3. **Calculate New Version**: Increments patch version
4. **Update Version**: Updates `src/__init__.py` with new version
5. **Build Docker Image**: Builds multi-arch image (amd64, arm64)
6. **Push to GHCR**: Pushes to `ghcr.io/<owner>/<repo>`
7. **Create Git Tag**: Creates version tag (e.g., `v0.0.2`)

## Image Tags

The workflow creates multiple tags:
- `v0.0.1`, `v0.0.2`, etc. (specific versions)
- `0.0.1`, `0.0.2`, etc. (without 'v' prefix)
- `0.0`, `0.1` (major.minor)
- `latest` (only on main branch)

## Usage

### Pull Image
```bash
docker pull ghcr.io/<owner>/<repo>:v0.0.1
```

### Use in Kubernetes
```yaml
image: ghcr.io/<owner>/<repo>:v0.0.1
```

### Public Access
If your repository is private, you may need to make the package public:
1. Go to repository → Packages
2. Click on the package
3. Package settings → Change visibility to Public

## Manual Trigger

The workflow runs automatically on push to main. To trigger manually:
1. Make a change to `src/` directory
2. Commit and push to `main`
3. Workflow will detect changes and build

## Skip CI

To skip CI (e.g., for documentation-only changes):
```bash
git commit -m "docs: update README [skip ci]"
```

