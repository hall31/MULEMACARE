# HealthOS Partner Bridge

MulemaCare connects to HealthOS for member eligibility verification and pre-authorization requests. The bridge is **disabled by default** and only available to pilot tenants.

## Architecture

```
MulemaCare API
    ↓
HealthOSClient (async HTTP)
    ├─ Signature: HMAC-SHA256
    │  Formula: timestamp | nonce | method | path | sha256(body)
    │  Signed with: HEALTHOS_PARTNER_API_KEY
    │
    ├─ Nonce anti-replay
    │  Storage: Redis (5-minute cache)
    │  Purpose: Prevent replay attacks
    │
    ├─ Retry logic
    │  Strategy: Exponential backoff (3 attempts)
    │  Backoff: 0.5s, 1s, 2s
    │
    └─ Graceful fallback
       On timeout/error: return error hint + eligible=null
       → Operator can proceed manually via ActionCenter HITL
       ↓
HealthOS API
```

## Configuration

All settings are environment variables:

```bash
# Enable the bridge (default: false)
MULEMACARE_HEALTHOS_BRIDGE_ENABLED=true

# HealthOS partner API (required if enabled)
HEALTHOS_BASE_URL=https://api.healthos.com
HEALTHOS_PARTNER_API_KEY=your-secret-key-here

# Timeouts and limits
HEALTHOS_TIMEOUT_MS=5000          # Default 5 seconds
HEALTHOS_PILOT_TENANT=mulemacare  # Only this tenant can call bridge

# Redis for nonce cache (required)
REDIS_URL=redis://localhost:6379/0
```

### Production Requirements

1. **HEALTHOS_PARTNER_API_KEY** must be 32+ characters
2. **Redis** must be configured and running
3. **TLS** required for HEALTHOS_BASE_URL
4. Network isolation: HealthOS API calls should be from private networks

## API Endpoints

### GET /api/v1/healthos/status

Returns bridge status and configuration (OPS/ADMIN only).

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8088/api/v1/healthos/status
```

**Response:**
```json
{
  "enabled": true,
  "mode": "read_eligibility_then_preauth_hitl",
  "pilot_tenant": "mulemacare",
  "base_url": "https://api.healthos.com",
  "timeout_ms": 5000
}
```

### POST /api/v1/healthos/eligibility

Fetch member eligibility from HealthOS (read-only). Pilot tenant only.

**Request:**
```json
{
  "cssa_id": "CSSA-001-2025",
  "healthos_patient_id": "pat-abc123"
}
```

**Response (success):**
```json
{
  "patient_id": "pat-abc123",
  "eligible": true,
  "coverage_start": "2024-01-01",
  "coverage_end": "2025-01-01",
  "plan_name": "Gold"
}
```

**Response (not found):**
```json
{
  "patient_id": "pat-unknown",
  "eligible": false,
  "error": "Patient not found in HealthOS"
}
```

**Response (timeout/fallback):**
```json
{
  "patient_id": "pat-xyz",
  "eligible": null,
  "error": "HealthOS service timeout — fallback to manual review"
}
```

### POST /api/v1/healthos/preauth-intent

Create a pre-authorization intent on HealthOS. Status is always **PENDING_REVIEW** — never auto-approved.

**Request:**
```json
{
  "cssa_id": "CSSA-001-2025",
  "healthos_patient_id": "pat-abc123",
  "reason": "Emergency surgery"
}
```

**Response (success):**
```json
{
  "ok": true,
  "proposal_id": "prop-healthos-123",
  "status": "PENDING_REVIEW"
}
```

**Response (fallback):**
```json
{
  "ok": false,
  "status": "PENDING_REVIEW",
  "error": "HealthOS service unavailable — fallback to manual creation"
}
```

## Security Contracts

### 1. Read-Only Eligibility

- Eligibility checks **never modify** HealthOS data
- No side effects on MulemaCare side
- Safe to retry without idempotency concerns

### 2. Pre-Authorization Never Auto-Approved

- Status always starts as **PENDING_REVIEW**
- Human (ActionCenter) must decide
- Bridge creates proposal on both HealthOS and MulemaCare
- Operator reviews both systems

### 3. Nonce Anti-Replay (5-minute window)

- Each request has a unique nonce
- Redis tracks used nonces for 5 minutes
- Prevents duplicate processing if request retries
- Nonce format: 32-character hex string

### 4. HMAC-SHA256 Signature

- Signed by HEALTHOS_PARTNER_API_KEY
- Formula: `timestamp|nonce|method|path|sha256(body)`
- Verified by HealthOS to authenticate MulemaCare
- Timeout: 5 minutes (timestamp skew tolerance)

### 5. Tenant Isolation

- Only `HEALTHOS_PILOT_TENANT` (default: `mulemacare`) can call bridge
- Other tenants get HTTP 403 Forbidden
- Prevents data leakage between Mutuelle instances

## Retry Strategy

Exponential backoff for transient failures:

| Attempt | Backoff | Total Time |
|---------|---------|-----------|
| 1       | —       | 0s        |
| 2       | 0.5s    | 0.5s      |
| 3       | 1.0s    | 1.5s      |
| 4 (fail)| —       | 1.5s      |

Retried errors:
- **EAGAIN** / **Network timeout**
- **Temporary HTTP 5xx** (e.g., 503 Service Unavailable)

Not retried:
- **HTTP 401** (bad auth)
- **HTTP 403** (permission denied)
- **HTTP 404** (not found)

## Graceful Degradation

When HealthOS is unavailable:

1. **Eligibility check** returns `eligible: null` with error message
2. **Preauth intent** returns `ok: false` but still posts to ActionCenter
3. Operator can proceed manually via UI
4. No blocking of operations

## Testing

### Local Development

```bash
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Enable bridge in .env
echo "MULEMACARE_HEALTHOS_BRIDGE_ENABLED=true" >> .env
echo "HEALTHOS_BASE_URL=https://api.healthos.test" >> .env
echo "HEALTHOS_PARTNER_API_KEY=test-secret-key-32-chars" >> .env
echo "REDIS_URL=redis://localhost:6379/0" >> .env

# Run tests
pytest api/tests/test_healthos_bridge.py -v

# Start server
make dev
```

### Mocking HealthOS (Unit Tests)

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_eligibility_success():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "eligible": True,
        "plan_name": "Gold",
    }

    with patch("httpx.AsyncClient.request", return_value=mock_response):
        client = HealthOSClient()
        result = await client.get_eligibility("pat-123")
        assert result["eligible"] is True
```

### Sandbox HealthOS

For testing without real HealthOS:

1. Deploy mock HealthOS service locally
2. Point HEALTHOS_BASE_URL to mock
3. Mock returns realistic eligibility responses
4. Test retry + fallback paths

Example mock service (FastAPI):
```python
from fastapi import FastAPI, Header
import hmac, hashlib

app = FastAPI()

@app.post("/api/v1/partner/preauth-intent")
async def mock_preauth(
    x_signature: str = Header(...),
    body: dict = None,
):
    # Verify signature, return 201 with proposal_id
    return {
        "proposal_id": "mock-prop-123",
        "status": "pending_review",
    }
```

## Deployment Checklist

- [ ] Redis service running and healthy
- [ ] HEALTHOS_PARTNER_API_KEY in secrets (not in git)
- [ ] HEALTHOS_BASE_URL points to production
- [ ] TLS certificate pinning configured (optional but recommended)
- [ ] Nonce cache retention set to 300 seconds
- [ ] Timeout set to 5000ms or higher
- [ ] Only pilot tenant can access bridge
- [ ] Audit logs enabled for all bridge calls
- [ ] ActionCenter HITL trained on preauth review flow
- [ ] Fallback procedures documented

## Troubleshooting

### Bridge returns 503 Disabled

```
Error: HealthOS bridge disabled
```

Check:
1. `MULEMACARE_HEALTHOS_BRIDGE_ENABLED=true`
2. `HEALTHOS_BASE_URL` and `HEALTHOS_PARTNER_API_KEY` configured

### Signature validation fails

```
Error: X-Signature validation failed
```

Check:
1. `HEALTHOS_PARTNER_API_KEY` matches HealthOS configuration
2. System clock is in sync (< 5 minutes skew)
3. Request body is exactly as HealthOS expects

### Nonce replay error

```
Error: Nonce has already been used
```

Check:
1. Redis is running and accessible
2. `REDIS_URL` is correct
3. Request is not being sent twice by upstream

### Timeout errors

```
Error: HealthOS service timeout
```

Check:
1. Network connectivity to HealthOS
2. `HEALTHOS_TIMEOUT_MS` is sufficient (5000+ recommended)
3. HealthOS service is healthy

## References

- **HealthOS API Docs**: https://docs.healthos.com/partner-api
- **Nonce Anti-Replay**: RFC 8305
- **HMAC-SHA256**: RFC 2104, FIPS 180-4
- **ActionCenter HITL**: docs/ACTION_CENTER.md
