# Événements — MulemaCare One (contrat L0)

Statut : brouillon v0.1 · 2026-09-30 · à relire par un humain. Modification uniquement via `specs/CHANGE-REQUESTS.md`.

Six événements (PRD §6). Ils sont écrits dans la table `outbox_events` **dans la même transaction** que le changement d'état qui les cause, puis publiés (livraison « au moins une fois »). Tout consommateur est donc idempotent sur `event_id` (le grand livre stocke `event_id` dans `ledger_entries.source_event_id`, unique par organisation).

## Règles communes

- Enveloppe identique pour tous : `event_id`, `event_type`, `event_version`, `occurred_at` (UTC, RFC 3339), `organization_id`, `payload`.
- **Aucune donnée identifiante ni médicale** : pas de nom, téléphone, date de naissance, photo, motif médical. Seulement des identifiants pseudonymes (UUID internes) et des numéros de dossier (`PEC-…`, `J-…`).
- Montants : entiers FCFA (`*_xof`), devise explicite `currency: "XOF"`.
- Toute évolution incompatible crée `event_version: 2` ; la version 1 reste publiée pendant la transition.
- Codes de règle au format stable du contrat (`R-01`, `R-12`, `ID-03`, `HL-01`…).

| Événement | Producteur | Consommateurs |
|---|---|---|
| `claim.requested` | L5 (claims) | L8 (JOE, préparation), console |
| `claim.decided` | L5 (claims) | L3 (grand livre : accord → 6011 / 4011), notifications |
| `contribution.received` | L4 (payments) | L3 (grand livre : 512x / 7061), L4 (réouverture des droits) |
| `member.status_changed` | L4 (members) | notifications, L8 |
| `ledger.entry_posted` | L3 (ledger) | console, rapprochements |
| `authorization.synced` | L5 (claims) | L3, console, comptoir (file de synchro) |

## claim.requested

Demande de prise en charge enregistrée, avant décision.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://mulemacare.one/events/claim.requested/v1.json",
  "title": "claim.requested",
  "type": "object",
  "additionalProperties": false,
  "required": ["event_id", "event_type", "event_version", "occurred_at", "organization_id", "payload"],
  "properties": {
    "event_id": {"type": "string", "format": "uuid"},
    "event_type": {"const": "claim.requested"},
    "event_version": {"const": 1},
    "occurred_at": {"type": "string", "format": "date-time"},
    "organization_id": {"type": "string", "format": "uuid"},
    "payload": {
      "type": "object",
      "additionalProperties": false,
      "required": ["claim_id", "claim_number", "member_id", "beneficiary_id", "provider_id", "channel", "service_date", "total_xof", "currency", "items"],
      "properties": {
        "claim_id": {"type": "string", "format": "uuid"},
        "claim_number": {"type": "string", "pattern": "^PEC-[0-9]{2}-[0-9]{5,}$"},
        "member_id": {"type": "string", "format": "uuid"},
        "beneficiary_id": {"type": "string", "format": "uuid", "description": "persons.id du bénéficiaire (pseudonyme interne)"},
        "provider_id": {"type": "string", "format": "uuid"},
        "identity_check_id": {"type": ["string", "null"], "format": "uuid"},
        "channel": {"enum": ["comptoir", "comptoir_hors_ligne", "console"]},
        "service_date": {"type": "string", "format": "date"},
        "total_xof": {"type": "integer", "minimum": 0},
        "currency": {"const": "XOF"},
        "items": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["line_no", "act_code", "quantity", "amount_xof"],
            "properties": {
              "line_no": {"type": "integer", "minimum": 1},
              "act_code": {"type": "string"},
              "quantity": {"type": "integer", "minimum": 1},
              "amount_xof": {"type": "integer", "minimum": 0}
            }
          }
        }
      }
    }
  }
}
```

## claim.decided

Décision prise par une règle (`source: "regle"` : `rule` obligatoire) ou par un humain (`source: "humain"` : `decided_by` obligatoire) ; conditions exprimées en `if/then`. Émis à chaque décision, y compris la mise en revue. Le grand livre ne passe d'écriture que pour `accordee_auto` et `accordee`.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://mulemacare.one/events/claim.decided/v1.json",
  "title": "claim.decided",
  "type": "object",
  "additionalProperties": false,
  "required": ["event_id", "event_type", "event_version", "occurred_at", "organization_id", "payload"],
  "properties": {
    "event_id": {"type": "string", "format": "uuid"},
    "event_type": {"const": "claim.decided"},
    "event_version": {"const": 1},
    "occurred_at": {"type": "string", "format": "date-time"},
    "organization_id": {"type": "string", "format": "uuid"},
    "payload": {
      "type": "object",
      "additionalProperties": false,
      "required": ["claim_id", "claim_number", "decision_sequence", "outcome", "source", "reason_code", "member_id", "provider_id", "service_date", "plan_version_id", "total_xof", "covered_xof", "patient_share_xof", "currency"],
      "allOf": [
        {
          "if": {"properties": {"source": {"const": "regle"}}, "required": ["source"]},
          "then": {"required": ["rule"], "properties": {"rule": {"type": "object"}}}
        },
        {
          "if": {"properties": {"source": {"const": "humain"}}, "required": ["source"]},
          "then": {"required": ["decided_by"], "properties": {"decided_by": {"type": "string"}}}
        }
      ],
      "properties": {
        "claim_id": {"type": "string", "format": "uuid"},
        "claim_number": {"type": "string", "pattern": "^PEC-[0-9]{2}-[0-9]{5,}$"},
        "decision_sequence": {"type": "integer", "minimum": 1},
        "outcome": {"enum": ["accordee_auto", "en_revue", "accordee", "refusee", "pieces_demandees", "annulee"]},
        "source": {"enum": ["regle", "humain"]},
        "rule": {
          "type": ["object", "null"],
          "additionalProperties": false,
          "required": ["rule_id", "code", "version"],
          "properties": {
            "rule_id": {"type": "string", "format": "uuid"},
            "code": {"type": "string", "pattern": "^[A-Z]{1,3}-[0-9]{2}$"},
            "version": {"type": "integer", "minimum": 1}
          }
        },
        "reason_code": {"type": "string", "pattern": "^[A-Z]{1,4}-[0-9]{2}$"},
        "decided_by": {"type": ["string", "null"], "format": "uuid", "description": "users.id si décision humaine"},
        "member_id": {"type": "string", "format": "uuid"},
        "provider_id": {"type": "string", "format": "uuid"},
        "service_date": {"type": "string", "format": "date"},
        "plan_version_id": {"type": "string", "format": "uuid"},
        "total_xof": {"type": "integer", "minimum": 0},
        "covered_xof": {"type": "integer", "minimum": 0},
        "patient_share_xof": {"type": "integer", "minimum": 0},
        "currency": {"const": "XOF"}
      }
    }
  }
}
```

## contribution.received

Paiement confirmé et affecté à une cotisation (après vérification de signature et d'idempotence du webhook).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://mulemacare.one/events/contribution.received/v1.json",
  "title": "contribution.received",
  "type": "object",
  "additionalProperties": false,
  "required": ["event_id", "event_type", "event_version", "occurred_at", "organization_id", "payload"],
  "properties": {
    "event_id": {"type": "string", "format": "uuid"},
    "event_type": {"const": "contribution.received"},
    "event_version": {"const": 1},
    "occurred_at": {"type": "string", "format": "date-time"},
    "organization_id": {"type": "string", "format": "uuid"},
    "payload": {
      "type": "object",
      "additionalProperties": false,
      "required": ["contribution_id", "payment_id", "member_id", "period_start", "amount_xof", "currency", "channel", "payer_kind", "confirmed_at"],
      "properties": {
        "contribution_id": {"type": "string", "format": "uuid"},
        "payment_id": {"type": "string", "format": "uuid"},
        "member_id": {"type": "string", "format": "uuid"},
        "period_start": {"type": "string", "format": "date"},
        "amount_xof": {"type": "integer", "minimum": 0},
        "currency": {"const": "XOF"},
        "channel": {"enum": ["wave", "orange_money", "mtn_momo", "virement", "prelevement_employeur", "simulation"]},
        "payer_kind": {"enum": ["adherent", "employeur", "proche"]},
        "payer_country_code": {"type": ["string", "null"], "pattern": "^[A-Z]{2}$"},
        "confirmed_at": {"type": "string", "format": "date-time"}
      }
    }
  }
}
```

## member.status_changed

Changement de statut d'adhérent (adhésion, fin de carence, paiement confirmé, impayé à J+45, décision du gestionnaire).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://mulemacare.one/events/member.status_changed/v1.json",
  "title": "member.status_changed",
  "type": "object",
  "additionalProperties": false,
  "required": ["event_id", "event_type", "event_version", "occurred_at", "organization_id", "payload"],
  "properties": {
    "event_id": {"type": "string", "format": "uuid"},
    "event_type": {"const": "member.status_changed"},
    "event_version": {"const": 1},
    "occurred_at": {"type": "string", "format": "date-time"},
    "organization_id": {"type": "string", "format": "uuid"},
    "payload": {
      "type": "object",
      "additionalProperties": false,
      "required": ["member_id", "to_status", "reason_code", "effective_at"],
      "properties": {
        "member_id": {"type": "string", "format": "uuid"},
        "from_status": {"enum": ["actif", "carence", "suspendu", null]},
        "to_status": {"enum": ["actif", "carence", "suspendu"]},
        "reason_code": {"enum": ["adhesion", "fin_de_carence", "paiement_confirme", "impaye", "decision_gestionnaire"]},
        "rule": {
          "type": ["object", "null"],
          "additionalProperties": false,
          "required": ["code", "version"],
          "properties": {
            "code": {"type": "string", "pattern": "^[A-Z]{1,3}-[0-9]{2}$"},
            "version": {"type": "integer", "minimum": 1}
          }
        },
        "actor_user_id": {"type": ["string", "null"], "format": "uuid"},
        "effective_at": {"type": "string", "format": "date-time"}
      }
    }
  }
}
```

## ledger.entry_posted

Écriture validée (équilibrée par construction : la base refuse le COMMIT sinon).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://mulemacare.one/events/ledger.entry_posted/v1.json",
  "title": "ledger.entry_posted",
  "type": "object",
  "additionalProperties": false,
  "required": ["event_id", "event_type", "event_version", "occurred_at", "organization_id", "payload"],
  "properties": {
    "event_id": {"type": "string", "format": "uuid"},
    "event_type": {"const": "ledger.entry_posted"},
    "event_version": {"const": 1},
    "occurred_at": {"type": "string", "format": "date-time"},
    "organization_id": {"type": "string", "format": "uuid"},
    "payload": {
      "type": "object",
      "additionalProperties": false,
      "required": ["entry_id", "entry_number", "accounting_date", "source_type", "currency", "total_debit_xof", "total_credit_xof", "lines"],
      "properties": {
        "entry_id": {"type": "string", "format": "uuid"},
        "entry_number": {"type": "string"},
        "accounting_date": {"type": "string", "format": "date"},
        "source_type": {"enum": ["prise_en_charge", "cotisation", "reglement", "contre_passation"]},
        "source_id": {"type": ["string", "null"], "format": "uuid"},
        "source_event_id": {"type": ["string", "null"], "format": "uuid"},
        "reverses_entry_id": {"type": ["string", "null"], "format": "uuid"},
        "currency": {"const": "XOF"},
        "total_debit_xof": {"type": "integer", "minimum": 0},
        "total_credit_xof": {"type": "integer", "minimum": 0},
        "lines": {
          "type": "array",
          "minItems": 2,
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["line_no", "account_code", "debit_xof", "credit_xof"],
            "properties": {
              "line_no": {"type": "integer", "minimum": 1},
              "account_code": {"type": "string", "pattern": "^[0-9]{4,8}$"},
              "debit_xof": {"type": "integer", "minimum": 0},
              "credit_xof": {"type": "integer", "minimum": 0},
              "provider_id": {"type": ["string", "null"], "format": "uuid"},
              "member_id": {"type": ["string", "null"], "format": "uuid"}
            }
          }
        }
      }
    }
  }
}
```

## authorization.synced

Accord provisoire signé hors ligne sur un appareil de comptoir (R13), rapproché au retour du réseau. `outcome: "confirmee"` si la signature, la validité (2 h) et le seuil sont respectés ; sinon `"rejetee"` avec un code stable obligatoire (`reason_code`) (`OFF-01` expiré, `OFF-02` signature invalide, `OFF-03` au-dessus du seuil).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://mulemacare.one/events/authorization.synced/v1.json",
  "title": "authorization.synced",
  "type": "object",
  "additionalProperties": false,
  "required": ["event_id", "event_type", "event_version", "occurred_at", "organization_id", "payload"],
  "properties": {
    "event_id": {"type": "string", "format": "uuid"},
    "event_type": {"const": "authorization.synced"},
    "event_version": {"const": 1},
    "occurred_at": {"type": "string", "format": "date-time"},
    "organization_id": {"type": "string", "format": "uuid"},
    "payload": {
      "type": "object",
      "additionalProperties": false,
      "required": ["authorization_id", "claim_id", "device_id", "offline_ref", "outcome", "issued_at", "expires_at", "synced_at", "covered_xof", "currency"],
      "allOf": [
        {
          "if": {"properties": {"outcome": {"const": "rejetee"}}, "required": ["outcome"]},
          "then": {"required": ["reason_code"], "properties": {"reason_code": {"type": "string"}}}
        }
      ],
      "properties": {
        "authorization_id": {"type": "string", "format": "uuid"},
        "claim_id": {"type": "string", "format": "uuid"},
        "device_id": {"type": "string", "format": "uuid"},
        "offline_ref": {"type": "string", "format": "uuid"},
        "outcome": {"enum": ["confirmee", "rejetee"]},
        "reason_code": {"type": ["string", "null"], "pattern": "^[A-Z]{1,4}-[0-9]{2}$"},
        "rule": {
          "type": "object",
          "additionalProperties": false,
          "required": ["code", "version"],
          "properties": {
            "code": {"type": "string", "pattern": "^[A-Z]{1,3}-[0-9]{2}$"},
            "version": {"type": "integer", "minimum": 1}
          }
        },
        "issued_at": {"type": "string", "format": "date-time"},
        "expires_at": {"type": "string", "format": "date-time"},
        "synced_at": {"type": "string", "format": "date-time"},
        "covered_xof": {"type": "integer", "minimum": 0},
        "currency": {"const": "XOF"}
      }
    }
  }
}
```
