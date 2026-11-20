# Dépendances — comptoir PWA (lot L7)

Versions exactes épinglées (`package.json`, `pnpm-lock.yaml` local). Toutes publiées depuis plus
d'un jour (délai minimal de pnpm respecté, aucune exception ajoutée).

## Exécution

| Paquet | Version | Licence | Raison | Alternative écartée |
|---|---|---|---|---|
| next | 16.3.6 | MIT | Stack imposée (AGENTS.md) : App Router, manifeste PWA (`app/manifest.ts`), relais `/api` même origine. | Vite + plugin PWA : hors stack. |
| react, react-dom | 19.3.0 | MIT | Requis par Next.js. | — |
| @tanstack/react-query | 5.104.0 | MIT | Stack imposée : `/v1/me` et politique hors ligne. `networkMode: "always"` pour que le comptoir gère lui-même la coupure au lieu de mettre les requêtes en pause. | Fetch à la main dans des effets : hors stack. |

**Polices : aucune dépendance (Phase 1, direction « Registre émeraude »).** Les paquets
`@fontsource/geist`, `@fontsource/geist-mono` et `@fontsource/schibsted-grotesk` (5.3.0) sont
**retirés** : la direction validée (`docs/POLISH_CONTRACT.md` §4) remplace Geist et Schibsted
Grotesk par Outfit (titres), Plus Jakarta Sans (texte) et Inter (chiffres).

| Fichiers | Licence | Raison | Alternative écartée |
|---|---|---|---|
| `src/app/fonts/*.woff2` : Outfit, Plus Jakarta Sans, Inter, variables, sous-ensemble latin (32 + 27 + 48 Ko = 107 Ko) | OFL-1.1 (`src/app/fonts/OFL-*.txt`) | Copies à l'identique de `specs/design/direction/fonts` (extraits de `@fontsource-variable/*` 5.3.0). Servies par `next/font/local` (fonction de Next, pas de paquet) : fichiers à empreinte sous `/_next/static/media`, donc mis en cache par le service worker pour le démarrage hors ligne ; police de repli aux métriques ajustées (CLS) ; préchargement de la seule police de texte ; `font-display: swap`. Aucun appel réseau hors de l'origine. | `@fontsource-variable/{outfit,plus-jakarta-sans,inter}` : trois paquets pour trois fichiers déjà livrés avec la planche ; `@font-face` + copie dans `public/` : pas d'empreinte, pas de repli ajusté, et le service worker aurait dû apprendre un nouveau chemin ; `next/font/google` : téléchargement depuis Google au build, interdit. |

Aucune autre dépendance d'exécution : IndexedDB (petite enveloppe maison d’une centaine de lignes,
`src/offline/db.ts`), signature (WebCrypto natif), lecture du QR (`BarcodeDetector` natif de
Chrome Android), service worker (écrit à la main, `public/sw.js`), traductions (`src/i18n`, une
seule langue).

## Développement et tests

| Paquet | Version | Licence | Raison | Alternative écartée |
|---|---|---|---|---|
| typescript | 5.9.3 | Apache-2.0 | `tsc --noEmit` strict. 5.x car `openapi-typescript` exige `^5`. | TypeScript 7 : incompatible avec openapi-typescript. |
| @types/node, @types/react, @types/react-dom | 24.19.0 / 19.3.0 / 19.3.0 | MIT | Typage. Node 24 = runtime du poste. | — |
| tailwindcss, @tailwindcss/postcss | 4.3.3 | MIT | Stack imposée. Palette, échelle typographique, polices et rayons par défaut **retirés** (`@theme { --color-*: initial; … }`) : seules les classes issues des jetons existent, et aucune taille de texte sous 16 px. | — |
| openapi-typescript | 7.13.0 | MIT | Types générés depuis `specs/openapi.yaml` : le client, le mock Playwright et les fixtures ne compilent pas s'ils s'écartent du contrat. | openapi-fetch (client généré) : un client maison d’environ 120 lignes suffit et garde la main sur le délai, l'idempotence et la détection de coupure. |
| vitest | 5.0.2 | MIT | Tests unitaires (stack). | Jest : plus lourd, ESM moins simple. |
| ajv | 8.20.0 | MIT | **Ajout (déjà utilisé par la console, même version).** `src/test/contract-event.ts` valide chaque événement de mesure émis (tests unitaires et mock Playwright) contre `ProductEventRequest` de `specs/openapi.yaml` (JSON Schema 2020-12 d'OpenAPI 3.1) : identifiant de session `^[0-9a-f]{32}$`, champs et bornes (CR-P2-02). Jamais embarqué dans l'app. | Validateur maison : réécrire JSON Schema (motifs, `$ref`, `additionalProperties`) est fragile ; comparer seulement des clés : laisse passer un identifiant ou une durée hors contrat. |
| yaml | 2.9.1 | ISC | **Ajout (déjà utilisé par la console et l'espace adhérent, même version).** Lecture de `specs/openapi.yaml` pour le juge ci-dessus. | Découper le YAML à la main (ce que faisait `telemetry.test.ts`) : fragile. |
| fake-indexeddb | 6.2.5 | Apache-2.0 | IndexedDB en mémoire pour tester la file de synchronisation sous Node. | Tester la file seulement dans Playwright : plus lent, moins ciblé. |
| @playwright/test | 1.63.0 | Apache-2.0 | Parcours, réseau coupé (`context.setOffline`), mesures des zones tactiles, service worker (stack). | Cypress : pas de coupure réseau réelle ni de multi-contexte. |
| @axe-core/playwright | 4.13.0 | MPL-2.0 | `make a11y` : axe-core, WCAG 2.0/2.1/2.2 A et AA (exigé par LOTS.md). Utilisé sans modification ; MPL-2.0 n'impose rien au code qui l'appelle. | pa11y : moteur axe identique, outil en plus. |

## Mocks de l'API : Prism pour le développement, mock typé dans Playwright pour les tests (pas MSW)

- **Développement manuel** : `make mock-api` à la racine (Prism, déjà fourni par L0) puis
  `MULEMA_API_URL=http://localhost:4010 next dev`. Le comptoir appelle `/api/*` en même origine,
  relayé par Next vers Prism : pas de CORS. Les sept requêtes émises par le comptoir ont été
  rejouées contre Prism : **aucune violation de requête**.
- **Tests Playwright** : `e2e/mock-api.ts`, interception `page.route` typée par le contrat. Il faut
  un mock **à état** (3 codes faux puis blocage ID-04, file hors ligne rapprochée par `offline_ref`,
  enregistrement de la clé publique pour vérifier la signature) : le mode statique de Prism renvoie
  toujours le premier exemple, et son mode dynamique des données aléatoires.
- **MSW écarté** : en navigateur il s'appuie sur son propre service worker, qui entre en conflit
  avec le service worker PWA sur la même portée — précisément ce que le lot doit prouver. Il
  aurait aussi embarqué du code de mock dans le bundle du comptoir.

## Outil de développement non embarqué

`scripts/gen-icons.mjs` rend les icônes PWA avec le Chromium de Playwright à partir des jetons
(aucune couleur recopiée). Les PNG produits sont dans `public/icons/`.
