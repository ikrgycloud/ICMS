VERSION = "0050_timetable_exception_changes"

def upgrade(engine):
    from sqlalchemy import inspect, text
    columns = {
        "timetable_entry_id": "VARCHAR",
        "timetable_plan_id": "VARCHAR",
        "class_session_id": "VARCHAR",
        "requested_by": "VARCHAR DEFAULT ''",
        "change_payload_json": "TEXT DEFAULT '{}'",
        "base_version": "INTEGER DEFAULT 0",
        "published_at": "TIMESTAMP",
    }
    with engine.begin() as conn:
        inspector = inspect(conn)
        if not inspector.has_table("timetable_exceptions"):
            return
        existing = {column["name"] for column in inspector.get_columns("timetable_exceptions")}
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE timetable_exceptions ADD COLUMN {name} {definition}"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_timetable_exceptions_entry ON timetable_exceptions(timetable_entry_id, status)"))
        entry_columns = {column["name"] for column in inspect(conn).get_columns("timetable_entries")}
        if "version_no" not in entry_columns:
            conn.execute(text("ALTER TABLE timetable_entries ADD COLUMN version_no INTEGER DEFAULT 1"))
