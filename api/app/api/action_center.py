"""ActionCenter HITL — proposals never auto-execute financial/coverage actions."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import TokenUser, require_roles
from app.domain.models import AgentProposal, AuditLog, Member
from app.repositories.audit import AuditRepository

router = APIRouter(prefix="/action-center", tags=["hitl"])


class CreateProposalBody(BaseModel):
    agent_name: str = Field(..., min_length=2)
    action_type: str = Field(..., min_length=2)
    cssa_id: str | None = None
    summary: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)


class DecideBody(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$")
    note: str | None = None


def _ser(p: AgentProposal) -> dict:
    return {
        "id": p.id,
        "agent_name": p.agent_name,
        "action_type": p.action_type,
        "status": p.status,
        "cssa_id": p.cssa_id,
        "summary": p.summary,
        "payload": json.loads(p.payload_json or "{}"),
        "evidence": json.loads(p.evidence_json or "{}"),
        "created_by": p.created_by,
        "decided_by": p.decided_by,
        "decision_note": p.decision_note,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "decided_at": p.decided_at.isoformat() if p.decided_at else None,
    }


def _ser_audit_log(log: AuditLog) -> dict:
    return {
        "id": log.id,
        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        "action": log.action,
        "actor_id": log.actor_id,
        "actor_role": log.actor_role,
        "agent_proposal_id": log.agent_proposal_id,
        "old_status": log.old_status,
        "new_status": log.new_status,
        "reason": log.reason,
        "context_data": log.context_data or {},
    }


@router.post("/proposals")
async def create_proposal(
    body: CreateProposalBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[TokenUser, Depends(require_roles("OPS", "ADMIN", "MEMBER"))],
) -> dict:
    prop = AgentProposal(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        agent_name=body.agent_name,
        action_type=body.action_type,
        status="pending",
        cssa_id=body.cssa_id.upper() if body.cssa_id else None,
        summary=body.summary,
        payload_json=json.dumps(body.payload, ensure_ascii=False),
        evidence_json=json.dumps(body.evidence, ensure_ascii=False),
        created_by=user.sub,
    )
    db.add(prop)
    await db.flush()

    # Log proposal creation
    audit_repo = AuditRepository(db)
    await audit_repo.log(
        action="created",
        actor_id=user.sub,
        actor_role=user.role,
        agent_proposal_id=prop.id,
        old_status=None,
        new_status="pending",
        reason="Proposal created by agent or user",
        metadata={
            "agent_name": body.agent_name,
            "action_type": body.action_type,
        },
    )

    await db.commit()
    await db.refresh(prop)
    return {"ok": True, "proposal": _ser(prop)}


@router.get("/proposals")
async def list_proposals(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[TokenUser, Depends(require_roles("OPS", "ADMIN"))],
    status_filter: str | None = None,
) -> dict:
    q = select(AgentProposal).where(AgentProposal.tenant_id == user.tenant_id)
    if status_filter:
        q = q.where(AgentProposal.status == status_filter)
    q = q.order_by(AgentProposal.created_at.desc()).limit(100)
    rows = (await db.execute(q)).scalars().all()
    return {"proposals": [_ser(p) for p in rows]}


@router.post("/proposals/{proposal_id}/decide")
async def decide_proposal(
    proposal_id: str,
    body: DecideBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[TokenUser, Depends(require_roles("OPS", "ADMIN"))],
) -> dict:
    result = await db.execute(select(AgentProposal).where(AgentProposal.id == proposal_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if prop.status != "pending":
        raise HTTPException(status_code=409, detail=f"Proposal already {prop.status}")

    old_status = prop.status
    new_status = body.decision
    prop.status = new_status
    prop.decided_by = user.sub
    prop.decision_note = body.note
    prop.decided_at = datetime.now(timezone.utc)

    audit_repo = AuditRepository(db)

    # Log decision (approved or rejected)
    await audit_repo.log(
        action=body.decision,
        actor_id=user.sub,
        actor_role=user.role,
        agent_proposal_id=prop.id,
        old_status=old_status,
        new_status=new_status,
        reason=body.note,
    )

    executed = False
    if body.decision == "approved":
        executed = await _execute(prop, db)
        if executed:
            prop.status = "executed"
            # Log execution
            await audit_repo.log(
                action="executed",
                actor_id="system",
                actor_role="system",
                agent_proposal_id=prop.id,
                old_status=new_status,
                new_status="executed",
                reason="Proposal executed successfully",
            )

    await db.commit()
    await db.refresh(prop)
    return {"ok": True, "proposal": _ser(prop), "executed": executed}


@router.get("/proposals/{proposal_id}/audit-trail")
async def get_audit_trail(
    proposal_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[TokenUser, Depends(require_roles("OPS", "ADMIN", "MEMBER"))],
) -> dict:
    """Retrieve complete immutable audit trail for a proposal."""
    # Verify proposal exists
    result = await db.execute(select(AgentProposal).where(AgentProposal.id == proposal_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")

    # Fetch audit trail
    audit_repo = AuditRepository(db)
    logs = await audit_repo.get_trail(proposal_id)

    return {
        "proposal_id": proposal_id,
        "audit_trail": [_ser_audit_log(log) for log in logs],
    }


async def _execute(prop: AgentProposal, db: AsyncSession) -> bool:
    payload = json.loads(prop.payload_json or "{}")
    if prop.action_type == "status_toggle" and prop.cssa_id:
        result = await db.execute(select(Member).where(Member.cssa_id == prop.cssa_id))
        member = result.scalar_one_or_none()
        if not member:
            return False
        member.status = str(payload.get("status", "ACTIVE")).upper()
        return True
    if prop.action_type == "claim_approve":
        # Mark executed — PHP claim store remains SoT until full sync
        return True
    if prop.action_type in {"preauth", "mcare_transmit"}:
        return True
    return False
