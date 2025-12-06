import json
import sys
from pathlib import Path
from typing import Dict, Tuple

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest
from fastapi.testclient import TestClient

from src import config, app as app_module


class DummyResponse:
    status_code = 200

    def json(self):
        return {"model": "dummy", "message": {"role": "assistant", "content": "ok"}, "done": True}

    @property
    def text(self):
        return json.dumps(self.json())


@pytest.fixture
def client_with_stub(monkeypatch, tmp_path) -> Tuple[TestClient, Dict]:
    captured: Dict = {}

    async def fake_chat_completion(base_url, payload):
        captured["payload"] = payload
        return DummyResponse()

    monkeypatch.setattr(app_module.ollama_client, "chat_completion", fake_chat_completion)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.invalid")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    settings = config.load_settings()
    app = app_module.create_app(settings)
    return TestClient(app), captured


def test_chat_completions_masks_pii(client_with_stub):
    client, captured = client_with_stub
    body = {
        "model": "llama3.1:8b",
        "messages": [{"role": "user", "content": "My IBAN is DE89370400440532013000"}],
    }
    resp = client.post("/v1/chat/completions", json=body)

    assert resp.status_code == 200
    assert resp.headers["X-PII-Redacted"] == "iban"
    assert "[REDACTED_IBAN]" in captured["payload"]["messages"][0]["content"]
    assert captured["payload"]["stream"] is False


def test_redacts_multiple_and_mixed_pii(client_with_stub):
    client, captured = client_with_stub
    body = {
        "model": "llama3.1:8b",
        "messages": [
            {
                "role": "user",
                "content": (
                    "Email me at jane.doe@example.com or call (555) 123-4567. "
                    "Card: 4111-1111-1111-1111"
                ),
            }
        ],
    }
    resp = client.post("/v1/chat/completions", json=body)

    assert resp.status_code == 200
    assert resp.headers["X-PII-Redacted"] == "credit_card,email,phone"
    masked = captured["payload"]["messages"][0]["content"]
    assert "[REDACTED_EMAIL]" in masked
    assert "[REDACTED_PHONE]" in masked
    assert "[REDACTED_CARD]" in masked


def test_does_not_over_redact_invalid_email(client_with_stub):
    client, captured = client_with_stub
    body = {
        "model": "llama3.1:8b",
        "messages": [{"role": "user", "content": "This looks like an email not@valid but is not."}],
    }
    resp = client.post("/v1/chat/completions", json=body)

    assert resp.status_code == 200
    assert resp.headers["X-PII-Redacted"] == "none"
    assert captured["payload"]["messages"][0]["content"] == body["messages"][0]["content"]


def test_admin_stats_counts_requests(client_with_stub):
    client, _ = client_with_stub
    body = {
        "model": "llama3.1:8b",
        "messages": [{"role": "user", "content": "Email me at jane@example.com and call 555-123-4567"}],
    }
    post_resp = client.post("/v1/chat/completions", json=body)
    assert post_resp.status_code == 200

    stats_resp = client.get("/admin/stats")
    assert stats_resp.status_code == 200

    payload = stats_resp.json()
    assert payload["total_requests"] == 1
    assert payload["pii_counts"].get("email") == 1
    assert payload["pii_counts"].get("phone") == 1
    assert payload["recent_events"]
