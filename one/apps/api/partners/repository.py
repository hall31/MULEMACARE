"""Dépôt des espaces assureur et employeur et de l'accueil d'organisation : seul endroit SQL.

Construit pour UNE organisation. Chaque requête filtre ``organization_id`` elle-même, sur CHAQUE
table lue, en plus de la RLS forcée (défense en profondeur, prouvée par
``tests/test_organization_filter.py`` sous une session qui échappe à la RLS).

Agrégats : la base renvoie des comptes, des sommes et, pour le k-anonymat, les identifiants
pseudonymes internes des personnes (UUID de ``persons`` ou ``members``) SEMAINE PAR SEMAINE ; ils
ne quittent pas le service (``api.partners.privacy``), aucune donnée de personne n'est lue (ni
nom, ni téléphone).

Une période terminée ne bouge plus (CR-P3-02, même règle que ``api.metrics``) : rien de
postérieur à ``until`` n'entre dans un agrégat.

- Dossiers comptés : demandés dans ``[since, until)`` et dont la DERNIÈRE décision prise avant
  ``until`` est un accord (``accordee_auto``, ``accordee``). Une décision tardive ne réécrit pas
  une semaine déjà publiée. Semaines d'un dossier : celle de la demande ET celle de la décision.
- Cotisations : payées dans ``[since, until)``, semaine du paiement.
- Statuts d'adhérent : instantané à ``until`` (dernier changement de ``member_status_history``
  strictement antérieur), jamais l'état « en direct ».

Gabarit : construit et recopié EN SQL depuis le document jsonb, pour que les paramètres de règle
gardent leur valeur numérique exacte (aucun aller-retour par un flottant Python).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.partners.privacy import Cell, People, Weeks

# Groupe d'employeurs (``:employers``) : NULL = toute l'organisation (espace assureur). La
# condition est écrite en toutes lettres dans chaque requête ; les fragments ci-dessous sont des
# constantes (rien n'est composé à partir d'une entrée).
STATUSES: Final = ("actif", "carence", "suspendu")


def _week(column: str) -> str:
    """Semaine civile locale (lundi) de ``column``, dans le fuseau ``:tz`` de l'organisation."""
    return f"CAST(date_trunc('week', {column} AT TIME ZONE :tz) AS date)"


# Dossiers accordés à la fin de la période (dernière décision antérieure à ``until``).
_GRANTED: Final = (
    "scoped AS (SELECT c.id, c.covered_xof, c.provider_id, c.beneficiary_person_id AS who, "
    "c.requested_at FROM claims c "
    "JOIN members m ON m.organization_id = :org AND m.id = c.member_id "
    "WHERE c.organization_id = :org AND c.requested_at >= :since AND c.requested_at < :until "
    "AND (CAST(:employers AS uuid[]) IS NULL "
    "OR m.employer_id = ANY(CAST(:employers AS uuid[])))), "
    "last_decision AS (SELECT DISTINCT ON (d.claim_id) d.claim_id, d.outcome, d.decided_at "
    "FROM claim_decisions d JOIN scoped s ON s.id = d.claim_id "
    "WHERE d.organization_id = :org AND d.decided_at < :until "
    "ORDER BY d.claim_id, d.sequence DESC), "
    "granted AS (SELECT s.id, s.covered_xof, s.provider_id, s.who, s.requested_at, l.decided_at "
    "FROM scoped s JOIN last_decision l ON l.claim_id = s.id "
    "WHERE l.outcome IN ('accordee_auto', 'accordee'))"
)

# Cellules par semaine à partir de ``keyed(k, amount, who, requested_at, decided_at)`` : la
# demande compte (compte et montant), la décision ne marque que sa semaine.
_CELLS_BY_WEEK: Final = (
    f"marks AS (SELECT k, amount, who, {_week('requested_at')} AS w, 1 AS counted FROM keyed "  # noqa: S608 — fragments constants
    f"UNION ALL SELECT k, 0, who, {_week('decided_at')}, 0 FROM keyed) "
    "SELECT k, w, sum(counted), coalesce(sum(amount), 0), array_agg(DISTINCT who) "
    "FROM marks GROUP BY k, w"
)

# Dossiers de la période, sans filtre de décision (délai et automatisation).
_SCOPED: Final = (
    "scoped AS (SELECT id, beneficiary_person_id AS who, requested_at FROM claims "
    "WHERE organization_id = :org AND requested_at >= :since AND requested_at < :until)"
)

# Personnes par semaine d'un CTE ``marks(who, w)`` ; une ligne par semaine.
_PEOPLE_BY_WEEK: Final = "SELECT w, array_agg(DISTINCT who) AS people FROM marks GROUP BY w"


@dataclass(frozen=True, slots=True)
class Mean:
    value: int | None
    people: People
    weeks: Weeks = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Ratio:
    numerator: int
    denominator: int
    people: People
    weeks: Weeks = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EmployerRow:
    id: UUID
    name: str
    contract_start: date
    contract_end: date | None


@dataclass(frozen=True, slots=True)
class NewTemplate:
    code: str
    version: int
    country_code: str
    label: str
    payload: str
    created_by: UUID


@dataclass(frozen=True, slots=True)
class NewOrganization:
    actor: UUID
    slug: str
    name: str
    country_code: str
    timezone: str
    capabilities: tuple[str, ...]
    regulator: str | None


@dataclass(frozen=True, slots=True)
class TemplateRow:
    id: UUID
    code: str
    version: int
    country_code: str
    label: str
    created_at: datetime
    payload: str


def _people(value: object) -> People:
    if not value:
        return frozenset()
    if not isinstance(value, list | tuple):
        msg = "tableau d'identifiants attendu"
        raise TypeError(msg)
    return frozenset(v if isinstance(v, UUID) else UUID(str(v)) for v in value if v is not None)


def _cells(rows: Sequence[Any]) -> list[Cell]:
    """Lignes ``(clé, semaine, compte, montant, personnes)`` → une cellule par clé."""
    counts: dict[str, int] = {}
    amounts: dict[str, int] = {}
    weeks: dict[str, dict[date, People]] = {}
    for key, week, count, amount, people in rows:
        k = str(key)
        counts[k] = counts.get(k, 0) + int(count)
        amounts[k] = amounts.get(k, 0) + int(amount)
        per_week = weeks.setdefault(k, {})
        per_week[week] = per_week.get(week, frozenset()) | _people(people)
    return [
        Cell(
            key=k,
            count=counts[k],
            amount=amounts[k],
            people=frozenset().union(*weeks[k].values()),
            weeks=weeks[k],
        )
        for k in sorted(counts)
    ]


def _single(cells: list[Cell], key: str) -> Cell:
    return cells[0] if cells else Cell(key, 0, 0, frozenset())


def _weeks(rows: Sequence[Any], week_at: int, people_at: int) -> tuple[People, Weeks]:
    weeks = {row[week_at]: _people(row[people_at]) for row in rows}
    return frozenset().union(*weeks.values()), weeks


class AggregateRepository:
    """Agrégats d'une organisation, éventuellement restreints à des groupes d'employeurs."""

    def __init__(self, session: AsyncSession, organization_id: UUID) -> None:
        self._session = session
        self.org = organization_id

    async def _rows(self, sql: str, **params: Any) -> Sequence[Any]:  # noqa: ANN401
        result = await self._session.execute(text(sql), {"org": self.org, **params})
        return result.all()

    async def timezone(self) -> str | None:
        rows = await self._rows("SELECT timezone FROM organizations WHERE id = :org")
        return str(rows[0][0]) if rows else None

    async def members_by_status(self, until: datetime, employer: UUID | None = None) -> list[Cell]:
        """Statuts à ``until`` : dernier changement strictement antérieur, par adhérent."""
        employers = None if employer is None else [employer]
        rows = await self._rows(
            "WITH at_end AS (SELECT DISTINCT ON (h.member_id) h.member_id, h.to_status "
            "FROM member_status_history h WHERE h.organization_id = :org "
            "AND h.occurred_at < :until ORDER BY h.member_id, h.occurred_at DESC, h.id DESC) "
            "SELECT a.to_status, count(*), array_agg(m.id) FROM at_end a "
            "JOIN members m ON m.organization_id = :org AND m.id = a.member_id "
            "WHERE m.organization_id = :org "
            "AND (CAST(:employers AS uuid[]) IS NULL "
            "OR m.employer_id = ANY(CAST(:employers AS uuid[]))) GROUP BY a.to_status",
            until=until,
            employers=employers,
        )
        found = {str(r[0]): Cell(str(r[0]), int(r[1]), 0, _people(r[2])) for r in rows}
        return [found.get(status, Cell(status, 0, 0, frozenset())) for status in STATUSES]

    async def premiums(self, since: datetime, until: datetime, tz: str) -> Cell:
        rows = await self._rows(
            f"SELECT 'total', {_week('c.paid_at')}, count(*), coalesce(sum(c.amount_xof), 0), "  # noqa: S608 — fragment constant
            "array_agg(DISTINCT c.member_id) FROM contributions c "
            "WHERE c.organization_id = :org AND c.status = 'payee' "
            "AND c.paid_at >= :since AND c.paid_at < :until GROUP BY 2",
            since=since,
            until=until,
            tz=tz,
        )
        return _single(_cells(rows), "total")

    async def claims_cost(
        self, since: datetime, until: datetime, tz: str, employer: UUID | None = None
    ) -> Cell:
        rows = await self._rows(
            f"WITH {_GRANTED}, keyed AS (SELECT 'total' AS k, covered_xof AS amount, who, "  # noqa: S608 — fragments constants
            f"requested_at, decided_at FROM granted), {_CELLS_BY_WEEK}",
            since=since,
            until=until,
            tz=tz,
            employers=None if employer is None else [employer],
        )
        return _single(_cells(rows), "total")

    async def benefits_by_category(
        self, since: datetime, until: datetime, tz: str, employer: UUID | None = None
    ) -> list[Cell]:
        """Part mutuelle par catégorie de garantie (acte → catégorie) ; jamais l'acte lui-même."""
        rows = await self._rows(
            f"WITH {_GRANTED}, keyed AS (SELECT a.coverage_category AS k, "  # noqa: S608 — fragments constants
            "sum(i.covered_xof) AS amount, g.who, g.requested_at, g.decided_at FROM granted g "
            "JOIN claim_items i ON i.organization_id = :org AND i.claim_id = g.id "
            "JOIN acts a ON a.organization_id = :org AND a.id = i.act_id "
            "GROUP BY a.coverage_category, g.id, g.who, g.requested_at, g.decided_at), "
            f"{_CELLS_BY_WEEK}",
            since=since,
            until=until,
            tz=tz,
            employers=None if employer is None else [employer],
        )
        return _cells(rows)

    async def providers(
        self, since: datetime, until: datetime, tz: str
    ) -> list[tuple[UUID, str, Cell]]:
        rows = await self._rows(
            f"WITH {_GRANTED}, keyed AS (SELECT CAST(p.id AS text) AS k, "  # noqa: S608 — fragments constants
            "g.covered_xof AS amount, g.who, g.requested_at, g.decided_at FROM granted g "
            "JOIN providers p ON p.organization_id = :org AND p.id = g.provider_id), "
            f"{_CELLS_BY_WEEK}",
            since=since,
            until=until,
            tz=tz,
            employers=None,
        )
        cells = _cells(rows)
        if not cells:
            return []
        names = await self._rows(
            "SELECT p.id, p.name FROM providers p WHERE p.organization_id = :org "
            "AND p.id = ANY(CAST(:ids AS uuid[]))",
            ids=[UUID(c.key) for c in cells],
        )
        by_id = {str(r[0]): (r[0], str(r[1])) for r in names}
        return [(*by_id[c.key], c) for c in cells if c.key in by_id]

    async def decision_delay(self, since: datetime, until: datetime, tz: str) -> Mean:
        """Délai moyen demande → première décision définitive (accord ou refus) prise avant
        ``until``, en ms. Semaines : demande et décision."""
        rows = await self._rows(
            f"WITH {_SCOPED}, final AS (SELECT s.id, s.who, s.requested_at, "  # noqa: S608 — fragments constants
            "min(d.decided_at) AS decided_at FROM claim_decisions d "
            "JOIN scoped s ON s.id = d.claim_id WHERE d.organization_id = :org "
            "AND d.decided_at < :until AND d.outcome IN ('accordee_auto', 'accordee', 'refusee') "
            "GROUP BY s.id, s.who, s.requested_at), "
            f"marks AS (SELECT who, {_week('requested_at')} AS w FROM final "
            f"UNION ALL SELECT who, {_week('decided_at')} FROM final) "
            "SELECT (SELECT CAST(round(avg(greatest(0, extract(epoch FROM decided_at - "
            "requested_at) * 1000))) AS bigint) FROM final), weeks.w, weeks.people "
            f"FROM ({_PEOPLE_BY_WEEK}) AS weeks",
            since=since,
            until=until,
            tz=tz,
        )
        if not rows:
            return Mean(None, frozenset())
        people, weeks = _weeks(rows, 1, 2)
        value = rows[0][0]
        return Mean(None if value is None else int(value), people, weeks)

    async def automation(self, since: datetime, until: datetime, tz: str) -> Ratio:
        """Dossiers dont la PREMIÈRE décision (prise avant ``until``) est un accord automatique
        (moteur de règles). Semaines : demande et première décision."""
        rows = await self._rows(
            f"WITH {_SCOPED}, first AS (SELECT DISTINCT ON (d.claim_id) d.claim_id, d.outcome, "  # noqa: S608 — fragments constants
            "d.decided_at FROM claim_decisions d JOIN scoped s ON s.id = d.claim_id "
            "WHERE d.organization_id = :org AND d.decided_at < :until "
            "ORDER BY d.claim_id, d.sequence), "
            "decided AS (SELECT s.who, s.requested_at, f.outcome, f.decided_at FROM first f "
            "JOIN scoped s ON s.id = f.claim_id), "
            f"marks AS (SELECT who, {_week('requested_at')} AS w FROM decided "
            f"UNION ALL SELECT who, {_week('decided_at')} FROM decided) "
            "SELECT (SELECT count(*) FILTER (WHERE outcome = 'accordee_auto') FROM decided), "
            "(SELECT count(*) FROM decided), weeks.w, weeks.people "
            f"FROM ({_PEOPLE_BY_WEEK}) AS weeks",
            since=since,
            until=until,
            tz=tz,
        )
        if not rows:
            return Ratio(0, 0, frozenset())
        people, weeks = _weeks(rows, 2, 3)
        return Ratio(int(rows[0][0]), int(rows[0][1]), people, weeks)

    async def employers(self, ids: Sequence[UUID]) -> list[EmployerRow]:
        rows = await self._rows(
            "SELECT e.id, e.name, e.contract_start, e.contract_end FROM employers e "
            "WHERE e.organization_id = :org AND e.id = ANY(CAST(:ids AS uuid[])) ORDER BY e.name",
            ids=list(ids),
        )
        return [EmployerRow(r[0], str(r[1]), r[2], r[3]) for r in rows]


# --- Gabarits et accueil d'organisation --------------------------------------------------------

_SNAPSHOT: Final = """
SELECT jsonb_build_object(
  'format_version', 1,
  'ledger_accounts', coalesce((
    SELECT jsonb_agg(jsonb_build_object('code', a.code, 'label', a.label,
                                        'account_class', a.account_class) ORDER BY a.code)
    FROM ledger_accounts a WHERE a.organization_id = :org), '[]'::jsonb),
  'rules', coalesce((
    SELECT jsonb_agg(jsonb_build_object('code', r.code, 'label', r.label, 'kind', r.kind,
                                        'params', v.params) ORDER BY r.code)
    FROM rules r JOIN rule_versions v ON v.organization_id = :org AND v.rule_id = r.id
    WHERE r.organization_id = :org AND v.state = 'en_vigueur' AND v.valid_from <= :day
      AND (v.valid_to IS NULL OR v.valid_to >= :day)), '[]'::jsonb),
  'plans', coalesce((
    SELECT jsonb_agg(jsonb_build_object(
      'code', p.code, 'name', p.name, 'coverage_rate_bp', v.coverage_rate_bp,
      'family_annual_ceiling_xof', v.family_annual_ceiling_xof,
      'waiting_period_days', v.waiting_period_days,
      'monthly_contribution_xof', v.monthly_contribution_xof,
      'coverages', coalesce((
        SELECT jsonb_agg(jsonb_build_object(
          'category', g.category, 'label', g.label, 'coverage_rate_bp', g.coverage_rate_bp,
          'annual_limit_xof', g.annual_limit_xof, 'limit_scope', g.limit_scope)
          ORDER BY g.category)
        FROM coverages g WHERE g.organization_id = :org AND g.plan_version_id = v.id),
        '[]'::jsonb)) ORDER BY p.code)
    FROM plans p JOIN plan_versions v ON v.organization_id = :org AND v.plan_id = p.id
    WHERE p.organization_id = :org AND p.status = 'active' AND v.state = 'en_vigueur'
      AND v.valid_from <= :day AND (v.valid_to IS NULL OR v.valid_to >= :day)), '[]'::jsonb),
  'acts', coalesce((
    SELECT jsonb_agg(jsonb_build_object(
      'code', a.code, 'label', a.label, 'coverage_category', a.coverage_category,
      'requires_prior_approval', a.requires_prior_approval,
      'tariff_xof', (SELECT t.amount_xof FROM tariff_items t
                     WHERE t.organization_id = :org AND t.act_id = a.id
                       AND t.valid_from <= :day AND (t.valid_to IS NULL OR t.valid_to >= :day)
                     ORDER BY t.valid_from DESC LIMIT 1)) ORDER BY a.code)
    FROM acts a WHERE a.organization_id = :org), '[]'::jsonb)
)::text
"""

# Copie dans l'organisation ACCUEILLIE (:org) depuis le document (:doc) : nouvelles lignes,
# version 1 en brouillon pour les règles et les produits, barème daté du jour (:day).
_COPY: Final = (
    (
        "ledger_accounts",
        "INSERT INTO ledger_accounts (organization_id, code, label, account_class) "
        "SELECT :org, x.code, x.label, x.account_class FROM jsonb_to_recordset("
        "CAST(:doc AS jsonb) -> 'ledger_accounts') AS x(code text, label text, "
        "account_class text)",
    ),
    (
        "rules",
        "INSERT INTO rules (organization_id, code, label, kind) "
        "SELECT :org, x.code, x.label, x.kind FROM jsonb_to_recordset("
        "CAST(:doc AS jsonb) -> 'rules') AS x(code text, label text, kind text)",
    ),
    (
        "rule_versions",
        "INSERT INTO rule_versions (organization_id, rule_id, version, valid_from, params, state) "
        "SELECT :org, r.id, 1, :day, x.params, 'brouillon' FROM jsonb_to_recordset("
        "CAST(:doc AS jsonb) -> 'rules') AS x(code text, params jsonb) "
        "JOIN rules r ON r.organization_id = :org AND r.code = x.code",
    ),
    (
        "plans",
        "INSERT INTO plans (organization_id, code, name) "
        "SELECT :org, x.code, x.name FROM jsonb_to_recordset("
        "CAST(:doc AS jsonb) -> 'plans') AS x(code text, name text)",
    ),
    (
        "plan_versions",
        "INSERT INTO plan_versions (organization_id, plan_id, version, valid_from, state, "
        "coverage_rate_bp, family_annual_ceiling_xof, waiting_period_days, "
        "monthly_contribution_xof) SELECT :org, p.id, 1, :day, 'brouillon', "
        "x.coverage_rate_bp, x.family_annual_ceiling_xof, x.waiting_period_days, "
        "x.monthly_contribution_xof FROM jsonb_to_recordset(CAST(:doc AS jsonb) -> 'plans') "
        "AS x(code text, coverage_rate_bp integer, family_annual_ceiling_xof bigint, "
        "waiting_period_days integer, monthly_contribution_xof bigint) "
        "JOIN plans p ON p.organization_id = :org AND p.code = x.code",
    ),
    (
        "coverages",
        "INSERT INTO coverages (organization_id, plan_version_id, category, label, "
        "coverage_rate_bp, annual_limit_xof, limit_scope) "
        "SELECT :org, v.id, g.category, g.label, g.coverage_rate_bp, g.annual_limit_xof, "
        "g.limit_scope FROM jsonb_to_recordset(CAST(:doc AS jsonb) -> 'plans') "
        "AS x(code text, coverages jsonb) "
        "CROSS JOIN LATERAL jsonb_to_recordset(x.coverages) AS g(category text, label text, "
        "coverage_rate_bp integer, annual_limit_xof bigint, limit_scope text) "
        "JOIN plans p ON p.organization_id = :org AND p.code = x.code "
        "JOIN plan_versions v ON v.organization_id = :org AND v.plan_id = p.id "
        "AND v.version = 1",
    ),
    (
        "acts",
        "INSERT INTO acts (organization_id, code, label, coverage_category, "
        "requires_prior_approval) SELECT :org, x.code, x.label, x.coverage_category, "
        "x.requires_prior_approval FROM jsonb_to_recordset(CAST(:doc AS jsonb) -> 'acts') "
        "AS x(code text, label text, coverage_category text, requires_prior_approval boolean)",
    ),
    (
        "tariff_items",
        "INSERT INTO tariff_items (organization_id, act_id, amount_xof, valid_from) "
        "SELECT :org, a.id, x.tariff_xof, :day FROM jsonb_to_recordset("
        "CAST(:doc AS jsonb) -> 'acts') AS x(code text, tariff_xof bigint) "
        "JOIN acts a ON a.organization_id = :org AND a.code = x.code "
        "WHERE x.tariff_xof IS NOT NULL",
    ),
)


class PlatformRepository:
    """Gabarits (organisation « plateforme ») et écriture dans l'organisation accueillie."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enter_organization(self, organization_id: UUID) -> None:
        """Positionne l'organisation de la suite de la transaction (RLS)."""
        await self._session.execute(
            select(func.set_config("app.organization_id", str(organization_id), True))
        )

    async def snapshot(self, org: UUID, day: date) -> str:
        result = await self._session.execute(text(_SNAPSHOT), {"org": org, "day": day})
        return str(result.scalar_one())

    async def lock_template_code(self, org: UUID, code: str) -> None:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"configuration_templates:{org}:{code}"},
        )

    async def next_template_version(self, org: UUID, code: str) -> int:
        result = await self._session.execute(
            text(
                "SELECT coalesce(max(version), 0) + 1 FROM configuration_templates "
                "WHERE organization_id = :org AND code = :code"
            ),
            {"org": org, "code": code},
        )
        return int(result.scalar_one())

    async def insert_template(self, org: UUID, new: NewTemplate) -> TemplateRow:
        result = await self._session.execute(
            text(
                "INSERT INTO configuration_templates (organization_id, code, version, "
                "country_code, label, payload, created_by) VALUES (:org, :code, :version, "
                ":country, :label, CAST(:payload AS jsonb), :created_by) "
                "RETURNING id, code, version, country_code, label, created_at, payload::text"
            ),
            {
                "org": org,
                "code": new.code,
                "version": new.version,
                "country": new.country_code,
                "label": new.label,
                "payload": new.payload,
                "created_by": new.created_by,
            },
        )
        return _template(result.one())

    async def templates(self, org: UUID) -> list[TemplateRow]:
        result = await self._session.execute(
            text(
                "SELECT id, code, version, country_code, label, created_at, payload::text "
                "FROM configuration_templates WHERE organization_id = :org "
                "ORDER BY code, version DESC"
            ),
            {"org": org},
        )
        return [_template(r) for r in result.all()]

    async def template(self, org: UUID, code: str, version: int | None) -> TemplateRow | None:
        result = await self._session.execute(
            text(
                "SELECT id, code, version, country_code, label, created_at, payload::text "
                "FROM configuration_templates WHERE organization_id = :org AND code = :code "
                "AND (CAST(:version AS integer) IS NULL OR version = :version) "
                "ORDER BY version DESC LIMIT 1"
            ),
            {"org": org, "code": code, "version": version},
        )
        row = result.first()
        return None if row is None else _template(row)

    async def create_organization(self, new: NewOrganization) -> UUID:
        """Fonction SECURITY DEFINER du contrat : vérifie l'administrateur de plateforme."""
        result = await self._session.execute(
            text(
                "SELECT platform_create_organization(:actor, :slug, :name, :country, :tz, "
                "CAST(:caps AS text[]), :regulator)"
            ),
            {
                "actor": new.actor,
                "slug": new.slug,
                "name": new.name,
                "country": new.country_code,
                "tz": new.timezone,
                "caps": list(new.capabilities),
                "regulator": new.regulator,
            },
        )
        created: object = result.scalar_one()
        return created if isinstance(created, UUID) else UUID(str(created))

    async def insert_first_manager(
        self,
        org: UUID,
        *,
        subject: str,
        display_name: str,
        email: str | None,
        roles: Sequence[str],
    ) -> UUID:
        """Utilisateur de l'organisation accueillie ; ``granted_by`` nul (attribué par la
        plateforme, dont l'administrateur n'appartient pas à cette organisation)."""
        result = await self._session.execute(
            text(
                "INSERT INTO users (organization_id, idp_subject, display_name, email) "
                "VALUES (:org, :subject, :display_name, :email) RETURNING id"
            ),
            {"org": org, "subject": subject, "display_name": display_name, "email": email},
        )
        user_id: object = result.scalar_one()
        for role in roles:
            await self._session.execute(
                text(
                    "INSERT INTO user_roles (organization_id, user_id, role) "
                    "VALUES (:org, :user, :role)"
                ),
                {"org": org, "user": user_id, "role": role},
            )
        return user_id if isinstance(user_id, UUID) else UUID(str(user_id))

    async def copy_template(self, org: UUID, payload: str, day: date) -> dict[str, int]:
        copied: dict[str, int] = {}
        for table, statement in _COPY:
            result = await self._session.execute(
                text(statement), {"org": org, "doc": payload, "day": day}
            )
            copied[table] = int(getattr(result, "rowcount", 0) or 0)
        return copied


def _template(row: Any) -> TemplateRow:  # noqa: ANN401
    return TemplateRow(
        id=row[0],
        code=str(row[1]),
        version=int(row[2]),
        country_code=str(row[3]),
        label=str(row[4]),
        created_at=row[5],
        payload=str(row[6]),
    )
