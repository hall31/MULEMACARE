# Audit Trail Specification — AgentProposal Traceability

## Overview

Complete immutable audit trail for tracking every lifecycle event of an `AgentProposal`. All status changes, decisions, and execution are logged with timestamps, actor information, and contextual metadata.

## Model

### `AuditLog` (ORM Model)

Located: `api/app/domain/models.py`

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    # Core
    id: str (PK)
    timestamp: datetime (server-default: now(), indexed)
    
    # Action tracking
    action: str (indexed)  # created|approved|rejected|executed
    
    # Actor tracking
    actor_id: str (indexed)  # user.id or "system"
    actor_role: str  # MEMBER|OPS|ADMIN|system
    
    # Reference
    agent_proposal_id: str (indexed, FK to AgentProposal.id)
    
    # State transition
    old_status: str | None  # previous status (null for created)
    new_status: str  # new status
    
    # Context
    reason: str | None  # decision note, error msg, etc
    metadata: dict  # JSON — agent version, prompt hash, feature flags, etc
```

## Lifecycle Events

### 1. Created
- **Action**: `created`
- **Trigger**: `POST /api/v1/action-center/proposals`
- **Actor**: User/Agent (non-system)
- **Status Change**: `None` → `pending`
- **Metadata**: `agent_name`, `action_type`

Example:
```json
{
  "action": "created",
  "actor_id": "agent-auto-approver-1",
  "actor_role": "ADMIN",
  "old_status": null,
  "new_status": "pending",
  "reason": "Proposal created by agent or user",
  "metadata": {
    "agent_name": "AutoApprover",
    "action_type": "claim_approve"
  }
}
```

### 2. Approved
- **Action**: `approved`
- **Trigger**: `POST /api/v1/action-center/proposals/{id}/decide` with `decision: "approved"`
- **Actor**: OPS/ADMIN user
- **Status Change**: `pending` → `approved`
- **Metadata**: Optional (decision context)

Example:
```json
{
  "action": "approved",
  "actor_id": "ops-user-123",
  "actor_role": "OPS",
  "old_status": "pending",
  "new_status": "approved",
  "reason": "Claim verified, no discrepancies found"
}
```

### 3. Rejected
- **Action**: `rejected`
- **Trigger**: `POST /api/v1/action-center/proposals/{id}/decide` with `decision: "rejected"`
- **Actor**: OPS/ADMIN user
- **Status Change**: `pending` → `rejected`
- **Metadata**: (terminal state — no further action)

Example:
```json
{
  "action": "rejected",
  "actor_id": "ops-user-456",
  "actor_role": "ADMIN",
  "old_status": "pending",
  "new_status": "rejected",
  "reason": "Claim amount exceeds annual limit"
}
```

### 4. Executed
- **Action**: `executed`
- **Trigger**: Automatic after `approved` if execution succeeds
- **Actor**: `system`
- **Status Change**: `approved` → `executed`
- **Metadata**: Execution details (e.g., member status updated, claim forwarded)

Example:
```json
{
  "action": "executed",
  "actor_id": "system",
  "actor_role": "system",
  "old_status": "approved",
  "new_status": "executed",
  "reason": "Proposal executed successfully",
  "metadata": {
    "execution_type": "status_toggle",
    "member_cssa_id": "MC-12345678"
  }
}
```

## API Endpoints

### Get Audit Trail
```
GET /api/v1/action-center/proposals/{proposal_id}/audit-trail
```

**Auth**: `OPS`, `ADMIN`, `MEMBER`

**Response**:
```json
{
  "proposal_id": "uuid-123",
  "audit_trail": [
    {
      "id": "audit-log-1",
      "timestamp": "2026-08-30T14:23:45.123Z",
      "action": "created",
      "actor_id": "agent-123",
      "actor_role": "ADMIN",
      "agent_proposal_id": "uuid-123",
      "old_status": null,
      "new_status": "pending",
      "reason": "Proposal created by agent or user",
      "metadata": {"agent_name": "AutoApprover"}
    },
    {
      "id": "audit-log-2",
      "timestamp": "2026-08-30T14:25:10.456Z",
      "action": "approved",
      "actor_id": "user-ops-456",
      "actor_role": "OPS",
      "agent_proposal_id": "uuid-123",
      "old_status": "pending",
      "new_status": "approved",
      "reason": "Claim looks good",
      "metadata": {}
    },
    {
      "id": "audit-log-3",
      "timestamp": "2026-08-30T14:25:11.789Z",
      "action": "executed",
      "actor_id": "system",
      "actor_role": "system",
      "agent_proposal_id": "uuid-123",
      "old_status": "approved",
      "new_status": "executed",
      "reason": "Proposal executed successfully",
      "metadata": {}
    }
  ]
}
```

## Repository Layer

Located: `api/app/repositories/audit.py`

```python
class AuditRepository:
    async def log(...) -> AuditLog
    async def get_trail(agent_proposal_id: str) -> list[AuditLog]
    async def get_by_id(log_id: str) -> AuditLog | None
```

## Immutability Guarantees

### Application Level
- Repository implements insert-only (`log()` method)
- No update or delete methods provided
- All state transitions captured at creation time

### Database Level (Recommended — Alembic Migration)
```sql
-- Prevent direct updates
ALTER TABLE audit_logs ADD CONSTRAINT audit_logs_no_updates
  CHECK (1=0) NOT VALID;

-- Prevent deletes (via trigger or application-level constraint)
-- PostgreSQL: CREATE TRIGGER audit_logs_protect_delete ...
```

Note: Current implementation relies on application-level discipline. Consider adding database constraints for defense-in-depth.

## Integration Points

### Action Center (`api/app/api/action_center.py`)

1. **Create Proposal** → Log `created` event
   ```python
   audit_repo.log(
       action="created",
       actor_id=user.sub,
       actor_role=user.role,
       ...
   )
   ```

2. **Decide Proposal** → Log `approved` or `rejected` event
   ```python
   audit_repo.log(
       action=body.decision,
       actor_id=user.sub,
       ...
   )
   ```

3. **Execute Approved** → Log `executed` event
   ```python
   audit_repo.log(
       action="executed",
       actor_id="system",
       ...
   )
   ```

## Testing

### E2E Tests
Located: `api/tests/test_audit_trail.py`

- `test_audit_trail_lifecycle()` — Create → Approve → Execute, verify logs
- `test_audit_trail_rejection()` — Create → Reject, verify logs
- `test_audit_trail_immutability()` — Verify insert-only pattern
- `test_audit_trail_metadata()` — Verify metadata capture

### Run Tests
```bash
cd api
pytest tests/test_audit_trail.py -v
```

## Migration (Optional)

### SQLAlchemy Auto-Create
- Tables are created automatically on app startup via `init_db()`
- No explicit Alembic migration needed for basic functionality

### Future: Alembic Setup
If versioned migrations are needed:
```bash
cd api
alembic init alembic
alembic revision --autogenerate -m "Add audit_logs table"
alembic upgrade head
```

## Contract Guarantees

1. ✅ All status changes are traceable
   - Every proposal lifecycle event is logged
   - Timestamps are server-side (UTC)

2. ✅ Human accountability
   - Every decision captured with actor ID and role
   - Decision notes stored for audit purposes

3. ✅ Immutable record
   - Logs are insert-only at application level
   - No updates or deletions allowed
   - Chronological ordering enforced

4. ✅ Rich context
   - Metadata captures agent versions, prompt hashes, etc.
   - Old/new status captured for every transition
   - Reasons/notes preserved for decisions

## Performance Considerations

- `audit_logs.timestamp` indexed for range queries
- `audit_logs.action` indexed for filtering by event type
- `audit_logs.actor_id` indexed for user accountability reports
- `audit_logs.agent_proposal_id` indexed for per-proposal trails (PRIMARY USE)

## Compliance & Governance

- **GDPR**: Actor IDs could be PII — ensure data retention policies are in place
- **Audit**: Can generate compliance reports by filtering on `action` and `timestamp` ranges
- **Forensics**: Full proposal lifecycle reconstructable from audit trail

## Future Enhancements

- [ ] Webhooks on audit events (e.g., notify compliance officer on rejection)
- [ ] Audit dashboard with filtering by action, actor, date range
- [ ] Export audit trail as PDF or CSV for regulatory reports
- [ ] Digital signatures on sensitive actions (approved/rejected)
- [ ] Archive old audit logs to cold storage (S3) after retention period
