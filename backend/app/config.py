from __future__ import annotations

from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Aether application settings loaded from environment variables (AETHER_ prefix) or .env file."""

    model_config = SettingsConfigDict(
        env_prefix="AETHER_",
        env_file=".env",  # DO NOT commit .env — use .env.example for defaults
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/aether",
        description="Async SQLAlchemy database URL",
    )

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # ── JWT ───────────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(
        ...,
        description="Secret key for signing JWT tokens (REQUIRED — no default)",
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=1)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30, ge=1)

    # ── Magic Link ────────────────────────────────────────────
    MAGIC_LINK_EXPIRE_MINUTES: int = Field(default=15, ge=1)
    FRONTEND_URL: str = Field(
        default="http://localhost:3000",
        description="Frontend base URL for magic link generation",
    )

    # ── Encryption ────────────────────────────────────────────
    ENCRYPTION_KEY: str = Field(
        default="",
        description="AES-256-GCM key (base64) for encrypting credentials at rest",
    )

    # ── CORS ──────────────────────────────────────────────────
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated CORS origins",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # ── Environment ───────────────────────────────────────────
    ENVIRONMENT: str = Field(
        default="development",
        pattern="^(development|test|production)$",
        description="Runtime environment",
    )


# Singleton — imported once and reused everywhere.
settings: Settings = Settings()
