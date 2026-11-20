"""Schémas de la marque blanche, conformes aux composants P3 de specs/openapi.yaml.

``UpdateBrandingRequest.theme`` est reçu comme un objet quelconque : la LISTE FERMÉE des jetons
est vérifiée par le service (``api.branding.palette``), pour répondre 422 BRD-02 avec le champ
fautif plutôt qu'un VAL-01 générique. Textes en texte brut : ni balise, ni caractère de contrôle.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from api.branding.logo import MAX_SRC_LENGTH

DOMAIN = r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
# Texte brut : ni balise, ni caractère de contrôle C0/C1, ni contrôle de direction ou de
# séparation (U+200B-U+200F, U+2028-U+202E, U+2060-U+2069, U+FEFF, U+FFF9-U+FFFB) qui
# retourneraient ou masqueraient le nom affiché. Au moins aussi strict que la contrainte de la
# base (``[:cntrl:]``) : un tel caractère donne 422, jamais 500 (CR-P3-02).
DISPLAY_NAME = (
    r"^[^<>\x00-\x1f\x7f-\x9f\u200b-\u200f\u2028-\u202e\u2060-\u2069\ufeff\ufff9-\ufffb]+$"
)
LEGAL_TEXT = r"^[^<>\x00-\x08\x0b\x0c\x0e-\x1f\x7f]*$"

type ThemeTokens = dict[str, dict[str, str]]
type DomainStatus = Literal["en_attente_de_verification", "verifie"]


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True)


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BrandLogo(_In):
    kind: Literal["url", "data_uri"]
    src: str = Field(min_length=1, max_length=MAX_SRC_LENGTH)


class UpdateBrandingRequest(_In):
    display_name: str = Field(min_length=1, max_length=80, pattern=DISPLAY_NAME)
    logo: BrandLogo | None = None
    theme: dict[str, Any] = Field(default_factory=dict)
    custom_domain: str | None = Field(default=None, max_length=253, pattern=DOMAIN)
    legal_notice: str | None = Field(default=None, max_length=4000, pattern=LEGAL_TEXT)
    privacy_notice: str | None = Field(default=None, max_length=4000, pattern=LEGAL_TEXT)


class BrandLogoOut(_Out):
    kind: Literal["url", "data_uri"]
    src: str


class DomainVerification(_Out):
    """Enregistrement DNS que l'organisation publie pour prouver la propriété du domaine."""

    record_type: Literal["TXT"]
    record_name: str
    record_value: str


class BrandingSettings(_Out):
    display_name: str
    logo: BrandLogoOut | None
    theme: ThemeTokens
    custom_domain: str | None
    legal_notice: str | None
    privacy_notice: str | None
    customized: bool
    updated_at: datetime | None
    # CR-P3-02 (ajouts) : le domaine n'est servi qu'une fois « verifie ».
    custom_domain_status: DomainStatus | None
    custom_domain_verification: DomainVerification | None


class OrganizationBranding(_Out):
    slug: str
    display_name: str
    country_code: Literal["CI", "SN"]
    currency: Literal["XOF"]
    logo: BrandLogoOut | None
    theme: ThemeTokens
    custom_domain: str | None
    legal_notice: str | None
    privacy_notice: str | None
