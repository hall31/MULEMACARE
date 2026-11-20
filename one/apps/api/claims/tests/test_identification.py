"""R1 — identification en trois facteurs au comptoir (QR, photo, code SMS).

Critère : trois codes faux bloquent la carte 15 minutes (règle ID-03 en données, v1 du jeu de
démonstration : 3 codes, 15 min). Le fournisseur SMS est simulé.
"""

from __future__ import annotations

from datetime import timedelta
from functools import partial

import httpx
from fastapi.testclient import TestClient

from api.claims.tests.conftest import ClaimsSeed
from api.claims.tests.flows import (
    ITEMS_48000,
    confirm_photo,
    create_claim,
    identify,
    in_parallel,
    send_code,
    start,
    verify,
    wrong_code,
)
from api.claims.tests.support import T0


def _ready_for_code(client: TestClient, seed: ClaimsSeed) -> tuple[str, str, str]:
    """Identification ouverte, photo confirmée, code envoyé : (identification, code, carte)."""
    member = seed.new_member()
    response = start(client, seed, member)
    assert response.status_code == 201, response.text
    identification = response.json()["id"]
    assert confirm_photo(client, seed, identification).status_code == 200
    assert send_code(client, seed, identification).status_code == 202
    return identification, seed.sms.last_code(member.phone or ""), str(member.card_id)


def test_trois_facteurs_verifient_l_identite(client: TestClient, seed: ClaimsSeed) -> None:
    member = seed.new_member()

    started = start(client, seed, member)
    assert started.status_code == 201, started.text
    body = started.json()
    assert body["status"] == "ouverte"
    assert body["qr_verified"] is True
    assert body["photo_confirmed"] is None
    assert body["code_verified"] is False
    assert body["beneficiary"]["member_number"] == member.member_number
    assert body["beneficiary"]["person_id"] == str(member.person_id)
    assert body["beneficiary"]["plan_code"] == "FAMILLE-OR"
    assert body["beneficiary"]["coverage_rate_bp"] == 8000
    assert body["beneficiary"]["member_status"] == "actif"
    identification = body["id"]

    photo = confirm_photo(client, seed, identification)
    assert photo.status_code == 200
    assert photo.json()["photo_confirmed"] is True

    sent = send_code(client, seed, identification)
    assert sent.status_code == 202, sent.text
    assert sent.json()["sent_at"].startswith("2026-10-01T09:00:00")
    code = seed.sms.last_code(member.phone or "")
    assert len(code) == 6
    assert code.isdigit()

    verified = verify(client, seed, identification, code)
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "verifiee"
    assert verified.json()["code_verified"] is True

    # Le code n'est jamais stocké en clair : ni dans l'identification, ni dans le message.
    with seed.owner() as conn:
        row = conn.execute(
            "SELECT code_hash, status FROM identity_checks WHERE id = %s", (identification,)
        ).fetchone()
        messages = conn.execute(
            "SELECT template_code, related_type, status FROM outbound_messages "
            "WHERE related_id = %s",
            (identification,),
        ).fetchall()
    assert row is not None
    assert row[1] == "verifiee"
    assert row[0] is None or code not in row[0]
    assert messages == [("code_identification", "identity_check", "envoye")]


def test_trois_codes_faux_bloquent_la_carte_15_minutes(
    client: TestClient, seed: ClaimsSeed
) -> None:
    identification, code, card = _ready_for_code(client, seed)

    first = verify(client, seed, identification, wrong_code(code))
    assert first.status_code == 422
    assert first.json()["code"] == "ID-03"
    assert first.json()["remaining_attempts"] == 2
    second = verify(client, seed, identification, wrong_code(code))
    assert second.json()["remaining_attempts"] == 1

    third = verify(client, seed, identification, wrong_code(code))
    assert third.status_code == 423, third.text
    assert third.json()["code"] == "ID-04"
    assert third.json()["retry_after_seconds"] == 900
    assert third.headers["content-type"].startswith("application/problem+json")

    # Le blocage est écrit en base malgré la réponse d'erreur (la transaction est validée).
    blocked_until = seed.scalar("SELECT blocked_until FROM cards WHERE id = %s", (card,))
    assert blocked_until == T0 + timedelta(minutes=15)

    # Pendant le blocage : le bon code ne passe pas, aucune nouvelle identification.
    late = verify(client, seed, identification, code)
    assert late.status_code == 423
    assert late.json()["code"] == "ID-04"
    member_qr = next(qr for qr, c in seed.qr.cards.items() if str(c) == card)
    seed.clock.advance(timedelta(minutes=14, seconds=59))
    retry = client.post(
        "/v1/counter/identifications",
        json={"qr_payload": member_qr},
        headers=seed.auth("clinique_p1"),
    )
    assert retry.status_code == 423
    assert retry.json()["retry_after_seconds"] == 1

    # Après 15 minutes : la carte est de nouveau utilisable.
    seed.clock.advance(timedelta(seconds=1))
    again = client.post(
        "/v1/counter/identifications",
        json={"qr_payload": member_qr},
        headers=seed.auth("clinique_p1"),
    )
    assert again.status_code == 201, again.text


def test_les_codes_faux_se_cumulent_sur_la_carte(client: TestClient, seed: ClaimsSeed) -> None:
    """Rouvrir une identification ne remet pas le compteur à zéro (blocage par carte)."""
    member = seed.new_member()
    for attempt in range(3):
        opened = start(client, seed, member)
        assert opened.status_code == 201
        identification = opened.json()["id"]
        confirm_photo(client, seed, identification)
        send_code(client, seed, identification)
        response = verify(
            client, seed, identification, wrong_code(seed.sms.last_code(member.phone or ""))
        )
        assert response.status_code == (423 if attempt == 2 else 422)
    assert start(client, seed, member).status_code == 423


def test_un_code_juste_remet_le_compteur_a_zero(client: TestClient, seed: ClaimsSeed) -> None:
    identification, code, card = _ready_for_code(client, seed)
    verify(client, seed, identification, wrong_code(code))
    verify(client, seed, identification, wrong_code(code))
    assert verify(client, seed, identification, code).status_code == 200
    assert seed.scalar("SELECT failed_code_count FROM cards WHERE id = %s", (card,)) == 0


def test_code_expire(client: TestClient, seed: ClaimsSeed) -> None:
    identification, code, _ = _ready_for_code(client, seed)
    seed.clock.advance(timedelta(minutes=10, seconds=1))
    response = verify(client, seed, identification, code)
    assert response.status_code == 410
    assert response.json()["code"] == "ID-05"


def test_photo_refusee_arrete_l_identification(client: TestClient, seed: ClaimsSeed) -> None:
    member = seed.new_member()
    identification = start(client, seed, member).json()["id"]
    refused = confirm_photo(client, seed, identification, confirmed=False)
    assert refused.status_code == 200
    assert refused.json()["status"] == "identite_refusee"
    assert refused.json()["photo_confirmed"] is False
    assert send_code(client, seed, identification).status_code == 409


def test_code_avant_photo_refuse(client: TestClient, seed: ClaimsSeed) -> None:
    member = seed.new_member()
    identification = start(client, seed, member).json()["id"]
    response = send_code(client, seed, identification)
    assert response.status_code == 409
    assert response.json()["code"] == "ID-07"


def test_saisie_manuelle_sans_qr_ne_vaut_pas_trois_facteurs(
    client: TestClient, seed: ClaimsSeed
) -> None:
    member = seed.new_member()
    opened = client.post(
        "/v1/counter/identifications",
        json={"member_number": member.member_number},
        headers=seed.auth("clinique_p1"),
    )
    assert opened.status_code == 201, opened.text
    assert opened.json()["qr_verified"] is False
    identification = opened.json()["id"]
    confirm_photo(client, seed, identification)
    send_code(client, seed, identification)
    verified = verify(client, seed, identification, seed.sms.last_code(member.phone or ""))
    assert verified.status_code == 200
    assert verified.json()["code_verified"] is True
    assert verified.json()["status"] == "ouverte"

    claim = create_claim(client, seed, identification, ITEMS_48000)
    assert claim.status_code == 422
    assert claim.json()["code"] == "ID-07"


def test_carte_inconnue_ou_revoquee(client: TestClient, seed: ClaimsSeed) -> None:
    unknown = client.post(
        "/v1/counter/identifications",
        json={"qr_payload": "QR-TEST-inconnu-000000"},
        headers=seed.auth("clinique_p1"),
    )
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "ID-06"
    revoked = seed.new_member(card_status="revoquee")
    assert start(client, seed, revoked).json()["code"] == "ID-06"


def test_sans_telephone_pas_de_code(client: TestClient, seed: ClaimsSeed) -> None:
    member = seed.new_member(no_phone=True)
    identification = start(client, seed, member).json()["id"]
    confirm_photo(client, seed, identification)
    response = send_code(client, seed, identification)
    assert response.status_code == 409
    assert response.json()["code"] == "ID-07"


def test_identification_d_une_autre_clinique_introuvable(
    client: TestClient, seed: ClaimsSeed
) -> None:
    member = seed.new_member()
    identification = start(client, seed, member).json()["id"]
    other = confirm_photo(client, seed, identification, who="clinique_p2")
    assert other.status_code == 404
    assert other.json()["code"] == "NOT-01"


def test_seule_la_clinique_identifie(client: TestClient, seed: ClaimsSeed) -> None:
    member = seed.new_member()
    for who in ("gestionnaire", "medecin_conseil", "admin"):
        response = start(client, seed, member, who)
        assert response.status_code == 403
        assert response.json()["code"] == "AUTH-02"


def test_identification_complete_puis_dossier(client: TestClient, seed: ClaimsSeed) -> None:
    member = seed.new_member()
    identification = identify(client, seed, member)
    assert create_claim(client, seed, identification, ITEMS_48000).status_code == 201


def _codes_pending_on_one_card(
    client: TestClient, seed: ClaimsSeed, count: int
) -> tuple[str, list[tuple[str, str]]]:
    """``count`` identifications ouvertes sur la MÊME carte, code envoyé : (carte, [(id, faux)])."""
    member = seed.new_member()
    pending = []
    for _ in range(count):
        opened = start(client, seed, member)
        assert opened.status_code == 201, opened.text
        identification = opened.json()["id"]
        assert confirm_photo(client, seed, identification).status_code == 200
        assert send_code(client, seed, identification).status_code == 202
        pending.append((identification, wrong_code(seed.sms.last_code(member.phone or ""))))
    return str(member.card_id), pending


def _verify_in_parallel(
    client: TestClient, seed: ClaimsSeed, pending: list[tuple[str, str]]
) -> list[int]:
    responses = in_parallel([partial(verify, client, seed, ident, code) for ident, code in pending])
    statuses = []
    for response in responses:
        assert isinstance(response, httpx.Response), repr(response)
        statuses.append(response.status_code)
    return sorted(statuses)


def test_codes_faux_concurrents_bloquent_la_carte_a_trois(
    client: TestClient, seed: ClaimsSeed
) -> None:
    """Cinq codes faux simultanés : 2 comptés, le 3e bloque, les suivants trouvent la carte
    bloquée. Exactement 3 échecs sont enregistrés, la carte est bloquée 15 minutes."""
    card, pending = _codes_pending_on_one_card(client, seed, 5)
    assert _verify_in_parallel(client, seed, pending) == [422, 422, 423, 423, 423]
    with seed.owner() as conn:
        row = conn.execute(
            "SELECT failed_code_count, blocked_until FROM cards WHERE id = %s", (card,)
        ).fetchone()
        failures = conn.execute(
            "SELECT sum(code_failed_attempts), count(*) FILTER (WHERE status = 'bloquee') "
            "FROM identity_checks WHERE card_id = %s",
            (card,),
        ).fetchone()
    assert row == (0, T0 + timedelta(minutes=15))
    assert failures == (3, 1)
