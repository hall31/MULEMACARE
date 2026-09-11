"""Sprint suite: HITL, agents, claims, MCare, HealthOS flag."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "sprint_os.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("JWT_SECRET", "sprint-jwt-secret-key-32chars-min!!")
    monkeypatch.setenv("MCARE_ENABLED", "true")
    monkeypatch.setenv("MULEMACARE_HEALTHOS_BRIDGE_ENABLED", "false")

    from app.core.config import get_settings
    from app.core import db as dbmod

    get_settings.cache_clear()
    settings = get_settings()

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    dbmod.engine = create_async_engine(settings.database_url, echo=False)
    dbmod.SessionLocal = async_sessionmaker(dbmod.engine, expire_on_commit=False)

    from app.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def _token(client: TestClient, email: str = "ops@mulemacare.example") -> str:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secret12345", "role": "OPS"},
    )
    if r.status_code == 409:
        r = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "secret12345"},
        )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_hitl_proposal_decide(client: TestClient) -> None:
    token = _token(client)
    h = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/v1/action-center/proposals",
        headers=h,
        json={
            "agent_name": "ClaimsTriageAgent",
            "action_type": "claim_approve",
            "cssa_id": "CSSA-HITL1",
            "summary": "Test claim",
            "payload": {"amount": 10000},
            "evidence": {"reco": "approve"},
        },
    )
    assert created.status_code == 200, created.text
    pid = created.json()["proposal"]["id"]
    assert created.json()["proposal"]["status"] == "pending"

    decided = client.post(
        f"/api/v1/action-center/proposals/{pid}/decide",
        headers=h,
        json={"decision": "approved", "note": "ok"},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["proposal"]["status"] in {"approved", "executed"}


def test_agents_quote_and_navigator(client: TestClient) -> None:
    token = _token(client, "agent@mulemacare.example")
    h = {"Authorization": f"Bearer {token}"}
    q = client.post(
        "/api/v1/agents/quote-advisor",
        headers=h,
        json={"plan_id": "silver", "composition": "family", "currency": "EUR", "cycle": "annual"},
    )
    assert q.status_code == 200, q.text
    assert q.json()["mode"] == "deterministic"
    assert q.json()["quote"]["amount"] > 0

    n = client.post(
        "/api/v1/agents/diaspora-navigator",
        headers=h,
        json={"country_slug": "france", "question": "Comment payer ?"},
    )
    assert n.status_code == 200
    assert "Stripe" in n.json()["narrative"]


def test_claims_triage_creates_pending_proposal(client: TestClient) -> None:
    token = _token(client, "claims@mulemacare.example")
    h = {"Authorization": f"Bearer {token}"}
    client.post(
        "/api/v1/members",
        headers=h,
        json={"cssa_id": "CSSA-CLM1", "status": "ACTIVE", "plan_id": "silver"},
    )
    client.post(
        "/api/v1/members/activate-from-stripe",
        headers=h,
        json={"cssa_id": "CSSA-CLM1"},
    )
    # ensure ACTIVE
    client.post(
        "/api/v1/members",
        headers=h,
        json={"cssa_id": "CSSA-CLM1", "status": "ACTIVE", "plan_id": "silver"},
    )
    from sqlalchemy import select
    # force active via proposal status_toggle
    prop = client.post(
        "/api/v1/action-center/proposals",
        headers=h,
        json={
            "agent_name": "ops",
            "action_type": "status_toggle",
            "cssa_id": "CSSA-CLM1",
            "summary": "force active",
            "payload": {"status": "ACTIVE"},
        },
    )
    pid = prop.json()["proposal"]["id"]
    client.post(
        f"/api/v1/action-center/proposals/{pid}/decide",
        headers=h,
        json={"decision": "approved"},
    )

    triage = client.post(
        "/api/v1/claims/triage",
        headers=h,
        json={
            "cssa_id": "CSSA-CLM1",
            "clinic_name": "Mermoz",
            "act_type": "consultation",
            "amount_invoiced": 25000,
        },
    )
    assert triage.status_code == 200, triage.text
    assert triage.json()["auto_approved"] is False
    assert triage.json()["status"] == "pending"


def test_mcare_tools_and_transmit(client: TestClient) -> None:
    token = _token(client, "mcare@mulemacare.example")
    h = {"Authorization": f"Bearer {token}"}
    client.post(
        "/api/v1/members",
        headers=h,
        json={"cssa_id": "CSSA-MC1", "status": "ACTIVE", "plan_id": "silver"},
    )
    prop = client.post(
        "/api/v1/action-center/proposals",
        headers=h,
        json={
            "agent_name": "ops",
            "action_type": "status_toggle",
            "cssa_id": "CSSA-MC1",
            "summary": "activate",
            "payload": {"status": "ACTIVE"},
        },
    )
    client.post(
        f"/api/v1/action-center/proposals/{prop.json()['proposal']['id']}/decide",
        headers=h,
        json={"decision": "approved"},
    )

    chat = client.post(
        "/api/v1/mcare/conversations",
        headers=h,
        json={
            "cssa_id": "CSSA-MC1",
            "beneficiary_name": "Maman",
            "message": "Fièvre depuis 2 jours",
        },
    )
    assert chat.status_code == 200, chat.text
    assert "IA" in chat.json()["tags"]
    cid = chat.json()["conversation_id"]

    tx = client.post(
        "/api/v1/mcare/conversations/transmit",
        headers=h,
        json={"conversation_id": cid},
    )
    assert tx.status_code == 200, tx.text
    assert tx.json()["proposal_id"]


def test_healthos_off_by_default(client: TestClient) -> None:
    token = _token(client, "hos@mulemacare.example")
    h = {"Authorization": f"Bearer {token}"}
    st = client.get("/api/v1/healthos/status", headers=h)
    assert st.status_code == 200
    assert st.json()["enabled"] is False
    el = client.post(
        "/api/v1/healthos/eligibility",
        headers=h,
        json={"cssa_id": "CSSA-TEST", "healthos_patient_id": "pat_1"},
    )
    assert el.status_code == 503
