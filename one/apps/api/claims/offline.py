"""Accord provisoire hors ligne (R13, côté serveur) : politique, appareils, synchronisation.

Synchronisation d'un accord, idempotente par (``device_id``, ``offline_ref``) :
1. appareil révoqué → OFF-04 (rien n'est créé : contenu non fiable) ;
2. signature ES256 invalide, ou champs en clair différents du contenu signé → OFF-02 ;
3. adhérent/bénéficiaire inconnu → NOT-01, acte inconnu → CLM-02 (rien n'est créé) ;
4. identification du contenu signé non vérifiée, d'un autre bénéficiaire ou déjà utilisée → ID-07 ;
5. synchronisé après ``expires_at``, ou validité plus longue que HL-01 → OFF-01 ;
6. total (déclaré ou au barème) ≥ seuil de R-12 → OFF-03 ;
7. sinon le moteur L2 décide, aux faits et versions de la date du soin, score de fraude lu à
   la synchronisation (Q-L5-08) :
   - ``refusee`` (R-01, R-04, R-07, R-09) → dossier refusé avec la règle du moteur, accord
     ``rejetee_a_la_synchro``, réponse ``rejetee`` avec ce code ;
   - ``en_revue`` (R-20) → dossier en revue du médecin-conseil, accord non confirmé
     (``rejetee_a_la_synchro``, couverture 0), réponse ``rejetee`` avec ``R-20`` ;
   - ``accordee_auto`` (R-12) → dossier accordé par le moteur, accord ``synchronisee`` (HL-01).
Les cas 2, 4, 5, 6 et 7 créent un dossier et un accord (traçabilité), émettent ``claim.decided``
et ``authorization.synced`` (specs/events.md) ; seul ``accordee_auto`` mène au grand livre.
Concurrence : chaque (``device_id``, ``offline_ref``) est verrouillé avant lecture (une même
file rejouée en parallèle ne crée qu'un dossier), l'identification l'est ``FOR UPDATE``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.engine import RowMapping

from api.claims import ecdsa, rulebook, views
from api.claims.common import access, clinic_provider, local_date
from api.claims.errors import invalid, not_found
from api.claims.ports import ClaimsRuntime
from api.claims.repository import ClaimsRepository
from api.claims.schemas import (
    CounterDevice,
    OfflineAuthorizationInput,
    OfflinePolicy,
    OfflineSyncItemResult,
    OfflineSyncRequest,
    OfflineSyncResult,
    RegisterCounterDeviceRequest,
    RuleRef,
    TariffItem,
    TariffList,
)
from api.claims.service import apply_decision, checked_fraud_score
from api.core.context import RequestContext
from api.rules.model import Decision, Outcome
from api.rules.model import RuleRef as EngineRuleRef

PAYLOAD_VERSION = 1


@dataclass(frozen=True, slots=True)
class _Signed:
    valid: bool
    content: dict[str, Any] | None


def _instant(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _matches(content: dict[str, Any], item: OfflineAuthorizationInput, device_id: UUID) -> bool:
    """Les champs en clair doivent égaler ceux du contenu signé (Q-L7-03)."""
    items = content.get("items")
    plain_items = [{"act_code": i.act_code, "quantity": i.quantity} for i in item.items]
    return (
        content.get("v") == PAYLOAD_VERSION
        and content.get("currency") == "XOF"
        and content.get("offline_ref") == str(item.offline_ref)
        and content.get("device_id") == str(device_id)
        and content.get("member_number") == item.member_number
        and content.get("beneficiary_id") == str(item.beneficiary_id)
        and content.get("service_date") == item.service_date.isoformat()
        and isinstance(items, list)
        and [
            {"act_code": i.get("act_code"), "quantity": i.get("quantity", 1)}
            for i in items
            if isinstance(i, dict)
        ]
        == plain_items
        and content.get("total_xof") == item.total_xof
        and content.get("covered_xof") == item.covered_xof
        and _instant(content.get("issued_at")) == item.issued_at
        and _instant(content.get("expires_at")) == item.expires_at
    )


def check_signature(public_key: str, item: OfflineAuthorizationInput, device_id: UUID) -> _Signed:
    try:
        key = ecdsa.parse_public_jwk(public_key)
        raw = ecdsa.b64url_decode(item.signed_payload)
        signature = ecdsa.b64url_decode(item.signature)
    except ValueError:
        return _Signed(valid=False, content=None)
    try:
        decoded = json.loads(raw)
    except ValueError:
        decoded = None
    content = decoded if isinstance(decoded, dict) else None
    valid = (
        content is not None
        and ecdsa.verify_es256(key, raw, signature)
        and _matches(content, item, device_id)
    )
    return _Signed(valid=valid, content=content)


@dataclass(frozen=True, slots=True)
class _Verdict:
    """Issue d'une synchronisation : décision du dossier et sort de l'accord provisoire."""

    outcome: str  # claim_decisions.outcome
    rule: EngineRuleRef  # règle qui décide le dossier (rule_id, rule_version)
    reason_code: str  # code stable de la décision du dossier
    sync_reason: str | None  # None = accord confirmé ; sinon code renvoyé au comptoir
    authorization_rule: EngineRuleRef  # règle portée par l'accord et authorization.synced
    review_due_at: datetime | None
    offline_trace: dict[str, object]  # étape HL-01 ajoutée à la trace du moteur


def _verdict(decision: Decision, hl01: EngineRuleRef, technical: str | None) -> _Verdict:
    """Rejet technique (OFF-0x, ID-07) décidé par HL-01, sinon décision du moteur L2.

    L'accord n'est confirmé que si le moteur accorde automatiquement (R-12) : un refus
    (R-01, R-04, R-07, R-09) ou une revue (R-20) le laisse non confirmé avec ce code.
    """
    sync_reason: str | None
    if technical is not None:
        outcome, rule, reason, sync_reason = "refusee", hl01, technical, technical
        message = f"Accord provisoire rejeté à la synchronisation ({technical})."
    else:
        outcome, rule, reason = decision.outcome.value, decision.rule, decision.reason_code
        confirmed = decision.outcome is Outcome.ACCORDEE_AUTO
        sync_reason = None if confirmed else decision.reason_code
        message = (
            "Accord provisoire hors ligne confirmé à la synchronisation."
            if confirmed
            else f"Accord provisoire non confirmé : décision du moteur ({reason})."
        )
    return _Verdict(
        outcome=outcome,
        rule=rule,
        reason_code=reason,
        sync_reason=sync_reason,
        authorization_rule=hl01 if technical is not None or sync_reason is None else rule,
        review_due_at=decision.review_due_at if outcome == Outcome.EN_REVUE else None,
        offline_trace={
            "rule_id": str(hl01.rule_id),
            "rule_code": hl01.code,
            "rule_version": hl01.version,
            "passed": sync_reason is None,
            "message": message,
        },
    )


class OfflineService:
    def __init__(self, ctx: RequestContext, runtime: ClaimsRuntime) -> None:
        self._ctx = ctx
        self._rt = runtime
        self._repo = ClaimsRepository(ctx.session, ctx.principal.organization_id)

    async def _today(self) -> tuple[datetime, str, date]:
        now = self._rt.clock.now()
        timezone = await self._repo.timezone()
        return now, timezone, local_date(now, timezone)

    async def policy(self) -> OfflinePolicy:
        _, _, today = await self._today()
        rules = await rulebook.offline_rules(self._ctx.session, self._repo.org, today)
        return OfflinePolicy(
            threshold_xof=rules.threshold_xof,
            validity_minutes=int(rules.validity.total_seconds() // 60),
            rules=[
                RuleRef(code=rules.auto.code, version=rules.auto.version),
                RuleRef(code=rules.offline.code, version=rules.offline.version),
            ],
            tariff=TariffList(
                at=today,
                items=[TariffItem.model_validate(dict(r)) for r in await self._repo.tariff(today)],
            ),
        )

    async def register_device(self, body: RegisterCounterDeviceRequest) -> CounterDevice:
        provider = clinic_provider(self._ctx)
        try:
            ecdsa.parse_public_jwk(body.public_key)
        except ecdsa.InvalidKeyError as exc:
            raise invalid(
                "La clé publique de l'appareil n'est pas une clé EC P-256 valide.",
                "Réinitialisez l'appareil de comptoir puis recommencez l'enregistrement.",
            ) from exc
        row = await self._repo.insert_device(
            provider_id=provider, label=body.label, public_key=body.public_key,
            at=self._rt.clock.now(),
        )  # fmt: skip
        return CounterDevice.model_validate(dict(row))

    async def sync(self, body: OfflineSyncRequest) -> OfflineSyncResult:
        device = await self._repo.device(body.device_id)
        if device is None or device["provider_id"] not in access(self._ctx).provider_ids:
            raise not_found("Appareil de comptoir inconnu.")
        now, timezone, _ = await self._today()
        # Verrous pris d'emblée et dans un ordre fixe : deux files concurrentes ne s'interbloquent
        # pas, et un offline_ref rejoué en parallèle attend puis relit l'accord déjà créé.
        for ref in sorted({str(item.offline_ref) for item in body.authorizations}):
            await self._repo.lock(f"offline:{device['id']}:{ref}")
        results = [await self._one(device, item, now, timezone) for item in body.authorizations]
        return OfflineSyncResult(results=results)

    @staticmethod
    def _result(
        item: OfflineAuthorizationInput,
        reason: str | None,
        claim_id: UUID | None = None,
        authorization_id: UUID | None = None,
    ) -> OfflineSyncItemResult:
        return OfflineSyncItemResult(
            offline_ref=item.offline_ref,
            outcome="confirmee" if reason is None else "rejetee",
            reason_code=reason,
            claim_id=claim_id,
            authorization_id=authorization_id,
        )

    async def _identification_ok(
        self, content: dict[str, Any] | None, member_id: UUID, person_id: UUID, provider: UUID
    ) -> UUID | None:
        try:
            identification_id = UUID(str((content or {}).get("identification_id")))
        except ValueError:
            return None
        row = await self._repo.identification(identification_id, for_update=True)
        if (
            row is None
            or row["status"] != "verifiee"
            or row["provider_id"] != provider
            or row["member_id"] != member_id
            or row["person_id"] != person_id
            or await self._repo.identification_used(identification_id)
        ):
            return None
        return identification_id

    async def _one(
        self, device: RowMapping, item: OfflineAuthorizationInput, now: datetime, timezone: str
    ) -> OfflineSyncItemResult:
        existing = await self._repo.offline_authorization(device["id"], item.offline_ref)
        if existing is not None:
            confirmed = existing["status"] == "synchronisee"
            return self._result(
                item,
                None if confirmed else str(existing["reason_code"]),
                existing["claim_id"],
                existing["id"],
            )
        if device["status"] != "actif":
            return self._result(item, "OFF-04")

        signed = check_signature(str(device["public_key"]), item, device["id"])
        member = await self._repo.member_by_number(item.member_number)
        if member is None or not await self._repo.is_beneficiary(
            member["id"], item.beneficiary_id, item.service_date
        ):
            return self._result(item, "NOT-01")
        codes = [i.act_code for i in item.items]
        acts = await self._repo.acts(codes, item.service_date)
        if any(code not in acts for code in codes):
            return self._result(item, "CLM-02")

        provider: UUID = device["provider_id"]
        rules = await rulebook.offline_rules(self._ctx.session, self._repo.org, item.service_date)
        # Score lu à la synchronisation par le même port qu'en ligne : sans score, R-12 ne
        # peut pas accorder et le moteur route vers R-20 (Q-L5-05, Q-L5-08).
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
                service_date=item.service_date,
                lines=[(i.act_code, i.quantity) for i in item.items],
                fraud_score=fraud,
                evaluated_at=now,
            ),
        )
        total = sum(line.amount_xof for line in evaluation.lines)
        identification, technical = await self._technical_checks(
            signed=signed,
            item=item,
            member_id=member["id"],
            provider=provider,
            rules=rules,
            total=total,
            now=now,
        )
        verdict = _verdict(
            evaluation.decision,
            EngineRuleRef(rules.offline.rule_id, rules.offline.code, rules.offline.version),
            technical,
        )
        claim_id = await self._record_claim(
            item=item,
            member=member,
            provider=provider,
            identification=identification,
            acts=acts,
            evaluation=evaluation,
            verdict=verdict,
            fraud=fraud,
            now=now,
            timezone=timezone,
        )
        authorization_id = await self._record_authorization(
            device=device,
            item=item,
            signed=signed,
            claim_id=claim_id,
            verdict=verdict,
            evaluation=evaluation,
            now=now,
            timezone=timezone,
        )
        return self._result(item, verdict.sync_reason, claim_id, authorization_id)

    async def _technical_checks(  # noqa: PLR0913 — contrôles 2, 4, 5, 6 de l'en-tête
        self,
        *,
        signed: _Signed,
        item: OfflineAuthorizationInput,
        member_id: UUID,
        provider: UUID,
        rules: rulebook.OfflineRules,
        total: int,
        now: datetime,
    ) -> tuple[UUID | None, str | None]:
        """Identification retenue et code de rejet technique (OFF-0x, ID-07), ou ``None``."""
        if not signed.valid:
            return None, "OFF-02"
        identification = await self._identification_ok(
            signed.content, member_id, item.beneficiary_id, provider
        )
        if identification is None:
            return None, "ID-07"
        if now > item.expires_at or item.expires_at - item.issued_at > rules.validity:
            return identification, "OFF-01"
        if max(item.total_xof, total) >= rules.threshold_xof:
            return identification, "OFF-03"
        return identification, None

    async def _record_claim(  # noqa: PLR0913 — dossier, lignes, décision et événements
        self,
        *,
        item: OfflineAuthorizationInput,
        member: RowMapping,
        provider: UUID,
        identification: UUID | None,
        acts: dict[str, RowMapping],
        evaluation: rulebook.Evaluation,
        verdict: _Verdict,
        fraud: Decimal | None,
        now: datetime,
        timezone: str,
    ) -> UUID:
        refused = verdict.outcome == "refusee"
        total = sum(line.amount_xof for line in evaluation.lines)
        covered = sum(line.covered_xof for line in evaluation.lines)
        await self._repo.lock("claims")
        today = local_date(now, timezone)
        claim_id = await self._repo.insert_claim(
            claim_number=await self._repo.next_number("claims", "claim_number", f"PEC-{today:%y}"),
            member_id=member["id"],
            beneficiary_person_id=item.beneficiary_id,
            provider_id=provider,
            identity_check_id=identification,
            channel="comptoir_hors_ligne",
            service_date=item.service_date,
            plan_version_id=evaluation.decision.plan_version_id,
            total_xof=total,
            covered_xof=covered,
            patient_share_xof=total - covered,
            fraud_score=fraud,
            healthos_encounter_ref=None,
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
            outcome=verdict.outcome,
            rule=verdict.rule,
            reason_code=verdict.reason_code,
            decided_by=None,
            trace=[*evaluation.decision.evaluation_trace(), verdict.offline_trace],
            now=now,
            review_due_at=verdict.review_due_at,
            refuse_amounts=refused,
        )
        return claim_id

    async def _record_authorization(  # noqa: PLR0913 — accord hors ligne et son événement
        self,
        *,
        device: RowMapping,
        item: OfflineAuthorizationInput,
        signed: _Signed,
        claim_id: UUID,
        verdict: _Verdict,
        evaluation: rulebook.Evaluation,
        now: datetime,
        timezone: str,
    ) -> UUID:
        confirmed = verdict.sync_reason is None
        covered = sum(line.covered_xof for line in evaluation.lines) if confirmed else 0
        rule = verdict.authorization_rule
        status = {None: "synchronisee", "OFF-01": "expiree"}.get(
            verdict.sync_reason, "rejetee_a_la_synchro"
        )
        await self._repo.lock("authorizations")
        today = local_date(now, timezone)
        authorization_id = await self._repo.insert_authorization(
            authorization_number=await self._repo.next_number(
                "authorizations", "authorization_number", f"ACC-{today:%y}"
            ),
            claim_id=claim_id,
            kind="provisoire_hors_ligne",
            status=status,
            covered_xof=covered,
            rule_id=rule.rule_id,
            rule_version=rule.version,
            issued_at=item.issued_at,
            expires_at=item.expires_at,
            device_id=device["id"],
            offline_ref=item.offline_ref,
            device_signature=item.signature,
            signed_payload=json.dumps(
                signed.content if signed.content is not None else {"illisible": True},
                ensure_ascii=False,
            ),
            synced_at=now,
        )
        await self._repo.insert_event(
            "authorization.synced",
            authorization_id,
            {
                "authorization_id": str(authorization_id),
                "claim_id": str(claim_id),
                "device_id": str(device["id"]),
                "offline_ref": str(item.offline_ref),
                "outcome": "confirmee" if confirmed else "rejetee",
                "reason_code": verdict.sync_reason,
                "rule": {"code": rule.code, "version": rule.version},
                "issued_at": item.issued_at.isoformat(),
                "expires_at": item.expires_at.isoformat(),
                "synced_at": now.isoformat(),
                "covered_xof": covered,
                "currency": "XOF",
            },
            now,
        )
        return authorization_id
