VERSION = "v0014_attendance_session"
from sqlalchemy import inspect, text
def upgrade(engine):
    with engine.begin() as c:
        if "attendance_records" in inspect(engine).get_table_names() and "session_id" not in {x["name"] for x in inspect(engine).get_columns("attendance_records")}: c.execute(text("ALTER TABLE attendance_records ADD COLUMN session_id VARCHAR"))
def downgrade(engine): return None
