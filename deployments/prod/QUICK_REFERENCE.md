# 🚀 Quick Reference - Production Deployment Commands

## **New Parameter-Based Approach**

### **📦 Full Deployment**
```bash
make prod-deploy                    # Complete system deployment
```

### **🏗️ Infrastructure Components**
```bash
make prod-deploy infra=risingwave   # Streaming database (PostgreSQL + MinIO)
make prod-deploy infra=mlflow       # ML experiment tracking
make prod-deploy infra=grafana      # Monitoring + dashboards
make prod-deploy infra=all          # All infrastructure components
```

### **🔧 Application Services**
```bash
make prod-deploy service=kafka                # Kafka cluster + UI
make prod-deploy service=trades               # Trade data processing
make prod-deploy service=candles              # OHLCV candle generation  
make prod-deploy service=technical-indicators # Technical analysis
make prod-deploy service=structurizr          # Architecture documentation
make prod-deploy service=all                  # All application services
```

## **🔍 Validation & Monitoring**
```bash
make prod-check-prereqs             # Verify prerequisites
make prod-validate-cluster          # Validate cluster connectivity
make prod-validate-deployment       # Health check after deployment
make prod-health                    # Quick health status
make prod-status                    # Detailed deployment status
make prod-logs                      # View service logs
make prod-get-endpoints             # Get service URLs
```

## **🧹 Maintenance**
```bash
make prod-cleanup                   # Remove entire deployment
make prod-reset                     # Cleanup + redeploy
make prod-clean                     # Clean temporary files
make prod-generate-dashboards       # Regenerate Grafana dashboards
```

## **📋 Common Workflows**

### **New Cluster Setup**
```bash
make prod-check-prereqs && make prod-deploy && make prod-get-endpoints
```

### **Infrastructure First**
```bash
make prod-deploy infra=risingwave
make prod-deploy infra=mlflow
make prod-deploy infra=grafana
```

### **Services Rollout**
```bash
make prod-deploy service=kafka
make prod-deploy service=trades
make prod-deploy service=candles
make prod-deploy service=technical-indicators
```

### **Update Specific Component**
```bash
make prod-deploy service=trades     # Update trades service
make prod-deploy infra=grafana      # Update Grafana
make prod-health                    # Verify health
```

## **⚡ Quick Examples**

| What you want to do | Command |
|---------------------|---------|
| Deploy everything | `make prod-deploy` |
| Just the database | `make prod-deploy infra=risingwave` |
| Just Kafka | `make prod-deploy service=kafka` |
| Just one service | `make prod-deploy service=trades` |
| All infrastructure | `make prod-deploy infra=all` |
| All services | `make prod-deploy service=all` |
| Check if healthy | `make prod-health` |
| Get service URLs | `make prod-get-endpoints` |
| Clean everything | `make prod-cleanup` |

## **🆘 Troubleshooting**

```bash
# If something's wrong
make prod-health                    # Quick status check
make prod-logs                      # View recent logs
make prod-status                    # Detailed status

# If you need to start over
make prod-cleanup                   # Remove everything
make prod-deploy                    # Redeploy

# Get help
make help                           # Show all available commands
```

---

**💡 Pro Tip**: All commands run from the project root directory!

**📚 For detailed guides**: See `NEW_CLUSTER_DEPLOYMENT_CHECKLIST.md` and `README.md` 