# Infrastructure Deployment - Industry Best Practices

## 🏗️ **Robust Infrastructure Deployment**

This project follows **industry best practices** for infrastructure deployment with automated table creation and dynamic service discovery.

### **Architecture Overview**

```
┌─────────────────────────────────────────────────────────────────┐
│                   Infrastructure Deployment                     │
├─────────────────────────────────────────────────────────────────┤
│  1. deploy_infrastructure.sh (Industry Standard Script)        │
│  2. Dynamic Service Discovery                                  │
│  3. Automated Table Creation                                   │
│  4. Post-Install Verification                                  │
└─────────────────────────────────────────────────────────────────┘
```

### **Deployment Options**

| Command | Description | Components |
|---------|-------------|------------|
| `make prod-deploy infra=true` | Full infrastructure | Kafka + RisingWave + MLflow + Grafana |
| `make prod-deploy infra=risingwave` | RisingWave focused | Kafka + RisingWave + Tables |
| `./deploy_infrastructure.sh` | Direct script execution | Full infrastructure |

### **Key Features** ✨

#### **1. Dynamic Bootstrap Server Discovery**
```bash
# Automatically discovers Kafka service
KAFKA_SERVICE=$(kubectl get svc -n kafka --no-headers | grep kafka-bootstrap | head -1 | awk '{print $1}')
KAFKA_BOOTSTRAP_SERVER="${KAFKA_SERVICE}.kafka.svc.cluster.local:9092"
```

#### **2. Automated Table Creation**
- ✅ **Post-install Job**: Runs after RisingWave deployment
- ✅ **Dynamic Configuration**: Uses discovered Kafka bootstrap server
- ✅ **Verification**: Ensures table creation success
- ✅ **RBAC**: Proper service accounts and permissions

#### **3. Industry Standard Components**
```yaml
# RBAC for Service Discovery
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: risingwave-post-install
rules:
- apiGroups: [""]
  resources: ["services"]
  verbs: ["get", "list"]
```

### **Usage Examples**

#### **Full Infrastructure Deployment**
```bash
# Deploy everything with automated table creation
make prod-deploy infra=true

# Verify deployment
make prod-access
```

#### **RisingWave-Focused Deployment**
```bash
# Deploy RisingWave with dependencies and table setup
make prod-deploy infra=risingwave

# Check table creation
kubectl logs -n risingwave job/risingwave-post-install
```

#### **Direct Script Usage**
```bash
cd deployments/prod
./deploy_infrastructure.sh
```

### **Table Creation Process** 📊

The automated table creation follows this robust workflow:

1. **Wait for RisingWave**: Ensures database is ready
2. **Service Discovery**: Dynamically finds Kafka bootstrap server
3. **Table Creation**: Creates `technical_indicators` table with correct Kafka connection
4. **Verification**: Confirms table exists and is accessible
5. **Logging**: Provides detailed logs for troubleshooting

### **Technical Indicators Table Schema**

```sql
CREATE TABLE IF NOT EXISTS technical_indicators (
    pair VARCHAR,                    -- Trading pair (e.g., 'BTC/EUR')
    open DOUBLE PRECISION,           -- Opening price
    high DOUBLE PRECISION,           -- Highest price
    low DOUBLE PRECISION,            -- Lowest price
    close DOUBLE PRECISION,          -- Closing price
    volume DOUBLE PRECISION,         -- Trading volume
    window_start_ms BIGINT,          -- Window start timestamp
    window_end_ms BIGINT,            -- Window end timestamp
    window_in_sec INTEGER,           -- Window duration
    -- Technical Indicators (7, 14, 21, 60 periods)
    sma_7 DOUBLE PRECISION,          -- Simple Moving Average
    ema_7 DOUBLE PRECISION,          -- Exponential Moving Average
    rsi_7 DOUBLE PRECISION,          -- Relative Strength Index
    adx_7 DOUBLE PRECISION,          -- Average Directional Index
    macd_7 DOUBLE PRECISION,         -- MACD Line
    macdsignal_7 DOUBLE PRECISION,   -- MACD Signal Line
    macdhist_7 DOUBLE PRECISION,     -- MACD Histogram
    -- ... (similar for 14, 21, 60 periods)
    obv DOUBLE PRECISION,            -- On-Balance Volume
    created_at TIMESTAMPTZ,          -- Creation timestamp
    PRIMARY KEY (pair, window_start_ms, window_end_ms)
) WITH (
    connector='kafka',
    topic='technical-indicators',
    properties.bootstrap.server='<DYNAMICALLY_DISCOVERED>'
) FORMAT PLAIN ENCODE JSON;
```

### **Monitoring & Verification** 🔍

#### **Check Infrastructure Status**
```bash
# View all services
make prod-access

# Check specific components
kubectl get all -n kafka
kubectl get all -n risingwave
kubectl get all -n mlflow
kubectl get all -n grafana
```

#### **Verify Table Creation**
```bash
# Check job status
kubectl get jobs -n risingwave

# View job logs
kubectl logs -n risingwave job/risingwave-post-install

# Test SQL connection
kubectl port-forward -n risingwave svc/risingwave 4567:4567 &
psql -h localhost -p 4567 -d dev -U root -c "SELECT COUNT(*) FROM technical_indicators;"
```

### **Troubleshooting** 🔧

#### **Common Issues**

| Issue | Solution |
|-------|----------|
| Job fails to find Kafka | Ensure Kafka is deployed in `kafka` namespace |
| Table creation timeout | Check RisingWave pod logs for errors |
| Permission denied | Verify RBAC configuration is applied |
| Wrong bootstrap server | Check Kafka service name in `kafka` namespace |

#### **Debug Commands**
```bash
# Check Kafka services
kubectl get svc -n kafka

# Check RisingWave readiness
kubectl get pods -n risingwave

# View detailed job logs
kubectl describe job risingwave-post-install -n risingwave

# Manual table verification
kubectl exec -n risingwave <risingwave-pod> -- psql -h risingwave -p 4567 -d dev -U root -c "\dt"
```

### **Benefits** 🚀

✅ **Zero Manual Configuration**: Fully automated setup  
✅ **Environment Agnostic**: Works across different clusters  
✅ **Failure Resilient**: Proper error handling and verification  
✅ **Industry Standard**: Follows Kubernetes best practices  
✅ **Scalable**: Easy to extend for additional tables/services  
✅ **Observable**: Comprehensive logging and monitoring  

### **Next Steps**

After successful infrastructure deployment:

1. **Deploy Services**: `make prod-deploy services=true`
2. **Monitor Data Flow**: Check Kafka UI and Grafana dashboards
3. **Verify Pipeline**: Ensure trades → candles → technical indicators flow
4. **Access Dashboards**: Use the URLs from `make prod-access`

This robust implementation ensures your crypto prediction system has a solid, industry-standard foundation! 🎯 