"""Accès SQL du lot L5 (SQLAlchemy Core ``text``), dans la transaction de la requête.

La transaction est ouverte par le noyau sous ``mulema_app`` avec ``app.organization_id`` (RLS
forcée) ; chaque requête filtre AUSSI explicitement par ``organization_id``. Tables en ajout seul
(``claim_decisions``, ``audit_events``) : INSERT seulement.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession


class ClaimsRepository:
    def __init__(self, session: AsyncSession, organization_id: UUID) -> None:
        self._s = session
        self.org = organization_id

    async def _one(self, sql: str, **params: Any) -> RowMapping | None:  # noqa: ANN401
        result = await self._s.execute(text(sql), {"org": self.org, **params})
        return result.mappings().one_or_none()

    async def _all(self, sql: str, **params: Any) -> Sequence[RowMapping]:  # noqa: ANN401
        result = await self._s.execute(text(sql), {"org": self.org, **params})
        return result.mappings().all()

    async def _exec(self, sql: str, **params: Any) -> None:  # noqa: ANN401
        await self._s.execute(text(sql), {"org": self.org, **params})

    # --- organisation, verrous, numéros ---------------------------------------------------

    async def timezone(self) -> str:
        row = await self._one("SELECT timezone FROM organizations WHERE id = :org")
        if row is None:
            msg = "organisation de la requête invisible (RLS)"
            raise LookupError(msg)
        return str(row["timezone"])

    async def lock(self, name: str) -> None:
        await self._exec(
            "SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))", key=f"{name}:{self.org}"
        )

    async def next_number(self, table: str, column: str, prefix: str) -> str:
        """Numéro suivant ``<prefix>-NNNNN`` (sous verrou de l'appelant)."""
        if (table, column) not in {
            ("claims", "claim_number"),
            ("authorizations", "authorization_number"),
        }:
            raise ValueError(table)
        start = len(prefix) + 2
        row = await self._one(
            f"SELECT coalesce(max(substring({column} FROM {start})::int), 0) AS n "  # noqa: S608
            f"FROM {table} WHERE organization_id = :org AND {column} LIKE :like "
            f"AND substring({column} FROM {start}) ~ '^[0-9]+$'",
            like=f"{prefix}-%",
        )
        current = int(row["n"]) if row is not None else 0
        return f"{prefix}-{current + 1:05d}"

    # --- cartes et identifications --------------------------------------------------------

    _CARD = (
        "SELECT c.id, c.member_id, c.person_id, c.status, c.failed_code_count, c.blocked_until "
        "FROM cards c WHERE c.organization_id = :org "
    )

    _HOLDER = (
        "AND c.status = 'active' AND (c.member_id, c.person_id) = ("
        "SELECT m.id, m.person_id FROM members m "
        "WHERE m.organization_id = :org AND m.member_number = :number)"
    )

    async def card(self, card_id: UUID, *, for_update: bool = False) -> RowMapping | None:
        lock = " FOR UPDATE" if for_update else ""
        sql = self._CARD + "AND c.id = :card" + lock
        return await self._one(sql, card=card_id)

    async def holder_card(self, member_number: str) -> RowMapping | None:
        sql = self._CARD + self._HOLDER
        return await self._one(sql, number=member_number)

    async def update_card(
        self, card_id: UUID, *, failed: int, blocked_until: datetime | None
    ) -> None:
        await self._exec(
            "UPDATE cards SET failed_code_count = :failed, blocked_until = :blocked "
            "WHERE organization_id = :org AND id = :card",
            failed=failed,
            blocked=blocked_until,
            card=card_id,
        )

    async def beneficiary(self, person_id: UUID, member_id: UUID, at: date) -> RowMapping | None:
        return await self._one(
            "SELECT p.id AS person_id, m.member_number, "
            "p.given_name || ' ' || p.family_name AS display_name, pl.code AS plan_code, "
            "m.status AS member_status, coalesce(("
            "  SELECT v.coverage_rate_bp FROM plan_versions v "
            "  WHERE v.organization_id = m.organization_id AND v.plan_id = m.plan_id "
            "  AND v.state IN ('en_vigueur', 'cloturee') AND v.valid_from <= :at "
            "  AND (v.valid_to IS NULL OR v.valid_to >= :at) ORDER BY v.version DESC LIMIT 1"
            "), 0) AS coverage_rate_bp "
            "FROM persons p JOIN members m ON m.organization_id = p.organization_id "
            "JOIN plans pl ON pl.organization_id = m.organization_id AND pl.id = m.plan_id "
            "WHERE p.organization_id = :org AND p.id = :person AND m.id = :member",
            person=person_id,
            member=member_id,
            at=at,
        )

    async def insert_identification(
        self, *, card_id: UUID, provider_id: UUID, operator: UUID, qr_verified: bool,
        started_at: datetime,
    ) -> UUID:  # fmt: skip
        row = await self._one(
            "INSERT INTO identity_checks (organization_id, card_id, provider_id, operator_user_id, "
            "qr_verified, started_at) VALUES (:org, :card, :provider, :operator, :qr, :at) "
            "RETURNING id",
            card=card_id,
            provider=provider_id,
            operator=operator,
            qr=qr_verified,
            at=started_at,
        )
        assert row is not None  # noqa: S101 — RETURNING d'un INSERT
        return UUID(str(row["id"]))

    _IDENTIFICATION = (
        "SELECT i.id, i.card_id, i.provider_id, i.qr_verified, i.photo_confirmed, "
        "i.code_hash, i.code_expires_at, i.code_failed_attempts, i.verified_at, i.status, "
        "c.member_id, c.person_id FROM identity_checks i JOIN cards c "
        "ON c.organization_id = i.organization_id AND c.id = i.card_id "
        "WHERE i.organization_id = :org AND i.id = :id"
    )

    async def identification(
        self, identification_id: UUID, *, for_update: bool = False
    ) -> RowMapping | None:
        lock = " FOR UPDATE OF i" if for_update else ""
        sql = self._IDENTIFICATION + lock
        return await self._one(sql, id=identification_id)

    async def update_identification(self, identification_id: UUID, **fields: Any) -> None:  # noqa: ANN401
        allowed = {
            "photo_confirmed", "code_hash", "code_sent_at", "code_expires_at",
            "code_failed_attempts", "verified_at", "status",
        }  # fmt: skip
        if not fields or set(fields) - allowed:
            raise ValueError(sorted(fields))
        assignments = ", ".join(f"{name} = :{name}" for name in sorted(fields))
        await self._exec(
            f"UPDATE identity_checks SET {assignments} "  # noqa: S608 — colonnes en liste blanche
            "WHERE organization_id = :org AND id = :id",
            id=identification_id,
            **fields,
        )

    async def identification_used(self, identification_id: UUID) -> bool:
        row = await self._one(
            "SELECT 1 AS used FROM claims WHERE organization_id = :org "
            "AND identity_check_id = :id LIMIT 1",
            id=identification_id,
        )
        return row is not None

    async def holder_phone(self, member_id: UUID) -> RowMapping | None:
        return await self._one(
            "SELECT p.id AS person_id, p.phone_e164 FROM members m JOIN persons p "
            "ON p.organization_id = m.organization_id AND p.id = m.person_id "
            "WHERE m.organization_id = :org AND m.id = :member",
            member=member_id,
        )

    async def insert_sms(self, *, person_id: UUID, related_id: UUID, sent_at: datetime) -> None:
        await self._exec(
            "INSERT INTO outbound_messages (organization_id, person_id, channel, template_code, "
            "related_type, related_id, status, created_at, sent_at) VALUES (:org, :person, "
            "'sms', 'code_identification', 'identity_check', :related, 'envoye', :at, :at)",
            person=person_id,
            related=related_id,
            at=sent_at,
        )

    # --- adhérent et actes ----------------------------------------------------------------

    async def member(self, member_id: UUID) -> RowMapping | None:
        return await self._one(
            "SELECT id, plan_id, member_number FROM members WHERE organization_id = :org "
            "AND id = :member",
            member=member_id,
        )

    async def member_by_number(self, number: str) -> RowMapping | None:
        return await self._one(
            "SELECT id, plan_id, person_id FROM members WHERE organization_id = :org "
            "AND member_number = :number",
            number=number,
        )

    async def is_beneficiary(self, member_id: UUID, person_id: UUID, at: date) -> bool:
        row = await self._one(
            "SELECT 1 AS ok FROM members m WHERE m.organization_id = :org AND m.id = :member "
            "AND (m.person_id = :person OR EXISTS (SELECT 1 FROM dependents d "
            "WHERE d.organization_id = m.organization_id AND d.member_id = m.id "
            "AND d.person_id = :person AND d.valid_from <= :at "
            "AND (d.valid_to IS NULL OR d.valid_to >= :at)))",
            member=member_id,
            person=person_id,
            at=at,
        )
        return row is not None

    async def acts(self, codes: Sequence[str], at: date) -> dict[str, RowMapping]:
        rows = await self._all(
            "SELECT a.id, a.code, a.label, ("
            "  SELECT t.id FROM tariff_items t WHERE t.organization_id = a.organization_id "
            "  AND t.act_id = a.id AND t.valid_from <= :at "
            "  AND (t.valid_to IS NULL OR t.valid_to >= :at) ORDER BY t.valid_from DESC LIMIT 1"
            ") AS tariff_item_id FROM acts a WHERE a.organization_id = :org "
            "AND a.code = ANY(:codes)",
            codes=list(codes),
            at=at,
        )
        return {str(r["code"]): r for r in rows}

    # --- dossiers -------------------------------------------------------------------------

    async def insert_claim(self, **values: Any) -> UUID:  # noqa: ANN401
        row = await self._one(
            "INSERT INTO claims (organization_id, claim_number, member_id, beneficiary_person_id, "
            "provider_id, identity_check_id, channel, service_date, plan_version_id, status, "
            "total_xof, covered_xof, patient_share_xof, fraud_score, healthos_encounter_ref, "
            "requested_at, created_by) VALUES (:org, :claim_number, :member_id, "
            ":beneficiary_person_id, :provider_id, :identity_check_id, :channel, :service_date, "
            ":plan_version_id, 'demandee', :total_xof, :covered_xof, :patient_share_xof, "
            ":fraud_score, :healthos_encounter_ref, :requested_at, :created_by) RETURNING id",
            **values,
        )
        assert row is not None  # noqa: S101
        return UUID(str(row["id"]))

    async def insert_items(self, claim_id: UUID, items: Sequence[Mapping[str, Any]]) -> None:
        for line_no, item in enumerate(items, start=1):
            await self._exec(
                "INSERT INTO claim_items (organization_id, claim_id, line_no, act_id, "
                "tariff_item_id, quantity, unit_amount_xof, amount_xof, covered_xof) VALUES "
                "(:org, :claim, :line_no, :act_id, :tariff_item_id, :quantity, :unit_amount_xof, "
                ":amount_xof, :covered_xof)",
                claim=claim_id,
                line_no=line_no,
                **item,
            )

    async def claim(self, claim_id: UUID, *, for_update: bool = False) -> RowMapping | None:
        lock = " FOR UPDATE" if for_update else ""
        return await self._one(
            "SELECT * FROM claims WHERE organization_id = :org AND id = :claim" + lock,  # noqa: S608
            claim=claim_id,
        )

    async def insert_decision(  # noqa: PLR0913
        self, claim_id: UUID, *, outcome: str, source: str, rule_id: UUID | None,
        rule_version: int | None, reason_code: str, decided_by: UUID | None,
        trace: list[dict[str, object]], decided_at: datetime,
    ) -> int:  # fmt: skip
        row = await self._one(
            "INSERT INTO claim_decisions (organization_id, claim_id, sequence, outcome, source, "
            "rule_id, rule_version, reason_code, decided_by, evaluation_trace, decided_at) "
            "SELECT :org, :claim, coalesce(max(sequence), 0) + 1, :outcome, :source, :rule_id, "
            ":rule_version, :reason, :by, CAST(:trace AS jsonb), :at FROM claim_decisions "
            "WHERE organization_id = :org AND claim_id = :claim RETURNING sequence",
            claim=claim_id,
            outcome=outcome,
            source=source,
            rule_id=rule_id,
            rule_version=rule_version,
            reason=reason_code,
            by=decided_by,
            trace=json.dumps(trace, ensure_ascii=False),
            at=decided_at,
        )
        assert row is not None  # noqa: S101
        return int(row["sequence"])

    async def set_claim_state(  # noqa: PLR0913
        self, claim_id: UUID, *, status: str, rule_id: UUID | None, rule_version: int | None,
        decided_at: datetime | None, review_due_at: datetime | None,
        covered_xof: int | None = None, patient_share_xof: int | None = None,
    ) -> None:  # fmt: skip
        await self._exec(
            "UPDATE claims SET status = :status, decision_rule_id = :rule_id, "
            "decision_rule_version = :rule_version, decided_at = :decided_at, "
            "review_due_at = :review_due_at, "
            "covered_xof = coalesce(:covered, covered_xof), "
            "patient_share_xof = coalesce(:share, patient_share_xof) "
            "WHERE organization_id = :org AND id = :claim",
            claim=claim_id,
            status=status,
            rule_id=rule_id,
            rule_version=rule_version,
            decided_at=decided_at,
            review_due_at=review_due_at,
            covered=covered_xof,
            share=patient_share_xof,
        )

    async def insert_authorization(self, **values: Any) -> UUID:  # noqa: ANN401
        row = await self._one(
            "INSERT INTO authorizations (organization_id, authorization_number, claim_id, kind, "
            "status, covered_xof, rule_id, rule_version, issued_at, expires_at, device_id, "
            "offline_ref, device_signature, signed_payload, synced_at) VALUES (:org, "
            ":authorization_number, :claim_id, :kind, :status, :covered_xof, :rule_id, "
            ":rule_version, :issued_at, :expires_at, :device_id, :offline_ref, "
            ":device_signature, CAST(:signed_payload AS jsonb), :synced_at) RETURNING id",
            **values,
        )
        assert row is not None  # noqa: S101
        return UUID(str(row["id"]))

    async def insert_documents(
        self, claim_id: UUID, documents: Sequence[tuple[str, str]], *, by: UUID, at: datetime
    ) -> None:
        for kind, ref in documents:
            await self._exec(
                "INSERT INTO claim_documents (organization_id, claim_id, kind, "
                "healthos_document_ref, submitted_by, submitted_at) VALUES (:org, :claim, :kind, "
                ":ref, :by, :at) ON CONFLICT (organization_id, claim_id, healthos_document_ref) "
                "DO NOTHING",
                claim=claim_id,
                kind=kind,
                ref=ref,
                by=by,
                at=at,
            )

    # --- lecture des dossiers (sans aucune donnée médicale) -------------------------------

    _SUMMARY = (
        "SELECT c.id, c.claim_number, c.member_id, c.provider_id, c.service_date, "
        "c.requested_at, c.status, c.total_xof, c.covered_xof, c.patient_share_xof, "
        "c.fraud_score, c.fraud_flagged, c.plan_version_id, c.review_due_at, "
        "p.given_name || ' ' || p.family_name AS member_display_name, pr.name AS provider_name, "
        "r.code AS rule_code, c.decision_rule_version AS rule_version "
        "FROM claims c "
        "JOIN persons p ON p.organization_id = c.organization_id "
        "AND p.id = c.beneficiary_person_id "
        "JOIN providers pr ON pr.organization_id = c.organization_id AND pr.id = c.provider_id "
        "LEFT JOIN rules r ON r.organization_id = c.organization_id "
        "AND r.id = c.decision_rule_id "
        "WHERE c.organization_id = :org "
    )

    async def summary(self, claim_id: UUID) -> RowMapping | None:
        return await self._one(self._SUMMARY + "AND c.id = :claim", claim=claim_id)

    async def list_summaries(  # noqa: PLR0913
        self, *, providers: Sequence[UUID] | None, status: str | None,
        fraud_flagged: bool | None, member_id: UUID | None, start: datetime | None,
        end: datetime | None, before: tuple[datetime, UUID] | None, limit: int,
    ) -> Sequence[RowMapping]:  # fmt: skip
        conditions = [
            ("AND c.provider_id = ANY(:providers) ", providers is not None),
            ("AND c.status = :status ", status is not None),
            ("AND c.fraud_flagged = :fraud ", fraud_flagged is not None),
            ("AND c.member_id = :member ", member_id is not None),
            ("AND c.requested_at >= :start ", start is not None),
            ("AND c.requested_at < :end ", end is not None),
            ("AND (c.requested_at, c.id) < (:before_at, :before_id) ", before is not None),
        ]
        where = "".join(sql for sql, active in conditions if active)
        return await self._all(
            self._SUMMARY + where + "ORDER BY c.requested_at DESC, c.id DESC LIMIT :limit",
            providers=list(providers or []),
            status=status,
            fraud=fraud_flagged,
            member=member_id,
            start=start,
            end=end,
            before_at=before[0] if before else None,
            before_id=before[1] if before else None,
            limit=limit,
        )

    async def items(self, claim_id: UUID) -> Sequence[RowMapping]:
        return await self._all(
            "SELECT i.line_no, a.code AS act_code, a.label, i.quantity, i.unit_amount_xof, "
            "i.amount_xof, i.covered_xof FROM claim_items i JOIN acts a "
            "ON a.organization_id = i.organization_id AND a.id = i.act_id "
            "WHERE i.organization_id = :org AND i.claim_id = :claim ORDER BY i.line_no",
            claim=claim_id,
        )

    async def decisions(self, claim_id: UUID) -> Sequence[RowMapping]:
        return await self._all(
            "SELECT d.sequence, d.outcome, d.source, r.code AS rule_code, d.rule_version, "
            "d.reason_code, d.decided_by, d.decided_at FROM claim_decisions d "
            "LEFT JOIN rules r ON r.organization_id = d.organization_id AND r.id = d.rule_id "
            "WHERE d.organization_id = :org AND d.claim_id = :claim ORDER BY d.sequence",
            claim=claim_id,
        )

    async def authorization(self, claim_id: UUID) -> RowMapping | None:
        return await self._one(
            "SELECT a.id, a.authorization_number, a.kind, a.status, a.covered_xof, "
            "r.code AS rule_code, a.rule_version, a.issued_at, a.expires_at "
            "FROM authorizations a JOIN rules r ON r.organization_id = a.organization_id "
            "AND r.id = a.rule_id WHERE a.organization_id = :org AND a.claim_id = :claim "
            "ORDER BY a.issued_at DESC LIMIT 1",
            claim=claim_id,
        )

    async def work_queue(
        self, day_start: datetime, day_end: datetime, unpaid_before: date
    ) -> RowMapping:
        row = await self._one(
            "SELECT "
            "(SELECT count(*) FROM claims WHERE organization_id = :org AND status = 'en_revue') "
            "AS claims_in_review, "
            "(SELECT count(*) FROM claims WHERE organization_id = :org AND fraud_flagged "
            " AND status IN ('demandee', 'en_revue', 'pieces_demandees')) AS fraud_alerts, "
            "(SELECT count(DISTINCT member_id) FROM contributions WHERE organization_id = :org "
            " AND status IN ('a_payer', 'en_retard') AND due_on < :unpaid_before) "
            "AS members_unpaid_over_30_days, "
            "(SELECT count(*) FROM claims WHERE organization_id = :org "
            " AND status = 'accordee_auto' AND requested_at >= :day_start "
            " AND requested_at < :day_end) AS auto_approved_today",
            day_start=day_start,
            day_end=day_end,
            unpaid_before=unpaid_before,
        )
        assert row is not None  # noqa: S101
        return row

    async def encounter_target(self, claim_id: UUID) -> RowMapping | None:
        return await self._one(
            "SELECT c.healthos_encounter_ref, p.healthos_pseudonym FROM claims c "
            "JOIN persons p ON p.organization_id = c.organization_id "
            "AND p.id = c.beneficiary_person_id WHERE c.organization_id = :org AND c.id = :claim",
            claim=claim_id,
        )

    # --- boîte d'envoi et idempotence -----------------------------------------------------

    async def insert_event(
        self, event_type: str, aggregate_id: UUID, payload: Mapping[str, Any], at: datetime
    ) -> None:
        await self._exec(
            "INSERT INTO outbox_events (organization_id, event_type, aggregate_id, payload, "
            "occurred_at) VALUES (:org, :type, :aggregate, CAST(:payload AS jsonb), :at)",
            type=event_type,
            aggregate=aggregate_id,
            payload=json.dumps(payload, ensure_ascii=False),
            at=at,
        )

    async def reserve_key(
        self, scope: str, key: str, request_hash: str, now: datetime, expires_at: datetime
    ) -> RowMapping | None:
        """Réserve la clé ; renvoie la ligne existante si elle l'était déjà."""
        await self._exec(
            "DELETE FROM idempotency_keys WHERE organization_id = :org AND scope = :scope "
            "AND key = :key AND expires_at <= :now",
            scope=scope,
            key=key,
            now=now,
        )
        inserted = await self._one(
            "INSERT INTO idempotency_keys (organization_id, scope, key, request_hash, created_at, "
            "expires_at) VALUES (:org, :scope, :key, :hash, :now, :expires) "
            "ON CONFLICT (organization_id, scope, key) DO NOTHING RETURNING key",
            scope=scope,
            key=key,
            hash=request_hash,
            now=now,
            expires=expires_at,
        )
        if inserted is not None:
            return None
        return await self._one(
            "SELECT request_hash, status, response_status, response_body FROM idempotency_keys "
            "WHERE organization_id = :org AND scope = :scope AND key = :key",
            scope=scope,
            key=key,
        )

    async def complete_key(self, scope: str, key: str, status: int, body: object) -> None:
        await self._exec(
            "UPDATE idempotency_keys SET status = 'terminee', response_status = :status, "
            "response_body = CAST(:body AS jsonb) WHERE organization_id = :org "
            "AND scope = :scope AND key = :key",
            scope=scope,
            key=key,
            status=status,
            body=json.dumps(body, ensure_ascii=False),
        )

    # --- appareils de comptoir ------------------------------------------------------------

    async def insert_device(
        self, *, provider_id: UUID, label: str, public_key: str, at: datetime
    ) -> RowMapping:
        row = await self._one(
            "INSERT INTO counter_devices (organization_id, provider_id, label, public_key, "
            "registered_at) VALUES (:org, :provider, :label, :key, :at) "
            "RETURNING id, label, status, registered_at",
            provider=provider_id,
            label=label,
            key=public_key,
            at=at,
        )
        assert row is not None  # noqa: S101
        return row

    async def device(self, device_id: UUID) -> RowMapping | None:
        return await self._one(
            "SELECT id, provider_id, public_key, status FROM counter_devices "
            "WHERE organization_id = :org AND id = :device",
            device=device_id,
        )

    async def offline_authorization(self, device_id: UUID, offline_ref: UUID) -> RowMapping | None:
        return await self._one(
            "SELECT a.id, a.claim_id, a.status, d.reason_code FROM authorizations a "
            "JOIN claim_decisions d ON d.organization_id = a.organization_id "
            "AND d.claim_id = a.claim_id AND d.sequence = 1 "
            "WHERE a.organization_id = :org AND a.device_id = :device AND a.offline_ref = :ref",
            device=device_id,
            ref=offline_ref,
        )

    async def tariff(self, at: date) -> Sequence[RowMapping]:
        return await self._all(
            "SELECT a.code AS act_code, a.label, t.amount_xof, t.valid_from, t.valid_to, "
            "a.requires_prior_approval FROM tariff_items t JOIN acts a "
            "ON a.organization_id = t.organization_id AND a.id = t.act_id "
            "WHERE t.organization_id = :org AND t.valid_from <= :at "
            "AND (t.valid_to IS NULL OR t.valid_to >= :at) ORDER BY a.code",
            at=at,
        )
