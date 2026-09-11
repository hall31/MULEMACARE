#!/bin/bash
# Audit Trail Verification Checklist

echo "=== MulemaCare Audit Trail Verification ==="
echo

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# 1. Check files exist
echo "Checking files..."
FILES=(
    "api/app/domain/models.py"
    "api/app/repositories/audit.py"
    "api/app/api/action_center.py"
    "api/tests/test_audit_trail.py"
    "docs/AUDIT_README.md"
    "docs/AUDIT_TRAIL_SPEC.md"
    "docs/AUDIT_IMPLEMENTATION.md"
    "docs/AUDIT_ALEMBIC_MIGRATION.md"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${RED}✗${NC} $file"
        ERRORS=$((ERRORS + 1))
    fi
done
echo

# 2. Check AuditLog model exists
echo "Checking AuditLog model..."
if grep -q "class AuditLog" api/app/domain/models.py; then
    echo -e "${GREEN}✓${NC} AuditLog class found"
else
    echo -e "${RED}✗${NC} AuditLog class NOT found"
    ERRORS=$((ERRORS + 1))
fi
echo

# 3. Check AuditRepository exists
echo "Checking AuditRepository..."
if grep -q "class AuditRepository" api/app/repositories/audit.py; then
    echo -e "${GREEN}✓${NC} AuditRepository class found"
else
    echo -e "${RED}✗${NC} AuditRepository class NOT found"
    ERRORS=$((ERRORS + 1))
fi

if grep -q "async def log" api/app/repositories/audit.py; then
    echo -e "${GREEN}✓${NC} log() method found"
else
    echo -e "${RED}✗${NC} log() method NOT found"
    ERRORS=$((ERRORS + 1))
fi

if grep -q "async def get_trail" api/app/repositories/audit.py; then
    echo -e "${GREEN}✓${NC} get_trail() method found"
else
    echo -e "${RED}✗${NC} get_trail() method NOT found"
    ERRORS=$((ERRORS + 1))
fi
echo

# 4. Check action_center.py integration
echo "Checking action_center.py integration..."
if grep -q "from app.repositories.audit import AuditRepository" api/app/api/action_center.py; then
    echo -e "${GREEN}✓${NC} AuditRepository imported"
else
    echo -e "${RED}✗${NC} AuditRepository NOT imported"
    ERRORS=$((ERRORS + 1))
fi

if grep -q "audit_repo.log" api/app/api/action_center.py; then
    echo -e "${GREEN}✓${NC} audit_repo.log() called"
else
    echo -e "${RED}✗${NC} audit_repo.log() NOT called"
    ERRORS=$((ERRORS + 1))
fi

if grep -q "get_audit_trail" api/app/api/action_center.py; then
    echo -e "${GREEN}✓${NC} get_audit_trail() endpoint found"
else
    echo -e "${RED}✗${NC} get_audit_trail() endpoint NOT found"
    ERRORS=$((ERRORS + 1))
fi
echo

# 5. Check test file
echo "Checking test file..."
if grep -q "def test_audit_trail_lifecycle" api/tests/test_audit_trail.py; then
    echo -e "${GREEN}✓${NC} test_audit_trail_lifecycle found"
else
    echo -e "${RED}✗${NC} test_audit_trail_lifecycle NOT found"
    ERRORS=$((ERRORS + 1))
fi

if grep -q "def test_audit_trail_rejection" api/tests/test_audit_trail.py; then
    echo -e "${GREEN}✓${NC} test_audit_trail_rejection found"
else
    echo -e "${RED}✗${NC} test_audit_trail_rejection NOT found"
    ERRORS=$((ERRORS + 1))
fi
echo

# 6. Summary
echo "=== Verification Summary ==="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo
    echo "Next steps:"
    echo "1. Run tests: pytest api/tests/test_audit_trail.py -v"
    echo "2. Review docs: docs/AUDIT_README.md"
    echo "3. Deploy code"
    echo "4. Verify endpoint: GET /api/v1/action-center/proposals/{id}/audit-trail"
    exit 0
else
    echo -e "${RED}✗ $ERRORS checks failed${NC}"
    exit 1
fi
