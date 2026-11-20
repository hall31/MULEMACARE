"""Interface du fournisseur d'identité et implémentation de TEST.

Le fournisseur n'est pas choisi (PRD §10 Q2). Le contrat attend un jeton porteur (JWT) qui
donne le sujet et l'organisation ; les rôles, eux, sont lus en base (``user_roles``), seule
source de vérité modifiable par l'admin (``replaceUserRoles``).

``InMemoryIdentityProvider`` n'est destiné qu'aux tests : il n'est jamais construit par défaut,
``create_app`` exige qu'on lui passe un fournisseur explicitement.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from api.core.errors import NotAuthenticatedError


@dataclass(frozen=True, slots=True)
class Identity:
    """Ce que le fournisseur garantit : un sujet stable et son organisation."""

    subject: str
    organization_id: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.organization_id, UUID):
            msg = "organization_id doit être un UUID"
            raise TypeError(msg)
        if not self.subject:
            msg = "sujet d'identité vide"
            raise ValueError(msg)


@runtime_checkable
class IdentityProvider(Protocol):
    async def authenticate(self, bearer_token: str) -> Identity:
        """Renvoie l'identité du jeton ou lève ``NotAuthenticatedError`` (AUTH-01)."""
        ...


class InMemoryIdentityProvider:
    """Fournisseur de TEST : jetons opaques aléatoires tenus en mémoire."""

    def __init__(self, tokens: Mapping[str, Identity] | None = None) -> None:
        self._tokens: dict[str, Identity] = dict(tokens or {})

    def issue(self, identity: Identity) -> str:
        token = secrets.token_urlsafe(32)
        self._tokens[token] = identity
        return token

    def revoke(self, token: str) -> None:
        self._tokens.pop(token, None)

    async def authenticate(self, bearer_token: str) -> Identity:
        identity = self._tokens.get(bearer_token)
        if identity is None:
            raise NotAuthenticatedError
        return identity
