"""Agents lecture seule — tools déterministes (pas de LLM inventé)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import TokenUser, require_roles
from app.domain.models import Member
from app.services.plan_catalog import PLAN_CATALOG, quote_amount

router = APIRouter(prefix="/agents", tags=["agents"])


class QuoteAsk(BaseModel):
    plan_id: str = "silver"
    composition: str = "family"
    currency: str = Field(default="EUR", pattern="^(EUR|USD|XAF)$")
    cycle: str = Field(default="annual", pattern="^(annual|monthly)$")


class EligibilityAsk(BaseModel):
    cssa_id: str


class NavigatorAsk(BaseModel):
    country_slug: str = "france"
    question: str = ""


@router.post("/quote-advisor")
async def quote_advisor(
    body: QuoteAsk,
    _: Annotated[TokenUser, Depends(require_roles("MEMBER", "OPS", "ADMIN"))],
) -> dict:
    plan = PLAN_CATALOG.get(body.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="Unknown plan")
    amount = quote_amount(body.plan_id, body.composition, body.currency, body.cycle)
    return {
        "agent": "QuoteAdvisor",
        "mode": "deterministic",
        "plan": {"id": body.plan_id, "name": plan["name"], "ceiling_label": plan["ceiling_label"]},
        "quote": {
            "plan_id": body.plan_id,
            "composition": body.composition,
            "currency": body.currency,
            "cycle": body.cycle,
            "amount": amount,
            "label": f"{amount} {body.currency} / {'an' if body.cycle == 'annual' else 'mois'}",
        },
        "narrative": (
            f"Formule {plan['name']} ({body.composition}) : "
            f"{amount} {body.currency} en cycle {body.cycle}. "
            f"Plafond indicatif : {plan['ceiling_label']}. "
            "Chiffres issus du catalogue Mutuelle — non inventés par un LLM."
        ),
    }


@router.post("/eligibility")
async def eligibility_agent(
    body: EligibilityAsk,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[TokenUser, Depends(require_roles("MEMBER", "OPS", "ADMIN"))],
) -> dict:
    result = await db.execute(select(Member).where(Member.cssa_id == body.cssa_id.upper()))
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in Mutuelle OS")
    active = member.status == "ACTIVE"
    plan = PLAN_CATALOG.get(member.plan_id, PLAN_CATALOG["silver"])
    return {
        "agent": "EligibilityAgent",
        "mode": "deterministic",
        "cssa_id": member.cssa_id,
        "status": member.status,
        "tiers_payant_active": active,
        "plan_id": member.plan_id,
        "plan_name": plan["name"],
        "ceiling_label": plan["ceiling_label"],
        "narrative": (
            f"Carte {member.cssa_id} : statut {member.status}. "
            + ("Tiers-payant ACTIF." if active else "Tiers-payant INACTIF — paiement requis.")
        ),
    }


@router.post("/diaspora-navigator")
async def diaspora_navigator(
    body: NavigatorAsk,
    _: Annotated[TokenUser, Depends(require_roles("MEMBER", "OPS", "ADMIN"))],
) -> dict:
    desk = {
        "france": {"whatsapp": "33659513458", "currency": "EUR", "cta": "/diaspora/france"},
        "belgique": {"whatsapp": "33659513458", "currency": "EUR", "cta": "/diaspora/belgique"},
        "canada": {"whatsapp": "33659513458", "currency": "EUR", "cta": "/diaspora/canada"},
    }
    info = desk.get(body.country_slug.lower(), desk["france"])
    return {
        "agent": "DiasporaCareNavigator",
        "mode": "deterministic",
        "country": body.country_slug,
        "currency_hint": info["currency"],
        "whatsapp_desk": info["whatsapp"],
        "cta_path": info["cta"],
        "narrative": (
            f"Depuis {body.country_slug}, payez en {info['currency']} via Stripe, "
            f"couvrez la famille au pays, desk WhatsApp +{info['whatsapp']}. "
            f"Parcours : {info['cta']} puis /adhesion."
        ),
        "echo_question": body.question[:500],
    }
