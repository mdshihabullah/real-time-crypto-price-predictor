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

# Production deployment without unnecessary validation
prod-check-cluster:
	@echo "🔍 Checking cluster connectivity..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	kubectl cluster-info >/dev/null 2>&1 || (echo "❌ Cluster not accessible. Check KUBECONFIG." && exit 1)
	@echo "✅ Cluster is accessible"

# Infrastructure deployment
prod-deploy-infra:
	@echo "🏗️ Deploying infrastructure using industry-standard script..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	if [ -f "./deploy_infrastructure.sh" ]; then \
		echo "📜 Running deploy_infrastructure.sh script..." && \
		bash ./deploy_infrastructure.sh; \
	else \
		echo "❌ deploy_infrastructure.sh not found, falling back to manual deployment..." && \
		echo "📦 Deploying Kafka..." && \
		kubectl apply -f https://strimzi.io/install/latest?namespace=kafka && \
		sleep 30 && \
		kubectl apply -f manifests/kafka-and-topics.yaml && \
		kubectl apply -f manifests/kafka-ui.yaml && \
		echo "📊 Deploying Grafana..." && \
		helm repo add grafana https://grafana.github.io/helm-charts --force-update && \
		helm upgrade --install grafana grafana/grafana \
			--namespace grafana --create-namespace \
			--values manifests/infrastructure/grafana-values.yaml \
			--timeout 600s --wait && \
		kubectl apply -f manifests/infrastructure/grafana-dashboards.yaml && \
		echo "✅ Manual infrastructure deployment complete"; \
	fi

# Service deployment
prod-deploy-services: prod-check-cluster
	@echo "🔧 Deploying all services..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	echo "🚀 Deploying trades service..." && \
	kubectl apply -k manifests/services/trades/ && \
	echo "🕯️ Deploying candles service..." && \
	source deployment.config && \
	export CANDLES_IMAGE && \
	envsubst < manifests/services/candles/candles.yaml | kubectl apply -f - && \
	echo "📈 Deploying technical-indicators service..." && \
	kubectl apply -k manifests/services/technical_indicators/ && \
	echo "🤖 Deploying predictor-training cronjob..." && \
	source deployment.config && \
	export PREDICTOR_TRAINING_IMAGE && \
	envsubst < manifests/services/predictor_training/cronjob.yaml | kubectl apply -f - && \
	kubectl apply -f manifests/services/predictor_training/secrets.yaml && \
	kubectl apply -f manifests/services/predictor_training/configmap.yaml && \
	echo "✅ All services deployed"

# Individual service deployments
prod-deploy-trades: prod-check-cluster
	@echo "🚀 Deploying trades services (backfill + websocket)..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	source deployment.config && \
	export TRADES_IMAGE && \
	envsubst < manifests/services/trades/trades-backfill.yaml | kubectl apply -f - && \
	envsubst < manifests/services/trades/trades-websocket.yaml | kubectl apply -f -

# Deploy trades with orchestrated sequence (backfill first, then websocket)
prod-deploy-trades-orchestrated: prod-check-cluster
	@echo "🚀 Deploying trades with orchestrated sequence..."
	@echo "📋 Step 1: Deploying backfill job first..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	source deployment.config && \
	export TRADES_IMAGE && \
	envsubst < manifests/services/trades/trades-backfill.yaml | kubectl apply -f - && \
	echo "⏳ Step 2: Waiting for backfill job to complete..." && \
	kubectl wait --for=condition=complete job/trades-backfill -n services --timeout=3600s && \
	echo "✅ Backfill job completed successfully!" && \
	echo "📋 Step 3: Deploying websocket service..." && \
	envsubst < manifests/services/trades/trades-websocket.yaml | kubectl apply -f - && \
	echo "⏳ Step 4: Waiting for websocket deployment to be ready..." && \
	kubectl wait --for=condition=available deployment/trades-websocket -n services --timeout=300s && \
	echo "✅ Trades orchestration completed successfully!"

# Deploy only the backfill job
prod-deploy-trades-backfill: prod-check-cluster
	@echo "📦 Deploying trades backfill job only..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	source deployment.config && \
	export TRADES_IMAGE && \
	envsubst < manifests/services/trades/trades-backfill.yaml | kubectl apply -f -

# Deploy only the websocket service
prod-deploy-trades-websocket: prod-check-cluster
	@echo "🌐 Deploying trades websocket service only..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	source deployment.config && \
	export TRADES_IMAGE && \
	envsubst < manifests/services/trades/trades-websocket.yaml | kubectl apply -f -

# Monitor backfill job progress
prod-monitor-backfill:
	@echo "👀 Monitoring backfill job progress..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	echo "📊 Job Status:" && \
	kubectl get job trades-backfill -n services -o wide && \
	echo "" && \
	echo "📄 Recent Logs:" && \
	kubectl logs -n services job/trades-backfill --tail=50 -f

# Check trades services status
prod-trades-status:
	@echo "📋 Checking trades services status..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	echo "🔍 Jobs:" && \
	kubectl get jobs -n services -l app=trades-backfill -o wide && \
	echo "" && \
	echo "🔍 Deployments:" && \
	kubectl get deployments -n services -l app=trades-websocket -o wide && \
	echo "" && \
	echo "🔍 Pods:" && \
	kubectl get pods -n services -l 'app in (trades-backfill,trades-websocket)' -o wide

# Clean up old trades deployments before orchestrated deployment
prod-cleanup-trades:
	@echo "🧹 Cleaning up existing trades deployments..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	kubectl delete deployment trades trades-websocket -n services --ignore-not-found=true && \
	kubectl delete job trades-backfill -n services --ignore-not-found=true && \
	echo "✅ Cleanup completed"

prod-deploy-candles: prod-check-cluster
	@echo "🕯️ Deploying candles service..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	source deployment.config && \
	export CANDLES_IMAGE && \
	envsubst < manifests/services/candles/candles.yaml | kubectl apply -f -

prod-deploy-technical-indicators: prod-check-cluster
	@echo "📈 Deploying technical-indicators service..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	source deployment.config && \
	export TECHNICAL_INDICATORS_IMAGE && \
	envsubst < manifests/services/technical_indicators/technical_indicators.yaml | kubectl apply -f -

prod-deploy-predictor-training: prod-check-cluster
	@echo "🤖 Deploying predictor-training cronjob..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	source deployment.config && \
	export PREDICTOR_TRAINING_IMAGE && \
	envsubst < manifests/services/predictor_training/cronjob.yaml | kubectl apply -f - && \
	kubectl apply -f manifests/services/predictor_training/secrets.yaml && \
	kubectl apply -f manifests/services/predictor_training/configmap.yaml

prod-deploy-structurizr: prod-check-cluster
	@echo "🏗️ Deploying structurizr service..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	source deployment.config && \
	export STRUCTURIZR_IMAGE && \
	envsubst < manifests/structurizr/structurizr.yaml | kubectl apply -f -

# Deploy trades with parallel start (websocket waits for backfill completion)
prod-deploy-trades-parallel: prod-check-cluster
	@echo "🚀 Deploying trades with parallel start..."
	@echo "📋 Starting backfill job and websocket deployment simultaneously..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	source deployment.config && \
	export TRADES_IMAGE && \
	echo "🔄 Starting backfill job..." && \
	envsubst < manifests/services/trades/trades-backfill.yaml | kubectl apply -f - && \
	echo "🔄 Starting websocket deployment (will wait for backfill completion)..." && \
	envsubst < manifests/services/trades/trades-websocket.yaml | kubectl apply -f - && \
	echo "✅ Both services started! Websocket will begin once backfill completes." && \
	echo "💡 Monitor progress with: make prod-monitor-trades-parallel"

# Monitor parallel trades deployment progress  
prod-monitor-trades-parallel:
	@echo "👀 Monitoring parallel trades deployment progress..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	echo "📊 Backfill Job Status:" && \
	kubectl get job trades-backfill -n services -o wide && \
	echo "" && \
	echo "📊 Websocket Deployment Status:" && \
	kubectl get deployment trades-websocket -n services -o wide && \
	echo "" && \
	echo "📊 Pod Status:" && \
	kubectl get pods -n services -l 'app in (trades-backfill,trades-websocket)' -o wide && \
	echo "" && \
	echo "🔍 Websocket init container logs (waiting for backfill):" && \
	if kubectl get pods -n services -l app=trades-websocket --no-headers -o custom-columns=":metadata.name" | head -1 | xargs -I {} kubectl logs -n services {} -c wait-for-backfill-completion 2>/dev/null; then \
		echo "Init container logs shown above."; \
	else \
		echo "No websocket pod ready yet or init container not started."; \
	fi

# Main deployment command - now much simpler
prod-deploy:
	@if [ "$(infra)" = "true" ] || [ "$(infra)" = "all" ] || [ "$(infra)" = "risingwave" ]; then \
		$(MAKE) prod-deploy-infra; \
	elif [ "$(services)" = "true" ] || [ "$(services)" = "all" ]; then \
		$(MAKE) prod-deploy-services; \
	elif [ "$(service)" = "trades" ] && [ "$(orchestrated)" = "true" ]; then \
		$(MAKE) prod-deploy-trades-orchestrated; \
	elif [ "$(service)" = "trades" ] && [ "$(parallel)" = "true" ]; then \
		$(MAKE) prod-deploy-trades-parallel; \
	elif [ "$(service)" = "trades" ]; then \
		$(MAKE) prod-deploy-trades; \
	elif [ "$(service)" = "candles" ]; then \
		$(MAKE) prod-deploy-candles; \
	elif [ "$(service)" = "technical-indicators" ]; then \
		$(MAKE) prod-deploy-technical-indicators; \
	elif [ "$(service)" = "predictor-training" ]; then \
		$(MAKE) prod-deploy-predictor-training; \
	elif [ "$(service)" = "structurizr" ]; then \
		$(MAKE) prod-deploy-structurizr; \
	else \
		$(MAKE) prod-deploy-services; \
	fi

# Deploy complete cluster from scratch
prod-create-cluster:
	@echo "🚀 Creating new DigitalOcean cluster and deploying complete infrastructure and services..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	if [ -f "./create-do-k8s-cluster.sh" ]; then \
		echo "📜 Running create-do-k8s-cluster.sh script..." && \
		bash ./create-do-k8s-cluster.sh && \
		echo "✅ Cluster creation and deployment completed successfully"; \
	else \
		echo "❌ create-do-k8s-cluster.sh not found" && \
		exit 1; \
	fi

# Production deployment utilities
prod-get-endpoints:
	@echo "🌐 Getting production service endpoints..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	kubectl get services -A

prod-status:
	@echo "📋 Getting production deployment status..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	kubectl get pods -n services && \
	kubectl get deployments -n services

prod-logs:
	@echo "📄 Getting production service logs..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	echo "=== Trades Service Logs ===" && \
	kubectl logs -n services -l app.kubernetes.io/name=trades --tail=20 && \
	echo "=== Candles Service Logs ===" && \
	kubectl logs -n services -l app=candles --tail=20 && \
	echo "=== Technical Indicators Service Logs ===" && \
	kubectl logs -n services -l app.kubernetes.io/name=technical-indicators --tail=20

prod-restart:
	@echo "🔄 Restarting all services..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	kubectl rollout restart deployment -n services

# Production service access
prod-access:
	@echo "🌐 Production Service Access URLs"
	@echo "=================================="
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	echo "" && \
	echo "📊 Direct Browser Access (LoadBalancer IPs):" && \
	echo "  Kafka UI:    http://$$(kubectl get svc kafka-ui -n kafka -o jsonpath='{.status.loadBalancer.ingress[0].ip}')" && \
	echo "  Grafana:     http://$$(kubectl get svc grafana -n grafana -o jsonpath='{.status.loadBalancer.ingress[0].ip}')" && \
	echo "  MLflow:      http://$$(kubectl get svc mlflow-tracking -n mlflow -o jsonpath='{.status.loadBalancer.ingress[0].ip}')" && \
	echo "  Structurizr: http://$$(kubectl get svc structurizr -n structurizr -o jsonpath='{.status.loadBalancer.ingress[0].ip}')" && \
	echo "" && \
	echo "🔑 Grafana Login Credentials:" && \
	echo "  Username: admin" && \
	echo "  Password: $$(kubectl get secret --namespace grafana grafana -o jsonpath='{.data.admin-password}' | base64 --decode)" && \
	echo "" && \
	echo "💡 All services are accessible directly via LoadBalancer IPs - no port-forwarding needed!"

prod-port-forward-kafka:
	@echo "🔗 Starting Kafka UI port-forward on localhost:8080..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	kubectl port-forward -n kafka svc/kafka-ui 8080:80

prod-port-forward-grafana:
	@echo "🔗 Starting Grafana port-forward on localhost:3000..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	kubectl port-forward -n grafana svc/grafana 3000:80

prod-port-forward-mlflow:
	@echo "🔗 Starting MLflow port-forward on localhost:5000..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	kubectl port-forward -n mlflow svc/mlflow-tracking 5000:80

prod-port-forward-structurizr:
	@echo "🔗 Starting Structurizr port-forward on localhost:8081..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	kubectl port-forward -n structurizr svc/structurizr 8081:80

# Production maintenance commands
prod-cleanup:
	@echo "🧹 Cleaning up production deployment..."
	@cd $(PROD_DIR) && \
	export KUBECONFIG=$$(pwd)/do-k8s-kubeconfig.yaml && \
	kubectl delete namespace services --ignore-not-found=true

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
	@echo "  prod-create-cluster         Create new cluster and deploy complete infrastructure and services"
	@echo "  prod-check-cluster          Check cluster connectivity"
	@echo "  prod-deploy                 Deploy all services (default)"
	@echo "  prod-deploy infra=true      Deploy all infrastructure (Kafka, RisingWave, MLflow, Grafana)"
	@echo "  prod-deploy infra=risingwave Deploy RisingWave and dependencies with table setup"
	@echo "  prod-deploy services=true   Deploy only services"
	@echo "  prod-deploy service=trades orchestrated=true  Deploy trades with orchestrated sequence (backfill → websocket)"
	@echo "  prod-deploy service=trades parallel=true      Deploy trades with parallel start (websocket waits for backfill) (RECOMMENDED)"
	@echo "  prod-deploy service=trades  Deploy trades services (both backfill + websocket)"
	@echo "  prod-deploy service=candles Deploy only candles service"
	@echo "  prod-deploy service=technical-indicators Deploy only technical-indicators service"
	@echo "  prod-deploy service=predictor-training Deploy only predictor-training cronjob"
	@echo "  prod-deploy service=structurizr    Deploy only structurizr service"
	@echo ""
	@echo "📦 Trades Service Specific Commands:"
	@echo "  prod-deploy-trades-parallel      Deploy trades with parallel start (websocket waits for backfill) (RECOMMENDED)"
	@echo "  prod-deploy-trades-orchestrated  Deploy trades with orchestrated sequence"
	@echo "  prod-deploy-trades-backfill      Deploy only the backfill job"
	@echo "  prod-deploy-trades-websocket     Deploy only the websocket service"
	@echo "  prod-monitor-trades-parallel     Monitor parallel trades deployment progress"
	@echo "  prod-monitor-backfill            Monitor backfill job progress"
	@echo "  prod-trades-status               Check trades services status"
	@echo "  prod-cleanup-trades              Clean up existing trades deployments"
	@echo ""
	@echo "🔧 Production Utilities:"
	@echo "  prod-get-endpoints          Get service endpoints"
	@echo "  prod-status                 Show deployment status"
	@echo "  prod-logs                   View service logs"
	@echo "  prod-restart                Restart all services"
	@echo "  prod-access                 Show service access URLs and credentials"
	@echo ""
	@echo "🌐 Production Service Access:"
	@echo "  prod-port-forward-kafka     Port-forward Kafka UI to localhost:8080"
	@echo "  prod-port-forward-grafana   Port-forward Grafana to localhost:3000"
	@echo "  prod-port-forward-mlflow    Port-forward MLflow to localhost:5000"
	@echo "  prod-port-forward-structurizr Port-forward Structurizr to localhost:8081"
	@echo ""
	@echo "🧹 Production Maintenance:"
	@echo "  prod-cleanup                Remove production deployment"
	@echo ""
	@echo "💡 Examples:"
	@echo "  make dev service=trades               # Run trades service locally"
	@echo "  make deploy-for-dev service=candles   # Deploy candles to Kind"
	@echo "  make ghcr-push service=trades         # Push trades image to registry"
	@echo "  make ghcr-push service=predictor_training # Push predictor training image to registry"
	@echo "  make prod-create-cluster              # Create new cluster and deploy everything"
	@echo "  make prod-deploy                      # Deploy all services"
	@echo "  make prod-deploy infra=true           # Deploy only infrastructure"
	@echo "  make prod-deploy service=trades orchestrated=true  # Deploy trades with orchestration (recommended)"
	@echo "  make prod-deploy service=candles      # Deploy only candles service"
	@echo "  make prod-deploy-trades-orchestrated  # Deploy trades with backfill → websocket sequence"
	@echo "  make prod-monitor-backfill            # Monitor backfill progress in real-time"
	@echo "  make prod-trades-status               # Check trades services status"
	@echo "  make prod-get-endpoints               # Get production service URLs"
	@echo ""
	@echo "📚 For detailed production deployment guide:"
	@echo "  cat deployments/prod/NEW_CLUSTER_DEPLOYMENT_CHECKLIST.md"

.DEFAULT_GOAL := help