"""Lien de paiement diaspora, checkout public (canaux simulés), cotisations et relances.

Le jeton du lien n'est montré qu'une fois ; seul son hachage est stocké. La page publique ne
montre que le montant et les initiales. Aucun numéro de carte bancaire n'est accepté.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date
from uuid import UUID

import psycopg

from api.members.tests.support import (
    L4Env,
    active_member,
    checkout,
    contribution_of,
    enroll,
    hook,
    issue_month,
    payment_link_token,
    post_webhook,
)

OCTOBER = date(2026, 10, 1)


def _member_with_contribution(env: L4Env) -> tuple[dict[str, object], UUID]:
    env.clock.set_day(OCTOBER)
    member = active_member(env, "a", given="Aminata", family="Kouassi")
    issue_month(env, "a", OCTOBER)
    return member, contribution_of(env, str(member["id"]), OCTOBER)


def test_lien_public_montre_montant_et_initiales_seulement(guarded: L4Env) -> None:
    env = guarded
    _, contribution = _member_with_contribution(env)
    token = payment_link_token(env, "a", contribution)

    stored = env.rows(
        "SELECT token_hash, expires_at, used_at FROM payment_links WHERE contribution_id = %s",
        (contribution,),
    )
    assert len(stored) == 1
    assert stored[0][0] == hashlib.sha256(token.encode()).hexdigest()
    assert token not in str(env.rows("SELECT * FROM payment_links"))
    assert token not in str(env.rows("SELECT response_body FROM idempotency_keys"))

    page = env.client.get(f"/v1/public/payment-links/{token}")
    assert page.status_code == 200, page.text
    assert page.json() == {
        "period_start": "2026-10-01",
        "amount_xof": 27500,
        "currency": "XOF",
        "holder_initials": "A. K.",
        "channels": ["mtn_momo", "orange_money", "wave"],
    }
    assert "Kouassi" not in page.text
    assert "Aminata" not in page.text


def test_creation_de_lien_idempotente_meme_jeton(guarded: L4Env) -> None:
    env = guarded
    _, contribution = _member_with_contribution(env)
    headers = env.headers("a", "gestionnaire", "cle-lien-0000000001")
    one = env.client.post(f"/v1/contributions/{contribution}/payment-links", headers=headers)
    two = env.client.post(f"/v1/contributions/{contribution}/payment-links", headers=headers)
    assert one.status_code == two.status_code == 201
    assert one.json() == two.json()
    assert (
        env.scalar("SELECT count(*) FROM payment_links WHERE contribution_id = %s", (contribution,))
        == 1
    )


def test_lien_inconnu_expire_ou_deja_paye(guarded: L4Env) -> None:
    env = guarded
    _, contribution = _member_with_contribution(env)
    token = payment_link_token(env, "a", contribution)
    unknown = env.client.get(f"/v1/public/payment-links/{'x' * 43}")
    assert unknown.status_code == 404

    payment = checkout(env, token)
    note = env.simulated("wave").notification(payment, occurred_at=env.clock.now())
    post_webhook(env, hook(env.orgs["a"].slug, "wave"), note.body, note.signature)
    # Le lien a servi : il n'ouvre plus rien.
    assert env.client.get(f"/v1/public/payment-links/{token}").status_code in {404, 410}
    again = env.client.post(
        f"/v1/public/payment-links/{token}/checkout",
        json={"channel": "wave"},
        headers={"Idempotency-Key": f"cle-{uuid.uuid4().hex}"},
    )
    assert again.status_code in {404, 410}

    # Lien expiré : l'expiration est comparée à l'heure de la base (fonction du contrat
    # resolve_payment_link), on la recule donc en propriétaire.
    other_contribution = _member_with_contribution(env)[1]
    other = payment_link_token(env, "a", other_contribution)
    with psycopg.connect(env.dsn) as conn:
        conn.execute(
            "UPDATE payment_links SET expires_at = now() - interval '1 second' "
            "WHERE contribution_id = %s",
            (other_contribution,),
        )
    assert env.client.get(f"/v1/public/payment-links/{other}").status_code in {404, 410}


def test_lien_refuse_pour_une_cotisation_deja_payee(guarded: L4Env) -> None:
    env = guarded
    _, contribution = _member_with_contribution(env)
    payment = checkout(env, payment_link_token(env, "a", contribution))
    note = env.simulated("wave").notification(payment, occurred_at=env.clock.now())
    post_webhook(env, hook(env.orgs["a"].slug, "wave"), note.body, note.signature)
    refused = env.client.post(
        f"/v1/contributions/{contribution}/payment-links",
        headers=env.headers("a", "gestionnaire"),
    )
    assert refused.status_code == 409


def test_checkout_idempotent_et_sans_carte_bancaire(guarded: L4Env) -> None:
    env = guarded
    _, contribution = _member_with_contribution(env)
    token = payment_link_token(env, "a", contribution)
    key = {"Idempotency-Key": "cle-checkout-00000001"}
    body = {"channel": "orange_money", "payer_country_code": "BE"}
    one = env.client.post(f"/v1/public/payment-links/{token}/checkout", json=body, headers=key)
    two = env.client.post(f"/v1/public/payment-links/{token}/checkout", json=body, headers=key)
    assert one.status_code == two.status_code == 201
    assert one.json() == two.json()
    assert one.json()["redirect_url"] is None
    assert (
        env.scalar("SELECT count(*) FROM payments WHERE contribution_id = %s", (contribution,)) == 1
    )
    conflict = env.client.post(
        f"/v1/public/payment-links/{token}/checkout",
        json={"channel": "wave", "payer_country_code": "BE"},
        headers=key,
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEM-01"

    card = env.client.post(
        f"/v1/public/payment-links/{token}/checkout",
        json={"channel": "wave", "card_number": "4111111111111111"},
        headers={"Idempotency-Key": f"cle-{uuid.uuid4().hex}"},
    )
    assert card.status_code == 422
    unsupported = env.client.post(
        f"/v1/public/payment-links/{token}/checkout",
        json={"channel": "virement"},
        headers={"Idempotency-Key": f"cle-{uuid.uuid4().hex}"},
    )
    assert unsupported.status_code == 422


def test_cotisations_du_plus_recent_au_plus_ancien(guarded: L4Env) -> None:
    env = guarded
    member, _ = _member_with_contribution(env)
    issue_month(env, "a", date(2026, 11, 1))
    issue_month(env, "a", date(2026, 11, 1))  # rejouable sans doublon
    items = env.client.get(
        f"/v1/members/{member['id']}/contributions", headers=env.auth("a", "gestionnaire")
    ).json()["items"]
    assert [c["period_start"] for c in items] == ["2026-11-01", "2026-10-01"]
    assert all(c["amount_xof"] == 27500 and c["currency"] == "XOF" for c in items)
    assert items[0]["channel"] is None


def test_relance_mise_en_file_avec_lien_de_paiement(guarded: L4Env) -> None:
    env = guarded
    member, contribution = _member_with_contribution(env)
    headers = env.headers("a", "gestionnaire", "cle-relance-00000001")
    body = {
        "channel": "sms",
        "template_code": "relance_cotisation",
        "contribution_id": str(contribution),
    }
    one = env.client.post(f"/v1/members/{member['id']}/reminders", json=body, headers=headers)
    assert one.status_code == 202, one.text
    assert one.json()["status"] == "en_file"
    again = env.client.post(f"/v1/members/{member['id']}/reminders", json=body, headers=headers)
    assert again.json() == one.json()
    rows = env.rows(
        "SELECT channel, template_code, related_type, related_id, status FROM outbound_messages "
        "WHERE id = %s",
        (UUID(one.json()["id"]),),
    )
    assert rows == [("sms", "relance_cotisation", "contribution", contribution, "en_file")]
    assert (
        env.scalar(
            "SELECT count(*) FROM payment_links WHERE contribution_id = %s AND used_at IS NULL",
            (contribution,),
        )
        == 1
    )


def test_relance_sms_sans_telephone_refusee(guarded: L4Env) -> None:
    env = guarded
    member = enroll(env, "a", OCTOBER, phone=None)
    response = env.client.post(
        f"/v1/members/{member['id']}/reminders",
        json={"channel": "sms", "template_code": "relance_cotisation"},
        headers=env.headers("a", "gestionnaire"),
    )
    assert response.status_code == 422


def test_isolation_liens_et_cotisations(guarded: L4Env) -> None:
    env = guarded
    _, contribution = _member_with_contribution(env)
    response = env.client.post(
        f"/v1/contributions/{contribution}/payment-links",
        headers=env.headers("b", "gestionnaire"),
    )
    assert response.status_code == 404
    # Un lien de A s'ouvre bien sur A : l'organisation vient du lien, jamais du client.
    token = payment_link_token(env, "a", contribution)
    payment = checkout(env, token)
    assert env.scalar("SELECT organization_id FROM payments WHERE id = %s", (payment,)) == (
        env.orgs["a"].id
    )
