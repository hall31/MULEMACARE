"""Schémas d'entrée et de sortie du lot L5, conformes aux composants de specs/openapi.yaml.

Aucun champ médical : le motif ne sort que par ``MedicalReason`` (médecin-conseil, audité).
``healthos_encounter_ref`` est reçu à la création mais n'est renvoyé par aucune réponse.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

AmountXof = Annotated[int, Field(ge=0)]
ReasonCode = Annotated[str, Field(pattern=r"^[A-Z]{1,4}-[0-9]{2}$")]
MemberNumber = Annotated[str, Field(pattern=r"^MC-[0-9]{8}$")]
MemberStatus = Literal["actif", "carence", "suspendu"]
ClaimStatus = Literal[
    "demandee", "accordee_auto", "en_revue", "pieces_demandees", "accordee", "refusee", "payee",
    "annulee",
]  # fmt: skip
DecisionOutcome = Literal[
    "accordee_auto", "en_revue", "accordee", "refusee", "pieces_demandees", "annulee"
]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True)


# --- Comptoir ----------------------------------------------------------------------------------


class StartIdentificationRequest(_In):
    qr_payload: Annotated[str, Field(min_length=16, max_length=2048)] | None = None
    member_number: MemberNumber | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        if (self.qr_payload is None) == (self.member_number is None):
            msg = "fournir soit qr_payload, soit member_number"
            raise ValueError(msg)
        return self


class Beneficiary(_Out):
    person_id: UUID
    member_number: str
    display_name: str
    photo_url: str | None
    plan_code: str
    coverage_rate_bp: int
    member_status: MemberStatus


class Identification(_Out):
    id: UUID
    status: Literal["ouverte", "verifiee", "identite_refusee", "bloquee", "expiree"]
    qr_verified: bool
    photo_confirmed: bool | None
    code_verified: bool
    beneficiary: Beneficiary


class PhotoConfirmationRequest(_In):
    confirmed: bool


class CodeSent(_Out):
    sent_at: datetime
    expires_at: datetime


class CodeVerificationRequest(_In):
    code: Annotated[str, Field(pattern=r"^[0-9]{6}$")]


# --- Prises en charge --------------------------------------------------------------------------


class ClaimItemInput(_In):
    act_code: Annotated[str, Field(min_length=2, max_length=32)]
    quantity: Annotated[int, Field(ge=1, le=1000)] = 1


class CreateClaimRequest(_In):
    identification_id: UUID
    service_date: date
    items: Annotated[list[ClaimItemInput], Field(min_length=1, max_length=50)]
    healthos_encounter_ref: Annotated[str, Field(pattern=r"^[A-Za-z0-9\-.]{1,64}$")] | None = None


class RuleRef(_Out):
    code: str
    version: int


class RuleCheck(_Out):
    rule: RuleRef
    passed: bool
    message: str


class Decision(_Out):
    outcome: Literal["accordee_auto", "en_revue", "refusee"]
    rule: RuleRef
    reason_code: str
    message: str
    total_xof: AmountXof
    covered_xof: AmountXof
    patient_share_xof: AmountXof
    currency: Literal["XOF"] = "XOF"
    plan_version_id: UUID
    review_due_at: datetime | None
    checks: list[RuleCheck]


class ClaimSummary(_Out):
    id: UUID
    claim_number: str
    member_id: UUID
    member_display_name: str
    provider_id: UUID
    provider_name: str
    service_date: date
    requested_at: datetime
    status: ClaimStatus
    total_xof: AmountXof
    covered_xof: AmountXof
    currency: Literal["XOF"] = "XOF"
    fraud_score: float | None
    fraud_flagged: bool
    rule: RuleRef | None


class PageInfo(_Out):
    next_cursor: str | None


class ClaimList(_Out):
    items: list[ClaimSummary]
    page: PageInfo


class ClaimItem(_Out):
    line_no: int
    act_code: str
    label: str
    quantity: int
    unit_amount_xof: AmountXof
    amount_xof: AmountXof
    covered_xof: AmountXof


class ClaimDecisionRecord(_Out):
    sequence: int
    outcome: DecisionOutcome
    source: Literal["regle", "humain"]
    rule: RuleRef | None
    reason_code: str
    decided_by: UUID | None
    decided_at: datetime


class Authorization(_Out):
    id: UUID
    authorization_number: str
    kind: Literal["en_ligne", "provisoire_hors_ligne"]
    status: Literal["emise", "synchronisee", "rejetee_a_la_synchro", "expiree", "annulee"]
    covered_xof: AmountXof
    currency: Literal["XOF"] = "XOF"
    rule: RuleRef
    issued_at: datetime
    expires_at: datetime | None


class ClaimDetail(_Out):
    claim: ClaimSummary
    patient_share_xof: AmountXof
    plan_version_id: UUID
    review_due_at: datetime | None
    items: list[ClaimItem]
    decisions: list[ClaimDecisionRecord]
    authorization: Authorization | None


class ClaimCreated(_Out):
    claim: ClaimSummary
    decision: Decision
    authorization: Authorization | None


class ClaimDocumentInput(_In):
    kind: Literal["facture", "piece_clinique", "justificatif_identite", "autre"]
    healthos_document_ref: Annotated[str, Field(min_length=1, max_length=200)]


class SubmitClaimDocumentsRequest(_In):
    documents: Annotated[list[ClaimDocumentInput], Field(min_length=1, max_length=20)]


class DecideClaimRequest(_In):
    decision: Literal["accorder", "refuser", "demander_pieces"]
    reason_code: ReasonCode


class MedicalReason(_Out):
    claim_id: UUID
    text: str
    source: Literal["healthos"] = "healthos"
    read_at: datetime
    audit_event_id: UUID


class WorkQueue(_Out):
    claims_in_review: int
    fraud_alerts: int
    members_unpaid_over_30_days: int
    auto_approved_today: int


# --- Hors ligne --------------------------------------------------------------------------------


class TariffItem(_Out):
    act_code: str
    label: str
    amount_xof: AmountXof
    currency: Literal["XOF"] = "XOF"
    valid_from: date
    valid_to: date | None
    requires_prior_approval: bool


class TariffList(_Out):
    at: date
    items: list[TariffItem]


class OfflinePolicy(_Out):
    threshold_xof: AmountXof
    validity_minutes: int
    currency: Literal["XOF"] = "XOF"
    rules: list[RuleRef]
    tariff: TariffList


class RegisterCounterDeviceRequest(_In):
    label: Annotated[str, Field(min_length=1, max_length=80)]
    public_key: Annotated[str, Field(min_length=2, max_length=1000)]


class CounterDevice(_Out):
    id: UUID
    label: str
    status: Literal["actif", "revoque"]
    registered_at: datetime


class OfflineAuthorizationInput(_In):
    offline_ref: UUID
    member_number: MemberNumber
    beneficiary_id: UUID
    service_date: date
    items: Annotated[list[ClaimItemInput], Field(min_length=1, max_length=50)]
    total_xof: AmountXof
    covered_xof: AmountXof
    issued_at: datetime
    expires_at: datetime
    signed_payload: Annotated[str, Field(min_length=1, max_length=20000)]
    signature: Annotated[str, Field(min_length=1, max_length=200)]

    @model_validator(mode="after")
    def _dated_window(self) -> Self:
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            msg = "issued_at et expires_at doivent porter un fuseau"
            raise ValueError(msg)
        if self.expires_at <= self.issued_at:
            msg = "expires_at doit suivre issued_at"
            raise ValueError(msg)
        return self


class OfflineSyncRequest(_In):
    device_id: UUID
    authorizations: Annotated[list[OfflineAuthorizationInput], Field(min_length=1, max_length=200)]


class OfflineSyncItemResult(_Out):
    offline_ref: UUID
    outcome: Literal["confirmee", "rejetee"]
    reason_code: str | None
    claim_id: UUID | None
    authorization_id: UUID | None


class OfflineSyncResult(_Out):
    results: list[OfflineSyncItemResult]
