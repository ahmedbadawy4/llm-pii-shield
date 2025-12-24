APP_NAME ?= pii-shield
RELEASE ?= pii-shield
NAMESPACE ?= pii-shield
HELM_CHART ?= deploy/helm/pii-shield
IMAGE_REPO ?= devopsahmed/mizan-llm
IMAGE_TAG ?= latest

HELM_SET_ARGS ?= --set image.repository=$(IMAGE_REPO) --set image.tag=$(IMAGE_TAG) --set namespace=$(NAMESPACE)

.PHONY: help
help:
	@printf "%s\n" "Targets:"
	@printf "%s\n" "  helm-lint        Lint the Helm chart"
	@printf "%s\n" "  helm-template    Render Helm templates"
	@printf "%s\n" "  helm-install     Install/upgrade the release"
	@printf "%s\n" "  helm-uninstall   Uninstall the release"
	@printf "%s\n" "  helm-values      Show chart values"
	@printf "%s\n" "  run              Run the API locally"
	@printf "%s\n" "  test             Run tests"
	@printf "%s\n" "  docker-build     Build the Docker image"
	@printf "%s\n" "  docker-run       Run the Docker image locally"

.PHONY: helm-lint
helm-lint:
	helm lint $(HELM_CHART)

.PHONY: helm-template
helm-template:
	helm template $(RELEASE) $(HELM_CHART) --namespace $(NAMESPACE) $(HELM_SET_ARGS)

.PHONY: helm-install
helm-install:
	helm upgrade --install $(RELEASE) $(HELM_CHART) --namespace $(NAMESPACE) --create-namespace $(HELM_SET_ARGS)

.PHONY: helm-uninstall
helm-uninstall:
	helm uninstall $(RELEASE) --namespace $(NAMESPACE)

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

.PHONY: docker-run
docker-run:
	docker run --rm -p 8000:8000 \
		-e OLLAMA_BASE_URL="http://host.docker.internal:11434" \
		--add-host=host.docker.internal:host-gateway \
		$(APP_NAME):$(IMAGE_TAG)
