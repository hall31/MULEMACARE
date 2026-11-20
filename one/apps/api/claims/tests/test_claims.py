"""R5 et R4 — la demande appelle le moteur L2, enregistre rule_id/rule_version, route ou refuse.

- 48 000 FCFA, score 0,06 : accordé automatiquement (R-12 v3), accord en ligne émis, écriture
  au grand livre après consommation de ``claim.decided`` par L3 ;
- 185 000 FCFA : revue (R-20 v2), AUCUN paiement : ni accord, ni écriture au grand livre ;
- refus avec code de règle stable (R-01, R-04, R-07).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from api.claims.tests.conftest import ClaimsSeed
from api.claims.tests.flows import (
    ITEMS_48000,
    ITEMS_185000,
    create_claim,
    drain_ledger,
    identify,
    ledger_entries_for,
    new_claim,
    outbox,
)


def _rule(seed: ClaimsSeed, code: str) -> str:
    return str(
        seed.scalar(
            "SELECT id FROM rules WHERE organization_id = %s AND code = %s", (seed.orgs["a"], code)
        )
    )


def test_dossier_sous_seuil_accorde_automatiquement(client: TestClient, seed: ClaimsSeed) -> None:
    member, body = new_claim(client, seed, ITEMS_48000)

    decision = body["decision"]
    assert decision["outcome"] == "accordee_auto"
    assert decision["rule"] == {"code": "R-12", "version": 3}
    assert decision["reason_code"] == "R-12"
    assert (decision["total_xof"], decision["covered_xof"], decision["patient_share_xof"]) == (
        48000,
        38400,
        9600,
    )
    assert decision["currency"] == "XOF"
    claim = body["claim"]
    assert claim["status"] == "accordee_auto"
    assert claim["rule"] == {"code": "R-12", "version": 3}
    assert claim["claim_number"].startswith("PEC-26-")
    assert body["authorization"]["kind"] == "en_ligne"
    assert body["authorization"]["status"] == "emise"
    assert body["authorization"]["covered_xof"] == 38400

    with seed.owner() as conn:
        row = conn.execute(
            "SELECT decision_rule_id, decision_rule_version, fraud_score, channel, "
            "identity_check_id IS NOT NULL FROM claims WHERE id = %s",
            (claim["id"],),
        ).fetchone()
        decisions = conn.execute(
            "SELECT sequence, outcome, source, rule_id, rule_version, reason_code, decided_by "
            "FROM claim_decisions WHERE claim_id = %s ORDER BY sequence",
            (claim["id"],),
        ).fetchall()
        items = conn.execute(
            "SELECT line_no, unit_amount_xof, quantity, amount_xof, covered_xof, "
            "tariff_item_id IS NOT NULL FROM claim_items WHERE claim_id = %s ORDER BY line_no",
            (claim["id"],),
        ).fetchall()
    assert row is not None
    assert str(row[0]) == _rule(seed, "R-12")
    assert row[1:4] == (3, Decimal("0.060"), "comptoir")
    assert row[4] is True
    assert [(d[0], d[1], d[2], str(d[3]), d[4], d[5], d[6]) for d in decisions] == [
        (1, "accordee_auto", "regle", _rule(seed, "R-12"), 3, "R-12", None)
    ]
    assert items == [
        (1, 25000, 1, 25000, 20000, True),
        (2, 8000, 1, 8000, 6400, True),
        (3, 15000, 1, 15000, 12000, True),
    ]
    assert seed.fraud.calls[-1] == member.member_id

    events = outbox(seed, claim["id"])
    assert [e[0] for e in events] == ["claim.requested", "claim.decided"]
    decided = events[1][1]
    assert decided["outcome"] == "accordee_auto"
    assert decided["source"] == "regle"
    assert decided["rule"] == {"rule_id": _rule(seed, "R-12"), "code": "R-12", "version": 3}
    assert decided["covered_xof"] == 38400

    drain_ledger(seed)
    assert ledger_entries_for(seed, claim["id"]) == 1


def test_dossier_au_dessus_du_seuil_part_en_revue_sans_paiement(
    client: TestClient, seed: ClaimsSeed
) -> None:
    payments_before = seed.scalar("SELECT count(*) FROM payments")
    _, body = new_claim(client, seed, ITEMS_185000)

    decision = body["decision"]
    assert decision["outcome"] == "en_revue"
    assert decision["rule"] == {"code": "R-20", "version": 2}
    assert decision["total_xof"] == 185000
    assert decision["review_due_at"].startswith("2026-10-01T11:00:00")
    assert body["claim"]["status"] == "en_revue"
    assert body["authorization"] is None
    claim_id = body["claim"]["id"]

    assert seed.scalar("SELECT count(*) FROM authorizations WHERE claim_id = %s", (claim_id,)) == 0
    decided = outbox(seed, claim_id)[1][1]
    assert decided["outcome"] == "en_revue"
    assert decided["rule"]["code"] == "R-20"

    drain_ledger(seed)
    assert ledger_entries_for(seed, claim_id) == 0
    assert seed.scalar("SELECT count(*) FROM payments") == payments_before


def test_sans_score_de_fraude_le_dossier_part_en_revue(
    client: TestClient, seed: ClaimsSeed
) -> None:
    seed.fraud.value = None
    _, body = new_claim(client, seed, ITEMS_48000)
    assert body["decision"]["outcome"] == "en_revue"


def test_score_de_fraude_au_seuil_part_en_revue(client: TestClient, seed: ClaimsSeed) -> None:
    seed.fraud.value = Decimal("0.20")
    _, body = new_claim(client, seed, ITEMS_48000)
    assert body["decision"]["outcome"] == "en_revue"


def test_prestataire_hors_reseau_refuse_r04(client: TestClient, seed: ClaimsSeed) -> None:
    _, body = new_claim(client, seed, ITEMS_48000, who="clinique_hors_reseau")
    assert body["decision"]["outcome"] == "refusee"
    assert body["decision"]["reason_code"] == "R-04"
    assert body["decision"]["rule"] == {"code": "R-04", "version": 2}
    assert body["decision"]["covered_xof"] == 0
    assert body["claim"]["status"] == "refusee"
    assert body["authorization"] is None


def test_droits_suspendus_refuse_r01(client: TestClient, seed: ClaimsSeed) -> None:
    member = seed.new_member(status="suspendu")
    identification = identify(client, seed, member)
    body = create_claim(client, seed, identification, ITEMS_48000).json()
    assert body["decision"]["reason_code"] == "R-01"
    assert body["decision"]["outcome"] == "refusee"


def test_impaye_de_45_jours_refuse_r01(client: TestClient, seed: ClaimsSeed) -> None:
    member = seed.new_member(unpaid_since=date(2026, 8, 5))  # 57 jours au 01/10
    identification = identify(client, seed, member)
    body = create_claim(client, seed, identification, ITEMS_48000).json()
    assert body["decision"]["reason_code"] == "R-01"


def test_carence_en_cours_refuse_r07(client: TestClient, seed: ClaimsSeed) -> None:
    member = seed.new_member(enrolled_on=date(2026, 9, 1))
    identification = identify(client, seed, member)
    body = create_claim(client, seed, identification, ITEMS_48000).json()
    assert body["decision"]["reason_code"] == "R-07"


def test_acte_inconnu_refuse_sans_dossier(client: TestClient, seed: ClaimsSeed) -> None:
    member = seed.new_member()
    identification = identify(client, seed, member)
    before = seed.scalar("SELECT count(*) FROM claims")
    response = create_claim(
        client, seed, identification, [{"act_code": "ACTE-INCONNU", "quantity": 1}]
    )
    assert response.status_code == 422
    assert response.json()["code"] == "CLM-02"
    assert seed.scalar("SELECT count(*) FROM claims") == before


def test_identification_requise_et_a_usage_unique(client: TestClient, seed: ClaimsSeed) -> None:
    member = seed.new_member()
    opened = client.post(
        "/v1/counter/identifications",
        json={"qr_payload": member.qr_payload},
        headers=seed.auth("clinique_p1"),
    ).json()["id"]
    incomplete = create_claim(client, seed, opened, ITEMS_48000)
    assert incomplete.status_code == 422
    assert incomplete.json()["code"] == "ID-07"

    identification = identify(client, seed, member)
    assert create_claim(client, seed, identification, ITEMS_48000).status_code == 201
    reused = create_claim(client, seed, identification, ITEMS_48000)
    assert reused.status_code == 409
    assert reused.json()["code"] == "CLM-01"


def test_identification_d_une_autre_clinique(client: TestClient, seed: ClaimsSeed) -> None:
    member = seed.new_member()
    identification = identify(client, seed, member)
    response = create_claim(client, seed, identification, ITEMS_48000, who="clinique_p2")
    assert response.status_code == 404


def test_demande_idempotente(client: TestClient, seed: ClaimsSeed) -> None:
    member = seed.new_member()
    identification = identify(client, seed, member)
    first = create_claim(client, seed, identification, ITEMS_48000, key="cle-idempotence-01")
    replay = create_claim(client, seed, identification, ITEMS_48000, key="cle-idempotence-01")
    assert first.status_code == replay.status_code == 201
    assert replay.json() == first.json()
    assert seed.scalar("SELECT count(*) FROM claims WHERE member_id = %s", (member.member_id,)) == 1
    other_body = create_claim(client, seed, identification, ITEMS_185000, key="cle-idempotence-01")
    assert other_body.status_code == 409
    assert other_body.json()["code"] == "IDEM-01"


def test_date_de_soin_future_refusee(client: TestClient, seed: ClaimsSeed) -> None:
    member = seed.new_member()
    identification = identify(client, seed, member)
    response = create_claim(client, seed, identification, ITEMS_48000, service_date="2026-10-02")
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-01"


def test_seule_la_clinique_demande(client: TestClient, seed: ClaimsSeed) -> None:
    member = seed.new_member()
    identification = identify(client, seed, member)
    for who in ("gestionnaire", "medecin_conseil", "admin"):
        response = create_claim(client, seed, identification, ITEMS_48000, who=who)
        assert response.status_code == 403
