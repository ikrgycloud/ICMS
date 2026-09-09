"""Add persisted academic hierarchy links for Phase 1 scope enforcement."""
from sqlalchemy import inspect, text

VERSION = "0014_academic_hierarchy"


def upgrade(engine):
    additions = {
        "departments": [("school_id", "VARCHAR")],
        "programs": [("school_id", "VARCHAR")],
        "courses": [("school_id", "VARCHAR")],
        "sections": [("school_id", "VARCHAR")],
        "staff_members": [("school_id", "VARCHAR"), ("program_id", "VARCHAR"), ("section_id", "VARCHAR")],
    }
    with engine.begin() as conn:
        inspector = inspect(conn)
        for table, columns in additions.items():
            if not inspector.has_table(table):
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        if inspector.has_table("departments") and inspector.has_table("schools"):
            conn.execute(text("""
                UPDATE departments
                SET school_id = CASE
                    WHEN upper(code) IN ('CSE', 'ECE', 'MAT') THEN 'school_schcom'
                    WHEN upper(code) IN ('MEC', 'CIV', 'EEE') THEN 'school_scheng'
                    WHEN upper(code) = 'MGT' THEN 'school_schbus'
                    WHEN upper(code) = 'HSS' THEN 'school_schsoc'
                    ELSE school_id
                END
                WHERE school_id IS NULL
            """))
        if inspector.has_table("programs"):
            conn.execute(text("UPDATE programs SET school_id = (SELECT school_id FROM departments WHERE departments.id = programs.dept_id) WHERE school_id IS NULL"))
        if inspector.has_table("courses"):
            conn.execute(text("UPDATE courses SET school_id = (SELECT school_id FROM departments WHERE departments.id = courses.dept_id) WHERE school_id IS NULL"))
        if inspector.has_table("sections"):
            conn.execute(text("UPDATE sections SET school_id = (SELECT school_id FROM departments WHERE departments.id = sections.dept_id) WHERE school_id IS NULL"))
        if inspector.has_table("staff_members"):
            conn.execute(text("UPDATE staff_members SET school_id = (SELECT school_id FROM departments WHERE departments.id = staff_members.dept_id) WHERE school_id IS NULL"))
            if inspector.has_table("sections"):
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