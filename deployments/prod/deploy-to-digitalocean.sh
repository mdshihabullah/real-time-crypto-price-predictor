#!/bin/bash
# Real-time Crypto Price Predictor - DigitalOcean Deployment Script
# This script deploys the entire crypto price prediction system to a DigitalOcean Kubernetes cluster

# Exit immediately if a command exits with a non-zero status
set -e
# Treat unset variables as an error when substituting
set -u
# Causes a pipeline to return the exit status of the last command in the pipe
# that returned a non-zero return value
set -o pipefail

# Color codes for better readability
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
BLUE="\033[0;34m"
NC="\033[0m" # No Color

log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    
    case "$level" in
        "INFO")
            echo -e "${GREEN}[INFO]${NC} ${timestamp} - $message"
            ;;
        "WARN")
            echo -e "${YELLOW}[WARN]${NC} ${timestamp} - $message"
            ;;
        "ERROR")
            echo -e "${RED}[ERROR]${NC} ${timestamp} - $message"
            ;;
        "DEBUG")
            echo -e "${BLUE}[DEBUG]${NC} ${timestamp} - $message"
            ;;
        *)
            echo -e "${timestamp} - $message"
            ;;
    esac
}

log "INFO" "Starting deployment to DigitalOcean Kubernetes cluster"

# Source the deployment configuration file
log "INFO" "Loading deployment configuration"
source deployment.config

# Set Kubernetes config to use DO cluster
export KUBECONFIG=$(pwd)/$KUBECONFIG_PATH

if [ ! -f "$KUBECONFIG" ]; then
    log "ERROR" "Kubeconfig file not found at $KUBECONFIG"
    log "ERROR" "Please check your KUBECONFIG_PATH in deployment.config"
    exit 1
fi

log "INFO" "Using DigitalOcean Kubernetes cluster with config: $KUBECONFIG"
kubectl get nodes

# Function to create necessary namespaces
create_namespaces() {
    log "INFO" "Creating namespaces..."
    for ns in "services" "structurizr" "kafka"; do
        kubectl create namespace $ns --dry-run=client -o yaml | kubectl apply -f -
    done
}

# Function to deploy Strimzi Kafka operator and wait for CRDs
deploy_strimzi() {
    log "INFO" "Cleaning up any existing Strimzi deployments..."
    kubectl -n kafka delete deployment strimzi-cluster-operator --ignore-not-found=true
    log "INFO" "Waiting for cleanup to complete..."
    sleep 10

    log "INFO" "Installing Strimzi CRDs and operator directly..."
    kubectl apply -f https://strimzi.io/install/latest?namespace=kafka

    log "INFO" "Waiting for Strimzi operator to be ready..."
    kubectl -n kafka wait --timeout=300s --for=condition=ready pod -l name=strimzi-cluster-operator || \
        log "WARN" "Timed out waiting for Strimzi operator pods"

    log "INFO" "Waiting for Strimzi CRDs to be established..."
    local max_attempts=10
    for i in $(seq 1 $max_attempts); do
        if kubectl get crd kafkas.kafka.strimzi.io &>/dev/null && \
           kubectl get crd kafkanodepools.kafka.strimzi.io &>/dev/null; then
            log "INFO" "Strimzi CRDs are ready."
            return 0
        else
            log "INFO" "Waiting for Strimzi CRDs to be installed (attempt $i/$max_attempts)..."
            sleep 10
        fi
        
        if [ $i -eq $max_attempts ]; then
            log "ERROR" "Timed out waiting for Strimzi CRDs to be installed."
            log "ERROR" "You may need to manually verify that the Strimzi operator is working correctly."
            exit 1
        fi
    done
}

# Function to deploy Kafka cluster and UI
deploy_kafka() {
    # Create processed directory if it doesn't exist
    mkdir -p manifests/processed

    log "INFO" "Deploying Kafka components..."
    kubectl apply -f manifests/kafka-and-topics.yaml

    # Clean up any existing kafka-ui deployment to avoid selector immutability issues
    log "INFO" "Cleaning up any existing Kafka UI deployment..."
    kubectl -n kafka delete deployment kafka-ui --ignore-not-found=true
    kubectl -n kafka delete service kafka-ui --ignore-not-found=true
    sleep 5

    # Deploy Kafka UI separately
    log "INFO" "Deploying Kafka UI..."
    kubectl apply -f manifests/kafka-ui.yaml

    log "INFO" "Waiting for Kafka cluster to be ready (this may take several minutes)..."
    # First check if the resource type exists
    if kubectl -n kafka get kafka &>/dev/null; then
        # Only wait if the resource type exists
        log "INFO" "Kafka CRD exists. Waiting for Kafka cluster to be ready..."
        kubectl -n kafka wait --for=condition=ready kafka crypto-kafka-cluster --timeout=180s || \
            log "WARN" "Timed out waiting for Kafka cluster to be ready"
    else
        log "WARN" "Unable to wait for Kafka cluster - resource type not found"
        log "WARN" "Continuing deployment, but Kafka resources may not be ready."
    fi
}

# Function to create kustomization overlays for services
create_kustomization_overlays() {
    log "INFO" "Setting up image configuration for services"
    # Export image variables for substitution
    export TRADES_IMAGE
    export CANDLES_IMAGE
    export STRUCTURIZR_IMAGE
    export TECHNICAL_INDICATORS_IMAGE

    # Clean any existing overlays
    rm -rf temp-kustomize
    
    log "INFO" "Creating kustomize overlays for services..."
    # Create temp directory for kustomize overlays
    mkdir -p temp-kustomize/{trades,candles,technical_indicators,structurizr}

    # Create kustomization overlay for trades
    log "DEBUG" "Creating trades overlay with image: ${TRADES_IMAGE}"
    cat > temp-kustomize/trades/kustomization.yaml << EOL
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: services
resources:
  - ../../manifests/services/trades
patches:
- patch: |
    - op: replace
      path: /spec/template/spec/containers/0/image
      value: ${TRADES_IMAGE}
  target:
    group: apps
    version: v1
    kind: Deployment
    name: trades
EOL

    # Create kustomization overlay for candles
    log "DEBUG" "Creating candles overlay with image: ${CANDLES_IMAGE}"
    cat > temp-kustomize/candles/kustomization.yaml << EOL
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: services
resources:
  - ../../manifests/services/candles
patches:
- patch: |
    - op: replace
      path: /spec/template/spec/containers/0/image
      value: ${CANDLES_IMAGE}
  target:
    group: apps
    version: v1
    kind: Deployment
    name: candles
EOL

    # Create kustomization overlay for technical_indicators
    log "DEBUG" "Creating technical-indicators overlay with image: ${TECHNICAL_INDICATORS_IMAGE}"
    cat > temp-kustomize/technical_indicators/kustomization.yaml << EOL
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: services
resources:
  - ../../manifests/services/technical_indicators
patches:
- patch: |
    - op: replace
      path: /spec/template/spec/containers/0/image
      value: ${TECHNICAL_INDICATORS_IMAGE}
  target:
    group: apps
    version: v1
    kind: Deployment
    name: technical-indicators
EOL

    # Process structurizr manifest with environment variables
    log "INFO" "Processing structurizr manifest..."
    envsubst < manifests/structurizr/structurizr.yaml > manifests/processed/structurizr-processed.yaml
}

# Function to wait for Kafka bootstrap service
wait_for_kafka_bootstrap() {
    log "INFO" "Waiting for Kafka bootstrap service..."
    local max_attempts=12
    local kafka_bootstrap="crypto-kafka-cluster-kafka-bootstrap"
    
    for i in $(seq 1 $max_attempts); do
        if kubectl -n kafka get service $kafka_bootstrap &>/dev/null; then
            log "INFO" "Kafka bootstrap service found: $kafka_bootstrap"
            return 0
        else
            log "INFO" "Waiting for Kafka bootstrap service (attempt $i/$max_attempts)..."
            sleep 10
        fi
        
        if [ $i -eq $max_attempts ]; then
            log "WARN" "Timed out waiting for Kafka bootstrap service."
            log "WARN" "Services might not be able to connect to Kafka."
            return 1
        fi
    done
}

# Function to deploy services using kustomize
deploy_services() {
    log "INFO" "Deploying services using kustomize..."
    kubectl apply -k temp-kustomize/trades/
    kubectl apply -k temp-kustomize/candles/
    kubectl apply -k temp-kustomize/technical_indicators/

    # Deploy structurizr using processed manifest
    log "INFO" "Deploying structurizr..."
    kubectl apply -f manifests/processed/structurizr-processed.yaml

    # Clean up temporary files
    log "INFO" "Cleaning up temporary files..."
    rm -rf temp-kustomize
}

# Function to display service access information
display_service_info() {
    log "INFO" "Deployment completed successfully!"
    log "INFO" "Waiting for Load Balancers to be provisioned (this may take a few minutes)..."
    sleep 30

    # Get LoadBalancer IPs
    local KAFKA_UI_IP=$(kubectl -n kafka get service kafka-ui -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
    local STRUCTURIZR_IP=$(kubectl -n structurizr get service structurizr -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)

    log "INFO" "----------------------------------------"
    log "INFO" "Access Services via their LoadBalancer IPs:"
    log "INFO" "- Kafka UI: http://${KAFKA_UI_IP:-<pending>}"
    log "INFO" "- Structurizr: http://${STRUCTURIZR_IP:-<pending>}"
    log "INFO" ""
    log "INFO" "Note: If IPs show as <pending>, run the following commands to check status:"
    log "INFO" "kubectl -n kafka get service kafka-ui"
    log "INFO" "kubectl -n structurizr get service structurizr"
    log "INFO" ""
    log "INFO" "Internal services (not accessible externally):"
    log "INFO" "- Trades Service: only accessible within the cluster"
    log "INFO" "- Candles Service: only accessible within the cluster"
    log "INFO" "- Technical Indicators Service: only accessible within the cluster"
    log "INFO" "----------------------------------------"

    # Check if all pods are running
    log "INFO" "Checking pod status:"
    kubectl get pods --namespace services
}

# Main function that orchestrates the entire deployment process
main() {
    # Create namespaces
    create_namespaces
    
    # Deploy Strimzi Kafka operator
    deploy_strimzi
    
    # Deploy Kafka and Kafka UI
    deploy_kafka
    
    # Create kustomization overlays for services
    create_kustomization_overlays
    
    # Wait for Kafka bootstrap service
    wait_for_kafka_bootstrap
    
    # Deploy services
    deploy_services
    
    # Display service access information
    display_service_info
}

# Execute main function
main