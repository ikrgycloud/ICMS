from sqlalchemy import create_engine, text, inspect

from migrations.v0049_offering_curriculum_and_enrollment import upgrade


def test_v0049_sqlite_upgrade_handles_duplicate_enrollment_cleanup_portably():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE enrollments (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR,
                student_id VARCHAR,
                section_id VARCHAR,
                status VARCHAR,
                requested_at TIMESTAMP
            )
        """))
        conn.execute(text("""
            INSERT INTO enrollments (id, tenant_id, student_id, section_id, status, requested_at)
            VALUES
                ('e1', 'tenant-a', 'student-1', 'section-1', 'enrolled', NULL),
                ('e2', 'tenant-a', 'student-1', 'section-1', 'requested', NULL)
        """))

    upgrade(engine)

    with engine.begin() as conn:
        row_count = conn.execute(text("SELECT COUNT(*) FROM enrollments")).scalar_one()
        assert row_count == 1
