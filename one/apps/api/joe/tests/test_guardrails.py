"""R11 — garde-fous statiques : registre d'outils fermé, aucun outil de décision, de paiement
ni de motif médical, aucune écriture hors ``ai_actions``, aucun SDK LLM.

Ces tests lisent le code ; ``test_read_only.py`` prouve les mêmes règles à l'exécution.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path
from types import MappingProxyType

import pytest

from api.core.permissions import OPERATION_ROLES
from api.joe.tools import PREPARATION_TOOLS, READ_TOOLS, TOOL_REGISTRY, ToolKind

JOE_DIR = Path(__file__).resolve().parents[1]
SOURCES = sorted(p for p in JOE_DIR.rglob("*.py") if "tests" not in p.parts)

# Registre fermé : ajouter un outil oblige à modifier CE test (revue humaine).
EXPECTED_TOOLS = {
    "lire_adherent": ToolKind.LECTURE,
    "lire_droits": ToolKind.LECTURE,
    "lire_historique": ToolKind.LECTURE,
    "lire_cotisations": ToolKind.LECTURE,
    "lire_bareme": ToolKind.LECTURE,
    "lire_dossier": ToolKind.LECTURE,
    "preparer_brouillon_decision": ToolKind.PREPARATION,
    "preparer_message": ToolKind.PREPARATION,
}

# Opérations du contrat que les outils de lecture peuvent emprunter : des GET, rien d'autre.
READ_OPERATIONS = {
    "getMember",
    "getMemberEntitlements",
    "listClaims",
    "getClaim",
    "listMemberContributions",
    "listTariffs",
}

# Contrainte CHECK de ai_actions.tool (specs/schema.sql) + verbes français équivalents.
FORBIDDEN_TOOL = re.compile(
    r"approve|reject|pay|decide|accord|refus|valid|rembours|annul|suspend|bloqu|envo",
    re.IGNORECASE,
)
MEDICAL = re.compile(r"motif|m[ée]dic|diagnos|ordonnance|healthos|clinique_ref", re.IGNORECASE)

FORBIDDEN_IMPORTS = {
    # Secret médical : JOE n'a aucun chemin vers le motif.
    "api.core.medical",
    "api.integrations.healthos",
    "api.integrations.healthos_sim",
    # Services qui décident, paient ou écrivent : jamais importés par JOE.
    "api.claims.service",
    "api.claims.identification",
    "api.claims.offline",
    "api.claims.rulebook",
    "api.payments.service",
    "api.payments.webhooks",
    "api.payments.jobs",
    "api.members.jobs",
    "api.ledger.service",
    "api.ledger.consumer",
    "api.rules.engine",
    # Pas de SDK LLM ni de client réseau tiers (interface interne, transport gardé L9).
    "openai",
    "anthropic",
    "litellm",
    "langchain",
    "httpx",
    "requests",
    "aiohttp",
    "socket",
    "urllib.request",
}

# Méthodes d'écriture des autres lots : aucun appel depuis JOE.
WRITE_CALL = re.compile(
    r"^(insert_\w*|update_\w*|set_\w*|mark_\w*|queue_\w*|revoke_\w*|append_\w*|add_\w*|"
    r"decide|apply_decision|create|create_link|issue_card|issue_month|change_status|"
    r"send_reminder|submit_documents|checkout|reverse|post_entry|complete_key|reserve_key|"
    r"read_medical_reason|record_status|transition)$"
)
WRITE_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|TRUNCATE|MERGE|ALTER|DROP|CREATE|GRANT|COPY)\b", re.IGNORECASE
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _sql_literals(path: Path) -> list[str]:
    """Chaînes du code qui ressemblent à du SQL (docstrings exclues : elles décrivent)."""
    tree = _tree(path)
    docstrings = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and id(node) not in docstrings
        and isinstance(node.value, str)
        and re.search(r"\b(SELECT|INSERT|UPDATE|DELETE|FROM|INTO|SET)\b", node.value)
    ]


def test_sources_trouvees() -> None:
    names = {p.name for p in SOURCES}
    assert {"tools.py", "service.py", "model.py", "journal.py", "guard.py"} <= names


def test_registre_ferme_et_exact() -> None:
    assert isinstance(TOOL_REGISTRY, MappingProxyType)
    assert {name: spec.kind for name, spec in TOOL_REGISTRY.items()} == EXPECTED_TOOLS
    assert set(READ_TOOLS) | set(PREPARATION_TOOLS) == set(TOOL_REGISTRY)
    with pytest.raises(TypeError):
        TOOL_REGISTRY["approve_claim"] = TOOL_REGISTRY["lire_dossier"]  # type: ignore[index]


@pytest.mark.parametrize("name", sorted(EXPECTED_TOOLS))
def test_aucun_outil_de_decision_de_paiement_ni_de_motif(name: str) -> None:
    spec = TOOL_REGISTRY[name]
    assert re.fullmatch(r"[a-z_]{2,64}", name)  # CHECK de ai_actions.tool
    assert not FORBIDDEN_TOOL.search(name), name
    assert not MEDICAL.search(name), name
    assert not MEDICAL.search(spec.description), spec.description


def test_les_outils_de_lecture_n_empruntent_que_des_operations_de_lecture() -> None:
    for name, tool in READ_TOOLS.items():
        assert tool.operation in OPERATION_ROLES, name
        assert tool.operation in READ_OPERATIONS, f"{name} emprunte {tool.operation}"


def test_les_outils_de_preparation_n_ont_aucun_acces_aux_donnees() -> None:
    """Un outil de préparation reçoit des constats déjà lus : ni session, ni dépôt, ni port."""
    for name, tool in PREPARATION_TOOLS.items():
        source = inspect.getsource(tool.run)
        for word in ("session", "ports", "repository", "Repository", "execute", "await "):
            assert word not in source, f"{name} : « {word} »"
        assert not inspect.iscoroutinefunction(tool.run), name


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_aucun_import_interdit(path: Path) -> None:
    for module in _imports(path):
        for forbidden in FORBIDDEN_IMPORTS:
            assert module != forbidden, f"{path.name} importe {module}"
            assert not module.startswith(f"{forbidden}."), f"{path.name} importe {module}"


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_aucun_appel_a_une_fonction_d_ecriture(path: Path) -> None:
    if path.name == "journal.py":  # seule écriture permise : ai_actions (vérifiée ci-dessous)
        return
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            assert not WRITE_CALL.match(name), f"{path.name}:{node.lineno} appelle {name}"


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_seule_ecriture_sql_dans_ai_actions(path: Path) -> None:
    for literal in _sql_literals(path):
        if re.match(r"\s*SET\b", literal):  # seul réglage admis : passer en lecture seule
            assert literal == "SET LOCAL transaction_read_only = on", literal
            continue
        writes = WRITE_SQL.findall(literal)
        if not writes:
            continue
        assert path.name == "journal.py", f"{path.name} écrit en SQL : {literal[:80]}"
        assert [w.upper() for w in writes] == ["INSERT"], literal[:80]
        assert re.search(r"INSERT\s+INTO\s+ai_actions\b", literal), literal[:80]


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_jamais_le_motif_medical(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    for needle in ("medical_reason", "readMedicalReason", "healthos_encounter_ref", "/medical"):
        assert needle not in source, f"{path.name} mentionne {needle}"
