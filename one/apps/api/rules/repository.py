"""Dépôts des produits, règles, barème et réseau (async).

- ``RulesRepository`` (lecture seule, psycopg) : charge le catalogue publié pour le moteur ;
  le moteur (``engine.evaluate``) décide sans base.
- ``CatalogRepository`` (session de la requête) : gestion du catalogue par les routes L2.

Chaque requête est sous RLS forcée (``app.organization_id``) ET filtre explicitement par
``organization_id`` : l'organisation vient toujours de l'appelant (jeton), jamais du client.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Final, Literal
from uuid import UUID

import psycopg
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from api.rules.errors import (
    DuplicateCodeError,
    OverlappingVersionsError,
    PublishedVersionFrozenError,
    RulesError,
)
from api.rules.model import (
    APPLICABLE_STATES,
    Catalog,
    ClaimItem,
    Coverage,
    Period,
    PlanVersion,
    ProviderFacts,
    RuleVersion,
    Tariff,
)

_STATES = sorted(APPLICABLE_STATES)


class NotFoundError(RulesError):
    """Enregistrement introuvable dans l'organisation."""

    code = "NOT-01"
    http_status = 404


class RulesRepository:
    """Lecture des versions publiées ; brouillons et versions soumises ne sont jamais chargés."""

    def __init__(self, conn: psycopg.AsyncConnection[Any]) -> None:
        self._conn = conn

    @asynccontextmanager
    async def _scoped(self, organization_id: UUID) -> AsyncIterator[psycopg.AsyncConnection[Any]]:
        async with self._conn.transaction():
            await self._conn.execute(
                "SELECT set_config('app.organization_id', %s, true)", (str(organization_id),)
            )
            yield self._conn

    async def catalog(self, organization_id: UUID, plan_id: UUID) -> Catalog:
        """Historique publié d'un produit et de toutes les règles de l'organisation."""
        async with self._scoped(organization_id) as conn:
            rule_rows = await (
                await conn.execute(
                    "SELECT v.rule_id, r.code, v.version, v.valid_from, v.valid_to, v.state, "
                    "v.params FROM rule_versions v "
                    "JOIN rules r ON r.organization_id = v.organization_id AND r.id = v.rule_id "
                    "WHERE v.organization_id = %s AND v.state = ANY(%s) "
                    "ORDER BY r.code, v.version",
                    (organization_id, _STATES),
                )
            ).fetchall()
            plan_rows = await (
                await conn.execute(
                    "SELECT id, plan_id, version, valid_from, valid_to, state, coverage_rate_bp, "
                    "family_annual_ceiling_xof, waiting_period_days FROM plan_versions "
                    "WHERE organization_id = %s AND plan_id = %s AND state = ANY(%s) "
                    "ORDER BY version",
                    (organization_id, plan_id, _STATES),
                )
            ).fetchall()
            coverage_rows = await (
                await conn.execute(
                    "SELECT c.plan_version_id, c.category, c.coverage_rate_bp FROM coverages c "
                    "JOIN plan_versions v ON v.organization_id = c.organization_id "
                    "AND v.id = c.plan_version_id "
                    "WHERE c.organization_id = %s AND v.plan_id = %s ORDER BY c.category",
                    (organization_id, plan_id),
                )
            ).fetchall()

        coverages: dict[UUID, list[Coverage]] = {}
        for version_id, category, rate in coverage_rows:
            coverages.setdefault(version_id, []).append(Coverage(category, rate))

        rules = tuple(
            RuleVersion(
                rule_id=rule_id,
                code=code,
                version=version,
                period=Period(valid_from, valid_to),
                state=state,
                params=params,
            )
            for rule_id, code, version, valid_from, valid_to, state, params in rule_rows
        )
        plans = tuple(
            PlanVersion(
                id=version_id,
                plan_id=plan,
                version=version,
                period=Period(valid_from, valid_to),
                state=state,
                coverage_rate_bp=rate,
                family_annual_ceiling_xof=int(ceiling),
                waiting_period_days=waiting,
                coverages=tuple(coverages.get(version_id, ())),
            )
            for version_id, plan, version, valid_from, valid_to, state, rate, ceiling, waiting in (
                plan_rows
            )
        )
        return Catalog(plan_versions=plans, rule_versions=rules)

    async def claim_items(
        self, organization_id: UUID, lines: Sequence[tuple[str, int]]
    ) -> list[ClaimItem]:
        """Lignes de soin (code d'acte, quantité) avec tout le barème daté de chaque acte.

        Un acte inconnu garde un barème vide : le moteur le refuse en R-04 (hors barème).
        """
        codes = sorted({code for code, _ in lines})
        async with self._scoped(organization_id) as conn:
            rows = await (
                await conn.execute(
                    "SELECT a.code, a.coverage_category, t.amount_xof, t.valid_from, t.valid_to "
                    "FROM acts a LEFT JOIN tariff_items t "
                    "ON t.organization_id = a.organization_id AND t.act_id = a.id "
                    "WHERE a.organization_id = %s AND a.code = ANY(%s) "
                    "ORDER BY a.code, t.valid_from",
                    (organization_id, codes),
                )
            ).fetchall()

        categories: dict[str, str] = {}
        tariffs: dict[str, list[Tariff]] = {}
        for code, category, amount, valid_from, valid_to in rows:
            categories[code] = category
            bucket = tariffs.setdefault(code, [])
            if amount is not None:
                bucket.append(Tariff(int(amount), Period(valid_from, valid_to)))
        return [
            ClaimItem(
                act_code=code,
                coverage_category=categories.get(code, ""),
                quantity=quantity,
                tariffs=tuple(tariffs.get(code, ())),
            )
            for code, quantity in lines
        ]

    async def provider_facts(self, organization_id: UUID, provider_id: UUID) -> ProviderFacts:
        """Statut et périodes de convention d'un prestataire (R-04)."""
        async with self._scoped(organization_id) as conn:
            provider = await (
                await conn.execute(
                    "SELECT status FROM providers WHERE organization_id = %s AND id = %s",
                    (organization_id, provider_id),
                )
            ).fetchone()
            if provider is None:
                raise NotFoundError(
                    "Prestataire introuvable.",
                    "Vérifiez l'établissement sélectionné ou contactez le gestionnaire.",
                )
            conventions = await (
                await conn.execute(
                    "SELECT valid_from, valid_to FROM provider_conventions "
                    "WHERE organization_id = %s AND provider_id = %s ORDER BY valid_from",
                    (organization_id, provider_id),
                )
            ).fetchall()
        return ProviderFacts(
            active=provider[0] == "actif",
            conventions=tuple(Period(start, end) for start, end in conventions),
        )


async def driver_connection(session: AsyncSession) -> psycopg.AsyncConnection[Any]:
    """Connexion psycopg de la transaction de la requête (même RLS, même rôle)."""
    connection = await session.connection()
    raw = await connection.get_raw_connection()
    driver = raw.driver_connection
    if not isinstance(driver, psycopg.AsyncConnection):
        msg = "pilote inattendu : psycopg asynchrone attendu"
        raise TypeError(msg)
    return driver


# --- Gestion du catalogue (routes L2) -----------------------------------------------------------

type VersionTable = Literal["plan_versions", "rule_versions"]

# Colonne parent et état publiable de chaque table versionnée (liste fermée : jamais du client).
_PARENT: Final[Mapping[str, str]] = {"plan_versions": "plan_id", "rule_versions": "rule_id"}
PUBLISHABLE_STATES: Final = frozenset({"brouillon", "soumise"})

# SQLSTATE propres au contrat (specs/schema.sql) et violation d'unicité.
_SQLSTATE_ERRORS: Final[Mapping[str, tuple[type[RulesError], str, str]]] = {
    "MCR01": (
        PublishedVersionFrozenError,
        "Cette version est déjà publiée : elle ne peut plus changer.",
        "Créez une nouvelle version avec sa date d'effet.",
    ),
    "MCR02": (
        OverlappingVersionsError,
        "La période de cette version chevauche une version déjà publiée.",
        "Choisissez une date d'effet postérieure à la dernière version publiée.",
    ),
    "23505": (
        DuplicateCodeError,
        "Ce code est déjà utilisé dans votre organisation.",
        "Choisissez un autre code ou modifiez l'élément existant.",
    ),
}


@dataclass(frozen=True, slots=True)
class PlanRecord:
    id: UUID
    code: str
    name: str
    status: str


@dataclass(frozen=True, slots=True)
class CoverageRecord:
    category: str
    label: str
    coverage_rate_bp: int | None
    annual_limit_xof: int | None
    limit_scope: str


@dataclass(frozen=True, slots=True)
class PlanVersionRecord:
    id: UUID
    plan_id: UUID
    version: int
    period: Period
    state: str
    coverage_rate_bp: int
    family_annual_ceiling_xof: int
    waiting_period_days: int
    monthly_contribution_xof: int
    coverages: tuple[CoverageRecord, ...]


@dataclass(frozen=True, slots=True)
class NewPlanVersion:
    period: Period
    coverage_rate_bp: int
    family_annual_ceiling_xof: int
    waiting_period_days: int
    monthly_contribution_xof: int
    coverages: tuple[CoverageRecord, ...]


@dataclass(frozen=True, slots=True)
class ProviderRecord:
    id: UUID
    name: str
    kind: str
    city: str
    country_code: str
    status: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ConventionRecord:
    id: UUID
    provider_id: UUID
    period: Period


@dataclass(frozen=True, slots=True)
class ActRecord:
    id: UUID
    code: str
    label: str
    coverage_category: str
    requires_prior_approval: bool


@dataclass(frozen=True, slots=True)
class TariffRecord:
    act_code: str
    label: str
    amount_xof: int
    period: Period
    requires_prior_approval: bool


@dataclass(frozen=True, slots=True)
class RuleRecord:
    id: UUID
    code: str
    label: str
    kind: str


@dataclass(frozen=True, slots=True)
class RuleVersionRecord:
    id: UUID
    rule_id: UUID
    rule_code: str
    version: int
    period: Period
    state: str
    params: Mapping[str, object]


_PROVIDER_SELECT: Final = (
    "SELECT id, name, kind, city, country_code, status, created_at FROM providers "
    "WHERE organization_id = :org AND id = :id"
)
_PROVIDER_SELECT_LOCK: Final = (
    "SELECT id, name, kind, city, country_code, status, created_at FROM providers "
    "WHERE organization_id = :org AND id = :id FOR UPDATE"
)
_ACTS_SELECT: Final = (
    "SELECT id, code, label, coverage_category, requires_prior_approval FROM acts "
    "WHERE organization_id = :org AND (CAST(:act AS uuid) IS NULL OR id = :act) ORDER BY code"
)
_ACTS_SELECT_LOCK: Final = (
    "SELECT id, code, label, coverage_category, requires_prior_approval FROM acts "
    "WHERE organization_id = :org AND (CAST(:act AS uuid) IS NULL OR id = :act) ORDER BY code "
    "FOR UPDATE"
)
_RULES_SELECT: Final = (
    "SELECT id, code, label, kind FROM rules WHERE organization_id = :org "
    "AND (CAST(:code AS text) IS NULL OR code = :code) ORDER BY code"
)
_RULES_SELECT_LOCK: Final = (
    "SELECT id, code, label, kind FROM rules WHERE organization_id = :org "
    "AND (CAST(:code AS text) IS NULL OR code = :code) ORDER BY code FOR UPDATE"
)


def _provider(row: Sequence[Any]) -> ProviderRecord:
    return ProviderRecord(row[0], row[1], row[2], row[3], str(row[4]), row[5], row[6])


def _rule_version(row: Sequence[Any]) -> RuleVersionRecord:
    return RuleVersionRecord(
        row[0], row[1], row[2], row[3], Period(row[4], row[5]), row[6], dict(row[7])
    )


class CatalogRepository:
    """Lecture et écriture du catalogue dans la transaction de la requête (RLS forcée)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _rows(self, query: str, params: Mapping[str, object]) -> Sequence[Any]:
        try:
            result = await self._session.execute(text(query), dict(params))
            if isinstance(result, CursorResult) and not result.returns_rows:
                return []  # INSERT / UPDATE sans RETURNING
            return result.all()
        except DBAPIError as exc:
            sqlstate = getattr(exc.orig, "sqlstate", None)
            if isinstance(sqlstate, str) and sqlstate in _SQLSTATE_ERRORS:
                error, message, action = _SQLSTATE_ERRORS[sqlstate]
                raise error(message, action) from exc
            raise

    async def _first(self, query: str, params: Mapping[str, object]) -> Any:  # noqa: ANN401
        rows = await self._rows(query, params)
        return rows[0] if rows else None

    async def organization_timezone(self, org: UUID) -> str:
        row = await self._first("SELECT timezone FROM organizations WHERE id = :org", {"org": org})
        if row is None:  # organisation invisible : RLS ou jeton incohérent
            raise NotFoundError("Organisation introuvable.", "Reconnectez-vous puis recommencez.")
        return str(row[0])

    # --- Produits ------------------------------------------------------------------------------

    async def plans(self, org: UUID, plan_id: UUID | None = None) -> list[PlanRecord]:
        rows = await self._rows(
            "SELECT id, code, name, status FROM plans WHERE organization_id = :org "
            "AND (CAST(:plan AS uuid) IS NULL OR id = :plan) ORDER BY code",
            {"org": org, "plan": plan_id},
        )
        return [PlanRecord(*row) for row in rows]

    async def lock_plan(self, org: UUID, plan_id: UUID) -> bool:
        row = await self._first(
            "SELECT 1 FROM plans WHERE organization_id = :org AND id = :plan FOR UPDATE",
            {"org": org, "plan": plan_id},
        )
        return row is not None

    async def insert_plan(self, org: UUID, code: str, name: str) -> PlanRecord:
        row = await self._first(
            "INSERT INTO plans (organization_id, code, name) VALUES (:org, :code, :name) "
            "RETURNING id, code, name, status",
            {"org": org, "code": code, "name": name},
        )
        return PlanRecord(*row)

    async def plan_versions(
        self, org: UUID, *, plan_ids: Sequence[UUID] = (), version_id: UUID | None = None
    ) -> list[PlanVersionRecord]:
        rows = await self._rows(
            "SELECT id, plan_id, version, valid_from, valid_to, state, coverage_rate_bp, "
            "family_annual_ceiling_xof, waiting_period_days, monthly_contribution_xof "
            "FROM plan_versions WHERE organization_id = :org "
            "AND (plan_id = ANY(:plans) OR id = :version) ORDER BY plan_id, version",
            {"org": org, "plans": list(plan_ids), "version": version_id},
        )
        coverage_rows = await self._rows(
            "SELECT plan_version_id, category, label, coverage_rate_bp, annual_limit_xof, "
            "limit_scope FROM coverages WHERE organization_id = :org "
            "AND plan_version_id = ANY(:versions) ORDER BY category",
            {"org": org, "versions": [row[0] for row in rows]},
        )
        coverages: dict[UUID, list[CoverageRecord]] = {}
        for version_id_, category, label, rate, limit, scope in coverage_rows:
            amount = None if limit is None else int(limit)
            coverages.setdefault(version_id_, []).append(
                CoverageRecord(category, label, rate, amount, scope)
            )
        return [
            PlanVersionRecord(
                id=row[0],
                plan_id=row[1],
                version=row[2],
                period=Period(row[3], row[4]),
                state=row[5],
                coverage_rate_bp=row[6],
                family_annual_ceiling_xof=int(row[7]),
                waiting_period_days=row[8],
                monthly_contribution_xof=int(row[9]),
                coverages=tuple(coverages.get(row[0], ())),
            )
            for row in rows
        ]

    async def insert_plan_version(self, org: UUID, plan_id: UUID, new: NewPlanVersion) -> UUID:
        """Brouillon numéroté à la suite (le produit doit être verrouillé par l'appelant)."""
        row = await self._first(
            "INSERT INTO plan_versions (organization_id, plan_id, version, valid_from, valid_to, "
            "coverage_rate_bp, family_annual_ceiling_xof, waiting_period_days, "
            "monthly_contribution_xof) SELECT :org, :plan, coalesce(max(version), 0) + 1, "
            ":valid_from, :valid_to, :rate, :ceiling, :waiting, :monthly FROM plan_versions "
            "WHERE organization_id = :org AND plan_id = :plan RETURNING id",
            {
                "org": org,
                "plan": plan_id,
                "valid_from": new.period.valid_from,
                "valid_to": new.period.valid_to,
                "rate": new.coverage_rate_bp,
                "ceiling": new.family_annual_ceiling_xof,
                "waiting": new.waiting_period_days,
                "monthly": new.monthly_contribution_xof,
            },
        )
        version_id: UUID = row[0]
        for coverage in new.coverages:
            await self._rows(
                "INSERT INTO coverages (organization_id, plan_version_id, category, label, "
                "coverage_rate_bp, annual_limit_xof, limit_scope) "
                "VALUES (:org, :version, :category, :label, :rate, :limit, :scope)",
                {
                    "org": org,
                    "version": version_id,
                    "category": coverage.category,
                    "label": coverage.label,
                    "rate": coverage.coverage_rate_bp,
                    "limit": coverage.annual_limit_xof,
                    "scope": coverage.limit_scope,
                },
            )
        return version_id

    # --- Publication (produits et règles) --------------------------------------------------------

    async def version_to_publish(
        self, table: VersionTable, org: UUID, version_id: UUID
    ) -> tuple[UUID, str, date] | None:
        """(parent, état, date d'effet) de la version, verrouillée pour la publication."""
        parent = _PARENT[table]
        row = await self._first(
            f"SELECT {parent}, state, valid_from FROM {table} "  # noqa: S608 — liste fermée
            "WHERE organization_id = :org AND id = :id FOR UPDATE",
            {"org": org, "id": version_id},
        )
        return None if row is None else (row[0], str(row[1]), row[2])

    async def close_open_predecessor(
        self, table: VersionTable, org: UUID, parent_id: UUID, version_id: UUID, valid_from: date
    ) -> None:
        """Clôt la veille la version publiée ouverte qui commence avant ``valid_from``.

        Seul changement permis par le contrat sur une version publiée (``valid_to``, une fois).
        """
        parent = _PARENT[table]
        await self._rows(
            f"UPDATE {table} SET valid_to = :closing "  # noqa: S608 — liste fermée
            f"WHERE organization_id = :org AND {parent} = :parent AND id <> :id "
            "AND state <> 'brouillon' AND valid_to IS NULL AND valid_from < :valid_from",
            {
                "org": org,
                "parent": parent_id,
                "id": version_id,
                "valid_from": valid_from,
                "closing": valid_from - timedelta(days=1),
            },
        )

    async def set_state(
        self,
        table: VersionTable,
        org: UUID,
        version_id: UUID,
        state: str,
        approval: tuple[UUID, datetime] | None = None,
    ) -> None:
        """Change l'état ; ``approval`` = (approbateur, instant) à la mise en vigueur."""
        approved_by, approved_at = approval if approval is not None else (None, None)
        await self._rows(
            f"UPDATE {table} SET state = :state, "  # noqa: S608 — liste fermée
            "approved_by = coalesce(:by, approved_by), approved_at = coalesce(:at, approved_at) "
            "WHERE organization_id = :org AND id = :id",
            {"org": org, "id": version_id, "state": state, "by": approved_by, "at": approved_at},
        )

    # --- Réseau ----------------------------------------------------------------------------------

    async def providers_page(
        self, org: UUID, after: tuple[datetime, UUID] | None, limit: int
    ) -> list[ProviderRecord]:
        """Page ordonnée par (création, id), après la position ``after`` (exclue)."""
        rows = await self._rows(
            "SELECT id, name, kind, city, country_code, status, created_at FROM providers "
            "WHERE organization_id = :org "
            "AND (CAST(:at AS timestamptz) IS NULL OR (created_at, id) > (:at, :id)) "
            "ORDER BY created_at, id LIMIT :limit",
            {
                "org": org,
                "at": after[0] if after else None,
                "id": after[1] if after else None,
                "limit": limit,
            },
        )
        return [_provider(row) for row in rows]

    async def provider(
        self, org: UUID, provider_id: UUID, *, lock: bool = False
    ) -> ProviderRecord | None:
        row = await self._first(
            _PROVIDER_SELECT_LOCK if lock else _PROVIDER_SELECT,
            {"org": org, "id": provider_id},
        )
        return None if row is None else _provider(row)

    async def insert_provider(
        self, org: UUID, name: str, kind: str, city: str, country_code: str
    ) -> ProviderRecord:
        row = await self._first(
            "INSERT INTO providers (organization_id, name, kind, city, country_code) "
            "VALUES (:org, :name, :kind, :city, :country) "
            "RETURNING id, name, kind, city, country_code, status, created_at",
            {"org": org, "name": name, "kind": kind, "city": city, "country": country_code},
        )
        return _provider(row)

    async def conventions(self, org: UUID, provider_ids: Sequence[UUID]) -> list[ConventionRecord]:
        rows = await self._rows(
            "SELECT id, provider_id, valid_from, valid_to FROM provider_conventions "
            "WHERE organization_id = :org AND provider_id = ANY(:providers) "
            "ORDER BY provider_id, valid_from",
            {"org": org, "providers": list(provider_ids)},
        )
        return [ConventionRecord(row[0], row[1], Period(row[2], row[3])) for row in rows]

    async def insert_convention(
        self, org: UUID, provider_id: UUID, period: Period
    ) -> ConventionRecord:
        row = await self._first(
            "INSERT INTO provider_conventions (organization_id, provider_id, valid_from, valid_to) "
            "VALUES (:org, :provider, :valid_from, :valid_to) "
            "RETURNING id, provider_id, valid_from, valid_to",
            {
                "org": org,
                "provider": provider_id,
                "valid_from": period.valid_from,
                "valid_to": period.valid_to,
            },
        )
        return ConventionRecord(row[0], row[1], Period(row[2], row[3]))

    # --- Nomenclature et barème ----------------------------------------------------------------

    async def acts(
        self, org: UUID, act_id: UUID | None = None, *, lock: bool = False
    ) -> list[ActRecord]:
        rows = await self._rows(
            _ACTS_SELECT_LOCK if lock else _ACTS_SELECT,
            {"org": org, "act": act_id},
        )
        return [ActRecord(*row) for row in rows]

    async def insert_act(
        self, org: UUID, code: str, label: str, category: str, prior_approval: bool
    ) -> ActRecord:
        row = await self._first(
            "INSERT INTO acts (organization_id, code, label, coverage_category, "
            "requires_prior_approval) VALUES (:org, :code, :label, :category, :prior) "
            "RETURNING id, code, label, coverage_category, requires_prior_approval",
            {
                "org": org,
                "code": code,
                "label": label,
                "category": category,
                "prior": prior_approval,
            },
        )
        return ActRecord(*row)

    async def tariffs(
        self, org: UUID, *, at: date | None = None, act_id: UUID | None = None
    ) -> list[TariffRecord]:
        """Barème en vigueur à ``at`` et/ou tout le barème d'un acte."""
        rows = await self._rows(
            "SELECT a.code, a.label, t.amount_xof, t.valid_from, t.valid_to, "
            "a.requires_prior_approval FROM tariff_items t JOIN acts a "
            "ON a.organization_id = t.organization_id AND a.id = t.act_id "
            "WHERE t.organization_id = :org "
            "AND (CAST(:act AS uuid) IS NULL OR t.act_id = :act) "
            "AND (CAST(:at AS date) IS NULL OR (t.valid_from <= :at "
            "AND (t.valid_to IS NULL OR :at <= t.valid_to))) "
            "ORDER BY a.code, t.valid_from",
            {"org": org, "act": act_id, "at": at},
        )
        return [
            TariffRecord(row[0], row[1], int(row[2]), Period(row[3], row[4]), row[5])
            for row in rows
        ]

    async def insert_tariff(self, org: UUID, act_id: UUID, amount_xof: int, period: Period) -> None:
        await self._rows(
            "INSERT INTO tariff_items (organization_id, act_id, amount_xof, valid_from, valid_to) "
            "VALUES (:org, :act, :amount, :valid_from, :valid_to)",
            {
                "org": org,
                "act": act_id,
                "amount": amount_xof,
                "valid_from": period.valid_from,
                "valid_to": period.valid_to,
            },
        )

    # --- Règles ----------------------------------------------------------------------------------

    async def rules(
        self, org: UUID, code: str | None = None, *, lock: bool = False
    ) -> list[RuleRecord]:
        rows = await self._rows(
            _RULES_SELECT_LOCK if lock else _RULES_SELECT,
            {"org": org, "code": code},
        )
        return [RuleRecord(*row) for row in rows]

    async def rule_versions(
        self, org: UUID, *, rule_ids: Sequence[UUID] = (), version_id: UUID | None = None
    ) -> list[RuleVersionRecord]:
        rows = await self._rows(
            "SELECT v.id, v.rule_id, r.code, v.version, v.valid_from, v.valid_to, v.state, "
            "v.params FROM rule_versions v JOIN rules r "
            "ON r.organization_id = v.organization_id AND r.id = v.rule_id "
            "WHERE v.organization_id = :org "
            "AND (v.rule_id = ANY(:rules) OR v.id = :version) ORDER BY r.code, v.version",
            {"org": org, "rules": list(rule_ids), "version": version_id},
        )
        return [_rule_version(row) for row in rows]

    async def insert_rule_version(
        self, org: UUID, rule_id: UUID, period: Period, params_json: str
    ) -> UUID:
        """Brouillon numéroté à la suite (la règle doit être verrouillée par l'appelant)."""
        row = await self._first(
            "INSERT INTO rule_versions (organization_id, rule_id, version, valid_from, valid_to, "
            "params) SELECT :org, :rule, coalesce(max(version), 0) + 1, :valid_from, :valid_to, "
            "CAST(:params AS jsonb) FROM rule_versions "
            "WHERE organization_id = :org AND rule_id = :rule RETURNING id",
            {
                "org": org,
                "rule": rule_id,
                "valid_from": period.valid_from,
                "valid_to": period.valid_to,
                "params": params_json,
            },
        )
        version_id: UUID = row[0]
        return version_id
