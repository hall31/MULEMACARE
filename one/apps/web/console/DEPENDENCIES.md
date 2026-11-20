# Dépendances — console (lot L6)

Chaque dépendance de `apps/web/console/package.json` avec sa licence, sa raison et l'alternative écartée (AGENTS.md, « Interdits »). Versions exactes épinglées ; verrou : `pnpm-lock.yaml` de la console (voir « À faire à la racine »).

## Serveur de mocks : MSW plutôt que Prism

LOTS.md propose Prism (`make mock-api`). Prism reste utilisable tel quel, mais il ne permet pas de prouver les deux parcours demandés sans modifier le contrat :

1. **Sans état.** Après `POST /v1/claims/{id}/decisions`, un `GET` du même dossier ne renvoie pas « accordée » : le parcours « le médecin-conseil accorde un dossier en revue » ne peut pas être vérifié de bout en bout.
2. **Sans rôles.** Prism ne lit pas le jeton ; il ne peut pas renvoyer `403 SEC-01` au gestionnaire et `200` au médecin-conseil sur `/medical-reason` sans en-tête `Prefer` piloté par le test, ce qui ne teste plus l'interface.
3. **Données sans sens métier.** Le contrat n'a presque pas d'`examples` ; Prism générerait des montants et statuts aléatoires. En ajouter serait une modification du contrat (interdite hors `CHANGE-REQUESTS.md`).

Garde-fous pour que les mocks restent « issus de l'OpenAPI » :
- les types du client sont générés depuis `specs/openapi.yaml` (`pnpm gen:api`) et `tests/unit/api-types.test.ts` échoue s'ils dérivent ;
- chaque route simulée doit exister dans le contrat, et 30 réponses (succès et erreurs, par rôle) sont validées contre les schémas du contrat (`tests/unit/contract.test.ts`, Ajv 2020-12).

## Exécution (`dependencies`)

| Paquet | Version | Licence | Raison | Alternative écartée |
|---|---|---|---|---|
| next | 16.3.6 | MIT | Imposé (AGENTS.md, Stack), App Router. 16.3.6 plutôt que 16.3.8 : 16.3.8 avait moins d'un jour à l'installation (politique d'âge minimal de pnpm). | — (imposé) |
| react, react-dom | 19.3.0 | MIT | Requis par Next.js 16. | — |
| @tanstack/react-query | 5.104.0 | MIT | Imposé (Stack) : cache, états chargement/erreur, mutations idempotentes. | — (imposé) |
| @tanstack/react-table | 8.21.3 | MIT | Imposé (Stack) : tables des prises en charge et des adhérents. v8 (API stable) plutôt que v9 : migration sans gain pour ce lot. | — (imposé) |
| radix-ui | 1.6.7 | MIT | Primitives des composants shadcn/ui (Dialog, AlertDialog, Tabs, Toggle, ToggleGroup, RadioGroup, Slot) : focus piégé, `aria-*`, clavier. Un seul paquet au lieu de sept `@radix-ui/react-*`. | Paquets `@radix-ui/react-*` séparés : même code, sept entrées à suivre. |
| class-variance-authority | 0.7.1 | Apache-2.0 | Variantes du bouton shadcn/ui. | Conditions à la main : moins lisible, non standard shadcn. |
| clsx | 2.1.1 | MIT | Composition de classes (`cn`), convention shadcn/ui. | — |
| tailwind-merge | 3.7.0 | MIT | Résout les conflits de classes Tailwind dans `cn`, convention shadcn/ui. | — |
| lucide-react | 0.577.0 | ISC | Icônes (jeu par défaut de shadcn/ui), SVG en ligne, `currentColor` : aucune couleur en dur. | SVG copiés du prototype : à maintenir à la main. |
| sonner | 2.0.8 | MIT | Toast de confirmation (composant `Sonner` de shadcn/ui), annoncé aux lecteurs d'écran ; couleurs passées par jetons. | Région `aria-live` maison : interdit si un équivalent shadcn existe (LOTS.md L6). |
| @fontsource/geist, @fontsource/geist-mono, @fontsource/schibsted-grotesk | 5.3.0 | OFL-1.1 | Polices des jetons (`--f-body`, `--f-mono`, `--f-display`) **auto-hébergées** dans le build : aucun appel à un CDN (R9, QUESTIONS.md Q-L0-16). | `next/font/google` : téléchargement depuis Google au build. Paquet `geist` (Vercel) : nom de famille haché, ne correspond pas au nom « Geist » des jetons. |

## Développement (`devDependencies`)

| Paquet | Version | Licence | Raison | Alternative écartée |
|---|---|---|---|---|
| typescript | 5.9.3 | Apache-2.0 | Typage strict (`pnpm typecheck`). 5.9 plutôt que 7 : greffon TypeScript de Next.js éprouvé sur 5.x. | — |
| @types/react, @types/react-dom, @types/node | 19.3.0 / 19.3.0 / 24.19.0 | MIT | Types pour React 19 et Node 24. | — |
| tailwindcss, @tailwindcss/postcss | 4.3.3 | MIT | Imposé (Stack). Les jetons sont exposés par `@theme inline` à partir de `specs/design/mulemacare-tokens.css`. | — (imposé) |
| msw | 2.15.0 | MIT | Serveur de mocks (voir plus haut) : service worker dans le navigateur, `msw/node` dans Vitest, mêmes gestionnaires. Son script `postinstall` est désactivé (`allowBuilds`) : le worker est généré par `pnpm mock:worker`. | Prism : voir plus haut. |
| openapi-typescript | 7.13.0 | MIT | Génère `src/api/schema.d.ts` depuis le contrat. | Types écrits à la main : dérive silencieuse. |
| ajv, ajv-formats | 8.20.0 / 3.0.1 | MIT | Valide les réponses des mocks contre les schémas JSON Schema 2020-12 du contrat. | Prism en mode validation : nécessite un serveur à part pendant les tests. |
| yaml | 2.9.1 | ISC | Lit `specs/openapi.yaml` dans les tests. | js-yaml : équivalent, `yaml` déjà présent dans l'arbre (Vite). |
| vitest | 4.1.11 | MIT | Imposé (Stack) : tests unitaires et de composants. | — (imposé) |
| jsdom | 26.1.0 | MIT | DOM des tests de composants (tiroir du dossier). | happy-dom : moins fidèle sur les rôles ARIA. |
| @testing-library/react, @testing-library/user-event | 16.3.3 / 14.6.7 | MIT | Tests de composants par rôle accessible, comme un utilisateur. | Enzyme : abandonné. |
| @playwright/test | 1.63.0 | Apache-2.0 | Imposé (Stack) : parcours et captures. | — (imposé) |
| @axe-core/playwright | 4.13.0 | MPL-2.0 | Audit axe (AGENTS.md, Stack) sur chaque page, clair et sombre. Utilisé sans modification (MPL : obligations seulement si le code du paquet est modifié). | Audit manuel : non reproductible. |

## À faire à la racine `one/` (fichiers partagés, non modifiés par ce lot)

- **Un seul verrou.** Pour l'instant la console a son propre `pnpm-workspace.yaml` et `pnpm-lock.yaml` (installation isolée, lots en parallèle). Après fusion des lots L6 et L7 : supprimer ces deux fichiers de la console, faire `pnpm install` à la racine, et ajouter dans `one/pnpm-workspace.yaml` :
  ```yaml
  allowBuilds:
    msw: false
  ```
  (sans ce réglage, pnpm 12 refuse `pnpm run` à cause du script `postinstall` de msw).
- **Makefile.** `make test-web` lance `pnpm -r --if-present run test` (Vitest de la console). Ajouter une cible pour les parcours : `test-web-e2e: ; $(PNPM) --filter @mulemacare-one/console test:e2e`, et faire passer `make check` par `pnpm --filter @mulemacare-one/console typecheck`.
- **`.gitignore`** racine : couvre déjà `node_modules/` et `.next/` ; ajouter `test-results/` et `playwright-report/` (déjà ignorés localement par `apps/web/console/.gitignore`).
- **`specs/QUESTIONS.md`** : les codes de motif des décisions humaines (`ACC-01`, `REF-01`, `REF-02`, `PCS-01`) sont provisoires dans `src/lib/decision-reasons.ts` en attendant Q-L0-13.
