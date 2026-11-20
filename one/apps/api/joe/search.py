"""Recherche ⌘K (``search``) : adhérents, dossiers et prestataires visibles par l'utilisateur.

Ce que chaque rôle voit suit les permissions du contrat, opération par opération :
- adhérents : rôles de ``getMember`` (gestionnaire, admin) ;
- dossiers : portée de ``listClaims`` (la clinique ne voit que ses établissements) ;
- prestataires : rôles de ``getProvider`` ; une clinique ne voit que les siens.
Lecture seule, sans modèle de langage ni journal ``ai_actions`` (pas une action de JOE).

``EXAMPLE_QUESTIONS`` : questions d'exemple à proposer dans la palette. Le contrat ``SearchHit``
n'a pas de type « question » : elles ne sont pas renvoyées par ``/v1/search`` (CR-L8-01).
"""

from __future__ import annotations

from typing import Final

from api.core.context import RequestContext
from api.core.errors import RoleForbiddenError
from api.core.permissions import OPERATION_ROLES, Role, access_scope
from api.joe.repository import JoeReadRepository, SearchRow
from api.joe.schemas import SearchHit, SearchResults

PER_TYPE_LIMIT: Final = 10

EXAMPLE_QUESTIONS: Final = (
    "Quels sont les droits de cet adhérent aujourd'hui ?",
    "Quel plafond familial reste-t-il cette année ?",
    "Résume ce dossier en revue.",
    "Quelles cotisations sont en retard ?",
    "Historique des prises en charge de l'adhérent",
    "Quel est le tarif d'une consultation de spécialiste ?",
)


def _has_any(ctx: RequestContext, operation: str) -> bool:
    return bool(ctx.principal.roles & OPERATION_ROLES[operation])


async def search(ctx: RequestContext, term: str) -> SearchResults:
    repo = JoeReadRepository(ctx.session, ctx.principal.organization_id)
    rows: list[SearchRow] = []
    if _has_any(ctx, "getMember"):
        rows += await repo.search_members(term, PER_TYPE_LIMIT)
    try:
        claims_scope = access_scope(ctx.principal, "listClaims")
    except RoleForbiddenError:
        claims_scope = None
    if claims_scope is not None:
        providers = None if claims_scope.unrestricted else sorted(claims_scope.provider_ids)
        rows += await repo.search_claims(term, providers, PER_TYPE_LIMIT)
    if _has_any(ctx, "getProvider"):
        rows += await repo.search_providers(term, None, PER_TYPE_LIMIT)
    elif Role.CLINIQUE in ctx.principal.roles:
        own = sorted(g.provider_id for g in ctx.principal.grants if g.provider_id is not None)
        rows += await repo.search_providers(term, own, PER_TYPE_LIMIT)
    return SearchResults(
        items=[
            SearchHit.model_validate({"type": r.type, "id": r.id, "label": r.label, "meta": r.meta})
            for r in rows
        ]
    )
