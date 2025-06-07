#!/bin/bash
# Production infrastructure deployment script for Digital Ocean Kubernetes
# This script deploys RisingWave, MLflow, and Grafana to the Digital Ocean cluster
# Supports future expansion for Metabase and LLM services

set -euo pipefail

# Color codes for better readability
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
BLUE="\033[0;34m"
NC="\033[0m" # No Color

# Logging function
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
        "SUCCESS")
            echo -e "${GREEN}[SUCCESS]${NC} ${timestamp} - $message"
            ;;
        *)
            echo -e "${timestamp} - $message"
            ;;
    esac
}

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFESTS_DIR="${SCRIPT_DIR}/manifests/infrastructure"
KUBECONFIG_FILE="${SCRIPT_DIR}/do-k8s-kubeconfig.yaml"

# Load configuration
if [ -f "${SCRIPT_DIR}/deployment.config" ]; then
    log "INFO" "Loading deployment configuration..."
    source "${SCRIPT_DIR}/deployment.config"
else
    log "ERROR" "deployment.config file not found!"
    exit 1
fi

# Set required environment variables with defaults
export MLFLOW_DB_PASSWORD="${MLFLOW_DB_PASSWORD:-mlflow123secure}"
export GRAFANA_DB_PASSWORD="${GRAFANA_DB_PASSWORD:-grafana123secure}"
export METABASE_DB_PASSWORD="${METABASE_DB_PASSWORD:-metabase123secure}"
export MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
export MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin123secure}"
export GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-grafana-admin-2024}"
export DOMAIN="${DOMAIN:-crypto-predictor.local}"
export ENABLE_RESOURCE_OPTIMIZATION="${ENABLE_RESOURCE_OPTIMIZATION:-true}"
export DEPLOY_METABASE="${DEPLOY_METABASE:-false}"
export DEPLOY_LLM_SERVICES="${DEPLOY_LLM_SERVICES:-false}"

# Set Kubernetes config to use DO cluster
export KUBECONFIG="${KUBECONFIG_FILE}"

# Function to check if namespace exists
namespace_exists() {
    kubectl get namespace "$1" &> /dev/null
}

# Function to create namespace if it doesn't exist
create_namespace() {
    local namespace=$1
    local description="${2:-}"
    
    if ! namespace_exists "$namespace"; then
        log "INFO" "Creating namespace: $namespace"
        kubectl create namespace "$namespace"
        
        # Add common labels for better resource management
        kubectl label namespace "$namespace" "app.kubernetes.io/part-of=crypto-predictor" --overwrite
        kubectl label namespace "$namespace" "environment=production" --overwrite
        
        if [ -n "$description" ]; then
            kubectl annotate namespace "$namespace" "description=$description" --overwrite
        fi
    else
        log "INFO" "Namespace $namespace already exists"
    fi
}

# Function to verify cluster resources
verify_cluster_resources() {
    log "INFO" "=== Verifying cluster resources ==="
    
    # Check kubectl connectivity
    if ! kubectl cluster-info &>/dev/null; then
        log "ERROR" "Failed to connect to Kubernetes cluster. Please check your kubeconfig."
        log "DEBUG" "KUBECONFIG=$KUBECONFIG"
        return 1
    fi
    
    # Check available nodes and resources
    local node_count=$(kubectl get nodes --no-headers 2>/dev/null | wc -l | tr -d ' ')
    local ready_nodes=$(kubectl get nodes --no-headers 2>/dev/null | grep -c "Ready" || echo "0")
    
    log "INFO" "Cluster has $ready_nodes/$node_count nodes ready"
    
    if [ "$node_count" -eq 0 ]; then
        log "ERROR" "No nodes found in the cluster!"
        return 1
    fi
    
    if [ "$ready_nodes" -eq 0 ]; then
        log "ERROR" "No ready nodes found in the cluster!"
        return 1
    fi
    
    # Check cluster capacity
    log "INFO" "Node Resources:"
    kubectl get nodes -o=custom-columns="NAME:.metadata.name,CPU:.status.allocatable.cpu,MEMORY:.status.allocatable.memory" --no-headers 2>/dev/null || log "WARN" "Failed to get node resources"
    
    # Check storage classes
    log "INFO" "Available Storage Classes:"
    kubectl get storageclass --no-headers 2>/dev/null || log "WARN" "Failed to get storage classes"
    
    # Check if default storage class is set
    if ! kubectl get storageclass 2>/dev/null | grep -q "(default)"; then
        log "WARN" "No default storage class found. Some components may fail to provision persistent volumes."
    fi
    
    return 0
}

# Function to wait for pods to be ready with improved error handling
wait_for_pods() {
    local namespace=$1
    local selector=$2
    local timeout_seconds=${3:-300}
    local start_time=$(date +%s)
    local end_time=$((start_time + timeout_seconds))
    
    log "INFO" "Waiting for pods with selector '$selector' in namespace '$namespace' to be ready (timeout: ${timeout_seconds}s)..."
    
    # Wait for at least one pod to be created
    local pod_count=0
    while [ $(date +%s) -lt $end_time ] && [ "$pod_count" -eq 0 ]; do
        pod_count=$(kubectl get pods -n "$namespace" -l "$selector" --no-headers 2>/dev/null | wc -l | tr -d ' ' || echo "0")
        if [ "$pod_count" -eq 0 ]; then
            log "DEBUG" "Waiting for pods to be created..."
            sleep 5
        fi
    done
    
    if [ "$pod_count" -eq 0 ]; then
        log "ERROR" "No pods found with selector '$selector' in namespace '$namespace' after waiting"
        return 1
    fi
    
    log "INFO" "Found $pod_count pod(s), waiting for them to be ready..."
    
    # Wait for all pods to be ready
    while [ $(date +%s) -lt $end_time ]; do
        local ready_count=$(kubectl get pods -n "$namespace" -l "$selector" --no-headers 2>/dev/null | grep -c "Running" || echo "0")
        
        if [ "$ready_count" -eq "$pod_count" ]; then
            local duration=$(( $(date +%s) - start_time ))
            log "SUCCESS" "All $pod_count pods are ready in ${duration}s"
            return 0
        fi
        
        log "DEBUG" "Pods ready: $ready_count/$pod_count"
        sleep 10
    done
    
    log "ERROR" "Timed out waiting for pods to be ready"
    kubectl get pods -n "$namespace" -l "$selector" -o wide
    return 1
}

# Function to deploy Helm chart with retry and better error handling
deploy_helm_chart() {
    local name=$1
    local namespace=$2
    local chart=$3
    local values_file=$4
    local timeout=${5:-600s}
    local max_retries=3
    local attempt=1
    
    # Validate values file exists
    if [ ! -f "$values_file" ]; then
        log "ERROR" "Values file not found: $values_file"
        return 1
    fi
    
    log "INFO" "Deploying $name to namespace $namespace using chart $chart..."
    
    # Add helm repos based on chart
    case "$chart" in
        risingwavelabs/*)
            log "INFO" "Adding RisingWave Helm repository..."
            helm repo add risingwavelabs https://risingwavelabs.github.io/helm-charts/ --force-update || log "WARN" "Failed to add risingwavelabs repo"
            ;;
        grafana/*)
            log "INFO" "Adding Grafana Helm repository..."
            helm repo add grafana https://grafana.github.io/helm-charts --force-update || log "WARN" "Failed to add grafana repo"
            ;;
        oci://*)
            log "INFO" "Using OCI chart: $chart"
            ;;
    esac
    
    # Update helm repos
    log "INFO" "Updating Helm repositories..."
    helm repo update || log "WARN" "Failed to update Helm repositories"
    
    # Retry loop for helm deployment
    while [ $attempt -le $max_retries ]; do
        log "INFO" "Deployment attempt $attempt of $max_retries for $name..."
        
        # Check if release exists
        if helm status -n "$namespace" "$name" &>/dev/null; then
            log "INFO" "Upgrading existing release $name..."
            action="upgrade"
        else
            log "INFO" "Installing new release $name..."
            action="install"
        fi
        
        # Deploy the chart
        if helm upgrade --install "$name" "$chart" \
            --namespace="$namespace" \
            --create-namespace \
            --values="$values_file" \
            --timeout="$timeout" \
            --wait \
            --wait-for-jobs; then
            
            log "SUCCESS" "Successfully deployed $name"
            return 0
        else
            local exit_code=$?
            log "WARN" "Failed to deploy $name (attempt $attempt/$max_retries), exit code: $exit_code"
            
            if [ $attempt -lt $max_retries ]; then
                local wait_seconds=$((attempt * 15))
                log "INFO" "Retrying in $wait_seconds seconds..."
                sleep $wait_seconds
            fi
            attempt=$((attempt + 1))
        fi
    done
    
    log "ERROR" "Failed to deploy $name after $max_retries attempts"
    return 1
}

# Function to create database and user in PostgreSQL
create_postgres_db_user() {
    local namespace=$1
    local db_name=$2
    local db_user=$3
    local db_password=$4
    local max_retries=10
    local attempt=1
    
    log "INFO" "=== Setting up PostgreSQL database: $db_name with user: $db_user ==="
    
    # Wait for PostgreSQL to be ready
    local pg_pod=""
    while [ $attempt -le $max_retries ]; do
        log "INFO" "Looking for PostgreSQL pod (attempt $attempt/$max_retries)..."
        
        pg_pod=$(kubectl get pods -n "$namespace" -l "app.kubernetes.io/name=postgresql" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
        
        if [ -n "$pg_pod" ]; then
            if kubectl exec -n "$namespace" "$pg_pod" -- pg_isready -U postgres -h localhost >/dev/null 2>&1; then
                log "INFO" "PostgreSQL is ready in pod: $pg_pod"
                break
            fi
        fi
        
        if [ $attempt -eq $max_retries ]; then
            log "ERROR" "Failed to connect to PostgreSQL after $max_retries attempts"
            return 1
        fi
        
        sleep 10
        attempt=$((attempt + 1))
    done
    
    # Function to execute SQL command
    execute_sql() {
        local sql="$1"
        local description="${2:-SQL command}"
        
        log "DEBUG" "Executing: $description"
        if kubectl exec -n "$namespace" "$pg_pod" -- psql -U postgres -t -c "$sql" 2>/dev/null; then
            return 0
        else
            log "ERROR" "Failed to execute: $description"
            return 1
        fi
    }
    
    # Create database if it doesn't exist
    log "INFO" "Creating database: $db_name"
    if ! execute_sql "SELECT 1 FROM pg_database WHERE datname = '$db_name'" "Check if database exists" | grep -q 1; then
        if execute_sql "CREATE DATABASE $db_name;" "Create database $db_name"; then
            log "SUCCESS" "Database created: $db_name"
        else
            return 1
        fi
    else
        log "INFO" "Database already exists: $db_name"
    fi
    
    # Create user if it doesn't exist
    log "INFO" "Creating user: $db_user"
    if ! execute_sql "SELECT 1 FROM pg_user WHERE usename = '$db_user'" "Check if user exists" | grep -q 1; then
        if execute_sql "CREATE USER $db_user WITH PASSWORD '$db_password' NOCREATEDB NOCREATEROLE;" "Create user $db_user"; then
            log "SUCCESS" "User created: $db_user"
        else
            return 1
        fi
    else
        log "INFO" "User already exists: $db_user"
        execute_sql "ALTER USER $db_user WITH PASSWORD '$db_password';" "Update user password"
    fi
    
    # Grant privileges
    log "INFO" "Granting privileges on $db_name to $db_user"
    execute_sql "GRANT ALL PRIVILEGES ON DATABASE $db_name TO $db_user;" "Grant privileges"
    
    return 0
}

# Function to deploy Grafana dashboards
deploy_grafana_dashboards() {
    log "INFO" "=== Deploying Grafana dashboards ==="
    
    # Apply the dashboard ConfigMaps
    if [ -f "$MANIFESTS_DIR/grafana-dashboards.yaml" ]; then
        log "INFO" "Applying Grafana dashboard ConfigMaps..."
        if kubectl apply -f "$MANIFESTS_DIR/grafana-dashboards.yaml"; then
            log "SUCCESS" "Grafana dashboards deployed successfully"
        else
            log "WARN" "Failed to deploy Grafana dashboards"
        fi
    else
        log "WARN" "Grafana dashboards file not found: $MANIFESTS_DIR/grafana-dashboards.yaml"
    fi
}

# Function to print service endpoints
print_service_endpoints() {
    log "INFO" "\n=== Service Endpoints ==="
    
    # Wait a bit for LoadBalancer IPs to be assigned
    log "INFO" "Waiting for LoadBalancer IPs to be assigned..."
    sleep 30
    
    # RisingWave Frontend
    local rw_frontend_ip=$(kubectl get svc -n risingwave risingwave-frontend -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "<pending>")
    log "INFO" "RisingWave Frontend: ${rw_frontend_ip}:4567 (SQL interface)"
    
    # MLflow
    local mlflow_ip=$(kubectl get svc -n mlflow mlflow -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "<pending>")
    log "INFO" "MLflow UI: http://${mlflow_ip}"
    
    # Grafana
    local grafana_ip=$(kubectl get svc -n grafana grafana -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "<pending>")
    log "INFO" "Grafana: http://${grafana_ip}"
    log "INFO" "Grafana Admin Username: admin"
    log "INFO" "Grafana Admin Password: ${GRAFANA_ADMIN_PASSWORD}"
    
    # MinIO (internal access)
    log "INFO" "\nMinIO (Internal Access):"
    log "INFO" "  kubectl port-forward -n risingwave svc/risingwave-minio 9001:9001"
    log "INFO" "  URL: http://localhost:9001"
    log "INFO" "  Username: ${MINIO_ROOT_USER}"
    log "INFO" "  Password: ${MINIO_ROOT_PASSWORD}"
    
    # Print port-forward commands if LoadBalancer is pending
    if [ "$rw_frontend_ip" = "<pending>" ] || [ "$mlflow_ip" = "<pending>" ] || [ "$grafana_ip" = "<pending>" ]; then
        log "INFO" "\n=== Alternative Access (Port Forwarding) ==="
        log "INFO" "Use these commands if LoadBalancer IPs are not available:"
        log "INFO" "  # RisingWave Frontend: kubectl port-forward -n risingwave svc/risingwave-frontend 4567:4567"
        log "INFO" "  # MLflow UI: kubectl port-forward -n mlflow svc/mlflow 5000:5000"
        log "INFO" "  # Grafana: kubectl port-forward -n grafana svc/grafana 3000:80"
    fi
}

# Function to verify deployments
verify_deployments() {
    log "INFO" "\n=== Verifying Deployments ==="
    
    local all_healthy=true
    local namespaces=("risingwave" "mlflow" "grafana")
    
    for ns in "${namespaces[@]}"; do
        log "INFO" "Checking deployments in namespace: $ns"
        
        if ! kubectl get namespace "$ns" &>/dev/null; then
            log "ERROR" "Namespace $ns not found!"
            all_healthy=false
            continue
        fi
        
        local deployments=$(kubectl get deployments -n "$ns" --no-headers 2>/dev/null | awk '{print $1}' || true)
        
        if [ -z "$deployments" ]; then
            log "WARN" "No deployments found in namespace $ns"
            continue
        fi
        
        for deployment in $deployments; do
            if kubectl rollout status -n "$ns" deployment/"$deployment" --timeout=30s &>/dev/null; then
                log "SUCCESS" "Deployment $deployment in $ns is healthy"
            else
                log "ERROR" "Deployment $deployment in $ns is not healthy"
                all_healthy=false
            fi
        done
    done
    
    if [ "$all_healthy" = true ]; then
        log "SUCCESS" "All deployments are healthy"
        return 0
    else
        log "ERROR" "Some deployments are not healthy. Check logs with 'kubectl logs' for details."
        return 1
    fi
}

# Main deployment function
main() {
    local start_time=$(date +%s)
    
    log "INFO" "=== Starting Infrastructure Deployment ==="
    log "INFO" "Configuration loaded from: ${SCRIPT_DIR}/deployment.config"
    log "INFO" "Using kubeconfig: ${KUBECONFIG_FILE}"
    
    # Verify cluster access and resources
    if ! verify_cluster_resources; then
        log "ERROR" "Cluster verification failed"
        exit 1
    fi
    
    # Create namespaces
    log "INFO" "=== Creating namespaces ==="
    create_namespace "risingwave" "Streaming database and storage backend"
    create_namespace "mlflow" "Machine learning experiment tracking"
    create_namespace "grafana" "Monitoring and visualization"
    
    # Future services (conditional)
    if [ "$DEPLOY_METABASE" = "true" ]; then
        create_namespace "metabase" "Business intelligence and analytics"
    fi
    
    if [ "$DEPLOY_LLM_SERVICES" = "true" ]; then
        create_namespace "llm-services" "Large language model services"
    fi
    
    # Deploy RisingWave (core streaming database)
    log "INFO" "=== Deploying RisingWave ==="
    if ! deploy_helm_chart "risingwave" "risingwave" \
        "risingwavelabs/risingwave" \
        "$MANIFESTS_DIR/risingwave-values.yaml" \
        "900s"; then
        log "ERROR" "Failed to deploy RisingWave"
        exit 1
    fi
    
    # Wait for RisingWave components to be ready
    log "INFO" "Waiting for RisingWave components to be ready..."
    if ! wait_for_pods "risingwave" "app.kubernetes.io/instance=risingwave" 600; then
        log "ERROR" "RisingWave pods failed to become ready"
        exit 1
    fi
    
    # Create databases for other services
    log "INFO" "=== Setting up databases ==="
    
    # MLflow database
    if ! create_postgres_db_user "risingwave" "mlflow" "mlflow" "$MLFLOW_DB_PASSWORD"; then
        log "WARN" "Failed to create MLflow database - will use SQLite fallback"
    fi
    
    # Grafana database
    if ! create_postgres_db_user "risingwave" "grafana" "grafana" "$GRAFANA_DB_PASSWORD"; then
        log "WARN" "Failed to create Grafana database - will use SQLite fallback"
    fi
    
    # Metabase database (if enabled)
    if [ "$DEPLOY_METABASE" = "true" ]; then
        if ! create_postgres_db_user "risingwave" "metabase" "metabase" "$METABASE_DB_PASSWORD"; then
            log "WARN" "Failed to create Metabase database"
        fi
    fi
    
    # Create MLflow MinIO secret
    log "INFO" "Creating MLflow MinIO secret..."
    if ! kubectl get secret -n mlflow mlflow-minio-credentials &>/dev/null; then
        if kubectl apply -f "$MANIFESTS_DIR/mlflow-minio-secret.yaml"; then
            log "SUCCESS" "MLflow MinIO secret created"
        else
            log "ERROR" "Failed to create MLflow MinIO secret"
            exit 1
        fi
    else
        log "INFO" "MLflow MinIO secret already exists"
    fi
    
    # Deploy MLflow
    log "INFO" "=== Deploying MLflow ==="
    if ! deploy_helm_chart "mlflow" "mlflow" \
        "oci://registry-1.docker.io/bitnamicharts/mlflow" \
        "$MANIFESTS_DIR/mlflow-values.yaml" \
        "600s"; then
        log "ERROR" "Failed to deploy MLflow"
        exit 1
    fi
    
    # Deploy Grafana
    log "INFO" "=== Deploying Grafana ==="
    if ! deploy_helm_chart "grafana" "grafana" \
        "grafana/grafana" \
        "$MANIFESTS_DIR/grafana-values.yaml" \
        "600s"; then
        log "ERROR" "Failed to deploy Grafana"
        exit 1
    fi
    
    # Deploy Grafana dashboards
    deploy_grafana_dashboards
    
    # Wait for all deployments to be ready
    log "INFO" "=== Waiting for all deployments to be ready ==="
    
    if ! wait_for_pods "mlflow" "app.kubernetes.io/instance=mlflow" 300; then
        log "WARN" "MLflow pods may not be fully ready"
    fi
    
    if ! wait_for_pods "grafana" "app.kubernetes.io/name=grafana" 300; then
        log "WARN" "Grafana pods may not be fully ready"
    fi
    
    # Verify all deployments
    verify_deployments
    
    # Print service endpoints
    print_service_endpoints
    
    local duration=$(( $(date +%s) - start_time ))
    log "SUCCESS" "=== Infrastructure deployment completed in ${duration} seconds! ==="
    
    # Display next steps
    log "INFO" "\n=== Next Steps ==="
    log "INFO" "1. Access Grafana to view crypto price dashboards"
    log "INFO" "2. Use MLflow to track machine learning experiments"
    log "INFO" "3. Connect to RisingWave for real-time data queries"
    log "INFO" "4. Check service status: kubectl get all --all-namespaces"
    log "INFO" "5. View logs if needed: kubectl logs -n <namespace> <pod-name>"
    
    if [ "$DEPLOY_METABASE" = "true" ]; then
        log "INFO" "6. Metabase namespace created - deploy when ready"
    fi
    
    if [ "$DEPLOY_LLM_SERVICES" = "true" ]; then
        log "INFO" "7. LLM services namespace created - deploy when ready"
    fi
    
    log "INFO" "\nNote: LoadBalancer IPs may take a few minutes to be assigned."
    log "INFO" "Run 'kubectl get svc -A' to check LoadBalancer status."
}

# Run main function
main "$@"
