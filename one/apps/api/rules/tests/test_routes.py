"""Routes L2 (produits, réseau, barème, règles) sur l'application ASSEMBLÉE, vrais jetons.

Pour CHACUNE des 19 opérations ``x-lot: L2`` du contrat : rôle autorisé (succès), rôle interdit
(403 AUTH-02, rien d'écrit) et isolation A/B (B ne lit ni ne modifie rien de A). Puis : version
publiée immuable (RUL-01), chevauchement (RUL-02), montants entiers, et ``evaluateRules`` qui
décide par le moteur (R4, R5) sans rien écrire.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID

import httpx
import pytest

from api.rules.tests.conftest import DEMO_PLAN, Insured, Platform, add_insured
from api.tests.paths import OPENAPI_YAML

ITEMS_48000: Final = [
    {"act_code": "CONS-GEN", "quantity": 1},
    {"act_code": "BIO-NFS", "quantity": 1},
    {"act_code": "CARD-ECG", "quantity": 1},
]
ITEMS_185000: Final = [
    {"act_code": "CONS-SPE", "quantity": 1},
    {"act_code": "IMG-ECHO-ABD", "quantity": 5},
]
_L2_OPERATION = re.compile(
    r"^\s+operationId:\s*(\w+)\n(?:(?!\s+operationId:).*\n)*?\s+x-lot:\s*L2\s*$", re.MULTILINE
)


def _code(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def call(env: Platform, who: str, method: str, url: str, body: Any = None) -> httpx.Response:  # noqa: ANN401
    response: httpx.Response = env.client.request(method, url, json=body, headers=env.auth(who))
    return response


def ok(response: httpx.Response, expected: int) -> Any:  # noqa: ANN401
    assert response.status_code == expected, response.text
    return response.json()


def problem(response: httpx.Response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == code, body
    assert body["message"]
    assert body["action"]


def version_body(valid_from: str, **overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    body: dict[str, Any] = {
        "valid_from": valid_from,
        "coverage_rate_bp": 8000,
        "family_annual_ceiling_xof": 3_000_000,
        "waiting_period_days": 60,
        "monthly_contribution_xof": 27_500,
        "coverages": [
            {"category": "soins_courants", "label": "Soins courants", "limit_scope": "famille"}
        ],
    }
    return body | overrides


@dataclass(frozen=True, slots=True)
class Ids:
    plan_id: str
    plan_version_id: str
    provider_id: str
    unconventioned_provider_id: str
    act_id: str
    act_code: str
    rule_version_id: str
    insured: Insured


@pytest.fixture(scope="module")
def ids(l2: Platform) -> Ids:
    """Catalogue de A créé par l'API (admin de A)."""
    env = l2
    plan = ok(
        call(env, "admin_a", "POST", "/v1/plans", {"code": _code("P"), "name": "Fictif"}), 201
    )
    version = ok(
        call(
            env, "admin_a", "POST", f"/v1/plans/{plan['id']}/versions", version_body("2026-01-01")
        ),
        201,
    )
    provider = ok(
        call(
            env,
            "admin_a",
            "POST",
            "/v1/providers",
            {
                "name": "Clinique fictive L2",
                "kind": "clinique",
                "city": "Abidjan",
                "country_code": "CI",
            },
        ),
        201,
    )
    ok(
        call(env, "admin_a", "POST", f"/v1/providers/{provider['id']}/conventions",
             {"valid_from": "2026-01-01"}),
        201,
    )  # fmt: skip
    outside = ok(
        call(
            env,
            "admin_a",
            "POST",
            "/v1/providers",
            {
                "name": "Cabinet hors réseau",
                "kind": "cabinet",
                "city": "Bouaké",
                "country_code": "CI",
            },
        ),
        201,
    )
    act_code = _code("ACT")
    act = ok(
        call(env, "admin_a", "POST", "/v1/acts",
             {"code": act_code, "label": "Acte fictif", "coverage_category": "soins_courants"}),
        201,
    )  # fmt: skip
    ok(
        call(env, "admin_a", "POST", f"/v1/acts/{act['id']}/tariffs",
             {"amount_xof": 12_000, "valid_from": "2026-01-01"}),
        201,
    )  # fmt: skip
    rule_version = ok(
        call(env, "admin_a", "POST", "/v1/rules/R-20/versions",
             {"valid_from": "2040-01-01", "params": {"delai_cible_minutes": 90}}),
        201,
    )  # fmt: skip
    return Ids(
        plan_id=plan["id"],
        plan_version_id=version["id"],
        provider_id=provider["id"],
        unconventioned_provider_id=outside["id"],
        act_id=act["id"],
        act_code=act_code,
        rule_version_id=rule_version["id"],
        insured=add_insured(env, "MC-90000001"),
    )


def evaluation_body(ids: Ids, items: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:  # noqa: ANN401
    body: dict[str, Any] = {
        "member_id": str(ids.insured.member_id),
        "beneficiary_id": str(ids.insured.person_id),
        "provider_id": str(ids.provider_id),
        "service_date": "2026-10-01",
        "items": items,
    }
    return body | extra


# --- Table des opérations ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Op:
    method: str
    url: Callable[[Ids], str]
    body: Callable[[Ids], Any]
    forbidden: str  # rôle de A hors des x-roles de l'opération
    table: str | None = None  # table qu'une écriture refusée ne doit pas toucher


def _none(_: Ids) -> None:
    return None


OPS: Final[dict[str, Op]] = {
    "listPlans": Op("GET", lambda i: "/v1/plans", _none, "medecin_conseil"),
    "createPlan": Op(
        "POST", lambda i: "/v1/plans", lambda i: {"code": _code("P"), "name": "X"},
        "gestionnaire", "plans",
    ),
    "getPlan": Op("GET", lambda i: f"/v1/plans/{i.plan_id}", _none, "medecin_conseil"),
    "createPlanVersion": Op(
        "POST", lambda i: f"/v1/plans/{i.plan_id}/versions",
        lambda i: version_body("2031-01-01"), "medecin_conseil", "plan_versions",
    ),
    "getPlanVersion": Op(
        "GET", lambda i: f"/v1/plan-versions/{i.plan_version_id}", _none, "medecin_conseil"
    ),
    "publishPlanVersion": Op(
        "POST", lambda i: f"/v1/plan-versions/{i.plan_version_id}/publication", _none,
        "gestionnaire", "plan_versions",
    ),
    "listProviders": Op("GET", lambda i: "/v1/providers", _none, "clinique_a"),
    "createProvider": Op(
        "POST", lambda i: "/v1/providers",
        lambda i: {"name": "N", "kind": "pharmacie", "city": "Abidjan", "country_code": "CI"},
        "medecin_conseil", "providers",
    ),
    "getProvider": Op("GET", lambda i: f"/v1/providers/{i.provider_id}", _none, "clinique_a"),
    "createProviderConvention": Op(
        "POST", lambda i: f"/v1/providers/{i.unconventioned_provider_id}/conventions",
        lambda i: {"valid_from": "2032-01-01"}, "medecin_conseil", "provider_conventions",
    ),
    "listTariffs": Op("GET", lambda i: "/v1/tariffs", _none, "employeur_a"),
    "listActs": Op("GET", lambda i: "/v1/acts", _none, "clinique_a"),
    "createAct": Op(
        "POST", lambda i: "/v1/acts",
        lambda i: {"code": _code("A"), "label": "L", "coverage_category": "soins_courants"},
        "medecin_conseil", "acts",
    ),
    "createTariffItem": Op(
        "POST", lambda i: f"/v1/acts/{i.act_id}/tariffs",
        lambda i: {"amount_xof": 5000, "valid_from": "2033-01-01"},
        "medecin_conseil", "tariff_items",
    ),
    "listRules": Op("GET", lambda i: "/v1/rules", _none, "clinique_a"),
    "listRuleVersions": Op("GET", lambda i: "/v1/rules/R-12/versions", _none, "clinique_a"),
    "createRuleVersion": Op(
        "POST", lambda i: "/v1/rules/R-20/versions",
        lambda i: {"valid_from": "2034-01-01", "params": {"delai_cible_minutes": 60}},
        "gestionnaire", "rule_versions",
    ),
    "publishRuleVersion": Op(
        "POST", lambda i: f"/v1/rule-versions/{i.rule_version_id}/publication", _none,
        "gestionnaire", "rule_versions",
    ),
    "evaluateRules": Op(
        "POST", lambda i: "/v1/rules/evaluation", lambda i: evaluation_body(i, ITEMS_48000),
        "clinique_a",
    ),
}  # fmt: skip


def test_la_table_couvre_exactement_les_operations_l2_du_contrat() -> None:
    contract = set(_L2_OPERATION.findall(OPENAPI_YAML.read_text(encoding="utf-8")))
    assert len(contract) == 19
    assert set(OPS) == contract


def _count(env: Platform, table: str) -> int:
    value = env.scalar(f"SELECT count(*) FROM {table}")  # table de la liste OPS, pas du client
    assert isinstance(value, int)
    return value


def _snapshot(env: Platform, table: str) -> list[tuple[Any, ...]]:
    return env.rows(f"SELECT to_jsonb(t)::text FROM {table} t ORDER BY 1")


# --- Rôle interdit : AUTH-02, rien d'écrit -----------------------------------------------------


@pytest.mark.parametrize("operation", sorted(OPS))
def test_role_interdit_auth_02(l2: Platform, ids: Ids, operation: str) -> None:
    op = OPS[operation]
    before = _snapshot(l2, op.table) if op.table else None
    response = call(l2, op.forbidden, op.method, op.url(ids), op.body(ids))
    problem(response, 403, "AUTH-02")
    if op.table:
        assert _snapshot(l2, op.table) == before


@pytest.mark.parametrize("operation", sorted(OPS))
def test_sans_jeton_auth_01(l2: Platform, ids: Ids, operation: str) -> None:
    op = OPS[operation]
    response = l2.client.request(op.method, op.url(ids), json=op.body(ids))
    problem(response, 401, "AUTH-01")


# --- Isolation A/B -----------------------------------------------------------------------------


def _iso_not_found(env: Platform, ids: Ids, operation: str) -> None:
    """B vise une ressource de A par son identifiant : 404 NOT-01, rien d'écrit chez A."""
    op = OPS[operation]
    before = _snapshot(env, op.table) if op.table else None
    problem(call(env, "admin_b", op.method, op.url(ids), op.body(ids)), 404, "NOT-01")
    if op.table:
        assert _snapshot(env, op.table) == before


def _ids_of(items: list[dict[str, Any]], key: str = "id") -> set[str]:
    return {str(item[key]) for item in items}


def _iso_list_plans(env: Platform, ids: Ids) -> None:
    seen = _ids_of(ok(call(env, "admin_b", "GET", "/v1/plans"), 200)["items"])
    assert seen
    assert ids.plan_id not in seen
    assert str(DEMO_PLAN) not in seen


def _iso_create_plan(env: Platform, ids: Ids) -> None:
    code = ok(call(env, "admin_a", "GET", f"/v1/plans/{ids.plan_id}"), 200)["code"]
    created = ok(call(env, "admin_b", "POST", "/v1/plans", {"code": code, "name": "B"}), 201)
    problem(call(env, "admin_a", "GET", f"/v1/plans/{created['id']}"), 404, "NOT-01")
    assert created["id"] not in _ids_of(ok(call(env, "admin_a", "GET", "/v1/plans"), 200)["items"])


def _iso_list_providers(env: Platform, ids: Ids) -> None:
    page = ok(call(env, "admin_b", "GET", "/v1/providers?limit=200"), 200)
    seen = _ids_of(page["items"])
    assert seen
    assert ids.provider_id not in seen
    assert str(env.providers["a"]) not in seen


def _iso_create_provider(env: Platform, ids: Ids) -> None:
    body = {"name": "Clinique B", "kind": "clinique", "city": "Dakar", "country_code": "SN"}
    created = ok(call(env, "admin_b", "POST", "/v1/providers", body), 201)
    problem(call(env, "admin_a", "GET", f"/v1/providers/{created['id']}"), 404, "NOT-01")


def _iso_list_tariffs(env: Platform, ids: Ids) -> None:
    items = ok(call(env, "admin_b", "GET", "/v1/tariffs?at=2026-10-01"), 200)["items"]
    codes = _ids_of(items, "act_code")
    assert codes == {"CONS-GEN"}  # le seul acte tarifé de B
    assert ids.act_code not in codes


def _iso_list_acts(env: Platform, ids: Ids) -> None:
    mine = ok(call(env, "admin_b", "GET", "/v1/acts"), 200)["items"]
    theirs = ok(call(env, "admin_a", "GET", "/v1/acts"), 200)["items"]
    assert "CONS-GEN" in _ids_of(mine, "code")
    assert not _ids_of(mine) & _ids_of(theirs)
    assert ids.act_id not in _ids_of(mine)


def _iso_create_act(env: Platform, ids: Ids) -> None:
    body = {
        "code": ids.act_code,
        "label": "Même code chez B",
        "coverage_category": "soins_courants",
    }
    created = ok(call(env, "admin_b", "POST", "/v1/acts", body), 201)
    assert created["id"] not in _ids_of(ok(call(env, "admin_a", "GET", "/v1/acts"), 200)["items"])


def _iso_list_rules(env: Platform, ids: Ids) -> None:
    items = ok(call(env, "admin_b", "GET", "/v1/rules"), 200)["items"]
    assert _ids_of(items, "code") == {"R-12"}  # B n'a que R-12
    a_versions = ok(call(env, "admin_a", "GET", "/v1/rules/R-12/versions"), 200)["items"]
    assert items[0]["current_version"]["id"] not in _ids_of(a_versions)


def _iso_list_rule_versions(env: Platform, ids: Ids) -> None:
    problem(call(env, "admin_b", "GET", "/v1/rules/R-20/versions"), 404, "NOT-01")
    mine = _ids_of(ok(call(env, "admin_b", "GET", "/v1/rules/R-12/versions"), 200)["items"])
    theirs = _ids_of(ok(call(env, "admin_a", "GET", "/v1/rules/R-12/versions"), 200)["items"])
    assert len(mine) == 1
    assert not mine & theirs


def _iso_create_rule_version(env: Platform, ids: Ids) -> None:
    _iso_not_found(env, ids, "createRuleVersion")  # B n'a pas de règle R-20


ISOLATION: Final[dict[str, Callable[[Platform, Ids], None]]] = {
    "listPlans": _iso_list_plans,
    "createPlan": _iso_create_plan,
    "listProviders": _iso_list_providers,
    "createProvider": _iso_create_provider,
    "listTariffs": _iso_list_tariffs,
    "listActs": _iso_list_acts,
    "createAct": _iso_create_act,
    "listRules": _iso_list_rules,
    "listRuleVersions": _iso_list_rule_versions,
    "createRuleVersion": _iso_create_rule_version,
}


@pytest.mark.parametrize("operation", sorted(OPS))
def test_isolation_a_b(l2: Platform, ids: Ids, operation: str) -> None:
    check = ISOLATION.get(operation)
    if check is None:  # opération adressée par un identifiant de A
        _iso_not_found(l2, ids, operation)
    else:
        check(l2, ids)


# --- Rôle autorisé : une opération, un test ---------------------------------------------------


def test_list_plans(l2: Platform, ids: Ids) -> None:
    items = ok(call(l2, "gestionnaire", "GET", "/v1/plans"), 200)["items"]
    demo = next(p for p in items if p["id"] == str(DEMO_PLAN))
    assert demo["code"] == "FAMILLE-OR"
    # Version en vigueur au 01/10/2026 (horloge) : v2 ; brouillon v3 listé mais pas courant.
    assert demo["current_version_id"] == "00000000-0000-4000-8000-000000000112"
    assert [v["version"] for v in demo["versions"]] == [1, 2, 3]
    assert ids.plan_id in _ids_of(items)


def test_create_plan(l2: Platform) -> None:
    code = _code("NEW")
    plan = ok(call(l2, "admin_a", "POST", "/v1/plans", {"code": code, "name": "Formule"}), 201)
    assert plan["code"] == code
    assert plan["status"] == "active"
    assert plan["versions"] == []
    assert plan["current_version_id"] is None
    # Code unique dans l'organisation.
    problem(call(l2, "admin_a", "POST", "/v1/plans", {"code": code, "name": "Bis"}), 409, "VAL-01")
    problem(
        call(l2, "admin_a", "POST", "/v1/plans", {"code": "minuscule", "name": "X"}), 422, "VAL-01"
    )


def test_get_plan(l2: Platform, ids: Ids) -> None:
    plan = ok(call(l2, "gestionnaire", "GET", f"/v1/plans/{ids.plan_id}"), 200)
    assert [v["id"] for v in plan["versions"]] == [ids.plan_version_id]
    problem(call(l2, "gestionnaire", "GET", f"/v1/plans/{uuid.uuid4()}"), 404, "NOT-01")


def test_create_plan_version(l2: Platform, ids: Ids) -> None:
    created = ok(
        call(
            l2, "gestionnaire", "POST", f"/v1/plans/{ids.plan_id}/versions",
            version_body("2030-01-01", valid_to="2030-12-31", coverage_rate_bp=7000),
        ),
        201,
    )  # fmt: skip
    assert created["state"] == "brouillon"
    assert created["version"] >= 2
    assert created["coverage_rate_bp"] == 7000
    assert created["family_annual_ceiling_xof"] == 3_000_000
    assert isinstance(created["family_annual_ceiling_xof"], int)
    assert created["currency"] == "XOF"
    assert created["coverages"][0]["category"] == "soins_courants"
    # Période inversée : refus.
    bad = version_body("2030-01-01", valid_to="2029-01-01")
    problem(call(l2, "admin_a", "POST", f"/v1/plans/{ids.plan_id}/versions", bad), 422, "VAL-01")
    # Montant décimal : refus (montants entiers).
    decimal = version_body("2030-01-01", monthly_contribution_xof=27500.5)
    problem(
        call(l2, "admin_a", "POST", f"/v1/plans/{ids.plan_id}/versions", decimal), 422, "VAL-01"
    )


def test_get_plan_version(l2: Platform, ids: Ids) -> None:
    version = ok(call(l2, "gestionnaire", "GET", f"/v1/plan-versions/{ids.plan_version_id}"), 200)
    assert version["plan_id"] == ids.plan_id
    assert version["valid_from"] == "2026-01-01"
    assert version["monthly_contribution_xof"] == 27_500


def test_publish_plan_version(l2: Platform) -> None:
    plan = ok(call(l2, "admin_a", "POST", "/v1/plans", {"code": _code("PUB"), "name": "P"}), 201)
    draft = ok(
        call(l2, "admin_a", "POST", f"/v1/plans/{plan['id']}/versions", version_body("2026-01-01")),
        201,
    )
    published = ok(call(l2, "admin_a", "POST", f"/v1/plan-versions/{draft['id']}/publication"), 200)
    assert published["state"] == "en_vigueur"
    row = l2.rows(
        "SELECT approved_by, approved_at IS NOT NULL FROM plan_versions WHERE id = %s",
        (UUID(draft["id"]),),
    )
    assert row == [(l2.users["admin_a"], True)]
    # Publiée = figée : une seconde publication est refusée (RUL-01).
    problem(
        call(l2, "admin_a", "POST", f"/v1/plan-versions/{draft['id']}/publication"), 409, "RUL-01"
    )
    current = ok(call(l2, "admin_a", "GET", f"/v1/plans/{plan['id']}"), 200)
    assert current["current_version_id"] == draft["id"]


def test_list_providers(l2: Platform, ids: Ids) -> None:
    page = ok(call(l2, "medecin_conseil", "GET", "/v1/providers?at=2026-10-01&limit=200"), 200)
    by_id = {p["id"]: p for p in page["items"]}
    assert by_id[ids.provider_id]["conventioned"] is True
    assert by_id[ids.unconventioned_provider_id]["conventioned"] is False
    assert page["page"]["next_cursor"] is None
    before = ok(call(l2, "gestionnaire", "GET", "/v1/providers?at=2025-06-01&limit=200"), 200)
    assert {p["id"]: p for p in before["items"]}[ids.provider_id]["conventioned"] is False


def test_list_providers_pagine(l2: Platform, ids: Ids) -> None:
    seen: list[str] = []
    cursor: str | None = None
    while True:
        url = "/v1/providers?limit=1" + (f"&cursor={cursor}" if cursor else "")
        page = ok(call(l2, "gestionnaire", "GET", url), 200)
        seen += [p["id"] for p in page["items"]]
        cursor = page["page"]["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) >= 3
    assert {ids.provider_id, ids.unconventioned_provider_id} <= set(seen)
    problem(call(l2, "gestionnaire", "GET", "/v1/providers?cursor=abime"), 422, "VAL-01")


def test_create_provider(l2: Platform) -> None:
    body = {
        "name": "Pharmacie fictive",
        "kind": "pharmacie",
        "city": "Abidjan",
        "country_code": "CI",
    }
    created = ok(call(l2, "gestionnaire", "POST", "/v1/providers", body), 201)
    assert created["status"] == "actif"
    assert created["conventioned"] is False
    assert created["conventions"] == []
    problem(
        call(l2, "gestionnaire", "POST", "/v1/providers", body | {"country_code": "FR"}),
        422,
        "VAL-01",
    )


def test_get_provider(l2: Platform, ids: Ids) -> None:
    provider = ok(call(l2, "medecin_conseil", "GET", f"/v1/providers/{ids.provider_id}"), 200)
    assert provider["conventioned"] is True
    assert [c["valid_from"] for c in provider["conventions"]] == ["2026-01-01"]


def test_create_provider_convention(l2: Platform) -> None:
    body = {"name": "Labo fictif", "kind": "laboratoire", "city": "Abidjan", "country_code": "CI"}
    provider = ok(call(l2, "admin_a", "POST", "/v1/providers", body), 201)
    url = f"/v1/providers/{provider['id']}/conventions"
    created = ok(
        call(
            l2, "gestionnaire", "POST", url, {"valid_from": "2026-01-01", "valid_to": "2026-12-31"}
        ),
        201,
    )
    assert created["valid_to"] == "2026-12-31"
    # Chevauchement d'une période de convention existante : RUL-02, rien d'ajouté.
    problem(call(l2, "gestionnaire", "POST", url, {"valid_from": "2026-06-01"}), 409, "RUL-02")
    ok(call(l2, "gestionnaire", "POST", url, {"valid_from": "2027-01-01"}), 201)
    count = l2.scalar(
        "SELECT count(*) FROM provider_conventions WHERE provider_id = %s",
        (UUID(provider["id"]),),
    )
    assert count == 2


def test_list_tariffs(l2: Platform, ids: Ids) -> None:
    tariffs = ok(call(l2, "clinique_a", "GET", "/v1/tariffs?at=2025-06-01"), 200)
    assert tariffs["at"] == "2025-06-01"
    by_code = {t["act_code"]: t for t in tariffs["items"]}
    assert by_code["CONS-GEN"]["amount_xof"] == 22_000  # barème 2025
    assert ids.act_code not in by_code
    today = ok(call(l2, "clinique_a", "GET", "/v1/tariffs"), 200)
    assert today["at"] == "2026-10-01"  # horloge de l'application, fuseau de l'organisation
    current = {t["act_code"]: t for t in today["items"]}
    assert current["CONS-GEN"]["amount_xof"] == 25_000
    assert current[ids.act_code] == {
        "act_code": ids.act_code,
        "label": "Acte fictif",
        "amount_xof": 12_000,
        "currency": "XOF",
        "valid_from": "2026-01-01",
        "valid_to": None,
        "requires_prior_approval": False,
    }


def test_list_acts(l2: Platform, ids: Ids) -> None:
    items = ok(call(l2, "medecin_conseil", "GET", "/v1/acts"), 200)["items"]
    codes = _ids_of(items, "code")
    assert {"CONS-GEN", "IMG-ECHO-ABD", ids.act_code} <= codes


def test_create_act(l2: Platform, ids: Ids) -> None:
    code = _code("RX")
    body = {"code": code, "label": "Radio fictive", "coverage_category": "soins_courants",
            "requires_prior_approval": True}  # fmt: skip
    created = ok(call(l2, "gestionnaire", "POST", "/v1/acts", body), 201)
    assert created["requires_prior_approval"] is True
    problem(call(l2, "gestionnaire", "POST", "/v1/acts", body), 409, "VAL-01")


def test_create_tariff_item(l2: Platform) -> None:
    act = ok(
        call(l2, "admin_a", "POST", "/v1/acts",
             {"code": _code("T"), "label": "Acte tarifé", "coverage_category": "optique"}),
        201,
    )  # fmt: skip
    url = f"/v1/acts/{act['id']}/tariffs"
    first = ok(
        call(l2, "gestionnaire", "POST", url,
             {"amount_xof": 9000, "valid_from": "2026-01-01", "valid_to": "2026-12-31"}),
        201,
    )  # fmt: skip
    assert first == {
        "act_code": act["code"],
        "label": "Acte tarifé",
        "amount_xof": 9000,
        "currency": "XOF",
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "requires_prior_approval": False,
    }
    # Deux montants le même jour rendraient le prix ambigu : RUL-02.
    problem(
        call(l2, "gestionnaire", "POST", url, {"amount_xof": 9500, "valid_from": "2026-12-01"}),
        409,
        "RUL-02",
    )
    problem(
        call(l2, "gestionnaire", "POST", url, {"amount_xof": 9.5, "valid_from": "2027-01-01"}),
        422,
        "VAL-01",
    )
    ok(call(l2, "gestionnaire", "POST", url, {"amount_xof": 9500, "valid_from": "2027-01-01"}), 201)


def test_list_rules(l2: Platform) -> None:
    items = ok(call(l2, "medecin_conseil", "GET", "/v1/rules"), 200)["items"]
    by_code = {r["code"]: r for r in items}
    assert {"R-01", "R-04", "R-07", "R-09", "R-12", "R-20", "ID-03", "HL-01"} == set(by_code)
    r12 = by_code["R-12"]
    assert r12["kind"] == "accord_automatique"
    assert r12["current_version"]["version"] == 3
    assert r12["current_version"]["params"]["total_max_exclu_xof"] == 50_000


def test_list_rule_versions(l2: Platform, ids: Ids) -> None:
    items = ok(call(l2, "gestionnaire", "GET", "/v1/rules/R-20/versions"), 200)["items"]
    assert [v["state"] for v in items][:1] == ["en_vigueur"]
    assert ids.rule_version_id in _ids_of(items)
    assert all(v["rule_code"] == "R-20" for v in items)
    problem(call(l2, "gestionnaire", "GET", "/v1/rules/R-99/versions"), 404, "NOT-01")


def test_create_rule_version(l2: Platform) -> None:
    url = "/v1/rules/R-12/versions"
    created = ok(
        call(l2, "admin_a", "POST", url, {"valid_from": "2050-01-01", "valid_to": "2050-12-31",
             "params": {"total_max_exclu_xof": 60_000, "score_fraude_max_exclu": 0.2}}),
        201,
    )  # fmt: skip
    assert created["state"] == "brouillon"
    assert created["rule_code"] == "R-12"
    assert created["version"] >= 4
    # Schéma fermé des paramètres de la règle : clé inconnue ou montant décimal = VAL-01.
    for params in (
        {"total_max_exclu_xof": 60_000, "score_fraude_max_exclu": 0.2, "autre": 1},
        {"total_max_exclu_xof": 60_000.5, "score_fraude_max_exclu": 0.2},
        {"total_max_exclu_xof": 60_000},
    ):
        problem(
            call(l2, "admin_a", "POST", url, {"valid_from": "2050-01-01", "params": params}),
            422,
            "VAL-01",
        )


def test_publish_rule_version_et_chevauchement(l2: Platform) -> None:
    """Une version de R-20 publiée (date d'effet future) clôt la précédente ; un chevauchement
    est refusé (RUL-02) sans rien modifier ; une version publiée est figée (RUL-01)."""
    url = "/v1/rules/R-20/versions"
    draft = ok(
        call(l2, "admin_a", "POST", url,
             {"valid_from": "2045-01-01", "params": {"delai_cible_minutes": 60}}),
        201,
    )  # fmt: skip
    published = ok(call(l2, "admin_a", "POST", f"/v1/rule-versions/{draft['id']}/publication"), 200)
    assert published["state"] == "en_vigueur"
    assert published["valid_from"] == "2045-01-01"
    versions = {v["version"]: v for v in ok(call(l2, "admin_a", "GET", url), 200)["items"]}
    assert versions[2]["valid_to"] == "2044-12-31"  # v2 close la veille, toujours publiée
    assert versions[2]["state"] == "en_vigueur"
    assert versions[2]["params"] == {"delai_cible_minutes": 120}

    overlapping = ok(
        call(l2, "admin_a", "POST", url,
             {"valid_from": "2044-06-01", "params": {"delai_cible_minutes": 30}}),
        201,
    )  # fmt: skip
    before = _snapshot(l2, "rule_versions")
    problem(
        call(l2, "admin_a", "POST", f"/v1/rule-versions/{overlapping['id']}/publication"),
        409,
        "RUL-02",
    )
    assert _snapshot(l2, "rule_versions") == before
    problem(
        call(l2, "admin_a", "POST", f"/v1/rule-versions/{draft['id']}/publication"), 409, "RUL-01"
    )


# --- evaluateRules : le moteur décide, rien n'est écrit (R4, R5) -------------------------------

WRITTEN_BY_A_DECISION: Final = (
    "claims", "claim_items", "claim_decisions", "authorizations", "outbox_events",
    "ledger_entries", "audit_events",
)  # fmt: skip


def _evaluate(env: Platform, who: str, body: dict[str, Any]) -> dict[str, Any]:
    counts = {t: _count(env, t) for t in WRITTEN_BY_A_DECISION}
    decision: dict[str, Any] = ok(call(env, who, "POST", "/v1/rules/evaluation", body), 200)
    assert {t: _count(env, t) for t in WRITTEN_BY_A_DECISION} == counts  # aucune écriture
    return decision


def test_evaluate_48000_score_006_accorde(l2: Platform, ids: Ids) -> None:
    body = evaluation_body(ids, ITEMS_48000, fraud_score=0.06)
    decision = _evaluate(l2, "gestionnaire", body)
    assert decision["outcome"] == "accordee_auto"
    assert decision["rule"] == {"code": "R-12", "version": 3}
    assert decision["reason_code"] == "R-12"
    assert decision["total_xof"] == 48_000
    assert decision["covered_xof"] == 38_400
    assert decision["patient_share_xof"] == 9_600
    assert decision["currency"] == "XOF"
    assert decision["plan_version_id"] == "00000000-0000-4000-8000-000000000112"
    assert decision["review_due_at"] is None
    assert [c["rule"]["code"] for c in decision["checks"]] == [
        "R-01",
        "R-04",
        "R-07",
        "R-09",
        "R-12",
    ]
    assert all(c["passed"] for c in decision["checks"])
    # Même entrée + mêmes versions = même décision.
    assert _evaluate(l2, "medecin_conseil", body) == decision


def test_evaluate_score_a_la_borne_exacte_part_en_revue(l2: Platform, ids: Ids) -> None:
    """0,20 exactement (borne exclue) : le score n'est jamais comparé en flottant approché."""
    decision = _evaluate(l2, "admin_a", evaluation_body(ids, ITEMS_48000, fraud_score=0.2))
    assert decision["outcome"] == "en_revue"


def test_evaluate_185000_part_en_revue(l2: Platform, ids: Ids) -> None:
    decision = _evaluate(l2, "admin_a", evaluation_body(ids, ITEMS_185000, fraud_score=0.06))
    assert decision["outcome"] == "en_revue"
    assert decision["rule"] == {"code": "R-20", "version": 2}
    assert decision["total_xof"] == 185_000
    assert decision["review_due_at"] == "2026-10-01T11:00:00Z"  # horloge + 120 min (R-20 v2)


def test_evaluate_hors_reseau_refuse_r_04(l2: Platform, ids: Ids) -> None:
    body = evaluation_body(ids, ITEMS_48000, fraud_score=0.06)
    body["provider_id"] = ids.unconventioned_provider_id
    decision = _evaluate(l2, "gestionnaire", body)
    assert decision["outcome"] == "refusee"
    assert decision["reason_code"] == "R-04"
    assert decision["covered_xof"] == 0
    assert decision["patient_share_xof"] == 48_000


def test_evaluate_droits_suspendus_refuse_r_01(l2: Platform) -> None:
    insured = add_insured(l2, "MC-90000002")
    l2.rows(
        "WITH s AS (UPDATE members SET status = 'suspendu' WHERE id = %s RETURNING id) "
        "INSERT INTO member_status_history (organization_id, member_id, from_status, to_status, "
        "reason_code, occurred_at) SELECT %s, id, 'actif', 'suspendu', 'impaye', "
        "TIMESTAMPTZ '2026-09-01 00:00Z' FROM s RETURNING id",
        (insured.member_id, l2.orgs["a"]),
    )
    body = {
        "member_id": str(insured.member_id),
        "beneficiary_id": str(insured.person_id),
        "provider_id": str(l2.providers["a"]),
        "service_date": "2026-10-01",
        "items": ITEMS_48000,
        "fraud_score": 0.06,
    }
    decision = _evaluate(l2, "gestionnaire", body)
    assert decision["outcome"] == "refusee"
    assert decision["reason_code"] == "R-01"
    # Au 15/08, avant la suspension, les droits étaient ouverts (statut à la date du soin).
    earlier = _evaluate(l2, "gestionnaire", body | {"service_date": "2026-08-15"})
    assert earlier["outcome"] == "accordee_auto"


def test_evaluate_entrees_invalides(l2: Platform, ids: Ids) -> None:
    url = "/v1/rules/evaluation"
    problem(call(l2, "admin_a", "POST", url, evaluation_body(ids, [])), 422, "VAL-01")
    problem(
        call(l2, "admin_a", "POST", url, evaluation_body(ids, ITEMS_48000, fraud_score=1.5)),
        422,
        "VAL-01",
    )
    stranger = evaluation_body(ids, ITEMS_48000) | {"beneficiary_id": str(uuid.uuid4())}
    problem(call(l2, "admin_a", "POST", url, stranger), 404, "NOT-01")
    unknown = evaluation_body(ids, ITEMS_48000) | {"member_id": str(uuid.uuid4())}
    problem(call(l2, "admin_a", "POST", url, unknown), 404, "NOT-01")
    # Soin daté avant toute version publiée du produit : NOT-01.
    problem(
        call(
            l2, "admin_a", "POST", url, evaluation_body(ids, ITEMS_48000, service_date="2024-06-01")
        ),
        404,
        "NOT-01",
    )
