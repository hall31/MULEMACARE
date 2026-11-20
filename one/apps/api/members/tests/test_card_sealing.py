"""Scellement du secret de carte (phase 4, voie 2) et QR à usage unique côté serveur.

- Format 2 : AES-256-GCM (``cryptography``), nonce aléatoire de 12 octets, données associées =
  version, identifiant de clé, organisation et carte ; clé dérivée par HKDF-SHA256 de la clé
  maîtresse ; identifiant de clé sur un octet pour la rotation.
- Format 1 (flot HMAC + étiquette HMAC, avant la phase 4) : lu, jamais écrit, et rescellé au
  format 2 à la première lecture.
- QR : une fenêtre consommée ne rouvre plus d'identification (Q-P1-06), sans changer le contrat.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from api.members import cards
from api.members.cards import CardKeys, CardQrVerifier, InMemoryQrReplayGuard, SealError
from api.members.tests.support import L4Env, enroll
from api.members.tests.test_cards import _issue, _keys, _qr, _verify

ORG = uuid.UUID("00000000-0000-4000-8000-0000000000a1")
CARD = uuid.UUID("00000000-0000-4000-8000-0000000000c1")
OTHER = uuid.UUID("00000000-0000-4000-8000-0000000000c2")
T0 = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)


def _master() -> bytes:
    return secrets.token_bytes(32)


def legacy_v1_seal(master: bytes, secret: bytes, organization_id: UUID, card_id: UUID) -> bytes:
    """Réimplémentation INDÉPENDANTE du format 1 (L4), pour fabriquer des cartes « anciennes »."""

    def derive(label: bytes) -> bytes:
        return hmac.new(master, b"mulema-card:" + label, hashlib.sha256).digest()

    context = organization_id.bytes + card_id.bytes
    nonce = secrets.token_bytes(16)
    stream = hmac.new(derive(b"enc"), nonce + context, hashlib.sha256).digest()
    cipher = bytes(a ^ b for a, b in zip(secret, stream, strict=True))
    tag = hmac.new(derive(b"mac"), b"\x01" + nonce + cipher + context, hashlib.sha256).digest()
    return b"\x01" + nonce + cipher + tag


# --- Format 2 : AES-256-GCM ----------------------------------------------------------------------


def test_format_2_aes_gcm_documente() -> None:
    master, secret = _master(), cards.new_secret()
    blob = CardKeys(master, key_id=7).seal(secret, organization_id=ORG, card_id=CARD)
    assert blob[0] == 2
    assert blob[1] == 7
    assert len(blob) == 1 + 1 + 12 + 32 + 16
    # Déchiffrement indépendant avec la construction documentée (interopérabilité, audit).
    key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=b"mulema-card:aes-256-gcm:v2"
    ).derive(master)
    aad = b"mulema-card-secret:v2" + bytes([7]) + ORG.bytes + CARD.bytes
    assert AESGCM(key).decrypt(blob[2:14], blob[14:], aad) == secret


def test_aller_retour_et_nonce_unique() -> None:
    keys, secret = CardKeys(_master()), cards.new_secret()
    blobs = [keys.seal(secret, organization_id=ORG, card_id=CARD) for _ in range(500)]
    assert len({b[2:14] for b in blobs}) == 500
    assert all(keys.open(b, organization_id=ORG, card_id=CARD) == secret for b in blobs[:5])


@pytest.mark.parametrize(
    ("org", "card"),
    [pytest.param(ORG, OTHER, id="autre-carte"), pytest.param(OTHER, CARD, id="autre-org")],
)
def test_blob_recopie_sur_une_autre_carte_refuse(org: UUID, card: UUID) -> None:
    keys = CardKeys(_master())
    blob = keys.seal(cards.new_secret(), organization_id=ORG, card_id=CARD)
    with pytest.raises(SealError):
        keys.open(blob, organization_id=org, card_id=card)


@pytest.mark.parametrize("index", [0, 1, 2, 13, 14, 45, 46, 61])
def test_blob_altere_refuse(index: int) -> None:
    keys = CardKeys(_master())
    blob = bytearray(keys.seal(cards.new_secret(), organization_id=ORG, card_id=CARD))
    blob[index] ^= 0x01
    with pytest.raises(SealError):
        keys.open(bytes(blob), organization_id=ORG, card_id=CARD)


@pytest.mark.parametrize("size", [0, 1, 14, 61, 63, 81])
def test_blob_de_mauvaise_taille_refuse(size: int) -> None:
    keys = CardKeys(_master())
    blob = keys.seal(cards.new_secret(), organization_id=ORG, card_id=CARD)
    with pytest.raises(SealError):
        keys.open((blob * 2)[:size], organization_id=ORG, card_id=CARD)


def test_autre_cle_maitresse_refusee() -> None:
    blob = CardKeys(_master()).seal(cards.new_secret(), organization_id=ORG, card_id=CARD)
    with pytest.raises(SealError):
        CardKeys(_master()).open(blob, organization_id=ORG, card_id=CARD)


# --- Format 1 (ancien) : lisible, à rescellé --------------------------------------------------


def test_ancien_format_lisible_et_signale_a_resceller() -> None:
    master, secret = _master(), cards.new_secret()
    legacy = legacy_v1_seal(master, secret, ORG, CARD)
    keys = CardKeys(master)
    assert keys.open(legacy, organization_id=ORG, card_id=CARD) == secret
    opened = keys.open_versioned(legacy, organization_id=ORG, card_id=CARD)
    assert (opened.secret, opened.needs_reseal) == (secret, True)
    fresh = keys.seal(secret, organization_id=ORG, card_id=CARD)
    assert keys.open_versioned(fresh, organization_id=ORG, card_id=CARD).needs_reseal is False


def test_ancien_format_altere_ou_recopie_refuse() -> None:
    master, secret = _master(), cards.new_secret()
    legacy = bytearray(legacy_v1_seal(master, secret, ORG, CARD))
    keys = CardKeys(master)
    with pytest.raises(SealError):
        keys.open(bytes(legacy), organization_id=ORG, card_id=OTHER)
    legacy[20] ^= 0x01
    with pytest.raises(SealError):
        keys.open(bytes(legacy), organization_id=ORG, card_id=CARD)


def test_ancien_format_scelle_par_une_cle_retiree() -> None:
    old, new, secret = _master(), _master(), cards.new_secret()
    legacy = legacy_v1_seal(old, secret, ORG, CARD)
    keys = CardKeys(new, key_id=2, retired=((1, old),))
    assert keys.open_versioned(legacy, organization_id=ORG, card_id=CARD).secret == secret


# --- Rotation de clé ----------------------------------------------------------------------------


def test_rotation_cle_retiree_lisible_puis_rescellee() -> None:
    old, new, secret = _master(), _master(), cards.new_secret()
    blob = CardKeys(old, key_id=1).seal(secret, organization_id=ORG, card_id=CARD)
    rotated = CardKeys(new, key_id=2, retired=((1, old),))
    opened = rotated.open_versioned(blob, organization_id=ORG, card_id=CARD)
    assert (opened.secret, opened.needs_reseal) == (secret, True)
    resealed = rotated.seal(secret, organization_id=ORG, card_id=CARD)
    assert resealed[1] == 2
    # Clé 1 oubliée : les blobs encore en clé 1 ne s'ouvrent plus.
    with pytest.raises(SealError):
        CardKeys(new, key_id=2).open(blob, organization_id=ORG, card_id=CARD)


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(lambda m: CardKeys(m[:31]), id="cle-courte"),
        pytest.param(lambda m: CardKeys(m, key_id=0), id="id-0"),
        pytest.param(lambda m: CardKeys(m, key_id=256), id="id-256"),
        pytest.param(lambda m: CardKeys(m, key_id=1, retired=((1, m),)), id="id-retire-courant"),
        pytest.param(lambda m: CardKeys(m, key_id=3, retired=((1, m), (1, m))), id="id-double"),
        pytest.param(lambda m: CardKeys(m, key_id=3, retired=((1, m[:8]),)), id="retiree-courte"),
    ],
)
def test_jeu_de_cles_invalide(build: Any) -> None:  # noqa: ANN401 — fabrique paramétrée
    with pytest.raises(ValueError):  # noqa: PT011 — message variable selon le défaut
        build(_master())


# --- En base : rescellement à la lecture, lot de rescellement -----------------------------------


def _blob(env: L4Env, card_id: str) -> bytes:
    return bytes(
        env.scalar("SELECT qr_secret_ciphertext FROM cards WHERE id = %s", (UUID(card_id),))
    )


def _to_legacy(env: L4Env, org: str, card_id: str) -> bytes:
    """Remplace le blob de la carte par le MÊME secret au format 1 (carte d'avant la phase 4)."""
    keys = _keys(env)
    org_id = env.orgs[org].id
    secret = keys.open(_blob(env, card_id), organization_id=org_id, card_id=UUID(card_id))
    legacy = legacy_v1_seal(keys.master_key, secret, org_id, UUID(card_id))
    env.rows(
        "UPDATE cards SET qr_secret_ciphertext = %s WHERE id = %s RETURNING id",
        (legacy, UUID(card_id)),
    )
    return secret


def test_carte_ancien_format_lisible_puis_rescellee_a_la_lecture(guarded: L4Env) -> None:
    env = guarded
    member = enroll(env, "a", date(2026, 10, 1))
    card = _issue(env, member, member["holder"]["person_id"])
    before = _qr(env, "a", card["id"])
    secret = _to_legacy(env, "a", card["id"])
    assert _blob(env, card["id"])[0] == 1

    assert _qr(env, "a", card["id"]) == before  # même secret, même QR
    resealed = _blob(env, card["id"])
    assert resealed[0] == 2
    assert resealed[1] == _keys(env).key_id
    keys = _keys(env)
    org_id = env.orgs["a"].id
    assert keys.open(resealed, organization_id=org_id, card_id=UUID(card["id"])) == secret
    assert _verify(env, "a", before) == UUID(card["id"])
    assert _blob(env, card["id"]) == resealed  # format courant : aucune réécriture


def test_verification_du_comptoir_resscelle_aussi(guarded: L4Env) -> None:
    env = guarded
    member = enroll(env, "a", date(2026, 10, 1))
    card = _issue(env, member, member["holder"]["person_id"])
    payload = _qr(env, "a", card["id"])
    _to_legacy(env, "a", card["id"])
    assert _verify(env, "a", payload) == UUID(card["id"])
    assert _blob(env, card["id"])[0] == 2


def test_rotation_en_base_et_lot_de_rescellement(guarded: L4Env) -> None:
    env = guarded
    member = enroll(env, "a", date(2026, 10, 1))
    holder = member["holder"]["person_id"]
    old_keys = _keys(env)
    org_id = env.orgs["a"].id
    ids = []
    for _ in range(3):
        dependent = env.client.post(
            f"/v1/members/{member['id']}/dependents",
            json={
                "person": {
                    "given_name": "Awa",
                    "family_name": "Fictive",
                    "birth_date": "2019-01-01",
                },
                "relationship": "enfant",
                "valid_from": "2026-10-01",
            },
            headers=env.auth("a", "gestionnaire"),
        ).json()
        ids.append(_issue(env, member, dependent["person_id"])["id"])
    ids.append(_issue(env, member, holder)["id"])
    _to_legacy(env, "a", ids[0])
    rotated = CardKeys(
        _master(), key_id=old_keys.key_id + 1, retired=((old_keys.key_id, old_keys.master_key),)
    )

    async def batch() -> tuple[int, int]:
        async with env.database.transaction(org_id) as session:
            first = await cards.reseal_stale(session, rotated, org_id, limit=100)
        async with env.database.transaction(org_id) as session:
            second = await cards.reseal_stale(session, rotated, org_id, limit=100)
        return first, second

    first, second = env.run(batch)
    assert first >= 4  # les cartes des tests précédents du module comptent aussi
    assert second == 0
    for card_id in ids:
        blob = _blob(env, card_id)
        assert (blob[0], blob[1]) == (2, rotated.key_id)
        with pytest.raises(SealError):
            old_keys.open(blob, organization_id=org_id, card_id=UUID(card_id))

    async def qr_with_rotated() -> str:
        async with env.database.transaction(org_id) as session:
            return await cards.current_qr_payload(
                session, rotated, org_id, UUID(ids[-1]), env.clock.now()
            )

    assert env.run(qr_with_rotated).startswith("MC1.")


def test_lot_de_rescellement_isole_par_organisation(guarded: L4Env) -> None:
    env = guarded
    member = enroll(env, "a", date(2026, 10, 1))
    card = _issue(env, member, member["holder"]["person_id"])
    _to_legacy(env, "a", card["id"])
    org_b = env.orgs["b"].id

    async def batch_b() -> int:
        async with env.database.transaction(org_b) as session:
            return await cards.reseal_stale(session, _keys(env), org_b, limit=100)

    assert env.run(batch_b) == 0
    assert _blob(env, card["id"])[0] == 1


# --- QR à usage unique (Q-P1-06), sans changement de contrat ------------------------------------


def _consume(guard: InMemoryQrReplayGuard, card: UUID, window: int, org: UUID = ORG) -> bool:
    return asyncio.run(guard.consume(organization_id=org, card_id=card, window=window, now=T0))


def test_garde_memoire_fenetre_consommee_une_seule_fois() -> None:
    guard = InMemoryQrReplayGuard()
    current = cards.window_of(T0)
    assert _consume(guard, CARD, current)
    assert not _consume(guard, CARD, current)  # rejeu
    assert not _consume(guard, CARD, current - 1)  # retour à la fenêtre tolérée
    assert _consume(guard, OTHER, current)  # autre carte
    assert _consume(guard, CARD, current, org=OTHER)  # autre organisation
    assert _consume(guard, CARD, current + 1)  # fenêtre suivante


def test_garde_memoire_concurrence_un_seul_gagnant() -> None:
    guard = InMemoryQrReplayGuard()
    window = cards.window_of(T0)

    async def race() -> list[bool]:
        return list(
            await asyncio.gather(
                *(
                    guard.consume(organization_id=ORG, card_id=CARD, window=window, now=T0)
                    for _ in range(50)
                )
            )
        )

    assert sorted(asyncio.run(race())) == [False] * 49 + [True]


def test_garde_memoire_bornee() -> None:
    guard = InMemoryQrReplayGuard()
    window = cards.window_of(T0)
    for _ in range(200):
        _consume(guard, uuid.uuid4(), window)
    assert len(guard) == 200
    later = T0 + timedelta(seconds=cards.WINDOW_SECONDS * (cards.TOLERATED_PAST_WINDOWS + 2))
    asyncio.run(
        guard.consume(organization_id=ORG, card_id=CARD, window=cards.window_of(later), now=later)
    )
    assert len(guard) == 1  # les fenêtres qui ne peuvent plus être présentées sont oubliées


def _resolve(env: L4Env, verifier: CardQrVerifier, org: str, payload: str) -> UUID | None:
    async def run() -> UUID | None:
        async with env.database.transaction(env.orgs[org].id) as session:
            return await verifier.resolve(
                payload, at=env.clock.now(), session=session, organization_id=env.orgs[org].id
            )

    return env.run(run)


def test_qr_rejoue_refuse_quand_la_garde_est_branchee(guarded: L4Env) -> None:
    env = guarded
    member = enroll(env, "a", date(2026, 10, 1))
    card = _issue(env, member, member["holder"]["person_id"])
    verifier = CardQrVerifier(_keys(env), replay_guard=InMemoryQrReplayGuard())
    payload = _qr(env, "a", card["id"])

    forged = payload[:-1] + ("0" if payload[-1] != "0" else "1")
    assert _resolve(env, verifier, "a", forged) is None  # un faux ne consomme rien
    assert _resolve(env, verifier, "b", payload) is None  # une autre organisation non plus
    assert _resolve(env, verifier, "a", payload) == UUID(card["id"])
    assert _resolve(env, verifier, "a", payload) is None  # rejeu (capture d'écran, photo)

    env.clock.advance(timedelta(seconds=cards.WINDOW_SECONDS))
    fresh = _qr(env, "a", card["id"])
    assert fresh != payload
    assert _resolve(env, verifier, "a", fresh) == UUID(card["id"])
    assert _resolve(env, verifier, "a", payload) is None  # fenêtre tolérée déjà dépassée


def test_sans_garde_le_comportement_l5_est_inchange(guarded: L4Env) -> None:
    env = guarded
    member = enroll(env, "a", date(2026, 10, 1))
    card = _issue(env, member, member["holder"]["person_id"])
    verifier = CardQrVerifier(_keys(env))
    payload = _qr(env, "a", card["id"])
    assert _resolve(env, verifier, "a", payload) == UUID(card["id"])
    assert _resolve(env, verifier, "a", payload) == UUID(card["id"])


def test_rescellement_concurrent_n_ecrase_pas_un_blob_plus_recent(guarded: L4Env) -> None:
    """Deux lecteurs rescellent la même carte : seul celui qui a lu le blob en place écrit."""
    env = guarded
    member = enroll(env, "a", date(2026, 10, 1))
    card = _issue(env, member, member["holder"]["person_id"])
    secret = _to_legacy(env, "a", card["id"])
    stale = _blob(env, card["id"])
    _qr(env, "a", card["id"])  # premier lecteur : rescelle
    winner = _blob(env, card["id"])
    assert winner != stale
    org_id = env.orgs["a"].id

    async def late_reader() -> bool:
        async with env.database.transaction(org_id) as session:
            return await cards._store_resealed(
                session, _keys(env), ids=(org_id, UUID(card["id"])), old=stale, secret=secret
            )

    assert env.run(late_reader) is False
    assert _blob(env, card["id"]) == winner
