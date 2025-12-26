#!/bin/bash
set -e

VERSION=${1:-latest}
COMMAND=${2:-all}
REGISTRY=${REGISTRY:-docker.io/yourusername}
IMAGE_NAME="smart-autoscaler"
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${VERSION}"

build() {
    echo "🔨 Building ${FULL_IMAGE}..."
    docker build -f Dockerfile.enhanced -t ${FULL_IMAGE} .
    echo "✅ Build complete"
}

push() {
    echo "📤 Pushing ${FULL_IMAGE}..."
    docker push ${FULL_IMAGE}
    echo "✅ Push complete"
}

deploy() {
    echo "🚀 Deploying to Kubernetes..."
    kubectl apply -f k8s/namespace.yaml
    kubectl apply -f k8s/rbac.yaml
    kubectl apply -f k8s/pvc.yaml
    kubectl apply -f k8s/configmap.yaml
    kubectl apply -f k8s/deployment.yaml
    kubectl apply -f k8s/service.yaml
    
    kubectl rollout status deployment/smart-autoscaler -n autoscaler-system --timeout=5m
    echo "✅ Deployment complete"
}

logs() {
    kubectl logs -f deployment/smart-autoscaler -n autoscaler-system
}

case "$COMMAND" in
    build) build ;;
    push) push ;;
    deploy) deploy ;;
    logs) logs ;;
    all) build && push && deploy ;;
    *) 
        echo "Usage: $0 [VERSION] [build|push|deploy|logs|all]"
        echo "Example: $0 v1.0.0 all"
        exit 1 
        ;;
esac
