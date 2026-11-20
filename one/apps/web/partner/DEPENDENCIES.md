# Dépendances — espaces partenaires (Phase 3, voie B)

Espace assureur et espace employeur. Mêmes versions exactes que la console et le comptoir : aucun
paquet nouveau dans l'espace de travail (verrou `one/pnpm-lock.yaml`, importateur ajouté seulement).

## Exécution

| Paquet | Version | Licence | Raison | Alternative écartée |
|---|---|---|---|---|
| next | 16.3.6 | MIT | Imposé (AGENTS.md, Stack), App Router, rendu serveur de la marque avant le premier affichage. | — (imposé) |
| react, react-dom | 19.3.0 | MIT | Requis par Next.js 16. | — |
| @tanstack/react-query | 5.104.0 | MIT | Imposé (Stack) : cache, états chargement / erreur, export en mutation. | — (imposé) |

**Pas de bibliothèque de graphiques** : les graphiques sont des barres HTML décoratives (`aria-hidden`)
avec la valeur écrite à côté et un tableau alternatif (`components/bar-chart.tsx`). Recharts, Nivo ou
Chart.js auraient ajouté 40 à 100 Ko de JavaScript et des SVG dont l'accessibilité se refait à la main.
**Pas de radix-ui, lucide-react, sonner, class-variance-authority, tailwind-merge** (présents dans la
console) : boutons, pastilles et icônes tiennent en 150 lignes (`components/ui.tsx`), sans recouvrement de classes.

## Développement

| Paquet | Version | Licence | Raison | Alternative écartée |
|---|---|---|---|---|
| typescript | 5.9.3 | Apache-2.0 | Typage strict. | — |
| @types/react, @types/react-dom, @types/node | 19.3.0 / 19.3.0 / 24.19.0 | MIT | Types. | — |
| tailwindcss, @tailwindcss/postcss | 4.3.3 | MIT | Imposé ; palette et échelle par défaut retirées, jetons du contrat seulement. | — (imposé) |
| msw | 2.15.0 | MIT | Mocks issus du contrat, dans le navigateur (démonstration) et dans Vitest (`msw/node`), comme la console (raisons dans `apps/web/console/DEPENDENCIES.md`). Worker copié de la console (`public/mockServiceWorker.js`, régénérable par `pnpm mock:worker`). | Prism : sans état ni rôles. |
| openapi-typescript | 7.13.0 | MIT | `src/api/schema.d.ts` généré (`make gen-api`) ; dérive détectée par `tests/unit/api-types.test.ts`. | Types à la main. |
| ajv, ajv-formats, yaml | 8.20.0 / 3.0.1 / 2.9.1 | MIT / MIT / ISC | Réponses des mocks validées contre le contrat (`tests/unit/contract.test.ts`). | — |
| vitest, jsdom | 4.1.11 / 26.1.0 | MIT | Tests unitaires et de composants (même couple que la console). | happy-dom. |
| @testing-library/react, @testing-library/user-event | 16.3.3 / 14.6.7 | MIT | Tests par rôle accessible. | — |
| @playwright/test, @axe-core/playwright | 1.63.0 / 4.13.0 | Apache-2.0 / MPL-2.0 | Parcours, responsive, captures, axe AA, budget de performance. | — |

## Code partagé et polices

- Moteur de thème par organisation : `apps/web/shared/brand` (voir `apps/web/shared/DEPENDENCIES.md`),
  importé par l'alias `@shared/*` (tsconfig, Vitest), compilé par Next (racine Turbopack = `one/`).
- Polices du contrat, auto-hébergées : copies des woff2 du comptoir (`src/app/fonts/`, OFL-1.1, licences à côté).

## Mesure produit

Aucun événement envoyé : le catalogue fermé (`ProductEventName`) n'a aucun événement propre à ces espaces,
et la consigne interdit d'en ajouter. Le client de mesure n'est donc pas embarqué (rien à consentir).
