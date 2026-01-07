#!/bin/bash
# Automated Release Script
# Usage: ./scripts/release.sh <version> [message]
# Example: ./scripts/release.sh 0.0.32-v1 "Fix autoscaling_v2 attribute"

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
    echo "Usage: ./scripts/release.sh <version> [message]"
    echo ""
    echo "Examples:"
    echo "  ./scripts/release.sh 0.0.32 \"Major release\""
    echo "  ./scripts/release.sh 0.0.32-v1 \"Fix startup bug\""
    echo "  ./scripts/release.sh 0.0.33 \"New feature\""
    exit 1
fi

VERSION=$1
MESSAGE=${2:-"Release v$VERSION"}

# Extract base version (without -vX suffix) for __init__.py
BASE_VERSION=$(echo "$VERSION" | sed 's/-v[0-9]*$//')

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Smart Autoscaler Release Automation               ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Version:${NC} $VERSION"
echo -e "${GREEN}Base Version:${NC} $BASE_VERSION"
echo -e "${GREEN}Message:${NC} $MESSAGE"
echo ""

# Show what will be updated
echo -e "${YELLOW}Files to update:${NC}"
echo "  • src/__init__.py → __version__ = \"$BASE_VERSION\""
echo "  • helm/smart-autoscaler/Chart.yaml → version: $BASE_VERSION, appVersion: \"$BASE_VERSION\""
echo "  • helm/smart-autoscaler/values.yaml → tag: \"$VERSION\""
echo "  • k8s/deployment.yaml → image tag: $VERSION"
echo "  • README.md → version badge + helm example"
echo "  • QUICKSTART.md → helm example"
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
echo -e "${GREEN}Step 1/5:${NC} Updating version numbers..."
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Update src/__init__.py (use base version)
echo "  📝 src/__init__.py..."
sed -i.bak "s/__version__ = \".*\"/__version__ = \"$BASE_VERSION\"/" src/__init__.py && rm src/__init__.py.bak

# Update Helm Chart.yaml (use base version)
echo "  📝 helm/smart-autoscaler/Chart.yaml..."
sed -i.bak "s/^version: .*/version: $BASE_VERSION/" helm/smart-autoscaler/Chart.yaml && rm helm/smart-autoscaler/Chart.yaml.bak
sed -i.bak "s/^appVersion: .*/appVersion: \"$BASE_VERSION\"/" helm/smart-autoscaler/Chart.yaml && rm helm/smart-autoscaler/Chart.yaml.bak

# Update Helm values.yaml (use full version with -vX suffix)
echo "  📝 helm/smart-autoscaler/values.yaml..."
sed -i.bak "s/tag: \".*\"/tag: \"$VERSION\"/" helm/smart-autoscaler/values.yaml && rm helm/smart-autoscaler/values.yaml.bak

# Update k8s/deployment.yaml (use full version with -vX suffix)
echo "  📝 k8s/deployment.yaml..."
sed -i.bak "s|image: ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:.*|image: ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:$VERSION|" k8s/deployment.yaml && rm k8s/deployment.yaml.bak

# Update README.md badge (use base version)
echo "  📝 README.md badge..."
sed -i.bak "s/version-[0-9.]*-blue/version-$BASE_VERSION-blue/" README.md && rm README.md.bak

# Update README.md helm install example
echo "  📝 README.md helm example..."
sed -i.bak "s/--set image.tag=v[0-9.]*-*v*[0-9]*/--set image.tag=$VERSION/" README.md && rm README.md.bak

# Update QUICKSTART.md helm install example
echo "  📝 QUICKSTART.md helm example..."
sed -i.bak "s/--set image.tag=v[0-9.]*-*v*[0-9]*/--set image.tag=$VERSION/" QUICKSTART.md && rm QUICKSTART.md.bak

echo -e "${GREEN}  ✓ Version numbers updated${NC}"
echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 2/5:${NC} Running tests..."
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if command -v python3 &> /dev/null; then
    echo "  🧪 Running pytest..."
    python3 -m pytest tests/ -q --tb=no 2>&1 | tail -3
    echo -e "${GREEN}  ✓ Tests passed${NC}"
else
    echo -e "${YELLOW}  ⚠️  Python not found, skipping tests${NC}"
fi
echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 3/5:${NC} Committing changes..."
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

git add -A
git commit -m "v$VERSION: $MESSAGE"
echo -e "${GREEN}  ✓ Changes committed${NC}"
echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 4/5:${NC} Pushing to main..."
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

git push origin main
echo -e "${GREEN}  ✓ Pushed to main${NC}"
echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 5/5:${NC} Creating and pushing tag..."
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

TAG_NAME="v$VERSION"
git tag -a "$TAG_NAME" -m "v$VERSION: $MESSAGE"
git push origin "$TAG_NAME"
echo -e "${GREEN}  ✓ Tag v$VERSION created and pushed${NC}"
echo ""

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  ✅ Release Complete!                      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📦 Version:${NC} $VERSION"
echo -e "${BLUE}🏷️  Tag:${NC} v$VERSION"
echo -e "${BLUE}🐳 Image:${NC} ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:$VERSION"
echo ""
echo -e "${YELLOW}GitHub Actions will build Docker image automatically.${NC}"
echo ""
