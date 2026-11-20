"""Import de l'existant en lecture seule (L11, R14, ADR-006 ; CR-L11-01, à valider).

Migration additive et rejouable (0006_import_existant.sql) : tables ``import_runs`` (journal
des imports appliqués) et ``external_ids`` (clés d'origine, ajout seul), RLS forcée et
politique ``tenant_isolation`` sur les deux, gardes de base MCI01 (devise), MCI02 (journal
figé), MCI03 (clé orpheline). 0001 à 0005 inchangées.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-02
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None

SQL = Path(__file__).with_name("0006_import_existant.sql")


def upgrade() -> None:
    # Même exécution que 0001 à 0005 : protocole simple du pilote.
    driver_connection = op.get_bind().connection.driver_connection
    if driver_connection is None:
        msg = "connexion pilote indisponible"
        raise RuntimeError(msg)
    driver_connection.execute(SQL.read_text(encoding="utf-8").encode())


def downgrade() -> None:
    msg = (
        "Revenir avant 0006 effacerait les clés d'origine des lignes importées et le journal "
        "des imports : le rapprochement avec l'existant deviendrait impossible. Opération "
        "interdite sans validation humaine (AGENTS.md)."
    )
    raise RuntimeError(msg)
