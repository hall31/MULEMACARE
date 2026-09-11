"""MCare Safety Guardrails — diagnosis detection, red flag detection, response validation.

Implements:
- DiagnosisDetector: regex + keyword patterns to detect diagnostic statements
- RedFlagDetector: critical symptom patterns requiring immediate medical attention
- SafetyEvaluator: orchestrates full response validation before transmission

All detection rules are language-aware (fr|en) and tuple-based for easy expansion.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class DiagnosisDetector:
    """Detects diagnosis statements in agent responses.

    Diagnosis is forbidden; only hypotheses are allowed.
    Examples:
    - FORBIDDEN: "vous avez une pneumonie" (you have pneumonia)
    - ALLOWED: "pourrait être une pneumonie, à explorer avec médecin"
    """

    def __init__(self, language: str = "fr"):
        """Initialize detector.

        Args:
            language: "fr" or "en" for language-specific patterns
        """
        self.language = language
        self._init_patterns()

    def _init_patterns(self) -> None:
        """Initialize diagnosis detection patterns per language."""
        if self.language == "fr":
            # French diagnosis patterns
            self.diagnosis_patterns = (
                r"\bvous\s+avez\s+(?:une?|du|de\s+la|des?)\s+",  # vous avez une X
                r"\bvous\s+êtes\s+(?:atteint|infecté|malade)",  # vous êtes atteint/infecté
                r"\bdiagnost(?:ique|iqué)\s+",  # diagnostiqué avec X
                r"\bvotre\s+condition\s+est\s+",  # votre condition est X
                r"\bvotre\s+maladie\s+est\s+",  # votre maladie est X
                r"\bcet\s+état\s+s?'appelle\s+",  # cet état s'appelle X (too definitive)
                r"\bc'est\s+(?:clairement|manifestement|évidemment)\s+",
                r"\bc'est\s+certainement\s+",  # c'est certainement X
                r"\bvous\s+souffrez\s+de\s+",  # vous souffrez de X
                r"\bil\s+y\s+a\s+(?:une?\s+)?infection\s+de\s+",  # il y a infection de X
            )

            self.benign_phrases = (
                "pourrait être",  # could be
                "suggère",  # suggests
                "possible",  # possible
                "à explorer",  # to explore
                "hypothèse",  # hypothesis
                "envisager",  # to consider
                "explorer",  # explore
                "médecin",  # doctor (context: should see doctor)
                "consultation",  # consult
            )
        else:
            # English diagnosis patterns
            self.diagnosis_patterns = (
                r"\byou\s+have\s+(?:a\s+)?",  # you have a X
                r"\byou\s+(?:are\s+)?(?:diagnosed|suffering|afflicted)\s+with\s+",
                r"\byour\s+condition\s+is\s+",  # your condition is X
                r"\byour\s+(?:disease|illness)\s+is\s+",  # your illness is X
                r"\bthis\s+is\s+(?:clearly|obviously|definitely)\s+",
                r"\byou\s+(?:definitely|certainly|have|clearly)\s+",
                r"\binfection\s+with\s+",  # infection with X
                r"\bdiagnosed\s+with\s+",  # diagnosed with X
            )

            self.benign_phrases = (
                "could be",
                "might be",
                "suggests",
                "possible",
                "to explore",
                "hypothesis",
                "consider",
                "see a doctor",
                "consult",
            )

    def detect(self, text: str) -> dict[str, Any]:
        """Detect if response contains diagnosis.

        Args:
            text: Agent response text

        Returns:
            {
                "diagnosis_detected": bool,
                "matches": [str],  # matched phrases
                "confidence": float (0.0-1.0),
            }
        """
        if not text:
            return {"diagnosis_detected": False, "matches": [], "confidence": 0.0}

        lower_text = text.lower()
        matches = []

        # Check for diagnosis patterns
        for pattern in self.diagnosis_patterns:
            found = re.finditer(pattern, lower_text, re.IGNORECASE)
            for match in found:
                # Extract context (50 chars before and after)
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].strip()
                matches.append(context)

        # If diagnosis pattern found, check if it's mitigated by benign phrases
        if matches:
            # Count benign phrases in vicinity
            benign_count = 0
            for phrase in self.benign_phrases:
                benign_count += lower_text.count(phrase)

            # High benign phrase count suggests mitigation
            diagnosis_confidence = max(0.0, min(1.0, len(matches) * 0.3 - benign_count * 0.1))

            return {
                "diagnosis_detected": diagnosis_confidence > 0.5,
                "matches": matches[:3],  # Return up to 3 matches
                "confidence": diagnosis_confidence,
            }

        return {"diagnosis_detected": False, "matches": [], "confidence": 0.0}


class RedFlagDetector:
    """Detects critical red flags requiring immediate medical attention.

    Red flags are symptoms/conditions that require urgent clinic or emergency visit.
    Examples:
    - Difficulty breathing / respiratory distress
    - Chest pain / cardiac symptoms
    - Loss of consciousness / seizures
    - Severe bleeding / trauma
    """

    def __init__(self, language: str = "fr"):
        """Initialize red flag detector.

        Args:
            language: "fr" or "en"
        """
        self.language = language
        self._init_flags()

    def _init_flags(self) -> None:
        """Initialize critical red flags per language."""
        if self.language == "fr":
            self.red_flag_patterns = (
                # Respiratory
                (r"difficultés?\s+(?:respiratoires?|à\s+respirer)", "respiratory_distress"),
                (r"(?:ne\s+peut\s+pas|ne\s+peut\s+plus)\s+respir", "respiratory_distress"),
                (r"asphyx|suffoc|étouff", "respiratory_distress"),
                (r"dyspnée", "respiratory_distress"),
                # Consciousness
                (r"(?:perte|perte\s+de)\s+conscience|inconscient", "loss_of_consciousness"),
                (r"syncope|évanouiss", "loss_of_consciousness"),
                # Seizures
                (r"convuls|crise|épileps|saisis", "seizure"),
                # Chest/Cardiac
                (r"douleur\s+(?:thoracique|à\s+la\s+poitrine|au\s+cœur|au\s+coeur)", "chest_pain"),
                (r"douleur\s+qui\s+irradie\s+(?:vers|au)", "chest_pain"),
                # Severe bleeding
                (r"saignement\s+(?:grave|important|abondant|incontrôlable)", "severe_bleeding"),
                (r"hémorrag|perte\s+de\s+sang\s+(?:grave|importante)", "severe_bleeding"),
                (r"crache\s+du\s+sang|hémoptys", "severe_bleeding"),
                # Severe abdominal pain
                (r"douleur\s+(?:abdominal|au\s+ventre)\s+(?:grave|extrême|intolérable)", "severe_abdominal_pain"),
                (r"rigidité\s+abdominale", "severe_abdominal_pain"),
                # Severe dehydration
                (r"déshydrat(?:ation)?|ne\s+peut\s+pas\s+boire", "severe_dehydration"),
                (r"pas\s+(?:urine|urinê|d'urine)", "severe_dehydration"),
                # Altered mental status
                (r"confusion|délirium|confusion\s+mentale", "altered_mental_status"),
                (r"incoherence|parole\s+incohérente", "altered_mental_status"),
                # High fever + severity
                (r"fièvre\s+(?:>|supérieure|supérieur|au-dessus)\s+40", "high_fever_severe"),
                (r"fièvre\s+(?:grave|extrême|dangereuse)", "high_fever_severe"),
                # Uncontrolled bleeding
                (r"saignement\s+(?:qu'on\s+ne\s+peut\s+pas|continu|persistent)", "uncontrolled_bleeding"),
            )
        else:
            # English red flag patterns
            self.red_flag_patterns = (
                (r"(?:difficulty|difficulty breathing|shortness of breath|can't breathe)", "respiratory_distress"),
                (r"asphyx|suffoc", "respiratory_distress"),
                (r"dyspn", "respiratory_distress"),
                (r"(?:loss of consciousness|unconscious|syncope|faint)", "loss_of_consciousness"),
                (r"seiz|convuls", "seizure"),
                (r"(?:chest pain|cardiac|heart pain|chest discomfort)", "chest_pain"),
                (r"(?:pain radiating|pain spreading)", "chest_pain"),
                (r"(?:severe bleeding|hemorrhage|uncontrolled bleeding)", "severe_bleeding"),
                (r"(?:cough up blood|hemoptysis)", "severe_bleeding"),
                (r"(?:severe abdominal pain|rigidity)", "severe_abdominal_pain"),
                (r"(?:severe dehydration|can't drink)", "severe_dehydration"),
                (r"(?:confusion|delirium|altered mental)", "altered_mental_status"),
                (r"fever\s+(?:>|greater|above)\s+40", "high_fever_severe"),
                (r"(?:uncontrolled bleeding|continuous bleeding)", "uncontrolled_bleeding"),
            )

    def detect(self, text: str) -> dict[str, Any]:
        """Detect red flags in text.

        Args:
            text: Agent response or symptom description

        Returns:
            {
                "has_red_flags": bool,
                "flags": [{"type": str, "text": str}],  # detected flags
            }
        """
        if not text:
            return {"has_red_flags": False, "flags": []}

        lower_text = text.lower()
        detected_flags = []
        seen_types = set()

        for pattern, flag_type in self.red_flag_patterns:
            matches = re.finditer(pattern, lower_text, re.IGNORECASE)
            for match in matches:
                if flag_type not in seen_types:
                    # Extract context
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 30)
                    context = text[start:end].strip()

                    detected_flags.append({"type": flag_type, "text": context})
                    seen_types.add(flag_type)

        return {
            "has_red_flags": len(detected_flags) > 0,
            "flags": detected_flags[:5],  # Return up to 5 flags
        }


class SafetyEvaluator:
    """Orchestrates full safety evaluation of MCare agent responses.

    Runs all detectors (diagnosis, red flags) and produces a pass/fail verdict.
    """

    def __init__(
        self,
        diagnosis_detector: DiagnosisDetector,
        red_flag_detector: RedFlagDetector,
    ):
        """Initialize evaluator with detectors.

        Args:
            diagnosis_detector: DiagnosisDetector instance
            red_flag_detector: RedFlagDetector instance
        """
        self.diagnosis_detector = diagnosis_detector
        self.red_flag_detector = red_flag_detector

    def evaluate(self, response: str) -> dict[str, Any]:
        """Full safety evaluation of response.

        Returns:
            {
                "passed": bool,  # True if safe to send to user
                "issues": [str],  # List of safety issues found
                "diagnosis_detected": bool,
                "red_flags_detected": bool,
                "diagnosis_confidence": float,
            }
        """
        issues = []

        # Check for diagnosis
        diagnosis_result = self.diagnosis_detector.detect(response)
        if diagnosis_result["diagnosis_detected"]:
            issues.append(
                f"Diagnosis detected (confidence: {diagnosis_result['confidence']:.1%}): "
                f"{diagnosis_result['matches'][0][:100] if diagnosis_result['matches'] else 'unknown'}"
            )

        # Check for red flags
        red_flag_result = self.red_flag_detector.detect(response)
        if red_flag_result["has_red_flags"]:
            flag_list = ", ".join(f["type"] for f in red_flag_result["flags"])
            issues.append(f"Red flags detected: {flag_list}")
            logger.warning(f"Red flags in response: {red_flag_result['flags']}")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "diagnosis_detected": diagnosis_result["diagnosis_detected"],
            "red_flags_detected": red_flag_result["has_red_flags"],
            "diagnosis_confidence": diagnosis_result["confidence"],
        }
