"""Une période terminée ne bouge plus (CR-P3-02) : rien de postérieur à ``until`` n'y entre.

Sur une vraie base (jeu d'isolation L0 : un adhérent, un dossier accordé automatiquement, une
cotisation payée, horodatés « maintenant »), sous une session propriétaire :

- une décision prise APRÈS la fin de la période (annulation tardive) ne retire pas le dossier
  d'une période déjà publiée (sinon « avant/après » isolerait ce dossier) ;
- un adhérent dont le statut a changé APRÈS la fin de la période n'y figure pas (instantané) ;
- chaque cellule porte ses semaines (demande et décision), base du seuil par semaine.
Données fictives.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import psycopg

from api.partners.repository import AggregateRepository
from api.partners.tests.test_organization_filter import _org, owner_session

TZ = "Africa/Abidjan"


def _window() -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    return now - timedelta(days=1), now + timedelta(days=1)


def test_decision_tardive_ne_reecrit_pas_la_periode(insurance_dsn: str) -> None:
    org = _org(insurance_dsn, "p3-tardive")
    since, until = _window()

    async def read() -> tuple[int, int]:
        async with owner_session(insurance_dsn, org) as session:
            repo = AggregateRepository(session, org)
            claims = await repo.claims_cost(since, until, TZ)
            return claims.count, len(claims.weeks)

    assert asyncio.run(read()) == (1, 1)
    with psycopg.connect(insurance_dsn) as conn:
        row = conn.execute(
            "SELECT c.id, u.id FROM claims c JOIN users u ON u.organization_id = c.organization_id "
            "WHERE c.organization_id = %s LIMIT 1",
            (org,),
        ).fetchone()
        assert row is not None
        claim, user = row
        conn.execute(
            "INSERT INTO claim_decisions (organization_id, claim_id, sequence, outcome, source, "
            "reason_code, decided_by, decided_at) VALUES (%s, %s, 2, 'annulee', 'humain', "
            "'ANN-01', %s, %s)",
            (org, claim, user, until + timedelta(days=1)),
        )
    assert asyncio.run(read()) == (1, 1)  # annulée APRÈS la période : la période ne bouge pas


def test_statut_pris_a_la_fin_de_la_periode(insurance_dsn: str) -> None:
    org = _org(insurance_dsn, "p3-instantane")
    since, until = _window()

    async def members(at: datetime) -> int:
        async with owner_session(insurance_dsn, org) as session:
            cells = await AggregateRepository(session, org).members_by_status(at)
            return sum(c.count for c in cells)

    assert asyncio.run(members(until)) == 1
    # Adhésion « maintenant » : avant la période, l'adhérent n'existait pas encore.
    assert asyncio.run(members(since)) == 0


def test_semaines_de_la_demande_et_de_la_decision(insurance_dsn: str) -> None:
    org = _org(insurance_dsn, "p3-semaines")
    since, until = _window()
    with psycopg.connect(insurance_dsn) as conn:
        conn.execute(
            "UPDATE claims SET requested_at = requested_at - interval '8 days' "
            "WHERE organization_id = %s",
            (org,),
        )

    async def read() -> tuple[int, list[frozenset[UUID]]]:
        async with owner_session(insurance_dsn, org) as session:
            cell = await AggregateRepository(session, org).claims_cost(
                since - timedelta(days=14), until, TZ
            )
            return cell.count, list(cell.weeks.values())

    count, weeks = asyncio.run(read())
    assert count == 1
    assert len(weeks) == 2  # semaine de la demande ET semaine de la décision
    assert all(len(people) == 1 for people in weeks)
