#!/bin/bash

# Create namespace named "metabase"if only it doesnt exist
echo "Creating namespace named 'metabase' if it doesn't exist..."
kubectl create namespace metabase --dry-run=client -o yaml | kubectl apply -f -

# Delete any existing Metabase deployments
echo "Deleting any existing Metabase deployments..."
kubectl delete deployment metabase --namespace metabase --ignore-not-found

# Apply the manifest
echo "Applying Metabase manifests..."
kubectl apply -f manifests/metabase-all-in-one.yaml

# Display connection information
echo "Metabase is being deployed. Once ready, you can access it via port-forwarding via localhost"
