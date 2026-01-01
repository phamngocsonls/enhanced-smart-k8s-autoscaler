# Changelog - Version 0.0.11-v2 (Hotfix)

## Release Date: 2026-01-01

## 🐛 Bug Fixes

### Namespace Filter Not Populating

**Issue**: The namespace filter dropdown only showed "All Namespaces" with no actual namespaces listed.

**Root Cause**: The namespace filter was only being populated in the `loadClusterMetrics()` function (Cluster tab), but not in the `loadDeployments()` function where it should be populated on initial page load.

**Fix**: 
- Added namespace filter population to `loadDeployments()` function
- Filter now populates immediately when deployments are loaded
- Preserves selected namespace when data refreshes
- Sorts namespaces alphabetically

**Files Modified**:
- `templates/dashboard.html` - Added namespace extraction and filter population

**Impact**: 
- ✅ Namespace filter now shows all namespaces from watched deployments
- ✅ Filter works immediately on page load
- ✅ Selection persists across refreshes
- ✅ Sorted alphabetically for easy navigation

### Version Test Pattern Updated

**Issue**: Version tests didn't support hotfix version format (X.Y.Z-vN)

**Fix**:
- Updated regex pattern to accept both `X.Y.Z` and `X.Y.Z-vN` formats
- Allows for hotfix releases without breaking tests

**Files Modified**:
- `tests/test_basic.py` - Updated version regex pattern
- `tests/test_core_features.py` - Updated version regex pattern

## 📝 Changes Summary

| Component | Change | Status |
|-----------|--------|--------|
| Namespace Filter | Fixed population on page load | ✅ Fixed |
| Version Tests | Support hotfix format | ✅ Updated |
| Version Number | Bumped to 0.0.11-v2 | ✅ Updated |

## 🔧 Technical Details

### Namespace Filter Implementation

**Before**:
```javascript
// Only populated in loadClusterMetrics() - Cluster tab
const namespaceFilter = document.getElementById('namespace-filter');
namespaceFilter.innerHTML = '<option value="all">All Namespaces</option>';
for (const ns of data.namespaces) {
    namespaceFilter.innerHTML += `<option value="${ns}">${ns}</option>`;
}
```

**After**:
```javascript
// Now also populated in loadDeployments() - on page load
const namespaces = [...new Set(deployments.map(d => d.namespace))].sort();
const namespaceFilter = document.getElementById('namespace-filter');
const currentValue = namespaceFilter.value;
namespaceFilter.innerHTML = '<option value="all">All Namespaces</option>';
for (const ns of namespaces) {
    const option = document.createElement('option');
    option.value = ns;
    option.textContent = ns;
    namespaceFilter.appendChild(option);
}
// Restore previous selection
if (currentValue && (currentValue === 'all' || namespaces.includes(currentValue))) {
    namespaceFilter.value = currentValue;
}
```

### Version Pattern

**Before**: `^\d+\.\d+\.\d+$` (only X.Y.Z)

**After**: `^\d+\.\d+\.\d+(-v\d+)?$` (X.Y.Z or X.Y.Z-vN)

**Examples**:
- ✅ `0.0.11` - Valid
- ✅ `0.0.11-v2` - Valid (hotfix)
- ✅ `1.2.3-v5` - Valid (hotfix)
- ❌ `0.0.11-beta` - Invalid (not a hotfix format)
- ❌ `0.0.11v2` - Invalid (missing dash)

## 🧪 Testing

### Manual Test

1. **Open dashboard**: http://localhost:5000
2. **Check namespace filter**: Should show "All Namespaces" and your namespaces (e.g., "demo")
3. **Select a namespace**: Filter should work on deployments table
4. **Refresh page**: Selected namespace should persist
5. **Switch tabs**: Filter should remain populated

### Automated Test

```bash
# Run version tests
python3.12 -m pytest tests/test_basic.py::test_imports -v
python3.12 -m pytest tests/test_core_features.py::TestVersioning::test_version_value -v

# Both should pass with version 0.0.11-v2
```

## 📊 Verification

### Before Fix
```
Namespace Filter: [All Namespaces ▼]
                  (empty - no options)
```

### After Fix
```
Namespace Filter: [All Namespaces ▼]
                  All Namespaces
                  demo
                  production
                  staging
```

## 🚀 Deployment

### Quick Deploy

```bash
# 1. Pull latest code
git pull origin dev

# 2. Restart dashboard
kubectl rollout restart deployment -n autoscaler-system smart-autoscaler

# 3. Verify
curl http://localhost:5000/api/deployments | jq '.[].namespace' | sort -u
# Should show your namespaces
```

### Docker

```bash
# Build with new version
docker build -t smart-autoscaler:0.0.11-v2 .

# Deploy
kubectl set image deployment/smart-autoscaler smart-autoscaler=smart-autoscaler:0.0.11-v2 -n autoscaler-system
```

## 🔄 Upgrade Path

From v0.0.11 to v0.0.11-v2:

1. **No breaking changes** - Direct upgrade
2. **No config changes** - Works with existing config
3. **No database migration** - Same schema
4. **Backward compatible** - Can rollback if needed

## 📝 Notes

- This is a hotfix release (v2) for v0.0.11
- Fixes UI bug that prevented namespace filtering
- No API changes
- No database changes
- Safe to deploy in production

## 🎯 Impact

**User Experience**:
- ✅ Namespace filter now works as expected
- ✅ Easier to navigate multi-namespace deployments
- ✅ Better UX for multi-tenant clusters

**Technical**:
- ✅ No performance impact
- ✅ No breaking changes
- ✅ Maintains backward compatibility

## 🐛 Known Issues

None - this hotfix resolves the namespace filter issue.

## 📚 Related Documentation

- Main changelog: `changelogs/CHANGELOG_v0.0.11.md`
- Cluster monitoring guide: `docs/CLUSTER_MONITORING.md`
- Quick reference: `QUICK_REFERENCE.md`

---

**Version**: 0.0.11-v2  
**Type**: Hotfix  
**Priority**: Medium  
**Breaking Changes**: None  
**Migration Required**: No
