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
PROD_TAG = beta-$(shell date +%d-%m-%Y)-$(GIT_COMMIT)
PROD_IMAGE_NAME = $(IMAGE_REPO)/$(service):$(PROD_TAG)

################################################################################
## Development
################################################################################

# Runs the trades service as a standalone Pyton app (not Dockerized)
dev:
	uv run services/${service}/src/${service}/main.py

# Builds a docker image from a given Dockerfile
build-for-dev:
	docker build -t $(DEV_IMAGE_NAME) \
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
	
	kubectl delete -f deployments/dev/${service}/${service}.yaml --ignore-not-found=true
	kubectl apply -f deployments/dev/${service}/${service}.yaml

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
## Production
################################################################################

# Login to GitHub Container Registry (run this once or when token expires)
ghcr-login:
	@echo "Please enter your GitHub Personal Access Token:"
	@read -s GITHUB_PAT && echo $$GITHUB_PAT | docker login ghcr.io -u $(GITHUB_USERNAME) --password-stdin

deploy-for-prod:
	# ---------------------------------------------------------------
	# Build & push a multi-arch image with proper OCI annotations
	# ---------------------------------------------------------------
	@echo "Building and pushing $(service) image to GitHub Container Registry…"

	docker buildx build --push \
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