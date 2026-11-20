"""Dépôt de LECTURE de JOE (SELECT seulement) : barème, pièces d'un dossier, recherche ⌘K,
journal ``ai_actions``.

La transaction vient du noyau (rôle ``mulema_app``, RLS forcée, organisation du jeton) ; chaque
requête filtre AUSSI explicitement par ``organization_id``. Aucune colonne médicale ni
référence HealthOS n'est lue. La seule écriture de JOE est dans ``api.joe.journal``.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class TariffLine:
    id: UUID
    act_code: str
    label: str
    amount_xof: int
    valid_from: date


@dataclass(frozen=True, slots=True)
class SearchRow:
    type: str
    id: UUID
    label: str
    meta: str | None


@dataclass(frozen=True, slots=True)
class AiActionRow:
    id: UUID
    occurred_at: datetime
    user_id: UUID
    kind: str
    tool: str
    model: str | None
    sources: list[dict[str, Any]]


def like_pattern(term: str) -> str:
    """Motif ILIKE « contient », jokers de l'utilisateur échappés."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class JoeReadRepository:
    def __init__(self, session: AsyncSession, organization_id: UUID) -> None:
        self._s = session
        self.org = organization_id

    async def _all(self, sql: str, **params: Any) -> Sequence[RowMapping]:  # noqa: ANN401
        result = await self._s.execute(text(sql), {"org": self.org, **params})
        return result.mappings().all()

    async def timezone(self) -> str:
        rows = await self._all("SELECT timezone FROM organizations WHERE id = :org")
        if not rows:
            msg = "organisation de la requête invisible (RLS)"
            raise LookupError(msg)
        return str(rows[0]["timezone"])

    async def member_number(self, member_id: UUID) -> str | None:
        rows = await self._all(
            "SELECT member_number FROM members WHERE organization_id = :org AND id = :member",
            member=member_id,
        )
        return str(rows[0]["member_number"]) if rows else None

    async def claim_document_kinds(self, claim_id: UUID) -> tuple[str, ...]:
        rows = await self._all(
            "SELECT kind FROM claim_documents WHERE organization_id = :org AND claim_id = :claim "
            "ORDER BY submitted_at, id",
            claim=claim_id,
        )
        return tuple(str(r["kind"]) for r in rows)

    async def tariff(self, at: date) -> Sequence[TariffLine]:
        rows = await self._all(
            "SELECT t.id, a.code AS act_code, a.label, t.amount_xof, t.valid_from "
            "FROM tariff_items t JOIN acts a ON a.organization_id = t.organization_id "
            "AND a.id = t.act_id WHERE t.organization_id = :org AND t.valid_from <= :at "
            "AND (t.valid_to IS NULL OR t.valid_to >= :at) ORDER BY a.code",
            at=at,
        )
        return [
            TariffLine(
                r["id"], str(r["act_code"]), str(r["label"]), int(r["amount_xof"]), r["valid_from"]
            )
            for r in rows
        ]

    # --- Recherche ⌘K ------------------------------------------------------------------------

    async def search_members(self, term: str, limit: int) -> list[SearchRow]:
        rows = await self._all(
            "SELECT m.id, m.member_number, p.given_name || ' ' || p.family_name AS name, "
            "m.status FROM members m JOIN persons p ON p.organization_id = m.organization_id "
            "AND p.id = m.person_id WHERE m.organization_id = :org AND ("
            "m.member_number ILIKE :like OR p.given_name ILIKE :like "
            "OR p.family_name ILIKE :like "
            "OR (p.given_name || ' ' || p.family_name) ILIKE :like) "
            "ORDER BY m.member_number LIMIT :limit",
            like=like_pattern(term),
            limit=limit,
        )
        return [
            SearchRow("member", r["id"], f"{r['member_number']} · {r['name']}", str(r["status"]))
            for r in rows
        ]

    async def search_claims(
        self, term: str, providers: Sequence[UUID] | None, limit: int
    ) -> list[SearchRow]:
        scoped = "AND c.provider_id = ANY(:providers) " if providers is not None else ""
        rows = await self._all(
            "SELECT c.id, c.claim_number, c.status FROM claims c "  # noqa: S608 — fragment fixe
            "WHERE c.organization_id = :org AND c.claim_number ILIKE :like "
            + scoped
            + "ORDER BY c.requested_at DESC, c.id DESC LIMIT :limit",
            like=like_pattern(term),
            providers=list(providers or []),
            limit=limit,
        )
        return [SearchRow("claim", r["id"], str(r["claim_number"]), str(r["status"])) for r in rows]

    async def search_providers(
        self, term: str, providers: Sequence[UUID] | None, limit: int
    ) -> list[SearchRow]:
        scoped = "AND p.id = ANY(:providers) " if providers is not None else ""
        rows = await self._all(
            "SELECT p.id, p.name, p.city FROM providers p "  # noqa: S608 — fragment fixe
            "WHERE p.organization_id = :org AND (p.name ILIKE :like OR p.city ILIKE :like) "
            + scoped
            + "ORDER BY p.name, p.id LIMIT :limit",
            like=like_pattern(term),
            providers=list(providers or []),
            limit=limit,
        )
        return [SearchRow("provider", r["id"], str(r["name"]), str(r["city"])) for r in rows]

    # --- Journal ------------------------------------------------------------------------------

    async def ai_actions(
        self,
        *,
        start: datetime | None,
        end: datetime | None,
        before: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[AiActionRow]:
        conditions = [
            ("AND occurred_at >= :start ", start is not None),
            ("AND occurred_at < :end ", end is not None),
            ("AND (occurred_at, id) < (:before_at, :before_id) ", before is not None),
        ]
        where = "".join(sql for sql, active in conditions if active)
        rows = await self._all(
            "SELECT id, occurred_at, user_id, kind, tool, model, sources FROM ai_actions "  # noqa: S608
            "WHERE organization_id = :org "
            + where
            + "ORDER BY occurred_at DESC, id DESC LIMIT :limit",
            start=start,
            end=end,
            before_at=before[0] if before else None,
            before_id=before[1] if before else None,
            limit=limit,
        )
        return [
            AiActionRow(
                id=r["id"],
                occurred_at=r["occurred_at"],
                user_id=r["user_id"],
                kind=str(r["kind"]),
                tool=str(r["tool"]),
                model=r["model"],
                sources=_json_list(r["sources"]),
            )
            for r in rows
        ]


def _json_list(value: object) -> list[dict[str, Any]]:
    data = json.loads(value) if isinstance(value, str) else value
    return [dict(x) for x in data] if isinstance(data, list) else []
