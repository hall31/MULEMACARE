"""Contrat L0 : ``specs/openapi.yaml`` couvre les lots L1 à L8 et les codes d'erreur stables.

Le lint structurel (OpenAPI 3.1) est fait par Spectral (``make contracts``). Ici, des invariants
métier vérifiables sans dépendance supplémentaire : lecture textuelle du YAML.
"""

from __future__ import annotations

import re

import pytest

from api.tests.paths import OPENAPI_YAML

# Opérations exigées par lot (LOTS.md). Égalité stricte : une opération retirée, renommée ou
# rattachée à un autre lot fait échouer le test.
OPERATIONS_BY_LOT: dict[str, frozenset[str]] = {
    "L1": frozenset(
        {
            "getCurrentUser",
            "getCurrentOrganization",
            "listUsers",
            "createUser",
            "replaceUserRoles",
            "listAuditEvents",
        }
    ),
    "L2": frozenset(
        {
            "listPlans",
            "createPlan",
            "getPlan",
            "createPlanVersion",
            "getPlanVersion",
            "publishPlanVersion",
            "listProviders",
            "createProvider",
            "getProvider",
            "createProviderConvention",
            "listTariffs",
            "listActs",
            "createAct",
            "createTariffItem",
            "listRules",
            "listRuleVersions",
            "createRuleVersion",
            "publishRuleVersion",
            "evaluateRules",
        }
    ),
    "L3": frozenset(
        {
            "listLedgerAccounts",
            "listLedgerEntries",
            "getLedgerEntry",
            "reverseLedgerEntry",
            "getLedgerBalance",
        }
    ),
    "L4": frozenset(
        {
            "listMembers",
            "createMember",
            "getMember",
            "addDependent",
            "getMemberEntitlements",
            "issueCard",
            "changeMemberStatus",
            "listMemberContributions",
            "sendReminder",
            "createPaymentLink",
            "getPublicPaymentLink",
            "startCheckout",
            "receivePaymentWebhook",
        }
    ),
    "L5": frozenset(
        {
            "startIdentification",
            "confirmPhoto",
            "sendIdentificationCode",
            "verifyIdentificationCode",
            "getOfflinePolicy",
            "registerCounterDevice",
            "syncOfflineAuthorizations",
            "listClaims",
            "createClaim",
            "getClaim",
            "decideClaim",
            "submitClaimDocuments",
            "readMedicalReason",
            "getWorkQueue",
        }
    ),
    "L8": frozenset({"askJoe", "draftClaimDecision", "draftMessage", "search", "listAiActions"}),
    # Phase 1, voie A : espace adhérent et diaspora (CR-P1-01, rôle adherent).
    "P1": frozenset(
        {
            "getMyCard",
            "listMyBeneficiaries",
            "listMyClaims",
            "getMyClaimTracking",
            "listMyContributions",
            "createMyPaymentLink",
        }
    ),
    # Phase 2, voie B : mesure produit (CR-P2-01), sans traceur tiers ni donnée identifiante.
    "P2": frozenset({"recordProductEvent", "getProductMetrics"}),
    # Phase 3, voie A : marque blanche, espaces assureur et employeur, accueil d'organisation
    # (CR-P3-01, vente clé en main aux assureurs).
    "P3": frozenset(
        {
            "getOrganizationBranding",
            "getBrandingSettings",
            "updateBrandingSettings",
            "verifyBrandingDomain",
            "getInsurerPortfolio",
            "exportInsurerPortfolio",
            "getEmployerConsumption",
            "listEmployerContracts",
            "createOrganization",
            "listConfigurationTemplates",
            "createConfigurationTemplate",
        }
    ),
}
_OPERATION = re.compile(r"operationId: (\w+)\n(?:(?!\s+operationId:).*\n)*?\s+x-lot: ([LP]\d)")
STABLE_CODES = (
    "R-01",
    "R-04",
    "R-07",
    "R-09",
    "R-12",
    "R-20",
    "ID-03",
    "ID-04",
    "SEC-01",
    # P3 (CR-P3-01) : gardes de marque blanche et d'accueil d'organisation.
    "BRD-01",
    "BRD-02",
    "BRD-03",
    "BRD-04",
    "BRD-05",
    "BRD-06",
    "ORG-01",
    "ORG-02",
)
# R11 : aucun outil de JOE ne décide ni ne paie.
FORBIDDEN_JOE_PATHS = re.compile(r"^  /v1/joe/\S*(approve|reject|pay|decide)", re.MULTILINE)


def _spec() -> str:
    return OPENAPI_YAML.read_text(encoding="utf-8")


def test_version_openapi_3_1() -> None:
    assert re.search(r"^openapi: 3\.1\.\d+$", _spec(), re.MULTILINE)


def _operations_by_lot() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for operation_id, lot in _OPERATION.findall(_spec()):
        found.setdefault(lot, set()).add(operation_id)
    return found


def test_chaque_operation_a_un_lot() -> None:
    declared = re.findall(r"operationId: (\w+)", _spec())
    assert len(declared) == len(set(declared)), "operationId en double"
    assert sum(len(ops) for ops in _operations_by_lot().values()) == len(declared)


@pytest.mark.parametrize("lot", sorted(OPERATIONS_BY_LOT))
def test_operations_exigees_par_lot(lot: str) -> None:
    found = _operations_by_lot().get(lot, set())
    expected = OPERATIONS_BY_LOT[lot]
    assert found == expected, (
        f"{lot} : manquantes {sorted(expected - found)}, inattendues {sorted(found - expected)}"
    )


def test_aucun_lot_hors_liste() -> None:
    assert set(_operations_by_lot()) == set(OPERATIONS_BY_LOT)


@pytest.mark.parametrize("code", STABLE_CODES)
def test_code_stable_declare(code: str) -> None:
    assert re.search(rf"^\s+- {re.escape(code)}$", _spec(), re.MULTILINE), code


def test_joe_n_expose_aucune_action_de_decision_ou_de_paiement() -> None:
    assert not FORBIDDEN_JOE_PATHS.findall(_spec())


def test_aucun_tenant_id_recu_du_client() -> None:
    """L'organisation vient du jeton, jamais d'un paramètre ou d'un corps de requête."""
    spec = _spec()
    assert not re.search(r"name: organi[sz]ation_?id", spec, re.IGNORECASE)
    # Seule exception : le webhook de paiement (sans jeton, signé) porte le slug dans son URL.
    slug_paths = re.findall(r"^  (/\S*\{organization_slug\}\S*):$", spec, re.MULTILINE)
    assert slug_paths == ["/v1/webhooks/{organization_slug}/payments/{channel}"]
    # Schémas de requête : blocs de composants dont le nom finit par « Request ».
    request_block = r"^    (\w+Request):\n(.*?)(?=^    \w+:\n|\Z)"
    blocks = re.findall(request_block, spec, re.MULTILINE | re.DOTALL)
    assert blocks, "aucun schéma *Request trouvé"
    leaking = sorted(name for name, body in blocks if "organization_id" in body)
    assert not leaking, f"organization_id accepté du client dans : {leaking}"


# Espace adhérent (P1) : aucun score de fraude, aucune règle interne, aucun acte, aucune donnée
# médicale. Contrôle sur la FERMETURE des schémas de réponse 2xx de /v1/me/* : schémas racines
# et tout ce qu'ils référencent ($ref), propriétés à toute profondeur.
MEMBER_SPACE_SCHEMAS = frozenset(
    {
        "MyCard",
        "MyBeneficiary",
        "MyClaim",
        "TrackingStep",
        "ClaimTracking",
        "MyContribution",
        "MyContributions",
    }
)
INTERNAL_FIELDS = re.compile(
    r"fraud|healthos|review_due_at|decided_by|evaluation|trace|rule_id|params|diagnos|motif",
    re.IGNORECASE,
)
# Mots interdits dans un nom de propriété ou de schéma (découpé en mots : act_code → act, code ;
# « contract » ne contient pas le mot « act »).
FORBIDDEN_WORDS = frozenset({"act", "acts", "score", "scores", "fraud", "rule", "rules"})
# Seule exception, voulue par le contrat (listMyClaims : « seulement le code public de la règle
# appliquée ») : la propriété ``rule`` qui pointe sur RuleRef, et RuleRef = {code, version}.
PUBLIC_RULE_SCHEMAS = frozenset({"RuleRef", "RuleCodeValue"})
PUBLIC_RULE_PROPERTY = "rule"
PUBLIC_RULE_FIELDS = frozenset({"code", "version"})
_SCHEMA_REF = re.compile(r"#/components/schemas/(\w+)")
_KEY = re.compile(r"^(\s*)([\w$-]+):")


def _words(name: str) -> set[str]:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return {w for w in re.split(r"[_\W]+", spaced.lower()) if w}


def _paths_section(spec: str) -> str:
    return spec.split("\npaths:\n", 1)[1].split("\ncomponents:\n", 1)[0]


def _member_space_roots(spec: str) -> dict[str, set[str]]:
    """operationId de /v1/me/* → schémas de ses réponses 2xx."""
    roots: dict[str, set[str]] = {}
    for block in re.split(r"(?m)^(?=  /)", _paths_section(spec)):
        if not block.startswith("  /v1/me/"):
            continue
        for operation in re.split(r"(?m)^(?=    (?:get|post|put|patch|delete):)", block)[1:]:
            found = re.search(r"operationId: (\w+)", operation)
            assert found, operation
            responses = operation.split("      responses:\n", 1)[1]
            ok = re.findall(r"(?ms)^        '2\d\d':\n(.*?)(?=^        '|\Z)", responses)
            roots[found.group(1)] = {ref for body in ok for ref in _SCHEMA_REF.findall(body)}
    return roots


def _schema_closure(spec: str, roots: set[str]) -> set[str]:
    seen: set[str] = set()
    pending = list(roots)
    while pending:
        name = pending.pop()
        if name not in seen:
            seen.add(name)
            pending += _SCHEMA_REF.findall(_schema_block(spec, name))
    return seen


def _properties(block: str) -> dict[str, str]:
    """Propriétés (toute profondeur) d'un schéma → texte de leur définition."""
    found: dict[str, str] = {}
    stack: list[tuple[int, str]] = []
    lines = block.splitlines()
    for index, line in enumerate(lines):
        match = _KEY.match(line)
        if not match or line.lstrip().startswith("- "):
            continue
        indent, key = len(match.group(1)), match.group(2)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if stack and stack[-1][1] == "properties":
            body = [line]
            for following in lines[index + 1 :]:
                if following.strip() and len(following) - len(following.lstrip()) <= indent:
                    break
                body.append(following)
            found[key] = "\n".join(body)
        stack.append((indent, key))
    return found


def _schema_block(spec: str, name: str) -> str:
    match = re.search(rf"^    {name}:\n(.*?)(?=^    \w+:\n|\Z)", spec, re.MULTILINE | re.DOTALL)
    assert match, f"schéma {name} absent du contrat"
    return match.group(1)


def _leaks(spec: str) -> list[str]:
    roots = _member_space_roots(spec)
    closure = _schema_closure(spec, set().union(*roots.values()))
    leaks = [
        f"schéma {name}"
        for name in sorted(closure - PUBLIC_RULE_SCHEMAS)
        if _words(name) & FORBIDDEN_WORDS
    ]
    for name in sorted(closure):
        for prop, body in _properties(_schema_block(spec, name)).items():
            if INTERNAL_FIELDS.search(prop):
                leaks.append(f"{name}.{prop}")
            elif _words(prop) & FORBIDDEN_WORDS:
                public = prop == PUBLIC_RULE_PROPERTY and set(_SCHEMA_REF.findall(body)) == {
                    "RuleRef"
                }
                if not public:
                    leaks.append(f"{name}.{prop}")
    if "RuleRef" in closure and set(_properties(_schema_block(spec, "RuleRef"))) != (
        PUBLIC_RULE_FIELDS
    ):
        leaks.append("RuleRef doit rester {code, version}")
    return leaks


def test_espace_adherent_reponses_lues() -> None:
    """Garde-fou du lecteur : chaque opération P1 a un schéma de réponse 2xx, fermeture large."""
    spec = _spec()
    roots = _member_space_roots(spec)
    assert set(roots) == OPERATIONS_BY_LOT["P1"]
    assert all(roots.values()), roots
    closure = _schema_closure(spec, set().union(*roots.values()))
    assert closure >= MEMBER_SPACE_SCHEMAS | {"Entitlements", "RuleRef", "PaymentLink"}
    assert {"rule", "entitlements", "qr_payload"} <= {
        prop for name in closure for prop in _properties(_schema_block(spec, name))
    }


def test_espace_adherent_sans_donnee_interne() -> None:
    """Ni acte, ni score, ni fraude, ni règle interne, ni donnée médicale dans /v1/me/*."""
    assert _leaks(_spec()) == []


def test_espace_adherent_reserve_au_role_adherent() -> None:
    spec = _spec()
    for operation in OPERATIONS_BY_LOT["P1"]:
        block = re.search(
            rf"operationId: {operation}\n(?:(?!\s+operationId:).*\n)*?\s+x-roles: \[([^\]]*)\]",
            spec,
        )
        assert block, operation
        assert block.group(1) == "adherent", operation


# Espaces assureur et employeur (P3) : agrégats seulement. Aucun nom de personne, aucun acte,
# aucun motif, aucun score dans les réponses 2xx de /v1/insurer/* et /v1/employer/*.
AGGREGATE_PREFIXES = ("  /v1/insurer/", "  /v1/employer/")
PERSONAL_FIELDS = re.compile(
    r"given_name|family_name|birth|phone|email|person|member_id|member_number|beneficiary"
    r"|claim_id|claim_number|card|fraud|healthos|diagnos|motif|act_code|reason",
    re.IGNORECASE,
)


def _aggregate_roots(spec: str) -> dict[str, set[str]]:
    roots: dict[str, set[str]] = {}
    for block in re.split(r"(?m)^(?=  /)", _paths_section(spec)):
        if not block.startswith(AGGREGATE_PREFIXES):
            continue
        for operation in re.split(r"(?m)^(?=    (?:get|post|put|patch|delete):)", block)[1:]:
            found = re.search(r"operationId: (\w+)", operation)
            assert found, operation
            responses = operation.split("      responses:\n", 1)[1]
            ok = re.findall(r"(?ms)^        '2\d\d':\n(.*?)(?=^        '|\Z)", responses)
            roots[found.group(1)] = {ref for body in ok for ref in _SCHEMA_REF.findall(body)}
    return roots


def test_espaces_assureur_et_employeur_sans_donnee_de_personne() -> None:
    spec = _spec()
    roots = _aggregate_roots(spec)
    assert set(roots) == {
        "getInsurerPortfolio",
        "exportInsurerPortfolio",
        "getEmployerConsumption",
        "listEmployerContracts",
    }
    closure = _schema_closure(spec, set().union(*roots.values()))
    assert {"InsurerPortfolio", "EmployerConsumption", "KAnonymousValue"} <= closure
    leaks = [
        f"{name}.{prop}"
        for name in sorted(closure)
        for prop in _properties(_schema_block(spec, name))
        if PERSONAL_FIELDS.search(prop)
    ]
    assert leaks == []


def test_valeurs_k_anonymes_bornees_a_5() -> None:
    block = _schema_block(_spec(), "KAnonymousValue")
    assert re.search(r"contributors:\n(?:.*\n)*?\s+minimum: 5", block)


def test_marque_publique_sans_identifiant_interne() -> None:
    """getOrganizationBranding (sans jeton) : ni id, ni utilisateur, ni réglage interne."""
    spec = _spec()
    properties = set(_properties(_schema_block(spec, "OrganizationBranding")))
    assert properties == {
        "slug",
        "display_name",
        "country_code",
        "currency",
        "logo",
        "theme",
        "custom_domain",
        "legal_notice",
        "privacy_notice",
    }


def test_jetons_surchargeables_liste_fermee() -> None:
    spec = _spec()
    for name in ("BrandTokenOverrides", "BrandTheme", "BrandLogo", "UpdateBrandingRequest"):
        assert "additionalProperties: false" in _schema_block(spec, name), name
    assert set(_properties(_schema_block(spec, "BrandTokenOverrides"))) == {
        "accent",
        "accent_hover",
        "accent_fg",
        "brand_deep",
    }
    assert set(_properties(_schema_block(spec, "BrandTheme"))) == {"light", "dark"}


def test_plateforme_reservee_a_l_administrateur_de_plateforme() -> None:
    spec = _spec()
    for operation in ("createOrganization", "listConfigurationTemplates",
                      "createConfigurationTemplate"):  # fmt: skip
        block = re.search(
            rf"operationId: {operation}\n(?:(?!\s+operationId:).*\n)*?\s+x-roles: \[([^\]]*)\]",
            spec,
        )
        assert block, operation
        assert block.group(1) == "admin_plateforme", operation
