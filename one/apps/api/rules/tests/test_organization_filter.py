"""Défense en profondeur : chaque requête du catalogue filtre ``organization_id`` elle-même.

La RLS reste la barrière principale (prouvée par ``test_routes.py``, sous ``mulema_app``). Ici
on la neutralise volontairement (propriétaire superutilisateur : hors RLS) pour prouver que
chaque lecture et chaque écriture de ``CatalogRepository`` porte AUSSI un filtre explicite sur
l'organisation de l'appelant. Retirer ce filtre d'une requête fait échouer ce test.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from api.rules.model import Period
from api.rules.repository import CatalogRepository
from api.rules.tests.conftest import DEMO_PLAN, Platform
from api.tests.e2e.conftest import ORG_A, sqlalchemy_url

FAR = date(2099, 1, 1)
DAY = date(2026, 10, 1)


@dataclass(frozen=True, slots=True)
class OrgB:
    id: UUID
    plan: UUID
    act: UUID
    rule: UUID
    rule_version: UUID
    provider: UUID


def _org_b(env: Platform) -> OrgB:
    org = env.orgs["b"]

    def one(table: str) -> UUID:
        value = env.scalar(f"SELECT id FROM {table} WHERE organization_id = %s", (org,))
        assert isinstance(value, UUID)
        return value

    return OrgB(
        org, one("plans"), one("acts"), one("rules"), one("rule_versions"), env.providers["b"]
    )


async def _products(repo: CatalogRepository, b: OrgB) -> None:
    assert await repo.organization_timezone(b.id) == "Africa/Abidjan"
    plans = await repo.plans(ORG_A)
    assert DEMO_PLAN in {p.id for p in plans}
    assert b.plan not in {p.id for p in plans}
    assert await repo.plans(ORG_A, b.plan) == []
    assert not await repo.lock_plan(ORG_A, b.plan)
    assert await repo.plan_versions(ORG_A, plan_ids=[b.plan]) == []
    b_versions = await repo.plan_versions(b.id, plan_ids=[b.plan])
    assert b_versions
    assert await repo.plan_versions(ORG_A, version_id=b_versions[0].id) == []
    assert await repo.version_to_publish("plan_versions", ORG_A, b_versions[0].id) is None
    assert await repo.version_to_publish("rule_versions", ORG_A, b.rule_version) is None


async def _network_and_tariffs(repo: CatalogRepository, b: OrgB) -> None:
    assert b.provider not in {p.id for p in await repo.providers_page(ORG_A, None, 500)}
    assert await repo.provider(ORG_A, b.provider) is None
    assert await repo.provider(ORG_A, b.provider, lock=True) is None
    assert await repo.conventions(ORG_A, [b.provider]) == []
    assert b.act not in {a.id for a in await repo.acts(ORG_A)}
    assert await repo.acts(ORG_A, b.act, lock=True) == []
    assert await repo.tariffs(ORG_A, act_id=b.act) == []
    assert len(await repo.tariffs(ORG_A, at=DAY)) == 6
    assert len(await repo.tariffs(b.id, at=DAY)) == 1


async def _rules(repo: CatalogRepository, b: OrgB) -> None:
    rules = await repo.rules(ORG_A)
    assert len(rules) == 8
    assert b.rule not in {r.id for r in rules}
    assert len(await repo.rules(ORG_A, "R-12", lock=True)) == 1
    assert await repo.rule_versions(ORG_A, rule_ids=[b.rule]) == []
    assert await repo.rule_versions(ORG_A, version_id=b.rule_version) == []


async def _writes(repo: CatalogRepository, b: OrgB, approver: UUID) -> None:
    """Une mise à jour visant B depuis A ne touche rien."""
    await repo.close_open_predecessor("rule_versions", ORG_A, b.rule, UUID(int=0), FAR)
    await repo.set_state(
        "rule_versions",
        ORG_A,
        b.rule_version,
        "cloturee",
        (approver, datetime(2026, 10, 1, tzinfo=UTC)),
    )
    after = await repo.rule_versions(b.id, version_id=b.rule_version)
    assert after[0].state == "en_vigueur"
    assert after[0].period == Period(date(2026, 1, 1), None)


def test_catalogue_filtre_par_organisation_meme_sans_rls(l2: Platform) -> None:
    env = l2
    b = _org_b(env)
    checks: list[Callable[[CatalogRepository], Awaitable[None]]] = [
        lambda repo: _products(repo, b),
        lambda repo: _network_and_tariffs(repo, b),
        lambda repo: _rules(repo, b),
        lambda repo: _writes(repo, b, env.users["admin_a"]),
    ]

    async def scenario() -> None:
        engine = create_async_engine(sqlalchemy_url(env.dsn))  # superutilisateur : hors RLS
        try:
            async with engine.connect() as conn, conn.begin() as tx:
                repo = CatalogRepository(AsyncSession(bind=conn))
                for check in checks:
                    await check(repo)
                await tx.rollback()
        finally:
            await engine.dispose()

    env.run(scenario)
