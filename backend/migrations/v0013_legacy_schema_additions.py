"""Move legacy additive schema work into the versioned migration chain."""
from sqlalchemy import inspect, text

VERSION = "0013_legacy_schema_additions"


def upgrade(engine):
    # Register every model so fresh databases are created by migrations too.
    import domain_models  # noqa: F401
    import frontdesk_models  # noqa: F401
    from models import Base
    Base.metadata.create_all(engine)

    additions = {
        "students": [("blood_group", "VARCHAR DEFAULT ''"), ("student_type", "VARCHAR DEFAULT 'Regular'")],
        "attendance_records": [("status", "VARCHAR DEFAULT 'present'"), ("note", "VARCHAR DEFAULT ''"), ("updated_at", "TIMESTAMP")],
        "assessments": [("assessment_type", "VARCHAR DEFAULT 'exam'"), ("scheduled_at", "TIMESTAMP"), ("end_at", "TIMESTAMP"), ("published", "BOOLEAN DEFAULT FALSE"), ("instructions", "TEXT DEFAULT ''"), ("status", "VARCHAR DEFAULT 'draft'"), ("academic_year", "VARCHAR DEFAULT ''"), ("created_by", "VARCHAR DEFAULT ''"), ("updated_by", "VARCHAR DEFAULT ''"), ("created_at", "TIMESTAMP"), ("updated_at", "TIMESTAMP"), ("published_at", "TIMESTAMP"), ("published_by", "VARCHAR DEFAULT ''")],
        "marks": [("status", "VARCHAR DEFAULT 'published'"), ("published_at", "TIMESTAMP"), ("published_by", "VARCHAR DEFAULT ''"), ("is_valid", "BOOLEAN DEFAULT TRUE"), ("updated_at", "TIMESTAMP")],
        "result_sheets": [("academic_year", "VARCHAR DEFAULT ''"), ("semester", "INTEGER"), ("updated_at", "TIMESTAMP")],
        "student_subject_results": [("course_id", "VARCHAR"), ("section_id", "VARCHAR"), ("result_sheet_id", "VARCHAR"), ("credits", "FLOAT DEFAULT 0"), ("grade", "VARCHAR DEFAULT ''"), ("grade_point", "FLOAT"), ("percentage", "FLOAT"), ("total_score", "FLOAT"), ("max_score", "FLOAT"), ("updated_at", "TIMESTAMP")],
        "book_loans": [("student_id", "VARCHAR")],
        "fee_invoices": [("fee_structure_id", "VARCHAR"), ("invoice_number", "VARCHAR DEFAULT ''"), ("academic_year_id", "VARCHAR DEFAULT ''"), ("semester_id", "VARCHAR DEFAULT ''"), ("fee_assignment_id", "VARCHAR DEFAULT ''"), ("gross_amount", "FLOAT DEFAULT 0"), ("scholarship_amount", "FLOAT DEFAULT 0"), ("waiver_amount", "FLOAT DEFAULT 0"), ("net_amount", "FLOAT DEFAULT 0")],
        "payments": [("challan_id", "VARCHAR"), ("cleared_at", "TIMESTAMP"), ("cleared_by", "VARCHAR DEFAULT ''"), ("remarks", "VARCHAR DEFAULT ''")],
        "academic_rollovers": [("executed_by", "VARCHAR DEFAULT ''"), ("executed_at", "TIMESTAMP"), ("remarks", "TEXT DEFAULT ''")],
        "academic_rollover_decisions": [("academic_status", "VARCHAR DEFAULT 'PENDING'"), ("finance_status", "VARCHAR DEFAULT 'CLEAR'"), ("outstanding_amount", "FLOAT DEFAULT 0"), ("carry_forward_amount", "FLOAT DEFAULT 0"), ("processed_at", "TIMESTAMP")],
        "complaints": [("student_id", "VARCHAR")],
        "fee_structures": [("academic_year", "VARCHAR DEFAULT ''"), ("campus", "VARCHAR DEFAULT ''"), ("quota_id", "VARCHAR"), ("cycle_program_id", "VARCHAR"), ("code", "VARCHAR DEFAULT ''"), ("academic_year_id", "VARCHAR"), ("semester_id", "VARCHAR"), ("campus_id", "VARCHAR"), ("batch_id", "VARCHAR"), ("student_type_id", "VARCHAR"), ("version", "INTEGER DEFAULT 1"), ("workflow_id", "VARCHAR"), ("description", "TEXT DEFAULT ''"), ("notes", "TEXT DEFAULT ''"), ("created_by", "VARCHAR DEFAULT ''"), ("updated_by", "VARCHAR DEFAULT ''"), ("created_at", "TIMESTAMP"), ("updated_at", "TIMESTAMP")],
    }
    with engine.begin() as conn:
        inspector = inspect(conn)
        for table, columns in additions.items():
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        if inspector.has_table("courses"):
            existing = {c["name"] for c in inspector.get_columns("courses")}
            for name in ("program_id", "regulation", "course_type", "category", "ltp", "prerequisite", "status"):
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE courses ADD COLUMN {name} VARCHAR"))
            conn.execute(text("UPDATE courses SET regulation = 'R2023' WHERE regulation IS NULL OR regulation = ''"))
            conn.execute(text("UPDATE courses SET course_type = CASE WHEN semester = 7 THEN 'Elective' ELSE 'Core' END WHERE course_type IS NULL OR course_type = ''"))
            conn.execute(text("UPDATE courses SET category = CASE WHEN semester = 7 THEN 'Professional Elective' ELSE 'Professional Core' END WHERE category IS NULL OR category = ''"))
            conn.execute(text("UPDATE courses SET ltp = CASE WHEN credits >= 4 THEN '3-1-0' WHEN credits = 3 THEN '3-0-0' ELSE '2-0-0' END WHERE ltp IS NULL OR ltp = ''"))
            conn.execute(text("UPDATE courses SET status = 'Active' WHERE status IS NULL OR status = ''"))
        if inspector.has_table("staff_members"):
            existing = {c["name"] for c in inspector.get_columns("staff_members")}
            for name in ("phone", "office_hours"):
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE staff_members ADD COLUMN {name} VARCHAR"))


def downgrade(engine):
    return None
