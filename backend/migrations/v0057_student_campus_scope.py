"""Canonical campus ownership for campus-scoped student aggregates."""
from sqlalchemy import inspect, text

VERSION = "0057_student_campus_scope"


def upgrade(engine):
    inspector = inspect(engine)
    if not inspector.has_table("students"):
        return
    columns = {column["name"] for column in inspector.get_columns("students")}
    with engine.begin() as conn:
        if "campus_scope_id" not in columns:
            conn.execute(text("ALTER TABLE students ADD COLUMN campus_scope_id VARCHAR"))
        # Backfill only from the persisted legacy campus label into a canonical
        # tenant scope; a UI request can never select or influence this value.
        conn.execute(text("""
            UPDATE students
            SET campus_scope_id = (
                SELECT org_scopes.id
                FROM org_scopes
                WHERE org_scopes.tenant_id = students.tenant_id
                  AND org_scopes.level = 'campus'
                  AND org_scopes.name = students.campus
                LIMIT 1
            )
            WHERE campus_scope_id IS NULL OR campus_scope_id = ''
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_students_campus_scope_id ON students (campus_scope_id)"))
