#!/bin/bash

# This script generates ConfigMaps for Grafana dashboards
# It reads JSON files from the dashboards directory and creates a YAML file with ConfigMaps

DASHBOARD_DIR="/Users/shihab/Documents/Development/LearningMLOps/real-time-crypto-price-predictor/dashboards/grafana"
OUTPUT_FILE="manifests/grafana-dashboards.yaml"
NAMESPACE="monitoring"

# Create output directory if it doesn't exist
mkdir -p $(dirname "$OUTPUT_FILE")

# Clear the output file
> "$OUTPUT_FILE"

# Process each JSON file in the dashboard directory
for dashboard_file in "$DASHBOARD_DIR"/*.json; do
  # Extract filename without path and extension
  filename=$(basename "$dashboard_file")
  dashboard_name=$(basename "$dashboard_file" .json)
  
  # Create a valid k8s resource name (lowercase, alphanumeric with dashes)
  resource_name=$(echo "$dashboard_name" | tr '[:upper:]' '[:lower:]' | tr '_' '-' | sed 's/[^a-z0-9-]/-/g')
  
  echo "Processing dashboard: $filename -> $resource_name"
  
  # Write ConfigMap header to the output file
  cat >> "$OUTPUT_FILE" << EOF
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-dashboard-$resource_name
  namespace: $NAMESPACE
  labels:
    grafana_dashboard: "1"
data:
  $filename: |-
EOF

  # Write the dashboard JSON content, indented with 4 spaces
  sed 's/^/    /' "$dashboard_file" >> "$OUTPUT_FILE"
  
  # Add an extra newline after each ConfigMap
  echo "" >> "$OUTPUT_FILE"
done

echo "ConfigMaps generated in $OUTPUT_FILE" 