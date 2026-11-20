"""R3 par l'API assemblée : règle modifiée le 01/01, soin du 20/12 traité le 05/01.

Le 01/10/2026, l'admin publie R-12 v4 (seuil 40 000 FCFA) et la version 3 de FAMILLE-OR, toutes
deux à date d'effet future (01/01/2027). Le 05/01/2027, un soin du 20/12/2026 de 48 000 FCFA est
évalué avec R-12 v3 et la version 2 du produit (accordé) ; le même soin daté du 05/01/2027 l'est
avec R-12 v4 et la version 3 (revue). Module à part : il modifie les versions de sa base.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final

from api.rules.tests.conftest import DEMO_PLAN_V2, DEMO_PLAN_V3, Platform, add_insured
from api.rules.tests.test_routes import ITEMS_48000, call, ok, problem

PROCESSING_DAY: Final = datetime(2027, 1, 5, 10, 0, tzinfo=UTC)


def _evaluate(env: Platform, body: dict[str, Any], service_date: str) -> dict[str, Any]:
    decision: dict[str, Any] = ok(
        call(env, "gestionnaire", "POST", "/v1/rules/evaluation",
             body | {"service_date": service_date}),
        200,
    )  # fmt: skip
    return decision


def test_soin_du_20_12_traite_le_05_01_avec_les_versions_du_20_12(l2: Platform) -> None:
    env = l2
    insured = add_insured(env, "MC-90000101")
    body = {
        "member_id": str(insured.member_id),
        "beneficiary_id": str(insured.person_id),
        "provider_id": str(env.providers["a"]),
        "items": ITEMS_48000,
        "fraud_score": 0.06,
    }

    # 01/10/2026 : publication à date d'effet future (règle et produit).
    draft = ok(
        call(env, "admin_a", "POST", "/v1/rules/R-12/versions",
             {"valid_from": "2027-01-01",
              "params": {"total_max_exclu_xof": 40_000, "score_fraude_max_exclu": 0.2}}),
        201,
    )  # fmt: skip
    published = ok(
        call(env, "admin_a", "POST", f"/v1/rule-versions/{draft['id']}/publication"), 200
    )
    assert (published["version"], published["state"]) == (4, "en_vigueur")
    plan_v3 = ok(call(env, "admin_a", "POST", f"/v1/plan-versions/{DEMO_PLAN_V3}/publication"), 200)
    assert plan_v3["state"] == "en_vigueur"

    # Aujourd'hui (01/10/2026), la règle courante reste v3, close au 31/12/2026.
    rules = {r["code"]: r for r in ok(call(env, "admin_a", "GET", "/v1/rules"), 200)["items"]}
    assert rules["R-12"]["current_version"]["version"] == 3
    assert rules["R-12"]["current_version"]["valid_to"] == "2026-12-31"

    # 05/01/2027 : traitement.
    env.clock.current = PROCESSING_DAY
    try:
        december = _evaluate(env, body, "2026-12-20")
        january = _evaluate(env, body, "2027-01-05")
        rules = {r["code"]: r for r in ok(call(env, "admin_a", "GET", "/v1/rules"), 200)["items"]}
    finally:
        env.clock.current = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)

    assert december["outcome"] == "accordee_auto"
    assert december["rule"] == {"code": "R-12", "version": 3}
    assert december["plan_version_id"] == str(DEMO_PLAN_V2)

    assert january["outcome"] == "en_revue"
    assert january["plan_version_id"] == str(DEMO_PLAN_V3)
    r12_check = next(c for c in january["checks"] if c["rule"]["code"] == "R-12")
    assert r12_check["rule"]["version"] == 4
    assert r12_check["passed"] is False

    assert rules["R-12"]["current_version"]["version"] == 4

    # La version 3 publiée n'a pas bougé (paramètres figés) ; la republier est refusé.
    versions = ok(call(env, "admin_a", "GET", "/v1/rules/R-12/versions"), 200)["items"]
    v3 = next(v for v in versions if v["version"] == 3)
    assert v3["params"] == {"total_max_exclu_xof": 50_000, "score_fraude_max_exclu": 0.2}
    problem(
        call(env, "admin_a", "POST", f"/v1/rule-versions/{v3['id']}/publication"), 409, "RUL-01"
    )
