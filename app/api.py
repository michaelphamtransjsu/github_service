"""Stage 1 API routes: health is functional; domain routes are placeholders."""

from typing import Annotated

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse

from app.models import HealthResponse

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse()


def not_implemented(request: Request) -> JSONResponse:
    request_id = request.state.request_id
    response = JSONResponse(
        status_code=501,
        content={
            "error": {
                "code": "not_implemented",
                "message": "This operation is reserved for a later project stage.",
                "request_id": request_id,
            }
        },
    )
    return response


@router.api_route("/issues", methods=["GET", "POST"], include_in_schema=False)
async def issues_placeholder(
    request: Request,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 30,
) -> JSONResponse:
    return not_implemented(request)


@router.api_route(
    "/issues/{issue_number}", methods=["GET", "PATCH", "DELETE"], include_in_schema=False
)
async def issue_placeholder(request: Request, issue_number: int) -> JSONResponse:
    return not_implemented(request)


@router.api_route(
    "/issues/{issue_number}/comments", methods=["GET", "POST"], include_in_schema=False
)
async def comments_placeholder(request: Request, issue_number: int) -> JSONResponse:
    return not_implemented(request)


@router.api_route(
    "/issues/{issue_number}/comments/{comment_id}",
    methods=["PATCH", "DELETE"],
    include_in_schema=False,
)
async def comment_placeholder(
    request: Request, issue_number: int, comment_id: int
) -> JSONResponse:
    return not_implemented(request)


@router.post("/webhooks/github", include_in_schema=False)
async def webhook_placeholder(
    request: Request,
    x_github_event: Annotated[str, Header()],
    x_github_delivery: Annotated[str, Header()],
    x_hub_signature_256: Annotated[str, Header()],
) -> JSONResponse:
    return not_implemented(request)
