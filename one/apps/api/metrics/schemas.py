"""Schémas de la mesure produit, conformes aux composants ``Product*`` de specs/openapi.yaml.

Requête : modèle FERMÉ (``extra="forbid"``) et STRICT (aucune conversion : ``"1200"``, ``true``
ou ``12.5`` ne deviennent pas des entiers). Seuls des noms en liste blanche, des énumérations
et des entiers bornés passent : aucun champ ne peut porter de texte libre.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

type EventName = Literal[
    "onboarding_started",
    "onboarding_step",
    "onboarding_completed",
    "card_presented",
    "counter_decision_shown",
    "payment_link_created",
    "palette_opened",
    "joe_question_asked",
    "notification_opened",
    "offline_banner_seen",
    "claim_tracking_viewed",
]
type Surface = Literal["console", "comptoir", "espace_adherent"]
type Variant = Literal[
    "en_ligne",
    "hors_ligne",
    "accordee",
    "revue",
    "refusee",
    "clavier",
    "bouton",
    "exemple",
    "saisie",
    "sms",
    "whatsapp",
    "in_app",
]
type RoleValue = Literal[
    "gestionnaire",
    "medecin_conseil",
    "clinique",
    "employeur",
    "admin",
    "adherent",
    "assureur",
    "admin_plateforme",
]
type MetricKey = Literal[
    "claims_auto_approved_rate",
    "claims_review_rate",
    "claims_decision_median_ms",
    "counter_decision_display_median_ms",
    "onboarding_completion_rate",
    "first_card_median_ms",
    "payment_links_paid_rate",
    "ledger_balance_gap_xof",
    "webhook_duplicate_rate",
]
type MetricUnit = Literal["pour_dix_mille", "millisecondes", "xof"]

# Exactement 16 octets aléatoires en hexadécimal minuscule (CR-P2-02) : aucune place pour un
# texte, un courriel, un numéro avec séparateurs. Validé puis écarté : ni stocké ni dérivé.
SESSION_PATTERN = r"^[0-9a-f]{32}$"
# Plafond commun ; chaque événement qui admet une durée a sa propre borne (``catalog``).
MAX_DURATION_MS = 3_600_000
MAX_STEP = 20


class ProductEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: EventName
    surface: Surface
    role: RoleValue
    session_id: Annotated[str, Field(pattern=SESSION_PATTERN)]
    duration_ms: Annotated[int, Field(ge=0, le=MAX_DURATION_MS)] | None = None
    step: Annotated[int, Field(ge=1, le=MAX_STEP)] | None = None
    variant: Variant | None = None


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True)


class ProductMetric(_Out):
    key: MetricKey
    unit: MetricUnit
    status: Literal["disponible", "masque"]
    value: int | None
    contributors: int | None


class ProductMetrics(_Out):
    period_from: date
    period_to: date
    generated_at: datetime
    k_anonymity_threshold: int
    items: list[ProductMetric]
