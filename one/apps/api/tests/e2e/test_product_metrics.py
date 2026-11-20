"""Mesure produit (Phase 2, voie B, x-lot P2, CR-P2-01, CR-P2-02) sur l'application ASSEMBLÉE.

Tout passe par l'API HTTP avec de vrais jetons, sous ``mulema_app`` (RLS forcée) et
``egress_guard`` (suite + liste blanche de l'application) : aucun traceur tiers, rien ne sort.

Jeu de l'organisation A, construit par les parcours réels :
- six adhérents inscrits par le gestionnaire, chacun avec son compte adhérent ;
- six dossiers au comptoir (QR affiché par l'espace adhérent) : deux accordés automatiquement
  (R-12), quatre en revue (R-20) décidés par le médecin-conseil 1 h, 2 h, 3 h et 4 h après la
  demande (deux accordés, deux refusés) ;
- six liens « inviter un proche à payer », cinq payés par webhook signé, dont un rejoué ;
- le grand livre alimenté par le consommateur L3 (dossiers accordés, cotisations reçues) ;
- des événements d'usage envoyés par les écrans (cinq agents de comptoir, six adhérents).
L'organisation B (jeu d'isolation) envoie ses propres événements : ils ne comptent jamais pour A.

Contributeur = PERSONNE (empreinte HMAC de l'utilisateur du jeton, clé du serveur), jamais la
session : recharger la page ne fabrique pas de contributeur. Publication par semaines civiles
entières et terminées, chaque semaine au seuil, effectif par palier (CR-P2-02) : les attaques du
vérificateur (personne seule qui recharge cinq fois ; deux périodes dont la différence isole une
contribution) sont rejouées ici. Données fictives.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
import pytest

from api.ledger.consumer import DrainReport, drain_outbox
from api.members.jobs import run_daily
from api.metrics.catalog import person_ref
from api.metrics.jobs import purge_expired_events
from api.metrics.privacy import contributor_band
from api.metrics.runtime import MetricsRuntime
from api.metrics.windows import retained_since
from api.payments.jobs import issue_month
from api.tests.e2e.conftest import ORG_A, ORG_A_SLUG, Platform
from api.tests.e2e.test_member_space import (
    ITEMS_48000,
    ITEMS_185000,
    _add_adherent,
    _claim,
    _contribution_id,
    _enroll,
    _my_card,
)

START = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)  # jeudi
OCTOBER = date(2026, 10, 1)
ZONE = ZoneInfo("Africa/Abidjan")  # fuseau des deux organisations du jeu
HOUR = timedelta(hours=1)
MEMBERS = 6
EVENTS = "/v1/telemetry/events"
METRICS = "/v1/metrics/product"
COUNTER_KEY = "counter_decision_display_median_ms"
COUNTER_A = ["clinique_a", "clinique_a1", "clinique_a2", "clinique_a3", "clinique_a4"]
B_FOUR = ["clinique_b1", "clinique_b2", "clinique_b3", "clinique_b4"]
B_FIVE = ["clinique_b", *B_FOUR]


def _session() -> str:
    """Identifiant de session comme le tire le navigateur : 16 octets aléatoires en hexadécimal."""
    return secrets.token_hex(16)


def _send(env: Platform, who: str, **event: Any) -> int:  # noqa: ANN401
    response = env.client.post(EVENTS, json=event, headers=env.auth(who))
    code: int = response.status_code
    return code


def _runtime(env: Platform) -> MetricsRuntime:
    runtime: MetricsRuntime = env.client.app.state.p2_metrics  # type: ignore[attr-defined]
    return runtime


def _next_week(env: Platform) -> date:
    """Avance l'horloge au lundi suivant, 09:00 UTC ; renvoie ce lundi."""
    today = env.clock.now().date()
    monday = today - timedelta(days=today.weekday()) + timedelta(days=7)
    env.clock.current = datetime.combine(monday, time(9), UTC)
    return monday


def _week(monday: date) -> dict[str, str]:
    return {"from": monday.isoformat(), "to": (monday + timedelta(days=6)).isoformat()}


def _window(env: Platform) -> dict[str, str]:
    """Du jeu (horloge de test ET horloge réelle des liens) jusqu'au jour de l'horloge."""
    today = datetime.now(UTC).date()
    return {
        "from": (min(OCTOBER, today) - timedelta(days=1)).isoformat(),
        "to": env.clock.now().date().isoformat(),
    }


def _body(
    env: Platform, who: str = "gestionnaire", params: dict[str, str] | None = None
) -> dict[str, Any]:
    response = env.client.get(METRICS, params=params or _window(env), headers=env.auth(who))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert body["k_anonymity_threshold"] == 5
    return body


def _metrics(
    env: Platform, who: str = "gestionnaire", params: dict[str, str] | None = None
) -> dict[str, dict[str, Any]]:
    return {item["key"]: item for item in _body(env, who, params)["items"]}


def _state(metric: dict[str, Any]) -> tuple[Any, Any, Any]:
    return metric["status"], metric["value"], metric["contributors"]


MASKED = ("masque", None, None)


def _drain(env: Platform) -> DrainReport:
    async def run() -> DrainReport:
        async with env.database.autocommit_connection() as conn:
            return await drain_outbox(conn, ORG_A)

    return env.run(run)


def _pay(env: Platform, who: str, contribution: str, *, replay: bool = False) -> None:
    link = env.client.post(
        f"/v1/me/contributions/{contribution}/payment-links", headers=env.headers(who)
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
    for _ in range(2 if replay else 1):
        hook = env.client.post(
            f"/v1/webhooks/{ORG_A_SLUG}/payments/wave",
            content=note.body,
            headers={"Content-Type": "application/json", "X-Signature": note.signature},
        )
        assert hook.status_code == 200, hook.text


@pytest.fixture(scope="module")
def measured(platform: Platform) -> dict[str, Any]:
    env = platform
    env.clock.current = START
    env.add_user("admin", "a", "admin")
    env.add_user("gestionnaire_b", "b", "gestionnaire")
    for who in COUNTER_A[1:]:
        env.add_user(who, "a", "clinique", env.providers["a"])
    for who in B_FOUR:
        env.add_user(who, "b", "clinique", env.providers["b"])
    phones = [f"+22507000088{i:02d}" for i in range(MEMBERS)]
    members = [_enroll(env, f"Mesure{i}", phone) for i, phone in enumerate(phones)]
    env.run(run_daily, env.database, ORG_A, env.clock.now())  # carence écoulée : actifs
    env.run(issue_month, env.database, ORG_A, OCTOBER, env.clock.now())
    for i, member in enumerate(members):
        _add_adherent(env, f"adh{i}", "a", UUID(member["id"]))
    member_b = UUID(
        str(env.scalar("SELECT id FROM members WHERE organization_id = %s", (env.orgs["b"],)))
    )
    _add_adherent(env, "adherent_b", "b", member_b)

    # Dossiers : deux accordés automatiquement, quatre en revue (même instant de demande).
    claims = [
        _claim(
            env,
            _my_card(env, f"adh{i}")["qr_payload"],
            phones[i],
            ITEMS_48000 if i < 2 else ITEMS_185000,
        )["claim"]
        for i in range(MEMBERS)
    ]
    assert [c["status"] for c in claims] == ["accordee_auto"] * 2 + ["en_revue"] * 4
    for claim, decision in zip(
        claims[2:], ("accorder", "accorder", "refuser", "refuser"), strict=True
    ):
        env.clock.advance(HOUR)
        decided = env.client.post(
            f"/v1/claims/{claim['id']}/decisions",
            json={"decision": decision, "reason_code": "MC-02"},
            headers=env.headers("medecin_conseil"),
        )
        assert decided.status_code == 200, decided.text

    # Liens de paiement : six créés, cinq payés (le premier webhook rejoué).
    contributions = [_contribution_id(env, m["id"]) for m in members]
    for i, contribution in enumerate(contributions[:5]):
        _pay(env, f"adh{i}", contribution, replay=i == 0)
    unpaid = env.client.post(
        f"/v1/me/contributions/{contributions[5]}/payment-links", headers=env.headers("adh5")
    )
    assert unpaid.status_code == 201, unpaid.text
    report = _drain(env)
    assert report.failed == 0, report

    # Écrans : six parcours d'accueil dans l'espace adhérent, cinq terminés ; la carte présentée
    # 10, 20, 30, 40 et 50 s après le début (médiane 30 s).
    sessions = [_session() for _ in range(MEMBERS)]
    for i, session in enumerate(sessions):
        base = {"surface": "espace_adherent", "role": "adherent", "session_id": session}
        assert _send(env, f"adh{i}", name="onboarding_started", **base) == 204
        assert _send(env, f"adh{i}", name="onboarding_step", step=1, **base) == 204
    for i, session in enumerate(sessions[:5]):
        env.clock.advance(timedelta(seconds=10))
        base = {"surface": "espace_adherent", "role": "adherent", "session_id": session}
        assert _send(env, f"adh{i}", name="card_presented", variant="en_ligne", **base) == 204
        assert _send(env, f"adh{i}", name="onboarding_completed", **base) == 204
    # Comptoir de A : cinq agents, une décision affichée chacun (médiane 6 s) ; comptoir de B :
    # quatre agents, très lents (ils fausseraient la médiane de A si l'isolation cédait).
    for who, duration in zip(COUNTER_A, (4000, 5000, 6000, 7000, 9000), strict=True):
        assert _counter(env, who, duration) == 204
    for who in B_FOUR:
        assert _counter(env, who, 80_000) == 204
    # Lecture la semaine qui suit le jeu (horloge de test ET horloge réelle des liens) : seules
    # les semaines terminées sont publiées.
    env.clock.current = max(env.clock.now(), datetime.now(UTC))
    _next_week(env)
    return {"members": members, "claims": claims, "contributions": contributions}


def _counter(env: Platform, who: str, duration: int) -> int:
    return _send(
        env,
        who,
        name="counter_decision_shown",
        surface="comptoir",
        role="clinique",
        session_id=_session(),
        variant="accordee",
        duration_ms=duration,
    )


# --- (1) recordProductEvent ---------------------------------------------------------------------


def test_evenement_stocke_sans_identifiant_de_personne(
    platform: Platform, measured: dict[str, Any]
) -> None:
    env = platform
    session = _session()
    assert (
        _send(
            env,
            "gestionnaire",
            name="palette_opened",
            surface="console",
            role="gestionnaire",
            session_id=session,
            variant="clavier",
        )
        == 204
    )
    rows = env.rows(
        "SELECT organization_id, role, surface, variant, session_ref FROM product_events "
        "WHERE name = 'palette_opened'"
    )
    assert len(rows) == 1
    org, role, surface, variant, ref = rows[0]
    assert (org, role, surface, variant) == (ORG_A, "gestionnaire", "console", "clavier")
    # Empreinte HMAC de l'utilisateur du jeton, avec la clé du serveur (absente de la base).
    user = env.users["gestionnaire"]
    assert ref == person_ref(_runtime(env).pseudonym_key, ORG_A, user)
    assert session not in ref
    # Rien qui relie l'événement à l'utilisateur : ni son identifiant, ni la session envoyée.
    dump = str(env.rows("SELECT row_to_json(e) FROM product_events e"))
    assert str(user) not in dump
    assert user.hex not in dump
    assert session not in dump


def test_meme_personne_meme_empreinte_quelle_que_soit_la_session(
    platform: Platform, measured: dict[str, Any]
) -> None:
    """Le contributeur ne vient pas du client : deux sessions de adh2, une seule empreinte."""
    env = platform
    base = {"name": "offline_banner_seen", "surface": "espace_adherent", "role": "adherent"}
    for who in ("adh2", "adh2", "adh3"):
        assert _send(env, who, session_id=_session(), **base) == 204
    refs = env.rows(
        "SELECT session_ref FROM product_events WHERE organization_id = %s "
        "AND name = 'offline_banner_seen' ORDER BY occurred_at, id",
        (ORG_A,),
    )
    assert len(refs) == 3
    assert len({r[0] for r in refs}) == 2


@pytest.mark.parametrize(
    ("who", "event", "expected"),
    [
        pytest.param(
            "adh0",
            {"name": "page_viewed", "surface": "espace_adherent", "role": "adherent"},
            (422, "VAL-01"),
            id="nom-hors-liste-blanche",
        ),
        pytest.param(
            "adh0",
            {
                "name": "onboarding_started",
                "surface": "espace_adherent",
                "role": "adherent",
                "comment": "texte libre",
            },
            (422, "VAL-01"),
            id="champ-inconnu",
        ),
        pytest.param(
            "adh0",
            {
                "name": "notification_opened",
                "surface": "espace_adherent",
                "role": "adherent",
                "variant": "Mesure0 Fictif",
            },
            (422, "VAL-01"),
            id="texte-libre",
        ),
        pytest.param(
            "adh0",
            {
                "name": "palette_opened",
                "surface": "console",
                "role": "adherent",
                "variant": "bouton",
            },
            (422, "VAL-01"),
            id="surface-du-role-ignoree",
        ),
        pytest.param(
            "adh0",
            {
                "name": "palette_opened",
                "surface": "console",
                "role": "gestionnaire",
                "variant": "bouton",
            },
            (403, "AUTH-02"),
            id="role-usurpe",
        ),
        pytest.param(
            "clinique_a",
            {
                "name": "counter_decision_shown",
                "surface": "comptoir",
                "role": "clinique",
                "variant": "accordee",
            },
            (422, "VAL-01"),
            id="duree-obligatoire-manquante",
        ),
        pytest.param(
            "clinique_a",
            {
                "name": "counter_decision_shown",
                "surface": "comptoir",
                "role": "clinique",
                "variant": "accordee",
                "duration_ms": 300_001,
            },
            (422, "VAL-01"),
            id="duree-comptoir-hors-borne",
        ),
        pytest.param(
            "adh0",
            {
                "name": "claim_tracking_viewed",
                "surface": "espace_adherent",
                "role": "adherent",
                "duration_ms": 1200,
            },
            (422, "VAL-01"),
            id="duree-sur-un-evenement-sans-duree",
        ),
        pytest.param(
            "adh0",
            {
                "name": "onboarding_started",
                "surface": "espace_adherent",
                "role": "adherent",
                "session_id": "k3Jd9-QpL2x_7HvN0aZtRw",
            },
            (422, "VAL-01"),
            id="session-base64url",
        ),
        pytest.param(
            "adh0",
            {
                "name": "onboarding_started",
                "surface": "espace_adherent",
                "role": "adherent",
                "session_id": "3F9C2A7BE41D48C09A5E6B1F0D2C8E74",
            },
            (422, "VAL-01"),
            id="session-majuscules",
        ),
    ],
)
def test_evenement_refuse(
    platform: Platform,
    measured: dict[str, Any],
    who: str,
    event: dict[str, Any],
    expected: tuple[int, str],
) -> None:
    env = platform
    status, code = expected
    before = env.scalar("SELECT count(*) FROM product_events")
    response = env.client.post(
        EVENTS, json={"session_id": _session()} | event, headers=env.auth(who)
    )
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == code
    assert env.scalar("SELECT count(*) FROM product_events") == before


def test_session_portant_l_identifiant_de_l_utilisateur_refusee(
    platform: Platform, measured: dict[str, Any]
) -> None:
    env = platform
    event = {
        "name": "onboarding_started",
        "surface": "espace_adherent",
        "role": "adherent",
        "session_id": env.users["adh0"].hex,
    }
    response = env.client.post(EVENTS, json=event, headers=env.auth("adh0"))
    assert response.status_code == 422, response.text
    assert [e["field"] for e in response.json()["errors"]] == ["session_id"]


def test_sans_jeton_rien_n_est_enregistre(platform: Platform, measured: dict[str, Any]) -> None:
    env = platform
    event = {"name": "onboarding_started", "surface": "espace_adherent", "role": "adherent"}
    response = env.client.post(EVENTS, json=event | {"session_id": _session()})
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH-01"


# --- (2) getProductMetrics ----------------------------------------------------------------------


def test_agregats_calcules_depuis_les_vraies_tables(
    platform: Platform, measured: dict[str, Any]
) -> None:
    body = _body(platform)
    # Période élargie aux semaines entières, coupée à la dernière semaine terminée.
    period_from = date.fromisoformat(body["period_from"])
    period_to = date.fromisoformat(body["period_to"])
    assert (period_from.weekday(), period_to.weekday()) == (0, 6)
    assert period_to < platform.clock.now().date()
    metrics = {item["key"]: item for item in body["items"]}
    expected = {
        # 2 accordés automatiquement sur 6 dossiers décidés, 6 bénéficiaires (palier 5).
        "claims_auto_approved_rate": ("pour_dix_mille", 3333, 5),
        # 4 dossiers routés en revue sur 6.
        "claims_review_rate": ("pour_dix_mille", 6667, 5),
        # Délais demande → décision : 0, 0, 1 h, 2 h, 3 h, 4 h ; médiane discrète = 1 h.
        "claims_decision_median_ms": ("millisecondes", 3_600_000, 5),
        # Comptoir de A : 4, 5, 6, 7, 9 s (cinq agents) ; ceux de B ne comptent pas.
        COUNTER_KEY: ("millisecondes", 6000, 5),
        # 5 accueils terminés sur 6 commencés (six personnes, palier 5).
        "onboarding_completion_rate": ("pour_dix_mille", 8333, 5),
        # Début de l'accueil → première carte présentée : 10 à 50 s, médiane 30 s.
        "first_card_median_ms": ("millisecondes", 30_000, 5),
        # 5 cotisations payées sur 6 invitées.
        "payment_links_paid_rate": ("pour_dix_mille", 8333, 5),
        # Aucun double effet malgré le webhook rejoué (5 cotisations reçues).
        "webhook_duplicate_rate": ("pour_dix_mille", 0, 5),
    }
    for key, (unit, value, contributors) in expected.items():
        assert metrics[key] == {
            "key": key,
            "unit": unit,
            "status": "disponible",
            "value": value,
            "contributors": contributors,
        }, key
    ledger = metrics["ledger_balance_gap_xof"]
    assert (ledger["unit"], ledger["status"], ledger["value"]) == ("xof", "disponible", 0)
    # 2 dossiers automatiques + 2 accordés par le médecin-conseil + 5 cotisations reçues.
    entries = platform.scalar(
        "SELECT count(*) FROM ledger_entries WHERE organization_id = %s", (ORG_A,)
    )
    assert entries >= 9
    assert ledger["contributors"] == contributor_band(entries)
    assert list(metrics) == [
        "claims_auto_approved_rate",
        "claims_review_rate",
        "claims_decision_median_ms",
        COUNTER_KEY,
        "onboarding_completion_rate",
        "first_card_median_ms",
        "payment_links_paid_rate",
        "ledger_balance_gap_xof",
        "webhook_duplicate_rate",
    ]


def test_admin_lit_les_memes_agregats(platform: Platform, measured: dict[str, Any]) -> None:
    assert _metrics(platform, "admin") == _metrics(platform)


@pytest.mark.parametrize("who", ["medecin_conseil", "clinique_a", "adh0"])
def test_reserve_au_gestionnaire_et_a_l_admin(
    platform: Platform, measured: dict[str, Any], who: str
) -> None:
    response = platform.client.get(METRICS, params=_window(platform), headers=platform.auth(who))
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "AUTH-02"


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"from": "2026-10-05", "to": "2026-10-01"}, id="debut-apres-fin"),
        pytest.param({"from": "2025-01-01", "to": "2026-10-01"}, id="plus-d-un-an"),
        pytest.param({"from": "hier"}, id="pas-une-date"),
    ],
)
def test_periode_invalide(
    platform: Platform, measured: dict[str, Any], params: dict[str, str]
) -> None:
    response = platform.client.get(METRICS, params=params, headers=platform.auth("gestionnaire"))
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VAL-01"


def test_semaine_en_cours_seule_refusee(platform: Platform, measured: dict[str, Any]) -> None:
    """Aucune semaine terminée dans la période : rien à publier (422, pas un agrégat partiel)."""
    today = platform.clock.now().date().isoformat()
    response = platform.client.get(
        METRICS, params={"from": today, "to": today}, headers=platform.auth("gestionnaire")
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VAL-01"
    assert [e["field"] for e in response.json()["errors"]] == ["to"]


# --- Gardes : k-anonymat, recoupement, isolation, rétention -------------------------------------


def test_k_anonymat_seuil_franchi_a_cinq_personnes_pas_a_quatre(
    platform: Platform, measured: dict[str, Any]
) -> None:
    """Quatre agents de B : masqué, même avec un 5e ÉVÉNEMENT d'un agent déjà compté (nouvelle
    session). Cinq agents : publié."""
    env = platform
    assert _state(_metrics(env, "gestionnaire_b")[COUNTER_KEY]) == MASKED
    # B : un dossier, une écriture, un lien du jeu d'isolation ; tout est sous le seuil.
    assert {m["status"] for m in _metrics(env, "gestionnaire_b").values()} == {"masque"}
    four = _next_week(env)
    for who in B_FOUR:
        assert _counter(env, who, 80_000) == 204
    assert _counter(env, "clinique_b1", 80_000) == 204
    five = _next_week(env)
    for who in B_FIVE:
        assert _counter(env, who, 80_000) == 204
    _next_week(env)
    assert _state(_metrics(env, "gestionnaire_b", _week(four))[COUNTER_KEY]) == MASKED
    shown = _metrics(env, "gestionnaire_b", _week(five))[COUNTER_KEY]
    assert _state(shown) == ("disponible", 80_000, 5)
    # A n'a pas bougé : les agents de B ne comptent jamais pour A.
    assert _state(_metrics(env)[COUNTER_KEY]) == ("disponible", 6000, 5)


def test_une_personne_seule_qui_recharge_cinq_fois_reste_masquee(
    platform: Platform, measured: dict[str, Any]
) -> None:
    """Attaque du vérificateur : chaque chargement de page tire une nouvelle session. Cinq
    sessions d'une même personne = un contributeur, sous le seuil."""
    env = platform
    week = _next_week(env)
    for _ in range(5):
        assert _counter(env, "clinique_b", 7000) == 204
    _next_week(env)
    assert _state(_metrics(env, "gestionnaire_b", _week(week))[COUNTER_KEY]) == MASKED
    start = datetime.combine(week, time.min, UTC)
    stored = env.rows(
        "SELECT count(*), count(DISTINCT session_ref) FROM product_events "
        "WHERE organization_id = %s AND occurred_at >= %s AND occurred_at < %s",
        (env.orgs["b"], start, start + timedelta(days=7)),
    )
    assert stored == [(5, 1)]


def test_recoupement_de_deux_periodes_n_isole_aucune_contribution(
    platform: Platform, measured: dict[str, Any]
) -> None:
    """Attaque du vérificateur : cinq agents la semaine 1 (médiane 6 s), un sixième la semaine
    2 (1 s). Avant correctif, deux requêtes donnaient effectif 5 → 6 et médiane 6000 → 5000, ce
    qui isolait la valeur du sixième. Désormais : la semaine en cours n'est jamais publiée, et la
    période qui l'inclut une fois terminée est masquée (son complément est sous le seuil)."""
    env = platform
    first = _next_week(env)
    for who, duration in zip(B_FIVE, (4000, 5000, 6000, 7000, 9000), strict=True):
        assert _counter(env, who, duration) == 204
    second = _next_week(env)
    env.add_user("clinique_b5", "b", "clinique", env.providers["b"])
    assert _counter(env, "clinique_b5", 1000) == 204

    # Pendant la semaine 2 : demander « jusqu'à aujourd'hui » ne publie que la semaine 1.
    today = env.clock.now().date().isoformat()
    during = _body(env, "gestionnaire_b", {"from": first.isoformat(), "to": today})
    assert (during["period_from"], during["period_to"]) == (
        first.isoformat(),
        (first + timedelta(days=6)).isoformat(),
    )
    reference = {item["key"]: item for item in during["items"]}[COUNTER_KEY]
    assert _state(reference) == ("disponible", 6000, 5)

    _next_week(env)
    # Période mal alignée (mardi → mercredi) : élargie à la semaine entière, même résultat.
    misaligned = {
        "from": (first + timedelta(days=1)).isoformat(),
        "to": (first + timedelta(days=2)).isoformat(),
    }
    body = _body(env, "gestionnaire_b", misaligned)
    assert body["period_from"] == first.isoformat()
    assert _state({i["key"]: i for i in body["items"]}[COUNTER_KEY]) == _state(reference)
    # Semaines 1 et 2 : six personnes, mais la semaine 2 n'en a qu'une → masqué.
    both = {"from": first.isoformat(), "to": (second + timedelta(days=6)).isoformat()}
    assert _state(_metrics(env, "gestionnaire_b", both)[COUNTER_KEY]) == MASKED
    assert _state(_metrics(env, "gestionnaire_b", _week(second))[COUNTER_KEY]) == MASKED


def test_semaine_dont_un_evenement_a_pu_expirer_jamais_publiee(
    platform: Platform, measured: dict[str, Any]
) -> None:
    """La purge retire des événements au fil des jours : une semaine à cheval sur la limite de
    rétention changerait d'une requête à l'autre. Elle n'est pas comptée, même pleine."""
    env = platform
    runtime = _runtime(env)
    floor = retained_since(env.clock.now(), runtime.retention_days, ZONE)
    with psycopg.connect(env.dsn) as conn:
        for at in (floor - HOUR, floor + HOUR):
            for _ in range(5):
                conn.execute(
                    "INSERT INTO product_events (organization_id, name, surface, role, "
                    "session_ref, duration_ms, variant, occurred_at, expires_at) VALUES (%s, "
                    "'counter_decision_shown', 'comptoir', 'clinique', %s, 7000, 'accordee', "
                    "%s, %s)",
                    (env.orgs["b"], secrets.token_hex(32), at, at + timedelta(days=3650)),
                )
    partial = _week((floor - timedelta(days=7)).date())
    kept = _week(floor.date())
    assert _state(_metrics(env, "gestionnaire_b", partial)[COUNTER_KEY]) == MASKED
    assert _state(_metrics(env, "gestionnaire_b", kept)[COUNTER_KEY]) == ("disponible", 7000, 5)


def test_doublon_de_webhook_detecte_dans_les_vraies_tables(
    platform: Platform, measured: dict[str, Any]
) -> None:
    """Mutation de donnée : un double effet injecté en base fait monter le taux (1 sur 5)."""
    env = platform
    contribution = UUID(measured["contributions"][1])
    with psycopg.connect(env.dsn) as conn:
        injected = conn.execute(
            "INSERT INTO outbox_events (organization_id, event_type, aggregate_id, payload, "
            "occurred_at, published_at) SELECT organization_id, event_type, aggregate_id, "
            "payload, occurred_at, occurred_at FROM outbox_events WHERE aggregate_id = %s "
            "AND event_type = 'contribution.received' RETURNING id",
            (contribution,),
        ).fetchall()
    assert len(injected) == 1
    try:
        duplicate = _metrics(env)["webhook_duplicate_rate"]
        assert (duplicate["value"], duplicate["contributors"]) == (2000, 5)
    finally:
        with psycopg.connect(env.dsn) as conn:
            conn.execute("DELETE FROM outbox_events WHERE id = %s", (injected[0][0],))
    assert _metrics(env)["webhook_duplicate_rate"]["value"] == 0


def test_evenement_expire_ignore_puis_purge(platform: Platform, measured: dict[str, Any]) -> None:
    """Expiré pour l'horloge de l'application ET pour celle de la base (la purge exige les deux)."""
    env = platform
    real = datetime.now(UTC)
    with psycopg.connect(env.dsn) as conn:
        conn.execute(
            "INSERT INTO product_events (organization_id, name, surface, role, session_ref, "
            "duration_ms, variant, occurred_at, expires_at) VALUES (%s, "
            "'counter_decision_shown', 'comptoir', 'clinique', %s, 1, 'accordee', %s, %s)",
            (ORG_A, "e" * 64, real - HOUR, real - timedelta(seconds=1)),
        )
    assert _state(_metrics(env)[COUNTER_KEY]) == ("disponible", 6000, 5)
    purged = env.run(purge_expired_events, env.database, ORG_A, env.clock.now())
    assert purged == 1
    left = env.scalar("SELECT count(*) FROM product_events WHERE session_ref = %s", ("e" * 64,))
    assert left == 0


def test_retention_configuree_posee_a_l_insertion(
    platform: Platform, measured: dict[str, Any]
) -> None:
    env = platform
    assert (
        _send(
            env,
            "adh1",
            name="claim_tracking_viewed",
            surface="espace_adherent",
            role="adherent",
            session_id=_session(),
        )
        == 204
    )
    occurred, expires = env.rows(
        "SELECT occurred_at, expires_at FROM product_events WHERE name = 'claim_tracking_viewed'"
    )[0]
    assert occurred == env.clock.now()
    # En UTC : deux dates du même fuseau local se soustraient en heure murale (changement d'heure).
    elapsed = expires.astimezone(UTC) - occurred.astimezone(UTC)
    assert elapsed == timedelta(days=_runtime(env).retention_days)
