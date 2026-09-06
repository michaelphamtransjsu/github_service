import hashlib
import hmac
import json

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api import get_event_store
from app.config import get_settings
from app.events import EventStore
from app.main import app


def signed_headers(body, event="issues", delivery="delivery-1", secret=b"unit-secret"):
    signature = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    return {
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": delivery,
        "X-Hub-Signature-256": signature,
        "Content-Type": "application/json",
    }


def setup(tmp_path):
    store = EventStore(f"sqlite:///{tmp_path / 'events.db'}")
    app.dependency_overrides[get_event_store] = lambda: store
    settings = get_settings()
    original = (settings.GITHUB_WEBHOOK_SECRET, settings.WEBHOOK_MAX_BODY_BYTES)
    settings.GITHUB_WEBHOOK_SECRET = SecretStr("unit-secret")
    return TestClient(app), store, settings, original


def teardown(settings, original):
    settings.GITHUB_WEBHOOK_SECRET, settings.WEBHOOK_MAX_BODY_BYTES = original
    app.dependency_overrides.clear()


def test_valid_issue_and_comment_metadata_duplicates_and_logging(tmp_path, caplog):
    client, store, settings, original = setup(tmp_path)
    try:
        for event, action, delivery in [
            ("issues", "opened", "one"),
            ("issue_comment", "created", "two"),
        ]:
            body = json.dumps(
                {"action": action, "issue": {"number": 42}, "body": "must not log"}
            ).encode()
            headers = signed_headers(body, event, delivery)
            assert client.post("/webhook", content=body, headers=headers).status_code == 204
            assert client.post("/webhook", content=body, headers=headers).status_code == 204
        result = client.get("/events").json()
        assert len(result) == 2
        assert set(result[0]) == {"id", "event", "action", "issue_number", "timestamp"}
        assert result[0]["issue_number"] == 42
        deliveries = [
            record for record in caplog.records if record.name == "github_service.webhook"
        ]
        assert deliveries
        assert all(
            hasattr(deliveries[0], value) for value in ["delivery_id", "event_type", "duplicate"]
        )
        text = caplog.text
        assert "must not log" not in text and "sha256=" not in text and "unit-secret" not in text
        assert len(EventStore(f"sqlite:///{tmp_path / 'events.db'}").list()) == 2
    finally:
        teardown(settings, original)


def test_ping_and_invalid_json_shapes_events_actions(tmp_path):
    client, store, settings, original = setup(tmp_path)
    try:
        for body, event, status in [
            (b"{", "ping", 400),
            (b"[]", "ping", 400),
            (b"{}", "unknown", 400),
            (b'{"action":"bad"}', "issues", 400),
        ]:
            response = client.post("/webhook", content=body, headers=signed_headers(body, event))
            assert (
                response.status_code == status
                and response.json()["error"]["code"] == "request_error"
            )
        body = b'{"zen":"safe"}'
        assert (
            client.post("/webhook", content=body, headers=signed_headers(body, "ping")).status_code
            == 204
        )
    finally:
        teardown(settings, original)


def test_missing_malformed_incorrect_and_tampered_signatures(tmp_path):
    client, store, settings, original = setup(tmp_path)
    body = b"{}"
    try:
        valid = signed_headers(body, "ping")
        cases = [
            {k: v for k, v in valid.items() if k != "X-Hub-Signature-256"},
            {**valid, "X-Hub-Signature-256": "bad"},
            {**valid, "X-Hub-Signature-256": "sha256=" + "z" * 64},
            {**valid, "X-Hub-Signature-256": "sha256=" + "0" * 64},
        ]
        for headers in cases:
            assert client.post("/webhook", content=body, headers=headers).status_code == 401
        assert client.post("/webhook", content=body + b" ", headers=valid).status_code == 401
    finally:
        teardown(settings, original)


def test_oversized_webhook(tmp_path):
    client, store, settings, original = setup(tmp_path)
    try:
        settings.WEBHOOK_MAX_BODY_BYTES = 3
        body = b"{}  "
        assert (
            client.post("/webhook", content=body, headers=signed_headers(body, "ping")).status_code
            == 413
        )
    finally:
        teardown(settings, original)
