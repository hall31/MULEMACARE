"""Espace adhérent (Phase 1, CR-P1-01) : rôle ``adherent`` rattaché à son contrat.

Migration additive et rejouable (0002_espace_adherent.sql) : colonne nullable
``user_roles.member_id``, rôle ``adherent`` ajouté à la liste autorisée, contrainte « member_id
si et seulement si adherent », clé étrangère composite vers ``members`` et son index. Aucune
donnée existante n'est réécrite ; 0001 reste figée (empreinte vérifiée par test_migrations.py).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None

SQL = Path(__file__).with_name("0002_espace_adherent.sql")


def upgrade() -> None:
    # Même exécution que 0001 : protocole simple du pilote (bloc DO, « :: »).
    driver_connection = op.get_bind().connection.driver_connection
    if driver_connection is None:
        msg = "connexion pilote indisponible"
        raise RuntimeError(msg)
    driver_connection.execute(SQL.read_text(encoding="utf-8").encode())


def downgrade() -> None:
    msg = (
        "Revenir avant 0002 supprimerait les comptes adhérents (user_roles.member_id) : "
        "opération interdite sans validation humaine (AGENTS.md)."
    )
    raise RuntimeError(msg)
