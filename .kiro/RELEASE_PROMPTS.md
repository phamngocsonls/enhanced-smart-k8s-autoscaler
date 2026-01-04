# Release Prompts for Kiro/Cursor AI

Quick prompts to tell the AI to create a new release.

---

## 🚀 Standard Release

Just say:

```
release version 0.0.24 with "Fix memory leak in prediction engine"
```

Or:

```
create new release v0.0.24: Fix memory leak
```

Or simply:

```
bump version to 0.0.24, fix memory leak
```

---

## 🧪 Pre-Release

```
pre-release version 0.0.25-beta with "New GenAI features (testing)"
```

Or:

```
create beta release 0.0.25-beta: New GenAI features
```

---

## 🔥 Hotfix

```
hotfix release 0.0.24-v2: Fix dashboard crash
```

Or:

```
quick release 0.0.24-v2 to fix dashboard crash
```

---

## 📝 What the AI Will Do

When you say "release version X.X.X", the AI will:

1. ✅ Update `src/__init__.py` version
2. ✅ Update `README.md` version badge
3. ✅ Update `helm/smart-autoscaler/Chart.yaml` version
4. ✅ Create `changelogs/CHANGELOG_vX.X.X.md`
5. ✅ Update README version history table
6. ✅ Provide git commands to run

---

## 💡 Examples

### Example 1: Bug Fix
```
release 0.0.24 with "Fix CPU spike detection bug"
```

### Example 2: New Feature
```
release 0.0.25 with "Add email notifications support"
```

### Example 3: UI Update
```
release 0.0.26 with "Improve dashboard performance"
```

### Example 4: Pre-Release
```
pre-release 0.0.27-beta with "Experimental multi-cluster support"
```

### Example 5: Multiple Changes
```
release 0.0.28 with "Fix memory leak, improve predictions, update docs"
```

---

## 🎯 Short Versions

You can be very brief:

```
bump 0.0.24
```

```
release 0.0.24
```

```
new version 0.0.24
```

The AI will ask for description if needed, or use a generic one.

---

## 🔄 Full Workflow

1. **Make your changes** (code, docs, etc.)

2. **Tell the AI**:
   ```
   release version 0.0.24 with "Your changes description"
   ```

3. **AI will**:
   - Update all version numbers
   - Create changelog
   - Update README
   - Give you git commands

4. **You run** the git commands (or use the script):
   ```bash
   ./scripts/release.sh 0.0.24 "Your changes"
   ```

5. **Done!** 🎉

---

## 📋 Template

Copy-paste and fill in:

```
release version [VERSION] with "[DESCRIPTION]"
```

Examples:
- `release version 0.0.24 with "Fix memory leak"`
- `pre-release version 0.0.25-beta with "New features (testing)"`
- `hotfix release 0.0.24-v2 with "Quick fix for crash"`

---

## 🤖 AI Understanding

The AI understands these keywords:
- **release** / **bump** / **new version** / **create release**
- **pre-release** / **beta** / **alpha** / **rc**
- **hotfix** / **quick fix** / **patch**
- **version** / **v** (optional)

So all of these work:
- ✅ "release 0.0.24"
- ✅ "bump version to 0.0.24"
- ✅ "create new release v0.0.24"
- ✅ "new version 0.0.24 with fix"
- ✅ "pre-release 0.0.25-beta"

---

## 💬 Natural Language

You can also be conversational:

```
Hey, I want to release a new version 0.0.24 that fixes the memory leak issue
```

```
Can you help me create version 0.0.25-beta? It has new GenAI features
```

```
I need to do a quick hotfix release 0.0.24-v2 for the dashboard crash
```

The AI will understand and do the release! 🚀
