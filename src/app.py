import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Set

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .clients import ollama as ollama_client
from .config import Settings, load_settings
from .pii import redact_pii
from . import storage


def setup_logger(log_level: str) -> logging.Logger:
    logger = logging.getLogger("pii_shield")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(log_level.upper())
    logger.propagate = False
    return logger


def log_metadata(logger: logging.Logger, payload: dict) -> None:
    logger.info(json.dumps(payload))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    logger = setup_logger(settings.log_level)
    storage.init_db(settings.database_path)

    app = FastAPI(title="LLM Privacy/PII Shield")

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")

        @app.get("/", include_in_schema=False)
        async def root():
            return RedirectResponse(url="/ui/")

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        req_id = str(uuid.uuid4())
        body = await request.json()

        messages = body.get("messages", [])
        if not isinstance(messages, list):
            raise HTTPException(status_code=400, detail="messages must be a list")

        original_len = 0
        masked_len = 0
        pii_types: Set[str] = set()

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

        body["messages"] = messages
        body.setdefault("stream", False)

        start = time.time()
        try:
            upstream_resp = await ollama_client.chat_completion(settings.ollama_base_url, body)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Ollama unreachable: {exc}") from exc
        duration = time.time() - start

        if upstream_resp.status_code != 200:
            raise HTTPException(
                status_code=upstream_resp.status_code,
                detail=upstream_resp.text,
            )

        try:
            upstream_json = upstream_resp.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Ollama returned invalid JSON: {exc}",
            ) from exc

        pii_list = sorted(pii_types)
        response = JSONResponse(content=upstream_json)
        response.headers["X-Request-ID"] = req_id
        response.headers["X-PII-Redacted"] = ",".join(pii_list) if pii_list else "none"
        response.headers["X-Original-Length"] = str(original_len)
        response.headers["X-Masked-Length"] = str(masked_len)
        response.headers["X-Latency-Seconds"] = f"{duration:.3f}"

        timestamp = datetime.now(timezone.utc).isoformat()
        client_ip = request.client.host if request.client else None
        audit_payload = {
            "id": req_id,
            "timestamp": timestamp,
            "pii_types": pii_list,
            "model": body.get("model"),
            "latency": duration,
            "original_length": original_len,
            "masked_length": masked_len,
            "client_ip": client_ip,
        }

        storage.record_request(settings.database_path, audit_payload)
        log_metadata(
            logger,
            {
                "event": "request.completed",
                **audit_payload,
            },
        )

        return response

    @app.get("/admin/stats")
    async def admin_stats(limit: int = 20):
        limited = max(1, min(limit, 100))
        return storage.fetch_stats(settings.database_path, limited)

    return app


app = create_app()
