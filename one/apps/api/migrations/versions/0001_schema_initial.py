"""Schéma initial de la base `insurance` : copie figée du contrat L0 (0001_schema_initial.sql).

La copie ne change plus une fois relue (empreinte vérifiée par test_migrations.py). Toute
évolution passe par une migration 0002+ ET met à jour specs/schema.sql ; un test vérifie que
le catalogue obtenu par toutes les migrations égale celui de specs/schema.sql.

Revision ID: 0001
Revises:
Create Date: 2026-09-30
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None

FROZEN_SQL = Path(__file__).with_name("0001_schema_initial.sql")


def upgrade() -> None:
    # Exécution directe par le pilote (protocole simple) : le SQL du contrat contient des
    # corps PL/pgSQL et des « :: » que le parseur de paramètres de SQLAlchemy ne doit pas voir.
    driver_connection = op.get_bind().connection.driver_connection
    if driver_connection is None:
        msg = "connexion pilote indisponible"
        raise RuntimeError(msg)
    driver_connection.execute(FROZEN_SQL.read_text(encoding="utf-8").encode())


def downgrade() -> None:
    msg = (
        "Revenir avant 0001 supprimerait toutes les données (dont le grand livre) : "
        "opération interdite sans validation humaine (AGENTS.md)."
    )
    raise RuntimeError(msg)
