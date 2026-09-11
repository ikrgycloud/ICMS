"""Backfill faculty program and section scope for existing installations."""
from sqlalchemy import inspect, text

VERSION = "0015_backfill_staff_scope"


def upgrade(engine):
    inspector = inspect(engine)
    if not inspector.has_table("staff_members") or not inspector.has_table("sections"):
        return
    columns = {column["name"] for column in inspector.get_columns("staff_members")}
    with engine.begin() as conn:
        if "section_id" in columns:
            conn.execute(text("""
                UPDATE staff_members
                SET section_id = (
                    SELECT sections.id FROM sections
                    WHERE sections.faculty_person_id = staff_members.id
                    AND sections.tenant_id = staff_members.tenant_id
                    LIMIT 1
                )
                WHERE section_id IS NULL
            """))
        if "program_id" in columns:
            conn.execute(text("""
                UPDATE staff_members
                SET program_id = (
                    SELECT courses.program_id FROM sections
                    JOIN courses ON courses.id = sections.course_id
                    WHERE sections.id = staff_members.section_id
                    LIMIT 1
                )
                WHERE program_id IS NULL AND section_id IS NOT NULL
            """))


def downgrade(engine):
    return None
