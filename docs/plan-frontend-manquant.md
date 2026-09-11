# Plan — Frontend manquant MulemaCare

> Canon : [`prd.md`](./prd.md) · [`prd-mcare.md`](./prd-mcare.md) · [`ART_ESPACES.md`](./ART_ESPACES.md) · [`MCARE_ART.md`](./MCARE_ART.md)  
> Maquettes : [`adherent.html`](./adherent.html) · [`admin.html`](./admin.html) · [`index.html`](./index.html)  
> Date : 2026-08-30 · Stack **Now** = PHP `site/` (Bio-Clinical Emerald) · **Later** = Next `cybernecs/mulemacare-web`  
> **Statut exécution : FE0–FE5 + Hub APIs DONE** · Gate `make qa-mulemacare` GREEN

---

## 1. Objectif business

Fermer l’écart **maquette ↔ prod** pour que diaspora et ops vivent le parcours vendable (carte, sinistres, réseau, MCare, HITL) sans alert() ni UI démo — conversion devis→paiement et rétention Silver+.

**KPI :** +20 % devis diaspora → paiement ; ≥ 35 % actifs utilisent MCare / mois ; NPS hub adhérent ≥ 45.

---

## 2. Inventaire — ce qui existe vs manque

### Déjà en prod (PHP)

| Surface | État |
|---------|------|
| Marketing (home, mutuelle, entreprises, réseau, partenaires, pays, devis, adhésion) | Présent — polish inégal vs `docs/index.html` |
| Stripe adhésion + retour `?paid=` | Présent |
| Gates `/login/adherent` · `/login/admin` | Auth OK — UI gate basique |
| `/espace-adherent` | Carte + plafond + bénéficiaires + claims table **partiel** |
| `/espace-admin` | Tabs membres/devis/claims/HITL/audit — **pas** le shell maquette |
| Borne clinique / verif carte | Présent (alerts) |
| Mutuelle OS API MCare | Backend tools — **0 UI chat** |

### Maquettes non portées (gap principal)

| Maquette adhérent | Dans PHP live ? |
|-------------------|-----------------|
| Shell app (top bar, nav Home / Sinistres / Couverture / Réseau / Paiements) | Non — page unique |
| Déclarer un sinistre (modal + états) | Non |
| Détail sinistre | Non |
| Couverture / plafonds par poste | Non |
| Recherche réseau + filtre tiers-payant | Non (page publique réseau ≠ hub) |
| Factures / payer maintenant (Stripe) | Partiel (retry PENDING only) |
| Notifications + toasts | Non (`alert`) |
| Switch devise EUR/USD/XAF | Non |
| Impression attestation soignée | Partiel (`window.print`) |

| Maquette admin | Dans PHP live ? |
|----------------|-----------------|
| Sidebar dark + layout app | Non — tabs dans page marketing |
| Dashboard KPIs réels (pas démo) | Partiel (`getDashboardStats`) |
| Fiche adhérent (drawer/modal) | Non |
| File sinistres (valider / pièces / refuser → HITL) | Non (liste claims brute) |
| CRUD réseau soins | Non |
| Formules & tarifs éditables | Non |
| HITL intégré dans file | Partiel (onglet séparé) |
| Toasts / empty / loading | Non |

| MCare | État |
|-------|------|
| Chat plein viewport + bénéficiaire | **Absent** |
| ClinCard tags IA | API only |
| Transmit + quota UI | API only |
| CTA diaspora → `/mcare` | Lien vers `/adhesion` (faux job) |
| Deep-link depuis espace adhérent | Bouton trompeur → adhesion |

| Acquisition polish | État |
|--------------------|------|
| Alignement home ↔ `docs/index.html` | Non fait |
| Landing MCare / pricing SKU | Absent |
| États loading/empty/error systématiques | Incomplets |
| Design tokens CSS centralisés | Inline par page |

---

## 3. Décision d’architecture FE

```text
NOW (2–3 sprints)     PHP packing des maquettes + MCare embed
                      Auth sessions déjà livrées (SA1–SA2)

LATER                 Next.js console cybernecs/mulemacare-web
                      (ops + MCare SPA) — après KPI PHP verts

NEVER                 Rewrite marketing PHP en Next dès J0
                      Obsidian neon / purple SaaS
```

**Principe :** porter `docs/adherent.html` et `docs/admin.html` **dans** `site/views` (HTML/CSS/JS) câblé aux APIs PHP/OS — pas de second stack tant que MCare conversion n’est pas prouvée.

---

## 4. Sprints frontend

### FE0 — Design system & Art (0,5–1 j)

| Ticket | DoD |
|--------|-----|
| FE0-1 | Extraire tokens communs → `site/assets/css/mulema-tokens.css` (+ Outfit / Plus Jakarta / Inter) |
| FE0-2 | Composants atomiques : btn, badge, toast, modal, empty, spinner (1 fichier JS `ui-kit.js`) |
| FE0-3 | Contrats Art : étendre `ART_ESPACES.md` + `MCARE_ART.md` (états 375/768/1280) |
| FE0-4 | Règle Zero Dead Button : chaque CTA = mutation state + feedback |

**Rollback :** CSS pages isolées inchangées.

---

### FE1 — Hub adhérent = maquette câblée (2–3 j) — **P0**

Porter le shell de `docs/adherent.html` derrière session MEMBER.

| Vue | API / source | États |
|-----|--------------|-------|
| Home | member session | loading / empty membership |
| Sinistres list+détail | `listClaims` scoped cssa | empty / error |
| Déclarer sinistre | `POST /api/claim` (member-scoped) | success toast + HITL note |
| Couverture | plan ceilings from config | — |
| Réseau | clinics config + search client | empty search |
| Paiements | status + Stripe checkout retry + factures stub | PENDING / ACTIVE |
| Attestation print | print CSS dédié | — |

| Ticket | DoD |
|--------|-----|
| FE1-1 | Remplacer `espace-adherent.php` monobloc par shell + `#view` |
| FE1-2 | Nav 5 vues + deep-link `?v=claims` |
| FE1-3 | Remplacer tous les `alert()` par toasts |
| FE1-4 | CTA MCare → `/mcare` (pas `/adhesion`) |
| FE1-5 | Tests smoke PHP / snapshot routes |

**Rollback :** flag `ADHERENT_HUB_V2=false` → ancienne page.

---

### FE2 — Hub admin = maquette câblée (2–3 j) — **P0**

Porter `docs/admin.html` shell derrière session OPS+TOTP.

| Vue | Câblage |
|-----|---------|
| Dashboard | `getDashboardStats` + pending HITL count |
| Adhérents | list + search/filter + fiche modal (PII masquée) |
| Sinistres | file ; actions → ActionCenter proposal (jamais auto) |
| HITL | intégré (badge count sidebar) |
| Réseau | lecture config (édition = Later) |
| Formules | lecture plans (édition = Later / HITL) |
| Audit | `audit.jsonl` tail |

| Ticket | DoD |
|--------|-----|
| FE2-1 | Layout sidebar + topbar Bio-Clinical (maquette) |
| FE2-2 | Fiche membre + toggle CSRF |
| FE2-3 | Claims ops → create proposal OS si enabled |
| FE2-4 | Kill alerts ; toasts + empty states |
| FE2-5 | Mobile : drawer sidebar |

**Rollback :** `ADMIN_HUB_V2=false`.

---

### FE3 — MCare chat UI (3–4 j) — **P0 commercial**

| Ticket | DoD |
|--------|-----|
| FE3-1 | Route `/mcare` + gate MEMBER ACTIVE |
| FE3-2 | Shell chat (brand MCare hero header, sélecteur bénéficiaire) |
| FE3-3 | Thread + composer ; POST conversations OS (proxy PHP session) |
| FE3-4 | Afficher tags `IA` + `Hypothèses non validées` |
| FE3-5 | Transmit → toast + quota restant ; état `quota_exhausted` |
| FE3-6 | CTA `/diaspora/{slug}` + home adhérent → `/mcare` |
| FE3-7 | Landing soft `/mcare/about` (SKU Essential/Family/Concierge) |

**SSE streaming :** PLUS TARD (réponses sync d’abord).  
**Rollback :** `MCARE_ENABLED=false`.

---

### FE4 — Acquisition polish (1,5–2 j) — **P1**

| Ticket | DoD |
|--------|-----|
| FE4-1 | Diff `docs/index.html` ↔ `home.php` : hero, simulateur, CTA Stripe, zero dead buttons |
| FE4-2 | Page `/mcare` marketing (si non logué) → login puis chat |
| FE4-3 | Diaspora pages : bloc MCare 1 job (headline + CTA) sans clutter |
| FE4-4 | Adhésion : états loading/success/error unifiés (toasts) |
| FE4-5 | Borne clinique : feedback UI sans `alert` |

---

### FE5 — Design QA & accessibilité (1 j) — **P1**

| Ticket | DoD |
|--------|-----|
| FE5-1 | Pass 375 / 768 / 1280 sur hubs + MCare + gates |
| FE5-2 | Focus visible, labels, `aria-live` toasts |
| FE5-3 | Contrast Bio-Clinical (pas de gris trop pâle) |
| FE5-4 | Checklist Zero Dead Button (grep `alert(` / `onclick={}` / href=#) |
| FE5-5 | `make qa-mulemacare` + smoke manuel documenté |

---

### FE6 — Console Next (Later) — **P2**

| Ticket | DoD |
|--------|-----|
| FE6-1 | App `web/` Next 16 · image `cybernecs/mulemacare-web` |
| FE6-2 | Migrer MCare + admin HITL en premier |
| FE6-3 | Auth : session bridge ou JWT httpOnly BFF |
| FE6-4 | Garder PHP pour SEO/acquisition |

**Ne pas démarrer FE6 avant FE3 vert + KPI soft.**

---

## 5. Ordre d’exécution

```text
FE0 tokens/toasts
 → FE1 hub adhérent (maquette)
 → FE2 hub admin (maquette)
 → FE3 MCare chat (vendable)
 → FE4 acquisition polish
 → FE5 a11y/QA
 → [gate KPI] FE6 Next later
```

Durée estimée **Now** : **10–14 jours** agent.

---

## 6. Risques

| Risque | Mitigation |
|--------|------------|
| Porter maquette = trop de JS monolithe | Découper `hub-adherent.js` / `hub-admin.js` / `mcare-chat.js` |
| Claim member sans auth partenaire confuse | Member declare = createClaim scoped + HITL ; borne reste partenaire later |
| MCare CTA mensonger | FE3 avant push commercial fort |
| Double stack trop tôt | FE6 gated KPI |

---

## 7. Tradeoffs

| Now | Later | Never |
|-----|-------|-------|
| PHP packing maquettes + MCare embed | Next console | Rewrite SEO site en Next |
| Toasts + shell app | SSE streaming MCare | Obsidian neon |
| Réseau/plans lecture seule admin | Édition tarifs HITL | Auto-valider sinistres dans l’UI |

---

## 8. Vérification

```bash
make qa-mulemacare
# Manuels FE5 : gates, hub adhérent 5 vues, admin sidebar, MCare transmit, diaspora CTA
grep -R "alert(" site/views/pages --include='*.php'   # viser 0 hors tests
```

---

## 9. Livrables docs

| Fichier | Rôle |
|---------|------|
| Ce plan | Carte gaps + sprints |
| `docs/ART_ESPACES.md` | Étendre FE0 |
| `docs/sprint-board.md` | Ajouter FE0–FE5 après go |
| `docs/MCARE_ART.md` | Inchangé (référence FE3) |
