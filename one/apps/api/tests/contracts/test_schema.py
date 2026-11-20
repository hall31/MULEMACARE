"""Contrat L0 : ``specs/schema.sql`` s'applique sur une base vide et respecte les invariants."""

from __future__ import annotations

import psycopg
import pytest

# Tables exigées par LOTS.md (L0) et par la consigne du lot.
REQUIRED_TABLES = frozenset(
    {
        "organizations",
        "persons",
        "members",
        "dependents",
        "plans",
        "plan_versions",
        "coverages",
        "providers",
        "claims",
        "claim_items",
        "authorizations",
        "contributions",
        "ledger_entries",
        "ledger_lines",
        "audit_events",
        "ai_actions",
        "users",
        "user_roles",
        "idempotency_keys",
    }
)

# Seule table sans organization_id : l'organisation elle-même (son id EST l'organisation).
TABLES_WITHOUT_ORGANIZATION_ID = frozenset({"organizations"})


def _tables(conn: psycopg.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
    ).fetchall()
    return {r[0] for r in rows}


def test_serveur_de_test_est_postgresql_16(pg_server_dsn: str) -> None:
    with psycopg.connect(pg_server_dsn) as conn:
        row = conn.execute("SHOW server_version_num").fetchone()
    assert row is not None
    assert 160000 <= int(row[0]) < 170000, f"PostgreSQL 16 attendu, obtenu {row[0]}"


def test_schema_s_applique_sur_une_base_vide(insurance_dsn: str) -> None:
    with psycopg.connect(insurance_dsn) as conn:
        missing = REQUIRED_TABLES - _tables(conn)
    assert not missing, f"tables manquantes : {sorted(missing)}"


def test_organization_id_non_nul_sur_chaque_table_metier(insurance_dsn: str) -> None:
    with psycopg.connect(insurance_dsn) as conn:
        tables = _tables(conn) - TABLES_WITHOUT_ORGANIZATION_ID
        rows = conn.execute(
            "SELECT table_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_name = 'organization_id'"
        ).fetchall()
    found = {r[0]: (r[1], r[2]) for r in rows}
    missing = sorted(t for t in tables if t not in found)
    assert not missing, f"organization_id absent de : {missing}"
    bad = sorted(t for t in tables if found[t] != ("uuid", "NO"))
    assert not bad, f"organization_id doit être uuid NOT NULL dans : {bad}"


def test_montants_en_entiers_bigint(insurance_dsn: str) -> None:
    with psycopg.connect(insurance_dsn) as conn:
        money = conn.execute(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_name LIKE '%\\_xof'"
        ).fetchall()
        floats = conn.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND data_type IN ('real', 'double precision', 'money')"
        ).fetchall()
    assert money, "aucune colonne monétaire *_xof trouvée"
    not_bigint = [(t, c, d) for t, c, d in money if d != "bigint"]
    assert not not_bigint, f"montants hors bigint : {not_bigint}"
    assert not floats, f"colonnes flottantes interdites : {floats}"


def test_chaque_cle_etrangere_est_indexee(insurance_dsn: str) -> None:
    """Chaque FK doit avoir un index dont les premières colonnes sont celles de la FK."""
    query = """
        SELECT c.conrelid::regclass::text, c.conname
        FROM pg_constraint c
        WHERE c.contype = 'f'
          AND c.connamespace = 'public'::regnamespace
          AND NOT EXISTS (
            SELECT 1 FROM pg_index i
            WHERE i.indrelid = c.conrelid
              AND (i.indkey::int2[])[0:array_length(c.conkey, 1) - 1] @> c.conkey
              AND (i.indkey::int2[])[0:array_length(c.conkey, 1) - 1] <@ c.conkey
          )
        ORDER BY 1, 2
    """
    with psycopg.connect(insurance_dsn) as conn:
        unindexed = conn.execute(query).fetchall()
    assert not unindexed, f"clés étrangères sans index : {unindexed}"


@pytest.mark.parametrize(
    ("statement", "expected_sqlstate"),
    [
        pytest.param(
            "INSERT INTO organizations (slug, name, country_code, timezone, capabilities) "
            "VALUES ('x-fr', 'X', 'FR', 'Europe/Paris', ARRAY['gestionnaire'])",
            "23514",
            id="pays-hors-instance",
        ),
        pytest.param(
            "INSERT INTO organizations (slug, name, country_code, timezone, capabilities) "
            "VALUES ('x-ci', 'X', 'CI', 'Africa/Abidjan', ARRAY['assureur_inconnu'])",
            "23514",
            id="capacite-inconnue",
        ),
    ],
)
def test_contraintes_d_organisation(
    insurance_dsn: str, statement: str, expected_sqlstate: str
) -> None:
    with psycopg.connect(insurance_dsn) as conn, pytest.raises(psycopg.Error) as exc:
        conn.execute(statement.encode())
    assert exc.value.sqlstate == expected_sqlstate
