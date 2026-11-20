"""Configuration du noyau, lue dans l'environnement (aucun secret dans le code)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal

from api.integrations.egress import ALLOWLIST_PATH, EgressAllowlist, load_allowlist

DEFAULT_APP_ROLE = "mulema_app"

type Environment = Literal["production", "development"]
ENVIRONMENTS: Final[frozenset[str]] = frozenset({"production", "development"})


class ConfigurationError(RuntimeError):
    """Configuration absente ou invalide : le démarrage est refusé (échec fermé).

    Le message nomme la variable en cause, jamais sa valeur (elle peut être un secret)."""


def deny_all_egress() -> EgressAllowlist:
    """Liste blanche vide : aucune connexion sortante (échec fermé)."""
    return EgressAllowlist(frozenset())


@dataclass(frozen=True, slots=True)
class Settings:
    """``database_url`` : URL SQLAlchemy async (``postgresql+psycopg://…``).

    ``app_role`` : rôle non propriétaire endossé à chaque transaction (``SET LOCAL ROLE``) ;
    ``None`` seulement si le rôle de connexion est lui-même soumis à la RLS.

    ``egress_allowlist`` : destinations réseau autorisées, imposées par ``egress_guard`` pendant
    toute la vie de l'application (R9). Vide par défaut : rien ne sort.

    ``environment`` : ``production`` par défaut (échec fermé). ``expose_docs`` : ``/docs``,
    ``/redoc`` et ``/openapi.json`` servis ; jamais en production (refusé par ``from_mapping``).

    ``strict_database_login`` : le rôle de CONNEXION (``session_user``) est lui aussi vérifié au
    démarrage (ni superutilisateur, ni BYPASSRLS, ni propriétaire). Toujours vrai pour une
    configuration lue dans l'environnement ; faux pour les tests, dont la connexion est un
    superutilisateur qui endosse ``mulema_app``.
    """

    database_url: str
    app_role: str | None = DEFAULT_APP_ROLE
    egress_allowlist: EgressAllowlist = field(default_factory=deny_all_egress)
    environment: Environment = "production"
    expose_docs: bool = False
    strict_database_login: bool = False

    def __post_init__(self) -> None:
        if self.environment == "production" and self.expose_docs:
            msg = "la documentation interactive de l'API est interdite en production"
            raise ConfigurationError(msg)

    @classmethod
    def from_env(cls) -> Settings:
        return cls.from_mapping(os.environ)

    @classmethod
    def from_mapping(cls, env: Mapping[str, str]) -> Settings:
        url = env.get("MULEMA_INSURANCE_DATABASE_URL")
        if not url:
            msg = "MULEMA_INSURANCE_DATABASE_URL manquante"
            raise ConfigurationError(msg)
        environment = env.get("MULEMA_ENV", "production") or "production"
        if environment not in ENVIRONMENTS:
            msg = "MULEMA_ENV : « production » ou « development » attendu"
            raise ConfigurationError(msg)
        role = env.get("MULEMA_DB_APP_ROLE", DEFAULT_APP_ROLE) or None
        if role is None and environment == "production":
            msg = "MULEMA_DB_APP_ROLE vide : un rôle applicatif non propriétaire est exigé"
            raise ConfigurationError(msg)
        country = env.get("MULEMA_COUNTRY")
        if not country:
            msg = "MULEMA_COUNTRY manquante (CI ou SN) : liste blanche réseau introuvable"
            raise ConfigurationError(msg)
        try:
            allowlist = load_allowlist(ALLOWLIST_PATH, country=country)
        except ValueError as exc:
            msg = "MULEMA_COUNTRY ou infra/egress-allowlist.txt invalide"
            raise ConfigurationError(msg) from exc
        docs = env.get("MULEMA_EXPOSE_DOCS", "") == "1"
        if docs and environment == "production":
            msg = "MULEMA_EXPOSE_DOCS=1 interdit en production"
            raise ConfigurationError(msg)
        return cls(
            database_url=url,
            app_role=role,
            egress_allowlist=allowlist,
            environment="development" if environment == "development" else "production",
            expose_docs=docs,
            strict_database_login=True,
        )
