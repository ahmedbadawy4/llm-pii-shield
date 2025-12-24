APP_NAME ?= pii-shield
RELEASE ?= pii-shield
NAMESPACE ?= pii-shield
HELM_CHART ?= deploy/helm/pii-shield
IMAGE_REPO ?= devopsahmed/mizan-llm
IMAGE_TAG ?= latest
HELM_API_BASE ?= http://localhost:30080
HELM_UI_URL ?= http://localhost:30081

HELM_SET_ARGS ?= --set image.repository=$(IMAGE_REPO) --set image.tag=$(IMAGE_TAG) --set namespace=$(NAMESPACE) --set ui.enabled=true

.PHONY: help
help:
	@printf "%s\n" "Targets:"
	@printf "%s\n" "  helm-lint        Lint the Helm chart"
	@printf "%s\n" "  helm-template    Render Helm templates"
	@printf "%s\n" "  helm-install     Install/upgrade the release"
	@printf "%s\n" "  helm-uninstall   Uninstall the release"
	@printf "%s\n" "  helm-urls        Show API/UI URLs"
	@printf "%s\n" "  helm-port-forward   Port-forward API and UI services"
	@printf "%s\n" "  helm-reset      Delete API deployment and re-install"
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
	docker build -t $(IMAGE_REPO):$(IMAGE_TAG) .
	helm upgrade --install $(RELEASE) $(HELM_CHART) --namespace $(NAMESPACE) --create-namespace $(HELM_SET_ARGS)
	kubectl -n $(NAMESPACE) rollout restart deploy/$(RELEASE)-pii-shield-ui

.PHONY: helm-uninstall
helm-uninstall:
	helm uninstall $(RELEASE) --namespace $(NAMESPACE)

.PHONY: helm-reset
helm-reset:
	kubectl -n $(NAMESPACE) delete deploy $(RELEASE)-pii-shield
	$(MAKE) helm-install

.PHONY: helm-urls
helm-urls:
	@echo "API: $(HELM_API_BASE)"
	@echo "UI: $(HELM_UI_URL)"

.PHONY: helm-port-forward
helm-port-forward:
	@echo "Starting port-forward for API (8000) and UI (8080)."
	@echo "API: http://localhost:8000"
	@echo "UI: http://localhost:8080"
	@echo "Press Ctrl+C to stop."
	@kubectl -n $(NAMESPACE) port-forward svc/$(RELEASE)-pii-shield 8000:8000 & \
	kubectl -n $(NAMESPACE) port-forward svc/$(RELEASE)-pii-shield-ui 8080:8080 & \
	wait

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
