"""Contrat L0 (R6) : la base ``insurance`` ne porte aucune donnée médicale.

Deux scans indépendants :
1. le texte de ``specs/schema.sql`` (commentaires SQL retirés) ;
2. le catalogue PostgreSQL après application du schéma (tables, vues, colonnes, types).
"""

from __future__ import annotations

import re

import psycopg
import pytest

from api.tests.paths import SCHEMA_SQL

FORBIDDEN_FRAGMENTS = (
    "diagnos",
    "motif_med",
    "ordonnance",
    "prescription",
    "medical",
    "symptom",
    "pathologi",
)

_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def forbidden_names(names: list[str]) -> list[str]:
    """Renvoie les noms qui contiennent un fragment interdit (insensible à la casse)."""
    return sorted({n for n in names for f in FORBIDDEN_FRAGMENTS if f in n.lower()})


def forbidden_in_sql(sql_text: str) -> list[str]:
    """Scanne le SQL hors commentaires et renvoie les fragments interdits trouvés."""
    code = _BLOCK_COMMENT.sub("", _LINE_COMMENT.sub("", sql_text)).lower()
    return sorted({f for f in FORBIDDEN_FRAGMENTS if f in code})


@pytest.mark.parametrize(
    "bad_sql",
    [
        "CREATE TABLE claims (id uuid, diagnostic text);",
        "CREATE TABLE claims (id uuid, motif_medical text);",
        "ALTER TABLE claims ADD COLUMN ordonnance_ref text;",
        "CREATE TABLE claims (id uuid, Diagnosis_Code text);",
        "CREATE TABLE claims (id uuid, medical_notes text);",
        "CREATE TABLE claims (id uuid, symptomes text);",
        "CREATE TABLE claims (id uuid, pathologie_code text);",
    ],
)
def test_le_scanner_detecte_une_colonne_interdite(bad_sql: str) -> None:
    """Le test échouerait si le schéma contenait une telle colonne (preuve par mutation)."""
    assert forbidden_in_sql(bad_sql)


def test_le_scanner_ignore_les_commentaires() -> None:
    assert not forbidden_in_sql("-- aucune colonne diagnostic\n/* ni ordonnance */ SELECT 1;")


def test_schema_sql_ne_contient_aucun_champ_medical() -> None:
    found = forbidden_in_sql(SCHEMA_SQL.read_text(encoding="utf-8"))
    assert not found, f"fragments médicaux interdits dans schema.sql : {found}"


def test_catalogue_ne_contient_aucune_colonne_medicale(insurance_dsn: str) -> None:
    with psycopg.connect(insurance_dsn) as conn:
        columns = [
            f"{t}.{c}"
            for t, c in conn.execute(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = 'public'"
            ).fetchall()
        ]
        relations = [
            r[0]
            for r in conn.execute(
                "SELECT relname FROM pg_class WHERE relnamespace = 'public'::regnamespace"
            ).fetchall()
        ]
    assert columns, "le catalogue devrait contenir des colonnes"
    assert not forbidden_names(columns), forbidden_names(columns)
    assert not forbidden_names(relations), forbidden_names(relations)
