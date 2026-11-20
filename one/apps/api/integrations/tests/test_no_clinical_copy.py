"""L9 « Ne pas faire » — aucune copie de données cliniques dans la base assurance.

Le module d'intégration lit HealthOS et rend la main : il n'a aucun accès à la base, n'écrit
rien, et ne met rien en cache. Un import de pilote de base ou une requête d'écriture dans ce
module ferait échouer ce test.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

INTEGRATIONS = Path(__file__).resolve().parents[1]
FORBIDDEN_IMPORTS = ("sqlalchemy", "psycopg", "asyncpg", "alembic", "redis", "sqlite3", "shelve")
WRITE_SQL = re.compile(r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|COPY\s+\w+)\b", re.IGNORECASE)
CACHES = ("lru_cache", "cache", "cached_property")
# Seule dépendance hors du module : la journalisation JSON du noyau (bibliothèque standard
# uniquement, vérifié ci-dessous), imposée par les conventions de code (logs structurés).
ALLOWED_CORE = frozenset({"api.core.jsonlog"})
JSONLOG = INTEGRATIONS.parent / "core" / "jsonlog.py"


def _modules() -> list[Path]:
    return sorted(p for p in INTEGRATIONS.glob("*.py"))


def _imports(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_integrations_modules_exist() -> None:
    names = {p.stem for p in _modules()}
    assert {"egress", "transport", "healthos", "healthos_sim", "deployment"} <= names


def test_no_database_driver_or_other_business_module_imported() -> None:
    for module in _modules():
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for name in _imports(tree):
            root = name.split(".")[0]
            assert root not in FORBIDDEN_IMPORTS, f"{module.name} importe {name}"
            if name.startswith("api.") and name not in ALLOWED_CORE:
                assert name.startswith("api.integrations"), f"{module.name} importe {name}"
    for name in _imports(ast.parse(JSONLOG.read_text(encoding="utf-8"))):
        assert name.split(".")[0] not in FORBIDDEN_IMPORTS, f"jsonlog importe {name}"
        assert not name.startswith("api."), f"jsonlog importe {name}"


def test_no_write_sql_and_no_cache_in_integrations() -> None:
    for module in _modules():
        source = module.read_text(encoding="utf-8")
        assert not WRITE_SQL.search(source), module.name
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for deco in node.decorator_list:
                    target = deco.func if isinstance(deco, ast.Call) else deco
                    label = (
                        target.attr if isinstance(target, ast.Attribute) else ast.unparse(target)
                    )
                    assert label not in CACHES, f"{module.name}:{node.name} met en cache"
