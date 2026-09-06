"""Shared transport models used by routes and the API contract."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictModel):
    status: Literal["ok"] = "ok"


class ErrorDetail(StrictModel):
    code: str
    message: str
    request_id: str
    details: dict[str, Any] | None = None


class ErrorResponse(StrictModel):
    error: ErrorDetail


class User(StrictModel):
    login: str
    id: int
    avatar_url: HttpUrl


class IssueCreate(StrictModel):
    title: str = Field(min_length=1, max_length=256)
    body: str | None = None
    labels: list[str] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)


class IssueUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    body: str | None = None
    state: Literal["open", "closed"] | None = None
    labels: list[str] | None = None
    assignees: list[str] | None = None


class Issue(StrictModel):
    number: int
    title: str
    body: str | None
    state: Literal["open", "closed"]
    html_url: HttpUrl
    user: User
    labels: list[str]
    assignees: list[User]
    created_at: datetime
    updated_at: datetime


class IssueList(StrictModel):
    items: list[Issue]
    page: int
    per_page: int


class CommentCreate(StrictModel):
    body: str = Field(min_length=1)


class CommentUpdate(StrictModel):
    body: str = Field(min_length=1)


class Comment(StrictModel):
    id: int
    body: str
    html_url: HttpUrl
    user: User
    created_at: datetime
    updated_at: datetime


class CommentList(StrictModel):
    items: list[Comment]
    page: int
    per_page: int


class WebhookAccepted(StrictModel):
    delivery_id: str
    status: Literal["accepted"] = "accepted"
