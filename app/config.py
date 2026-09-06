"""Environment-backed application configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from fixed, uppercase environment variable names."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_ENV: Literal["development", "test", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    DATABASE_URL: str = "sqlite:///./github_service.db"
    GITHUB_TOKEN: SecretStr | None = None
    GITHUB_OWNER: str | None = None
    GITHUB_REPO: str | None = None
    GITHUB_WEBHOOK_SECRET: SecretStr | None = None
    GITHUB_API_URL: str = "https://api.github.com"


@lru_cache
def get_settings() -> Settings:
    """Return one immutable-by-convention settings instance per process."""

    return Settings()
