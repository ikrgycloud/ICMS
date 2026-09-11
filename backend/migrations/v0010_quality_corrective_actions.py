"""Academic quality review and corrective-action workflow."""
from sqlalchemy import text
VERSION = "0010_quality_corrective_actions"
def upgrade(engine):
    statements = [
        """CREATE TABLE IF NOT EXISTS academic_quality_reviews (id VARCHAR PRIMARY KEY, tenant_id VARCHAR, title VARCHAR, scope_level VARCHAR DEFAULT 'institution', scope_ref VARCHAR DEFAULT '', metric_key VARCHAR, metric_value FLOAT, threshold FLOAT, deviation TEXT DEFAULT '', root_cause TEXT DEFAULT '', state VARCHAR DEFAULT 'OPEN', owner_id VARCHAR DEFAULT '', due_at TIMESTAMP, status_version INTEGER DEFAULT 0, created_by VARCHAR DEFAULT '', verified_by VARCHAR DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS corrective_actions (id VARCHAR PRIMARY KEY, tenant_id VARCHAR, review_id VARCHAR NOT NULL, title VARCHAR, owner_id VARCHAR, deadline TIMESTAMP, evidence TEXT DEFAULT '', state VARCHAR DEFAULT 'OPEN', status_version INTEGER DEFAULT 0, created_by VARCHAR DEFAULT '', verified_by VARCHAR DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        "CREATE INDEX IF NOT EXISTS ix_quality_reviews_state ON academic_quality_reviews (state, due_at)",
        "CREATE INDEX IF NOT EXISTS ix_corrective_actions_state ON corrective_actions (state, deadline)",
    ]
    with engine.begin() as conn:
        for statement in statements: conn.execute(text(statement))
