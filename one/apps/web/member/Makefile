# Espace adhérent et lien de paiement diaspora (Phase 1, voie B). Binaires locaux appelés
# directement : aucun `pnpm run` ne déclenche d'installation de l'espace de travail racine.
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
BIN := node_modules/.bin

.PHONY: install gen-api typecheck test build e2e a11y perf screenshots check

install: ## Dépendances (lockfile local, comme le comptoir)
	pnpm install --ignore-workspace --frozen-lockfile

gen-api: ## Types TypeScript générés depuis specs/openapi.yaml
	$(BIN)/openapi-typescript ../../../specs/openapi.yaml -o src/api/schema.d.ts

typecheck: ## tsc strict
	$(BIN)/tsc --noEmit

test: ## Vitest : contrat sans donnée médicale, QR, hors ligne, purge de la carte, partage, jetons, traductions, dérive des types générés
	$(BIN)/vitest run

build: ## next build
	$(BIN)/next build

e2e: ## Playwright : parcours, états, hors ligne, PWA, zones tactiles, axe, performance (build + serveur inclus)
	$(BIN)/playwright test

a11y: ## axe-core WCAG 2.2 A/AA sur chaque écran et état, clair et sombre
	$(BIN)/playwright test e2e/a11y.spec.ts

perf: ## LCP / CLS / poids sur 3G rapide, carte et lien de paiement
	$(BIN)/playwright test e2e/perf.spec.ts --workers=1

screenshots: ## Captures dans screenshots/ et comparaisons avec la planche (compare-*.png)
	MEMBER_SCREENSHOTS=1 $(BIN)/playwright test e2e/screenshots.spec.ts --workers=1

check: typecheck test e2e ## Tout l'espace adhérent
