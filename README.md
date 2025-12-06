LLM Privacy/PII Shield
======================

FastAPI service that redacts PII from user prompts before proxying them to an Ollama model, with audit-friendly metadata logging and a lightweight stats endpoint.

Prerequisites
-------------
- Python 3.12
- Docker (for containerized runs)
- Ollama running locally
- Environment variable `OLLAMA_BASE_URL` pointing at your Ollama instance (defaults to `http://host.docker.internal:11434`)
- Optional: `DATABASE_PATH` (defaults to `./data/audit.db`), `LOG_LEVEL` (defaults to `INFO`), `REDACT_ASSISTANT` (default `false`)

Install Ollama locally
----------------------
- macOS: `brew install ollama` (or download the app from ollama.com)
- start `ollama serve`
- pulled model (e.g., `ollama pull llama3.1:8b`)

Local development (no Docker)
-----------------------------
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OLLAMA_BASE_URL="http://127.0.0.1:11434"  # adjust if needed
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Docker build and run
--------------------
```bash
docker build -t pii-shield .
docker run --rm \
  -p 8000:8000 \
  -e OLLAMA_BASE_URL="http://host.docker.internal:11434" \
  --add-host=host.docker.internal:host-gateway \
  pii-shield
```
If your Ollama instance is on a different host/port, change `OLLAMA_BASE_URL` accordingly.

API contract
------------
- Endpoint: `POST /v1/chat/completions`
- Request validated with Pydantic: `model` (string), `messages` (list of `{role, content}`), optional `stream` (default forced to `False` when omitted), and any extra fields are forwarded untouched to Ollama.
- Redaction scope: only `user` messages are redacted. `system`/`assistant` messages are proxied as-is.
- Optional: set `REDACT_ASSISTANT=true` to also redact assistant messages before logging/persistence.
- PII types masked: email, phone numbers, IBAN, credit card numbers, SSN-like patterns, simple street addresses (number + street name). Placeholders such as `[REDACTED_EMAIL]` replace matches.
- Unsupported: OpenAI tool/function calling metadata is passed through unchanged; if Ollama does not support a field it will respond with an error. Prompts are **not** logged—only metadata is.

Example request and expected response
-------------------------------------
```bash
curl -i -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.1:8b","messages":[{"role":"user","content":"My IBAN is DE89370400440532013000"}]}'
```

Example response (headers will vary):
```
HTTP/1.1 200 OK
date: Fri, 05 Dec 2025 23:27:22 GMT
server: uvicorn
content-type: application/json
x-request-id: 1b8a44f3-445b-4d38-8c07-1b557a8a2b4f
x-pii-redacted: iban
x-original-length: 33
x-masked-length: 29
x-latency-seconds: 2.598

{"model":"llama3.1:8b","created_at":"2025-12-05T23:27:25.103308Z","message":{"role":"assistant","content":"I can’t provide information that would compromise the security of your bank account. Is there anything else I can help you with?"},"done":true,"done_reason":"stop"}
```
Note: user PII is masked before forwarding, so the `messages` sent to Ollama contain placeholders (e.g., `[REDACTED_IBAN]`).

Structured logging and audit storage
------------------------------------
- Each request writes a JSON log line with: `event`, `id`, `timestamp`, `pii_types`, `model`, `latency`, `original_length`, `masked_length`, `client_ip`.
- Prompts/responses are **not** logged in this mode—only metadata.
- Metadata is also persisted to a local SQLite database at `DATABASE_PATH` for basic auditing and reporting.

Admin stats endpoint
--------------------
- `GET /admin/stats?limit=20` returns:
  - `total_requests`
  - `pii_counts` (per type)
  - `recent_events` (up to `limit`, with request id/timestamp/model/latency/lengths/pii_types)
- `limit` is clamped between 1 and 100.
- **Security:** Designed for internal dashboards or debugging. Do not expose `/admin/stats` publicly without authentication or network restrictions, even though it only returns metadata.

Simple UI
---------
- A lightweight HTML console is available at `/ui` (served by the same FastAPI app) to send prompts, view responses/headers, and fetch `/admin/stats`.
- Static assets live in `static/index.html` and are copied into the Docker image.

Running tests
-------------
- Local: install deps (prefer Python 3.12), then run:
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  pytest
  ```

- In Docker (no local deps needed):
  ```bash
  docker run --rm \
    -v "$PWD":/app \
    -w /app \
    python:3.12-slim \
    sh -c "pip install --no-cache-dir -r requirements.txt && pytest"
  ```

Project layout
--------------
- `src/app.py`: FastAPI app and routes
- `src/pii.py`: regex definitions and masking helpers
- `src/config.py`: environment-driven settings
- `src/clients/ollama.py`: minimal Ollama HTTP client
- `src/storage.py`: SQLite audit persistence helpers
- `src/main.py`: uvicorn entrypoint (imports `app`)
- `tests/`: pytest suite
- `Dockerfile`: container build for the API

Scope and positioning
---------------------
- Regex-based, best-effort PII shielding; not a guarantee of full PII removal. For strict compliance, combine with additional safeguards and review.
- Geared toward homelab/early-stage use; avoid exposing admin endpoints publicly without auth/network controls.

Future issues to track
----------------------
- Add basic API key auth for `/admin/stats`.
- Expand false-positive coverage for credit cards/addresses.
- Iterate UI at `/ui` for better usability.
