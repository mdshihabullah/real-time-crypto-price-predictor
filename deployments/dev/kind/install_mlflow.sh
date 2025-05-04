#!/bin/bash

helm upgrade --install --create-namespace --wait mlflow oci://registry-1.docker.io/bitnamicharts/mlflow --namespace=mlflow --values manifests/mlflow-values.yaml
kubectl apply --recursive -f manifests/mlflow-minio-secret.yaml 