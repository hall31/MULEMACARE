"""Preuve de propriété du domaine de marque blanche (Phase 3, CR-P3-02).

Migration additive et rejouable (0005_preuve_de_domaine.sql) : colonnes
``custom_domain_token`` et ``custom_domain_verified_at`` (nullables) et deux contraintes sur
``organization_branding``, déclencheur ``organization_branding_domain_reverify`` (une preuve ne
s'hérite pas), ``resolve_organization_branding`` remplacée (organisations actives, domaines
prouvés seulement ; même signature, mêmes droits). 0001 à 0004 inchangées.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-02
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | None = None
depends_on: str | None = None

SQL = Path(__file__).with_name("0005_preuve_de_domaine.sql")


def upgrade() -> None:
    # Même exécution que 0001 à 0004 : protocole simple du pilote.
    driver_connection = op.get_bind().connection.driver_connection
    if driver_connection is None:
        msg = "connexion pilote indisponible"
        raise RuntimeError(msg)
    driver_connection.execute(SQL.read_text(encoding="utf-8").encode())


def downgrade() -> None:
    msg = (
        "Revenir avant 0005 effacerait les preuves de propriété des domaines et rouvrirait la "
        "lecture publique aux domaines non prouvés : opération interdite sans validation "
        "humaine (AGENTS.md)."
    )
    raise RuntimeError(msg)
