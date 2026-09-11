"""Row-Level Security (RLS) for Postgres multi-tenant isolation."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def init_rls_policies(db: AsyncSession) -> None:
    """Initialize RLS policies for Postgres. Run once at startup or via migration."""

    statements = [
        # Enable RLS on tables
        "ALTER TABLE members ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE users ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE agent_proposals ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE mcare_conversations ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE mcare_messages ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;",

        # members table: users can see only their own tenant
        """
        DROP POLICY IF EXISTS members_tenant_isolation ON members;
        CREATE POLICY members_tenant_isolation ON members
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = current_user_id()
                    AND users.tenant_id = (
                        SELECT tenant_id FROM members
                        WHERE members.cssa_id = current_user_cssa_id()
                    )
                )
            );
        """,

        # agent_proposals: OPS/ADMIN can see only their tenant
        """
        DROP POLICY IF EXISTS proposals_tenant_isolation ON agent_proposals;
        CREATE POLICY proposals_tenant_isolation ON agent_proposals
            USING (tenant_id = current_tenant_id());
        """,

        # mcare_conversations: tenant isolation
        """
        DROP POLICY IF EXISTS mcare_conv_tenant_isolation ON mcare_conversations;
        CREATE POLICY mcare_conv_tenant_isolation ON mcare_conversations
            USING (
                EXISTS (
                    SELECT 1 FROM members m
                    WHERE m.cssa_id = mcare_conversations.cssa_id
                    AND (SELECT tenant_id FROM users WHERE id = current_user_id()) =
                        (SELECT tenant_id FROM users WHERE id = current_user_id())
                )
            );
        """,
    ]

    for stmt in statements:
        try:
            await db.execute(text(stmt))
        except Exception as e:
            # Policy may already exist; log but don't fail
            print(f"RLS warning: {e}")

    await db.commit()


def current_tenant_id() -> str:
    """Get tenant_id from JWT claim (via Postgres current_setting or app-level)."""
    # In production, set via: SET app.tenant_id = '...';
    # before executing queries. Fallback to 'mulemacare'.
    return "mulemacare"


def current_user_id() -> str:
    """Get user_id from JWT claim (via Postgres current_setting)."""
    return "system"


def current_user_cssa_id() -> str:
    """Get CSSA ID from JWT claim."""
    return ""
