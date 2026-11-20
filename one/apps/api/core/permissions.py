"""Rôles et permissions : par rôle (opération du contrat) et par attribut (portée).

- Par rôle : ``OPERATION_ROLES`` associe chaque ``operationId`` de specs/openapi.yaml à ses
  ``x-roles``. ``test_permissions.py`` échoue si la matrice diverge du contrat.
- Phase 3 (CR-P3-01) : ``assureur`` lit des agrégats k-anonymes de son organisation ;
  ``admin_plateforme`` accueille des organisations et n'a aucun accès métier.
- Par attribut : un rôle ``clinique`` est limité à ses établissements (``provider_id``), un
  rôle ``employeur`` à son groupe (``employer_id``), un rôle ``adherent`` (Phase 1, CR-P1-01) à
  SON contrat (``member_id``). Hors périmètre = introuvable (NOT-01).
- Secret médical (R6) : ``readMedicalReason`` n'est ouvert qu'au médecin-conseil ; tout autre
  rôle, admin compris, reçoit SEC-01.

Usage par les autres lots : ``Depends(require_operation("getClaim"))`` dans la route, puis
``authorize(ctx.principal, "getClaim", ResourceScope(provider_id=claim.provider_id))`` ou
``ctx.access.provider_ids`` pour filtrer une liste.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Final
from uuid import UUID

from api.core.errors import MedicalSecretError, NotFoundError, RoleForbiddenError


class Role(StrEnum):
    GESTIONNAIRE = "gestionnaire"
    MEDECIN_CONSEIL = "medecin_conseil"
    CLINIQUE = "clinique"
    EMPLOYEUR = "employeur"
    ADMIN = "admin"
    ADHERENT = "adherent"
    # Phase 3 (CR-P3-01) : lecture d'agrégats k-anonymes, et accueil d'organisations.
    ASSUREUR = "assureur"
    ADMIN_PLATEFORME = "admin_plateforme"


@dataclass(frozen=True, slots=True)
class RoleGrant:
    """Rôle attribué, avec son attribut de portée (contrainte CHECK de ``user_roles``)."""

    role: Role
    provider_id: UUID | None = None
    employer_id: UUID | None = None
    member_id: UUID | None = None

    def __post_init__(self) -> None:
        if (self.role is Role.CLINIQUE) != (self.provider_id is not None):
            msg = "portée invalide : provider_id est requis pour le rôle clinique, et seulement lui"
            raise ValueError(msg)
        if (self.role is Role.EMPLOYEUR) != (self.employer_id is not None):
            msg = (
                "portée invalide : employer_id est requis pour le rôle employeur, et seulement lui"
            )
            raise ValueError(msg)
        if (self.role is Role.ADHERENT) != (self.member_id is not None):
            msg = "portée invalide : member_id est requis pour le rôle adherent, et seulement lui"
            raise ValueError(msg)

    @property
    def unrestricted(self) -> bool:
        return self.provider_id is None and self.employer_id is None and self.member_id is None

    def sort_key(self) -> tuple[str, str, str, str]:
        return (
            self.role.value,
            str(self.provider_id or ""),
            str(self.employer_id or ""),
            str(self.member_id or ""),
        )


@dataclass(frozen=True, slots=True)
class Principal:
    """Utilisateur authentifié, dans l'organisation de son jeton."""

    user_id: UUID
    organization_id: UUID
    grants: tuple[RoleGrant, ...]

    @property
    def roles(self) -> frozenset[Role]:
        return frozenset(g.role for g in self.grants)


@dataclass(frozen=True, slots=True)
class ResourceScope:
    """Attributs de la ressource visée, comparés à la portée des rôles restreints."""

    provider_id: UUID | None = None
    employer_id: UUID | None = None
    member_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class AccessScope:
    """Ce que l'utilisateur peut atteindre pour une opération donnée."""

    roles: frozenset[Role]
    unrestricted: bool
    provider_ids: frozenset[UUID] = field(default_factory=frozenset)
    employer_ids: frozenset[UUID] = field(default_factory=frozenset)
    member_ids: frozenset[UUID] = field(default_factory=frozenset)

    def allows(self, resource: ResourceScope) -> bool:
        if self.unrestricted:
            return True
        return (
            (resource.provider_id is not None and resource.provider_id in self.provider_ids)
            or (resource.employer_id is not None and resource.employer_id in self.employer_ids)
            or (resource.member_id is not None and resource.member_id in self.member_ids)
        )


G, M, C, E, A = Role.GESTIONNAIRE, Role.MEDECIN_CONSEIL, Role.CLINIQUE, Role.EMPLOYEUR, Role.ADMIN
AD = Role.ADHERENT
AS, AP = Role.ASSUREUR, Role.ADMIN_PLATEFORME

# Recopie des ``x-roles`` de specs/openapi.yaml (contrat L0), vérifiée par test.
OPERATION_ROLES: Final[Mapping[str, frozenset[Role]]] = MappingProxyType(
    {
        # L1 noyau
        "getCurrentUser": frozenset({G, M, C, E, A, AD, AS, AP}),
        "getCurrentOrganization": frozenset({G, M, C, E, A, AD, AS, AP}),
        "listUsers": frozenset({A}),
        "createUser": frozenset({A}),
        "replaceUserRoles": frozenset({A}),
        "listAuditEvents": frozenset({A}),
        # L2 produits et règles
        "listPlans": frozenset({G, A}),
        "createPlan": frozenset({A}),
        "getPlan": frozenset({G, A}),
        "createPlanVersion": frozenset({G, A}),
        "getPlanVersion": frozenset({G, A}),
        "publishPlanVersion": frozenset({A}),
        "listProviders": frozenset({G, M, A}),
        "createProvider": frozenset({G, A}),
        "getProvider": frozenset({G, M, A}),
        "createProviderConvention": frozenset({G, A}),
        "listTariffs": frozenset({G, M, C, A}),
        "listActs": frozenset({G, M, A}),
        "createAct": frozenset({G, A}),
        "createTariffItem": frozenset({G, A}),
        "listRules": frozenset({G, M, A}),
        "listRuleVersions": frozenset({G, M, A}),
        "createRuleVersion": frozenset({A}),
        "publishRuleVersion": frozenset({A}),
        "evaluateRules": frozenset({G, M, A}),
        # L3 grand livre
        "listLedgerAccounts": frozenset({G, A}),
        "listLedgerEntries": frozenset({G, A}),
        "getLedgerEntry": frozenset({G, A}),
        "reverseLedgerEntry": frozenset({G, A}),
        "getLedgerBalance": frozenset({G, A}),
        # L4 adhérents et cotisations
        "listMembers": frozenset({G, A}),
        "createMember": frozenset({G, A}),
        "getMember": frozenset({G, A}),
        "addDependent": frozenset({G, A}),
        "getMemberEntitlements": frozenset({G, M, A}),
        "issueCard": frozenset({G, A}),
        "changeMemberStatus": frozenset({G, A}),
        "listMemberContributions": frozenset({G, A}),
        "sendReminder": frozenset({G, A}),
        "createPaymentLink": frozenset({G, A}),
        # L5 comptoir et prises en charge
        "startIdentification": frozenset({C}),
        "confirmPhoto": frozenset({C}),
        "sendIdentificationCode": frozenset({C}),
        "verifyIdentificationCode": frozenset({C}),
        "getOfflinePolicy": frozenset({C}),
        "registerCounterDevice": frozenset({C}),
        "syncOfflineAuthorizations": frozenset({C}),
        "listClaims": frozenset({G, M, C, A}),
        "createClaim": frozenset({C}),
        "getClaim": frozenset({G, M, C, A}),
        "decideClaim": frozenset({M}),
        "submitClaimDocuments": frozenset({C}),
        "readMedicalReason": frozenset({M}),
        "getWorkQueue": frozenset({G, M, A}),
        # L8 JOE
        "askJoe": frozenset({G, M, A}),
        "draftClaimDecision": frozenset({M}),
        "draftMessage": frozenset({G, A}),
        "search": frozenset({G, M, C, A}),
        "listAiActions": frozenset({A}),
        # P1 espace adhérent et diaspora (CR-P1-01) : l'adhérent, sur SON contrat seulement
        "getMyCard": frozenset({AD}),
        "listMyBeneficiaries": frozenset({AD}),
        "listMyClaims": frozenset({AD}),
        "getMyClaimTracking": frozenset({AD}),
        "listMyContributions": frozenset({AD}),
        "createMyPaymentLink": frozenset({AD}),
        # P2 mesure produit (CR-P2-01) : chacun mesure ses écrans ; agrégats à la gestion
        "recordProductEvent": frozenset({G, M, C, E, A, AD, AS, AP}),
        "getProductMetrics": frozenset({G, A}),
        # P3 marque blanche (CR-P3-01) : écriture par l'admin d'organisation, lecture publique
        "getBrandingSettings": frozenset({A}),
        "updateBrandingSettings": frozenset({A}),
        "verifyBrandingDomain": frozenset({A}),  # CR-P3-02 : preuve de propriété du domaine
        # P3 espace assureur : agrégats k-anonymes, lecture seule
        "getInsurerPortfolio": frozenset({AS, A}),
        "exportInsurerPortfolio": frozenset({AS, A}),
        # P3 espace employeur : son groupe seulement (attribut employer_id)
        "getEmployerConsumption": frozenset({E}),
        "listEmployerContracts": frozenset({E}),
        # P3 plateforme : accueil d'organisation par copie de gabarit
        "createOrganization": frozenset({AP}),
        "listConfigurationTemplates": frozenset({AP}),
        "createConfigurationTemplate": frozenset({AP}),
    }
)

# Opérations sans utilisateur (lien de paiement public, webhook signé) : hors matrice.
UNAUTHENTICATED_OPERATIONS: Final = frozenset(
    {"getPublicPaymentLink", "startCheckout", "receivePaymentWebhook", "getOrganizationBranding"}
)
# Jamais attribué par l'API (createUser, replaceUserRoles) : posé par l'exploitation, dans une
# organisation « plateforme » seulement (garde de la base, migration 0004).
NON_GRANTABLE_ROLES: Final = frozenset({Role.ADMIN_PLATEFORME})

MEDICAL_REASON_OPERATION: Final = "readMedicalReason"


def access_scope(principal: Principal, operation: str) -> AccessScope:
    """Portée de l'utilisateur pour une opération ; lève AUTH-02 (ou SEC-01) sinon."""
    try:
        allowed = OPERATION_ROLES[operation]
    except KeyError:
        msg = f"opération inconnue du contrat : {operation}"
        raise LookupError(msg) from None
    grants = [g for g in principal.grants if g.role in allowed]
    if not grants:
        if operation == MEDICAL_REASON_OPERATION:
            raise MedicalSecretError
        raise RoleForbiddenError
    return AccessScope(
        roles=frozenset(g.role for g in grants),
        unrestricted=any(g.unrestricted for g in grants),
        provider_ids=frozenset(g.provider_id for g in grants if g.provider_id is not None),
        employer_ids=frozenset(g.employer_id for g in grants if g.employer_id is not None),
        member_ids=frozenset(g.member_id for g in grants if g.member_id is not None),
    )


def authorize(
    principal: Principal, operation: str, resource: ResourceScope | None = None
) -> AccessScope:
    """Contrôle par rôle puis par attribut ; hors périmètre = NOT-01 (on ne dit pas pourquoi)."""
    scope = access_scope(principal, operation)
    if resource is not None and not scope.allows(resource):
        raise NotFoundError
    return scope
