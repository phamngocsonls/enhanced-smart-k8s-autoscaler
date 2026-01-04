#!/bin/bash
# Automated Release Script
# Usage: ./scripts/release.sh <version> <description>
# Example: ./scripts/release.sh 0.0.24 "Fix memory leak in prediction engine"

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check arguments
if [ -z "$1" ]; then
    echo -e "${RED}❌ Error: Version required${NC}"
    echo ""
    echo "Usage: ./scripts/release.sh <version> <description>"
    echo ""
    echo "Examples:"
    echo "  ./scripts/release.sh 0.0.24 \"Fix memory leak\""
    echo "  ./scripts/release.sh 0.0.24-beta \"New UI (pre-release)\" --pre-release"
    exit 1
fi

VERSION=$1
DESCRIPTION=${2:-"Release v$VERSION"}
IS_PRERELEASE=false

# Check for pre-release flag
if [[ "$3" == "--pre-release" ]] || [[ "$VERSION" == *"beta"* ]] || [[ "$VERSION" == *"alpha"* ]] || [[ "$VERSION" == *"rc"* ]]; then
    IS_PRERELEASE=true
fi

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Smart Autoscaler Release Automation               ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Version:${NC} v$VERSION"
echo -e "${GREEN}Description:${NC} $DESCRIPTION"
echo -e "${GREEN}Pre-release:${NC} $IS_PRERELEASE"
echo ""

# Confirm
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Cancelled${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 1/7:${NC} Updating version numbers..."
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Update src/__init__.py
echo "  📝 Updating src/__init__.py..."
sed -i.bak "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" src/__init__.py && rm src/__init__.py.bak

# Update README.md badge
echo "  📝 Updating README.md badge..."
if [ "$IS_PRERELEASE" = true ]; then
    sed -i.bak "s/version-.*-blue/version-$VERSION--beta-blue/" README.md && rm README.md.bak
else
    sed -i.bak "s/version-.*-blue/version-$VERSION-blue/" README.md && rm README.md.bak
fi

# Update Helm Chart.yaml
echo "  📝 Updating helm/smart-autoscaler/Chart.yaml..."
sed -i.bak "s/^version: .*/version: $VERSION/" helm/smart-autoscaler/Chart.yaml && rm helm/smart-autoscaler/Chart.yaml.bak
sed -i.bak "s/^appVersion: .*/appVersion: \"$VERSION\"/" helm/smart-autoscaler/Chart.yaml && rm helm/smart-autoscaler/Chart.yaml.bak

echo -e "${GREEN}  ✓ Version numbers updated${NC}"
echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 2/7:${NC} Creating changelog..."
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

CHANGELOG_FILE="changelogs/CHANGELOG_v$VERSION.md"

if [ -f "$CHANGELOG_FILE" ]; then
    echo -e "${YELLOW}  ⚠️  Changelog already exists: $CHANGELOG_FILE${NC}"
else
    echo "  📝 Creating $CHANGELOG_FILE..."
    cat > "$CHANGELOG_FILE" << EOF
# Changelog v$VERSION

**Release Date**: $(date +%Y-%m-%d)  
**Type**: $([ "$IS_PRERELEASE" = true ] && echo "Pre-Release" || echo "Stable Release")

---

## 📝 Changes

$DESCRIPTION

---

## 🚀 Upgrade Instructions

\`\`\`bash
# Pull latest image
docker pull ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:v$VERSION

# Or using kubectl
kubectl set image deployment/smart-autoscaler \\
  smart-autoscaler=ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:v$VERSION \\
  -n autoscaler-system

# Or using Helm
helm upgrade smart-autoscaler ./helm/smart-autoscaler \\
  --namespace autoscaler-system \\
  --set image.tag=v$VERSION
\`\`\`

---

**Version**: v$VERSION  
**Status**: $([ "$IS_PRERELEASE" = true ] && echo "Pre-Release" || echo "Stable")
EOF
    echo -e "${GREEN}  ✓ Changelog created${NC}"
fi

echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 3/7:${NC} Updating README version history..."
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Add to version history in README (after the header line)
if grep -q "| v$VERSION |" README.md; then
    echo -e "${YELLOW}  ⚠️  Version already in README${NC}"
else
    echo "  📝 Adding v$VERSION to README version history..."
    # Find the line with version history header and add new version after it
    sed -i.bak "/^| Version | Date | Changes |$/a\\
| v$VERSION | $(date +%Y-%m-%d) | $DESCRIPTION |" README.md && rm README.md.bak
    echo -e "${GREEN}  ✓ README updated${NC}"
fi

echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 4/7:${NC} Committing changes..."
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

git add -A
git commit -m "v$VERSION: $DESCRIPTION"
echo -e "${GREEN}  ✓ Changes committed${NC}"
echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 5/7:${NC} Pushing to dev branch..."
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

git push origin dev
echo -e "${GREEN}  ✓ Pushed to dev${NC}"
echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 6/7:${NC} Merging to main..."
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

git checkout main
git merge dev
git push origin main
echo -e "${GREEN}  ✓ Merged to main${NC}"
echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 7/7:${NC} Creating and pushing tag..."
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

TAG_NAME="v$VERSION"
if [ "$IS_PRERELEASE" = true ]; then
    TAG_MESSAGE="v$VERSION: $DESCRIPTION (Pre-Release)"
else
    TAG_MESSAGE="v$VERSION: $DESCRIPTION"
fi

git tag -a "$TAG_NAME" -m "$TAG_MESSAGE"
git push origin "$TAG_NAME"
echo -e "${GREEN}  ✓ Tag created and pushed${NC}"
echo ""

# Go back to dev
git checkout dev

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  ✅ Release Complete!                      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📦 Version:${NC} v$VERSION"
echo -e "${BLUE}🏷️  Tag:${NC} $TAG_NAME"
echo -e "${BLUE}📝 Changelog:${NC} $CHANGELOG_FILE"
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. 🐳 GitHub Actions will build Docker image automatically"
echo "   Image: ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:v$VERSION"
echo ""
echo "2. 📦 Create GitHub Release:"
echo "   https://github.com/phamngocsonls/enhanced-smart-k8s-autoscaler/releases/new?tag=$TAG_NAME"
if [ "$IS_PRERELEASE" = true ]; then
    echo "   ⚠️  Remember to check 'This is a pre-release'"
fi
echo ""
echo "3. 📝 Edit the changelog if needed:"
echo "   vim $CHANGELOG_FILE"
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}🎉 Done! You're on dev branch.${NC}"
echo ""
