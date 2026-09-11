# -*- coding: utf-8 -*-
"""
Database engine + seed. Multi-tenant shared-schema with tenant_id (Document §6).
Uses PostgreSQL when DATABASE_URL is set, else falls back to local SQLite so the
whole system runs even without Docker.
"""
import os
import json
import re
from datetime import datetime, timedelta
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from models import (Base, Tenant, Institution, AuthorityMembership, BranchOrganization, OrgScope, Person, User, Role, Permission,
                    RolePermission, ApprovalLimit, UserRole, Designation)
import domain_models  # Ensure all declarative models are registered before metadata.create_all().
from authority import pwhash, VERBS, scope_covers
from matrices import (rbac_for, APPROVAL_LIMITS, scope_for, APPROVAL_MATRIX)

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "catalog.json")) as f:
    CATALOG = json.load(f)

OFFICES = CATALOG["offices"]
LEVELS = CATALOG["levels"]
TENANT = "t_main"
CAMPUS_SCOPES = [
    "Main Campus",
    "North Campus",
    "City Campus",
    "Medical Sciences Campus",
    "Research Park Campus",
    "School of Design Campus",
]

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{HERE}/icms.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def ensure_additive_schema():
    """Create missing tables and add newly introduced additive columns safely."""
    Base.metadata.create_all(engine)

    additions = {
        "users": [("last_login_at", "TIMESTAMP"), ("onboarding_completed_at", "TIMESTAMP"),
                  ("password_created_at", "TIMESTAMP"),
                  ("demo_password_enabled", "BOOLEAN DEFAULT FALSE")],
        "tenants": [("institution_id", "VARCHAR")],
        "students": [
            ("blood_group", "VARCHAR DEFAULT ''"),
            ("student_type", "VARCHAR DEFAULT 'Regular'"),
            ("campus_scope_id", "VARCHAR"),
        ],
        "sections": [("campus_scope_id", "VARCHAR")],
        "staff_members": [("campus_scope_id", "VARCHAR")],
        "budget_lines": [("campus_scope_id", "VARCHAR")],
        "leave_requests": [("campus_scope_id", "VARCHAR")],
        "hostel_rooms": [("campus", "VARCHAR DEFAULT ''"), ("campus_scope_id", "VARCHAR")],
        "hostel_allocations": [("campus", "VARCHAR DEFAULT ''"), ("campus_scope_id", "VARCHAR")],
        "compliance_requirements": [("campus_scope_id", "VARCHAR")],
        "transport_routes": [("campus_scope_id", "VARCHAR")],
        "research_projects": [("campus_scope_id", "VARCHAR")],
        "complaints": [
            ("campus_scope_id", "VARCHAR"),
            ("investigation_notes", "TEXT DEFAULT ''"),
            ("investigated_by", "VARCHAR DEFAULT ''"),
            ("investigated_at", "TIMESTAMP"),
            ("resolution_notes", "TEXT DEFAULT ''"),
            ("resolved_by", "VARCHAR DEFAULT ''"),
            ("resolved_at", "TIMESTAMP"),
        ],
        # Existing job posting rows are preserved.  These additive fields
        # support tenant-local recruitment requirements created by a Principal.
        "job_postings": [
            ("dept_id", "VARCHAR"),
            ("description", "TEXT DEFAULT ''"),
            ("qualification", "VARCHAR DEFAULT ''"),
            ("experience", "VARCHAR DEFAULT ''"),
            ("skills", "TEXT DEFAULT ''"),
            ("closing_date", "DATE"),
            ("priority", "VARCHAR DEFAULT 'normal'"),
            ("notes", "TEXT DEFAULT ''"),
            ("created_by", "VARCHAR DEFAULT ''"),
            ("created_at", "TIMESTAMP"),
        ],
        "attendance_records": [
            ("status", "VARCHAR DEFAULT 'present'"),
            ("note", "VARCHAR DEFAULT ''"),
            ("updated_at", "TIMESTAMP"),
        ],
        "assessments": [
            ("assessment_type", "VARCHAR DEFAULT 'exam'"),
            ("scheduled_at", "TIMESTAMP"),
            ("end_at", "TIMESTAMP"),
            ("published", "BOOLEAN DEFAULT FALSE"),
            ("instructions", "TEXT DEFAULT ''"),
            ("status", "VARCHAR DEFAULT 'draft'"),
            ("academic_year", "VARCHAR DEFAULT ''"),
            ("created_by", "VARCHAR DEFAULT ''"),
            ("updated_by", "VARCHAR DEFAULT ''"),
            ("created_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
            ("published_at", "TIMESTAMP"),
            ("published_by", "VARCHAR DEFAULT ''"),
            ("marks_state", "VARCHAR DEFAULT 'draft'"),
            ("workflow_id", "VARCHAR"),
        ],
        "marks": [
            ("status", "VARCHAR DEFAULT 'published'"),
            ("published_at", "TIMESTAMP"),
            ("published_by", "VARCHAR DEFAULT ''"),
            ("is_valid", "BOOLEAN DEFAULT TRUE"),
            ("updated_at", "TIMESTAMP"),
        ],
        "result_sheets": [
            ("academic_year", "VARCHAR DEFAULT ''"),
            ("semester", "INTEGER"),
            ("updated_at", "TIMESTAMP"),
        ],
        "student_subject_results": [
            ("course_id", "VARCHAR"),
            ("section_id", "VARCHAR"),
            ("result_sheet_id", "VARCHAR"),
            ("credits", "FLOAT DEFAULT 0"),
            ("grade", "VARCHAR DEFAULT ''"),
            ("grade_point", "FLOAT"),
            ("percentage", "FLOAT"),
            ("total_score", "FLOAT"),
            ("max_score", "FLOAT"),
            ("updated_at", "TIMESTAMP"),
        ],
        "book_loans": [
            ("student_id", "VARCHAR"),
        ],
        "workflow_instances": [
            ("campus_scope_id", "VARCHAR"),
            ("current_owner_office_n", "INTEGER"),
            ("current_owner_user_id", "VARCHAR"),
        ],
        "assets": [
            ("campus_scope_id", "VARCHAR"),
        ],
        "placement_drives": [
            ("campus_scope_id", "VARCHAR"),
        ],
        "audit_logs": [
            ("campus_scope_id", "VARCHAR"),
        ],
    }

    with engine.begin() as conn:
        inspector = inspect(conn)
        for table_name, columns in additions.items():
            if not inspector.has_table(table_name):
                continue
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, ddl in columns:
                if column_name in existing:
                    continue
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))
        if inspector.has_table("workflow_instances") and inspector.has_table("org_scopes"):
            indexes = {index["name"] for index in inspect(conn).get_indexes("workflow_instances")}
            if "ix_workflow_instances_campus_scope_id" not in indexes:
                conn.execute(text("CREATE INDEX ix_workflow_instances_campus_scope_id ON workflow_instances (campus_scope_id)"))
            if "ix_workflow_instances_current_owner_user_id" not in indexes:
                conn.execute(text("CREATE INDEX ix_workflow_instances_current_owner_user_id ON workflow_instances (current_owner_user_id)"))
            if "ix_workflow_instances_current_owner_office_n" not in indexes:
                conn.execute(text("CREATE INDEX ix_workflow_instances_current_owner_office_n ON workflow_instances (current_owner_office_n)"))
            foreign_keys = {fk.get("name") for fk in inspect(conn).get_foreign_keys("workflow_instances")}
            if conn.dialect.name == "postgresql" and "fk_workflow_instances_campus_scope" not in foreign_keys:
                conn.execute(text("ALTER TABLE workflow_instances ADD CONSTRAINT fk_workflow_instances_campus_scope FOREIGN KEY (campus_scope_id) REFERENCES org_scopes (id)"))
        if inspector.has_table("assessments"):
            indexes = {index["name"] for index in inspect(conn).get_indexes("assessments")}
            for index_name, column_name in (("ix_assessments_marks_state", "marks_state"),
                                            ("ix_assessments_workflow_id", "workflow_id")):
                if index_name not in indexes:
                    conn.execute(text(f"CREATE INDEX {index_name} ON assessments ({column_name})"))
            if conn.dialect.name == "postgresql":
                foreign_keys = {fk.get("name") for fk in inspect(conn).get_foreign_keys("assessments")}
                if "fk_assessments_workflow" not in foreign_keys:
                    conn.execute(text("ALTER TABLE assessments ADD CONSTRAINT fk_assessments_workflow FOREIGN KEY (workflow_id) REFERENCES workflow_instances (id)"))
            conn.execute(text("""
                UPDATE assessments
                SET marks_state = CASE WHEN status = 'cancelled' THEN 'cancelled' ELSE 'draft' END
                WHERE marks_state IS NULL OR marks_state = ''
            """))
            if inspector.has_table("result_sheets"):
                # A published ResultSheet is authoritative evidence that the
                # linked assessment already completed the historical process.
                conn.execute(text("""
                    UPDATE assessments
                    SET marks_state = 'published'
                    WHERE marks_state = 'draft'
                      AND EXISTS (
                          SELECT 1 FROM result_sheets AS result
                          WHERE result.tenant_id = assessments.tenant_id
                            AND result.section_id = assessments.section_id
                            AND result.status = 'published'
                      )
                """))
        # A compliance requirement is the authoritative campus owner of its
        # linked workflow.  Backfill only that exact one-to-one relationship;
        # no display name or Main Campus fallback is used for generic workflows.
        if (inspector.has_table("workflow_instances")
                and inspector.has_table("compliance_requirements")):
            if conn.dialect.name == "postgresql":
                conn.execute(text("""
                    UPDATE workflow_instances AS workflow
                    SET campus_scope_id = matched.campus_scope_id
                    FROM (
                        SELECT workflow_row.id, MIN(requirement.campus_scope_id) AS campus_scope_id
                        FROM workflow_instances AS workflow_row
                        JOIN compliance_requirements AS requirement
                          ON requirement.workflow_id = workflow_row.id
                         AND requirement.tenant_id = workflow_row.tenant_id
                        WHERE workflow_row.campus_scope_id IS NULL
                          AND requirement.campus_scope_id IS NOT NULL
                        GROUP BY workflow_row.id
                        HAVING COUNT(DISTINCT requirement.campus_scope_id) = 1
                    ) AS matched
                    WHERE workflow.id = matched.id
                """))
                # Earlier seeded compliance escalations retained the Principal
                # stage.  The configured next stage is Vice Chairman (index 3).
                # This correction is deliberately limited to already-escalated,
                # compliance-linked workflows with authoritative campus scope.
                conn.execute(text("""
                    UPDATE workflow_instances AS workflow
                    SET current_stage = 3
                    WHERE workflow.process_key = 'compliance_requirement'
                      AND workflow.state = 'escalated'
                      AND workflow.escalated = TRUE
                      AND workflow.current_stage = 2
                      AND workflow.campus_scope_id IS NOT NULL
                      AND EXISTS (
                          SELECT 1 FROM compliance_requirements AS requirement
                          WHERE requirement.workflow_id = workflow.id
                            AND requirement.tenant_id = workflow.tenant_id
                            AND requirement.campus_scope_id = workflow.campus_scope_id
                      )
                """))
            else:
                conn.execute(text("""
                    UPDATE workflow_instances
                    SET campus_scope_id = (
                        SELECT MIN(requirement.campus_scope_id)
                        FROM compliance_requirements AS requirement
                        WHERE requirement.workflow_id = workflow_instances.id
                          AND requirement.tenant_id = workflow_instances.tenant_id
                          AND requirement.campus_scope_id IS NOT NULL
                        GROUP BY requirement.workflow_id
                        HAVING COUNT(DISTINCT requirement.campus_scope_id) = 1
                    )
                    WHERE campus_scope_id IS NULL
                      AND EXISTS (
                          SELECT 1 FROM compliance_requirements AS requirement
                          WHERE requirement.workflow_id = workflow_instances.id
                            AND requirement.tenant_id = workflow_instances.tenant_id
                            AND requirement.campus_scope_id IS NOT NULL
                          GROUP BY requirement.workflow_id
                          HAVING COUNT(DISTINCT requirement.campus_scope_id) = 1
                      )
                """))
        # A risk record is the authoritative canonical-campus source for its
        # linked escalation workflow.  This backfill is deliberately limited
        # to that one-to-one foreign reference; no campus display value or
        # tenant default is ever used.
        if (inspector.has_table("workflow_instances")
                and inspector.has_table("risk_records")):
            conn.execute(text("""
                UPDATE workflow_instances
                SET campus_scope_id = (
                    SELECT risk.campus_scope_id
                    FROM risk_records AS risk
                    WHERE risk.escalation_workflow_id = workflow_instances.id
                      AND risk.tenant_id = workflow_instances.tenant_id
                      AND risk.campus_scope_id IS NOT NULL
                )
                WHERE campus_scope_id IS NULL
                  AND process_key IN ('campus_risk_escalation', 'campus_risk_escalation_critical')
                  AND EXISTS (
                    SELECT 1 FROM risk_records AS risk
                    WHERE risk.escalation_workflow_id = workflow_instances.id
                      AND risk.tenant_id = workflow_instances.tenant_id
                      AND risk.campus_scope_id IS NOT NULL
                  )
            """))
        # Phase 6A: canonical ownership for infrastructure and placements.
        # Existing rows stay NULL: no legacy text or descriptive value is used
        # as evidence of campus ownership.
        if inspector.has_table("org_scopes"):
            for table_name, constraint_name in (
                ("assets", "fk_assets_campus_scope"),
                ("placement_drives", "fk_placement_drives_campus_scope"),
                ("audit_logs", "fk_audit_logs_campus_scope"),
                ("sections", "fk_sections_campus_scope"),
            ):
                if not inspector.has_table(table_name):
                    continue
                index_name = f"ix_{table_name}_campus_scope_id"
                indexes = {index["name"] for index in inspect(conn).get_indexes(table_name)}
                if index_name not in indexes:
                    conn.execute(text(f"CREATE INDEX {index_name} ON {table_name} (campus_scope_id)"))
                foreign_keys = {fk.get("name") for fk in inspect(conn).get_foreign_keys(table_name)}
                if conn.dialect.name == "postgresql" and constraint_name not in foreign_keys:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} FOREIGN KEY (campus_scope_id) REFERENCES org_scopes (id)"))
        # Canonicalise only records whose own tenant-local display campus
        # resolves to exactly one OrgScope.  Blank records remain unassigned:
        # no tenant is ever inferred as Main Campus during application startup.
        if inspector.has_table("org_scopes"):
            canonical_tables = ("students", "staff_members", "budget_lines", "hostel_rooms", "hostel_allocations", "compliance_requirements")
            for table_name in canonical_tables:
                if not inspector.has_table(table_name):
                    continue
                index_name = f"ix_{table_name}_campus_scope_id"
                indexes = {index["name"] for index in inspect(conn).get_indexes(table_name)}
                if index_name not in indexes:
                    conn.execute(text(f"CREATE INDEX {index_name} ON {table_name} (campus_scope_id)"))
                if conn.dialect.name == "postgresql":
                    constraint_name = f"fk_{table_name}_campus_scope"
                    foreign_keys = {fk.get("name") for fk in inspect(conn).get_foreign_keys(table_name)}
                    if constraint_name not in foreign_keys:
                        conn.execute(text(f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} FOREIGN KEY (campus_scope_id) REFERENCES org_scopes (id)"))
                    conn.execute(text(f"""
                        UPDATE {table_name} AS record
                        SET campus_scope_id = scope.id
                        FROM org_scopes AS scope
                        WHERE record.campus_scope_id IS NULL
                          AND record.campus IS NOT NULL AND record.campus <> ''
                          AND scope.tenant_id = record.tenant_id
                          AND scope.level = 'campus' AND scope.name = record.campus
                    """))
                else:
                    conn.execute(text(f"""
                        UPDATE {table_name}
                        SET campus_scope_id = (
                            SELECT scope.id FROM org_scopes AS scope
                            WHERE scope.tenant_id = {table_name}.tenant_id
                              AND scope.level = 'campus' AND scope.name = {table_name}.campus
                        )
                        WHERE campus_scope_id IS NULL AND campus IS NOT NULL AND campus <> ''
                          AND EXISTS (SELECT 1 FROM org_scopes AS scope
                                      WHERE scope.tenant_id = {table_name}.tenant_id
                                        AND scope.level = 'campus' AND scope.name = {table_name}.campus)
                    """))
            if inspector.has_table("complaints"):
                indexes = {index["name"] for index in inspect(conn).get_indexes("complaints")}
                if "ix_complaints_campus_scope_id" not in indexes:
                    conn.execute(text("CREATE INDEX ix_complaints_campus_scope_id ON complaints (campus_scope_id)"))
                foreign_keys = {fk.get("name") for fk in inspect(conn).get_foreign_keys("complaints")}
                if conn.dialect.name == "postgresql" and "fk_complaints_campus_scope" not in foreign_keys:
                    conn.execute(text("ALTER TABLE complaints ADD CONSTRAINT fk_complaints_campus_scope FOREIGN KEY (campus_scope_id) REFERENCES org_scopes (id)"))
            # Sections are the authoritative campus parent for examination
            # records.  Backfill only when their enrolled students or owning
            # department resolve to exactly one tenant-local campus scope.
            # Ambiguous legacy rows deliberately remain unassigned and fail
            # closed for campus-scoped readers.
            if inspector.has_table("sections") and inspector.has_table("enrollments") and inspector.has_table("students"):
                if conn.dialect.name == "postgresql":
                    conn.execute(text("""
                        UPDATE sections AS section
                        SET campus_scope_id = matched.campus_scope_id
                        FROM (
                            SELECT section_row.id, MIN(student.campus_scope_id) AS campus_scope_id
                            FROM sections AS section_row
                            JOIN enrollments AS enrollment
                              ON enrollment.section_id = section_row.id
                             AND enrollment.tenant_id = section_row.tenant_id
                             AND enrollment.status = 'enrolled'
                            JOIN students AS student
                              ON student.id = enrollment.student_id
                             AND student.tenant_id = section_row.tenant_id
                            WHERE section_row.campus_scope_id IS NULL
                              AND student.campus_scope_id IS NOT NULL
                            GROUP BY section_row.id
                            HAVING COUNT(DISTINCT student.campus_scope_id) = 1
                        ) AS matched
                        WHERE section.id = matched.id
                    """))
                    if inspector.has_table("departments"):
                        conn.execute(text("""
                            UPDATE sections AS section
                            SET campus_scope_id = matched.campus_scope_id
                            FROM (
                                SELECT section_row.id, MIN(scope.id) AS campus_scope_id
                                FROM sections AS section_row
                                JOIN departments AS department
                                  ON department.id = section_row.dept_id
                                 AND department.tenant_id = section_row.tenant_id
                                JOIN org_scopes AS scope
                                  ON scope.tenant_id = section_row.tenant_id
                                 AND scope.level = 'campus'
                                 AND scope.name = department.campus
                                WHERE section_row.campus_scope_id IS NULL
                                  AND department.campus IS NOT NULL
                                  AND department.campus <> ''
                                GROUP BY section_row.id
                                HAVING COUNT(DISTINCT scope.id) = 1
                            ) AS matched
                            WHERE section.id = matched.id
                        """))
                else:
                    conn.execute(text("""
                        UPDATE sections
                        SET campus_scope_id = (
                            SELECT MIN(student.campus_scope_id)
                            FROM enrollments AS enrollment
                            JOIN students AS student
                              ON student.id = enrollment.student_id
                             AND student.tenant_id = sections.tenant_id
                            WHERE enrollment.section_id = sections.id
                              AND enrollment.tenant_id = sections.tenant_id
                              AND enrollment.status = 'enrolled'
                              AND student.campus_scope_id IS NOT NULL
                        )
                        WHERE campus_scope_id IS NULL
                          AND 1 = (
                            SELECT COUNT(DISTINCT student.campus_scope_id)
                            FROM enrollments AS enrollment
                            JOIN students AS student
                              ON student.id = enrollment.student_id
                             AND student.tenant_id = sections.tenant_id
                            WHERE enrollment.section_id = sections.id
                              AND enrollment.tenant_id = sections.tenant_id
                              AND enrollment.status = 'enrolled'
                              AND student.campus_scope_id IS NOT NULL
                          )
                    """))
                    if inspector.has_table("departments"):
                        conn.execute(text("""
                            UPDATE sections
                            SET campus_scope_id = (
                                SELECT MIN(scope.id)
                                FROM departments AS department
                                JOIN org_scopes AS scope
                                  ON scope.tenant_id = sections.tenant_id
                                 AND scope.level = 'campus'
                                 AND scope.name = department.campus
                            WHERE department.id = sections.dept_id
                                  AND department.tenant_id = sections.tenant_id
                                  AND department.campus IS NOT NULL
                                  AND department.campus <> ''
                            )
                            WHERE campus_scope_id IS NULL
                              AND 1 = (
                                SELECT COUNT(DISTINCT scope.id)
                                FROM departments AS department
                                JOIN org_scopes AS scope
                                  ON scope.tenant_id = sections.tenant_id
                                 AND scope.level = 'campus'
                                 AND scope.name = department.campus
                                WHERE department.id = sections.dept_id
                                  AND department.tenant_id = sections.tenant_id
                                  AND department.campus IS NOT NULL
                                  AND department.campus <> ''
                              )
                        """))
            # A historical complaint has no reliable descriptive campus field.
            # Backfill it only when its raised_by value exactly matches a
            # tenant-local student roll number with one unambiguous canonical
            # campus.  All other legacy rows stay unassigned and therefore
            # fail closed for campus-scoped readers.
            if inspector.has_table("complaints") and inspector.has_table("students"):
                if conn.dialect.name == "postgresql":
                    conn.execute(text("""
                        UPDATE complaints AS complaint
                        SET campus_scope_id = match.campus_scope_id
                        FROM (
                            SELECT complaint_row.id, MIN(student.campus_scope_id) AS campus_scope_id
                            FROM complaints AS complaint_row
                            JOIN students AS student
                              ON student.tenant_id = complaint_row.tenant_id
                             AND student.roll_no = complaint_row.raised_by
                            WHERE complaint_row.campus_scope_id IS NULL
                              AND student.campus_scope_id IS NOT NULL
                            GROUP BY complaint_row.id
                            HAVING COUNT(DISTINCT student.campus_scope_id) = 1
                        ) AS match
                        WHERE complaint.id = match.id
                    """))
                else:
                    conn.execute(text("""
                        UPDATE complaints
                        SET campus_scope_id = (
                            SELECT MIN(student.campus_scope_id)
                            FROM students AS student
                            WHERE student.tenant_id = complaints.tenant_id
                              AND student.roll_no = complaints.raised_by
                              AND student.campus_scope_id IS NOT NULL
                            GROUP BY student.roll_no
                            HAVING COUNT(DISTINCT student.campus_scope_id) = 1
                        )
                        WHERE campus_scope_id IS NULL
                          AND EXISTS (
                            SELECT 1 FROM students AS student
                            WHERE student.tenant_id = complaints.tenant_id
                              AND student.roll_no = complaints.raised_by
                              AND student.campus_scope_id IS NOT NULL
                            GROUP BY student.roll_no
                            HAVING COUNT(DISTINCT student.campus_scope_id) = 1
                          )
                    """))
            # Transport and research predate canonical campus ownership and
            # have no display-campus column.  They can be assigned only when
            # a tenant has exactly one campus scope; a multi-campus tenant's
            # legacy records remain deliberately unassigned rather than being
            # guessed as Main Campus.
            for table_name in ("transport_routes", "research_projects"):
                if not inspector.has_table(table_name):
                    continue
                index_name = f"ix_{table_name}_campus_scope_id"
                indexes = {index["name"] for index in inspect(conn).get_indexes(table_name)}
                if index_name not in indexes:
                    conn.execute(text(f"CREATE INDEX {index_name} ON {table_name} (campus_scope_id)"))
                if conn.dialect.name == "postgresql":
                    constraint_name = f"fk_{table_name}_campus_scope"
                    foreign_keys = {fk.get("name") for fk in inspect(conn).get_foreign_keys(table_name)}
                    if constraint_name not in foreign_keys:
                        conn.execute(text(f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} FOREIGN KEY (campus_scope_id) REFERENCES org_scopes (id)"))
                    conn.execute(text(f"""
                        UPDATE {table_name} AS record
                        SET campus_scope_id = scope.id
                        FROM org_scopes AS scope
                        WHERE record.campus_scope_id IS NULL
                          AND scope.tenant_id = record.tenant_id
                          AND scope.level = 'campus'
                          AND 1 = (SELECT COUNT(*) FROM org_scopes only_scope
                                   WHERE only_scope.tenant_id = record.tenant_id
                                     AND only_scope.level = 'campus')
                    """))
                else:
                    conn.execute(text(f"""
                        UPDATE {table_name}
                        SET campus_scope_id = (SELECT scope.id FROM org_scopes AS scope
                                               WHERE scope.tenant_id = {table_name}.tenant_id
                                                 AND scope.level = 'campus')
                        WHERE campus_scope_id IS NULL
                          AND 1 = (SELECT COUNT(*) FROM org_scopes only_scope
                                   WHERE only_scope.tenant_id = {table_name}.tenant_id
                                     AND only_scope.level = 'campus')
                    """))
            if inspector.has_table("leave_requests") and inspector.has_table("staff_members"):
                if conn.dialect.name == "postgresql":
                    conn.execute(text("""
                        UPDATE leave_requests AS leave_record
                        SET campus_scope_id = staff.campus_scope_id
                        FROM staff_members AS staff
                        WHERE leave_record.campus_scope_id IS NULL
                          AND leave_record.staff_id = staff.id
                          AND leave_record.tenant_id = staff.tenant_id
                          AND staff.campus_scope_id IS NOT NULL
                    """))
                else:
                    conn.execute(text("""
                        UPDATE leave_requests
                        SET campus_scope_id = (SELECT staff.campus_scope_id FROM staff_members AS staff
                                               WHERE staff.id = leave_requests.staff_id
                                                 AND staff.tenant_id = leave_requests.tenant_id)
                        WHERE campus_scope_id IS NULL AND EXISTS
                          (SELECT 1 FROM staff_members AS staff WHERE staff.id = leave_requests.staff_id
                           AND staff.tenant_id = leave_requests.tenant_id AND staff.campus_scope_id IS NOT NULL)
                    """))


def office(n: int) -> dict:
    for o in OFFICES:
        if o["n"] == n:
            return o
    return {}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _ensure_course_columns():
    """Small additive migration for the course-catalog fields introduced after v1."""
    if not inspect(engine).has_table("courses"):
        return
    wanted = {
        "program_id": "VARCHAR", "regulation": "VARCHAR", "course_type": "VARCHAR",
        "category": "VARCHAR", "ltp": "VARCHAR", "prerequisite": "VARCHAR", "status": "VARCHAR",
    }
    existing = {column["name"] for column in inspect(engine).get_columns("courses")}
    with engine.begin() as connection:
        for name, column_type in wanted.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE courses ADD COLUMN {name} {column_type}"))
        connection.execute(text("UPDATE courses SET regulation = 'R2023' WHERE regulation IS NULL OR regulation = ''"))
        connection.execute(text("UPDATE courses SET course_type = CASE WHEN semester = 7 THEN 'Elective' ELSE 'Core' END WHERE course_type IS NULL OR course_type = ''"))
        connection.execute(text("UPDATE courses SET category = CASE WHEN semester = 7 THEN 'Professional Elective' ELSE 'Professional Core' END WHERE category IS NULL OR category = ''"))
        connection.execute(text("UPDATE courses SET ltp = CASE WHEN credits >= 4 THEN '3-1-0' WHEN credits = 3 THEN '3-0-0' ELSE '2-0-0' END WHERE ltp IS NULL OR ltp = ''"))
        connection.execute(text("UPDATE courses SET status = 'Active' WHERE status IS NULL OR status = ''"))


def _ensure_staff_contact_columns():
    """Add optional faculty contact fields without requiring a database reset."""
    if not inspect(engine).has_table("staff_members"):
        return
    wanted = {"phone": "VARCHAR", "office_hours": "VARCHAR"}
    existing = {column["name"] for column in inspect(engine).get_columns("staff_members")}
    with engine.begin() as connection:
        for name, column_type in wanted.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE staff_members ADD COLUMN {name} {column_type}"))


def level_privileged(level: int) -> bool:
    # MFA for staff & privileged roles (Document §7 step 3) — students/parents optional.
    return level <= 7


# Demo username for each office head (matches the login screen's demo accounts).
DEMO_USERNAMES = {
    1: "chairman", 2: "vice_chairman", 3: "campus_head", 4: "principal",
    5: "vice_principal", 6: "dean_academics", 7: "dean_administration",
    8: "dean_student_affairs", 9: "dean_rd_iqac", 10: "hod", 11: "professor",
    12: "associate_professor", 13: "assistant_professor", 14: "lecturer",
    15: "admissions", 16: "exam_controller", 17: "academic_coordinator",
    18: "placement", 19: "librarian", 20: "grievance", 21: "discipline",
    22: "finance_manager", 23: "accounts", 24: "hr_manager", 25: "hr_executive",
    26: "admin_manager", 27: "it_manager", 28: "system_admin", 29: "maintenance",
    30: "hostel_warden", 31: "transport", 32: "purchase", 33: "store",
    34: "security", 35: "front_office", 36: "student", 37: "parent",
    38: "alumni", 39: "external_auditor", 40: "governing_body",
}


# Keep the SQLite test database aligned with the approved model even when an older
# file already exists and startup seed is skipped by tests that use SessionLocal directly.
# The local DB also needs the baseline org-scope and demo-user records that the
# workflow approval path validates against; bootstrap them once at import time.
ensure_additive_schema()


def seed():
    Base.metadata.create_all(engine)
    _ensure_course_columns()
    _ensure_staff_contact_columns()
    ensure_additive_schema()
    s = SessionLocal()
    try:
        # Tenant + scope tree (Document §6, §11).
        institution = s.get(Institution, "inst_icms")
        if not institution:
            institution = Institution(id="inst_icms", name="ICMS University Group")
            s.add(institution)
        if not s.get(Tenant, TENANT):
            s.add(Tenant(id=TENANT, institution_id=institution.id, name="ICMS University Group"))
        else:
            main_tenant = s.get(Tenant, TENANT)
            if not main_tenant.institution_id:
                main_tenant.institution_id = institution.id
        if not s.get(OrgScope, "scope_global"):
            s.add(OrgScope(id="scope_global", tenant_id=TENANT, level="global", name="Group"))
        if not s.get(OrgScope, "scope_univ"):
            s.add(OrgScope(id="scope_univ", tenant_id=TENANT, level="university",
                           name="University", parent_id="scope_global"))
        for c in CAMPUS_SCOPES:
            sid = f"scope_{slug(c)}"
            if not s.get(OrgScope, sid):
                s.add(OrgScope(id=sid, tenant_id=TENANT, level="campus",
                               name=c, parent_id="scope_univ"))

        # Permissions catalog.
        for v in VERBS:
            pid = f"perm_{v}"
            if not s.get(Permission, pid):
                s.add(Permission(id=pid, resource="*", action=v))

        # Approval limits (Document §10).
        i = 0
        for scope_level, procs in APPROVAL_LIMITS.items():
            for proc, thr in procs.items():
                i += 1
                lid = f"lim_{i}"
                if not s.get(ApprovalLimit, lid):
                    s.add(ApprovalLimit(id=lid, tenant_id=TENANT,
                                        scope_level=scope_level, process=proc, threshold=thr))

        # Offices -> Roles -> RolePermissions (from RBAC matrix).
        for o in OFFICES:
            level = o["level"]
            level_name = LEVELS[str(level)]["name"]
            for idx, role_name in enumerate(o["internal_roles"]):
                role_id = f"role_{o['n']}_{idx}"
                if not s.get(Role, role_id):
                    s.add(Role(id=role_id, tenant_id=TENANT, office_n=o["n"],
                               name=role_name, category=level_name))
                for v in VERBS:
                    auth = rbac_for(o["n"], level, v)
                    rpid = f"rp_{o['n']}_{idx}_{v}"
                    if not s.get(RolePermission, rpid):
                        s.add(RolePermission(id=rpid, role_id=role_id,
                                             office_n=o["n"], action=v, authority=auth))

        # Flush the shared reference data before inserting rows that depend on it.
        # SessionLocal has autoflush disabled, so PostgreSQL cannot otherwise
        # guarantee that foreign-key parents are inserted first.
        s.flush()

        # Demo people: one head account per office (password: demo123).
        for o in OFFICES:
            n = o["n"]
            uname = DEMO_USERNAMES.get(n, f"office_{n}")
            head_role = o["internal_roles"][0]
            pid = f"person_{n}"
            if not s.get(Person, pid):
                s.add(Person(id=pid, tenant_id=TENANT, name=head_role,
                             email=f"{uname}@icms.edu", contact="+91-00000-00000"))

        s.flush()

        # Designations and users depend on the people inserted above.
        for o in OFFICES:
            n = o["n"]
            uname = DEMO_USERNAMES.get(n, f"office_{n}")
            head_role = o["internal_roles"][0]
            pid = f"person_{n}"
            desg_id = f"desg_{n}"
            if not s.get(Designation, desg_id):
                s.add(Designation(id=desg_id, person_id=pid, title=head_role,
                                  employee_id=f"EMP{n:03d}"))
            uid = f"user_{n}"
            if not s.get(User, uid):
                s.add(User(id=uid, tenant_id=TENANT, person_id=pid, username=uname,
                           password_hash=pwhash("demo123"),
                           mfa_enabled=level_privileged(o["level"]),
                           office_n=n, role=head_role, scope_level=scope_for(n),
                           scope_ref="scope_global"))

        s.flush()

        # User-role links depend on both users and roles.
        for o in OFFICES:
            n = o["n"]
            uid = f"user_{n}"
            urid = f"ur_{n}"
            if not s.get(UserRole, urid):
                s.add(UserRole(id=urid, user_id=uid, role_id=f"role_{n}_0",
                               org_scope_id="scope_global"))

        # Governance identities are institution authorities. Every operational
        # identity also receives an explicit server-side Main Campus membership.
        s.flush()
        for office_n in range(1, len(OFFICES) + 1):
            scope_id = None if office_n in (1, 2) else "scope_main_campus"
            jurisdiction = "institution" if office_n in (1, 2) else "scope"
            user = s.get(User, f"user_{office_n}")
            membership_id = f"membership_{office_n}_main"
            if user and not s.get(AuthorityMembership, membership_id):
                s.add(AuthorityMembership(id=membership_id, user_id=user.id,
                      institution_id=institution.id, tenant_id=None if jurisdiction == "institution" else TENANT,
                      org_scope_id=scope_id, office_n=office_n, role_template_key=f"office_{office_n}",
                      jurisdiction_type=jurisdiction, status="active"))

        # Explicitly repair only the two original Main Campus demo identities.
        # This is legacy seed maintenance, not a fallback for branch users.
        # Runtime authorization resolves their AuthorityMembership scope.
        principal = s.get(User, "user_4")
        if principal and principal.tenant_id == TENANT and principal.scope_ref == "scope_global":
            principal.scope_ref = "scope_main_campus"

        campus_head = s.get(User, "user_3")
        if campus_head and campus_head.tenant_id == TENANT and campus_head.scope_ref == "scope_global":
            campus_head.scope_ref = "scope_main_campus"

        # Repair only legacy branch accounts created before the onboarding
        # lifecycle existed.  Main Campus demo accounts are deliberately not
        # touched; they retain their established demo credentials.
        branch_tenants = [row.tenant_id for row in s.query(BranchOrganization).all()]
        if branch_tenants:
            (s.query(User).filter(User.tenant_id.in_(branch_tenants),
                                  User.onboarding_completed_at.is_(None),
                                  User.last_login_at.is_(None),
                                  User.status == "active")
             .update({User.status: "invited"}, synchronize_session=False))

        s.commit()
        return {"status": "seeded", "offices": len(OFFICES),
                "campuses": len(CAMPUS_SCOPES),
                "roles": s.query(Role).count(), "users": s.query(User).count()}
    finally:
        s.close()


# Schema creation is safe for every environment. Demo/reference seeding is not:
# production must never add or update operational records merely because the
# service was restarted.
ensure_additive_schema()
if os.getenv("ENVIRONMENT", "production").lower() == "development":
    try:
        seed()
    except Exception as e:
        # Development seeding may partially fail on import; the schema remains
        # available and the development startup retry can report the failure.
        import sys
        print(f"Warning: development seed at import time partially failed: {e}", file=sys.stderr)
