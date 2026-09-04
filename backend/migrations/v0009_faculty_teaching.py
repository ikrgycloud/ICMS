"""Add the faculty teaching, attendance, mentoring, and research foundation."""
from sqlalchemy import inspect, text

import domain_models as D

VERSION = "v0009_faculty_teaching"


NEW_TABLES = (
    D.TeachingAllocation,
    D.CourseMaterial,
    D.StaffCheckIn,
    D.MentorAssignment,
    D.MentoringCase,
    D.MentoringNote,
    D.MentoringFollowUp,
    D.FacultyFunctionalAssignment,
    D.ClassSession,
    D.AttendanceCorrectionRequest,
    D.AssignmentSubmission,
    D.AssignmentEvaluation,
    D.ResearchProgress,
    D.ResearchMilestone,
    D.ResearchPublication,
)


ADDITIVE_COLUMNS = {
    "attendance_records": (
        ("class_session_id", "VARCHAR REFERENCES class_sessions(id)"),
        ("version_no", "INTEGER DEFAULT 1"),
        ("finalized_at", "TIMESTAMP"),
    ),
    "assessments": (
        ("marks_state", "VARCHAR DEFAULT 'draft'"),
        ("workflow_instance_id", "VARCHAR REFERENCES workflow_instances(id)"),
        ("marks_submitted_by", "VARCHAR DEFAULT ''"),
        ("marks_submitted_at", "TIMESTAMP"),
        ("marks_approved_at", "TIMESTAMP"),
        ("marks_published_at", "TIMESTAMP"),
        ("marks_revision", "INTEGER DEFAULT 1"),
        ("marks_return_comment", "TEXT DEFAULT ''"),
    ),
    "assignments": (
        ("max_marks", "FLOAT DEFAULT 100"),
        ("allow_late", "BOOLEAN DEFAULT TRUE"),
        ("faculty_id", "VARCHAR REFERENCES staff_members(id)"),
        ("teaching_allocation_id", "VARCHAR REFERENCES teaching_allocations(id)"),
        ("published_at", "TIMESTAMP"),
        ("published_by", "VARCHAR DEFAULT ''"),
        ("closed_at", "TIMESTAMP"),
        ("closed_by", "VARCHAR DEFAULT ''"),
    ),
    "leave_requests": (
        ("workflow_instance_id", "VARCHAR REFERENCES workflow_instances(id)"),
        ("requested_by", "VARCHAR DEFAULT ''"),
        ("half_day", "BOOLEAN DEFAULT FALSE"),
        ("submitted_at", "TIMESTAMP"),
        ("updated_at", "TIMESTAMP"),
        ("returned_comment", "TEXT DEFAULT ''"),
    ),
    "research_projects": (
        ("owner_id", "VARCHAR REFERENCES staff_members(id)"),
        ("category", "VARCHAR DEFAULT ''"),
        ("summary", "TEXT DEFAULT ''"),
        ("start_date", "DATE"),
        ("expected_end_date", "DATE"),
        ("completed_at", "TIMESTAMP"),
        ("closed_at", "TIMESTAMP"),
        ("created_at", "TIMESTAMP"),
        ("updated_at", "TIMESTAMP"),
    ),
}


INDEXES = (
    ("ix_attendance_records_class_session_id", "attendance_records", "class_session_id", False),
    ("ix_assessments_marks_state", "assessments", "marks_state", False),
    ("ix_assessments_workflow_instance_id", "assessments", "workflow_instance_id", True),
    ("ix_leave_requests_workflow_instance_id", "leave_requests", "workflow_instance_id", True),
    ("ix_leave_requests_requested_by", "leave_requests", "requested_by", False),
    ("ix_research_projects_owner_id", "research_projects", "owner_id", False),
)


def upgrade(engine):
    # These are explicit, versioned table creations; checkfirst makes reruns and
    # databases partially initialized by older create_all bootstraps safe.
    for model in NEW_TABLES:
        model.__table__.create(bind=engine, checkfirst=True)

    with engine.begin() as conn:
        inspector = inspect(conn)
        table_names = set(inspector.get_table_names())
        for table_name, additions in ADDITIVE_COLUMNS.items():
            if table_name not in table_names:
                continue
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, ddl in additions:
                if column_name not in existing:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))

        inspector = inspect(conn)
        for index_name, table_name, column_name, unique in INDEXES:
            if table_name not in table_names:
                continue
            existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
            if index_name not in existing_indexes:
                qualifier = "UNIQUE " if unique else ""
                conn.execute(text(
                    f"CREATE {qualifier}INDEX {index_name} ON {table_name} ({column_name})"
                ))
