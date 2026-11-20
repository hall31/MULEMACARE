"""Application ASSEMBLÉE pour les routes L2 : fixture ``platform`` des tests de bout en bout.

Chaque module de test reçoit sa base (fixture de portée module), sous ``mulema_app`` (RLS
forcée) et ``egress_guard``, avec de vrais jetons. ``l2`` ajoute les utilisateurs dont les
routes L2 ont besoin (admins A et B, employeur) et un adhérent fictif actif, posé en SQL par le
propriétaire (le lot L4 n'est pas sous test ici). Toutes les données sont fictives.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from uuid import UUID

import psycopg
import pytest

from api.core.identity import Identity
from api.tests.e2e.conftest import ORG_A, Platform, platform

# ``platform`` : fixture de l'application assemblée, réexportée pour ce dossier.
__all__ = ["Platform", "add_employer_user", "add_insured", "l2", "platform"]

DEMO_PLAN = UUID("00000000-0000-4000-8000-000000000101")
DEMO_PLAN_V2 = UUID("00000000-0000-4000-8000-000000000112")
DEMO_PLAN_V3 = UUID("00000000-0000-4000-8000-000000000113")


@dataclass(frozen=True, slots=True)
class Insured:
    member_id: UUID
    person_id: UUID


def add_employer_user(env: Platform, who: str, org: str) -> None:
    """Utilisateur au rôle ``employeur`` (aucun accès L2), rattaché à un employeur fictif."""
    subject = f"sub-l2-{who}-{uuid.uuid4().hex[:8]}"
    with psycopg.connect(env.dsn) as conn:
        employer = conn.execute(
            "INSERT INTO employers (organization_id, name, contract_start) "
            "VALUES (%s, 'Employeur fictif L2', DATE '2026-01-01') RETURNING id",
            (env.orgs[org],),
        ).fetchone()
        user = conn.execute(
            "INSERT INTO users (organization_id, idp_subject, display_name) "
            "VALUES (%s, %s, 'Agent fictif employeur') RETURNING id",
            (env.orgs[org], subject),
        ).fetchone()
        assert employer is not None
        assert user is not None
        conn.execute(
            "INSERT INTO user_roles (organization_id, user_id, role, employer_id) "
            "VALUES (%s, %s, 'employeur', %s)",
            (env.orgs[org], user[0], employer[0]),
        )
    env.users[who] = user[0]
    env.tokens[who] = env.idp.issue(Identity(subject=subject, organization_id=env.orgs[org]))


def add_insured(env: Platform, number: str) -> Insured:
    """Adhérent fictif actif depuis le 01/01/2026 sur FAMILLE-OR, sans impayé."""
    with psycopg.connect(env.dsn) as conn:
        conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(ORG_A),))
        person = conn.execute(
            "INSERT INTO persons (organization_id, given_name, family_name, birth_date) "
            "VALUES (%s, 'Prénom', 'Fictif', DATE '1990-01-01') RETURNING id",
            (ORG_A,),
        ).fetchone()
        assert person is not None
        member = conn.execute(
            "INSERT INTO members (organization_id, person_id, member_number, plan_id, status, "
            "status_changed_at, enrolled_on, waiting_period_ends_on) VALUES "
            "(%s, %s, %s, %s, 'actif', TIMESTAMPTZ '2026-01-01 00:00Z', DATE '2026-01-01', "
            "DATE '2026-03-02') RETURNING id",
            (ORG_A, person[0], number, DEMO_PLAN),
        ).fetchone()
        assert member is not None
        conn.execute(
            "INSERT INTO member_status_history (organization_id, member_id, to_status, "
            "reason_code, occurred_at) VALUES (%s, %s, 'actif', 'adhesion', "
            "TIMESTAMPTZ '2026-01-01 00:00Z')",
            (ORG_A, member[0]),
        )
    return Insured(member_id=member[0], person_id=person[0])


@pytest.fixture(scope="module")
def l2(platform: Platform) -> Platform:
    platform.add_user("admin_a", "a", "admin")
    platform.add_user("admin_b", "b", "admin")
    platform.add_user("gestionnaire_b", "b", "gestionnaire")
    add_employer_user(platform, "employeur_a", "a")
    return platform
