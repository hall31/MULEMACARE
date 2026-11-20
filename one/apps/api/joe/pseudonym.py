"""Pseudonymisation de tout ce qui part vers le modèle (AGENTS.md : aucune donnée identifiante
vers un LLM, R9).

Trois couches :
1. les outils ne produisent que des faits à JETONS (``[ADH-1]``, ``[PEC-1]``…) et déclarent
   chaque valeur identifiante rencontrée (``forbid``) : nom, téléphone, numéro d'adhérent, date
   de naissance ;
2. la question libre de l'utilisateur est masquée (``mask_question``) : valeurs connues, numéros,
   téléphones, courriels, dates, mots à majuscule hors début de phrase (noms propres) ;
3. contrôle final avant envoi (``check``), en échec fermé : une valeur interdite, un UUID, un
   téléphone ou un numéro d'adhérent bloque l'appel, et ``ModelGateway`` se replie sur le
   modèle déterministe LOCAL (rien ne sort).
Les jetons sont réhydratés dans la réponse avec des libellés non identifiants (numéro de
dossier, numéro d'adhérent), jamais avec un nom.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Final
from uuid import UUID

from api.core.jsonlog import LOGGER_NAME, log_event
from api.joe.model import LanguageModel, ModelRequest, ModelUnavailableError

logger = logging.getLogger(f"{LOGGER_NAME}.joe")

# Préfixe de jeton par type d'enregistrement (types ``Source`` du contrat).
TOKEN_PREFIX: Final = {
    "member": "ADH",
    "claim": "PEC",
    "contribution": "COT",
    "provider": "ETAB",
    "plan_version": "FORM",
    "tariff_item": "TARIF",
    "rule_version": "REGLE",
    "ledger_entry": "ECR",
}
_TOKEN: Final = re.compile(r"\[(?:ADH|PEC|COT|ETAB|FORM|TARIF|REGLE|ECR)-\d+\]")

_UUID: Final = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE
)
_PHONE: Final = re.compile(r"\+\d{8,15}\b|\b\d{8,}\b")
_MEMBER_NUMBER: Final = re.compile(r"\bMC-\d{8}\b", re.IGNORECASE)
_EMAIL: Final = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_DATE: Final = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b")
_DIGIT_RUN: Final = re.compile(r"(?:\+?\d[\s.-]?){6,}\d")
_WORD: Final = re.compile("[^\\W\\d_][\\w'\u2019-]*")
# Codes métier gardés tels quels (actes, règles) : majuscules + tiret + chiffres/lettres.
_CODE: Final = re.compile(r"[A-Z]{1,5}(?:-[A-Z0-9]+)+|FCFA|XOF|JOE")
_SENTENCE_END: Final = re.compile(r"[.?!:;]\s*$")
# Un mot en début de phrase n'est gardé que s'il est un mot courant de question (un prénom
# tapé en tête de phrase serait sinon envoyé tel quel).
_COMMON_STARTS: Final = frozenset(
    {
        "quel",
        "quelle",
        "quels",
        "quelles",
        "quand",
        "où",
        "comment",
        "combien",
        "pourquoi",
        "qui",
        "que",
        "qu",
        "est-ce",
        "y",
        "a-t-il",
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        "du",
        "de",
        "ce",
        "cet",
        "cette",
        "ces",
        "son",
        "sa",
        "ses",
        "mon",
        "ma",
        "mes",
        "ton",
        "ta",
        "tes",
        "votre",
        "vos",
        "leur",
        "leurs",
        "et",
        "ou",
        "mais",
        "donc",
        "puis",
        "alors",
        "aussi",
        "encore",
        "il",
        "elle",
        "ils",
        "elles",
        "on",
        "je",
        "tu",
        "nous",
        "vous",
        "à",
        "au",
        "aux",
        "pour",
        "sur",
        "dans",
        "avec",
        "sans",
        "par",
        "chez",
        "entre",
        "selon",
        "depuis",
        "avant",
        "après",
        "droits",
        "droit",
        "historique",
        "barème",
        "bareme",
        "tarif",
        "tarifs",
        "cotisation",
        "cotisations",
        "dossier",
        "dossiers",
        "prise",
        "prises",
        "adhérent",
        "adherent",
        "adhérents",
        "plafond",
        "statut",
        "carence",
        "résume",
        "résumé",
        "résumer",
        "montre",
        "montrer",
        "donne",
        "donner",
        "liste",
        "lister",
        "affiche",
        "afficher",
        "explique",
        "expliquer",
        "peux",
        "peut",
        "faut-il",
        "peut-il",
        "doit-il",
        "dois-je",
        "est-il",
        "sont-ils",
        "ont-ils",
        "faut",
        "faudrait",
        "oui",
        "non",
        "merci",
        "bonjour",
        "stp",
        "svp",
    }
)

# Questions qui visent le motif médical : JOE refuse sans rien lire (R6).
_MEDICAL: Final = re.compile(
    r"motif|diagnos|ordonnance|maladie|patholog|sympt[oô]m|m[ée]dica(?:l|le|ux)\b|"
    r"pourquoi .* (?:consult|soign)|\bpathologie",
    re.IGNORECASE,
)


class IdentifyingDataError(ValueError):
    """Une donnée identifiante allait partir vers le modèle (le message ne la contient pas)."""


def asks_medical(question: str) -> bool:
    return bool(_MEDICAL.search(question))


@dataclass
class Pseudonymizer:
    """Jetons stables pour une action de JOE, et liste des valeurs interdites."""

    _tokens: dict[tuple[str, UUID], str] = field(default_factory=dict)
    _labels: dict[str, str] = field(default_factory=dict)
    _counters: dict[str, int] = field(default_factory=dict)
    _forbidden: set[str] = field(default_factory=set)

    def token(self, kind: str, record_id: UUID, label: str) -> str:
        key = (kind, record_id)
        if key not in self._tokens:
            prefix = TOKEN_PREFIX[kind]
            self._counters[prefix] = self._counters.get(prefix, 0) + 1
            token = f"[{prefix}-{self._counters[prefix]}]"
            self._tokens[key] = token
            self._labels[token] = label
        return self._tokens[key]

    def forbid(self, *values: str | None) -> None:
        for value in values:
            if value and len(value.strip()) >= 2:  # noqa: PLR2004 — une lettre n'identifie pas
                self._forbidden.add(value.strip())

    @property
    def forbidden(self) -> frozenset[str]:
        return frozenset(self._forbidden)

    def check(self, text: str) -> None:
        """Échec fermé : lève si ``text`` contient une valeur identifiante."""
        lowered = text.casefold()
        for value in self._forbidden:
            if re.search(rf"(?<!\w){re.escape(value.casefold())}(?!\w)", lowered):
                raise IdentifyingDataError("valeur identifiante connue")
        for pattern, what in (
            (_UUID, "identifiant interne"),
            (_PHONE, "numéro de téléphone"),
            (_MEMBER_NUMBER, "numéro d'adhérent"),
            (_EMAIL, "courriel"),
        ):
            if pattern.search(text):
                raise IdentifyingDataError(what)

    def rehydrate(self, text: str) -> str:
        return _TOKEN.sub(lambda m: self._labels.get(m.group(0), m.group(0)), text)


def mask_question(question: str, pz: Pseudonymizer) -> str:
    """Question libre rendue sûre pour le modèle (elle peut contenir un nom tapé par l'agent)."""
    masked = question
    for value in sorted(pz.forbidden, key=len, reverse=True):
        masked = re.sub(rf"(?<!\w){re.escape(value)}(?!\w)", "[masqué]", masked, flags=re.I)
    masked = _EMAIL.sub("[courriel]", masked)
    masked = _MEMBER_NUMBER.sub("[numéro]", masked)
    masked = _UUID.sub("[identifiant]", masked)
    masked = _DATE.sub("[date]", masked)
    masked = _DIGIT_RUN.sub("[numéro]", masked)
    masked = _PHONE.sub("[numéro]", masked).strip()
    return _mask_proper_nouns(masked)


def _mask_proper_nouns(text: str) -> str:
    """Tout mot à initiale majuscule est traité comme un nom propre, sauf un code métier ou,
    en début de phrase, un mot courant de question."""
    out: list[str] = []
    cursor = 0
    for match in _WORD.finditer(text):
        word = match.group(0)
        before = text[: match.start()]
        if not word[0].isupper() or before.endswith("[") or _CODE.fullmatch(word):
            continue
        sentence_start = not before.strip() or bool(_SENTENCE_END.search(before))
        if sentence_start and word.lower() in _COMMON_STARTS:
            continue
        out.append(text[cursor : match.start()])
        out.append("[nom]")
        cursor = match.end()
    out.append(text[cursor:])
    return "".join(out)


@dataclass(frozen=True, slots=True)
class GatewayResult:
    text: str
    model: str
    blocked: bool = False


class ModelGateway:
    """Seul passage vers le modèle : contrôle final, puis repli déterministe en cas d'échec."""

    def __init__(self, model: LanguageModel, *, fallback: LanguageModel) -> None:
        self._model = model
        self._fallback = fallback

    async def complete(self, request: ModelRequest, pz: Pseudonymizer) -> GatewayResult:
        try:
            pz.check(request.prompt())
        except IdentifyingDataError as exc:
            # Bug d'outil : on ne l'envoie pas. Le repli est local (aucune requête sortante).
            log_event(logger, logging.ERROR, "joe.model.blocked", reason=str(exc))
            text = await self._fallback.complete(request)
            return GatewayResult(text=text, model=self._fallback.name, blocked=True)
        try:
            text = await self._model.complete(request)
        except ModelUnavailableError as exc:
            log_event(
                logger, logging.WARNING, "joe.model.unavailable", model=self._model.name,
                reason=str(exc),
            )  # fmt: skip
            text = await self._fallback.complete(request)
            return GatewayResult(text=text, model=self._fallback.name)
        return GatewayResult(text=text, model=self._model.name)
