import hashlib
import hmac

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api import get_event_store
from app.config import get_settings
from app.events import EventStore
from app.main import app


def test_valid_duplicate_invalid_and_tampered_webhooks(tmp_path) -> None:
    store = EventStore(f"sqlite:///{tmp_path / 'events.db'}")
    app.dependency_overrides[get_event_store] = lambda: store
    settings = get_settings()
    original = settings.GITHUB_WEBHOOK_SECRET
    settings.GITHUB_WEBHOOK_SECRET = SecretStr("unit-secret")
    body = b'{"zen":"safe"}'
    signature = "sha256=" + hmac.new(b"unit-secret", body, hashlib.sha256).hexdigest()
    headers = {
        "X-GitHub-Event": "ping",
        "X-GitHub-Delivery": "delivery-1",
        "X-Hub-Signature-256": signature,
        "Content-Type": "application/json",
    }
    try:
        client = TestClient(app)
        assert client.post("/webhook", content=body, headers=headers).status_code == 204
        assert client.post("/webhook", content=body, headers=headers).status_code == 204
        assert len(client.get("/events").json()) == 1
        bad = {**headers, "X-Hub-Signature-256": "sha256=" + "0" * 64}
        assert client.post("/webhook", content=body, headers=bad).status_code == 401
        assert client.post("/webhook", content=body + b" ", headers=headers).status_code == 401
    finally:
        settings.GITHUB_WEBHOOK_SECRET = original
        app.dependency_overrides.clear()
