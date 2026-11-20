"""Opérations L3 de specs/openapi.yaml sur l'application ASSEMBLÉE (``create_app`` du noyau).

Aucune surcharge de dépendance : vrais jetons de test (``InMemoryIdentityProvider``), rôles lus
en base (``user_roles``), autorisation par ``require_operation`` du noyau, connexion du grand
livre prise dans le pool du noyau. L'organisation vient toujours du jeton, jamais de la requête.
Deux organisations fictives A et B : rien de B n'est visible depuis A.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
import pytest
from fastapi.testclient import TestClient

from api.core.app import create_app
from api.core.identity import Identity, InMemoryIdentityProvider
from api.core.settings import Settings
from api.core.tests.conftest import sqlalchemy_url
from api.ledger.consumer import handle_event
from api.ledger.tests.support import (
    Org,
    app_connection,
    claim_decided,
    contribution_received,
    run,
    setup_org,
)
from api.tests.contracts.helpers import APP_ROLE

A_COVERED, A_CONTRIBUTION, B_COVERED = 38400, 27500, 91000


@dataclass
class Api:
    client: TestClient
    orgs: dict[str, Org]
    entries: dict[str, str]
    tokens: dict[tuple[str, str], str] = field(default_factory=dict)

    def auth(self, org: str, role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[(org, role)]}"}

    def get(self, path: str, org: str = "a", role: str = "gestionnaire", **kw: Any) -> Any:  # noqa: ANN401
        return self.client.get(path, headers=self.auth(org, role), **kw)

    def reverse(self, entry_id: str, key: str, reason: str = "erreur de barème", **who: str) -> Any:  # noqa: ANN401
        headers = {**self.auth(who.get("org", "a"), who.get("role", "gestionnaire"))}
        headers["Idempotency-Key"] = key
        return self.client.post(
            f"/v1/ledger/entries/{entry_id}/reversal", json={"reason": reason}, headers=headers
        )


def _add_user(dsn: str, org: Org, role: str | None, idp: InMemoryIdentityProvider) -> str:
    """Utilisateur fictif (posé par le propriétaire) et son jeton de test."""
    subject = f"sub-{org.id.hex[:8]}-{role or 'sans-role'}"
    with psycopg.connect(dsn) as conn:
        row = conn.execute(
            "INSERT INTO users (organization_id, idp_subject, display_name) "
            "VALUES (%s, %s, 'Agent fictif') RETURNING id",
            (org.id, subject),
        ).fetchone()
        assert row is not None
        user_id: UUID = row[0]
        if role is not None:
            provider = org.provider_id if role == "clinique" else None
            conn.execute(
                "INSERT INTO user_roles (organization_id, user_id, role, provider_id) "
                "VALUES (%s, %s, %s, %s)",
                (org.id, user_id, role, provider),
            )
    return idp.issue(Identity(subject=subject, organization_id=org.id))


@pytest.fixture
def api(insurance_dsn: str) -> Iterator[Api]:
    orgs = {
        "a": setup_org(insurance_dsn, "mutuelle-a"),
        "b": setup_org(insurance_dsn, "mutuelle-b"),
    }

    async def _seed() -> dict[str, str]:
        async with app_connection(insurance_dsn) as conn:
            a = orgs["a"]
            entry_a = await handle_event(conn, a.id, claim_decided(a, covered_xof=A_COVERED))
            await handle_event(conn, a.id, contribution_received(a, amount_xof=A_CONTRIBUTION))
            b = orgs["b"]
            entry_b = await handle_event(conn, b.id, claim_decided(b, covered_xof=B_COVERED))
        return {"a": str(entry_a), "b": str(entry_b)}

    entries = run(_seed())
    idp = InMemoryIdentityProvider()
    tokens = {
        (key, role or "sans_role"): _add_user(insurance_dsn, org, role, idp)
        for key, org in orgs.items()
        for role in ("gestionnaire", "admin", "clinique", "medecin_conseil", None)
    }
    app = create_app(
        Settings(database_url=sqlalchemy_url(insurance_dsn), app_role=APP_ROLE),
        identity_provider=idp,
    )
    with TestClient(app) as client:
        yield Api(client, orgs, entries, tokens)


def _problem(response: Any, status: int, code: str) -> None:  # noqa: ANN401
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == code
    assert body["message"]
    assert body["action"]
    assert body["request_id"]


# --- Isolation, autorisation, authentification (noyau L1) ------------------------------------


def test_un_utilisateur_de_a_ne_voit_rien_de_b(api: Api) -> None:
    journal = api.get("/v1/ledger/entries", params={"limit": 200})
    assert journal.status_code == 200, journal.text
    ids = {item["id"] for item in journal.json()["items"]}
    assert api.entries["a"] in ids
    assert api.entries["b"] not in ids
    assert len(ids) == 2  # prise en charge + cotisation de A, rien d'autre

    _problem(api.get(f"/v1/ledger/entries/{api.entries['b']}"), 404, "NOT-01")
    _problem(api.reverse(api.entries["b"], "cle-croisee-01"), 404, "NOT-01")

    balance = api.get("/v1/ledger/balance", params={"at": "2099-12-31"}).json()
    assert balance["total_debit_xof"] == A_COVERED + A_CONTRIBUTION  # sans les 91 000 de B
    accounts = api.get("/v1/ledger/accounts").json()["items"]
    assert len(accounts) == 6  # le plan de A seul, pas celui de B

    # Et l'inverse : B voit sa propre écriture, pas celles de A.
    seen_by_b = {i["id"] for i in api.get("/v1/ledger/entries", org="b").json()["items"]}
    assert seen_by_b == {api.entries["b"]}


def test_un_gestionnaire_lit_la_balance(api: Api) -> None:
    response = api.get("/v1/ledger/balance", params={"at": "2026-12-31"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["at"] == "2026-12-31"
    assert body["currency"] == "XOF"
    assert body["total_debit_xof"] == body["total_credit_xof"] == A_COVERED + A_CONTRIBUTION


@pytest.mark.parametrize("role", ["clinique", "medecin_conseil", "sans_role"])
@pytest.mark.parametrize(
    "path", ["/v1/ledger/accounts", "/v1/ledger/entries", "/v1/ledger/balance"]
)
def test_role_non_autorise_refuse(api: Api, role: str, path: str) -> None:
    # Contrat (openapi.yaml, ErrorCode) : rôle insuffisant = 403 AUTH-02 ; SEC-01 est réservé
    # au motif médical (readMedicalReason).
    _problem(api.get(path, role=role), 403, "AUTH-02")


def test_contre_passation_refusee_hors_gestionnaire(api: Api) -> None:
    _problem(api.reverse(api.entries["a"], "cle-role-0001", role="clinique"), 403, "AUTH-02")
    detail = api.get(f"/v1/ledger/entries/{api.entries['a']}").json()
    assert detail["reversed_by_entry_id"] is None


def test_admin_autorise(api: Api) -> None:
    assert api.get("/v1/ledger/accounts", role="admin").status_code == 200


def test_sans_jeton_echec_ferme(api: Api) -> None:
    _problem(api.client.get("/v1/ledger/balance"), 401, "AUTH-01")
    bad = {"Authorization": "Bearer jeton-inconnu"}
    _problem(api.client.get("/v1/ledger/balance", headers=bad), 401, "AUTH-01")


# --- Opérations du grand livre ------------------------------------------------------------------


def test_plan_de_comptes(api: Api) -> None:
    response = api.get("/v1/ledger/accounts")
    assert response.status_code == 200
    codes = [item["code"] for item in response.json()["items"]]
    assert codes == ["4011", "5110", "5121", "5122", "6011", "7061"]
    assert set(response.json()["items"][0]) == {"code", "label", "account_class"}


def test_journal_filtre_par_compte_et_pagine(api: Api) -> None:
    response = api.get("/v1/ledger/entries", params={"limit": 1})
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    cursor = body["page"]["next_cursor"]
    assert cursor
    second = api.get("/v1/ledger/entries", params={"limit": 1, "cursor": cursor}).json()
    assert len(second["items"]) == 1
    assert second["page"]["next_cursor"] is None
    assert {body["items"][0]["id"], second["items"][0]["id"]} >= {api.entries["a"]}

    only_6011 = api.get("/v1/ledger/entries", params={"account_code": "6011"}).json()
    assert [item["id"] for item in only_6011["items"]] == [api.entries["a"]]
    out_of_range = api.get(
        "/v1/ledger/entries", params={"from": "2027-01-01", "to": "2027-12-31"}
    ).json()
    assert out_of_range["items"] == []


def test_curseur_invalide(api: Api) -> None:
    _problem(api.get("/v1/ledger/entries", params={"cursor": "%%%"}), 422, "VAL-01")


def test_detail_d_une_ecriture(api: Api) -> None:
    response = api.get(f"/v1/ledger/entries/{api.entries['a']}")
    assert response.status_code == 200
    body = response.json()
    assert body["source_type"] == "prise_en_charge"
    assert body["currency"] == "XOF"
    assert body["reversed_by_entry_id"] is None
    assert [(li["account_code"], li["debit_xof"], li["credit_xof"]) for li in body["lines"]] == [
        ("6011", A_COVERED, 0),
        ("4011", 0, A_COVERED),
    ]
    assert body["lines"][0]["account_label"] == "Prestations santé"


def test_ecriture_inconnue(api: Api) -> None:
    missing = "00000000-0000-4000-8000-00000000abcd"
    _problem(api.get(f"/v1/ledger/entries/{missing}"), 404, "NOT-01")


def test_contre_passation_idempotente_puis_led_01(api: Api) -> None:
    entry = api.entries["a"]
    first = api.reverse(entry, "cle-reversal-0001")
    assert first.status_code == 201, first.text
    reversal = first.json()
    assert reversal["source_type"] == "contre_passation"
    assert reversal["reverses_entry_id"] == entry
    mirrored = [(li["account_code"], li["debit_xof"], li["credit_xof"]) for li in reversal["lines"]]
    assert mirrored == [("6011", 0, A_COVERED), ("4011", A_COVERED, 0)]

    replay = api.reverse(entry, "cle-reversal-0001")
    assert replay.status_code == 201
    assert replay.json()["id"] == reversal["id"]

    _problem(api.reverse(entry, "cle-reversal-0001", reason="autre motif"), 409, "IDEM-01")
    _problem(api.reverse(entry, "cle-autre-02"), 409, "LED-01")
    original = api.get(f"/v1/ledger/entries/{entry}").json()
    assert original["reversed_by_entry_id"] == reversal["id"]


def test_contre_passation_d_une_ecriture_inconnue(api: Api) -> None:
    _problem(api.reverse("00000000-0000-4000-8000-00000000abcd", "cle-inconnue-01"), 404, "NOT-01")


def test_balance_equilibree_et_contre_passation_l_annule(api: Api) -> None:
    before = api.get("/v1/ledger/balance", params={"at": "2026-12-31"}).json()
    rows = {row["account_code"]: row for row in before["rows"]}
    assert (rows["6011"]["debit_xof"], rows["6011"]["credit_xof"]) == (A_COVERED, 0)
    assert (rows["5121"]["debit_xof"], rows["7061"]["credit_xof"]) == (
        A_CONTRIBUTION,
        A_CONTRIBUTION,
    )

    assert api.reverse(api.entries["a"], "cle-balance-01").status_code == 201
    after = api.get("/v1/ledger/balance", params={"at": "2099-12-31"}).json()
    assert after["total_debit_xof"] == after["total_credit_xof"]
    net = {r["account_code"]: r["debit_xof"] - r["credit_xof"] for r in after["rows"]}
    assert net["6011"] == 0
    assert net["4011"] == 0

    past = api.get("/v1/ledger/balance", params={"at": "2026-01-01"}).json()
    assert past["total_debit_xof"] == 0


def test_balance_par_defaut_a_la_date_du_jour_locale(api: Api) -> None:
    body = api.get("/v1/ledger/balance").json()
    today = datetime.now(ZoneInfo("Africa/Abidjan")).date()
    assert date.fromisoformat(body["at"]) in {today, today - timedelta(days=1)}  # minuit
