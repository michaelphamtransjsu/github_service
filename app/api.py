"""HTTP API routes."""

import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request, Response

from app.config import get_settings
from app.events import EventStore
from app.github import GitHubClient
from app.models import (
    Comment,
    CommentCreate,
    CommentList,
    HealthResponse,
    Issue,
    IssueCreate,
    IssueList,
    IssueUpdate,
)

router = APIRouter()


async def get_github_client() -> AsyncIterator[GitHubClient]:
    client = GitHubClient(get_settings())
    try:
        yield client
    finally:
        await client.close()


def get_event_store() -> EventStore:
    return EventStore(get_settings().DATABASE_URL)


@router.get("/healthz", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse()


@router.post("/issues", response_model=Issue, status_code=201, tags=["issues"])
async def create_issue(body: IssueCreate, client: GitHubClient = Depends(get_github_client)) -> Any:
    return await client.create_issue(body.model_dump(exclude_none=True))


@router.get("/issues", response_model=IssueList, tags=["issues"])
async def list_issues(
    response: Response,
    state: Literal["open", "closed", "all"] = "open",
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 30,
    client: GitHubClient = Depends(get_github_client),
) -> IssueList:
    items, link = await client.list_issues(state, page, per_page)
    if link:
        response.headers["Link"] = link
    return IssueList(items=items, page=page, per_page=per_page)


@router.get("/issues/{issue_number}", response_model=Issue, tags=["issues"])
async def get_issue(
    issue_number: Annotated[int, Path(ge=1)], client: GitHubClient = Depends(get_github_client)
) -> Any:
    return await client.get_issue(issue_number)


@router.patch("/issues/{issue_number}", response_model=Issue, tags=["issues"])
async def update_issue(
    issue_number: Annotated[int, Path(ge=1)],
    body: IssueUpdate,
    client: GitHubClient = Depends(get_github_client),
) -> Any:
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "At least one field must be supplied.")
    return await client.update_issue(issue_number, changes)


@router.post(
    "/issues/{issue_number}/comments", response_model=Comment, status_code=201, tags=["comments"]
)
async def create_comment(
    issue_number: Annotated[int, Path(ge=1)],
    body: CommentCreate,
    client: GitHubClient = Depends(get_github_client),
) -> Any:
    return await client.create_comment(issue_number, body.model_dump())


@router.get("/issues/{issue_number}/comments", response_model=CommentList, tags=["comments"])
async def list_comments(
    response: Response,
    issue_number: Annotated[int, Path(ge=1)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 30,
    client: GitHubClient = Depends(get_github_client),
) -> CommentList:
    items, link = await client.list_comments(issue_number, page, per_page)
    if link:
        response.headers["Link"] = link
    return CommentList(items=items, page=page, per_page=per_page)


KNOWN_ACTIONS = {
    "issues": {
        "opened",
        "edited",
        "deleted",
        "transferred",
        "pinned",
        "unpinned",
        "closed",
        "reopened",
        "assigned",
        "unassigned",
        "labeled",
        "unlabeled",
        "locked",
        "unlocked",
        "milestoned",
        "demilestoned",
    },
    "issue_comment": {"created", "edited", "deleted"},
}


@router.post("/webhook", status_code=204, tags=["webhooks"])
async def webhook(
    request: Request,
    x_github_event: Annotated[str, Header(min_length=1)],
    x_github_delivery: Annotated[str, Header(min_length=1)],
    x_hub_signature_256: Annotated[str, Header(pattern=r"^sha256=[0-9a-f]{64}$")],
    store: EventStore = Depends(get_event_store),
) -> Response:
    secret = get_settings().GITHUB_WEBHOOK_SECRET
    if secret is None:
        raise HTTPException(503, "Webhook integration is not configured.")
    raw = await request.body()
    expected = (
        "sha256=" + hmac.new(secret.get_secret_value().encode(), raw, hashlib.sha256).hexdigest()
    )
    if not hmac.compare_digest(expected, x_hub_signature_256):
        raise HTTPException(401, "Invalid webhook signature.")
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(400, "Webhook body must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(400, "Webhook body must be an object.")
    if x_github_event not in {"ping", *KNOWN_ACTIONS}:
        raise HTTPException(422, "Unsupported webhook event.")
    action = payload.get("action")
    if x_github_event in KNOWN_ACTIONS and action not in KNOWN_ACTIONS[x_github_event]:
        raise HTTPException(422, "Unsupported webhook action.")
    store.add(x_github_delivery, x_github_event, action, payload)
    return Response(status_code=204)


@router.get("/events", tags=["webhooks"])
async def list_events(
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    store: EventStore = Depends(get_event_store),
) -> list[dict[str, Any]]:
    return store.list(limit)
