# Dépendances — espace adhérent et lien de paiement diaspora (Phase 1, voie B)

Versions exactes épinglées (`package.json`, `pnpm-lock.yaml` local, installation
`pnpm install --ignore-workspace` comme le comptoir). Mêmes versions que le comptoir pour tout ce
qui est partagé ; trois ajouts justifiés ci-dessous (`uqr`, `yaml`, `ajv`).

## Exécution

| Paquet | Version | Licence | Raison | Alternative écartée |
|---|---|---|---|---|
| next | 16.3.6 | MIT | Stack imposée (AGENTS.md) : App Router, manifeste PWA, relais `/api` même origine. | — |
| react, react-dom | 19.3.0 | MIT | Requis par Next.js. | — |
| @tanstack/react-query | 5.104.0 | MIT | Stack imposée. Le QR est redemandé par `refetchInterval` calculé sur l'échéance annoncée par le serveur ; `networkMode: "always"` pour gérer soi-même le hors ligne. | Fetch dans des effets : hors stack. |
| **uqr** | 0.1.3 | MIT | **Ajout.** Le comptoir LIT le QR (`BarcodeDetector` natif) ; l'espace adhérent doit le DESSINER, et aucun navigateur ne sait encoder un QR. uqr (unjs) est un portage de l'encodeur de référence de Nayuki, sans dépendance, ESM, environ 4 Ko compressés, chargé à part après les données (hors du JavaScript initial). Correction d'erreur M. Testé : la matrice affichée est recalculée dans Playwright à partir de la charge utile servie (`e2e/journeys.spec.ts`). | `qrcode` (MIT) : plus lourd, dépendances, sortie canvas/data-URL inutile ici ; encodeur maison : 300 lignes de Reed-Solomon et de masques à maintenir et à prouver ; QR rendu côté serveur : le QR change toutes les 30 s et doit tourner hors de tout aller-retour HTML. |

**Polices : aucune dépendance.** `src/app/fonts/*.woff2` (Outfit, Plus Jakarta Sans, Inter, OFL-1.1,
licences à côté) sont des copies à l'identique de `apps/web/counter/src/app/fonts`, servies par
`next/font/local` (empreinte, repli ajusté, préchargement de la seule police de texte). Aucun CDN.

Aucune autre dépendance d'exécution : partage (Web Share natif, lien `wa.me` ouvert par
l'adhérent, `navigator.clipboard`), plein écran (Fullscreen API), écran allumé (Wake Lock API),
service worker écrit à la main (`public/sw.js`), traductions (`src/i18n`).

## Développement et tests

| Paquet | Version | Licence | Raison | Alternative écartée |
|---|---|---|---|---|
| typescript | 5.9.3 | Apache-2.0 | `tsc --noEmit` strict (versions du comptoir). | — |
| @types/node, @types/react, @types/react-dom | 24.19.0 / 19.3.0 / 19.3.0 | MIT | Typage. | — |
| tailwindcss, @tailwindcss/postcss | 4.3.3 | MIT | Stack imposée. Palette, échelle de texte, rayons et ombres par défaut retirés : seules les classes issues des jetons existent, et aucune taille sous 16 px. | — |
| openapi-typescript | 7.13.0 | MIT | Types générés depuis `specs/openapi.yaml` : client, fixtures et mock Playwright ne compilent pas s'ils s'écartent du contrat. | openapi-fetch : un client maison d'environ 100 lignes garde la main sur le délai, l'idempotence et la détection de coupure. |
| vitest | 5.0.2 | MIT | Tests unitaires. | — |
| **yaml** | 2.9.1 | ISC | **Ajout (déjà utilisé par la console, même version).** `src/contract.test.ts` lit `specs/openapi.yaml` pour prouver qu'aucune réponse consommée ne déclare de clé médicale, de score ou de règle interne, et que chaque donnée simulée est conforme au schéma, sans clé en plus. | Types seuls : ils n'empêchent pas une clé en trop à l'exécution ; analyse du YAML à la main : fragile. |
| **ajv** | 8.20.0 | MIT | **Ajout (déjà utilisé par la console, même version).** `src/test/contract-event.ts` valide chaque événement de mesure émis (tests unitaires et mock Playwright, qui répond 422 comme l'API) contre `ProductEventRequest` de `specs/openapi.yaml` : identifiant de session `^[0-9a-f]{32}$`, champs et bornes (CR-P2-02). Jamais embarqué dans l'app. | Validateur maison de JSON Schema : fragile ; `src/contract.test.ts` ne vérifie que les clés, pas les motifs ni les bornes. |
| @playwright/test | 1.63.0 | Apache-2.0 | Parcours, réseau coupé, service worker, mesures tactiles, performance par CDP. | — |
| @axe-core/playwright | 4.13.0 | MPL-2.0 | axe WCAG 2.0/2.1/2.2 A et AA, clair et sombre. Utilisé sans modification. | — |

## Mocks de l'API : même choix que le comptoir (pas MSW)

- **Développement manuel** : `make mock-api` à la racine (Prism) puis
  `MULEMA_API_URL=http://localhost:4010 NEXT_PUBLIC_MULEMA_AUTH_MODE=test node_modules/.bin/next dev -p 3200`.
- **Tests Playwright** : `e2e/mock-api.ts`, interception `page.route` typée par le contrat et nourrie
  par `src/test/fixtures.ts` (vérifiées par `src/contract.test.ts`). Mock à état : QR qui change
  à chaque appel avec une fenêtre réglable, clés d'idempotence, coupures ciblées, paiement
  confirmé / en attente / lien expiré (410) / inconnu (404).
- **MSW écarté** pour la même raison que le comptoir : son service worker entre en conflit avec
  celui de la PWA sur la même portée, et il embarquerait du code de mock dans le bundle.
