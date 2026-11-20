"""Espace adhérent et diaspora (Phase 1, x-lot P1) sur l'application ASSEMBLÉE.

Rôle ``adherent`` (CR-P1-01) : un compte rattaché à UN contrat (``user_roles.member_id``). Il ne
voit que ses propres données : isolation par personne (un adhérent A ne voit rien d'un adhérent
A' de la même organisation) ET par organisation (RLS forcée sous ``mulema_app``).

Parcours, tout par l'API HTTP avec de vrais jetons : le gestionnaire inscrit deux adhérents de la
même organisation (A, avec un enfant ; A') ; la clinique scanne le QR que l'adhérent affiche
depuis ``getMyCard`` (QR dynamique réel de L4) ; dossiers accordés (R-12), en revue (R-20),
refusé par le médecin-conseil ; l'adhérent invite un proche à payer sa cotisation par un lien
(flux L4 réutilisé : page publique, checkout, webhook signé). La suite tourne sous
``egress_guard`` (suite + liste blanche de l'application). Données fictives.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg
import pytest

from api.core.identity import Identity
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
REASON = "Motif fictif espace adhérent — symptôme inventé pour le test"
OCTOBER = date(2026, 10, 1)
START = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
CEILING = 3_000_000  # plafond familial de FAMILLE-OR v1 (jeu de démonstration, proto)
COVERED_48000 = 38_400  # 80 % de 48 000
# Ce que l'adhérent ne doit jamais recevoir : score de fraude, règle interne, revue, médical.
FORBIDDEN_KEYS = frozenset(
    {
        "fraud_score",
        "fraud_flagged",
        "healthos_encounter_ref",
        "evaluation_trace",
        "checks",
        "review_due_at",
        "decided_by",
        "rule_id",
        "params",
        "text",
        "act_code",
    }
)


# --- Aides -----------------------------------------------------------------------------------


def _keys(value: object) -> set[str]:
    """Toutes les clés d'un document JSON, à toute profondeur."""
    if isinstance(value, dict):
        found = set(value)
        for item in value.values():
            found |= _keys(item)
        return found
    if isinstance(value, list):
        return set().union(*(_keys(item) for item in value)) if value else set()
    return set()


def _add_adherent(env: Platform, who: str, org: str, member_id: UUID) -> None:
    """Compte adhérent rattaché à un contrat (inséré en propriétaire, comme ``add_user``)."""
    subject = f"sub-e2e-{who}-{uuid.uuid4().hex[:8]}"
    with psycopg.connect(env.dsn) as conn:
        row = conn.execute(
            "INSERT INTO users (organization_id, idp_subject, display_name) "
            "VALUES (%s, %s, %s) RETURNING id",
            (env.orgs[org], subject, f"Adhérent fictif {who}"),
        ).fetchone()
        assert row is not None
        conn.execute(
            "INSERT INTO user_roles (organization_id, user_id, role, member_id) "
            "VALUES (%s, %s, 'adherent', %s)",
            (env.orgs[org], row[0], member_id),
        )
    env.users[who] = row[0]
    env.tokens[who] = env.idp.issue(Identity(subject=subject, organization_id=env.orgs[org]))


def _enroll(env: Platform, given_name: str, phone: str) -> dict[str, Any]:
    created = env.client.post(
        "/v1/members",
        json={
            "holder": {
                "given_name": given_name,
                "family_name": "Fictif",
                "birth_date": "1988-03-04",
                "phone_e164": phone,
            },
            "plan_code": "FAMILLE-OR",
            "enrolled_on": "2026-07-01",
        },
        headers=env.headers("gestionnaire"),
    )
    assert created.status_code == 201, created.text
    member: dict[str, Any] = created.json()
    _issue_card(env, member["id"], member["holder"]["person_id"])
    return member


def _issue_card(env: Platform, member_id: str, person_id: str) -> None:
    card = env.client.post(
        f"/v1/members/{member_id}/cards",
        json={"person_id": person_id},
        headers=env.headers("gestionnaire"),
    )
    assert card.status_code == 201, card.text


def _my_card(env: Platform, who: str, person_id: str | None = None) -> dict[str, Any]:
    params = {"person_id": person_id} if person_id else None
    response = env.client.get("/v1/me/card", params=params, headers=env.auth(who))
    assert response.status_code == 200, response.text
    card: dict[str, Any] = response.json()
    return card


def _claim(
    env: Platform,
    qr_payload: str,
    phone: str,
    items: list[dict[str, Any]],
    *,
    encounter_ref: str | None = None,
) -> dict[str, Any]:
    """R1 au comptoir avec le QR affiché par l'espace adhérent, puis demande de prise en charge."""
    who = "clinique_a"
    started = env.client.post(
        "/v1/counter/identifications", json={"qr_payload": qr_payload}, headers=env.auth(who)
    )
    assert started.status_code == 201, started.text
    identification = str(started.json()["id"])
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
    body: dict[str, Any] = {
        "identification_id": identification,
        "service_date": env.clock.now().date().isoformat(),
        "items": items,
    }
    if encounter_ref is not None:
        body["healthos_encounter_ref"] = encounter_ref
    response = env.client.post("/v1/claims", json=body, headers=env.headers(who))
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def _contribution_id(env: Platform, member_id: str) -> str:
    return str(
        env.scalar(
            "SELECT id FROM contributions WHERE member_id = %s AND period_start = %s",
            (UUID(member_id), OCTOBER),
        )
    )


def _links_of(env: Platform, contribution_id: str) -> int:
    return int(
        env.scalar(
            "SELECT count(*) FROM payment_links WHERE contribution_id = %s",
            (UUID(contribution_id),),
        )
    )


# --- Jeu de données : deux adhérents de la même organisation, un adhérent de B ---------------


@pytest.fixture(scope="module")
def space(platform: Platform) -> dict[str, Any]:
    env = platform
    env.clock.current = START
    phone_a, phone_a2 = "+2250700007701", "+2250700007702"
    member_a = _enroll(env, "Awa", phone_a)
    child = env.client.post(
        f"/v1/members/{member_a['id']}/dependents",
        json={
            "person": {"given_name": "Enfant", "family_name": "Fictif", "birth_date": "2019-02-02"},
            "relationship": "enfant",
            "valid_from": "2026-07-01",
        },
        headers=env.auth("gestionnaire"),
    )
    assert child.status_code == 201, child.text
    child_person = str(child.json()["person_id"])
    _issue_card(env, member_a["id"], child_person)
    member_a2 = _enroll(env, "Autre", phone_a2)
    # Ayant droit de A' : un filtre par contrat oublié sur les ayants droit le ferait voir à A.
    spouse_a2 = env.client.post(
        f"/v1/members/{member_a2['id']}/dependents",
        json={
            "person": {
                "given_name": "Conjoint",
                "family_name": "Autre",
                "birth_date": "1990-01-01",
            },
            "relationship": "conjoint",
            "valid_from": "2026-07-01",
        },
        headers=env.auth("gestionnaire"),
    )
    assert spouse_a2.status_code == 201, spouse_a2.text
    _issue_card(env, member_a2["id"], str(spouse_a2.json()["person_id"]))

    env.run(run_daily, env.database, ORG_A, env.clock.now())  # carence écoulée : actifs
    env.run(issue_month, env.database, ORG_A, OCTOBER, env.clock.now())

    _add_adherent(env, "adherent_a", "a", UUID(member_a["id"]))
    _add_adherent(env, "adherent_a2", "a", UUID(member_a2["id"]))
    member_b = UUID(
        str(env.scalar("SELECT id FROM members WHERE organization_id = %s", (env.orgs["b"],)))
    )
    _add_adherent(env, "adherent_b", "b", member_b)

    # Dossiers de A : QR affiché par l'espace adhérent, scanné par la clinique.
    pseudonym = env.scalar(
        "SELECT healthos_pseudonym FROM persons WHERE id = %s",
        (UUID(member_a["holder"]["person_id"]),),
    )
    ref = f"enc-p1-{uuid.uuid4().hex[:8]}"
    env.healthos.add_patient(
        pseudonym=pseudonym,
        healthos_id=f"pat-{ref}",
        given_name="Awa",
        family_name="Fictif",
        phone=phone_a,
        birth_date="1988-03-04",
    )
    env.healthos.add_encounter(
        ref=ref,
        pseudonym=pseudonym,
        status="finished",
        start="2026-10-01T08:30:00Z",
        facility_ref="Organization/fac-p1",
        reason=REASON,
    )
    qr_a = _my_card(env, "adherent_a")["qr_payload"]
    auto = _claim(env, qr_a, phone_a, ITEMS_48000)
    review = _claim(env, qr_a, phone_a, ITEMS_185000, encounter_ref=ref)
    refused = _claim(env, qr_a, phone_a, ITEMS_185000)
    decided = env.client.post(
        f"/v1/claims/{refused['claim']['id']}/decisions",
        json={"decision": "refuser", "reason_code": "MC-02"},
        headers=env.headers("medecin_conseil"),
    )
    assert decided.status_code == 200, decided.text
    child_qr = _my_card(env, "adherent_a", child_person)["qr_payload"]
    child_claim = _claim(env, child_qr, phone_a, ITEMS_48000)
    # Dossier de A' (même organisation).
    other = _claim(env, _my_card(env, "adherent_a2")["qr_payload"], phone_a2, ITEMS_48000)
    claim_b = str(env.scalar("SELECT id FROM claims WHERE organization_id = %s", (env.orgs["b"],)))
    return {
        "member_a": member_a,
        "member_a2": member_a2,
        "member_b": member_b,
        "child_person": child_person,
        "phone_a": phone_a,
        "encounter_ref": ref,
        "auto": auto["claim"],
        "review": review["claim"],
        "refused": refused["claim"],
        "child_claim": child_claim["claim"],
        "other": other["claim"],
        "claim_b": claim_b,
        "spouse_a2": str(spouse_a2.json()["person_id"]),
    }


# --- Ma carte ----------------------------------------------------------------------------------


def test_ma_carte_qr_dynamique_droits_et_plafond_restant(
    platform: Platform, space: dict[str, Any]
) -> None:
    env = platform
    response = env.client.get("/v1/me/card", headers=env.auth("adherent_a"))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    card = response.json()
    holder = space["member_a"]["holder"]
    assert card["person_id"] == holder["person_id"]
    assert card["relationship"] == "titulaire"
    assert card["member_number"] == space["member_a"]["member_number"]
    assert (card["plan_code"], card["coverage_rate_bp"]) == ("FAMILLE-OR", 8000)
    assert card["card_status"] == "active"
    assert card["beneficiaries_count"] == 2
    assert card["qr_payload"].startswith("MC1.")
    assert datetime.fromisoformat(card["qr_refresh_at"]) > datetime.fromisoformat(
        card["qr_generated_at"]
    )
    rights = card["entitlements"]
    assert rights["member_id"] == space["member_a"]["id"]
    assert (rights["status"], rights["rights_open"]) == ("actif", True)
    # Plafond familial : dossiers accordés de A et de son enfant, jamais ceux de A'.
    consumed = 2 * COVERED_48000
    assert (rights["family_annual_ceiling_xof"], rights["consumed_xof"]) == (CEILING, consumed)
    assert rights["remaining_xof"] == CEILING - consumed
    assert all(
        isinstance(rights[k], int) and not isinstance(rights[k], bool)
        for k in ("family_annual_ceiling_xof", "consumed_xof", "remaining_xof")
    )
    assert rights["currency"] == "XOF"


def test_le_qr_de_l_espace_adherent_est_accepte_au_comptoir_et_tourne(
    platform: Platform, space: dict[str, Any]
) -> None:
    env = platform
    first = _my_card(env, "adherent_a")
    scanned = env.client.post(
        "/v1/counter/identifications",
        json={"qr_payload": first["qr_payload"]},
        headers=env.auth("clinique_a"),
    )
    assert scanned.status_code == 201, scanned.text
    assert scanned.json()["qr_verified"] is True
    assert scanned.json()["beneficiary"]["person_id"] == space["member_a"]["holder"]["person_id"]

    env.clock.advance(timedelta(seconds=30))
    second = _my_card(env, "adherent_a")
    assert second["qr_payload"] != first["qr_payload"]
    assert second["card_id"] == first["card_id"]


def test_carte_d_un_beneficiaire_du_contrat_seulement(
    platform: Platform, space: dict[str, Any]
) -> None:
    env = platform
    child = _my_card(env, "adherent_a", space["child_person"])
    assert (child["person_id"], child["relationship"]) == (space["child_person"], "enfant")
    for foreign in (
        space["member_a2"]["holder"]["person_id"],
        space["spouse_a2"],
        str(uuid.uuid4()),
    ):
        refused = env.client.get(
            "/v1/me/card", params={"person_id": foreign}, headers=env.auth("adherent_a")
        )
        assert refused.status_code == 404, refused.text
        assert refused.json()["code"] == "NOT-01"
        assert "qr_payload" not in refused.text


# --- Mes bénéficiaires -------------------------------------------------------------------------


def test_mes_beneficiaires(platform: Platform, space: dict[str, Any]) -> None:
    env = platform
    response = env.client.get("/v1/me/beneficiaries", headers=env.auth("adherent_a"))
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [(b["person_id"], b["relationship"], b["card_status"]) for b in items] == [
        (space["member_a"]["holder"]["person_id"], "titulaire", "active"),
        (space["child_person"], "enfant", "active"),
    ]
    assert space["member_a2"]["holder"]["person_id"] not in response.text
    assert space["spouse_a2"] not in response.text


# --- Mes prises en charge ----------------------------------------------------------------------


def test_mes_prises_en_charge_sans_motif_medical_ni_score_de_fraude(
    platform: Platform, space: dict[str, Any]
) -> None:
    env = platform
    response = env.client.get("/v1/me/claims", headers=env.auth("adherent_a"))
    assert response.status_code == 200, response.text
    body = response.json()
    numbers = {c["claim_number"] for c in body["items"]}
    expected = {space[k]["claim_number"] for k in ("auto", "review", "refused", "child_claim")}
    assert numbers == expected
    assert space["other"]["claim_number"] not in response.text
    assert not _keys(body) & FORBIDDEN_KEYS
    assert REASON not in response.text
    assert space["encounter_ref"] not in response.text
    by_number = {c["claim_number"]: c for c in body["items"]}
    auto = by_number[space["auto"]["claim_number"]]
    assert auto["status"] == "accordee_auto"
    assert auto["rule"] == {"code": "R-12", "version": 3}
    assert (auto["total_xof"], auto["covered_xof"], auto["patient_share_xof"]) == (
        48000,
        COVERED_48000,
        48000 - COVERED_48000,
    )
    child = by_number[space["child_claim"]["claim_number"]]
    assert child["beneficiary_person_id"] == space["child_person"]
    assert child["beneficiary_given_name"] == "Enfant"


def test_mes_prises_en_charge_pagination(platform: Platform, space: dict[str, Any]) -> None:
    env = platform
    seen: list[str] = []
    cursor: str | None = None
    for _ in range(10):
        params: dict[str, Any] = {"limit": 1}
        if cursor:
            params["cursor"] = cursor
        page = env.client.get("/v1/me/claims", params=params, headers=env.auth("adherent_a"))
        assert page.status_code == 200, page.text
        seen += [c["id"] for c in page.json()["items"]]
        cursor = page.json()["page"]["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 4
    assert space["other"]["id"] not in seen


def _steps(env: Platform, who: str, claim_id: str) -> list[dict[str, Any]]:
    response = env.client.get(f"/v1/me/claims/{claim_id}/tracking", headers=env.auth(who))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["claim"]["id"] == claim_id
    assert not _keys(body) & FORBIDDEN_KEYS
    assert REASON not in response.text
    steps: list[dict[str, Any]] = body["steps"]
    assert [s["key"] for s in steps] == ["demande_recue", "accordee", "virement", "recu"]
    return steps


def test_suivi_d_un_remboursement_accorde_en_etapes(
    platform: Platform, space: dict[str, Any]
) -> None:
    steps = _steps(platform, "adherent_a", space["auto"]["id"])
    assert [s["state"] for s in steps] == ["fait", "fait", "en_cours", "a_venir"]
    assert steps[0]["at"] is not None
    assert steps[1]["rule"] == {"code": "R-12", "version": 3}
    assert steps[1]["at"] is not None


def test_suivi_d_un_dossier_en_revue(platform: Platform, space: dict[str, Any]) -> None:
    steps = _steps(platform, "adherent_a", space["review"]["id"])
    assert [s["state"] for s in steps] == ["fait", "en_cours", "a_venir", "a_venir"]
    assert steps[1]["rule"] == {"code": "R-20", "version": 2}


def test_suivi_d_un_dossier_refuse(platform: Platform, space: dict[str, Any]) -> None:
    steps = _steps(platform, "adherent_a", space["refused"]["id"])
    assert [s["state"] for s in steps] == ["fait", "refuse", "sans_objet", "sans_objet"]
    assert steps[1]["reason_code"] == "MC-02"
    assert steps[1]["rule"] is None


def test_suivi_d_un_dossier_d_un_autre_adherent_introuvable(
    platform: Platform, space: dict[str, Any]
) -> None:
    env = platform
    for who, claim_id in (
        ("adherent_a", space["other"]["id"]),  # A' de la même organisation
        ("adherent_a", space["claim_b"]),  # organisation B
        ("adherent_a2", space["auto"]["id"]),
        ("adherent_b", space["auto"]["id"]),
    ):
        response = env.client.get(f"/v1/me/claims/{claim_id}/tracking", headers=env.auth(who))
        assert response.status_code == 404, (who, response.text)
        assert response.json()["code"] == "NOT-01"


def test_l_adherent_d_une_autre_organisation_ne_voit_que_les_siens(
    platform: Platform, space: dict[str, Any]
) -> None:
    env = platform
    response = env.client.get("/v1/me/claims", headers=env.auth("adherent_b"))
    assert response.status_code == 200, response.text
    ids = {c["id"] for c in response.json()["items"]}
    assert ids == {space["claim_b"]}
    beneficiaries = env.client.get("/v1/me/beneficiaries", headers=env.auth("adherent_b"))
    assert beneficiaries.status_code == 200, beneficiaries.text
    assert space["member_a"]["holder"]["person_id"] not in beneficiaries.text


# --- Cotisations et lien « inviter un proche à payer » -----------------------------------------


def test_mes_cotisations_et_l_echeance(platform: Platform, space: dict[str, Any]) -> None:
    env = platform
    response = env.client.get("/v1/me/contributions", headers=env.auth("adherent_a"))
    assert response.status_code == 200, response.text
    body = response.json()
    own = _contribution_id(env, space["member_a"]["id"])
    assert [c["id"] for c in body["items"]] == [own]
    assert body["next_due"]["id"] == own
    assert (body["next_due"]["amount_xof"], body["next_due"]["currency"]) == (27500, "XOF")
    assert body["next_due"]["due_on"] == OCTOBER.isoformat()
    assert _contribution_id(env, space["member_a2"]["id"]) not in response.text


def test_inviter_un_proche_a_payer_ouvre_le_flux_diaspora(
    platform: Platform, space: dict[str, Any]
) -> None:
    env = platform
    contribution = _contribution_id(env, space["member_a"]["id"])
    headers = env.headers("adherent_a")
    link = env.client.post(f"/v1/me/contributions/{contribution}/payment-links", headers=headers)
    assert link.status_code == 201, link.text
    replay = env.client.post(f"/v1/me/contributions/{contribution}/payment-links", headers=headers)
    assert replay.status_code == 201, replay.text
    assert replay.json() == link.json()
    assert _links_of(env, contribution) == 1

    token = str(link.json()["url"]).rsplit("/", 1)[1]
    public = env.client.get(f"/v1/public/payment-links/{token}")
    assert public.status_code == 200, public.text
    assert public.json()["holder_initials"] == "A. F."
    assert public.json()["amount_xof"] == 27500
    checkout = env.client.post(
        f"/v1/public/payment-links/{token}/checkout",
        json={"channel": "wave", "payer_country_code": "FR"},
        headers={"Idempotency-Key": f"cle-{uuid.uuid4().hex}"},
    )
    assert checkout.status_code == 201, checkout.text
    note = env.wave.notification(UUID(checkout.json()["payment_id"]), occurred_at=env.clock.now())
    hook = env.client.post(
        f"/v1/webhooks/{ORG_A_SLUG}/payments/wave",
        content=note.body,
        headers={"Content-Type": "application/json", "X-Signature": note.signature},
    )
    assert hook.status_code == 200, hook.text

    after = env.client.get("/v1/me/contributions", headers=env.auth("adherent_a")).json()
    paid = after["items"][0]
    assert (paid["status"], paid["channel"]) == ("payee", "wave")
    assert (paid["payer_kind"], paid["payer_country_code"]) == ("proche", "FR")
    assert after["next_due"] is None


def test_lien_de_paiement_refuse_pour_la_cotisation_d_un_autre_adherent(
    platform: Platform, space: dict[str, Any]
) -> None:
    env = platform
    foreign = _contribution_id(env, space["member_a2"]["id"])
    # A' crée un lien avec sa clé : A rejoue la même clé sur la cotisation de A'.
    key = f"cle-{uuid.uuid4().hex}"
    mine = env.client.post(
        f"/v1/me/contributions/{foreign}/payment-links",
        headers=env.auth("adherent_a2") | {"Idempotency-Key": key},
    )
    assert mine.status_code == 201, mine.text
    before = _links_of(env, foreign)
    for headers in (
        env.auth("adherent_a") | {"Idempotency-Key": key},
        env.headers("adherent_a"),
        env.headers("adherent_b"),
    ):
        stolen = env.client.post(f"/v1/me/contributions/{foreign}/payment-links", headers=headers)
        assert stolen.status_code == 404, stolen.text
        assert stolen.json()["code"] == "NOT-01"
        assert mine.json()["url"] not in stolen.text
    assert _links_of(env, foreign) == before


# --- Rôles ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/v1/members"),
        ("get", "/v1/claims"),
        ("get", "/v1/work-queue"),
        ("get", "/v1/ledger/accounts"),
        ("get", "/v1/search?q=Awa"),
    ],
)
def test_l_adherent_n_a_aucune_operation_de_gestion(
    platform: Platform, space: dict[str, Any], method: str, path: str
) -> None:
    del space
    response = platform.client.request(method, path, headers=platform.auth("adherent_a"))
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "AUTH-02"


def test_l_adherent_ne_lit_pas_les_fiches_par_identifiant(
    platform: Platform, space: dict[str, Any]
) -> None:
    env = platform
    member_id = space["member_a"]["id"]
    for path in (
        f"/v1/members/{member_id}",
        f"/v1/members/{member_id}/entitlements",
        f"/v1/members/{member_id}/contributions",
        f"/v1/claims/{space['auto']['id']}",
        f"/v1/claims/{space['auto']['id']}/medical-reason",
    ):
        response = env.client.get(path, headers=env.auth("adherent_a"))
        assert response.status_code == 403, (path, response.text)


@pytest.mark.parametrize("who", ["gestionnaire", "medecin_conseil", "clinique_a"])
def test_l_espace_adherent_est_reserve_au_role_adherent(
    platform: Platform, space: dict[str, Any], who: str
) -> None:
    del space
    for path in ("/v1/me/card", "/v1/me/beneficiaries", "/v1/me/claims", "/v1/me/contributions"):
        response = platform.client.get(path, headers=platform.auth(who))
        assert response.status_code == 403, (who, path, response.text)
        assert response.json()["code"] == "AUTH-02"


def test_mon_compte_porte_le_role_adherent_et_son_contrat(
    platform: Platform, space: dict[str, Any]
) -> None:
    env = platform
    response = env.client.get("/v1/me", headers=env.auth("adherent_a"))
    assert response.status_code == 200, response.text
    assert response.json()["roles"] == [
        {
            "role": "adherent",
            "provider_id": None,
            "employer_id": None,
            "member_id": space["member_a"]["id"],
        }
    ]


def test_sans_jeton_rien(platform: Platform, space: dict[str, Any]) -> None:
    del space
    response = platform.client.get("/v1/me/card")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH-01"
