#!/bin/bash
# Deployment Validation Script
# This script validates that all components are deployed and working correctly

set -euo pipefail

# Color codes
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
        "SUCCESS")
            echo -e "${GREEN}[SUCCESS]${NC} ${timestamp} - $message"
            ;;
        *)
            echo -e "${timestamp} - $message"
            ;;
    esac
}

# Function to check if namespace exists and has resources
check_namespace() {
    local namespace=$1
    local description="${2:-}"
    
    log "INFO" "Checking namespace: $namespace"
    
    if ! kubectl get namespace "$namespace" &>/dev/null; then
        log "ERROR" "Namespace $namespace not found"
        return 1
    fi
    
    local pod_count=$(kubectl get pods -n "$namespace" --no-headers 2>/dev/null | wc -l | tr -d ' ')
    local running_pods=$(kubectl get pods -n "$namespace" --no-headers 2>/dev/null | grep -c "Running" || echo "0")
    
    if [ "$pod_count" -eq 0 ]; then
        log "WARN" "No pods found in namespace $namespace"
        return 1
    fi
    
    log "INFO" "  Pods: $running_pods/$pod_count running"
    
    if [ "$running_pods" -eq "$pod_count" ]; then
        log "SUCCESS" "All pods in $namespace are running"
        return 0
    else
        log "WARN" "Some pods in $namespace are not running"
        kubectl get pods -n "$namespace" | grep -v "Running" || true
        return 1
    fi
}

# Function to check service endpoints
check_service_endpoints() {
    log "INFO" "Checking service endpoints..."
    
    # Check LoadBalancer services
    local lb_services=$(kubectl get svc -A --no-headers | grep LoadBalancer | wc -l | tr -d ' ')
    log "INFO" "Found $lb_services LoadBalancer services"
    
    # List all LoadBalancer services with their IPs
    kubectl get svc -A | grep LoadBalancer | while read -r namespace name type cluster_ip external_ip ports age; do
        if [ "$external_ip" = "<pending>" ]; then
            log "WARN" "Service $namespace/$name has pending external IP"
        else
            log "SUCCESS" "Service $namespace/$name has external IP: $external_ip"
        fi
    done
}

# Function to test RisingWave connectivity
test_risingwave() {
    log "INFO" "Testing RisingWave connectivity..."
    
    local rw_pod=$(kubectl get pods -n risingwave -l "risingwave/component=frontend" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [ -z "$rw_pod" ]; then
        log "ERROR" "RisingWave frontend pod not found"
        return 1
    fi
    
    # Test SQL connectivity
    if kubectl exec -n risingwave "$rw_pod" -- psql -h localhost -p 4567 -d dev -U root -c "SELECT 'RisingWave is working!' as status;" &>/dev/null; then
        log "SUCCESS" "RisingWave SQL interface is working"
        return 0
    else
        log "ERROR" "RisingWave SQL interface is not responding"
        return 1
    fi
}

# Function to check Grafana dashboards
check_grafana_dashboards() {
    log "INFO" "Checking Grafana dashboards..."
    
    local dashboard_count=$(kubectl get configmaps -n grafana -l "grafana_dashboard=1" --no-headers 2>/dev/null | wc -l | tr -d ' ')
    
    if [ "$dashboard_count" -gt 0 ]; then
        log "SUCCESS" "Found $dashboard_count Grafana dashboard ConfigMaps"
        kubectl get configmaps -n grafana -l "grafana_dashboard=1" --no-headers | while read -r name rest; do
            log "INFO" "  Dashboard ConfigMap: $name"
        done
        return 0
    else
        log "WARN" "No Grafana dashboard ConfigMaps found"
        return 1
    fi
}

# Function to check Kafka cluster
check_kafka() {
    log "INFO" "Checking Kafka cluster..."
    
    local kafka_pods=$(kubectl get pods -n kafka -l "app.kubernetes.io/name=kafka" --no-headers 2>/dev/null | wc -l | tr -d ' ')
    local kafka_running=$(kubectl get pods -n kafka -l "app.kubernetes.io/name=kafka" --no-headers 2>/dev/null | grep -c "Running" || echo "0")
    
    if [ "$kafka_pods" -gt 0 ] && [ "$kafka_running" -eq "$kafka_pods" ]; then
        log "SUCCESS" "Kafka cluster is running ($kafka_running/$kafka_pods pods)"
        return 0
    else
        log "ERROR" "Kafka cluster issues detected ($kafka_running/$kafka_pods pods running)"
        return 1
    fi
}

# Function to check application services
check_application_services() {
    log "INFO" "Checking application services..."
    
    local services=("trades" "candles" "technical-indicators")
    local all_healthy=true
    
    for service in "${services[@]}"; do
        local pod_count=$(kubectl get pods -n services -l "app=$service" --no-headers 2>/dev/null | wc -l | tr -d ' ')
        local running_count=$(kubectl get pods -n services -l "app=$service" --no-headers 2>/dev/null | grep -c "Running" || echo "0")
        
        if [ "$pod_count" -gt 0 ] && [ "$running_count" -eq "$pod_count" ]; then
            log "SUCCESS" "Service $service is healthy ($running_count/$pod_count pods)"
        else
            log "ERROR" "Service $service has issues ($running_count/$pod_count pods running)"
            all_healthy=false
        fi
    done
    
    if [ "$all_healthy" = true ]; then
        return 0
    else
        return 1
    fi
}

# Function to display summary
display_summary() {
    log "INFO" "=== Deployment Validation Summary ==="
    
    # Count total pods
    local total_pods=$(kubectl get pods -A --no-headers 2>/dev/null | wc -l | tr -d ' ')
    local running_pods=$(kubectl get pods -A --no-headers 2>/dev/null | grep -c "Running" || echo "0")
    local pending_pods=$(kubectl get pods -A --no-headers 2>/dev/null | grep -c "Pending" || echo "0")
    local failed_pods=$(kubectl get pods -A --no-headers 2>/dev/null | grep -E "(Error|CrashLoopBackOff|ImagePullBackOff)" | wc -l | tr -d ' ')
    
    log "INFO" "Total Pods: $total_pods"
    log "INFO" "  Running: $running_pods"
    log "INFO" "  Pending: $pending_pods"
    log "INFO" "  Failed: $failed_pods"
    
    # Count services
    local total_services=$(kubectl get svc -A --no-headers 2>/dev/null | wc -l | tr -d ' ')
    local lb_services=$(kubectl get svc -A --no-headers 2>/dev/null | grep -c "LoadBalancer" || echo "0")
    
    log "INFO" "Total Services: $total_services"
    log "INFO" "  LoadBalancer: $lb_services"
    
    # Show resource usage
    log "INFO" "Node Resource Usage:"
    kubectl top nodes 2>/dev/null || log "WARN" "Metrics server not available"
}

# Main validation function
main() {
    log "INFO" "=== Starting Deployment Validation ==="
    
    # Set KUBECONFIG if not already set
    if [ -z "${KUBECONFIG:-}" ] && [ -f "do-k8s-kubeconfig.yaml" ]; then
        export KUBECONFIG=$(pwd)/do-k8s-kubeconfig.yaml
        log "INFO" "Set KUBECONFIG to: $KUBECONFIG"
    fi
    
    # Check if kubectl is working
    if ! kubectl cluster-info &>/dev/null; then
        log "ERROR" "kubectl is not configured or cluster is not accessible"
        log "INFO" "Current KUBECONFIG: ${KUBECONFIG:-default}"
        log "INFO" "Please ensure your kubeconfig is correct and cluster is reachable"
        exit 1
    fi
    
    log "INFO" "Kubernetes cluster is accessible"
    log "INFO" "Current context: $(kubectl config current-context)"
    
    local validation_passed=true
    
    # Check all namespaces
    local namespaces=("kafka" "services" "structurizr" "risingwave" "mlflow" "grafana")
    
    for namespace in "${namespaces[@]}"; do
        if ! check_namespace "$namespace"; then
            validation_passed=false
        fi
    done
    
    # Check service endpoints
    check_service_endpoints
    
    # Test specific components
    if ! test_risingwave; then
        validation_passed=false
    fi
    
    if ! check_grafana_dashboards; then
        validation_passed=false
    fi
    
    if ! check_kafka; then
        validation_passed=false
    fi
    
    if ! check_application_services; then
        validation_passed=false
    fi
    
    # Display summary
    display_summary
    
    # Final result
    if [ "$validation_passed" = true ]; then
        log "SUCCESS" "=== Deployment validation PASSED ==="
        log "INFO" "All components are deployed and healthy"
        
        # Show access information
        log "INFO" "\n=== Access Information ==="
        log "INFO" "Get LoadBalancer IPs: kubectl get svc -A | grep LoadBalancer"
        log "INFO" "Port forward Grafana: kubectl port-forward -n grafana svc/grafana 3000:80"
        log "INFO" "Port forward MLflow: kubectl port-forward -n mlflow svc/mlflow 5000:5000"
        log "INFO" "Port forward Kafka UI: kubectl port-forward -n kafka svc/kafka-ui 8080:80"
        
        exit 0
    else
        log "ERROR" "=== Deployment validation FAILED ==="
        log "ERROR" "Some components have issues - check the logs above"
        
        # Show troubleshooting commands
        log "INFO" "\n=== Troubleshooting Commands ==="
        log "INFO" "Check pod status: kubectl get pods -A | grep -v Running"
        log "INFO" "Check events: kubectl get events -A --sort-by='.lastTimestamp'"
        log "INFO" "Check logs: kubectl logs -n <namespace> <pod-name>"
        
        exit 1
    fi
}

# Run main function
main "$@" 