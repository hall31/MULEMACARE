"""MCare — chat diaspora tools-backed (fondation vendable)."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import TokenUser, require_roles
from app.domain.models import AgentProposal, McareConversation, McareMessage, Member
from app.services.plan_catalog import NETWORK_SAMPLE, PLAN_CATALOG

router = APIRouter(prefix="/mcare", tags=["mcare"])


def mcare_enabled() -> bool:
    return os.getenv("MCARE_ENABLED", "false").lower() in {"1", "true", "yes"}


class StartConversationBody(BaseModel):
    cssa_id: str = Field(..., min_length=6)
    beneficiary_name: str | None = None
    message: str = Field(..., min_length=1, max_length=4000)


class TransmitBody(BaseModel):
    conversation_id: str


def _intent(message: str) -> str:
    m = message.lower()
    if any(w in m for w in ("fièvre", "fievre", "douleur", "toux", "symptôme", "symptome")):
        return "symptoms"
    if any(w in m for w in ("couvert", "garantie", "plafond", "carence")):
        return "coverage"
    if any(w in m for w in ("clinique", "pharmacie", "réseau", "reseau", "où aller", "ou aller")):
        return "network"
    if any(w in m for w in ("carte", "cssa", "qr")):
        return "card"
    return "general"


@router.get("/status")
def status() -> dict:
    return {
        "enabled": mcare_enabled(),
        "product": "MCare",
        "requires_active_membership": True,
        "docs": "docs/prd-mcare.md",
    }


@router.post("/conversations")
async def start_conversation(
    body: StartConversationBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[TokenUser, Depends(require_roles("MEMBER", "OPS", "ADMIN"))],
) -> dict:
    if not mcare_enabled():
        raise HTTPException(status_code=503, detail="MCare disabled (set MCARE_ENABLED=true)")

    result = await db.execute(select(Member).where(Member.cssa_id == body.cssa_id.upper()))
    member = result.scalar_one_or_none()
    if member and member.status != "ACTIVE":
        raise HTTPException(status_code=402, detail="MCare Family requires ACTIVE (Stripe-paid) membership")

    intent = _intent(body.message)
    plan = PLAN_CATALOG.get(member.plan_id if member else "silver", PLAN_CATALOG["silver"])
    conv_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    reply = ""
    clin_card = None
    if intent == "coverage":
        reply = (
            f"Couverture {plan['name']} : {plan['ceiling_label']}. "
            "Carences et plafonds sont lus depuis le catalogue Mutuelle (tool déterministe)."
        )
    elif intent == "network":
        clinics = ", ".join(f"{c['name']} ({c['city']})" for c in NETWORK_SAMPLE)
        reply = f"Cliniques tiers-payant proches : {clinics}."
    elif intent == "card":
        reply = (
            f"Carte CSSA {body.cssa_id.upper()} — "
            + ("ACTIVE." if member and member.status == "ACTIVE" else "vérifiez le paiement Stripe.")
        )
    elif intent == "symptoms":
        clin_card = {
            "tags": ["IA", "Hypothèses non validées"],
            "concern_level": "modere",
            "hypotheses": ["Syndrome fébrile à explorer", "Infection virale possible"],
            "next_step": "Transmettre à un médecin humain / Lisacare — jamais un diagnostic final IA.",
        }
        reply = (
            "J'ai préparé une ClinCard d'orientation (tags IA obligatoires). "
            "Utilisez /transmit pour envoyer au médecin (consomme 1 crédit quota)."
        )
    else:
        reply = (
            "Je suis MCare. Posez une question sur couverture, réseau, carte, ou symptômes. "
            "L'IA oriente ; un médecin humain valide."
        )

    if body.beneficiary_name:
        reply = f"Concernant {body.beneficiary_name}: " + reply

    conv = McareConversation(
        id=conv_id,
        cssa_id=body.cssa_id.upper(),
        beneficiary_name=body.beneficiary_name,
        status="orientation" if clin_card else "collect",
    )
    db.add(conv)
    db.add(
        McareMessage(
            id=str(uuid.uuid4()),
            conversation_id=conv_id,
            role="user",
            content=body.message,
            created_at=now,
        )
    )
    db.add(
        McareMessage(
            id=str(uuid.uuid4()),
            conversation_id=conv_id,
            role="mcare",
            content=reply,
            message_type="clin_card" if clin_card else "text",
            payload_json=json.dumps(clin_card, ensure_ascii=False) if clin_card else None,
            created_at=now,
        )
    )
    await db.commit()

    messages = [
        {"role": "user", "content": body.message, "message_type": "text"},
        {
            "role": "mcare",
            "content": reply,
            "message_type": "clin_card" if clin_card else "text",
            "clin_card": clin_card,
        },
    ]
    return {
        "conversation_id": conv_id,
        "cssa_id": body.cssa_id.upper(),
        "status": conv.status,
        "intent": intent,
        "quota_remaining": member.mcare_quota_remaining if member else plan["mcare_quota"],
        "messages": messages,
        "tags": ["IA", "Hypothèses non validées"] if clin_card else [],
    }


@router.post("/conversations/transmit")
async def transmit(
    body: TransmitBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[TokenUser, Depends(require_roles("MEMBER", "OPS", "ADMIN"))],
) -> dict:
    if not mcare_enabled():
        raise HTTPException(status_code=503, detail="MCare disabled")
    result = await db.execute(select(McareConversation).where(McareConversation.id == body.conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    member_res = await db.execute(select(Member).where(Member.cssa_id == conv.cssa_id))
    member = member_res.scalar_one_or_none()
    if member:
        if member.mcare_quota_remaining <= 0:
            raise HTTPException(status_code=402, detail="MCare quota exhausted")
        member.mcare_quota_remaining -= 1

    conv.status = "transmitted"
    prop = AgentProposal(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        agent_name="MCare",
        action_type="mcare_transmit",
        status="pending",
        cssa_id=conv.cssa_id,
        summary=f"Transmit conversation {conv.id} to human doctor / Lisacare",
        payload_json=json.dumps({"conversation_id": conv.id, "lisacare": True}, ensure_ascii=False),
        evidence_json=json.dumps({"beneficiary": conv.beneficiary_name}, ensure_ascii=False),
        created_by=user.sub,
    )
    db.add(prop)
    await db.commit()
    return {
        "ok": True,
        "conversation_status": "transmitted",
        "proposal_id": prop.id,
        "quota_remaining": member.mcare_quota_remaining if member else None,
        "lisacare_url": "https://lisacare.mulemacare.com",
        "message": "Dossier transmis — validation médecin humaine requise (HITL).",
    }
