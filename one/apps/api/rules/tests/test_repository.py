"""Dépôt des versions (PostgreSQL 16 réel, rôle applicatif sous RLS forcée)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg import sql

from api.rules.engine import evaluate
from api.rules.model import Catalog, ClaimFacts, MemberFacts, Outcome
from api.rules.repository import RulesRepository
from api.rules.versions import select_in_force
from api.tests.contracts.helpers import APP_ROLE, create_organization

DEMO_ORG = UUID("00000000-0000-4000-8000-000000000001")
DEMO_PLAN = UUID("00000000-0000-4000-8000-000000000101")
PLAN_V1 = UUID("00000000-0000-4000-8000-000000000111")
PLAN_V2 = UUID("00000000-0000-4000-8000-000000000112")


def _run[T](dsn: str, work: Callable[[RulesRepository], Awaitable[T]]) -> T:
    """Exécute ``work`` avec un dépôt connecté sous le rôle applicatif (pas de superutilisateur)."""

    async def main() -> T:
        async with await psycopg.AsyncConnection.connect(dsn) as conn:
            await conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(APP_ROLE)))
            await conn.commit()
            return await work(RulesRepository(conn))

    return asyncio.run(main())


def _admin(dsn: str, query: str, params: tuple[object, ...] = ()) -> None:
    with psycopg.connect(dsn) as conn:
        conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(DEMO_ORG),))
        conn.execute(query.encode(), params)


def _add_r12_v2_2025(dsn: str) -> None:
    """Historique fictif : R-12 v2 (seuil 40 000) close au 31/12/2025."""
    _admin(
        dsn,
        "INSERT INTO rule_versions (organization_id, rule_id, version, valid_from, valid_to, "
        "params, state) SELECT organization_id, id, 2, DATE '2025-01-01', DATE '2025-12-31', "
        "'{\"total_max_exclu_xof\": 40000, \"score_fraude_max_exclu\": 0.20}'::jsonb, 'cloturee' "
        "FROM rules WHERE code = 'R-12'",
    )


def test_catalogue_charge_les_versions_publiees(seeded_dsn: str) -> None:
    catalog = _run(seeded_dsn, lambda repo: repo.catalog(DEMO_ORG, DEMO_PLAN))

    assert {(p.version, p.state) for p in catalog.plan_versions} == {
        (1, "cloturee"),
        (2, "en_vigueur"),
    }  # la v3 brouillon n'est pas chargée
    codes = {r.code for r in catalog.rule_versions}
    assert {"R-01", "R-04", "R-07", "R-09", "R-12", "R-20"} <= codes
    v2 = next(p for p in catalog.plan_versions if p.version == 2)
    assert (v2.coverage_rate_bp, v2.family_annual_ceiling_xof, v2.waiting_period_days) == (
        8000,
        3_000_000,
        60,
    )
    assert type(v2.family_annual_ceiling_xof) is int
    assert "hospitalisation" in {c.category for c in v2.coverages}
    r12 = next(r for r in catalog.rule_versions if r.code == "R-12")
    assert r12.params["total_max_exclu_xof"] == 50000


def test_soin_du_20_12_traite_le_05_01_charge_la_version_du_20_12(seeded_dsn: str) -> None:
    _add_r12_v2_2025(seeded_dsn)
    catalog = _run(seeded_dsn, lambda repo: repo.catalog(DEMO_ORG, DEMO_PLAN))
    r12 = [r for r in catalog.rule_versions if r.code == "R-12"]

    old = select_in_force(r12, date(2025, 12, 20), what="R-12")
    new = select_in_force(r12, date(2026, 1, 5), what="R-12")
    assert (old.version, old.params["total_max_exclu_xof"]) == (2, 40000)
    assert (new.version, new.params["total_max_exclu_xof"]) == (3, 50000)
    assert select_in_force(catalog.plan_versions, date(2025, 12, 20), what="produit").id == PLAN_V1
    assert select_in_force(catalog.plan_versions, date(2026, 1, 5), what="produit").id == PLAN_V2


def test_decision_reference_la_version_en_base(seeded_dsn: str) -> None:
    catalog = _run(seeded_dsn, lambda repo: repo.catalog(DEMO_ORG, DEMO_PLAN))
    provider_id = _insert_provider(seeded_dsn)
    service_date = date(2026, 6, 15)

    async def load(repo: RulesRepository) -> ClaimFacts:
        items = await repo.claim_items(DEMO_ORG, [("CONS-GEN", 1), ("CARD-ECG", 1), ("BIO-NFS", 1)])
        provider = await repo.provider_facts(DEMO_ORG, provider_id)
        return ClaimFacts(
            plan_id=DEMO_PLAN,
            service_date=service_date,
            evaluated_at=datetime(2026, 6, 15, 9, 0, tzinfo=UTC),
            member=MemberFacts(status="actif", enrolled_on=date(2025, 1, 10), unpaid_days=0),
            provider=provider,
            items=tuple(items),
            family_consumed_xof=0,
            fraud_score=Decimal("0.06"),
        )

    f = _run(seeded_dsn, load)
    decision = evaluate(f, catalog)
    assert decision.outcome is Outcome.ACCORDEE_AUTO
    assert decision.total_xof == 48_000

    with psycopg.connect(seeded_dsn) as conn:
        row = conn.execute(
            "SELECT r.code, v.version FROM rule_versions v JOIN rules r ON r.id = v.rule_id "
            "WHERE v.rule_id = %s AND v.version = %s",
            (decision.rule.rule_id, decision.rule.version),
        ).fetchone()
    assert row == ("R-12", 3)


def test_acte_inconnu_sans_bareme(seeded_dsn: str) -> None:
    items = _run(seeded_dsn, lambda repo: repo.claim_items(DEMO_ORG, [("ACTE-INCONNU", 2)]))
    assert len(items) == 1
    assert items[0].tariffs == ()
    assert items[0].quantity == 2


def test_isolation_aucune_version_d_une_autre_organisation(seeded_dsn: str) -> None:
    with psycopg.connect(seeded_dsn) as conn:
        other = create_organization(conn, "autre-mutuelle")
        conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(other),))
        conn.execute(
            "INSERT INTO rules (organization_id, code, label, kind) "
            "VALUES (%s, 'R-12', 'Accord automatique B', 'accord_automatique')",
            (other,),
        )
    demo = _run(seeded_dsn, lambda repo: repo.catalog(DEMO_ORG, DEMO_PLAN))
    other_catalog = _run(seeded_dsn, lambda repo: repo.catalog(other, DEMO_PLAN))

    assert other_catalog == Catalog((), ())
    assert all(r.rule_id != other for r in demo.rule_versions)


def _insert_provider(dsn: str) -> UUID:
    with psycopg.connect(dsn) as conn:
        conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(DEMO_ORG),))
        row = conn.execute(
            "INSERT INTO providers (organization_id, name, kind, city, country_code) "
            "VALUES (%s, 'Clinique fictive', 'clinique', 'Ville fictive', 'CI') RETURNING id",
            (DEMO_ORG,),
        ).fetchone()
        assert row is not None
        provider_id: UUID = row[0]
        conn.execute(
            "INSERT INTO provider_conventions (organization_id, provider_id, valid_from) "
            "VALUES (%s, %s, DATE '2025-01-01')",
            (DEMO_ORG, provider_id),
        )
    return provider_id
