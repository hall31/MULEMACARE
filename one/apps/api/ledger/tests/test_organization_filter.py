"""Défense en profondeur : les lectures du grand livre filtrent ``organization_id`` elles-mêmes.

La RLS reste la barrière principale. Ici, on la neutralise volontairement (connexion
propriétaire, superutilisateur : hors RLS) pour prouver que chaque lecture porte AUSSI un filtre
explicite sur l'organisation du principal. Retirer ce filtre d'une requête fait échouer ce test.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import psycopg
import pytest

from api.ledger import consumer, repository, service
from api.ledger.domain import EntryQuery, LedgerError
from api.ledger.repository import Conn
from api.ledger.tests.support import (
    Org,
    app_connection,
    claim_decided,
    contribution_received,
    run,
    setup_org,
    write_outbox,
)

A_COVERED, B_COVERED = 38400, 91000


@asynccontextmanager
async def owner_connection(dsn: str) -> AsyncIterator[Conn]:
    """Superutilisateur en autocommit : la RLS ne s'applique PAS à cette connexion."""
    conn = await psycopg.AsyncConnection.connect(dsn, autocommit=True)
    try:
        yield conn
    finally:
        await conn.close()


@pytest.fixture
def two_orgs(insurance_dsn: str) -> tuple[Org, Org, UUID, UUID]:
    a, b = setup_org(insurance_dsn, "filtre-a"), setup_org(insurance_dsn, "filtre-b")

    async def _seed() -> tuple[UUID, UUID]:
        async with app_connection(insurance_dsn) as conn:
            entry_a = await consumer.handle_event(
                conn, a.id, claim_decided(a, covered_xof=A_COVERED)
            )
            entry_b = await consumer.handle_event(
                conn, b.id, claim_decided(b, covered_xof=B_COVERED)
            )
        assert entry_a is not None
        assert entry_b is not None
        return entry_a, entry_b

    entry_a, entry_b = run(_seed())
    return a, b, entry_a, entry_b


def test_lectures_filtrees_meme_sans_rls(
    insurance_dsn: str, two_orgs: tuple[Org, Org, UUID, UUID]
) -> None:
    a, _, entry_a, entry_b = two_orgs

    async def scenario() -> None:
        async with owner_connection(insurance_dsn) as conn:
            page = await service.list_entries(conn, a.id, EntryQuery(limit=200))
            assert [e.id for e in page.items] == [entry_a]

            by_account = await service.list_entries(
                conn, a.id, EntryQuery(account_code="6011", limit=200)
            )
            assert [e.id for e in by_account.items] == [entry_a]

            with pytest.raises(LedgerError) as caught:
                await service.get_entry(conn, a.id, entry_b)
            assert caught.value.code == "NOT-01"

            mine = await service.get_entry(conn, a.id, entry_a)
            assert len(mine.lines) == 2

            accounts = await service.list_accounts(conn, a.id)
            assert len(accounts) == 6

            balance = await service.balance(conn, a.id)
            assert sum(row.debit_xof for row in balance.rows) == A_COVERED

            async with conn.transaction():
                assert await repository.load_entry(conn, a.id, entry_b) is None
                assert await repository.reversal_of(conn, a.id, entry_b) is None
                ids = await repository.account_ids(conn, a.id, ["6011", "4011"])
                assert len(ids) == 2

    run(scenario())


def test_evenements_en_attente_filtres_par_organisation(
    insurance_dsn: str, two_orgs: tuple[Org, Org, UUID, UUID]
) -> None:
    a, b, _, _ = two_orgs
    pending_b = contribution_received(b)
    write_outbox(b, pending_b)

    async def scenario() -> None:
        async with owner_connection(insurance_dsn) as conn, conn.transaction():
            assert await repository.pending_events(conn, a.id, 100) == []
            seen_by_b = [row[0] for row in await repository.pending_events(conn, b.id, 100)]
            assert seen_by_b == [pending_b.id]
            assert await repository.entry_id_for_event(conn, a.id, pending_b.id) is None

    run(scenario())


def test_numerotation_par_organisation(
    insurance_dsn: str, two_orgs: tuple[Org, Org, UUID, UUID]
) -> None:
    """Le numéro suivant ne dépend que du journal de l'organisation, même hors RLS."""
    a, b, _, _ = two_orgs

    async def scenario() -> tuple[str, str]:
        async with app_connection(insurance_dsn) as conn:
            await consumer.handle_event(conn, a.id, contribution_received(a))  # A : 2 écritures
        async with owner_connection(insurance_dsn) as conn, conn.transaction():
            entry_a = await repository.load_entry(conn, a.id, two_orgs[2])
            assert entry_a is not None
            day = entry_a.accounting_date
            return (
                await repository.next_entry_number(conn, a.id, day),
                await repository.next_entry_number(conn, b.id, day),
            )

    next_a, next_b = run(scenario())
    assert next_a.endswith("-0000003")
    assert next_b.endswith("-0000002")
