"""Dépôt de l'espace adhérent (P1) : seul endroit SQL du module, lecture seule.

Le dépôt est construit pour UN contrat : celui du rôle ``adherent`` du jeton (jamais un
paramètre de la requête). Chaque requête filtre par ``organization_id`` (en plus de la RLS
forcée) ET par ce contrat (``member_id``) : un adhérent A ne lit rien de l'adhérent A' de la
même organisation. Les tests de mutation retirent ces filtres et exigent le rouge.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession


class MemberSpaceRepository:
    def __init__(self, session: AsyncSession, organization_id: UUID, member_id: UUID) -> None:
        self._session = session
        self.org = organization_id
        self.member = member_id

    async def _all(self, sql: str, **params: Any) -> Sequence[RowMapping]:  # noqa: ANN401
        bound = {"org": self.org, "member": self.member, **params}
        return (await self._session.execute(text(sql), bound)).mappings().all()

    async def _one(self, sql: str, **params: Any) -> RowMapping | None:  # noqa: ANN401
        rows = await self._all(sql, **params)
        return rows[0] if rows else None

    # --- Contrat, bénéficiaires, carte -----------------------------------------------------

    async def contract(self) -> RowMapping | None:
        return await self._one(
            "SELECT m.id, m.member_number, m.person_id, pl.code AS plan_code FROM members m "
            "JOIN plans pl ON pl.organization_id = m.organization_id AND pl.id = m.plan_id "
            "WHERE m.organization_id = :org AND m.id = :member"
        )

    async def beneficiaries(self) -> Sequence[RowMapping]:
        """Titulaire puis ayants droit du contrat, avec leur carte active éventuelle."""
        return await self._all(
            "SELECT b.person_id, p.given_name, p.family_name, b.relationship, b.valid_from, "
            "b.valid_to, c.id AS card_id, c.blocked_until FROM ("
            " SELECT m.person_id, 'titulaire' AS relationship, m.enrolled_on AS valid_from, "
            " CAST(NULL AS date) AS valid_to, 0 AS rank, m.created_at FROM members m "
            " WHERE m.organization_id = :org AND m.id = :member "
            " UNION ALL "
            " SELECT d.person_id, d.relationship, d.valid_from, d.valid_to, 1, d.created_at "
            " FROM dependents d WHERE d.organization_id = :org AND d.member_id = :member"
            ") b "
            "JOIN persons p ON p.organization_id = :org AND p.id = b.person_id "
            "LEFT JOIN cards c ON c.organization_id = :org AND c.member_id = :member "
            "AND c.person_id = b.person_id AND c.status = 'active' "
            "ORDER BY b.rank, b.valid_from, b.created_at, b.person_id"
        )

    async def coverage_rate_bp(self, plan_version_id: UUID) -> int:
        row = await self._one(
            "SELECT coverage_rate_bp FROM plan_versions "
            "WHERE organization_id = :org AND id = :version",
            version=plan_version_id,
        )
        return int(row["coverage_rate_bp"]) if row is not None else 0

    # --- Prises en charge (sans acte, motif, score ni règle interne) ------------------------

    _CLAIM = (
        "SELECT c.id, c.claim_number, c.beneficiary_person_id, "
        "p.given_name AS beneficiary_given_name, pr.name AS provider_name, c.service_date, "
        "c.requested_at, c.status, c.total_xof, c.covered_xof, c.patient_share_xof, "
        "r.code AS rule_code, c.decision_rule_version AS rule_version "
        "FROM claims c "
        "JOIN persons p ON p.organization_id = c.organization_id "
        "AND p.id = c.beneficiary_person_id "
        "JOIN providers pr ON pr.organization_id = c.organization_id AND pr.id = c.provider_id "
        "LEFT JOIN rules r ON r.organization_id = c.organization_id "
        "AND r.id = c.decision_rule_id "
        "WHERE c.organization_id = :org AND c.member_id = :member "
    )

    async def claims_page(
        self, before: tuple[datetime, UUID] | None, limit: int
    ) -> Sequence[RowMapping]:
        position = "AND (c.requested_at, c.id) < (:before_at, :before_id) " if before else ""
        return await self._all(
            self._CLAIM + position + "ORDER BY c.requested_at DESC, c.id DESC LIMIT :limit",
            before_at=before[0] if before else None,
            before_id=before[1] if before else None,
            limit=limit,
        )

    async def claim(self, claim_id: UUID) -> RowMapping | None:
        return await self._one(self._CLAIM + "AND c.id = :claim", claim=claim_id)

    async def decisions(self, claim_id: UUID) -> Sequence[RowMapping]:
        """Journal des décisions d'un dossier DU contrat (jointure sur le contrat)."""
        return await self._all(
            "SELECT d.outcome, r.code AS rule_code, d.rule_version, d.reason_code, d.decided_at "
            "FROM claim_decisions d "
            "JOIN claims c ON c.organization_id = d.organization_id AND c.id = d.claim_id "
            "AND c.member_id = :member "
            "LEFT JOIN rules r ON r.organization_id = d.organization_id AND r.id = d.rule_id "
            "WHERE d.organization_id = :org AND d.claim_id = :claim ORDER BY d.sequence",
            claim=claim_id,
        )

    # --- Cotisations ----------------------------------------------------------------------------

    async def contributions(self) -> Sequence[RowMapping]:
        """Échéances du contrat ; payeur = type et pays seulement (aucune autre donnée)."""
        return await self._all(
            "SELECT c.id, c.period_start, c.due_on, c.amount_xof, c.status, c.paid_at, "
            "pay.channel, pay.payer_kind, pay.payer_country_code FROM contributions c "
            "LEFT JOIN LATERAL (SELECT p.channel, p.payer_kind, p.payer_country_code "
            " FROM payments p WHERE p.organization_id = c.organization_id "
            " AND p.contribution_id = c.id AND p.status = 'confirme' "
            " ORDER BY p.confirmed_at DESC LIMIT 1) pay ON true "
            "WHERE c.organization_id = :org AND c.member_id = :member "
            "ORDER BY c.period_start DESC, c.id DESC"
        )
