"""Catalogue et dossiers FICTIFS pour les tests du moteur (aucune donnée réelle).

Le catalogue reprend le paramétrage de ``specs/seeds/demo.sql`` (valeurs (proto)) et y ajoute
un historique 2025 fictif : produit v1 et règle R-12 v2 (seuil 40 000 FCFA), remplacée le
01/01/2026 par R-12 v3 (seuil 50 000 FCFA). Sert à prouver R3 (version à la date du soin).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, TypedDict, Unpack
from uuid import UUID

from api.rules.model import (
    Catalog,
    ClaimFacts,
    ClaimItem,
    Coverage,
    MemberFacts,
    Period,
    PlanVersion,
    ProviderFacts,
    RuleVersion,
    Tariff,
)

PLAN_ID = UUID("00000000-0000-4000-8000-000000000101")
PLAN_V1_ID = UUID("00000000-0000-4000-8000-000000000111")
PLAN_V2_ID = UUID("00000000-0000-4000-8000-000000000112")
PLAN_V3_ID = UUID("00000000-0000-4000-8000-000000000113")

RULE_IDS: dict[str, UUID] = {
    code: UUID(f"00000000-0000-4000-9000-0000000000{index:02d}")
    for index, code in enumerate(["R-01", "R-04", "R-07", "R-09", "R-12", "R-20"], start=1)
}

Y2025 = Period(date(2025, 1, 1), date(2025, 12, 31))
Y2026 = Period(date(2026, 1, 1), None)


def rule(
    code: str, version: int, period: Period, params: dict[str, Any], state: str = ""
) -> RuleVersion:
    return RuleVersion(
        rule_id=RULE_IDS[code],
        code=code,
        version=version,
        period=period,
        state=state or ("cloturee" if period.valid_to else "en_vigueur"),
        params=params,
    )


R01 = {"statuts_ouvrant_droits": ["actif"], "suspension_apres_jours_impayes": 45}
R04 = {"convention_active_a_la_date_du_soin": True}
R07 = {"delai_source": "plan_version"}
R09 = {"perimetre": "famille"}
R12_V2 = {"total_max_exclu_xof": 40000, "score_fraude_max_exclu": 0.20}
R12_V3 = {"total_max_exclu_xof": 50000, "score_fraude_max_exclu": 0.20}
R20 = {"delai_cible_minutes": 120}

RULE_HISTORY: tuple[RuleVersion, ...] = (
    # Historique 2025 fictif (versions closes au 31/12/2025).
    rule("R-01", 1, Y2025, R01),
    rule("R-04", 1, Y2025, R04),
    rule("R-07", 1, Y2025, R07),
    rule("R-09", 1, Y2025, R09),
    rule("R-12", 2, Y2025, R12_V2),
    rule("R-20", 1, Y2025, R20),
    # En vigueur depuis le 01/01/2026 (demo.sql).
    rule("R-01", 2, Y2026, R01),
    rule("R-04", 2, Y2026, R04),
    rule("R-07", 2, Y2026, R07),
    rule("R-09", 2, Y2026, R09),
    rule("R-12", 3, Y2026, R12_V3),
    rule("R-20", 2, Y2026, R20),
)

COVERAGES = (
    Coverage("soins_courants", None),
    Coverage("hospitalisation", None),
    Coverage("optique", None),
)

PLAN_HISTORY: tuple[PlanVersion, ...] = (
    PlanVersion(PLAN_V1_ID, PLAN_ID, 1, Y2025, "cloturee", 8000, 2_500_000, 90, COVERAGES),
    PlanVersion(
        PLAN_V2_ID,
        PLAN_ID,
        2,
        Period(date(2026, 1, 1), date(2026, 12, 31)),
        "en_vigueur",
        8000,
        3_000_000,
        60,
        COVERAGES,
    ),
    PlanVersion(
        PLAN_V3_ID,
        PLAN_ID,
        3,
        Period(date(2027, 1, 1), None),
        "brouillon",
        8000,
        3_200_000,
        60,
        COVERAGES,
    ),
)

CATALOG = Catalog(plan_versions=PLAN_HISTORY, rule_versions=RULE_HISTORY)

# Barème conventionné (demo.sql) : CONS-GEN change au 01/01/2026.
TARIFFS: dict[str, tuple[Tariff, ...]] = {
    "CONS-GEN": (Tariff(22000, Y2025), Tariff(25000, Y2026)),
    "BIO-NFS": (Tariff(8000, Y2025), Tariff(8000, Y2026)),
    "CARD-ECG": (Tariff(15000, Y2025), Tariff(15000, Y2026)),
    "IMG-ECHO-ABD": (Tariff(30000, Y2025), Tariff(30000, Y2026)),
    "IMG-RX-THO": (Tariff(18000, Y2025), Tariff(18000, Y2026)),
    "CONS-SPE": (Tariff(35000, Y2025), Tariff(35000, Y2026)),
}


def item(act_code: str, quantity: int = 1, category: str = "soins_courants") -> ClaimItem:
    return ClaimItem(act_code, category, quantity, TARIFFS.get(act_code, ()))


class FactsOverrides(TypedDict, total=False):
    """Champs de ``ClaimFacts`` surchargeables dans un test."""

    service_date: date
    evaluated_at: datetime
    member: MemberFacts
    provider: ProviderFacts
    family_consumed_xof: int


def facts(
    *items: ClaimItem,
    fraud_score: str | None = "0.06",
    **overrides: Unpack[FactsOverrides],
) -> ClaimFacts:
    """Dossier sous seuil, tout en règle, sauf surcharges explicites."""
    base = ClaimFacts(
        plan_id=PLAN_ID,
        service_date=date(2026, 6, 15),
        evaluated_at=datetime(2026, 6, 15, 9, 30, tzinfo=UTC),
        member=MemberFacts(status="actif", enrolled_on=date(2024, 3, 1), unpaid_days=0),
        provider=ProviderFacts(active=True, conventions=(Period(date(2024, 1, 1), None),)),
        items=items or (item("CONS-GEN"),),
        family_consumed_xof=0,
        fraud_score=None if fraud_score is None else Decimal(fraud_score),
    )
    return replace(base, **overrides)
