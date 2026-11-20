"""Parcours « comptoir » de bout en bout sur l'application ASSEMBLÉE (R1, R2, R5, R6, R7, R9).

Cotisation payée par webhook simulé → droits rouverts → identification à trois facteurs avec le
QR dynamique réel de L4 → 48 000 FCFA accordés par R-12 v3 → écriture équilibrée au grand
livre par le consommateur de l'outbox (L3) ; puis 185 000 FCFA → revue R-20, aucune écriture
→ le médecin-conseil accorde → écriture. Secret médical, isolation entre cliniques et
organisations, audit du motif.

Tout passe par l'API HTTP avec de vrais jetons ; seuls les traitements planifiés (quotidien,
émission mensuelle, consommateur du grand livre) sont appelés directement, dans la boucle et le
pool de l'application, sous ``mulema_app``. Le parcours tourne sous ``egress_guard`` (suite +
liste blanche de l'application, qui ne contient que HealthOS simulé).
"""

from __future__ import annotations

import socket
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from api.integrations.egress import EgressDeniedError
from api.ledger.consumer import DrainReport, drain_outbox
from api.members.cards import current_qr_payload
from api.members.jobs import run_daily
from api.payments.jobs import issue_month
from api.tests.e2e.conftest import ORG_A, ORG_A_SLUG, Platform

ITEMS_48000: list[dict[str, Any]] = [
    {"act_code": "CONS-GEN", "quantity": 1},
    {"act_code": "BIO-NFS", "quantity": 1},
    {"act_code": "CARD-ECG", "quantity": 1},
]
ITEMS_185000: list[dict[str, Any]] = [
    {"act_code": "CONS-SPE", "quantity": 1},
    {"act_code": "IMG-ECHO-ABD", "quantity": 5},
]
REASON = "Motif fictif e2e — douleur inventée pour le test"
MEDICAL_READ = "claim.medical_reason.read"
OCTOBER = date(2026, 10, 1)
PAYMENT_DAY = datetime(2026, 11, 15, 9, 0, tzinfo=UTC)  # échéance du 01/10 + 45 jours


# --- Aides -----------------------------------------------------------------------------------


def _drain_ledger(env: Platform) -> DrainReport:
    """Consommateur de l'outbox du grand livre, sur le pool de l'application (``mulema_app``)."""

    async def run() -> DrainReport:
        async with env.database.autocommit_connection() as conn:
            return await drain_outbox(conn, ORG_A)

    return env.run(run)


def _qr(env: Platform, card_id: UUID) -> str:
    """QR affiché par l'espace adhérent à l'instant de l'horloge (hors contrat HTTP)."""

    async def run() -> str:
        async with env.database.transaction(ORG_A) as session:
            return await current_qr_payload(session, env.card_keys, ORG_A, card_id, env.clock.now())

    return env.run(run)


def _status(env: Platform, member_id: str) -> str:
    value = env.scalar("SELECT status FROM members WHERE id = %s", (UUID(member_id),))
    assert isinstance(value, str)
    return value


def _rights_open(env: Platform, member_id: str) -> bool:
    response = env.client.get(
        f"/v1/members/{member_id}/entitlements", headers=env.auth("gestionnaire")
    )
    assert response.status_code == 200, response.text
    return bool(response.json()["rights_open"])


def _balanced_entries(env: Platform, source_id: str) -> list[tuple[int, int, int]]:
    """(nombre de lignes, total débit, total crédit) de chaque écriture d'une source."""
    return [
        (int(r[0]), int(r[1]), int(r[2]))
        for r in env.rows(
            "SELECT count(l.id), sum(l.debit_xof), sum(l.credit_xof) FROM ledger_entries e "
            "JOIN ledger_lines l ON l.entry_id = e.id WHERE e.source_id = %s GROUP BY e.id",
            (UUID(source_id),),
        )
    ]


def _identify(env: Platform, card_id: UUID, phone: str, who: str = "clinique_a") -> str:
    """R1 : QR dynamique, photo, code SMS — par l'API du comptoir."""
    started = env.client.post(
        "/v1/counter/identifications", json={"qr_payload": _qr(env, card_id)}, headers=env.auth(who)
    )
    assert started.status_code == 201, started.text
    identification = str(started.json()["id"])
    assert started.json()["qr_verified"] is True
    photo = env.client.post(
        f"/v1/counter/identifications/{identification}/photo-confirmation",
        json={"confirmed": True},
        headers=env.auth(who),
    )
    assert photo.status_code == 200, photo.text
    sent = env.client.post(
        f"/v1/counter/identifications/{identification}/code", headers=env.auth(who)
    )
    assert sent.status_code == 202, sent.text
    verified = env.client.post(
        f"/v1/counter/identifications/{identification}/code-verification",
        json={"code": env.sms.last_code(phone)},
        headers=env.auth(who),
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "verifiee"
    return identification


def _claim(
    env: Platform,
    insured: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    encounter_ref: str | None = None,
) -> dict[str, Any]:
    identification = _identify(env, insured["card_id"], insured["phone"])
    body: dict[str, Any] = {
        "identification_id": identification,
        "service_date": env.clock.now().date().isoformat(),
        "items": items,
    }
    if encounter_ref is not None:
        body["healthos_encounter_ref"] = encounter_ref
    response = env.client.post("/v1/claims", json=body, headers=env.headers("clinique_a"))
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


# --- Adhérent couvert : adhésion, carte, cotisation impayée, paiement par webhook -------------


@pytest.fixture(scope="module")
def insured(platform: Platform) -> dict[str, Any]:
    env = platform
    phone = "+2250700009901"
    env.clock.current = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    created = env.client.post(
        "/v1/members",
        json={
            "holder": {
                "given_name": "Prénom",
                "family_name": "Fictif",
                "birth_date": "1990-05-12",
                "phone_e164": phone,
            },
            "plan_code": "FAMILLE-OR",
            "enrolled_on": "2026-07-01",
        },
        headers=env.headers("gestionnaire"),
    )
    assert created.status_code == 201, created.text
    member = created.json()
    member_id, person_id = member["id"], member["holder"]["person_id"]
    card = env.client.post(
        f"/v1/members/{member_id}/cards",
        json={"person_id": person_id},
        headers=env.headers("gestionnaire"),
    )
    assert card.status_code == 201, card.text

    env.run(run_daily, env.database, ORG_A, env.clock.now())  # carence écoulée : actif
    env.run(issue_month, env.database, ORG_A, OCTOBER, env.clock.now())
    env.clock.current = PAYMENT_DAY
    env.run(run_daily, env.database, ORG_A, env.clock.now())  # J+45 d'impayé : suspendu (R8)
    rights_before = _rights_open(env, member_id)
    status_before = _status(env, member_id)

    contribution = env.scalar(
        "SELECT id FROM contributions WHERE member_id = %s AND period_start = %s",
        (UUID(member_id), OCTOBER),
    )
    link = env.client.post(
        f"/v1/contributions/{contribution}/payment-links", headers=env.headers("gestionnaire")
    )
    assert link.status_code == 201, link.text
    token = str(link.json()["url"]).rsplit("/", 1)[1]
    checkout = env.client.post(
        f"/v1/public/payment-links/{token}/checkout",
        json={"channel": "wave", "payer_country_code": "CI"},
        headers={"Idempotency-Key": f"cle-{uuid.uuid4().hex}"},
    )
    assert checkout.status_code == 201, checkout.text
    payment_id = UUID(checkout.json()["payment_id"])
    note = env.wave.notification(payment_id, occurred_at=env.clock.now())
    hook = env.client.post(
        f"/v1/webhooks/{ORG_A_SLUG}/payments/wave",
        content=note.body,
        headers={"Content-Type": "application/json", "X-Signature": note.signature},
    )
    assert hook.status_code == 200, hook.text
    return {
        "member_id": member_id,
        "person_id": person_id,
        "card_id": UUID(card.json()["id"]),
        "phone": phone,
        "contribution_id": str(contribution),
        "status_before": status_before,
        "rights_before": rights_before,
        "webhook": hook.json(),
    }


# --- Parcours ----------------------------------------------------------------------------------


def test_le_webhook_de_cotisation_rouvre_les_droits_et_passe_l_ecriture(
    platform: Platform, insured: dict[str, Any]
) -> None:
    env = platform
    assert (insured["status_before"], insured["rights_before"]) == ("suspendu", False)
    assert insured["webhook"] == {"received": True, "duplicate": False}
    assert _status(env, insured["member_id"]) == "actif"
    assert _rights_open(env, insured["member_id"]) is True

    _drain_ledger(env)
    entries = _balanced_entries(env, insured["contribution_id"])
    assert entries == [(2, 27500, 27500)]


def test_48000_fcfa_accorde_par_r12_puis_ecrit_au_grand_livre(
    platform: Platform, insured: dict[str, Any]
) -> None:
    env = platform
    created = _claim(env, insured, ITEMS_48000)

    decision = created["decision"]
    assert decision["outcome"] == "accordee_auto"
    assert decision["rule"] == {"code": "R-12", "version": 3}
    assert (decision["total_xof"], decision["covered_xof"]) == (48000, 38400)
    claim_id = created["claim"]["id"]
    rule_id, rule_version = env.rows(
        "SELECT decision_rule_id, decision_rule_version FROM claims WHERE id = %s",
        (UUID(claim_id),),
    )[0]
    assert rule_version == 3
    assert rule_id == env.scalar(
        "SELECT id FROM rules WHERE organization_id = %s AND code = 'R-12'", (ORG_A,)
    )
    fraud_score = env.scalar("SELECT fraud_score FROM claims WHERE id = %s", (UUID(claim_id),))
    assert fraud_score == Decimal("0.060")

    assert _balanced_entries(env, claim_id) == []  # rien avant le consommateur
    report = _drain_ledger(env)
    assert report.failed == 0
    assert _balanced_entries(env, claim_id) == [(2, 38400, 38400)]
    _drain_ledger(env)  # rejeu : idempotent
    assert _balanced_entries(env, claim_id) == [(2, 38400, 38400)]


def test_185000_fcfa_en_revue_sans_ecriture_puis_accord_du_medecin_conseil(
    platform: Platform, insured: dict[str, Any]
) -> None:
    env = platform
    created = _claim(env, insured, ITEMS_185000)
    assert created["decision"]["outcome"] == "en_revue"
    assert created["decision"]["rule"] == {"code": "R-20", "version": 2}
    assert created["authorization"] is None
    claim_id = created["claim"]["id"]

    _drain_ledger(env)
    assert _balanced_entries(env, claim_id) == []

    decided = env.client.post(
        f"/v1/claims/{claim_id}/decisions",
        json={"decision": "accorder", "reason_code": "MC-01"},
        headers=env.headers("medecin_conseil"),
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["claim"]["status"] == "accordee"

    _drain_ledger(env)
    covered = int(
        env.scalar("SELECT sum(covered_xof) FROM claim_items WHERE claim_id = %s", (claim_id,))
    )
    assert covered == 148000
    assert _balanced_entries(env, claim_id) == [(2, covered, covered)]


def test_secret_medical_audit_et_isolation(platform: Platform, insured: dict[str, Any]) -> None:
    env = platform
    pseudonym = env.scalar(
        "SELECT healthos_pseudonym FROM persons WHERE id = %s", (UUID(insured["person_id"]),)
    )
    ref = f"enc-e2e-{uuid.uuid4().hex[:8]}"
    env.healthos.add_patient(
        pseudonym=pseudonym,
        healthos_id=f"pat-{ref}",
        given_name="Prénom",
        family_name="Fictif",
        phone="+2250700000000",
        birth_date="1990-05-12",
    )
    env.healthos.add_encounter(
        ref=ref,
        pseudonym=pseudonym,
        status="finished",
        start="2026-11-15T08:30:00Z",
        facility_ref="Organization/fac-e2e",
        reason=REASON,
    )
    claim_id = _claim(env, insured, ITEMS_185000, encounter_ref=ref)["claim"]["id"]

    # Le gestionnaire ne reçoit aucune donnée médicale, et n'a pas accès au motif.
    for path in (f"/v1/claims/{claim_id}", "/v1/claims", "/v1/work-queue"):
        response = env.client.get(path, headers=env.auth("gestionnaire"))
        assert response.status_code == 200, response.text
        assert REASON not in response.text
        assert ref not in response.text
    refused = env.client.get(
        f"/v1/claims/{claim_id}/medical-reason", headers=env.auth("gestionnaire")
    )
    assert refused.status_code == 403
    assert refused.json()["code"] == "SEC-01"

    # La clinique de B ne voit pas les dossiers de A.
    other = env.client.get(f"/v1/claims/{claim_id}", headers=env.auth("clinique_b"))
    assert other.status_code == 404
    listed = env.client.get("/v1/claims", headers=env.auth("clinique_b"))
    assert listed.status_code == 200, listed.text
    assert claim_id not in listed.text

    # Le médecin-conseil lit le motif : une entrée audit_events par lecture.
    reads = "SELECT count(*) FROM audit_events WHERE action = %s AND target_id = %s"
    assert env.scalar(reads, (MEDICAL_READ, UUID(claim_id))) == 0
    read = env.client.get(
        f"/v1/claims/{claim_id}/medical-reason", headers=env.auth("medecin_conseil")
    )
    assert read.status_code == 200, read.text
    assert read.json()["text"] == REASON
    assert read.headers["cache-control"] == "no-store"
    assert env.scalar(reads, (MEDICAL_READ, UUID(claim_id))) == 1
    assert (
        env.scalar(
            "SELECT actor_user_id FROM audit_events WHERE id = %s",
            (UUID(read.json()["audit_event_id"]),),
        )
        == (env.users["medecin_conseil"])
    )


def test_la_garde_d_egress_refuse_toute_destination_hors_liste(platform: Platform) -> None:
    """R9 : l'application tourne sous sa liste blanche (HealthOS simulé seul)."""
    del platform
    with pytest.raises(EgressDeniedError):
        socket.create_connection(("192.0.2.10", 443), timeout=1)
