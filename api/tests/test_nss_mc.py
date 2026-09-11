"""NSS-MC: 20 billion capacity, checksum, country aliases."""

from __future__ import annotations

from app.services.nss_mc import (
    SERIAL_MOD,
    TARGET_LIVES,
    compact_nss,
    issue_preview_nss,
    issue_sequential_nss,
    iso7064_mod97_10,
    normalize_country,
    parse_nss,
    validate_nss,
)


def test_capacity_covers_20_billion_in_one_country() -> None:
    assert SERIAL_MOD >= TARGET_LIVES
    assert SERIAL_MOD // TARGET_LIVES >= 5


def test_checksum_roundtrip_and_typo() -> None:
    compact = compact_nss(8, 120, 1234)
    assert len(compact) == 17
    assert validate_nss(compact)
    parsed = parse_nss(compact)
    assert parsed is not None
    assert parsed["iso3n"] == 120
    assert parsed["serial"] == 1234
    swapped = compact[:5] + compact[6] + compact[5] + compact[7:]
    if swapped != compact:
        assert not validate_nss(swapped)


def test_mod97_matches_iban_family() -> None:
    payload = "812000000001234"
    kk = iso7064_mod97_10(payload)
    assert len(kk) == 2
    assert int(payload + kk) % 97 == 1


def test_country_aliases_senegal_cameroon_rdc() -> None:
    assert normalize_country("SENEGAL")["iso2"] == "SN"
    assert normalize_country("Sénégal")["iso3n"] == 686
    assert normalize_country("Cameroon")["iso2"] == "CM"
    assert normalize_country("Ca")["iso2"] == "CM"
    assert normalize_country("République démocratique du Congo")["iso2"] == "CD"
    assert normalize_country("Congo")["iso2"] == "CG"
    assert normalize_country("Côte d'Ivoire")["iso2"] == "CI"
    assert normalize_country("zsdzdzd")["iso2"] == "XX"
    assert normalize_country("")["iso2"] == "XX"


def test_preview_stable_and_sequential_allocator() -> None:
    a = issue_preview_nss(120, "user-42")
    b = issue_preview_nss(120, "user-42")
    c = issue_preview_nss(120, "user-43")
    assert a["compact"] == b["compact"]
    assert a["compact"] != c["compact"]
    seq = issue_sequential_nss(686, 1)
    assert validate_nss(seq["display"])
    assert seq["serial"] == 1
    assert seq["iso3n"] == 686


def test_no_pii_in_spec_and_display_prefix() -> None:
    from app.services.nss_mc import cssa_encodes_formula, issue_cssa_card, spec

    s = spec()
    assert s["capacity"]["encodes_sex"] is False
    assert s["capacity"]["encodes_birth"] is False
    assert s["capacity"]["cssa_encodes_plan"] is False
    assert s["human"].startswith("NSS-8-")
    assert validate_nss(s["human"])
    card = issue_cssa_card(year=2026)
    assert card.startswith("CSSA-26-")
    assert len(card.split("-")[-1]) == 8
    assert cssa_encodes_formula(card) is False
    assert cssa_encodes_formula("CSSA-SILVER-26") is True
