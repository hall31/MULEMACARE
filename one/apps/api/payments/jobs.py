"""Émission mensuelle des cotisations (une échéance par adhérent et par mois, rejouable).

Appelé par l'ordonnanceur de l'exploitation le 1er du mois (ou rattrapage) ; aucune route du
contrat ne crée de cotisation. Montant = cotisation mensuelle de la version de formule en
vigueur au 1er du mois ; échéance = 1er du mois (défaut, Q-L4-01).
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime
from uuid import UUID

from api.core.clock import ensure_utc
from api.core.database import Database
from api.core.jsonlog import log_event
from api.payments.repository import PaymentRepository

logger = logging.getLogger("mulema.payments.jobs")


async def issue_month(
    database: Database, organization_id: UUID, period_start: date, now: datetime
) -> int:
    if period_start.day != 1:
        msg = "une période de cotisation commence le 1er du mois"
        raise ValueError(msg)
    last_day = calendar.monthrange(period_start.year, period_start.month)[1]
    period_end = period_start.replace(day=last_day)
    async with database.transaction(organization_id) as session:
        created = await PaymentRepository(session).issue_month(
            organization_id, period_start, period_end, ensure_utc(now)
        )
    log_event(
        logger,
        logging.INFO,
        "payments.contributions_issued",
        organization_id=organization_id,
        period_start=period_start.isoformat(),
        created=created,
    )
    return created
