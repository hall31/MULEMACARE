"""Members API — persistance SQLAlchemy (SQLite/PG) + activation Stripe."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import TokenUser, require_roles
from app.domain.models import Member
from app.services.nss_mc import cssa_encodes_formula, display_nss

router = APIRouter(prefix="/members", tags=["members"])


class UpsertMemberBody(BaseModel):
    cssa_id: str = Field(..., min_length=6)
    nss_id: str | None = Field(default=None, max_length=32)
    plan_id: str = "silver"
    currency: str = Field(default="EUR", pattern="^(EUR|USD|XAF)$")
    subscriber_name: str = ""
    subscriber_country: str = ""
    stripe_checkout_id: str | None = None
    status: str = "PENDING_PAYMENT"


class StripeActivateBody(BaseModel):
    cssa_id: str
    checkout_session_id: str | None = None
    subscription_id: str | None = None


def _serialize(m: Member) -> dict:
    return {
        "cssa_id": m.cssa_id,
        "nss_id": m.nss_id,
        "nss_display": display_nss(m.nss_id) if m.nss_id else None,
        "status": m.status,
        "payment_status": m.payment_status,
        "plan_id": m.plan_id,
        "currency": m.currency,
        "subscriber_name": m.subscriber_name,
        "subscriber_country": m.subscriber_country,
        "stripe_checkout_id": m.stripe_checkout_id,
        "stripe_subscription_id": m.stripe_subscription_id,
        "paid_at": m.paid_at.isoformat() if m.paid_at else None,
        "card_kind": "cssa",
        "coverage_kind": "formule",
    }


@router.post("")
async def upsert_member(
    body: UpsertMemberBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[TokenUser, Depends(require_roles("OPS", "ADMIN"))],
) -> dict:
    cssa = body.cssa_id.upper()
    if cssa_encodes_formula(cssa):
        raise HTTPException(status_code=400, detail="cssa_id must not encode a coverage formula")
    result = await db.execute(select(Member).where(Member.cssa_id == cssa))
    member = result.scalar_one_or_none()
    if member is None:
        member = Member(cssa_id=cssa)
        db.add(member)
    member.plan_id = body.plan_id
    member.nss_id = body.nss_id
    member.currency = body.currency
    member.subscriber_name = body.subscriber_name
    member.subscriber_country = body.subscriber_country
    member.stripe_checkout_id = body.stripe_checkout_id
    member.status = body.status
    member.payment_status = "unpaid" if body.status != "ACTIVE" else "paid"
    await db.commit()
    await db.refresh(member)
    return {"ok": True, "member": _serialize(member)}


@router.get("/{cssa_id}")
async def get_member(
    cssa_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[TokenUser, Depends(require_roles("MEMBER", "OPS", "ADMIN"))],
) -> dict:
    result = await db.execute(select(Member).where(Member.cssa_id == cssa_id.upper()))
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"member": _serialize(member), "tenant_id": user.tenant_id}


@router.post("/activate-from-stripe")
async def activate_from_stripe(
    body: StripeActivateBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[TokenUser, Depends(require_roles("OPS", "ADMIN"))],
) -> dict:
    cssa = body.cssa_id.upper()
    result = await db.execute(select(Member).where(Member.cssa_id == cssa))
    member = result.scalar_one_or_none()
    if member is None and body.checkout_session_id:
        result = await db.execute(
            select(Member).where(Member.stripe_checkout_id == body.checkout_session_id)
        )
        member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found for Stripe activation")

    member.status = "ACTIVE"
    member.payment_status = "paid"
    member.paid_at = datetime.now(timezone.utc)
    if body.checkout_session_id:
        member.stripe_checkout_id = body.checkout_session_id
    if body.subscription_id:
        member.stripe_subscription_id = body.subscription_id
    await db.commit()
    await db.refresh(member)
    return {"ok": True, "member": _serialize(member)}
