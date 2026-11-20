# AGENTS.md — MulemaCare One

Lis ce fichier et `specs/PRD.md` avant toute action. Si les deux se contredisent, le PRD gagne et tu signales l'écart.

## Ce que tu construis

MulemaCare One est le noyau de gestion de la mutuelle santé MulemaCare (Côte d'Ivoire, Sénégal) : adhésions, cotisations, tiers payant en temps réel, prestations, grand livre. Il accueillera ensuite des assureurs en gestion déléguée, puis des courtiers. Les clients sont des gestionnaires de mutuelle, des médecins-conseils, des cliniques et des adhérents.

## Méthode de travail

1. Tu reçois un lot (L0 à L9) dans `specs/LOTS.md`. Tu ne travailles que sur ce lot, dans son périmètre de dossiers.
2. Tu crées une branche `lot/<id>-<nom-court>` (exemple : `lot/L3-grand-livre`).
3. Pour chaque exigence du lot, tu écris d'abord le test qui traduit son critère d'acceptation (section 4 du PRD), tu le vois échouer, puis tu codes jusqu'à ce qu'il passe.
4. Tu lances `make check` avant chaque commit. Un commit qui ne passe pas `make check` n'existe pas.
5. Tu ouvres une PR avec : le lot, les exigences couvertes (R1…), la liste des tests ajoutés, et pour les lots UI une capture du parcours.
6. Tu ne déclares jamais un lot fini : tu coches la définition du « fini » (PRD section 9) et un agent vérificateur valide.

## Stack

- Frontend : Next.js (App Router), TypeScript strict, Tailwind, shadcn/ui, TanStack Query et TanStack Table.
- Backend : Python 3.12, FastAPI, SQLAlchemy 2, Pydantic v2, Alembic.
- Données : PostgreSQL 16 (deux bases logiques : `clinical` et `insurance`), Redis.
- Tests : pytest, Vitest, Playwright, axe pour l'accessibilité.
- Structure : `apps/api/<module>`, `apps/web/console`, `apps/web/counter`, `specs/`, `infra/`.

## Commandes

```
make dev         # lance API, web et bases locales
make check       # lint + typecheck + tests (obligatoire avant commit)
make test-api    # uv run pytest
make test-web    # pnpm test
make a11y        # audit axe du comptoir
make egress      # test réseau : aucune requête hors liste blanche
```

## Règles métier qui ne se négocient pas

- **Secret médical.** La base `insurance` ne contient aucun diagnostic, aucun motif médical, aucune ordonnance. Le médecin-conseil lit le motif à la demande depuis HealthOS ; chaque lecture crée une entrée `audit_events`.
- **Les décisions viennent des règles, pas de l'IA.** Une prise en charge est accordée, routée ou refusée par le moteur de règles, qui enregistre `rule_id` et `rule_version`. JOE recommande, explique et prépare ; il ne change jamais l'état d'une prise en charge et ne déclenche aucun paiement.
- **Grand livre en ajout seul.** Jamais de `UPDATE` ni de `DELETE` sur `ledger_entries` ou `ledger_lines`. Une erreur se corrige par contre-passation. Chaque écriture a total débits = total crédits.
- **Versions de règles.** Un soin est évalué avec la version de produit et de règle en vigueur à la date du soin, pas à la date du traitement.
- **Résidence des données.** Aucune donnée personnelle ne quitte le pays de l'instance. Aucun appel à une API externe avec des données identifiantes, y compris un LLM.
- **Isolation.** Toute table métier porte `organization_id`. Toute requête est filtrée par l'organisation de l'utilisateur. Chaque nouvelle table reçoit son test d'isolation.
- **Argent.** Montants en entiers (FCFA, pas de décimales), jamais en flottants. Devise explicite dans les contrats.
- **Idempotence.** Tout webhook et toute commande de paiement est idempotent (clé d'idempotence stockée).

## Conventions de code

- Erreurs métier : exception typée avec un code stable (`R-01` droits suspendus, `R-04` hors réseau…). Le message affiché à l'utilisateur est en français, simple, et dit quoi faire.
- Logs structurés (JSON), sans nom, téléphone ni numéro de carte en clair. Identifiants pseudonymes uniquement.
- Pas de logique métier dans les routes : route → service → dépôt.
- Migrations Alembic pour tout changement de schéma, revues avec le lot L0.
- Dates en UTC en base, affichage en heure locale (Africa/Abidjan, Africa/Dakar).
- Textes de l'interface en français, dans des fichiers de traduction, jamais en dur dans les composants.

## Design

- Lis `docs/POLISH_CONTRACT.md` avant toute modification frontend (direction, contraste, mouvement, états, interdits).
- Utilise uniquement les jetons de `specs/design/mulemacare-tokens.css`. Aucune couleur hexadécimale dans le code des composants.
- Console (gestionnaire, médecin-conseil) : densité console, 14 px.
- Comptoir et espace adhérent : `data-surface="counter"` sur le layout, zones tactiles 48 px, texte 16 px minimum, bouton principal 56 px en bas de l'écran, pas de texte secondaire pâle.
- Mode plein soleil : attribut `data-sun`, noir sur blanc.
- Les statuts utilisent les couleurs sémantiques (ok, warn, crit), jamais la couleur d'accent.
- Respecte `prefers-reduced-motion`. Chaque contrôle a un état de focus visible.

## Contrats

`specs/schema.sql`, `specs/openapi.yaml` et `specs/events.md` sont les contrats. Si ton lot a besoin de les modifier, tu t'arrêtes, tu décris le changement voulu dans `specs/CHANGE-REQUESTS.md` et tu attends la validation d'un humain. Tu ne les modifies pas toi-même, même pour « juste une colonne ».

## Interdits

- Ajouter une dépendance sans justification écrite dans la PR (nom, licence, raison, alternative écartée).
- Mettre un secret, une clé ou un jeton dans le code ou les tests.
- Appeler un service réseau qui n'est pas dans `infra/egress-allowlist.txt`.
- Utiliser des données réelles d'adhérents dans les tests, les captures ou les logs. Les jeux de données sont fictifs.
- Désactiver un test, un linter ou une règle de typage pour faire passer `make check`.
- Élargir ton lot : pas de fonctionnalité « raisonnable » qui n'est pas dans le PRD. Les non-objectifs du PRD (section 2) sont des interdits.
- Créer une migration qui supprime ou réécrit des données sans validation humaine.

## En cas de doute

Tu t'arrêtes et tu écris la question dans la section 10 du PRD (ou dans `specs/QUESTIONS.md` si tu ne peux pas modifier le PRD), avec ta proposition par défaut. Tu continues sur la partie qui n'est pas bloquée. Tu ne devines pas une règle métier, un seuil, un taux ou une obligation réglementaire.

## Ce que tu dis dans ta réponse finale

Quatre lignes : ce qui est livré, les exigences couvertes avec le test qui les prouve, ce qui reste ouvert, et ce qu'un humain doit valider. Pas de récit du travail.
