"""Le moteur est pur et n'appelle aucun LLM (LOTS.md, L2 « Ne pas faire »)."""

from __future__ import annotations

import ast
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parents[1]
ENGINE_FILES = ("engine.py", "model.py", "params.py", "versions.py", "errors.py")

# Bibliothèque standard seulement, plus les modules du paquet.
ENGINE_ALLOWED = {
    "__future__",
    "collections",
    "dataclasses",
    "datetime",
    "decimal",
    "enum",
    "types",
    "typing",
    "uuid",
    "api",
}
FORBIDDEN_ANYWHERE = {
    "openai",
    "anthropic",
    "httpx",
    "requests",
    "urllib",
    "aiohttp",
    "socket",
    "litellm",
    "langchain",
    "random",
    "time",
    "api.joe",
    "api.integrations",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _matches(module: str, prefixes: set[str]) -> bool:
    return any(module == p or module.startswith(f"{p}.") for p in prefixes)


def test_moteur_sans_io_ni_horloge() -> None:
    for name in ENGINE_FILES:
        for module in _imports(RULES_DIR / name):
            assert _matches(module, ENGINE_ALLOWED), f"{name} importe {module}"
            if module.startswith("api"):
                assert module.startswith("api.rules"), f"{name} importe {module}"


def test_aucun_appel_llm_ni_reseau_dans_le_module() -> None:
    files = [p for p in RULES_DIR.rglob("*.py") if "tests" not in p.parts]
    assert files
    for path in files:
        for module in _imports(path):
            assert not _matches(module, FORBIDDEN_ANYWHERE), f"{path.name} importe {module}"
        source = path.read_text(encoding="utf-8")
        for call in ("datetime.now", "date.today", "utcnow"):
            assert call not in source, f"{path.name} lit l'horloge ({call})"
