"""Journal de JOE : la SEULE écriture du module, dans ``ai_actions`` (table en ajout seul).

Chaque action (lecture d'outil, réponse, refus, préparation) y est inscrite avec ses sources,
dans la transaction de la requête, APRÈS la sortie du garde de lecture seule. La base vérifie
elle-même qu'une réponse ou une préparation cite au moins une source, et qu'aucun nom d'outil
ne contient ``approve``, ``reject``, ``pay`` ou ``decide`` (CHECK de ``specs/schema.sql``).
``input`` et ``output`` ne portent que des identifiants et du texte pseudonymisé (jetons).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

type ActionKind = Literal["lecture", "preparation", "reponse", "refus"]
type JsonScalar = str | int | bool | None


@dataclass(frozen=True, slots=True)
class SourceRef:
    """Enregistrement consulté (``Source`` du contrat)."""

    type: str
    id: UUID
    label: str

    def as_json(self) -> dict[str, str]:
        return {"type": self.type, "id": str(self.id), "label": self.label}


def unique_sources(sources: Sequence[SourceRef]) -> tuple[SourceRef, ...]:
    seen: dict[tuple[str, UUID], SourceRef] = {}
    for source in sources:
        seen.setdefault((source.type, source.id), source)
    return tuple(seen.values())


class AiActionJournal:
    def __init__(self, session: AsyncSession, organization_id: UUID, user_id: UUID) -> None:
        self._s = session
        self._org = organization_id
        self._user = user_id

    async def record(  # noqa: PLR0913 — colonnes de ai_actions
        self,
        *,
        kind: ActionKind,
        tool: str,
        sources: Sequence[SourceRef],
        model: str | None = None,
        input: Mapping[str, JsonScalar] | None = None,
        output: Mapping[str, JsonScalar] | None = None,
    ) -> UUID:
        result = await self._s.execute(
            text(
                "INSERT INTO ai_actions (organization_id, user_id, kind, tool, model, input, "
                "output, sources) VALUES (:org, :user, :kind, :tool, :model, "
                "CAST(:input AS jsonb), CAST(:output AS jsonb), CAST(:sources AS jsonb)) "
                "RETURNING id"
            ),
            {
                "org": self._org,
                "user": self._user,
                "kind": kind,
                "tool": tool,
                "model": model,
                "input": json.dumps(dict(input or {}), ensure_ascii=False),
                "output": json.dumps(dict(output or {}), ensure_ascii=False),
                "sources": json.dumps(
                    [s.as_json() for s in unique_sources(sources)], ensure_ascii=False
                ),
            },
        )
        return UUID(str(result.scalar_one()))
