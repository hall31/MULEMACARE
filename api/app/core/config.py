"""Settings Mutuelle OS."""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./mulemacare_os.db"
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = 60 * 24
    mcare_enabled: bool = False
    stripe_secret_key: str = ""
    fernet_key: str = ""  # Encryption key for PII health data
    environment: str = "development"  # development|staging|production

    # MCare AI — Claude API configuration
    anthropic_api_key: str = ""  # Claude API key (set via ANTHROPIC_API_KEY env var)

    # HealthOS bridge — OFF by default, read-only eligibility only when enabled
    mulemacare_healthos_bridge_enabled: bool = False
    healthos_base_url: str = ""  # e.g., https://api.healthos.com
    healthos_partner_api_key: str = ""  # HMAC-SHA256 signing key
    healthos_timeout_ms: int = 5000  # Request timeout in milliseconds
    healthos_pilot_tenant: str = "mulemacare"  # Only this tenant can call bridge
    redis_url: str = "redis://localhost:6379/0"  # Nonce cache (anti-replay)

    @field_validator("jwt_secret", mode="before")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if not v:
            v = os.getenv("JWT_SECRET", "").strip()

        env = os.getenv("ENVIRONMENT", "development").lower()

        # Production requires JWT_SECRET
        if env == "production" and not v:
            raise ValueError("JWT_SECRET must be set via environment variable in production (min 32 characters)")

        # Development: allow dev-only default if not provided
        if not v:
            if env == "development":
                logger.warning("JWT_SECRET not set — using dev-only default (INSECURE for production)")
                return "dev-only-32-chars-minimum-secret!"
            else:
                raise ValueError("JWT_SECRET required for staging/production")

        # Validate length
        if len(v) < 32:
            raise ValueError(f"JWT_SECRET must be at least 32 characters (got {len(v)})")

        return v

    @field_validator("fernet_key", mode="before")
    @classmethod
    def validate_fernet_key(cls, v: str) -> str:
        if not v:
            v = os.getenv("FERNET_KEY", "").strip()

        # Production requires FERNET_KEY
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env == "production" and not v:
            raise ValueError("FERNET_KEY must be set via environment variable in production")

        # Development: warn but allow (uses unencrypted fallback)
        if not v and env == "development":
            logger.warning("FERNET_KEY not set — PII health data will NOT be encrypted in development mode")

        # If provided, validate format (should be 44-char base64 Fernet key)
        if v and len(v) != 44:
            logger.warning(f"FERNET_KEY length is {len(v)}, expected 44 chars (Fernet format)")

        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
