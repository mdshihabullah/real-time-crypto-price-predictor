

info:
	echo "Kafka UI is now accessible at http://localhost:19092"

# Build and deploy the Structurizr Docker image
c4model:
	# Create namespace if it doesn't exist
	kubectl create namespace structurizr --dry-run=client -o yaml | kubectl apply -f -
	
	echo "Building and deploying Structurizr..."
	docker build -t structurizr:dev -f docker/structurizr.Dockerfile .
	kind load docker-image structurizr:dev --name rwml-34fa
	
	# The namespace is already in the YAML - no need to specify again
	kubectl apply -f deployments/structurizr/structurizr.yaml
	
	# These operations need the namespace specified
	kubectl rollout restart deployment/structurizr-lite -n structurizr
	kubectl wait --for=condition=ready pod -l app=structurizr-lite -n structurizr --timeout=60s
	
	echo "Structurizr is now accessible at http://localhost:8089"
	echo "Note: If you update your C4 model, run 'make c4model' again to rebuild and redeploy"

dev:
	uv run services/${service}/src/${service}/main.py

# Build the Docker image for the service
build:
	docker build -t ${service}:dev -f docker/service.Dockerfile --build-arg SERVICE_NAME=${service} .

# Push the Docker image to the Kind cluster
push:
	kind load docker-image ${service}:dev --name rwml-34fa

# Deploy the Docker image to the Kind cluster
deploy: build push
	kubectl delete -f deployments/dev/${service}/${service}.yaml --ignore-not-found=true
	kubectl apply -f deployments/dev/${service}/${service}.yaml

lint:
	ruff check . --fix