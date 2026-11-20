"""R2 + R8 — webhooks de paiement (canaux SIMULÉS, sous garde d'egress).

- un paiement confirmé par webhook ouvre les droits en moins de 60 s (dans la même transaction) ;
- le même webhook rejoué ne crée rien (séquentiel, en parallèle, et entrelacé de façon
  déterministe : la seconde transaction attend le COMMIT de la première) ;
- signature invalide ou absente : 401 PAY-01, rien n'est enregistré ;
- isolation : le slug d'une organisation ne donne accès à aucun paiement d'une autre.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any
from uuid import UUID

from api.members.idempotency import fingerprint
from api.members.tests.support import (
    L4Env,
    assert_payload_conforms,
    checkout,
    events,
    hook,
    payment_link_token,
    post_webhook,
    suspended_member,
)
from api.payments.schemas import PaymentWebhookRequest
from api.payments.webhooks import WebhookService

SLA_SECONDS = 60


def _member_status(env: L4Env, member_id: str) -> str:
    value = env.scalar("SELECT status FROM members WHERE id = %s", (UUID(member_id),))
    assert isinstance(value, str)
    return value


def _prepared_payment(env: L4Env, channel: str = "wave") -> tuple[dict[str, Any], UUID, UUID]:
    member, contribution = suspended_member(env, "a")
    token = payment_link_token(env, "a", contribution)
    payment = checkout(env, token, channel)
    return member, contribution, payment


def test_paiement_confirme_ouvre_les_droits_en_moins_de_60_s(guarded: L4Env) -> None:
    env = guarded
    member, contribution, payment = _prepared_payment(env)
    rights_before = env.client.get(
        f"/v1/members/{member['id']}/entitlements", headers=env.auth("a", "gestionnaire")
    ).json()["rights_open"]
    assert rights_before is False

    note = env.simulated("wave").notification(payment, occurred_at=env.clock.now())
    started = time.monotonic()
    response = post_webhook(env, hook(env.orgs["a"].slug, "wave"), note.body, note.signature)
    assert response.status_code == 200, response.text
    assert response.json() == {"received": True, "duplicate": False}
    rights = env.client.get(
        f"/v1/members/{member['id']}/entitlements", headers=env.auth("a", "gestionnaire")
    ).json()
    elapsed = time.monotonic() - started

    assert rights["rights_open"] is True
    assert rights["status"] == "actif"
    assert elapsed < SLA_SECONDS
    assert _member_status(env, member["id"]) == "actif"
    assert env.rows(
        "SELECT status, paid_at IS NOT NULL FROM contributions WHERE id = %s", (contribution,)
    ) == [("payee", True)]
    assert env.rows(
        "SELECT status, payer_kind, payer_country_code FROM payments WHERE id = %s", (payment,)
    ) == [("confirme", "proche", "FR")]
    assert (
        env.scalar(
            "SELECT count(*) FROM payment_links WHERE contribution_id = %s AND used_at IS NULL",
            (contribution,),
        )
        == 0
    )

    received = events(env, "contribution.received", contribution_id=str(contribution))
    assert len(received) == 1
    payload = received[0]["payload"]
    assert payload["payment_id"] == str(payment)
    assert payload["amount_xof"] == 27500
    assert payload["channel"] == "wave"
    assert payload["member_id"] == member["id"]
    assert_payload_conforms("contribution.received", payload)
    reopened = events(env, "member.status_changed", member_id=member["id"])[-1]["payload"]
    assert reopened["from_status"] == "suspendu"
    assert reopened["to_status"] == "actif"
    assert reopened["reason_code"] == "paiement_confirme"
    assert reopened["rule"] == {"code": "R-01", "version": 1}
    assert_payload_conforms("member.status_changed", reopened)

    listing = env.client.get(
        f"/v1/members/{member['id']}/contributions", headers=env.auth("a", "gestionnaire")
    ).json()["items"]
    paid = next(c for c in listing if c["id"] == str(contribution))
    assert paid["status"] == "payee"
    assert paid["channel"] == "wave"


def test_meme_webhook_rejoue_ne_cree_aucun_doublon(guarded: L4Env) -> None:
    env = guarded
    member, contribution, payment = _prepared_payment(env, "orange_money")
    note = env.simulated("orange_money").notification(payment, occurred_at=env.clock.now())
    slug = env.orgs["a"].slug
    first = post_webhook(env, hook(slug, "orange_money"), note.body, note.signature)
    second = post_webhook(env, hook(slug, "orange_money"), note.body, note.signature)
    assert first.json() == {"received": True, "duplicate": False}
    assert second.status_code == 200
    assert second.json() == {"received": True, "duplicate": True}

    assert len(events(env, "contribution.received", contribution_id=str(contribution))) == 1
    reopenings = [
        e
        for e in events(env, "member.status_changed", member_id=member["id"])
        if e["payload"]["reason_code"] == "paiement_confirme"
    ]
    assert len(reopenings) == 1
    assert (
        env.scalar(
            "SELECT count(*) FROM member_status_history WHERE member_id = %s "
            "AND reason_code = 'paiement_confirme'",
            (UUID(member["id"]),),
        )
        == 1
    )
    assert (
        env.scalar(
            "SELECT count(*) FROM idempotency_keys "
            "WHERE scope = 'webhook:orange_money' AND key = %s",
            (note.event_id,),
        )
        == 1
    )


def test_nouvelle_notification_pour_un_paiement_deja_confirme_sans_effet(guarded: L4Env) -> None:
    """Deuxième barrière : un canal qui renvoie le paiement sous un autre event_id."""
    env = guarded
    _, contribution, payment = _prepared_payment(env)
    channel = env.simulated("wave")
    slug = env.orgs["a"].slug
    one = channel.notification(payment, occurred_at=env.clock.now())
    two = channel.notification(payment, occurred_at=env.clock.now())
    assert one.event_id != two.event_id
    assert (
        post_webhook(env, hook(slug, "wave"), one.body, one.signature).json()["duplicate"] is False
    )
    again = post_webhook(env, hook(slug, "wave"), two.body, two.signature)
    assert again.status_code == 200
    assert again.json() == {"received": True, "duplicate": True}
    assert len(events(env, "contribution.received", contribution_id=str(contribution))) == 1


def test_webhooks_identiques_en_parallele_un_seul_effet(guarded: L4Env) -> None:
    env = guarded
    member, contribution, payment = _prepared_payment(env, "mtn_momo")
    note = env.simulated("mtn_momo").notification(payment, occurred_at=env.clock.now())
    slug = env.orgs["a"].slug
    parallel = 8
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        responses = list(
            pool.map(
                lambda _: post_webhook(env, hook(slug, "mtn_momo"), note.body, note.signature),
                range(parallel),
            )
        )
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    flags = sorted(r.json()["duplicate"] for r in responses)
    assert flags == [False] + [True] * (parallel - 1)
    assert len(events(env, "contribution.received", contribution_id=str(contribution))) == 1
    assert (
        env.scalar(
            "SELECT count(*) FROM member_status_history WHERE member_id = %s "
            "AND reason_code = 'paiement_confirme'",
            (UUID(member["id"]),),
        )
        == 1
    )
    assert _member_status(env, member["id"]) == "actif"


def test_entrelacement_deterministe_la_seconde_transaction_attend(guarded: L4Env) -> None:
    """T1 traite sans valider ; T2 (même notification) reste bloquée ; T1 valide ; T2 = doublon."""
    env = guarded
    member, contribution, payment = _prepared_payment(env)
    note = env.simulated("wave").notification(payment, occurred_at=env.clock.now())
    notification = PaymentWebhookRequest.model_validate_json(note.body)
    request_hash = fingerprint(notification.model_dump(mode="json"))
    service: WebhookService = env.client.app.state.l4_webhooks  # type: ignore[attr-defined]
    slug = env.orgs["a"].slug

    async def scenario() -> tuple[bool, bool, bool]:
        async with env.database.transaction(None) as first:
            ack_one = await service.apply(first, slug, "wave", notification, request_hash)

            async def second_attempt() -> bool:
                async with env.database.transaction(None) as second:
                    ack = await service.apply(second, slug, "wave", notification, request_hash)
                    return ack.duplicate

            pending = asyncio.create_task(second_attempt())
            await asyncio.sleep(0.5)
            blocked = not pending.done()
        # T1 validée à la sortie du bloc : T2 se débloque et lit la réponse enregistrée.
        dup_two = await asyncio.wait_for(pending, timeout=10)
        return ack_one.duplicate, blocked, dup_two

    dup_one, blocked, dup_two = env.run(scenario)
    assert dup_one is False
    assert blocked is True
    assert dup_two is True
    assert len(events(env, "contribution.received", contribution_id=str(contribution))) == 1
    assert _member_status(env, member["id"]) == "actif"


def test_signature_invalide_refusee_sans_effet(guarded: L4Env) -> None:
    env = guarded
    member, contribution, payment = _prepared_payment(env)
    channel = env.simulated("wave")
    note = channel.notification(payment, occurred_at=env.clock.now())
    slug = env.orgs["a"].slug

    forged = "0" * 64
    other_channel = env.simulated("orange_money").sign(note.body)
    tampered_body = note.body.replace(b"27500", b"2750")
    for body, signature in (
        (note.body, forged),
        (note.body, None),
        (note.body, other_channel),
        (tampered_body, note.signature),
    ):
        response = post_webhook(env, hook(slug, "wave"), body, signature)
        assert response.status_code == 401, response.text
        assert response.json()["code"] == "PAY-01"
        assert response.headers["content-type"].startswith("application/problem+json")

    assert env.scalar("SELECT status FROM payments WHERE id = %s", (payment,)) == "en_attente"
    assert env.scalar("SELECT status FROM contributions WHERE id = %s", (contribution,)) != "payee"
    assert _member_status(env, member["id"]) == "suspendu"
    assert events(env, "contribution.received", contribution_id=str(contribution)) == []
    assert env.scalar("SELECT count(*) FROM idempotency_keys WHERE key = %s", (note.event_id,)) == 0

    # La vraie notification passe ensuite normalement.
    ok = post_webhook(env, hook(slug, "wave"), note.body, note.signature)
    assert ok.json() == {"received": True, "duplicate": False}


def test_montant_different_refuse(guarded: L4Env) -> None:
    env = guarded
    _, contribution, payment = _prepared_payment(env)
    note = env.simulated("wave").notification(payment, occurred_at=env.clock.now(), amount_xof=1000)
    response = post_webhook(env, hook(env.orgs["a"].slug, "wave"), note.body, note.signature)
    assert response.status_code == 409
    assert response.json()["code"] == "PAY-02"
    assert env.scalar("SELECT status FROM payments WHERE id = %s", (payment,)) == "en_attente"
    assert events(env, "contribution.received", contribution_id=str(contribution)) == []


def test_paiement_echoue_sans_ouverture_de_droits(guarded: L4Env) -> None:
    env = guarded
    member, contribution, payment = _prepared_payment(env)
    note = env.simulated("wave").notification(payment, occurred_at=env.clock.now(), status="echoue")
    response = post_webhook(env, hook(env.orgs["a"].slug, "wave"), note.body, note.signature)
    assert response.json() == {"received": True, "duplicate": False}
    assert env.scalar("SELECT status FROM payments WHERE id = %s", (payment,)) == "echoue"
    assert _member_status(env, member["id"]) == "suspendu"
    assert events(env, "contribution.received", contribution_id=str(contribution)) == []


def test_isolation_le_slug_de_b_ne_confirme_pas_un_paiement_de_a(guarded: L4Env) -> None:
    env = guarded
    member, contribution, payment = _prepared_payment(env)
    note = env.simulated("wave").notification(payment, occurred_at=env.clock.now())
    response = post_webhook(env, hook(env.orgs["b"].slug, "wave"), note.body, note.signature)
    assert response.status_code == 404
    assert response.json()["code"] == "NOT-01"
    assert env.scalar("SELECT status FROM payments WHERE id = %s", (payment,)) == "en_attente"
    assert _member_status(env, member["id"]) == "suspendu"
    assert events(env, "contribution.received", contribution_id=str(contribution)) == []


def test_organisation_ou_canal_inconnus(guarded: L4Env) -> None:
    env = guarded
    _, _, payment = _prepared_payment(env)
    note = env.simulated("wave").notification(payment, occurred_at=env.clock.now())
    unknown = post_webhook(
        env, hook(f"inconnue-{uuid.uuid4().hex[:6]}", "wave"), note.body, note.signature
    )
    assert unknown.status_code == 404
    not_simulated = post_webhook(
        env, hook(env.orgs["a"].slug, "virement"), note.body, note.signature
    )
    assert not_simulated.status_code == 404
    bad_channel = post_webhook(env, hook(env.orgs["a"].slug, "carte"), note.body, note.signature)
    assert bad_channel.status_code == 422


def test_corps_invalide_signe(guarded: L4Env) -> None:
    env = guarded
    channel = env.simulated("wave")
    body = b'{"event_id": "evt-court", "card_number": "4111111111111111"}'
    response = post_webhook(env, hook(env.orgs["a"].slug, "wave"), body, channel.sign(body))
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-01"


def test_la_journee_de_paiement_reste_a_la_bonne_date(guarded: L4Env) -> None:
    """La date de paiement enregistrée est celle de l'horloge du serveur (UTC)."""
    env = guarded
    _, contribution, payment = _prepared_payment(env)
    note = env.simulated("wave").notification(payment, occurred_at=env.clock.now())
    post_webhook(env, hook(env.orgs["a"].slug, "wave"), note.body, note.signature)
    paid_at = env.scalar("SELECT paid_at FROM contributions WHERE id = %s", (contribution,))
    assert paid_at.date() == date(2026, 11, 15)
