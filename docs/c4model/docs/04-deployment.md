# Deployment

The Crypto Price Prediction System is deployed on Kubernetes, providing a scalable, resilient, and manageable infrastructure.

![Kubernetes Deployment](images/14.png)

## Deployment Architecture

The system is deployed as a collection of Kubernetes resources:

- **Deployments**: For stateless services (Sentiment Extractor, Trade to OHLC, etc.)
- **StatefulSets**: For stateful components (Kafka, RisingWave, Elasticsearch)
- **Services**: For internal communication and load balancing
- **ConfigMaps**: For service configuration
- **Secrets**: For sensitive information (API keys, credentials)

## Service Deployment

Each of the seven microservices is deployed as a Kubernetes Deployment with:

- Appropriate resource requests and limits
- Health checks (liveness and readiness probes)
- Horizontal Pod Autoscaler for scaling
- Proper service account and RBAC permissions

## Data Infrastructure

### Kafka

Kafka is deployed using the Strimzi operator, which provides:
- Automated broker deployment
- Topic management via CRDs
- Monitoring integration
- Automatic scaling
- Rolling updates

### RisingWave

RisingWave is deployed as a StatefulSet with:
- Persistent storage for feature data
- High availability configuration
- Backup and restore capabilities
- Proper resource allocation

### MLflow

MLflow is deployed with:
- A PostgreSQL backend for metadata
- S3-compatible storage for model artifacts
- Web UI exposed through an Ingress

### Elasticsearch

Elasticsearch is deployed as a cluster with:
- Data nodes for storage
- Client nodes for queries
- Master nodes for cluster management
- Index lifecycle management

## Observability

The deployment includes comprehensive observability:

- **Prometheus**: For metrics collection
- **Grafana**: For visualization and dashboards
- **Loki**: For log aggregation
- **Tempo**: For distributed tracing
- **Alertmanager**: For alerting

## Resource Requirements

The system's components have these approximate resource requirements:

| Component | CPU (requests/limits) | Memory (requests/limits) | Storage |
|-----------|------------------------|--------------------------|---------|
| Sentiment Extractor | 1000m/2000m | 2Gi/4Gi | - |
| Trade to OHLC | 500m/1000m | 1Gi/2Gi | - |
| Technical Indicators | 500m/1000m | 1Gi/2Gi | - |
| Model Trainer | 2000m/4000m | 4Gi/8Gi | - |
| Price Predictor | 1000m/2000m | 2Gi/4Gi | - |
| Predictions API | 500m/1000m | 1Gi/2Gi | - |
| Model Error Monitor | 500m/1000m | 1Gi/2Gi | - |
| Kafka | 1000m/2000m | 4Gi/8Gi | 100Gi |
| RisingWave | 2000m/4000m | 8Gi/16Gi | 200Gi |
| Elasticsearch | 1000m/3000m | 4Gi/8Gi | 100Gi |
| MLflow | 500m/1000m | 1Gi/2Gi | 50Gi |

## Scaling Strategy

The system is designed to scale based on:

- Trade volume: More trades require more processing in the Trade to OHLC service
- News volume: More news requires more processing in the Sentiment Extractor
- Prediction requests: Higher API load scales the Predictions API service
- Model complexity: More complex models need more resources for the Model Trainer

Each component can scale independently based on its specific load metrics.

## Security Considerations

The deployment includes several security measures:

- Network policies to restrict communication between services
- Service accounts with minimal required permissions
- Secret management for sensitive configuration
- Container security best practices (non-root users, read-only filesystems)
- Regular security updates 