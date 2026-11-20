"""Correspondances déclarées des sources connues.

``LARAVEL_2026`` : génération 2026 de Laravel (``mutual_formulas``, ``mutual_formula_cap_*``,
``mutual_subscriptions`` + ``users``, ``payments``, ``claims``, ``health_providers``), écrite
d'après les migrations de ``mulema-app/apps/mutuelle`` (lues en lecture seule, aucune ligne).

Chaque choix non prouvé par le code de l'existant est marqué « à confirmer » et listé dans
``specs/QUESTIONS.md`` (Q-L11-xx) : sens de ``users.name`` / ``users.surname``, ``users.age``
comme date de naissance, attributs du JSON ``beneficiaries``, rattachement de
``payments.subscription_id``, ville des prestataires (absente de ``health_providers``).

Non déclarées ici, faute de décision (PRD §10) : la génération ``subscription_aderents``
(formule et taux en texte : une table formule-texte → code de One est à fournir par Dajan) et
le site PHP (``mulema_*`` : aucune table de formule, nom en un seul champ, pas de date de
naissance, devise XAF et indicatif +237 par défaut — refusé par IMP-02 dans une organisation
XOF). Leurs statuts sont déjà dans ``statuses.STATUS_MAP``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from api.legacy_import.spec import (
    Dataset,
    EntitySpec,
    ImportSpec,
    JsonDependents,
    Key,
    Ref,
    validate_spec,
)

LARAVEL_2026: Final = validate_spec(
    ImportSpec(
        source="laravel_2026",
        version="laravel-2026.1",
        vocabularies={
            "relationship": {
                "spouse": "conjoint",
                "conjoint": "conjoint",
                "child": "enfant",
                "enfant": "enfant",
            },
            # HealthProvider::TYPE_* ; dentiste et opticien : type One à décider (Q-L11-05).
            "provider_kind": {
                "clinic": "clinique",
                "hospital": "hopital",
                "pharmacy": "pharmacie",
            },
            # HealthProvider::STATUS_* : seul un établissement approuvé est actif.
            "provider_status": {
                "approved": "actif",
                "pending": "suspendu",
                "rejected": "suspendu",
            },
            "country": {"CI": "CI", "SN": "SN", "+225": "CI", "+221": "SN"},
        },
        entities={
            "plan": EntitySpec(
                kind="plan",
                dataset=Dataset(
                    "formulas",
                    "SELECT id AS formula_id, code AS formula_code, name AS formula_name "
                    "FROM mutual_formulas",
                ),
                keys=(Key("formula_code", "formula_code"), Key("formula_id", "formula_id")),
                fields={"code": "formula_code", "name": "formula_name"},
            ),
            "plan_version": EntitySpec(
                kind="plan_version",
                dataset=Dataset(
                    "formula_versions",
                    "SELECT v.id AS cap_version_id, v.formula_id, v.effective_from, "
                    "v.effective_to, f.reimbursement_rate, v.global_cap_amount, "
                    "v.general_carence_days, f.base_premium, v.currency "
                    "FROM mutual_formula_cap_versions v "
                    "JOIN mutual_formulas f ON f.id = v.formula_id",
                ),
                keys=(Key("cap_version_id", "cap_version_id"),),
                refs={"plan": Ref("plan", "formula_id", "formula_id")},
                fields={
                    "valid_from": "effective_from",
                    "valid_to": "effective_to",
                    "coverage_rate_percent": "reimbursement_rate",
                    "family_annual_ceiling": "global_cap_amount",
                    "waiting_period_days": "general_carence_days",
                    "monthly_contribution": "base_premium",
                    "currency": "currency",
                },
            ),
            "coverage": EntitySpec(
                kind="coverage",
                dataset=Dataset(
                    "formula_coverages",
                    "SELECT CONCAT(i.cap_version_id, '-', c.code) AS coverage_key, "
                    "i.cap_version_id, c.code AS category_code, c.name AS category_name "
                    "FROM mutual_formula_cap_items i "
                    "JOIN mutual_acts a ON a.id = i.act_id "
                    "JOIN mutual_act_categories c ON c.id = a.category_id "
                    "GROUP BY i.cap_version_id, c.code, c.name",
                ),
                keys=(Key("coverage_key", "coverage_key"),),
                refs={"plan_version": Ref("plan_version", "cap_version_id", "cap_version_id")},
                fields={"category": "category_code", "label": "category_name"},
            ),
            "provider": EntitySpec(
                kind="provider",
                dataset=Dataset(
                    "providers",
                    "SELECT id AS health_provider_id, user_id AS provider_user_id, "
                    "establishment_name, establishment_type, country_code, "
                    "verification_status FROM health_providers",
                ),
                keys=(
                    Key("health_provider_id", "health_provider_id"),
                    Key("provider_user_id", "provider_user_id"),
                ),
                fields={
                    "name": "establishment_name",
                    "kind": "establishment_type",
                    "country": "country_code",
                    "status": "verification_status",
                },
                # health_providers n'a pas de ville : constante déclarée, à compléter (Q-L11-06).
                constants={"city": "A completer"},
            ),
            "member": EntitySpec(
                kind="member",
                dataset=Dataset(
                    "subscriptions",
                    "SELECT s.id AS subscription_row_id, s.subscription_number, "
                    "s.user_id AS legacy_user_id, s.formula_id, s.status, s.begin_date, "
                    "s.beneficiaries, u.name AS user_name, u.surname AS user_surname, "
                    "u.age AS user_birth_date, u.phone AS user_phone, u.phone_country_code, "
                    "u.email AS user_email "
                    "FROM mutual_subscriptions s JOIN users u ON u.id = s.user_id",
                ),
                keys=(
                    Key("subscription_number", "subscription_number"),
                    Key("subscription_row_id", "subscription_row_id"),
                    Key("legacy_user_id", "legacy_user_id"),
                ),
                person_keys=(Key("legacy_user_id", "legacy_user_id"),),
                refs={"plan": Ref("plan", "formula_id", "formula_id")},
                fields={
                    # Sens de name/surname et de age : à confirmer (Q-L11-01, Q-L11-02).
                    "family_name": "user_name",
                    "given_name": "user_surname",
                    "birth_date": "user_birth_date",
                    "phone": "user_phone",
                    "phone_country_code": "phone_country_code",
                    "email": "user_email",
                    "status": "status",
                    "enrolled_on": "begin_date",
                    "beneficiaries_json": "beneficiaries",
                },
                status_vocabulary="laravel_2026.subscription",
                # Attributs du JSON beneficiaries : à confirmer sur la structure réelle (Q-L11-03).
                json_dependents=JsonDependents(
                    given_name="first_name",
                    family_name="last_name",
                    birth_date="birth_date",
                    relationship="relationship",
                ),
            ),
            "contribution": EntitySpec(
                kind="contribution",
                dataset=Dataset(
                    "payments",
                    "SELECT id AS payment_row_id, subscription_id, amount, currency, "
                    "payment_date, status, type FROM payments",
                ),
                keys=(Key("payment_row_id", "payment_row_id"),),
                # payments.subscription_id → mutual_subscriptions.id : à confirmer (Q-L11-04).
                refs={"member": Ref("member", "subscription_row_id", "subscription_id")},
                fields={
                    "amount": "amount",
                    "currency": "currency",
                    "paid_on": "payment_date",
                    "status": "status",
                },
                status_vocabulary="laravel.payment",
                only_when={"type": frozenset({"paiement"})},
            ),
            "claim": EntitySpec(
                kind="claim",
                dataset=Dataset(
                    "claims",
                    "SELECT claim_reference, patient_id, provider_id, service_date, "
                    "amount_claimed, amount_approved, status FROM claims "
                    "WHERE deleted_at IS NULL",
                ),
                keys=(Key("claim_reference", "claim_reference"),),
                refs={
                    "member": Ref("member", "legacy_user_id", "patient_id"),
                    "provider": Ref("provider", "provider_user_id", "provider_id"),
                },
                fields={
                    "service_date": "service_date",
                    "total": "amount_claimed",
                    "covered": "amount_approved",
                    "status": "status",
                },
                status_vocabulary="laravel_2026.claim",
            ),
        },
    )
)

SPECS: Final[Mapping[str, ImportSpec]] = {"laravel_2026": LARAVEL_2026}
