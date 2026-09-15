VERSION = "0053_timetable_change_workflow_version"


def upgrade(engine):
    """Add a state-concurrency token without changing entry-version semantics."""
    from sqlalchemy import inspect, text
    if "timetable_exceptions" not in inspect(engine).get_table_names():
        return
    with engine.begin() as conn:
        columns = {column["name"] for column in inspect(conn).get_columns("timetable_exceptions")}
        if "workflow_version_no" not in columns:
            conn.execute(text("ALTER TABLE timetable_exceptions ADD COLUMN workflow_version_no INTEGER DEFAULT 1 NOT NULL"))
        conn.execute(text("UPDATE timetable_exceptions SET workflow_version_no = 1 WHERE workflow_version_no IS NULL"))


def downgrade(engine):
    return None
