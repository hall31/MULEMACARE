# Code partagé des apps web — moteur de thème par organisation (P3)

`apps/web/shared/brand` : lecture de `getOrganizationBranding`, liste fermée des jetons, garde de
contraste WCAG AA (mêmes paires et mêmes seuils que `apps/api/branding/palette.py`, vérifiés par test),
feuille de style de la marque, logo assaini, couleur conforme la plus proche, organisations fictives.

## Pourquoi un paquet de l'espace de travail importé par alias, et pas une dépendance `workspace:*`

- **Une seule copie de la logique de sécurité** (liste fermée, contraste, logo) : quatre copies dériveraient.
- **Aucun build** : du TypeScript pur, sans React ni Next, compilé par chaque app (alias `@shared/*` dans
  `tsconfig.json` et `vitest.config.ts` ; racine Turbopack = `one/`, donc le dossier est dans le graphe).
- **Pas de `workspace:*`** dans les apps : le comptoir et l'espace adhérent gardent leur installation
  isolée (`pnpm install --ignore-workspace`, leur Makefile), qu'une dépendance de workspace casserait.
- Le `package.json` du dossier n'existe que pour que `make test-web` (`pnpm -r`) joue son typage et ses
  tests (`pnpm --filter @mulemacare-one/shared test`).
- Les adaptateurs React (style dans le `<head>`, contexte du nom et du logo, avertissement de
  développement) restent dans chaque app : 3 petits fichiers `src/brand/`, chacun à la convention de son app.

## Dépendances (développement seulement)

| Paquet | Version | Licence | Raison |
|---|---|---|---|
| typescript | 5.9.3 | Apache-2.0 | Typage strict du module. |
| vitest | 5.0.2 | MIT | Tests (version du comptoir et de l'espace adhérent). |
| @types/node | 24.19.0 | MIT | Lecture des contrats dans les tests de parité. |

`brand/contract-palette.ts` est un miroir GÉNÉRÉ des couleurs du contrat (`node scripts/gen-contract-palette.mjs`),
tenu identique à `specs/design/mulemacare-tokens.css` par `brand/contract-palette.test.ts`.
