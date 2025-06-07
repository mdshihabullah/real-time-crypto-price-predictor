# 🚀 New Cluster Deployment Checklist

**Complete guide for deploying the Real-time Crypto Price Predictor to a brand new DigitalOcean Kubernetes cluster**

## ✅ Pre-Deployment Checklist

### 1. **Prerequisites Verification**

```bash
# Run this to check everything automatically
make prod-check-prereqs
```

**Manual Verification:**
- [ ] **kubectl** installed and working (`kubectl version --client`)
- [ ] **Helm 3.x** installed (`helm version`)
- [ ] **Python 3** with **PyYAML** (`python3 -c "import yaml"`)
- [ ] **envsubst** available (for variable substitution)
- [ ] **DigitalOcean CLI** (optional but helpful: `doctl version`)

### 2. **Cluster Preparation**

- [ ] **New DigitalOcean Kubernetes cluster** is created and ready
- [ ] **Kubeconfig downloaded** and saved as `do-k8s-kubeconfig.yaml`
- [ ] **Cluster has sufficient resources** (minimum 2×2vCPU nodes)
- [ ] **LoadBalancer support** is available (standard on DigitalOcean)
- [ ] **Block storage** is available (`do-block-storage` StorageClass)

**Validate cluster connectivity:**
```bash
make prod-validate-cluster
```

### 3. **Configuration Setup**

- [ ] **deployment.config** file exists and is properly configured
- [ ] **All required environment variables** are set (see configuration section)
- [ ] **Image references** are valid and accessible
- [ ] **Passwords changed** from defaults (security!)

**Validate configuration:**
```bash
./pre_deployment_check.sh
```

### 4. **Required Files & Directory Structure**

```
deployments/prod/
├── ✅ Makefile                          # New Makefile commands
├── ✅ deployment.config                 # Configuration variables
├── ✅ do-k8s-kubeconfig.yaml           # Your cluster's kubeconfig
├── ✅ create-do-k8s-cluster.sh         # Main deployment script
├── ✅ deploy_infrastructure.sh         # Infrastructure deployment
├── ✅ generate_grafana_dashboards.py   # Dashboard generation
├── ✅ pre_deployment_check.sh          # Validation script
├── ✅ manifests/
│   ├── ✅ infrastructure/              # RisingWave, MLflow, Grafana
│   ├── ✅ services/                    # Application services
│   ├── ✅ structurizr/                 # Architecture docs
│   ├── ✅ kafka-and-topics.yaml       # Kafka cluster config
│   └── ✅ kafka-ui.yaml               # Kafka UI
└── ✅ ../../dashboards/grafana/        # Dashboard JSON files
```

## 🚀 Deployment Process

### **Option A: Full Automated Deployment (Recommended)**

```bash
# 1. Comprehensive validation
make prod-check-prereqs

# 2. Deploy everything
make prod-deploy

# 3. Get service endpoints
make prod-get-endpoints
```

### **Option B: Step-by-Step Deployment**

```bash
# Step 1: Validate everything
./pre_deployment_check.sh

# Step 2: Infrastructure only
make prod-deploy infra=all

# Step 3: Services only  
make prod-deploy service=all

# Step 4: Verify deployment
make prod-validate-deployment
```

### **Option C: Original Scripts (Fallback)**

```bash
# Make executable
chmod +x *.sh

# Validate first
./pre_deployment_check.sh

# Deploy everything
./create-do-k8s-cluster.sh
```

## 🔍 Validation & Verification

### **Immediate Checks (< 5 minutes)**

```bash
# Quick health check
make prod-health

# Check pod status
kubectl get pods -A

# Check services
kubectl get svc -A | grep LoadBalancer
```

### **Complete Validation (10-15 minutes)**

```bash
# Full deployment validation
make prod-validate-deployment

# Get all endpoints
make prod-get-endpoints

# Check logs for errors
make prod-logs
```

### **Expected Deployment State**

**Namespaces:**
- [ ] `kafka` - Kafka cluster + UI
- [ ] `services` - Application services (trades, candles, technical-indicators)
- [ ] `structurizr` - Architecture documentation
- [ ] `risingwave` - Streaming database + storage
- [ ] `mlflow` - ML experiment tracking
- [ ] `grafana` - Monitoring + dashboards

**Running Pods (~15-20 total):**
```bash
kubectl get pods -A | grep -E "(Running|Ready)"
```

**External Services (LoadBalancer IPs):**
- [ ] **Grafana**: `http://<IP>` (admin/your-password)
- [ ] **MLflow**: `http://<IP>`
- [ ] **Kafka UI**: `http://<IP>`
- [ ] **Structurizr**: `http://<IP>`
- [ ] **RisingWave SQL**: `<IP>:4567`

## 🛠️ Troubleshooting Guide

### **Issue 1: Prerequisites Missing**

**Symptoms:** `make prod-check-prereqs` fails
**Solution:**
```bash
# Install missing tools
# MacOS
brew install kubectl helm python3

# Ubuntu/Debian
sudo apt update && sudo apt install kubectl python3-pip
curl https://get.helm.sh/helm-v3.12.0-linux-amd64.tar.gz | tar xz
sudo mv linux-amd64/helm /usr/local/bin/

# Install PyYAML
pip3 install pyyaml
```

### **Issue 2: Cluster Connection Failed**

**Symptoms:** `make prod-validate-cluster` fails
**Solution:**
1. **Check kubeconfig file**: Ensure `do-k8s-kubeconfig.yaml` is valid
2. **Test manually**: `kubectl --kubeconfig=do-k8s-kubeconfig.yaml get nodes`
3. **Download fresh kubeconfig** from DigitalOcean console
4. **Check cluster status** in DigitalOcean dashboard

### **Issue 3: Resource Constraints**

**Symptoms:** Pods stuck in `Pending` state
**Solution:**
```bash
# Check available resources
kubectl describe nodes

# Check resource requests
kubectl describe pod <pending-pod> -n <namespace>

# Scale down if needed (edit values files)
# Or upgrade cluster to more nodes/bigger nodes
```

### **Issue 4: LoadBalancer IPs Pending**

**Symptoms:** Services show `<pending>` external IPs
**Solution:**
```bash
# Wait 5-10 minutes (DigitalOcean LoadBalancers take time)
watch kubectl get svc -A | grep LoadBalancer

# Check DigitalOcean LoadBalancer quota/limits
# Use port-forwarding as alternative:
kubectl port-forward -n grafana svc/grafana 3000:80
```

### **Issue 5: Image Pull Errors**

**Symptoms:** Pods with `ImagePullBackOff`
**Solution:**
1. **Check image exists**: `docker manifest inspect <image-name>`
2. **Verify image tags** in `deployment.config`
3. **Check registry credentials** if using private registry
4. **Update to latest working images**

### **Issue 6: Database Connection Issues**

**Symptoms:** Services can't connect to databases
**Solution:**
```bash
# Check PostgreSQL pod
kubectl get pods -n risingwave -l app.kubernetes.io/name=postgresql

# Check if databases were created
kubectl logs -n risingwave deployment/risingwave-meta

# Manual database check
kubectl exec -n risingwave <postgres-pod> -- psql -U postgres -l
```

### **Issue 7: Kafka Services Failing**

**Symptoms:** Technical indicators in `CrashLoopBackOff`
**Solution:**
```bash
# Check Kafka cluster status
kubectl get kafka -n kafka

# Wait for Kafka to be ready
kubectl wait --for=condition=Ready kafka/crypto-kafka-cluster -n kafka --timeout=600s

# Check topic creation
kubectl exec -n kafka <kafka-pod> -- kafka-topics.sh --bootstrap-server localhost:9092 --list
```

## 🔧 Post-Deployment Configuration

### **1. Access Grafana Dashboards**

```bash
# Get Grafana IP
GRAFANA_IP=$(kubectl get svc -n grafana grafana -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "Grafana: http://$GRAFANA_IP (admin/$(grep GRAFANA_ADMIN_PASSWORD deployment.config | cut -d'=' -f2))"
```

**Expected Dashboards:**
- [ ] **Crypto Currency Price** - Real-time candlestick charts
- [ ] **Technical Indicators** - SMA, EMA, RSI, MACD, OBV

### **2. Verify Data Flow**

```bash
# Connect to RisingWave SQL interface
kubectl port-forward -n risingwave svc/risingwave-frontend 4567:4567

# Check tables (in another terminal)
psql -h localhost -p 4567 -d dev -U root -c "\dt"
psql -h localhost -p 4567 -d dev -U root -c "SELECT * FROM trades LIMIT 5;"
```

### **3. MLflow Setup**

```bash
# Get MLflow IP
MLFLOW_IP=$(kubectl get svc -n mlflow mlflow -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "MLflow: http://$MLFLOW_IP"
```

## 🎯 Success Criteria

### **✅ Deployment is successful when:**

1. **All pods are Running** (`kubectl get pods -A`)
2. **All LoadBalancer services have external IPs** (`kubectl get svc -A | grep LoadBalancer`)
3. **Grafana accessible** with pre-loaded dashboards
4. **RisingWave SQL interface** accessible
5. **Data flowing** through services (trades → candles → technical indicators)
6. **No CrashLoopBackOff** or persistent errors

### **📊 Health Check Commands:**

```bash
# Overall health
make prod-health

# Resource usage
kubectl top nodes && kubectl top pods -A

# Service endpoints
make prod-get-endpoints

# Recent logs
make prod-logs
```

## 🔄 Cleanup & Reset

### **Full Cleanup:**
```bash
make prod-cleanup  # Interactive confirmation
```

### **Reset & Redeploy:**
```bash
make prod-reset    # Cleanup + redeploy
```

### **Partial Cleanup:**
```bash
# Remove specific namespace
kubectl delete namespace services

# Clean temp files only
make prod-clean
```

## 📋 Quick Reference Commands

```bash
# === DEPLOYMENT ===
make prod-check-prereqs      # Validate prerequisites
make prod-validate-cluster   # Validate cluster
make prod-deploy             # Full deployment
make prod-get-endpoints      # Get service IPs

# === MONITORING ===
make prod-status            # Deployment status
make prod-health            # Quick health check
make prod-logs              # View recent logs
make prod-validate-deployment  # Full validation

# === MAINTENANCE ===
make prod-cleanup           # Remove everything
make prod-reset             # Cleanup + redeploy
make prod-clean             # Clean temp files

# === INDIVIDUAL COMPONENTS ===
make prod-deploy infra=risingwave     # RisingWave only
make prod-deploy infra=all           # All infrastructure
make prod-deploy service=trades      # Trades service only
make prod-deploy service=all         # All services
make prod-generate-dashboards    # Grafana dashboards
```

## 🎯 Final Notes

### **✅ This deployment should work if:**
1. You have a valid DigitalOcean Kubernetes cluster (2+ nodes, 2vCPU each minimum)
2. Your kubeconfig is saved as `do-k8s-kubeconfig.yaml`
3. All prerequisite tools are installed
4. The `deployment.config` file has valid configuration

### **🚨 Common Gotchas:**
- **Wait for LoadBalancers**: DigitalOcean LBs take 2-5 minutes to provision
- **Resource constraints**: Monitor `kubectl top nodes` for resource usage
- **Order matters**: Infrastructure must deploy before services
- **Kafka readiness**: Services depend on Kafka being fully ready

### **🆘 If all else fails:**
1. Run `./pre_deployment_check.sh` for detailed validation
2. Check `make prod-logs` for error details
3. Verify cluster resources with `kubectl describe nodes`
4. Try deploying components individually (infrastructure first, then services)

**This comprehensive deployment process should successfully recreate your entire crypto price prediction system on any new DigitalOcean Kubernetes cluster! 🚀** 