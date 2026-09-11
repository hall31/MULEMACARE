# Plan — Admin super secure + Espace adhérent

> Produit : MulemaCare · Canon : [`prd.md`](./prd.md) · Maquettes : [`admin.html`](./admin.html), [`adherent.html`](./adherent.html)  
> Date : 2026-08-30 · Stack cible : **PHP site + Mutuelle OS JWT** (Next.js console = PLUS TARD)

---

## 1. Objectif business

Livrer deux espaces **authentifiés** (ops + adhérent) sans fuite PII via URL/lookup public, pour que le cash Stripe et le HITL soient opérés / consultés en confiance.

**KPI :** 0 accès PII sans session valide ; 100 % actions admin critiques (toggle, HITL decide) exigent rôle OPS/ADMIN + audit.

---

## 2. État actuel (gap)

| Surface | Aujourd’hui | Risque |
|---------|-------------|--------|
| `/espace-adherent` | Lookup `?adh=` **ou** fallback démo avec PII réelle-looking | Enumeration CSSA + PII exposée |
| `/espace-admin` | UI ops ouverte ; HITL via Bearer collé dans le DOM | Pas de gate ; token en localStorage/DOM |
| Maquettes `docs/*.html` | Gate login + layout app déjà designés | Non câblés |
| Mutuelle OS | JWT MEMBER/OPS/ADMIN | Pas encore le front de session PHP |

---

## 3. Architecture minimale

```text
Browser
  ├─ /login/adherent     magic-link ou OTP email/SMS → session PHP HttpOnly
  ├─ /login/admin        email+password + TOTP (2FA) → session PHP HttpOnly
  ├─ /espace-adherent    middleware session MEMBER (cssa_id bound)
  └─ /espace-admin       middleware session OPS|ADMIN + CSRF

Mutuelle OS (api/)
  └─ auth JWT (déjà) — PHP échange session ↔ service token court pour HITL/OS
```

**Décisions :**

1. **Session PHP HttpOnly Secure SameSite=Lax** pour les pages (pas de JWT en localStorage).
2. **Admin = 2FA obligatoire** (TOTP) dès le premier compte ops.
3. **Adhérent = magic link** (email Stripe / membership) + code 6 chiffres ; pas de mot de passe faible au lancement.
4. **PII** : masquer email/téléphone hors session ; logs sans PII claire.
5. **HITL / toggle** : CSRF + rôle serveur ; plus de token collé dans l’UI.
6. UI : porter le **gate + shell** des maquettes Bio-Clinical Emerald (`#097268`), pas Obsidian neon.

---

## 4. Personas & RBAC

| Rôle | Entrée | Voit | Peut |
|------|--------|------|------|
| **MEMBER** | Magic link / OTP | Sa carte, plafonds, bénéficiaires, claims, MCare CTA | Retry Stripe si PENDING ; ouvrir MCare |
| **OPS** | Login + 2FA | Membres, claims queue, ActionCenter | Approuver/rejeter proposals ; suspend (via HITL) |
| **ADMIN** | Login + 2FA | Tout OPS + audit + users ops | Créer ops ; rotation flags |
| **PARTNER** | PLUS TARD | Eligibility borne | Lecture seule |

---

## 5. Sprints (exécution)

### SA0 — Contrat & Art (0,5 j)

| Ticket | DoD |
|--------|-----|
| SA0-1 | Extraire tokens gate/shell depuis `docs/admin.html` + `docs/adherent.html` → `docs/ART_ESPACES.md` |
| SA0-2 | Matrice RBAC + états UI (loading/empty/error/success/locked/2fa) |
| SA0-3 | Threat model 1 page (CSRF, session fixation, enumeration, XSS token) |

### SA1 — Auth adhérent (1–1,5 j) — **priorité PII**

| Ticket | DoD |
|--------|-----|
| SA1-1 | Table/store `member_auth_challenges` (cssa_id, email hash, code, expires, used) |
| SA1-2 | `POST /api/auth/adherent/request` — rate-limit 5/h/IP + anti-enumeration (toujours 200) |
| SA1-3 | `POST /api/auth/adherent/verify` → session `role=MEMBER`, `cssa_id` |
| SA1-4 | Middleware : `/espace-adherent` **refuse** sans session ; **supprimer** fallback démo PII |
| SA1-5 | Gate UI (porter maquette) + logout |
| SA1-6 | Tests : no session → 302 ; mauvais code → 401 ; bon code → vue scoped |

**Rollback :** flag `MEMBER_AUTH_REQUIRED=false` (dev only) — **interdit en prod**.

### SA2 — Auth admin super secure (1,5–2 j)

| Ticket | DoD |
|--------|-----|
| SA2-1 | Users ops en DB (hash Argon2id) ; seed 1er ADMIN via CLI env |
| SA2-2 | Login email/password + enrollment TOTP (QR) obligatoire avant hub |
| SA2-3 | Session OPS/ADMIN ; idle timeout 30 min ; absolute 8 h |
| SA2-4 | CSRF double-submit ou synchronizer token sur toutes mutations |
| SA2-5 | Gate `/admin/login` ; `/espace-admin` derrière middleware |
| SA2-6 | Remplacer champ « Bearer OPS token » : PHP appelle OS avec **service token serveur** |
| SA2-7 | Headers : `Content-Security-Policy`, `X-Frame-Options: DENY`, no-cache sur pages auth |
| SA2-8 | Tests : sans session 302 ; sans 2FA bloqué ; CSRF fail 403 ; non-ADMIN ne crée pas d’ops |

**Rollback :** freeze admin (maintenance page) plutôt que open access.

### SA3 — Packing espace adhérent (1 j)

| Ticket | DoD |
|--------|-----|
| SA3-1 | Shell maquette : carte CSSA, plafond, bénéficiaires, claims **scopés session** |
| SA3-2 | CTA MCare + retry paiement Stripe si `PENDING_PAYMENT` |
| SA3-3 | Masquage PII partielle (email `e***@`, téléphone) hors besoin |
| SA3-4 | Empty/error : membership introuvable / suspendue / unpaid |

### SA4 — Packing admin + audit (1–1,5 j)

| Ticket | DoD |
|--------|-----|
| SA4-1 | Shell sidebar maquette (Dashboard, Membres, Claims, HITL, Audit) |
| SA4-2 | HITL list/decide sans token client |
| SA4-3 | Toggle status → **toujours** ActionCenter proposal (déjà OS) + trace audit PHP |
| SA4-4 | Journal audit : who/when/what/cssa/ip (append-only) |
| SA4-5 | Rate-limit admin API + lockout 5 fails / 15 min |

### SA5 — QA sécurité + gate (0,5 j)

| Ticket | DoD |
|--------|-----|
| SA5-1 | `make qa-mulemacare` + tests auth PHP/pytest |
| SA5-2 | Checklist : pas de PII dans URL ; pas de JWT navigateur ; CSP ; 2FA ; CSRF |
| SA5-3 | Mettre à jour `sprint-board.md` |

---

## 6. Risques

| Risque | Mitigation |
|--------|------------|
| Enumeration magic-link | Réponse générique + rate-limit + CAPTCHA later |
| OTP intercept email | TTL 10 min ; 1 usage ; binding IP soft |
| Admin password spray | Argon2id + lockout + 2FA |
| Session hijack | Secure + HttpOnly + regenerate on login |
| Token OS dans browser | Jamais ; proxy PHP serveur |

---

## 7. Tradeoffs

| Now | Later | Never |
|-----|-------|-------|
| Sessions PHP + magic link + admin 2FA | Next.js console + Passkeys / WebAuthn | Auth par seul `?adh=` CSSA |
| Porter maquettes HTML existantes | SSO Google Workspace ops | JWT en localStorage |
| Audit append file/DB | SIEM / OpenTelemetry full | Open admin sans 2FA « temporaire prod » |

---

## 8. Vérification

```bash
make qa-mulemacare
php site/tests/test_auth_adherent.php   # à créer
php site/tests/test_auth_admin.php      # à créer
# Manuels : gate UX 375/768/1280 ; 2FA enroll ; CSRF ; session expire
```

---

## 9. Ordre recommandé

```text
SA0 Art/threat → SA1 Adhérent auth (coupe la fuite PII) → SA2 Admin 2FA
→ SA3 Packing adhérent → SA4 Packing admin+audit → SA5 QA
```

Durée estimée : **5–7 jours** agent + ops (seed admin + secrets email SMTP).
