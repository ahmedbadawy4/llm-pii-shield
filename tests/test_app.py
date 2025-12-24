import importlib
from typing import Dict
from typing import Tuple

import httpx
import pytest
from fastapi.testclient import TestClient

from src import config

app_module = importlib.import_module("src.app")


def _make_settings(db_path) -> config.Settings:
    return config.Settings(
        ollama_base_url="http://ollama.invalid",
        database_path=db_path,
        log_level="INFO",
        redact_assistant=False,
        admin_api_key="test-key",
        llm_provider="ollama",
        azure_openai_endpoint=None,
        azure_openai_deployment=None,
        allowed_models=None,
    )


@pytest.fixture
def client_with_stub(monkeypatch, tmp_path) -> Tuple[TestClient, Dict]:
    captured: Dict = {}

    async def fake_chat_completion(base_url, payload):
        captured["payload"] = payload
        return httpx.Response(
            status_code=200,
            json={"model": "dummy", "message": {"role": "assistant", "content": "ok"}},
            request=httpx.Request("POST", "http://ollama.invalid/api/chat"),
        )

    monkeypatch.setattr(
        app_module.adapters.ollama_client, "chat_completion", fake_chat_completion
    )

    settings = _make_settings(tmp_path / "audit.db")
    app = app_module.create_app(settings)
    return TestClient(app), captured


def test_chat_completion_redacts_and_sets_headers(client_with_stub):
    client, captured = client_with_stub
    body = {
        "model": "llama3.1:8b",
        "messages": [
            {
                "role": "user",
                "content": "Email me at jane.doe@example.com and call (555) 123-4567",
            }
        ],
    }

    resp = client.post("/v1/chat/completions", json=body)

    assert resp.status_code == 200
    assert resp.headers["X-PII-Redacted"] == "email,phone"
    assert resp.headers["X-Original-Length"].isdigit()
    assert resp.headers["X-Masked-Length"].isdigit()
    masked = captured["payload"]["messages"][0]["content"]
    assert "[REDACTED_EMAIL]" in masked
    assert "[REDACTED_PHONE]" in masked
    assert captured["payload"]["stream"] is False


def test_chat_completion_forces_stream_false_when_missing(client_with_stub):
    client, captured = client_with_stub
    body = {
        "model": "llama3.1:8b",
        "messages": [{"role": "user", "content": "just text"}],
    }

    resp = client.post("/v1/chat/completions", json=body)

    assert resp.status_code == 200
    assert captured["payload"]["stream"] is False


def test_metrics_exposed(client_with_stub):
    client, _ = client_with_stub
    body = {
        "model": "llama3.1:8b",
        "messages": [{"role": "user", "content": "Email me at a@b.com"}],
    }
    client.post("/v1/chat/completions", json=body)

    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert "pii_shield_chat_requests_total" in metrics_resp.text
    assert "pii_shield_chat_latency_seconds" in metrics_resp.text
    assert "pii_shield_upstream_latency_seconds" in metrics_resp.text
    assert "pii_shield_pii_redactions_total" in metrics_resp.text
    assert "pii_shield_blocked_requests_total" in metrics_resp.text
    assert "pii_shield_chat_errors_total" in metrics_resp.text


def test_logs_do_not_include_raw_pii(client_with_stub, caplog):
    client, _ = client_with_stub
    caplog.set_level("INFO", logger="pii_shield")
    body = {
        "model": "llama3.1:8b",
        "messages": [
            {
                "role": "user",
                "content": "Email me at jane.doe@example.com and call (555) 123-4567",
            }
        ],
    }

    resp = client.post("/v1/chat/completions", json=body)

    assert resp.status_code == 200
    payload = resp.json()
    assistant_content = ""
    if isinstance(payload, dict):
        message = payload.get("message", {})
        if isinstance(message, dict):
            assistant_content = message.get("content") or ""
    assert "jane.doe@example.com" not in assistant_content
    assert "(555) 123-4567" not in assistant_content
    assert "jane.doe@example.com" not in caplog.text
    assert "(555) 123-4567" not in caplog.text


def test_policy_deny_blocks_request(tmp_path):
    settings = _make_settings(tmp_path / "audit.db")
    settings.allowed_models = ["llama3.1:8b"]
    app = app_module.create_app(settings)
    client = TestClient(app)
    body = {
        "model": "blocked-model",
        "messages": [{"role": "user", "content": "Email me at a@b.com"}],
    }

    resp = client.post("/v1/chat/completions", json=body)

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Model not allowed by policy."


def test_upstream_error_is_propagated(monkeypatch, tmp_path):
    async def failing_chat_completion(base_url, payload):
        return httpx.Response(
            status_code=502,
            text="upstream bad",
            request=httpx.Request("POST", "http://ollama.invalid/api/chat"),
        )

    monkeypatch.setattr(
        app_module.adapters.ollama_client, "chat_completion", failing_chat_completion
    )
    client = TestClient(app_module.create_app(_make_settings(tmp_path / "audit.db")))

    resp = client.post(
        "/v1/chat/completions",
        json={"model": "llama3.1:8b", "messages": [{"role": "user", "content": "x"}]},
    )

    assert resp.status_code == 502
    assert resp.json()["detail"] == "upstream bad"


def test_admin_stats_tracks_requests(monkeypatch, tmp_path):
    captured: Dict = {}

    async def fake_chat_completion(base_url, payload):
        captured.setdefault("payloads", []).append(payload)
        return httpx.Response(
            status_code=200,
            json={"model": "dummy", "message": {"role": "assistant", "content": "ok"}},
            request=httpx.Request("POST", "http://ollama.invalid/api/chat"),
        )

    monkeypatch.setattr(
        app_module.adapters.ollama_client, "chat_completion", fake_chat_completion
    )
    client = TestClient(app_module.create_app(_make_settings(tmp_path / "audit.db")))

    client.post(
        "/v1/chat/completions",
        json={
            "model": "llama3.1:8b",
            "messages": [
                {
                    "role": "user",
                    "content": "Email jane@example.com and call 555-123-4567",
                }
            ],
        },
    )
    client.post(
        "/v1/chat/completions",
        json={
            "model": "llama3.1:8b",
            "messages": [
                {
                    "role": "user",
                    "content": "Card 4111-1111-1111-1111 and SSN 123-45-6789",
                }
            ],
        },
    )

    stats_resp = client.get("/admin/stats", headers={"X-Admin-Key": "test-key"})

    assert stats_resp.status_code == 200
    payload = stats_resp.json()
    assert payload["total_requests"] == 2
    assert payload["pii_counts"]["email"] == 1
    assert payload["pii_counts"]["phone"] == 1
    assert payload["pii_counts"]["credit_card"] == 1
    assert payload["pii_counts"]["ssn"] == 1
    assert payload["recent_events"]
