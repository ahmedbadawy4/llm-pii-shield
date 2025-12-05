LLM Privacy/PII Shield
======================

FastAPI service that redacts common PII (email, phone, IBAN) from user prompts before proxying them to an Ollama model.

Prerequisites
-------------
- Python 3.12
- Docker (for containerized runs)
- Ollama running locally
- Environment variable `OLLAMA_BASE_URL` pointing at your Ollama instance (defaults to `http://host.docker.internal:11434`)

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
- `src/`: application code (`src/main.py`)
- `tests/`: pytest suite
- `Dockerfile`: container build for the API
