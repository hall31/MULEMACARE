"""Claims triage — always creates HITL proposal, never auto-approves."""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import TokenUser, require_roles
from app.domain.models import AgentProposal, Member
from app.services.plan_catalog import PLAN_CATALOG

router = APIRouter(prefix="/claims", tags=["claims"])


class TriageBody(BaseModel):
    cssa_id: str
    clinic_name: str = "Clinique conventionnée"
    act_type: str = "consultation"
    amount_invoiced: int = Field(..., gt=0)
    notes: str = ""


@router.post("/triage")
async def claims_triage(
    body: TriageBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[TokenUser, Depends(require_roles("OPS", "ADMIN", "MEMBER"))],
) -> dict:
    result = await db.execute(select(Member).where(Member.cssa_id == body.cssa_id.upper()))
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.status != "ACTIVE":
        raise HTTPException(status_code=402, detail="Card not ACTIVE — payment required")

    plan = PLAN_CATALOG.get(member.plan_id, PLAN_CATALOG["silver"])
    recommendation = "approve" if body.amount_invoiced <= 150000 else "review"
    evidence = {
        "cssa_id": member.cssa_id,
        "plan_id": member.plan_id,
        "ceiling_label": plan["ceiling_label"],
        "amount_invoiced": body.amount_invoiced,
        "clinic_name": body.clinic_name,
        "act_type": body.act_type,
        "recommendation": recommendation,
    }
    prop = AgentProposal(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        agent_name="ClaimsTriageAgent",
        action_type="claim_approve",
        status="pending",
        cssa_id=member.cssa_id,
        summary=(
            f"PEC {body.act_type} {body.amount_invoiced} XAF @ {body.clinic_name} "
            f"— reco {recommendation} (HITL obligatoire)"
        ),
        payload_json=json.dumps(
            {
                "amount_invoiced": body.amount_invoiced,
                "clinic_name": body.clinic_name,
                "act_type": body.act_type,
                "notes": body.notes,
            },
            ensure_ascii=False,
        ),
        evidence_json=json.dumps(evidence, ensure_ascii=False),
        created_by=user.sub,
    )
    db.add(prop)
    await db.commit()
    await db.refresh(prop)
    return {
        "agent": "ClaimsTriageAgent",
        "auto_approved": False,
        "proposal_id": prop.id,
        "status": "pending",
        "evidence": evidence,
        "narrative": (
            "Sinistre soumis à l'ActionCenter. Aucune prise en charge financière "
            "n'est exécutée sans décision humaine OPS/ADMIN."
        ),
    }
