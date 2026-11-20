"""Accueil d'organisation par l'administrateur de plateforme (P3, CR-P3-01).

``createConfigurationTemplate`` : instantané, à la date du jour, de la configuration EN VIGUEUR
de l'organisation « plateforme » (plan de comptes, règles, produits et garanties, actes et
barème), stocké comme nouvelle version figée d'un gabarit.

``createOrganization``, en UNE transaction (tout ou rien) :
1. gabarit lu dans l'organisation « plateforme » (même pays, sinon ORG-02) ;
2. organisation créée par la fonction SECURITY DEFINER du contrat, qui revérifie
   l'administrateur de plateforme (MCP01 → AUTH-02 ; MCP02 → ORG-01) ; statut `integration` ;
3. audit `organization.created` dans l'organisation « plateforme » ;
4. bascule de la transaction dans l'organisation accueillie (``app.organization_id``) : premier
   gestionnaire (rôles `gestionnaire` et `admin`), copie du gabarit en NOUVELLES lignes
   (règles et produits en version 1 `brouillon`), audit `organization.onboarded` ;
5. retour dans l'organisation « plateforme ». Rien n'est partagé : la RLS n'admet que des lignes
   de l'organisation positionnée, et chaque ligne copiée reçoit un nouvel identifiant.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Final
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError

from api.core.clock import ensure_utc
from api.core.context import RequestContext
from api.core.errors import FieldError, NotFoundError, RoleForbiddenError, ValidationFailedError
from api.core.jsonlog import LOGGER_NAME, log_event
from api.core.repositories import (
    AuditEntry,
    AuditRepository,
    OrganizationRepository,
    UserRepository,
)
from api.core.services import AuditIntent, AuditService, organization_out, user_out
from api.partners.errors import OrganizationSlugTakenError, TemplateUnavailableError
from api.partners.period import local_today
from api.partners.repository import (
    NewOrganization,
    NewTemplate,
    PlatformRepository,
    TemplateRow,
)
from api.partners.schemas import (
    ConfigurationTemplate,
    ConfigurationTemplateList,
    CreateConfigurationTemplateRequest,
    CreateOrganizationRequest,
    OrganizationOnboarding,
    TemplateContents,
    TemplatePayload,
    TemplateVersionRef,
)
from api.partners.service import PartnersRuntime

logger = logging.getLogger(f"{LOGGER_NAME}.partners.onboarding")

TIMEZONES: Final = {"CI": "Africa/Abidjan", "SN": "Africa/Dakar"}
FIRST_MANAGER_ROLES: Final = ("gestionnaire", "admin")
PLATFORM_REFUSED: Final = "MCP01"
SLUG_TAKEN: Final = "MCP02"
TEMPLATE_CREATED: Final = "configuration_template.created"
ORGANIZATION_CREATED: Final = "organization.created"
ORGANIZATION_ONBOARDED: Final = "organization.onboarded"


def _payload(row: TemplateRow) -> TemplatePayload:
    try:
        return TemplatePayload.model_validate_json(row.payload)
    except ValidationError:
        raise TemplateUnavailableError from None


def _template_out(row: TemplateRow) -> ConfigurationTemplate:
    return ConfigurationTemplate.model_validate(
        {
            "id": row.id,
            "code": row.code,
            "version": row.version,
            "country_code": row.country_code,  # contrôlé par le modèle (CI, SN)
            "label": row.label,
            "created_at": row.created_at,
            "contents": _payload(row).contents(),
        }
    )


def _sqlstate(exc: DBAPIError) -> str | None:
    state = getattr(exc.orig, "sqlstate", None)
    return state if isinstance(state, str) else None


@dataclass(frozen=True, slots=True)
class PlatformService:
    ctx: RequestContext
    runtime: PartnersRuntime

    @property
    def platform(self) -> UUID:
        return self.ctx.principal.organization_id

    @property
    def repo(self) -> PlatformRepository:
        return PlatformRepository(self.ctx.session)

    async def _platform_today(self) -> tuple[str, date]:
        organization = await OrganizationRepository(self.ctx.session).get(self.platform)
        if organization is None:
            raise NotFoundError
        return organization.timezone, local_today(
            ensure_utc(self.runtime.clock.now()), organization.timezone
        )

    async def list_templates(self) -> ConfigurationTemplateList:
        rows = await self.repo.templates(self.platform)
        return ConfigurationTemplateList(items=[_template_out(r) for r in rows])

    async def create_template(
        self, body: CreateConfigurationTemplateRequest
    ) -> ConfigurationTemplate:
        _, today = await self._platform_today()
        repo = self.repo
        snapshot = await repo.snapshot(self.platform, today)
        payload = TemplatePayload.model_validate_json(snapshot)
        if not payload.plans or not payload.rules:
            raise ValidationFailedError(
                "Aucun produit ou aucune règle n'est en vigueur aujourd'hui.",
                "Publiez au moins un produit et ses règles avant de créer un gabarit.",
                errors=(FieldError("code", "Configuration en vigueur vide."),),
            )
        await repo.lock_template_code(self.platform, body.code)
        version = await repo.next_template_version(self.platform, body.code)
        row = await repo.insert_template(
            self.platform,
            NewTemplate(
                code=body.code,
                version=version,
                country_code=body.country_code,
                label=body.label,
                payload=snapshot,
                created_by=self.ctx.principal.user_id,
            ),
        )
        contents = payload.contents()
        await AuditService.for_session(self.ctx.session).record(
            self.ctx,
            AuditIntent(
                TEMPLATE_CREATED,
                "configuration_template",
                row.id,
                {"code": row.code, "version": row.version, "contents": contents.model_dump()},
            ),
        )
        return _template_out(row)

    async def create_organization(self, body: CreateOrganizationRequest) -> OrganizationOnboarding:
        repo = self.repo
        template = await repo.template(self.platform, body.template.code, body.template.version)
        if template is None or template.country_code != body.country_code:
            raise TemplateUnavailableError
        payload = _payload(template)
        timezone = TIMEZONES[body.country_code]
        try:
            created = await repo.create_organization(
                NewOrganization(
                    actor=self.ctx.principal.user_id,
                    slug=body.slug,
                    name=body.name,
                    country_code=body.country_code,
                    timezone=timezone,
                    capabilities=tuple(dict.fromkeys(body.capabilities)),
                    regulator=body.regulator,
                )
            )
        except DBAPIError as exc:
            state = _sqlstate(exc)
            if state == PLATFORM_REFUSED:
                raise RoleForbiddenError from exc
            if state == SLUG_TAKEN:
                raise OrganizationSlugTakenError from exc
            raise
        reference = {"code": template.code, "version": template.version}
        await AuditService.for_session(self.ctx.session).record(
            self.ctx,
            AuditIntent(
                ORGANIZATION_CREATED,
                "organization",
                created,
                {"slug": body.slug, "country_code": body.country_code, "template": reference},
            ),
        )
        today = local_today(ensure_utc(self.runtime.clock.now()), timezone)

        # --- Organisation accueillie : la transaction ne voit plus que ses lignes (RLS).
        await repo.enter_organization(created)
        manager_id = await repo.insert_first_manager(
            created,
            subject=body.first_manager.idp_subject,
            display_name=body.first_manager.display_name,
            email=body.first_manager.email,
            roles=FIRST_MANAGER_ROLES,
        )
        copied = await repo.copy_template(created, template.payload, today)
        contents = TemplateContents(
            ledger_accounts=copied["ledger_accounts"],
            rules=copied["rules"],
            plans=copied["plans"],
            coverages=copied["coverages"],
            acts=copied["acts"],
            tariff_items=copied["tariff_items"],
        )
        if contents != payload.contents():  # copie partielle : tout est annulé
            msg = "copie du gabarit incomplète"
            raise RuntimeError(msg)
        await AuditRepository(self.ctx.session).append(
            created,
            AuditEntry(
                action=ORGANIZATION_ONBOARDED,
                target_type="organization",
                target_id=created,
                actor_user_id=None,  # l'administrateur n'appartient pas à cette organisation
                actor_role="admin_plateforme",
                request_id=self.ctx.request_id,
                metadata={
                    "platform_organization_id": str(self.platform),
                    "template": {"code": template.code, "version": template.version},
                    "first_manager_user_id": str(manager_id),
                    "copied": dict(copied),
                },
            ),
        )
        organization = await OrganizationRepository(self.ctx.session).get(created)
        manager = await UserRepository(self.ctx.session).get(created, manager_id)
        # Retour dans l'organisation « plateforme » (une erreur plus haut annule tout).
        await repo.enter_organization(self.platform)
        if organization is None or manager is None:  # invisible après création : incohérence
            raise NotFoundError
        log_event(
            logger,
            logging.INFO,
            "partners.organization_onboarded",
            organization_id=self.platform,
            created_organization_id=created,
            template_code=template.code,
            template_version=template.version,
        )
        return OrganizationOnboarding(
            organization=organization_out(organization),
            first_manager=user_out(manager),
            template=TemplateVersionRef(code=template.code, version=template.version),
            copied=contents,
        )
