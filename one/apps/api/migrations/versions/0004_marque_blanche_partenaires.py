"""Marque blanche, espaces assureur et employeur, accueil d'organisation (Phase 3, CR-P3-01).

Migration additive et rejouable (0004_marque_blanche_partenaires.sql) : listes fermées élargies
(capacité ``plateforme``, rôles ``assureur`` et ``admin_plateforme``), tables
``organization_branding`` et ``configuration_templates`` (RLS forcée, politique
``tenant_isolation``), fonctions ``resolve_organization_branding`` et
``platform_create_organization`` réservées à ``mulema_app``. 0001, 0002 et 0003 inchangées.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-02
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None

SQL = Path(__file__).with_name("0004_marque_blanche_partenaires.sql")


def upgrade() -> None:
    # Même exécution que 0001 à 0003 : protocole simple du pilote (blocs DO).
    driver_connection = op.get_bind().connection.driver_connection
    if driver_connection is None:
        msg = "connexion pilote indisponible"
        raise RuntimeError(msg)
    driver_connection.execute(SQL.read_text(encoding="utf-8").encode())


def downgrade() -> None:
    msg = (
        "Revenir avant 0004 supprimerait la marque des organisations et les gabarits de "
        "configuration : opération interdite sans validation humaine (AGENTS.md)."
    )
    raise RuntimeError(msg)
