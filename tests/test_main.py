from fastapi.testclient import TestClient

from src import main


def test_chat_completions_masks_pii(monkeypatch):
    captured = {}

    class DummyResponse:
        status_code = 200

        def json(self):
            return {"model": "dummy", "message": {"role": "assistant", "content": "ok"}, "done": True}

        @property
        def text(self):
            return '{"model":"dummy","done":true}'

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

        async def post(self, path, json, headers):
            captured["payload"] = json
            return DummyResponse()

    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    client = TestClient(main.app)
    body = {
        "model": "llama3.1:8b",
        "messages": [{"role": "user", "content": "My IBAN is DE89370400440532013000"}],
    }
    resp = client.post("/v1/chat/completions", json=body)

    assert resp.status_code == 200
    assert resp.headers["X-PII-Redacted"] == "iban"
    assert "[REDACTED_IBAN]" in captured["payload"]["messages"][0]["content"]
    assert captured["payload"]["stream"] is False
