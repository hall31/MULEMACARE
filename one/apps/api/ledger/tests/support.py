"""Aides des tests L3 : organisation fictive, connexions sous ``mulema_app``, événements.

Le paramétrage (organisation, utilisateur, prestataire, adhérent) est posé par le propriétaire,
comme le ferait l'administration ; tout ce qui touche au grand livre passe ensuite par le rôle
applicatif non propriétaire (RLS et GRANT appliqués comme en production).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg import sql

from api.ledger.consumer import OutboxEvent
from api.ledger.repository import Conn
from api.ledger.service import install_chart_of_accounts
from api.tests.contracts.helpers import APP_ROLE, create_organization


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    """Exécute une coroutine depuis un test synchrone."""
    return asyncio.run(coro)


@asynccontextmanager
async def app_connection(dsn: str) -> AsyncIterator[Conn]:
    """Connexion asynchrone en autocommit sous le rôle applicatif (sans organisation fixée).

    Le service positionne lui-même ``app.organization_id`` (SET LOCAL) dans chaque transaction.
    """
    conn = await psycopg.AsyncConnection.connect(dsn, autocommit=True)
    try:
        await conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(APP_ROLE)))
        yield conn
    finally:
        await conn.close()


@dataclass(frozen=True)
class Org:
    """Organisation fictive prête pour le grand livre."""

    dsn: str
    id: UUID
    user_id: UUID
    provider_id: UUID
    member_id: UUID


def setup_org(dsn: str, slug: str) -> Org:
    """Crée une organisation fictive (propriétaire) puis installe le plan de comptes (app)."""
    with psycopg.connect(dsn) as conn:
        org = create_organization(conn, slug)
        conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(org),))
        user = _one_id(
            conn,
            "INSERT INTO users (organization_id, idp_subject, display_name) "
            "VALUES (%s, %s, 'Gestionnaire fictif') RETURNING id",
            (org, f"sub-{slug}"),
        )
        provider = _one_id(
            conn,
            "INSERT INTO providers (organization_id, name, kind, city, country_code) "
            "VALUES (%s, 'Clinique fictive', 'clinique', 'Abidjan', 'CI') RETURNING id",
            (org,),
        )
        person = _one_id(
            conn,
            "INSERT INTO persons (organization_id, given_name, family_name, birth_date) "
            "VALUES (%s, 'Prénom', 'Fictif', DATE '1990-01-01') RETURNING id",
            (org,),
        )
        plan = _one_id(
            conn,
            "INSERT INTO plans (organization_id, code, name) "
            "VALUES (%s, 'FORMULE-T', 'Formule test') RETURNING id",
            (org,),
        )
        member = _one_id(
            conn,
            "INSERT INTO members (organization_id, person_id, member_number, plan_id, status, "
            "enrolled_on, waiting_period_ends_on) VALUES (%s, %s, 'MC-00000001', %s, 'actif', "
            "DATE '2026-01-01', DATE '2026-03-02') RETURNING id",
            (org, person, plan),
        )

    async def _chart() -> None:
        async with app_connection(dsn) as conn:
            await install_chart_of_accounts(conn, org)

    run(_chart())
    return Org(dsn, org, user, provider, member)


def _one_id(conn: psycopg.Connection, query: str, params: tuple[object, ...]) -> UUID:
    row = conn.execute(query.encode(), params).fetchone()
    assert row is not None
    assert isinstance(row[0], UUID)
    return row[0]


def claim_decided(
    org: Org,
    *,
    outcome: str = "accordee_auto",
    covered_xof: int = 38400,
    event_id: UUID | None = None,
    occurred_at: datetime | None = None,
) -> OutboxEvent:
    """Événement ``claim.decided`` fictif conforme à specs/events.md."""
    total = covered_xof + 9600
    payload: dict[str, Any] = {
        "claim_id": str(uuid4()),
        "claim_number": "PEC-26-00001",
        "decision_sequence": 1,
        "outcome": outcome,
        "source": "regle",
        "rule": {"rule_id": str(uuid4()), "code": "R-12", "version": 3},
        "reason_code": "R-12",
        "decided_by": None,
        "member_id": str(org.member_id),
        "provider_id": str(org.provider_id),
        "service_date": "2026-09-30",
        "plan_version_id": str(uuid4()),
        "total_xof": total,
        "covered_xof": covered_xof,
        "patient_share_xof": total - covered_xof,
        "currency": "XOF",
    }
    return OutboxEvent(
        id=event_id or uuid4(),
        organization_id=org.id,
        event_type="claim.decided",
        event_version=1,
        occurred_at=occurred_at or datetime(2026, 9, 30, 10, 0, tzinfo=UTC),
        payload=payload,
    )


def contribution_received(
    org: Org,
    *,
    channel: str = "wave",
    amount_xof: int = 27500,
    event_id: UUID | None = None,
) -> OutboxEvent:
    """Événement ``contribution.received`` fictif conforme à specs/events.md."""
    payload: dict[str, Any] = {
        "contribution_id": str(uuid4()),
        "payment_id": str(uuid4()),
        "member_id": str(org.member_id),
        "period_start": "2026-10-01",
        "amount_xof": amount_xof,
        "currency": "XOF",
        "channel": channel,
        "payer_kind": "proche",
        "payer_country_code": "FR",
        "confirmed_at": "2026-10-02T08:30:00Z",
    }
    return OutboxEvent(
        id=event_id or uuid4(),
        organization_id=org.id,
        event_type="contribution.received",
        event_version=1,
        occurred_at=datetime(2026, 10, 2, 8, 30, tzinfo=UTC),
        payload=payload,
    )


def write_outbox(org: Org, event: OutboxEvent) -> None:
    """Écrit l'événement dans ``outbox_events`` comme le ferait son producteur (L4, L5)."""
    with psycopg.connect(org.dsn) as conn:
        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(APP_ROLE)))
        conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(org.id),))
        aggregate = event.payload.get("claim_id") or event.payload["contribution_id"]
        conn.execute(
            "INSERT INTO outbox_events (id, organization_id, event_type, event_version, "
            "aggregate_id, payload, occurred_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                event.id,
                event.organization_id,
                event.event_type,
                event.event_version,
                aggregate,
                json.dumps(event.payload),
                event.occurred_at,
            ),
        )
