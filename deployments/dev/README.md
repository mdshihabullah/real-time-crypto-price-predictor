# Kubernetes Deployments for Development

This directory contains the Kubernetes deployment configurations for development environments.

## State Management for Quixstreams Services

Services that use Quixstreams require a writable state directory for local state management. This directory is used to store local state information and is essential for Kafka consumer group state management.

### Common Issues

If you encounter this error:
```
PermissionError: [Errno 13] Permission denied: '/app/state'
```

This means that the Quixstreams application cannot create or access its state directory. This happens because:

1. The container is running as a non-root user (good security practice)
2. The default state directory does not exist or has incorrect permissions

### Solution

Our solution involves:

1. Using a Kubernetes volume (emptyDir) to store state
2. Using an init container to set the correct permissions
3. Mounting the volume at the correct path (/app/state) where Quixstreams expects it

### Implementation

For each service using Quixstreams, ensure your deployment YAML includes:

```yaml
spec:
  template:
    spec:
      initContainers:
      - name: init-state-dir
        image: busybox
        command: ['sh', '-c', 'mkdir -p /app/state && chmod 777 /app/state']
        volumeMounts:
        - name: state-volume
          mountPath: /app/state
      containers:
      - name: your-service
        # ... other settings
        env:
        - name: QUIX_STATE_DIRECTORY
          value: "/app/state"
        volumeMounts:
        - name: state-volume
          mountPath: /app/state
      volumes:
      - name: state-volume
        emptyDir: {}
```

### Production Considerations

For production environments, consider:

1. Using PersistentVolumes instead of emptyDir for durable state
2. Setting resource limits and requests
3. Implementing backup strategies for the state directory

## Templates

See the `template` directory for reference deployment templates that follow these best practices. 


## Grafana Dashboard Configuration

This project uses ConfigMaps to dynamically load Grafana dashboards from JSON files. The setup follows best practices for Kubernetes deployments in both development and production environments.

### How it works

1. Dashboard JSON files are stored in the `dashboards/grafana/` directory
2. The `generate-dashboard-configmaps.sh` script creates ConfigMaps from these JSON files
3. Grafana's sidecar container automatically discovers and loads these dashboards

### Adding a new dashboard

1. Create your dashboard in Grafana UI and export as JSON
2. Save the JSON file in `dashboards/grafana/`
3. Run the dashboard setup:

```bash
cd deployments/dev/kind
./apply-grafana-dashboards.sh
```

### In production (DigitalOcean Kubernetes)

The same approach works in production:

1. Store dashboard JSON files in Git
2. Include the dashboard generation as part of your CI/CD pipeline
3. Apply the generated ConfigMaps to your Kubernetes cluster

This approach is scalable and maintainable even with hundreds of dashboards.
