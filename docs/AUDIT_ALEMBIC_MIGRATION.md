# Alembic Migration Guide (Optional)

## Current Approach (Recommended)

MulemaCare uses SQLAlchemy's `init_db()` for automatic table creation on app startup. **No Alembic migration is required** for basic functionality.

```python
# app/core/db.py
async def init_db() -> None:
    from app.domain import models  # Imports all models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # ← Creates audit_logs table
```

## When to Use Alembic

Use Alembic if you need:
- Version-controlled database schema changes
- Zero-downtime deployments
- Rollback capability
- Team collaboration on schema changes
- Production change tracking

## Setup Alembic (Optional)

If you want versioned migrations:

### 1. Install Alembic
```bash
cd api
pip install alembic
```

### 2. Initialize Alembic
```bash
alembic init alembic
```

This creates:
```
alembic/
├── env.py                 (SQLAlchemy config)
├── script.py.template     (revision template)
└── versions/              (migration files)
```

### 3. Configure `alembic/env.py`

Replace the database connection setup:

```python
# alembic/env.py
from sqlalchemy import engine_from_config, pool
from logging.config import fileConfig
from alembic import context
from app.core.db import Base
from app.core.config import get_settings

# ... existing setup ...

config = context.config
settings = get_settings()

# Set SQL Alchemy URL
config.set_main_option("sqlalchemy.url", settings.database_url)

# ... existing fileConfig ...

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()

# ... rest of file unchanged ...
```

### 4. Create Initial Migration

```bash
cd api
alembic revision --autogenerate -m "Initial schema with audit_logs table"
```

This generates a migration file in `alembic/versions/` that includes the `audit_logs` table creation.

### 5. Review Generated Migration

```bash
# Review the generated migration file
cat alembic/versions/001_*.py
```

Example output:
```python
def upgrade() -> None:
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(64), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('action', sa.String(32), nullable=False),
        sa.Column('actor_id', sa.String(64), nullable=False),
        sa.Column('actor_role', sa.String(32), nullable=True),
        sa.Column('agent_proposal_id', sa.String(64), nullable=False),
        sa.Column('old_status', sa.String(32), nullable=True),
        sa.Column('new_status', sa.String(32), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_logs_agent_proposal_id'), 'audit_logs', ['agent_proposal_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_id'), 'audit_logs', ['actor_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_audit_logs_timestamp'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_actor_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_agent_proposal_id'), table_name='audit_logs')
    op.drop_table('audit_logs')
```

### 6. Apply Migration

```bash
# Apply all pending migrations
alembic upgrade head

# Verify
alembic current  # Shows current migration version
```

### 7. Integrate with App Startup

Modify `app/main.py` to run migrations on startup (optional):

```python
# app/main.py
@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Option A: Use SQLAlchemy auto-create (current approach)
    await init_db()
    
    # Option B: Use Alembic migrations (alternative)
    # from alembic.config import Config
    # from alembic.runtime.migration import MigrationContext
    # from alembic.operations import Operations
    # from sqlalchemy import text
    # 
    # config = Config("alembic.ini")
    # async with engine.begin() as conn:
    #     await conn.run_sync(
    #         lambda conn: MigrationContext.configure(conn).run_migrations()
    #     )
    
    yield
```

## Deployment with Alembic

### Development
```bash
# After schema changes
alembic revision --autogenerate -m "Descriptive message"
alembic upgrade head
```

### Production (CI/CD)
```bash
# Before deploying new code
alembic upgrade head

# Then deploy app
docker-compose up -d api
```

## Best Practices

1. **Always review auto-generated migrations**
   - Alembic can miss custom logic
   - Verify the SQL is correct before applying

2. **Test migrations locally first**
   - Run against test database
   - Verify up and down migrations work

3. **One migration per feature**
   - Don't combine multiple changes
   - Makes rollback cleaner

4. **Name migrations descriptively**
   - "001_add_audit_logs_table"
   - "002_add_audit_logs_indexes"

5. **Keep migrations small**
   - Don't mix schema and data changes
   - Don't mix multiple tables in one migration

## Downside of Alembic

- **Extra complexity**: Requires version files in git
- **Synchronization**: Must keep models.py and migrations in sync
- **Overkill for small projects**: MulemaCare currently doesn't need it

## Recommendation

**For MulemaCare**: Continue with SQLAlchemy `init_db()` until you need:
- Team collaboration on schema changes
- Production rollback capability
- Change audit trails (ironic!)

At that point, adopt Alembic using the setup above.

## Immutability Constraint (Alembic)

If using Alembic, add database-level immutability constraint:

```python
# alembic/versions/002_add_audit_logs_immutability.py
def upgrade() -> None:
    # PostgreSQL: Prevent updates
    op.execute("""
        CREATE TRIGGER audit_logs_no_update
        BEFORE UPDATE ON audit_logs
        FOR EACH ROW
        EXECUTE PROCEDURE raise_immutable_error();
        
        CREATE FUNCTION raise_immutable_error() RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Audit logs are immutable';
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Or constraint-based approach
    op.execute("""
        ALTER TABLE audit_logs ADD CONSTRAINT audit_logs_read_only
        CHECK (FALSE);
    """)

def downgrade() -> None:
    op.execute("DROP TRIGGER audit_logs_no_update ON audit_logs;")
    op.execute("DROP FUNCTION raise_immutable_error();")
    op.execute("ALTER TABLE audit_logs DROP CONSTRAINT audit_logs_read_only;")
```

**Note**: The current implementation enforces immutability at the application layer (no update/delete methods in repository). Database constraints are optional but recommended for defense-in-depth.
