"""R2 — adhérents, ayants droit, statuts (actif, carence, suspendu), changeMemberStatus.

Tout passe par l'API réelle sous le rôle ``mulema_app`` (RLS forcée).
"""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta
from uuid import UUID

from api.members.tests.support import (
    L4Env,
    active_member,
    assert_payload_conforms,
    enroll,
    events,
    issue_month,
    run_daily,
)


def test_adhesion_cree_le_titulaire_en_carence_avec_historique_et_evenement(
    guarded: L4Env,
) -> None:
    env = guarded
    env.clock.set_day(date(2026, 10, 1))
    member = enroll(env, "a", date(2026, 10, 1))

    assert re.fullmatch(r"MC-[0-9]{8}", member["member_number"])
    assert member["status"] == "carence"
    assert member["plan_code"] == "FORMULE-T"
    assert member["enrolled_on"] == "2026-10-01"
    # Carence de 60 jours portée par la version de produit en vigueur à l'adhésion.
    assert member["waiting_period_ends_on"] == "2026-11-30"
    assert member["holder"]["family_name"] == "Koné"
    assert member["dependents"] == []

    history = env.rows(
        "SELECT from_status, to_status, reason_code FROM member_status_history "
        "WHERE member_id = %s",
        (UUID(member["id"]),),
    )
    assert history == [(None, "carence", "adhesion")]
    emitted = events(env, "member.status_changed", member_id=member["id"])
    assert len(emitted) == 1
    assert emitted[0]["payload"]["to_status"] == "carence"
    assert emitted[0]["payload"]["reason_code"] == "adhesion"
    assert emitted[0]["published_at"] is None
    assert_payload_conforms("member.status_changed", emitted[0]["payload"])


def test_adhesion_idempotente_par_cle_stockee(guarded: L4Env) -> None:
    env = guarded
    body = {
        "holder": {"given_name": "Moussa", "family_name": "Diallo", "birth_date": "1985-02-03"},
        "plan_code": "FORMULE-T",
        "enrolled_on": "2026-10-01",
    }
    headers = env.headers("a", "gestionnaire")
    first = env.client.post("/v1/members", json=body, headers=headers)
    again = env.client.post("/v1/members", json=body, headers=headers)
    assert first.status_code == again.status_code == 201
    assert first.json()["id"] == again.json()["id"]
    assert (
        env.scalar(
            "SELECT count(*) FROM members m JOIN persons p ON p.id = m.person_id "
            "WHERE p.family_name = 'Diallo' AND m.organization_id = %s",
            (env.orgs["a"].id,),
        )
        == 1
    )

    other = {**body, "enrolled_on": "2026-10-02"}
    conflict = env.client.post("/v1/members", json=other, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEM-01"


def test_adhesion_refuse_une_formule_inconnue(guarded: L4Env) -> None:
    env = guarded
    response = env.client.post(
        "/v1/members",
        json={
            "holder": {"given_name": "A", "family_name": "B", "birth_date": "1990-01-01"},
            "plan_code": "INCONNUE",
            "enrolled_on": "2026-10-01",
        },
        headers=env.headers("a", "gestionnaire"),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-01"
    assert response.json()["errors"][0]["field"] == "plan_code"


def test_ayant_droit_ajoute_et_visible_sur_la_fiche(guarded: L4Env) -> None:
    env = guarded
    member = enroll(env, "a", date(2026, 9, 1))
    response = env.client.post(
        f"/v1/members/{member['id']}/dependents",
        json={
            "person": {"given_name": "Ibrahim", "family_name": "Koné", "birth_date": "2019-04-01"},
            "relationship": "enfant",
            "valid_from": "2026-09-01",
        },
        headers=env.auth("a", "gestionnaire"),
    )
    assert response.status_code == 201, response.text
    dependent = response.json()
    assert dependent["relationship"] == "enfant"
    assert dependent["valid_to"] is None

    fiche = env.client.get(f"/v1/members/{member['id']}", headers=env.auth("a", "gestionnaire"))
    assert fiche.status_code == 200
    assert [d["person_id"] for d in fiche.json()["dependents"]] == [dependent["person_id"]]


def test_liste_filtree_par_statut_et_recherche(guarded: L4Env) -> None:
    env = guarded
    marker = f"Zz{uuid.uuid4().hex[:6]}"
    member = enroll(env, "a", date(2026, 10, 1), family=marker)
    response = env.client.get(
        "/v1/members",
        params={"q": marker, "status": "carence"},
        headers=env.auth("a", "gestionnaire"),
    )
    assert response.status_code == 200
    assert [m["id"] for m in response.json()["items"]] == [member["id"]]
    none = env.client.get(
        "/v1/members",
        params={"q": marker, "status": "actif"},
        headers=env.auth("a", "gestionnaire"),
    )
    assert none.json()["items"] == []
    by_number = env.client.get(
        "/v1/members", params={"q": member["member_number"]}, headers=env.auth("a", "gestionnaire")
    )
    assert [m["id"] for m in by_number.json()["items"]] == [member["id"]]


def test_liste_paginee_par_curseur(guarded: L4Env) -> None:
    env = guarded
    marker = f"Pg{uuid.uuid4().hex[:6]}"
    created = {enroll(env, "a", date(2026, 10, 1), family=marker)["id"] for _ in range(3)}
    seen: list[str] = []
    cursor: str | None = None
    for _ in range(4):
        params: dict[str, str | int] = {"q": marker, "limit": 2}
        if cursor:
            params["cursor"] = cursor
        page = env.client.get("/v1/members", params=params, headers=env.auth("a", "gestionnaire"))
        assert page.status_code == 200
        seen += [m["id"] for m in page.json()["items"]]
        cursor = page.json()["page"]["next_cursor"]
        if cursor is None:
            break
    assert sorted(seen) == sorted(created)


def test_fin_de_carence_automatique(guarded: L4Env) -> None:
    env = guarded
    env.clock.set_day(date(2026, 10, 1))
    member = enroll(env, "a", date(2026, 10, 1))
    env.clock.set_day(date(2026, 11, 29))
    run_daily(env, "a")
    assert env.scalar("SELECT status FROM members WHERE id = %s", (UUID(member["id"]),)) == (
        "carence"
    )
    env.clock.set_day(date(2026, 11, 30))
    run_daily(env, "a")
    assert env.scalar("SELECT status FROM members WHERE id = %s", (UUID(member["id"]),)) == "actif"
    emitted = events(env, "member.status_changed", member_id=member["id"])
    assert [e["payload"]["reason_code"] for e in emitted] == ["adhesion", "fin_de_carence"]


def test_droits_a_une_date(guarded: L4Env) -> None:
    env = guarded
    env.clock.set_day(date(2026, 10, 1))
    member = active_member(env, "a")
    response = env.client.get(
        f"/v1/members/{member['id']}/entitlements",
        params={"at": "2026-10-01"},
        headers=env.auth("a", "medecin_conseil"),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "actif"
    assert body["rights_open"] is True
    assert body["family_annual_ceiling_xof"] == 3_000_000
    assert body["consumed_xof"] == 0
    assert body["remaining_xof"] == 3_000_000
    assert body["currency"] == "XOF"

    # Avant l'adhésion : aucun droit.
    before = env.client.get(
        f"/v1/members/{member['id']}/entitlements",
        params={"at": (date.fromisoformat(member["enrolled_on"]) - timedelta(days=1)).isoformat()},
        headers=env.auth("a", "gestionnaire"),
    )
    assert before.json()["rights_open"] is False


def test_changement_de_statut_par_le_gestionnaire_audite_et_publie(guarded: L4Env) -> None:
    env = guarded
    env.clock.set_day(date(2026, 10, 1))
    member = active_member(env, "a")
    response = env.client.post(
        f"/v1/members/{member['id']}/status-changes",
        json={"to_status": "suspendu"},
        headers=env.headers("a", "gestionnaire"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "suspendu"

    history = env.rows(
        "SELECT from_status, to_status, reason_code, actor_user_id FROM member_status_history "
        "WHERE member_id = %s ORDER BY occurred_at, id",
        (UUID(member["id"]),),
    )
    assert history[-1] == (
        "actif",
        "suspendu",
        "decision_gestionnaire",
        env.orgs["a"].users["gestionnaire"],
    )
    audit = env.rows(
        "SELECT action, actor_user_id FROM audit_events WHERE target_id = %s",
        (UUID(member["id"]),),
    )
    assert audit == [("member.status_changed", env.orgs["a"].users["gestionnaire"])]
    emitted = events(env, "member.status_changed", member_id=member["id"])
    last = emitted[-1]["payload"]
    assert last["reason_code"] == "decision_gestionnaire"
    assert last["actor_user_id"] == str(env.orgs["a"].users["gestionnaire"])
    assert_payload_conforms("member.status_changed", last)

    same = env.client.post(
        f"/v1/members/{member['id']}/status-changes",
        json={"to_status": "suspendu"},
        headers=env.headers("a", "gestionnaire"),
    )
    assert same.status_code == 409
    assert same.json()["code"] == "MBR-01"

    # Retour à « actif » autorisé : aucune cotisation impayée.
    back = env.client.post(
        f"/v1/members/{member['id']}/status-changes",
        json={"to_status": "actif"},
        headers=env.headers("a", "gestionnaire"),
    )
    assert back.status_code == 200
    assert back.json()["status"] == "actif"


def test_reactivation_refusee_tant_que_l_impaye_depasse_le_seuil(guarded: L4Env) -> None:
    env = guarded
    env.clock.set_day(date(2026, 10, 1))
    member = active_member(env, "a")
    issue_month(env, "a", date(2026, 10, 1))
    env.clock.set_day(date(2026, 11, 20))
    run_daily(env, "a")
    refused = env.client.post(
        f"/v1/members/{member['id']}/status-changes",
        json={"to_status": "actif"},
        headers=env.headers("a", "gestionnaire"),
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "MBR-01"


def test_carence_vers_actif_refuse_avant_la_fin_du_delai(guarded: L4Env) -> None:
    env = guarded
    env.clock.set_day(date(2026, 10, 1))
    member = enroll(env, "a", date(2026, 10, 1))
    refused = env.client.post(
        f"/v1/members/{member['id']}/status-changes",
        json={"to_status": "actif"},
        headers=env.headers("a", "gestionnaire"),
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "MBR-01"


def test_roles_hors_contrat_refuses(guarded: L4Env) -> None:
    env = guarded
    member = enroll(env, "a", date(2026, 10, 1))
    assert env.client.get("/v1/members", headers=env.auth("a", "clinique")).status_code == 403
    assert (
        env.client.get(
            f"/v1/members/{member['id']}", headers=env.auth("a", "medecin_conseil")
        ).json()["code"]
        == "AUTH-02"
    )
    assert env.client.get("/v1/members").status_code == 401


def test_isolation_un_gestionnaire_de_b_ne_voit_rien_de_a(guarded: L4Env) -> None:
    env = guarded
    env.clock.set_day(date(2026, 10, 1))
    member = active_member(env, "a")
    issue_month(env, "a", date(2026, 10, 1))
    b = env.auth("b", "gestionnaire")
    member_id = member["id"]
    for path in (
        f"/v1/members/{member_id}",
        f"/v1/members/{member_id}/entitlements",
        f"/v1/members/{member_id}/contributions",
    ):
        response = env.client.get(path, headers=b)
        assert response.status_code == 404, path
        assert response.json()["code"] == "NOT-01"
    listing = env.client.get("/v1/members", params={"q": member["member_number"]}, headers=b)
    assert listing.json()["items"] == []
    for path, body in (
        (f"/v1/members/{member_id}/status-changes", {"to_status": "suspendu"}),
        (f"/v1/members/{member_id}/cards", {"person_id": member["holder"]["person_id"]}),
        (f"/v1/members/{member_id}/reminders", {"channel": "sms", "template_code": "relance"}),
    ):
        response = env.client.post(path, json=body, headers=env.headers("b", "gestionnaire"))
        assert response.status_code == 404, path
    dependent = env.client.post(
        f"/v1/members/{member_id}/dependents",
        json={
            "person": {"given_name": "X", "family_name": "Y", "birth_date": "2020-01-01"},
            "relationship": "enfant",
            "valid_from": "2026-10-01",
        },
        headers=b,
    )
    assert dependent.status_code == 404
    assert env.scalar("SELECT status FROM members WHERE id = %s", (UUID(member_id),)) == "actif"
