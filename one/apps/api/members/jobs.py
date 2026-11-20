"""Traitement quotidien des statuts (R2, R8), une organisation à la fois, sous ``mulema_app``.

Dans une seule transaction (rejouable : un second passage le même jour ne change rien) :
1. échéances dépassées : ``a_payer`` → ``en_retard`` ;
2. impayé ≥ seuil de R-01 (45 jours, proto) : actif ou carence → ``suspendu`` (``impaye``) ;
3. carence écoulée et impayé sous le seuil : carence → ``actif`` (``fin_de_carence``).

Le seuil est celui de la version de R-01 en vigueur le jour du traitement. L'ordonnancement
(cron, file) relève de l'exploitation ; ce module n'en impose aucun.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import CursorResult, text

from api.core.clock import ensure_utc
from api.core.database import Database
from api.core.jsonlog import log_event
from api.members.repository import MemberRepository
from api.members.status import (
    Change,
    local_today,
    organization_timezone,
    rights_policy,
    transition,
    unpaid_days,
)

logger = logging.getLogger("mulema.members.jobs")


@dataclass(frozen=True, slots=True)
class DailyReport:
    overdue: int
    suspended: int
    activated: int


async def run_daily(database: Database, organization_id: UUID, now: datetime) -> DailyReport:
    now = ensure_utc(now)
    async with database.transaction(organization_id) as session:
        repo = MemberRepository(session)
        timezone = await organization_timezone(repo, organization_id)
        today = local_today(now, timezone)
        marked = await session.execute(
            text(
                "UPDATE contributions SET status = 'en_retard' WHERE organization_id = :org "
                "AND status = 'a_payer' AND due_on < :today"
            ),
            {"org": organization_id, "today": today},
        )
        overdue = marked.rowcount if isinstance(marked, CursorResult) else 0
        policy = await rights_policy(repo, organization_id, today)
        suspended = activated = 0
        for member in await repo.members_to_review(organization_id):
            late = await unpaid_days(repo, organization_id, member.id, today, timezone)
            if late >= policy.suspension_after_unpaid_days:
                change = Change("suspendu", "impaye", now, rule=policy)
                await transition(repo, organization_id, member, change)
                suspended += 1
            elif member.status == "carence" and member.waiting_period_ends_on <= today:
                await transition(
                    repo, organization_id, member, Change("actif", "fin_de_carence", now)
                )
                activated += 1
    report = DailyReport(overdue=int(overdue or 0), suspended=suspended, activated=activated)
    log_event(
        logger,
        logging.INFO,
        "members.daily_run",
        organization_id=organization_id,
        overdue=report.overdue,
        suspended=report.suspended,
        activated=report.activated,
    )
    return report
