# HealthOS Bridge Quick Start

## 1. Enable the Bridge (Development)

Copy the example config:

```bash
cp api/.env.example.healthos .env.local
```

Edit `.env.local` and set:

```bash
MULEMACARE_HEALTHOS_BRIDGE_ENABLED=true
HEALTHOS_BASE_URL=https://sandbox.healthos.com  # or your test env
HEALTHOS_PARTNER_API_KEY=your-32-char-secret-key
REDIS_URL=redis://localhost:6379/0
```

## 2. Start Redis

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

Or use Docker Compose:

```bash
docker-compose up -d mulemacare-redis
```

## 3. Start the API

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run with the config
export $(cat .env.local | xargs)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

## 4. Test the Bridge

### Check bridge status:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/healthos/status
```

Response:
```json
{
  "enabled": true,
  "mode": "read_eligibility_then_preauth_hitl",
  "pilot_tenant": "mulemacare",
  "base_url": "https://sandbox.healthos.com",
  "timeout_ms": 5000
}
```

### Fetch eligibility:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cssa_id": "CSSA-001-2025",
    "healthos_patient_id": "pat-abc123"
  }' \
  http://localhost:8080/api/v1/healthos/eligibility
```

Response (if eligible):
```json
{
  "patient_id": "pat-abc123",
  "eligible": true,
  "coverage_start": "2024-01-01",
  "coverage_end": "2025-01-01",
  "plan_name": "Gold"
}
```

Response (if fallback to error):
```json
{
  "patient_id": "pat-abc123",
  "eligible": null,
  "error": "HealthOS service timeout — fallback to manual review"
}
```

### Create preauth intent:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cssa_id": "CSSA-001-2025",
    "healthos_patient_id": "pat-abc123",
    "reason": "Emergency surgery"
  }' \
  http://localhost:8080/api/v1/healthos/preauth-intent
```

Response:
```json
{
  "ok": true,
  "proposal_id": "prop-healthos-123",
  "status": "PENDING_REVIEW"
}
```

## 5. Run Tests

```bash
cd api
. .venv/bin/activate

# All tests
pytest -v

# HealthOS bridge tests only
pytest tests/test_healthos_bridge.py -v

# With coverage
pytest tests/test_healthos_bridge.py --cov=app.services.healthos_client --cov-report=term-missing
```

## 6. Production Deployment

### Requirements

1. **Redis** must be running and accessible
2. **HEALTHOS_PARTNER_API_KEY** must be in secrets (use AWS Secrets Manager, Vault, etc.)
3. **HEALTHOS_BASE_URL** must use TLS (https)
4. Network: API server must have outbound access to HealthOS API

### Secrets Management

**Never commit secrets to git.** Use environment management:

```bash
# AWS Secrets Manager
aws secretsmanager get-secret-value --secret-id mulemacare/healthos-api-key \
  --query SecretString --output text

# Vault
vault kv get secret/mulemacare/healthos

# Environment variables (Docker/Kubernetes)
export HEALTHOS_PARTNER_API_KEY=$(kubectl get secret mulemacare-secrets -o jsonpath='{.data.healthos-api-key}' | base64 -d)
```

### Docker Compose Production

```bash
docker-compose -f docker-compose.yml up -d
```

The `docker-compose.yml` includes:
- Redis service with persistence
- MulemaCare API with health checks
- Environment variable injection for secrets

### Verify Deployment

```bash
# Check Redis is healthy
docker-compose exec mulemacare-redis redis-cli ping
# Expected: PONG

# Check API is healthy
curl http://localhost:8088/health
# Expected: 200 OK

# Check bridge is enabled
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8088/api/v1/healthos/status
```

## Troubleshooting

### "HealthOS bridge disabled"

The bridge is not enabled. Check `.env` file:

```bash
MULEMACARE_HEALTHOS_BRIDGE_ENABLED=true
```

### "HealthOS not configured"

Missing base URL or API key. Check:

```bash
echo $HEALTHOS_BASE_URL
echo $HEALTHOS_PARTNER_API_KEY | head -c 5...  # Don't print full key
```

### "Nonce has already been used"

Nonce anti-replay protection triggered. This is **expected** if:
- Request was sent twice by accident
- Redis contains old nonce

To clear (development only):

```bash
redis-cli FLUSHDB
```

### "HealthOS service timeout"

The bridge timed out waiting for HealthOS. Check:

```bash
# 1. Network connectivity
curl -I https://api.healthos.com

# 2. Increase timeout if needed
HEALTHOS_TIMEOUT_MS=10000
```

### Signature validation failed

The HMAC signature is wrong. Check:

```bash
# 1. API key matches HealthOS config
echo $HEALTHOS_PARTNER_API_KEY

# 2. System time is in sync (within 5 minutes)
date
ntpdate -q pool.ntp.org
```

## Next Steps

1. **Map CSSA ↔ HealthOS patient IDs**: Create a lookup table
2. **Train operators**: Show how to handle PENDING_REVIEW preauths
3. **Monitor bridge**: Set up alerts for timeout/error rates
4. **Document fallback**: What happens if HealthOS is down?

See also:
- [HEALTHOS_BRIDGE.md](HEALTHOS_BRIDGE.md) — Full documentation
- [ACTION_CENTER.md](ACTION_CENTER.md) — HITL review process
