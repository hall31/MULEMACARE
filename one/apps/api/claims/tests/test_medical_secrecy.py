"""R6 — secret médical côté prises en charge.

- Aucune donnée médicale dans les réponses du gestionnaire (ni motif, ni référence de
  consultation HealthOS, ni champ à nom médical).
- ``readMedicalReason`` : médecin-conseil seulement (SEC-01 sinon), motif lu à la demande chez
  HealthOS (L9) avec le pseudonyme seul, chaque lecture crée un ``audit_events``, réponse
  ``Cache-Control: no-store``, motif jamais stocké.
"""

from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from api.claims.tests.conftest import ClaimsSeed, MemberRef
from api.claims.tests.flows import ITEMS_185000, create_claim, identify

REASON = "Motif fictif de test — douleur thoracique inventée"
MEDICAL_KEY = re.compile(r"diagnos|motif|medical|reason|ordonnance|prescri|encounter", re.I)
READ_ACTION = "claim.medical_reason.read"


def _claim_with_encounter(client: TestClient, seed: ClaimsSeed) -> tuple[MemberRef, str, str]:
    member = seed.new_member()
    ref = f"enc-{member.member_number[-4:]}"
    seed.healthos.add_patient(
        pseudonym=member.pseudonym,
        healthos_id=f"pat-{member.member_number[-4:]}",
        given_name="Prénom",
        family_name="Fictif",
        phone="+2250700000000",
        birth_date="1990-01-01",
    )
    seed.healthos.add_encounter(
        ref=ref,
        pseudonym=member.pseudonym,
        status="finished",
        start="2026-10-01T08:30:00Z",
        facility_ref="Organization/fac-1",
        reason=REASON,
    )
    identification = identify(client, seed, member)
    response = create_claim(client, seed, identification, ITEMS_185000, encounter_ref=ref)
    assert response.status_code == 201, response.text
    return member, response.json()["claim"]["id"], ref


def _keys(node: Any) -> list[str]:  # noqa: ANN401 — parcours d'un JSON arbitraire
    if isinstance(node, dict):
        return [*node.keys(), *(k for v in node.values() for k in _keys(v))]
    if isinstance(node, list):
        return [k for v in node for k in _keys(v)]
    return []


def _audit_reads(seed: ClaimsSeed, claim_id: str) -> int:
    return int(
        seed.scalar(
            "SELECT count(*) FROM audit_events WHERE action = %s AND target_id = %s",
            (READ_ACTION, claim_id),
        )
    )


@pytest.mark.parametrize("who", ["gestionnaire", "admin", "medecin_conseil", "clinique_p1"])
def test_aucune_donnee_medicale_dans_les_reponses_hors_motif(
    client: TestClient, seed: ClaimsSeed, who: str
) -> None:
    _, claim_id, ref = _claim_with_encounter(client, seed)
    responses = [
        client.get(f"/v1/claims/{claim_id}", headers=seed.auth(who)),
        client.get("/v1/claims", headers=seed.auth(who)),
    ]
    if who != "clinique_p1":
        responses.append(client.get("/v1/work-queue", headers=seed.auth(who)))
    for response in responses:
        assert response.status_code == 200, response.text
        assert REASON not in response.text
        assert ref not in response.text
        # ``reason_code`` est un code administratif (R-12, MC-01…), jamais un motif médical.
        medical = [k for k in _keys(response.json()) if MEDICAL_KEY.search(k)]
        assert [k for k in medical if k != "reason_code"] == []


def test_le_medecin_conseil_lit_le_motif_avec_audit(client: TestClient, seed: ClaimsSeed) -> None:
    member, claim_id, ref = _claim_with_encounter(client, seed)
    before = len(seed.healthos.requests)

    response = client.get(
        f"/v1/claims/{claim_id}/medical-reason",
        headers=seed.auth("medecin_conseil") | {"X-Request-ID": "req-lecture-motif"},
    )

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["text"] == REASON
    assert body["source"] == "healthos"
    assert body["claim_id"] == claim_id
    with seed.owner() as conn:
        row = conn.execute(
            "SELECT action, actor_user_id, actor_role, target_type, target_id, request_id, "
            "metadata FROM audit_events WHERE id = %s",
            (body["audit_event_id"],),
        ).fetchone()
    assert row is not None
    assert row[:6] == (
        READ_ACTION,
        seed.users["medecin_conseil"],
        "medecin_conseil",
        "claim",
        UUID(claim_id),
        "req-lecture-motif",
    )
    assert REASON not in json.dumps(row[6])

    # Seul le pseudonyme est parti vers HealthOS.
    sent = json.dumps([r.as_dict() for r in seed.healthos.requests[before:]])
    assert str(member.pseudonym) in sent
    assert ref in sent
    assert "Fictif" not in sent
    assert member.member_number not in sent

    # Chaque lecture crée sa propre entrée.
    client.get(f"/v1/claims/{claim_id}/medical-reason", headers=seed.auth("medecin_conseil"))
    assert _audit_reads(seed, claim_id) == 2


@pytest.mark.parametrize("who", ["gestionnaire", "admin", "clinique_p1", "employeur_sans_droit"])
def test_autres_roles_refuses_sans_appel_ni_audit(
    client: TestClient, seed: ClaimsSeed, who: str
) -> None:
    _, claim_id, _ = _claim_with_encounter(client, seed)
    before = len(seed.healthos.requests)
    response = client.get(f"/v1/claims/{claim_id}/medical-reason", headers=seed.auth(who))
    assert response.status_code == 403
    assert response.json()["code"] == "SEC-01"
    assert REASON not in response.text
    assert len(seed.healthos.requests) == before
    assert _audit_reads(seed, claim_id) == 0


def test_healthos_indisponible_ni_motif_ni_audit(client: TestClient, seed: ClaimsSeed) -> None:
    _, claim_id, _ = _claim_with_encounter(client, seed)
    seed.healthos.fail_with = 503
    response = client.get(
        f"/v1/claims/{claim_id}/medical-reason", headers=seed.auth("medecin_conseil")
    )
    assert response.status_code == 502
    assert response.json()["code"] == "INT-01"
    assert _audit_reads(seed, claim_id) == 0


def test_dossier_sans_consultation(client: TestClient, seed: ClaimsSeed) -> None:
    member = seed.new_member()
    identification = identify(client, seed, member)
    claim_id = create_claim(client, seed, identification, ITEMS_185000).json()["claim"]["id"]
    response = client.get(
        f"/v1/claims/{claim_id}/medical-reason", headers=seed.auth("medecin_conseil")
    )
    assert response.status_code == 404
    assert _audit_reads(seed, claim_id) == 0


def test_medecin_d_une_autre_organisation(client: TestClient, seed: ClaimsSeed) -> None:
    _, claim_id, _ = _claim_with_encounter(client, seed)
    response = client.get(
        f"/v1/claims/{claim_id}/medical-reason", headers=seed.auth("medecin_conseil_b")
    )
    assert response.status_code == 404
    assert _audit_reads(seed, claim_id) == 0


def test_le_motif_n_entre_jamais_dans_la_base(client: TestClient, seed: ClaimsSeed) -> None:
    _, claim_id, _ = _claim_with_encounter(client, seed)
    client.get(f"/v1/claims/{claim_id}/medical-reason", headers=seed.auth("medecin_conseil"))
    with seed.owner() as conn:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            ).fetchall()
        ]
        for table in tables:
            dump = conn.execute(
                sql.SQL("SELECT coalesce(string_agg(t::text, ''), '') FROM {} t").format(
                    sql.Identifier(table)
                )
            ).fetchone()
            assert dump is not None
            assert REASON not in dump[0], table
