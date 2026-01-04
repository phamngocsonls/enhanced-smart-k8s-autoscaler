#!/bin/bash
# Build base image with Python dependencies
# Run this when requirements.txt changes
#
# Usage:
#   ./scripts/build-base-image.sh           # Build for local architecture (macOS/Linux)
#   ./scripts/build-base-image.sh --push    # Build and push to registry
#   ./scripts/build-base-image.sh --analyze # Build and show size analysis

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Build Smart Autoscaler Base Image                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Detect OS
OS=$(uname -s)
ARCH=$(uname -m)
echo -e "${GREEN}Detected:${NC} $OS / $ARCH"

# Generate hash of requirements file
if command -v sha256sum &> /dev/null; then
    REQ_HASH=$(sha256sum requirements-enhanced.txt | cut -d' ' -f1 | cut -c1-8)
elif command -v shasum &> /dev/null; then
    # macOS fallback
    REQ_HASH=$(shasum -a 256 requirements-enhanced.txt | cut -d' ' -f1 | cut -c1-8)
else
    echo -e "${YELLOW}Warning: sha256sum/shasum not found, using timestamp${NC}"
    REQ_HASH=$(date +%s | tail -c 9)
fi

echo -e "${GREEN}Requirements hash:${NC} $REQ_HASH"
echo ""

# Image names
REGISTRY="ghcr.io"
REPO="phamngocsonls/enhanced-smart-k8s-autoscaler"
BASE_IMAGE="$REGISTRY/$REPO-base"

# Check if we should push
PUSH_IMAGE=false
ANALYZE_SIZE=false
if [[ "$1" == "--push" ]]; then
    PUSH_IMAGE=true
    echo -e "${YELLOW}Push mode enabled${NC}"
    echo ""
elif [[ "$1" == "--analyze" ]]; then
    ANALYZE_SIZE=true
    echo -e "${CYAN}Size analysis mode enabled${NC}"
    echo ""
fi

echo -e "${BLUE}Building base image for local architecture...${NC}"
echo -e "${GREEN}Platform:${NC} $OS/$ARCH"
echo ""

# Build base image (single architecture for local use)
docker build \
  -f Dockerfile.base \
  -t "$BASE_IMAGE:$REQ_HASH" \
  -t "$BASE_IMAGE:latest" \
  .

echo ""
echo -e "${GREEN}✅ Base image built successfully!${NC}"
echo ""

# Size analysis
if [[ "$ANALYZE_SIZE" == true ]] || [[ "$PUSH_IMAGE" == true ]]; then
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}Image Size Analysis${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    BASE_SIZE=$(docker images "$BASE_IMAGE:latest" --format "{{.Size}}")
    echo -e "${GREEN}Base image size:${NC} $BASE_SIZE"
    
    # Show layer breakdown
    echo ""
    echo -e "${CYAN}Layer breakdown:${NC}"
    docker history "$BASE_IMAGE:latest" --human --no-trunc | head -15
    
    echo ""
    echo -e "${CYAN}Largest dependencies:${NC}"
    docker run --rm "$BASE_IMAGE:latest" pip list --format=freeze | head -20
    
    echo ""
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Images created:${NC}"
echo "  • $BASE_IMAGE:$REQ_HASH"
echo "  • $BASE_IMAGE:latest"
echo ""

if [[ "$PUSH_IMAGE" == true ]]; then
    echo -e "${BLUE}Pushing to registry...${NC}"
    docker push "$BASE_IMAGE:$REQ_HASH"
    docker push "$BASE_IMAGE:latest"
    echo -e "${GREEN}✅ Images pushed successfully!${NC}"
    echo ""
else
    echo -e "${YELLOW}To push to registry:${NC}"
    echo "  ./scripts/build-base-image.sh --push"
    echo ""
fi

echo -e "${YELLOW}To test fast build:${NC}"
echo "  docker build -f Dockerfile.fast -t test:latest ."
echo ""

echo -e "${YELLOW}To analyze image size:${NC}"
echo "  ./scripts/build-base-image.sh --analyze"
echo ""

echo -e "${YELLOW}Note:${NC} This builds for your local architecture ($ARCH)."
echo "For multi-arch builds (linux/amd64 + linux/arm64), use GitHub Actions:"
echo "  git push  # Triggers .github/workflows/build-base.yml when requirements.txt changes"
echo ""

echo -e "${CYAN}Build Options:${NC}"
echo "  • Dockerfile.minimal  - Smallest image (~250MB, no ML/AI)"
echo "  • Dockerfile.fast     - Fast builds with base image (~450MB)"
echo "  • Dockerfile.enhanced - Full build with all features (~450MB)"
echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
