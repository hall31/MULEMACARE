"""Description SQLAlchemy (Core) des tables du noyau, conforme à specs/schema.sql.

Ces objets servent à écrire des requêtes typées ; ils ne créent rien (le schéma vient de la
migration 0001). ``test_tables.py`` vérifie qu'ils ont exactement les colonnes du contrat.
"""

from __future__ import annotations

from sqlalchemy import (
    ARRAY,
    CHAR,
    TIMESTAMP,
    Column,
    FetchedValue,
    ForeignKey,
    MetaData,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

organizations = Table(
    "organizations",
    metadata,
    Column("id", Uuid, primary_key=True, server_default=FetchedValue()),
    Column("slug", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("country_code", CHAR(2), nullable=False),
    Column("timezone", Text, nullable=False),
    Column("currency", CHAR(3), nullable=False),
    Column("capabilities", ARRAY(Text), nullable=False),
    Column("managed_by_organization_id", Uuid),
    Column("regulator", Text),
    Column("status", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
)

users = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True, server_default=FetchedValue()),
    Column("organization_id", Uuid, ForeignKey("organizations.id"), nullable=False),
    Column("idp_subject", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("email", Text),
    Column("status", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
)

user_roles = Table(
    "user_roles",
    metadata,
    Column("id", Uuid, primary_key=True, server_default=FetchedValue()),
    Column("organization_id", Uuid, nullable=False),
    Column("user_id", Uuid, nullable=False),
    Column("role", Text, nullable=False),
    Column("provider_id", Uuid),
    Column("employer_id", Uuid),
    Column("granted_by", Uuid),
    Column("granted_at", TIMESTAMP(timezone=True), nullable=False),
    Column("member_id", Uuid),  # migration 0002 (CR-P1-01)
)

audit_events = Table(
    "audit_events",
    metadata,
    Column("id", Uuid, primary_key=True, server_default=FetchedValue()),
    Column("organization_id", Uuid, nullable=False),
    Column("occurred_at", TIMESTAMP(timezone=True), nullable=False),
    Column("actor_user_id", Uuid),
    Column("actor_role", Text),
    Column("action", Text, nullable=False),
    Column("target_type", Text, nullable=False),
    Column("target_id", Uuid),
    Column("request_id", Text),
    Column("metadata", JSONB, nullable=False),
)

# Tables d'autres lots, lues seulement pour valider les attributs de portée d'un rôle.
providers = Table(
    "providers",
    metadata,
    Column("id", Uuid, primary_key=True, server_default=FetchedValue()),
    Column("organization_id", Uuid, nullable=False),
)

employers = Table(
    "employers",
    metadata,
    Column("id", Uuid, primary_key=True, server_default=FetchedValue()),
    Column("organization_id", Uuid, nullable=False),
)

members = Table(
    "members",
    metadata,
    Column("id", Uuid, primary_key=True, server_default=FetchedValue()),
    Column("organization_id", Uuid, nullable=False),
)
