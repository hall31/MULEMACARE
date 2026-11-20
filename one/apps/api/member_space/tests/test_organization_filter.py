"""Défense en profondeur : l'espace adhérent filtre ``organization_id`` lui-même, hors RLS.

Même preuve que ``ledger/tests/test_organization_filter.py`` (M11). La RLS reste la barrière
principale ; ici on la neutralise volontairement (superutilisateur, sans ``SET ROLE`` : hors
RLS) et on construit le dépôt avec l'organisation A et le contrat d'un adhérent de B. Un filtre
par contrat seul (``member_id``) trouverait les données de B : chaque lecture doit revenir vide
parce qu'elle filtre AUSSI l'organisation du principal. Retirer ce filtre d'une requête fait
échouer ce test. Le témoin positif (organisation B, contrat de B) prouve que les données sont
bien lisibles par cette connexion. Données fictives.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.context import RequestContext
from api.core.database import Database, IsolationNotEnforcedError
from api.core.errors import NotFoundError
from api.core.permissions import Principal, Role, RoleGrant, access_scope
from api.member_space.repository import MemberSpaceRepository
from api.member_space.service import MemberSpaceService
from api.members.cards import CardKeys
from api.tests.e2e.conftest import TestClock, sqlalchemy_url
from api.tests.paths import ONE_ROOT

FIXTURE = ONE_ROOT / "apps" / "api" / "tests" / "contracts" / "fixtures" / "one_row_per_table.sql"
NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
COVERAGE_RATE_BP = 8000  # FORMULE-T v1 du jeu d'isolation


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


@dataclass(frozen=True, slots=True)
class Contract:
    """Contrat de l'adhérent du jeu d'isolation d'une organisation."""

    org: UUID
    member: UUID
    claim: UUID
    plan_version: UUID


def _seed(dsn: str, slug: str) -> Contract:
    org = uuid4()
    script = FIXTURE.read_text(encoding="utf-8")
    with psycopg.connect(dsn) as conn:
        conn.execute(script.replace("__ORG__", str(org)).replace("__SLUG__", slug).encode())
        row = conn.execute(
            "SELECT c.member_id, c.id, c.plan_version_id FROM claims c "
            "WHERE c.organization_id = %s",
            (org,),
        ).fetchone()
    assert row is not None
    return Contract(org=org, member=row[0], claim=row[1], plan_version=row[2])


@pytest.fixture
def contracts(insurance_dsn: str) -> tuple[Contract, Contract]:
    return _seed(insurance_dsn, "espace-a"), _seed(insurance_dsn, "espace-b")


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


async def _visible_without_rls(session: AsyncSession, member: UUID) -> int:
    """Lignes du contrat visibles par cette session sans filtre d'organisation."""
    row = (
        await session.execute(
            text("SELECT count(*) FROM claims WHERE member_id = :member"), {"member": member}
        )
    ).one()
    return int(row[0])


def test_temoin_le_contrat_de_b_est_lisible_par_b(
    insurance_dsn: str, contracts: tuple[Contract, Contract]
) -> None:
    """Sans ce témoin, un dépôt qui ne lit rien passerait le test suivant."""
    b = contracts[1]

    async def scenario() -> None:
        async with owner_session(insurance_dsn, b.org) as session:
            repo = MemberSpaceRepository(session, b.org, b.member)
            assert await repo.contract() is not None
            assert len(await repo.beneficiaries()) == 2  # titulaire + enfant
            assert [r["id"] for r in await repo.claims_page(None, 50)] == [b.claim]
            assert await repo.claim(b.claim) is not None
            assert len(await repo.decisions(b.claim)) == 1
            assert len(await repo.contributions()) == 1
            assert await repo.coverage_rate_bp(b.plan_version) == COVERAGE_RATE_BP

    _run(scenario())


def test_lectures_du_depot_filtrees_par_organisation_meme_sans_rls(
    insurance_dsn: str, contracts: tuple[Contract, Contract]
) -> None:
    a, b = contracts

    async def scenario() -> None:
        async with owner_session(insurance_dsn, a.org) as session:
            assert await _visible_without_rls(session, b.member) == 1  # la RLS ne filtre pas
            repo = MemberSpaceRepository(session, a.org, b.member)
            assert await repo.contract() is None
            assert list(await repo.beneficiaries()) == []
            assert list(await repo.claims_page(None, 50)) == []
            assert await repo.claim(b.claim) is None
            assert list(await repo.decisions(b.claim)) == []
            assert list(await repo.contributions()) == []
            assert await repo.coverage_rate_bp(b.plan_version) == 0

    _run(scenario())


def test_service_de_l_espace_adherent_filtre_par_organisation_meme_sans_rls(
    insurance_dsn: str, contracts: tuple[Contract, Contract]
) -> None:
    """Un principal de A rattaché (à tort) au contrat de B ne lit rien de B, même hors RLS."""
    a, b = contracts
    principal = Principal(
        user_id=uuid4(),
        organization_id=a.org,
        grants=(RoleGrant(Role.ADHERENT, member_id=b.member),),
    )

    async def scenario() -> None:
        async with owner_session(insurance_dsn, a.org) as session:
            assert await _visible_without_rls(session, b.member) == 1
            service = MemberSpaceService(
                ctx=RequestContext(
                    principal=principal,
                    session=session,
                    request_id="req_filtre",
                    access=access_scope(principal, "getMyCard"),
                ),
                clock=TestClock(NOW),
                card_keys=CardKeys(bytes(32)),
            )
            with pytest.raises(NotFoundError):
                await service.card(None)
            assert (await service.beneficiaries()).items == []
            assert (await service.claims(None, 50)).items == []
            with pytest.raises(NotFoundError):
                await service.tracking(b.claim)
            contributions = await service.contributions()
            assert (contributions.items, contributions.next_due) == ([], None)

    _run(scenario())
