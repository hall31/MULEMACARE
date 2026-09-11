"""Pytest configuration and fixtures."""

from __future__ import annotations

import os
from cryptography.fernet import Fernet

# Set required environment variables before importing app modules
os.environ.setdefault("JWT_SECRET", "test_secret_" * 3)  # 32+ chars
os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode("utf-8"))
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
