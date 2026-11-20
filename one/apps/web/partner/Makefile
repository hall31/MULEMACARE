# Espaces assureur et employeur (Phase 3, voie B). Binaires locaux appelés directement.
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
BIN := node_modules/.bin

.PHONY: gen-api typecheck test build e2e a11y perf check

gen-api: ## Types TypeScript générés depuis specs/openapi.yaml
	$(BIN)/openapi-typescript ../../../specs/openapi.yaml -o src/api/schema.d.ts

typecheck: ## tsc strict
	$(BIN)/tsc --noEmit

test: ## Vitest : contrat des mocks, k-anonymat affiché, états, règles de design
	$(BIN)/vitest run

build: ## Build de production
	$(BIN)/next build

e2e: ## Playwright : parcours, export CSV, responsive 375/768/1280, marques, axe (build + serveur inclus)
	$(BIN)/playwright test

a11y: ## axe-core WCAG 2.2 A/AA : espaces assureur et employeur, clair et sombre, 375 et 1280 px
	$(BIN)/playwright test tests/e2e/a11y.spec.ts

perf: ## LCP, CLS, polices, aucune ressource tierce (3G rapide, processeur ×4)
	$(BIN)/playwright test tests/e2e/perf.spec.ts

check: typecheck test build e2e
