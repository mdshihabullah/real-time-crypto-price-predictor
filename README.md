# Real-Time Crypto Price Predictor

A system for collecting and predicting cryptocurrency prices in real-time.

## Building and Deploying Services

This project follows Open Container Initiative (OCI) standards for image building and deployment.

### Local Development

Build and deploy a service to your local Kind cluster:

```
# Build a service (e.g., trades)
make build-for-dev service=trades

# Deploy to local Kind cluster
make deploy-for-dev service=trades

# Or do both in one step
make deploy-for-dev service=trades
```

### Production Deployment

To push a service to GitHub Container Registry:

1. **First, authenticate with GitHub Container Registry**:
   ```
   # Authenticate with GitHub Container Registry (needed once)
   make ghcr-login
   ```

2. **Build and push**:
   ```
   # Build, tag, and push to GitHub Container Registry
   make deploy-for-prod service=trades
   ```

#### Authentication Requirements

For GitHub Container Registry authentication:
1. Create a Personal Access Token (PAT) with `write:packages` and `read:packages` permissions
2. Either:
   - Use the interactive prompt: `make ghcr-login`

## OCI Compliance

This project adheres to Open Container Initiative (OCI) standards:

1. **Image Labels**:
   - All images include standard metadata labels such as title, description, version, etc.
   - Labels follow the `org.opencontainers.image.*` namespace

2. **Consistent Naming**:
   - Uses semantic versioning through git tags
   - Includes build date and git commit in image metadata
   - Production images include a timestamp and git hash for traceability

## Service Architecture

The system consists of multiple microservices:

- `trades`: Collects real-time trade data from exchanges
- `candles`: Processes trade data into candlestick patterns

Each service is built and deployed independently.
