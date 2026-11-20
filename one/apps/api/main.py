"""Point d'entrée de production (L10) : ``python -m api.main`` ou ``uvicorn api.main:app_factory
--factory``.

Construit l'application ASSEMBLÉE (``create_app(..., modules=AppModules(...))``) depuis
l'environnement, et refuse de démarrer (échec FERMÉ) si :
- une variable obligatoire manque ou est invalide (base, pays, rôle applicatif, clés
  ``MULEMA_CARD_KEY`` et ``MULEMA_METRICS_PSEUDONYM_KEY``, secrets de lien de paiement,
  fournisseur d'identité OIDC) — le message nomme la variable, jamais sa valeur ;
- au démarrage, le rôle de connexion OU le rôle effectif est superutilisateur, BYPASSRLS ou
  propriétaire (``Database.verify_isolation_enforced(strict_login=True)``).

Choix tant que le PRD §10 n'est pas tranché : canaux de paiement SIMULÉS (un canal n'est activé
que si son secret est fourni), aucun fournisseur SMS (``UnconfiguredSmsSender`` : aucun envoi,
Q-L5-01), aucun score de fraude (tout dossier part en revue, Q-L0-05), JOE déterministe sauf
configuration locale. ``InMemoryIdentityProvider`` (tests) n'est jamais construit ici.

Variables : voir ``.env.example`` et ``docs/DEPLOYMENT.md``.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final

import uvicorn
from fastapi import FastAPI

from api.claims.ports import ClaimsRuntime
from api.core.app import AppModules, create_app
from api.core.clock import SystemClock
from api.core.jsonlog import LOGGER_NAME, configure_json_logging, log_event
from api.core.oidc import (
    DEFAULT_LEEWAY_SECONDS,
    DEFAULT_ORGANIZATION_CLAIM,
    SUPPORTED_ALGORITHMS,
    FileJwksSource,
    HttpJwksSource,
    JwksSource,
    OidcConfig,
    OidcIdentityProvider,
)
from api.core.ratelimit import RateLimits, parse_trusted_proxies
from api.core.settings import ConfigurationError, Settings
from api.integrations.deployment import build_healthos_client, load_deployment
from api.integrations.transport import GuardedHttpTransport, split_destination
from api.joe.model import JoeModelSettings, build_language_model
from api.joe.ports import member_reader_factory
from api.joe.service import JoeRuntime
from api.members.cards import CardKeys, CardQrVerifier
from api.members.routes import MembersRuntime
from api.metrics.runtime import MetricsRuntime
from api.payments.channels import SIMULATED_CHANNELS, ChannelRegistry, SimulatedChannel
from api.payments.config import PaymentsConfig
from api.payments.routes import PaymentsRuntime
from api.rules.routes import RulesRuntime

logger = logging.getLogger(f"{LOGGER_NAME}.main")

MIN_SECRET_BYTES: Final = 32
DEFAULT_HOST: Final = "127.0.0.1"
DEFAULT_PORT: Final = 8000
GRACEFUL_SHUTDOWN_SECONDS: Final = 20
JWKS_TIMEOUT_SECONDS: Final = 5.0
EXIT_CONFIGURATION: Final = 78  # EX_CONFIG (sysexits.h)
# Émetteur de développement (``api.core.devtools``) : refusé en production.
DEV_ISSUER_SUFFIX: Final = ".invalid"


class UnconfiguredSmsSender:
    """Aucun fournisseur SMS choisi (Q-L5-01) : n'envoie rien, ne garde rien en mémoire.

    L'identification au comptoir ne peut donc pas aboutir au code SMS en production tant
    qu'un fournisseur n'est pas branché ; l'événement est journalisé sans numéro ni code."""

    async def send_code(self, *, phone_e164: str, code: str) -> None:
        del phone_e164, code
        log_event(logger, logging.WARNING, "sms.not_configured")


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        msg = f"{name} manquante"
        raise ConfigurationError(msg)
    return value


def hex_secret(env: Mapping[str, str], name: str, *, required: bool = True) -> bytes | None:
    """Secret hexadécimal d'au moins 32 octets ; ``None`` si absent et facultatif."""
    raw = env.get(name, "").strip()
    if not raw:
        if required:
            msg = f"{name} manquante (hexadécimal, {MIN_SECRET_BYTES} octets minimum)"
            raise ConfigurationError(msg)
        return None
    try:
        value = bytes.fromhex(raw)
    except ValueError:
        msg = f"{name} doit être en hexadécimal"
        raise ConfigurationError(msg) from None
    if len(value) < MIN_SECRET_BYTES:
        msg = f"{name} trop courte ({MIN_SECRET_BYTES} octets minimum)"
        raise ConfigurationError(msg)
    return value


def _require_secret(env: Mapping[str, str], name: str) -> bytes:
    value = hex_secret(env, name)
    assert value is not None  # noqa: S101 — garanti par required=True
    return value


def payments_config(env: Mapping[str, str]) -> PaymentsConfig:
    """Même lecture que ``PaymentsConfig.from_env``, depuis un dictionnaire, avec des erreurs
    qui nomment la variable. Canaux SIMULÉS, activés seulement si leur secret est fourni."""
    channels = [
        SimulatedChannel(name, secret)
        for name in SIMULATED_CHANNELS
        if (secret := hex_secret(env, f"MULEMA_PAYMENT_SECRET_{name.upper()}", required=False))
    ]
    base_url = _required(env, "MULEMA_PAYMENT_PUBLIC_BASE_URL").rstrip("/")
    if not base_url.startswith("https://"):
        msg = "MULEMA_PAYMENT_PUBLIC_BASE_URL doit être une URL https"
        raise ConfigurationError(msg)
    return PaymentsConfig(
        link_secret=_require_secret(env, "MULEMA_PAYMENT_LINK_SECRET"),
        public_base_url=base_url,
        channels=ChannelRegistry(channels),
    )


def _jwks_source(env: Mapping[str, str], settings: Settings) -> JwksSource:
    url = env.get("MULEMA_OIDC_JWKS_URL", "").strip()
    path = env.get("MULEMA_OIDC_JWKS_FILE", "").strip()
    if bool(url) == bool(path):
        msg = "MULEMA_OIDC_JWKS_URL ou MULEMA_OIDC_JWKS_FILE : exactement l'une des deux"
        raise ConfigurationError(msg)
    if path:
        file = Path(path)
        if not file.is_file():
            msg = "MULEMA_OIDC_JWKS_FILE : fichier introuvable"
            raise ConfigurationError(msg)
        return FileJwksSource(file)
    scheme, host, port, _ = split_destination(url)
    if scheme != "https":
        msg = "MULEMA_OIDC_JWKS_URL doit être une URL https"
        raise ConfigurationError(msg)
    if not settings.egress_allowlist.allows(host, port):
        msg = (
            "MULEMA_OIDC_JWKS_URL hors liste blanche : ajouter l'hôte à "
            "infra/egress-allowlist.txt et infra/deploy/<pays>.toml (revue humaine)"
        )
        raise ConfigurationError(msg)
    transport = GuardedHttpTransport(
        settings.egress_allowlist, timeout_seconds=JWKS_TIMEOUT_SECONDS
    )
    return HttpJwksSource(url, transport)


def identity_provider(env: Mapping[str, str], settings: Settings) -> OidcIdentityProvider:
    issuer = _required(env, "MULEMA_OIDC_ISSUER")
    if settings.environment == "production" and (
        not issuer.startswith("https://")
        or (split_destination(issuer)[1].endswith(DEV_ISSUER_SUFFIX))
    ):
        msg = "MULEMA_OIDC_ISSUER : émetteur https réel exigé en production"
        raise ConfigurationError(msg)
    raw_algorithms = env.get("MULEMA_OIDC_ALGORITHMS", "").strip()
    algorithms = (
        frozenset(a.strip() for a in raw_algorithms.split(",") if a.strip())
        if raw_algorithms
        else SUPPORTED_ALGORITHMS
    )
    raw_leeway = env.get("MULEMA_OIDC_LEEWAY_SECONDS", "").strip()
    try:
        leeway = int(raw_leeway) if raw_leeway else DEFAULT_LEEWAY_SECONDS
        config = OidcConfig(
            issuer=issuer,
            audience=_required(env, "MULEMA_OIDC_AUDIENCE"),
            algorithms=algorithms,
            organization_claim=env.get("MULEMA_OIDC_ORG_CLAIM", "").strip()
            or DEFAULT_ORGANIZATION_CLAIM,
            leeway_seconds=leeway,
        )
    except ValueError as exc:
        msg = "MULEMA_OIDC_* invalide (algorithmes RS256/ES256, tolérance 0 à 300 s)"
        raise ConfigurationError(msg) from exc
    return OidcIdentityProvider(config, _jwks_source(env, settings))


def rate_limits(env: Mapping[str, str]) -> RateLimits:
    try:
        proxies = parse_trusted_proxies(env.get("MULEMA_TRUSTED_PROXIES", ""))
    except ValueError as exc:
        msg = "MULEMA_TRUSTED_PROXIES : adresses ou réseaux IP séparés par des virgules"
        raise ConfigurationError(msg) from exc
    return RateLimits(trusted_proxies=proxies)


def build_modules(env: Mapping[str, str], settings: Settings, country: str) -> AppModules:
    clock = SystemClock()
    card_keys = CardKeys(_require_secret(env, "MULEMA_CARD_KEY"))
    try:
        deployment = load_deployment(country)
        metrics = MetricsRuntime.from_env(clock, env)
        joe_settings = JoeModelSettings.from_env(env)
    except ValueError as exc:
        msg = f"configuration invalide : {exc}"  # messages sans valeur secrète (noms seuls)
        raise ConfigurationError(msg) from exc
    if deployment.allowlist != settings.egress_allowlist:
        msg = "infra/deploy et la liste blanche chargée divergent"
        raise ConfigurationError(msg)
    return AppModules(
        members=MembersRuntime(clock=clock, card_keys=card_keys),
        payments=PaymentsRuntime(clock=clock, config=payments_config(env)),
        claims=ClaimsRuntime(
            healthos=build_healthos_client(deployment),
            qr_verifier=CardQrVerifier(card_keys),
            sms_sender=UnconfiguredSmsSender(),
            clock=clock,
        ),
        rules=RulesRuntime(clock=clock),
        joe=JoeRuntime(
            clock=clock,
            model=build_language_model(joe_settings),
            members=member_reader_factory(clock, card_keys),
        ),
        metrics=metrics,
    )


def build_app(env: Mapping[str, str]) -> FastAPI:
    """Application de production depuis ``env`` ; ``ConfigurationError`` si incomplète."""
    settings = Settings.from_mapping(env)
    country = _required(env, "MULEMA_COUNTRY")
    return create_app(
        settings,
        identity_provider=identity_provider(env, settings),
        modules=build_modules(env, settings, country),
        rate_limits=rate_limits(env),
    )


def app_factory() -> FastAPI:
    """Pour ``uvicorn api.main:app_factory --factory`` (journal JSON, environnement réel)."""
    configure_json_logging()
    return build_app(os.environ)


def _port(env: Mapping[str, str]) -> int:
    raw = env.get("MULEMA_HTTP_PORT", "").strip()
    if not raw:
        return DEFAULT_PORT
    if not raw.isdigit() or not 0 < int(raw) < 65536:  # noqa: PLR2004 — borne de port TCP
        msg = "MULEMA_HTTP_PORT invalide"
        raise ConfigurationError(msg)
    return int(raw)


def main() -> int:
    configure_json_logging()
    try:
        app = build_app(os.environ)
        port = _port(os.environ)
    except ConfigurationError as exc:
        log_event(logger, logging.CRITICAL, "startup.refused", reason=str(exc))
        return EXIT_CONFIGURATION
    config = uvicorn.Config(
        app,
        host=os.environ.get("MULEMA_HTTP_HOST", DEFAULT_HOST),
        port=port,
        log_config=None,  # journal JSON du logger « mulema » ; pas de format uvicorn
        access_log=False,  # le journal d'accès est celui de l'application (sans donnée)
        proxy_headers=False,  # X-Forwarded-For n'est lu que par la limitation de débit
        server_header=False,
        date_header=False,
        lifespan="on",  # échec du démarrage (rôle, base) = arrêt du processus
        timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_SECONDS,
    )
    server = uvicorn.Server(config)
    server.run()
    # uvicorn ne lève pas sur un échec de démarrage : il s'arrête sans servir.
    return 0 if server.started else 1


if __name__ == "__main__":
    sys.exit(main())
