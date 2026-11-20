"""Dépôt de la mesure produit : seul endroit SQL du module.

Construit pour UNE organisation (celle du jeton). Chaque requête filtre ``organization_id``
elle-même, sur chaque table lue, en plus de la RLS forcée (défense en profondeur, prouvée par
``tests/test_repository.py`` sous une session qui échappe à la RLS). Les agrégats sont calculés
en base ; seuls des effectifs, des sommes et des médianes en sortent, jamais une ligne.

Fenêtre : ``[start, end)`` en UTC, bornes alignées sur des semaines par le service. Rien de
postérieur à ``end`` n'entre dans un agrégat (décision, paiement, fin d'accueil, réception) :
une période terminée ne bouge plus. Les événements expirés (``expires_at <= now``) ne comptent
plus, même avant la purge.

Contre le recoupement (CR-P2-02), chaque lecture rend aussi ``weakest_window`` : l'effectif de
personnes de sa semaine la plus faible, calculé sur les lignes qui DÉTERMINENT la valeur (pas
sur toutes les lignes lues, sinon une semaine gonflée de lignes sans effet passerait le seuil).
Contributeur : la personne (``session_ref`` porte l'empreinte HMAC de l'utilisateur), le
bénéficiaire (dossiers), l'adhérent (liens, cotisations).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Final, NamedTuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class Ratio(NamedTuple):
    numerator: int
    denominator: int
    contributors: int
    weakest_window: int


class Median(NamedTuple):
    value: int | None
    contributors: int
    weakest_window: int


class Total(NamedTuple):
    value: int
    contributors: int


class Outcomes(NamedTuple):
    decided: int
    auto: int
    review: int
    contributors: int
    weakest_window: int


@dataclass(frozen=True, slots=True)
class StoredEvent:
    name: str
    surface: str
    role: str
    session_ref: str
    duration_ms: int | None
    step: int | None
    variant: str | None
    occurred_at: datetime
    expires_at: datetime


def _week(column: str) -> str:
    """Semaine civile locale (lundi) de ``column``, dans le fuseau ``:tz`` de l'organisation."""
    return f"date_trunc('week', {column} AT TIME ZONE :tz)"


# Effectif de personnes de la semaine la plus faible, sur le CTE ``acts(who, w)`` ; 0 si vide.
_WEAKEST: Final = (
    "(SELECT coalesce(min(n), 0) FROM "
    "(SELECT count(DISTINCT who) AS n FROM acts GROUP BY w) AS weeks)"
)

_EVENTS: Final = (
    "FROM product_events WHERE organization_id = :org AND occurred_at >= :start "
    "AND occurred_at < :end AND expires_at > :now "
)


class MetricsRepository:
    def __init__(self, session: AsyncSession, organization_id: UUID) -> None:
        self._session = session
        self.org = organization_id

    async def _row(self, sql: str, **params: Any) -> tuple[Any, ...]:  # noqa: ANN401
        result = await self._session.execute(text(sql), {"org": self.org, **params})
        return tuple(result.one())

    # --- Écriture ------------------------------------------------------------------------------

    async def record(self, event: StoredEvent) -> None:
        await self._session.execute(
            text(
                "INSERT INTO product_events (organization_id, name, surface, role, session_ref, "
                "duration_ms, step, variant, occurred_at, expires_at) VALUES (:org, :name, "
                ":surface, :role, :session_ref, :duration_ms, :step, :variant, :occurred_at, "
                ":expires_at)"
            ),
            {"org": self.org, **asdict(event)},
        )

    async def timezone(self) -> str | None:
        result = await self._session.execute(
            text("SELECT timezone FROM organizations WHERE id = :org"), {"org": self.org}
        )
        value = result.scalar_one_or_none()
        return str(value) if value is not None else None

    # --- Événements d'usage --------------------------------------------------------------------

    async def counter_display(
        self, start: datetime, end: datetime, now: datetime, tz: str
    ) -> Median:
        """Scan → écran de décision au comptoir : médiane PAR PERSONNE, puis médiane des
        personnes (une personne qui envoie cent événements pèse autant qu'une autre)."""
        row = await self._row(
            f"WITH acts AS (SELECT session_ref AS who, duration_ms, {_week('occurred_at')} AS w "  # noqa: S608 — fragments constants
            f"{_EVENTS}AND name = 'counter_decision_shown' AND duration_ms IS NOT NULL), "
            "per_person AS (SELECT percentile_disc(0.5) WITHIN GROUP (ORDER BY duration_ms) "
            "AS value FROM acts GROUP BY who) "
            "SELECT (SELECT percentile_disc(0.5) WITHIN GROUP (ORDER BY value) FROM per_person), "
            f"(SELECT count(*) FROM per_person), {_WEAKEST}",
            start=start,
            end=end,
            now=now,
            tz=tz,
        )
        return Median(None if row[0] is None else int(row[0]), int(row[1]), int(row[2]))

    async def onboarding(self, start: datetime, end: datetime, now: datetime, tz: str) -> Ratio:
        """Personnes qui ont terminé l'accueil parmi celles qui l'ont commencé dans la période.

        Lignes déterminantes : premier début et première fin de chaque personne comptée.
        """
        row = await self._row(
            "WITH firsts AS (SELECT session_ref AS who, "  # noqa: S608 — fragments constants
            "min(occurred_at) FILTER (WHERE name = 'onboarding_started') AS began, "
            "min(occurred_at) FILTER (WHERE name = 'onboarding_completed') AS done "
            f"{_EVENTS}AND name IN ('onboarding_started', 'onboarding_completed') "
            "GROUP BY session_ref), "
            "started AS (SELECT * FROM firsts WHERE began IS NOT NULL), "
            f"acts AS (SELECT who, {_week('began')} AS w FROM started "
            f"UNION ALL SELECT who, {_week('done')} FROM started WHERE done IS NOT NULL) "
            "SELECT count(*) FILTER (WHERE done IS NOT NULL), count(*), count(*), "
            f"{_WEAKEST} FROM started",
            start=start,
            end=end,
            now=now,
            tz=tz,
        )
        return Ratio(int(row[0]), int(row[1]), int(row[2]), int(row[3]))

    async def first_card(self, start: datetime, end: datetime, now: datetime, tz: str) -> Median:
        """Début de l'accueil → première carte présentée, par personne."""
        row = await self._row(
            "WITH firsts AS (SELECT session_ref AS who, "  # noqa: S608 — fragments constants
            "min(occurred_at) FILTER (WHERE name = 'onboarding_started') AS began, "
            "min(occurred_at) FILTER (WHERE name = 'card_presented') AS card "
            f"{_EVENTS}AND name IN ('onboarding_started', 'card_presented') "
            "GROUP BY session_ref), "
            "kept AS (SELECT who, began, card, "
            "CAST(round(extract(epoch FROM card - began) * 1000) AS bigint) AS value "
            "FROM firsts WHERE began IS NOT NULL AND card >= began), "
            f"acts AS (SELECT who, {_week('began')} AS w FROM kept "
            f"UNION ALL SELECT who, {_week('card')} FROM kept) "
            "SELECT percentile_disc(0.5) WITHIN GROUP (ORDER BY value), count(*), "
            f"{_WEAKEST} FROM kept",
            start=start,
            end=end,
            now=now,
            tz=tz,
        )
        return Median(None if row[0] is None else int(row[0]), int(row[1]), int(row[2]))

    # --- Dossiers ------------------------------------------------------------------------------

    async def claim_outcomes(self, start: datetime, end: datetime, tz: str) -> Outcomes:
        """Première décision de chaque dossier (prise avant la fin de la période) : accord
        automatique, revue, ou autre."""
        row = await self._row(
            "WITH scoped AS (SELECT id, beneficiary_person_id AS who, requested_at FROM claims "  # noqa: S608 — fragments constants
            "WHERE organization_id = :org AND requested_at >= :start AND requested_at < :end)"
            ", first_decision AS (SELECT DISTINCT ON (d.claim_id) d.claim_id, d.outcome, "
            "d.decided_at, s.who, s.requested_at "
            "FROM claim_decisions d JOIN scoped s ON s.id = d.claim_id "
            "WHERE d.organization_id = :org AND d.decided_at < :end "
            "ORDER BY d.claim_id, d.sequence), "
            f"acts AS (SELECT who, {_week('requested_at')} AS w FROM first_decision "
            f"UNION ALL SELECT who, {_week('decided_at')} FROM first_decision) "
            "SELECT count(*), count(*) FILTER (WHERE outcome = 'accordee_auto'), "
            "count(*) FILTER (WHERE outcome = 'en_revue'), count(DISTINCT who), "
            f"{_WEAKEST} FROM first_decision",
            start=start,
            end=end,
            tz=tz,
        )
        return Outcomes(int(row[0]), int(row[1]), int(row[2]), int(row[3]), int(row[4]))

    async def decision_delay(self, start: datetime, end: datetime, tz: str) -> Median:
        """Demande → première décision définitive (accord automatique, accord ou refus) prise
        avant la fin de la période."""
        row = await self._row(
            "WITH scoped AS (SELECT id, beneficiary_person_id AS who, requested_at FROM claims "  # noqa: S608 — fragments constants
            "WHERE organization_id = :org AND requested_at >= :start AND requested_at < :end)"
            ", final AS (SELECT s.who, s.requested_at, min(d.decided_at) AS decided_at "
            "FROM claim_decisions d JOIN scoped s ON s.id = d.claim_id "
            "WHERE d.organization_id = :org AND d.decided_at < :end "
            "AND d.outcome IN ('accordee_auto', 'accordee', 'refusee') "
            "GROUP BY d.claim_id, s.who, s.requested_at), "
            f"acts AS (SELECT who, {_week('requested_at')} AS w FROM final "
            f"UNION ALL SELECT who, {_week('decided_at')} FROM final) "
            "SELECT percentile_disc(0.5) WITHIN GROUP (ORDER BY greatest(0, "
            "CAST(round(extract(epoch FROM decided_at - requested_at) * 1000) AS bigint))), "
            f"count(DISTINCT who), {_WEAKEST} FROM final",
            start=start,
            end=end,
            tz=tz,
        )
        return Median(None if row[0] is None else int(row[0]), int(row[1]), int(row[2]))

    # --- Cotisations, grand livre --------------------------------------------------------------

    async def payment_links(self, start: datetime, end: datetime, tz: str) -> Ratio:
        """Cotisations payées (avant la fin de la période) parmi celles qui ont reçu un lien
        dans la période."""
        row = await self._row(
            "WITH per AS (SELECT pl.contribution_id, min(pl.created_at) AS created, "  # noqa: S608 — fragments constants
            "min(pl.used_at) FILTER (WHERE pl.used_at < :end) AS paid FROM payment_links pl "
            "WHERE pl.organization_id = :org AND pl.created_at >= :start "
            "AND pl.created_at < :end GROUP BY pl.contribution_id), "
            "linked AS (SELECT per.created, per.paid, c.member_id AS who FROM per "
            "JOIN contributions c ON c.organization_id = :org AND c.id = per.contribution_id), "
            f"acts AS (SELECT who, {_week('created')} AS w FROM linked "
            f"UNION ALL SELECT who, {_week('paid')} FROM linked WHERE paid IS NOT NULL) "
            "SELECT count(*) FILTER (WHERE paid IS NOT NULL), count(*), count(DISTINCT who), "
            f"{_WEAKEST} FROM linked",
            start=start,
            end=end,
            tz=tz,
        )
        return Ratio(int(row[0]), int(row[1]), int(row[2]), int(row[3]))

    async def ledger_gap(self, until: date) -> Total:
        """Débits moins crédits de toutes les écritures jusqu'à ``until`` inclus (attendu : 0).

        Pas de semaine la plus faible : chaque écriture est équilibrée par contrainte de base
        (``ledger_entries_balanced``), la différence de deux cumuls vaut donc 0 et ne révèle rien
        d'une personne ; l'effectif (écritures) reste au seuil et publié par palier.
        """
        row = await self._row(
            "SELECT coalesce(sum(l.debit_xof), 0) - coalesce(sum(l.credit_xof), 0), "
            "count(DISTINCT e.id) FROM ledger_entries e JOIN ledger_lines l "
            "ON l.organization_id = :org AND l.entry_id = e.id "
            "WHERE e.organization_id = :org AND e.accounting_date <= :until",
            until=until,
        )
        return Total(int(row[0]), int(row[1]))

    async def webhook_duplicates(self, start: datetime, end: datetime, tz: str) -> Ratio:
        """Cotisations reçues plus d'une fois dans la période (double effet d'un webhook) ;
        attendu : 0. Lignes déterminantes : première et deuxième réception."""
        row = await self._row(
            "WITH received AS (SELECT aggregate_id, count(*) AS times, "  # noqa: S608 — fragments constants
            "min(occurred_at) AS first_at, "
            "(array_agg(occurred_at ORDER BY occurred_at))[2] AS second_at "
            "FROM outbox_events WHERE organization_id = :org "
            "AND event_type = 'contribution.received' "
            "AND occurred_at >= :start AND occurred_at < :end GROUP BY aggregate_id), "
            "linked AS (SELECT r.times, r.first_at, r.second_at, c.member_id AS who "
            "FROM received r JOIN contributions c "
            "ON c.organization_id = :org AND c.id = r.aggregate_id), "
            f"acts AS (SELECT who, {_week('first_at')} AS w FROM linked "
            f"UNION ALL SELECT who, {_week('second_at')} FROM linked WHERE second_at IS NOT NULL) "
            "SELECT count(*) FILTER (WHERE times > 1), count(*), count(DISTINCT who), "
            f"{_WEAKEST} FROM linked",
            start=start,
            end=end,
            tz=tz,
        )
        return Ratio(int(row[0]), int(row[1]), int(row[2]), int(row[3]))
