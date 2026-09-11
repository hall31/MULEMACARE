"""Audit log repository — insert-only immutable audit trail."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import AuditLog


class AuditRepository:
    """CRUD for AuditLog — write-only, no updates/deletes."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action: str,
        actor_id: str,
        actor_role: str,
        agent_proposal_id: str,
        old_status: str | None,
        new_status: str,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Create and persist an immutable audit log entry."""
        import uuid

        log_entry = AuditLog(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            agent_proposal_id=agent_proposal_id,
            old_status=old_status,
            new_status=new_status,
            reason=reason,
            metadata=metadata or {},
        )
        self.db.add(log_entry)
        await self.db.flush()  # Flush but don't commit — let caller handle transaction
        return log_entry

    async def get_trail(self, agent_proposal_id: str) -> list[AuditLog]:
        """Fetch full audit trail for a proposal, chronological order."""
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.agent_proposal_id == agent_proposal_id)
            .order_by(AuditLog.timestamp.asc())
        )
        return result.scalars().all()

    async def get_by_id(self, log_id: str) -> AuditLog | None:
        """Fetch single audit log by ID."""
        result = await self.db.execute(select(AuditLog).where(AuditLog.id == log_id))
        return result.scalar_one_or_none()
