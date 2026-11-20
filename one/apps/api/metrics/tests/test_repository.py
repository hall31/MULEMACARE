"""Table ``product_events`` (migration 0003, CR-P2-01) : base, RLS, droits, rétention.

1. Barrières de la BASE, indépendantes de l'API (mutation « liste blanche retirée du code ») :
   sous ``mulema_app``, un nom, une surface ou une variante hors liste, une empreinte de session
   qui n'est pas une empreinte, une durée hors borne sont refusés par les CHECK ; aucune mise à
   jour (pas de droit UPDATE) ; écriture chez une autre organisation refusée (RLS).
2. Défense en profondeur (mutation « RLS neutralisée ») : sous un superutilisateur SANS rôle
   applicatif, la RLS ne filtre rien ; le dépôt construit pour l'organisation A ne lit pourtant
   aucune ligne de B, parce que chaque requête filtre ``organization_id`` elle-même. Le témoin
   positif prouve que les lignes de B sont lisibles par cette connexion.
3. Contre le recoupement (CR-P2-02) : l'effectif compte des PERSONNES (empreinte), chaque
   personne pèse une fois dans une médiane, chaque lecture remonte l'effectif de sa semaine la
   plus faible, et rien de postérieur à la fin de la période n'y entre (une période terminée ne
   bouge plus).
4. Rétention : la purge ne supprime que les lignes expirées de SON organisation, et jamais une
   ligne que l'horloge de la BASE ne tient pas pour expirée (même si l'appelant se trompe).
Données fictives.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import Database, IsolationNotEnforcedError
from api.metrics.jobs import main, purge_expired_events
from api.metrics.repository import MetricsRepository
from api.tests.contracts.helpers import APP_ROLE, connect_as_app
from api.tests.e2e.conftest import sqlalchemy_url
from api.tests.paths import ONE_ROOT

FIXTURE = ONE_ROOT / "apps" / "api" / "tests" / "contracts" / "fixtures" / "one_row_per_table.sql"
NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)  # jeudi : START et END restent dans sa semaine
START, END = NOW - timedelta(days=1), NOW + timedelta(days=1)
TZ = "Africa/Abidjan"
REF = "a" * 64


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def _org(dsn: str, slug: str) -> UUID:
    org = uuid4()
    script = FIXTURE.read_text(encoding="utf-8")
    with psycopg.connect(dsn) as conn:
        conn.execute(script.replace("__ORG__", str(org)).replace("__SLUG__", slug).encode())
    return org


@pytest.fixture
def orgs(insurance_dsn: str) -> tuple[UUID, UUID]:
    return _org(insurance_dsn, "mesure-a"), _org(insurance_dsn, "mesure-b")


def _insert(conn: psycopg.Connection, org: UUID, **overrides: object) -> None:
    row: dict[str, object] = {
        "organization_id": org,
        "name": "counter_decision_shown",
        "surface": "comptoir",
        "role": "clinique",
        "session_ref": uuid4().hex * 2,
        "duration_ms": 6000,
        "step": None,
        "variant": "accordee",
        "occurred_at": NOW,
        "expires_at": NOW + timedelta(days=90),
    } | overrides
    columns = ", ".join(row)
    values = ", ".join(f"%({k})s" for k in row)
    conn.execute(f"INSERT INTO product_events ({columns}) VALUES ({values})".encode(), row)


# --- 1. Barrières de la base ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"name": "page_viewed"}, id="nom-hors-liste"),
        pytest.param({"surface": "site_public"}, id="surface-hors-liste"),
        pytest.param({"role": "payeur"}, id="role-hors-liste"),
        pytest.param({"variant": "Awa Fictif"}, id="texte-libre"),
        pytest.param({"session_ref": "session-brute-du-navigateur"}, id="session-non-hachee"),
        pytest.param({"duration_ms": -1}, id="duree-negative"),
        pytest.param({"step": 99}, id="etape-hors-borne"),
        pytest.param({"expires_at": NOW}, id="retention-nulle"),
    ],
)
def test_la_base_refuse_hors_liste_sous_le_role_applicatif(
    orgs: tuple[UUID, UUID], insurance_dsn: str, overrides: dict[str, object]
) -> None:
    a, _ = orgs
    with connect_as_app(insurance_dsn, a) as conn, pytest.raises(psycopg.errors.CheckViolation):
        _insert(conn, a, **overrides)


def test_la_table_ne_porte_aucun_identifiant_de_personne(insurance_dsn: str) -> None:
    with psycopg.connect(insurance_dsn) as conn:
        columns = {
            r[0]
            for r in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'product_events'"
            ).fetchall()
        }
    assert columns == {
        "id",
        "organization_id",
        "name",
        "surface",
        "role",
        "session_ref",
        "duration_ms",
        "step",
        "variant",
        "occurred_at",
        "expires_at",
    }


def test_droits_du_role_applicatif(insurance_dsn: str) -> None:
    """Lecture, ajout, purge ; jamais de mise à jour (un événement ne se réécrit pas)."""
    with psycopg.connect(insurance_dsn) as conn:
        rights = conn.execute(
            "SELECT has_table_privilege(%s, 'product_events', 'SELECT'), "
            "has_table_privilege(%s, 'product_events', 'INSERT'), "
            "has_table_privilege(%s, 'product_events', 'DELETE'), "
            "has_table_privilege(%s, 'product_events', 'UPDATE'), "
            "has_table_privilege(%s, 'product_events', 'TRUNCATE')",
            (APP_ROLE,) * 5,
        ).fetchone()
    assert rights == (True, True, True, False, False)


def test_ecriture_chez_une_autre_organisation_refusee(
    orgs: tuple[UUID, UUID], insurance_dsn: str
) -> None:
    a, b = orgs
    with connect_as_app(insurance_dsn, a) as conn, pytest.raises(psycopg.Error) as caught:
        _insert(conn, b)
    assert caught.value.sqlstate == "42501"


def test_mise_a_jour_refusee(orgs: tuple[UUID, UUID], insurance_dsn: str) -> None:
    a, _ = orgs
    with connect_as_app(insurance_dsn, a) as conn, pytest.raises(psycopg.Error) as caught:
        conn.execute("UPDATE product_events SET duration_ms = 1")
    assert caught.value.sqlstate == "42501"


# --- 2. Défense en profondeur : le dépôt filtre l'organisation lui-même ---------------------------


@asynccontextmanager
async def owner_session(dsn: str, organization_id: UUID) -> AsyncIterator[AsyncSession]:
    """Superutilisateur SANS rôle applicatif : la RLS ne s'applique PAS à cette session."""
    database = Database(sqlalchemy_url(dsn), app_role=None, pool_size=1)
    try:
        with pytest.raises(IsolationNotEnforcedError):  # garde : on est bien hors RLS
            await database.verify_isolation_enforced()
        async with database.transaction(organization_id) as session:
            yield session
    finally:
        await database.dispose()


def _seed_b(dsn: str, b: UUID) -> None:
    """Cinq sessions de B sur chaque mesure lue par le dépôt (au-dessus du seuil k = 5)."""
    with psycopg.connect(dsn) as conn:
        for i in range(5):
            ref = f"{i:x}" * 64
            _insert(conn, b, session_ref=ref, duration_ms=1000 * (i + 1))
            _insert(
                conn,
                b,
                name="onboarding_started",
                surface="espace_adherent",
                role="adherent",
                session_ref=ref,
                duration_ms=None,
                variant=None,
            )
            _insert(
                conn,
                b,
                name="card_presented",
                surface="espace_adherent",
                role="adherent",
                session_ref=ref,
                duration_ms=None,
                variant="en_ligne",
                occurred_at=NOW + timedelta(seconds=10),
            )
            _insert(
                conn,
                b,
                name="onboarding_completed",
                surface="espace_adherent",
                role="adherent",
                session_ref=ref,
                duration_ms=None,
                variant=None,
            )


WIDE = START - timedelta(days=400), END + timedelta(days=400)


def test_temoin_les_lignes_de_b_sont_lisibles_par_b(
    orgs: tuple[UUID, UUID], insurance_dsn: str
) -> None:
    """Sans ce témoin, un dépôt qui ne lit rien passerait le test suivant."""
    _, b = orgs
    _seed_b(insurance_dsn, b)

    async def scenario() -> None:
        async with owner_session(insurance_dsn, b) as session:
            repo = MetricsRepository(session, b)
            assert tuple(await repo.counter_display(START, END, NOW, TZ)) == (3000, 5, 5)
            assert tuple(await repo.onboarding(START, END, NOW, TZ)) == (5, 5, 5, 5)
            assert tuple(await repo.first_card(START, END, NOW, TZ)) == (10_000, 5, 5)
            # Jeu d'isolation : un dossier accordé automatiquement, une écriture équilibrée,
            # un lien de paiement non payé (dates réelles : fenêtre large).
            assert tuple(await repo.claim_outcomes(*WIDE, TZ)) == (1, 1, 0, 1, 1)
            assert tuple(await repo.ledger_gap(date(2026, 12, 31))) == (0, 1)
            assert tuple(await repo.payment_links(*WIDE, TZ)) == (0, 1, 1, 1)

    _run(scenario())


def test_lectures_du_depot_filtrees_par_organisation_meme_sans_rls(
    orgs: tuple[UUID, UUID], insurance_dsn: str
) -> None:
    a, b = orgs
    _seed_b(insurance_dsn, b)
    with psycopg.connect(insurance_dsn) as conn:
        b_rows = conn.execute(
            "SELECT count(*) FROM product_events WHERE organization_id = %s", (b,)
        ).fetchone()
    assert b_rows is not None

    async def scenario() -> None:
        async with owner_session(insurance_dsn, a) as session:
            visible = (
                await session.execute(
                    text("SELECT count(*) FROM product_events WHERE organization_id = :b"),
                    {"b": b},
                )
            ).one()
            assert int(visible[0]) == b_rows[0] > 20  # la RLS ne filtre pas cette session
            repo = MetricsRepository(session, a)
            assert tuple(await repo.counter_display(START, END, NOW, TZ)) == (None, 0, 0)
            assert tuple(await repo.onboarding(START, END, NOW, TZ)) == (0, 0, 0, 0)
            assert tuple(await repo.first_card(START, END, NOW, TZ)) == (None, 0, 0)
            # Le seul dossier de A.
            assert tuple(await repo.claim_outcomes(*WIDE, TZ)) == (1, 1, 0, 1, 1)
            assert tuple(await repo.ledger_gap(date(2026, 12, 31))) == (0, 1)
            assert tuple(await repo.payment_links(*WIDE, TZ)) == (0, 1, 1, 1)

    _run(scenario())


# --- 3. Contre le recoupement ------------------------------------------------------------------


def _read[T](dsn: str, org: UUID, read: Callable[[MetricsRepository], Awaitable[T]]) -> T:
    async def scenario() -> T:
        async with owner_session(dsn, org) as session:
            return await read(MetricsRepository(session, org))

    return _run(scenario())


def test_l_effectif_compte_des_personnes_pas_des_evenements(
    orgs: tuple[UUID, UUID], insurance_dsn: str
) -> None:
    """Quatre personnes qui envoient chacune trois événements : effectif 4 (sous le seuil k)."""
    _, b = orgs
    with psycopg.connect(insurance_dsn) as conn:
        for i in range(4):
            for _ in range(3):
                _insert(conn, b, session_ref=f"{i:x}" * 64, duration_ms=2000)

    found = _read(insurance_dsn, b, lambda r: r.counter_display(START, END, NOW, TZ))
    assert tuple(found) == (2000, 4, 4)


def test_une_personne_ne_domine_pas_la_mediane(orgs: tuple[UUID, UUID], insurance_dsn: str) -> None:
    """Cinq personnes, dont une envoie vingt événements : chacune pèse UNE fois (médiane par
    personne, puis médiane des personnes). Sinon la médiane publiée serait la sienne."""
    _, b = orgs
    with psycopg.connect(insurance_dsn) as conn:
        for i in range(4):
            _insert(conn, b, session_ref=f"{i:x}" * 64, duration_ms=1000 * (i + 1))
        for _ in range(20):
            _insert(conn, b, session_ref="9" * 64, duration_ms=60_000)

    found = _read(insurance_dsn, b, lambda r: r.counter_display(START, END, NOW, TZ))
    assert tuple(found) == (3000, 5, 5)


def test_la_semaine_la_plus_faible_est_remontee(
    orgs: tuple[UUID, UUID], insurance_dsn: str
) -> None:
    """Cinq personnes la semaine 1, une seule la semaine 2 : sur les deux semaines, l'effectif
    est 6 mais la semaine la plus faible n'en a qu'une (le complément isolerait sa valeur)."""
    _, b = orgs
    week_later = NOW + timedelta(days=7)
    with psycopg.connect(insurance_dsn) as conn:
        for i in range(5):
            _insert(conn, b, session_ref=f"{i:x}" * 64, duration_ms=6000)
        _insert(conn, b, session_ref="f" * 64, duration_ms=1000, occurred_at=week_later)

    both = _read(insurance_dsn, b, lambda r: r.counter_display(START, END + timedelta(7), NOW, TZ))
    assert tuple(both)[1:] == (6, 1)
    first = _read(insurance_dsn, b, lambda r: r.counter_display(START, END, NOW, TZ))
    assert tuple(first) == (6000, 5, 5)


def test_onboarding_termine_apres_la_periode_ignore(
    orgs: tuple[UUID, UUID], insurance_dsn: str
) -> None:
    """Une période terminée ne bouge plus : une fin d'accueil postérieure n'y entre pas."""
    _, b = orgs
    adherent: dict[str, object] = {"surface": "espace_adherent", "role": "adherent"}
    with psycopg.connect(insurance_dsn) as conn:
        for i in range(5):
            ref = f"{i:x}" * 64
            base = adherent | {"session_ref": ref, "duration_ms": None, "variant": None}
            _insert(conn, b, name="onboarding_started", **base)
            late = END + timedelta(hours=1)
            _insert(conn, b, name="onboarding_completed", occurred_at=late, **base)

    found = _read(insurance_dsn, b, lambda r: r.onboarding(START, END, NOW, TZ))
    assert tuple(found) == (0, 5, 5, 5)
    later = _read(insurance_dsn, b, lambda r: r.onboarding(START, END + timedelta(days=1), NOW, TZ))
    assert tuple(later) == (5, 5, 5, 5)


def test_fin_d_accueil_isolee_dans_une_semaine_remontee(
    orgs: tuple[UUID, UUID], insurance_dsn: str
) -> None:
    """Cinq débuts la semaine 1, une seule fin la semaine 2 : sur les deux semaines, la fin
    isolée change le taux (0 → 1/5) ; sa semaine n'a qu'une personne, l'agrégat sera masqué."""
    _, b = orgs
    adherent: dict[str, object] = {"surface": "espace_adherent", "role": "adherent"}
    with psycopg.connect(insurance_dsn) as conn:
        for i in range(5):
            base = adherent | {"session_ref": f"{i:x}" * 64, "duration_ms": None, "variant": None}
            _insert(conn, b, name="onboarding_started", **base)
        done = adherent | {"session_ref": "0" * 64, "duration_ms": None, "variant": None}
        _insert(conn, b, name="onboarding_completed", occurred_at=NOW + timedelta(days=7), **done)

    both = _read(insurance_dsn, b, lambda r: r.onboarding(START, END + timedelta(7), NOW, TZ))
    assert tuple(both) == (1, 5, 5, 1)


def test_decision_posterieure_a_la_periode_ignoree(
    orgs: tuple[UUID, UUID], insurance_dsn: str
) -> None:
    """Le dossier de B est demandé dix jours avant sa décision : une période qui s'arrête avant
    la décision ne la compte pas, et ne changera donc pas quand elle arrivera."""
    _, b = orgs
    with psycopg.connect(insurance_dsn) as conn:
        row = conn.execute(
            "UPDATE claims SET requested_at = requested_at - interval '10 days' "
            "WHERE organization_id = %s RETURNING requested_at",
            (b,),
        ).fetchone()
    assert row is not None
    requested: datetime = row[0]
    start, end = requested - timedelta(hours=1), requested + timedelta(days=5)
    after = requested + timedelta(days=11)
    assert tuple(_read(insurance_dsn, b, lambda r: r.claim_outcomes(start, end, TZ))) == (
        0,
        0,
        0,
        0,
        0,
    )
    assert tuple(_read(insurance_dsn, b, lambda r: r.decision_delay(start, end, TZ))) == (
        None,
        0,
        0,
    )
    decided = _read(insurance_dsn, b, lambda r: r.claim_outcomes(start, after, TZ))
    assert decided.decided == 1


def test_paiement_posterieur_a_la_periode_ignore(
    orgs: tuple[UUID, UUID], insurance_dsn: str
) -> None:
    _, b = orgs
    with psycopg.connect(insurance_dsn) as conn:
        row = conn.execute(
            "UPDATE payment_links SET used_at = created_at + interval '10 days' "
            "WHERE organization_id = %s RETURNING created_at",
            (b,),
        ).fetchone()
    assert row is not None
    created: datetime = row[0]
    start, end = created - timedelta(hours=1), created + timedelta(days=5)
    after = created + timedelta(days=11)
    assert tuple(_read(insurance_dsn, b, lambda r: r.payment_links(start, end, TZ))) == (
        0,
        1,
        1,
        1,
    )
    paid = _read(insurance_dsn, b, lambda r: r.payment_links(start, after, TZ))
    assert paid.numerator == 1


def test_reception_posterieure_a_la_periode_ignoree(
    orgs: tuple[UUID, UUID], insurance_dsn: str
) -> None:
    """Une seconde réception (double effet) arrivée après la fin ne change pas la période."""
    _, b = orgs
    with psycopg.connect(insurance_dsn) as conn:
        row = conn.execute(
            "SELECT id FROM contributions WHERE organization_id = %s", (b,)
        ).fetchone()
        assert row is not None
        for at in (NOW, NOW + timedelta(days=10)):
            conn.execute(
                "INSERT INTO outbox_events (organization_id, event_type, aggregate_id, payload, "
                "occurred_at) VALUES (%s, 'contribution.received', %s, '{}'::jsonb, %s)",
                (b, row[0], at),
            )
    found = _read(insurance_dsn, b, lambda r: r.webhook_duplicates(START, END, TZ))
    assert tuple(found) == (0, 1, 1, 1)
    later = END + timedelta(days=10)
    assert tuple(_read(insurance_dsn, b, lambda r: r.webhook_duplicates(START, later, TZ))) == (
        1,
        1,
        1,
        1,
    )


# --- 4. Rétention ----------------------------------------------------------------------------


def _count(dsn: str, org: UUID) -> int:
    with psycopg.connect(dsn) as conn:
        row = conn.execute(
            "SELECT count(*) FROM product_events WHERE organization_id = %s", (org,)
        ).fetchone()
    assert row is not None
    return int(row[0])


def test_purge_des_evenements_expires_de_son_organisation_seulement(
    orgs: tuple[UUID, UUID], insurance_dsn: str
) -> None:
    a, b = orgs
    with psycopg.connect(insurance_dsn) as conn:
        conn.execute("DELETE FROM product_events")
        _insert(conn, a, occurred_at=NOW - timedelta(days=200), expires_at=NOW - timedelta(days=1))
        _insert(conn, a, occurred_at=NOW, expires_at=NOW + timedelta(days=1))
        _insert(conn, b, occurred_at=NOW - timedelta(days=200), expires_at=NOW - timedelta(days=1))

    async def scenario() -> int:
        database = Database(sqlalchemy_url(insurance_dsn), app_role=APP_ROLE, pool_size=1)
        try:
            return await purge_expired_events(database, a, NOW)
        finally:
            await database.dispose()

    assert _run(scenario()) == 1
    assert (_count(insurance_dsn, a), _count(insurance_dsn, b)) == (1, 1)


def _purge_as_app(dsn: str, org: UUID, now: datetime) -> int:
    async def scenario() -> int:
        database = Database(sqlalchemy_url(dsn), app_role=APP_ROLE, pool_size=1)
        try:
            return await purge_expired_events(database, org, now)
        finally:
            await database.dispose()

    return _run(scenario())


def test_purge_ne_supprime_jamais_une_ligne_non_expiree_selon_la_base(
    orgs: tuple[UUID, UUID], insurance_dsn: str
) -> None:
    """Sous ``mulema_app``, même appelée avec une horloge fausse (dix ans d'avance), la purge
    ne supprime que ce que l'horloge de la BASE tient pour expiré."""
    a, _ = orgs
    real = datetime.now(UTC)
    with psycopg.connect(insurance_dsn) as conn:
        conn.execute("DELETE FROM product_events WHERE organization_id = %s", (a,))
        _insert(conn, a, occurred_at=real - timedelta(days=2), expires_at=real - timedelta(days=1))
        _insert(conn, a, occurred_at=real, expires_at=real + timedelta(days=1))

    assert _purge_as_app(insurance_dsn, a, real + timedelta(days=3650)) == 1
    assert _count(insurance_dsn, a) == 1


def test_commande_de_purge_planifiable(orgs: tuple[UUID, UUID], insurance_dsn: str) -> None:
    """``python -m api.metrics purge --organization <id>`` (tâche quotidienne de l'exploitation)."""
    a, b = orgs
    real = datetime.now(UTC)
    with psycopg.connect(insurance_dsn) as conn:
        conn.execute("DELETE FROM product_events WHERE organization_id IN (%s, %s)", (a, b))
        for org in (a, b):
            _insert(conn, org, occurred_at=real - timedelta(days=9), expires_at=real - timedelta(1))
            _insert(conn, org, occurred_at=real, expires_at=real + timedelta(days=1))
    env = {"MULEMA_INSURANCE_DATABASE_URL": sqlalchemy_url(insurance_dsn)}
    assert main(["purge", "--organization", str(a)], env) == 0
    assert (_count(insurance_dsn, a), _count(insurance_dsn, b)) == (1, 2)
    assert main(["purge", "--organization", str(a), "--organization", str(b)], env) == 0
    assert (_count(insurance_dsn, a), _count(insurance_dsn, b)) == (1, 1)


def test_commande_de_purge_refuse_une_organisation_invalide(insurance_dsn: str) -> None:
    env = {"MULEMA_INSURANCE_DATABASE_URL": sqlalchemy_url(insurance_dsn)}
    with pytest.raises(SystemExit):
        main(["purge", "--organization", "pas-un-uuid"], env)
    with pytest.raises(SystemExit):
        main(["purge"], env)


def test_un_evenement_expire_n_est_plus_compte_avant_meme_la_purge(
    orgs: tuple[UUID, UUID], insurance_dsn: str
) -> None:
    _, b = orgs
    _seed_b(insurance_dsn, b)
    with psycopg.connect(insurance_dsn) as conn:  # expiré à l'instant même : exclu
        _insert(
            conn,
            b,
            session_ref="f" * 64,
            duration_ms=86_000_000,
            occurred_at=NOW - timedelta(hours=1),
            expires_at=NOW,
        )

    found = _read(insurance_dsn, b, lambda r: r.counter_display(START, END, NOW, TZ))
    assert tuple(found) == (3000, 5, 5)
