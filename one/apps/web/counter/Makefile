# Comptoir PWA (lot L7). Binaires locaux appelés directement : aucun `pnpm run` ne déclenche
# d'installation de l'espace de travail racine.
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
BIN := node_modules/.bin

.PHONY: install gen-api typecheck test build e2e a11y icons check

install: ## Dépendances du comptoir (lockfile local tant que la racine n'est pas fusionnée)
	pnpm install --ignore-workspace --frozen-lockfile

gen-api: ## Types TypeScript générés depuis specs/openapi.yaml
	$(BIN)/openapi-typescript ../../../specs/openapi.yaml -o src/api/schema.d.ts

typecheck: ## tsc strict
	$(BIN)/tsc --noEmit

test: ## Vitest : politique hors ligne, signature, file IndexedDB, règles de design, dérive des types générés
	$(BIN)/vitest run

e2e: ## Playwright : cinq écrans, hors ligne, zones tactiles, PWA, axe (build + serveur inclus)
	$(BIN)/playwright test

a11y: ## axe-core WCAG 2.2 A/AA sur les cinq écrans, thèmes clair, sombre et plein soleil
	$(BIN)/playwright test e2e/a11y.spec.ts

icons: ## Régénère les icônes PWA à partir des jetons
	node scripts/gen-icons.mjs

check: typecheck test e2e ## Tout le lot L7
