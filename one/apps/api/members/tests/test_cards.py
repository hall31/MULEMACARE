"""R2 — cartes à QR dynamique : émission, réémission (révocation), code qui change, secret chiffré.

Le QR encode (carte, fenêtre de 30 s, code HMAC du secret de la carte). Le secret n'est jamais
stocké en clair ni renvoyé par l'API ; ``verify_qr_payload`` est le point d'entrée de L5.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from api.members.cards import CardKeys, current_qr_payload, verify_qr_payload
from api.members.routes import MembersRuntime
from api.members.tests.support import L4Env, enroll


def _issue(
    env: L4Env, member: dict[str, Any], person_id: str, key: str | None = None
) -> dict[str, Any]:
    response = env.client.post(
        f"/v1/members/{member['id']}/cards",
        json={"person_id": person_id},
        headers=env.headers("a", "gestionnaire", key),
    )
    assert response.status_code == 201, response.text
    card: dict[str, Any] = response.json()
    return card


def _keys(env: L4Env) -> CardKeys:
    runtime: MembersRuntime = env.client.app.state.l4_members  # type: ignore[attr-defined]
    return runtime.card_keys


def _qr(env: L4Env, org: str, card_id: str) -> str:
    async def run() -> str:
        async with env.database.transaction(env.orgs[org].id) as session:
            return await current_qr_payload(
                session, _keys(env), env.orgs[org].id, UUID(card_id), env.clock.now()
            )

    return env.run(run)


def _verify(env: L4Env, org: str, payload: str) -> UUID | None:
    async def run() -> UUID | None:
        async with env.database.transaction(env.orgs[org].id) as session:
            return await verify_qr_payload(
                session, _keys(env), env.orgs[org].id, payload, env.clock.now()
            )

    return env.run(run)


def test_carte_emise_puis_reemise_revoque_l_ancienne(guarded: L4Env) -> None:
    env = guarded
    member = enroll(env, "a", date(2026, 10, 1))
    holder = member["holder"]["person_id"]
    first = _issue(env, member, holder)
    assert first["status"] == "active"
    assert first["revoked_card_id"] is None
    assert "qr" not in " ".join(first)  # aucun secret ni QR dans la réponse

    second = _issue(env, member, holder)
    assert second["revoked_card_id"] == first["id"]
    states = dict(env.rows("SELECT id, status FROM cards WHERE person_id = %s", (UUID(holder),)))
    assert states == {UUID(first["id"]): "revoquee", UUID(second["id"]): "active"}


def test_emission_idempotente(guarded: L4Env) -> None:
    env = guarded
    member = enroll(env, "a", date(2026, 10, 1))
    holder = member["holder"]["person_id"]
    one = _issue(env, member, holder, key="cle-carte-unique-0001")
    two = _issue(env, member, holder, key="cle-carte-unique-0001")
    assert one == two
    assert env.scalar("SELECT count(*) FROM cards WHERE person_id = %s", (UUID(holder),)) == 1


def test_carte_d_un_ayant_droit_et_refus_d_une_personne_etrangere(guarded: L4Env) -> None:
    env = guarded
    member = enroll(env, "a", date(2026, 10, 1))
    dependent = env.client.post(
        f"/v1/members/{member['id']}/dependents",
        json={
            "person": {"given_name": "Fatou", "family_name": "Koné", "birth_date": "2018-01-01"},
            "relationship": "enfant",
            "valid_from": "2026-10-01",
        },
        headers=env.auth("a", "gestionnaire"),
    ).json()
    card = _issue(env, member, dependent["person_id"])
    assert card["person_id"] == dependent["person_id"]

    stranger = enroll(env, "a", date(2026, 10, 1))
    refused = env.client.post(
        f"/v1/members/{member['id']}/cards",
        json={"person_id": stranger["holder"]["person_id"]},
        headers=env.headers("a", "gestionnaire"),
    )
    assert refused.status_code == 404


def test_qr_dynamique_change_et_expire(guarded: L4Env) -> None:
    env = guarded
    member = enroll(env, "a", date(2026, 10, 1))
    card = _issue(env, member, member["holder"]["person_id"])

    payload = _qr(env, "a", card["id"])
    assert len(payload) >= 16
    assert _verify(env, "a", payload) == UUID(card["id"])

    env.clock.advance(timedelta(seconds=90))
    later = _qr(env, "a", card["id"])
    assert later != payload
    assert _verify(env, "a", payload) is None  # ancien code : expiré
    assert _verify(env, "a", later) == UUID(card["id"])

    tampered = later[:-1] + ("0" if later[-1] != "0" else "1")
    assert _verify(env, "a", tampered) is None
    assert _verify(env, "a", "n'importe quoi de long") is None
    # Isolation : une autre organisation ne reconnaît pas la carte.
    assert _verify(env, "b", later) is None

    # Carte révoquée par une réémission : son QR n'est plus reconnu.
    _issue(env, member, member["holder"]["person_id"])
    assert _verify(env, "a", later) is None


def test_secret_du_qr_stocke_chiffre(guarded: L4Env) -> None:
    env = guarded
    member = enroll(env, "a", date(2026, 10, 1))
    card = _issue(env, member, member["holder"]["person_id"])
    blobs = [
        bytes(row[0])
        for row in env.rows(
            "SELECT qr_secret_ciphertext FROM cards WHERE id = %s", (UUID(card["id"]),)
        )
    ]
    assert len(blobs) == 1
    other = _issue(env, member, member["holder"]["person_id"])
    other_blob = bytes(
        env.scalar("SELECT qr_secret_ciphertext FROM cards WHERE id = %s", (UUID(other["id"]),))
    )
    assert blobs[0] != other_blob
    assert len(blobs[0]) > 32  # nonce + chiffré + étiquette d'intégrité
