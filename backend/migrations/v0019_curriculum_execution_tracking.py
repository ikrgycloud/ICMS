VERSION = "v0019_curriculum_execution_tracking"
from sqlalchemy import inspect, text
from models import Base
import domain_models  # noqa: F401

def upgrade(engine):
    Base.metadata.create_all(engine)
    additions = {"expected_completion_date":"DATE", "actual_completion_date":"DATE", "execution_status":"VARCHAR DEFAULT 'Not Started'", "execution_remarks":"TEXT DEFAULT ''", "execution_completed_by":"VARCHAR DEFAULT ''", "execution_completed_at":"TIMESTAMP"}
    with engine.begin() as conn:
        existing = {c["name"] for c in inspect(conn).get_columns("course_offerings")}
        for name, ddl in additions.items():
            if name not in existing: conn.execute(text(f"ALTER TABLE course_offerings ADD COLUMN {name} {ddl}"))
def downgrade(engine): return None
