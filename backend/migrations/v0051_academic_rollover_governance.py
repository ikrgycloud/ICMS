VERSION = "0051_academic_rollover_governance"


def upgrade(engine):
    from sqlalchemy import inspect, text
    with engine.begin() as conn:
        inspector = inspect(conn)
        if not inspector.has_table("academic_rollovers"):
            return
        existing = {column["name"] for column in inspector.get_columns("academic_rollovers")}
        columns = {
            "dept_id": "VARCHAR",
            "version_no": "INTEGER NOT NULL DEFAULT 1",
            "hod_reviewed_by": "VARCHAR DEFAULT ''",
            "dean_reviewed_by": "VARCHAR DEFAULT ''",
            "finance_reviewed_by": "VARCHAR DEFAULT ''",
            "workflow_reason": "TEXT DEFAULT ''",
        }
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE academic_rollovers ADD COLUMN {name} {definition}"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_academic_rollovers_dept_status ON academic_rollovers(dept_id, status)"))
