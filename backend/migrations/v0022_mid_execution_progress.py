from sqlalchemy import inspect, text
from models import Base
import domain_models  # noqa: F401

VERSION = "v0022_mid_execution_progress"


def upgrade(engine):
    Base.metadata.create_all(engine)
    additions = {
        "mid1_completion_percentage": "INTEGER",
        "mid2_remaining_syllabus_percentage": "INTEGER",
    }
    with engine.begin() as conn:
        existing = {c["name"] for c in inspect(conn).get_columns("course_offerings")}
        for name, ddl in additions.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE course_offerings ADD COLUMN {name} {ddl}"))


def downgrade(engine):
    return None