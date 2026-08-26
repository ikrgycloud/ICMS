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

from models import (Base, Tenant, OrgScope, Person, User, Role, Permission,
                    RolePermission, ApprovalLimit, UserRole, Designation)
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
        "students": [
            ("blood_group", "VARCHAR DEFAULT ''"),
            ("student_type", "VARCHAR DEFAULT 'Regular'"),
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


def office(n: int) -> dict:
    for o in OFFICES:
        if o["n"] == n:
            return o
    return {}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


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


def seed():
    ensure_additive_schema()
    s = SessionLocal()
    try:
        # Tenant + scope tree (Document §6, §11).
        if not s.get(Tenant, TENANT):
            s.add(Tenant(id=TENANT, name="ICMS University Group"))
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

        # The demo Principal is a campus role.  Older databases were seeded
        # with the global scope for every demo account, which let this account
        # see students belonging to other campuses.  Keep the scope explicit
        # and in the same human-readable form used by Student.campus.
        principal = s.get(User, "user_4")
        if principal and principal.scope_ref == "scope_global":
            principal.scope_ref = CAMPUS_SCOPES[0]

        s.commit()
        return {"status": "seeded", "offices": len(OFFICES),
                "campuses": len(CAMPUS_SCOPES),
                "roles": s.query(Role).count(), "users": s.query(User).count()}
    finally:
        s.close()


def level_privileged(level: int) -> bool:
    # MFA for staff & privileged roles (Document §7 step 3) — students/parents optional.
    return level <= 7
