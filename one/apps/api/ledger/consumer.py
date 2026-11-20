"""Consommateur des événements ``claim.decided`` et ``contribution.received`` (specs/events.md).

Livraison « au moins une fois » : le consommateur est idempotent sur ``event_id``, stocké dans
``ledger_entries.source_event_id`` (unique par organisation). Le verrou de journal sérialise les
rejeux concurrents ; la contrainte d'unicité reste la barrière finale.

Écritures produites :
- ``claim.decided`` avec ``accordee_auto`` ou ``accordee`` : 6011 au débit, 4011 au crédit, du
  montant pris en charge (``covered_xof``), tiers = prestataire. Autres issues : rien.
- ``contribution.received`` : trésorerie du canal (5121, 5122, 5110) au débit, 7061 au crédit,
  tiers = adhérent. Canal sans compte au plan : refus explicite (VAL-01), rien n'est deviné.
Date comptable : jour civil local de l'organisation (décision : ``occurred_at`` ; cotisation :
``confirmed_at``).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final
from uuid import UUID
from zoneinfo import ZoneInfo

from api.core.jsonlog import LOGGER_NAME, log_exception
from api.ledger import repository
from api.ledger.accounts import (
    CASH_ACCOUNT_BY_CHANNEL,
    CLAIM_EXPENSE,
    CONTRIBUTION_REVENUE,
    PROVIDER_PAYABLE,
)
from api.ledger.domain import CURRENCY, EntryDraft, LedgerError, LineDraft, invalid
from api.ledger.repository import Conn
from api.ledger.service import post_locked, unit_of_work

logger = logging.getLogger(f"{LOGGER_NAME}.ledger.consumer")

CONSUMED_EVENTS: Final = frozenset({"claim.decided", "contribution.received"})
POSTING_OUTCOMES: Final = frozenset({"accordee_auto", "accordee"})
CLAIM_OUTCOMES: Final = POSTING_OUTCOMES | {"en_revue", "refusee", "pieces_demandees", "annulee"}
_CLAIM_NUMBER = re.compile(r"^PEC-[0-9]{2}-[0-9]{5,}$")
_EVENT_ACTION = "Corrigez l'événement chez son producteur puis rejouez-le."


@dataclass(frozen=True, slots=True)
class OutboxEvent:
    """Enveloppe commune des événements (specs/events.md) ; ``id`` = ``event_id``."""

    id: UUID
    organization_id: UUID
    event_type: str
    event_version: int
    occurred_at: datetime
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class DrainReport:
    posted: int = 0
    skipped: int = 0
    failed: int = 0


def _bad(field: str) -> LedgerError:
    return invalid(f"Événement invalide : champ « {field} » absent ou incorrect.", _EVENT_ACTION)


def _uuid(payload: dict[str, Any], field: str) -> UUID:
    value = payload.get(field)
    if not isinstance(value, str):
        raise _bad(field)
    try:
        return UUID(value)
    except ValueError as exc:
        raise _bad(field) from exc


def _amount(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if type(value) is not int or value < 0:
        raise _bad(field)
    return value


def _text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise _bad(field)
    return value


def _local_date(moment: datetime, timezone: str) -> date:
    if moment.tzinfo is None:
        raise _bad("occurred_at")
    return moment.astimezone(ZoneInfo(timezone)).date()


def _claim_draft(event: OutboxEvent, timezone: str) -> EntryDraft | None:
    payload = event.payload
    outcome = _text(payload, "outcome")
    if outcome not in CLAIM_OUTCOMES:
        raise _bad("outcome")
    if outcome not in POSTING_OUTCOMES:
        return None
    covered = _amount(payload, "covered_xof")
    if covered == 0:
        return None
    claim_number = _text(payload, "claim_number")
    if not _CLAIM_NUMBER.match(claim_number):
        raise _bad("claim_number")
    provider = _uuid(payload, "provider_id")
    return EntryDraft(
        accounting_date=_local_date(event.occurred_at, timezone),
        label=f"Prise en charge {claim_number}",
        source_type="prise_en_charge",
        source_id=_uuid(payload, "claim_id"),
        source_event_id=event.id,
        lines=(
            LineDraft(CLAIM_EXPENSE, covered, 0, provider_id=provider),
            LineDraft(PROVIDER_PAYABLE, 0, covered, provider_id=provider),
        ),
    )


def _contribution_draft(event: OutboxEvent, timezone: str) -> EntryDraft | None:
    payload = event.payload
    amount = _amount(payload, "amount_xof")
    if amount == 0:
        return None
    channel = _text(payload, "channel")
    cash_account = CASH_ACCOUNT_BY_CHANNEL.get(channel)
    if cash_account is None:
        raise invalid(
            f"Aucun compte de trésorerie pour le canal « {channel} » dans le plan de comptes.",
            "Faites compléter le plan de comptes par le gestionnaire puis rejouez l'événement.",
        )
    member = _uuid(payload, "member_id")
    try:
        confirmed_at = datetime.fromisoformat(_text(payload, "confirmed_at"))
        period = date.fromisoformat(_text(payload, "period_start"))
    except ValueError as exc:
        raise _bad("confirmed_at / period_start") from exc
    return EntryDraft(
        accounting_date=_local_date(confirmed_at, timezone),
        label=f"Cotisation {period:%m/%Y}",
        source_type="cotisation",
        source_id=_uuid(payload, "contribution_id"),
        source_event_id=event.id,
        lines=(
            LineDraft(cash_account, amount, 0, member_id=member),
            LineDraft(CONTRIBUTION_REVENUE, 0, amount, member_id=member),
        ),
    )


def _draft_for(event: OutboxEvent, timezone: str) -> EntryDraft | None:
    if event.payload.get("currency") != CURRENCY:
        raise _bad("currency")
    if event.event_type == "claim.decided":
        return _claim_draft(event, timezone)
    return _contribution_draft(event, timezone)


async def handle_event(conn: Conn, organization_id: UUID, event: OutboxEvent) -> UUID | None:
    """Passe l'écriture de l'événement, une seule fois. Renvoie l'écriture, ou ``None``."""
    if event.organization_id != organization_id:
        raise invalid("Événement d'une autre organisation.", _EVENT_ACTION)
    if event.event_type not in CONSUMED_EVENTS or event.event_version != 1:
        raise invalid(
            f"Événement non consommé par le grand livre : {event.event_type} "
            f"v{event.event_version}.",
            _EVENT_ACTION,
        )
    async with unit_of_work(conn, organization_id, lock=True):
        existing = await repository.entry_id_for_event(conn, organization_id, event.id)
        if existing is not None:
            return existing
        timezone = await repository.organization_timezone(conn, organization_id)
        draft = _draft_for(event, timezone)
        if draft is None:
            return None
        entry = await post_locked(conn, organization_id, draft)
    return entry.id


async def drain_outbox(conn: Conn, organization_id: UUID, *, limit: int = 500) -> DrainReport:
    """Consomme les événements en attente de l'organisation, chacun dans sa transaction.

    Un événement refusé (VAL-01) est journalisé et compté, sans bloquer les suivants ; il
    reste en attente et sera reproposé tant qu'il n'est pas corrigé. N'écrit rien dans l'outbox
    source (partagée avec L4).
    """
    async with unit_of_work(conn, organization_id, lock=False):
        rows = await repository.pending_events(conn, organization_id, limit)
    posted = skipped = failed = 0
    for event_id, org, event_type, version, occurred_at, payload in rows:
        event = OutboxEvent(
            id=event_id,
            organization_id=org,
            event_type=str(event_type),
            event_version=int(version),
            occurred_at=occurred_at,
            payload=payload if isinstance(payload, dict) else {},
        )
        try:
            entry_id = await handle_event(conn, organization_id, event)
        except LedgerError as exc:
            failed += 1
            log_exception(
                logger,
                "ledger.event_rejected",
                organization_id=organization_id,
                event_id=event.id,
                event_type=event.event_type,
                code=exc.code,
            )
            continue
        if entry_id is None:
            skipped += 1
        else:
            posted += 1
    return DrainReport(posted=posted, skipped=skipped, failed=failed)
