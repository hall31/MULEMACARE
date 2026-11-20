"""Statuts d'adhérent (actif, carence, suspendu) : règle R-01 en données, transitions, événement.

Le seuil de suspension et les statuts ouvrant droit viennent de la version de R-01 en vigueur à
la date considérée (``rule_versions.params``, lus par ``api.rules.params.rights`` de L2) : rien
n'est codé en dur. Les mêmes définitions servent au traitement quotidien (J+45), à la
réouverture après paiement et à ``getMemberEntitlements``, pour que les trois concordent avec
le moteur de règles (``unpaid_days >= seuil`` ferme les droits, Q-L2-01).

Toute transition écrit, dans la transaction de l'appelant : ``members.status``,
``member_status_history`` (ajout seul) et l'événement ``member.status_changed`` (outbox).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Final, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import status

from api.members import outbox
from api.members.errors import MembershipError, invalid, status_change_refused
from api.members.repository import HistoryEntry, MemberRecord, MemberRepository
from api.rules import params
from api.rules.errors import RulesError
from api.rules.versions import select_in_force

type MemberStatus = Literal["actif", "carence", "suspendu"]
type StatusReason = Literal[
    "adhesion", "fin_de_carence", "paiement_confirme", "impaye", "decision_gestionnaire"
]

RIGHTS_RULE: Final = "R-01"


@dataclass(frozen=True, slots=True)
class RightsPolicy:
    """R-01 en vigueur à une date : statuts ouvrant droit et seuil d'impayé (jours)."""

    code: str
    version: int
    open_statuses: frozenset[str]
    suspension_after_unpaid_days: int

    def rule_ref(self) -> dict[str, object]:
        return {"code": self.code, "version": self.version}


def local_today(moment: datetime, timezone: str) -> date:
    return moment.astimezone(ZoneInfo(timezone)).date()


def end_of_day(day: date, timezone: str) -> datetime:
    """Premier instant du lendemain (fuseau de l'organisation) : borne exclue d'une journée."""
    return datetime.combine(day + timedelta(days=1), time.min, ZoneInfo(timezone))


def configuration_error(exc: RulesError) -> MembershipError:
    return MembershipError("VAL-01", status.HTTP_422_UNPROCESSABLE_CONTENT, exc.message, exc.action)


async def rights_policy(repo: MemberRepository, org: UUID, day: date) -> RightsPolicy:
    try:
        rule = select_in_force(
            await repo.rule_versions(org, RIGHTS_RULE), day, what="la règle R-01"
        )
        parsed = params.rights(rule)
    except RulesError as exc:
        raise configuration_error(exc) from exc
    return RightsPolicy(
        code=rule.code,
        version=rule.version,
        open_statuses=parsed.open_statuses,
        suspension_after_unpaid_days=parsed.suspension_after_unpaid_days,
    )


async def organization_timezone(repo: MemberRepository, org: UUID) -> str:
    timezone = await repo.organization_timezone(org)
    if timezone is None:  # organisation invisible : RLS ou jeton incohérent
        raise invalid("organization", "Organisation inconnue.")
    return timezone


async def unpaid_days(
    repo: MemberRepository, org: UUID, member_id: UUID, day: date, timezone: str
) -> int:
    """Jours écoulés depuis la plus ancienne échéance non réglée à la fin de ``day``."""
    oldest = await repo.oldest_unpaid_due_on(org, member_id, end_of_day(day, timezone))
    return 0 if oldest is None else max((day - oldest).days, 0)


def status_after_regularisation(member: MemberRecord, day: date) -> MemberStatus:
    """Statut d'un adhérent dont l'impayé repasse sous le seuil : carence si non écoulée."""
    return "actif" if member.waiting_period_ends_on <= day else "carence"


@dataclass(frozen=True, slots=True)
class Change:
    """Changement de statut demandé (motif du contrat, auteur éventuel, règle citée)."""

    to_status: MemberStatus
    reason: StatusReason
    at: datetime
    actor_user_id: UUID | None = None
    rule: RightsPolicy | None = None


async def transition(
    repo: MemberRepository, org: UUID, member: MemberRecord, change: Change
) -> None:
    """Change le statut, ajoute l'historique et l'événement, dans la transaction courante."""
    effective_at = await record_status(repo, org, member.id, member.status, change)
    await repo.set_status(org, member.id, change.to_status, effective_at)


async def record_status(
    repo: MemberRepository,
    org: UUID,
    member_id: UUID,
    from_status: str | None,
    change: Change,
) -> datetime:
    """Historique (ajout seul) + événement ; renvoie l'horodatage effectif du changement."""
    effective_at = await repo.append_history(
        org,
        HistoryEntry(
            member_id=member_id,
            from_status=from_status,
            to_status=change.to_status,
            reason_code=change.reason,
            actor_user_id=change.actor_user_id,
            at=change.at,
        ),
    )
    actor = change.actor_user_id
    await outbox.emit(
        repo.session,
        outbox.NewEvent(
            organization_id=org,
            event_type="member.status_changed",
            aggregate_id=member_id,
            occurred_at=effective_at,
            payload={
                "member_id": str(member_id),
                "from_status": from_status,
                "to_status": change.to_status,
                "reason_code": change.reason,
                "rule": None if change.rule is None else change.rule.rule_ref(),
                "actor_user_id": None if actor is None else str(actor),
                "effective_at": outbox.rfc3339(effective_at),
            },
        ),
    )
    return effective_at


async def reopen_after_payment(
    repo: MemberRepository, *, org: UUID, member_id: UUID, now: datetime
) -> bool:
    """Après un paiement confirmé : un adhérent suspendu repasse en droits si l'impayé le permet.

    Appelé dans la transaction du webhook : les droits sont ouverts au COMMIT de la
    notification (R2, bien en deçà de 60 s). Renvoie vrai si le statut a changé.
    """
    member = await repo.get(org, member_id, lock=True)
    if member is None or member.status != "suspendu":
        return False
    timezone = await organization_timezone(repo, org)
    day = local_today(now, timezone)
    policy = await rights_policy(repo, org, day)
    if (
        await unpaid_days(repo, org, member.id, day, timezone)
        >= policy.suspension_after_unpaid_days
    ):
        return False
    change = Change(status_after_regularisation(member, day), "paiement_confirme", now, rule=policy)
    await transition(repo, org, member, change)
    return True


async def check_manual_change(
    repo: MemberRepository, *, org: UUID, member: MemberRecord, to_status: str, now: datetime
) -> None:
    """Transitions permises au gestionnaire ; sinon MBR-01 (contrat ``changeMemberStatus``).

    - vers « suspendu » : depuis actif ou carence ;
    - vers « actif » : seulement si la carence est écoulée ET l'impayé sous le seuil R-01
      (sinon le traitement quotidien le resuspendrait, et R-01 refuserait les soins) ;
    - vers « carence » : seulement depuis « suspendu », si la carence n'est pas écoulée.
    """
    if to_status == member.status:
        raise status_change_refused(
            f"L'adhérent est déjà au statut « {to_status} ».",
            "Rechargez la fiche : aucun changement n'est nécessaire.",
        )
    timezone = await organization_timezone(repo, org)
    day = local_today(now, timezone)
    if to_status == "suspendu":
        return
    waiting_over = member.waiting_period_ends_on <= day
    if to_status == "carence":
        if member.status != "suspendu" or waiting_over:
            raise status_change_refused(
                "Le statut « carence » ne s'applique que pendant le délai de carence.",
                "Choisissez « actif » ou « suspendu ».",
            )
        return
    if not waiting_over:
        raise status_change_refused(
            "Le délai de carence n'est pas écoulé : l'adhérent ne peut pas être activé.",
            f"Attendez le {member.waiting_period_ends_on:%d/%m/%Y}.",
        )
    policy = await rights_policy(repo, org, day)
    if (
        await unpaid_days(repo, org, member.id, day, timezone)
        >= policy.suspension_after_unpaid_days
    ):
        raise status_change_refused(
            "Une cotisation reste impayée au-delà du délai de la règle R-01.",
            "Faites régulariser la cotisation : les droits s'ouvriront au paiement.",
        )
