"""Add explicit hierarchy columns to Phase 1 governance entities."""
from sqlalchemy import inspect, text

VERSION = "0016_governance_hierarchy"

TABLES = {
    "academic_proposals": ["school_id", "dept_id", "program_id", "section_id"],
    "timetable_exceptions": ["school_id", "dept_id", "program_id"],
    "academic_quality_reviews": ["school_id", "dept_id", "program_id", "section_id"],
    "corrective_actions": ["school_id", "dept_id", "program_id", "section_id"],
    "academic_committees": ["school_id", "dept_id"],
    "committee_meetings": ["school_id", "dept_id"],
    "committee_resolutions": ["school_id", "dept_id"],
    "committee_action_items": ["school_id", "dept_id"],
    "program_outcomes": ["school_id", "dept_id"],
    "course_outcomes": ["school_id", "dept_id", "program_id"],
    "outcome_mappings": ["school_id", "dept_id", "program_id", "course_id"],
    "next_semester_plans": ["school_id", "dept_id", "program_id", "section_id"],
}


def upgrade(engine):
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in TABLES.items():
            if not inspector.has_table(table):
                continue
            existing = {item["name"] for item in inspector.get_columns(table)}
            for column in columns:
                if column not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} VARCHAR"))
        if inspector.has_table("academic_proposals"):
            conn.execute(text("UPDATE academic_proposals SET dept_id = NULLIF(scope_ref, '') WHERE dept_id IS NULL AND scope_ref IN (SELECT id FROM departments)"))
            conn.execute(text("UPDATE academic_proposals SET school_id = (SELECT school_id FROM departments WHERE departments.id = academic_proposals.dept_id) WHERE school_id IS NULL"))
        if inspector.has_table("academic_quality_reviews"):
            conn.execute(text("UPDATE academic_quality_reviews SET dept_id = NULLIF(scope_ref, '') WHERE dept_id IS NULL AND scope_ref IN (SELECT id FROM departments)"))
            conn.execute(text("UPDATE academic_quality_reviews SET school_id = (SELECT school_id FROM departments WHERE departments.id = academic_quality_reviews.dept_id) WHERE school_id IS NULL"))
        if inspector.has_table("next_semester_plans"):
            conn.execute(text("UPDATE next_semester_plans SET dept_id = NULLIF(summary, '') WHERE dept_id IS NULL AND summary IN (SELECT id FROM departments)"))
            conn.execute(text("UPDATE next_semester_plans SET school_id = (SELECT school_id FROM departments WHERE departments.id = next_semester_plans.dept_id) WHERE school_id IS NULL"))


def downgrade(engine):
    return None