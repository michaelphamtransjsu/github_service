from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api import get_github_client
from app.main import app

NOW = datetime.now(UTC).isoformat()
USER = {"login": "octo", "id": 1, "avatar_url": "https://example.com/avatar"}
ISSUE = {
    "number": 7,
    "title": "test",
    "body": None,
    "state": "open",
    "html_url": "https://example.com/issues/7",
    "user": USER,
    "labels": [],
    "assignees": [],
    "created_at": NOW,
    "updated_at": NOW,
}
COMMENT = {
    "id": 9,
    "body": "hello",
    "html_url": "https://example.com/comments/9",
    "user": USER,
    "created_at": NOW,
    "updated_at": NOW,
}


class FakeGitHub:
    async def create_issue(self, payload):
        return {**ISSUE, "title": payload["title"]}

    async def list_issues(self, state, page, per_page):
        return [ISSUE], '<next>; rel="next"'

    async def get_issue(self, number):
        return {**ISSUE, "number": number}

    async def update_issue(self, number, payload):
        return {**ISSUE, "number": number, **payload}

    async def create_comment(self, number, payload):
        return {**COMMENT, **payload}

    async def list_comments(self, number, page, per_page):
        return [COMMENT], '<next>; rel="next"'


@pytest.fixture
def client():
    app.dependency_overrides[get_github_client] = lambda: FakeGitHub()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_issue_crud_success_location_and_links(client):
    created = client.post("/issues", json={"title": "new"})
    assert created.status_code == 201
    assert created.headers["location"] == "/issues/7"
    listed = client.get("/issues")
    assert listed.status_code == 200 and listed.headers["link"] == '<next>; rel="next"'
    assert listed.json()["items"][0]["number"] == 7
    assert client.get("/issues/7").status_code == 200
    assert client.patch("/issues/7", json={"title": "changed"}).json()["title"] == "changed"


@pytest.mark.parametrize("state", ["closed", "open"])
def test_close_and_reopen(client, state):
    response = client.patch("/issues/7", json={"state": state})
    assert response.status_code == 200 and response.json()["state"] == state


def test_comment_create_and_list(client):
    assert client.post("/issues/7/comments", json={"body": "made"}).status_code == 201
    response = client.get("/issues/7/comments")
    assert response.status_code == 200 and response.headers["link"] == '<next>; rel="next"'


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/issues", {}),
        ("post", "/issues", {"title": ""}),
        ("patch", "/issues/7", {}),
        ("patch", "/issues/7", {"state": "invalid"}),
        ("get", "/issues?state=invalid", None),
        ("get", "/issues?page=0", None),
    ],
)
def test_payload_and_query_validation_is_structured_400(client, method, path, body):
    response = client.request(method, path, json=body)
    assert response.status_code == 400
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
