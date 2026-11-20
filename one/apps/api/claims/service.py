"""Prises en charge (R1, R4, R5, R6) : la décision vient du moteur L2 ou d'un humain habilité.

- ``create`` : identification vérifiée (trois facteurs) → faits → ``engine.evaluate`` (L2) →
  décision écrite avec ``rule_id``/``rule_version`` → ``claim.requested`` puis
  ``claim.decided`` dans la boîte d'envoi. Un accord en ligne n'est émis que pour
  ``accordee_auto`` ; une revue ne crée NI accord NI écriture (le grand livre ne passe
  d'écriture que pour ``accordee_auto`` et ``accordee``).
- ``decide`` : médecin-conseil seulement (la route l'impose), dossier ``en_revue`` seulement.
- ``submit_documents`` : la clinique remet en revue un dossier ``pieces_demandees`` (Q-L0-20).
- ``read_medical_reason`` : permission SEC-01 et audit par ``MedicalReasonAccess`` (L1), lecture
  chez HealthOS par le client L9 dont le hook exige l'audit déjà écrit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from sqlalchemy.engine import RowMapping

from api.claims import rulebook, views
from api.claims.common import (
    access,
    clinic_provider,
    ensure_in_scope,
    idempotency_conflict,
    idempotency_in_progress,
    local_date,
    request_hash,
)
from api.claims.errors import (
    act_off_tariff,
    identification_incomplete,
    invalid,
    not_found,
    transition_forbidden,
)
from api.claims.ports import ClaimsRuntime
from api.claims.repository import ClaimsRepository
from api.claims.schemas import (
    ClaimCreated,
    ClaimDetail,
    ClaimList,
    CreateClaimRequest,
    DecideClaimRequest,
    MedicalReason,
    PageInfo,
    SubmitClaimDocumentsRequest,
    WorkQueue,
)
from api.core.context import RequestContext
from api.core.errors import InternalError, NotFoundError, UpstreamUnavailableError
from api.core.medical import MedicalReasonAccess
from api.core.pagination import decode_cursor, encode_cursor
from api.core.repositories import AuditRecord, AuditRepository, Keyset
from api.core.services import AuditIntent, AuditService
from api.integrations.egress import EgressDeniedError
from api.integrations.healthos import (
    HealthOSNotFoundError,
    HealthOSUnavailableError,
    ReasonReadAuditEvent,
    ReasonReadContext,
)
from api.rules.model import Outcome
from api.rules.model import RuleRef as EngineRuleRef

logger = logging.getLogger(__name__)

KEY_TTL: Final = timedelta(hours=24)  # comme L3 ; défaut technique non fixé par le contrat
HUMAN_OUTCOMES: Final = {
    "accorder": "accordee",
    "refuser": "refusee",
    "demander_pieces": "pieces_demandees",
}
BACK_TO_REVIEW_REASON: Final = "R-20"
_SCORE_STEP: Final = Decimal("0.001")


@dataclass(frozen=True, slots=True)
class Stored:
    """Réponse déjà produite par une clé d'idempotence."""

    status: int
    body: Any


class Idempotency:
    def __init__(self, repo: ClaimsRepository, runtime: ClaimsRuntime) -> None:
        self._repo = repo
        self._rt = runtime

    async def begin(self, scope: str, key: str, payload: object) -> Stored | None:
        now = self._rt.clock.now()
        row = await self._repo.reserve_key(scope, key, request_hash(payload), now, now + KEY_TTL)
        if row is None:
            return None
        if row["request_hash"] != request_hash(payload):
            raise idempotency_conflict()
        if row["status"] != "terminee" or row["response_status"] is None:
            raise idempotency_in_progress()
        return Stored(int(row["response_status"]), row["response_body"])

    async def complete(self, scope: str, key: str, status: int, body: Any) -> None:  # noqa: ANN401
        await self._repo.complete_key(scope, key, status, body)


async def apply_decision(  # noqa: PLR0913 — une décision du journal et ses effets
    repo: ClaimsRepository,
    claim_id: UUID,
    *,
    outcome: str,
    rule: EngineRuleRef | None,
    reason_code: str,
    decided_by: UUID | None,
    trace: list[dict[str, object]],
    now: datetime,
    review_due_at: datetime | None,
    refuse_amounts: bool = False,
) -> None:
    """Ajoute la décision (ajout seul), recopie l'état sur le dossier, émet ``claim.decided``."""
    sequence = await repo.insert_decision(
        claim_id,
        outcome=outcome,
        source="regle" if rule is not None else "humain",
        rule_id=rule.rule_id if rule else None,
        rule_version=rule.version if rule else None,
        reason_code=reason_code,
        decided_by=decided_by,
        trace=trace,
        decided_at=now,
    )
    claim = await repo.claim(claim_id)
    if claim is None:
        raise not_found()
    await repo.set_claim_state(
        claim_id,
        status=outcome,
        rule_id=rule.rule_id if rule else None,
        rule_version=rule.version if rule else None,
        decided_at=None if outcome == "en_revue" else now,
        review_due_at=review_due_at,
        covered_xof=0 if refuse_amounts else None,
        patient_share_xof=int(claim["total_xof"]) if refuse_amounts else None,
    )
    claim = await repo.claim(claim_id)
    assert claim is not None  # noqa: S101 — relu dans la même transaction
    await repo.insert_event(
        "claim.decided",
        claim_id,
        views.claim_decided(
            claim,
            sequence=sequence,
            outcome=outcome,
            rule=rule,
            reason_code=reason_code,
            decided_by=decided_by,
        ),
        now,
    )


class CapturingAuditService(AuditService):
    """Audit du noyau qui retient la dernière entrée écrite (identifiant renvoyé à L9)."""

    last: AuditRecord | None = None

    async def record(self, ctx: RequestContext, intent: AuditIntent) -> AuditRecord:
        self.last = await super().record(ctx, intent)
        return self.last


def checked_fraud_score(value: Decimal | None) -> Decimal | None:
    """Score du port de fraude borné à [0, 1] et arrondi au millième (``claims.fraud_score``)."""
    if value is None:
        return None
    if not Decimal(0) <= value <= Decimal(1):
        msg = "score de fraude hors de [0, 1]"
        raise ValueError(msg)
    return value.quantize(_SCORE_STEP)


class ClaimsService:
    def __init__(self, ctx: RequestContext, runtime: ClaimsRuntime) -> None:
        self._ctx = ctx
        self._rt = runtime
        self._repo = ClaimsRepository(ctx.session, ctx.principal.organization_id)
        self._idem = Idempotency(self._repo, runtime)

    async def _today(self) -> tuple[datetime, str, date]:
        now = self._rt.clock.now()
        timezone = await self._repo.timezone()
        return now, timezone, local_date(now, timezone)

    async def _visible_claim(self, claim_id: UUID, *, for_update: bool = False) -> RowMapping:
        claim = await self._repo.claim(claim_id, for_update=for_update)
        if claim is None:
            raise not_found("Dossier introuvable.")
        ensure_in_scope(self._ctx, claim["provider_id"])
        return claim

    # --- demande ----------------------------------------------------------------------------

    async def create(self, body: CreateClaimRequest, key: str) -> tuple[int, Any]:
        provider = clinic_provider(self._ctx)
        scope = "command:claim.create"
        payload = body.model_dump(mode="json")
        stored = await self._idem.begin(scope, key, payload)
        if stored is not None:
            return stored.status, stored.body

        identification = await self._repo.identification(body.identification_id, for_update=True)
        if identification is None:
            raise not_found("Identification introuvable.")
        ensure_in_scope(self._ctx, identification["provider_id"])
        if identification["status"] != "verifiee":
            raise identification_incomplete(
                "L'identité n'a pas été vérifiée par les trois facteurs (carte, photo, code).",
                status_code=422,
            )
        if await self._repo.identification_used(identification["id"]):
            raise transition_forbidden("Cette identification a déjà servi pour un dossier.")
        now, timezone, today = await self._today()
        if body.service_date > today:
            raise invalid("La date du soin ne peut pas être dans le futur.")

        codes = [item.act_code for item in body.items]
        acts = await self._repo.acts(codes, body.service_date)
        unknown = sorted({c for c in codes if c not in acts})
        if unknown:
            raise act_off_tariff(unknown)
        member = await self._repo.member(identification["member_id"])
        if member is None:
            raise not_found()

        fraud = checked_fraud_score(
            await self._rt.fraud_scorer.score(member_id=member["id"], provider_id=provider)
        )
        evaluation = await rulebook.evaluate_claim(
            self._ctx.session,
            rulebook.ClaimContext(
                organization_id=self._repo.org,
                timezone=timezone,
                member_id=member["id"],
                plan_id=member["plan_id"],
                provider_id=provider,
                service_date=body.service_date,
                lines=[(i.act_code, i.quantity) for i in body.items],
                fraud_score=fraud,
                evaluated_at=now,
            ),
        )
        decision = evaluation.decision
        refused = decision.outcome is Outcome.REFUSEE

        await self._repo.lock("claims")
        number = await self._repo.next_number("claims", "claim_number", f"PEC-{today:%y}")
        claim_id = await self._repo.insert_claim(
            claim_number=number,
            member_id=member["id"],
            beneficiary_person_id=identification["person_id"],
            provider_id=provider,
            identity_check_id=identification["id"],
            channel="comptoir",
            service_date=body.service_date,
            plan_version_id=decision.plan_version_id,
            total_xof=decision.total_xof,
            covered_xof=decision.covered_xof,
            patient_share_xof=decision.patient_share_xof,
            fraud_score=fraud,
            healthos_encounter_ref=body.healthos_encounter_ref,
            requested_at=now,
            created_by=self._ctx.principal.user_id,
        )
        await self._repo.insert_items(
            claim_id,
            [
                {
                    "act_id": acts[line.act_code]["id"],
                    "tariff_item_id": acts[line.act_code]["tariff_item_id"],
                    "quantity": line.quantity,
                    "unit_amount_xof": line.unit_amount_xof,
                    "amount_xof": line.amount_xof,
                    "covered_xof": 0 if refused else line.covered_xof,
                }
                for line in evaluation.lines
            ],
        )
        claim = await self._repo.claim(claim_id)
        assert claim is not None  # noqa: S101
        await self._repo.insert_event(
            "claim.requested",
            claim_id,
            views.claim_requested(
                claim, [(li.act_code, li.quantity, li.amount_xof) for li in evaluation.lines]
            ),
            now,
        )
        await apply_decision(
            self._repo,
            claim_id,
            outcome=decision.outcome.value,
            rule=decision.rule,
            reason_code=decision.reason_code,
            decided_by=None,
            trace=decision.evaluation_trace(),
            now=now,
            review_due_at=decision.review_due_at,
        )
        if decision.outcome is Outcome.ACCORDEE_AUTO:
            await self._repo.lock("authorizations")
            await self._repo.insert_authorization(
                authorization_number=await self._repo.next_number(
                    "authorizations", "authorization_number", f"ACC-{today:%y}"
                ),
                claim_id=claim_id,
                kind="en_ligne",
                status="emise",
                covered_xof=decision.covered_xof,
                rule_id=decision.rule.rule_id,
                rule_version=decision.rule.version,
                issued_at=now,
                expires_at=None,
                device_id=None,
                offline_ref=None,
                device_signature=None,
                signed_payload=None,
                synced_at=None,
            )
        summary_row = await self._repo.summary(claim_id)
        assert summary_row is not None  # noqa: S101
        created = ClaimCreated(
            claim=views.summary(summary_row),
            decision=views.engine_decision(decision),
            authorization=views.authorization(await self._repo.authorization(claim_id)),
        )
        body_out = created.model_dump(mode="json")
        await self._idem.complete(scope, key, 201, body_out)
        return 201, body_out

    # --- lecture ----------------------------------------------------------------------------

    async def get(self, claim_id: UUID) -> ClaimDetail:
        await self._visible_claim(claim_id)
        return await views.detail(self._repo, claim_id)

    async def list(  # noqa: PLR0913 — filtres du contrat
        self,
        *,
        status: str | None,
        fraud_flagged: bool | None,
        member_id: UUID | None,
        date_from: date | None,
        date_to: date | None,
        cursor: str | None,
        limit: int,
    ) -> ClaimList:
        scope = access(self._ctx)
        timezone = await self._repo.timezone()
        start = rulebook.day_bounds(date_from, timezone)[0] if date_from else None
        end = rulebook.day_bounds(date_to, timezone)[1] if date_to else None
        position = decode_cursor(cursor)
        rows = await self._repo.list_summaries(
            providers=None if scope.unrestricted else sorted(scope.provider_ids),
            status=status,
            fraud_flagged=fraud_flagged,
            member_id=member_id,
            start=start,
            end=end,
            before=(position.at, position.id) if position else None,
            limit=limit + 1,
        )
        page = rows[:limit]
        following = Keyset(page[-1]["requested_at"], page[-1]["id"]) if len(rows) > limit else None
        return ClaimList(
            items=[views.summary(r) for r in page],
            page=PageInfo(next_cursor=encode_cursor(following)),
        )

    async def work_queue(self) -> WorkQueue:
        _, timezone, today = await self._today()
        start, end = rulebook.day_bounds(today, timezone)
        row = await self._repo.work_queue(start, end, today - timedelta(days=30))
        return WorkQueue.model_validate(dict(row))

    # --- décisions humaines -----------------------------------------------------------------

    async def decide(self, claim_id: UUID, body: DecideClaimRequest, key: str) -> tuple[int, Any]:
        scope = "command:claim.decide"
        stored = await self._idem.begin(
            scope, key, {"claim_id": str(claim_id), **body.model_dump(mode="json")}
        )
        if stored is not None:
            return stored.status, stored.body
        claim = await self._visible_claim(claim_id, for_update=True)
        if claim["status"] != "en_revue":
            raise transition_forbidden("Seul un dossier en revue peut recevoir une décision.")
        outcome = HUMAN_OUTCOMES[body.decision]
        now = self._rt.clock.now()
        await apply_decision(
            self._repo,
            claim_id,
            outcome=outcome,
            rule=None,
            reason_code=body.reason_code,
            decided_by=self._ctx.principal.user_id,
            trace=[],
            now=now,
            review_due_at=None,
            refuse_amounts=outcome == "refusee",
        )
        body_out = (await views.detail(self._repo, claim_id)).model_dump(mode="json")
        await self._idem.complete(scope, key, 200, body_out)
        return 200, body_out

    async def submit_documents(
        self, claim_id: UUID, body: SubmitClaimDocumentsRequest, key: str
    ) -> tuple[int, Any]:
        scope = "command:claim.documents"
        stored = await self._idem.begin(
            scope, key, {"claim_id": str(claim_id), **body.model_dump(mode="json")}
        )
        if stored is not None:
            return stored.status, stored.body
        claim = await self._visible_claim(claim_id, for_update=True)
        if claim["status"] != "pieces_demandees":
            raise transition_forbidden("Ce dossier n'attend aucune pièce.")
        now = self._rt.clock.now()
        await self._repo.insert_documents(
            claim_id,
            [(d.kind, d.healthos_document_ref) for d in body.documents],
            by=self._ctx.principal.user_id,
            at=now,
        )
        delay = await rulebook.review_delay(
            self._ctx.session, self._repo.org, claim["service_date"]
        )
        await apply_decision(
            self._repo,
            claim_id,
            outcome="en_revue",
            rule=None,
            reason_code=BACK_TO_REVIEW_REASON,
            decided_by=self._ctx.principal.user_id,
            trace=[],
            now=now,
            review_due_at=now + delay,
        )
        body_out = (await views.detail(self._repo, claim_id)).model_dump(mode="json")
        await self._idem.complete(scope, key, 200, body_out)
        return 200, body_out

    # --- motif médical (R6) -----------------------------------------------------------------

    async def read_medical_reason(self, claim_id: UUID) -> MedicalReason:
        await self._visible_claim(claim_id)
        target = await self._repo.encounter_target(claim_id)
        if target is None or target["healthos_encounter_ref"] is None:
            raise not_found("Aucune consultation HealthOS n'est rattachée à ce dossier.")
        audit = CapturingAuditService(AuditRepository(self._ctx.session))
        ctx = self._ctx

        async def audit_already_written(event: ReasonReadAuditEvent) -> UUID:
            # L1 a écrit l'entrée avant d'appeler ``fetch`` ; sans elle, HealthOS n'est pas lu.
            if audit.last is None or audit.last.target_id != event.target_id:
                msg = "lecture du motif sans entrée d'audit"
                raise RuntimeError(msg)
            return audit.last.id

        async def fetch() -> str:
            try:
                read = await self._rt.healthos.read_medical_reason(
                    encounter_ref=str(target["healthos_encounter_ref"]),
                    pseudonym=target["healthos_pseudonym"],
                    context=ReasonReadContext(
                        organization_id=ctx.principal.organization_id,
                        claim_id=claim_id,
                        actor_user_id=ctx.principal.user_id,
                        actor_role="medecin_conseil",
                        request_id=ctx.request_id,
                    ),
                    record_audit=audit_already_written,
                )
            except HealthOSUnavailableError as exc:
                raise UpstreamUnavailableError from exc
            except HealthOSNotFoundError as exc:
                raise NotFoundError from exc
            except EgressDeniedError as exc:
                logger.exception("claims.healthos_egress_denied")
                raise InternalError from exc
            return read.text

        result = await MedicalReasonAccess(audit, self._rt.clock).read(
            ctx, claim_id=claim_id, fetch=fetch
        )
        return MedicalReason(
            claim_id=result.claim_id,
            text=result.text,
            read_at=result.read_at,
            audit_event_id=result.audit_event_id,
        )
