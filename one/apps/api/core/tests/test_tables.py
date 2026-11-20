"""Les tables SQLAlchemy du noyau décrivent exactement les colonnes du contrat schema.sql."""

from __future__ import annotations

import psycopg
import pytest
from sqlalchemy import Table

from api.core.tables import audit_events, organizations, user_roles, users
from api.core.tests.conftest import CoreSeed


@pytest.mark.parametrize("table", [organizations, users, user_roles, audit_events])
def test_colonnes_identiques_au_contrat(core_seed: CoreSeed, table: Table) -> None:
    with psycopg.connect(core_seed.dsn) as conn:
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s",
            (table.name,),
        ).fetchall()
    assert {r[0] for r in rows} == {c.name for c in table.columns}
