"""Cartes à QR dynamique (R2) : secret par carte scellé, code qui change toutes les 30 s.

Secret de carte : 32 octets aléatoires, stockés dans ``cards.qr_secret_ciphertext`` sous forme
scellée par une clé de l'application (hors base, ``MULEMA_CARD_KEY``), au format 2 (phase 4) :

    blob = 0x02 || id_clé(1) || nonce(12) || AES-256-GCM(clé, nonce, secret, ad)
    clé  = HKDF-SHA256(clé maîtresse, info="mulema-card:aes-256-gcm:v2")
    ad   = "mulema-card-secret:v2" || id_clé || organisation || carte

(``cryptography``, specs/DEPENDENCIES.md). Nonce aléatoire par scellement ; les données associées
lient le blob à SA carte et SON organisation (un blob recopié est refusé). ``id_clé`` permet la
rotation : la clé courante scelle, les clés retirées ne font qu'ouvrir, et tout blob lu sous une
clé retirée est rescellé sous la clé courante (``reseal_stale`` pour le faire par lot).

Format 1 (L4, avant la phase 4 : flot HMAC-SHA256 + étiquette HMAC) : LU SEULEMENT, pour que les
cartes déjà émises restent valides, et rescellé au format 2 à la première lecture. À supprimer
quand plus aucune carte n'est au format 1 (docs/SECURITY.md, « Rotation et ancien format »).

QR : ``MC1.<carte>.<fenêtre>.<code>`` où ``fenêtre`` = temps Unix // 30 et ``code`` = 20
premiers caractères hexadécimaux de HMAC-SHA256(secret, carte:fenêtre). Une fenêtre de
tolérance en arrière (horloge du téléphone légèrement en retard) est acceptée. Usage unique
(Q-P1-06) : si une garde de rejeu est branchée (``CardQrVerifier.replay_guard``), une fenêtre
consommée par une identification n'en rouvre pas d'autre, ni la fenêtre précédente.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, Protocol, cast
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.clock import ensure_utc

SECRET_BYTES: Final = 32
WINDOW_SECONDS: Final = 30
TOLERATED_PAST_WINDOWS: Final = 1
_CODE_HEX: Final = 20
_QR: Final = re.compile(r"^MC1\.([0-9a-f]{32})\.([0-9]{1,12})\.([0-9a-f]{20})$")

# Format 2 (courant) : AES-256-GCM.
_V2: Final = 2
GCM_NONCE_BYTES: Final = 12
GCM_TAG_BYTES: Final = 16
_V2_SIZE: Final = 2 + GCM_NONCE_BYTES + SECRET_BYTES + GCM_TAG_BYTES
_HKDF_INFO: Final = b"mulema-card:aes-256-gcm:v2"
_AD_PREFIX: Final = b"mulema-card-secret:v2"
_MAX_KEY_ID: Final = 255

# Format 1 (ancien, lecture seule).
_V1: Final = 1
_V1_NONCE_BYTES: Final = 16
_V1_TAG_BYTES: Final = 32
_V1_SIZE: Final = 1 + _V1_NONCE_BYTES + SECRET_BYTES + _V1_TAG_BYTES


class SealError(ValueError):
    """Blob de secret de carte altéré, recopié ou scellé avec une clé inconnue."""


@dataclass(frozen=True, slots=True)
class OpenedSecret:
    secret: bytes
    needs_reseal: bool  # ancien format ou clé retirée : à resceller sous la clé courante


def _check_key(key: bytes) -> None:
    if len(key) < SECRET_BYTES:
        msg = "clé de carte trop courte (32 octets minimum)"
        raise ValueError(msg)


def _aes_key(master_key: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(master_key)


def _ad(key_id: int, organization_id: UUID, card_id: UUID) -> bytes:
    return _AD_PREFIX + bytes([key_id]) + organization_id.bytes + card_id.bytes


def _open_v1(master_key: bytes, blob: bytes, context: bytes) -> bytes | None:
    """Ancien format (L4) : ``None`` si l'étiquette ne correspond pas à cette clé."""

    def derive(label: bytes) -> bytes:
        return hmac.new(master_key, b"mulema-card:" + label, hashlib.sha256).digest()

    nonce = blob[1 : 1 + _V1_NONCE_BYTES]
    cipher = blob[1 + _V1_NONCE_BYTES : 1 + _V1_NONCE_BYTES + SECRET_BYTES]
    tag = blob[1 + _V1_NONCE_BYTES + SECRET_BYTES :]
    wanted = hmac.new(derive(b"mac"), blob[:1] + nonce + cipher + context, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, wanted):
        return None
    stream = hmac.new(derive(b"enc"), nonce + context, hashlib.sha256).digest()
    return bytes(a ^ b for a, b in zip(cipher, stream, strict=True))


@dataclass(frozen=True, slots=True)
class CardKeys:
    """Clés de l'application, jamais stockées en base.

    ``master_key`` (32 octets au moins) scelle sous ``key_id`` ; ``retired`` liste les clés
    précédentes ``(id, clé)`` qui ne servent plus qu'à ouvrir (rotation).
    """

    master_key: bytes
    key_id: int = 1
    retired: tuple[tuple[int, bytes], ...] = ()
    _aes: dict[int, AESGCM] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _check_key(self.master_key)
        ids = [self.key_id, *(kid for kid, _ in self.retired)]
        if any(not 1 <= kid <= _MAX_KEY_ID for kid in ids):
            msg = "identifiant de clé de carte hors de [1, 255]"
            raise ValueError(msg)
        if len(set(ids)) != len(ids):
            msg = "identifiants de clé de carte en double"
            raise ValueError(msg)
        for _, key in self.retired:
            _check_key(key)
        aes = {self.key_id: AESGCM(_aes_key(self.master_key))}
        aes.update({kid: AESGCM(_aes_key(key)) for kid, key in self.retired})
        object.__setattr__(self, "_aes", aes)

    def seal(self, secret: bytes, *, organization_id: UUID, card_id: UUID) -> bytes:
        if len(secret) != SECRET_BYTES:
            msg = "secret de carte de taille inattendue"
            raise ValueError(msg)
        nonce = secrets.token_bytes(GCM_NONCE_BYTES)
        sealed = self._aes[self.key_id].encrypt(
            nonce, secret, _ad(self.key_id, organization_id, card_id)
        )
        return bytes([_V2, self.key_id]) + nonce + sealed

    def open_versioned(self, blob: bytes, *, organization_id: UUID, card_id: UUID) -> OpenedSecret:
        if len(blob) == _V2_SIZE and blob[0] == _V2:
            key_id = blob[1]
            aes = self._aes.get(key_id)
            if aes is None:
                raise SealError("secret de carte scellé par une clé inconnue")
            try:
                secret = aes.decrypt(
                    blob[2 : 2 + GCM_NONCE_BYTES],
                    blob[2 + GCM_NONCE_BYTES :],
                    _ad(key_id, organization_id, card_id),
                )
            except InvalidTag as exc:
                raise SealError("secret de carte altéré") from exc
            return OpenedSecret(secret, needs_reseal=key_id != self.key_id)
        if len(blob) == _V1_SIZE and blob[0] == _V1:
            context = organization_id.bytes + card_id.bytes
            for key in (self.master_key, *(k for _, k in self.retired)):
                secret_v1 = _open_v1(key, blob, context)
                if secret_v1 is not None:
                    return OpenedSecret(secret_v1, needs_reseal=True)
            raise SealError("secret de carte altéré")
        raise SealError("format de secret de carte inconnu")

    def open(self, blob: bytes, *, organization_id: UUID, card_id: UUID) -> bytes:
        return self.open_versioned(blob, organization_id=organization_id, card_id=card_id).secret


def new_secret() -> bytes:
    return secrets.token_bytes(SECRET_BYTES)


def window_of(moment: datetime) -> int:
    return int(ensure_utc(moment).timestamp()) // WINDOW_SECONDS


def _code(secret: bytes, card_id: UUID, window: int) -> str:
    message = f"{card_id.hex}:{window}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()[:_CODE_HEX]


def qr_payload(secret: bytes, card_id: UUID, moment: datetime) -> str:
    window = window_of(moment)
    return f"MC1.{card_id.hex}.{window}.{_code(secret, card_id, window)}"


def parse_qr(payload: str) -> tuple[UUID, int, str] | None:
    match = _QR.fullmatch(payload)
    if match is None:
        return None
    return UUID(hex=match.group(1)), int(match.group(2)), match.group(3)


def code_matches(secret: bytes, card_id: UUID, window: int, code: str, moment: datetime) -> bool:
    current = window_of(moment)
    if not current - TOLERATED_PAST_WINDOWS <= window <= current:
        return False
    return hmac.compare_digest(_code(secret, card_id, window), code)


# --- Garde de rejeu du QR (Q-P1-06), sans changement de contrat --------------------------------


class QrReplayGuard(Protocol):
    """Mémoire des fenêtres de QR déjà consommées, par (organisation, carte).

    ``consume`` renvoie ``True`` si ``window`` est STRICTEMENT postérieure à la dernière fenêtre
    consommée pour cette carte (et l'enregistre), ``False`` sinon : un QR ne sert qu'une fois, et
    revenir à la fenêtre tolérée après usage de la courante est refusé. L'opération doit être
    atomique. Implémentation partagée entre processus (Redis, script Lua « lire, comparer,
    écrire avec expiration ») : voir docs/SECURITY.md ; ``InMemoryQrReplayGuard`` ne protège
    qu'à l'intérieur d'un processus.
    """

    async def consume(
        self, *, organization_id: UUID, card_id: UUID, window: int, now: datetime
    ) -> bool: ...


class InMemoryQrReplayGuard:
    """Garde de rejeu en mémoire d'un processus (un seul processus d'API, ou tests).

    Bornée : une fenêtre que plus aucun QR acceptable ne peut précéder est oubliée (au plus une
    purge par fenêtre de 30 s). Atomique : aucun ``await`` entre la lecture et l'écriture, et un
    verrou de fil pour un usage depuis plusieurs boucles.
    """

    def __init__(self) -> None:
        self._last: dict[tuple[UUID, UUID], int] = {}
        self._lock = threading.Lock()
        self._purged_at: int | None = None

    def __len__(self) -> int:
        return len(self._last)

    async def consume(
        self, *, organization_id: UUID, card_id: UUID, window: int, now: datetime
    ) -> bool:
        current = window_of(now)
        key = (organization_id, card_id)
        with self._lock:
            if self._purged_at != current:
                oldest_acceptable = current - TOLERATED_PAST_WINDOWS
                self._last = {k: w for k, w in self._last.items() if w >= oldest_acceptable}
                self._purged_at = current
            last = self._last.get(key)
            if last is not None and window <= last:
                return False
            self._last[key] = window
            return True


# --- Accès base (dans la transaction de l'appelant, organisation déjà positionnée) ---------


async def _store_resealed(
    session: AsyncSession, keys: CardKeys, *, ids: tuple[UUID, UUID], old: bytes, secret: bytes
) -> bool:
    """Rescelle sous la clé courante ; comparer-échanger sur l'ancien blob (lecteurs concurrents).

    ``ids`` = (organisation, carte).
    """
    organization_id, card_id = ids
    new = keys.seal(secret, organization_id=organization_id, card_id=card_id)
    result = await session.execute(
        text(
            "UPDATE cards SET qr_secret_ciphertext = :new WHERE organization_id = :org "
            "AND id = :card AND qr_secret_ciphertext = :old RETURNING id"
        ),
        {"new": new, "org": organization_id, "card": card_id, "old": old},
    )
    return result.first() is not None


async def _active_secret(
    session: AsyncSession, keys: CardKeys, organization_id: UUID, card_id: UUID
) -> bytes | None:
    row = (
        await session.execute(
            text(
                "SELECT qr_secret_ciphertext FROM cards WHERE organization_id = :org "
                "AND id = :card AND status = 'active'"
            ),
            {"org": organization_id, "card": card_id},
        )
    ).first()
    if row is None:
        return None
    blob = bytes(row[0])
    opened = keys.open_versioned(blob, organization_id=organization_id, card_id=card_id)
    if opened.needs_reseal:
        await _store_resealed(
            session, keys, ids=(organization_id, card_id), old=blob, secret=opened.secret
        )
    return opened.secret


async def reseal_stale(
    session: AsyncSession, keys: CardKeys, organization_id: UUID, *, limit: int
) -> int:
    """Rescelle par lot les cartes (actives ou non) encore à l'ancien format ou sous une clé
    retirée, dans l'organisation positionnée. Renvoie le nombre de cartes rescellées ; à
    relancer jusqu'à 0 avant de retirer une clé ou de supprimer la lecture du format 1."""
    rows = (
        await session.execute(
            text(
                "SELECT id, qr_secret_ciphertext FROM cards WHERE organization_id = :org "
                "AND NOT (get_byte(qr_secret_ciphertext, 0) = :v2 "
                "AND get_byte(qr_secret_ciphertext, 1) = :kid) "
                "ORDER BY id LIMIT :limit FOR UPDATE SKIP LOCKED"
            ),
            {"org": organization_id, "v2": _V2, "kid": keys.key_id, "limit": limit},
        )
    ).all()
    done = 0
    for row in rows:
        card_id, blob = cast("UUID", row[0]), bytes(cast("bytes", row[1]))
        opened = keys.open_versioned(blob, organization_id=organization_id, card_id=card_id)
        if await _store_resealed(
            session, keys, ids=(organization_id, card_id), old=blob, secret=opened.secret
        ):
            done += 1
    return done


async def current_qr_payload(
    session: AsyncSession, keys: CardKeys, organization_id: UUID, card_id: UUID, moment: datetime
) -> str:
    """QR à afficher maintenant pour une carte active (espace adhérent, hors contrat HTTP)."""
    secret = await _active_secret(session, keys, organization_id, card_id)
    if secret is None:
        msg = "carte inconnue ou révoquée"
        raise LookupError(msg)
    return qr_payload(secret, card_id, moment)


async def _verified_card(
    session: AsyncSession, keys: CardKeys, organization_id: UUID, payload: str, moment: datetime
) -> tuple[UUID, int] | None:
    """(carte, fenêtre) d'un QR authentique, dans sa fenêtre, d'une carte active, sinon None."""
    parsed = parse_qr(payload)
    if parsed is None:
        return None
    card_id, window, code = parsed
    try:
        secret = await _active_secret(session, keys, organization_id, card_id)
    except SealError:
        return None
    if secret is None or not code_matches(secret, card_id, window, code, moment):
        return None
    return card_id, window


async def verify_qr_payload(
    session: AsyncSession, keys: CardKeys, organization_id: UUID, payload: str, moment: datetime
) -> UUID | None:
    """Point d'entrée du comptoir (L5) : carte active reconnue, ou ``None`` (ID-06). Sans état."""
    found = await _verified_card(session, keys, organization_id, payload, moment)
    return None if found is None else found[0]


@dataclass(frozen=True, slots=True)
class CardQrVerifier:
    """Adaptateur du port ``QrVerifier`` du comptoir (L5) sur la vérification L4 ci-dessus.

    ``replay_guard`` : QR à usage unique (Q-P1-06). ``None`` garde le comportement L5 (QR
    réutilisable pendant sa fenêtre et la suivante) ; l'assemblage de production doit en passer
    une (docs/SECURITY.md). Un QR rejoué est refusé comme une carte inconnue (ID-06) : aucun
    code d'erreur nouveau dans le contrat.
    """

    keys: CardKeys
    replay_guard: QrReplayGuard | None = None

    async def resolve(
        self, qr_payload: str, *, at: datetime, session: AsyncSession, organization_id: UUID
    ) -> UUID | None:
        found = await _verified_card(session, self.keys, organization_id, qr_payload, at)
        if found is None:
            return None
        card_id, window = found
        # La garde n'est consultée qu'APRÈS la vérification du code : un QR forgé ou expiré ne
        # consomme rien (pas de déni de service par QR inventé).
        if self.replay_guard is not None and not await self.replay_guard.consume(
            organization_id=organization_id, card_id=card_id, window=window, now=at
        ):
            return None
        return card_id
