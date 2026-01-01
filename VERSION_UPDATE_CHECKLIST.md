# Version Update Checklist

When updating the version, follow these steps to avoid test failures:

## 1. Update Version Number

```bash
# Edit src/__init__.py
__version__ = "X.Y.Z"
```

## 2. Create Changelog

```bash
# Create changelog file
touch changelogs/CHANGELOG_vX.Y.Z.md

# Add content following the template
```

## 3. Update Documentation (if needed)

- [ ] README.md - Update version badge if present
- [ ] FEATURES_SUMMARY.md - Update version at top
- [ ] Any other docs mentioning version

## 4. Run Tests

```bash
# Run tests to ensure they pass
./run_tests.sh

# Or manually
python3.12 -m pytest tests/ -v --cov=src --cov-report=term --cov-fail-under=25
```

## 5. Commit and Tag

```bash
# Commit changes
git add .
git commit -m "Release vX.Y.Z: Brief description"

# Create tag
git tag -a vX.Y.Z -m "Release vX.Y.Z: Description"

# Push
git push origin <branch>
git push origin vX.Y.Z
```

## Common Mistakes to Avoid

### ❌ DON'T: Hardcode version in tests
```python
# Bad - will break on every version update
assert src.__version__ == "0.0.9"
```

### ✅ DO: Check version format instead
```python
# Good - checks format, not specific version
import re
assert re.match(r'^\d+\.\d+\.\d+$', src.__version__)
```

### ❌ DON'T: Update version without changelog
- Always create a changelog file for the new version
- Document what changed, why, and how to use new features

### ✅ DO: Follow semver
- MAJOR.MINOR.PATCH (e.g., 1.2.3)
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes (backward compatible)

## Automated Checks

The CI pipeline now includes:
- ✅ Version format validation (semver)
- ✅ Changelog existence check (warning only)
- ✅ Test suite runs on all PRs

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 0.0.11 | 2026-01-01 | Cluster monitoring + Priority scaling |
| 0.0.10 | 2026-01-01 | Priority-based scaling |
| 0.0.9 | 2025-12-XX | Smart dashboard features |
| 0.0.6 | 2025-XX-XX | Core features |

## Quick Commands

```bash
# Check current version
grep __version__ src/__init__.py

# List all version tags
git tag -l | grep ^v

# See what changed in a version
git show vX.Y.Z

# Compare two versions
git diff vX.Y.Z..vA.B.C
```
