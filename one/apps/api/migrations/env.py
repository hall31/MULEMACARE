"""Environnement Alembic : migrations SQL explicites, sans autogénération (contrat = schema.sql)."""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, pool

config = context.config


def _database_url() -> str:
    url = config.get_main_option("sqlalchemy.url") or os.environ.get(
        "MULEMA_INSURANCE_DATABASE_URL", ""
    )
    if not url:
        msg = (
            "URL de base absente : définissez MULEMA_INSURANCE_DATABASE_URL "
            "(postgresql+psycopg://…/insurance)."
        )
        raise RuntimeError(msg)
    return url


def run_migrations_offline() -> None:
    context.configure(url=_database_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
