"""Défense en profondeur (P3) : les dépôts filtrent ``organization_id`` eux-mêmes, hors RLS.

Même preuve que ``member_space/tests/test_organization_filter.py`` : la RLS est neutralisée
volontairement (superutilisateur, sans rôle applicatif) ; un dépôt construit pour
l'organisation A ne doit RIEN lire de B. Le témoin prouve que cette connexion voit bien B.
Retirer le filtre d'organisation d'une requête fait échouer ce test. Données fictives (jeu
d'isolation L0 : une ligne par table et par organisation).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.branding.repository import BrandingRepository
from api.core.database import Database, IsolationNotEnforcedError
from api.partners.repository import AggregateRepository, PlatformRepository
from api.tests.e2e.conftest import sqlalchemy_url
from api.tests.paths import ONE_ROOT

FIXTURE = ONE_ROOT / "apps" / "api" / "tests" / "contracts" / "fixtures" / "one_row_per_table.sql"


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def _org(dsn: str, slug: str) -> UUID:
    org = uuid4()
    script = FIXTURE.read_text(encoding="utf-8")
    with psycopg.connect(dsn) as conn:
        conn.execute(script.replace("__ORG__", str(org)).replace("__SLUG__", slug).encode())
        conn.execute(
            "UPDATE contributions SET status = 'payee', paid_at = now() WHERE organization_id = %s",
            (org,),
        )
    return org


@pytest.fixture
def orgs(insurance_dsn: str) -> tuple[UUID, UUID]:
    return _org(insurance_dsn, "p3-a"), _org(insurance_dsn, "p3-b")


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


def _window() -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    return now - timedelta(days=1), now + timedelta(days=1)


async def _reads(session: AsyncSession, org: UUID, employer: UUID) -> dict[str, object]:
    repo = AggregateRepository(session, org)
    since, until = _window()
    tz = "Africa/Abidjan"
    statuses = await repo.members_by_status(until)
    return {
        "timezone": await repo.timezone(),
        "members": sum(c.count for c in statuses),
        "group": sum(c.count for c in await repo.members_by_status(until, employer)),
        "premiums": (await repo.premiums(since, until, tz)).count,
        "claims": (await repo.claims_cost(since, until, tz)).count,
        "group_claims": (await repo.claims_cost(since, until, tz, employer)).count,
        "categories": sum(c.count for c in await repo.benefits_by_category(since, until, tz)),
        "providers": len(await repo.providers(since, until, tz)),
        "delay_people": len((await repo.decision_delay(since, until, tz)).people),
        "decided": (await repo.automation(since, until, tz)).denominator,
        "employers": len(await repo.employers([employer])),
        "branding": (await BrandingRepository(session).get(org)) is not None,
        "templates": len(await PlatformRepository(session).templates(org)),
    }


EXPECTED_OWN: dict[str, object] = {
    "timezone": "Africa/Abidjan",
    "members": 1,
    "group": 1,
    "premiums": 1,
    "claims": 1,
    "group_claims": 1,
    "categories": 1,
    "providers": 1,
    "delay_people": 1,
    "decided": 1,
    "employers": 1,
    "branding": True,
    "templates": 1,
}


async def _employer(session: AsyncSession, org: UUID) -> UUID:
    row = (
        await session.execute(
            text("SELECT id FROM employers WHERE organization_id = :org"), {"org": org}
        )
    ).one()
    employer: UUID = row[0]
    return employer


def test_temoin_b_lit_ses_propres_agregats(insurance_dsn: str, orgs: tuple[UUID, UUID]) -> None:
    """Sans ce témoin, un dépôt qui ne lit rien passerait le test suivant."""
    b = orgs[1]

    async def scenario() -> dict[str, object]:
        async with owner_session(insurance_dsn, b) as session:
            return await _reads(session, b, await _employer(session, b))

    assert _run(scenario()) == EXPECTED_OWN


def test_depot_de_a_ne_lit_rien_de_b_meme_sans_rls(
    insurance_dsn: str, orgs: tuple[UUID, UUID]
) -> None:
    a, b = orgs

    async def scenario() -> tuple[int, dict[str, object]]:
        async with owner_session(insurance_dsn, a) as session:
            visible: int = (await session.execute(text("SELECT count(*) FROM claims"))).scalar_one()
            # Dépôt de A interrogé avec l'employeur de B : rien de B ne doit remonter.
            return int(visible), await _reads(session, a, await _employer(session, b))

    visible, reads = _run(scenario())
    assert visible == 2  # hors RLS : les dossiers de A ET de B sont lisibles par la connexion
    assert reads == EXPECTED_OWN | {"group": 0, "group_claims": 0, "employers": 0}


def test_gabarit_d_une_autre_organisation_introuvable(
    insurance_dsn: str, orgs: tuple[UUID, UUID]
) -> None:
    a, _ = orgs

    async def scenario() -> object:
        async with owner_session(insurance_dsn, a) as session:
            return await PlatformRepository(session).template(a, "gabarit-p3-b", None)

    assert _run(scenario()) is None
