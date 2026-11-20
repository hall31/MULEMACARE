"""Journal d'audit immuable : ajout seul, consultation filtrée, métadonnées non identifiantes."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.context import RequestContext
from api.core.database import Database
from api.core.permissions import Principal, Role, RoleGrant
from api.core.repositories import AuditRepository
from api.core.services import AuditIntent, AuditService
from api.core.tests.conftest import APP_ROLE, CoreSeed


def _ctx(seed: CoreSeed, session: AsyncSession) -> RequestContext:
    principal = Principal(
        user_id=seed.users[("a", "gestionnaire")],
        organization_id=seed.orgs["a"],
        grants=(RoleGrant(Role.GESTIONNAIRE),),
    )
    return RequestContext(principal=principal, session=session, request_id="req-audit")


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_events SET action = 'x.y'",
        "DELETE FROM audit_events",
        "TRUNCATE audit_events",
    ],
)
def test_audit_non_modifiable_par_l_api(core_seed: CoreSeed, statement: str) -> None:
    async def scenario() -> None:
        db = Database(core_seed.url, app_role=APP_ROLE)
        try:
            async with db.transaction(core_seed.orgs["a"]) as session:
                await session.execute(text(statement))
        finally:
            await db.dispose()

    with pytest.raises(DBAPIError) as exc:
        asyncio.run(scenario())
    assert getattr(exc.value.orig, "sqlstate", None) in {"42501", "MCL01"}


def test_audit_non_modifiable_meme_par_le_proprietaire(core_seed: CoreSeed) -> None:
    with psycopg.connect(core_seed.dsn) as conn, pytest.raises(psycopg.Error) as exc:
        conn.execute("UPDATE audit_events SET action = 'x.y'")
    assert exc.value.sqlstate == "MCL01"


def test_le_depot_d_audit_n_expose_ni_modification_ni_suppression() -> None:
    public = {name for name in dir(AuditRepository) if not name.startswith("_")}
    assert public == {"append", "list_page"}


def test_enregistrer_un_evenement_en_utc(core_seed: CoreSeed) -> None:
    target = uuid4()

    async def scenario() -> datetime:
        db = Database(core_seed.url, app_role=APP_ROLE)
        try:
            async with db.transaction(core_seed.orgs["a"]) as session:
                event = await AuditService.for_session(session).record(
                    _ctx(core_seed, session),
                    AuditIntent("claim.viewed", "claim", target, {"channel": "console"}),
                )
                return event.occurred_at
        finally:
            await db.dispose()

    occurred = asyncio.run(scenario())
    assert occurred.tzinfo is not None
    assert occurred.utcoffset() == UTC.utcoffset(None)


@pytest.mark.parametrize(
    "metadata",
    [
        {"display_name": "Awa Fictive"},
        {"phone": "+2250700000000"},
        {"email": "a@example.invalid"},
        {"motif": "texte"},
        {"Nom Complet": "x"},
        {"nested": {"given_name": "x"}},
    ],
)
def test_metadonnees_identifiantes_refusees(
    core_seed: CoreSeed, metadata: dict[str, object]
) -> None:
    async def scenario() -> None:
        db = Database(core_seed.url, app_role=APP_ROLE)
        try:
            async with db.transaction(core_seed.orgs["a"]) as session:
                await AuditService.for_session(session).record(
                    _ctx(core_seed, session),
                    AuditIntent("claim.viewed", "claim", uuid4(), metadata),
                )
        finally:
            await db.dispose()

    with pytest.raises(ValueError, match="métadonnée"):
        asyncio.run(scenario())


def test_action_au_format_du_contrat(core_seed: CoreSeed) -> None:
    async def scenario() -> None:
        db = Database(core_seed.url, app_role=APP_ROLE)
        try:
            async with db.transaction(core_seed.orgs["a"]) as session:
                await AuditService.for_session(session).record(
                    _ctx(core_seed, session), AuditIntent("SansPoint", "claim")
                )
        finally:
            await db.dispose()

    with pytest.raises(ValueError, match="action"):
        asyncio.run(scenario())


def test_consulter_le_journal_filtre_par_action_et_cible(
    client: TestClient, core_seed: CoreSeed
) -> None:
    claim = core_seed.claims["a"]
    response = client.get(
        "/v1/audit-events",
        params={"action": "claim.medical_reason.read", "target_id": str(claim)},
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items, "le jeu d'isolation contient une lecture du motif pour A"
    assert all(i["action"] == "claim.medical_reason.read" for i in items)
    assert all(i["target_id"] == str(claim) for i in items)
    assert all(i["occurred_at"].endswith(("Z", "+00:00")) for i in items)
    assert "metadata" not in items[0]


def test_journal_trie_du_plus_recent_et_pagine(client: TestClient, core_seed: CoreSeed) -> None:
    for _ in range(3):
        client.post(
            "/v1/users",
            json={
                "idp_subject": f"sub-{uuid4().hex}",
                "display_name": "A",
                "roles": [{"role": "gestionnaire"}],
            },
            headers=core_seed.auth("a", "admin"),
        )
    first = client.get(
        "/v1/audit-events",
        params={"action": "user.created", "limit": 2},
        headers=core_seed.auth("a", "admin"),
    ).json()
    assert len(first["items"]) == 2
    assert first["items"][0]["occurred_at"] >= first["items"][1]["occurred_at"]
    second = client.get(
        "/v1/audit-events",
        params={"action": "user.created", "limit": 2, "cursor": first["page"]["next_cursor"]},
        headers=core_seed.auth("a", "admin"),
    ).json()
    assert second["items"]
    assert {i["id"] for i in first["items"]}.isdisjoint({i["id"] for i in second["items"]})


def test_journal_filtre_par_periode(client: TestClient, core_seed: CoreSeed) -> None:
    today = datetime.now(UTC).date().isoformat()
    inside = client.get(
        "/v1/audit-events",
        params={"from": today, "to": today},
        headers=core_seed.auth("a", "admin"),
    )
    assert inside.status_code == 200
    assert inside.json()["items"]
    before = client.get(
        "/v1/audit-events", params={"to": "2020-01-01"}, headers=core_seed.auth("a", "admin")
    )
    assert before.json()["items"] == []


def test_journal_reserve_a_l_admin(client: TestClient, core_seed: CoreSeed) -> None:
    for role in ("gestionnaire", "medecin_conseil", "clinique", "employeur"):
        response = client.get("/v1/audit-events", headers=core_seed.auth("a", role))
        assert response.status_code == 403
