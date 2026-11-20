"""R7 — ``UPDATE`` et ``DELETE`` refusés sur les écritures passées par le service du grand livre.

Deux barrières indépendantes, prouvées sur des écritures réelles du lot L3 :
- le rôle applicatif ``mulema_app`` n'a pas le privilège (SQLSTATE 42501) ;
- les déclencheurs refusent même le propriétaire (SQLSTATE MCL01).
Le service n'expose d'ailleurs aucune opération de modification ou de suppression.
"""

from __future__ import annotations

import importlib
import inspect
import re
from datetime import date

import psycopg
import pytest
from psycopg import sql

from api.ledger import consumer, repository, service
from api.ledger.domain import EntryDraft, LineDraft
from api.ledger.tests.support import Org, app_connection, run, setup_org
from api.tests.contracts.helpers import APP_ROLE

routes = importlib.import_module("api.ledger.routes")

INSUFFICIENT_PRIVILEGE = "42501"
MUTATIONS = [
    pytest.param("UPDATE ledger_entries SET label = 'modifié'", id="update-entries"),
    pytest.param("UPDATE ledger_entries SET accounting_date = accounting_date", id="update-date"),
    pytest.param("DELETE FROM ledger_entries", id="delete-entries"),
    pytest.param("UPDATE ledger_lines SET debit_xof = debit_xof + 1", id="update-lines"),
    pytest.param("DELETE FROM ledger_lines", id="delete-lines"),
]


@pytest.fixture
def org(insurance_dsn: str) -> Org:
    org = setup_org(insurance_dsn, "mutuelle-immuable")

    async def _post() -> None:
        async with app_connection(insurance_dsn) as conn:
            await service.post_entry(
                conn,
                org.id,
                EntryDraft(
                    accounting_date=date(2026, 9, 30),
                    label="Accord PEC-26-00001",
                    source_type="prise_en_charge",
                    lines=(LineDraft("6011", 38400, 0), LineDraft("4011", 0, 38400)),
                ),
            )

    run(_post())
    return org


def _snapshot(dsn: str, org: Org) -> list[tuple[object, ...]]:
    with psycopg.connect(dsn) as conn:
        conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(org.id),))
        return conn.execute(
            "SELECT e.entry_number, e.label, l.line_no, l.debit_xof, l.credit_xof "
            "FROM ledger_entries e JOIN ledger_lines l ON l.entry_id = e.id ORDER BY 1, 3"
        ).fetchall()


@pytest.mark.parametrize("statement", MUTATIONS)
def test_update_et_delete_refuses_au_role_applicatif(org: Org, statement: str) -> None:
    before = _snapshot(org.dsn, org)
    with psycopg.connect(org.dsn) as conn:
        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(APP_ROLE)))
        conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(org.id),))
        with pytest.raises(psycopg.Error) as exc:
            conn.execute(statement.encode())
    assert exc.value.sqlstate == INSUFFICIENT_PRIVILEGE
    assert _snapshot(org.dsn, org) == before
    assert len(before) == 2


@pytest.mark.parametrize("statement", MUTATIONS)
def test_update_et_delete_refuses_meme_au_proprietaire(org: Org, statement: str) -> None:
    before = _snapshot(org.dsn, org)
    with psycopg.connect(org.dsn) as conn:
        conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(org.id),))
        with pytest.raises(psycopg.Error) as exc:
            conn.execute(statement.encode())
    assert exc.value.sqlstate == "MCL01"
    assert _snapshot(org.dsn, org) == before


def test_le_module_n_emet_aucun_update_ni_delete_sur_le_grand_livre() -> None:
    """Garde-fou statique : aucune instruction de modification du grand livre dans le code."""
    forbidden = re.compile(r"\b(UPDATE|DELETE\s+FROM)\s+ledger_(entries|lines)\b", re.IGNORECASE)
    for module in (repository, service, consumer, routes):
        assert not forbidden.search(inspect.getsource(module)), module.__name__
