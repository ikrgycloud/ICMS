VERSION = "0049_offering_curriculum_and_enrollment"

def upgrade(engine):
    from sqlalchemy import inspect, text
    with engine.begin() as conn:
        inspector = inspect(conn)
        if inspector.has_table("course_offerings") and "curriculum_version_id" not in {c["name"] for c in inspector.get_columns("course_offerings")}:
            conn.execute(text("ALTER TABLE course_offerings ADD COLUMN curriculum_version_id VARCHAR"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_course_offerings_curriculum_version_id ON course_offerings(curriculum_version_id)"))
        if inspector.has_table("enrollments"):
            # Legacy seed/import data can contain repeated rows for the same
            # student and section. Retain the active/latest authoritative row
            # before adding the invariant used by self-registration.
            dialect_name = engine.dialect.name
            if dialect_name == "sqlite":
                # SQLite does not support PostgreSQL's DELETE ... USING / ctid
                # de-duplication syntax. Use a portable windowed delete pattern
                # with the rowid alias that SQLite understands.
                conn.execute(text("""
                    DELETE FROM enrollments
                    WHERE id IN (
                        SELECT id FROM (
                            SELECT id,
                                   ROW_NUMBER() OVER (
                                       PARTITION BY tenant_id, student_id, section_id
                                       ORDER BY CASE status WHEN 'enrolled' THEN 0 WHEN 'requested' THEN 1 ELSE 2 END,
                                                requested_at DESC,
                                                id DESC
                                   ) AS row_number
                            FROM enrollments
                        )
                        WHERE row_number > 1
                    )
                """))
            else:
                conn.execute(text("""
                    DELETE FROM enrollments AS duplicate
                    USING (
                        SELECT ctid,
                               ROW_NUMBER() OVER (
                                   PARTITION BY tenant_id, student_id, section_id
                                   ORDER BY CASE status WHEN 'enrolled' THEN 0 WHEN 'requested' THEN 1 ELSE 2 END,
                                            requested_at DESC NULLS LAST,
                                            id DESC
                               ) AS row_number
                        FROM enrollments
                    ) AS ranked
                    WHERE duplicate.ctid = ranked.ctid AND ranked.row_number > 1
                """))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_enrollment_student_section ON enrollments(tenant_id, student_id, section_id)"))
