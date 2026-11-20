"""Contrat L0 (R7) : grand livre en ajout seul et écritures équilibrées, garantis par la base.

Les écritures sont passées sous le rôle applicatif ``mulema_app`` (non propriétaire, soumis à
la RLS). Deux barrières indépendantes :
- privilèges : ``mulema_app`` n'a ni UPDATE, ni DELETE, ni TRUNCATE (SQLSTATE 42501) ;
- déclencheurs : même le propriétaire est refusé (MCL01).

Codes SQLSTATE du contrat (voir specs/schema.sql) :
- MCL01 : UPDATE / DELETE / TRUNCATE sur une table en ajout seul ;
- MCL02 : écriture déséquilibrée ou de moins de deux lignes (vérifié au COMMIT) ;
- MCL03 : ligne ajoutée à une écriture déjà validée ;
- MCL04 : contre-passation qui n'est pas le miroir exact de l'écriture d'origine.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import psycopg
import pytest

from api.tests.contracts.helpers import (
    Line,
    connect_as_app,
    create_account,
    create_organization,
    insert_entry,
    insert_line,
)

INSUFFICIENT_PRIVILEGE = "42501"
APPEND_ONLY_TABLES = (
    "ledger_entries",
    "ledger_lines",
    "audit_events",
    "ai_actions",
    "claim_decisions",
    "member_status_history",
)


@dataclass(frozen=True)
class Books:
    dsn: str
    org: UUID
    charge: UUID  # 6011 Prestations santé
    payable: UUID  # 4011 Prestataires à payer
    entry: UUID  # écriture équilibrée déjà validée (passée par le rôle applicatif)


@pytest.fixture
def books(insurance_dsn: str) -> Books:
    # Paramétrage initial par le propriétaire (migration / administration).
    with psycopg.connect(insurance_dsn) as conn:
        org = create_organization(conn, "mutuelle-test")
        charge = create_account(conn, org, "6011", "charge")
        payable = create_account(conn, org, "4011", "passif")
    # Écriture passée par l'application.
    with connect_as_app(insurance_dsn, org) as conn, conn.transaction():
        entry = insert_entry(conn, org, "J-TEST-0001")
        insert_line(conn, org, entry, Line(1, charge, 38400, 0))
        insert_line(conn, org, entry, Line(2, payable, 0, 38400))
    return Books(insurance_dsn, org, charge, payable, entry)


def _reverse(conn: psycopg.Connection, books: Books, number: str) -> UUID:
    row = conn.execute(
        "INSERT INTO ledger_entries (organization_id, entry_number, accounting_date, "
        "label, source_type, reverses_entry_id) VALUES (%s, %s, DATE '2026-09-30', "
        "'Contre-passation', 'contre_passation', %s) RETURNING id",
        (books.org, number, books.entry),
    ).fetchone()
    assert row is not None
    value = row[0]
    assert isinstance(value, UUID)
    return value


MUTATIONS = [
    pytest.param("UPDATE ledger_entries SET label = 'modifié'", id="update-entries"),
    pytest.param("DELETE FROM ledger_entries", id="delete-entries"),
    pytest.param("UPDATE ledger_lines SET debit_xof = debit_xof + 1", id="update-lines"),
    pytest.param("DELETE FROM ledger_lines", id="delete-lines"),
    pytest.param("TRUNCATE ledger_lines", id="truncate-lines"),
    pytest.param("TRUNCATE ledger_entries CASCADE", id="truncate-entries"),
]


@pytest.mark.parametrize("statement", MUTATIONS)
def test_role_applicatif_sans_privilege_de_modification(books: Books, statement: str) -> None:
    with connect_as_app(books.dsn, books.org) as conn:
        with pytest.raises(psycopg.Error) as exc:
            conn.execute(statement.encode())
        assert exc.value.sqlstate == INSUFFICIENT_PRIVILEGE
        conn.rollback()
        count = conn.execute("SELECT count(*) FROM ledger_lines").fetchone()
    assert count == (2,), "les lignes validées doivent rester intactes"


@pytest.mark.parametrize("statement", MUTATIONS)
def test_meme_le_proprietaire_est_refuse_par_declencheur(books: Books, statement: str) -> None:
    with psycopg.connect(books.dsn) as conn:
        with pytest.raises(psycopg.Error) as exc:
            conn.execute(statement.encode())
        assert exc.value.sqlstate == "MCL01"
        conn.rollback()
        count = conn.execute("SELECT count(*) FROM ledger_lines").fetchone()
    assert count == (2,)


@pytest.mark.parametrize("table", APPEND_ONLY_TABLES)
def test_privileges_du_role_applicatif_sur_les_tables_en_ajout_seul(
    insurance_dsn: str, table: str
) -> None:
    with psycopg.connect(insurance_dsn) as conn:
        row = conn.execute(
            "SELECT has_table_privilege('mulema_app', %s, 'INSERT'), "
            "has_table_privilege('mulema_app', %s, 'SELECT'), "
            "has_table_privilege('mulema_app', %s, 'UPDATE'), "
            "has_table_privilege('mulema_app', %s, 'DELETE'), "
            "has_table_privilege('mulema_app', %s, 'TRUNCATE')",
            (table,) * 5,
        ).fetchone()
    assert row == (True, True, False, False, False)


def test_ecriture_equilibree_acceptee(books: Books) -> None:
    with connect_as_app(books.dsn, books.org) as conn:
        row = conn.execute(
            "SELECT sum(debit_xof), sum(credit_xof) FROM ledger_lines WHERE entry_id = %s",
            (books.entry,),
        ).fetchone()
    assert row == (38400, 38400)


def test_ecriture_desequilibree_refusee_au_commit(books: Books) -> None:
    with connect_as_app(books.dsn, books.org) as conn:
        entry = insert_entry(conn, books.org, "J-TEST-0002")
        insert_line(conn, books.org, entry, Line(1, books.charge, 38400, 0))
        insert_line(conn, books.org, entry, Line(2, books.payable, 0, 38000))
        with pytest.raises(psycopg.Error) as exc:
            conn.commit()
    assert exc.value.sqlstate == "MCL02"


def test_ecriture_sans_ligne_refusee(books: Books) -> None:
    with connect_as_app(books.dsn, books.org) as conn:
        insert_entry(conn, books.org, "J-TEST-0003")
        with pytest.raises(psycopg.Error) as exc:
            conn.commit()
    assert exc.value.sqlstate == "MCL02"


def test_ecriture_a_une_seule_ligne_refusee(books: Books) -> None:
    with connect_as_app(books.dsn, books.org) as conn:
        entry = insert_entry(conn, books.org, "J-TEST-0004")
        insert_line(conn, books.org, entry, Line(1, books.charge, 38400, 0))
        with pytest.raises(psycopg.Error) as exc:
            conn.commit()
    assert exc.value.sqlstate == "MCL02"


def test_ajout_de_ligne_a_une_ecriture_validee_refuse(books: Books) -> None:
    with connect_as_app(books.dsn, books.org) as conn, pytest.raises(psycopg.Error) as exc:
        insert_line(conn, books.org, books.entry, Line(3, books.charge, 100, 0))
    assert exc.value.sqlstate == "MCL03"


@pytest.mark.parametrize(
    ("debit", "credit"),
    [
        pytest.param(100, 100, id="debit-et-credit"),
        pytest.param(0, 0, id="ligne-nulle"),
        pytest.param(-5, 0, id="negatif"),
    ],
)
def test_ligne_porte_soit_un_debit_soit_un_credit(books: Books, debit: int, credit: int) -> None:
    with connect_as_app(books.dsn, books.org) as conn:
        entry = insert_entry(conn, books.org, "J-TEST-0005")
        with pytest.raises(psycopg.Error) as exc:
            insert_line(conn, books.org, entry, Line(1, books.charge, debit, credit))
    assert exc.value.sqlstate == "23514"


def test_contre_passation_annule_l_effet_et_ne_se_fait_qu_une_fois(books: Books) -> None:
    with connect_as_app(books.dsn, books.org) as conn:
        with conn.transaction():
            reversal = _reverse(conn, books, "J-TEST-0006")
            insert_line(conn, books.org, reversal, Line(1, books.payable, 38400, 0))
            insert_line(conn, books.org, reversal, Line(2, books.charge, 0, 38400))
        balance = conn.execute(
            "SELECT sum(debit_xof) - sum(credit_xof) FROM ledger_lines WHERE account_id = %s",
            (books.charge,),
        ).fetchone()
        assert balance == (0,)
        with pytest.raises(psycopg.Error) as exc:
            _reverse(conn, books, "J-TEST-0007")
    assert exc.value.sqlstate == "23505"


@pytest.mark.parametrize(
    "lines",
    [
        pytest.param([(1, "payable", 30000, 0), (2, "charge", 0, 30000)], id="montant-partiel"),
        pytest.param([(1, "charge", 38400, 0), (2, "payable", 0, 38400)], id="meme-sens"),
    ],
)
def test_contre_passation_doit_etre_le_miroir_exact(
    books: Books, lines: list[tuple[int, str, int, int]]
) -> None:
    accounts = {"payable": books.payable, "charge": books.charge}
    with connect_as_app(books.dsn, books.org) as conn:
        reversal = _reverse(conn, books, "J-TEST-0008")
        for line_no, account, debit, credit in lines:
            insert_line(conn, books.org, reversal, Line(line_no, accounts[account], debit, credit))
        with pytest.raises(psycopg.Error) as exc:
            conn.commit()
    assert exc.value.sqlstate == "MCL04"


@pytest.mark.parametrize("table", APPEND_ONLY_TABLES[2:])
def test_journaux_immuables_meme_pour_le_proprietaire(insurance_dsn: str, table: str) -> None:
    """Déclencheur de niveau instruction : refusé même sans ligne touchée."""
    with psycopg.connect(insurance_dsn) as conn:
        with pytest.raises(psycopg.Error) as exc:
            conn.execute(f"DELETE FROM {table}".encode())
        assert exc.value.sqlstate == "MCL01"
        conn.rollback()
        with pytest.raises(psycopg.Error) as exc:
            conn.execute(f"UPDATE {table} SET organization_id = organization_id".encode())
        assert exc.value.sqlstate == "MCL01"
