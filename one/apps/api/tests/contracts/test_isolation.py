"""Contrat L0 (R10) : isolation par organisation, prouvée table par table sous le rôle applicatif.

Pour CHAQUE table de ``specs/schema.sql`` : une ligne de l'organisation B est invisible depuis A,
A voit exactement ses propres lignes, et la seule politique est ``tenant_isolation``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql

from api.tests.contracts.helpers import APP_ROLE, connect_as_app
from api.tests.paths import SCHEMA_SQL

FIXTURE = Path(__file__).parent / "fixtures" / "one_row_per_table.sql"
TABLES = re.findall(
    r"^CREATE TABLE (\w+)", SCHEMA_SQL.read_text(encoding="utf-8"), flags=re.MULTILINE
)
EXPECTED_QUAL = "(organization_id = app_current_organization_id())"
EXPECTED_QUAL_ORGS = "(id = app_current_organization_id())"


def _org_column(table: str) -> str:
    return "id" if table == "organizations" else "organization_id"


@dataclass(frozen=True)
class TwoOrgs:
    dsn: str
    a: UUID
    b: UUID


def _load(dsn: str, org: UUID, slug: str) -> None:
    script = FIXTURE.read_text(encoding="utf-8")
    script = script.replace("__ORG__", str(org)).replace("__SLUG__", slug)
    with psycopg.connect(dsn) as conn:
        conn.execute(script.encode())


@pytest.fixture
def two_orgs(insurance_dsn: str) -> TwoOrgs:
    a, b = uuid4(), uuid4()
    _load(insurance_dsn, a, "org-a")
    _load(insurance_dsn, b, "org-b")
    return TwoOrgs(insurance_dsn, a, b)


def _count(conn: psycopg.Connection, table: str, org: UUID | None = None) -> int:
    query = sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
    params: tuple[str, ...] = ()
    if org is not None:
        query = sql.SQL("{} WHERE {} = %s").format(query, sql.Identifier(_org_column(table)))
        params = (str(org),)
    row = conn.execute(query, params).fetchone()
    assert row is not None
    return int(row[0])


def test_liste_des_tables_lue_dans_le_contrat() -> None:
    assert len(TABLES) >= 30
    assert "claims" in TABLES
    assert "ledger_lines" in TABLES


def test_le_jeu_couvre_chaque_table(two_orgs: TwoOrgs) -> None:
    """Garde-fou : une table ajoutée sans ligne dans le jeu fait échouer ce test."""
    with psycopg.connect(two_orgs.dsn) as conn:  # propriétaire : voit tout
        empty = [t for t in TABLES for org in (two_orgs.a, two_orgs.b) if _count(conn, t, org) == 0]
    assert not empty, f"tables sans ligne dans le jeu d'isolation : {sorted(set(empty))}"


@pytest.mark.parametrize("table", TABLES)
def test_une_ligne_de_b_est_invisible_depuis_a(two_orgs: TwoOrgs, table: str) -> None:
    with psycopg.connect(two_orgs.dsn) as owner:
        own_rows = _count(owner, table, two_orgs.a)
    with connect_as_app(two_orgs.dsn, two_orgs.a) as conn:
        assert _count(conn, table, two_orgs.b) == 0, f"{table} : lignes de B visibles depuis A"
        assert _count(conn, table) == own_rows, f"{table} : A ne voit pas exactement ses lignes"
    with connect_as_app(two_orgs.dsn, two_orgs.b) as conn:
        assert _count(conn, table, two_orgs.b) >= 1, f"{table} : B ne voit pas ses lignes"


@pytest.mark.parametrize("table", TABLES)
def test_sans_organisation_positionnee_rien_n_est_visible(two_orgs: TwoOrgs, table: str) -> None:
    with psycopg.connect(two_orgs.dsn) as conn:
        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(APP_ROLE)))
        assert _count(conn, table) == 0


def test_a_ne_peut_pas_ecrire_chez_b(two_orgs: TwoOrgs) -> None:
    with connect_as_app(two_orgs.dsn, two_orgs.a) as conn, pytest.raises(psycopg.Error) as exc:
        conn.execute(
            "INSERT INTO plans (organization_id, code, name) VALUES (%s, 'INTRUS', 'Intrus')",
            (str(two_orgs.b),),
        )
    assert exc.value.sqlstate == "42501"


@pytest.mark.parametrize("table", TABLES)
def test_une_seule_politique_tenant_isolation_et_rls_forcee(insurance_dsn: str, table: str) -> None:
    """Échoue si une politique plus large (ex. USING (true)) est ajoutée à une table."""
    with psycopg.connect(insurance_dsn) as conn:
        flags = conn.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = %s::regclass",
            (table,),
        ).fetchone()
        policies = conn.execute(
            "SELECT policyname, permissive, roles::text[], cmd, qual, with_check "
            "FROM pg_policies WHERE schemaname = 'public' AND tablename = %s",
            (table,),
        ).fetchall()
    assert flags == (True, True), f"{table} : RLS non activée ou non forcée"
    qual = EXPECTED_QUAL_ORGS if table == "organizations" else EXPECTED_QUAL
    assert policies == [("tenant_isolation", "PERMISSIVE", ["public"], "ALL", qual, qual)], (
        f"{table} : politiques inattendues {policies}"
    )


def test_role_applicatif_sans_pouvoir_particulier(insurance_dsn: str) -> None:
    with psycopg.connect(insurance_dsn) as conn:
        role = conn.execute(
            "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, rolcanlogin "
            "FROM pg_roles WHERE rolname = %s",
            (APP_ROLE,),
        ).fetchone()
        owned = conn.execute(
            "SELECT count(*) FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner "
            "WHERE r.rolname = %s",
            (APP_ROLE,),
        ).fetchone()
    assert role == (False, False, False, False, False)
    assert owned == (0,), "le rôle applicatif ne doit posséder aucun objet"
