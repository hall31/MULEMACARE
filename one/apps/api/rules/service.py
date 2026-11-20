"""Service L2 : produits versionnés, réseau, barème, règles en données, simulation de décision.

- L'organisation vient toujours du principal authentifié (``ctx.principal.organization_id``).
- Publication (R3) : brouillon → soumise → en vigueur, dans la transaction de la requête ; la
  version publiée ouverte qui précède est close la veille de la nouvelle date d'effet (seul
  changement que le contrat permet sur une version publiée). Une version publiée ne se
  republie pas (RUL-01) ; un chevauchement est refusé par la base (RUL-02), tout est annulé.
- ``evaluate`` rassemble les faits et appelle ``engine.evaluate`` : aucune règle n'est
  réimplémentée ici, et rien n'est écrit (aucune décision de prise en charge).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo

from api.core.clock import Clock
from api.core.context import RequestContext
from api.core.pagination import decode_cursor, encode_cursor
from api.core.repositories import Keyset
from api.members.repository import MemberRepository
from api.members.status import end_of_day, unpaid_days
from api.rules import engine, params
from api.rules.errors import (
    InvalidRequestError,
    NoVersionInForceError,
    OverlappingVersionsError,
    PublishedVersionFrozenError,
)
from api.rules.model import ClaimFacts, MemberFacts, Period
from api.rules.model import Decision as EngineDecision
from api.rules.model import RuleVersion as EngineRuleVersion
from api.rules.repository import (
    PUBLISHABLE_STATES,
    CatalogRepository,
    ConventionRecord,
    CoverageRecord,
    NewPlanVersion,
    NotFoundError,
    PlanRecord,
    PlanVersionRecord,
    ProviderRecord,
    RulesRepository,
    RuleVersionRecord,
    TariffRecord,
    VersionTable,
    driver_connection,
)
from api.rules.schemas import (
    Act,
    ActList,
    CreateActRequest,
    CreatePlanRequest,
    CreatePlanVersionRequest,
    CreateProviderConventionRequest,
    CreateProviderRequest,
    CreateRuleVersionRequest,
    CreateTariffItemRequest,
    Decision,
    EvaluateRulesRequest,
    PageInfo,
    Plan,
    PlanList,
    PlanVersion,
    Provider,
    ProviderConvention,
    ProviderList,
    Rule,
    RuleList,
    RuleVersion,
    RuleVersionList,
    TariffItem,
    TariffList,
)
from api.rules.versions import select_in_force

# Schéma fermé des paramètres de chaque règle de décision (lu par le moteur).
PARAM_VALIDATORS: Final[Mapping[str, Callable[[EngineRuleVersion], object]]] = {
    "R-01": params.rights,
    "R-04": params.network,
    "R-07": params.waiting,
    "R-09": params.ceiling,
    "R-12": params.auto_approval,
    "R-20": params.review,
}
PUBLISHED_STATE: Final = "en_vigueur"


def _not_found(what: str) -> NotFoundError:
    return NotFoundError(f"{what} introuvable.", "Vérifiez le lien ou revenez à la liste.")


def _period(valid_from: date, valid_to: date | None) -> Period:
    if valid_to is not None and valid_to < valid_from:
        raise InvalidRequestError(
            "La date de fin précède la date d'effet.",
            "Corrigez la période (fin le même jour ou après la date d'effet).",
        )
    return Period(valid_from, valid_to)


def _overlaps(a: Period, b: Period) -> bool:
    return (a.valid_to is None or b.valid_from <= a.valid_to) and (
        b.valid_to is None or a.valid_from <= b.valid_to
    )


def _in_force[V: (PlanVersionRecord, RuleVersionRecord)](
    versions: Iterable[V], day: date
) -> V | None:
    """Version publiée en vigueur à ``day`` (règle du moteur), ou aucune."""
    try:
        return select_in_force(list(versions), day, what="la version")
    except (NoVersionInForceError, OverlappingVersionsError):
        return None


# --- Conversions vers le contrat ------------------------------------------------------------


def _plan_version_out(v: PlanVersionRecord) -> PlanVersion:
    return PlanVersion.model_validate(
        {
            "id": v.id,
            "plan_id": v.plan_id,
            "version": v.version,
            "valid_from": v.period.valid_from,
            "valid_to": v.period.valid_to,
            "state": v.state,
            "coverage_rate_bp": v.coverage_rate_bp,
            "family_annual_ceiling_xof": v.family_annual_ceiling_xof,
            "waiting_period_days": v.waiting_period_days,
            "monthly_contribution_xof": v.monthly_contribution_xof,
            "coverages": [
                {
                    "category": c.category,
                    "label": c.label,
                    "coverage_rate_bp": c.coverage_rate_bp,
                    "annual_limit_xof": c.annual_limit_xof,
                    "limit_scope": c.limit_scope,
                }
                for c in v.coverages
            ],
        }
    )


def _plan_out(plan: PlanRecord, versions: Sequence[PlanVersionRecord], today: date) -> Plan:
    current = _in_force(versions, today)
    return Plan(
        id=plan.id,
        code=plan.code,
        name=plan.name,
        status=plan.status,  # type: ignore[arg-type]  # CHECK de la base
        current_version_id=None if current is None else current.id,
        versions=[_plan_version_out(v) for v in versions],
    )


def _provider_out(
    provider: ProviderRecord, conventions: Sequence[ConventionRecord], day: date
) -> Provider:
    return Provider.model_validate(
        {
            "id": provider.id,
            "name": provider.name,
            "kind": provider.kind,
            "city": provider.city,
            "country_code": provider.country_code,
            "status": provider.status,
            "conventioned": any(c.period.contains(day) for c in conventions),
            "conventions": [_convention_out(c) for c in conventions],
        }
    )


def _convention_out(c: ConventionRecord) -> ProviderConvention:
    return ProviderConvention(id=c.id, valid_from=c.period.valid_from, valid_to=c.period.valid_to)


def _tariff_out(t: TariffRecord) -> TariffItem:
    return TariffItem(
        act_code=t.act_code,
        label=t.label,
        amount_xof=t.amount_xof,
        valid_from=t.period.valid_from,
        valid_to=t.period.valid_to,
        requires_prior_approval=t.requires_prior_approval,
    )


def _rule_version_out(v: RuleVersionRecord) -> RuleVersion:
    return RuleVersion.model_validate(
        {
            "id": v.id,
            "rule_code": v.rule_code,
            "version": v.version,
            "valid_from": v.period.valid_from,
            "valid_to": v.period.valid_to,
            "state": v.state,
            "params": dict(v.params),
        }
    )


def decision_out(decision: EngineDecision) -> Decision:
    return Decision.model_validate(
        {
            "outcome": decision.outcome.value,
            "rule": {"code": decision.rule.code, "version": decision.rule.version},
            "reason_code": decision.reason_code,
            "message": decision.message,
            "total_xof": decision.total_xof,
            "covered_xof": decision.covered_xof,
            "patient_share_xof": decision.patient_share_xof,
            "currency": decision.currency,
            "plan_version_id": decision.plan_version_id,
            "review_due_at": decision.review_due_at,
            "checks": [
                {
                    "rule": {"code": c.rule.code, "version": c.rule.version},
                    "passed": c.passed,
                    "message": c.message,
                }
                for c in decision.checks
            ],
        }
    )


# --- Service ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CatalogService:
    ctx: RequestContext
    clock: Clock

    @property
    def org(self) -> UUID:
        return self.ctx.principal.organization_id

    @property
    def repo(self) -> CatalogRepository:
        return CatalogRepository(self.ctx.session)

    async def today(self) -> date:
        """Jour civil courant dans le fuseau de l'organisation."""
        timezone = await self.repo.organization_timezone(self.org)
        return self.clock.now().astimezone(ZoneInfo(timezone)).date()

    # --- Produits ----------------------------------------------------------------------------

    async def _plans(self, plan_id: UUID | None = None) -> list[Plan]:
        plans = await self.repo.plans(self.org, plan_id)
        versions = await self.repo.plan_versions(self.org, plan_ids=[p.id for p in plans])
        today = await self.today()
        return [_plan_out(p, [v for v in versions if v.plan_id == p.id], today) for p in plans]

    async def list_plans(self) -> PlanList:
        return PlanList(items=await self._plans())

    async def get_plan(self, plan_id: UUID) -> Plan:
        found = await self._plans(plan_id)
        if not found:
            raise _not_found("Produit")
        return found[0]

    async def create_plan(self, body: CreatePlanRequest) -> Plan:
        plan = await self.repo.insert_plan(self.org, body.code, body.name)
        return _plan_out(plan, [], await self.today())

    async def _plan_version(self, version_id: UUID) -> PlanVersionRecord:
        found = await self.repo.plan_versions(self.org, version_id=version_id)
        if not found:
            raise _not_found("Version de produit")
        return found[0]

    async def get_plan_version(self, version_id: UUID) -> PlanVersion:
        return _plan_version_out(await self._plan_version(version_id))

    async def create_plan_version(
        self, plan_id: UUID, body: CreatePlanVersionRequest
    ) -> PlanVersion:
        categories = [c.category for c in body.coverages]
        if len(set(categories)) != len(categories):
            raise InvalidRequestError(
                "Une garantie apparaît deux fois dans la version.",
                "Gardez une seule ligne par catégorie de garantie.",
            )
        period = _period(body.valid_from, body.valid_to)
        if not await self.repo.lock_plan(self.org, plan_id):
            raise _not_found("Produit")
        version_id = await self.repo.insert_plan_version(
            self.org,
            plan_id,
            NewPlanVersion(
                period=period,
                coverage_rate_bp=body.coverage_rate_bp,
                family_annual_ceiling_xof=body.family_annual_ceiling_xof,
                waiting_period_days=body.waiting_period_days,
                monthly_contribution_xof=body.monthly_contribution_xof,
                coverages=tuple(
                    CoverageRecord(
                        c.category, c.label, c.coverage_rate_bp, c.annual_limit_xof, c.limit_scope
                    )
                    for c in body.coverages
                ),
            ),
        )
        return await self.get_plan_version(version_id)

    async def _publish(self, table: VersionTable, version_id: UUID, what: str) -> None:
        found = await self.repo.version_to_publish(table, self.org, version_id)
        if found is None:
            raise _not_found(what)
        parent_id, state, valid_from = found
        if state not in PUBLISHABLE_STATES:
            raise PublishedVersionFrozenError(
                "Cette version est déjà publiée : elle ne peut plus changer.",
                "Créez une nouvelle version avec sa date d'effet.",
            )
        await self.repo.close_open_predecessor(table, self.org, parent_id, version_id, valid_from)
        if state == "brouillon":
            await self.repo.set_state(table, self.org, version_id, "soumise")
        await self.repo.set_state(
            table,
            self.org,
            version_id,
            PUBLISHED_STATE,
            (self.ctx.principal.user_id, self.clock.now()),
        )

    async def publish_plan_version(self, version_id: UUID) -> PlanVersion:
        await self._publish("plan_versions", version_id, "Version de produit")
        return await self.get_plan_version(version_id)

    # --- Réseau ------------------------------------------------------------------------------

    async def _providers_out(
        self, providers: Sequence[ProviderRecord], day: date
    ) -> list[Provider]:
        conventions = await self.repo.conventions(self.org, [p.id for p in providers])
        return [
            _provider_out(p, [c for c in conventions if c.provider_id == p.id], day)
            for p in providers
        ]

    async def list_providers(self, at: date | None, cursor: str | None, limit: int) -> ProviderList:
        position = decode_cursor(cursor)
        after = None if position is None else (position.at, position.id)
        rows = await self.repo.providers_page(self.org, after, limit + 1)
        page, more = rows[:limit], len(rows) > limit
        last = page[-1] if more and page else None
        return ProviderList(
            items=await self._providers_out(page, at or await self.today()),
            page=PageInfo(
                next_cursor=None
                if last is None
                else encode_cursor(Keyset(last.created_at, last.id))
            ),
        )

    async def get_provider(self, provider_id: UUID) -> Provider:
        provider = await self.repo.provider(self.org, provider_id)
        if provider is None:
            raise _not_found("Prestataire")
        return (await self._providers_out([provider], await self.today()))[0]

    async def create_provider(self, body: CreateProviderRequest) -> Provider:
        provider = await self.repo.insert_provider(
            self.org, body.name, body.kind, body.city, body.country_code
        )
        return _provider_out(provider, [], await self.today())

    async def create_convention(
        self, provider_id: UUID, body: CreateProviderConventionRequest
    ) -> ProviderConvention:
        period = _period(body.valid_from, body.valid_to)
        if await self.repo.provider(self.org, provider_id, lock=True) is None:
            raise _not_found("Prestataire")
        existing = await self.repo.conventions(self.org, [provider_id])
        if any(_overlaps(c.period, period) for c in existing):
            raise OverlappingVersionsError(
                "Cette période chevauche une convention existante du prestataire.",
                "Choisissez une date d'effet après la fin de la convention en cours.",
            )
        return _convention_out(await self.repo.insert_convention(self.org, provider_id, period))

    # --- Nomenclature et barème --------------------------------------------------------------

    async def list_tariffs(self, at: date | None) -> TariffList:
        day = at or await self.today()
        return TariffList(at=day, items=[_tariff_out(t) for t in await self.repo.tariffs(
            self.org, at=day
        )])  # fmt: skip

    async def list_acts(self) -> ActList:
        acts = await self.repo.acts(self.org)
        return ActList(items=[Act.model_validate(a, from_attributes=True) for a in acts])

    async def create_act(self, body: CreateActRequest) -> Act:
        act = await self.repo.insert_act(
            self.org, body.code, body.label, body.coverage_category, body.requires_prior_approval
        )
        return Act.model_validate(act, from_attributes=True)

    async def create_tariff(self, act_id: UUID, body: CreateTariffItemRequest) -> TariffItem:
        period = _period(body.valid_from, body.valid_to)
        if not await self.repo.acts(self.org, act_id, lock=True):
            raise _not_found("Acte")
        existing = await self.repo.tariffs(self.org, act_id=act_id)
        if any(_overlaps(t.period, period) for t in existing):
            raise OverlappingVersionsError(
                "Cet acte a déjà un montant de barème sur cette période.",
                "Choisissez une date d'effet après la fin du montant en cours.",
            )
        await self.repo.insert_tariff(self.org, act_id, body.amount_xof, period)
        created = [t for t in await self.repo.tariffs(self.org, act_id=act_id)
                   if t.period.valid_from == period.valid_from]  # fmt: skip
        return _tariff_out(created[0])

    # --- Règles ------------------------------------------------------------------------------

    async def list_rules(self) -> RuleList:
        rules = await self.repo.rules(self.org)
        versions = await self.repo.rule_versions(self.org, rule_ids=[r.id for r in rules])
        today = await self.today()
        items = []
        for rule in rules:
            current = _in_force((v for v in versions if v.rule_id == rule.id), today)
            items.append(
                Rule.model_validate(
                    {
                        "code": rule.code,
                        "label": rule.label,
                        "kind": rule.kind,
                        "current_version": None if current is None else _rule_version_out(current),
                    }
                )
            )
        return RuleList(items=items)

    async def list_rule_versions(self, code: str) -> RuleVersionList:
        rules = await self.repo.rules(self.org, code)
        if not rules:
            raise _not_found("Règle")
        versions = await self.repo.rule_versions(self.org, rule_ids=[rules[0].id])
        return RuleVersionList(items=[_rule_version_out(v) for v in versions])

    async def create_rule_version(self, code: str, body: CreateRuleVersionRequest) -> RuleVersion:
        period = _period(body.valid_from, body.valid_to)
        rules = await self.repo.rules(self.org, code, lock=True)
        if not rules:
            raise _not_found("Règle")
        try:
            params_json = json.dumps(body.params, allow_nan=False)
        except ValueError as exc:
            raise InvalidRequestError(
                "Les paramètres contiennent une valeur numérique invalide.",
                "Utilisez des nombres finis (montants en entiers FCFA).",
            ) from exc
        version_id = await self.repo.insert_rule_version(self.org, rules[0].id, period, params_json)
        created = (await self.repo.rule_versions(self.org, version_id=version_id))[0]
        validate = PARAM_VALIDATORS.get(created.rule_code)
        if validate is not None:  # erreur = annulation de la transaction, rien n'est créé
            validate(
                EngineRuleVersion(
                    rule_id=created.rule_id,
                    code=created.rule_code,
                    version=created.version,
                    period=created.period,
                    state=created.state,
                    params=created.params,
                )
            )
        return _rule_version_out(created)

    async def publish_rule_version(self, version_id: UUID) -> RuleVersion:
        await self._publish("rule_versions", version_id, "Version de règle")
        return _rule_version_out(
            (await self.repo.rule_versions(self.org, version_id=version_id))[0]
        )

    # --- Simulation --------------------------------------------------------------------------

    async def evaluate(self, body: EvaluateRulesRequest) -> Decision:
        """Faits à la date du soin → ``engine.evaluate``. Lecture seule."""
        members = MemberRepository(self.ctx.session)
        member = await members.get(self.org, body.member_id)
        if member is None or not await members.is_beneficiary(
            self.org, body.member_id, body.beneficiary_id
        ):
            raise _not_found("Adhérent ou bénéficiaire")
        timezone = await self.repo.organization_timezone(self.org)
        day = body.service_date
        rules = RulesRepository(await driver_connection(self.ctx.session))
        catalog = await rules.catalog(self.org, member.plan_id)
        provider = await rules.provider_facts(self.org, body.provider_id)
        items = await rules.claim_items(self.org, [(i.act_code, i.quantity) for i in body.items])
        status = await members.status_at(self.org, member.id, end_of_day(day, timezone))
        facts = ClaimFacts(
            plan_id=member.plan_id,
            service_date=day,
            evaluated_at=self.clock.now(),
            member=MemberFacts(
                status=status or member.status,
                enrolled_on=member.enrolled_on,
                unpaid_days=await unpaid_days(members, self.org, member.id, day, timezone),
            ),
            provider=provider,
            items=tuple(items),
            # Consommation de l'année civile du soin (même période que L4/L5, Q-L0-07).
            family_consumed_xof=await members.consumed_xof(
                self.org, member.id, date(day.year, 1, 1), date(day.year, 12, 31)
            ),
            fraud_score=body.fraud_score,
        )
        return decision_out(engine.evaluate(facts, catalog))
