# Demandes de changement des contrats

`specs/schema.sql`, `specs/openapi.yaml` et `specs/events.md` sont des contrats. Un lot qui a besoin de les modifier s'arrête, ajoute une entrée ci-dessous et attend la validation d'un humain (AGENTS.md, « Contrats »).

## Modèle

```
### CR-000 — titre court
- Lot demandeur : Lx
- Contrat : schema.sql | openapi.yaml | events.md
- Changement voulu : (colonne, endpoint, champ… avec le texte exact proposé)
- Raison : (exigence R… ou critère d'acceptation bloqué)
- Impact : (autres lots, migration Alembic, données existantes)
- Statut : proposée | acceptée par <nom> le <date> | refusée
```

## Demandes

Aucune (contrats créés par le lot L0, 2026-09-30).

### CR-L3-01 — réponse 422 sur les opérations du grand livre
- Lot demandeur : L3
- Contrat : openapi.yaml
- Changement voulu : ajouter `'422': {$ref: '#/components/responses/ValidationError'}` à `listLedgerEntries` (curseur invalide, `account_code`/`limit` hors bornes), `reverseLedgerEntry` (`reason` hors 3-200 caractères, `Idempotency-Key` absente ou hors 8-200) et `getLedgerBalance` (`at` qui n'est pas une date).
- Raison : ces entrées invalides produisent déjà un 422 (VAL-01) ; le contrat ne le déclare pas, donc les mocks Prism (L6) et les clients ne le prévoient pas. Pas bloquant pour R7.
- Impact : openapi.yaml seulement ; aucun schéma, aucune migration. Le format problem+json des erreurs de validation FastAPI reste à brancher globalement par L1.
- Statut : proposée

### CR-L1-01 — code d'erreur stable pour « utilisateur déjà rattaché »
- Lot demandeur : L1
- Contrat : openapi.yaml
- Changement voulu : ajouter `USR-01` à `components.schemas.ErrorCode` (« USR-01 sujet d'identité déjà rattaché à un utilisateur de l'organisation ») et à la description de `components.responses.Conflict`.
- Raison : `createUser` déclare un 409, mais aucun code de la liste `Conflict` ne correspond. En attendant, L1 renvoie 409 avec le code `VAL-01` (conforme à l'énumération actuelle, mais peu précis).
- Impact : openapi.yaml seulement ; `DuplicateUserError` (apps/api/core/errors.py) passera à `USR-01`.
- Statut : proposée

### CR-L1-02 — retrait d'un rôle impossible sous le rôle applicatif
- Lot demandeur : L1
- Contrat : schema.sql
- Changement voulu, au choix (préférence : option A, elle garde l'historique) :
  - A. `user_roles` : ajouter `revoked_at timestamptz` et `revoked_by uuid` (FK composite vers `users`), remplacer `UNIQUE NULLS NOT DISTINCT (organization_id, user_id, role, provider_id, employer_id)` par un index unique partiel `WHERE revoked_at IS NULL`, et ne lire que les rôles non révoqués ;
  - B. `GRANT DELETE ON user_roles TO mulema_app`.
- Raison : `replaceUserRoles` « remplace l'ensemble des rôles », mais `mulema_app` n'a ni `DELETE` sur `user_roles`, ni colonne permettant de désactiver une attribution (les CHECK interdisent de la neutraliser par `UPDATE`). Aujourd'hui, L1 accepte les ajouts et refuse tout retrait avec 409 `VAL-01`, sans rien modifier (test `test_retrait_de_role_refuse_tant_que_le_contrat_ne_le_permet_pas`). R10/R6 ne sont pas bloqués ; la gestion des droits l'est en partie (un médecin-conseil qui quitte la mutuelle ne peut être retiré qu'en désactivant son compte).
- Impact : A = migration 0002 (ajout de colonnes, aucune donnée réécrite) + fixture d'isolation inchangée ; B = une ligne de GRANT. L1 adaptera `UserService.replace_roles`.
- Statut : proposée

### CR-L1-03 — réponse 422 sur les listes paginées du noyau
- Lot demandeur : L1
- Contrat : openapi.yaml
- Changement voulu : ajouter `'422': {$ref: '#/components/responses/ValidationError'}` à `listUsers` et `listAuditEvents` (curseur altéré, `limit` hors 1-200, `from`/`to`/`target_id` mal formés).
- Raison : ces entrées produisent déjà un 422 `VAL-01` (problem+json branché globalement par L1 dans `api.core.app`, ce qui couvre aussi le point de CR-L3-01). Même logique que CR-L3-01.
- Impact : openapi.yaml seulement.
- Statut : proposée

### CR-L4-01 — distinguer lien expiré/utilisé et lien inconnu
- Lot demandeur : L4
- Contrat : schema.sql
- Changement voulu : `resolve_payment_link(p_token_hash text)` renvoie aussi `state text` (`'valide' | 'expire' | 'utilise'`) en retirant `used_at IS NULL AND expires_at > now()` du filtre, pour que l'API rende 410 PAY-03 au lieu de 404 (le contrat OpenAPI déclare 410 pour `getPublicPaymentLink` et `startCheckout`).
- Raison : critère « lien expiré ou déjà utilisé : PAY-03 » du contrat inatteignable ; aujourd'hui 404 (Q-L4-04).
- Impact : migration 0002 (remplacement de fonction, aucune donnée) ; `payments.repository.resolve_link` filtre l'état ; aucun autre lot.
- Statut : proposée

### CR-L8-01 — questions d'exemple dans la recherche ⌘K
- Lot demandeur : L8
- Contrat : openapi.yaml
- Changement voulu, au choix (préférence : A) :
  - A. `SearchHit.type` : ajouter `question` à l'énumération (`[member, claim, provider, question]`), `id` devenant facultatif pour ce type (ou un UUID stable par question) ; `/v1/search` renvoie les questions d'exemple dont le texte contient `q` ;
  - B. nouvelle opération `GET /v1/joe/example-questions` (`listJoeExamples`, `x-lot: L8`, `x-roles: [gestionnaire, medecin_conseil, admin]`) renvoyant `{items: [string]}`.
- Raison : la consigne L8 demande des « questions d'exemple » dans la palette ⌘K ; `SearchHit.type` n'admet que member/claim/provider. Les questions existent dans `api.joe.search.EXAMPLE_QUESTIONS` mais ne sont pas exposées.
- Impact : openapi.yaml seulement ; L6 (console) pour l'affichage ; aucun schéma, aucune migration.
- Statut : proposée

### CR-L8-02 — réponse 404 de `askJoe` et 422 des brouillons
- Lot demandeur : L8
- Contrat : openapi.yaml
- Changement voulu : documenter que `askJoe` répond 200 `kind: refus` (et non 404) quand le dossier ou l'adhérent est introuvable ou hors périmètre ; ajouter `'422': {$ref: '#/components/responses/ValidationError'}` à `draftClaimDecision`, `draftMessage` et `listAiActions` (corps invalide, curseur altéré, `limit` hors bornes).
- Raison : ces entrées produisent déjà un 422 `VAL-01` (problem+json du noyau) que le contrat ne déclare pas (même logique que CR-L1-03, CR-L3-01).
- Impact : openapi.yaml seulement.
- Statut : proposée

### CR-L5-01 — codes de règle dans le résultat de synchronisation hors ligne
- Lot demandeur : L5
- Contrat : openapi.yaml, events.md (descriptions seulement)
- Changement voulu : dans la description de `syncOfflineAuthorizations` et de `authorization.synced`, ajouter qu'un accord valide (signature, validité, seuil) est ensuite décidé par le moteur L2 à la date du soin : `rejetee` avec `R-01`, `R-04`, `R-07` ou `R-09` si le moteur refuse, `rejetee` avec `R-20` si le dossier part en revue du médecin-conseil (accord provisoire non confirmé), et que `rule` porte alors cette règle (HL-01 pour les rejets OFF-0x et pour un accord confirmé).
- Raison : l'ancien comportement confirmait tout accord valide par HL-01 sans lire la décision du moteur (adhérent suspendu, en carence ou clinique hors réseau accordés : défaut bloquant). Les codes R-0x sont déjà dans `ErrorCode` et respectent le motif `reason_code` d'`authorization.synced` : aucun schéma ne change, seules les descriptions qui ne citent que OFF-0x sont incomplètes.
- Impact : texte d'openapi.yaml et d'events.md ; aucun schéma, aucune migration. Le comptoir (L7) doit afficher le motif R-0x/R-20 reçu à la synchronisation. Détail et questions ouvertes : `apps/api/claims/QUESTIONS.md` Q-L5-08.
- Statut : proposée

### CR-P1-01 — rôle `adherent` et espace adhérent / diaspora (« mon compte »)
- Lot demandeur : Phase 1, voie A (API espace adhérent et diaspora)
- Contrat : schema.sql, openapi.yaml (events.md inchangé)
- Statut : **appliqué sur instruction de Dajan pour enchaîner la Phase 1 — à valider**. Extension strictement additive : aucune suppression, aucun changement de sens, migration 0001 inchangée (empreinte figée toujours vraie).
- Changement appliqué :
  - schema.sql + migration Alembic **0002** (`apps/api/migrations/versions/0002_espace_adherent.sql`, rejouable) : `user_roles.member_id uuid` nullable ; rôle `adherent` ajouté à la liste de `user_roles.role` (contrainte élargie) ; `CHECK ((role = 'adherent') = (member_id IS NOT NULL))` (`user_roles_adherent_scope_check`) ; clé étrangère composite `(organization_id, member_id) → members` (`user_roles_member_fk`) et son index. Aucune ligne existante réécrite ; droits de `mulema_app` et RLS inchangés. Le retour arrière (`downgrade`) est refusé sans validation humaine (il effacerait les comptes adhérents).
  - openapi.yaml : `Role` += `adherent` ; `RoleGrant.member_id` (facultatif, obligatoire pour `adherent`, interdit sinon) ; `getCurrentUser` et `getCurrentOrganization` ouverts à `adherent` ; tag `espace-adherent` ; six opérations `x-lot: P1`, `x-roles: [adherent]` : `getMyCard` (`GET /v1/me/card`), `listMyBeneficiaries` (`GET /v1/me/beneficiaries`), `listMyClaims` (`GET /v1/me/claims`), `getMyClaimTracking` (`GET /v1/me/claims/{claim_id}/tracking`), `listMyContributions` (`GET /v1/me/contributions`), `createMyPaymentLink` (`POST /v1/me/contributions/{contribution_id}/payment-links`) ; schémas `MyCard`, `MyBeneficiary(List)`, `MyClaim(List)`, `TrackingStep`, `ClaimTracking`, `MyContribution(s)`, `BeneficiaryRelationship`.
  - `.spectral.yaml` : `x-lot` admet `P1` en plus de `L1`…`L8` (niveau `--fail-severity=hint` inchangé).
- Raison : le contrat n'avait ni rôle adhérent ni « mon compte » ; l'espace adhérent du POLISH_CONTRACT (ma carte, plafond restant, frise du remboursement, cotisation du mois, inviter un proche à payer) et l'écran 03 de `specs/design/direction/index.html` n'avaient aucune opération à consommer.
- Isolation : le contrat consulté vient du jeton (attribution `adherent` en base, Q-L1-01), jamais de la requête ; chaque requête filtre organisation ET contrat ; un dossier, une personne ou une cotisation hors du contrat donne 404 NOT-01. L'appartenance d'une cotisation est vérifiée AVANT le rejeu de la clé d'idempotence.
- Rôle `payeur` : **non ajouté**. Le payeur diaspora reste sans compte et passe par le lien public (`getPublicPaymentLink`, `startCheckout`, L4) ; un rôle authentifié n'apporterait rien au parcours.
- Impact : `apps/api/core` (matrice, `RoleGrant.member_id`, validation de `createUser`/`replaceUserRoles`), nouveau module `apps/api/member_space`, `PaymentService.create_member_link` (même flux que `createPaymentLink`) ; types générés de la console régénérés (`pnpm gen:api`) ; le comptoir (`apps/web/counter/src/api/schema.d.ts`) n'est PAS régénéré (autre agent) : à faire par son propriétaire, il n'a pas de test de dérive. Questions ouvertes : Q-P1-01 à Q-P1-05 (QUESTIONS.md).

### CR-P1-02 — lien de paiement public et carte : ce qui manque à l'espace adhérent (voie B)
- Lot demandeur : Phase 1, voie B (application web `apps/web/member`)
- Contrat : openapi.yaml (schema.sql seulement si les champs n'existent pas déjà en base)
- Changement voulu (tous additifs, champs facultatifs) :
  1. `PublicPaymentLink.expires_at` (`date-time`) : la planche affiche « Lien valable jusqu'au 08/10/2026 » ; le payeur ne le voit pas aujourd'hui (la date n'est donnée qu'à l'adhérent, dans `PaymentLink`).
  2. `PaymentChannel` += `carte_bancaire` : la planche et la tâche prévoient la carte pour la diaspora ; absente de l'énumération, donc jamais proposée (l'espace affiche les `channels` reçus).
  3. Statut public d'un paiement démarré (ex. `GET /v1/public/payment-links/{token}/checkout/{payment_id}` → `Checkout`, ou `PublicPaymentLink.state` `a_payer | payee | expiree`) : après `en_attente` sans `redirect_url`, le payeur n'a aucun moyen de savoir que c'est confirmé ; et 410 PAY-03 ne distingue pas « payé » d'« expiré » (voir CR-L4-01).
  4. Facultatif : montant débité dans la devise du canal (`Checkout.charged_amount_minor`, `charged_currency`) pour afficher l'euro en héros comme la planche ; en attendant, l'espace affiche un équivalent indicatif à la parité fixe (1 € = 655,957 FCFA).
  5. `MyCard.plan_name` (libellé commercial, « Santé Famille Or ») : seul `plan_code` existe, affiché tel quel (« Formule FAMILLE-OR »).
- Raison : écrans 03 et 04 de `specs/design/direction` ; questions `apps/web/member/QUESTIONS.md` Q-P1W-04 à 06 et 09. Rien n'est bloquant : l'espace fonctionne sur le contrat actuel.
- Impact : `apps/api/payments` (champs 1 à 4), `apps/api/member_space` (5) ; types régénérés (`make gen-api`) dans `apps/web/member`, `apps/web/console`.
- Statut : proposée

### CR-P2-01 — mesure produit : événements d'usage et indicateurs k-anonymes
- Lot demandeur : Phase 2, voie B (mesure produit)
- Contrat : schema.sql, openapi.yaml (events.md inchangé : les événements d'usage ne sont pas des événements métier et ne passent pas par `outbox_events`)
- Statut : **CR-P2-01 appliqué sur instruction de Dajan pour enchaîner les phases — à valider**. Extension strictement additive : aucune suppression, aucun changement de sens ; migrations 0001 et 0002 inchangées (empreinte de 0001 toujours vraie).
- Changement appliqué :
  - schema.sql + migration Alembic **0003** (`apps/api/migrations/versions/0003_mesure_produit.sql`, rejouable, retour arrière refusé sans validation humaine) : table `product_events` (`organization_id`, `name` en liste blanche fermée de 11 événements, `surface` console | comptoir | espace_adherent, `role`, `session_ref` = empreinte SHA-256 hexadécimale, `duration_ms` 0 à 86 400 000, `step` 1 à 20, `variant` en liste fermée, `occurred_at`, `expires_at` > `occurred_at`) ; RLS activée et forcée, politique unique `tenant_isolation` ; index `(organization_id, name, occurred_at)` et `(organization_id, expires_at)` ; droits de `mulema_app` : SELECT, INSERT, DELETE (purge par rétention), jamais UPDATE. Aucune colonne d'utilisateur, d'adhérent, de carte ni de texte libre.
  - openapi.yaml : tag `mesure` ; deux opérations `x-lot: P2` : `recordProductEvent` (`POST /v1/telemetry/events`, tous les rôles, 204) et `getProductMetrics` (`GET /v1/metrics/product`, `x-roles: [gestionnaire, admin]`, paramètres `from`/`to` existants) ; schémas `ProductEventName`, `ProductSurface`, `ProductEventVariant`, `ProductEventRequest` (`additionalProperties: false`), `ProductMetricKey`, `ProductMetric`, `ProductMetrics`.
  - `.spectral.yaml` : `x-lot` admet `P2` (niveau `--fail-severity=hint` inchangé).
- Garanties : organisation et heure prises du serveur ; `role` doit appartenir au jeton (403 AUTH-02) et correspondre à la surface (422) ; propriétés admises par événement (422 sinon) ; l'identifiant de session brut n'est jamais stocké (empreinte par organisation et par jour UTC) et il est refusé s'il contient l'identifiant de l'utilisateur, de son organisation, d'un attribut de portée, ou s'il n'est fait que de chiffres. Indicateurs calculés en base depuis `claims`, `claim_decisions`, `product_events` (non expirés), `payment_links`, `contributions`, `ledger_entries`/`ledger_lines`, `outbox_events` ; masqués sous 5 contributeurs (ni valeur ni effectif). Aucun appel réseau : rien ne quitte l'instance (R9).
- Raison : instruction Phase 2 voie B (« chaque écran a un indicateur lié à un comportement ») et métriques de pilotage citées par Dajan ; l'écran de décision du comptoir < 10 s (POLISH_CONTRACT §11, « à chronométrer ») n'avait aucun moyen d'être mesuré en usage réel.
- Impact : `apps/api/core` (matrice : deux opérations ; `AppModules.metrics` obligatoire), nouveau module `apps/api/metrics`, jeu d'isolation (une ligne `product_events`), tests de contrat et de migration (tête 0003). **Les types générés des applications web (`apps/web/member`, `apps/web/counter`, `apps/web/console`) doivent être régénérés par leur propriétaire (`make gen-api`)** : les tests de dérive de `member` et `counter` échouent tant que ce n'est pas fait. Questions ouvertes : Q-P2-01 à Q-P2-07 (QUESTIONS.md).

### CR-P2A-01 — garanties par type de soin dans « ma carte »
- Lot demandeur : Phase 2, voie A (UX : découverte de l'espace adhérent)
- Contrat : openapi.yaml
- Changement voulu : `MyCard.coverages` (facultatif) : liste `{category, label, coverage_rate_bp | null, annual_limit_xof | null, limit_scope}` de la version de produit en vigueur aujourd'hui (même forme que `Coverage`, déjà servie au gestionnaire par `getPlanVersion`) ; et `MyCard.plan_name` (déjà demandé par CR-P1-02 point 5).
- Raison : l'étape 1 de la découverte (« ce que la mutuelle rembourse et à quel taux ») ne peut montrer que le taux général de la carte (`coverage_rate_bp`), le plafond familial et la règle du réseau (R-04) : l'adhérent ne voit pas qu'optique ou dentaire ont un taux et un plafond propres. Aucune autre opération du rôle `adherent` ne les expose.
- Impact : `apps/api/member_space` (lecture de la version en vigueur, déjà faite pour les droits) ; types régénérés ; aucune migration.
- Statut : proposée

### CR-P2A-02 — date de fin de validité de la carte
- Lot demandeur : Phase 2, voie A (notifications dérivées)
- Contrat : openapi.yaml (schema.sql seulement si la colonne n'existe pas)
- Changement voulu : `MyCard.expires_on` et `MyBeneficiary.card_expires_on` (`date`, nullables).
- Raison : la notification « carte expirée » est aujourd'hui dérivée de la fin de couverture du bénéficiaire (`MyBeneficiary.valid_to`) ; le contrat ne connaît pas de date d'expiration de la carte elle-même. Sans elle, une carte révoquée ou arrivée à échéance n'est signalée qu'au comptoir (ID-06).
- Impact : `apps/api/member_space` ; types régénérés.
- Statut : proposée

### CR-P2A-03 — date du dernier changement de statut d'un dossier vu par l'adhérent
- Lot demandeur : Phase 2, voie A (notifications dérivées)
- Contrat : openapi.yaml
- Changement voulu : `MyClaim.status_changed_at` (`date-time`), date de la dernière décision ou du dernier changement d'état.
- Raison : « remboursement passé à l'étape suivante » se calcule aujourd'hui en comparant le statut à celui de la dernière lecture, gardé sur le téléphone (identifiant et code de statut seulement). Avec cette date, l'espace n'aurait plus rien à garder : comparer à l'heure de dernière ouverture suffirait.
- Impact : `apps/api/member_space` (lecture de `claim_decisions`) ; types régénérés ; aucune migration.
- Statut : proposée

### CR-P3-01 — marque blanche, espaces assureur et employeur, accueil d'organisation
- Lot demandeur : Phase 3, voie A (API) — vente clé en main aux assureurs
- Contrat : schema.sql, openapi.yaml (events.md inchangé : aucun nouvel événement métier)
- Statut : **CR-P3-01 appliqué sur instruction de Dajan pour enchaîner les phases — à valider**. Extension strictement additive : aucune suppression, aucun changement de sens ; migrations 0001, 0002 et 0003 inchangées (empreinte de 0001 toujours vraie).
- Décision métier : le non-objectif « pas de module assureur ni courtier » (PRD §2) est périmé depuis la décision de Dajan du 01/10/2026 (vendre One clé en main aux assureurs). PRD §2 amendé : assureur en lecture agrégée, employeur, marque blanche et accueil d'organisation entrent ; le courtier, toute lecture inter-organisations (même en gestion déléguée) et toute donnée de personne côté assureur ou employeur restent exclus.
- Changement appliqué :
  - schema.sql + migration Alembic **0004** (`apps/api/migrations/versions/0004_marque_blanche_partenaires.sql`, rejouable, retour arrière refusé sans validation humaine) :
    - listes fermées ÉLARGIES (mêmes noms de contrainte, tout ce qui passait passe encore) : capacité `plateforme` (`organizations_capabilities_check`), rôles `assureur` et `admin_plateforme` (`user_roles_role_check`, `product_events_role_check`) ;
    - déclencheur `user_roles_platform_admin_guard` : `admin_plateforme` refusé (MCP01) hors d'une organisation de capacité `plateforme` ;
    - table `organization_branding` (une ligne par organisation) : nom affiché (texte brut, 80), logo (`url` | `data_uri`, contrôles de forme), `theme` jsonb vérifié par `branding_theme_is_closed` (clés `light`/`dark` seulement, jetons `accent`, `accent_hover`, `accent_fg`, `brand_deep`, valeurs `#rrggbb`), domaine unique, textes légaux (texte brut, 4 000) ; droits SELECT, INSERT, UPDATE ;
    - table `configuration_templates` (gabarit versionné, en ajout seul : `forbid_mutation`) ; droits SELECT, INSERT ;
    - RLS activée ET forcée, politique unique `tenant_isolation` sur les deux tables ; une ligne de chaque dans le jeu d'isolation (test par table) ;
    - fonctions SECURITY DEFINER réservées à `mulema_app` : `resolve_organization_branding(slug, domaine)` (champs non sensibles) et `platform_create_organization(...)` (revérifie l'administrateur ACTIF d'une organisation « plateforme » ACTIVE ; statut `integration` ; jamais la capacité `plateforme` ; MCP01 refus, MCP02 identifiant pris).
  - openapi.yaml : tags `marque-blanche`, `espace-assureur`, `espace-employeur`, `plateforme` ; `Role` += `assureur`, `admin_plateforme` ; capacité `plateforme` ; `ErrorCode` += `BRD-01` (contraste), `BRD-02` (jeton hors liste), `BRD-03` (logo), `BRD-04` (domaine pris), `ORG-01` (identifiant pris), `ORG-02` (gabarit inconnu ou autre pays) ; `getCurrentUser`, `getCurrentOrganization`, `recordProductEvent` ouverts aux deux nouveaux rôles (surface console) ; dix opérations `x-lot: P3` :
    `getOrganizationBranding` (public), `getBrandingSettings`, `updateBrandingSettings` (admin), `getInsurerPortfolio`, `exportInsurerPortfolio` (assureur, admin), `getEmployerConsumption`, `listEmployerContracts` (employeur, portée `employer_id`), `createOrganization`, `listConfigurationTemplates`, `createConfigurationTemplate` (admin_plateforme).
  - `.spectral.yaml` : `x-lot` admet `P3` (niveau `--fail-severity=hint` inchangé).
- Gardes et preuves (tests d'abord, application assemblée, vrais jetons, `mulema_app` + `egress_guard`) :
  - contraste calculé par le serveur avec le calcul partagé `api.branding.contrast` (le test des jetons du contrat de design s'en sert aussi) sur chaque paire du contrat qui touche un jeton surchargé, en clair et en sombre ; accent égal à un statut refusé ; plein soleil non surchargeable ;
  - liste fermée vérifiée deux fois (API : BRD-02 ; base : contrainte `organization_branding_theme_check`) ;
  - logo : chemin interne, `https` vers un hôte:port de la liste blanche d'egress, ou data-URI PNG/WebP/JPEG à signature vérifiée ou SVG assaini par liste blanche (aucun script, `on*`, `style`, lien, image, `use`, DOCTYPE, entité, commentaire, référence externe), 32 Ko ;
  - k-anonymat (seuil 5 et paliers d'effectif de `api.metrics`) + protection contre la soustraction : statuts masqués ensemble, catégories et prestataires sous le seuil fondus dans `autres_regroupes` jusqu'à 5 personnes ; aucune personne dans les réponses ni dans le CSV (injection de formule neutralisée) ;
  - accueil d'organisation en une transaction : copie du gabarit en nouvelles lignes (règles et produits en version 1 `brouillon`), aucun identifiant commun, audit dans les deux organisations, tout ou rien ;
  - mutations jouées (garde neutralisée, rouge exigé et obtenu) : seuil k, masque complémentaire, fonte dans `autres`, filtre d'organisation hors RLS (deux requêtes), portée employeur, seuil de contraste, liste fermée côté API (la base refuse encore), matrice de rôles, RLS de `organization_branding`, attribut `on*` du SVG, hôte hors liste blanche, garde de la base pour `admin_plateforme` (matrice ouverte : 403 quand même), attribution de `admin_plateforme` par l'API.
- Raison : vente clé en main aux assureurs (décision du 01/10) ; aucune opération ne permettait de personnaliser la marque, de donner une vue agrégée à un assureur ou à un employeur, ni d'ouvrir une organisation sans SQL manuel.
- Impact : `apps/api/core` (rôles, matrice, codes d'erreur, `createUser`/`replaceUserRoles` refusent `admin_plateforme`, montage de `api.branding` et `api.partners`), `apps/api/metrics` (deux rôles sur la surface console), tests de contrat et de migration (tête 0004), jeu d'isolation (deux lignes). **`apps/web` n'est pas touché : les types générés des applications web doivent être régénérés par leur propriétaire (`make gen-api`)** ; un écran de réglage de marque, un espace assureur et un espace employeur restent à construire (voie B). Questions ouvertes : Q-P3-01 à Q-P3-12 (QUESTIONS.md).

### CR-P2-02 — mesure produit : k-anonymat par personne, anti-recoupement, identifiants bornés
- Lot demandeur : Phase 2, voie B (correctif de vérificateur sur CR-P2-01, commit 0608b8949)
- Contrat : openapi.yaml (passages P2 seulement : `recordProductEvent`, `getProductMetrics`, `ProductEventRequest`, `ProductMetricKey`, `ProductMetric`) ; schema.sql et events.md inchangés ; **aucune migration** (0003 inchangée, 0004 non touchée)
- Statut : **CR-P2-02 correctif de vérificateur appliqué sur instruction de Dajan — à valider**.
- Défauts prouvés par le vérificateur (attaques sur copie) :
  1. k-anonymat faux : l'effectif comptait des SESSIONS, une par chargement de page ; une personne seule franchissait le seuil en rechargeant cinq fois, et deux périodes recoupées isolaient une contribution masquée (effectif 5 → 6, médiane 6000 → 5000).
  2. identifiant possible : `duration_ms` admis sur les 11 événements, `session_id` acceptait du texte base64url de 22 à 64 caractères.
- Changement appliqué :
  - Contributeur = PERSONNE : `product_events.session_ref` (nom conservé, CHECK 64 hexadécimaux inchangé) porte `HMAC-SHA256(clé, "mulema.metrics.person.v1:" ‖ organisation ‖ utilisateur du jeton)`. Rien du client n'y entre. Clé : `MULEMA_METRICS_PSEUDONYM_KEY` (hexadécimal, 32 octets min., obligatoire, jamais en base ni dans le dépôt, absente de `repr`). Rotation : nouvelle clé + `MULEMA_METRICS_PSEUDONYM_KEY_SINCE=<jour>` ; les indicateurs d'usage ne comptent que les semaines qui commencent strictement après ce jour (sinon une personne aurait deux empreintes). Procédure dans `api/metrics/runtime.py`.
  - Médianes d'écran : médiane par personne puis médiane des personnes (une personne qui envoie cent événements pèse une fois).
  - Anti-recoupement : période élargie aux semaines civiles entières (lundi → dimanche, fuseau de l'organisation) et coupée à la dernière semaine terminée (`period_from`/`period_to` rendent la période publiée ; aucune semaine terminée → 422 VAL-01) ; chaque indicateur est masqué si une semaine non vide de la période a moins de 5 contributeurs (calculé sur les lignes qui déterminent la valeur) ; rien de postérieur à la fin de la période n'y entre (décision, paiement, fin d'accueil, réception de webhook : une période terminée ne bouge plus) ; événements d'usage comptés seulement sur des semaines dont aucun n'a pu expirer.
  - Effectif publié par palier (5, 10, 20, 50, 100 = « 100 ou plus »), jamais exact ; `contributors` reste un entier ≥ 5 (pas de changement de type pour les clients).
  - `session_id` : exactement `^[0-9a-f]{32}$`, validé puis écarté (ni stocké ni dérivé) ; toujours refusé s'il est l'identifiant de l'utilisateur, de son organisation ou d'un attribut de portée, ou fait de chiffres seuls. Pas de CHECK en base : la valeur n'est jamais stockée.
  - `duration_ms` : interdit (422, même 0) sauf `counter_decision_shown` (obligatoire, 0 à 300 000) et `onboarding_completed` (facultatif, 0 à 3 600 000, envoyé par l'espace adhérent) ; plafond du schéma 3 600 000.
  - Purge planifiable : `cd apps && uv run python -m api.metrics purge --organization <uuid> [...]` (quotidienne, à la charge de l'exploitation ; lit `MULEMA_INSURANCE_DATABASE_URL`, `MULEMA_DB_APP_ROLE`, refuse une connexion hors RLS). Sous `mulema_app`, la purge exige `expires_at <= now()` de la BASE en plus de l'horloge de l'appelant : une ligne non expirée n'est jamais supprimée.
- Preuves : `apps/api/metrics/tests/` (test_windows, test_privacy, test_catalog, test_runtime, test_repository) et `apps/api/tests/e2e/test_product_metrics.py` rejouent les deux attaques (personne seule qui recharge cinq fois → masqué ; semaine 1 publiée 6000/5 puis semaines 1+2 → masqué, semaine en cours jamais publiée). 25 mutations jouées (garde neutralisée, rouge exigé et obtenu), dont : contributeur = session, HMAC sans clé, semaine faible ignorée, effectif exact, semaine en cours publiée, semaine partiellement expirée, rotation ignorée, médiane sur les événements, bornes de fin retirées (décision, paiement, événement, réception), session texte, durée partout, borne de durée, purge sans horloge de la base, clé dans `repr`.
- Impact hors module : `tests/e2e/conftest.py` et `tests/e2e/test_mounted_operations.py` (clé de test tirée au hasard). **Les trois applications web tirent encore `session_id` en base64url 22 caractères (`newSessionId` de `apps/web/{console,counter,member}/src/lib/telemetry.ts`) : tous leurs événements sont refusés (422) tant que leur propriétaire ne passe pas à 16 octets en hexadécimal et ne régénère pas les types (`make gen-api`).** Le déploiement doit fournir `MULEMA_METRICS_PSEUDONYM_KEY`. `apps/api/partners` réutilise `contributor_band` (signature inchangée).
- Rend caduque Q-P2-05 (rotation journalière de l'empreinte de session) ; Q-P2-04 tranché pour le grand livre : effectif au seuil et par palier, sans règle par semaine (cumul d'écritures équilibrées par contrainte de base, la différence de deux cumuls vaut 0).
- À valider : seuil 5 et paliers ; semaine civile comme fenêtre (7 jours) ; bornes de durée (5 min comptoir, 1 h accueil) ; rétention 180 jours (Q-P2-02) ; empreinte stable par personne sur toute la rétention (reliable dans la base, non réidentifiable sans la clé) ; risque résiduel des indicateurs métier : un même bénéficiaire peut porter plusieurs dossiers d'une période (pas de pondération par personne pour les dossiers).

### CR-P3-02 — espaces assureur et employeur anti-recoupement, domaine prouvé, logo durci
- Lot demandeur : Phase 3, voie A (correctif de vérificateur sur CR-P3-01, commit 2ff9a4a3f)
- Contrat : schema.sql, openapi.yaml (passages P3 seulement) ; events.md inchangé
- Statut : **CR-P3-02 correctif de vérificateur appliqué sur instruction de Dajan — à valider**.
- Défauts prouvés par le vérificateur (attaques sur copie) :
  1. k-anonymat cassé par soustraction : [J] puis [J, J+1], ou la même période avant/après un dossier, isolaient la contribution d'UNE personne (1 dossier, 16 000 F).
  2. valeurs exactes publiées (effectif d'adhérents, comptes de dossiers, montants, JSON et CSV) ; garde d'injection de formule CSV sans test qui tombe (mutation M8 survivante).
  3. domaine détournable : un admin d'organisation pouvait déclarer l'hôte du lien de paiement (`payer.mulemacare.invalid`) ou `mulemacare.com`, aussitôt servi par la lecture publique.
  4. SVG : `<?xml-stylesheet …?>` en tête passait (prise pour une déclaration XML) ; réserves : `\u0085` dans un nom → 500, `foreignObject` refusé seulement par espace de noms (mutation survivante), hôte HealthOS admis pour un logo, lecture publique servant les organisations en intégration.
- Changement appliqué :
  - Espaces assureur et employeur (`apps/api/partners`) — même méthode que la mesure produit (CR-P2-02) : période élargie aux semaines civiles entières et coupée à la dernière semaine TERMINÉE (`period_from`/`period_to` rendent la période publiée ; aucune semaine terminée → 422 VAL-01 champ `to` ; fin dans le futur coupée) ; masque si une semaine non vide de la période a moins de 5 personnes (semaines de la demande ET de la décision d'un dossier, du paiement d'une cotisation) ; rien de postérieur à la fin de la période (dossier compté si sa DERNIÈRE décision avant la fin est un accord ; statuts d'adhérent = instantané à la fin de la période depuis `member_status_history` ; effectif des contrats employeur = fin de la dernière semaine terminée). Masques complémentaires et fonte dans `autres_regroupes` jugés semaine par semaine.
  - Jamais de valeur exacte : comptes (`members_total`, `members_by_status[].count`, `claims`) publiés au plancher du palier 5/10/20/50/100 ; montants (`premiums_xof`, `claims_cost_xof`, `covered_xof`) arrondis au millier de francs CFA ; CSV identique. Garde de formule CSV étendue (blancs de tête, `\n`, formes pleine chasse) et testée par mutation.
  - Domaine personnalisé (`apps/api/branding`) : liste réservée (BRD-05 : noms à usage spécial, domaines MulemaCare, hôte du lien de paiement public, destinations de la liste blanche d'egress et leurs zones parentes, sous-domaines compris) ; preuve de propriété par enregistrement DNS TXT `_mulemacare-verification.<domaine>` = `mulemacare-verification=<jeton 128 bits>` via un PORT (`DnsTxtResolver` ; défaut sans résolveur : rien n'est prouvé, le domaine reste désactivé, le slug reste utilisable ; implémentation de test en mémoire ; aucun appel réseau) ; lecture publique par domaine seulement si PROUVÉ ; changer de domaine efface la preuve (service ET déclencheur de base).
  - Lecture publique : organisations `active` seulement ; inconnue, en intégration ou inactive → même 404 NOT-01.
  - Logo : hôtes `https` sur une liste DÉDIÉE (`BrandingPorts.logo_hosts`, vide par défaut), jamais la liste blanche d'egress (HealthOS) ; SVG : seule déclaration `<?xml version="1.0" encoding="UTF-8"?>` en tout premier, toute autre instruction de traitement refusée (BRD-03) ; éléments actifs (`foreignObject`, `script`, `style`, `image`, `use`, `a`, `set`, `animate`…) refusés nommément, avant la liste blanche ; nom affiché : contrôles C0/C1, direction et séparateurs refusés en 422 (jamais 500).
  - schema.sql + migration Alembic **0005** (`apps/api/migrations/versions/0005_preuve_de_domaine.sql`, additive et rejouable, retour arrière refusé sans validation humaine ; 0001 à 0004 inchangées) : colonnes nullables `organization_branding.custom_domain_token` (`^[0-9a-f]{32}$`) et `custom_domain_verified_at` ; contraintes `organization_branding_domain_token_check`, `organization_branding_domain_proof_check` ; déclencheur `organization_branding_domain_reverify` ; `resolve_organization_branding` remplacée (même signature et mêmes droits ; `status = 'active'`, domaine prouvé seulement). Un domaine déclaré avant 0005 reste en base, en attente de preuve (aucune ligne réécrite).
  - openapi.yaml : opération `verifyBrandingDomain` (`POST /v1/organization/branding/domain-verification`, `x-lot: P3`, `x-roles: [admin]`, 200 `BrandingSettings`, 422 BRD-05/BRD-06) ; `ErrorCode` += `BRD-05` (domaine réservé, 422), `BRD-06` (propriété non prouvée, 422) ; schéma `DomainVerification` ; descriptions de `getOrganizationBranding`, `updateBrandingSettings`, `getInsurerPortfolio`, `exportInsurerPortfolio`, `getEmployerConsumption`, `listEmployerContracts` mises à jour.
- **Changements de forme pour les clients (à transmettre à l'agent web)** :
  1. `BrandingSettings` : DEUX CHAMPS AJOUTÉS (requis, nullables) : `custom_domain_status` (`en_attente_de_verification` | `verifie` | null) et `custom_domain_verification` (`{record_type: "TXT", record_name, record_value}` | null). Aucun champ retiré ni renommé.
  2. Nouvelle opération `verifyBrandingDomain` (bouton « Vérifier le domaine » de l'écran de marque) ; nouveaux codes d'erreur `BRD-05`, `BRD-06` à traduire.
  3. `OrganizationBranding` (lecture publique) : forme inchangée ; `custom_domain` vaut null tant que le domaine n'est pas prouvé ; `domain=` d'un domaine non prouvé → 404.
  4. `KAnonymousValue` : forme et types inchangés (`value` reste un entier), mais SENS CHANGÉ pour les comptes et montants : `value` d'un compte est le plancher du palier (afficher « 5 et plus », jamais « 5 adhérents » comme exact), `value` d'un montant est arrondi au millier (afficher « ≈ »). `period_from`/`period_to` peuvent différer de la période demandée (semaines entières, dernière semaine terminée) : l'interface doit afficher la période RENDUE ; une période sans semaine terminée (par exemple « cette semaine ») répond 422 VAL-01.
- Preuves (tests d'abord, rouges puis verts ; application assemblée, vrais jetons, `mulema_app` + `egress_guard`) : `apps/api/tests/e2e/test_partners.py` (attaques du vérificateur rejouées : [J] puis [J, J+1] → réponses identiques ; avant/après un dossier → identiques ; [S1, S2] avec une semaine d'une personne → masqué ; période future coupée ; CSV sans valeur exacte), `apps/api/partners/tests/` (`test_privacy`, `test_period`, `test_csv`), `apps/api/tests/e2e/test_branding.py` (org B refusée sur `payer.mulemacare.invalid` et `mulemacare.com` en BRD-05 ; preuve DNS ; preuve non héritée ; 404 identiques ; HealthOS refusé ; C1/bidi 422 ; attaques SVG du vérificateur), `apps/api/branding/tests/` (`test_logo`, `test_domains`), `apps/api/tests/contracts/test_migrations.py` (0005 additive, rejouable, gardes de base). Mutations jouées : voir la réponse de livraison.
- Impact hors modules : `apps/api/core` (codes BRD-05/06, matrice `verifyBrandingDomain`, `AppModules.branding` facultatif), `tests/e2e/conftest.py` (DNS de test, hôte de logo fictif), tests de contrat (tête 0005, opération P3, codes). **`apps/web` n'est pas touché : types à régénérer par leur propriétaire (`make gen-api`).** Questions ouvertes : Q-P3-13 à Q-P3-18.

### CR-P3-03 — manques constatés par la voie B (web) : liste des organisations, marque d'une autre organisation, plein soleil en système sombre
- Lot demandeur : Phase 3, voie B (web : marque blanche, espaces partenaires, écran « Organisations »)
- Contrat : openapi.yaml (1, 2), specs/design/mulemacare-tokens.css (3) ; schema.sql et events.md inchangés
- Statut : **demandé, NON appliqué** (la voie B ne touche pas aux contrats) — à valider par un humain.
- Changements demandés :
  1. `listOrganizations` (`GET /v1/platform/organizations`, `admin_plateforme`) : identifiant public, nom, pays, statut, capacités, gabarit d'origine, date d'accueil ; paginé. Aujourd'hui l'écran « Organisations » ne peut lister que celles accueillies depuis l'ouverture de la page (dit à l'écran). Aucune donnée métier.
  2. Marque d'une organisation accueillie par la plateforme : `getBrandingSettings` et `updateBrandingSettings` ne visent que l'organisation du jeton (`admin`). Pour livrer une marque « clé en main » à l'accueil, il faudrait soit une variante `admin_plateforme` (`/v1/platform/organizations/{slug}/branding`), soit acter que la marque est toujours réglée par l'admin de l'organisation (défaut actuel de l'écran). Q-P3-19.
  3. Jetons : `[data-sun]` (spécificité 0-1-0) perd contre `@media (prefers-color-scheme: dark) :root:not([data-theme="light"])` (0-2-0). Au comptoir, un téléphone en thème système sombre passé en plein soleil garde l'accent et les fonds SOMBRES (`--accent` lu = `#4fc2b0` au lieu de `#00473f`), contrairement au contrat (§9 : « noir sur blanc, quel que soit le thème »). Prouvé par `apps/web/counter/e2e/brand.spec.ts` (l'assertion de plein soleil est jouée en clair à cause de ce défaut). Correctif proposé : sélecteur `:root[data-sun], [data-sun]` (0-2-0, déclaré après le sombre). `make a11y` ne le voit pas : le plein soleil n'y est audité qu'en clair.
- Impact web si accepté : (1) remplacer la liste de session par `listOrganizations` ; (2) champ « organisation » dans l'écran de marque pour `admin_plateforme` ; (3) aucun (le moteur de thème exclut déjà `[data-sun]`).
