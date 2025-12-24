# PII Shield Helm Chart

Quick-start for running the gateway on a local Kubernetes cluster with persistence, Prometheus, and Grafana.

## Prerequisites
- Kubernetes cluster (local kind/minikube/microk8s)
- Helm 3
- Container image available to the cluster (set `image.repository`/`tag` in `values.yaml`)

## Install (basic, no ingress)
```bash
helm upgrade --install pii-shield ./pii-shield \
  --set image.repository=YOUR_REPO/pii-shield \
  --set image.tag=latest
```
For local clusters (Docker Desktop), build the image locally and set `image.pullPolicy=IfNotPresent` so the UI assets are available.

## Enable ingress (optional)
```bash
helm upgrade --install pii-shield ./pii-shield \
  --set image.repository=YOUR_REPO/pii-shield \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=pii.local \
  --set ingress.hosts[0].paths[0].path=/ \
  --set ingress.hosts[0].paths[0].pathType=Prefix
```

## Local NodePort (no ingress required)
```bash
make helm-urls
```

## Prometheus + Grafana
Prometheus and Grafana are deployed by default in this chart. Grafana NodePort defaults to `http://localhost:30030` (login `admin` / `admin`).

## Persistence
- By default, a PVC is created and mounted at `/app/data` for the SQLite audit DB.
- To re-use an existing claim: `--set persistence.existingClaim=my-claim`.

## Admin API key (optional)
Create a secret and reference it from values:
```bash
kubectl create secret generic pii-shield-admin \
  --from-literal=ADMIN_API_KEY='your-secret'
helm upgrade --install pii-shield ./pii-shield \
  --set image.repository=YOUR_REPO/pii-shield \
  --set adminApiKey.enabled=true \
  --set adminApiKey.existingSecret=pii-shield-admin \
  --set adminApiKey.keyName=ADMIN_API_KEY
```

For demos only, you can let the chart create the secret:
```bash
helm upgrade --install pii-shield ./pii-shield \
  --set image.repository=YOUR_REPO/pii-shield \
  --set adminApiKey.enabled=true \
  --set adminApiKey.value='change-me'
```

## UI (standalone deployment)
Enable the separate UI pod and service:
```bash
helm upgrade --install pii-shield ./pii-shield \
  --set image.repository=YOUR_REPO/pii-shield \
  --set ui.enabled=true
```
To publish the UI via ingress:
```bash
helm upgrade --install pii-shield ./pii-shield \
  --set image.repository=YOUR_REPO/pii-shield \
  --set ui.enabled=true \
  --set ui.ingress.enabled=true \
  --set ui.ingress.hosts[0].host=pii-shield-ui.local \
  --set ui.ingress.hosts[0].paths[0].path=/ \
  --set ui.ingress.hosts[0].paths[0].pathType=Prefix
```
The UI ConfigMap defaults the API base URL to the in-cluster service; override with `ui.apiBaseUrl`.
