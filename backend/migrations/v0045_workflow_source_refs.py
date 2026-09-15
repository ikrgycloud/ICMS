"""Add source-domain references for generic workflow handoffs."""
from sqlalchemy import inspect, text

VERSION = "0045_workflow_source_refs"


def upgrade(engine):
    inspector = inspect(engine)
    if not inspector.has_table("workflow_instances"):
        return
    columns = {column["name"] for column in inspector.get_columns("workflow_instances")}
    with engine.begin() as conn:
        if "source_type" not in columns:
            conn.execute(text("ALTER TABLE workflow_instances ADD COLUMN source_type VARCHAR DEFAULT ''"))
        if "source_id" not in columns:
            conn.execute(text("ALTER TABLE workflow_instances ADD COLUMN source_id VARCHAR DEFAULT ''"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_workflow_instances_source_type ON workflow_instances (source_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_workflow_instances_source_id ON workflow_instances (source_id)"))


def downgrade(engine):
    return None