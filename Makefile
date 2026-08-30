.PHONY: qa-mulemacare qa-php qa-api test-healthos-bridge dev-healthos

qa-php:
	php site/tests/test_stripe_webhook_activation.php
	php site/tests/test_api_webhook_controller.php
	php site/tests/test_auth_espaces.php
	php site/tests/test_nss_identity.php
	php site/tests/test_hub_api.php
	php -l site/app/Services/StripePaymentService.php
	php -l site/app/Services/MembershipService.php
	php -l site/app/Services/NssService.php
	php -l site/app/Services/MutuelleOsClient.php
	php -l site/app/Services/AuthService.php
	php -l site/app/Services/SessionService.php
	php -l site/app/Services/TotpService.php
	php -l site/app/Controllers/ApiController.php
	php -l site/app/Controllers/AuthController.php
	php -l site/app/Controllers/HubApiController.php
	php -l site/app/Controllers/HomeController.php

qa-api:
	cd api && . .venv/bin/activate && PYTHONPATH=. pytest -q

test-healthos-bridge:
	cd api && . .venv/bin/activate && PYTHONPATH=. pytest tests/test_healthos_bridge.py -v

dev-healthos:
	@echo "Starting MulemaCare with HealthOS bridge..."
	@echo "HealthOS bridge endpoints will be available at:"
	@echo "  GET  http://localhost:8088/api/v1/healthos/status"
	@echo "  POST http://localhost:8088/api/v1/healthos/eligibility"
	@echo "  POST http://localhost:8088/api/v1/healthos/preauth-intent"
	@echo ""
	@echo "Configure .env with:"
	@echo "  MULEMACARE_HEALTHOS_BRIDGE_ENABLED=true"
	@echo "  HEALTHOS_BASE_URL=https://api.healthos.com"
	@echo "  HEALTHOS_PARTNER_API_KEY=your-key-here"
	docker-compose up

qa-mulemacare: qa-php qa-api
	@echo "QA MulemaCare GREEN"
