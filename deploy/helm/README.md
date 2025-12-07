# PII Shield Helm Chart

Quick-start for running the gateway on a local Kubernetes cluster with persistence and optional ingress/monitoring.

## Prerequisites
- Kubernetes cluster (local kind/minikube/microk8s)
- Helm 3
- Container image available to the cluster (set `image.repository`/`tag` in `values.yaml`)
- If using ServiceMonitor, Prometheus Operator must be installed.

## Install (basic, no ingress)
```bash
helm upgrade --install pii-shield ./pii-shield \
  --set image.repository=YOUR_REPO/pii-shield \
  --set image.tag=latest
```

## Enable ingress (example)
```bash
helm upgrade --install pii-shield ./pii-shield \
  --set image.repository=YOUR_REPO/pii-shield \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=pii.local \
  --set ingress.hosts[0].paths[0].path=/ \
  --set ingress.hosts[0].paths[0].pathType=Prefix
```

## Prometheus scraping
```bash
helm upgrade --install pii-shield ./pii-shield \
  --set image.repository=YOUR_REPO/pii-shield \
  --set serviceMonitor.enabled=true
```

## Persistence
- By default, a PVC is created and mounted at `/app/data` for the SQLite audit DB.
- To re-use an existing claim: `--set persistence.existingClaim=my-claim`.
