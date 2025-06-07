# Real-time Crypto Price Predictor - Production Deployment

This directory contains the production deployment scripts for the Real-time Crypto Price Predictor system on DigitalOcean Kubernetes.

## 🚀 Quick Start

### Prerequisites

1. **DigitalOcean Kubernetes Cluster**: A running DO Kubernetes cluster
2. **kubectl**: Configured to access your cluster
3. **Helm**: Version 3.x installed
4. **Python 3**: For dashboard generation (with `pyyaml` package)
5. **Kubeconfig**: Valid kubeconfig file for your cluster

### **🆕 NEW: One-Command Deployment with Root Makefile**

The easiest way to deploy is using the integrated root Makefile commands:

```bash
# 1. Check all prerequisites and validate cluster
make prod-check-prereqs

# 2. Validate cluster connectivity and resources  
make prod-validate-cluster

# 3. Deploy complete system
make prod-deploy

# 4. Get service endpoints
make prod-get-endpoints
```

### Alternative: Script-based Deployment

If you prefer the original scripts:

```bash
# Make scripts executable
chmod +x *.sh

# Validate everything is ready
./pre_deployment_check.sh

# Run the complete deployment
./create-do-k8s-cluster.sh
```

## 📋 What Gets Deployed

### Core Infrastructure
- **RisingWave**: Streaming database with PostgreSQL and MinIO
- **MLflow**: Machine learning experiment tracking
- **Grafana**: Monitoring and visualization with pre-loaded dashboards

### Application Services
- **Kafka Cluster**: Message streaming with Strimzi operator
- **Trades Service**: Real-time trade data processing
- **Candles Service**: OHLCV candle generation
- **Technical Indicators Service**: Technical analysis calculations
- **Structurizr**: Architecture documentation

### Monitoring & Visualization
- **Kafka UI**: Web interface for Kafka management
- **Grafana Dashboards**: 
  - Crypto Currency Price (candlestick charts)
  - Technical Indicators (SMA, EMA, RSI, MACD, OBV)

## 🔧 Configuration

### Environment Variables

Edit `deployment.config` to customize your deployment:

```bash
# Docker Images
TRADES_IMAGE=ghcr.io/mdshihabullah/real-time-crypto-price-predictor/trades:latest
CANDLES_IMAGE=ghcr.io/mdshihabullah/real-time-crypto-price-predictor/candles:latest
TECHNICAL_INDICATORS_IMAGE=ghcr.io/mdshihabullah/real-time-crypto-price-predictor/technical_indicators:latest
STRUCTURIZR_IMAGE=ghcr.io/mdshihabullah/real-time-crypto-price-predictor/structurizr:latest

# Kubernetes Configuration
KUBECONFIG_PATH=do-k8s-kubeconfig.yaml

# Database Passwords (change these!)
MLFLOW_DB_PASSWORD=your-secure-password
GRAFANA_DB_PASSWORD=your-secure-password
MINIO_ROOT_PASSWORD=your-secure-password
GRAFANA_ADMIN_PASSWORD=your-secure-password

# Resource Optimization
ENABLE_RESOURCE_OPTIMIZATION=true

# Future Services
DEPLOY_METABASE=false
DEPLOY_LLM_SERVICES=false
```

## 🛠️ Root Makefile Commands

### Prerequisites and Validation
```bash
make prod-check-prereqs          # Verify all prerequisites (kubectl, helm, python3, etc.)
make prod-validate-cluster       # Validate cluster connectivity and resources
make prod-validate-deployment    # Validate deployment health after deployment
```

### Deployment Commands
```bash
make prod-deploy                      # Deploy complete system to new cluster
make prod-deploy infra=<name>         # Deploy specific infrastructure (risingwave|mlflow|grafana|all)
make prod-deploy service=<name>       # Deploy specific service (trades|candles|technical-indicators|structurizr|kafka|all)
```

### Utilities
```bash
make prod-generate-dashboards    # Generate Grafana dashboard ConfigMaps
make prod-get-endpoints          # Get service endpoints and access info
make prod-status                 # Show deployment status
make prod-health                 # Quick health check
make prod-logs                   # View recent logs from all namespaces
```

### Maintenance
```bash
make prod-cleanup               # Clean up deployment (with confirmation)
make prod-reset                 # Full reset (cleanup + redeploy)
make prod-clean                 # Clean up temporary files only
```

### View All Commands
```bash
make help                       # Show all available commands with descriptions
```

## 🔍 Pre-Deployment Validation

**NEW**: Before deploying to a new cluster, run the comprehensive validation:

```bash
./pre_deployment_check.sh
```

This script validates:
- ✅ All required tools (kubectl, helm, python3, pyyaml)
- ✅ Required files and directory structure
- ✅ Configuration variables
- ✅ Cluster connectivity and resources
- ✅ Storage class availability
- ✅ Docker image accessibility (if Docker available)
- ✅ Grafana dashboard files
- ⚠️ Potential conflicts with existing deployments

## 🚀 Deployment Workflows

### For a Brand New Cluster

```bash
# 1. Save your new cluster's kubeconfig as do-k8s-kubeconfig.yaml
# 2. Update deployment.config if needed
# 3. Run validation and deployment
make prod-check-prereqs && make prod-deploy
```

### Modular Infrastructure Deployment

```bash
# Deploy all infrastructure
make prod-deploy infra=all

# Deploy specific infrastructure components
make prod-deploy infra=risingwave    # Streaming database + PostgreSQL + MinIO
make prod-deploy infra=mlflow        # ML experiment tracking
make prod-deploy infra=grafana       # Monitoring + dashboards
```

### Modular Service Deployment

```bash
# Deploy all services
make prod-deploy service=all

# Deploy specific services
make prod-deploy service=kafka                # Kafka cluster + UI
make prod-deploy service=trades               # Trades data processing
make prod-deploy service=candles              # OHLCV candle generation
make prod-deploy service=technical-indicators # Technical analysis
make prod-deploy service=structurizr          # Architecture documentation
```

### Incremental Updates & Common Scenarios

```bash
# Update specific service
make prod-deploy service=trades

# Update infrastructure component  
make prod-deploy infra=grafana

# Update all services
make prod-deploy service=all
```

### Real-World Deployment Examples

```bash
# 🚀 Full production deployment (new cluster)
make prod-deploy

# 🏗️ Infrastructure-first approach
make prod-deploy infra=risingwave    # Deploy streaming database first
make prod-deploy infra=mlflow        # Add ML tracking
make prod-deploy service=kafka       # Deploy message queue
make prod-deploy service=trades      # Start data ingestion

# 🔧 Service-by-service rollout
make prod-deploy service=kafka       # Message infrastructure
make prod-deploy service=trades      # Data ingestion
make prod-deploy service=candles     # Data transformation
make prod-deploy service=technical-indicators  # Analysis

# 📊 Monitoring setup
make prod-deploy infra=grafana       # Deploy Grafana + dashboards
make prod-get-endpoints              # Get access URLs

# 🔄 Rolling updates
make prod-deploy service=trades      # Update specific service
make prod-health                     # Verify health
```

## 📊 Resource Requirements

### Optimized for DigitalOcean 2×2vCPU Clusters

The deployment is optimized for smaller clusters:

- **CPU Requests**: ~1.5 cores total
- **Memory Requests**: ~8GB total  
- **Storage**: ~20GB persistent volumes
- **LoadBalancers**: 5 external services

### Resource Breakdown per Component

| Component | CPU Request | Memory Request | Storage |
|-----------|-------------|----------------|---------|
| RisingWave Meta | 200m | 512Mi | 5Gi |
| RisingWave Frontend | 100m | 1Gi | - |
| RisingWave Compute | 300m | 1Gi | - |
| RisingWave Compactor | 200m | 512Mi | - |
| PostgreSQL | 200m | 512Mi | 5Gi |
| MinIO | 100m | 512Mi | 5Gi |
| MLflow | 100m | 512Mi | - |
| Grafana | 50m | 256Mi | - |

## 🌐 Service Access

### External LoadBalancer Services

After deployment, services are accessible via LoadBalancer IPs:

```bash
# Get all external IPs
make prod-get-endpoints

# Or manually check
kubectl get svc -A | grep LoadBalancer
```

**Expected Services:**
- **Grafana**: `http://<EXTERNAL-IP>` (admin/your-password)
- **MLflow**: `http://<EXTERNAL-IP>`
- **Kafka UI**: `http://<EXTERNAL-IP>`
- **Structurizr**: `http://<EXTERNAL-IP>`
- **RisingWave SQL**: `<EXTERNAL-IP>:4567`

### Port Forwarding (Alternative Access)

If LoadBalancer IPs are pending:

```bash
# Grafana
kubectl port-forward -n grafana svc/grafana 3000:80

# MLflow  
kubectl port-forward -n mlflow svc/mlflow 5000:5000

# Kafka UI
kubectl port-forward -n kafka svc/kafka-ui 8080:80

# RisingWave SQL Interface
kubectl port-forward -n risingwave svc/risingwave-frontend 4567:4567

# MinIO Console
kubectl port-forward -n risingwave svc/risingwave-minio 9001:9001
```

## 🔧 Troubleshooting

### Common Issues and Solutions

#### 1. LoadBalancer IPs Stuck at `<pending>`

**Solution**: DigitalOcean LoadBalancers take 2-5 minutes to provision.

```bash
# Check status
kubectl get svc -A | grep LoadBalancer

# Wait and check again
watch kubectl get svc -A
```

#### 2. Pods in `CrashLoopBackOff`

**Solution**: Usually resource constraints or missing dependencies.

```bash
# Check pod status
make status

# View logs
kubectl logs -n <namespace> <pod-name>

# Check resource usage
kubectl top nodes
kubectl top pods -A
```

#### 3. Kafka Services Not Starting

**Solution**: Ensure Kafka cluster is ready before deploying services.

```bash
# Check Kafka cluster status
kubectl get kafka -n kafka

# Wait for Kafka to be ready
kubectl wait --for=condition=Ready kafka/crypto-kafka-cluster -n kafka --timeout=300s
```

#### 4. Database Connection Issues

**Solution**: Check if PostgreSQL is ready and databases are created.

```bash
# Check PostgreSQL pod
kubectl get pods -n risingwave -l app.kubernetes.io/name=postgresql

# Check database creation logs
kubectl logs -n risingwave deployment/risingwave-meta
```

#### 5. Image Pull Errors

**Solution**: Check image accessibility and credentials.

```bash
# Test image accessibility
docker manifest inspect <image-name>

# Check if images need authentication
kubectl get pods -o jsonpath='{.items[*].status.containerStatuses[*].state.waiting.reason}' | grep -o ImagePullBackOff
```

### Validation and Health Checks

```bash
# Full deployment validation
make validate-deployment

# Quick health check
make health

# Check logs from all namespaces  
make logs

# Check resource usage
kubectl top nodes
kubectl top pods -A
```

### Resource Optimization

If running into resource constraints:

1. **Reduce Replica Counts**: Edit values files to reduce replicas
2. **Lower Resource Requests**: Adjust CPU/memory requests in values files  
3. **Disable Auto-scaling**: Turn off autoscaling in resource-constrained environments
4. **Use NodePort Instead**: Switch LoadBalancer to NodePort services

```bash
# Example: Reduce RisingWave compute replicas
# Edit manifests/infrastructure/risingwave-values.yaml
computeComponent:
  replicaCount: 1  # Reduce from default
```

## 🧹 Cleanup

### Remove Everything

```bash
make cleanup
# Confirms before deletion
```

### Manual Cleanup

```bash
# Delete namespaces (removes everything in them)
kubectl delete namespace services kafka risingwave mlflow grafana structurizr

# Clean temporary files
make clean
```

## 🔄 Updates and Maintenance

### Update Configuration

1. Edit `deployment.config`
2. Run: `make reset` (full redeploy) or update specific components

### Update Images

1. Update image tags in `deployment.config`
2. Redeploy specific services:

```bash
# Update all services
make prod-deploy service=all

# Update specific service
make prod-deploy service=trades
```

### Add New Services

The architecture supports future expansion:

1. **Metabase**: Set `DEPLOY_METABASE=true` in config
2. **LLM Services**: Set `DEPLOY_LLM_SERVICES=true` in config
3. **Custom Services**: Add to `manifests/services/` directory

## 📈 Monitoring and Observability

### Grafana Dashboards

Pre-loaded dashboards include:
- **Crypto Currency Price**: Real-time price charts with candlesticks
- **Technical Indicators**: SMA, EMA, RSI, MACD, OBV visualizations

### System Monitoring

```bash
# Check overall system health
make health

# Monitor resource usage
kubectl top nodes
kubectl top pods -A

# View service logs
make logs
```

### Database Monitoring

```bash
# Connect to RisingWave SQL interface
kubectl port-forward -n risingwave svc/risingwave-frontend 4567:4567

# Connect with PostgreSQL client
psql -h localhost -p 4567 -d dev -U root
```

## 🔮 Future Enhancements

The deployment supports planned additions:

- **Metabase**: Business intelligence dashboards
- **LLM Services**: AI-powered analysis and predictions
- **Advanced Monitoring**: Prometheus, AlertManager
- **Service Mesh**: Istio for advanced traffic management
- **GitOps**: ArgoCD for automated deployments

---

## 📞 Support

If you encounter issues:

1. **Run validation**: `./pre_deployment_check.sh`
2. **Check health**: `make health`  
3. **View logs**: `make logs`
4. **Check resources**: `kubectl top nodes && kubectl top pods -A`

For deployment on a new cluster, ensure you:
1. ✅ Have valid kubeconfig saved as `do-k8s-kubeconfig.yaml`
2. ✅ Run `make check-prereqs` first
3. ✅ Validate cluster with `make validate-cluster`
4. ✅ Then deploy with `make create-cluster`

**The deployment scripts are designed to be fully automated and should recreate the entire system successfully on any new DigitalOcean Kubernetes cluster.**