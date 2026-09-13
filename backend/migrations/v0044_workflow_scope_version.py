"""Add explicit workflow scope and optimistic decision versioning."""
from sqlalchemy import inspect, text

VERSION = "0044_workflow_scope_version"


def upgrade(engine):
    inspector = inspect(engine)
    if not inspector.has_table("workflow_instances"):
        return
    existing = {column["name"] for column in inspector.get_columns("workflow_instances")}
    with engine.begin() as conn:
        if "scope_ref" not in existing:
            conn.execute(text("ALTER TABLE workflow_instances ADD COLUMN scope_ref VARCHAR DEFAULT ''"))
        if "version_no" not in existing:
            conn.execute(text("ALTER TABLE workflow_instances ADD COLUMN version_no INTEGER DEFAULT 1 NOT NULL"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_workflow_instances_scope_ref ON workflow_instances (scope_ref)"))
        conn.execute(text("UPDATE workflow_instances SET version_no = 1 WHERE version_no IS NULL"))


def downgrade(engine):
    return None
