"""NSS-MC — numéro de sécurité sociale MulemaCare.

Identifiant à vie d'une personne (pas d'une police). Dimensionné pour
20 milliards de vies, sans encoder le sexe ni la date de naissance.

Format compact 17 chiffres::

    S CCC NNNNNNNNNNN KK
    │  │            │  └─ 2 clés ISO/IEC 7064 Mod 97-10
    │  │            └──── 11 chiffres de série (10¹¹ = 100 Md / pays)
    │  └────────────────── ISO 3166-1 numérique (pays d'affiliation)
    └───────────────────── schéma (8 = v1 ; jamais 0 — Excel)

Capacité : 100 milliards de vies par pays, donc 20 milliards même si
toutes les vies sont affiliées à un seul pays (marge ×5). Le CSSA reste
le n° de carte / police ; le NSS-MC est l'identité civile.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import unicodedata
from datetime import date
from typing import Any

SCHEME = 8
SERIAL_DIGITS = 11
SERIAL_MOD = 10**SERIAL_DIGITS
UNKNOWN_ISO3N = 999
TARGET_LIVES = 20_000_000_000
PREVIEW_NS = b"NSS-MC-v1"

# iso2 → métadonnées. iso3n = ISO 3166-1 numeric.
COUNTRIES: dict[str, dict[str, Any]] = {
    "CM": {"iso2": "CM", "iso3n": 120, "label": "Cameroun", "zone": "local", "flag": "🇨🇲"},
    "SN": {"iso2": "SN", "iso3n": 686, "label": "Sénégal", "zone": "local", "flag": "🇸🇳"},
    "CI": {"iso2": "CI", "iso3n": 384, "label": "Côte d'Ivoire", "zone": "local", "flag": "🇨🇮"},
    "CG": {"iso2": "CG", "iso3n": 178, "label": "Congo-Brazzaville", "zone": "local", "flag": "🇨🇬"},
    "CD": {"iso2": "CD", "iso3n": 180, "label": "RDC", "zone": "local", "flag": "🇨🇩"},
    "MG": {"iso2": "MG", "iso3n": 450, "label": "Madagascar", "zone": "local", "flag": "🇲🇬"},
    "BJ": {"iso2": "BJ", "iso3n": 204, "label": "Bénin", "zone": "local", "flag": "🇧🇯"},
    "GA": {"iso2": "GA", "iso3n": 266, "label": "Gabon", "zone": "local", "flag": "🇬🇦"},
    "TG": {"iso2": "TG", "iso3n": 768, "label": "Togo", "zone": "local", "flag": "🇹🇬"},
    "NE": {"iso2": "NE", "iso3n": 562, "label": "Niger", "zone": "local", "flag": "🇳🇪"},
    "TD": {"iso2": "TD", "iso3n": 148, "label": "Tchad", "zone": "local", "flag": "🇹🇩"},
    "GN": {"iso2": "GN", "iso3n": 324, "label": "Guinée", "zone": "local", "flag": "🇬🇳"},
    "GW": {"iso2": "GW", "iso3n": 624, "label": "Guinée-Bissau", "zone": "local", "flag": "🇬🇼"},
    "GH": {"iso2": "GH", "iso3n": 288, "label": "Ghana", "zone": "local", "flag": "🇬🇭"},
    "DJ": {"iso2": "DJ", "iso3n": 262, "label": "Djibouti", "zone": "local", "flag": "🇩🇯"},
    "MR": {"iso2": "MR", "iso3n": 478, "label": "Mauritanie", "zone": "local", "flag": "🇲🇷"},
    "MA": {"iso2": "MA", "iso3n": 504, "label": "Maroc", "zone": "local", "flag": "🇲🇦"},
    "TN": {"iso2": "TN", "iso3n": 788, "label": "Tunisie", "zone": "local", "flag": "🇹🇳"},
    "ZA": {"iso2": "ZA", "iso3n": 710, "label": "Afrique du Sud", "zone": "local", "flag": "🇿🇦"},
    "MU": {"iso2": "MU", "iso3n": 480, "label": "Maurice", "zone": "local", "flag": "🇲🇺"},
    "HT": {"iso2": "HT", "iso3n": 332, "label": "Haïti", "zone": "diaspora", "flag": "🇭🇹"},
    "FR": {"iso2": "FR", "iso3n": 250, "label": "France", "zone": "diaspora", "flag": "🇫🇷"},
    "BE": {"iso2": "BE", "iso3n": 56, "label": "Belgique", "zone": "diaspora", "flag": "🇧🇪"},
    "CA": {"iso2": "CA", "iso3n": 124, "label": "Canada", "zone": "diaspora", "flag": "🇨🇦"},
    "US": {"iso2": "US", "iso3n": 840, "label": "États-Unis", "zone": "diaspora", "flag": "🇺🇸"},
    "GB": {"iso2": "GB", "iso3n": 826, "label": "Royaume-Uni", "zone": "diaspora", "flag": "🇬🇧"},
    "ES": {"iso2": "ES", "iso3n": 724, "label": "Espagne", "zone": "diaspora", "flag": "🇪🇸"},
    "IT": {"iso2": "IT", "iso3n": 380, "label": "Italie", "zone": "diaspora", "flag": "🇮🇹"},
    "PL": {"iso2": "PL", "iso3n": 616, "label": "Pologne", "zone": "diaspora", "flag": "🇵🇱"},
    "RO": {"iso2": "RO", "iso3n": 642, "label": "Roumanie", "zone": "diaspora", "flag": "🇷🇴"},
    "BS": {"iso2": "BS", "iso3n": 44, "label": "Bahamas", "zone": "diaspora", "flag": "🇧🇸"},
    "AU": {"iso2": "AU", "iso3n": 36, "label": "Australie", "zone": "diaspora", "flag": "🇦🇺"},
    "XX": {"iso2": "XX", "iso3n": UNKNOWN_ISO3N, "label": "Non classé", "zone": "unknown", "flag": "🏳️"},
}

# Clés déjà repliées (fold). Les plus spécifiques d'abord pour le match contains.
_ALIAS_EXACT: dict[str, str] = {
    "cameroun": "CM",
    "cameroon": "CM",
    "kamerun": "CM",
    "camero": "CM",
    "cameron": "CM",
    "camerou": "CM",
    "camee": "CM",
    "camer": "CM",
    "came": "CM",
    "cam": "CM",
    "ca": "CM",
    "senegal": "SN",
    "senagal": "SN",
    "sengal": "SN",
    "sene": "SN",
    "sen": "SN",
    "se": "SN",
    "dakar": "SN",
    "cote d ivoire": "CI",
    "cote d ivoir": "CI",
    "cote divoire": "CI",
    "cote di": "CI",
    "cote": "CI",
    "ivory coast": "CI",
    "ci": "CI",
    "congo brazzaville": "CG",
    "congo brazza": "CG",
    "republique du congo": "CG",
    "republic of the congo": "CG",
    "rep congo": "CG",
    "brazzaville": "CG",
    "congo": "CG",
    "cong": "CG",
    "rdc": "CD",
    "rd congo": "CD",
    "congo rdc": "CD",
    "congo kinshasa": "CD",
    "republique democratique du congo": "CD",
    "republique democratique du": "CD",
    "democratic republic of the congo": "CD",
    "madagascar": "MG",
    "madagasacar": "MG",
    "madagascat": "MG",
    "mada": "MG",
    "nosy be": "MG",
    "benin": "BJ",
    "gabon": "GA",
    "gab": "GA",
    "togo": "TG",
    "niger": "NE",
    "tchad": "TD",
    "guinee bissau": "GW",
    "guinee": "GN",
    "ghana": "GH",
    "djibouti": "DJ",
    "mauritanie": "MR",
    "maroc": "MA",
    "morocco": "MA",
    "tunisie": "TN",
    "afrique du sud": "ZA",
    "ile maurice": "MU",
    "maurice": "MU",
    "haiti": "HT",
    "hai": "HT",
    "france": "FR",
    "francia": "FR",
    "franca": "FR",
    "fran": "FR",
    "fra": "FR",
    "fr": "FR",
    "martinique": "FR",
    "milhaud": "FR",
    "belgique": "BE",
    "belgium": "BE",
    "bel": "BE",
    "canada": "CA",
    "etats unis": "US",
    "united states": "US",
    "usa": "US",
    "united kingdom": "GB",
    "espagne": "ES",
    "italie": "IT",
    "italy": "IT",
    "pologne": "PL",
    "romania": "RO",
    "roumanie": "RO",
    "bahamas": "BS",
    "australie": "AU",
    "au": "AU",
}


def fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _country_record(iso2: str) -> dict[str, Any]:
    rec = COUNTRIES[iso2]
    return {
        "iso2": rec["iso2"],
        "iso3n": rec["iso3n"],
        "iso3n_pad": f"{rec['iso3n']:03d}",
        "label": rec["label"],
        "zone": rec["zone"],
        "flag": rec["flag"],
        "raw": "",
        "classified": iso2 != "XX",
    }


def normalize_country(raw: str) -> dict[str, Any]:
    """Map a free-text `pays` field to ISO 3166-1 + zone MulemaCare."""
    original = (raw or "").strip()
    key = fold(original)
    iso2 = "XX"
    if key:
        if key in _ALIAS_EXACT:
            iso2 = _ALIAS_EXACT[key]
        else:
            for alias, code in sorted(_ALIAS_EXACT.items(), key=lambda kv: -len(kv[0])):
                if len(alias) < 4:
                    continue
                if alias in key or key in alias:
                    iso2 = code
                    break
    rec = _country_record(iso2)
    rec["raw"] = original
    return rec


def iso7064_mod97_10(payload: str) -> str:
    """2 check digits; same family as IBAN. Catches most swap/typo errors."""
    if not payload.isdigit():
        raise ValueError("payload must be digits")
    remainder = int(payload + "00") % 97
    return f"{98 - remainder:02d}"


def compact_nss(scheme: int, iso3n: int, serial: int) -> str:
    if not 1 <= scheme <= 9:
        raise ValueError("scheme must be 1-9")
    if not 0 <= iso3n <= 999:
        raise ValueError("iso3n out of range")
    if not 0 <= serial < SERIAL_MOD:
        raise ValueError("serial out of range")
    payload = f"{scheme}{iso3n:03d}{serial:0{SERIAL_DIGITS}d}"
    return payload + iso7064_mod97_10(payload)


def display_nss(compact: str) -> str:
    digits = re.sub(r"\D", "", compact)
    if len(digits) != 17:
        return compact
    return f"NSS-{digits[0]}-{digits[1:4]}-{digits[4:15]}-{digits[15:]}"


def parse_nss(value: str) -> dict[str, Any] | None:
    compact = re.sub(r"\D", "", value or "")
    if len(compact) != 17 or not compact.isdigit():
        return None
    scheme = int(compact[0])
    iso3n = int(compact[1:4])
    serial = int(compact[4:15])
    check = compact[15:]
    payload = compact[:15]
    valid = iso7064_mod97_10(payload) == check
    iso2 = next((c["iso2"] for c in COUNTRIES.values() if c["iso3n"] == iso3n), "XX")
    meta = COUNTRIES.get(iso2, COUNTRIES["XX"])
    return {
        "compact": compact,
        "display": display_nss(compact),
        "scheme": scheme,
        "iso3n": iso3n,
        "iso2": iso2,
        "label": meta["label"],
        "serial": serial,
        "check": check,
        "valid": valid,
    }


def validate_nss(value: str) -> bool:
    parsed = parse_nss(value)
    return bool(parsed and parsed["valid"] and parsed["scheme"] == SCHEME)


def preview_serial(iso3n: int, person_key: str) -> int:
    """Deterministic serial for CRM preview (not the production allocator)."""
    digest = hashlib.sha256(PREVIEW_NS + f"|{iso3n:03d}|{person_key}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % SERIAL_MOD


def issue_preview_nss(iso3n: int, person_key: str, *, scheme: int = SCHEME) -> dict[str, Any]:
    serial = preview_serial(iso3n, person_key)
    compact = compact_nss(scheme, iso3n, serial)
    parsed = parse_nss(compact)
    assert parsed is not None
    return parsed


def issue_cssa_card(*, year: int | None = None) -> str:
    """Digital insurance card. Never encodes bronze/silver/gold/platinium."""
    yy = f"{(year if year is not None else date.today().year) % 100:02d}"
    return f"CSSA-{yy}-{secrets.token_hex(4).upper()}"


def cssa_encodes_formula(cssa: str) -> bool:
    blob = (cssa or "").lower()
    return any(token in blob for token in ("bronze", "silver", "gold", "platinium", "platinum", "formule"))


def issue_sequential_nss(iso3n: int, counter: int, *, scheme: int = SCHEME) -> dict[str, Any]:
    """Production allocator: monotonic counter per country, never reused."""
    if not 0 <= counter < SERIAL_MOD:
        raise ValueError("counter exhausted for this country")
    compact = compact_nss(scheme, iso3n, counter)
    parsed = parse_nss(compact)
    assert parsed is not None
    return parsed


def capacity() -> dict[str, Any]:
    per_country = SERIAL_MOD
    return {
        "target_lives": TARGET_LIVES,
        "serial_digits": SERIAL_DIGITS,
        "per_country": per_country,
        "headroom_x": per_country / TARGET_LIVES,
        "legacy_cssa_per_year": 16**8,
        "cssa_format": "CSSA-YY-XXXXXXXX",
        "cssa_encodes_plan": False,
        "total_digits": 17,
        "scheme": SCHEME,
        "unknown_iso3n": UNKNOWN_ISO3N,
        "encodes_sex": False,
        "encodes_birth": False,
        "check_algo": "ISO/IEC 7064 Mod 97-10",
    }


def spec() -> dict[str, Any]:
    return {
        "name": "NSS-MC",
        "version": "1",
        "format": "S-CCC-NNNNNNNNNNN-KK",
        "human": "NSS-8-120-00000001234-17",
        "rules": [
            "Identité à vie ≠ n° de carte CSSA (police / cotisation).",
            "La carte CSSA n'est pas une formule Bronze/Silver/Gold/Platinium.",
            "Jamais de sexe, date ou lieu de naissance dans le numéro (RGPD).",
            "Jamais de sexe, date ou lieu de naissance dans le numéro (RGPD).",
            "Série monotone par pays (séquence PostgreSQL) — jamais réutilisée.",
            "Le preview CRM est un hash stable, pas l'allocateur de production.",
            "Contrôle HITL avant activation d'une carte liée à un NSS.",
        ],
        "capacity": capacity(),
        "countries": [
            {
                "iso2": c["iso2"],
                "iso3n": c["iso3n"],
                "iso3n_pad": f"{c['iso3n']:03d}",
                "label": c["label"],
                "zone": c["zone"],
                "flag": c["flag"],
            }
            for c in COUNTRIES.values()
            if c["iso2"] != "XX"
        ],
    }
