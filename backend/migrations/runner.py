"""Tiny migration runner shared by PostgreSQL and SQLite deployments."""
from sqlalchemy import inspect, text

from migrations import (v0001_admissions_foundation, v0002_repair_legacy_application_status,
                        v0003_admission_seat_pool_identity, v0004_admissions_phase2_application_context)
from migrations import v0005_admissions_eligibility
from migrations import v0006_admissions_phase4
from migrations import v0007_admissions_phase5
from migrations import v0008_transport_route_status
from migrations import v0009_course_offerings
from migrations import v0010_offering_workflow
from migrations import v0011_section_offering
from migrations import v0012_timetable_plan_workflows
from migrations import v0013_class_sessions, v0014_attendance_session
from migrations import v0015_session_checkins
from migrations import v0016_curriculum_execution
from migrations import v0017_academic_calendar_scope
from migrations import v0018_timetable_conflicts
from migrations import v0019_curriculum_execution_tracking
from migrations import v0020_execution_targets
from migrations import v0021_execution_marks
from migrations import v0022_mid_execution_progress

MIGRATIONS = [v0001_admissions_foundation, v0002_repair_legacy_application_status,
              v0003_admission_seat_pool_identity, v0004_admissions_phase2_application_context]
MIGRATIONS.append(v0005_admissions_eligibility)
MIGRATIONS.append(v0006_admissions_phase4)
MIGRATIONS.append(v0007_admissions_phase5)
MIGRATIONS.append(v0008_transport_route_status)
MIGRATIONS.append(v0009_course_offerings)
MIGRATIONS.append(v0010_offering_workflow)
MIGRATIONS.append(v0011_section_offering)
MIGRATIONS.append(v0012_timetable_plan_workflows)
MIGRATIONS.extend([v0013_class_sessions, v0014_attendance_session])
MIGRATIONS.append(v0015_session_checkins)
MIGRATIONS.append(v0016_curriculum_execution)
MIGRATIONS.append(v0017_academic_calendar_scope)
MIGRATIONS.append(v0018_timetable_conflicts)
MIGRATIONS.append(v0019_curriculum_execution_tracking)
MIGRATIONS.append(v0020_execution_targets)
MIGRATIONS.append(v0021_execution_marks)
MIGRATIONS.append(v0022_mid_execution_progress)


def upgrade(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS icms_schema_migrations (version VARCHAR(64) PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
        applied = {row[0] for row in conn.execute(text("SELECT version FROM icms_schema_migrations"))}
    for migration in MIGRATIONS:
        if migration.VERSION in applied:
            continue
        migration.upgrade(engine)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO icms_schema_migrations (version) VALUES (:version)"), {"version": migration.VERSION})


def column_exists(engine, table, column):
    return inspect(engine).has_table(table) and column in {c["name"] for c in inspect(engine).get_columns(table)}
