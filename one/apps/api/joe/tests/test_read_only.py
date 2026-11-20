"""R11 — à l'exécution : chaque outil du registre ne fait que lire.

Deux barrières indépendantes, prouvées séparément :
1. le garde enregistre chaque requête SQL et refuse avant exécution tout ce qui n'est pas une
   lecture ;
2. la base elle-même : le garde ouvre un point de sauvegarde en ``transaction_read_only`` ; une
   écriture déguisée (CTE) qui passerait la première barrière est refusée par PostgreSQL.
Le test d'outil échoue si un outil du registre appelle une fonction d'écriture.
"""

from __future__ import annotations

import asyncio
import re
import secrets
import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from api.claims.tests.conftest import APP_ROLE, ORG_A, ClaimsSeed
from api.core.context import RequestContext
from api.core.database import Database
from api.core.permissions import Principal, Role, RoleGrant
from api.joe.guard import ReadOnlyViolationError, read_only
from api.joe.ports import ReadPorts, member_reader_factory
from api.joe.pseudonym import Pseudonymizer
from api.joe.tests.support import JoeHarness, snapshot
from api.joe.tools import READ_TOOLS, ToolArgs
from api.members.cards import CardKeys

READ_STATEMENT = re.compile(r"^\s*(SELECT|WITH|SHOW)\b", re.IGNORECASE)


def _run_as_gestionnaire[T](seed: ClaimsSeed, body: Callable[[RequestContext], Awaitable[T]]) -> T:
    async def go() -> T:
        database = Database(seed.url, app_role=APP_ROLE)
        try:
            async with database.transaction(ORG_A) as session:
                principal = Principal(
                    user_id=seed.users["gestionnaire"],
                    organization_id=ORG_A,
                    grants=(RoleGrant(Role.GESTIONNAIRE),),
                )
                return await body(RequestContext(principal, session, "req_test_joe"))
        finally:
            await database.dispose()

    return asyncio.run(go())


def _args(harness: JoeHarness) -> ToolArgs:
    return ToolArgs(
        member_id=harness.scenario.member.member_id,
        claim_id=UUID(harness.scenario.review_claim_id),
        at=date(2026, 10, 1),
    )


@pytest.mark.parametrize("name", sorted(READ_TOOLS))
def test_chaque_outil_du_registre_ne_fait_que_lire(harness: JoeHarness, name: str) -> None:
    seed = harness.seed
    before = snapshot(seed)
    members = member_reader_factory(seed.clock, CardKeys(secrets.token_bytes(32)))

    async def body(ctx: RequestContext) -> tuple[list[str], int]:
        ports = ReadPorts(ctx, members(ctx))
        async with read_only(ctx.session) as scope:
            finding = await READ_TOOLS[name].run(ports, Pseudonymizer(), _args(harness))
        return list(scope.statements), len(finding.sources)

    statements, sources = _run_as_gestionnaire(seed, body)
    assert statements, f"{name} n'a rien lu"
    for statement in statements:
        assert READ_STATEMENT.match(statement), f"{name} a exécuté : {statement[:120]}"
    assert sources > 0, f"{name} ne cite aucune source"
    assert snapshot(seed) == before


def test_tous_les_outils_de_lecture_sont_couverts() -> None:
    assert set(READ_TOOLS) == {
        "lire_adherent",
        "lire_droits",
        "lire_historique",
        "lire_cotisations",
        "lire_bareme",
        "lire_dossier",
    }


def test_barriere_applicative_une_ecriture_est_refusee_avant_execution(
    harness: JoeHarness,
) -> None:
    seed = harness.seed
    before = snapshot(seed)

    async def body(ctx: RequestContext) -> None:
        async with read_only(ctx.session):
            await ctx.session.execute(
                text("UPDATE claims SET status = 'accordee' WHERE id = :id"),
                {"id": harness.scenario.review_claim_id},
            )

    with pytest.raises(ReadOnlyViolationError):
        _run_as_gestionnaire(seed, body)
    assert snapshot(seed) == before


def test_barriere_base_une_ecriture_deguisee_est_refusee_par_postgresql(
    harness: JoeHarness,
) -> None:
    seed = harness.seed
    before = snapshot(seed)

    async def body(ctx: RequestContext) -> None:
        async with read_only(ctx.session):
            await ctx.session.execute(
                text(
                    "WITH w AS (UPDATE claims SET status = 'accordee' WHERE id = :id "
                    "RETURNING id) SELECT count(*) FROM w"
                ),
                {"id": harness.scenario.review_claim_id},
            )

    with pytest.raises(DBAPIError, match="read-only transaction"):
        _run_as_gestionnaire(seed, body)
    assert snapshot(seed) == before


def test_apres_le_garde_la_transaction_ecrit_de_nouveau_le_journal(harness: JoeHarness) -> None:
    """Le garde ne laisse pas la transaction en lecture seule : le journal s'écrit après."""
    seed = harness.seed
    marker = f"test_{uuid.uuid4().hex[:8]}"

    async def body(ctx: RequestContext) -> str:
        async with read_only(ctx.session):
            await ctx.session.execute(text("SELECT 1"))
        state: str = (await ctx.session.execute(text("SHOW transaction_read_only"))).scalar_one()
        await ctx.session.execute(
            text(
                "INSERT INTO ai_actions (organization_id, user_id, kind, tool, input) "
                "VALUES (:org, :user, 'lecture', 'lire_bareme', CAST(:input AS jsonb))"
            ),
            {"org": ORG_A, "user": seed.users["gestionnaire"], "input": f'{{"m": "{marker}"}}'},
        )
        return str(state)

    assert _run_as_gestionnaire(seed, body) == "off"
    assert seed.scalar("SELECT count(*) FROM ai_actions WHERE input->>'m' = %s", (marker,)) == 1
