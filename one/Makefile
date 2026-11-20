# MulemaCare One — commandes (AGENTS.md). `make check` est obligatoire avant tout commit.
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

UV ?= uv
PNPM ?= pnpm
SPECTRAL ?= $(PNPM) dlx @stoplight/spectral-cli@6.16.3
PRISM ?= $(PNPM) dlx @stoplight/prism-cli@5.16.0

.PHONY: help check lint typecheck contracts test-api test-web mock-api dev a11y perf egress

help: ## Liste les commandes
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

check: lint typecheck contracts test-api test-web ## Lint + typage + contrats + tests (obligatoire avant commit)

lint: ## Ruff (lint + format)
	$(UV) run ruff check .
	$(UV) run ruff format --check .

typecheck: ## mypy strict
	$(UV) run mypy

contracts: ## Lint Spectral de specs/openapi.yaml
	$(SPECTRAL) lint specs/openapi.yaml --ruleset .spectral.yaml --fail-severity=hint

test-api: ## Tests Python (PostgreSQL 16 embarqué, ou MULEMA_TEST_DATABASE_URL)
	$(UV) run pytest

test-web: ## Typage, tests et build des apps web (console, comptoir, adhérent, partenaires) et du moteur de thème partagé
	@# pnpm -r couvre tout apps/web/* : console, counter, member, partner (P3) et shared (moteur de thème, sans build).
	$(PNPM) -r --if-present run typecheck
	$(PNPM) -r --if-present run test
	$(PNPM) -r --if-present run build

mock-api: ## Serveur de mocks Prism sur le contrat (pour L6/L7)
	$(PRISM) mock specs/openapi.yaml --port 4010

dev: ## API, web et bases locales — serveur ASGI non installé (voir le message)
	@echo "make dev : aucun serveur ASGI (uvicorn) dans les dépendances ; l'ajouter demande une" >&2
	@echo "justification (specs/DEPENDENCIES.md). L'application assemblée est" >&2
	@echo "api.core.app.create_app(settings, identity_provider=..., modules=AppModules(...)) ;" >&2
	@echo "elle est exercée de bout en bout par : $(UV) run pytest apps/api/tests/e2e" >&2
	@echo "Pour les UI : make mock-api." >&2; exit 2

a11y: ## Audit axe du comptoir, de l'espace adhérent et des espaces partenaires
	$(MAKE) -C apps/web/counter a11y
	$(MAKE) -C apps/web/member a11y
	$(MAKE) -C apps/web/partner a11y

perf: ## Budgets de performance (LCP, CLS, JavaScript, polices) : comptoir, espace adhérent, espaces partenaires
	cd apps/web/counter && node_modules/.bin/playwright test e2e/perf.spec.ts
	$(MAKE) -C apps/web/member perf
	$(MAKE) -C apps/web/partner perf

egress: ## Test réseau : aucune requête hors liste blanche (garde de suite + app factory)
	$(UV) run pytest apps/api/integrations apps/api/ledger/tests/test_egress_suite.py apps/api/core/tests/test_egress_app.py -q
