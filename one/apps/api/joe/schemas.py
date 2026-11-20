"""Schémas L8, conformes aux composants ``Joe*``, ``DecisionDraft*``, ``MessageDraft*``,
``Search*`` et ``AiAction*`` de specs/openapi.yaml."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

type SourceType = Literal[
    "member", "claim", "contribution", "ledger_entry", "plan_version", "rule_version",
    "provider", "tariff_item",
]  # fmt: skip
type MessagePurpose = Literal["relance_cotisation", "confirmation_accord", "demande_pieces"]
type Recommendation = Literal["accorder", "refuser", "demander_pieces"]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True)


class Source(_Out):
    type: SourceType
    id: UUID
    label: str


class JoeQuestionRequest(_In):
    question: str = Field(min_length=2, max_length=1000)
    claim_id: UUID | None = None
    member_id: UUID | None = None


class JoeAnswer(_Out):
    ai_action_id: UUID
    kind: Literal["reponse", "refus"]
    answer: str
    sources: list[Source]


class DecisionDraftRequest(_In):
    claim_id: UUID


class DecisionDraft(_Out):
    ai_action_id: UUID
    claim_id: UUID
    recommendation: Recommendation
    rationale: str
    sources: list[Source] = Field(min_length=1)
    applied: Literal[False] = False


class MessageDraftRequest(_In):
    member_id: UUID
    purpose: MessagePurpose


class MessageDraft(_Out):
    ai_action_id: UUID
    channel: Literal["sms", "whatsapp"]
    text: str
    sources: list[Source] = Field(min_length=1)


class SearchHit(_Out):
    type: Literal["member", "claim", "provider"]
    id: UUID
    label: str
    meta: str | None


class SearchResults(_Out):
    items: list[SearchHit]


class AiAction(_Out):
    id: UUID
    occurred_at: datetime
    user_id: UUID
    kind: Literal["lecture", "preparation", "reponse", "refus"]
    tool: str
    model: str | None
    sources: list[Source]


class PageInfo(_Out):
    next_cursor: str | None


class AiActionList(_Out):
    items: list[AiAction]
    page: PageInfo


class AiActionsParams(BaseModel):
    """Paramètres de ``listAiActions`` ; ``from`` et ``to`` sont des jours inclus (Q-L1-02)."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    start: date | None = Field(default=None, alias="from")
    end: date | None = Field(default=None, alias="to")
    cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
