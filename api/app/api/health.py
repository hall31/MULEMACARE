"""Health & readiness probes."""

from __future__ import annotations

import os

from fastapi import APIRouter

router = APIRouter(tags=["ops"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "mulemacare-api"}


@router.get("/ready")
def ready() -> dict[str, object]:
    stripe_ready = bool(os.getenv("STRIPE_SECRET_KEY", "").startswith("sk_"))
    return {
        "status": "ready",
        "checks": {
            "stripe_env": stripe_ready,
            "php_site_bridge": True,
        },
    }
