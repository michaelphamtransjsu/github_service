from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/healthz", headers={"X-Request-ID": "test-request"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"] == "test-request"


def test_request_id_is_generated() -> None:
    response = client.get("/healthz")

    assert response.headers["X-Request-ID"]


def test_stage_two_route_is_typed_placeholder() -> None:
    response = client.get("/issues")

    assert response.status_code == 501
    assert response.json()["error"]["code"] == "not_implemented"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
