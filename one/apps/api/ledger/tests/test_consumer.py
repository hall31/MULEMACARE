"""R7 — consommateur des événements ``claim.decided`` et ``contribution.received`` (outbox).

- accord (``accordee_auto``, ``accordee``) : 6011 au débit / 4011 au crédit du montant couvert ;
- autres issues : aucune écriture (specs/events.md) ;
- cotisation reçue : compte de trésorerie du canal (5121, 5122, 5110) au débit / 7061 au crédit ;
- chaque écriture émet ``ledger.entry_posted`` dans la même transaction ;
- la lecture de l'outbox est idempotente et n'en marque rien (autres consommateurs : L4).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import pytest

from api.ledger.consumer import drain_outbox, handle_event
from api.ledger.domain import LedgerError
from api.ledger.repository import Conn
from api.ledger.service import get_entry, list_entries
from api.ledger.tests.support import (
    Org,
    app_connection,
    claim_decided,
    contribution_received,
    run,
    setup_org,
    write_outbox,
)
from api.tests.paths import EVENTS_MD


@pytest.fixture
def org(insurance_dsn: str) -> Org:
    return setup_org(insurance_dsn, "mutuelle-conso")


async def _scalar(conn: Conn, org: Org, query: str, params: tuple[object, ...] = ()) -> Any:  # noqa: ANN401
    async with conn.transaction():
        await conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(org.id),))
        cur = await conn.execute(query.encode(), params)
        row = await cur.fetchone()
    assert row is not None
    return row[0]


@pytest.mark.parametrize("outcome", ["accordee_auto", "accordee"])
def test_accord_passe_6011_au_debit_et_4011_au_credit(org: Org, outcome: str) -> None:
    event = claim_decided(org, outcome=outcome, covered_xof=38400)

    async def _go() -> None:
        async with app_connection(org.dsn) as conn:
            entry_id = await handle_event(conn, org.id, event)
            assert entry_id is not None
            entry = await get_entry(conn, org.id, entry_id)
        assert entry.source_type == "prise_en_charge"
        assert entry.source_id == UUID(event.payload["claim_id"])
        assert entry.accounting_date == date(2026, 9, 30)
        assert entry.currency == "XOF"
        assert re.fullmatch(r"J-2026-[0-9]{7}", entry.entry_number)
        lines = [
            (li.account_code, li.debit_xof, li.credit_xof, li.provider_id) for li in entry.lines
        ]
        assert lines == [
            ("6011", 38400, 0, org.provider_id),
            ("4011", 0, 38400, org.provider_id),
        ]

    run(_go())


@pytest.mark.parametrize("outcome", ["en_revue", "refusee", "pieces_demandees", "annulee"])
def test_decision_sans_accord_ne_passe_aucune_ecriture(org: Org, outcome: str) -> None:
    async def _go() -> None:
        async with app_connection(org.dsn) as conn:
            assert await handle_event(conn, org.id, claim_decided(org, outcome=outcome)) is None
            assert await _scalar(conn, org, "SELECT count(*) FROM ledger_entries") == 0

    run(_go())


def test_accord_a_zero_franc_ne_passe_aucune_ecriture(org: Org) -> None:
    async def _go() -> None:
        async with app_connection(org.dsn) as conn:
            assert await handle_event(conn, org.id, claim_decided(org, covered_xof=0)) is None

    run(_go())


@pytest.mark.parametrize(
    ("channel", "cash_account"),
    [
        ("wave", "5121"),
        ("orange_money", "5122"),
        ("virement", "5110"),
        ("prelevement_employeur", "5110"),
    ],
)
def test_cotisation_recue_debite_la_tresorerie_du_canal(
    org: Org, channel: str, cash_account: str
) -> None:
    event = contribution_received(org, channel=channel, amount_xof=27500)

    async def _go() -> None:
        async with app_connection(org.dsn) as conn:
            entry_id = await handle_event(conn, org.id, event)
            assert entry_id is not None
            entry = await get_entry(conn, org.id, entry_id)
        assert entry.source_type == "cotisation"
        assert entry.source_id == UUID(event.payload["contribution_id"])
        assert entry.accounting_date == date(2026, 10, 2)
        lines = [(li.account_code, li.debit_xof, li.credit_xof, li.member_id) for li in entry.lines]
        assert lines == [(cash_account, 27500, 0, org.member_id), ("7061", 0, 27500, org.member_id)]

    run(_go())


@pytest.mark.parametrize("channel", ["mtn_momo", "simulation"])
def test_canal_sans_compte_de_tresorerie_est_refuse_sans_ecriture(org: Org, channel: str) -> None:
    """Q-L0-11 : pas de compte MTN dans le plan initial ; on ne devine pas le compte."""

    async def _go() -> None:
        async with app_connection(org.dsn) as conn:
            with pytest.raises(LedgerError) as exc:
                await handle_event(conn, org.id, contribution_received(org, channel=channel))
            assert exc.value.code == "VAL-01"
            assert await _scalar(conn, org, "SELECT count(*) FROM ledger_entries") == 0

    run(_go())


def test_evenement_d_une_autre_organisation_refuse(org: Org, insurance_dsn: str) -> None:
    other = setup_org(insurance_dsn, "mutuelle-autre")

    async def _go() -> None:
        async with app_connection(org.dsn) as conn:
            with pytest.raises(LedgerError) as exc:
                await handle_event(conn, org.id, claim_decided(other))
            assert exc.value.code == "VAL-01"

    run(_go())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("covered_xof", 384.5),
        ("covered_xof", "38400"),
        ("covered_xof", True),
        ("covered_xof", -1),
        ("currency", "EUR"),
        ("provider_id", "pas-un-uuid"),
    ],
)
def test_charge_utile_invalide_refusee(org: Org, field: str, value: object) -> None:
    event = claim_decided(org)
    event.payload[field] = value

    async def _go() -> None:
        async with app_connection(org.dsn) as conn:
            with pytest.raises(LedgerError) as exc:
                await handle_event(conn, org.id, event)
            assert exc.value.code == "VAL-01"

    run(_go())


def _entry_posted_schema() -> dict[str, Any]:
    blocks = re.findall(r"```json\n(.*?)\n```", EVENTS_MD.read_text(encoding="utf-8"), re.DOTALL)
    for block in blocks:
        doc: dict[str, Any] = json.loads(block)
        if doc.get("title") == "ledger.entry_posted":
            return doc
    raise AssertionError("schéma ledger.entry_posted introuvable")


def test_chaque_ecriture_emet_ledger_entry_posted_conforme(org: Org) -> None:
    schema = _entry_posted_schema()["properties"]["payload"]
    line_schema = schema["properties"]["lines"]["items"]
    event = claim_decided(org, covered_xof=20000)

    async def _go() -> dict[str, Any]:
        async with app_connection(org.dsn) as conn:
            entry_id = await handle_event(conn, org.id, event)
            payload: dict[str, Any] = await _scalar(
                conn,
                org,
                "SELECT payload FROM outbox_events WHERE event_type = 'ledger.entry_posted' "
                "AND aggregate_id = %s",
                (entry_id,),
            )
        return payload

    payload = run(_go())
    assert set(schema["required"]) <= set(payload) <= set(schema["properties"])
    assert payload["total_debit_xof"] == payload["total_credit_xof"] == 20000
    assert payload["source_event_id"] == str(event.id)
    assert payload["currency"] == "XOF"
    for line in payload["lines"]:
        assert set(line_schema["required"]) <= set(line) <= set(line_schema["properties"])
        assert isinstance(line["debit_xof"], int)


def test_drain_de_l_outbox_idempotent_et_non_destructif(org: Org) -> None:
    accorde = claim_decided(org, covered_xof=38400)
    en_revue = claim_decided(org, outcome="en_revue", covered_xof=185000)
    cotisation = contribution_received(org, channel="orange_money")
    mtn = contribution_received(org, channel="mtn_momo")
    for event in (accorde, en_revue, cotisation, mtn):
        write_outbox(org, event)

    async def _go() -> None:
        async with app_connection(org.dsn) as conn:
            first = await drain_outbox(conn, org.id)
            assert (first.posted, first.failed) == (2, 1)
            second = await drain_outbox(conn, org.id)
            assert (second.posted, second.failed) == (0, 1)
            assert await _scalar(conn, org, "SELECT count(*) FROM ledger_entries") == 2
            # L'outbox est partagée (L4 consomme aussi contribution.received) : rien n'est marqué.
            assert (
                await _scalar(
                    conn, org, "SELECT count(*) FROM outbox_events WHERE published_at IS NOT NULL"
                )
                == 0
            )

    run(_go())


def test_isolation_une_organisation_ne_voit_pas_le_grand_livre_d_une_autre(
    org: Org, insurance_dsn: str
) -> None:
    other = setup_org(insurance_dsn, "mutuelle-voisine")
    write_outbox(org, claim_decided(org))

    async def _go() -> None:
        async with app_connection(org.dsn) as conn:
            await drain_outbox(conn, org.id)
            mine = await list_entries(conn, org.id)
            assert len(mine.items) == 1
            assert (await drain_outbox(conn, other.id)).posted == 0
            theirs = await list_entries(conn, other.id)
            assert theirs.items == []
            with pytest.raises(LedgerError) as exc:
                await get_entry(conn, other.id, mine.items[0].id)
            assert exc.value.code == "NOT-01"

    run(_go())


def test_date_comptable_en_heure_locale_de_l_organisation(org: Org) -> None:
    """Africa/Abidjan = UTC+0 : 23:30 UTC reste le même jour civil."""
    event = claim_decided(org, occurred_at=datetime(2026, 12, 31, 23, 30, tzinfo=UTC))

    async def _go() -> None:
        async with app_connection(org.dsn) as conn:
            entry_id = await handle_event(conn, org.id, event)
            assert entry_id is not None
            entry = await get_entry(conn, org.id, entry_id)
        assert entry.accounting_date == date(2026, 12, 31)
        assert entry.entry_number.startswith("J-2026-")

    run(_go())
