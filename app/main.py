"""FastAPI application factory and exception mapping."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import router
from app.config import get_settings
from app.github import GitHubError
from app.logging import configure_logging
from app.middleware import RequestContextMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    application = FastAPI(
        title="GitHub Issues Gateway",
        version="0.1.0",
        description="Gateway for repository issues and signed GitHub webhook events.",
    )
    application.add_middleware(RequestContextMiddleware)
    application.include_router(router)

    def error(request: Request, status: int, code: str, message: str, details=None):
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": request.state.request_id,
                    **({"details": details} if details else {}),
                }
            },
        )

    @application.exception_handler(GitHubError)
    async def github_error(request: Request, exc: GitHubError):
        return error(request, exc.status_code, exc.code, exc.message, exc.details)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error(request, exc.status_code, "request_error", str(exc.detail))

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return error(
            request, 422, "validation_error", "Request validation failed.", {"errors": exc.errors()}
        )

    return application


app = create_app()
