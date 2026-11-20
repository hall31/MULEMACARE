"""R7 — propriétés du grand livre sur des milliers d'écritures aléatoires (hypothesis).

Critères d'acceptation (PRD §4, LOTS.md L3) :
- débits = crédits sur des milliers d'écritures aléatoires, par écriture, par compte et au total ;
- une écriture déséquilibrée est refusée par le service ET, s'il est contourné, par la base ;
- la contre-passation annule l'effet de l'écriture sur la balance ;
- le même événement rejoué ne produit qu'une seule écriture.

Tout passe par le rôle applicatif ``mulema_app``.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from contextlib import AsyncExitStack
from datetime import date
from itertools import pairwise

import psycopg
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from api.ledger.accounts import CHART_OF_ACCOUNTS
from api.ledger.consumer import handle_event
from api.ledger.domain import EntryDraft, LedgerError, LineDraft, ReversalCommand
from api.ledger.repository import Conn, insert_entry_unchecked
from api.ledger.service import balance, post_entry, reverse_entry
from api.ledger.tests.support import (
    Org,
    app_connection,
    claim_decided,
    contribution_received,
    run,
    setup_org,
)

CODES = [account.code for account in CHART_OF_ACCOUNTS]
AMOUNT = st.integers(min_value=1, max_value=50_000_000)


def _settings(max_examples: int) -> settings:
    """Base de données hypothesis désactivée : aucun fichier écrit hors du dossier du lot."""
    return settings(
        max_examples=max_examples,
        deadline=None,
        database=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
    )


@st.composite
def raw_lines(draw: st.DrawFn) -> list[tuple[str, int, int]]:
    """Lignes quelconques (compte, débit, crédit) : équilibrées ou non."""
    n = draw(st.integers(min_value=2, max_value=6))
    lines = []
    for _ in range(n):
        code = draw(st.sampled_from(CODES))
        amount = draw(AMOUNT)
        lines.append((code, amount, 0) if draw(st.booleans()) else (code, 0, amount))
    return lines


@st.composite
def balanced_lines(draw: st.DrawFn) -> list[tuple[str, int, int]]:
    """Lignes équilibrées : montants débiteurs répartis aléatoirement au crédit."""
    debits = draw(st.lists(AMOUNT, min_size=1, max_size=3))
    total = sum(debits)
    cuts = sorted(draw(st.sets(st.integers(1, total - 1), max_size=2))) if total > 1 else []
    bounds = [0, *cuts, total]
    credits = [b - a for a, b in pairwise(bounds)]
    lines = [(draw(st.sampled_from(CODES)), d, 0) for d in debits]
    lines += [(draw(st.sampled_from(CODES)), 0, c) for c in credits]
    return draw(st.permutations(lines))


def _draft(lines: list[tuple[str, int, int]], label: str = "Écriture aléatoire") -> EntryDraft:
    return EntryDraft(
        accounting_date=date(2026, 9, 30),
        label=label,
        source_type="reglement",
        lines=tuple(LineDraft(code, debit, credit) for code, debit, credit in lines),
    )


def _is_balanced(lines: list[tuple[str, int, int]]) -> bool:
    return sum(d for _, d, _ in lines) == sum(c for _, _, c in lines)


async def _net_by_account(conn: Conn, org: Org) -> dict[str, int]:
    result = await balance(conn, org.id, at=date(2099, 12, 31))
    return {row.account_code: row.debit_xof - row.credit_xof for row in result.rows}


async def _ledger_totals(conn: Conn, org: Org) -> tuple[int, int, int]:
    """(écritures déséquilibrées, total débit, total crédit) lus directement en SQL."""
    async with conn.transaction():
        await conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(org.id),))
        cur = await conn.execute(
            "SELECT count(*) FILTER (WHERE d <> c), coalesce(sum(d), 0), coalesce(sum(c), 0) "
            "FROM (SELECT entry_id, sum(debit_xof) AS d, sum(credit_xof) AS c "
            "      FROM ledger_lines GROUP BY entry_id) AS t"
        )
        row = await cur.fetchone()
    assert row is not None
    return int(row[0]), int(row[1]), int(row[2])


def test_debits_egal_credits_sur_des_milliers_d_ecritures(insurance_dsn: str) -> None:
    org = setup_org(insurance_dsn, "mutuelle-prop")
    outcome: Counter[str] = Counter()

    async def _post_all(batch: list[list[tuple[str, int, int]]]) -> None:
        async with app_connection(org.dsn) as conn:
            for lines in batch:
                if _is_balanced(lines):
                    await post_entry(conn, org.id, _draft(lines))
                    outcome["acceptees"] += 1
                else:
                    with pytest.raises(LedgerError) as exc:
                        await post_entry(conn, org.id, _draft(lines))
                    assert exc.value.code == "VAL-01"
                    outcome["refusees"] += 1
            unbalanced, debit, credit = await _ledger_totals(conn, org)
            assert unbalanced == 0
            assert debit == credit
            result = await balance(conn, org.id, at=date(2099, 12, 31))
            assert result.total_debit_xof == result.total_credit_xof == debit

    # 3 écritures équilibrées pour 1 quelconque : >= 100 x 20 x 3/4 = 1 500 acceptées attendues.
    entries = st.one_of(balanced_lines(), balanced_lines(), balanced_lines(), raw_lines())

    @_settings(100)
    @given(st.lists(entries, min_size=20, max_size=40))
    def _property(batch: list[list[tuple[str, int, int]]]) -> None:
        run(_post_all(batch))

    _property()
    assert outcome["acceptees"] >= 1000, outcome
    assert outcome["refusees"] > 0, outcome


async def _insert_without_service_checks(
    conn: Conn, org: Org, lines: list[tuple[str, int, int]]
) -> None:
    async with conn.transaction():
        await conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(org.id),))
        await insert_entry_unchecked(conn, org.id, _draft(lines), "J-BRUT-0001")


def test_la_base_refuse_une_ecriture_desequilibree_meme_si_le_service_est_contourne(
    insurance_dsn: str,
) -> None:
    org = setup_org(insurance_dsn, "mutuelle-brute")

    async def _attempt(lines: list[tuple[str, int, int]]) -> None:
        async with app_connection(org.dsn) as conn:
            with pytest.raises(psycopg.Error) as exc:
                await _insert_without_service_checks(conn, org, lines)
            assert exc.value.sqlstate == "MCL02"
            _, debit, credit = await _ledger_totals(conn, org)
            assert debit == credit == 0

    @_settings(40)
    @given(raw_lines().filter(lambda lines: not _is_balanced(lines)))
    def _property(lines: list[tuple[str, int, int]]) -> None:
        run(_attempt(lines))

    _property()


def test_contre_passation_annule_l_effet_sur_la_balance(insurance_dsn: str) -> None:
    org = setup_org(insurance_dsn, "mutuelle-cp")
    reversals = Counter[str]()

    async def _roundtrip(lines: list[tuple[str, int, int]], key: int) -> None:
        async with app_connection(org.dsn) as conn:
            before = await _net_by_account(conn, org)
            posted = await post_entry(conn, org.id, _draft(lines))
            reversal = await reverse_entry(
                conn,
                org.id,
                ReversalCommand(posted.id, "erreur de saisie", org.user_id, f"cle-cp-{key:08d}"),
            )
            assert reversal.reverses_entry_id == posted.id
            assert await _net_by_account(conn, org) == before
            with pytest.raises(LedgerError) as exc:
                await reverse_entry(
                    conn,
                    org.id,
                    ReversalCommand(posted.id, "deuxième essai", org.user_id, f"cle-cp2-{key:08d}"),
                )
            assert exc.value.code == "LED-01"
            reversals["ok"] += 1

    @_settings(60)
    @given(balanced_lines())
    def _property(lines: list[tuple[str, int, int]]) -> None:
        run(_roundtrip(lines, reversals["ok"]))

    _property()
    assert reversals["ok"] >= 60


def test_meme_evenement_rejoue_une_seule_ecriture(insurance_dsn: str) -> None:
    org = setup_org(insurance_dsn, "mutuelle-rejeu")

    async def _replay(kind: str, amount: int, replays: int, parallel: bool) -> None:
        event = (
            claim_decided(org, outcome=kind, covered_xof=amount)
            if kind in {"accordee_auto", "accordee"}
            else contribution_received(org, channel=kind, amount_xof=amount)
        )
        async with AsyncExitStack() as stack:
            # Rejeux concurrents : une connexion par livraison (comme plusieurs workers).
            conns = [
                await stack.enter_async_context(app_connection(org.dsn)) for _ in range(replays)
            ]
            first = conns[0]
            if parallel:
                ids = await asyncio.gather(*(handle_event(c, org.id, event) for c in conns))
            else:
                ids = [await handle_event(first, org.id, event) for _ in range(replays)]
            assert len(set(ids)) == 1
            assert ids[0] is not None
            async with first.transaction():
                await first.execute(
                    "SELECT set_config('app.organization_id', %s, true)", (str(org.id),)
                )
                cur = await first.execute(
                    "SELECT count(*) FROM ledger_entries WHERE source_event_id = %s", (event.id,)
                )
                row = await cur.fetchone()
                cur = await first.execute(
                    "SELECT count(*) FROM outbox_events WHERE event_type = 'ledger.entry_posted' "
                    "AND aggregate_id = %s",
                    (ids[0],),
                )
                posted_events = await cur.fetchone()
        assert row == (1,)
        assert posted_events == (1,)

    @_settings(40)
    @given(
        st.sampled_from(["accordee_auto", "accordee", "wave", "orange_money", "virement"]),
        AMOUNT,
        st.integers(min_value=2, max_value=5),
        st.booleans(),
    )
    def _property(kind: str, amount: int, replays: int, parallel: bool) -> None:
        run(_replay(kind, amount, replays, parallel))

    _property()
