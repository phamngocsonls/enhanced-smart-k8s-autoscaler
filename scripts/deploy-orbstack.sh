#!/bin/bash
#
# Smart Autoscaler - OrbStack Local Deployment Script
# Deploys everything needed for local development/demo on macOS
#
# Prerequisites: OrbStack installed with Kubernetes enabled
#
# Usage:
#   ./scripts/deploy-orbstack.sh
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Smart Autoscaler - OrbStack Local Deployment           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}[1/8] Checking prerequisites...${NC}"
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}❌ kubectl not found${NC}"
        echo "Install with: brew install kubectl"
        exit 1
    fi
    echo -e "${GREEN}  ✓ kubectl found${NC}"
    
    # Check helm
    if ! command -v helm &> /dev/null; then
        echo -e "${YELLOW}  ⚠ helm not found, installing...${NC}"
        brew install helm
    fi
    echo -e "${GREEN}  ✓ helm found${NC}"
    
    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        echo -e "${RED}❌ Cannot connect to Kubernetes cluster${NC}"
        echo ""
        echo "Make sure OrbStack is running with Kubernetes enabled:"
        echo "  1. Open OrbStack"
        echo "  2. Go to Settings → Kubernetes"
        echo "  3. Enable Kubernetes"
        echo ""
        exit 1
    fi
    echo -e "${GREEN}  ✓ Connected to OrbStack Kubernetes${NC}"
    echo ""
}

# Install metrics-server (required for HPA to get CPU/memory metrics)
install_metrics_server() {
    echo -e "${YELLOW}[2/8] Installing metrics-server...${NC}"
    
    # Check if metrics-server is already installed
    if kubectl get deployment metrics-server -n kube-system &> /dev/null; then
        echo -e "${GREEN}  ✓ metrics-server already installed${NC}"
    else
        # Install metrics-server
        kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
        
        # Patch for local clusters (insecure TLS)
        sleep 5
        kubectl patch deployment metrics-server -n kube-system --type='json' -p='[
          {"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}
        ]' 2>/dev/null || true
        
        echo -e "${GREEN}  ✓ metrics-server installed${NC}"
    fi
    echo ""
}

# Install Prometheus Stack (Prometheus + kube-state-metrics + node-exporter)
install_prometheus() {
    echo -e "${YELLOW}[3/8] Installing Prometheus Stack...${NC}"
    
    # Add helm repo
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
    helm repo update
    
    # Create namespace
    kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
    
    # Install Prometheus with kube-state-metrics enabled (required for kube_* metrics)
    # The autoscaler needs these metrics:
    #   - kube_node_status_capacity (kube-state-metrics)
    #   - kube_node_status_allocatable (kube-state-metrics)
    #   - kube_pod_container_resource_requests (kube-state-metrics)
    #   - kube_deployment_spec_replicas (kube-state-metrics)
    #   - kube_pod_start_time (kube-state-metrics)
    #   - node_cpu_seconds_total (node-exporter)
    #   - container_cpu_usage_seconds_total (cAdvisor/kubelet)
    helm upgrade --install prometheus prometheus-community/prometheus \
        --namespace monitoring \
        --set server.persistentVolume.enabled=false \
        --set server.retention=3d \
        --set alertmanager.enabled=false \
        --set pushgateway.enabled=false \
        --set kube-state-metrics.enabled=true \
        --set prometheus-node-exporter.enabled=true \
        --set server.resources.requests.cpu=100m \
        --set server.resources.requests.memory=256Mi \
        --set server.resources.limits.cpu=500m \
        --set server.resources.limits.memory=512Mi \
        --wait --timeout 5m
    
    echo -e "${GREEN}  ✓ Prometheus Stack installed (with kube-state-metrics & node-exporter)${NC}"
    echo ""
}

# Deploy sample application
deploy_sample_app() {
    echo -e "${YELLOW}[4/8] Deploying sample application...${NC}"
    
    # Create sample nginx deployment with HPA
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: demo
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-app
  namespace: demo
spec:
  replicas: 2
  selector:
    matchLabels:
      app: demo-app
  template:
    metadata:
      labels:
        app: demo-app
    spec:
      containers:
      - name: nginx
        image: nginx:alpine
        ports:
        - containerPort: 80
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 200m
            memory: 256Mi
---
apiVersion: v1
kind: Service
metadata:
  name: demo-app
  namespace: demo
spec:
  selector:
    app: demo-app
  ports:
  - port: 80
    targetPort: 80
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: demo-app-hpa
  namespace: demo
  labels:
    managed-by: smart-autoscaler
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: demo-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  # Anti-flapping behavior - CRITICAL for production
  behavior:
    scaleDown:
      # Wait 5 minutes before scaling down (prevents flapping)
      stabilizationWindowSeconds: 300
      policies:
      - type: Pods
        value: 1
        periodSeconds: 60      # Max 1 pod per minute
      - type: Percent
        value: 10
        periodSeconds: 60      # Max 10% per minute
      selectPolicy: Min        # Use least aggressive
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Pods
        value: 4
        periodSeconds: 15      # Max 4 pods per 15 seconds
      - type: Percent
        value: 100
        periodSeconds: 15      # Max double per 15 seconds
      selectPolicy: Max        # Use most aggressive
EOF
    
    echo -e "${GREEN}  ✓ Sample app deployed (demo/demo-app)${NC}"
    echo ""
}

# Deploy Smart Autoscaler
deploy_autoscaler() {
    echo -e "${YELLOW}[5/8] Deploying Smart Autoscaler...${NC}"
    
    # Create namespace
    kubectl create namespace autoscaler-system --dry-run=client -o yaml | kubectl apply -f -
    
    # Apply RBAC
    kubectl apply -f k8s/rbac.yaml
    
    # Create ConfigMap
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: smart-autoscaler-config
  namespace: autoscaler-system
data:
  PROMETHEUS_URL: "http://prometheus-server.monitoring:80"
  CHECK_INTERVAL: "30"
  TARGET_NODE_UTILIZATION: "30"
  DRY_RUN: "false"
  ENABLE_PREDICTIVE: "true"
  ENABLE_AUTOTUNING: "true"
  ENABLE_AUTO_DISCOVERY: "true"
  ENABLE_PRESCALE: "true"
  COST_PER_VCPU_HOUR: "0.04"
  COST_PER_GB_MEMORY_HOUR: "0.004"
  LOG_LEVEL: "INFO"
  LOG_FORMAT: "json"
  PROMETHEUS_RATE_LIMIT: "10"
  K8S_API_RATE_LIMIT: "20"
  MEMORY_WARNING_THRESHOLD: "0.75"
  MEMORY_CRITICAL_THRESHOLD: "0.9"
  # Watch the demo app
  DEPLOYMENT_0_NAMESPACE: "demo"
  DEPLOYMENT_0_NAME: "demo-app"
  DEPLOYMENT_0_HPA_NAME: "demo-app-hpa"
  DEPLOYMENT_0_STARTUP_FILTER: "1"
EOF
    
    # Create PVC (use emptyDir for local dev)
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: autoscaler-db
  namespace: autoscaler-system
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
EOF
    
    # Deploy the autoscaler
    cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: smart-autoscaler
  namespace: autoscaler-system
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: smart-autoscaler
  template:
    metadata:
      labels:
        app: smart-autoscaler
    spec:
      serviceAccountName: smart-autoscaler
      containers:
      - name: operator
        image: ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:0.0.33
        imagePullPolicy: IfNotPresent
        envFrom:
        - configMapRef:
            name: smart-autoscaler-config
        env:
        - name: PYTHONUNBUFFERED
          value: "1"
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
        volumeMounts:
        - name: database
          mountPath: /data
        ports:
        - containerPort: 8000
          name: metrics
        - containerPort: 5000
          name: dashboard
        livenessProbe:
          httpGet:
            path: /api/health
            port: 5000
          initialDelaySeconds: 60
          periodSeconds: 30
          timeoutSeconds: 5
        readinessProbe:
          httpGet:
            path: /api/health
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
      volumes:
      - name: database
        persistentVolumeClaim:
          claimName: autoscaler-db
EOF
    
    # Create Service
    kubectl apply -f k8s/service.yaml
    
    echo -e "${GREEN}  ✓ Smart Autoscaler deployed${NC}"
    echo ""
}

# Wait for pods
wait_for_pods() {
    echo -e "${YELLOW}[6/8] Waiting for pods to be ready...${NC}"
    
    echo -e "  Waiting for Prometheus..."
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=prometheus -n monitoring --timeout=120s 2>/dev/null || true
    
    echo -e "  Waiting for demo app..."
    kubectl wait --for=condition=ready pod -l app=demo-app -n demo --timeout=60s 2>/dev/null || true
    
    echo -e "  Waiting for autoscaler..."
    kubectl wait --for=condition=ready pod -l app=smart-autoscaler -n autoscaler-system --timeout=120s 2>/dev/null || true
    
    echo -e "${GREEN}  ✓ All pods ready${NC}"
    echo ""
}

# Setup port forwards
setup_access() {
    echo -e "${YELLOW}[7/8] Setting up access...${NC}"
    
    # Kill any existing port-forwards
    pkill -f "kubectl port-forward.*5000" 2>/dev/null || true
    pkill -f "kubectl port-forward.*9090" 2>/dev/null || true
    
    # Start port-forwards in background
    kubectl port-forward svc/smart-autoscaler -n autoscaler-system 5000:5000 &>/dev/null &
    kubectl port-forward svc/prometheus-server -n monitoring 9090:80 &>/dev/null &
    
    sleep 2
    echo -e "${GREEN}  ✓ Port forwards started${NC}"
    echo ""
}

# Show status
show_status() {
    echo -e "${YELLOW}[8/8] Deployment Status${NC}"
    echo ""
    
    echo -e "${BLUE}Pods:${NC}"
    kubectl get pods -A | grep -E "NAME|prometheus|demo-app|smart-autoscaler"
    echo ""
    
    echo -e "${BLUE}Services:${NC}"
    kubectl get svc -A | grep -E "NAME|prometheus|demo-app|smart-autoscaler"
    echo ""
    
    echo -e "${BLUE}HPA:${NC}"
    kubectl get hpa -A
    echo ""
}

# Print access info
print_access_info() {
    echo -e "${CYAN}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                    🎉 Deployment Complete!                  ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo -e "${GREEN}Access URLs:${NC}"
    echo -e "  📊 Dashboard:  ${CYAN}http://localhost:5000${NC}"
    echo -e "  📈 Prometheus: ${CYAN}http://localhost:9090${NC}"
    echo ""
    echo -e "${GREEN}Useful Commands:${NC}"
    echo -e "  # View autoscaler logs"
    echo -e "  ${YELLOW}kubectl logs -f deployment/smart-autoscaler -n autoscaler-system${NC}"
    echo ""
    echo -e "  # Generate load on demo app"
    echo -e "  ${YELLOW}kubectl run load-gen --image=busybox --restart=Never -- /bin/sh -c 'while true; do wget -q -O- http://demo-app.demo; done'${NC}"
    echo ""
    echo -e "  # Watch HPA changes"
    echo -e "  ${YELLOW}watch kubectl get hpa -A${NC}"
    echo ""
    echo -e "  # Restart port-forwards (if needed)"
    echo -e "  ${YELLOW}kubectl port-forward svc/smart-autoscaler -n autoscaler-system 5000:5000${NC}"
    echo -e "  ${YELLOW}kubectl port-forward svc/prometheus-server -n monitoring 9090:80${NC}"
    echo ""
    echo -e "${GREEN}To uninstall:${NC}"
    echo -e "  ${YELLOW}./scripts/deploy-orbstack.sh --uninstall${NC}"
    echo ""
}

# Uninstall
uninstall() {
    echo -e "${YELLOW}Uninstalling Smart Autoscaler...${NC}"
    
    # Kill port-forwards
    pkill -f "kubectl port-forward.*5000" 2>/dev/null || true
    pkill -f "kubectl port-forward.*9090" 2>/dev/null || true
    
    # Delete namespaces
    kubectl delete namespace autoscaler-system --ignore-not-found
    kubectl delete namespace demo --ignore-not-found
    
    # Uninstall Prometheus
    helm uninstall prometheus -n monitoring 2>/dev/null || true
    kubectl delete namespace monitoring --ignore-not-found
    
    echo -e "${GREEN}✓ Uninstalled${NC}"
    exit 0
}

# Main
main() {
    # Check for uninstall flag
    if [[ "$1" == "--uninstall" ]] || [[ "$1" == "-u" ]]; then
        uninstall
    fi
    
    check_prerequisites
    install_metrics_server
    install_prometheus
    deploy_sample_app
    deploy_autoscaler
    wait_for_pods
    setup_access
    show_status
    print_access_info
}

main "$@"
