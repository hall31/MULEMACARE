"""Service de la mesure produit : enregistrer un événement, calculer les indicateurs.

- ``record`` : contrôle (liste blanche, rôle du jeton, règles de l'événement, session), puis
  insertion avec l'heure du SERVEUR, l'organisation du jeton, l'empreinte HMAC de la PERSONNE
  (utilisateur du jeton, clé du serveur) et l'échéance de rétention. Ni l'utilisateur, ni son
  contrat, ni l'identifiant de session ne sont écrits.
- ``product_metrics`` : période en jours locaux de l'organisation (30 derniers jours par défaut,
  366 au plus), élargie aux semaines entières et coupée à la dernière semaine terminée
  (``windows``) ; indicateurs calculés en base puis publiés sous le seuil de k-anonymat, par
  période ET par semaine (``privacy``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final
from zoneinfo import ZoneInfo

from api.core.clock import ensure_utc
from api.core.context import RequestContext
from api.core.errors import FieldError, NotFoundError, ValidationFailedError
from api.core.jsonlog import LOGGER_NAME, log_event
from api.metrics.catalog import check_event, person_ref
from api.metrics.privacy import K_ANONYMITY, median_metric, rate_metric, total_metric
from api.metrics.repository import MetricsRepository, StoredEvent
from api.metrics.runtime import MetricsRuntime
from api.metrics.schemas import ProductEventRequest, ProductMetric, ProductMetrics
from api.metrics.windows import aligned_period, event_floor, local_midnight

logger = logging.getLogger(f"{LOGGER_NAME}.metrics")

DEFAULT_PERIOD_DAYS: Final = 30
MAX_PERIOD_DAYS: Final = 366


def _invalid_period(field: str, message: str) -> ValidationFailedError:
    return ValidationFailedError(
        "La période demandée n'est pas valide.",
        "Choisissez une date de début avant la date de fin, sur un an au plus.",
        errors=(FieldError(field, message),),
    )


@dataclass(frozen=True, slots=True)
class MetricsService:
    ctx: RequestContext
    runtime: MetricsRuntime

    @property
    def repo(self) -> MetricsRepository:
        return MetricsRepository(self.ctx.session, self.ctx.principal.organization_id)

    async def record(self, event: ProductEventRequest) -> None:
        check_event(event, self.ctx.principal)
        org = self.ctx.principal.organization_id
        now = ensure_utc(self.runtime.clock.now())
        await self.repo.record(
            StoredEvent(
                name=event.name,
                surface=event.surface,
                role=event.role,
                session_ref=person_ref(self.runtime.pseudonym_key, org, self.ctx.principal.user_id),
                duration_ms=event.duration_ms,
                step=event.step,
                variant=event.variant,
                occurred_at=now,
                expires_at=now + timedelta(days=self.runtime.retention_days),
            )
        )
        log_event(
            logger,
            logging.INFO,
            "metrics.event_recorded",
            organization_id=org,
            event_name=event.name,
            surface=event.surface,
        )

    def _period(self, start: date | None, end: date | None, today: date) -> tuple[date, date]:
        """Période demandée (bornes validées), puis alignée sur des semaines terminées."""
        period_to = end or today
        period_from = start or period_to - timedelta(days=DEFAULT_PERIOD_DAYS - 1)
        if period_from > period_to:
            raise _invalid_period("from", "La date de début dépasse la date de fin.")
        if (period_to - period_from).days + 1 > MAX_PERIOD_DAYS:
            raise _invalid_period("from", f"Période de {MAX_PERIOD_DAYS} jours au plus.")
        aligned = aligned_period(period_from, period_to, today)
        if aligned is None:
            raise _invalid_period(
                "to",
                "Aucune semaine terminée dans la période : les indicateurs sont publiés par "
                "semaines entières (lundi à dimanche), une fois la semaine écoulée.",
            )
        return aligned

    async def product_metrics(self, start: date | None, end: date | None) -> ProductMetrics:
        repo = self.repo
        timezone = await repo.timezone()
        if timezone is None:  # organisation invisible : RLS ou jeton incohérent
            raise NotFoundError
        zone = ZoneInfo(timezone)
        now = ensure_utc(self.runtime.clock.now())
        period_from, period_to = self._period(start, end, now.astimezone(zone).date())
        since = local_midnight(period_from, zone)
        until = local_midnight(period_to + timedelta(days=1), zone)
        # Événements d'usage : semaines intactes (aucune purge possible) et postérieures à la
        # rotation de la clé seulement ; les tables métier ne sont pas purgées.
        events_since = event_floor(
            since, now, self.runtime.retention_days, self.runtime.pseudonym_key_since, zone
        )

        outcomes = await repo.claim_outcomes(since, until, timezone)
        delay = await repo.decision_delay(since, until, timezone)
        counter = await repo.counter_display(events_since, until, now, timezone)
        onboarding = await repo.onboarding(events_since, until, now, timezone)
        first_card = await repo.first_card(events_since, until, now, timezone)
        links = await repo.payment_links(since, until, timezone)
        ledger = await repo.ledger_gap(period_to)
        webhooks = await repo.webhook_duplicates(since, until, timezone)
        items: list[ProductMetric] = [
            rate_metric(
                "claims_auto_approved_rate",
                outcomes.auto,
                outcomes.decided,
                outcomes.contributors,
                outcomes.weakest_window,
            ),
            rate_metric(
                "claims_review_rate",
                outcomes.review,
                outcomes.decided,
                outcomes.contributors,
                outcomes.weakest_window,
            ),
            median_metric("claims_decision_median_ms", *delay),
            median_metric("counter_decision_display_median_ms", *counter),
            rate_metric("onboarding_completion_rate", *onboarding),
            median_metric("first_card_median_ms", *first_card),
            rate_metric("payment_links_paid_rate", *links),
            # Cumul d'écritures équilibrées : aucune semaine à isoler (voir ``ledger_gap``).
            total_metric(
                "ledger_balance_gap_xof", ledger.value, ledger.contributors, ledger.contributors
            ),
            rate_metric("webhook_duplicate_rate", *webhooks),
        ]
        return ProductMetrics(
            period_from=period_from,
            period_to=period_to,
            generated_at=now,
            k_anonymity_threshold=K_ANONYMITY,
            items=items,
        )
