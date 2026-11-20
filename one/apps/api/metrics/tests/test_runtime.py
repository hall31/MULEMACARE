"""Configuration de la mesure (CR-P2-02) : clé de pseudonymisation hors base et hors dépôt.

La clé vient de l'environnement (``MULEMA_METRICS_PSEUDONYM_KEY``, hexadécimal, 32 octets au
moins) ; sans elle, l'application ne démarre pas (aucune clé par défaut dans le code). Elle
n'apparaît jamais dans une représentation de l'objet (journaux, traces d'erreur).
"""

from __future__ import annotations

import secrets
from datetime import UTC, date, datetime

import pytest

from api.metrics.runtime import KEY_ENV, KEY_SINCE_ENV, RETENTION_ENV, MetricsRuntime


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 10, 1, tzinfo=UTC)


def test_cle_lue_dans_l_environnement() -> None:
    key = secrets.token_hex(32)
    runtime = MetricsRuntime.from_env(_Clock(), {KEY_ENV: key})
    assert runtime.pseudonym_key == bytes.fromhex(key)
    assert runtime.pseudonym_key_since is None


@pytest.mark.parametrize(
    "env",
    [
        pytest.param({}, id="cle-absente"),
        pytest.param({KEY_ENV: ""}, id="cle-vide"),
        pytest.param({KEY_ENV: "pas-de-l-hexadecimal"}, id="cle-non-hexadecimale"),
        pytest.param({KEY_ENV: "ab" * 31}, id="cle-trop-courte"),
    ],
)
def test_sans_cle_valide_pas_de_demarrage(env: dict[str, str]) -> None:
    with pytest.raises(ValueError, match=KEY_ENV):
        MetricsRuntime.from_env(_Clock(), env)


def test_cle_trop_courte_refusee_meme_sans_l_environnement() -> None:
    with pytest.raises(ValueError, match="32 octets"):
        MetricsRuntime(clock=_Clock(), pseudonym_key=b"\x01" * 31)


def test_la_cle_n_apparait_dans_aucune_representation() -> None:
    key = secrets.token_bytes(32)
    runtime = MetricsRuntime(clock=_Clock(), pseudonym_key=key)
    assert key.hex() not in repr(runtime)
    assert repr(key) not in repr(runtime)


def test_rotation_datee_et_retention() -> None:
    runtime = MetricsRuntime.from_env(
        _Clock(),
        {KEY_ENV: secrets.token_hex(32), KEY_SINCE_ENV: "2026-10-04", RETENTION_ENV: "90"},
    )
    assert runtime.pseudonym_key_since == date(2026, 10, 4)
    assert runtime.retention_days == 90


def test_date_de_rotation_invalide_refusee() -> None:
    with pytest.raises(ValueError, match=KEY_SINCE_ENV):
        MetricsRuntime.from_env(_Clock(), {KEY_ENV: secrets.token_hex(32), KEY_SINCE_ENV: "hier"})
