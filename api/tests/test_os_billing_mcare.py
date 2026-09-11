"""Preuve Mutuelle OS : JWT + members DB PENDING→ACTIVE + MCare."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test_os.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-32chars-min!!")
    monkeypatch.setenv("MCARE_ENABLED", "false")

    # Reset settings cache + recreate engine bindings
    from app.core.config import get_settings
    from app.core import db as dbmod

    get_settings.cache_clear()
    settings = get_settings()
    assert "test_os.db" in settings.database_url

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    dbmod.engine = create_async_engine(settings.database_url, echo=False)
    dbmod.SessionLocal = async_sessionmaker(dbmod.engine, expire_on_commit=False)

    from app.main import app

    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()


def _ops_token(client: TestClient) -> str:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "ops@mulemacare.example", "password": "secret123", "role": "OPS"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_jwt_member_pending_to_active(client: TestClient) -> None:
    token = _ops_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    cssa = "CSSA-JWT26"

    denied = client.post(
        "/api/v1/members",
        json={"cssa_id": cssa, "status": "PENDING_PAYMENT"},
    )
    assert denied.status_code == 401

    r = client.post(
        "/api/v1/members",
        headers=headers,
        json={
            "cssa_id": cssa,
            "plan_id": "silver",
            "currency": "EUR",
            "subscriber_name": "JWT Tester",
            "stripe_checkout_id": "cs_jwt",
            "status": "PENDING_PAYMENT",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["member"]["status"] == "PENDING_PAYMENT"

    act = client.post(
        "/api/v1/members/activate-from-stripe",
        headers=headers,
        json={"cssa_id": cssa, "checkout_session_id": "cs_jwt", "subscription_id": "sub_jwt"},
    )
    assert act.status_code == 200, act.text
    assert act.json()["member"]["status"] == "ACTIVE"
    assert act.json()["member"]["payment_status"] == "paid"

    got = client.get(f"/api/v1/members/{cssa}", headers=headers)
    assert got.json()["member"]["status"] == "ACTIVE"


def test_cssa_rejects_formula_in_card_id(client: TestClient) -> None:
    token = _ops_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    bad = client.post(
        "/api/v1/members",
        headers=headers,
        json={"cssa_id": "CSSA-SILVER-26", "plan_id": "silver", "status": "PENDING_PAYMENT"},
    )
    assert bad.status_code == 400


def test_mcare_flag(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    st = client.get("/api/v1/mcare/status")
    assert st.status_code == 200

    unauth = client.post(
        "/api/v1/mcare/conversations",
        json={"cssa_id": "CSSA-JWT26", "message": "Fièvre"},
    )
    assert unauth.status_code == 401

    token = _ops_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    monkeypatch.setenv("MCARE_ENABLED", "false")
    blocked = client.post(
        "/api/v1/mcare/conversations",
        headers=headers,
        json={"cssa_id": "CSSA-JWT26", "message": "Fièvre"},
    )
    assert blocked.status_code == 503

    monkeypatch.setenv("MCARE_ENABLED", "true")
    client.post(
        "/api/v1/members",
        headers=headers,
        json={"cssa_id": "CSSA-JWT26", "status": "ACTIVE", "plan_id": "silver"},
    )
    prop = client.post(
        "/api/v1/action-center/proposals",
        headers=headers,
        json={
            "agent_name": "ops",
            "action_type": "status_toggle",
            "cssa_id": "CSSA-JWT26",
            "summary": "activate",
            "payload": {"status": "ACTIVE"},
        },
    )
    client.post(
        f"/api/v1/action-center/proposals/{prop.json()['proposal']['id']}/decide",
        headers=headers,
        json={"decision": "approved"},
    )
    ok = client.post(
        "/api/v1/mcare/conversations",
        headers=headers,
        json={
            "cssa_id": "CSSA-JWT26",
            "beneficiary_name": "Maman",
            "message": "Fièvre",
        },
    )
    assert ok.status_code == 200, ok.text
    assert "IA" in ok.json()["tags"]


def test_health(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"
