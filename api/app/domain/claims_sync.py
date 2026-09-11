"""Claims synchronization between PHP (source of truth) and Mutuelle OS (mirror)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ClaimStatus(str, Enum):
    """Claim lifecycle states."""
    SUBMITTED = "submitted"  # Initial submission by clinic
    PENDING_TRIAGE = "pending_triage"  # Waiting agent triage
    PENDING_REVIEW = "pending_review"  # Waiting HITL approval
    APPROVED = "approved"  # Approved, ready for payment
    REJECTED = "rejected"  # Rejected with reason
    PAID = "paid"  # Executed by finance
    APPEALED = "appealed"  # Member/clinic appealed


class Claim(Base):
    """Claims mirror in Mutuelle OS (synced from PHP MySQL via webhook)."""

    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cssa_id: Mapped[str] = mapped_column(String(64), index=True)
    clinic_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    act_type: Mapped[str] = mapped_column(String(64))  # consultation, hospitalization, drug, etc
    amount_invoiced: Mapped[int] = mapped_column(Integer)  # cents (XAF, EUR, USD)
    currency: Mapped[str] = mapped_column(String(8), default="XAF")
    status: Mapped[str] = mapped_column(String(32), default=ClaimStatus.SUBMITTED, index=True)

    # Triage result
    approved_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approval_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # References
    agent_proposal_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    healthos_preauth_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Sync metadata
    source_system: Mapped[str] = mapped_column(String(32), default="php_mysql")  # php_mysql, external_api
    external_claim_id: Mapped[str | None] = mapped_column(String(128), nullable=True)  # Reference in source system
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_sync_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class ClaimSyncLog(Base):
    """Audit log for claim synchronization events."""

    __tablename__ = "claim_sync_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(64), index=True)
    sync_direction: Mapped[str] = mapped_column(String(32))  # php_to_os, os_to_php
    action: Mapped[str] = mapped_column(String(64))  # created, status_updated, approved_amount_set
    old_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
