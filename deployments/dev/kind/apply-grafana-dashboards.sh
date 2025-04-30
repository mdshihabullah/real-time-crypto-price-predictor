#!/bin/bash

# Generate the dashboard ConfigMaps from JSON files
./generate-dashboard-configmaps.sh

# Apply the generated ConfigMaps
echo "Applying Grafana dashboard ConfigMaps..."
kubectl apply -f manifests/grafana-dashboards.yaml

echo "Grafana dashboards applied successfully!" 