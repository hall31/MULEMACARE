# Plan — Tarifs + canaux de paiement (corrigé)

> **Statut : IMPLÉMENTÉ 2026-08-30** (register-first WhatsApp, Qonto HITL, Stripe diaspora, TariffCatalog).  
> Produit : MulemaCare · Canon : [`prd.md`](./prd.md) · Stripe : [`STRIPE_DIASPORA.md`](./STRIPE_DIASPORA.md) · [`WHATSAPP_ADHESION.md`](./WHATSAPP_ADHESION.md) · [`QONTO_DIASPORA.md`](./QONTO_DIASPORA.md)  
> Date : 2026-08-30 · Diaspora = **Stripe** ou **Qonto** ; Afrique MoMo = **enregistrement + WhatsApp + HITL** (Stripe MoMo = Later si compte prêt).

---

## 1. Objectif business

1. **Tarifs** : une seule grille versionnée (simulateur, site, Stripe Prices, messages desk).  
2. **Encaissement** : 3 rails clairs, activation carte seulement après preuve machine ou HITL.

**KPI :** conversion devis→`ACTIVE` diaspora (Stripe + Qonto) ; délai médian Qonto HITL < 1 j ouvré ; 0 écart tarif affiché vs facturé.

---

## 2. Matrice de paiement (canon produit)

| Segment | Devise | Canal principal | Activation `ACTIVE` | WhatsApp |
|---------|--------|-----------------|---------------------|----------|
| **Diaspora** | EUR / USD | **1. Stripe Checkout** (carte / paiement en ligne) | Webhook Stripe signé | Support / relance uniquement |
| **Diaspora** | EUR / USD | **2. Virement vers compte Qonto** | Ops confirme + HITL (IBAN + réf CSSA) | Envoi preuve / CSSA au desk |
| **Afrique** | XAF | **Orange Money / MTN MoMo via Stripe** | Webhook Stripe (Payment Method Mobile Money) | Support si échec / aide USSD |
| Entreprise | multi | Devis RH + Qonto ou Stripe | HITL + preuve | Négociation desk |

### Règle d’or

Aucune carte `ACTIVE` sans :

- webhook **Stripe** valide (Checkout carte **ou** Mobile Money), **ou**
- **virement Qonto** vérifié + décision **OPS/ADMIN** (HITL).

**Never :** ACTIVE sur simple message WhatsApp sans preuve Qonto/MoMo ni webhook.

### Rôle WhatsApp (réduit)

- Inscription assistée (desk crée le dossier / renvoie le lien `/adhesion`).  
- Relance PENDING.  
- Réception **capture** virement Qonto (réf + CSSA).  
- Aide si Stripe MoMo échoue.  
- **Pas** un substitut à Stripe diaspora ni à Qonto.

---

## 3. Architecture cible

```text
                 ┌─────────────────────────────┐
                 │  Tariff Catalog vN (JSON)   │
                 └───────────┬─────────────────┘
                             │
     ┌───────────────────────┼───────────────────────┐
     ▼                       ▼                       ▼
 Stripe Checkout        Stripe Mobile Money      Virement Qonto
 EUR/USD carte          Orange / MTN (XAF)       IBAN + libellé CSSA
 webhook → ACTIVE       webhook → ACTIVE         HITL ops → ACTIVE
                             │
                    WhatsApp = desk / preuve / support
```

---

## Partie A — Mise à jour des tarifs

*(Inchangé dans l’esprit — catalogue versionné + HITL publish.)*

### A0 — Gouvernance (0,5 j)

| Ticket | DoD |
|--------|-----|
| A0-1 | Propriétaire tarif + calendrier publish |
| A0-2 | Canon `site/data/tariffs/vYYYY-MM-DD.json` |
| A0-3 | `tariff_version` sur devis / membership |
| A0-4 | Checklist sync : config · llms · UI · **Stripe Price map** · montants Qonto affichés |

### A1 — Catalogue versionné (1–1,5 j)

| Ticket | DoD |
|--------|-----|
| A1-1 | `TariffCatalog` JSON + fallback `config.php` |
| A1-2 | Schéma plan / composition / currency / cycle / amount / ceiling |
| A1-3 | Remise annuelle configurable |
| A1-4 | Devis figés sur `tariff_version` à l’émission |

### A2 — Admin Formules & tarifs (1,5–2 j)

Draft → proposal `tariff_publish` HITL ADMIN → publish + rollback `TARIFF_ACTIVE_VERSION`.  
**Never :** auto-publish ; édition live prod sans version.

### A3 — Sync canaux (1 j)

| Canal | Action |
|-------|--------|
| Site / simulateur | Lit catalogue |
| `llms.txt` | Généré depuis catalogue |
| Stripe | `stripe_price_map` + recreate Price si montant change |
| Qonto UX | Montant + libellé obligatoire `CSSA-…` sur le virement |
| OS QuoteAdvisor | Aligné catalogue |

### A4 — Runbook publish

1. Draft vN+1 → preview → HITL ADMIN.  
2. Activer version.  
3. Recréer Stripe Prices EUR/USD (+ XAF MoMo si applicable).  
4. Smoke : devis + Checkout test + écran Qonto montant.  
5. Banner optionnel « Tarifs au [date] ».

---

## Partie B — Rails de paiement

### B0 — Diaspora : Stripe en ligne (déjà Sprint 1 — à durcir)

| Ticket | DoD |
|--------|-----|
| B0-1 | `/adhesion` EUR/USD → Checkout Subscription (existant) |
| B0-2 | UI claire : « Payer en ligne (carte) » = CTA primaire diaspora |
| B0-3 | Sync Price IDs avec catalogue (lien A3) |
| B0-4 | Tests webhook PENDING→ACTIVE inchangés / verts |

### B1 — Diaspora : virement Qonto (nouveau, ~2 j)

```text
CTA « Virement bancaire (Qonto) »
  → POST /api/subscribe (payment_method=qonto|bank_transfer)
  → membre PENDING_PAYMENT + amount_due + tariff_version
  → page instructions : IBAN Qonto + BIC + libellé = CSSA-…
  → user vire + (option) envoie preuve WhatsApp
  → ops : file PENDING qonto → confirmer → HITL → ACTIVE
```

| Ticket | DoD |
|--------|-----|
| B1-1 | Env : `QONTO_IBAN`, `QONTO_BIC`, `QONTO_ACCOUNT_NAME`, `QONTO_BANK_LABEL` (jamais en git) |
| B1-2 | Page `/adhesion` success PENDING : IBAN copy + montant + libellé CSSA |
| B1-3 | Admin : file `PENDING_PAYMENT` canal `qonto` |
| B1-4 | `POST /api/admin/payments/qonto/confirm` → proposal `qonto_payment_confirm` HITL |
| B1-5 | Approve → `ACTIVE` + audit (acteur, montant, réf virement) |
| B1-6 | WhatsApp template **preuve Qonto** (CSSA + montant) — support, pas paiement |

**Never :** créditer ACTIVE sans rapprochement humain (API Qonto auto = Later).

### B2 — Afrique : Orange Money / MoMo via Stripe (~2–2,5 j)

```text
CTA « Orange Money / MTN MoMo »
  → POST /api/subscribe (payment_method=orange_money|mtn_momo, currency=XAF)
  → Stripe Checkout / Payment Element avec PM Mobile Money
  → webhook → ACTIVE (même pipeline que diaspora carte)
```

| Ticket | DoD |
|--------|-----|
| B2-1 | Activer Payment Methods Orange Money / MTN MoMo sur le compte Stripe (ops Dashboard) |
| B2-2 | `StripePaymentService` : session XAF + `payment_method_types` adaptés (ou automatic_payment_methods) |
| B2-3 | UI `/adhesion` XAF : CTA Stripe MoMo (pas « payer hors Stripe ») |
| B2-4 | Webhook : même chemin d’activation que carte (idempotent) |
| B2-5 | Fallback UI si PM indispo : message + WhatsApp support (PENDING, pas ACTIVE) |
| B2-6 | Tests : mock session XAF + webhook ACTIVE |

**Risque produit :** disponibilité Stripe Mobile Money selon pays / compte. Si XAF non supporté sur le compte → rester PENDING + desk (Qonto ou preuve MoMo HITL) jusqu’à activation Stripe — **ne pas inventer un PSP parallèle NOW**.

### B3 — WhatsApp (support only) (~1 j)

| Ticket | DoD |
|--------|-----|
| B3-1 | CTAs « Besoin d’aide » / « Envoyer ma preuve de virement » → `wa.me` avec CSSA + montant |
| B3-2 | Admin « Créer dossier + renvoyer lien paiement » (Stripe ou Qonto) |
| B3-3 | Deep-link `/adhesion?plan=…&currency=…` préremplit le tunnel |
| B3-4 | Later : WhatsApp Cloud API ; OCR preuve |

### B4 — UX adhésion (0,5–1 j)

**Diaspora (EUR/USD) — choix explicite :**

1. Payer en ligne (Stripe) — primaire  
2. Virement Qonto — secondaire  

**Afrique (XAF) :**

1. Orange Money / MoMo (Stripe) — primaire  
2. Aide WhatsApp si échec  

Badges admin : `stripe` · `stripe_momo` · `qonto`.

États : loading / empty / error / success / `pending_payment` / locked.

---

## 4. Sprints ordonnés

| Sprint | Contenu | Durée |
|--------|---------|--------|
| **T0** | Gouvernance + extract catalogue v0 | 0,5–1 j |
| **T1** | `TariffCatalog` + `tariff_version` + tests | 1–1,5 j |
| **T2** | Admin draft → HITL publish | 1,5–2 j |
| **T3** | Sync llms + Stripe price map | 1 j |
| **P0** | Diaspora Stripe UI + Price map (durcissement) | 0,5 j |
| **P1** | Virement Qonto + file HITL confirm | 2 j |
| **P2** | Stripe Orange Money / MoMo (XAF) | 2–2,5 j |
| **P3** | WhatsApp support + deep-link + preuves Qonto | 1 j |
| **QA** | Tests + smoke 3 rails | 0,5 j |

**Ordre recommandé :** T0→T1 → **P0→P1** (cash diaspora complet) → **P2** (Afrique Stripe) → T2→T3 // P3.

Durée estimée : **9–12 jours**.

---

## 5. Risques

| Risque | Mitigation |
|--------|------------|
| Double paiement Stripe + Qonto | Verrou statut ; confirm Qonto refuse si déjà ACTIVE Stripe |
| Stripe MoMo indispo XAF | Feature flag ; fallback PENDING + desk ; pas de faux CTA |
| Libellé virement sans CSSA | UI copy obligatoire + rejet ops si libellé manquant |
| IBAN Qonto en clair dans repo | Env only + `.env.example` placeholders |
| Écart tarif | Catalogue unique + checklist A0-4 |

---

## 6. Tradeoffs

| Now | Later | Never |
|-----|-------|-------|
| Stripe diaspora + Qonto HITL | API rapprochement Qonto auto | ACTIVE sans webhook / sans HITL Qonto |
| Stripe MoMo XAF si compte prêt | Autre PSP (Flutterwave…) | Remplacer Stripe diaspora par WhatsApp |
| WhatsApp = support / preuve | Cloud API + OCR | Paiement « virtuel » WhatsApp sans rail |

---

## 7. Vérification

```bash
make qa-mulemacare
php site/tests/test_tariff_catalog.php
php site/tests/test_qonto_payment_hitl.php
php site/tests/test_stripe_momo_xaf.php   # mock

# Manuels
# 1) EUR Stripe → ACTIVE (régression)
# 2) EUR Qonto → PENDING → confirm HITL → ACTIVE
# 3) XAF MoMo Stripe → ACTIVE (ou PENDING + message si PM off)
# 4) Publish tarif vN+1 → montants cohérents 3 rails
```

---

## 8. Livrables docs

| Fichier | Rôle |
|---------|------|
| Ce plan | Canon tarifs + **matrice paiement** |
| `docs/TARIFF_RUNBOOK.md` | Publish tarifs (T0) |
| `docs/QONTO_DIASPORA.md` | Ops IBAN + rapprochement (P1) |
| `docs/STRIPE_DIASPORA.md` | Mettre à jour : + MoMo XAF + lien Qonto |
| `sprint-board.md` | Sprints T* / P* après go |

---

## 9. Décision produit (figée ici)

> **Diaspora** = paiement en ligne **Stripe** **ou** virement **Qonto**.  
> **Orange Money / MoMo** = paiement **via Stripe**.  
> **WhatsApp** = inscription assistée, support, envoi de preuves — **pas** le moyen de paiement.
