#!/bin/bash
# Pre-deployment validation script for Real-time Crypto Price Predictor
# Comprehensive checks to ensure successful deployment before running main scripts

set -euo pipefail

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
        "SUCCESS")
            echo -e "${GREEN}[SUCCESS]${NC} ${timestamp} - $message"
            ;;
        *)
            echo -e "${timestamp} - $message"
            ;;
    esac
}

# Global variables for tracking validation results
VALIDATION_ERRORS=0
VALIDATION_WARNINGS=0

# Function to increment error count
error() {
    VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
    log "ERROR" "$1"
}

# Function to increment warning count
warning() {
    VALIDATION_WARNINGS=$((VALIDATION_WARNINGS + 1))
    log "WARN" "$1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisite tools
check_prerequisites() {
    log "INFO" "=== Checking Prerequisites ==="
    
    # Check kubectl
    if command_exists kubectl; then
        local kubectl_version=$(kubectl version --client --short 2>/dev/null | head -1 || echo "unknown")
        log "SUCCESS" "kubectl found: $kubectl_version"
    else
        error "kubectl not found. Please install kubectl"
        return 1
    fi
    
    # Check helm
    if command_exists helm; then
        local helm_version=$(helm version --short 2>/dev/null || echo "unknown")
        log "SUCCESS" "Helm found: $helm_version"
    else
        error "Helm not found. Please install Helm 3.x"
        return 1
    fi
    
    # Check python3
    if command_exists python3; then
        local python_version=$(python3 --version 2>/dev/null || echo "unknown")
        log "SUCCESS" "Python3 found: $python_version"
    else
        error "Python3 not found. Please install Python 3.x"
        return 1
    fi
    
    # Check pyyaml
    if python3 -c "import yaml" 2>/dev/null; then
        log "SUCCESS" "PyYAML available"
    else
        warning "PyYAML not found. Attempting to install..."
        if pip3 install pyyaml 2>/dev/null; then
            log "SUCCESS" "PyYAML installed successfully"
        else
            error "Failed to install PyYAML. Please install manually: pip3 install pyyaml"
        fi
    fi
    
    # Check envsubst (for environment variable substitution)
    if command_exists envsubst; then
        log "SUCCESS" "envsubst found"
    else
        warning "envsubst not found. It may be needed for some configurations"
    fi
    
    # Check Docker (optional but helpful for debugging)
    if command_exists docker; then
        log "INFO" "Docker found (optional)"
    else
        log "INFO" "Docker not found (optional, but helpful for debugging images)"
    fi
    
    return 0
}

# Check required files and directories
check_files_and_directories() {
    log "INFO" "=== Checking Required Files and Directories ==="
    
    local required_files=(
        "deployment.config"
        "do-k8s-kubeconfig.yaml"
        "create-do-k8s-cluster.sh"
        "deploy_infrastructure.sh"
        "generate_grafana_dashboards.py"
    )
    
    local required_dirs=(
        "manifests"
        "manifests/infrastructure"
        "manifests/services"
        "manifests/structurizr"
    )
    
    # Check required files
    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            log "SUCCESS" "Required file found: $file"
        else
            error "Required file missing: $file"
        fi
    done
    
    # Check required directories
    for dir in "${required_dirs[@]}"; do
        if [ -d "$dir" ]; then
            log "SUCCESS" "Required directory found: $dir"
        else
            error "Required directory missing: $dir"
        fi
    done
    
    # Check specific manifest files
    local manifest_files=(
        "manifests/infrastructure/risingwave-values.yaml"
        "manifests/infrastructure/mlflow-values.yaml"
        "manifests/infrastructure/grafana-values.yaml"
        "manifests/infrastructure/mlflow-minio-secret.yaml"
        "manifests/kafka-and-topics.yaml"
        "manifests/kafka-ui.yaml"
    )
    
    for file in "${manifest_files[@]}"; do
        if [ -f "$file" ]; then
            log "SUCCESS" "Manifest file found: $file"
        else
            error "Manifest file missing: $file"
        fi
    done
    
    # Check service directories
    local service_dirs=("trades" "candles" "technical_indicators")
    for service in "${service_dirs[@]}"; do
        if [ -d "manifests/services/$service" ]; then
            log "SUCCESS" "Service manifest directory found: manifests/services/$service"
        else
            error "Service manifest directory missing: manifests/services/$service"
        fi
    done
    
    return 0
}

# Validate configuration file
validate_configuration() {
    log "INFO" "=== Validating Configuration ==="
    
    if [ ! -f "deployment.config" ]; then
        error "Configuration file deployment.config not found"
        return 1
    fi
    
    # Source the configuration
    source deployment.config
    
    # Check required environment variables
    local required_vars=(
        "TRADES_IMAGE"
        "CANDLES_IMAGE"
        "TECHNICAL_INDICATORS_IMAGE"
        "STRUCTURIZR_IMAGE"
        "KUBECONFIG_PATH"
        "MLFLOW_DB_PASSWORD"
        "GRAFANA_DB_PASSWORD"
        "MINIO_ROOT_USER"
        "MINIO_ROOT_PASSWORD"
        "GRAFANA_ADMIN_PASSWORD"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -n "${!var:-}" ]; then
            log "SUCCESS" "Configuration variable set: $var"
        else
            error "Configuration variable not set or empty: $var"
        fi
    done
    
    # Validate image references (basic format check)
    local images=("$TRADES_IMAGE" "$CANDLES_IMAGE" "$TECHNICAL_INDICATORS_IMAGE" "$STRUCTURIZR_IMAGE")
    for image in "${images[@]}"; do
        if [[ "$image" =~ ^[a-z0-9._/-]+:[a-z0-9._-]+$ ]]; then
            log "SUCCESS" "Image format valid: $image"
        else
            warning "Image format may be invalid: $image"
        fi
    done
    
    return 0
}

# Validate cluster connectivity and resources
validate_cluster() {
    log "INFO" "=== Validating Cluster Connectivity and Resources ==="
    
    # Check kubeconfig file
    local kubeconfig_path="${KUBECONFIG_PATH:-do-k8s-kubeconfig.yaml}"
    if [ ! -f "$kubeconfig_path" ]; then
        error "Kubeconfig file not found: $kubeconfig_path"
        return 1
    fi
    
    # Set KUBECONFIG for validation
    export KUBECONFIG="$(pwd)/$kubeconfig_path"
    
    # Test cluster connectivity
    if kubectl cluster-info >/dev/null 2>&1; then
        log "SUCCESS" "Cluster connectivity verified"
    else
        error "Cannot connect to Kubernetes cluster. Please check your kubeconfig and cluster status"
        return 1
    fi
    
    # Check nodes
    local node_count=$(kubectl get nodes --no-headers 2>/dev/null | wc -l | tr -d ' ')
    local ready_nodes=$(kubectl get nodes --no-headers 2>/dev/null | grep -c "Ready" || echo "0")
    
    if [ "$ready_nodes" -gt 0 ]; then
        log "SUCCESS" "Cluster has $ready_nodes/$node_count nodes ready"
    else
        error "No ready nodes found in the cluster"
        return 1
    fi
    
    # Check node resources
    log "INFO" "Checking node resources..."
    kubectl get nodes -o=custom-columns="NAME:.metadata.name,CPU:.status.allocatable.cpu,MEMORY:.status.allocatable.memory" --no-headers 2>/dev/null || warning "Failed to get node resource information"
    
    # Check storage classes
    if kubectl get storageclass >/dev/null 2>&1; then
        local storage_classes=$(kubectl get storageclass --no-headers | wc -l | tr -d ' ')
        log "SUCCESS" "Found $storage_classes storage class(es)"
        
        # Check for do-block-storage specifically
        if kubectl get storageclass do-block-storage >/dev/null 2>&1; then
            log "SUCCESS" "do-block-storage StorageClass found"
        else
            warning "do-block-storage StorageClass not found. Available storage classes:"
            kubectl get storageclass --no-headers | while read -r name provisioner age; do
                log "INFO" "  - $name (provisioner: $provisioner)"
            done
        fi
    else
        warning "No storage classes found or unable to query"
    fi
    
    # Check for existing deployments that might conflict
    local existing_namespaces=$(kubectl get namespaces -o name 2>/dev/null | grep -E "(services|kafka|risingwave|mlflow|grafana|structurizr)" | wc -l | tr -d ' ')
    if [ "$existing_namespaces" -gt 0 ]; then
        warning "Found $existing_namespaces existing deployment namespace(s):"
        kubectl get namespaces | grep -E "(services|kafka|risingwave|mlflow|grafana|structurizr)" || true
        warning "Existing deployments may conflict with new deployment"
    else
        log "SUCCESS" "No conflicting namespaces found"
    fi
    
    return 0
}

# Check resource requirements vs available resources
check_resource_requirements() {
    log "INFO" "=== Checking Resource Requirements ==="
    
    # Calculate approximate resource requirements (based on values files)
    # These are estimates from the optimized values
    local total_cpu_request="1500m"  # Approximate sum of all CPU requests
    local total_memory_request="8Gi"  # Approximate sum of all memory requests
    
    log "INFO" "Estimated resource requirements:"
    log "INFO" "  - CPU requests: ~$total_cpu_request"
    log "INFO" "  - Memory requests: ~$total_memory_request"
    
    # Check available resources (simplified)
    if command -v bc >/dev/null 2>&1; then
        # Get allocatable resources if bc is available for calculations
        local total_cpu=$(kubectl get nodes -o jsonpath='{.items[*].status.allocatable.cpu}' 2>/dev/null | tr ' ' '+' | sed 's/+$//' || echo "0")
        local total_memory=$(kubectl get nodes -o jsonpath='{.items[*].status.allocatable.memory}' 2>/dev/null | head -1 || echo "0")
        
        if [ "$total_cpu" != "0" ] && [ "$total_memory" != "0" ]; then
            log "INFO" "Available cluster resources:"
            log "INFO" "  - Total CPU: $total_cpu"
            log "INFO" "  - Total Memory: $total_memory"
        else
            warning "Unable to calculate exact resource availability"
        fi
    else
        log "INFO" "Install 'bc' for detailed resource calculations"
    fi
    
    # Check for sufficient disk space (very basic check)
    local available_disk=$(df -h . | tail -1 | awk '{print $4}' || echo "unknown")
    log "INFO" "Available disk space in current directory: $available_disk"
    
    return 0
}

# Validate Docker images accessibility (if Docker is available)
validate_images() {
    log "INFO" "=== Validating Docker Images ==="
    
    if ! command_exists docker; then
        log "INFO" "Docker not available, skipping image validation"
        return 0
    fi
    
    # Source configuration to get image names
    source deployment.config 2>/dev/null || return 1
    
    local images=("$TRADES_IMAGE" "$CANDLES_IMAGE" "$TECHNICAL_INDICATORS_IMAGE" "$STRUCTURIZR_IMAGE")
    
    for image in "${images[@]}"; do
        log "INFO" "Checking image: $image"
        # Note: This doesn't actually pull the image, just checks if Docker can resolve it
        # In a production environment, you might want to actually test pulls
        if docker manifest inspect "$image" >/dev/null 2>&1; then
            log "SUCCESS" "Image accessible: $image"
        else
            warning "Image may not be accessible or requires authentication: $image"
        fi
    done
    
    return 0
}

# Check Grafana dashboards
validate_dashboards() {
    log "INFO" "=== Validating Grafana Dashboards ==="
    
    local dashboard_dir="../../dashboards/grafana"
    if [ -d "$dashboard_dir" ]; then
        local dashboard_count=$(find "$dashboard_dir" -name "*.json" | wc -l | tr -d ' ')
        if [ "$dashboard_count" -gt 0 ]; then
            log "SUCCESS" "Found $dashboard_count Grafana dashboard(s)"
            find "$dashboard_dir" -name "*.json" | while read -r dashboard; do
                log "INFO" "  - $(basename "$dashboard")"
            done
        else
            warning "No Grafana dashboard JSON files found in $dashboard_dir"
        fi
    else
        warning "Grafana dashboards directory not found: $dashboard_dir"
    fi
    
    # Test dashboard generation script
    if [ -f "generate_grafana_dashboards.py" ]; then
        log "INFO" "Testing dashboard generation..."
        if python3 generate_grafana_dashboards.py --help >/dev/null 2>&1 || python3 -c "exec(open('generate_grafana_dashboards.py').read())" >/dev/null 2>&1; then
            log "SUCCESS" "Dashboard generation script can be executed"
        else
            warning "Dashboard generation script may have issues"
        fi
    fi
    
    return 0
}

# Generate validation report
generate_report() {
    log "INFO" "=== Validation Report ==="
    
    if [ $VALIDATION_ERRORS -eq 0 ] && [ $VALIDATION_WARNINGS -eq 0 ]; then
        log "SUCCESS" "✅ All validations passed! Ready for deployment."
        log "INFO" "You can now run: make create-cluster"
        return 0
    elif [ $VALIDATION_ERRORS -eq 0 ]; then
        log "WARN" "⚠️  Validation completed with $VALIDATION_WARNINGS warning(s)."
        log "INFO" "Deployment should work, but please review warnings above."
        log "INFO" "You can proceed with: make create-cluster"
        return 0
    else
        log "ERROR" "❌ Validation failed with $VALIDATION_ERRORS error(s) and $VALIDATION_WARNINGS warning(s)."
        log "ERROR" "Please fix the errors above before attempting deployment."
        return 1
    fi
}

# Main validation function
main() {
    log "INFO" "=== Starting Pre-Deployment Validation ==="
    log "INFO" "This script will validate all prerequisites for successful deployment"
    
    # Run all validation checks
    check_prerequisites || true
    check_files_and_directories || true
    validate_configuration || true
    validate_cluster || true
    check_resource_requirements || true
    validate_images || true
    validate_dashboards || true
    
    # Generate final report
    generate_report
}

# Handle script interruption
trap 'log "ERROR" "Validation interrupted"; exit 1' INT TERM

# Run main function
main "$@" 