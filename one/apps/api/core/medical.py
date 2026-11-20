"""Seul passage vers le motif médical (R6) : permission SEC-01 puis audit de chaque lecture.

Le motif n'est jamais stocké, ni journalisé, ni mis en cache : il est lu chez HealthOS par la
fonction ``fetch`` fournie par l'appelant (L5, avec le client L9), puis renvoyé tel quel.

Ordre garanti par ``read`` :
1. contrôle : seul le médecin-conseil passe, tout autre rôle (admin compris) reçoit SEC-01 et
   HealthOS n'est pas appelé ;
2. l'entrée ``claim.medical_reason.read`` est écrite dans la transaction de la requête ;
3. HealthOS est appelé ; s'il échoue, la transaction est annulée (rien n'a été lu).
La transaction est validée avant l'envoi de la réponse (``CurrentContext``).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from api.core.clock import Clock, SystemClock
from api.core.context import RequestContext
from api.core.permissions import MEDICAL_REASON_OPERATION, Role, access_scope
from api.core.services import AuditIntent, AuditService

MEDICAL_REASON_READ: Final = "claim.medical_reason.read"
# En-têtes à poser sur la réponse HTTP qui porte le motif (contrat : Cache-Control no-store).
MEDICAL_REASON_RESPONSE_HEADERS: Final = {"Cache-Control": "no-store"}

MedicalReasonFetcher = Callable[[], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class MedicalReasonRead:
    claim_id: UUID
    text: str
    read_at: datetime
    audit_event_id: UUID

    def __repr__(self) -> str:  # le motif ne doit pas apparaître dans une trace
        return f"MedicalReasonRead(claim_id={self.claim_id}, audit_event_id={self.audit_event_id})"


class MedicalReasonAccess:
    def __init__(self, audit: AuditService, clock: Clock | None = None) -> None:
        self._audit = audit
        self._clock = clock or SystemClock()

    async def read(
        self, ctx: RequestContext, *, claim_id: UUID, fetch: MedicalReasonFetcher
    ) -> MedicalReasonRead:
        access_scope(ctx.principal, MEDICAL_REASON_OPERATION)  # SEC-01 sinon
        event = await self._audit.record(
            ctx,
            AuditIntent(
                action=MEDICAL_REASON_READ,
                target_type="claim",
                target_id=claim_id,
                actor_role=Role.MEDECIN_CONSEIL.value,
            ),
        )
        text = await fetch()
        return MedicalReasonRead(
            claim_id=claim_id, text=text, read_at=self._clock.now(), audit_event_id=event.id
        )
