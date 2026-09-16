"""Canonical campus ownership for asset, placement, and risk-action records."""
from sqlalchemy import inspect, text

VERSION = "0060_campus_performance_scope"


def upgrade(engine):
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in ("assets", "placement_drives"):
            if not inspector.has_table(table):
                continue
            columns = {column["name"] for column in inspector.get_columns(table)}
            if "campus_scope_id" not in columns:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN campus_scope_id VARCHAR"))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_campus_scope_id ON {table} (campus_scope_id)"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS risk_corrective_actions (
                id VARCHAR(64) PRIMARY KEY, tenant_id VARCHAR(64) NOT NULL,
                risk_id VARCHAR(64) NOT NULL, owner_id VARCHAR(128), description TEXT NOT NULL,
                due_at TIMESTAMP, status VARCHAR(40) DEFAULT 'OPEN', completion_note TEXT DEFAULT '',
                completed_at TIMESTAMP, verified_at TIMESTAMP, verified_by VARCHAR(128),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_risk_corrective_actions_risk_id ON risk_corrective_actions (risk_id)"))
