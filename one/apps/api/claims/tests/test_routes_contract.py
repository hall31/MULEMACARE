"""Le routeur L5 expose exactement les opérations ``x-lot: L5`` de specs/openapi.yaml."""

from __future__ import annotations

import re

from fastapi.routing import APIRoute

from api.claims.routes import router
from api.tests.paths import OPENAPI_YAML

_OPERATION = re.compile(
    r"^  (/v1/\S+):\n|^    (get|post|put|delete|patch):\n      operationId: (\w+)\n(?:.*\n)*?"
    r"      x-lot: (L\d)",
    re.MULTILINE,
)


def _contract_l5() -> set[tuple[str, str, str]]:
    found: set[tuple[str, str, str]] = set()
    path = ""
    for m in _OPERATION.finditer(OPENAPI_YAML.read_text(encoding="utf-8")):
        if m.group(1):
            path = m.group(1)
        elif m.group(4) == "L5":
            found.add((m.group(2).upper(), path, m.group(3)))
    return found


def test_routes_identiques_au_contrat() -> None:
    routes = {
        (method, route.path, route.operation_id or "")
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods or ()
    }
    assert routes == _contract_l5()
    assert len(routes) == 14
