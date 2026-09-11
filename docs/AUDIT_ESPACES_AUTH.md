# Audit code — post SA0–SA5 (2026-08-30)

## Scope

Auth adhérent/admin, packing espaces, HITL proxy, gate QA `make qa-mulemacare`.

## Verdict

**PASS conditionnel** — fondations auth livrées et tests verts. Ops humains + SMTP OTP + hardening claim/partner restent hors scope automatisé.

## Preuves gate

| Check | Résultat |
|-------|----------|
| `php site/tests/test_auth_espaces.php` | PASS (OTP, CSRF, Argon2id, TOTP) |
| Stripe webhook PHP tests | PASS |
| `pytest` Mutuelle OS | 8 passed |
| `make qa-mulemacare` | GREEN |

## Exigences plan → statut

| Exigence | Preuve | Statut |
|----------|--------|--------|
| SA0 ART + threat | `docs/ART_ESPACES.md` | Done |
| Adhérent OTP + session | `AuthService` + `/login/adherent` | Done |
| Kill démo PII / `?adh=` | `espace-adherent` session-only | Done |
| Admin Argon2 + TOTP | `seed_admin.php` + `/login/admin` | Done |
| CSRF mutations | toggle + HITL decide | Done |
| Pas de JWT OS dans le DOM | proxy `service_token` | Done |
| Headers sécurité gates | CSP / XFO / no-store | Done |
| Audit trail | `audit.jsonl` + onglet admin | Done |
| Packing adhérent/admin | gates + logout + HITL sans token | Done (maquette partielle) |

## Findings (sévérité)

### High — mitigé

| ID | Finding | Mitigation livrée |
|----|---------|-------------------|
| A1 | Lookup public PII | Session MEMBER/OPS + masquage email/tél |
| A2 | Admin ouvert + Bearer DOM | Gate 2FA + service token serveur |
| A3 | Démo PII Eric Awono | Supprimée adhérent + admin empty state |

### Medium — rester vigilant

| ID | Finding | Action |
|----|---------|--------|
| M1 | OTP non envoyé par email réel (log only) | Brancher SMTP/Resend ; garder `MULEMACARE_AUTH_DEBUG` off en prod |
| M2 | `POST /api/claim` sans auth partenaire | SA-PARTNER later (HMAC clinique) |
| M3 | DB IONOS DNS noise en local | OK fallback JSON ; ne pas logger credentials |

### Low

| ID | Finding | Action |
|----|---------|--------|
| L1 | JWT test secret < 32 bytes (warning PyJWT) | Allonger `JWT_SECRET` en prod |
| L2 | Admin shell encore dark custom vs maquette claire | Polish UI later |
| L3 | Deprecated `ReflectionProperty::setAccessible` PHP 8.5 tests | Cleanup test helpers |

## Invariants à préserver

1. `MEMBER_AUTH_REQUIRED=true` en prod.
2. `MULEMACARE_AUTH_DEBUG=false` en prod (sinon OTP/TOTP secrets exposés).
3. Aucune auto-approve claim/préauth.
4. Seed admin via CLI env only — jamais commit de password.

## Ops humain

```bash
ADMIN_EMAIL=ops@… ADMIN_PASSWORD='…' php site/tools/seed_admin.php
# Configurer MULEMACARE_OS_SERVICE_TOKEN + Stripe webhook Dashboard
```
