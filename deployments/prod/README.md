# Production Deployment Guide

## Simplified Deployment

The deployment script has been improved to:

1. Read configuration from `deployments/prod/deployment.config`
2. Run without any command-line arguments
3. Process all manifest files with environment variables
4. Correctly handle the directory structure

## Deploying to DigitalOcean

To deploy to DigitalOcean, simply run:

```bash
./deployments/prod/deploy-to-digitalocean.sh
```

All configuration is read from `deployment.config`.

## Configuration File

The `deployments/prod/deployment.config` file contains:

```
TRADES_IMAGE=ghcr.io/mdshihabullah/real-time-crypto-price-predictor/trades:beta-21-04-2025-94df373
CANDLES_IMAGE=ghcr.io/mdshihabullah/real-time-crypto-price-predictor/candles:beta-21-04-2025-94df373
STRUCTURIZR_IMAGE=ghcr.io/mdshihabullah/real-time-crypto-price-predictor/structurizr:beta-22-04-2025-94df373
KUBECONFIG_PATH=k8s-rwml-fra1-13-kubeconfig.yaml
```

You can update this file to change image versions or the path to your kubeconfig file.

## Required Files

1. `k8s-rwml-fra1-13-kubeconfig.yaml` - Your DigitalOcean Kubernetes cluster kubeconfig (or as specified in deployment.config)
2. `deployments/prod/deployment.config` - Configuration for Docker images and kubeconfig

The kubeconfig file should be kept private and not committed to the repository. The .gitignore file is already configured to exclude this file.

## Manifest Structure

```
deployments/prod/manifests/
├── kafka-and-topics.yaml
├── kafka-cluster.yaml
├── services/
│   ├── candles/
│   │   └── candles.yaml
│   └── trades/
│       └── trades.yaml
└── structurizr/
    └── structurizr.yaml
```

## Accessing Services

After deployment, you can access the services via NodePorts on any cluster node IP:

- Kafka UI: `http://<node-ip>:30080`
- Trades Service: `http://<node-ip>:30800`
- Candles Service: `http://<node-ip>:30801`
- Structurizr: `http://<node-ip>:30001` 