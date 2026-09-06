"""FastAPI application factory and exception mapping."""

from fastapi import FastAPI

from app.api import router
from app.config import get_settings
from app.logging import configure_logging
from app.middleware import RequestContextMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    application = FastAPI(
        title="GitHub Issues Gateway",
        version="0.1.0",
        description="Stage 1 contract-first gateway; domain operations are placeholders.",
    )
    application.add_middleware(RequestContextMiddleware)
    application.include_router(router)

    return application


app = create_app()
