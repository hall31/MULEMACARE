# PRD — MulemaCare One

Oct 1, 2026 · @Dajan · v0.2 (réécrit au format `prd-gen`) · statut : à valider par Dajan

Le noyau de gestion de la mutuelle MulemaCare (Côte d'Ivoire, Sénégal) : adhésions, cotisations, tiers payant en temps réel, prestations, grand livre. Les valeurs marquées *(proto)* viennent du prototype et ne sont pas des décisions métier : elles sont listées en section 10.

## 1. Problème et contexte

- **Problème :** la mutuelle tourne sur trois systèmes qui se recoupent (Laravel `MUTUELLE`, site PHP `MULEMACARE/site`, HealthOS). Aucun ne prouve un tiers payant en temps réel : le site PHP n'a pas d'authentification, ses KPI sont fabriqués et il retombe en silence sur des fichiers JSON ; Laravel est la source de vérité assurantielle mais n'a pas de règles versionnées ni de grand livre en ajout seul.
- **Preuve :** audit du code (01/10) ; volume faible, environ 420 adhérents et 216 ayants droit selon `INGEST_LEGACY.md` (chiffre de documentation).
- **Pourquoi maintenant :** cliniques et assureur pilote arrivent ; secret médical, résidence des données et traçabilité ne se rajoutent pas après coup.
- **Produit parent :** s'appuie sur HealthOS pour le dossier clinique (identifiant pseudonyme seulement) ; remplace à terme la gestion assurantielle de Laravel (ADR-001).

## 2. Objectifs et non-objectifs

**Objectifs (v1)**
1. Une clinique obtient une décision de prise en charge au comptoir en moins de 10 s pour un dossier automatique.
2. Chaque décision est rejouable : règle et version enregistrées, grand livre équilibré, écart de rapprochement avec l'existant à 0.
3. Aucune donnée médicale dans la base assurance.

**Non-objectifs**
- Pas d'intégration réelle Wave / Orange Money / MTN tant que la section 10 n'a pas tranché l'accès API.
- Pas de lettrage ni de clôture de période.
- ~~Pas de module assureur ni courtier (seulement le modèle multi-organisations).~~ **Amendé le 01/10/2026** (décision de Dajan : vendre One clé en main aux assureurs ; CR-P3-01, appliqué pour enchaîner les phases — à valider). Entrent dans le périmètre : la marque blanche par organisation, l'espace assureur en lecture seule (portefeuille agrégé k-anonyme, export CSV agrégé), l'espace employeur (consommation agrégée du groupe, échéances) et l'accueil d'une organisation par un administrateur de plateforme (copie de gabarit, jamais de ligne partagée). Restent des non-objectifs : le module courtier ; toute lecture d'une organisation par une autre, y compris en gestion déléguée ; toute décision, écriture ou donnée de personne côté assureur ou employeur.
- Pas d'app mobile native (PWA comptoir uniquement).
- Aucune décision de prise en charge prise par un LLM.
- Pas de migration MySQL → PostgreSQL « en une fois » ; pas de repli silencieux sur des fichiers.

## 3. Utilisateurs et parcours clés

| Persona | Parcours | Écrans | Résultat attendu |
| --- | --- | --- | --- |
| Clinique | Scanne la carte, identité, code SMS, actes | Comptoir en 5 écrans | Décision en moins de 10 s ; hors ligne : accord provisoire 2 h |
| Médecin-conseil | Traite la file de revue, lit le motif à la demande | Prises en charge, tiroir | Décision tracée, lecture auditée |
| Gestionnaire | Suit dossiers, adhérents, grand livre, produits | Console | Aucune donnée médicale visible |
| Payeur diaspora | Paie par lien | Lien de paiement | Droits ouverts en moins de 60 s |

- **Prototype de référence :** `specs/design/prototype.html` (MulemaCare One)
- **Design system :** `specs/design/mulemacare-tokens.css` (jetons clair, sombre, plein soleil)
- **Contrat de design :** `docs/POLISH_CONTRACT.md` (gagne sur le prototype pour le visuel) ; métriques en §11 : contraste ≥ 4,5:1 (7:1 plein soleil), 0 violation axe, cibles ≥ 48 px, LCP < 2,5 s en 3G rapide, CLS < 0,1.

## 4. Exigences et critères d'acceptation

| ID | Exigence | Critère d'acceptation | Priorité |
| --- | --- | --- | --- |
| R1 | Tiers payant en temps réel, identification à trois facteurs (QR, photo, code SMS) | Étant donné trois codes faux, quand le 3e est saisi, alors la carte est bloquée 15 min ; un dossier sous seuil est accordé automatiquement | P0 |
| R2 | Adhésions : adhérents, ayants droit, statuts (actif, carence, suspendu), carte QR dynamique | Un paiement confirmé ouvre les droits en moins de 60 s | P0 |
| R3 | Produits versionnés à date d'effet | Un soin du 20/12 traité le 05/01 est évalué avec la version du 20/12 | P0 |
| R4 | Règles de droits et de réseau en données (R-01, R-04, R-07, R-09) | Hors réseau ou droits suspendus : refus avec code de règle stable | P0 |
| R5 | Accord automatique (R-12) et revue (R-20) | 48 000 FCFA, score 0,06 : accordé ; 185 000 FCFA : revue, aucun paiement créé *(proto)* | P0 |
| R6 | Secret médical | Aucune colonne de diagnostic ; réponses du gestionnaire sans donnée médicale ; chaque lecture du motif crée un `audit_events` | P0 |
| R7 | Grand livre en ajout seul, partie double | `UPDATE`/`DELETE` refusés ; débits = crédits sur 1 000 écritures aléatoires ; contre-passation annule l'effet | P0 |
| R8 | Cotisations idempotentes | Même webhook rejoué : aucun doublon ; suspension automatique à J+45 d'impayé *(proto)* | P0 |
| R9 | Résidence des données | Test réseau échoue si une requête sort hors liste blanche ; seul l'identifiant pseudonyme part vers HealthOS | P0 |
| R10 | Isolation par organisation | Un utilisateur de A ne lit rien de B, sur chaque table métier | P0 |
| R11 | JOE recommande, n'agit pas | Sans validation humaine aucun état ne change ; aucun outil `approve`/`reject`/`pay` ; chaque réponse cite ses sources | P1 |
| R12 | Comptoir accessible | Zones tactiles ≥ 48 px, texte ≥ 16 px, contraste AA, mode plein soleil | P0 |
| R13 | Hors ligne | Accord provisoire signé sur l'appareil sous le seuil, valable 2 h, synchronisé puis décidé par le moteur de règles | P0 |
| R14 | Import de l'existant en lecture seule | Étant donné la base Laravel, quand l'import tourne, alors le nombre d'adhérents et la somme des cotisations de One égalent ceux de la source (écart 0), chaque ligne garde son identifiant d'origine, rejouer l'import ne crée aucun doublon | P0 |
| R15 | Mode ombre | Sur 4 semaines, ≥ 99 % des décisions de One concordent avec `reimbursement/simulate` de Laravel ; chaque écart est listé avec sa règle | P0 |
| R16 | Pont d'éligibilité | Laravel interroge One via le contrat `laravel-bridge` sans changer de format ; One reste lecture seule sur les écritures de Laravel tant que la bascule n'est pas décidée | P1 |
| R17 | Bascule par cohorte réversible | Une cohorte basculée peut revenir sur Laravel sans perte : rapprochement quotidien à écart 0, accès Laravel en lecture conservé 6 mois | P1 |

## 5. Décisions d'architecture

Sept décisions coûteuses à défaire, détail et alternatives écartées en Annexe A : ADR-001 One devient la source de vérité par cohorte (strangler), Laravel maître jusqu'à la bascule ; ADR-002 deux bases `insurance` et `clinical` liées par identifiant pseudonyme ; ADR-003 monolithe modulaire FastAPI + Next.js ; ADR-004 décisions par moteur de règles versionné, JOE en lecture seule ; ADR-005 montants en entiers mineurs, devise explicite (XOF ≠ XAF) ; ADR-006 table `external_ids` pour les clés d'origine ; ADR-007 rôle applicatif non propriétaire, RLS forcée.

## 6. Contrats et interfaces

- **Modèle de données :** `specs/schema.sql` (16 tables de base plus identification, cartes, paiements, `outbox_events`, `external_ids` à ajouter par change request).
- **API :** `specs/openapi.yaml` (toutes les opérations des lots L1 à L8, montées dans l'application assemblée).
- **Événements :** `specs/events.md` : `claim.requested`, `claim.decided`, `contribution.received`, `member.status_changed`, `ledger.entry_posted`, `authorization.synced`.
- **Intégrations existantes :** contrat `laravel-bridge` de Laravel (réutilisé tel quel pour R16) et passerelle partenaire de HealthOS ; détail en Annexe B.
- Règle : un agent qui doit modifier un contrat s'arrête et l'écrit dans `specs/CHANGE-REQUESTS.md`.

## 7. Règles pour les agents

Recopiées dans `AGENTS.md` (stack, `make check`, jetons de design, interdits, en cas de doute écrire la question en §10). Aucune donnée réelle d'adhérent n'entre dans le dépôt : les jeux d'import de test sont fictifs.

## 8. Découpage en lots

| Lot | Périmètre | Exigences | Dépend de | État |
| --- | --- | --- | --- | --- |
| L0 | Contrats, outillage | — | — | livré |
| L1 | Noyau, rôles, audit | R6, R10 | L0 | livré |
| L2 | Produits et règles | R3, R4, R5 | L0 | livré |
| L3 | Grand livre | R7 | L0 | livré |
| L4 | Adhésions, cotisations | R2, R8 | L1, L3 | livré (canaux simulés) |
| L5 | Tiers payant API | R1, R13 | L1, L2, L3, L9 | livré |
| L6 | Console | R5, R6 | L0 | livré (mocks) |
| L7 | Comptoir PWA | R12, R13 | L0 | livré (mocks) |
| L8 | JOE | R11 | L5 | livré |
| L9 | HealthOS, résidence des données | R9 | L0 | livré (simulé) |
| L10 | Entrée de production, identité, vraie base | R2, R10 | L1 | à faire |
| L11 | Import Laravel en lecture seule | R14 | L10 | à faire |
| L12 | Mode ombre et rapport d'écarts | R15 | L11 | à faire |
| L13 | Pont `laravel-bridge` | R16 | L11 | à faire |
| L14 | Bascule par cohorte et rapprochement | R17 | L12, L13 | à faire |

## 9. Définition du « fini »

- [ ] Chaque critère d'acceptation du lot a un test automatisé qui passe
- [ ] `make check` passe (lint, typage, contrats, tests Python et web, builds)
- [ ] Aucun contrat de la section 6 modifié sans validation
- [ ] Capture Playwright du parcours pour les lots UI
- [ ] PRD mis à jour si le comportement a changé
- [ ] Un agent vérificateur qui n'a pas écrit le code a répondu « prouvé » pour chaque critère
- [ ] Pour L11 à L14 : rapprochement à écart 0 documenté, plan de retour arrière écrit

## 10. Questions ouvertes

- [ ] Accès API Wave / Orange Money / MTN MoMo — défaut : canaux simulés — Dajan
- [ ] Fournisseur d'identité de One — défaut : interface + implémentation de test — Dajan
- [ ] Seuils *(proto)* : 50 000 FCFA, score fraude 0,20 (et 0,6), carence 60 j, J+45 — défaut : valeurs du prototype, en données — Dajan
- [ ] Fournisseur du score de fraude (sans lui tout dossier part en revue) — Dajan
- [ ] Contrat réel HealthOS (son `Patient` FHIR renvoie nom et téléphone ; pas d'`Encounter` ni de recherche par pseudonyme) — Dajan
- [ ] Qui paie un soin fait sur la foi d'un accord provisoire ensuite refusé par le moteur — Dajan
- [ ] Hébergement HDS pour adhérents résidant en France (bloquant la production, pas le développement) — Dajan
- [ ] Agrément : statut de MulemaCare (mutuelle ou assureur), régulateur (CIMA, AIRMS), validité du préfixe « CSSA » — Dajan
- [ ] Laquelle des deux générations de modèle Laravel est la vraie (`subscription_aderents` ancien, `mutual_subscriptions` 2026), et d'où vient la donnée de production réelle (`mulemacare.com`, MySQL `mulemacare_prod`) — Dajan
- [ ] Comptage réel de la base de production : les 420 et 216 sont des chiffres de documentation — Dajan
- [ ] Phase 3 (marque blanche, assureur, employeur, plateforme) : définition du ratio S/P, statut et activation d'une organisation accueillie, qui détient le rôle `admin_plateforme` — défauts dans `specs/QUESTIONS.md` (Q-P3-01 à Q-P3-12) — Dajan
- [ ] Les autres questions de `specs/QUESTIONS.md`, chacune avec son défaut — Dajan

## Annexe A — Décisions d'architecture (détail)

| ADR | Décision | Pourquoi | Alternative écartée |
| --- | --- | --- | --- |
| 001 | One devient la source de vérité assurantielle par cohorte (strangler) ; Laravel reste maître jusqu'à la bascule | Données réglementées, volume faible, retour arrière nécessaire | Migration en une fois ; Laravel maître définitif |
| 002 | Deux bases : `insurance` (One) et `clinical` (HealthOS), liées par identifiant pseudonyme | Secret médical, résidence des données | Une base commune |
| 003 | Modular monolith FastAPI, route → service → dépôt ; Next.js pour console et comptoir | MVP d'abord, pas de split prématuré | Microservices |
| 004 | Décisions par moteur de règles versionné, JOE en lecture seule | Rejouable, auditable, aucun LLM décisionnel | Décision par LLM |
| 005 | Montants en entiers mineurs, devise explicite (XOF) ; l'existant mêle XAF et XOF et decimal(12,2) | Pas de flottants ; XAF (Cameroun) ≠ XOF (CI, Sénégal) | Decimal partout |
| 006 | Table `external_ids(source, clé)` ; clés stables : `subscription_number`, `membership_id`, `cssa_number`, `claim_reference`, `legacy_user_id` ; l'email sert au dédoublonnage, jamais de clé | Import rejouable, rapprochement | Clé = email |
| 007 | Rôle applicatif `mulema_app` non propriétaire, RLS forcée, API jamais sous le propriétaire | Sinon RLS et grand livre contournables | Rôle propriétaire |

## Annexe B — Intégrations existantes (détail)

- Laravel `MUTUELLE/mulema-app/packages/contracts/openapi/laravel-bridge.openapi.yaml` (`eligibility/check`, `reimbursement/simulate`, `member-summary`, `pricing`, `patient-read-snapshot`) : contrat réutilisé tel quel pour R16.
  - HealthOS `healthos_partner_gateway.py` (`eligibility`, `claims/analyze`, `claims/preauthorize`, `trust-score`), requêtes signées HMAC avec anti-rejeu : contrat réel de HealthOS à fixer (section 10).
