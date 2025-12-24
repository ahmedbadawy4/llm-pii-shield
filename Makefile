APP_NAME ?= pii-shield
RELEASE ?= pii-shield
NAMESPACE ?= pii-shield
HELM_RELEASE ?= $(RELEASE)
HELM_NAMESPACE ?= $(NAMESPACE)
HELM_CHART ?= deploy/helm/pii-shield
DOCKER_COMPOSE ?= docker compose
IMAGE_REPO ?= devopsahmed/mizan-llm
IMAGE_TAG ?= latest
KIND_CLUSTER ?=
HELM_API_BASE ?= http://localhost:30080
HELM_UI_URL ?= http://localhost:30081
HELM_GRAFANA_URL ?= http://localhost:30030
OLLAMA_BASE_URL ?= http://host.docker.internal:11434
HELM_SET_ARGS ?= --set ui.enabled=true

.PHONY: help
help:
	@printf "%s\n" "Targets:"
	@printf "%s\n" "  helm-lint        Lint the Helm chart"
	@printf "%s\n" "  helm-template    Render Helm templates"
	@printf "%s\n" "  helm-install     Install/upgrade the release"
	@printf "%s\n" "  helm-install-ollama-external Install/upgrade with external Ollama"
	@printf "%s\n" "  helm-uninstall   Uninstall the release"
	@printf "%s\n" "  helm-urls        Show API/UI URLs"
	@printf "%s\n" "  helm-port-forward   Port-forward API service"
	@printf "%s\n" "  helm-reset      Delete API deployment and re-install"
	@printf "%s\n" "  helm-values      Show chart values"
	@printf "%s\n" "  run              Run the API locally"
	@printf "%s\n" "  test             Run tests"
	@printf "%s\n" "  docker-build     Build the Docker image"
	@printf "%s\n" "  docker-up        Start Docker Compose stack"
	@printf "%s\n" "  docker-down      Stop Docker Compose stack"
	@printf "%s\n" "  docker-run       Run the Docker image locally"

.PHONY: helm-lint
helm-lint:
	helm lint $(HELM_CHART)

.PHONY: helm-template
helm-template:
	helm template $(HELM_RELEASE) $(HELM_CHART) --namespace $(HELM_NAMESPACE) $(HELM_SET_ARGS)

.PHONY: helm-install
helm-install:
	docker build -t $(IMAGE_REPO):$(IMAGE_TAG) .
	@if [ -n "$(KIND_CLUSTER)" ]; then \
		kind load docker-image $(IMAGE_REPO):$(IMAGE_TAG) --name $(KIND_CLUSTER); \
	fi
	helm upgrade --install $(HELM_RELEASE) $(HELM_CHART) \
		--namespace $(HELM_NAMESPACE) --create-namespace \
		--set image.repository=$(IMAGE_REPO) \
		--set image.tag=$(IMAGE_TAG) \
		--set image.pullPolicy=IfNotPresent \
		--set ollama.enabled=true \
		$(HELM_SET_ARGS)

.PHONY: helm-install-ollama-external
helm-install-ollama-external:
	docker build -t $(IMAGE_REPO):$(IMAGE_TAG) .
	@if [ -n "$(KIND_CLUSTER)" ]; then \
		kind load docker-image $(IMAGE_REPO):$(IMAGE_TAG) --name $(KIND_CLUSTER); \
	fi
	helm upgrade --install $(HELM_RELEASE) $(HELM_CHART) \
		--namespace $(HELM_NAMESPACE) --create-namespace \
		--set image.repository=$(IMAGE_REPO) \
		--set image.tag=$(IMAGE_TAG) \
		--set image.pullPolicy=IfNotPresent \
		--set ollama.enabled=false \
		--set env.ollamaBaseUrl=$(OLLAMA_BASE_URL) \
		$(HELM_SET_ARGS)

.PHONY: helm-uninstall
helm-uninstall:
	helm uninstall $(HELM_RELEASE) --namespace $(HELM_NAMESPACE)
.PHONY: helm-reset
helm-reset:
	kubectl -n $(HELM_NAMESPACE) delete deploy $(HELM_RELEASE)-pii-shield
	$(MAKE) helm-install

.PHONY: helm-urls
helm-urls:
	@echo "API: $(HELM_API_BASE)"
	@echo "UI: $(HELM_UI_URL)"
	@echo "Grafana: $(HELM_GRAFANA_URL)"

.PHONY: helm-port-forward
helm-port-forward:
	@echo "Starting port-forward for API (8000)."
	@echo "API: http://localhost:8000"
	@echo "Press Ctrl+C to stop."
	kubectl -n $(HELM_NAMESPACE) port-forward svc/$(HELM_RELEASE)-pii-shield 8000:8000

.PHONY: helm-values
helm-values:
	helm show values $(HELM_CHART)

.PHONY: run
run:
	uvicorn src.main:app --host 0.0.0.0 --port 8000

.PHONY: test
test:
	pytest

.PHONY: docker-build
docker-build:
	docker build -t $(APP_NAME):$(IMAGE_TAG) .

.PHONY: docker-up
docker-up:
	$(DOCKER_COMPOSE) up -d --build

.PHONY: docker-down
docker-down:
	$(DOCKER_COMPOSE) down

.PHONY: docker-run
docker-run:
	docker run --rm -p 8000:8000 \
		-e OLLAMA_BASE_URL="http://host.docker.internal:11434" \
		--add-host=host.docker.internal:host-gateway \
		$(APP_NAME):$(IMAGE_TAG)
