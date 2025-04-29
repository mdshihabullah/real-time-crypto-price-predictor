#!/bin/bash
set -e

# Source the deployment configuration file
source deployment.config

# Set Kubernetes config to use DO cluster
export KUBECONFIG=$(pwd)/$KUBECONFIG_PATH

if [ ! -f "$KUBECONFIG" ]; then
  echo "Error: Kubeconfig file not found at $KUBECONFIG"
  echo "Please check your KUBECONFIG_PATH in deployment.config"
  exit 1
fi

echo "Using DigitalOcean Kubernetes cluster with config: $KUBECONFIG"
kubectl get nodes

# Create necessary namespaces
echo "Creating namespaces..."
kubectl create namespace services --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace structurizr --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace kafka --dry-run=client -o yaml | kubectl apply -f -

# Clean up any existing Strimzi deployment to avoid conflicts
echo "Cleaning up any existing Strimzi deployments..."
kubectl -n kafka delete deployment strimzi-cluster-operator --ignore-not-found=true
echo "Waiting for cleanup to complete..."
sleep 10

# Apply Strimzi CRDs directly first to ensure they're installed
echo "Installing Strimzi CRDs and operator directly..."
kubectl apply -f https://strimzi.io/install/latest?namespace=kafka

# Wait for the Strimzi operator to be ready
echo "Waiting for Strimzi operator to be ready..."
kubectl -n kafka wait --timeout=300s --for=condition=ready pod -l name=strimzi-cluster-operator || true

# Wait for Strimzi CRDs to be established
echo "Waiting for Strimzi CRDs to be established..."
for i in {1..10}; do
  if kubectl get crd kafkas.kafka.strimzi.io &>/dev/null && \
     kubectl get crd kafkanodepools.kafka.strimzi.io &>/dev/null; then
    echo "Strimzi CRDs are ready."
    break
  else
    echo "Waiting for Strimzi CRDs to be installed (attempt $i)..."
    sleep 10
  fi
  
  if [ $i -eq 10 ]; then
    echo "ERROR: Timed out waiting for Strimzi CRDs to be installed."
    echo "You may need to manually verify that the Strimzi operator is working correctly."
    exit 1
  fi
done

# Create processed directory if it doesn't exist
mkdir -p manifests/processed

# Deploy Kafka and related components
echo "Deploying Kafka components..."
kubectl apply -f manifests/kafka-and-topics.yaml

# First delete any existing kafka-ui deployment to avoid selector immutability issues
echo "Cleaning up any existing Kafka UI deployment..."
kubectl -n kafka delete deployment kafka-ui --ignore-not-found=true
kubectl -n kafka delete service kafka-ui --ignore-not-found=true
sleep 5

# Deploy Kafka UI separately
echo "Deploying Kafka UI..."
kubectl apply -f manifests/kafka-ui.yaml

echo "Waiting for Kafka cluster to be ready (this may take several minutes)..."
# First check if the resource type exists
if kubectl -n kafka get kafka &>/dev/null; then
  # Only wait if the resource type exists
  echo "Kafka CRD exists. Waiting for Kafka cluster to be ready..."
  kubectl -n kafka wait --for=condition=ready kafka crypto-kafka-cluster --timeout=180s || true
else
  echo "WARNING: Unable to wait for Kafka cluster - resource type not found"
  echo "Continuing deployment, but Kafka resources may not be ready."
fi

# Set environment variables for service manifests
export TRADES_IMAGE
export CANDLES_IMAGE
export STRUCTURIZR_IMAGE
export TECHNICAL_INDICATORS_IMAGE
# Process services manifests with environment variables
echo "Processing service manifests..."
envsubst < manifests/services/trades/trades.yaml > manifests/processed/trades-processed.yaml
envsubst < manifests/services/candles/candles.yaml > manifests/processed/candles-processed.yaml
envsubst < manifests/services/technical_indicators/technical_indicators.yaml > manifests/processed/technical_indicators-processed.yaml
envsubst < manifests/structurizr/structurizr.yaml > manifests/processed/structurizr-processed.yaml

# Wait for Kafka bootstrap service to be available
echo "Waiting for Kafka bootstrap service..."
for i in {1..12}; do
  if kubectl -n kafka get service crypto-kafka-cluster-kafka-bootstrap &>/dev/null; then
    echo "Kafka bootstrap service found."
    break
  else
    echo "Waiting for Kafka bootstrap service (attempt $i)..."
    sleep 10
  fi
  
  if [ $i -eq 12 ]; then
    echo "WARNING: Timed out waiting for Kafka bootstrap service."
    echo "Services might not be able to connect to Kafka."
  fi
done

# Deploy services
echo "Deploying services..."
kubectl apply -f manifests/processed/trades-processed.yaml
kubectl apply -f manifests/processed/candles-processed.yaml
kubectl apply -f manifests/processed/technical_indicators-processed.yaml
kubectl apply -f manifests/processed/structurizr-processed.yaml

echo "Deployment completed successfully!"
echo ""
echo "Waiting for Load Balancers to be provisioned (this may take a few minutes)..."
sleep 30

# Get LoadBalancer IPs
KAFKA_UI_IP=$(kubectl -n kafka get service kafka-ui -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
STRUCTURIZR_IP=$(kubectl -n structurizr get service structurizr -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

echo "Access Services via their LoadBalancer IPs:"
echo "- Kafka UI: http://${KAFKA_UI_IP:-<pending>}"
echo "- Structurizr: http://${STRUCTURIZR_IP:-<pending>}"
echo ""
echo "Note: If IPs show as <pending>, run the following commands to check status:"
echo "kubectl -n kafka get service kafka-ui"
echo "kubectl -n structurizr get service structurizr"
echo ""
echo "Internal services (not accessible externally):"
echo "- Trades Service: only accessible within the cluster"
echo "- Candles Service: only accessible within the cluster"
echo "- Technical Indicators Service: only accessible within the cluster"

# Check if all pods are running
echo ""
echo "Checking pod status:"
kubectl get pods --all-namespaces 