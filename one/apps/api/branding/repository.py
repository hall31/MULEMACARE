"""Dépôt de la marque blanche : seul endroit SQL du module.

Lecture et écriture pour UNE organisation (celle du jeton), filtrées par ``organization_id`` en
plus de la RLS forcée. La lecture publique passe par la fonction SECURITY DEFINER du contrat
``resolve_organization_branding`` (champs non sensibles seulement), sans organisation positionnée.

Domaine personnalisé (CR-P3-02, migration 0005) : un jeton de preuve propre au domaine déclaré
(``custom_domain_token``) et l'instant de la preuve (``custom_domain_verified_at``). Changer de
domaine efface la preuve et tire un nouveau jeton, ici (``upsert``) ET dans la base (déclencheur
``organization_branding_domain_reverify``). La lecture publique ne sert que les organisations
ACTIVES et, par domaine, que les domaines PROUVÉS.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DOMAIN_CONSTRAINT: Final = "organization_branding_custom_domain_key"


@dataclass(frozen=True, slots=True)
class BrandingRecord:
    display_name: str
    logo_kind: str | None
    logo_src: str | None
    theme: dict[str, dict[str, str]]
    custom_domain: str | None
    legal_notice: str | None
    privacy_notice: str | None
    updated_at: datetime | None
    custom_domain_token: str | None = None
    custom_domain_verified_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PublicBrandingRecord:
    slug: str
    name: str
    country_code: str
    currency: str
    branding: BrandingRecord | None


def _theme(value: object) -> dict[str, dict[str, str]]:
    raw = json.loads(value) if isinstance(value, str) else value
    if not isinstance(raw, dict):
        return {}
    return {
        str(theme): {str(k): str(v) for k, v in tokens.items()}
        for theme, tokens in raw.items()
        if isinstance(tokens, dict)
    }


def _record(row: Any) -> BrandingRecord:  # noqa: ANN401
    return BrandingRecord(
        display_name=str(row.display_name),
        logo_kind=row.logo_kind,
        logo_src=row.logo_src,
        theme=_theme(row.theme),
        custom_domain=row.custom_domain,
        legal_notice=row.legal_notice,
        privacy_notice=row.privacy_notice,
        updated_at=getattr(row, "updated_at", None),
        custom_domain_token=getattr(row, "custom_domain_token", None),
        custom_domain_verified_at=getattr(row, "custom_domain_verified_at", None),
    )


class BrandingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def organization_name(self, org: UUID) -> str | None:
        result = await self._session.execute(
            text("SELECT name FROM organizations WHERE id = :org"), {"org": org}
        )
        value = result.scalar_one_or_none()
        return None if value is None else str(value)

    async def get(self, org: UUID) -> BrandingRecord | None:
        result = await self._session.execute(
            text(
                "SELECT display_name, logo_kind, logo_src, theme, custom_domain, legal_notice, "
                "privacy_notice, updated_at, custom_domain_token, custom_domain_verified_at "
                "FROM organization_branding WHERE organization_id = :org"
            ),
            {"org": org},
        )
        row = result.first()
        return None if row is None else _record(row)

    async def upsert(
        self, org: UUID, record: BrandingRecord, *, updated_by: UUID, now: datetime
    ) -> None:
        await self._session.execute(
            text(
                "INSERT INTO organization_branding (organization_id, display_name, logo_kind, "
                "logo_src, theme, custom_domain, custom_domain_token, legal_notice, "
                "privacy_notice, updated_by, updated_at) VALUES (:org, :display_name, "
                ":logo_kind, :logo_src, CAST(:theme AS jsonb), :custom_domain, :token, "
                ":legal_notice, :privacy_notice, :updated_by, :now) "
                "ON CONFLICT (organization_id) DO UPDATE SET "
                "display_name = EXCLUDED.display_name, logo_kind = EXCLUDED.logo_kind, "
                "logo_src = EXCLUDED.logo_src, theme = EXCLUDED.theme, "
                # Même domaine : preuve et jeton conservés ; autre domaine : tout est à refaire.
                "custom_domain_token = CASE WHEN organization_branding.custom_domain "
                "IS NOT DISTINCT FROM EXCLUDED.custom_domain THEN coalesce("
                "organization_branding.custom_domain_token, EXCLUDED.custom_domain_token) "
                "ELSE EXCLUDED.custom_domain_token END, "
                "custom_domain_verified_at = CASE WHEN organization_branding.custom_domain "
                "IS NOT DISTINCT FROM EXCLUDED.custom_domain "
                "THEN organization_branding.custom_domain_verified_at END, "
                "custom_domain = EXCLUDED.custom_domain, legal_notice = EXCLUDED.legal_notice, "
                "privacy_notice = EXCLUDED.privacy_notice, updated_by = EXCLUDED.updated_by, "
                "updated_at = EXCLUDED.updated_at "
                "WHERE organization_branding.organization_id = :org"
            ),
            {
                "org": org,
                "display_name": record.display_name,
                "logo_kind": record.logo_kind,
                "logo_src": record.logo_src,
                "theme": json.dumps(record.theme, sort_keys=True),
                "custom_domain": record.custom_domain,
                "token": record.custom_domain_token,
                "legal_notice": record.legal_notice,
                "privacy_notice": record.privacy_notice,
                "updated_by": updated_by,
                "now": now,
            },
        )

    async def mark_domain_verified(
        self, org: UUID, *, domain: str, token: str, now: datetime
    ) -> bool:
        """Preuve enregistrée seulement si le domaine ET le jeton vérifiés sont encore ceux de
        l'organisation (un changement concurrent ne peut pas hériter de la preuve)."""
        result = await self._session.execute(
            text(
                "UPDATE organization_branding SET custom_domain_verified_at = :now "
                "WHERE organization_id = :org AND custom_domain = :domain "
                "AND custom_domain_token = :token RETURNING organization_id"
            ),
            {"org": org, "domain": domain, "token": token, "now": now},
        )
        return result.first() is not None

    async def resolve_public(
        self, slug: str | None, domain: str | None
    ) -> PublicBrandingRecord | None:
        result = await self._session.execute(
            text(
                "SELECT slug, name, country_code, currency, display_name, logo_kind, logo_src, "
                "theme, custom_domain, legal_notice, privacy_notice "
                "FROM resolve_organization_branding(:slug, :domain)"
            ),
            {"slug": slug, "domain": domain},
        )
        rows = result.all()
        if len(rows) != 1:  # inconnue (0) ; deux réponses (slug ET domaine) : refus prudent
            return None
        row = rows[0]
        branding = None if row.display_name is None else _record(row)
        return PublicBrandingRecord(
            slug=str(row.slug),
            name=str(row.name),
            country_code=str(row.country_code),
            currency=str(row.currency),
            branding=branding,
        )
