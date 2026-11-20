"""Parcours d'API réutilisés par les tests L5 (comptoir, dossier, grand livre)."""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import UUID

import httpx
import psycopg
from fastapi.testclient import TestClient
from psycopg import sql

from api.claims.tests.conftest import ClaimsSeed, MemberRef
from api.claims.tests.support import event_schemas, schema_errors
from api.ledger.consumer import drain_outbox


def as_response(value: object) -> httpx.Response:
    assert isinstance(value, httpx.Response)
    return value


def in_parallel(calls: list[Callable[[], httpx.Response]]) -> list[httpx.Response | Exception]:
    """Lance les appels en même temps (une barrière les libère ensemble).

    Le ``TestClient`` partage une boucle d'événements : les requêtes s'entrelacent réellement
    sur leurs ``await`` (base de données). Une exception serveur est rendue, pas levée.
    """
    barrier = threading.Barrier(len(calls))

    def run(call: Callable[[], httpx.Response]) -> httpx.Response | Exception:
        barrier.wait()
        try:
            return call()
        except Exception as exc:  # l'erreur serveur est un résultat du test
            return exc

    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        return list(pool.map(run, calls))


# 25 000 + 8 000 + 15 000 = 48 000 FCFA (PRD §4 R5, accord automatique).
ITEMS_48000: list[dict[str, Any]] = [
    {"act_code": "CONS-GEN", "quantity": 1},
    {"act_code": "BIO-NFS", "quantity": 1},
    {"act_code": "CARD-ECG", "quantity": 1},
]
# 35 000 + 5 x 30 000 = 185 000 FCFA (PRD §4 R5, revue du médecin-conseil).
ITEMS_185000: list[dict[str, Any]] = [
    {"act_code": "CONS-SPE", "quantity": 1},
    {"act_code": "IMG-ECHO-ABD", "quantity": 5},
]
SERVICE_DATE = "2026-10-01"


def start(
    client: TestClient, seed: ClaimsSeed, member: MemberRef, who: str = "clinique_p1"
) -> httpx.Response:
    return as_response(
        client.post(
            "/v1/counter/identifications",
            json={"qr_payload": member.qr_payload},
            headers=seed.auth(who),
        )
    )


def send_code(
    client: TestClient, seed: ClaimsSeed, identification: str, who: str = "clinique_p1"
) -> httpx.Response:
    return as_response(
        client.post(f"/v1/counter/identifications/{identification}/code", headers=seed.auth(who))
    )


def verify(
    client: TestClient, seed: ClaimsSeed, identification: str, code: str, who: str = "clinique_p1"
) -> httpx.Response:
    return as_response(
        client.post(
            f"/v1/counter/identifications/{identification}/code-verification",
            json={"code": code},
            headers=seed.auth(who),
        )
    )


def confirm_photo(
    client: TestClient,
    seed: ClaimsSeed,
    identification: str,
    *,
    confirmed: bool = True,
    who: str = "clinique_p1",
) -> httpx.Response:
    return as_response(
        client.post(
            f"/v1/counter/identifications/{identification}/photo-confirmation",
            json={"confirmed": confirmed},
            headers=seed.auth(who),
        )
    )


def wrong_code(correct: str) -> str:
    return f"{(int(correct) + 1) % 1_000_000:06d}"


def identify(
    client: TestClient, seed: ClaimsSeed, member: MemberRef, who: str = "clinique_p1"
) -> str:
    """Les trois facteurs au comptoir : QR, photo, code SMS. Renvoie l'identification."""
    response = start(client, seed, member, who)
    assert response.status_code == 201, response.text
    identification = str(response.json()["id"])
    assert confirm_photo(client, seed, identification, who=who).status_code == 200
    assert send_code(client, seed, identification, who).status_code == 202
    code = seed.sms.last_code(member.phone or "")
    verified = verify(client, seed, identification, code, who)
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "verifiee"
    return identification


def create_claim(  # noqa: PLR0913 — demande de prise en charge paramétrable
    client: TestClient,
    seed: ClaimsSeed,
    identification: str,
    items: list[dict[str, Any]],
    *,
    who: str = "clinique_p1",
    key: str | None = None,
    service_date: str = SERVICE_DATE,
    encounter_ref: str | None = None,
) -> httpx.Response:
    body: dict[str, Any] = {
        "identification_id": identification,
        "service_date": service_date,
        "items": items,
    }
    if encounter_ref is not None:
        body["healthos_encounter_ref"] = encounter_ref
    return as_response(
        client.post(
            "/v1/claims",
            json=body,
            headers=seed.auth(who) | {"Idempotency-Key": key or f"cle-{uuid.uuid4().hex}"},
        )
    )


def new_claim(
    client: TestClient,
    seed: ClaimsSeed,
    items: list[dict[str, Any]],
    *,
    who: str = "clinique_p1",
    encounter_ref: str | None = None,
) -> tuple[MemberRef, dict[str, Any]]:
    member = seed.new_member()
    identification = identify(client, seed, member, who)
    response = create_claim(
        client, seed, identification, items, who=who, encounter_ref=encounter_ref
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return member, body


def decide(  # noqa: PLR0913 — décision paramétrable
    client: TestClient,
    seed: ClaimsSeed,
    claim_id: str,
    decision: str,
    *,
    who: str = "medecin_conseil",
    reason_code: str = "MC-01",
    key: str | None = None,
) -> httpx.Response:
    return as_response(
        client.post(
            f"/v1/claims/{claim_id}/decisions",
            json={"decision": decision, "reason_code": reason_code},
            headers=seed.auth(who) | {"Idempotency-Key": key or f"cle-{uuid.uuid4().hex}"},
        )
    )


def outbox(seed: ClaimsSeed, aggregate_id: str | UUID) -> list[tuple[str, dict[str, Any]]]:
    """Événements de la boîte d'envoi d'un agrégat, dans l'ordre, enveloppe validée."""
    with seed.owner() as conn:
        rows = conn.execute(
            "SELECT id, organization_id, event_type, event_version, occurred_at, payload "
            "FROM outbox_events WHERE aggregate_id = %s ORDER BY occurred_at, event_type DESC",
            (str(aggregate_id),),
        ).fetchall()
    schemas = event_schemas()
    out = []
    for event_id, org, event_type, version, occurred_at, payload in rows:
        envelope = {
            "event_id": str(event_id),
            "event_type": event_type,
            "event_version": version,
            "occurred_at": occurred_at.isoformat(),
            "organization_id": str(org),
            "payload": payload,
        }
        errors = schema_errors(json.loads(json.dumps(envelope)), schemas[event_type])
        assert errors == [], errors
        out.append((str(event_type), dict(payload)))
    return out


def drain_ledger(seed: ClaimsSeed) -> None:
    """Fait tourner le consommateur du grand livre (L3) sous le rôle applicatif."""

    async def run() -> None:
        conn = await psycopg.AsyncConnection.connect(seed.dsn, autocommit=True)
        try:
            await conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier("mulema_app")))
            await drain_outbox(conn, seed.orgs["a"])
        finally:
            await conn.close()

    asyncio.run(run())


def ledger_entries_for(seed: ClaimsSeed, claim_id: str) -> int:
    return int(
        seed.scalar(
            "SELECT count(*) FROM ledger_entries WHERE source_type = 'prise_en_charge' "
            "AND source_id = %s",
            (claim_id,),
        )
    )
