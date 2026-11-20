"""Services des espaces assureur et employeur (P3, CR-P3-01, CR-P3-02) : agrégats k-anonymes.

- ``InsurerService`` : portefeuille de l'organisation du jeton (assureur, admin), export CSV.
- ``EmployerService`` : groupes de la PORTÉE du jeton (attribut ``employer_id``), jamais un
  autre groupe, jamais une personne.
Période publiée : semaines entières et terminées (``period``) ; valeurs publiées par
``privacy`` (seuil par période ET par semaine, comptes par palier, montants au millier).
Calculs entiers : taux en points de base (demi vers le haut), montants en francs CFA.
"""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal
from uuid import UUID

from api.core.clock import Clock, ensure_utc
from api.core.context import RequestContext
from api.core.errors import NotFoundError
from api.core.jsonlog import LOGGER_NAME, log_event
from api.core.services import AuditIntent, AuditService
from api.partners import privacy
from api.partners.period import Period, local_today, published_until, resolve_period
from api.partners.privacy import (
    Cell,
    amount_value,
    count_value,
    fold_cells,
    mask_cells,
    masked,
    measure_value,
    merge,
)
from api.partners.repository import AggregateRepository, Ratio
from api.partners.schemas import (
    BenefitCategory,
    EmployerConsumption,
    EmployerContract,
    EmployerContractList,
    EmployerGroupConsumption,
    InsurerPortfolio,
    KValue,
    OtherProviders,
    ProviderShare,
    StatusCount,
)

logger = logging.getLogger(f"{LOGGER_NAME}.partners")

BASIS_POINTS: Final = 10_000
TOP_PROVIDERS: Final = 5
PORTFOLIO_EXPORTED: Final = "insurer.portfolio_exported"
# Débuts de formule de tableur (y compris leurs formes pleine chasse), après d'éventuels blancs.
_FORMULA_PREFIXES: Final = (
    "=",
    "+",
    "-",
    "@",
    "\t",
    "\r",
    "\n",
    "\uff1d",
    "\uff0b",
    "\uff0d",
    "\uff20",
)


@dataclass(frozen=True, slots=True)
class PartnersRuntime:
    clock: Clock


def rate_bp(numerator: int, denominator: int) -> int | None:
    if denominator <= 0:
        return None
    return (2 * BASIS_POINTS * numerator + denominator) // (2 * denominator)


def _statuses(cells: Sequence[Cell]) -> list[StatusCount]:
    published = mask_cells(cells)
    return [
        StatusCount.model_validate(
            {
                "status": c.key,  # clés fixes : actif, carence, suspendu
                "count": count_value(c) if published[c.key] else masked(),
            }
        )
        for c in cells
    ]


def _members_total(cells: Sequence[Cell]) -> KValue:
    return count_value(merge(cells, "total"))


def _categories(cells: Sequence[Cell]) -> list[BenefitCategory]:
    shown, other = fold_cells(cells)
    rows = [*shown, *([other] if other is not None else [])]
    return [
        BenefitCategory(category=c.key, claims=count_value(c), covered_xof=amount_value(c))
        for c in rows
    ]


def _ratio(ratio: Ratio) -> KValue:
    return measure_value(rate_bp(ratio.numerator, ratio.denominator), ratio.people, ratio.weeks)


def _loss_ratio(claims: Cell, premiums: Cell) -> KValue:
    # Le ratio dépend des sinistrés ET des cotisants : chacun des deux groupes doit passer le
    # seuil (période et semaines) ; l'effectif publié est celui du plus petit.
    if amount_value(claims).status == "masque" or amount_value(premiums).status == "masque":
        return masked()
    smaller = claims if len(claims.people) <= len(premiums.people) else premiums
    return measure_value(rate_bp(claims.amount, premiums.amount), smaller.people, smaller.weeks)


@dataclass(frozen=True, slots=True)
class InsurerService:
    ctx: RequestContext
    runtime: PartnersRuntime

    @property
    def repo(self) -> AggregateRepository:
        return AggregateRepository(self.ctx.session, self.ctx.principal.organization_id)

    async def _period(self, start: date | None, end: date | None) -> tuple[Period, datetime, str]:
        timezone = await self.repo.timezone()
        if timezone is None:  # organisation invisible : RLS ou jeton incohérent
            raise NotFoundError
        now = ensure_utc(self.runtime.clock.now())
        return resolve_period(start, end, now, timezone), now, timezone

    async def portfolio(self, start: date | None, end: date | None) -> InsurerPortfolio:
        period, now, tz = await self._period(start, end)
        repo = self.repo
        since, until = period.since, period.until
        statuses = await repo.members_by_status(until)
        premiums = await repo.premiums(since, until, tz)
        claims = await repo.claims_cost(since, until, tz)
        providers = await repo.providers(since, until, tz)
        names = {str(provider_id): (provider_id, name) for provider_id, name, _ in providers}
        shown, rest = fold_cells([cell for _, _, cell in providers], limit=TOP_PROVIDERS)
        delay = await repo.decision_delay(since, until, tz)
        return InsurerPortfolio(
            period_from=period.start,
            period_to=period.end,
            generated_at=now,
            k_anonymity_threshold=privacy.K_ANONYMITY,
            currency="XOF",
            members_total=_members_total(statuses),
            members_by_status=_statuses(statuses),
            premiums_xof=amount_value(premiums),
            claims_cost_xof=amount_value(claims),
            loss_ratio_bp=_loss_ratio(claims, premiums),
            benefits_by_category=_categories(await repo.benefits_by_category(since, until, tz)),
            top_providers=[
                ProviderShare(
                    provider_id=names[c.key][0],
                    name=names[c.key][1],
                    claims=count_value(c),
                    covered_xof=amount_value(c),
                )
                for c in shown
            ],
            other_providers=OtherProviders(
                claims=count_value(rest) if rest else masked(),
                covered_xof=amount_value(rest) if rest else masked(),
            ),
            decision_delay_mean_ms=measure_value(delay.value, delay.people, delay.weeks),
            automation_rate_bp=_ratio(await repo.automation(since, until, tz)),
        )

    async def export_csv(self, start: date | None, end: date | None) -> str:
        portfolio = await self.portfolio(start, end)
        await AuditService.for_session(self.ctx.session).record(
            self.ctx,
            AuditIntent(
                PORTFOLIO_EXPORTED,
                "organization",
                self.ctx.principal.organization_id,
                {
                    "period_from": portfolio.period_from.isoformat(),
                    "period_to": portfolio.period_to.isoformat(),
                },
            ),
        )
        log_event(
            logger,
            logging.INFO,
            "partners.portfolio_exported",
            organization_id=self.ctx.principal.organization_id,
        )
        return portfolio_csv(portfolio)


def cell_text(value: str) -> str:
    """Neutralise une formule de tableur (CSV injection) : préfixe apostrophe.

    Un tableur ignore les blancs de tête : « =1 » précédé d'espaces reste une formule.
    """
    return f"'{value}" if value.lstrip(" ").startswith(_FORMULA_PREFIXES) else value


def portfolio_csv(portfolio: InsurerPortfolio) -> str:
    rows: list[tuple[str, str, KValue, str]] = [
        ("adherents", "total", portfolio.members_total, "nombre"),
        *(("adherents", s.status, s.count, "nombre") for s in portfolio.members_by_status),
        ("primes", "encaissees", portfolio.premiums_xof, "xof"),
        ("sinistres", "part_mutuelle", portfolio.claims_cost_xof, "xof"),
        ("ratio", "sinistres_sur_primes", portfolio.loss_ratio_bp, "pour_dix_mille"),
    ]
    for category in portfolio.benefits_by_category:
        rows.append(("categorie_dossiers", category.category, category.claims, "nombre"))
        rows.append(("categorie_part_mutuelle", category.category, category.covered_xof, "xof"))
    for provider in portfolio.top_providers:
        rows.append(("prestataire_dossiers", provider.name, provider.claims, "nombre"))
        rows.append(("prestataire_part_mutuelle", provider.name, provider.covered_xof, "xof"))
    rows += [
        ("autres_prestataires", "dossiers", portfolio.other_providers.claims, "nombre"),
        ("autres_prestataires", "part_mutuelle", portfolio.other_providers.covered_xof, "xof"),
        ("decision", "delai_moyen", portfolio.decision_delay_mean_ms, "millisecondes"),
        ("decision", "part_automatique", portfolio.automation_rate_bp, "pour_dix_mille"),
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(["section", "cle", "statut", "valeur", "effectif", "unite"])
    writer.writerow(
        [
            "periode",
            f"{portfolio.period_from.isoformat()}/{portfolio.period_to.isoformat()}",
            "",
            "",
            "",
            "",
        ]
    )
    for section, key, value, unit in rows:
        writer.writerow(
            [
                section,
                cell_text(key),
                value.status,
                "" if value.value is None else str(value.value),
                "" if value.contributors is None else str(value.contributors),
                unit,
            ]
        )
    return buffer.getvalue()


@dataclass(frozen=True, slots=True)
class EmployerService:
    ctx: RequestContext
    runtime: PartnersRuntime

    @property
    def repo(self) -> AggregateRepository:
        return AggregateRepository(self.ctx.session, self.ctx.principal.organization_id)

    def _scope(self) -> list[UUID]:
        access = self.ctx.access
        if access is None:  # pragma: no cover — posé par require_operation
            raise NotFoundError
        # Rôle employeur : toujours restreint à ses groupes (contrainte du contrat).
        return sorted(access.employer_ids, key=str)

    async def _timezone(self) -> str:
        timezone = await self.repo.timezone()
        if timezone is None:
            raise NotFoundError
        return timezone

    async def consumption(self, start: date | None, end: date | None) -> EmployerConsumption:
        now = ensure_utc(self.runtime.clock.now())
        tz = await self._timezone()
        period = resolve_period(start, end, now, tz)
        since, until = period.since, period.until
        repo = self.repo
        groups: list[EmployerGroupConsumption] = []
        for employer in await repo.employers(self._scope()):
            statuses = await repo.members_by_status(until, employer.id)
            claims = await repo.claims_cost(since, until, tz, employer.id)
            groups.append(
                EmployerGroupConsumption(
                    employer_id=employer.id,
                    name=employer.name,
                    members_total=_members_total(statuses),
                    members_by_status=_statuses(statuses),
                    claims=count_value(claims),
                    covered_xof=amount_value(claims),
                    benefits_by_category=_categories(
                        await repo.benefits_by_category(since, until, tz, employer.id)
                    ),
                )
            )
        return EmployerConsumption(
            period_from=period.start,
            period_to=period.end,
            generated_at=now,
            k_anonymity_threshold=privacy.K_ANONYMITY,
            currency="XOF",
            groups=groups,
        )

    async def contracts(self, within_days: int) -> EmployerContractList:
        now = ensure_utc(self.runtime.clock.now())
        tz = await self._timezone()
        today = local_today(now, tz)
        # Effectif : instantané à la fin de la dernière semaine terminée, jamais « en direct ».
        snapshot = published_until(now, tz)
        repo = self.repo
        items: list[EmployerContract] = []
        for employer in await repo.employers(self._scope()):
            remaining = (
                None if employer.contract_end is None else (employer.contract_end - today).days
            )
            state: Literal["en_cours", "a_echeance", "echu", "sans_echeance"]
            if remaining is None:
                state = "sans_echeance"
            elif remaining < 0:
                state = "echu"
            elif remaining <= within_days:
                state = "a_echeance"
            else:
                state = "en_cours"
            items.append(
                EmployerContract(
                    employer_id=employer.id,
                    name=employer.name,
                    contract_start=employer.contract_start,
                    contract_end=employer.contract_end,
                    days_remaining=remaining,
                    status=state,
                    members_total=_members_total(
                        await repo.members_by_status(snapshot, employer.id)
                    ),
                )
            )
        return EmployerContractList(as_of=today, within_days=within_days, items=items)
