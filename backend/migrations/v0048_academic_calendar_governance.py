VERSION = "0048_academic_calendar_governance"


def upgrade(engine):
    """Add the state-machine fields used by the F039 calendar workflow."""
    from sqlalchemy import inspect, text
    if "academic_calendar_entries" not in inspect(engine).get_table_names():
        return
    wanted = {
        "version_no": "INTEGER DEFAULT 1 NOT NULL",
        "requires_vp": "BOOLEAN DEFAULT FALSE NOT NULL",
        "dean_approved_by": "VARCHAR DEFAULT ''",
        "dean_approved_at": "TIMESTAMP",
        "vp_approved_by": "VARCHAR DEFAULT ''",
        "vp_approved_at": "TIMESTAMP",
        "workflow_reason": "TEXT DEFAULT ''",
    }
    with engine.begin() as conn:
        existing = {column["name"] for column in inspect(conn).get_columns("academic_calendar_entries")}
        for name, ddl in wanted.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE academic_calendar_entries ADD COLUMN {name} {ddl}"))
