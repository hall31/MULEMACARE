"""Outbox partagée L4 → L3 : ``contribution.received`` est consommable par le grand livre.

Le consommateur réel de L3 (``drain_outbox``), sous ``mulema_app``, passe 5121 / 7061 pour un
paiement Wave ; ni L4 ni L3 ne marquent ``published_at``.
"""

from __future__ import annotations

from uuid import UUID

import psycopg
from psycopg import sql

from api.ledger.consumer import drain_outbox
from api.members.tests.support import (
    L4Env,
    checkout,
    events,
    hook,
    payment_link_token,
    post_webhook,
    suspended_member,
)
from api.tests.contracts.helpers import APP_ROLE


async def _drain(dsn: str, organization_id: UUID) -> tuple[int, int]:
    conn = await psycopg.AsyncConnection.connect(dsn, autocommit=True)
    try:
        await conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(APP_ROLE)))
        report = await drain_outbox(conn, organization_id)
    finally:
        await conn.close()
    return report.posted, report.failed


def test_le_grand_livre_consomme_la_cotisation_recue(guarded: L4Env) -> None:
    env = guarded
    _, contribution = suspended_member(env, "a")
    payment = checkout(env, payment_link_token(env, "a", contribution), "wave")
    note = env.simulated("wave").notification(payment, occurred_at=env.clock.now())
    assert (
        post_webhook(env, hook(env.orgs["a"].slug, "wave"), note.body, note.signature).status_code
        == 200
    )

    received = events(env, "contribution.received", contribution_id=str(contribution))
    assert len(received) == 1
    posted, failed = env.run(_drain, env.dsn, env.orgs["a"].id)
    assert (posted, failed) == (1, 0)

    lines = env.rows(
        "SELECT a.code, l.debit_xof, l.credit_xof FROM ledger_entries e "
        "JOIN ledger_lines l ON l.entry_id = e.id JOIN ledger_accounts a ON a.id = l.account_id "
        "WHERE e.source_event_id = %s ORDER BY l.line_no",
        (received[0]["event_id"],),
    )
    assert lines == [("5121", 27500, 0), ("7061", 0, 27500)]
    assert (
        events(env, "contribution.received", contribution_id=str(contribution))[0]["published_at"]
        is None
    )
    # Rejouer le consommateur ne repasse rien.
    assert env.run(_drain, env.dsn, env.orgs["a"].id) == (0, 0)
