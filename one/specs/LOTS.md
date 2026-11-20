# specs/LOTS.md — Consignes par lot

Chaque lot : un agent, une branche, un périmètre de dossiers. Ordre : L0 d'abord et seul, relu par un humain ; ensuite L1, L2, L3, L6, L7 et L9 en parallèle ; puis L4 et L5 ; enfin L8.

Chaque consigne commence par le même en-tête à donner à l'agent :

> Tu es l'agent du lot <ID>. Lis `AGENTS.md`, `specs/PRD.md`, puis cette consigne. Travaille uniquement dans ton périmètre. Écris le test de chaque critère avant le code. `make check` doit passer. Tu ne modifies aucun contrat. En cas de doute, pose la question, ne devine pas.

---

## L0 — Contrats

**Périmètre :** `specs/schema.sql`, `specs/openapi.yaml`, `specs/events.md`, `specs/design/`, migrations initiales.
**Exigences :** aucune directe ; rend toutes les autres possibles.
**Produire :**
1. `schema.sql` : organizations, persons, members, dependents, plans, plan_versions, coverages, providers, claims, claim_items, authorizations, contributions, ledger_entries, ledger_lines, audit_events, ai_actions. Clés étrangères, index, `organization_id` partout, montants en entiers. Aucune colonne de diagnostic.
2. `openapi.yaml` : tous les endpoints des lots L1 à L8, avec entrées, sorties, erreurs (codes stables). Un serveur de mocks (Prism) pour les lots UI.
3. `events.md` : les six événements du PRD section 6, avec schéma JSON de chaque payload.
4. Copie des jetons de design dans `specs/design/`.
**Vérification :** `schema.sql` s'applique sur une base vide ; `openapi.yaml` passe un linter (Spectral) ; un test scanne le schéma et échoue si un nom de colonne contient `diagnos`, `motif_med`, `ordonnance`.
**Ne pas faire :** aucun code applicatif. Un humain relit avant que les autres lots démarrent.

## L1 — Noyau : organisations, rôles, audit

**Périmètre :** `apps/api/core`.
**Exigences :** R6 (séparation, côté permissions), R10 (isolation).
**Produire :** organisations et utilisateurs, rôles (gestionnaire, médecin-conseil, clinique, employeur, admin), permissions par rôle et par attribut, journal d'audit immuable, dépendance FastAPI qui injecte l'organisation dans chaque requête.
**Vérification :** test d'isolation généré pour chaque table métier (un utilisateur de A ne lit rien de B) ; test qu'un gestionnaire ne peut pas lire le motif médical ; chaque lecture du motif crée une entrée d'audit.
**Ne pas faire :** pas de fournisseur d'identité choisi (question ouverte) ; utilise une interface et une implémentation de test.

## L2 — Produits et moteur de règles

**Périmètre :** `apps/api/rules`.
**Exigences :** R3, R4, R5.
**Produire :** produits et versions avec date d'effet, règles stockées en données (conditions, seuil, taux), évaluation déterministe, enregistrement de `rule_id` et `rule_version` dans chaque décision, règles R-01 (droits), R-04 (réseau), R-07 (carence), R-09 (plafond), R-12 (accord automatique), R-20 (revue).
**Vérification :** test de la règle modifiée le 01/01 et du soin du 20/12 traité le 05/01 ; test de propriété : même entrée + même version = même décision ; 185 000 FCFA part en revue ; 48 000 FCFA avec score 0,06 est accordé.
**Ne pas faire :** aucun appel à un LLM dans ce module.

## L3 — Grand livre

**Périmètre :** `apps/api/ledger`.
**Exigences :** R7.
**Produire :** écritures en partie double, triggers PostgreSQL interdisant `UPDATE` et `DELETE`, contre-passation, plan de comptes (4011, 5110, 5121, 5122, 6011, 7061 pour commencer), balance, consommateur de l'événement `claim.decided` et `contribution.received`.
**Vérification :** tentative d'`UPDATE` et de `DELETE` refusée ; test de propriété (hypothesis) : sur des milliers d'écritures aléatoires, débits = crédits ; contre-passation d'une écriture annule son effet sur la balance.
**Ne pas faire :** pas de lettrage ni de clôture de période dans cette version.

## L4 — Adhésions et cotisations

**Périmètre :** `apps/api/members`, `apps/api/payments`.
**Exigences :** R2, R8.
**Produire :** adhérents et ayants droit, statuts (actif, carence, suspendu), cartes à QR dynamique, cotisations, webhooks Wave, Orange Money et MTN MoMo derrière une interface (implémentations simulées d'abord), lien de paiement diaspora, relances.
**Vérification :** paiement confirmé par webhook ouvre les droits en moins de 60 s ; le même webhook rejoué ne crée pas de doublon ; suspension automatique à J+45 d'impayé.
**Ne pas faire :** pas d'intégration réelle tant que la section 10 n'a pas tranché l'accès API ; pas de stockage de numéro de carte bancaire.

## L5 — Tiers payant et revue médecin-conseil (API)

**Périmètre :** `apps/api/claims`.
**Exigences :** R1, R4, R5, R6.
**Produire :** identification en trois facteurs (QR, photo, code SMS), demande de prise en charge, appel au moteur de règles, routage vers la revue, décisions humaines (accorder, refuser, demander des pièces), lecture du motif à la demande depuis HealthOS avec audit.
**Vérification :** trois codes faux bloquent la carte 15 minutes ; un dossier sous seuil est accordé automatiquement ; un dossier au-dessus part en revue sans création de paiement ; aucune donnée médicale dans les réponses du rôle gestionnaire.
**Ne pas faire :** ne réimplémente pas les règles ; appelle L2.

## L6 — Console gestionnaire et médecin-conseil

**Périmètre :** `apps/web/console`.
**Exigences :** R5, R6 (côté interface).
**Produire :** accueil, prises en charge avec filtres, tiroir du dossier, adhérents, grand livre en lecture, produits et versions. Point de départ : le prototype MulemaCare One. Utilise les mocks OpenAPI au début.
**Vérification :** Playwright : parcours « le médecin-conseil accorde un dossier en revue » et « le gestionnaire ne voit pas le motif médical » ; capture jointe à la PR.
**Ne pas faire :** aucune couleur en dur ; pas de nouveau composant si un équivalent shadcn/ui existe.

## L7 — Comptoir PWA

**Périmètre :** `apps/web/counter`.
**Exigences :** R1 (interface), R12, R13.
**Produire :** les cinq écrans du comptoir (carte, identité, code, actes, décision), mode plein soleil, mode hors ligne (accord provisoire signé sur l'appareil, valable 2 h, file de synchronisation), installation PWA.
**Vérification :** `make a11y` sans violation AA ; Playwright avec réseau coupé : un dossier sous seuil est accordé en provisoire puis synchronisé ; zones tactiles mesurées à 48 px minimum ; capture jointe.
**Ne pas faire :** pas de texte secondaire pâle ; pas de fonctionnalité hors des cinq écrans.

## L8 — JOE

**Périmètre :** `apps/api/joe`.
**Exigences :** R11.
**Produire :** couche d'outils en lecture (adhérent, droits, historique, barème), outils de préparation (brouillon de décision, message), garde-fous (aucun outil n'écrit un état de prise en charge), journalisation de chaque action avec ses sources dans `ai_actions`, interface LLM interne à modèle configurable, recherche ⌘K.
**Vérification :** test : une recommandation de JOE sans validation humaine ne change aucun état ; test : aucune requête sortante avec donnée identifiante ; chaque réponse cite les enregistrements consultés.
**Ne pas faire :** aucun outil `approve`, `reject` ou `pay` accessible à JOE.

## L9 — Intégration HealthOS et résidence des données

**Périmètre :** `apps/api/integrations`, `infra/`.
**Exigences :** R9.
**Produire :** client FHIR minimal vers HealthOS (identité, consultation, motif à la demande), liste blanche réseau (`infra/egress-allowlist.txt`), test `make egress`, configuration de déploiement par pays.
**Vérification :** le test réseau échoue si une requête sort hors liste blanche ; le client n'envoie que l'identifiant pseudonyme, jamais le nom.
**Ne pas faire :** pas de copie de données cliniques dans la base assurance.

---

## Agent vérificateur (à lancer après chaque lot)

> Tu n'as pas écrit ce code. Lis le PRD (sections 4 et 9), la PR et les tests. Pour chaque critère d'acceptation du lot, dis s'il est prouvé par un test qui échouerait si le code était faux. Cherche : un contrat modifié, un diagnostic dans la base assurance, un `UPDATE` ou `DELETE` sur le grand livre, une couleur en dur, une dépendance non justifiée, un appel réseau hors liste blanche, un test désactivé. Réponds par une liste : critère, prouvé ou non, pourquoi. Ne modifie pas le code.
