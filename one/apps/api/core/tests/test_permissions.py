"""Permissions par rôle (matrice du contrat) et par attribut (clinique, employeur)."""

from __future__ import annotations

import re
from uuid import uuid4

import pytest

from api.core.errors import MedicalSecretError, NotFoundError, RoleForbiddenError
from api.core.permissions import (
    MEDICAL_REASON_OPERATION,
    OPERATION_ROLES,
    UNAUTHENTICATED_OPERATIONS,
    Principal,
    ResourceScope,
    Role,
    RoleGrant,
    access_scope,
    authorize,
)
from api.tests.paths import OPENAPI_YAML

_OPERATION = re.compile(
    r"operationId: (\w+)\n(?:.*\n)*?\s+x-roles: \[([^\]]*)\]", flags=re.MULTILINE
)
CONTRACT: dict[str, frozenset[str]] = {
    op: frozenset(r.strip() for r in roles.split(","))
    for op, roles in _OPERATION.findall(OPENAPI_YAML.read_text(encoding="utf-8"))
}
NON_USER_ROLES = frozenset({"public", "canal_de_paiement"})


def _principal(*grants: RoleGrant) -> Principal:
    return Principal(user_id=uuid4(), organization_id=uuid4(), grants=grants)


def _grant(role: Role) -> RoleGrant:
    """Attribution valide d'un rôle, avec l'attribut de portée qu'il exige."""
    return RoleGrant(
        role,
        provider_id=uuid4() if role is Role.CLINIQUE else None,
        employer_id=uuid4() if role is Role.EMPLOYEUR else None,
        member_id=uuid4() if role is Role.ADHERENT else None,
    )


def test_le_contrat_declare_x_roles_pour_chaque_operation() -> None:
    operations = re.findall(r"operationId: (\w+)", OPENAPI_YAML.read_text(encoding="utf-8"))
    assert len(operations) == len(CONTRACT) >= 60


def test_matrice_identique_aux_x_roles_du_contrat() -> None:
    """Toute divergence entre le code et ``x-roles`` d'openapi.yaml fait échouer ce test."""
    expected_user_ops = {op: r for op, r in CONTRACT.items() if not r & NON_USER_ROLES}
    expected_public = {op for op, r in CONTRACT.items() if r & NON_USER_ROLES}
    actual = {op: frozenset(role.value for role in roles) for op, roles in OPERATION_ROLES.items()}
    assert actual == expected_user_ops
    assert expected_public == UNAUTHENTICATED_OPERATIONS


def test_les_roles_sont_ceux_du_contrat() -> None:
    assert {r.value for r in Role} == {
        "gestionnaire",
        "medecin_conseil",
        "clinique",
        "employeur",
        "admin",
        "adherent",
        "assureur",
        "admin_plateforme",
    }


@pytest.mark.parametrize(("operation", "roles"), sorted(OPERATION_ROLES.items()))
def test_chaque_role_hors_matrice_est_refuse(operation: str, roles: frozenset[Role]) -> None:
    for role in Role:
        principal = _principal(_grant(role))
        if role in roles:
            assert role in access_scope(principal, operation).roles
        else:
            with pytest.raises((RoleForbiddenError, MedicalSecretError)):
                access_scope(principal, operation)


def test_sans_role_tout_est_refuse() -> None:
    for operation in OPERATION_ROLES:
        with pytest.raises((RoleForbiddenError, MedicalSecretError)):
            access_scope(_principal(), operation)


@pytest.mark.parametrize("role", [r for r in Role if r is not Role.MEDECIN_CONSEIL])
def test_motif_medical_refuse_avec_sec_01(role: Role) -> None:
    with pytest.raises(MedicalSecretError) as exc:
        access_scope(_principal(_grant(role)), MEDICAL_REASON_OPERATION)
    assert exc.value.code == "SEC-01"
    assert exc.value.status_code == 403


def test_motif_medical_refuse_meme_a_un_gestionnaire_admin() -> None:
    with pytest.raises(MedicalSecretError):
        access_scope(
            _principal(RoleGrant(Role.GESTIONNAIRE), RoleGrant(Role.ADMIN)),
            MEDICAL_REASON_OPERATION,
        )


def test_operation_inconnue_refusee_a_la_declaration() -> None:
    with pytest.raises(LookupError):
        access_scope(_principal(RoleGrant(Role.ADMIN)), "operationQuiNExistePas")


def test_clinique_ne_voit_que_ses_dossiers() -> None:
    mine, other = uuid4(), uuid4()
    clinic = _principal(RoleGrant(Role.CLINIQUE, provider_id=mine))
    scope = authorize(clinic, "getClaim", ResourceScope(provider_id=mine))
    assert not scope.unrestricted
    assert scope.provider_ids == frozenset({mine})
    with pytest.raises(NotFoundError) as exc:
        authorize(clinic, "getClaim", ResourceScope(provider_id=other))
    assert exc.value.code == "NOT-01"
    with pytest.raises(NotFoundError):
        authorize(clinic, "getClaim", ResourceScope())


def test_clinique_a_plusieurs_etablissements() -> None:
    p1, p2 = uuid4(), uuid4()
    clinic = _principal(
        RoleGrant(Role.CLINIQUE, provider_id=p1), RoleGrant(Role.CLINIQUE, provider_id=p2)
    )
    assert authorize(clinic, "listClaims").provider_ids == frozenset({p1, p2})
    authorize(clinic, "getClaim", ResourceScope(provider_id=p2))


def test_gestionnaire_sans_restriction_d_attribut() -> None:
    scope = authorize(
        _principal(RoleGrant(Role.GESTIONNAIRE)), "getClaim", ResourceScope(provider_id=uuid4())
    )
    assert scope.unrestricted


def test_un_role_global_l_emporte_sur_un_role_restreint() -> None:
    principal = _principal(
        RoleGrant(Role.CLINIQUE, provider_id=uuid4()), RoleGrant(Role.GESTIONNAIRE)
    )
    assert authorize(principal, "getClaim", ResourceScope(provider_id=uuid4())).unrestricted


def test_employeur_limite_a_son_groupe() -> None:
    mine, other = uuid4(), uuid4()
    employer = _principal(RoleGrant(Role.EMPLOYEUR, employer_id=mine))
    authorize(employer, "getCurrentUser", ResourceScope(employer_id=mine))
    with pytest.raises(NotFoundError):
        authorize(employer, "getCurrentUser", ResourceScope(employer_id=other))


@pytest.mark.parametrize(
    ("role", "provider", "employer"),
    [
        (Role.CLINIQUE, False, False),
        (Role.EMPLOYEUR, False, False),
        (Role.GESTIONNAIRE, True, False),
        (Role.ADMIN, False, True),
        (Role.CLINIQUE, True, True),
    ],
)
def test_attribut_de_portee_coherent_avec_le_role(
    role: Role, provider: bool, employer: bool
) -> None:
    with pytest.raises(ValueError, match="portée"):
        RoleGrant(
            role,
            provider_id=uuid4() if provider else None,
            employer_id=uuid4() if employer else None,
        )


# --- Phase 1 : rôle adhérent (CR-P1-01), limité à SON contrat ---------------------------------

SELF_SERVICE_OPERATIONS = frozenset(
    {
        "getMyCard",
        "listMyBeneficiaries",
        "listMyClaims",
        "getMyClaimTracking",
        "listMyContributions",
        "createMyPaymentLink",
    }
)


def test_l_espace_adherent_n_est_ouvert_qu_a_l_adherent() -> None:
    for operation in SELF_SERVICE_OPERATIONS:
        assert OPERATION_ROLES[operation] == frozenset({Role.ADHERENT})


def test_l_adherent_n_a_que_son_compte_et_son_espace() -> None:
    """Plus l'envoi des événements d'usage de SES écrans (P2) : écriture seule, aucune lecture."""
    allowed = {op for op, roles in OPERATION_ROLES.items() if Role.ADHERENT in roles}
    assert allowed == SELF_SERVICE_OPERATIONS | {
        "getCurrentUser",
        "getCurrentOrganization",
        "recordProductEvent",
    }


def test_les_agregats_produit_reserves_a_la_gestion() -> None:
    """P2 : seuls gestionnaire et admin lisent les indicateurs (ni médecin-conseil, ni clinique)."""
    assert OPERATION_ROLES["getProductMetrics"] == frozenset({Role.GESTIONNAIRE, Role.ADMIN})
    assert OPERATION_ROLES["recordProductEvent"] == frozenset(Role)


def test_portee_adherent_limitee_a_son_contrat() -> None:
    mine, other = uuid4(), uuid4()
    adherent = _principal(RoleGrant(Role.ADHERENT, member_id=mine))
    scope = authorize(adherent, "listMyClaims", ResourceScope(member_id=mine))
    assert not scope.unrestricted
    assert scope.member_ids == frozenset({mine})
    with pytest.raises(NotFoundError):
        authorize(adherent, "listMyClaims", ResourceScope(member_id=other))
    with pytest.raises(NotFoundError):
        authorize(adherent, "listMyClaims", ResourceScope())


def test_un_role_de_gestion_ne_donne_aucun_contrat_a_l_espace_adherent() -> None:
    """Un gestionnaire qui est aussi adhérent n'atteint, dans son espace, que son contrat."""
    mine = uuid4()
    principal = _principal(RoleGrant(Role.GESTIONNAIRE), RoleGrant(Role.ADHERENT, member_id=mine))
    scope = access_scope(principal, "listMyClaims")
    assert scope.roles == frozenset({Role.ADHERENT})
    assert not scope.unrestricted
    assert scope.member_ids == frozenset({mine})


@pytest.mark.parametrize("role", [r for r in Role if r is not Role.ADHERENT])
def test_member_id_reserve_au_role_adherent(role: Role) -> None:
    with pytest.raises(ValueError, match="portée"):
        RoleGrant(
            role,
            provider_id=uuid4() if role is Role.CLINIQUE else None,
            employer_id=uuid4() if role is Role.EMPLOYEUR else None,
            member_id=uuid4(),
        )


def test_adherent_sans_contrat_refuse() -> None:
    with pytest.raises(ValueError, match="portée"):
        RoleGrant(Role.ADHERENT)


# --- Phase 3 : assureur, employeur, admin de plateforme (CR-P3-01) ----------------------------

INSURER_OPERATIONS = frozenset({"getInsurerPortfolio", "exportInsurerPortfolio"})
EMPLOYER_OPERATIONS = frozenset({"getEmployerConsumption", "listEmployerContracts"})
PLATFORM_OPERATIONS = frozenset(
    {"createOrganization", "listConfigurationTemplates", "createConfigurationTemplate"}
)
SELF = frozenset({"getCurrentUser", "getCurrentOrganization", "recordProductEvent"})


def test_l_assureur_ne_lit_que_des_agregats() -> None:
    """Lecture seule : son compte, ses écrans, le portefeuille agrégé. Rien d'autre."""
    allowed = {op for op, roles in OPERATION_ROLES.items() if Role.ASSUREUR in roles}
    assert allowed == SELF | INSURER_OPERATIONS


def test_l_admin_de_plateforme_n_a_que_l_accueil() -> None:
    """Aucun accès métier : ni adhérent, ni dossier, ni grand livre, ni agrégat d'une autre."""
    allowed = {op for op, roles in OPERATION_ROLES.items() if Role.ADMIN_PLATEFORME in roles}
    assert allowed == SELF | PLATFORM_OPERATIONS


def test_l_accueil_d_organisation_reserve_a_la_plateforme() -> None:
    for operation in PLATFORM_OPERATIONS:
        assert OPERATION_ROLES[operation] == frozenset({Role.ADMIN_PLATEFORME})
    for role in (Role.ADMIN, Role.GESTIONNAIRE, Role.ASSUREUR):
        with pytest.raises(RoleForbiddenError):
            access_scope(_principal(RoleGrant(role)), "createOrganization")


def test_la_marque_s_ecrit_par_l_admin_d_organisation_et_se_lit_sans_jeton() -> None:
    assert OPERATION_ROLES["updateBrandingSettings"] == frozenset({Role.ADMIN})
    assert OPERATION_ROLES["getBrandingSettings"] == frozenset({Role.ADMIN})
    assert OPERATION_ROLES["verifyBrandingDomain"] == frozenset({Role.ADMIN})  # CR-P3-02
    assert "getOrganizationBranding" in UNAUTHENTICATED_OPERATIONS


def test_espace_employeur_limite_a_son_groupe() -> None:
    mine = uuid4()
    for operation in EMPLOYER_OPERATIONS:
        assert OPERATION_ROLES[operation] == frozenset({Role.EMPLOYEUR})
        scope = access_scope(_principal(RoleGrant(Role.EMPLOYEUR, employer_id=mine)), operation)
        assert not scope.unrestricted
        assert scope.employer_ids == frozenset({mine})


def test_portefeuille_assureur_ferme_aux_autres_roles() -> None:
    for role in (Role.GESTIONNAIRE, Role.MEDECIN_CONSEIL, Role.ADHERENT, Role.EMPLOYEUR):
        with pytest.raises(RoleForbiddenError):
            access_scope(_principal(_grant(role)), "getInsurerPortfolio")
