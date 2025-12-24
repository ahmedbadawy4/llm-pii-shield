# PII Shield UI (simple)

This is a lightweight, static UI for the PII Shield API. It is served by the standalone UI pod in Helm or any static file server.

## Run locally
1. Start the API (from the repo root):
   ```bash
   make run
   ```
2. Serve the UI (from the repo root):
   ```bash
   python -m http.server 8080 -d ui
   ```
3. Open http://localhost:8080

## Notes
- The UI calls the API at the current origin by default; set the API base URL in the UI if the API is elsewhere.
- For Kubernetes, the Helm chart injects the API base URL into `config.js` using `ui.apiBaseUrl`.
