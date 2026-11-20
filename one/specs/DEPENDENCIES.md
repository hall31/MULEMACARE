# Dépendances — MulemaCare One

Toute dépendance ajoutée est listée ici avec sa licence, sa raison et l'alternative écartée (AGENTS.md, « Interdits »). Versions exactes : `uv.lock`.

## Python — exécution (`pyproject.toml`, `dependencies`)

| Paquet | Version (lock L0) | Licence | Raison | Alternative écartée |
|---|---|---|---|---|
| sqlalchemy | 2.1.1 (`>=2.0,<2.2`) | MIT | ORM imposé par la stack (AGENTS.md) ; requis par Alembic. | — (imposé) |
| alembic | 1.20.0 | MIT | Migrations imposées par la stack ; 0001 applique `specs/schema.sql`. | Scripts SQL à la main : pas d'historique de version en base. |
| psycopg[binary] | 3.3.6 | LGPL-3.0-only | Pilote PostgreSQL synchrone pour Alembic et les tests de contrat (exécution de scripts multi-instructions avec PL/pgSQL). Utilisé comme bibliothèque non modifiée. | asyncpg (Apache-2.0) : asynchrone, inadapté à Alembic ; reste le candidat du runtime async en L1, à justifier par L1. psycopg2 : ancienne génération. |

## Python — développement (`dependency-groups.dev`)

| Paquet | Version | Licence | Raison | Alternative écartée |
|---|---|---|---|---|
| pytest | 8.4.2 | MIT | Tests imposés par la stack. | — |
| ruff | 0.16.9 | MIT | Lint + format (`make lint`). | flake8 + black : deux outils au lieu d'un. |
| mypy | 1.20.2 | MIT | Typage strict (`make typecheck`). | pyright : exige Node côté Python. |
| pgserver | 0.1.4 | Apache-2.0 (fichier LICENSE du paquet ; binaires PostgreSQL sous licence PostgreSQL) | Fournit un **PostgreSQL 16.2 réel** embarqué pour les tests, sans Docker ni installation système. Dépendances transitives : fasteners (Apache-2.0), platformdirs (MIT), psutil (BSD-3-Clause). | Docker/testcontainers : démon absent sur le poste de dev ; PostgreSQL Homebrew : version 18, pas 16 ; PGlite : WASM, pas un serveur PostgreSQL 16 natif (triggers différés et RLS à reprouver). |

En CI, `MULEMA_TEST_DATABASE_URL` peut pointer vers un service PostgreSQL 16 ; pgserver n'est alors pas démarré.

## Outils Node exécutés à la demande (non installés dans le dépôt)

| Outil | Version | Licence | Usage | Raison |
|---|---|---|---|---|
| @stoplight/spectral-cli | 6.16.3 | Apache-2.0 | `make contracts` (via `pnpm dlx`, inclus dans `make check`) | Linter OpenAPI demandé par LOTS.md (L0). Premier lancement : téléchargement depuis le registre npm, puis cache pnpm. |
| @stoplight/prism-cli | 5.16.0 | Apache-2.0 | `make mock-api` (via `pnpm dlx`) | Serveur de mocks du contrat pour L6/L7 (LOTS.md). |

## Aucune dépendance web

`apps/web/console` et `apps/web/counter` sont des paquets vides au lot L0 ; leurs dépendances (Next.js, Tailwind, shadcn/ui, TanStack…) seront justifiées par L6 et L7.

## Ajouts d'intégration vague 1 (L1, L2, L3, L9)

| Nom | Licence | Raison | Alternative écartée |
|---|---|---|---|
| fastapi | MIT | API HTTP des lots L1, L3 (stack imposée par AGENTS.md) | — |
| greenlet | MIT | requis par SQLAlchemy asyncio | — |
| hypothesis (dev) | MPL-2.0 | tests de propriété R3 (L2) et R7 (L3) | tests à exemples seuls, insuffisants pour R7 |
| httpx (dev) | BSD-3-Clause | client de test FastAPI ; starlette le signale déprécié au profit de httpx2, à revoir | requests |

## Phase 4, voie 2 — durcissement : retrait de la cryptographie maison

| Nom | Version (lock) | Licence | Raison | Alternative écartée |
|---|---|---|---|---|
| cryptography | 46.0.7 (`>=46,<47`) | Apache-2.0 OU BSD-3-Clause (double licence au choix) ; dépendances transitives cffi (MIT) et pycparser (BSD-3-Clause) | Retirer la cryptographie écrite à la main : vérification ES256 des accords hors ligne (`apps/api/claims/ecdsa.py`, auparavant arithmétique de courbe P-256 en Python pur) et scellement du secret de carte (`apps/api/members/cards.py`, auparavant flot XOR dérivé de HMAC + étiquette HMAC, Q-L4-05) remplacé par AES-256-GCM avec données associées et identifiant de clé. Bibliothèque de référence de l'écosystème Python, adossée à OpenSSL, maintenue par la PyCA, roues binaires pour macOS et Linux. | Garder le code maison : non audité, non constant en temps, aucune revue tierce. PyCryptodome (BSD/domaine public) : moins répandu, API plus bas niveau. `ecdsa` (python-ecdsa, MIT) : Python pur, non constant en temps, ne couvre pas AES-GCM. PyNaCl (Apache-2.0) : pas de P-256 ni d'AES-GCM (ES256 est imposé par le format du comptoir, Q-L7-03). |

`pyjwt[crypto]` (qui tire aussi `cryptography`) est ajouté en parallèle par la voie OIDC : sa justification relève de cette voie.
