"""Marque blanche (Phase 3, x-lot P3, CR-P3-01) sur l'application ASSEMBLÉE.

Par l'API HTTP avec de vrais jetons, sous ``mulema_app`` (RLS forcée) et ``egress_guard``.
Gardes prouvées, chacune avec sa mutation : contraste WCAG AA calculé par le serveur (clair et
sombre), liste fermée de jetons (API puis base), logo non exécutable et hors liste blanche
refusé, rôle (admin d'organisation seulement), isolation (domaine d'une autre organisation,
réglages de B invisibles de A), lecture publique non sensible.

Revue P3 (CR-P3-02) : domaine réservé refusé (BRD-05), domaine servi seulement après preuve DNS
(port de test ``Platform.dns``, BRD-06 sinon), lecture publique sans oracle (inconnue = non
active), hôte de logo sur une liste DÉDIÉE (jamais HealthOS), déclaration XML stricte,
caractères de contrôle C1 et de direction refusés en 422 (jamais 500). Données fictives.
"""

from __future__ import annotations

import base64
import json
from dataclasses import asdict
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from api.branding import domains, palette, service
from api.branding.contrast import contrast_ratio
from api.branding.domains import verification_record
from api.tests.e2e.conftest import LOGO_HOST, ORG_A, ORG_A_SLUG, Platform

SETTINGS = "/v1/organization/branding"
VERIFY = "/v1/organization/branding/domain-verification"
PUBLIC = "/v1/public/branding"
GOLD = "#d97706"  # or de marque : 3,19:1 sur blanc
SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>Logo fictif</title>'
    '<circle cx="12" cy="12" r="10" fill="#1d4ed8"/></svg>'
)
SVG_SCRIPT = SVG.replace("<title>", "<script>alert(1)</script><title>")
DOMAIN = "sante.assurance-fictive.ci"


def _data_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _body(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    return {
        "display_name": "Assurance fictive Santé",
        "logo": {"kind": "data_uri", "src": _data_uri(SVG)},
        "theme": {
            "light": {"accent": "#1D4ED8", "accent_hover": "#1e3a8a"},
            "dark": {"accent": "#7dd3fc", "accent_hover": "#bae6fd", "accent_fg": "#0b1640"},
        },
        "custom_domain": DOMAIN,
        "legal_notice": "Assurance fictive SA, capital fictif.\nSiège : Abidjan (fictif).",
        "privacy_notice": "Données traitées en Côte d'Ivoire (fictif).",
    } | overrides


@pytest.fixture(scope="module")
def branded(platform: Platform) -> Platform:
    platform.add_user("admin", "a", "admin")
    platform.add_user("admin_b", "b", "admin")
    return platform


def _put(env: Platform, who: str, body: dict[str, Any]) -> Any:  # noqa: ANN401
    return env.client.put(SETTINGS, json=body, headers=env.auth(who))


def _public(env: Platform, **params: str) -> Any:  # noqa: ANN401
    return env.client.get(PUBLIC, params=params)


def _verify(env: Platform, who: str) -> Any:  # noqa: ANN401
    return env.client.post(VERIFY, headers=env.auth(who))


def _publish_txt(env: Platform, who: str) -> None:
    """L'organisation publie l'enregistrement TXT demandé (DNS de test, aucun réseau)."""
    record = env.client.get(SETTINGS, headers=env.auth(who)).json()["custom_domain_verification"]
    env.dns.publish(record["record_name"], record["record_value"])


def _problem(response: Any) -> dict[str, Any]:  # noqa: ANN401
    """Corps d'erreur sans ce qui change à chaque requête (identifiant de requête)."""
    body: dict[str, Any] = response.json()
    return {k: v for k, v in body.items() if k not in {"request_id", "instance", "trace_id"}}


def _accent(env: Platform) -> str | None:
    theme = _public(env, slug=ORG_A_SLUG).json()["theme"]
    accent: str | None = theme.get("light", {}).get("accent")
    return accent


# --- Lecture publique ----------------------------------------------------------------------------


def test_marque_par_defaut_avant_tout_reglage(branded: Platform) -> None:
    body = _public(branded, slug=ORG_A_SLUG)
    assert body.status_code == 200, body.text
    assert body.json() == {
        "slug": ORG_A_SLUG,
        "display_name": "Mutuelle MulemaCare (démonstration)",
        "country_code": "CI",
        "currency": "XOF",
        "logo": None,
        "theme": {},
        "custom_domain": None,
        "legal_notice": None,
        "privacy_notice": None,
    }


@pytest.mark.parametrize(
    ("params", "status", "code"),
    [
        pytest.param({}, 422, "VAL-01", id="sans-cle"),
        pytest.param({"slug": ORG_A_SLUG, "domain": DOMAIN}, 422, "VAL-01", id="deux-cles"),
        pytest.param({"slug": "inconnue-ci"}, 404, "NOT-01", id="inconnue"),
        pytest.param({"slug": "Majuscules"}, 422, "VAL-01", id="slug-invalide"),
    ],
)
def test_lecture_publique_refusee(
    branded: Platform, params: dict[str, str], status: int, code: str
) -> None:
    response = _public(branded, **params)
    assert response.status_code == status, response.text
    assert response.json()["code"] == code


# --- Écriture par l'admin d'organisation ---------------------------------------------------------


def test_admin_regle_sa_marque_et_lecture_publique(branded: Platform) -> None:
    env = branded
    response = _put(env, "admin", _body())
    assert response.status_code == 200, response.text
    settings = response.json()
    assert settings["customized"] is True
    assert settings["theme"]["light"] == {"accent": "#1d4ed8", "accent_hover": "#1e3a8a"}
    # Domaine déclaré mais pas prouvé : jamais servi, slug utilisable.
    assert settings["custom_domain_status"] == "en_attente_de_verification"
    assert _public(env, domain=DOMAIN).status_code == 404
    assert _public(env, slug=ORG_A_SLUG).json()["custom_domain"] is None
    _publish_txt(env, "admin")
    verified = _verify(env, "admin")
    assert verified.status_code == 200, verified.text
    assert verified.json()["custom_domain_status"] == "verifie"
    by_slug = _public(env, slug=ORG_A_SLUG).json()
    by_domain = _public(env, domain=DOMAIN.upper()).json()
    assert by_slug == by_domain
    assert by_slug["custom_domain"] == DOMAIN
    assert by_slug["display_name"] == "Assurance fictive Santé"
    assert by_slug["logo"] == {"kind": "data_uri", "src": _data_uri(SVG)}
    # Rien d'interne dans la lecture publique.
    dump = json.dumps(by_slug)
    assert str(ORG_A) not in dump
    assert str(env.users["admin"]) not in dump
    assert {"id", "organization_id", "updated_by", "updated_at", "customized"}.isdisjoint(by_slug)
    audit = env.rows(
        "SELECT actor_user_id, metadata->'tokens' FROM audit_events WHERE organization_id = %s "
        "AND action = 'organization.branding_updated' ORDER BY occurred_at DESC LIMIT 1",
        (ORG_A,),
    )
    assert audit[0][0] == env.users["admin"]
    assert "dark.accent_fg" in audit[0][1]


def test_logo_https_d_un_hote_de_logo_dedie(branded: Platform) -> None:
    env = branded
    src = f"https://{LOGO_HOST}/logos/fictif.png"
    response = _put(env, "admin", _body(logo={"kind": "url", "src": src}))
    assert response.status_code == 200, response.text
    assert _public(env, slug=ORG_A_SLUG).json()["logo"]["src"] == src


def test_logo_vers_healthos_refuse_brd_03(branded: Platform) -> None:
    """HealthOS est dans la liste blanche d'egress du SERVEUR, jamais une source d'image."""
    env = branded
    for path in ("/fhir/Patient/x", "/logos/fictif.png"):
        src = f"https://127.0.0.1:{env.healthos.port}{path}"
        response = _put(env, "admin", _body(logo={"kind": "url", "src": src}))
        assert (response.status_code, response.json()["code"]) == (422, "BRD-03"), src


# --- Garde de contraste --------------------------------------------------------------------------


def test_contraste_insuffisant_en_clair_refuse_brd_01(branded: Platform) -> None:
    env = branded
    assert _put(env, "admin", _body()).status_code == 200
    response = _put(env, "admin", _body(theme={"light": {"accent": GOLD}}))
    assert response.status_code == 422, response.text
    problem = response.json()
    assert problem["code"] == "BRD-01"
    fields = {e["field"]: e["message"] for e in problem["errors"]}
    assert "theme.light.accent" in fields
    assert any("3,19:1" in m and "4,5:1" in m for m in fields.values())
    assert _accent(env) == "#1d4ed8"  # rien d'enregistré


def test_contraste_insuffisant_en_sombre_refuse_brd_01(branded: Platform) -> None:
    response = _put(branded, "admin", _body(theme={"dark": {"accent_fg": "#4fc2b0"}}))
    assert response.status_code == 422
    assert response.json()["code"] == "BRD-01"
    assert {e["field"] for e in response.json()["errors"]} == {"theme.dark.accent_fg"}


def test_mutation_seuil_neutralise_la_couleur_passerait(
    branded: Platform, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Témoin : sans le seuil AA, le même or est accepté ; le refus vient bien de la garde."""
    env = branded
    monkeypatch.setattr(palette, "TEXT_MINIMUM", 1.0)
    monkeypatch.setattr(palette, "UI_MINIMUM", 1.0)
    weak = _put(env, "admin", _body(theme={"light": {"accent": GOLD, "accent_hover": "#b45309"}}))
    assert weak.status_code == 200, weak.text
    monkeypatch.undo()
    assert _put(env, "admin", _body()).status_code == 200  # remise en état conforme


# --- Liste fermée de jetons, pas de CSS libre ----------------------------------------------------


@pytest.mark.parametrize(
    ("theme", "field"),
    [
        pytest.param({"light": {"bg": "#000000"}}, "theme.light.bg", id="fond"),
        pytest.param({"light": {"fg": "#ffffff"}}, "theme.light.fg", id="encre"),
        pytest.param({"sun": {"accent": "#1d4ed8"}}, "theme.sun", id="plein-soleil"),
        pytest.param(
            {"light": {"accent": "#000; background: url(https://x)"}},
            "theme.light.accent",
            id="css-libre",
        ),
        pytest.param({"light": {"accent": "teal"}}, "theme.light.accent", id="nom-de-couleur"),
    ],
)
def test_jeton_hors_liste_refuse_brd_02(
    branded: Platform, theme: dict[str, Any], field: str
) -> None:
    response = _put(branded, "admin", _body(theme=theme))
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "BRD-02"
    assert field in {e["field"] for e in response.json()["errors"]}


def test_mutation_liste_fermee_retiree_de_l_api_la_base_refuse(
    branded: Platform, monkeypatch: pytest.MonkeyPatch
) -> None:
    """API neutralisée : la contrainte de la base refuse encore un jeton hors liste (rien écrit)."""
    env = branded
    monkeypatch.setattr(service, "check_theme_overrides", lambda _theme: [])
    with pytest.raises(IntegrityError, match="organization_branding_theme_check"):
        _put(env, "admin", _body(theme={"light": {"bg": "#000000"}}))
    stored = env.scalar(
        "SELECT theme::text FROM organization_branding WHERE organization_id = %s", (ORG_A,)
    )
    assert '"bg"' not in stored


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"display_name": "<style>body{}</style>"}, id="balise-nom"),
        pytest.param({"legal_notice": "<script>alert(1)</script>"}, id="balise-mentions"),
        pytest.param({"css": "body{background:red}"}, id="champ-css"),
        pytest.param({"custom_domain": "https://x.ci"}, id="domaine-url"),
    ],
)
def test_texte_brut_seulement(branded: Platform, overrides: dict[str, Any]) -> None:
    response = _put(branded, "admin", _body(**overrides))
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VAL-01"


# --- Logo ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "logo",
    [
        pytest.param({"kind": "data_uri", "src": _data_uri(SVG_SCRIPT)}, id="svg-script"),
        pytest.param({"kind": "url", "src": "https://cdn.example.com/logo.png"}, id="hors-liste"),
        pytest.param({"kind": "url", "src": "javascript:alert(1)"}, id="javascript"),
        pytest.param({"kind": "data_uri", "src": "data:text/html;base64,PHNjcmlwdD4="}, id="html"),
    ],
)
def test_logo_refuse_brd_03(branded: Platform, logo: dict[str, str]) -> None:
    response = _put(branded, "admin", _body(logo=logo))
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "BRD-03"
    assert "script" not in json.dumps(_public(branded, slug=ORG_A_SLUG).json())


# --- Rôles et isolation --------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["gestionnaire", "medecin_conseil", "clinique_a"])
def test_reglages_reserves_a_l_admin(branded: Platform, who: str) -> None:
    for response in (
        _put(branded, who, _body()),
        branded.client.get(SETTINGS, headers=branded.auth(who)),
    ):
        assert response.status_code == 403, response.text
        assert response.json()["code"] == "AUTH-02"


def test_sans_jeton_refuse(branded: Platform) -> None:
    assert branded.client.put(SETTINGS, json=_body()).status_code == 401
    assert branded.client.get(SETTINGS).status_code == 401


def test_domaine_d_une_autre_organisation_refuse_brd_04(branded: Platform) -> None:
    env = branded
    assert _put(env, "admin", _body()).status_code == 200
    taken = _put(env, "admin_b", _body(display_name="Marque B fictive"))
    assert taken.status_code == 409, taken.text
    assert taken.json()["code"] == "BRD-04"
    own = _put(env, "admin_b", _body(display_name="Marque B fictive", custom_domain="b.fictif.ci"))
    assert own.status_code == 200, own.text


def test_reglages_de_b_invisibles_de_a(branded: Platform) -> None:
    env = branded
    other = _put(env, "admin_b", _body(display_name="Marque B", custom_domain="b2.fictif.ci"))
    assert other.status_code == 200, other.text
    assert _put(env, "admin", _body()).status_code == 200
    mine = env.client.get(SETTINGS, headers=env.auth("admin")).json()
    theirs = env.client.get(SETTINGS, headers=env.auth("admin_b")).json()
    assert mine["display_name"] == "Assurance fictive Santé"
    assert theirs["display_name"] == "Marque B"
    rows = env.rows("SELECT organization_id FROM organization_branding ORDER BY organization_id")
    assert {r[0] for r in rows} == {ORG_A, env.orgs["b"]}


# --- Revue P3 (CR-P3-02) : domaine détournable -------------------------------------------------


@pytest.mark.parametrize(
    "domain",
    [
        "payer.mulemacare.invalid",  # hôte du lien de paiement public de l'instance
        "x.payer.mulemacare.invalid",
        "mulemacare.com",
        "www.mulemacare.com",
        "intranet.local",
        "healthos.ci.mulemacare.internal",
        "assurance.example",
    ],
)
def test_domaine_reserve_refuse_brd_05(branded: Platform, domain: str) -> None:
    env = branded
    response = _put(env, "admin_b", _body(display_name="Marque B pirate", custom_domain=domain))
    assert (response.status_code, response.json()["code"]) == (422, "BRD-05"), response.text
    assert {e["field"] for e in response.json()["errors"]} == {"custom_domain"}
    assert _public(env, domain=domain).status_code == 404
    stored = env.rows(
        "SELECT custom_domain FROM organization_branding WHERE custom_domain = %s", (domain,)
    )
    assert stored == []


@pytest.mark.parametrize("domain", ["localhost", "Sante.CI", "evil.example/x", "a.ci:443"])
def test_domaine_mal_forme_refuse_val_01(branded: Platform, domain: str) -> None:
    response = _put(branded, "admin_b", _body(display_name="Marque B", custom_domain=domain))
    assert (response.status_code, response.json()["code"]) == (422, "VAL-01"), response.text


def test_mutation_liste_reservee_neutralisee_le_domaine_n_est_toujours_pas_servi(
    branded: Platform, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Liste réservée retirée : le domaine de la plateforme est enregistré mais reste en attente
    (aucune preuve DNS possible), donc jamais servi. Deux gardes indépendantes."""
    env = branded
    monkeypatch.setattr(domains.ReservedDomains, "reserves", lambda _self, _domain: False)
    response = _put(env, "admin_b", _body(display_name="B", custom_domain="pay.mulemacare.com"))
    assert response.status_code == 200, response.text
    assert response.json()["custom_domain_status"] == "en_attente_de_verification"
    assert _verify(env, "admin_b").json()["code"] == "BRD-06"
    assert _public(env, domain="pay.mulemacare.com").status_code == 404
    monkeypatch.undo()
    assert _put(env, "admin_b", _body(display_name="B", custom_domain=None)).status_code == 200


def test_verification_exige_l_enregistrement_txt_brd_06(branded: Platform) -> None:
    env = branded
    domain = "sante.b-fictive.ci"
    settings = _put(env, "admin_b", _body(display_name="Marque B", custom_domain=domain)).json()
    record = settings["custom_domain_verification"]
    assert record["record_type"] == "TXT"
    assert record["record_name"] == f"_mulemacare-verification.{domain}"
    token = record["record_value"].removeprefix("mulemacare-verification=")
    assert record == asdict(verification_record(domain, token))
    refused = _verify(env, "admin_b")
    assert (refused.status_code, refused.json()["code"]) == (422, "BRD-06"), refused.text
    # Le jeton d'une AUTRE organisation, ou publié sous un autre nom, ne prouve rien.
    env.dns.publish(domain, record["record_value"])
    env.dns.publish(record["record_name"], "mulemacare-verification=" + "0" * 32)
    assert _verify(env, "admin_b").json()["code"] == "BRD-06"
    assert _public(env, domain=domain).status_code == 404
    env.dns.publish(record["record_name"], record["record_value"])
    ok = _verify(env, "admin_b")
    assert ok.status_code == 200, ok.text
    assert ok.json()["custom_domain_status"] == "verifie"
    public = _public(env, domain=domain)
    assert public.status_code == 200
    assert public.json()["display_name"] == "Marque B"
    audit = env.rows(
        "SELECT count(*) FROM audit_events WHERE organization_id = %s "
        "AND action = 'organization.custom_domain_verified'",
        (env.orgs["b"],),
    )
    assert audit == [(1,)]


def test_changer_de_domaine_reinitialise_la_verification(branded: Platform) -> None:
    env = branded
    first = "b4.fictif.ci"
    _put(env, "admin_b", _body(display_name="Marque B", custom_domain=first))
    _publish_txt(env, "admin_b")
    assert _verify(env, "admin_b").json()["custom_domain_status"] == "verifie"
    old_token = env.client.get(SETTINGS, headers=env.auth("admin_b")).json()[
        "custom_domain_verification"
    ]["record_value"]
    # Même domaine réenregistré : la preuve tient.
    same = _put(env, "admin_b", _body(display_name="Marque B2", custom_domain=first)).json()
    assert same["custom_domain_status"] == "verifie"
    # Autre domaine : nouvelle preuve exigée, nouveau jeton, l'ancien domaine n'est plus servi.
    moved = _put(env, "admin_b", _body(display_name="Marque B", custom_domain="b5.fictif.ci"))
    assert moved.json()["custom_domain_status"] == "en_attente_de_verification"
    assert moved.json()["custom_domain_verification"]["record_value"] != old_token
    assert _public(env, domain=first).status_code == 404
    assert _public(env, domain="b5.fictif.ci").status_code == 404


def test_verification_reservee_a_l_admin(branded: Platform) -> None:
    for who in ("gestionnaire", "medecin_conseil"):
        response = _verify(branded, who)
        assert (response.status_code, response.json()["code"]) == (403, "AUTH-02")
    assert branded.client.post(VERIFY).status_code == 401


def test_sans_domaine_rien_a_verifier(branded: Platform) -> None:
    env = branded
    assert (
        _put(env, "admin_b", _body(display_name="Marque B", custom_domain=None)).status_code == 200
    )
    settings = env.client.get(SETTINGS, headers=env.auth("admin_b")).json()
    assert (settings["custom_domain_status"], settings["custom_domain_verification"]) == (
        None,
        None,
    )
    assert _verify(env, "admin_b").json()["code"] == "BRD-06"


# --- Revue P3 (CR-P3-02) : lecture publique sans oracle ----------------------------------------


@pytest.mark.parametrize("state", ["integration", "inactive"])
def test_lecture_publique_organisation_non_active_comme_inconnue(
    branded: Platform, state: str
) -> None:
    env = branded
    b_slug = env.scalar("SELECT slug FROM organizations WHERE id = %s", (env.orgs["b"],))
    assert _public(env, slug=b_slug).status_code == 200  # témoin : active, servie
    unknown = _public(env, slug="zz-inconnue")
    try:
        env.rows(
            "UPDATE organizations SET status = %s WHERE id = %s RETURNING id",
            (state, env.orgs["b"]),
        )
        hidden = _public(env, slug=b_slug)
        assert (hidden.status_code, unknown.status_code) == (404, 404)
        assert _problem(hidden) == _problem(unknown)
    finally:
        env.rows(
            "UPDATE organizations SET status = 'active' WHERE id = %s RETURNING id",
            (env.orgs["b"],),
        )


# --- Revue P3 (CR-P3-02) : texte brut, jamais de 500 ------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("A\u0085B", id="c1-nel"),
        pytest.param("A\u009bB", id="c1-csi"),
        pytest.param("Assur\u202eecnaruss", id="bidi-rlo"),
        pytest.param("A\u2066B", id="bidi-isolat"),
        pytest.param("A\u2028B", id="separateur-de-ligne"),
        pytest.param("A\ufeffB", id="bom"),
    ],
)
def test_nom_avec_caractere_de_controle_422(branded: Platform, name: str) -> None:
    response = _put(branded, "admin", _body(display_name=name))
    assert (response.status_code, response.json()["code"]) == (422, "VAL-01"), response.text


# ============================== Revue P3 : attaques du vérificateur ==============================
_E = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{}</svg>'
_X = 'xmlns:xlink="http://www.w3.org/1999/xlink"'


@pytest.mark.parametrize(
    "theme",
    [
        {"light": {"accent": "#7fd3c6"}},
        {"dark": {"accent": "#0b3f3a"}},
        {"light": {"brand_deep": "#9ad0c8"}},
        {"light": {"accent_hover": "#5fd0c0"}},
        {"light": {"accent": "#166534"}},
        {"dark": {"accent": "#4fc2b0", "accent_fg": "#4fc2b0"}},
    ],
)
def test_rv_contraste(branded: Platform, theme: dict[str, Any]) -> None:
    r = _put(branded, "admin", _body(theme=theme))
    assert (r.status_code, r.json()["code"]) == (422, "BRD-01"), r.text


@pytest.mark.parametrize(
    "theme",
    [
        {"light": {"focus": "#000000"}},
        {"light": {"bg": "#000000"}},
        {"sun": {"accent": "#000000"}},
        {"light": {"--accent": "#1d4ed8"}},
        {"light": {"accent": "red"}},
        {"light": {"accent": "#fff"}},
        {"light": {"accent": "#1d4ed8;background:url(https://x.example)"}},
        {"light": {"accent": "var(--crit)"}},
        {"light": {"accent": "#1d4ed8\n"}},
        {"light": {"accent": ["#1d4ed8"]}},
        {"light": {"accent": None}},
        {"light": "#1d4ed8"},
        {"light": {"accent": "#1d4ed8", "css": "body{display:none}"}},
    ],
)
def test_rv_jeton_ou_css_libre(branded: Platform, theme: dict[str, Any]) -> None:
    r = _put(branded, "admin", _body(theme=theme))
    assert (r.status_code, r.json()["code"]) == (422, "BRD-02"), r.text


def test_rv_sonde_accent_fg_clair_conforme(branded: Platform) -> None:
    """Sonde du vérificateur : #e0f0ff sur l'accent par défaut #097268 = 5,0:1 (AA : 4,5:1) ;
    sur l'accent survolé #075e56, davantage. Conforme, donc accepté (ce n'est pas un défaut)."""
    assert contrast_ratio("#e0f0ff", "#097268") >= palette.TEXT_MINIMUM
    response = _put(branded, "admin", _body(theme={"light": {"accent_fg": "#e0f0ff"}}))
    assert response.status_code == 200, response.text
    assert _put(branded, "admin", _body()).status_code == 200  # remise en état


_BAD_SVG = {
    "onload": '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><title>t</title></svg>',
    "foreign": _E.format(
        '<foreignObject><div xmlns="http://www.w3.org/1999/xhtml">x</div></foreignObject>'
    ),
    "foreign-vide": _E.format('<foreignObject width="1" height="1"/>'),
    "image": _E.format('<image href="https://evil.example/x.png"/>'),
    "use-xlink": (
        f'<svg xmlns="http://www.w3.org/2000/svg" {_X}>'
        '<use xlink:href="https://evil.example/a.svg#a"/></svg>'
    ),
    "style-attr": _E.format('<circle r="1" style="fill:url(https://evil.example/a)"/>'),
    "style-el": _E.format("<style>@import url(https://evil.example/x.css);</style>"),
    "fill-ext": _E.format('<circle r="1" fill="url(https://evil.example/#a)"/>'),
    "fill-entite": _E.format('<circle r="1" fill="&#117;rl(https://evil.example/#a)"/>'),
    "doctype": '<!DOCTYPE svg [<!ENTITY x "y">]>' + _E.format("<title>&x;</title>"),
    "commentaire": _E.format("<!-- x --><title>t</title>"),
    "pi-stylesheet-seule": '<?xml-stylesheet type="text/css" href="https://evil.example/x.css"?>'
    + _E.format("<title>t</title>"),
    "pi-apres-decl": '<?xml version="1.0"?><?xml-stylesheet href="https://evil.example/x.css"?>'
    + _E.format("<title>t</title>"),
    "script-ns": _E.format(
        '<svg:script xmlns:svg="http://www.w3.org/2000/svg">alert(1)</svg:script>'
    ),
    "a-href": _E.format('<a href="javascript:alert(1)"><circle r="1"/></a>'),
    "animate": _E.format('<set attributeName="href" to="javascript:alert(1)"/>'),
    "xml-base": '<svg xmlns="http://www.w3.org/2000/svg" xml:base="https://evil.example/"/>',
}


@pytest.mark.parametrize("name", list(_BAD_SVG))
def test_rv_svg(branded: Platform, name: str) -> None:
    r = _put(branded, "admin", _body(logo={"kind": "data_uri", "src": _data_uri(_BAD_SVG[name])}))
    assert (r.status_code, r.json().get("code")) == (422, "BRD-03"), (name, r.text[:200])


def _b64(raw: bytes, mime: str) -> str:
    return f"data:image/{mime};base64," + base64.b64encode(raw).decode()


@pytest.mark.parametrize(
    "src",
    [
        pytest.param(_b64(b"\x89PNG\r\n\x1a\n" + b"\0" * (32 * 1024), "png"), id="png-33k"),
        pytest.param(_b64(SVG.encode(), "png"), id="svg-annonce-png"),
        pytest.param(_b64(b"\x89PNG\r\n\x1a\n" + b"\0" * 10, "svg+xml"), id="png-annonce-svg"),
        pytest.param(_b64(b"<html><script>1</script>", "jpeg"), id="html-annonce-jpeg"),
        pytest.param("data:image/svg+xml;utf8," + SVG, id="non-base64"),
        pytest.param("data:image/svg+xml;charset=utf-8;base64,AAAA", id="param-mime"),
        pytest.param("data:image/PNG;base64,AAAA", id="mime-majuscule"),
        pytest.param(_b64(b"\x89PNG\r\n\x1a\n" + b"\0" * (200 * 1024), "png"), id="geant"),
    ],
)
def test_rv_data_uri(branded: Platform, src: str) -> None:
    r = _put(branded, "admin", _body(logo={"kind": "data_uri", "src": src}))
    assert r.status_code == 422, r.text[:200]


def test_rv_url(branded: Platform) -> None:
    port = branded.healthos.port
    for src in (
        f"https://127.0.0.1:{port}@evil.example/x.png",
        f"https://evil.example@127.0.0.1:{port}/x.png",
        f"https://127.0.0.1:{port}/x.png?a=1",
        f"https://127.0.0.1:{port + 1}/x.png",
        "https://127.0.0.1/x.png",
        "//evil.example/x.png",
        "/\\evil.example/x.png",
        "/a/../../x.png",
        "http://127.0.0.1/x.png",
        f"https://127.0.0.1:{port}/a/%2e%2e/x",
        "data:image/png;base64,iVBORw0KGgo=",
        f"https://{LOGO_HOST}:8443/x.png",
        f"http://{LOGO_HOST}/x.png",
    ):
        r = _put(branded, "admin", _body(logo={"kind": "url", "src": src}))
        assert r.status_code == 422, (src, r.text[:200])


@pytest.mark.parametrize(
    "name",
    ["<b>x</b>", '"><img src=x onerror=alert(1)>', "a\nb", "a\x00b", "a\x7fb"],
)
def test_rv_nom_html(branded: Platform, name: str) -> None:
    r = _put(branded, "admin", _body(display_name=name))
    assert r.status_code == 422, r.text[:200]


def test_rv_legal_html(branded: Platform) -> None:
    r = _put(branded, "admin", _body(legal_notice="<script>alert(1)</script>"))
    assert r.status_code == 422


def test_rv_roles_ecriture(branded: Platform) -> None:
    env = branded
    env.add_user("rv_assureur", "a", "assureur")
    assert _put(env, "rv_assureur", _body()).status_code == 403
    assert env.client.get(SETTINGS, headers=env.auth("rv_assureur")).status_code == 403
    assert _verify(env, "rv_assureur").status_code == 403
    # Corps qui tente de viser une autre organisation : champs inconnus refusés.
    r = _put(env, "admin", _body() | {"organization_id": str(env.orgs["b"])})
    assert r.status_code == 422
