"""R6 — secret médical côté permissions, et audit de chaque lecture du motif.

Le service ``MedicalReasonAccess`` du noyau est le seul passage vers le motif médical (L5 le
branche sur HealthOS via L9). Ici HealthOS est simulé par la sonde de test.
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from api.core.context import RequestContext
from api.core.database import Database
from api.core.errors import UpstreamUnavailableError
from api.core.medical import MedicalReasonAccess
from api.core.permissions import Principal, Role, RoleGrant
from api.core.services import AuditService
from api.core.tests.conftest import CoreSeed, owner_count
from api.core.tests.probe import FAKE_HEALTHOS_CALLS

READ_ACTION = "claim.medical_reason.read"


def _audit_reads(seed: CoreSeed, claim: UUID) -> int:
    return owner_count(
        seed,
        "SELECT count(*) FROM audit_events WHERE action = %s AND target_id = %s",
        (READ_ACTION, claim),
    )


@pytest.mark.parametrize("role", ["gestionnaire", "admin", "clinique", "employeur", "sans_role"])
def test_seul_le_medecin_conseil_lit_le_motif(
    client: TestClient, core_seed: CoreSeed, role: str
) -> None:
    claim = core_seed.claims["a"]
    before_audit = _audit_reads(core_seed, claim)
    before_calls = len(FAKE_HEALTHOS_CALLS)

    response = client.get(
        f"/_probe/claims/{claim}/medical-reason", headers=core_seed.auth("a", role)
    )

    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "SEC-01"
    assert "Motif fictif" not in response.text
    assert len(FAKE_HEALTHOS_CALLS) == before_calls, "HealthOS appelé malgré le refus"
    assert _audit_reads(core_seed, claim) == before_audit


def test_chaque_lecture_du_motif_cree_une_entree_d_audit(
    client: TestClient, core_seed: CoreSeed
) -> None:
    claim = core_seed.claims["a"]
    doctor = core_seed.users[("a", "medecin_conseil")]
    before = _audit_reads(core_seed, claim)

    event_ids = []
    for _ in range(3):
        response = client.get(
            f"/_probe/claims/{claim}/medical-reason",
            headers=core_seed.auth("a", "medecin_conseil") | {"X-Request-ID": "req-test-motif"},
        )
        assert response.status_code == 200, response.text
        event_ids.append(response.json()["audit_event_id"])

    assert _audit_reads(core_seed, claim) == before + 3
    assert len(set(event_ids)) == 3
    with psycopg.connect(core_seed.dsn) as conn:
        rows = conn.execute(
            "SELECT organization_id, actor_user_id, actor_role, target_type, request_id, metadata "
            "FROM audit_events WHERE id = ANY(%s::uuid[])",
            (event_ids,),
        ).fetchall()
    assert len(rows) == 3
    for org, actor, actor_role, target_type, request_id, metadata in rows:
        assert org == core_seed.orgs["a"]
        assert actor == doctor
        assert actor_role == "medecin_conseil"
        assert target_type == "claim"
        assert request_id == "req-test-motif"
        assert "Motif" not in str(metadata), "le motif ne doit jamais entrer dans la base"


def test_lecture_echouee_chez_healthos_ne_laisse_ni_motif_ni_audit_partiel(
    core_seed: CoreSeed,
) -> None:
    """Si HealthOS échoue, rien n'a été lu : la transaction (audit compris) est annulée."""
    claim = uuid4()
    principal = Principal(
        user_id=core_seed.users[("a", "medecin_conseil")],
        organization_id=core_seed.orgs["a"],
        grants=(RoleGrant(Role.MEDECIN_CONSEIL),),
    )

    async def failing() -> str:
        raise UpstreamUnavailableError

    async def scenario() -> None:
        db = Database(core_seed.url, app_role="mulema_app")
        try:
            async with db.transaction(principal.organization_id) as session:
                ctx = RequestContext(principal=principal, session=session, request_id="r1")
                await MedicalReasonAccess(AuditService.for_session(session)).read(
                    ctx, claim_id=claim, fetch=failing
                )
        finally:
            await db.dispose()

    with pytest.raises(UpstreamUnavailableError):
        asyncio.run(scenario())
    assert _audit_reads(core_seed, claim) == 0
