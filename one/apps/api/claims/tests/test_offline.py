"""R13 côté serveur — accord provisoire hors ligne signé ES256 sur l'appareil, rapproché à la
synchronisation (``authorization.synced``). Format de signature du comptoir : Q-L7-03."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import partial
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from api.claims.tests.conftest import ClaimsSeed, MemberRef
from api.claims.tests.flows import (
    ITEMS_48000,
    ITEMS_185000,
    SERVICE_DATE,
    as_response,
    drain_ledger,
    identify,
    in_parallel,
    ledger_entries_for,
    outbox,
)
from api.claims.tests.support import T0, TestDeviceKey, b64url, canonical_json


def _register(
    client: TestClient, seed: ClaimsSeed, key: TestDeviceKey, who: str = "clinique_p1"
) -> str:
    response = client.post(
        "/v1/counter/devices",
        json={"label": "Comptoir fictif", "public_key": key.public_jwk},
        headers=seed.auth(who),
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "actif"
    return str(response.json()["id"])


def _accord(  # noqa: PLR0913 — accord provisoire paramétrable
    key: TestDeviceKey,
    device_id: str,
    identification: str,
    member: MemberRef,
    *,
    items: list[dict[str, Any]],
    total: int,
    covered: int,
    issued_at: datetime = T0,
    validity: timedelta = timedelta(hours=2),
) -> dict[str, Any]:
    offline_ref = str(uuid.uuid4())
    content = {
        "v": 1,
        "offline_ref": offline_ref,
        "device_id": device_id,
        "identification_id": identification,
        "member_number": member.member_number,
        "beneficiary_id": str(member.person_id),
        "service_date": SERVICE_DATE,
        "items": items,
        "total_xof": total,
        "covered_xof": covered,
        "currency": "XOF",
        "issued_at": issued_at.isoformat().replace("+00:00", "Z"),
        "expires_at": (issued_at + validity).isoformat().replace("+00:00", "Z"),
        "rules": [{"code": "R-12", "version": 3}, {"code": "HL-01", "version": 1}],
    }
    raw = canonical_json(content)
    return {
        "offline_ref": offline_ref,
        "member_number": member.member_number,
        "beneficiary_id": str(member.person_id),
        "service_date": SERVICE_DATE,
        "items": items,
        "total_xof": total,
        "covered_xof": covered,
        "issued_at": content["issued_at"],
        "expires_at": content["expires_at"],
        "signed_payload": b64url(raw),
        "signature": key.sign(raw),
    }


def _sync(
    client: TestClient,
    seed: ClaimsSeed,
    device_id: str,
    accords: list[dict[str, Any]],
    who: str = "clinique_p1",
) -> httpx.Response:
    return as_response(
        client.post(
            "/v1/authorizations/offline-sync",
            json={"device_id": device_id, "authorizations": accords},
            headers=seed.auth(who),
        )
    )


def _prepared(client: TestClient, seed: ClaimsSeed) -> tuple[TestDeviceKey, str, str, MemberRef]:
    key = TestDeviceKey.generate()
    device = _register(client, seed, key)
    member = seed.new_member()
    identification = identify(client, seed, member)
    return key, device, identification, member


def test_politique_hors_ligne_issue_des_regles(client: TestClient, seed: ClaimsSeed) -> None:
    response = client.get("/v1/counter/offline-policy", headers=seed.auth("clinique_p1"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["threshold_xof"] == 50000
    assert body["validity_minutes"] == 120
    assert body["currency"] == "XOF"
    assert {(r["code"], r["version"]) for r in body["rules"]} == {("R-12", 3), ("HL-01", 1)}
    tariff = {i["act_code"]: i["amount_xof"] for i in body["tariff"]["items"]}
    assert tariff["CONS-GEN"] == 25000
    assert body["tariff"]["at"] == "2026-10-01"


def test_cle_publique_invalide_refusee(client: TestClient, seed: ClaimsSeed) -> None:
    bad = '{"crv":"P-256","kty":"EC","x":"AAAA","y":"AAAA"}'
    response = client.post(
        "/v1/counter/devices",
        json={"label": "Comptoir", "public_key": bad},
        headers=seed.auth("clinique_p1"),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-01"


def test_accord_sous_seuil_confirme_puis_rejoue_sans_doublon(
    client: TestClient, seed: ClaimsSeed
) -> None:
    key, device, identification, member = _prepared(client, seed)
    accord = _accord(
        key, device, identification, member, items=ITEMS_48000, total=48000, covered=38400
    )
    seed.clock.advance(timedelta(minutes=30))

    response = _sync(client, seed, device, [accord])
    assert response.status_code == 200, response.text
    [result] = response.json()["results"]
    assert result["outcome"] == "confirmee"
    assert result["reason_code"] is None
    claim_id, authorization_id = result["claim_id"], result["authorization_id"]

    with seed.owner() as conn:
        claim = conn.execute(
            "SELECT channel, status, total_xof, covered_xof, identity_check_id::text "
            "FROM claims WHERE id = %s",
            (claim_id,),
        ).fetchone()
        auth = conn.execute(
            "SELECT a.kind, a.status, r.code, a.rule_version, a.synced_at, a.covered_xof "
            "FROM authorizations a JOIN rules r ON r.id = a.rule_id WHERE a.id = %s",
            (authorization_id,),
        ).fetchone()
    assert claim == ("comptoir_hors_ligne", "accordee_auto", 48000, 38400, identification)
    assert auth == (
        "provisoire_hors_ligne",
        "synchronisee",
        "HL-01",
        1,
        T0 + timedelta(minutes=30),
        38400,
    )
    events = outbox(seed, authorization_id)
    assert [e[0] for e in events] == ["authorization.synced"]
    assert events[0][1]["outcome"] == "confirmee"
    assert events[0][1]["rule"] == {"code": "HL-01", "version": 1}
    claim_events = outbox(seed, claim_id)
    assert [e[0] for e in claim_events] == ["claim.requested", "claim.decided"]
    # La décision du dossier vient du moteur L2 (R-12), pas de HL-01.
    assert claim_events[1][1]["rule"]["code"] == "R-12"
    assert (claim_events[1][1]["outcome"], claim_events[1][1]["reason_code"]) == (
        "accordee_auto",
        "R-12",
    )
    drain_ledger(seed)
    assert ledger_entries_for(seed, claim_id) == 1

    replay = _sync(client, seed, device, [accord])
    assert replay.json()["results"] == [result]
    assert seed.scalar("SELECT count(*) FROM claims WHERE member_id = %s", (member.member_id,)) == 1
    assert len(outbox(seed, authorization_id)) == 1


def test_signature_invalide_rejetee_off02(client: TestClient, seed: ClaimsSeed) -> None:
    key, device, identification, member = _prepared(client, seed)
    accord = _accord(
        key, device, identification, member, items=ITEMS_48000, total=48000, covered=38400
    )
    accord["signature"] = TestDeviceKey.generate().sign(b"autre contenu")
    [result] = _sync(client, seed, device, [accord]).json()["results"]
    assert (result["outcome"], result["reason_code"]) == ("rejetee", "OFF-02")
    assert (
        seed.scalar("SELECT status FROM claims WHERE id = %s", (result["claim_id"],)) == "refusee"
    )
    event = outbox(seed, result["authorization_id"])[0][1]
    assert (event["outcome"], event["reason_code"]) == ("rejetee", "OFF-02")


def test_champs_en_clair_differents_du_contenu_signe_off02(
    client: TestClient, seed: ClaimsSeed
) -> None:
    key, device, identification, member = _prepared(client, seed)
    accord = _accord(
        key, device, identification, member, items=ITEMS_48000, total=48000, covered=38400
    )
    accord["covered_xof"] = 48000
    [result] = _sync(client, seed, device, [accord]).json()["results"]
    assert result["reason_code"] == "OFF-02"


def test_accord_synchronise_apres_expiration_off01(client: TestClient, seed: ClaimsSeed) -> None:
    key, device, identification, member = _prepared(client, seed)
    accord = _accord(
        key, device, identification, member, items=ITEMS_48000, total=48000, covered=38400
    )
    seed.clock.advance(timedelta(hours=2, seconds=1))
    [result] = _sync(client, seed, device, [accord]).json()["results"]
    assert (result["outcome"], result["reason_code"]) == ("rejetee", "OFF-01")
    assert (
        seed.scalar(
            "SELECT status FROM authorizations WHERE id = %s", (result["authorization_id"],)
        )
        == "expiree"
    )


def test_validite_plus_longue_que_la_regle_off01(client: TestClient, seed: ClaimsSeed) -> None:
    key, device, identification, member = _prepared(client, seed)
    accord = _accord(
        key,
        device,
        identification,
        member,
        items=ITEMS_48000,
        total=48000,
        covered=38400,
        validity=timedelta(hours=5),
    )
    [result] = _sync(client, seed, device, [accord]).json()["results"]
    assert result["reason_code"] == "OFF-01"


def test_accord_au_dessus_du_seuil_off03(client: TestClient, seed: ClaimsSeed) -> None:
    key, device, identification, member = _prepared(client, seed)
    accord = _accord(
        key, device, identification, member, items=ITEMS_185000, total=185000, covered=148000
    )
    [result] = _sync(client, seed, device, [accord]).json()["results"]
    assert (result["outcome"], result["reason_code"]) == ("rejetee", "OFF-03")


def test_appareil_revoque_off04(client: TestClient, seed: ClaimsSeed) -> None:
    key, device, identification, member = _prepared(client, seed)
    with seed.owner() as conn:
        conn.execute(
            "UPDATE counter_devices SET status = 'revoque', revoked_at = now() WHERE id = %s",
            (device,),
        )
    accord = _accord(
        key, device, identification, member, items=ITEMS_48000, total=48000, covered=38400
    )
    [result] = _sync(client, seed, device, [accord]).json()["results"]
    assert (result["outcome"], result["reason_code"]) == ("rejetee", "OFF-04")
    assert result["claim_id"] is None


def test_appareil_d_une_autre_clinique(client: TestClient, seed: ClaimsSeed) -> None:
    key, device, identification, member = _prepared(client, seed)
    accord = _accord(
        key, device, identification, member, items=ITEMS_48000, total=48000, covered=38400
    )
    response = _sync(client, seed, device, [accord], who="clinique_p2")
    assert response.status_code == 404


# --- Décision du moteur L2 à la synchronisation (Q-L5-08) --------------------------------------


def _decision(seed: ClaimsSeed, claim_id: str) -> list[tuple[Any, ...]]:
    with seed.owner() as conn:
        return list(
            conn.execute(
                "SELECT d.outcome, d.source, r.code, d.rule_version, d.reason_code "
                "FROM claim_decisions d JOIN rules r ON r.id = d.rule_id "
                "WHERE d.claim_id = %s ORDER BY d.sequence",
                (claim_id,),
            ).fetchall()
        )


def _authorization(seed: ClaimsSeed, authorization_id: str) -> tuple[Any, ...] | None:
    with seed.owner() as conn:
        return conn.execute(
            "SELECT a.status, r.code, a.rule_version, a.covered_xof "
            "FROM authorizations a JOIN rules r ON r.id = a.rule_id WHERE a.id = %s",
            (authorization_id,),
        ).fetchone()


@pytest.mark.parametrize(
    ("member_kwargs", "clinic", "code", "version"),
    [
        ({"status": "suspendu"}, "clinique_p1", "R-01", 1),
        ({"unpaid_since": date(2026, 8, 5)}, "clinique_p1", "R-01", 1),
        ({}, "clinique_hors_reseau", "R-04", 2),
        ({"enrolled_on": date(2026, 9, 1)}, "clinique_p1", "R-07", 1),
    ],
    ids=["suspendu", "impaye", "hors-reseau", "carence"],
)
def test_accord_provisoire_refuse_par_le_moteur_n_est_pas_confirme(  # noqa: PLR0913
    *,
    client: TestClient,
    seed: ClaimsSeed,
    member_kwargs: dict[str, Any],
    clinic: str,
    code: str,
    version: int,
) -> None:
    key = TestDeviceKey.generate()
    device = _register(client, seed, key, who=clinic)
    member = seed.new_member(**member_kwargs)
    identification = identify(client, seed, member, who=clinic)
    accord = _accord(
        key, device, identification, member, items=ITEMS_48000, total=48000, covered=38400
    )
    seed.clock.advance(timedelta(minutes=30))

    [result] = _sync(client, seed, device, [accord], who=clinic).json()["results"]
    assert (result["outcome"], result["reason_code"]) == ("rejetee", code)
    claim_id, authorization_id = result["claim_id"], result["authorization_id"]

    expected_version = seed.scalar(
        "SELECT max(v.version) FROM rule_versions v JOIN rules r ON r.id = v.rule_id "
        "WHERE r.code = %s AND r.organization_id = %s AND v.state = 'en_vigueur'",
        (code, seed.orgs["a"]),
    )
    assert expected_version == version
    assert _decision(seed, claim_id) == [("refusee", "regle", code, version, code)]
    assert (
        seed.scalar("SELECT status || ':' || covered_xof FROM claims WHERE id = %s", (claim_id,))
        == "refusee:0"
    )
    assert _authorization(seed, authorization_id) == ("rejetee_a_la_synchro", code, version, 0)

    claim_events = outbox(seed, claim_id)
    assert [e[0] for e in claim_events] == ["claim.requested", "claim.decided"]
    decided = claim_events[1][1]
    assert (decided["outcome"], decided["reason_code"], decided["rule"]["code"]) == (
        "refusee",
        code,
        code,
    )
    synced = outbox(seed, authorization_id)[0][1]
    assert (synced["outcome"], synced["reason_code"], synced["covered_xof"]) == (
        "rejetee",
        code,
        0,
    )
    drain_ledger(seed)
    assert ledger_entries_for(seed, claim_id) == 0

    replay = _sync(client, seed, device, [accord], who=clinic)
    assert replay.json()["results"] == [result]


@pytest.mark.parametrize("score", [None, "0.20"], ids=["sans-score", "score-au-seuil"])
def test_accord_provisoire_route_en_revue_par_le_moteur(
    client: TestClient, seed: ClaimsSeed, score: str | None
) -> None:
    seed.fraud.value = None if score is None else Decimal(score)
    key, device, identification, member = _prepared(client, seed)
    accord = _accord(
        key, device, identification, member, items=ITEMS_48000, total=48000, covered=38400
    )
    seed.clock.advance(timedelta(minutes=30))

    [result] = _sync(client, seed, device, [accord]).json()["results"]
    assert (result["outcome"], result["reason_code"]) == ("rejetee", "R-20")
    claim_id, authorization_id = result["claim_id"], result["authorization_id"]

    [(outcome, source, rule, _, reason)] = _decision(seed, claim_id)
    assert (outcome, source, rule, reason) == ("en_revue", "regle", "R-20", "R-20")
    with seed.owner() as conn:
        claim = conn.execute(
            "SELECT status, covered_xof, review_due_at FROM claims WHERE id = %s", (claim_id,)
        ).fetchone()
    assert claim == ("en_revue", 38400, T0 + timedelta(minutes=30, hours=2))
    assert _authorization(seed, authorization_id) == ("rejetee_a_la_synchro", "R-20", 2, 0)
    drain_ledger(seed)
    assert ledger_entries_for(seed, claim_id) == 0

    # Le médecin-conseil le voit dans sa file.
    listed = client.get(
        "/v1/claims", params={"status": "en_revue"}, headers=seed.auth("medecin_conseil")
    )
    assert claim_id in {c["id"] for c in listed.json()["items"]}


# --- Réutilisation d'identification et synchronisations concurrentes ---------------------------


def test_identification_deja_utilisee_par_un_autre_accord_id07(
    client: TestClient, seed: ClaimsSeed
) -> None:
    key, device, identification, member = _prepared(client, seed)
    first = _accord(
        key, device, identification, member, items=ITEMS_48000, total=48000, covered=38400
    )
    second = _accord(
        key, device, identification, member, items=ITEMS_48000, total=48000, covered=38400
    )
    [one] = _sync(client, seed, device, [first]).json()["results"]
    [two] = _sync(client, seed, device, [second]).json()["results"]
    assert one["outcome"] == "confirmee"
    assert (two["outcome"], two["reason_code"]) == ("rejetee", "ID-07")
    assert (
        seed.scalar("SELECT count(*) FROM claims WHERE identity_check_id = %s", (identification,))
        == 1
    )


def test_identification_reutilisee_en_parallele_un_seul_accord(
    client: TestClient, seed: ClaimsSeed
) -> None:
    key, device, identification, member = _prepared(client, seed)
    accords = [
        _accord(key, device, identification, member, items=ITEMS_48000, total=48000, covered=38400)
        for _ in range(4)
    ]
    responses = in_parallel([partial(_sync, client, seed, device, [accord]) for accord in accords])
    outcomes = []
    for response in responses:
        assert isinstance(response, httpx.Response), repr(response)
        assert response.status_code == 200, response.text
        [result] = response.json()["results"]
        outcomes.append((result["outcome"], result["reason_code"]))
    assert sorted(outcomes) == [("confirmee", None)] + [("rejetee", "ID-07")] * 3
    assert (
        seed.scalar("SELECT count(*) FROM claims WHERE identity_check_id = %s", (identification,))
        == 1
    )


def test_meme_offline_ref_synchronise_en_parallele_un_seul_dossier(
    client: TestClient, seed: ClaimsSeed
) -> None:
    key, device, identification, member = _prepared(client, seed)
    accord = _accord(
        key, device, identification, member, items=ITEMS_48000, total=48000, covered=38400
    )
    responses = in_parallel([lambda: _sync(client, seed, device, [accord]) for _ in range(4)])
    results = []
    for response in responses:
        assert isinstance(response, httpx.Response), repr(response)
        assert response.status_code == 200, response.text
        results.append(response.json()["results"])
    assert all(r == results[0] for r in results)
    assert results[0][0]["outcome"] == "confirmee"
    assert seed.scalar("SELECT count(*) FROM claims WHERE member_id = %s", (member.member_id,)) == 1
    assert (
        seed.scalar(
            "SELECT count(*) FROM authorizations WHERE offline_ref = %s",
            (accord["offline_ref"],),
        )
        == 1
    )
