"""Registre FERMÉ des outils de JOE (R11).

Deux familles, et seulement elles :
- LECTURE (``READ_TOOLS``) : adhérent, droits, historique, cotisations, barème, dossier. Chaque
  outil reçoit le port de lecture (``ReadPorts``) et emprunte la permission d'une opération GET
  du contrat : JOE ne voit que ce que l'utilisateur peut voir ;
- PRÉPARATION (``PREPARATION_TOOLS``) : brouillon de décision, brouillon de message. Fonctions
  pures sur des constats déjà lus : ni session, ni port, ni écriture.

Il n'existe AUCUN outil qui accorde, refuse, paie, change un statut ou lit le motif médical ;
le registre est un ``MappingProxyType`` (immuable) et ``test_guardrails`` échoue si sa liste
change. Les faits produits ne contiennent que des JETONS (``[ADH-1]``…) : les valeurs
identifiantes vues sont déclarées au ``Pseudonymizer`` et n'atteignent jamais le modèle.

Recommandation du brouillon de décision (défaut Q-L8-02, à valider) : refuser si les droits
sont fermés à la date du soin ou si le plafond restant ne couvre pas la part couverte ;
demander des pièces si une alerte de fraude est levée ou si aucune facture n'est déposée ;
accorder sinon. C'est une RECOMMANDATION : seul ``decideClaim`` (médecin-conseil) décide.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import Final
from uuid import UUID

from api.core.errors import MedicalSecretError, NotFoundError, RoleForbiddenError
from api.core.permissions import Principal, access_scope
from api.joe.guard import ReadOnlyScope
from api.joe.journal import SourceRef, unique_sources
from api.joe.ports import ReadPorts
from api.joe.pseudonym import Pseudonymizer

UNPAID: Final = frozenset({"a_payer", "en_retard"})
GRANTED: Final = frozenset({"accordee_auto", "accordee", "payee"})
IN_REVIEW: Final = frozenset({"en_revue", "pieces_demandees"})


class ToolKind(StrEnum):
    LECTURE = "lecture"
    PREPARATION = "preparation"


class ToolInputMissingError(LookupError):
    """L'outil a besoin d'un identifiant (adhérent, dossier) que la question ne donne pas."""


@dataclass(frozen=True, slots=True)
class ToolArgs:
    member_id: UUID | None = None
    claim_id: UUID | None = None
    at: date | None = None


@dataclass(frozen=True, slots=True)
class Finding:
    """Constat d'un outil de lecture : faits à jetons, sources, signaux pour la préparation."""

    tool: str
    facts: tuple[str, ...]
    sources: tuple[SourceRef, ...]
    signals: frozenset[str] = frozenset()
    values: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    member_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class PreparationInput:
    findings: tuple[Finding, ...]
    purpose: str | None = None


@dataclass(frozen=True, slots=True)
class Proposal:
    """Brouillon : texte à jetons, sources citées, recommandation éventuelle. Jamais appliqué."""

    text: str
    sources: tuple[SourceRef, ...]
    recommendation: str | None = None


type ReadRun = Callable[[ReadPorts, Pseudonymizer, ToolArgs], Awaitable[Finding]]
type PreparationRun = Callable[[PreparationInput], Proposal]


@dataclass(frozen=True, slots=True)
class ReadTool:
    name: str
    operation: str
    description: str
    run: ReadRun
    kind: ToolKind = ToolKind.LECTURE


@dataclass(frozen=True, slots=True)
class PreparationTool:
    name: str
    description: str
    run: PreparationRun
    kind: ToolKind = ToolKind.PREPARATION


# --- Mise en forme --------------------------------------------------------------------------


def fcfa(amount: int) -> str:
    return f"{amount:,} FCFA".replace(",", " ")


def _member_id(args: ToolArgs) -> UUID:
    if args.member_id is None:
        raise ToolInputMissingError("member_id")
    return args.member_id


def _at(args: ToolArgs) -> date:
    if args.at is None:  # le service passe toujours la date locale de l'organisation
        raise ToolInputMissingError("at")
    return args.at


def _forbid_name(pz: Pseudonymizer, full_name: str) -> None:
    pz.forbid(full_name, *full_name.split())


async def _member_token(ports: ReadPorts, pz: Pseudonymizer, member_id: UUID) -> SourceRef:
    number = await ports.member_number(member_id)
    if number is None:
        raise NotFoundError("Adhérent introuvable.")
    pz.forbid(number)
    source = SourceRef("member", member_id, number)
    pz.token("member", member_id, number)
    return source


def _tok(pz: Pseudonymizer, source: SourceRef) -> str:
    return pz.token(source.type, source.id, source.label)


# --- Outils de lecture ------------------------------------------------------------------------


async def lire_adherent(ports: ReadPorts, pz: Pseudonymizer, args: ToolArgs) -> Finding:
    member = await ports.member(_member_id(args))
    holder = member.holder
    pz.forbid(holder.given_name, holder.family_name, holder.phone_e164, member.member_number,
              holder.birth_date.isoformat())  # fmt: skip
    for dependent in member.dependents:
        pz.forbid(dependent.given_name, dependent.family_name)
    source = SourceRef("member", member.id, member.member_number)
    fact = (
        f"{_tok(pz, source)} : formule {member.plan_code}, statut {member.status}, adhérent "
        f"depuis le {member.enrolled_on.isoformat()}, fin de carence le "
        f"{member.waiting_period_ends_on.isoformat()}, {len(member.dependents)} ayant(s) droit."
    )
    return Finding("lire_adherent", (fact,), (source,), member_id=member.id)


async def lire_droits(ports: ReadPorts, pz: Pseudonymizer, args: ToolArgs) -> Finding:
    member_id = _member_id(args)
    member = await _member_token(ports, pz, member_id)
    rights = await ports.entitlements(member_id, _at(args))
    version = SourceRef("plan_version", rights.plan_version_id, "Version de formule")
    fact = (
        f"{_tok(pz, member)} au {rights.at.isoformat()} : statut {rights.status}, droits "
        f"{'ouverts' if rights.rights_open else 'fermés'}, plafond familial "
        f"{fcfa(rights.family_annual_ceiling_xof)}, consommé {fcfa(rights.consumed_xof)}, "
        f"reste {fcfa(rights.remaining_xof)}, fin de carence le "
        f"{rights.waiting_period_ends_on.isoformat()} ({_tok(pz, version)})."
    )
    return Finding(
        "lire_droits",
        (fact,),
        (member, version),
        signals=frozenset() if rights.rights_open else frozenset({"droits_fermes"}),
        values=MappingProxyType({"reste_xof": str(rights.remaining_xof)}),
        member_id=member_id,
    )


async def lire_historique(ports: ReadPorts, pz: Pseudonymizer, args: ToolArgs) -> Finding:
    member_id = _member_id(args)
    member = await _member_token(ports, pz, member_id)
    claims = await ports.member_claims(member_id)
    facts: list[str] = []
    sources: list[SourceRef] = [member]
    values: dict[str, str] = {}
    for claim in claims:
        _forbid_name(pz, claim.member_display_name)
        ref = SourceRef("claim", claim.id, claim.claim_number)
        provider = SourceRef("provider", claim.provider_id, claim.provider_name)
        sources += [ref, provider]
        rule = f", règle {claim.rule.code} v{claim.rule.version}" if claim.rule else ""
        facts.append(
            f"{_tok(pz, ref)} du {claim.service_date.isoformat()} chez {_tok(pz, provider)} : "
            f"{claim.status}, total {fcfa(claim.total_xof)}, couvert {fcfa(claim.covered_xof)}"
            f"{rule}."
        )
        if claim.status in GRANTED and "accord_token" not in values:
            values |= {
                "accord_token": _tok(pz, ref),
                "accord_date": claim.service_date.isoformat(),
                "accord_couvert": fcfa(claim.covered_xof),
                "accord_reste": fcfa(claim.total_xof - claim.covered_xof),
            }
        if claim.status == "pieces_demandees" and "pieces_token" not in values:
            values["pieces_token"] = _tok(pz, ref)
    if not facts:
        facts.append(f"{_tok(pz, member)} : aucune prise en charge enregistrée.")
    return Finding(
        "lire_historique", tuple(facts), tuple(sources),
        values=MappingProxyType(values), member_id=member_id,
    )  # fmt: skip


async def lire_cotisations(ports: ReadPorts, pz: Pseudonymizer, args: ToolArgs) -> Finding:
    member_id = _member_id(args)
    member = await _member_token(ports, pz, member_id)
    contributions = await ports.contributions(member_id)
    facts: list[str] = []
    sources: list[SourceRef] = [member]
    unpaid = [c for c in contributions if c.status in UNPAID]
    for c in contributions:
        period = c.period_start.strftime("%Y-%m")
        ref = SourceRef("contribution", c.id, f"Cotisation {period}")
        sources.append(ref)
        facts.append(
            f"Cotisation {period} de {_tok(pz, member)} ({_tok(pz, ref)}) : "
            f"{fcfa(c.amount_xof)}, {c.status}, échéance le {c.due_on.isoformat()}."
        )
    if not facts:
        facts.append(f"{_tok(pz, member)} : aucune cotisation émise.")
    values: dict[str, str] = {}
    if unpaid:
        oldest = min(unpaid, key=lambda c: c.due_on)
        values = {
            "impaye_periode": oldest.period_start.strftime("%m/%Y"),
            "impaye_montant": fcfa(oldest.amount_xof),
        }
    return Finding(
        "lire_cotisations", tuple(facts), tuple(sources),
        signals=frozenset({"cotisation_impayee"}) if unpaid else frozenset(),
        values=MappingProxyType(values), member_id=member_id,
    )  # fmt: skip


async def lire_bareme(ports: ReadPorts, pz: Pseudonymizer, args: ToolArgs) -> Finding:
    del pz  # le barème ne porte aucune donnée personnelle
    at = _at(args)
    lines = await ports.tariff(at)
    facts = tuple(
        f"Barème au {at.isoformat()} : {line.act_code} ({line.label}) = {fcfa(line.amount_xof)}, "
        f"depuis le {line.valid_from.isoformat()}."
        for line in lines
    )
    sources = tuple(SourceRef("tariff_item", line.id, line.act_code) for line in lines)
    return Finding("lire_bareme", facts, sources)


async def lire_dossier(ports: ReadPorts, pz: Pseudonymizer, args: ToolArgs) -> Finding:
    if args.claim_id is None:
        raise ToolInputMissingError("claim_id")
    detail = await ports.claim(args.claim_id)
    claim = detail.claim
    _forbid_name(pz, claim.member_display_name)
    member = await _member_token(ports, pz, claim.member_id)
    ref = SourceRef("claim", claim.id, claim.claim_number)
    provider = SourceRef("provider", claim.provider_id, claim.provider_name)
    version = SourceRef("plan_version", detail.plan_version_id, "Version de formule")
    kinds = await ports.claim_document_kinds(claim.id)
    acts = ", ".join(f"{i.act_code} x{i.quantity} ({fcfa(i.amount_xof)})" for i in detail.items)
    last = detail.decisions[-1] if detail.decisions else None
    decided = (
        f"{last.outcome} par {last.source} "
        + (
            f"(règle {last.rule.code} v{last.rule.version})"
            if last.rule
            else f"({last.reason_code})"
        )
        if last
        else "aucune"
    )
    score = "inconnu" if claim.fraud_score is None else f"{claim.fraud_score:.2f}"
    facts = (
        f"{_tok(pz, ref)} du {claim.service_date.isoformat()} chez {_tok(pz, provider)} pour "
        f"{_tok(pz, member)} : statut {claim.status}, total {fcfa(claim.total_xof)}, couvert "
        f"{fcfa(claim.covered_xof)}, reste à charge {fcfa(detail.patient_share_xof)} "
        f"({_tok(pz, version)}).",
        f"Actes : {acts or 'aucun'}.",
        f"Dernière décision : {decided}.",
        f"Score de fraude {score}, alerte {'levée' if claim.fraud_flagged else 'non levée'}.",
        f"Pièces déposées : {', '.join(kinds) or 'aucune'}.",
    )
    signals = {"en_revue"} if claim.status in IN_REVIEW else set()
    if claim.fraud_flagged:
        signals.add("fraude_signalee")
    if "facture" not in kinds:
        signals.add("sans_facture")
    return Finding(
        "lire_dossier",
        facts,
        (ref, member, provider, version),
        signals=frozenset(signals),
        values=MappingProxyType(
            {
                "service_date": claim.service_date.isoformat(),
                "covered_xof": str(claim.covered_xof),
                "status": claim.status,
            }
        ),
        member_id=claim.member_id,
    )


# --- Outils de préparation (purs) ------------------------------------------------------------


def _all_sources(findings: tuple[Finding, ...]) -> tuple[SourceRef, ...]:
    return unique_sources([s for f in findings for s in f.sources])


def _by_tool(findings: tuple[Finding, ...]) -> dict[str, Finding]:
    return {f.tool: f for f in findings}


def preparer_brouillon_decision(inp: PreparationInput) -> Proposal:
    found = _by_tool(inp.findings)
    signals = frozenset().union(*(f.signals for f in inp.findings))
    covered = (
        int(found["lire_dossier"].values.get("covered_xof", "0")) if "lire_dossier" in found else 0
    )
    remaining = found["lire_droits"].values.get("reste_xof") if "lire_droits" in found else None
    reasons: list[str] = []
    if "droits_fermes" in signals:
        recommendation = "refuser"
        reasons.append("les droits sont fermés à la date du soin (R-01)")
    elif remaining is not None and int(remaining) < covered:
        recommendation = "refuser"
        reasons.append(
            f"le plafond familial restant ({fcfa(int(remaining))}) ne couvre pas la part "
            f"couverte demandée ({fcfa(covered)}) (R-09)"
        )
    elif signals & {"fraude_signalee", "sans_facture"}:
        recommendation = "demander_pieces"
        if "fraude_signalee" in signals:
            reasons.append("une alerte de fraude est levée sur le dossier")
        if "sans_facture" in signals:
            reasons.append("aucune facture n'est déposée")
    else:
        recommendation = "accorder"
        reasons.append(
            "droits ouverts, plafond suffisant, facture déposée et aucune alerte de fraude"
        )
    if remaining is None:
        reasons.append("droits non vérifiés (lecture non autorisée)")
    text = (
        f"Recommandation : {recommendation.replace('_', ' ')}, car {' ; '.join(reasons)}. "
        "La décision appartient au médecin-conseil."
    )
    return Proposal(text=text, sources=_all_sources(inp.findings), recommendation=recommendation)


def preparer_message(inp: PreparationInput) -> Proposal:
    found = _by_tool(inp.findings)
    history = found["lire_historique"].values if "lire_historique" in found else {}
    dues = found["lire_cotisations"].values if "lire_cotisations" in found else {}
    if inp.purpose == "relance_cotisation":
        text = (
            f"Bonjour, votre cotisation MulemaCare de {dues['impaye_periode']} "
            f"({dues['impaye_montant']}) n'est pas encore réglée. Vous pouvez la payer avec le "
            "lien de paiement que la mutuelle vous envoie. Merci."
            if dues
            else "Bonjour, vos cotisations MulemaCare sont à jour. Merci de votre confiance."
        )
    elif inp.purpose == "confirmation_accord":
        text = (
            f"Bonjour, votre prise en charge {history['accord_token']} du "
            f"{history['accord_date']} est accordée : {history['accord_couvert']} pris en "
            f"charge par la mutuelle, {history['accord_reste']} à votre charge."
            if "accord_token" in history
            else "Bonjour, aucune prise en charge accordée n'a été trouvée sur votre dossier."
        )
    elif inp.purpose == "demande_pieces":
        text = (
            f"Bonjour, pour votre dossier {history['pieces_token']}, la mutuelle a besoin de "
            "pièces complémentaires. Merci de les remettre à votre établissement de soins."
            if "pieces_token" in history
            else "Bonjour, la mutuelle n'attend aucune pièce de votre part pour le moment."
        )
    else:
        msg = f"objet de message inconnu : {inp.purpose!r}"
        raise ValueError(msg)
    return Proposal(text=text, sources=_all_sources(inp.findings))


# --- Registre fermé ---------------------------------------------------------------------------

READ_TOOLS: Final[Mapping[str, ReadTool]] = MappingProxyType(
    {
        t.name: t
        for t in (
            ReadTool("lire_adherent", "getMember",
                     "Fiche adhérent : formule, statut, ayants droit.", lire_adherent),
            ReadTool("lire_droits", "getMemberEntitlements",
                     "Droits à une date : statut, plafond familial, consommé, reste.", lire_droits),
            ReadTool("lire_historique", "listClaims",
                     "Dernières prises en charge de l'adhérent (statut, montants, règle).",
                     lire_historique),
            ReadTool("lire_cotisations", "listMemberContributions",
                     "Cotisations de l'adhérent et retards.", lire_cotisations),
            ReadTool("lire_bareme", "listTariffs", "Barème des actes en vigueur à une date.",
                     lire_bareme),
            ReadTool("lire_dossier", "getClaim",
                     "Dossier : montants, actes, décisions, alerte de fraude, pièces déposées.",
                     lire_dossier),
        )
    }
)  # fmt: skip

PREPARATION_TOOLS: Final[Mapping[str, PreparationTool]] = MappingProxyType(
    {
        t.name: t
        for t in (
            PreparationTool("preparer_brouillon_decision",
                            "Brouillon de recommandation, dossier en revue (jamais appliqué).",
                            preparer_brouillon_decision),
            PreparationTool("preparer_message",
                            "Brouillon de SMS pour un adhérent (l'envoi reste humain).",
                            preparer_message),
        )
    }
)  # fmt: skip

TOOL_REGISTRY: Final[Mapping[str, ReadTool | PreparationTool]] = MappingProxyType(
    {**READ_TOOLS, **PREPARATION_TOOLS}
)


async def run_read_tool(  # noqa: PLR0913 — contexte complet d'un appel d'outil
    scope: ReadOnlyScope,
    *,
    principal: Principal,
    ports: ReadPorts,
    pz: Pseudonymizer,
    name: str,
    args: ToolArgs,
) -> Finding | None:
    """Exécute un outil du registre, DANS le garde de lecture seule, avec les droits de
    l'utilisateur. ``None`` si son rôle ne permet pas la lecture (l'outil n'est pas cité)."""
    if not scope.active:
        msg = "outil de lecture hors du garde de lecture seule"
        raise RuntimeError(msg)
    tool = READ_TOOLS.get(name)
    if tool is None:
        msg = f"outil inconnu du registre : {name}"
        raise LookupError(msg)
    try:
        access_scope(principal, tool.operation)
    except (RoleForbiddenError, MedicalSecretError):
        return None
    return await tool.run(ports, pz, args)


def run_preparation_tool(name: str, inp: PreparationInput) -> Proposal:
    tool = PREPARATION_TOOLS.get(name)
    if tool is None:
        msg = f"outil inconnu du registre : {name}"
        raise LookupError(msg)
    return tool.run(inp)
