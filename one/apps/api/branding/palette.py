"""Garde de contraste côté serveur pour la marque blanche (CR-P3-01).

Une organisation ne propose PAS un thème : elle surcharge une LISTE FERMÉE de jetons
(``OVERRIDABLE_TOKENS``), dans les thèmes clair et sombre seulement. Le plein soleil reste noir
sur blanc quel que soit le thème (POLISH_CONTRACT §9) : il n'est pas surchargeable. Le focus suit
l'accent (contrat §2). Aucune autre clé, aucune valeur autre que ``#rrggbb`` : pas de CSS libre.

Les jetons effectifs = palette de base (copie de ``specs/design/mulemacare-tokens.css``, tenue
identique par ``tests/test_palette.py``) + surcharges. Chaque paire du contrat qui touche un jeton
surchargeable (``GUARDED_TEXT_PAIRS`` : 4,5:1 ; ``GUARDED_UI_PAIRS`` : 3:1) est recalculée avec
``api.branding.contrast`` ; une paire sous le seuil fait refuser la couleur (422 BRD-01), avec le
thème, la paire et le rapport, pour que l'écran de réglage dise quoi corriger.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal

from api.branding.contrast import HEX_COLOR, contrast_ratio

type ThemeName = Literal["light", "dark"]
type ProblemKind = Literal["contraste", "jeton"]

THEMES: Final[tuple[ThemeName, ...]] = ("light", "dark")
THEME_LABELS: Final[Mapping[str, str]] = MappingProxyType({"light": "clair", "dark": "sombre"})
OVERRIDABLE_TOKENS: Final = ("accent", "accent_hover", "accent_fg", "brand_deep")
TEXT_MINIMUM: float = 4.5
UI_MINIMUM: float = 3.0
# Jetons sémantiques que l'accent ne doit jamais copier (POLISH_CONTRACT §5).
STATUS_TOKENS: Final = ("--ok", "--warn", "--crit", "--info")

_LIGHT: Final[Mapping[str, str]] = MappingProxyType(
    {
        "--bg": "#f6f9fb",
        "--surface": "#ffffff",
        "--accent": "#097268",
        "--accent-hover": "#075e56",
        "--accent-2": "#e3f3ef",
        "--accent-fg": "#ffffff",
        "--focus": "#097268",
        "--ok": "#166534",
        "--warn": "#92400e",
        "--crit": "#b91c1c",
        "--info": "#1e40af",
        "--brand-deep": "#064a43",
        "--brand-on-deep": "#ffffff",
        "--brand-on-deep-2": "#b9e4dc",
    }
)
_DARK: Final[Mapping[str, str]] = MappingProxyType(
    {
        **_LIGHT,
        "--bg": "#0d1417",
        "--surface": "#131c20",
        "--accent": "#4fc2b0",
        "--accent-hover": "#6fd3c3",
        "--accent-2": "#123430",
        "--accent-fg": "#04211d",
        "--focus": "#4fc2b0",
        "--ok": "#6fcf8e",
        "--warn": "#f0b45e",
        "--crit": "#f38e86",
        "--info": "#9bb4f6",
        "--brand-deep": "#0b3f3a",
    }
)
BASE_TOKENS: Final[Mapping[str, Mapping[str, str]]] = MappingProxyType(
    {"light": _LIGHT, "dark": _DARK}
)

# Paires du contrat (test_design_tokens.py) qui touchent --accent, --accent-hover, --accent-fg,
# --brand-deep ou --focus (qui suit l'accent).
GUARDED_TEXT_PAIRS: Final = (
    ("--accent", "--bg"),
    ("--accent", "--surface"),
    ("--accent", "--accent-2"),
    ("--accent-fg", "--accent"),
    ("--accent-fg", "--accent-hover"),
    ("--brand-on-deep", "--brand-deep"),
    ("--brand-on-deep-2", "--brand-deep"),
)
GUARDED_UI_PAIRS: Final = (("--focus", "--surface"), ("--focus", "--bg"))


@dataclass(frozen=True, slots=True)
class PaletteProblem:
    """Un refus, rattaché au champ de la requête (``theme.<thème>.<jeton>``)."""

    kind: ProblemKind
    field: str
    message: str


def _css_name(token: str) -> str:
    return "--" + token.replace("_", "-")


def _token_of(css_name: str) -> str | None:
    if css_name == "--focus":
        return "accent"
    token = css_name.removeprefix("--").replace("-", "_")
    return token if token in OVERRIDABLE_TOKENS else None


def _ratio(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def _limit(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def effective_tokens(theme: ThemeName, overrides: Mapping[str, str]) -> dict[str, str]:
    """Jetons du thème après surcharge ; le focus suit l'accent."""
    tokens = dict(BASE_TOKENS[theme])
    for token, value in overrides.items():
        tokens[_css_name(token)] = value.lower()
    tokens["--focus"] = tokens["--accent"]
    return tokens


def _closed_list_problems(theme_overrides: Mapping[str, object]) -> list[PaletteProblem]:
    problems: list[PaletteProblem] = []
    for theme, overrides in theme_overrides.items():
        if theme not in THEMES:
            problems.append(
                PaletteProblem(
                    "jeton", f"theme.{theme}", "Seuls les thèmes clair et sombre se personnalisent."
                )
            )
            continue
        if not isinstance(overrides, Mapping):
            problems.append(PaletteProblem("jeton", f"theme.{theme}", "Liste de jetons attendue."))
            continue
        for token, value in overrides.items():
            field = f"theme.{theme}.{token}"
            if token not in OVERRIDABLE_TOKENS:
                problems.append(
                    PaletteProblem(
                        "jeton",
                        field,
                        "Jeton non personnalisable. Jetons admis : "
                        + ", ".join(OVERRIDABLE_TOKENS)
                        + ".",
                    )
                )
            elif not isinstance(value, str) or not HEX_COLOR.fullmatch(value.lower()):
                problems.append(
                    PaletteProblem("jeton", field, "Couleur attendue au format #RRGGBB.")
                )
    return problems


def _contrast_problems(theme: ThemeName, overrides: Mapping[str, str]) -> list[PaletteProblem]:
    tokens = effective_tokens(theme, overrides)
    label = THEME_LABELS[theme]
    problems: list[PaletteProblem] = []
    for pairs, minimum in ((GUARDED_TEXT_PAIRS, TEXT_MINIMUM), (GUARDED_UI_PAIRS, UI_MINIMUM)):
        for fg, bg in pairs:
            ratio = contrast_ratio(tokens[fg], tokens[bg])
            if ratio >= minimum:
                continue
            touched = [t for t in (_token_of(fg), _token_of(bg)) if t is not None]
            blamed = [t for t in touched if t in overrides] or touched
            for token in dict.fromkeys(blamed):
                problems.append(
                    PaletteProblem(
                        "contraste",
                        f"theme.{theme}.{token}",
                        f"Thème {label} : {fg} sur {bg} donne {_ratio(ratio)}:1, "
                        f"il faut au moins {_limit(minimum)}:1 (WCAG AA).",
                    )
                )
    if "accent" in overrides and tokens["--accent"] in {tokens[s] for s in STATUS_TOKENS}:
        problems.append(
            PaletteProblem(
                "contraste",
                f"theme.{theme}.accent",
                f"Thème {label} : l'accent reprend une couleur de statut (ok, attention, "
                "critique, en cours) ; choisissez une autre couleur.",
            )
        )
    return problems


def check_theme_overrides(theme_overrides: Mapping[str, object]) -> list[PaletteProblem]:
    """Problèmes de la proposition (liste vide : acceptée). Liste fermée d'abord, puis AA."""
    problems = _closed_list_problems(theme_overrides)
    if problems:
        return problems
    for theme in THEMES:
        raw = theme_overrides.get(theme) or {}
        if not isinstance(raw, Mapping):  # pragma: no cover — écarté par la liste fermée
            continue
        overrides = {str(k): str(v).lower() for k, v in raw.items()}
        problems += _contrast_problems(theme, overrides)
    return problems
