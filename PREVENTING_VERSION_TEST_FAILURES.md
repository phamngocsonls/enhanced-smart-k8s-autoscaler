# Preventing Version Test Failures

## Problem

When updating the version in `src/__init__.py`, tests fail because they check for a hardcoded version:

```python
# ❌ This breaks on every version update
assert src.__version__ == "0.0.9"
```

**Error:**
```
AssertionError: assert '0.0.11' == '0.0.9'
```

## Solution

### 1. Make Tests Version-Agnostic ✅

Instead of checking for a specific version, check that:
- Version exists
- Version follows semver format (X.Y.Z)

**Updated tests:**

```python
# tests/test_basic.py
def test_imports():
    """Test basic imports"""
    try:
        import src
        import re
        assert hasattr(src, '__version__')
        assert re.match(r'^\d+\.\d+\.\d+$', src.__version__), \
            f"Version {src.__version__} doesn't follow semver format"
    except Exception as e:
        pytest.fail(f"Import failed: {e}")

# tests/test_core_features.py
def test_version_value(self):
    """Test version exists and follows semver format"""
    import src
    import re
    assert hasattr(src, '__version__')
    assert re.match(r'^\d+\.\d+\.\d+$', src.__version__), \
        f"Version {src.__version__} doesn't follow semver format (X.Y.Z)"
```

### 2. Add Version Check Workflow ✅

Created `.github/workflows/version-check.yml` to automatically:
- Validate version format (semver)
- Check if changelog exists (warning only)
- Run on all PRs and pushes

### 3. Create Update Checklist ✅

Created `VERSION_UPDATE_CHECKLIST.md` with:
- Step-by-step version update process
- Common mistakes to avoid
- Quick reference commands

## Files Modified

1. ✅ `tests/test_basic.py` - Version-agnostic test
2. ✅ `tests/test_core_features.py` - Version-agnostic test
3. ✅ `.github/workflows/version-check.yml` - Automated validation
4. ✅ `VERSION_UPDATE_CHECKLIST.md` - Update guide
5. ✅ `PREVENTING_VERSION_TEST_FAILURES.md` - This document

## Benefits

### Before (Hardcoded Version)
- ❌ Tests fail on every version update
- ❌ Easy to forget to update tests
- ❌ Manual process, error-prone
- ❌ Blocks CI/CD pipeline

### After (Version-Agnostic)
- ✅ Tests pass regardless of version
- ✅ Validates version format automatically
- ✅ CI checks version consistency
- ✅ No manual test updates needed

## Testing

### Verify Tests Pass

```bash
# Run all tests
./run_tests.sh

# Or specific tests
python3.12 -m pytest tests/test_basic.py::test_imports -v
python3.12 -m pytest tests/test_core_features.py::TestVersioning::test_version_value -v
```

### Test Version Validation

```bash
# Valid version (should pass)
echo '__version__ = "1.2.3"' > src/__init__.py
python3 -c "import sys; sys.path.insert(0, '.'); from src import __version__; import re; assert re.match(r'^\d+\.\d+\.\d+$', __version__)"

# Invalid version (should fail)
echo '__version__ = "1.2"' > src/__init__.py
python3 -c "import sys; sys.path.insert(0, '.'); from src import __version__; import re; assert re.match(r'^\d+\.\d+\.\d+$', __version__)"
```

## Version Update Process

### Quick Steps

1. **Update version**: Edit `src/__init__.py`
   ```python
   __version__ = "X.Y.Z"
   ```

2. **Create changelog**: `changelogs/CHANGELOG_vX.Y.Z.md`

3. **Run tests**: `./run_tests.sh`

4. **Commit and tag**:
   ```bash
   git add .
   git commit -m "Release vX.Y.Z: Description"
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin <branch>
   git push origin vX.Y.Z
   ```

### Detailed Process

See `VERSION_UPDATE_CHECKLIST.md` for complete checklist.

## Semver Format

We follow semantic versioning (semver):

```
MAJOR.MINOR.PATCH
  |     |     |
  |     |     └─ Bug fixes (backward compatible)
  |     └─────── New features (backward compatible)
  └───────────── Breaking changes
```

**Examples:**
- ✅ `0.0.11` - Valid
- ✅ `1.2.3` - Valid
- ✅ `10.20.30` - Valid
- ❌ `1.2` - Invalid (missing patch)
- ❌ `v1.2.3` - Invalid (has 'v' prefix)
- ❌ `1.2.3-beta` - Invalid (has suffix)

## CI/CD Integration

### Version Check Workflow

Runs on every PR and push to main/dev:

```yaml
- Check version format (semver)
- Warn if changelog missing
- Fail if version invalid
```

### Test Workflow

Runs full test suite including version tests:

```yaml
- Run pytest with coverage
- Version tests now pass automatically
- No manual intervention needed
```

## Troubleshooting

### Tests Still Failing?

1. **Check version format**:
   ```bash
   grep __version__ src/__init__.py
   # Should output: __version__ = "X.Y.Z"
   ```

2. **Verify regex pattern**:
   ```bash
   python3 -c "import re; print(re.match(r'^\d+\.\d+\.\d+$', '0.0.11'))"
   # Should output: <re.Match object...>
   ```

3. **Run tests locally**:
   ```bash
   python3.12 -m pytest tests/test_basic.py -v
   ```

### Version Check Workflow Failing?

1. **Check version format** in `src/__init__.py`
2. **Ensure no 'v' prefix** (use `0.0.11` not `v0.0.11`)
3. **Follow semver** (X.Y.Z format)

## Best Practices

### ✅ DO

- Use semver format (X.Y.Z)
- Create changelog for each version
- Run tests before committing
- Tag releases properly
- Document breaking changes

### ❌ DON'T

- Hardcode version in tests
- Skip changelog creation
- Use non-semver formats
- Forget to update version
- Push without testing

## Future Improvements

Potential enhancements:

- [ ] Auto-generate changelog from commits
- [ ] Version bump script (interactive)
- [ ] Pre-commit hook to validate version
- [ ] Automatic version increment in CI
- [ ] Release notes generator
- [ ] Version comparison tool

## Summary

**Problem**: Tests failed when version changed because they checked for hardcoded version.

**Solution**: Made tests version-agnostic by checking format instead of specific version.

**Result**: Tests now pass regardless of version, CI validates format automatically, and we have a clear update process.

**Impact**: No more manual test updates, faster releases, fewer errors.
