VERSION = "v0018_timetable_conflicts"

from sqlalchemy import inspect, text
from models import Base
import domain_models  # noqa: F401

def upgrade(engine):
    Base.metadata.create_all(engine)
    additions = {
        "severity": "VARCHAR DEFAULT 'Medium'",
        "status": "VARCHAR DEFAULT 'Active'",
        "resolution_note": "TEXT DEFAULT ''",
        "resolved_by": "VARCHAR DEFAULT ''",
        "resolved_at": "TIMESTAMP",
        "detected_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP",
    }
    with engine.begin() as conn:
        if not inspect(engine).has_table("timetable_conflicts"):
            return
        existing = {c["name"] for c in inspect(conn).get_columns("timetable_conflicts")}
        for name, ddl in additions.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE timetable_conflicts ADD COLUMN {name} {ddl}"))

def downgrade(engine):
    pass
