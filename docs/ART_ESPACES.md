# ART — Espaces Adhérent & Admin (SA0)

> Bio-Clinical Emerald · source maquettes `docs/adherent.html` + `docs/admin.html`  
> 2026-08-30

## Tokens

| Token | Valeur |
|-------|--------|
| `--em` | `#097268` |
| `--em5` | `#0D9488` |
| `--em9` | `#064A43` |
| `--em050` | `#F0FAF8` |
| `--bg` | `#F6F9FB` |
| `--ink` | `#0F172A` |
| `--line` | `#E2E8F0` |
| Display | Outfit |
| Body | Plus Jakarta Sans |
| Numerics | Inter tabular |

## Gates

- Split panel : gauche brand dark/emerald, droite formulaire.
- Un job : s’authentifier. Pas de stats dans le gate.
- États : `idle` · `loading` · `error` · `success` · `locked` (rate-limit) · `2fa` (admin enroll/verify).

## Shells

| Surface | Layout |
|---------|--------|
| Adhérent | Top bar sticky + hub carte CSSA / plafond / claims |
| Admin | Sidebar dark 242px + main ; onglets Dashboard / Membres / Claims / HITL / Audit |

## RBAC (UI)

| État | MEMBER | OPS | ADMIN |
|------|--------|-----|-------|
| Voir sa carte | ✓ | — | — |
| HITL decide | — | ✓ | ✓ |
| Seed ops users | — | — | ✓ |
| Audit log | — | lecture | ✓ |

## Threat model (1 page)

| Menace | Contrôle |
|--------|----------|
| CSRF | Synchronizer token session + header/body `csrf_token` |
| Session fixation | `session_regenerate_id(true)` au login |
| Enumeration OTP | Toujours HTTP 200 + message générique ; rate-limit 5/h/IP |
| XSS token OS | Jamais de JWT OS dans le DOM ; proxy PHP + `service_token` serveur |
| Clickjacking | `X-Frame-Options: DENY` + CSP `frame-ancestors 'none'` |
| PII URL | Interdit lookup `?adh=` sans session |
| Brute force admin | Lockout 5 fails / 15 min + TOTP obligatoire |
