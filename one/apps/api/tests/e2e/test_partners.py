"""Espaces assureur et employeur, accueil d'organisation (Phase 3, x-lot P3, CR-P3-01).

Sur l'application ASSEMBLÉE, par l'API HTTP avec de vrais jetons, sous ``mulema_app`` (RLS
forcée) et ``egress_guard``. Jeu de l'organisation A construit par les parcours réels :
- deux groupes d'employeurs fictifs (Alpha : six adhérents ; Beta : deux), adhérents inscrits par
  le gestionnaire, cartes et QR réels, carence écoulée ;
- onze dossiers accordés automatiquement au comptoir (R-12) : six « soins courants » (Alpha),
  trois « dentaire » (trois des six d'Alpha), deux « optique » (Beta) ;
- six cotisations d'Alpha payées par lien (webhook signé).
Ce que chaque test prouve : agrégats publiés jamais exacts (comptes par palier, montants au
millier), période en semaines entières et terminées (CR-P3-02 : la semaine du 28/09 n'est lue
qu'à partir du lundi 05/10), k-anonymat (seuil 5 atteint par « autres », masques
complémentaires, semaine faible), recoupement de requêtes rejoué par l'attaque du vérificateur
(avant/après un dossier, [J] puis [J, J+1]), aucune personne dans les réponses, portée de
l'employeur, rôles,
isolation (organisation B), et l'accueil d'une organisation par copie (jamais de partage), tout
ou rien, refusé par la base même si la matrice cédait. Données fictives.
"""

from __future__ import annotations

import csv
import io
import json
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from types import MappingProxyType
from typing import Any
from uuid import UUID

import psycopg
import pytest

from api.core import permissions
from api.core.identity import Identity
from api.core.permissions import Role
from api.members.jobs import run_daily
from api.partners.repository import PlatformRepository
from api.payments.jobs import issue_month
from api.tests.e2e.conftest import ORG_A, ORG_A_SLUG, Platform
from api.tests.e2e.test_member_space import ITEMS_48000, _add_adherent, _claim, _my_card
from api.tests.paths import OPENAPI_YAML

START = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)  # jeudi : semaine du lundi 28/09
READ_AT = START + timedelta(days=7)  # jeudi suivant : la semaine du 28/09 est terminée
WEEK = {"from": "2026-09-28", "to": "2026-10-04"}
BANDS = (5, 10, 20, 50, 100)
OCTOBER = date(2026, 10, 1)
PORTFOLIO = "/v1/insurer/portfolio"
CONSUMPTION = "/v1/employer/consumption"
CONTRACTS = "/v1/employer/contracts"
ORGANIZATIONS = "/v1/platform/organizations"
TEMPLATES = "/v1/platform/configuration-templates"
COVERED_48000 = 38_400  # 80 % de 48 000 (FAMILLE-OR v2)
COVERED_OPTIQUE = 24_000  # 80 % de 30 000
COVERED_DENTAIRE = 16_000  # 80 % de 20 000
CONTRIBUTION = 27_500
ALPHA, BETA = 6, 2
NAMES = [f"Partenaire{i}" for i in range(ALPHA + BETA)]


def _window() -> dict[str, str]:
    """La semaine du jeu (28/09 → 04/10) : tous les horodatages viennent de l'horloge de test."""
    return dict(WEEK)


def _employer(env: Platform, name: str, end: date | None) -> UUID:
    with psycopg.connect(env.dsn) as conn:
        row = conn.execute(
            "INSERT INTO employers (organization_id, name, contract_start, contract_end) "
            "VALUES (%s, %s, DATE '2026-01-01', %s) RETURNING id",
            (ORG_A, name, end),
        ).fetchone()
    assert row is not None
    employer: UUID = row[0]
    return employer


def _act(env: Platform, code: str, category: str, amount: int) -> None:
    with psycopg.connect(env.dsn) as conn:
        act = conn.execute(
            "INSERT INTO acts (organization_id, code, label, coverage_category) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (ORG_A, code, f"Acte fictif {code}", category),
        ).fetchone()
        assert act is not None
        conn.execute(
            "INSERT INTO tariff_items (organization_id, act_id, amount_xof, valid_from) "
            "VALUES (%s, %s, %s, DATE '2026-01-01')",
            (ORG_A, act[0], amount),
        )


def _enroll(env: Platform, name: str, phone: str, employer: UUID) -> dict[str, Any]:
    created = env.client.post(
        "/v1/members",
        json={
            "holder": {
                "given_name": name,
                "family_name": "Fictif",
                "birth_date": "1985-05-05",
                "phone_e164": phone,
            },
            "plan_code": "FAMILLE-OR",
            "employer_id": str(employer),
            "enrolled_on": "2026-07-01",
        },
        headers=env.headers("gestionnaire"),
    )
    assert created.status_code == 201, created.text
    member: dict[str, Any] = created.json()
    card = env.client.post(
        f"/v1/members/{member['id']}/cards",
        json={"person_id": member["holder"]["person_id"]},
        headers=env.headers("gestionnaire"),
    )
    assert card.status_code == 201, card.text
    return member


def _pay(env: Platform, member_id: str) -> None:
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


def _token(env: Platform, who: str, org: UUID, grants: list[tuple[str, UUID | None]]) -> None:
    """Utilisateur fictif inséré en propriétaire, avec ses rôles (et groupes d'employeur)."""
    subject = f"sub-e2e-{who}-{uuid.uuid4().hex[:8]}"
    with psycopg.connect(env.dsn) as conn:
        row = conn.execute(
            "INSERT INTO users (organization_id, idp_subject, display_name) "
            "VALUES (%s, %s, %s) RETURNING id",
            (org, subject, f"Agent fictif {who}"),
        ).fetchone()
        assert row is not None
        for role, employer in grants:
            conn.execute(
                "INSERT INTO user_roles (organization_id, user_id, role, employer_id) "
                "VALUES (%s, %s, %s, %s)",
                (org, row[0], role, employer),
            )
    env.users[who] = row[0]
    env.tokens[who] = env.idp.issue(Identity(subject=subject, organization_id=org))


@pytest.fixture(scope="module")
def portfolio(platform: Platform) -> dict[str, Any]:
    env = platform
    env.clock.current = START
    alpha = _employer(env, "Groupe fictif Alpha", START.date() + timedelta(days=60))
    beta = _employer(env, "Groupe fictif Beta", None)
    _act(env, "OPT-MONT", "optique", 30_000)
    _act(env, "DENT-SOIN", "dentaire", 20_000)
    phones = [f"+22507000099{i:02d}" for i in range(ALPHA + BETA)]
    members = [
        _enroll(env, NAMES[i], phones[i], alpha if i < ALPHA else beta) for i in range(ALPHA + BETA)
    ]
    env.run(run_daily, env.database, ORG_A, env.clock.now())
    env.run(issue_month, env.database, ORG_A, OCTOBER, env.clock.now())
    for i, member in enumerate(members):
        _add_adherent(env, f"p3adh{i}", "a", UUID(member["id"]))
    claims: list[dict[str, Any]] = []
    for i in range(ALPHA):
        qr = _my_card(env, f"p3adh{i}")["qr_payload"]
        claims.append(_claim(env, qr, phones[i], ITEMS_48000)["claim"])
    for i in range(3):
        qr = _my_card(env, f"p3adh{i}")["qr_payload"]
        claims.append(
            _claim(env, qr, phones[i], [{"act_code": "DENT-SOIN", "quantity": 1}])["claim"]
        )
    for i in range(ALPHA, ALPHA + BETA):
        qr = _my_card(env, f"p3adh{i}")["qr_payload"]
        claims.append(
            _claim(env, qr, phones[i], [{"act_code": "OPT-MONT", "quantity": 1}])["claim"]
        )
    assert [c["status"] for c in claims] == ["accordee_auto"] * len(claims)
    for member in members[:ALPHA]:
        _pay(env, member["id"])

    _token(env, "assureur", ORG_A, [("assureur", None)])
    _token(env, "admin", ORG_A, [("admin", None)])
    _token(env, "employeur_alpha", ORG_A, [("employeur", alpha)])
    _token(env, "employeur_deux", ORG_A, [("employeur", alpha), ("employeur", beta)])
    _token(env, "assureur_b", env.orgs["b"], [("assureur", None)])
    return {"alpha": alpha, "beta": beta, "members": members, "claims": claims}


def _get(env: Platform, path: str, who: str, **params: Any) -> dict[str, Any]:  # noqa: ANN401
    """Lecture une fois la semaine du jeu terminée (la semaine en cours n'est jamais publiée)."""
    env.clock.current = READ_AT
    response = env.client.get(path, params=_window() | params, headers=env.auth(who))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _band(people: int) -> int:
    """Palier publié pour un effectif ou un compte (5, 10, 20…), jamais la valeur exacte."""
    return max(b for b in BANDS if b <= people)


def _xof(amount: int) -> int:
    """Montant publié : millier de francs CFA le plus proche, jamais le montant exact."""
    return (amount + 500) // 1000 * 1000


def _shown(value: dict[str, Any]) -> tuple[int, int]:
    assert value["status"] == "disponible", value
    return value["value"], value["contributors"]


def _masked(value: dict[str, Any]) -> bool:
    return value == {"status": "masque", "value": None, "contributors": None}


# --- Espace assureur -----------------------------------------------------------------------------


def test_portefeuille_agrege_publie_jamais_exact(
    platform: Platform, portfolio: dict[str, Any]
) -> None:
    body = _get(platform, PORTFOLIO, "assureur")
    assert body["k_anonymity_threshold"] == 5
    assert body["currency"] == "XOF"
    assert (body["period_from"], body["period_to"]) == (WEEK["from"], WEEK["to"])
    # Huit adhérents : publié « 5 » (palier), jamais 8.
    assert _shown(body["members_total"]) == (_band(ALPHA + BETA), _band(ALPHA + BETA))
    assert _shown(body["premiums_xof"]) == (_xof(ALPHA * CONTRIBUTION), _band(ALPHA))
    cost = ALPHA * COVERED_48000 + 3 * COVERED_DENTAIRE + BETA * COVERED_OPTIQUE
    assert cost % 1000 != 0  # 326 400 : publié 326 000
    assert _shown(body["claims_cost_xof"]) == (_xof(cost), _band(ALPHA + BETA))
    expected_ratio = (2 * 10_000 * cost + ALPHA * CONTRIBUTION) // (2 * ALPHA * CONTRIBUTION)
    # S/P porté par le plus petit des deux groupes (6 cotisants, 8 sinistrés).
    assert _shown(body["loss_ratio_bp"]) == (expected_ratio, _band(ALPHA))
    assert _shown(body["automation_rate_bp"]) == (10_000, _band(ALPHA + BETA))
    delay, people = _shown(body["decision_delay_mean_ms"])
    assert delay >= 0
    assert people == _band(ALPHA + BETA)
    assert [p["name"] for p in body["top_providers"]] == ["Clinique fictive A"]
    assert _shown(body["top_providers"][0]["claims"]) == (
        _band(len(portfolio["claims"])),
        _band(ALPHA + BETA),
    )
    assert _masked(body["other_providers"]["claims"])


def test_categories_sous_le_seuil_fondues_et_autres_publie_a_5(
    platform: Platform, portfolio: dict[str, Any]
) -> None:
    """optique (2) et dentaire (3) ne sont jamais cités ; réunis, ils portent 5 personnes."""
    body = _get(platform, PORTFOLIO, "assureur")
    rows = {row["category"]: row for row in body["benefits_by_category"]}
    assert set(rows) == {"soins_courants", "autres_regroupes"}
    assert _shown(rows["soins_courants"]["covered_xof"]) == (
        _xof(ALPHA * COVERED_48000),
        _band(ALPHA),
    )
    others = 3 * COVERED_DENTAIRE + BETA * COVERED_OPTIQUE
    assert _shown(rows["autres_regroupes"]["covered_xof"]) == (_xof(others), _band(5))
    assert _shown(rows["autres_regroupes"]["claims"]) == (5, _band(5))


def test_statuts_masques_ensemble(platform: Platform, portfolio: dict[str, Any]) -> None:
    """Huit actifs, zéro en carence ou suspendu : publier « actif = 8 » dirait la situation de
    chacun ; les trois statuts sont masqués, seul le total est publié."""
    body = _get(platform, PORTFOLIO, "assureur")
    assert [s["status"] for s in body["members_by_status"]] == ["actif", "carence", "suspendu"]
    assert all(_masked(s["count"]) for s in body["members_by_status"])


def test_aucune_personne_dans_les_agregats(platform: Platform, portfolio: dict[str, Any]) -> None:
    dumps = [
        json.dumps(_get(platform, PORTFOLIO, "assureur")),
        json.dumps(_get(platform, CONSUMPTION, "employeur_deux")),
        json.dumps(_get(platform, CONTRACTS, "employeur_deux")),
    ]
    forbidden = [*NAMES, "Fictif", "+2250700009"]
    forbidden += [m["id"] for m in portfolio["members"]]
    forbidden += [m["holder"]["person_id"] for m in portfolio["members"]]
    forbidden += [c["id"] for c in portfolio["claims"]]
    for dump in dumps:
        assert [f for f in forbidden if f in dump] == []
        assert "member_id" not in dump
        assert "act_code" not in dump


def test_export_csv_memes_masques_et_journalise(
    platform: Platform, portfolio: dict[str, Any]
) -> None:
    env = platform
    env.clock.current = READ_AT
    response = env.client.get(f"{PORTFOLIO}/export", params=_window(), headers=env.auth("assureur"))
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["cache-control"] == "no-store"
    rows = list(csv.reader(io.StringIO(response.text), delimiter=";"))
    assert rows[0] == ["section", "cle", "statut", "valeur", "effectif", "unite"]
    cells = {(r[0], r[1]): r[2:] for r in rows[2:]}
    assert cells[("primes", "encaissees")] == [
        "disponible",
        str(_xof(ALPHA * CONTRIBUTION)),
        str(_band(ALPHA)),
        "xof",
    ]
    assert cells[("adherents", "suspendu")] == ["masque", "", "", "nombre"]
    assert not any(name in response.text for name in NAMES)
    audit = env.scalar(
        "SELECT count(*) FROM audit_events WHERE organization_id = %s "
        "AND action = 'insurer.portfolio_exported' AND actor_user_id = %s",
        (ORG_A, env.users["assureur"]),
    )
    assert audit == 1


def test_assureur_de_b_ne_voit_rien_de_a(platform: Platform, portfolio: dict[str, Any]) -> None:
    """Isolation (RLS) : B n'a qu'un adhérent et un dossier ; rien de A ne s'y ajoute."""
    body = _get(platform, PORTFOLIO, "assureur_b")
    assert _masked(body["members_total"])
    assert _masked(body["claims_cost_xof"])
    assert body["top_providers"] == []
    assert "Clinique fictive A" not in json.dumps(body)


@pytest.mark.parametrize(
    ("who", "path", "expected"),
    [
        pytest.param("admin", PORTFOLIO, 200, id="admin-portefeuille"),
        pytest.param("gestionnaire", PORTFOLIO, 403, id="gestionnaire-portefeuille"),
        pytest.param("employeur_alpha", PORTFOLIO, 403, id="employeur-portefeuille"),
        pytest.param("clinique_a", f"{PORTFOLIO}/export", 403, id="clinique-export"),
        pytest.param("assureur", CONSUMPTION, 403, id="assureur-employeur"),
        pytest.param("assureur", "/v1/members", 403, id="assureur-adherents"),
        pytest.param("assureur", "/v1/claims", 403, id="assureur-dossiers"),
        pytest.param("assureur", "/v1/ledger/entries", 403, id="assureur-grand-livre"),
        pytest.param("admin", CONSUMPTION, 403, id="admin-employeur"),
    ],
)
def test_roles(
    platform: Platform, portfolio: dict[str, Any], who: str, path: str, expected: int
) -> None:
    platform.clock.current = READ_AT
    response = platform.client.get(path, params=_window(), headers=platform.auth(who))
    assert response.status_code == expected, response.text
    if expected == 403:
        assert response.json()["code"] == "AUTH-02"


def test_sans_jeton_refuse(platform: Platform, portfolio: dict[str, Any]) -> None:
    for path in (PORTFOLIO, CONSUMPTION, CONTRACTS, TEMPLATES):
        assert platform.client.get(path).status_code == 401


def test_periode_invalide(platform: Platform, portfolio: dict[str, Any]) -> None:
    response = platform.client.get(
        PORTFOLIO,
        params={"from": "2026-10-10", "to": "2026-10-01"},
        headers=platform.auth("assureur"),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-01"


# --- Espace employeur ----------------------------------------------------------------------------


def test_employeur_ne_voit_que_son_groupe(platform: Platform, portfolio: dict[str, Any]) -> None:
    body = _get(platform, CONSUMPTION, "employeur_alpha")
    assert [g["employer_id"] for g in body["groups"]] == [str(portfolio["alpha"])]
    group = body["groups"][0]
    assert _shown(group["members_total"]) == (_band(ALPHA), _band(ALPHA))
    assert _shown(group["claims"]) == (_band(ALPHA + 3), _band(ALPHA))
    covered = ALPHA * COVERED_48000 + 3 * COVERED_DENTAIRE
    assert _shown(group["covered_xof"]) == (_xof(covered), _band(ALPHA))
    # dentaire (3) sous le seuil : « autres » trop petit, soins courants y est fondu.
    rows = {row["category"]: row for row in group["benefits_by_category"]}
    assert set(rows) == {"autres_regroupes"}
    assert _shown(rows["autres_regroupes"]["covered_xof"]) == (_xof(covered), _band(ALPHA))


def test_petit_groupe_entierement_masque(platform: Platform, portfolio: dict[str, Any]) -> None:
    body = _get(platform, CONSUMPTION, "employeur_deux")
    groups = {g["employer_id"]: g for g in body["groups"]}
    beta = groups[str(portfolio["beta"])]
    assert _masked(beta["members_total"])
    assert _masked(beta["claims"])
    assert _masked(beta["covered_xof"])
    assert [_masked(r["covered_xof"]) for r in beta["benefits_by_category"]] == [True]


def test_contrats_et_echeances(platform: Platform, portfolio: dict[str, Any]) -> None:
    env = platform
    env.clock.current = START
    response = env.client.get(
        CONTRACTS, params={"within_days": 90}, headers=env.auth("employeur_deux")
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["as_of"] == "2026-10-01"
    items = {i["employer_id"]: i for i in body["items"]}
    alpha, beta = items[str(portfolio["alpha"])], items[str(portfolio["beta"])]
    assert (alpha["status"], alpha["days_remaining"]) == ("a_echeance", 60)
    assert (beta["status"], beta["days_remaining"]) == ("sans_echeance", None)
    shorter = env.client.get(
        CONTRACTS, params={"within_days": 30}, headers=env.auth("employeur_alpha")
    ).json()
    assert [i["status"] for i in shorter["items"]] == ["en_cours"]
    assert (
        env.client.get(
            CONTRACTS, params={"within_days": 0}, headers=env.auth("employeur_alpha")
        ).status_code
        == 422
    )


# --- Plateforme : accueil d'organisation par copie de gabarit ------------------------------------


@pytest.fixture(scope="module")
def plateforme(platform: Platform, portfolio: dict[str, Any]) -> Platform:
    """L'organisation A (jeu de démonstration) devient « plateforme » ; un administrateur."""
    env = platform
    with psycopg.connect(env.dsn) as conn:
        conn.execute(
            "UPDATE organizations SET capabilities = ARRAY['porteur_de_risque', 'gestionnaire', "
            "'plateforme'] WHERE id = %s",
            (ORG_A,),
        )
    _token(env, "admin_plateforme", ORG_A, [("admin_plateforme", None)])
    return env


def _template(env: Platform, code: str = "mutuelle-ci", who: str = "admin_plateforme") -> Any:  # noqa: ANN401
    return env.client.post(
        TEMPLATES,
        json={"code": code, "country_code": "CI", "label": "Mutuelle santé Côte d'Ivoire"},
        headers=env.auth(who),
    )


def _onboard(env: Platform, slug: str, **overrides: Any) -> Any:  # noqa: ANN401
    body: dict[str, Any] = {
        "slug": slug,
        "name": "Assurance fictive",
        "country_code": "CI",
        "capabilities": ["porteur_de_risque", "gestionnaire"],
        "first_manager": {"idp_subject": f"sub-{slug}", "display_name": "Gestionnaire fictif"},
        "template": {"code": "mutuelle-ci"},
    } | overrides
    return env.client.post(ORGANIZATIONS, json=body, headers=env.auth("admin_plateforme"))


def test_gabarit_instantane_versionne(plateforme: Platform) -> None:
    env = plateforme
    first = _template(env)
    assert first.status_code == 201, first.text
    assert first.json()["version"] == 1
    assert first.json()["contents"] == {
        "ledger_accounts": 6,
        "rules": 8,
        "plans": 1,
        "coverages": 5,
        "acts": 8,
        "tariff_items": 8,
    }
    second = _template(env)
    assert second.json()["version"] == 2
    listed = env.client.get(TEMPLATES, headers=env.auth("admin_plateforme")).json()
    assert [(t["code"], t["version"]) for t in listed["items"]] == [
        ("mutuelle-ci", 2),
        ("mutuelle-ci", 1),
    ]
    payload = env.scalar(
        "SELECT payload::text FROM configuration_templates WHERE version = 1 AND code = %s",
        ("mutuelle-ci",),
    )
    assert "Partenaire" not in payload  # aucune personne dans un gabarit
    assert '"score_fraude_max_exclu": 0.20' in payload  # valeur exacte, jamais un flottant


def test_accueil_d_organisation_par_copie(plateforme: Platform) -> None:
    env = plateforme
    _template(env)
    created = _onboard(env, "assurance-fictive-ci")
    assert created.status_code == 201, created.text
    body = created.json()
    new_org = UUID(body["organization"]["id"])
    assert body["organization"]["slug"] == "assurance-fictive-ci"
    assert body["organization"]["capabilities"] == ["porteur_de_risque", "gestionnaire"]
    assert body["copied"] == {
        "ledger_accounts": 6,
        "rules": 8,
        "plans": 1,
        "coverages": 5,
        "acts": 8,
        "tariff_items": 8,
    }
    assert sorted(r["role"] for r in body["first_manager"]["roles"]) == ["admin", "gestionnaire"]
    assert env.scalar("SELECT status FROM organizations WHERE id = %s", (new_org,)) == (
        "integration"
    )
    # Nouvelle version isolée : version 1 en brouillon, à publier par l'organisation accueillie.
    states = env.rows(
        "SELECT DISTINCT version, state FROM rule_versions WHERE organization_id = %s "
        "UNION SELECT DISTINCT version, state FROM plan_versions WHERE organization_id = %s",
        (new_org, new_org),
    )
    assert states == [(1, "brouillon")]
    # Jamais une ligne partagée : aucun identifiant commun avec la plateforme, rien de pointé.
    for table in ("rules", "plans", "acts", "ledger_accounts", "tariff_items", "coverages"):
        shared = env.scalar(
            f"SELECT count(*) FROM {table} n JOIN {table} p ON p.id = n.id "
            "WHERE n.organization_id = %s AND p.organization_id = %s",
            (new_org, ORG_A),
        )
        assert shared == 0, table
    params = env.scalar(
        "SELECT v.params::text FROM rule_versions v JOIN rules r ON r.id = v.rule_id "
        "WHERE r.organization_id = %s AND r.code = 'R-12'",
        (new_org,),
    )
    assert json.loads(params) == {"total_max_exclu_xof": 50000, "score_fraude_max_exclu": 0.2}
    assert '"score_fraude_max_exclu": 0.20' in params  # copié en SQL : valeur exacte
    assert env.scalar("SELECT count(*) FROM members WHERE organization_id = %s", (new_org,)) == 0


def test_accueil_journalise_dans_les_deux_organisations(plateforme: Platform) -> None:
    env = plateforme
    _template(env)
    body = _onboard(env, "assurance-journal-ci").json()
    new_org = UUID(body["organization"]["id"])
    platform_event = env.rows(
        "SELECT actor_user_id, metadata->>'slug' FROM audit_events WHERE organization_id = %s "
        "AND action = 'organization.created' AND target_id = %s",
        (ORG_A, new_org),
    )
    assert platform_event == [(env.users["admin_plateforme"], "assurance-journal-ci")]
    hosted_event = env.rows(
        "SELECT actor_user_id, actor_role, metadata->>'platform_organization_id' "
        "FROM audit_events WHERE organization_id = %s AND action = 'organization.onboarded'",
        (new_org,),
    )
    assert hosted_event == [(None, "admin_plateforme", str(ORG_A))]


def test_premier_gestionnaire_isole_dans_sa_organisation(plateforme: Platform) -> None:
    env = plateforme
    _template(env)
    body = _onboard(env, "assurance-isolee-ci").json()
    new_org = UUID(body["organization"]["id"])
    token = env.idp.issue(Identity(subject="sub-assurance-isolee-ci", organization_id=new_org))
    auth = {"Authorization": f"Bearer {token}"}
    me = env.client.get("/v1/me", headers=auth)
    assert me.status_code == 200, me.text
    assert me.json()["organization"]["id"] == str(new_org)
    plans = env.client.get("/v1/plans", headers=auth).json()
    assert [p["code"] for p in plans["items"]] == ["FAMILLE-OR"]
    assert env.client.get("/v1/members", headers=auth).json()["items"] == []
    # La plateforme, elle, ne lit rien de l'organisation accueillie.
    portfolio = _get(env, PORTFOLIO, "admin")
    assert "assurance" not in json.dumps(portfolio).lower()


@pytest.mark.parametrize(
    ("overrides", "status", "code"),
    [
        pytest.param({"template": {"code": "inconnu-ci"}}, 422, "ORG-02", id="gabarit-inconnu"),
        pytest.param(
            {"country_code": "SN", "slug": "assurance-sn"}, 422, "ORG-02", id="autre-pays"
        ),
        pytest.param({"capabilities": ["plateforme"]}, 422, "VAL-01", id="capacite-plateforme"),
        pytest.param({"organization_id": str(ORG_A)}, 422, "VAL-01", id="organisation-du-client"),
    ],
)
def test_accueil_refuse(
    plateforme: Platform, overrides: dict[str, Any], status: int, code: str
) -> None:
    env = plateforme
    _template(env)
    before = env.scalar("SELECT count(*) FROM organizations")
    response = _onboard(env, overrides.pop("slug", "assurance-refusee"), **overrides)
    assert response.status_code == status, response.text
    assert response.json()["code"] == code
    assert env.scalar("SELECT count(*) FROM organizations") == before


def test_identifiant_deja_pris(plateforme: Platform) -> None:
    env = plateforme
    _template(env)
    response = _onboard(env, ORG_A_SLUG)
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "ORG-01"


def test_tout_ou_rien(plateforme: Platform, monkeypatch: pytest.MonkeyPatch) -> None:
    """Une panne pendant la copie n'en laisse aucune trace : ni organisation, ni audit."""
    env = plateforme
    _template(env)

    async def broken(*_: object, **__: object) -> dict[str, int]:
        msg = "panne simulée pendant la copie"
        raise RuntimeError(msg)

    monkeypatch.setattr(PlatformRepository, "copy_template", broken)
    with pytest.raises(RuntimeError, match="panne simulée"):  # 500 SYS-01 côté client
        _onboard(env, "assurance-panne-ci")
    assert env.scalar("SELECT count(*) FROM organizations WHERE slug = 'assurance-panne-ci'") == 0
    assert (
        env.scalar(
            "SELECT count(*) FROM audit_events WHERE action = 'organization.created' "
            "AND metadata->>'slug' = 'assurance-panne-ci'"
        )
        == 0
    )


@pytest.mark.parametrize("who", ["admin", "gestionnaire", "assureur"])
def test_accueil_reserve_a_l_admin_de_plateforme(plateforme: Platform, who: str) -> None:
    env = plateforme
    for response in (
        env.client.post(ORGANIZATIONS, json={}, headers=env.auth(who)),
        _template(env, who=who),
        env.client.get(TEMPLATES, headers=env.auth(who)),
    ):
        assert response.status_code == 403, response.text
        assert response.json()["code"] == "AUTH-02"


def test_mutation_matrice_ouverte_la_base_refuse_encore(
    plateforme: Platform, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Matrice neutralisée (l'admin d'organisation autorisé) : la fonction du contrat refuse
    (MCP01 → 403), aucune organisation n'est créée. La garde de rôle tient sans l'API."""
    env = plateforme
    _template(env)
    opened = dict(permissions.OPERATION_ROLES)
    opened["createOrganization"] = frozenset({Role.ADMIN, Role.ADMIN_PLATEFORME})
    monkeypatch.setattr(permissions, "OPERATION_ROLES", MappingProxyType(opened))
    before = env.scalar("SELECT count(*) FROM organizations")
    body = {
        "slug": "assurance-intruse",
        "name": "Intrus",
        "country_code": "CI",
        "capabilities": ["gestionnaire"],
        "first_manager": {"idp_subject": "sub-intrus", "display_name": "Intrus"},
        "template": {"code": "mutuelle-ci"},
    }
    response = env.client.post(ORGANIZATIONS, json=body, headers=env.auth("admin"))
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "AUTH-02"
    assert env.scalar("SELECT count(*) FROM organizations") == before


def test_admin_plateforme_n_est_jamais_attribue_par_l_api(plateforme: Platform) -> None:
    env = plateforme
    response = env.client.post(
        "/v1/users",
        json={
            "idp_subject": "sub-escalade",
            "display_name": "Escalade",
            "roles": [{"role": "admin_plateforme"}],
        },
        headers=env.auth("admin"),
    )
    assert response.status_code == 422, response.text
    assert response.json()["errors"][0]["field"] == "roles.0.role"


# --- Revue P3 (CR-P3-02) : attaques du vérificateur rejouées, elles ne doivent plus rien isoler ---


def _published(env: Platform, path: str, who: str, frm: str, to: str) -> dict[str, Any]:
    response = env.client.get(path, params={"from": frm, "to": to}, headers=env.auth(who))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    body.pop("generated_at")
    return body


READERS = (("employeur_alpha", CONSUMPTION), ("assureur", PORTFOLIO))


def test_rv_periodes_j_puis_j_plus_un_rendent_la_meme_reponse(
    platform: Platform, portfolio: dict[str, Any]
) -> None:
    """Attaque : [J] puis [J, J+1] isolait le dossier d'UNE personne le jour J+1."""
    env = platform
    env.clock.current = START + timedelta(days=1, hours=1)  # vendredi 02/10, même semaine
    qr = _my_card(env, "p3adh1")["qr_payload"]
    added = _claim(env, qr, "+2250700009901", [{"act_code": "DENT-SOIN", "quantity": 1}])
    assert added["claim"]["status"] == "accordee_auto"
    # Semaine en cours : jamais publiée, quelle que soit la période demandée (ni J, ni J+1).
    for who, path in READERS:
        live = env.client.get(
            path, params={"from": "2026-10-01", "to": "2026-10-02"}, headers=env.auth(who)
        )
        assert (live.status_code, live.json()["code"]) == (422, "VAL-01"), live.text
    env.clock.current = READ_AT
    for who, path in READERS:
        one = _published(env, path, who, "2026-10-01", "2026-10-01")
        two = _published(env, path, who, "2026-10-01", "2026-10-02")
        assert one == two, who
        assert (one["period_from"], one["period_to"]) == (WEEK["from"], WEEK["to"])


def test_rv_periode_dans_le_futur(platform: Platform, portfolio: dict[str, Any]) -> None:
    env = platform
    env.clock.current = READ_AT
    cut = env.client.get(
        PORTFOLIO, params={"from": "2026-10-01", "to": "2027-09-30"}, headers=env.auth("assureur")
    )
    assert cut.status_code == 200, cut.text
    assert cut.json()["period_to"] == WEEK["to"]  # coupée à la dernière semaine terminée
    future = env.client.get(
        PORTFOLIO, params={"from": "2026-11-02", "to": "2026-11-30"}, headers=env.auth("assureur")
    )
    assert (future.status_code, future.json()["code"]) == (422, "VAL-01")


def test_rv_avant_apres_un_dossier_rien_ne_bouge(
    platform: Platform, portfolio: dict[str, Any]
) -> None:
    """Attaque : même période lue avant puis après UN dossier d'UN salarié (différence = 1)."""
    env = platform
    env.clock.current = READ_AT
    before = {who: _published(env, path, who, "2026-10-01", "2026-10-01") for who, path in READERS}
    qr = _my_card(env, "p3adh0")["qr_payload"]
    added = _claim(env, qr, "+2250700009900", [{"act_code": "DENT-SOIN", "quantity": 1}])
    assert added["claim"]["status"] == "accordee_auto"
    after = {who: _published(env, path, who, "2026-10-01", "2026-10-01") for who, path in READERS}
    assert after == before
    # Une semaine plus tard, la semaine du dossier est terminée : [S1, S2] contient une semaine
    # d'UNE personne. Tout ce qu'elle porte est masqué, la différence avec [S1] n'isole rien.
    env.clock.current = READ_AT + timedelta(days=7)
    assert (
        _published(env, CONSUMPTION, "employeur_alpha", *WEEK.values()) == before["employeur_alpha"]
    )
    group = _published(env, CONSUMPTION, "employeur_alpha", "2026-09-28", "2026-10-11")["groups"][0]
    assert _masked(group["claims"])
    assert _masked(group["covered_xof"])
    assert all(_masked(row["covered_xof"]) for row in group["benefits_by_category"])
    insurer = _published(env, PORTFOLIO, "assureur", "2026-09-28", "2026-10-11")
    for key in ("claims_cost_xof", "loss_ratio_bp", "decision_delay_mean_ms", "automation_rate_bp"):
        assert _masked(insurer[key]), key
    assert insurer["top_providers"] == []
    assert _masked(insurer["other_providers"]["covered_xof"])
    assert all(_masked(row["covered_xof"]) for row in insurer["benefits_by_category"])
    assert _shown(insurer["premiums_xof"])[0] % 1000 == 0  # semaine 2 sans cotisation


def test_rv_export_sans_valeur_exacte(platform: Platform, portfolio: dict[str, Any]) -> None:
    """CSV : comptes et effectifs par palier, montants au millier, cellules masquées vides."""
    env = platform
    env.clock.current = READ_AT + timedelta(days=7)
    response = env.client.get(
        f"{PORTFOLIO}/export",
        params={"from": "2026-09-28", "to": "2026-10-11"},
        headers=env.auth("assureur"),
    )
    assert response.status_code == 200, response.text
    rows = list(csv.reader(io.StringIO(response.text), delimiter=";"))[2:]
    assert rows
    for _section, _key, state, value, people, unit in rows:
        if state == "masque":
            assert (value, people) == ("", ""), _key
            continue
        assert int(people) in BANDS
        if unit == "nombre":
            assert int(value) in BANDS
        if unit == "xof":
            assert int(value) % 1000 == 0


def test_rv_assureur_aucune_ecriture() -> None:
    method = None
    methods: dict[str, str | None] = {}
    for line in OPENAPI_YAML.read_text().splitlines():
        found = re.match(r"^    (get|post|put|patch|delete):", line)
        if found:
            method = found.group(1)
        operation = re.match(r"^\s+operationId: (\w+)", line)
        if operation:
            methods[operation.group(1)] = method
    writes = {
        k
        for k, v in permissions.OPERATION_ROLES.items()
        if Role.ASSUREUR in v and methods[k] != "get"
    }
    assert writes <= {"recordProductEvent"}, writes


@pytest.mark.parametrize("who", ["employeur_alpha", "clinique_a", "medecin_conseil"])
def test_rv_accueil_refuse_aux_autres_roles(plateforme: Platform, who: str) -> None:
    response = plateforme.client.post(ORGANIZATIONS, json={}, headers=plateforme.auth(who))
    assert response.status_code == 403, response.text


def test_rv_premier_gestionnaire_sans_mot_de_passe(plateforme: Platform) -> None:
    env = plateforme
    _template(env)
    manager = {"idp_subject": "s", "display_name": "G", "password": "secret"}
    response = _onboard(env, "assurance-mdp", first_manager=manager)
    assert response.status_code == 422, response.text


def test_rv_trigger_admin_plateforme_hors_plateforme(plateforme: Platform) -> None:
    env = plateforme
    with psycopg.connect(env.dsn) as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE organization_id = %s LIMIT 1", (env.orgs["b"],)
        ).fetchone()
        assert row is not None
        with pytest.raises(psycopg.Error) as caught:
            conn.execute(
                "INSERT INTO user_roles (organization_id, user_id, role) "
                "VALUES (%s, %s, 'admin_plateforme')",
                (env.orgs["b"], row[0]),
            )
    assert caught.value.sqlstate == "MCP01"
