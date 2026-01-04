# Quick Release Guide

## 🎯 Tell the AI (Kiro/Cursor)

Just say one of these:

```
release version 0.0.24 with "Fix memory leak"
```

```
pre-release 0.0.25-beta with "New features (testing)"
```

```
bump version to 0.0.24
```

The AI will:
1. Update all version numbers
2. Create changelog
3. Update README
4. Give you git commands

---

## 🚀 Or Use the Script

```bash
./scripts/release.sh 0.0.24 "Fix memory leak"
```

Does everything automatically!

---

## 📝 Examples

| What to Say | Result |
|-------------|--------|
| `release 0.0.24 with "Fix bug"` | Stable release v0.0.24 |
| `pre-release 0.0.25-beta with "New feature"` | Beta release v0.0.25-beta |
| `hotfix 0.0.24-v2 with "Quick fix"` | Hotfix v0.0.24-v2 |
| `bump 0.0.24` | Quick version bump |

---

## 🔄 Full Workflow

1. Make changes
2. Tell AI: `release 0.0.24 with "Your changes"`
3. Run: `./scripts/release.sh 0.0.24 "Your changes"`
4. Done! 🎉

---

See [.kiro/RELEASE_PROMPTS.md](.kiro/RELEASE_PROMPTS.md) for more examples.
