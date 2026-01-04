#!/bin/bash
# Compare different Docker build strategies
# Shows size, build time, and features for each option

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Docker Image Comparison Tool                      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Build all variants
echo -e "${CYAN}Building all Docker variants...${NC}"
echo ""

# Minimal
echo -e "${YELLOW}[1/3] Building minimal image...${NC}"
START_MINIMAL=$(date +%s)
docker build -f Dockerfile.minimal -t smart-autoscaler:minimal -q . > /dev/null 2>&1
END_MINIMAL=$(date +%s)
TIME_MINIMAL=$((END_MINIMAL - START_MINIMAL))

# Enhanced
echo -e "${YELLOW}[2/3] Building enhanced image...${NC}"
START_ENHANCED=$(date +%s)
docker build -f Dockerfile.enhanced -t smart-autoscaler:enhanced -q . > /dev/null 2>&1
END_ENHANCED=$(date +%s)
TIME_ENHANCED=$((END_ENHANCED - START_ENHANCED))

# Fast (requires base)
echo -e "${YELLOW}[3/3] Building fast image...${NC}"
if docker image inspect ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler-base:latest > /dev/null 2>&1; then
    START_FAST=$(date +%s)
    docker build -f Dockerfile.fast -t smart-autoscaler:fast -q . > /dev/null 2>&1
    END_FAST=$(date +%s)
    TIME_FAST=$((END_FAST - START_FAST))
    FAST_AVAILABLE=true
else
    echo -e "${RED}  ⚠️  Base image not found. Run: ./scripts/build-base-image.sh${NC}"
    FAST_AVAILABLE=false
fi

echo ""
echo -e "${GREEN}✅ All images built successfully!${NC}"
echo ""

# Get sizes
SIZE_MINIMAL=$(docker images smart-autoscaler:minimal --format "{{.Size}}")
SIZE_ENHANCED=$(docker images smart-autoscaler:enhanced --format "{{.Size}}")
if [[ "$FAST_AVAILABLE" == true ]]; then
    SIZE_FAST=$(docker images smart-autoscaler:fast --format "{{.Size}}")
fi

# Display comparison table
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}Image Comparison${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
printf "%-20s %-15s %-15s %-40s\n" "Variant" "Size" "Build Time" "Features"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
printf "%-20s ${GREEN}%-15s${NC} %-15s %-40s\n" "Minimal" "$SIZE_MINIMAL" "${TIME_MINIMAL}s" "Core only (no ML/AI)"
printf "%-20s ${YELLOW}%-15s${NC} %-15s %-40s\n" "Enhanced" "$SIZE_ENHANCED" "${TIME_ENHANCED}s" "All features (ML + AI support)"
if [[ "$FAST_AVAILABLE" == true ]]; then
    printf "%-20s ${CYAN}%-15s${NC} ${GREEN}%-15s${NC} %-40s\n" "Fast" "$SIZE_FAST" "${TIME_FAST}s" "All features (requires base image)"
else
    printf "%-20s ${RED}%-15s${NC} %-15s %-40s\n" "Fast" "N/A" "N/A" "Base image not built"
fi
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Feature comparison
echo -e "${CYAN}Feature Comparison${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
printf "%-30s %-12s %-12s %-12s\n" "Feature" "Minimal" "Enhanced" "Fast"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
printf "%-30s ${GREEN}%-12s${NC} ${GREEN}%-12s${NC} ${GREEN}%-12s${NC}\n" "Core Autoscaling" "✅" "✅" "✅"
printf "%-30s ${GREEN}%-12s${NC} ${GREEN}%-12s${NC} ${GREEN}%-12s${NC}\n" "HPA Management" "✅" "✅" "✅"
printf "%-30s ${GREEN}%-12s${NC} ${GREEN}%-12s${NC} ${GREEN}%-12s${NC}\n" "Cost Optimization" "✅" "✅" "✅"
printf "%-30s ${GREEN}%-12s${NC} ${GREEN}%-12s${NC} ${GREEN}%-12s${NC}\n" "Dashboard" "✅" "✅" "✅"
printf "%-30s ${RED}%-12s${NC} ${GREEN}%-12s${NC} ${GREEN}%-12s${NC}\n" "Predictive Scaling (ML)" "❌" "✅" "✅"
printf "%-30s ${RED}%-12s${NC} ${YELLOW}%-12s${NC} ${YELLOW}%-12s${NC}\n" "GenAI Features" "❌" "Optional" "Optional"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Recommendations
echo -e "${CYAN}Recommendations${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Production (no ML):${NC}     Use Minimal  (smallest, fastest startup)"
echo -e "${GREEN}Production (with ML):${NC}   Use Enhanced (all features, self-contained)"
echo -e "${GREEN}Development:${NC}            Use Fast     (10x faster rebuilds)"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Dependency breakdown
echo -e "${CYAN}Dependency Analysis (Enhanced)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
docker run --rm smart-autoscaler:enhanced pip list --format=columns | grep -E "kubernetes|prometheus|flask|numpy|scikit|scipy|statsmodels" || true
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Cleanup option
echo -e "${YELLOW}To clean up test images:${NC}"
echo "  docker rmi smart-autoscaler:minimal smart-autoscaler:enhanced smart-autoscaler:fast"
echo ""
