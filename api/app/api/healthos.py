"""HealthOS partner bridge — OFF by default, read eligibility only when enabled.

Routes:
- GET /api/v1/healthos/status — bridge status (OPS/ADMIN only)
- POST /api/v1/healthos/eligibility — fetch member eligibility from HealthOS (read-only)
- POST /api/v1/healthos/preauth-intent — create preauth proposal (PENDING_REVIEW only)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.security import TokenUser, require_roles
from app.domain.models import AgentProposal
from app.services.healthos_client import (
    HealthOSClient,
    HealthOSClientError,
    get_healthos_client,
)

router = APIRouter(prefix="/healthos", tags=["healthos"])


class EligibilityRequest(BaseModel):
    """Request to fetch member eligibility from HealthOS."""

    cssa_id: str = Field(..., description="MulemaCare member ID (CSSA)")
    healthos_patient_id: str = Field(..., description="HealthOS patient ID")


class PreauthIntentRequest(BaseModel):
    """Request to create a pre-authorization intent on HealthOS."""

    cssa_id: str = Field(..., description="MulemaCare member ID (CSSA)")
    healthos_patient_id: str = Field(..., description="HealthOS patient ID")
    reason: str = Field(default="", description="Reason for pre-authorization")


class EligibilityResponse(BaseModel):
    """Response: member eligibility from HealthOS."""

    patient_id: str
    eligible: bool | None
    coverage_start: str | None = None
    coverage_end: str | None = None
    plan_name: str | None = None
    error: str | None = None


class PreauthIntentResponse(BaseModel):
    """Response: pre-authorization intent created (PENDING_REVIEW)."""

    ok: bool
    proposal_id: str | None = None
    status: str = "PENDING_REVIEW"
    error: str | None = None


def check_bridge_enabled() -> bool:
    """Check if HealthOS bridge is enabled."""
    settings = get_settings()
    return settings.mulemacare_healthos_bridge_enabled


def check_pilot_tenant(user: TokenUser) -> None:
    """Check if user belongs to pilot tenant."""
    settings = get_settings()
    if user.tenant_id != settings.healthos_pilot_tenant:
        raise HTTPException(
            status_code=403,
            detail=f"HealthOS bridge only available for tenant {settings.healthos_pilot_tenant}",
        )


@router.get("/status")
async def healthos_status(
    _: Annotated[TokenUser, Depends(require_roles("OPS", "ADMIN"))],
) -> dict:
    """Return HealthOS bridge status and configuration."""
    settings = get_settings()
    return {
        "enabled": settings.mulemacare_healthos_bridge_enabled,
        "mode": "read_eligibility_then_preauth_hitl",
        "pilot_tenant": settings.healthos_pilot_tenant,
        "base_url": settings.healthos_base_url or "(not configured)",
        "timeout_ms": settings.healthos_timeout_ms,
        "docs": "docs/HEALTHOS_BRIDGE.md",
    }


@router.post("/eligibility")
async def eligibility(
    request: EligibilityRequest,
    user: Annotated[TokenUser, Depends(require_roles("OPS", "ADMIN"))],
    client: Annotated[HealthOSClient, Depends(get_healthos_client)],
) -> EligibilityResponse:
    """Fetch member eligibility from HealthOS (read-only).

    Pilot tenant only. Requires HealthOS base URL and API key configured.
    Gracefully falls back if HealthOS is unavailable.
    """
    settings = get_settings()

    if not settings.mulemacare_healthos_bridge_enabled:
        raise HTTPException(status_code=503, detail="HealthOS bridge disabled")

    check_pilot_tenant(user)

    if not settings.healthos_base_url or not settings.healthos_partner_api_key:
        raise HTTPException(
            status_code=503,
            detail="HealthOS not configured (HEALTHOS_BASE_URL or API key missing)",
        )

    try:
        result = await client.get_eligibility(request.healthos_patient_id)
        return EligibilityResponse(**result)
    except HealthOSClientError as e:
        raise HTTPException(status_code=503, detail=f"HealthOS error: {e}")


@router.post("/preauth-intent")
async def preauth_intent(
    request: PreauthIntentRequest,
    user: Annotated[TokenUser, Depends(require_roles("OPS", "ADMIN"))],
    client: Annotated[HealthOSClient, Depends(get_healthos_client)],
) -> PreauthIntentResponse:
    """Create a pre-authorization intent on HealthOS (PENDING_REVIEW).

    Pilot tenant only. Decision is made by ActionCenter HITL, never auto-approved.

    The intent is created on HealthOS with status PENDING_REVIEW. An ActionCenter
    proposal is created separately with action_type=preauth for human review.
    """
    settings = get_settings()

    if not settings.mulemacare_healthos_bridge_enabled:
        raise HTTPException(status_code=503, detail="HealthOS bridge disabled")

    check_pilot_tenant(user)

    if not settings.healthos_base_url or not settings.healthos_partner_api_key:
        raise HTTPException(
            status_code=503,
            detail="HealthOS not configured (HEALTHOS_BASE_URL or API key missing)",
        )

    try:
        result = await client.create_preauth_intent(
            cssa_id=request.cssa_id,
            healthos_patient_id=request.healthos_patient_id,
            reason=request.reason,
        )
        return PreauthIntentResponse(**result)
    except HealthOSClientError as e:
        raise HTTPException(status_code=503, detail=f"HealthOS error: {e}")
