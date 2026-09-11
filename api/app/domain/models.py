"""Domain ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, EncryptedText


class Member(Base):
    __tablename__ = "members"

    cssa_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    nss_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING_PAYMENT")
    payment_status: Mapped[str] = mapped_column(String(32), default="unpaid")
    plan_id: Mapped[str] = mapped_column(String(32), default="silver")
    currency: Mapped[str] = mapped_column(String(8), default="EUR")
    subscriber_name: Mapped[str] = mapped_column(String(255), default="")
    subscriber_country: Mapped[str] = mapped_column(String(64), default="")
    stripe_checkout_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mcare_quota_remaining: Mapped[int] = mapped_column(Integer, default=15)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="MEMBER")
    tenant_id: Mapped[str] = mapped_column(String(64), default="mulemacare")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentProposal(Base):
    __tablename__ = "agent_proposals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="mulemacare", index=True)
    agent_name: Mapped[str] = mapped_column(String(64))
    action_type: Mapped[str] = mapped_column(String(64))  # claim_approve|status_toggle|preauth|mcare_transmit
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    cssa_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    # PII health data — encrypted at ORM layer with Fernet
    payload_json: Mapped[str] = mapped_column(EncryptedText, default="{}")
    evidence_json: Mapped[str] = mapped_column(EncryptedText, default="{}")
    created_by: Mapped[str] = mapped_column(String(64), default="system")
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class McareConversation(Base):
    __tablename__ = "mcare_conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cssa_id: Mapped[str] = mapped_column(String(64), index=True)
    beneficiary_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="collect")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class McareMessage(Base):
    __tablename__ = "mcare_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(32))  # user|mcare|system
    content: Mapped[str] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(String(32), default="text")  # text|clin_card
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Immutable audit trail for AgentProposal lifecycle tracking."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    action: Mapped[str] = mapped_column(
        String(32),
        index=True,
    )  # created|approved|rejected|executed
    actor_id: Mapped[str] = mapped_column(String(64), index=True)  # user ID or "system"
    actor_role: Mapped[str] = mapped_column(String(32), default="system")  # MEMBER|OPS|ADMIN|system
    agent_proposal_id: Mapped[str] = mapped_column(String(64), index=True)  # FK to AgentProposal
    old_status: Mapped[str | None] = mapped_column(String(32), nullable=True)  # previous status
    new_status: Mapped[str] = mapped_column(String(32))  # new status
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)  # decision note or reason
    context_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # agent version, prompt hash, etc
