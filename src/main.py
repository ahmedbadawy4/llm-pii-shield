import os
import re
import time
import uuid
from typing import List, Tuple

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

# When running inside Docker this allows access to your host's Ollama daemon
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

app = FastAPI(title="LLM Privacy/PII Shield")

# PII patterns
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_REGEX = re.compile(r"\+?\d[\d\s().-]{7,}\d")
IBAN_REGEX = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")


def mask_pattern(text: str, pattern: re.Pattern, placeholder: str) -> Tuple[str, bool]:
    if pattern.search(text):
        text = pattern.sub(placeholder, text)
        return text, True
    return text, False


def redact_pii(text: str) -> Tuple[str, List[str]]:
    detected: List[str] = []

    text, hit = mask_pattern(text, EMAIL_REGEX, "[REDACTED_EMAIL]")
    if hit:
        detected.append("email")

    text, hit = mask_pattern(text, IBAN_REGEX, "[REDACTED_IBAN]")
    if hit:
        detected.append("iban")

    text, hit = mask_pattern(text, PHONE_REGEX, "[REDACTED_PHONE]")
    if hit:
        detected.append("phone")

    return text, detected


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    req_id = str(uuid.uuid4())
    body = await request.json()

    messages = body.get("messages", [])
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="messages must be a list")

    original_len = 0
    masked_len = 0
    pii_types = set()

    # Redact PII only in user messages
    for msg in messages:
        if not isinstance(msg, dict):
            continue

        content = msg.get("content")
        if not isinstance(content, str):
            continue

        original_len += len(content)

        if msg.get("role") == "user":
            masked_content, detected = redact_pii(content)
            masked_len += len(masked_content)
            msg["content"] = masked_content
            pii_types.update(detected)
        else:
            masked_len += len(content)

    # Update body in-place
    body["messages"] = messages
    # Ollama streams by default; disable streaming so we can parse JSON
    body.setdefault("stream", False)

    # Ollama requires only JSON headers
    headers = {
        "Content-Type": "application/json",
    }

    # Call Ollama chat API
    start = time.time()
    try:
        async with httpx.AsyncClient(base_url=OLLAMA_BASE_URL, timeout=60.0) as client:
            upstream_resp = await client.post("/api/chat", json=body, headers=headers)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Ollama unreachable: {exc}") from exc
    duration = time.time() - start

    if upstream_resp.status_code != 200:
        raise HTTPException(
            status_code=upstream_resp.status_code,
            detail=upstream_resp.text
        )

    try:
        upstream_json = upstream_resp.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama returned invalid JSON: {exc}"
        ) from exc

    response = JSONResponse(content=upstream_json)
    response.headers["X-Request-ID"] = req_id
    response.headers["X-PII-Redacted"] = ",".join(sorted(pii_types)) if pii_types else "none"
    response.headers["X-Original-Length"] = str(original_len)
    response.headers["X-Masked-Length"] = str(masked_len)
    response.headers["X-Latency-Seconds"] = f"{duration:.3f}"

    return response
