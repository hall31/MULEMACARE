"""Aides SQL pour les tests de contrat (données fictives uniquement)."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple
from uuid import UUID

import psycopg
from psycopg import sql


def apply_sql_file(dsn: str, path: Path) -> None:
    """Applique un fichier SQL en une transaction (protocole simple, sans paramètres)."""
    with psycopg.connect(dsn) as conn:
        conn.execute(path.read_text(encoding="utf-8").encode())


def _returning_id(cur: psycopg.Cursor[tuple[object, ...]]) -> UUID:
    row = cur.fetchone()
    assert row is not None
    value = row[0]
    assert isinstance(value, UUID)
    return value


def create_organization(conn: psycopg.Connection, slug: str) -> UUID:
    return _returning_id(
        conn.execute(
            "INSERT INTO organizations (slug, name, country_code, timezone, capabilities) "
            "VALUES (%s, %s, 'CI', 'Africa/Abidjan', ARRAY['porteur_de_risque', 'gestionnaire']) "
            "RETURNING id",
            (slug, f"Organisation fictive {slug}"),
        )
    )


def create_account(conn: psycopg.Connection, org: UUID, code: str, account_class: str) -> UUID:
    return _returning_id(
        conn.execute(
            "INSERT INTO ledger_accounts (organization_id, code, label, account_class) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (org, code, f"Compte {code}", account_class),
        )
    )


def insert_entry(conn: psycopg.Connection, org: UUID, number: str) -> UUID:
    return _returning_id(
        conn.execute(
            "INSERT INTO ledger_entries (organization_id, entry_number, accounting_date, label, "
            "source_type) VALUES (%s, %s, DATE '2026-09-30', 'Écriture de test', "
            "'prise_en_charge') RETURNING id",
            (org, number),
        )
    )


class Line(NamedTuple):
    """Ligne comptable : numéro, compte, débit, crédit (entiers FCFA)."""

    line_no: int
    account: UUID
    debit: int
    credit: int


def insert_line(conn: psycopg.Connection, org: UUID, entry: UUID, line: Line) -> UUID:
    return _returning_id(
        conn.execute(
            "INSERT INTO ledger_lines (organization_id, entry_id, line_no, account_id, "
            "debit_xof, credit_xof) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (org, entry, line.line_no, line.account, line.debit, line.credit),
        )
    )


APP_ROLE = "mulema_app"


def connect_as_app(dsn: str, org: UUID) -> psycopg.Connection:
    """Connexion sous le rôle applicatif non propriétaire, organisation positionnée.

    Le serveur de test ne fournit qu'un superutilisateur ; ``SET ROLE`` fait perdre ses
    privilèges pour la session (RLS et GRANT s'appliquent comme en production).
    """
    conn = psycopg.connect(dsn)
    conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(APP_ROLE)))
    conn.execute("SELECT set_config('app.organization_id', %s, false)", (str(org),))
    conn.commit()
    return conn
