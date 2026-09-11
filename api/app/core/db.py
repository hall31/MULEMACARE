"""SQLAlchemy async engine + session + encrypted types."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import TypeDecorator, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class EncryptedText(TypeDecorator):
    """
    SQLAlchemy TypeDecorator for transparent encryption/decryption of PII health data.

    - Stores encrypted data as Text in the database
    - Automatically decrypts on read, encrypts on write
    - Fernet symmetric encryption (CBC mode with HMAC)
    - Fallback: if FERNET_KEY is empty in development, stores plaintext with warning
    """

    impl = Text
    cache_ok = True

    def __init__(self) -> None:
        super().__init__()
        self._fernet: Fernet | None = None
        self._encryption_disabled = False

        # Initialize Fernet if key is available
        if settings.fernet_key:
            try:
                self._fernet = Fernet(settings.fernet_key.encode("utf-8"))
            except Exception as e:
                logger.error(f"Failed to initialize Fernet from FERNET_KEY: {e}")
                self._encryption_disabled = True
        else:
            self._encryption_disabled = True
            if settings.environment == "development":
                logger.warning("EncryptedText: encryption disabled — using plaintext fallback in development")
            else:
                logger.error("EncryptedText: FERNET_KEY missing — encryption will fail in production")

    def process_bind_param(self, value: str | None, dialect: Any) -> str | None:
        """Encrypt on write to database."""
        if value is None:
            return None

        if self._encryption_disabled or not self._fernet:
            return value

        try:
            encrypted = self._fernet.encrypt(value.encode("utf-8"))
            return encrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise

    def process_result_value(self, value: str | None, dialect: Any) -> str | None:
        """Decrypt on read from database."""
        if value is None:
            return None

        if self._encryption_disabled or not self._fernet:
            return value

        try:
            decrypted = self._fernet.decrypt(value.encode("utf-8"))
            return decrypted.decode("utf-8")
        except InvalidToken as e:
            logger.error(f"Decryption failed — invalid token or wrong key: {e}")
            raise
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    # Import models so metadata is populated
    from app.domain import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
