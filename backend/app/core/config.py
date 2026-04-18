"""
PetroLedger — Application Configuration.

Uses pydantic-settings v2 for environment-based configuration.
All values are read from environment variables or a .env file.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL connection string (async driver recommended, e.g. postgresql+asyncpg://…)",
    )

    # ── Redis ───────────────────────────────────────────────────────────
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string",
    )

    # ── Auth / JWT ──────────────────────────────────────────────────────
    SECRET_KEY: str = Field(
        ..., description="Secret key used for signing JWTs and other tokens"
    )
    ALGORITHM: str = Field(
        default="HS256", description="JWT signing algorithm"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30, description="Access-token lifetime in minutes"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7, description="Refresh-token lifetime in days"
    )

    # ── Application ─────────────────────────────────────────────────────
    APP_VERSION: str = Field(default="0.1.0", description="Application version string")
    ENABLE_DOCS: bool = Field(
        default=True,
        description="Force-enable Swagger/ReDoc even in production",
    )
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://localhost:5176",
            "http://localhost:5177",
        ],
        description="Allowed CORS origins",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        """Accept wildcard, JSON list, or comma-separated string.

        NoDecode prevents pydantic-settings from JSON-parsing env strings before
        this validator runs, so values like ``*`` or ``https://a.com,https://b.com``
        are accepted directly.
        """
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):
                import json
                return json.loads(s)
            return [origin.strip() for origin in s.split(",") if origin.strip()]
        return v  # type: ignore[return-value]

    # ── Environment ─────────────────────────────────────────────────────
    ENVIRONMENT: Literal["dev", "test", "staging", "prod"] = Field(
        default="dev", description="Current deployment environment"
    )

    # ── AWS / S3 ────────────────────────────────────────────────────────
    AWS_ACCESS_KEY_ID: str = Field(default="", description="AWS access key ID")
    AWS_SECRET_ACCESS_KEY: str = Field(default="", description="AWS secret access key")
    AWS_REGION: str = Field(default="ap-south-1", description="AWS region")
    AWS_SNS_REGION: str = Field(
        default="ap-south-1",
        description="AWS region for SNS (SMS OTP); can differ from S3 region",
    )
    S3_BUCKET: str = Field(default="", description="S3 bucket for file uploads")

    # ── Developer / Superadmin ──────────────────────────────────────────
    SUPERADMIN_EMAIL: str = Field(
        ...,
        description="Email address granted cross-tenant superadmin access. Required; no default.",
    )
    SUPERADMIN_PASSWORD: str = Field(
        default="",
        description="Initial superadmin password seeded at startup (blank = skip seed)",
    )

    # ── Google OAuth ────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = Field(
        default="",
        description="Google OAuth client ID (aud claim on incoming id_token)",
    )
    GOOGLE_CLIENT_SECRET: str = Field(
        default="",
        description="Google OAuth client secret (unused for id_token verify but kept for auth-code flow parity)",
    )

    # ── Observability ───────────────────────────────────────────────────
    SENTRY_DSN: str = Field(default="", description="Sentry DSN for error tracking")

    # ── Email / SMTP ────────────────────────────────────────────────────
    SMTP_HOST: str = Field(default="", description="SMTP server host. Leave blank to skip sending and log to console.")
    SMTP_PORT: int = Field(default=587, description="SMTP server port")
    SMTP_USERNAME: str = Field(default="", description="SMTP username / sender email")
    SMTP_PASSWORD: str = Field(default="", description="SMTP password or app password")
    SMTP_FROM_EMAIL: str = Field(default="", description="From address (defaults to SMTP_USERNAME if blank)")
    SMTP_USE_TLS: bool = Field(default=True, description="Use STARTTLS")

    FRONTEND_OWNER_URL: str = Field(default="http://localhost:5173", description="Owner portal URL")
    FRONTEND_MANAGER_URL: str = Field(default="http://localhost:5174", description="Manager portal URL")
    FRONTEND_ADMIN_URL: str = Field(default="http://localhost:5175", description="Admin portal URL")
    FRONTEND_WORKER_URL: str = Field(default="http://localhost:5176", description="Worker portal URL")
    FRONTEND_DEVPORTAL_URL: str = Field(default="http://localhost:5177", description="Developer portal URL")

    INVITE_EXPIRY_HOURS: int = Field(default=48, description="Invite expiry in hours")

    # ── Celery ──────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = Field(
        default="",
        description="Celery broker URL. Falls back to REDIS_URL if empty.",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def celery_broker(self) -> str:
        """Resolved Celery broker — falls back to REDIS_URL when not set."""
        return self.CELERY_BROKER_URL or self.REDIS_URL

    # ── Helpers ─────────────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "prod"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "dev"

    @property
    def show_docs(self) -> bool:
        """Whether to enable Swagger/ReDoc UI."""
        return self.ENABLE_DOCS or not self.is_production


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance (singleton per process)."""
    return Settings()  # type: ignore[call-arg]


def clear_settings_cache() -> None:
    """Evict the cached :class:`Settings` so the next call re-reads env vars."""
    get_settings.cache_clear()