#!/bin/bash
#
# Smart Autoscaler - GKE Deployment Script
# Quick deploy with environment file support
#
# Usage:
#   ./scripts/deploy-gke.sh [options]
#
# Options:
#   -e, --env FILE          Environment file (default: .env)
#   -n, --namespace NS      Kubernetes namespace (default: autoscaler-system)
#   -p, --prometheus        Install Prometheus if not present
#   -d, --dry-run           Show what would be deployed without applying
#   -u, --uninstall         Uninstall the autoscaler
#   -h, --help              Show this help message
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Defaults
ENV_FILE=".env"
NAMESPACE="autoscaler-system"
INSTALL_PROMETHEUS=false
DRY_RUN=false
UNINSTALL=false
IMAGE="ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:latest"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENV_FILE="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -p|--prometheus)
            INSTALL_PROMETHEUS=true
            shift
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -u|--uninstall)
            UNINSTALL=true
            shift
            ;;
        -h|--help)
            head -25 "$0" | tail -20
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Smart Kubernetes Autoscaler - GKE Deployment         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"
    
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}❌ kubectl not found. Please install kubectl.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ kubectl found${NC}"
    
    if ! command -v gcloud &> /dev/null; then
        echo -e "${YELLOW}⚠ gcloud not found. Some features may not work.${NC}"
    else
        echo -e "${GREEN}✓ gcloud found${NC}"
    fi
    
    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        echo -e "${RED}❌ Cannot connect to Kubernetes cluster.${NC}"
        echo -e "${YELLOW}Run: gcloud container clusters get-credentials <cluster-name> --zone <zone>${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Connected to cluster${NC}"
    
    echo ""
}

# Load environment file
load_env() {
    if [[ -f "$ENV_FILE" ]]; then
        echo -e "${YELLOW}Loading environment from: $ENV_FILE${NC}"
        export $(grep -v '^#' "$ENV_FILE" | xargs)
        echo -e "${GREEN}✓ Environment loaded${NC}"
    else
        echo -e "${YELLOW}⚠ Environment file not found: $ENV_FILE${NC}"
        echo -e "${YELLOW}  Using default values...${NC}"
    fi
    echo ""
}

# Create sample env file
create_sample_env() {
    if [[ ! -f ".env.example" ]]; then
        cat > .env.example << 'EOF'
# Smart Autoscaler Configuration
# Copy this file to .env and customize

# Prometheus URL (required)
PROMETHEUS_URL=http://prometheus-server.monitoring:9090

# Check interval in seconds
CHECK_INTERVAL=60

# Target node CPU utilization (percentage)
TARGET_NODE_UTILIZATION=70

# Enable dry-run mode (no actual scaling)
DRY_RUN=false

# Enable predictive scaling
ENABLE_PREDICTIVE=true

# Enable auto-tuning
ENABLE_AUTOTUNING=true

# Cost settings (USD)
COST_PER_VCPU_HOUR=0.04
COST_PER_GB_MEMORY_HOUR=0.004

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Rate limiting
PROMETHEUS_RATE_LIMIT=10
K8S_API_RATE_LIMIT=20

# Memory thresholds
MEMORY_WARNING_THRESHOLD=0.75
MEMORY_CRITICAL_THRESHOLD=0.9

# Watched deployments (comma-separated)
# Format: namespace/deployment/hpa-name
WATCHED_DEPLOYMENTS=default/my-app/my-app-hpa
EOF
        echo -e "${GREEN}✓ Created .env.example${NC}"
    fi
}

# Install Prometheus
install_prometheus() {
    echo -e "${YELLOW}Installing Prometheus...${NC}"
    
    # Check if Helm is installed
    if ! command -v helm &> /dev/null; then
        echo -e "${RED}❌ Helm not found. Installing Helm...${NC}"
        curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
    fi
    
    # Add Prometheus repo
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo update
    
    # Create monitoring namespace
    kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
    
    # Install Prometheus
    if $DRY_RUN; then
        echo -e "${YELLOW}[DRY-RUN] Would install Prometheus with:${NC}"
        echo "helm install prometheus prometheus-community/prometheus -n monitoring"
    else
        helm upgrade --install prometheus prometheus-community/prometheus \
            --namespace monitoring \
            --set server.persistentVolume.enabled=false \
            --set alertmanager.enabled=false \
            --wait
        
        echo -e "${GREEN}✓ Prometheus installed${NC}"
        echo -e "${BLUE}  Prometheus URL: http://prometheus-server.monitoring:9090${NC}"
    fi
    echo ""
}

# Check if Prometheus exists
check_prometheus() {
    if kubectl get svc prometheus-server -n monitoring &> /dev/null; then
        echo -e "${GREEN}✓ Prometheus found in monitoring namespace${NC}"
        return 0
    elif kubectl get svc -A | grep -q prometheus; then
        echo -e "${GREEN}✓ Prometheus found in cluster${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ Prometheus not found${NC}"
        return 1
    fi
}

# Deploy autoscaler
deploy_autoscaler() {
    echo -e "${YELLOW}Deploying Smart Autoscaler...${NC}"
    
    # Create namespace
    if $DRY_RUN; then
        echo -e "${YELLOW}[DRY-RUN] Would create namespace: $NAMESPACE${NC}"
    else
        kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    fi
    
    # Apply RBAC
    echo -e "${BLUE}Applying RBAC...${NC}"
    if $DRY_RUN; then
        echo "[DRY-RUN] kubectl apply -f k8s/rbac.yaml"
    else
        kubectl apply -f k8s/rbac.yaml
    fi
    
    # Create ConfigMap from environment
    echo -e "${BLUE}Creating ConfigMap...${NC}"
    create_configmap
    
    # Apply PVC
    echo -e "${BLUE}Creating PersistentVolumeClaim...${NC}"
    if $DRY_RUN; then
        echo "[DRY-RUN] kubectl apply -f k8s/pvc.yaml"
    else
        kubectl apply -f k8s/pvc.yaml
    fi
    
    # Apply Deployment
    echo -e "${BLUE}Deploying application...${NC}"
    if $DRY_RUN; then
        echo "[DRY-RUN] kubectl apply -f k8s/deployment.yaml"
    else
        # Update image in deployment
        sed "s|image:.*|image: $IMAGE|g" k8s/deployment.yaml | kubectl apply -f -
    fi
    
    # Apply Service
    echo -e "${BLUE}Creating Service...${NC}"
    if $DRY_RUN; then
        echo "[DRY-RUN] kubectl apply -f k8s/service.yaml"
    else
        kubectl apply -f k8s/service.yaml
    fi
    
    echo ""
    echo -e "${GREEN}✓ Deployment complete!${NC}"
}

# Create ConfigMap from environment variables
create_configmap() {
    local PROM_URL="${PROMETHEUS_URL:-http://prometheus-server.monitoring:9090}"
    local CHECK_INT="${CHECK_INTERVAL:-60}"
    local TARGET_UTIL="${TARGET_NODE_UTILIZATION:-70}"
    local DRY="${DRY_RUN_MODE:-false}"
    local PREDICTIVE="${ENABLE_PREDICTIVE:-true}"
    local AUTOTUNING="${ENABLE_AUTOTUNING:-true}"
    local VCPU_COST="${COST_PER_VCPU_HOUR:-0.04}"
    local MEM_COST="${COST_PER_GB_MEMORY_HOUR:-0.004}"
    local LOG_LVL="${LOG_LEVEL:-INFO}"
    local DEPLOYMENTS="${WATCHED_DEPLOYMENTS:-}"
    
    cat << EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: smart-autoscaler-config
  namespace: $NAMESPACE
data:
  PROMETHEUS_URL: "$PROM_URL"
  CHECK_INTERVAL: "$CHECK_INT"
  TARGET_NODE_UTILIZATION: "$TARGET_UTIL"
  DRY_RUN: "$DRY"
  ENABLE_PREDICTIVE: "$PREDICTIVE"
  ENABLE_AUTOTUNING: "$AUTOTUNING"
  COST_PER_VCPU_HOUR: "$VCPU_COST"
  COST_PER_GB_MEMORY_HOUR: "$MEM_COST"
  LOG_LEVEL: "$LOG_LVL"
  WATCHED_DEPLOYMENTS: "$DEPLOYMENTS"
EOF
}

# Uninstall
uninstall() {
    echo -e "${YELLOW}Uninstalling Smart Autoscaler...${NC}"
    
    if $DRY_RUN; then
        echo "[DRY-RUN] Would delete namespace: $NAMESPACE"
    else
        kubectl delete namespace "$NAMESPACE" --ignore-not-found
        echo -e "${GREEN}✓ Uninstalled${NC}"
    fi
}

# Show status
show_status() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}                    Deployment Status                       ${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    
    echo -e "${YELLOW}Pods:${NC}"
    kubectl get pods -n "$NAMESPACE" 2>/dev/null || echo "No pods found"
    echo ""
    
    echo -e "${YELLOW}Services:${NC}"
    kubectl get svc -n "$NAMESPACE" 2>/dev/null || echo "No services found"
    echo ""
    
    # Get dashboard URL
    local NODE_PORT=$(kubectl get svc smart-autoscaler -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo "")
    if [[ -n "$NODE_PORT" ]]; then
        echo -e "${GREEN}Dashboard available at:${NC}"
        echo -e "  kubectl port-forward svc/smart-autoscaler -n $NAMESPACE 5000:5000"
        echo -e "  Then open: http://localhost:5000"
    fi
    echo ""
}

# Main
main() {
    check_prerequisites
    create_sample_env
    load_env
    
    if $UNINSTALL; then
        uninstall
        exit 0
    fi
    
    # Check/Install Prometheus
    if ! check_prometheus; then
        if $INSTALL_PROMETHEUS; then
            install_prometheus
        else
            echo -e "${YELLOW}Prometheus not found. Use -p flag to install it.${NC}"
            echo -e "${YELLOW}Or set PROMETHEUS_URL in your .env file.${NC}"
            echo ""
        fi
    fi
    
    deploy_autoscaler
    
    if ! $DRY_RUN; then
        echo -e "${YELLOW}Waiting for pods to be ready...${NC}"
        kubectl wait --for=condition=ready pod -l app=smart-autoscaler -n "$NAMESPACE" --timeout=120s 2>/dev/null || true
        show_status
    fi
}

main
