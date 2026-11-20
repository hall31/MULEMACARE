"""R8 — suspension automatique à J+45 d'impayé (seuil lu dans R-01, en données).

La cotisation d'octobre est due le 01/10. Le traitement quotidien la laisse « actif » à J+44
(14/11) et suspend à J+45 (15/11), avec historique, événement et règle R-01 citée.
"""

from __future__ import annotations

import json
from datetime import date
from uuid import UUID

import psycopg

from api.members.tests.support import (
    L4Env,
    active_member,
    assert_payload_conforms,
    contribution_of,
    events,
    issue_month,
    run_daily,
)

OCTOBER = date(2026, 10, 1)


def _status(env: L4Env, member_id: str) -> str:
    value = env.scalar("SELECT status FROM members WHERE id = %s", (UUID(member_id),))
    assert isinstance(value, str)
    return value


def _rights(env: L4Env, member_id: str, at: date) -> bool:
    response = env.client.get(
        f"/v1/members/{member_id}/entitlements",
        params={"at": at.isoformat()},
        headers=env.auth("a", "gestionnaire"),
    )
    assert response.status_code == 200, response.text
    value = response.json()["rights_open"]
    assert isinstance(value, bool)
    return value


def test_suspension_a_j_plus_45_et_pas_avant(guarded: L4Env) -> None:
    env = guarded
    env.clock.set_day(OCTOBER)
    member = active_member(env, "a")
    assert issue_month(env, "a", OCTOBER) >= 1
    contribution = contribution_of(env, member["id"], OCTOBER)
    assert env.rows(
        "SELECT due_on, amount_xof, status FROM contributions WHERE id = %s", (contribution,)
    ) == [(OCTOBER, 27500, "a_payer")]

    env.clock.set_day(date(2026, 11, 14))  # J+44
    run_daily(env, "a")
    assert _status(env, member["id"]) == "actif"
    assert _rights(env, member["id"], date(2026, 11, 14)) is True
    assert env.scalar("SELECT status FROM contributions WHERE id = %s", (contribution,)) == (
        "en_retard"
    )

    env.clock.set_day(date(2026, 11, 15))  # J+45
    report = run_daily(env, "a")
    assert report.suspended >= 1
    assert _status(env, member["id"]) == "suspendu"
    assert _rights(env, member["id"], date(2026, 11, 15)) is False
    # La veille, les droits étaient ouverts : la lecture à une date reste rejouable.
    assert _rights(env, member["id"], date(2026, 11, 14)) is True

    history = env.rows(
        "SELECT from_status, to_status, reason_code, actor_user_id FROM member_status_history "
        "WHERE member_id = %s ORDER BY occurred_at, id",
        (UUID(member["id"]),),
    )
    assert history[-1] == ("actif", "suspendu", "impaye", None)
    last = events(env, "member.status_changed", member_id=member["id"])[-1]["payload"]
    assert last["reason_code"] == "impaye"
    assert last["rule"] == {"code": "R-01", "version": 1}
    assert last["actor_user_id"] is None
    assert_payload_conforms("member.status_changed", last)

    # Rejouer le traitement le même jour ne change rien (ni historique, ni événement).
    before = len(events(env, "member.status_changed", member_id=member["id"]))
    run_daily(env, "a")
    assert len(events(env, "member.status_changed", member_id=member["id"])) == before


def test_le_seuil_vient_des_donnees_de_r01(guarded: L4Env) -> None:
    """Une version R-01 v2 à 30 jours, en vigueur depuis le 01/11, suspend dès J+30."""
    env = guarded
    env.clock.set_day(OCTOBER)
    org = env.orgs["a"]
    with psycopg.connect(env.dsn) as conn:
        conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(org.id),))
        conn.execute(
            "UPDATE rule_versions SET valid_to = DATE '2026-10-31' WHERE organization_id = %s "
            "AND version = 1 AND rule_id = (SELECT id FROM rules WHERE organization_id = %s "
            "AND code = 'R-01')",
            (org.id, org.id),
        )
        conn.execute(
            "INSERT INTO rule_versions (organization_id, rule_id, version, valid_from, params, "
            "state) SELECT %s, id, 2, DATE '2026-11-01', %s, 'en_vigueur' FROM rules "
            "WHERE organization_id = %s AND code = 'R-01'",
            (
                org.id,
                json.dumps(
                    {"statuts_ouvrant_droits": ["actif"], "suspension_apres_jours_impayes": 30}
                ),
                org.id,
            ),
        )
    try:
        member = active_member(env, "a")
        issue_month(env, "a", OCTOBER)
        env.clock.set_day(date(2026, 10, 31))  # J+30, mais v1 (45 j) encore en vigueur
        run_daily(env, "a")
        assert _status(env, member["id"]) == "actif"
        env.clock.set_day(date(2026, 11, 1))  # J+31, v2 (30 j) en vigueur
        run_daily(env, "a")
        assert _status(env, member["id"]) == "suspendu"
        last = events(env, "member.status_changed", member_id=member["id"])[-1]["payload"]
        assert last["rule"] == {"code": "R-01", "version": 2}
    finally:
        with psycopg.connect(env.dsn) as conn:
            conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(org.id),))
            # Remise en état du paramétrage partagé du module (propriétaire, hors API).
            conn.execute("ALTER TABLE rule_versions DISABLE TRIGGER rule_versions_frozen")
            conn.execute(
                "DELETE FROM rule_versions WHERE organization_id = %s AND version = 2", (org.id,)
            )
            conn.execute(
                "UPDATE rule_versions SET valid_to = NULL WHERE organization_id = %s "
                "AND version = 1 AND rule_id = (SELECT id FROM rules WHERE organization_id = %s "
                "AND code = 'R-01')",
                (org.id, org.id),
            )
            conn.execute("ALTER TABLE rule_versions ENABLE TRIGGER rule_versions_frozen")


def test_suspension_isolee_par_organisation(guarded: L4Env) -> None:
    """Le traitement de B ne touche pas un adhérent de A, même impayé depuis 45 jours."""
    env = guarded
    env.clock.set_day(OCTOBER)
    member = active_member(env, "a")
    issue_month(env, "a", OCTOBER)
    env.clock.set_day(date(2026, 11, 20))
    run_daily(env, "b")
    assert _status(env, member["id"]) == "actif"
    run_daily(env, "a")
    assert _status(env, member["id"]) == "suspendu"
