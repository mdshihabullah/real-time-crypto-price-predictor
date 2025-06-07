################################################################################
## Global Variables - OCI Compliant Naming
################################################################################
# Repository details
GITHUB_USERNAME := mdshihabullah
IMAGE_REPO := ghcr.io/$(GITHUB_USERNAME)/real-time-crypto-price-predictor
VERSION := $(shell git describe --tags --always || echo "0.1.0")
GIT_COMMIT := $(shell git rev-parse --short HEAD)
BUILD_DATE := $(shell date -u +'%Y-%m-%dT%H:%M:%SZ')
FULL_IMAGE_NAME = $(IMAGE_REPO)/$(service):$(VERSION)
DEV_IMAGE_NAME = $(service):dev
PROD_TAG = beta-$(shell date +%d-%m-%Y-%H-%M)-$(GIT_COMMIT)
PROD_IMAGE_NAME = $(IMAGE_REPO)/$(service):$(PROD_TAG)

# Production deployment configuration
PROD_DIR := deployments/prod

################################################################################
## Development
################################################################################

# Runs the trades service as a standalone Pyton app (not Dockerized)
dev:
	uv run services/${service}/src/${service}/main.py

# Builds a docker image from a given Dockerfile
build-for-dev:
	docker buildx build --no-cache \
		-t $(DEV_IMAGE_NAME) \
		--build-arg SERVICE_NAME=${service} \
		--build-arg BUILD_DATE="$(BUILD_DATE)" \
		--build-arg VERSION="$(VERSION)" \
		--build-arg SOURCE_COMMIT="$(GIT_COMMIT)" \
		-f docker/${service}.Dockerfile .

# Push the docker image to the docker registry of our kind cluster
push-for-dev:
	kind load docker-image $(DEV_IMAGE_NAME) --name rwml-34fa

# Deploys the docker image to the kind cluster
deploy-for-dev: build-for-dev push-for-dev
	# Create namespace if it doesn't exist
	kubectl create namespace services --dry-run=client -o yaml | kubectl apply -f -
	
	# Clean up any existing deployments
	kubectl delete deployment,cronjob -n services -l app.kubernetes.io/name=${service} --ignore-not-found=true
	
	# Apply using kustomize
	kubectl apply -k deployments/dev/${service}/

info:
	echo "Kafka UI is now accessible at http://localhost:19092"

# Build and deploy the Structurizr Docker image
c4model:
	# Create namespace if it doesn't exist
	kubectl create namespace structurizr --dry-run=client -o yaml | kubectl apply -f -
	
	echo "Building and deploying Structurizr..."
	docker build -t structurizr:dev \
		--build-arg BUILD_DATE="$(BUILD_DATE)" \
		--build-arg SOURCE_COMMIT="$(GIT_COMMIT)" \
		-f docker/structurizr.Dockerfile .
	kind load docker-image structurizr:dev --name rwml-34fa
	
	# The namespace is already in the YAML - no need to specify again
	kubectl apply -f deployments/structurizr/structurizr.yaml
	
	# These operations need the namespace specified
	kubectl rollout restart deployment/structurizr-lite -n structurizr
	kubectl wait --for=condition=ready pod -l app=structurizr-lite -n structurizr --timeout=60s
	
	echo "Structurizr is now accessible at http://localhost:8089"
	echo "Note: If you update your C4 model, run 'make c4model' again to rebuild and redeploy"

lint:
	ruff check . --fix

################################################################################
## Production Image Management
################################################################################

# Login to GitHub Container Registry (run this once or when token expires)
ghcr-login:
	@echo "Please enter your GitHub Personal Access Token:"
	@read -s GITHUB_PAT && echo $$GITHUB_PAT | docker login ghcr.io -u $(GITHUB_USERNAME) --password-stdin

ghcr-push:
	# ---------------------------------------------------------------
	# Build & push a multi-arch image with proper OCI annotations
	# ---------------------------------------------------------------
	@echo "Building and pushing $(service) image to GitHub Container Registry…"

	docker buildx build --push --no-cache \
	    --platform linux/amd64 \
		-t $(PROD_IMAGE_NAME) \
		--build-arg SERVICE_NAME=${service} \
		--build-arg BUILD_DATE="$(BUILD_DATE)" \
		--build-arg VERSION="$(VERSION)" \
		--build-arg SOURCE_COMMIT="$(GIT_COMMIT)" \
		--label org.opencontainers.image.title="${service} Service" \
		--label org.opencontainers.image.description="${service} service for real-time cryptocurrency price prediction system" \
		--label org.opencontainers.image.url="https://github.com/mdshihabullah/real-time-crypto-price-predictor" \
		--label org.opencontainers.image.source="https://github.com/mdshihabullah/real-time-crypto-price-predictor/tree/$(GIT_COMMIT)" \
		--label org.opencontainers.image.version="$(VERSION)" \
		--label org.opencontainers.image.created="$(BUILD_DATE)" \
		--label org.opencontainers.image.revision="$(GIT_COMMIT)" \
		--label org.opencontainers.image.licenses="Apache-2.0" \
		--label org.opencontainers.image.authors="$(GITHUB_USERNAME)" \
		--label org.opencontainers.image.base.name="$(FULL_IMAGE_NAME)" \
		-f docker/${service}.Dockerfile .

	@echo "Image $(PROD_IMAGE_NAME) built and pushed successfully."

################################################################################
## Production Deployment (DigitalOcean Kubernetes)
################################################################################

# Production deployment prerequisites and validation
prod-check-prereqs:
	@echo "🔍 Checking production deployment prerequisites..."
	@cd $(PROD_DIR) && ./pre_deployment_check.sh

prod-validate-cluster:
	@echo "🔍 Validating production cluster connectivity and resources..."
	@cd $(PROD_DIR) && ./pre_deployment_check.sh

# Modular production deployment with parameters
prod-deploy: prod-check-prereqs
	@if [ "$(infra)" = "risingwave" ]; then \
		echo "🏗️ Deploying RisingWave infrastructure..."; \
		cd $(PROD_DIR) && $(MAKE) deploy-infrastructure; \
	elif [ "$(infra)" = "mlflow" ]; then \
		echo "🏗️ Deploying MLflow infrastructure..."; \
		cd $(PROD_DIR) && helm upgrade --install mlflow oci://registry-1.docker.io/bitnamicharts/mlflow \
			--namespace mlflow --create-namespace \
			--values manifests/infrastructure/mlflow-values.yaml \
			--timeout 600s --wait; \
	elif [ "$(infra)" = "grafana" ]; then \
		echo "🏗️ Deploying Grafana infrastructure..."; \
		cd $(PROD_DIR) && $(MAKE) generate-dashboards && \
		helm upgrade --install grafana grafana/grafana \
			--namespace grafana --create-namespace \
			--values manifests/infrastructure/grafana-values.yaml \
			--timeout 600s --wait && \
		kubectl apply -f manifests/infrastructure/grafana-dashboards.yaml; \
	elif [ "$(infra)" = "all" ]; then \
		echo "🏗️ Deploying all infrastructure components..."; \
		cd $(PROD_DIR) && $(MAKE) deploy-infrastructure; \
	elif [ "$(service)" = "trades" ]; then \
		echo "🔧 Deploying trades service..."; \
		cd $(PROD_DIR) && kubectl apply -k manifests/services/trades/; \
	elif [ "$(service)" = "candles" ]; then \
		echo "🔧 Deploying candles service..."; \
		cd $(PROD_DIR) && \
		export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
		source deployment.config && \
		export CANDLES_IMAGE && \
		envsubst < manifests/services/candles/candles.yaml | kubectl apply -f -; \
	elif [ "$(service)" = "technical-indicators" ]; then \
		echo "🔧 Deploying technical-indicators service..."; \
		cd $(PROD_DIR) && kubectl apply -k manifests/services/technical_indicators/; \
	elif [ "$(service)" = "structurizr" ]; then \
		echo "🔧 Deploying structurizr service..."; \
		cd $(PROD_DIR) && envsubst < manifests/structurizr/structurizr.yaml | kubectl apply -f -; \
	elif [ "$(service)" = "kafka" ]; then \
		echo "🔧 Deploying Kafka services..."; \
		cd $(PROD_DIR) && kubectl apply -f https://strimzi.io/install/latest?namespace=kafka && \
		sleep 30 && kubectl apply -f manifests/kafka-and-topics.yaml && kubectl apply -f manifests/kafka-ui.yaml; \
	elif [ "$(service)" = "all" ]; then \
		echo "🔧 Deploying all application services..."; \
		cd $(PROD_DIR) && $(MAKE) deploy-services; \
	else \
		echo "🚀 Starting full production deployment..."; \
		cd $(PROD_DIR) && $(MAKE) create-cluster; \
	fi

# Production deployment utilities
prod-generate-dashboards:
	@echo "📊 Generating Grafana dashboards..."
	@cd $(PROD_DIR) && $(MAKE) generate-dashboards

prod-get-endpoints:
	@echo "🌐 Getting production service endpoints..."
	@cd $(PROD_DIR) && $(MAKE) get-endpoints

prod-status:
	@echo "📋 Getting production deployment status..."
	@cd $(PROD_DIR) && $(MAKE) status

prod-health:
	@echo "🩺 Performing production health check..."
	@cd $(PROD_DIR) && $(MAKE) health

prod-logs:
	@echo "📄 Getting production service logs..."
	@cd $(PROD_DIR) && $(MAKE) logs

prod-validate-deployment:
	@echo "✅ Validating production deployment..."
	@cd $(PROD_DIR) && $(MAKE) validate-deployment

# Production maintenance commands
prod-cleanup:
	@echo "🧹 Cleaning up production deployment..."
	@cd $(PROD_DIR) && $(MAKE) cleanup

prod-reset:
	@echo "🔄 Resetting production deployment..."
	@cd $(PROD_DIR) && $(MAKE) reset

prod-clean:
	@echo "🗑️ Cleaning temporary files..."
	@cd $(PROD_DIR) && $(MAKE) clean

################################################################################
## Help and Information
################################################################################

help:
	@echo "🚀 Real-time Crypto Price Predictor - Build & Deployment"
	@echo "========================================================"
	@echo ""
	@echo "📦 Development Commands:"
	@echo "  dev service=<name>           Run service locally (non-dockerized)"
	@echo "  build-for-dev service=<name> Build Docker image for development"
	@echo "  deploy-for-dev service=<name> Build and deploy to Kind cluster"
	@echo "  c4model                      Build and deploy architecture documentation"
	@echo "  info                         Show development service info"
	@echo "  lint                         Run code linting"
	@echo ""
	@echo "🏗️ Production Image Management:"
	@echo "  ghcr-login                   Login to GitHub Container Registry"
	@echo "  ghcr-push service=<name>     Build and push production image"
	@echo ""
	@echo "☁️ Production Deployment (DigitalOcean):"
	@echo "  prod-check-prereqs          Verify deployment prerequisites"
	@echo "  prod-validate-cluster       Validate cluster connectivity"
	@echo "  prod-deploy                 Full production deployment"
	@echo "  prod-deploy infra=<name>    Deploy specific infrastructure (risingwave|mlflow|grafana|all)"
	@echo "  prod-deploy service=<name>  Deploy specific service (trades|candles|technical-indicators|structurizr|kafka|all)"
	@echo ""
	@echo "🔧 Production Utilities:"
	@echo "  prod-generate-dashboards    Generate Grafana dashboards"
	@echo "  prod-get-endpoints          Get service endpoints"
	@echo "  prod-status                 Show deployment status"
	@echo "  prod-health                 Quick health check"
	@echo "  prod-logs                   View service logs"
	@echo "  prod-validate-deployment    Validate deployment health"
	@echo ""
	@echo "🧹 Production Maintenance:"
	@echo "  prod-cleanup                Remove production deployment"
	@echo "  prod-reset                  Full reset (cleanup + redeploy)"
	@echo "  prod-clean                  Clean temporary files"
	@echo ""
	@echo "💡 Examples:"
	@echo "  make dev service=trades               # Run trades service locally"
	@echo "  make deploy-for-dev service=candles   # Deploy candles to Kind"
	@echo "  make ghcr-push service=trades         # Push trades image to registry"
	@echo "  make prod-deploy                      # Full production deployment"
	@echo "  make prod-deploy infra=risingwave     # Deploy only RisingWave"
	@echo "  make prod-deploy service=trades       # Deploy only trades service"
	@echo "  make prod-get-endpoints               # Get production service URLs"
	@echo ""
	@echo "📚 For detailed production deployment guide:"
	@echo "  cat deployments/prod/NEW_CLUSTER_DEPLOYMENT_CHECKLIST.md"

.DEFAULT_GOAL := help