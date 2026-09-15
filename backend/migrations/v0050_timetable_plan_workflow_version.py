VERSION = "v0050_timetable_plan_workflow_version"


def upgrade(engine):
    """Add an authoritative version column for timetable plan workflow decisions."""
    from sqlalchemy import inspect, text
    if "timetable_plan_workflows" not in inspect(engine).get_table_names():
        return
    with engine.begin() as conn:
        existing = {column["name"] for column in inspect(conn).get_columns("timetable_plan_workflows")}
        if "version_no" not in existing:
            conn.execute(text("ALTER TABLE timetable_plan_workflows ADD COLUMN version_no INTEGER DEFAULT 1 NOT NULL"))
        conn.execute(text("UPDATE timetable_plan_workflows SET version_no = 1 WHERE version_no IS NULL"))


def downgrade(engine):
    return None
