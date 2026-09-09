VERSION = "v0017_academic_calendar_scope"

def upgrade(engine):
    from sqlalchemy import inspect, text
    from models import Base
    import domain_models  # noqa: F401
    Base.metadata.create_all(engine)
    additions = {
        "academic_year": "VARCHAR DEFAULT ''",
        "program_id": "VARCHAR",
        "department_id": "VARCHAR",
        "student_year": "INTEGER",
        "start_time": "VARCHAR DEFAULT ''",
        "end_time": "VARCHAR DEFAULT ''",
    }
    with engine.begin() as conn:
        existing = {c["name"] for c in inspect(conn).get_columns("academic_calendar_entries")}
        for name, ddl in additions.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE academic_calendar_entries ADD COLUMN {name} {ddl}"))

def downgrade(engine):
    return None
