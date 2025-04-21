#!/bin/bash
# Steps:

# 1. Delete the cluster (if it exists, otherwise it will fail)
echo "Deleting the cluster..."
kind delete cluster --name rwml-34fa

# 2. Delete the docker network (if it exists, otherwise it will fail)
echo "Deleting the docker network..."
docker network rm rwml-34fa-network

# 3. Create the docker network
echo "Creating the docker network..."
docker network create --subnet 172.100.0.0/16 rwml-34fa-network

# 4. Create the cluster
echo "Creating the cluster..."
KIND_EXPERIMENTAL_DOCKER_NETWORK=rwml-34fa-network kind create cluster --config ./kind-with-portmapping.yaml

# 5. Install Kafka
echo "Installing Kafka..."
chmod +x ./install_kafka.sh
./install_kafka.sh

# 6. Install Kafka UI
echo "Installing Kafka UI..."
chmod +x ./install_kafka_ui.sh
./install_kafka_ui.sh

# 7. Wait for Kafka UI pod to be ready
echo "Waiting for Kafka UI pod to be ready..."
# Allow time for the pod to be created
sleep 10

# More robust wait for pod creation and readiness with retries
MAX_RETRIES=30
RETRY_COUNT=0
READY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ] && [ "$READY" = false ]; do
  if kubectl get pods -n kafka -l app.kubernetes.io/component=kafka-ui 2>/dev/null | grep -q "Running"; then
    if kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=kafka-ui -n kafka --timeout=10s 2>/dev/null; then
      READY=true
      echo "Kafka UI pod is ready now."
    fi
  fi
  
  if [ "$READY" = false ]; then
    echo "Waiting for Kafka UI pod to be ready... (Attempt $((RETRY_COUNT+1))/$MAX_RETRIES)"
    RETRY_COUNT=$((RETRY_COUNT+1))
    sleep 5
  fi
done

if [ "$READY" = false ]; then
  echo "Warning: Kafka UI pod is not ready after $MAX_RETRIES attempts, but proceeding with port forwarding anyway."
fi

# 8. Port forward Kafka UI
echo "Port forwarding Kafka UI to localhost:19092..."
kubectl port-forward -n kafka svc/kafka-ui 19092:8080