"""Chemins des contrats du lot L0, partagés par les tests."""

from __future__ import annotations

from pathlib import Path

ONE_ROOT = Path(__file__).resolve().parents[3]
SPECS = ONE_ROOT / "specs"
SCHEMA_SQL = SPECS / "schema.sql"
DEMO_SEED_SQL = SPECS / "seeds" / "demo.sql"
OPENAPI_YAML = SPECS / "openapi.yaml"
EVENTS_MD = SPECS / "events.md"
TOKENS_CSS = SPECS / "design" / "mulemacare-tokens.css"
ALEMBIC_INI = ONE_ROOT / "alembic.ini"
