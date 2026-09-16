"""Persist the active executive escalation recipient on each workflow."""
from sqlalchemy import inspect, text

VERSION = "0061_workflow_executive_escalation_route"


def upgrade(engine):
    inspector = inspect(engine)
    if not inspector.has_table("workflow_instances"):
        return
    columns = {column["name"] for column in inspector.get_columns("workflow_instances")}
    with engine.begin() as conn:
        if "escalation_to_office_n" not in columns:
            conn.execute(text("ALTER TABLE workflow_instances ADD COLUMN escalation_to_office_n INTEGER"))
        if "escalation_from_office_n" not in columns:
            conn.execute(text("ALTER TABLE workflow_instances ADD COLUMN escalation_from_office_n INTEGER"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_workflow_instances_escalation_to ON workflow_instances (escalation_to_office_n)"))


def downgrade(engine):
    return None
