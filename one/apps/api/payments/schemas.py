"""Schémas « cotisations » conformes aux composants L4 de specs/openapi.yaml.

``CheckoutRequest`` et ``PaymentWebhookRequest`` refusent tout champ inconnu : aucun numéro de
carte bancaire ne peut entrer (``additionalProperties: false`` du contrat).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

type PaymentChannelValue = Literal[
    "wave", "orange_money", "mtn_momo", "virement", "prelevement_employeur", "simulation"
]
type ContributionStatus = Literal["a_payer", "payee", "en_retard", "annulee"]
type PaymentStatus = Literal["en_attente", "confirme", "echoue"]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True)


class Contribution(_Out):
    id: UUID
    period_start: date
    due_on: date
    amount_xof: int = Field(ge=0)
    currency: Literal["XOF"] = "XOF"
    status: ContributionStatus
    paid_at: datetime | None
    channel: PaymentChannelValue | None


class ContributionList(_Out):
    items: list[Contribution]


class PaymentLink(_Out):
    url: str
    expires_at: datetime


class PublicPaymentLink(_Out):
    period_start: date
    amount_xof: int = Field(ge=0)
    currency: Literal["XOF"] = "XOF"
    holder_initials: str
    channels: list[PaymentChannelValue]


class CheckoutRequest(_In):
    channel: PaymentChannelValue
    payer_country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")


class Checkout(_Out):
    payment_id: UUID
    status: PaymentStatus
    redirect_url: str | None


class ReminderRequest(_In):
    channel: Literal["sms", "whatsapp"]
    template_code: str = Field(pattern=r"^[a-z_]{2,64}$")
    contribution_id: UUID | None = None


class QueuedMessage(_Out):
    id: UUID
    status: Literal["en_file", "envoye", "echoue"]


class PaymentWebhookRequest(_In):
    event_id: str = Field(min_length=8, max_length=200)
    provider_reference: str = Field(min_length=1, max_length=200)
    merchant_reference: UUID
    status: Literal["confirme", "echoue"]
    amount_xof: int = Field(ge=0)
    currency: Literal["XOF"]
    occurred_at: AwareDatetime


class WebhookAck(_Out):
    received: bool
    duplicate: bool
