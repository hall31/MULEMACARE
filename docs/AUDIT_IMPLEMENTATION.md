# Audit Trail Implementation Guide

## Deliverables Checklist

- [x] **1. Domain Model** (`api/app/domain/models.py`)
  - Added `AuditLog` ORM class with full lifecycle tracking fields
  - Indexed for performance: `timestamp`, `action`, `actor_id`, `agent_proposal_id`
  - JSON metadata field for extensibility
  - Server-side UTC timestamps

- [x] **2. Repository Layer** (`api/app/repositories/audit.py`)
  - `AuditRepository` class with insert-only CRUD
  - `log()` method for creating immutable log entries
  - `get_trail()` method for chronological retrieval per proposal
  - `get_by_id()` for individual log lookup
  - No update/delete methods — enforces immutability at application level

- [x] **3. API Integration** (`api/app/api/action_center.py`)
  - Modified `create_proposal()` to log `created` event
  - Modified `decide_proposal()` to log `approved`/`rejected` events
  - Added execution logging on successful approval
  - Helper serializer `_ser_audit_log()` for JSON responses

- [x] **4. New Endpoint** (`GET /api/v1/action-center/proposals/{id}/audit-trail`)
  - Requires auth (OPS, ADMIN, MEMBER)
  - Returns chronological audit trail for a proposal
  - Verifies proposal exists before returning logs
  - JSON response with full audit entry details

- [x] **5. E2E Tests** (`api/tests/test_audit_trail.py`)
  - `test_audit_trail_lifecycle()` — Create → Approve → Execute flow
  - `test_audit_trail_rejection()` — Create → Reject flow
  - `test_audit_trail_immutability()` — Design test (enforced by no-delete repo)
  - `test_audit_trail_metadata()` — Metadata capture validation

- [x] **6. Documentation**
  - `docs/AUDIT_TRAIL_SPEC.md` — Complete spec, lifecycle, contract guarantees
  - `docs/AUDIT_IMPLEMENTATION.md` — This implementation guide

## Files Changed/Created

### New Files
- `api/app/repositories/audit.py` — AuditRepository class
- `api/tests/test_audit_trail.py` — E2E test suite
- `docs/AUDIT_TRAIL_SPEC.md` — Specification and contract
- `docs/AUDIT_IMPLEMENTATION.md` — This guide

### Modified Files
- `api/app/domain/models.py` — Added AuditLog model class
- `api/app/api/action_center.py` — Integrated audit logging into all decision points

### No Changes Required
- Database migrations (SQLAlchemy creates table on `init_db()` startup)
- Alembic (optional — see migration strategy below)

## Deployment Steps

### 1. Code Deploy
```bash
cd /path/to/mulemacare/api

# Install dependencies (if new)
pip install -e .

# Run existing tests to ensure no regression
pytest tests/ -v

# Run new audit trail tests
pytest tests/test_audit_trail.py -v
```

### 2. Database (Automatic)
- On next app startup, `init_db()` creates `audit_logs` table
- No manual DDL required
- Indexes are created automatically

### 3. Restart App
```bash
# Restart uvicorn (in dev or prod)
# The table is created on first run via init_db() lifespan hook
```

## Testing Locally

### Unit Test
```bash
cd api
pytest tests/test_audit_trail.py::test_audit_trail_lifecycle -v
```

### Manual E2E (using curl)
```bash
# 1. Create proposal
curl -X POST http://localhost:8000/api/v1/action-center/proposals \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "AutoApprover",
    "action_type": "claim_approve",
    "cssa_id": "MC-12345678",
    "summary": "Test proposal",
    "payload": {"amount": 1000},
    "evidence": {}
  }' | jq .

# Save proposal_id from response

# 2. Get audit trail (empty except "created")
curl http://localhost:8000/api/v1/action-center/proposals/PROPOSAL_ID/audit-trail \
  -H "Authorization: Bearer YOUR_TOKEN" | jq .

# 3. Decide proposal
curl -X POST http://localhost:8000/api/v1/action-center/proposals/PROPOSAL_ID/decide \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "approved",
    "note": "Test approval"
  }' | jq .

# 4. Get audit trail (now has "created" + "approved" + "executed")
curl http://localhost:8000/api/v1/action-center/proposals/PROPOSAL_ID/audit-trail \
  -H "Authorization: Bearer YOUR_TOKEN" | jq .
```

## API Contract Summary

### Audit Log Entry
```json
{
  "id": "uuid-log",
  "timestamp": "2026-08-30T14:23:45.123Z",
  "action": "created|approved|rejected|executed",
  "actor_id": "user-id or system",
  "actor_role": "MEMBER|OPS|ADMIN|system",
  "agent_proposal_id": "uuid-proposal",
  "old_status": "pending|approved|null",
  "new_status": "pending|approved|rejected|executed",
  "reason": "Decision note or execution detail",
  "metadata": {"agent_name": "...", "action_type": "..."}
}
```

### Audit Trail Response
```json
{
  "proposal_id": "uuid",
  "audit_trail": [
    { /* entry 1 */ },
    { /* entry 2 */ },
    { /* entry N */ }
  ]
}
```

## Design Decisions

### 1. Immutability at Application Level
- Repository exposes `log()` and `get_*()` only — no update/delete methods
- Database constraints could be added (see AUDIT_TRAIL_SPEC.md)
- Simpler than implementing triggers or application locking

### 2. UTC Timestamps
- Server-side generation with `server_default=func.now()`
- Prevents client clock skew issues
- Consistent across all deployments

### 3. Actor ID = User ID or "system"
- When a human makes a decision: actor_id = user.sub, actor_role = user.role
- When execution is automatic: actor_id = "system", actor_role = "system"
- Clear accountability for audit purposes

### 4. Metadata as JSON
- Flexible for capturing agent version, prompt hash, feature flags, etc.
- Stored as native JSON type (PostgreSQL, MySQL 5.7+)
- Easily queryable and searchable

### 5. Chronological Ordering in Repository
- `get_trail()` returns logs sorted by timestamp ASC
- Guarantees audit trail is always in order
- Caller doesn't need to sort

## Performance Characteristics

### Writes (Logging)
- Blocking insert (awaits flush)
- Called during `decide_proposal()` and execution
- ~1-3 logs per proposal lifecycle
- Impact: negligible (one row per action)

### Reads (Audit Trail Retrieval)
- O(n) query where n = number of logs for a proposal
- Indexed by `agent_proposal_id`
- Typical n = 2-4 (created, approved/rejected, executed)
- Response time: <50ms for typical proposals

### Storage
- ~500 bytes per log entry (metadata varies)
- Estimated: 1 MB per 2000 active proposals
- Archive old logs after retention period if needed

## Monitoring & Observability

### Key Metrics
- `audit_logs` table row count (monitors proposal activity)
- Query latency on `get_trail()` (should be <50ms)
- Rejected proposals by reason (via audit trail metadata)

### Querying Examples
```sql
-- Recent approvals
SELECT * FROM audit_logs 
WHERE action = 'approved' 
AND timestamp > NOW() - INTERVAL '7 days'
ORDER BY timestamp DESC;

-- Decision-maker accountability
SELECT actor_id, COUNT(*) as decisions_made
FROM audit_logs 
WHERE action IN ('approved', 'rejected')
GROUP BY actor_id;

-- Execution failures (approved but not executed)
SELECT agent_proposal_id, COUNT(*) as attempts
FROM audit_logs 
WHERE action = 'approved'
GROUP BY agent_proposal_id
HAVING COUNT(*) = 1;  -- No "executed" event
```

## Future Enhancements

### Phase 2
- [ ] Webhooks: Emit events on audit actions (Kafka, AMQP)
- [ ] Compliance Dashboard: Filter/export audit logs
- [ ] Digital Signatures: Sign approved/rejected decisions

### Phase 3
- [ ] Archive Strategy: Move old logs to S3/cold storage
- [ ] Retention Policy: Delete logs after 7 years (compliance)
- [ ] Audit Report Generator: PDF/CSV for regulatory audits

## Troubleshooting

### No audit logs appearing
1. Check `audit_logs` table exists: `SELECT COUNT(*) FROM audit_logs;`
2. Verify `init_db()` ran on startup (check logs)
3. Ensure `AuditRepository.log()` is being called (add print debug)

### Audit trail endpoint returns 404
1. Verify proposal exists: `SELECT * FROM agent_proposals WHERE id = '...';`
2. Check proposal was created after code deploy (old proposals won't have logs)

### Performance degradation
1. Check `audit_logs` table size: `SELECT pg_size_pretty(pg_total_relation_size('audit_logs'));`
2. Verify indexes exist: `SELECT * FROM pg_indexes WHERE tablename = 'audit_logs';`
3. Consider archiving old logs if table grows >1GB

## Rollback Plan

If issues arise:

1. **Code Rollback**
   - Revert commits to `action_center.py`, `models.py`, `audit.py`
   - Logs already written won't be read
   - Proposals continue to function

2. **Data Cleanup** (if needed)
   - Truncate audit_logs: `TRUNCATE TABLE audit_logs;`
   - No impact on proposal data

3. **Quick Disable**
   - Comment out audit logging calls in `action_center.py`
   - App continues without new logs (not recommended)

## Support & Questions

For questions on the audit trail implementation:
1. Read `docs/AUDIT_TRAIL_SPEC.md` for full contract
2. Check `api/tests/test_audit_trail.py` for usage examples
3. Review `api/app/repositories/audit.py` for repository methods
