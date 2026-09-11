"""MulemaCare Mutuelle OS — FastAPI entrypoint."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.action_center import router as action_center_router
from app.api.agents import router as agents_router
from app.api.auth import router as auth_router
from app.api.claims import router as claims_router
from app.api.health import router as health_router
from app.api.healthos import router as healthos_router
from app.api.mcare import router as mcare_router
from app.api.mcare_ai import router as mcare_ai_router
from app.api.members import router as members_router
from app.api.stripe_bridge import router as stripe_bridge_router
from app.core.db import init_db
from app.services.healthos_client import close_healthos_client, get_healthos_client


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    await init_db()
    await get_healthos_client()  # Initialize HealthOS client + Redis
    yield
    # Shutdown
    await close_healthos_client()


app = FastAPI(
    title="MulemaCare Mutuelle OS",
    version="0.3.0",
    description="Agents + HITL + Stripe mirror + MCare. Site PHP = façade acquisition.",
    lifespan=lifespan,
)

allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://127.0.0.1:8080,http://localhost:8080").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(stripe_bridge_router, prefix="/api/v1")
app.include_router(members_router, prefix="/api/v1")
app.include_router(action_center_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(claims_router, prefix="/api/v1")
app.include_router(healthos_router, prefix="/api/v1")
app.include_router(mcare_router, prefix="/api/v1")
app.include_router(mcare_ai_router, prefix="/api/v1")
