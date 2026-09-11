"""MCare AI Integration Routes — Claude API-backed medical orientation chat.

Routes:
- POST /api/v1/mcare/chat — send message, get agent response with safety checks
- GET /api/v1/mcare/conversations/{id}/cards — list ClinCards for conversation
- POST /api/v1/mcare/conversations/{id}/transmit — escalate to Lisacare human doctor
- GET /api/v1/mcare/health-check — LLM latency + availability check

All responses tagged with "IA" + "Hypothèses non validées" disclaimer.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import TokenUser, require_roles
from app.domain.mcare_models import (
    ClinCard,
    QuotaCheckResponse,
    SpecialistType,
)
from app.domain.models import AgentProposal, McareConversation, McareMessage, Member
from app.services.mcare_agents import (
    MCareAgentError,
    SpecialistAgent,
    route_to_specialist,
)
from app.services.plan_catalog import PLAN_CATALOG

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcare", tags=["mcare_ai"])


def mcare_enabled() -> bool:
    """Check if MCare AI is enabled."""
    return os.getenv("MCARE_ENABLED", "false").lower() in {"1", "true", "yes"}


def anthropic_configured() -> bool:
    """Check if Claude API is configured."""
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())


class ChatRequest(BaseModel):
    """Request to send message to MCare AI agent."""

    conversation_id: str | None = Field(
        default=None, description="Existing conversation ID (optional)"
    )
    cssa_id: str = Field(..., min_length=6, description="Member CSSA ID")
    beneficiary_name: str | None = Field(
        default=None, description="Beneficiary name (if dependent)"
    )
    message: str = Field(..., min_length=1, max_length=4000, description="User message")
    language: str = Field(default="fr", description="fr|en")


class ChatResponse(BaseModel):
    """Response from MCare AI agent."""

    conversation_id: str
    cssa_id: str
    message: str
    specialist_type: str
    clin_card: ClinCard | None = None
    tags: list[str]
    quota_remaining: int | None = None
    safety_check: dict | None = None
    timestamp: datetime


class TransmitRequest(BaseModel):
    """Request to transmit conversation to Lisacare."""

    conversation_id: str
    reason: str = Field(
        default="user_request",
        description="Why transmitted: user_request|red_flags|quality_check",
    )


class TransmitResponse(BaseModel):
    """Response from transmit endpoint."""

    ok: bool
    conversation_status: str
    proposal_id: str | None = None
    lisacare_id: str | None = None
    message: str
    quota_remaining: int | None = None


class HealthCheckResponse(BaseModel):
    """MCare AI health check response."""

    status: str  # "healthy" | "degraded" | "unavailable"
    llm_available: bool
    llm_model: str
    llm_latency_ms: int | None = None
    mcare_enabled: bool
    error: str | None = None


@router.get("/status")
async def status() -> dict[str, Any]:
    """Get MCare AI service status."""
    return {
        "enabled": mcare_enabled(),
        "anthropic_configured": anthropic_configured(),
        "product": "MCare AI",
        "requires_active_membership": True,
        "docs": "docs/prd-mcare.md",
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[TokenUser, Depends(require_roles("MEMBER", "OPS", "ADMIN"))],
) -> ChatResponse:
    """Send message to MCare AI specialist agent.

    Routes to appropriate specialist based on message keywords:
    - TRIAGE: symptoms, medical questions
    - COVERAGE: insurance, benefits
    - NETWORK: clinic access
    - GENERAL: FAQ, administrative

    All responses validated for:
    - No diagnosis statements
    - Red flags detected
    - Quota consumption

    Returns:
        ChatResponse with agent response, clinical card (if triage), and safety check
    """
    if not mcare_enabled():
        raise HTTPException(
            status_code=503, detail="MCare AI disabled (set MCARE_ENABLED=true)"
        )

    if not anthropic_configured():
        raise HTTPException(
            status_code=503,
            detail="Claude API not configured (set ANTHROPIC_API_KEY)",
        )

    # Verify member is active
    result = await db.execute(select(Member).where(Member.cssa_id == body.cssa_id.upper()))
    member = result.scalar_one_or_none()
    if member and member.status != "ACTIVE":
        raise HTTPException(
            status_code=402,
            detail="MCare AI requires ACTIVE (Stripe-paid) membership",
        )

    # Check quota
    plan = PLAN_CATALOG.get(member.plan_id if member else "silver", PLAN_CATALOG["silver"])
    quota_remaining = member.mcare_quota_remaining if member else plan.get("mcare_quota", 15)
    if quota_remaining <= 0:
        raise HTTPException(status_code=402, detail="MCare AI quota exhausted")

    # Create or fetch conversation
    conv_id = body.conversation_id or str(uuid.uuid4())
    conv_result = await db.execute(
        select(McareConversation).where(McareConversation.id == conv_id)
    )
    conv = conv_result.scalar_one_or_none()

    if not conv:
        conv = McareConversation(
            id=conv_id,
            cssa_id=body.cssa_id.upper(),
            beneficiary_name=body.beneficiary_name,
            status="collect",
        )
        db.add(conv)
    else:
        # Verify conversation belongs to member
        if conv.cssa_id != body.cssa_id.upper():
            raise HTTPException(status_code=403, detail="Conversation not owned by member")

    # Fetch conversation history
    hist_result = await db.execute(
        select(McareMessage)
        .where(McareMessage.conversation_id == conv_id)
        .order_by(McareMessage.created_at)
    )
    history = hist_result.scalars().all()

    # Build conversation for Claude
    conversation_history = []
    for msg in history[-10:]:  # Last 10 messages for context window
        conversation_history.append(
            {
                "role": "user" if msg.role == "user" else "assistant",
                "content": msg.content,
            }
        )

    # Route to specialist
    specialist_type = route_to_specialist(body.message, language=body.language)

    try:
        # Call Claude specialist agent
        agent = SpecialistAgent(
            specialist_type=specialist_type,
            language=body.language,
        )
        agent_result = await agent.chat(
            user_message=body.message,
            conversation_history=conversation_history,
        )
    except MCareAgentError as e:
        logger.error(f"MCare agent error: {e}")
        raise HTTPException(
            status_code=503, detail=f"MCare AI error: {e}"
        ) from e

    # Extract response data
    response_text = agent_result["response"]
    clin_card = agent_result.get("clin_card")
    safety_check = agent_result.get("safety_check", {})

    # Store messages in database
    now = datetime.now(timezone.utc)
    db.add(
        McareMessage(
            id=str(uuid.uuid4()),
            conversation_id=conv_id,
            role="user",
            content=body.message,
            message_type="text",
            created_at=now,
        )
    )

    # Determine message type based on clin_card
    message_type = "clin_card" if clin_card else "text"

    db.add(
        McareMessage(
            id=str(uuid.uuid4()),
            conversation_id=conv_id,
            role="mcare",
            content=response_text,
            message_type=message_type,
            payload_json=json.dumps(
                clin_card.model_dump(), ensure_ascii=False
            ) if clin_card else None,
            created_at=now,
        )
    )

    # Update conversation status if symptoms detected
    if clin_card or specialist_type == SpecialistType.TRIAGE:
        conv.status = "orientation"

    # Decrement quota
    if member:
        member.mcare_quota_remaining = max(0, member.mcare_quota_remaining - 1)

    await db.commit()

    return ChatResponse(
        conversation_id=conv_id,
        cssa_id=body.cssa_id.upper(),
        message=response_text,
        specialist_type=specialist_type.value,
        clin_card=clin_card,
        tags=["IA", "Hypothèses non validées"],
        quota_remaining=(
            member.mcare_quota_remaining if member else quota_remaining - 1
        ),
        safety_check=safety_check,
        timestamp=now,
    )


@router.get("/conversations/{conversation_id}/cards")
async def get_clin_cards(
    conversation_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[TokenUser, Depends(require_roles("MEMBER", "OPS", "ADMIN"))],
) -> dict[str, Any]:
    """Fetch all ClinCards (clinical orientation cards) for a conversation.

    Returns:
        {
            "conversation_id": str,
            "cssa_id": str,
            "cards": [
                {
                    "message_id": str,
                    "timestamp": datetime,
                    "clin_card": ClinCard,
                }
            ]
        }
    """
    # Fetch conversation
    conv_result = await db.execute(
        select(McareConversation).where(McareConversation.id == conversation_id)
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify ownership (allow MEMBER to view own, OPS/ADMIN to view all)
    if conv.cssa_id != user.sub and user.role not in ("OPS", "ADMIN"):
        raise HTTPException(status_code=403, detail="Not authorized")

    # Fetch clin_card messages
    cards_result = await db.execute(
        select(McareMessage)
        .where(
            (McareMessage.conversation_id == conversation_id)
            & (McareMessage.message_type == "clin_card")
        )
        .order_by(McareMessage.created_at)
    )
    card_messages = cards_result.scalars().all()

    cards = []
    for msg in card_messages:
        if msg.payload_json:
            try:
                card_data = json.loads(msg.payload_json)
                cards.append(
                    {
                        "message_id": msg.id,
                        "timestamp": msg.created_at,
                        "clin_card": ClinCard(**card_data),
                    }
                )
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in message {msg.id}")

    return {
        "conversation_id": conversation_id,
        "cssa_id": conv.cssa_id,
        "card_count": len(cards),
        "cards": cards,
    }


@router.post("/conversations/{conversation_id}/transmit", response_model=TransmitResponse)
async def transmit_to_lisacare(
    conversation_id: str,
    body: TransmitRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[TokenUser, Depends(require_roles("MEMBER", "OPS", "ADMIN"))],
) -> TransmitResponse:
    """Escalate conversation to Lisacare (human doctor review).

    Consumes 1 MCare credit from member quota.
    Creates AgentProposal for HITL (human-in-the-loop) approval.

    Returns:
        TransmitResponse with Lisacare case ID and status
    """
    if not mcare_enabled():
        raise HTTPException(status_code=503, detail="MCare AI disabled")

    # Fetch conversation
    conv_result = await db.execute(
        select(McareConversation).where(McareConversation.id == conversation_id)
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify ownership
    if conv.cssa_id != user.sub and user.role not in ("OPS", "ADMIN"):
        raise HTTPException(status_code=403, detail="Not authorized")

    # Fetch member
    member_result = await db.execute(
        select(Member).where(Member.cssa_id == conv.cssa_id)
    )
    member = member_result.scalar_one_or_none()
    if member and member.mcare_quota_remaining <= 0:
        raise HTTPException(status_code=402, detail="MCare quota exhausted")

    # Decrement quota
    if member:
        member.mcare_quota_remaining = max(0, member.mcare_quota_remaining - 1)

    # Create agent proposal for HITL
    prop = AgentProposal(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        agent_name="MCare",
        action_type="mcare_transmit",
        status="pending",
        cssa_id=conv.cssa_id,
        summary=f"Escalate MCare conversation {conversation_id} to Lisacare human doctor",
        payload_json=json.dumps(
            {
                "conversation_id": conversation_id,
                "reason": body.reason,
                "beneficiary": conv.beneficiary_name,
            },
            ensure_ascii=False,
        ),
        evidence_json=json.dumps(
            {"conversation_id": conversation_id}, ensure_ascii=False
        ),
        created_by=user.sub,
    )
    db.add(prop)

    # Update conversation status
    conv.status = "transmitted"

    await db.commit()

    return TransmitResponse(
        ok=True,
        conversation_status="transmitted",
        proposal_id=prop.id,
        lisacare_id=f"HC-{conversation_id[:8]}",
        message=(
            "Dossier transmis à Lisacare pour validation médecin humaine. "
            "Vous recevrez un suivi sous 24h."
        ),
        quota_remaining=member.mcare_quota_remaining if member else None,
    )


@router.get("/quota/{cssa_id}", response_model=QuotaCheckResponse)
async def check_quota(
    cssa_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[TokenUser, Depends(require_roles("MEMBER", "OPS", "ADMIN"))],
) -> QuotaCheckResponse:
    """Check MCare AI quota for a member."""
    result = await db.execute(select(Member).where(Member.cssa_id == cssa_id.upper()))
    member = result.scalar_one_or_none()

    if not member:
        plan = PLAN_CATALOG.get("silver", PLAN_CATALOG["silver"])
        return QuotaCheckResponse(
            cssa_id=cssa_id.upper(),
            quota_remaining=plan.get("mcare_quota", 15),
            status="INACTIVE",
            message="Member not found — using default quota",
        )

    if member.status != "ACTIVE":
        return QuotaCheckResponse(
            cssa_id=cssa_id.upper(),
            quota_remaining=0,
            status="INACTIVE",
            message="Member not active",
        )

    status = "EXHAUSTED" if member.mcare_quota_remaining <= 0 else "ACTIVE"
    return QuotaCheckResponse(
        cssa_id=cssa_id.upper(),
        quota_remaining=member.mcare_quota_remaining,
        status=status,
        message=f"{member.mcare_quota_remaining} credits remaining",
    )


@router.get("/health-check", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Check MCare AI health (LLM availability, latency)."""
    if not mcare_enabled():
        return HealthCheckResponse(
            status="unavailable",
            llm_available=False,
            llm_model="none",
            mcare_enabled=False,
            error="MCare AI disabled",
        )

    if not anthropic_configured():
        return HealthCheckResponse(
            status="unavailable",
            llm_available=False,
            llm_model="claude-3-5-sonnet-20241022",
            mcare_enabled=True,
            error="Claude API not configured",
        )

    try:
        # Quick LLM health check
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        start = time.time()

        msg = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": "Health check"}],
        )

        latency_ms = int((time.time() - start) * 1000)

        return HealthCheckResponse(
            status="healthy",
            llm_available=True,
            llm_model="claude-3-5-sonnet-20241022",
            llm_latency_ms=latency_ms,
            mcare_enabled=True,
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheckResponse(
            status="degraded",
            llm_available=False,
            llm_model="claude-3-5-sonnet-20241022",
            mcare_enabled=True,
            error=str(e),
        )
