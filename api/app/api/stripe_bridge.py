"""Lecture-only bridge: statut abonnement Stripe / CSSA (Sprint 2 stub)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/billing", tags=["billing"])


class DiasporaCheckoutIntent(BaseModel):
    """Intent renvoyé au site PHP / futurs clients MCare."""

    cssa_id: str = Field(..., min_length=6)
    currency: str = Field(..., pattern="^(EUR|USD)$")
    cycle: str = Field(default="annual", pattern="^(annual|monthly)$")
    amount_major: float = Field(..., gt=0)
    plan_id: str


@router.get("/diaspora/status/{cssa_id}")
def diaspora_status(cssa_id: str) -> dict[str, object]:
    """Stub: le site PHP reste source of truth Sprint 1; OS exposera PG ensuite."""
    if not cssa_id.upper().startswith("CSSA-"):
        raise HTTPException(status_code=400, detail="Invalid CSSA id")
    return {
        "cssa_id": cssa_id.upper(),
        "source": "php_site_pending_sync",
        "hint": "Query PHP /api/adherent/lookup until Mutuelle OS owns members table",
    }


@router.post("/diaspora/checkout-intent")
def checkout_intent(body: DiasporaCheckoutIntent) -> dict[str, object]:
    """Valide le contrat d'intent; création Checkout reste sur PHP Sprint 1."""
    return {
        "ok": True,
        "delegate_to": "POST /api/subscribe on mulemacare.com PHP",
        "intent": body.model_dump(),
    }
