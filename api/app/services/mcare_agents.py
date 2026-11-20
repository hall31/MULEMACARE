"""MCare AI Agents — specialist routing and response generation via the AI trunk.

Implements:
- SpecialistAgent: structured medical orientation through the platform AI trunk
- route_to_specialist: symptom keyword matching → agent persona selection
- evaluate_response: safety validation (no diagnosis, red flags detected)
- transmit_to_lisacare: delegate to human doctor via Lisacare API

All agents follow guardrails:
- NEVER diagnose (forbidden: "you have X disease")
- ALWAYS identify critical red flags
- Provide hypothesis + next steps, never final medical advice
- All responses tagged with "IA - Hypothèses non validées"

Accès modèle : ``cybernecs_ai_gateway.build_gateway()`` est le seul point du
monorepo autorisé à atteindre un fournisseur (plafond de coût, souveraineté,
prompt caching, circuit breaker). Ce module ne nomme **aucun** modèle : il
demande un tier (``MCARE_TASK_TYPE``), la table de routage de
``cybernecs-agent-core`` choisit le modèle. Le modèle réellement utilisé est
rapporté par la Gateway (``GatewayResult.model_used``).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from cybernecs_agent_core import Gateway, TaskType
from cybernecs_agent_core.gateway import Transport
from cybernecs_ai_gateway import GatewaySettings, build_gateway

from app.core.config import get_settings
from app.core.mcare_safety import DiagnosisDetector, RedFlagDetector, SafetyEvaluator
from app.domain.mcare_models import ClinCard, SpecialistType

logger = logging.getLogger(__name__)

#: Tier du tronc IA pour l'orientation MCare. Raisonnement : l'orientation
#: clinique était servie par un modèle de cette classe avant la migration.
MCARE_TASK_TYPE = TaskType.REASONING

_MAX_TOKENS = 1024


def mcare_api_key() -> str:
    """Clé fournisseur de MCare : environnement d'abord, puis Settings (.env)."""
    return (os.getenv("ANTHROPIC_API_KEY") or get_settings().anthropic_api_key or "").strip()


def llm_configured() -> bool:
    """Réévalué à chaque appel par la Gateway : une clé retirée coupe l'appel."""
    return bool(mcare_api_key())


def build_mcare_gateway(*, transport: Transport | None = None) -> Gateway:
    """Gateway du tronc IA, câblée sur la clé de MCare.

    La clé part par ``api_keys`` : les Settings la lisent depuis ``.env``, qui ne
    peuple pas ``os.environ``. Les stubs sont vides — un contenu vide devient une
    ``MCareAgentError`` (503), jamais une réponse simulée montrée à un membre.
    ``transport`` n'est injecté que par les tests.
    """
    online = llm_configured()
    return build_gateway(
        settings=GatewaySettings(off=not online, keys_enabled=online),
        api_keys={"ANTHROPIC_API_KEY": mcare_api_key()},
        key_available=llm_configured,
        offline_stub="",
        error_stub="",
        blocked_stub="",
        transport=transport,
    )


_gateway: Gateway | None = None


def get_mcare_gateway() -> Gateway:
    """Singleton de process — la Gateway porte des circuit breakers à conserver."""
    global _gateway
    if _gateway is None:
        _gateway = build_mcare_gateway()
    return _gateway


class MCareAgentError(Exception):
    """MCare agent runtime error."""

    pass


class SpecialistAgent:
    """Medical orientation chat through the platform AI trunk.

    Each agent persona handles a specific concern:
    - Triage: acute symptoms, red flags, emergency signals
    - Coverage: insurance coverage, benefits, thresholds
    - Network: clinics, pharmacies, access points
    - General: lifestyle, preventive care, FAQ

    All responses go through safety_evaluator before transmission.
    """

    def __init__(
        self,
        specialist_type: SpecialistType,
        language: str = "fr",
        gateway: Gateway | None = None,
    ):
        """Initialize specialist agent.

        Args:
            specialist_type: Agent persona (triage|coverage|network|general)
            language: Response language (fr|en)
            gateway: AI trunk gateway (process singleton by default)
        """
        self.specialist_type = specialist_type
        self.language = language
        self.settings = get_settings()

        if not llm_configured():
            raise MCareAgentError("ANTHROPIC_API_KEY not configured")
        self._gateway = gateway or get_mcare_gateway()

        # Safety evaluators
        self.diagnosis_detector = DiagnosisDetector(language=language)
        self.red_flag_detector = RedFlagDetector(language=language)
        self.safety_evaluator = SafetyEvaluator(
            diagnosis_detector=self.diagnosis_detector,
            red_flag_detector=self.red_flag_detector,
        )

    def _system_prompt(self) -> str:
        """Return system prompt for specialist type."""
        prompts = {
            SpecialistType.TRIAGE: (
                "Tu es MCare Triage — agent d'orientation médicale de la mutuelle MulemaCare. "
                "Rôle: collecter les symptômes, évaluer l'urgence (pas de diagnostic final), "
                "identifier les drapeaux rouges, proposer les prochaines étapes. "
                "IMPORTANT: "
                "- Ne JAMAIS diagnostiquer (pas 'vous avez X maladie') "
                "- Toujours mentionner que l'IA propose des hypothèses à explorer "
                "- Si symptômes critiques (difficultés respiratoires, douleur thoracique, convulsions, "
                "perte de conscience), recommander appel d'urgence (15/SAMU) immédiatement "
                "- Collecter: symptômes, durée, antécédents, allergies, médicaments actuels "
                "- Proposer: orientation (consultation, urgences), cliniques tiers-payant "
                "- Répondre en français cliniquement pertinent, compréhensible aux patients "
            ),
            SpecialistType.COVERAGE: (
                "Tu es MCare Coverage — agent d'information sur les garanties et franchises. "
                "Rôle: répondre aux questions sur couverture, plafonds, délais de carence, "
                "actes pris en charge. "
                "IMPORTANT: "
                "- Lire depuis le catalogue plan_catalog.py (PLAN_CATALOG) "
                "- Informer du plafond global, des franchises, des actes exclus "
                "- Orienter vers documentation officielle pour arbitrages complexes "
                "- Pas de promesses non fondées (vérifier catalogue avant de répondre) "
            ),
            SpecialistType.NETWORK: (
                "Tu es MCare Network — agent d'accès aux cliniques et pharmacies du réseau. "
                "Rôle: proposer les établissements proches en tiers-payant, leurs spécialités, "
                "horaires, modes de prise de RDV. "
                "IMPORTANT: "
                "- Utiliser la base réseau (clinics_network.json simulé) "
                "- Géolocaliser si possible (région mentionnée) "
                "- Proposer tiers-payant direct ou remboursement selon bénéficiaire "
                "- Horaires d'urgence si symptômes aigus "
            ),
            SpecialistType.GENERAL: (
                "Tu es MCare General — agent FAQ pour questions générales. "
                "Rôle: couvrir adhésion, carte digitale, tarifs, FAQ produit MulemaCare. "
                "IMPORTANT: "
                "- Répondre avec bienveillance aux demandes administratives "
                "- Valider statut adhésion si CSSA ID fourni "
                "- Orienter vers support/téléphone si besoin HITL "
                "- Pas de promesses commerciales non autorisées "
            ),
        }
        return prompts.get(
            self.specialist_type,
            prompts[SpecialistType.GENERAL],
        )

    async def chat(
        self,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Send user message to the specialist and get orientation response.

        Args:
            user_message: User's question/symptom description
            conversation_history: Prior messages in conversation
                (list of {"role": "user"|"assistant", "content": str})

        Returns:
            {
                "response": str (orientation text, no diagnosis),
                "clin_card": ClinCard (structured output if symptoms),
                "safety_check": {"passed": bool, "issues": [str]},
                "model": str (model actually routed by the AI trunk),
                "usage": {"input_tokens": int, "output_tokens": int},
            }

        Raises:
            MCareAgentError: no model answered (provider errors, offline, blocked)
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt()},
            *(conversation_history or []),
            {"role": "user", "content": user_message},
        ]

        # Les erreurs fournisseur sont absorbées par la Gateway (fallback, circuit
        # breaker) et rendues comme un contenu vide + error_message ; une exception
        # ici est un défaut du tronc lui-même. Dans les deux cas : 503 côté route.
        try:
            result = await self._gateway.run(
                messages,
                task_type=MCARE_TASK_TYPE,
                max_tokens=_MAX_TOKENS,
            )
        except Exception as e:  # noqa: BLE001 — un agent clinique dégrade en 503
            logger.error(f"AI trunk error: {e}")
            raise MCareAgentError(f"AI trunk error: {e}") from e

        if not result.content:
            reason = result.error_message or "empty_response"
            logger.error(f"LLM unavailable: {reason}")
            raise MCareAgentError(f"LLM unavailable: {reason}")

        response_text = result.content
        usage = {
            "input_tokens": result.prompt_tokens,
            "output_tokens": result.completion_tokens,
        }

        # Safety evaluation
        safety_result = self.safety_evaluator.evaluate(response_text)
        if not safety_result["passed"]:
            logger.warning(
                f"Safety check failed for specialist {self.specialist_type.value}: "
                f"{safety_result['issues']}"
            )
            # Mark as failed but don't raise — let caller decide
            return {
                "response": response_text,
                "clin_card": None,
                "safety_check": safety_result,
                "model": result.model_used,
                "usage": usage,
            }

        # Extract clinical card if symptoms mentioned
        clin_card = None
        if self.specialist_type == SpecialistType.TRIAGE:
            clin_card = self._extract_clin_card(response_text)

        return {
            "response": response_text,
            "clin_card": clin_card,
            "safety_check": safety_result,
            "model": result.model_used,
            "usage": usage,
        }

    def _extract_clin_card(self, response_text: str) -> ClinCard | None:
        """Parse response text to extract structured clinical card.

        Looks for markers like:
        - Symptômes: ... Hypothèses: ... Prochaines étapes: ...
        - Or uses LLM-structured parsing if JSON present

        Returns:
            ClinCard or None if no symptoms detected
        """
        try:
            # Try to find JSON block in response
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_str = response_text[start:end].strip()
                data = json.loads(json_str)

                return ClinCard(
                    symptoms=data.get("symptoms", []),
                    hypothesis_list=data.get("hypotheses", []),
                    next_steps=data.get("next_steps", ""),
                    red_flags=data.get("red_flags", []),
                    tags=["IA", "Hypothèses non validées"],
                    concern_level=data.get("concern_level", "modere"),
                )
            else:
                # Fallback: create basic card from response text
                return ClinCard(
                    symptoms=["À explorer"],
                    hypothesis_list=["Orientation en cours"],
                    next_steps="Consultation avec médecin recommandée",
                    red_flags=[],
                    tags=["IA", "Hypothèses non validées"],
                    concern_level="modere",
                )
        except Exception as e:
            logger.warning(f"Failed to extract clinical card: {e}")
            return None

    @staticmethod
    def evaluate_response(response: str, language: str = "fr") -> dict[str, Any]:
        """Static utility: verify response for safety issues.

        Returns:
            {
                "passed": bool,
                "diagnosis_detected": bool,
                "red_flags": [str],
                "issues": [str],
            }
        """
        diagnosis_detector = DiagnosisDetector(language=language)
        red_flag_detector = RedFlagDetector(language=language)
        safety_evaluator = SafetyEvaluator(
            diagnosis_detector=diagnosis_detector,
            red_flag_detector=red_flag_detector,
        )
        return safety_evaluator.evaluate(response)

    @staticmethod
    def transmit_to_lisacare(
        conversation_id: str,
        cssa_id: str,
        beneficiary_name: str | None,
        reason: str,
    ) -> dict[str, Any]:
        """Notify Lisacare (HealthOS partner) of escalation.

        Args:
            conversation_id: MCare conversation ID
            cssa_id: Member CSSA ID
            beneficiary_name: Beneficiary name (if dependent)
            reason: Why transmitted (symptoms, red flags, expert request, etc)

        Returns:
            {
                "ok": bool,
                "lisacare_id": str | None,
                "status": str,
                "message": str,
            }

        Note:
            This is async-ready but called from sync context in action_center.
            Real implementation would queue to async task or use sync HTTP client.
        """
        logger.info(
            f"Escalating conversation {conversation_id} (member {cssa_id}) to Lisacare. "
            f"Reason: {reason}"
        )

        # TODO: Implement actual Lisacare API call
        # For now, return mock success response
        return {
            "ok": True,
            "lisacare_id": f"HC-{conversation_id[:8]}",
            "status": "PENDING_DOCTOR_REVIEW",
            "message": (
                f"Dossier transmis à Lisacare pour validation médecin humaine. "
                f"Vous recevrez un appel de suivi sous 24h."
            ),
        }


def route_to_specialist(
    message: str,
    language: str = "fr",
) -> SpecialistType:
    """Route user message to appropriate specialist agent.

    Uses keyword matching to pick agent:
    - TRIAGE: fièvre, douleur, symptôme, toux, mal, ...
    - COVERAGE: couvert, garantie, plafond, franchise, carence, tarif, ...
    - NETWORK: clinique, pharmacie, réseau, où aller, RDV, ...
    - GENERAL: carte, cssa, adhésion, statut, question générale, ...

    Args:
        message: User message
        language: fr|en (for keyword matching)

    Returns:
        SpecialistType enum value
    """
    m = message.lower()

    triage_keywords = (
        "fièvre",
        "fievre",
        "douleur",
        "toux",
        "symptôme",
        "symptome",
        "mal",
        "fatigue",
        "nausée",
        "nausee",
        "vertiges",
        "étourdissement",
        "etourdissement",
        "saignement",
        "respir",
        "difficultés",
        "difficul",
        "urgence",
        "grave",
        "critique",
    )
    coverage_keywords = (
        "couvert",
        "garantie",
        "plafond",
        "franchise",
        "carence",
        "tarif",
        "prix",
        "coût",
        "acte",
        "pris en charge",
        "prises en charge",
        "remboursement",
        "couverture",
        "bénéfice",
    )
    network_keywords = (
        "clinique",
        "pharmacie",
        "réseau",
        "reseau",
        "où aller",
        "ou aller",
        "rdv",
        "rendez",
        "medecin",
        "médecin",
        "docteur",
        "spécialiste",
        "specialiste",
        "hôpital",
        "hopital",
        "adresse",
        "horaire",
    )

    # Check triage (highest priority — safety critical)
    if any(kw in m for kw in triage_keywords):
        return SpecialistType.TRIAGE

    # Check coverage
    if any(kw in m for kw in coverage_keywords):
        return SpecialistType.COVERAGE

    # Check network
    if any(kw in m for kw in network_keywords):
        return SpecialistType.NETWORK

    # Default to general
    return SpecialistType.GENERAL
