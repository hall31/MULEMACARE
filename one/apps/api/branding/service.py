"""Service de la marque blanche (P3, CR-P3-01).

- ``update`` (admin d'organisation) : gardes dans l'ordre du contrat — liste fermée de jetons
  (BRD-02), contraste WCAG AA en clair et en sombre (BRD-01), logo non exécutable (BRD-03),
  domaine non réservé (BRD-05, CR-P3-02), domaine libre (BRD-04) — puis écriture et audit
  ``organization.branding_updated``. Un domaine nouveau reçoit un jeton de preuve et reste « en
  attente de vérification ».
- ``verify_domain`` (admin d'organisation, CR-P3-02) : preuve de propriété par le port DNS
  (``domains.DnsTxtResolver``) ; BRD-06 tant que l'enregistrement TXT manque ; audit
  ``organization.custom_domain_verified``.
- ``settings`` : réglages de l'organisation du jeton (valeurs par défaut si rien n'est réglé).
- ``public`` (sans jeton) : marque non sensible d'une organisation ACTIVE, par identifiant
  public OU par domaine PROUVÉ ; inconnue et non active donnent le même 404.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Final

from sqlalchemy.exc import IntegrityError

from api.branding.domains import (
    DnsTxtResolver,
    NoDnsTxtResolver,
    ReservedDomains,
    new_token,
    proves_ownership,
    verification_record,
)
from api.branding.errors import (
    BrandContrastError,
    BrandDomainReservedError,
    BrandDomainTakenError,
    BrandDomainUnverifiedError,
    BrandLogoError,
    BrandTokenError,
)
from api.branding.logo import LogoRejectedError, validate_logo
from api.branding.palette import check_theme_overrides
from api.branding.repository import DOMAIN_CONSTRAINT, BrandingRecord, BrandingRepository
from api.branding.schemas import (
    BrandingSettings,
    BrandLogoOut,
    DomainVerification,
    OrganizationBranding,
    UpdateBrandingRequest,
)
from api.core.clock import Clock, ensure_utc
from api.core.context import RequestContext
from api.core.database import Database
from api.core.errors import FieldError, NotFoundError, ValidationFailedError
from api.core.jsonlog import LOGGER_NAME, log_event
from api.core.services import AuditIntent, AuditService
from api.integrations.egress import EgressAllowlist

logger = logging.getLogger(f"{LOGGER_NAME}.branding")

BRANDING_UPDATED: Final = "organization.branding_updated"
DOMAIN_VERIFIED: Final = "organization.custom_domain_verified"
_UNIQUE_VIOLATION: Final = "23505"


def _no_logo_host() -> EgressAllowlist:
    return EgressAllowlist(frozenset())


@dataclass(frozen=True, slots=True)
class BrandingPorts:
    """Dépendances de la marque blanche fournies au montage (``AppModules.branding``).

    - ``dns`` : port de preuve DNS ; défaut sans résolution (domaine jamais prouvé, donc jamais
      servi : le domaine personnalisé reste désactivé, le slug reste utilisable).
    - ``logo_hosts`` : liste DÉDIÉE des hôtes:ports admis pour un logo https ; vide par défaut.
      Jamais la liste blanche d'egress (HealthOS, bases : CR-P3-02).
    - ``reserved_hosts`` : hôtes de l'instance à réserver en plus de ceux déduits au montage.
    """

    dns: DnsTxtResolver = field(default_factory=NoDnsTxtResolver)
    logo_hosts: EgressAllowlist = field(default_factory=_no_logo_host)
    reserved_hosts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BrandingRuntime:
    """``logo_hosts`` : hôtes admis pour un logo https (liste dédiée) ; ``reserved`` : domaines
    jamais déclarables ; ``dns`` : port de preuve de propriété."""

    logo_hosts: EgressAllowlist
    reserved: ReservedDomains
    dns: DnsTxtResolver
    clock: Clock


def _logo(record: BrandingRecord | None) -> BrandLogoOut | None:
    if record is None or record.logo_kind is None or record.logo_src is None:
        return None
    return BrandLogoOut.model_validate({"kind": record.logo_kind, "src": record.logo_src})


def _normalized_theme(theme: Mapping[str, object]) -> dict[str, dict[str, str]]:
    normalized: dict[str, dict[str, str]] = {}
    for name, tokens in theme.items():
        if isinstance(tokens, Mapping) and tokens:
            normalized[name] = {str(k): str(v).lower() for k, v in sorted(tokens.items())}
    return normalized


def _domain_state(
    record: BrandingRecord,
) -> tuple[str | None, DomainVerification | None]:
    if record.custom_domain is None:
        return None, None
    status = "verifie" if record.custom_domain_verified_at is not None else None
    proof = (
        None
        if record.custom_domain_token is None
        else DomainVerification.model_validate(
            asdict(verification_record(record.custom_domain, record.custom_domain_token))
        )
    )
    return status or "en_attente_de_verification", proof


def _settings(record: BrandingRecord | None, default_name: str) -> BrandingSettings:
    if record is None:
        return BrandingSettings(
            display_name=default_name,
            logo=None,
            theme={},
            custom_domain=None,
            legal_notice=None,
            privacy_notice=None,
            customized=False,
            updated_at=None,
            custom_domain_status=None,
            custom_domain_verification=None,
        )
    status, proof = _domain_state(record)
    return BrandingSettings.model_validate(
        {
            "display_name": record.display_name,
            "logo": _logo(record),
            "theme": record.theme,
            "custom_domain": record.custom_domain,
            "legal_notice": record.legal_notice,
            "privacy_notice": record.privacy_notice,
            "customized": True,
            "updated_at": record.updated_at,
            "custom_domain_status": status,
            "custom_domain_verification": proof,
        }
    )


@dataclass(frozen=True, slots=True)
class BrandingService:
    runtime: BrandingRuntime

    def _checked_theme(self, theme: Mapping[str, object]) -> dict[str, dict[str, str]]:
        problems = check_theme_overrides(theme)
        tokens = [p for p in problems if p.kind == "jeton"]
        if tokens:
            raise BrandTokenError(errors=tuple(FieldError(p.field, p.message) for p in tokens))
        if problems:
            raise BrandContrastError(errors=tuple(FieldError(p.field, p.message) for p in problems))
        return _normalized_theme(theme)

    def _checked_logo(self, body: UpdateBrandingRequest) -> tuple[str | None, str | None]:
        if body.logo is None:
            return None, None
        try:
            src = validate_logo(body.logo.kind, body.logo.src, self.runtime.logo_hosts)
        except LogoRejectedError as problem:
            raise BrandLogoError(errors=(FieldError(problem.field, problem.reason),)) from None
        return body.logo.kind, src

    def _checked_domain(self, domain: str | None) -> str | None:
        if domain is not None and self.runtime.reserved.reserves(domain):
            raise BrandDomainReservedError(
                errors=(FieldError("custom_domain", "Domaine réservé : déclarez le vôtre."),)
            )
        return domain

    async def settings(self, ctx: RequestContext) -> BrandingSettings:
        repo = BrandingRepository(ctx.session)
        org = ctx.principal.organization_id
        name = await repo.organization_name(org)
        if name is None:
            raise NotFoundError
        return _settings(await repo.get(org), name)

    async def update(self, ctx: RequestContext, body: UpdateBrandingRequest) -> BrandingSettings:
        theme = self._checked_theme(body.theme)
        logo_kind, logo_src = self._checked_logo(body)
        domain = self._checked_domain(body.custom_domain)
        org = ctx.principal.organization_id
        record = BrandingRecord(
            display_name=body.display_name.strip(),
            logo_kind=logo_kind,
            logo_src=logo_src,
            theme=theme,
            custom_domain=domain,
            legal_notice=body.legal_notice,
            privacy_notice=body.privacy_notice,
            updated_at=None,
            # Nouveau jeton à chaque écriture ; le dépôt garde l'ancien si le domaine ne change
            # pas (preuve conservée), sinon la preuve est à refaire.
            custom_domain_token=None if domain is None else new_token(),
        )
        repo = BrandingRepository(ctx.session)
        try:
            async with ctx.session.begin_nested():
                await repo.upsert(
                    org,
                    record,
                    updated_by=ctx.principal.user_id,
                    now=ensure_utc(self.runtime.clock.now()),
                )
        except IntegrityError as exc:
            constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            state = getattr(exc.orig, "sqlstate", None)
            if state == _UNIQUE_VIOLATION and constraint == DOMAIN_CONSTRAINT:
                raise BrandDomainTakenError(
                    errors=(FieldError("custom_domain", "Domaine déjà déclaré."),)
                ) from exc
            raise
        await AuditService.for_session(ctx.session).record(
            ctx,
            AuditIntent(
                BRANDING_UPDATED,
                "organization",
                org,
                {
                    "tokens": sorted(f"{t}.{k}" for t, tokens in theme.items() for k in tokens),
                    "logo_kind": logo_kind,
                    "custom_domain_set": body.custom_domain is not None,
                },
            ),
        )
        log_event(logger, logging.INFO, "branding.updated", organization_id=org)
        return await self.settings(ctx)

    async def verify_domain(self, ctx: RequestContext) -> BrandingSettings:
        """Preuve de propriété du domaine déclaré, par le port DNS (aucun appel réseau ici)."""
        org = ctx.principal.organization_id
        repo = BrandingRepository(ctx.session)
        record = await repo.get(org)
        domain = None if record is None else record.custom_domain
        token = None if record is None else record.custom_domain_token
        if record is None or domain is None or token is None:
            raise BrandDomainUnverifiedError(
                errors=(FieldError("custom_domain", "Aucun domaine à vérifier : déclarez-le."),)
            )
        self._checked_domain(domain)  # la liste réservée a pu s'étendre depuis la déclaration
        if record.custom_domain_verified_at is None:
            proof = verification_record(domain, token)
            if not await proves_ownership(self.runtime.dns, domain, token):
                raise BrandDomainUnverifiedError(
                    errors=(
                        FieldError(
                            "custom_domain",
                            f"Enregistrement TXT « {proof.record_name} » introuvable "
                            "ou sans la valeur attendue.",
                        ),
                    )
                )
            now = ensure_utc(self.runtime.clock.now())
            if not await repo.mark_domain_verified(org, domain=domain, token=token, now=now):
                raise BrandDomainUnverifiedError  # domaine changé pendant la vérification
            await AuditService.for_session(ctx.session).record(
                ctx, AuditIntent(DOMAIN_VERIFIED, "organization", org, {})
            )
            log_event(logger, logging.INFO, "branding.domain_verified", organization_id=org)
        return await self.settings(ctx)

    async def public(
        self, database: Database, slug: str | None, domain: str | None
    ) -> OrganizationBranding:
        if (slug is None) == (domain is None):
            raise ValidationFailedError(
                "Indiquez l'identifiant de l'organisation OU son domaine.",
                "Passez soit « slug », soit « domain », pas les deux.",
                errors=(FieldError("slug", "Exactement un de slug ou domain."),),
            )
        async with database.transaction(None) as session:
            found = await BrandingRepository(session).resolve_public(
                slug, domain.lower() if domain else None
            )
        if found is None:
            raise NotFoundError
        branding = found.branding
        return OrganizationBranding.model_validate(
            {
                "slug": found.slug,
                "display_name": branding.display_name if branding else found.name,
                "country_code": found.country_code,  # contrôlé par le modèle (CI, SN)
                "currency": found.currency,  # contrôlé par le modèle (XOF)
                "logo": _logo(branding),
                "theme": branding.theme if branding else {},
                # Domaine servi seulement s'il est prouvé (la fonction du contrat le filtre).
                "custom_domain": branding.custom_domain if branding else None,
                "legal_notice": branding.legal_notice if branding else None,
                "privacy_notice": branding.privacy_notice if branding else None,
            }
        )
