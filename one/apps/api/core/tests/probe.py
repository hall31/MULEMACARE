"""Routes de TEST uniquement : sondes qui passent par la vraie chaîne du noyau.

Jeton → fournisseur d'identité → ``SET LOCAL ROLE`` + ``app.organization_id`` → requête. Elles
prouvent l'isolation table par table « via l'API du noyau » sans attendre les routes des lots
L2 à L8. Jamais montées par l'application réelle.
"""

from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text

from api.core.context import CurrentContext
from api.core.medical import MedicalReasonAccess
from api.core.services import AuditService
from api.tests.paths import SCHEMA_SQL

TABLES: tuple[str, ...] = tuple(
    re.findall(r"^CREATE TABLE (\w+)", SCHEMA_SQL.read_text(encoding="utf-8"), flags=re.MULTILINE)
)

probe_router = APIRouter(prefix="/_probe", include_in_schema=False)


class TableCounts(BaseModel):
    visible_total: int
    visible_for_other: int
    setting: str | None


class MedicalProbeOut(BaseModel):
    text: str
    audit_event_id: UUID


FAKE_HEALTHOS_CALLS: list[UUID] = []


@probe_router.get("/tables/{table}")
async def count_rows(table: str, other: UUID, ctx: CurrentContext) -> TableCounts:
    assert table in TABLES
    column = "id" if table == "organizations" else "organization_id"
    total: int = (await ctx.session.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()
    other_rows: int = (
        await ctx.session.execute(
            text(f"SELECT count(*) FROM {table} WHERE {column} = :other"), {"other": other}
        )
    ).scalar_one()
    setting: str | None = (
        await ctx.session.execute(text("SELECT current_setting('app.organization_id', true)"))
    ).scalar_one()
    return TableCounts(visible_total=total, visible_for_other=other_rows, setting=setting)


@probe_router.post("/deferred-commit-failure")
async def deferred_commit_failure(ctx: CurrentContext) -> dict[str, str]:
    """Écriture comptable sans lignes : refusée seulement au COMMIT (MCL02, différé)."""
    await ctx.session.execute(
        text(
            "INSERT INTO ledger_entries (organization_id, entry_number, accounting_date, label, "
            "source_type) VALUES (:org, :num, DATE '2026-10-01', 'Sonde', 'reglement')"
        ),
        {"org": ctx.principal.organization_id, "num": f"SONDE-{uuid4().hex[:8]}"},
    )
    return {"statut": "ok"}


async def _medical_access(ctx: CurrentContext) -> MedicalReasonAccess:
    return MedicalReasonAccess(AuditService.for_session(ctx.session))


@probe_router.get("/claims/{claim_id}/medical-reason")
async def read_medical_reason(
    claim_id: UUID,
    ctx: CurrentContext,
    access: Annotated[MedicalReasonAccess, Depends(_medical_access)],
) -> MedicalProbeOut:
    async def fake_healthos() -> str:
        FAKE_HEALTHOS_CALLS.append(claim_id)
        return "Motif fictif renvoyé par un HealthOS simulé"

    result = await access.read(ctx, claim_id=claim_id, fetch=fake_healthos)
    return MedicalProbeOut(text=result.text, audit_event_id=result.audit_event_id)
