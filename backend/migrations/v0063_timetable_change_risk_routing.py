VERSION = "0063_timetable_change_risk_routing"


def upgrade(engine):
    """Persist the server-calculated approval route for timetable changes."""
    from sqlalchemy import inspect, text
    if "timetable_exceptions" not in inspect(engine).get_table_names():
        return
    with engine.begin() as conn:
        columns = {column["name"] for column in inspect(conn).get_columns("timetable_exceptions")}
        additions = {
            "risk_level": "VARCHAR DEFAULT 'INSTITUTIONAL' NOT NULL",
            "risk_reason": "TEXT DEFAULT ''",
            "approval_route": "VARCHAR DEFAULT 'HOD → Dean Academics → Vice Principal → Academic Coordinator'",
        }
        for name, ddl in additions.items():
            if name not in columns:
                conn.execute(text(f"ALTER TABLE timetable_exceptions ADD COLUMN {name} {ddl}"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_timetable_exceptions_risk_level ON timetable_exceptions(risk_level)"))


def downgrade(engine):
    return None
