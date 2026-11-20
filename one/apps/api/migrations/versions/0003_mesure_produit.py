"""Mesure produit (Phase 2, voie B, CR-P2-01) : table ``product_events``.

Migration additive et rejouable (0003_mesure_produit.sql) : une table nouvelle, sa RLS forcée
(politique ``tenant_isolation``), ses index et les droits de ``mulema_app`` (SELECT, INSERT,
DELETE pour la purge par rétention ; jamais UPDATE). Aucune table existante n'est touchée ;
0001 et 0002 restent inchangées.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-01
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None

SQL = Path(__file__).with_name("0003_mesure_produit.sql")


def upgrade() -> None:
    # Même exécution que 0001 et 0002 : protocole simple du pilote (bloc DO).
    driver_connection = op.get_bind().connection.driver_connection
    if driver_connection is None:
        msg = "connexion pilote indisponible"
        raise RuntimeError(msg)
    driver_connection.execute(SQL.read_text(encoding="utf-8").encode())


def downgrade() -> None:
    msg = (
        "Revenir avant 0003 supprimerait les événements de mesure (product_events) : "
        "opération interdite sans validation humaine (AGENTS.md)."
    )
    raise RuntimeError(msg)
