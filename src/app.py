import json
import logging
import secrets
import time
import uuid
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Set

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.staticfiles import StaticFiles
import os

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client import Counter
from prometheus_client import Histogram
from prometheus_client import generate_latest

from . import storage
from .clients import adapters
from .config import Settings
from .config import load_settings
from .pii import redact_pii
from .schemas import ChatCompletionRequest

CHAT_REQUEST_COUNT = Counter(
    "pii_shield_chat_requests_total",
    "Count of chat completion requests processed",
    ["status"],
)
CHAT_LATENCY = Histogram(
    "pii_shield_chat_latency_seconds",
    "Latency for chat completion requests in seconds",
)


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
    provider_adapter = adapters.build_adapter(settings)

    app = FastAPI(title="LLM Privacy/PII Shield")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:30081",
            "http://127.0.0.1:30081",
            "http://localhost:30080",
            "http://127.0.0.1:30080",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    serve_ui = os.getenv("SERVE_UI", "false").strip().lower() in {"1", "true", "yes", "on"}
    ui_dir = Path(__file__).resolve().parent.parent / "ui"
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if serve_ui:
        if ui_dir.exists():
            app.mount("/ui", StaticFiles(directory=ui_dir, html=True), name="ui")
        elif static_dir.exists():
            app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")

        if ui_dir.exists() or static_dir.exists():
            @app.get("/", include_in_schema=False)
            async def root():
                return RedirectResponse(url="/ui/")

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request, body: ChatCompletionRequest):
        req_id = str(uuid.uuid4())
        payload = body.to_payload()
        messages = body.messages

        original_len = 0
        masked_len = 0
        pii_types: Set[str] = set()

        normalized_messages = []
        for msg in messages:
            msg_dict = msg.model_dump()
            content = msg_dict.get("content")
            role = msg_dict.get("role")

            if not isinstance(content, str):
                normalized_messages.append(msg_dict)
                continue

            original_len += len(content)

            should_mask = role == "user" or (
                settings.redact_assistant and role == "assistant"
            )
            if should_mask:
                masked_content, detected = redact_pii(content)
                masked_len += len(masked_content)
                msg_dict["content"] = masked_content
                pii_types.update(detected)
            else:
                masked_len += len(content)

            normalized_messages.append(msg_dict)

        payload["messages"] = normalized_messages

        start = time.time()
        try:
            upstream_resp = await provider_adapter.chat_completion(payload)
        except NotImplementedError as exc:
            CHAT_REQUEST_COUNT.labels(status="error").inc()
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except Exception as exc:
            CHAT_REQUEST_COUNT.labels(status="error").inc()
            raise HTTPException(
                status_code=502, detail=f"Upstream unreachable: {exc}"
            ) from exc
        duration = time.time() - start

        if upstream_resp.status_code != 200:
            CHAT_REQUEST_COUNT.labels(status="error").inc()
            raise HTTPException(
                status_code=upstream_resp.status_code,
                detail=upstream_resp.text,
            )

        try:
            upstream_json = upstream_resp.json()
        except ValueError as exc:
            CHAT_REQUEST_COUNT.labels(status="error").inc()
            raise HTTPException(
                status_code=502,
                detail=f"Ollama returned invalid JSON: {exc}",
            ) from exc

        CHAT_LATENCY.observe(duration)
        CHAT_REQUEST_COUNT.labels(status="success").inc()

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
            "model": payload.get("model"),
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
    async def admin_stats(request: Request, limit: int = 20):
        if not settings.admin_api_key:
            raise HTTPException(
                status_code=503,
                detail="Admin stats disabled; set ADMIN_API_KEY to enable.",
            )
        provided_key = request.headers.get("X-Admin-Key")
        if not provided_key or not secrets.compare_digest(
            provided_key, settings.admin_api_key
        ):
            raise HTTPException(status_code=401, detail="Invalid admin key.")
        limited = max(1, min(limit, 100))
        return storage.fetch_stats(settings.database_path, limited)

    return app


app = create_app()
