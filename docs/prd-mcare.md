# PRD — MCare : Chat Famille Diaspora (interface type ChatGPT)

> **Produit commercial :** **MCare** — assistant conversationnel santé & mutuelle pour les familles de la diaspora  
> **Maison mère :** MulemaCare Health Group (`mulemacare.com`)  
> **Référence produit sœur :** KijamiCare / Dr Benji (`APPS/PUBLIC/HEALTH/KIJAMICARE`) — même pattern UX/éthique, marque & stack MulemaCare  
> **Date :** 2026-08-30  
> **Statut :** PRD vente + livraison (à brancher sur Mutuelle OS / site PHP)  
> **Design :** Bio-Clinical Emerald MulemaCare (`#097268`) — pas Warm Clinical Kijami, pas Obsidian neon

**Doc liée :** [`prd.md`](./prd.md) (mutuelle full AI agentic) · Bridge [`HEALTHOS_BRIDGE.md`](./HEALTHOS_BRIDGE.md)

---

## 1. Objectif business mesurable

Vendre aux **sponsors diaspora** (FR / EU / US / UK) une **interface chat type ChatGPT** qui leur permet, en langage naturel, de :

1. comprendre la couverture de **leur famille au pays**,
2. orienter un proche (triage pré-clinique),
3. déclencher les bons gestes mutuelle (carte CSSA, réseau, Lisacare, préauth),

…sans se perdre dans des formulaires, et **sans jamais laisser l’IA diagnostiquer ou engager la couverture seule**.

**KPI nord (90 j post-lancement) :** ≥ 35 % des adhérents diaspora actifs utilisent MCare ≥ 1× / mois ; **KPI conversion :** +20 % taux devis diaspora → paiement vs parcours formulaire seul ; **KPI clinique :** 100 % des orientations transmises portent tags `IA` + `Hypothèses non validées` et file médecin humaine.

---

## 2. Hypothèse de valeur + KPI

| Hypothèse | Preuve |
|-----------|--------|
| Le chat réduit l’anxiété « mon parent est malade, que faire ? » plus vite qu’un call center | Médiane 1ʳᵉ réponse utile < 30 s ; NPS MCare ≥ 45 |
| Bundler MCare dans Silver+ augmente l’upsell Bronze → Silver | +15 % mix Silver+ sur cohortes diaspora |
| Transmettre au médecin (Lisacare / réseau) depuis le chat augmente l’usage télésoin | +25 % sessions Lisacare initiées depuis MCare |
| Quotas visibles type ChatGPT (crédits / mois) créent une perception premium | ≥ 60 % des users comprennent leur quota restant (micro-survey) |

---

## 3. Ce qu’on vend (offre commerciale)

### 3.1 Positionnement one-liner

> **MCare** — le ChatGPT de votre famille au pays : posez la question en français, l’assistant MulemaCare oriente, la mutuelle couvre, un médecin humain valide.

### 3.2 Packaging (SKU)

| SKU | Inclus | Prix indicatif (sponsor) | Quota MCare |
|-----|--------|--------------------------|-------------|
| **MCare Essential** (add-on Bronze) | Chat couverture + réseau + FAQ mutuelle | +5 € / mois ou inclus Soft launch | 5 transmissions médecin / mois |
| **MCare Family** (défaut Silver+) | + triage pré-clinique + cercle famille + carte CSSA dans le fil | Inclus Silver / Gold | 15 / mois (Silver) · illimité soft-capped (Gold) |
| **MCare Platinium Concierge** | + priorité file médecin < 4 h + WhatsApp desk | Inclus Platinium | Illimité + concierge humain |

Règle quota (héritée KijamiCare) : **la discussion libre ne consomme pas** ; **seule la transmission** vers médecin / préauth consomme 1 crédit.

### 3.3 Promesse marketing (autorisée)

- Chat conversationnel pour **suivre et protéger** la famille au pays.
- Réponses sur **garanties, carences, plafonds, cliniques proches** sourcées Mutuelle OS / `config.php`.
- Orientation symptômes → **Lisacare / clinique conventionnée** avec validation humaine.
- Multidevise & Mobile Money déjà sur le site MulemaCare.

### 3.4 Interdits marketing (NE PAS CLAIMER)

- « Diagnostic médical par IA »
- « Remplacement du médecin »
- « 500 médecins en ligne » ou tout fake social proof
- Auto-approbation de prise en charge / remboursement

---

## 4. Personas & RBAC

| Rôle | Persona | Accès MCare |
|------|---------|-------------|
| `sponsor` (adhérent diaspora) | Amina, Paris — paie pour maman Douala + frère Yaoundé | Chat complet sur **son cercle familial** uniquement |
| `beneficiary` | Maman Douala | Carte CSSA / lien signé ; **pas** le chat clinique sponsor (opt-in WhatsApp plus tard) |
| `doctor` / Lisacare | Médecin de garde | File des dossiers transmis (`pending_review`) |
| `ops` / admin mutuelle | Back-office | Quotas, flags, audit — **zéro contenu clinique** |
| Agent MCare (LLM) | — | Tools déterministes seulement ; propose, n’exécute pas le financier |

---

## 5. Expérience produit — interface type ChatGPT

### 5.1 Surface UX (3 actes)

| Acte | Contenu |
|------|---------|
| **Hook** | Thread chat plein écran (desktop) / plein viewport (mobile) ; sélection du **bénéficiaire** du cercle en tête ; brand MCare visible |
| **Preuve** | Messages streaming ; cartes structurées : couverture restante, carence, clinique proche, `ClinCard` hypothèses taguées IA |
| **Action** | CTA dans le fil : « Transmettre au médecin », « Voir carte CSSA », « Appeler Lisacare », « Ouvrir borne / réseau » |

États obligatoires : **loading / empty / error / success / quota_exhausted / unauthorized**.

Viewports cibles : **375 / 768 / 1280**.

### 5.2 Capacités conversationnelles (MVP)

| Intent | Comportement | Tool déterministe |
|--------|--------------|-------------------|
| « Qu’est-ce qui est couvert pour maman ? » | Résumé plan + plafonds restants | Eligibility / Membership |
| « Fièvre depuis 2 jours à Douala » | Collecte symptômes → triage → ClinCard | Benji-like engine + red flags |
| « Où aller sans avancer d’argent ? » | 3 cliniques proches conventionnées | Réseau soins config |
| « Active / renvoie la carte » | Lien carte + QR | MembershipService |
| « Est-ce que ça passe la carence ? » | Dates carence explicites | Membership rules |
| « Paie / cotisation » | Statut cotisation + deep-link paiement | Quote / billing (HITL si geste) |

### 5.3 Machine à états clinique (calque KijamiCare)

```text
collect → analysis → orientation → transmitted → validated|corrected|rejected|urgent
```

- Tags obligatoires sur toute ClinCard : **`IA`** + **`Hypothèses non validées`**.
- Validation finale : tag **`Médecin humain`** + identité praticien.
- Urgence / red flag → modal SAMU + numéros pays (`config.contact.emergency_samu`) — **pas** de conseil « restez chez vous » si red flag.

### 5.4 Différenciation vs KijamiCare (Dr Benji)

| | KijamiCare | **MCare (MulemaCare)** |
|--|------------|------------------------|
| Marque assistant | Dr Benji | **MCare** (ou « Assistant Mulema » — figé à l’Art) |
| Design | Warm Clinical `#2c7744` | Bio-Clinical Emerald `#097268` |
| Acquisition | App Next dédiée | Site PHP diaspora + espace adhérent → chat |
| Télésoin | Intégré | **Pont Lisacare** (déjà dans écosystème site) |
| Senior care | — | **Pont Ongwa** si parent âgé |
| Mutuelle backend | HealthOS Kijami | Mutuelle OS + CSSA Mulema + bridge HealthOS optionnel |

**Réutiliser** : pattern chat SSE, ClinCard, quotas, transmit→file médecin, isolation admin≠clinique.  
**Ne pas copier** : tokens CSS, copy « Benji », fake counts.

---

## 6. Architecture minimale

```text
Sponsor diaspora
    │  Web chat MCare (Next slice ou embed dans espace-adherent)
    ▼
Mutuelle OS FastAPI  ── agents MCare + ActionCenter HITL
    │ tools: eligibility, network, membership, quote
    │ clinical engine: triage + ClinCard (Fernet at-rest)
    ├──────────────► Lisacare (WhatsApp / télétriage)
    ├──────────────► Ongwa (si senior)
    └──────────────► HealthOS partner (préauth PENDING_REVIEW, flag OFF défaut)
site PHP (mulemacare.com)
    · /diaspora/{slug} CTA « Parler à MCare »
    · /espace-adherent deep-link chat
```

### API contrat (MVP)

```text
POST   /api/v1/mcare/conversations
GET    /api/v1/mcare/conversations/{id}/stream     # SSE tokens
POST   /api/v1/mcare/conversations/{id}/message
POST   /api/v1/mcare/conversations/{id}/transmit   # −1 quota
GET    /api/v1/mcare/family                        # cercle + plafonds
GET    /api/v1/doctor/mcare/queue
POST   /api/v1/doctor/mcare/cases/{id}/decide
```

Images Docker : `cybernecs/mulemacare-api`, `cybernecs/mulemacare-mcare-web` (si front séparé).

---

## 7. Risques + dette + sécurité

| Risque | Mitigation |
|--------|------------|
| LLM invente un plafond / une clinique | Tools only ; refus de répondre hors tool |
| Perception « ChatGPT = médecin » | Disclaimer permanent + tags ClinCard + transmit humain |
| Fuite conversations vers admin | RBAC : ops bloqués sur payloads cliniques (tests matrice) |
| Coût LLM diaspora illimité | Quotas + soft cap Gold + local_models_only option air-gap |
| Double produit Kijami vs Mulema | Marque MCare distincte ; pas de partage de tenant data |

PII : Fernet sur messages & triage ; audit append-only ; tenant depuis JWT.

---

## 8. Tradeoffs — Now / Later / Never

| Now | Later | Never |
|-----|-------|-------|
| Chat couverture + réseau + triage + transmit Lisacare/médecin | Voice / WhatsApp inbound sponsor | Diagnostic autonome |
| Quotas par plan Silver+ | Multi-bénéficiaire concurrent threads | Fake « N médecins online » |
| Embed dans espace adhérent + CTA pages `/diaspora/*` | App mobile Expo MCare | Remplacer Lisacare par le chat |
| ClinCard + file médecin | Bridge HealthOS préauth depuis chat | Admin lit le fil clinique |
| **Paiement Stripe abonnement avant accès MCare Family** | Essai freemium limité | Chat MCare sans adhésion payée |

---

## 9. Plan livraison (6 jalons) + rollback

1. **MC0 — Contrat Art + disclaimer légal** (2 j) — tokens MCare, copy, anti-patterns. Rollback : pas de ship UI.
2. **MC1 — API conversations + SSE + Fernet** (5 j) — sans LLM prod (réponses scriptées). Rollback : flag `mcare_enabled=false`.
3. **MC2 — Tools mutuelle** (eligibility, network, carte) (4 j). Rollback : chat FAQ statique.
4. **MC3 — Triage + ClinCard + quotas** (5 j). Rollback : désactiver transmit.
5. **MC4 — File médecin / pont Lisacare + HITL** (5 j). Rollback : WhatsApp desk manuel actuel.
6. **MC5 — Packing commercial** (3 j) — SKU dans `config.php` plans, CTA `/diaspora/{slug}`, pricing site, `llms.txt` update. Rollback : retirer CTAs.

---

## 10. Vérification

| Gate | Critère |
|------|---------|
| Éthique | 0 ClinCard sans tags IA ; 0 path diagnostic final sans médecin |
| Quota | Transmit décrémente ; chat libre non |
| Isolation | Test RBAC : admin ≠ messages cliniques |
| UX | loading/empty/error/success/quota ; 375/768/1280 |
| Produit | CTA diaspora → chat ; deep-link depuis espace adhérent |
| QA | pytest moteur états + vitest Benji-like chat ; smoke SSE |

---

## 11. DoD « on vend MCare »

- [ ] Page / section pricing MCare sur le site (Silver+ « inclus », Bronze add-on).
- [ ] Chat live pour sponsor authentifié sur son cercle familial.
- [ ] Au moins 4 intents tools-backed (couverture, symptômes, réseau, carte).
- [ ] Transmit → file humaine (Lisacare ou médecin réseau).
- [ ] Quotas visibles type ChatGPT.
- [ ] Zéro claim marketing interdit en prod.
- [ ] Feature flag + rollback documenté.

---

## 12. Messages Growth (exemples autorisés)

- « Depuis Paris, parlez à MCare comme à ChatGPT : “Maman a de la fièvre à Douala — que faire ?” »
- « L’IA oriente. Votre mutuelle MulemaCare couvre. Un médecin valide. »
- « Inclus dès la formule Silver — pour toute la famille au pays. »

---

## Annexe — Mapping site existant → MCare

| Existant `site/` | Rôle pour MCare |
|------------------|-----------------|
| `/diaspora/{slug}`, `/pays/{slug}` | Landing acquisition + CTA « Essayer MCare » |
| `/espace-adherent` | Host du chat post-login |
| `/api/verify-card`, membership | Tools carte / éligibilité |
| `/reseau-soins` | Tool cliniques |
| Plans Bronze→Platinium + devises | Quotas & packaging SKU |
| Lisacare / Ongwa dans `config.ecosystem` | Hand-off post-orientation |
| `HealthOSClient` | Later : préauth depuis transmit (HITL) |
