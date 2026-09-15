"""Persist Dean Academics organisational assignments.

The migration is additive and intentionally does not infer or create broad
assignments from legacy users.  An institution administrator must explicitly
assign production Dean scope after deployment.
"""
from sqlalchemy import text

VERSION = "0038_dean_scope_assignments"


def upgrade(engine):
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dean_scope_assignments (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                dean_user_id VARCHAR NOT NULL,
                school_id VARCHAR NULL,
                dept_id VARCHAR NULL,
                program_id VARCHAR NULL,
                section_id VARCHAR NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                effective_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                effective_to TIMESTAMP NULL,
                created_by VARCHAR NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_dean_scope_assignment_actor ON dean_scope_assignments (tenant_id, dean_user_id, active)"))
        # Role definitions are policy data, not demo users.  Insert them for
        # every existing tenant without creating an account or organisational
        # assignment; a System Administrator must still provision both.
        conn.execute(text("""
            INSERT INTO roles (id, tenant_id, office_n, name, category)
            SELECT 'role_program_coordinator_' || t.id, t.id, 41, 'Program Coordinator', 'Administration (Academic & Student)'
            FROM tenants t
            WHERE NOT EXISTS (SELECT 1 FROM roles r WHERE r.tenant_id = t.id AND r.office_n = 41)
        """))
        conn.execute(text("""
            INSERT INTO roles (id, tenant_id, office_n, name, category)
            SELECT 'role_academic_office_' || t.id, t.id, 42, 'Academic Office Officer', 'Administration (Academic & Student)'
            FROM tenants t
            WHERE NOT EXISTS (SELECT 1 FROM roles r WHERE r.tenant_id = t.id AND r.office_n = 42)
        """))
        conn.execute(text("""
            INSERT INTO roles (id, tenant_id, office_n, name, category)
            SELECT 'role_timetable_coordinator_' || t.id, t.id, 43, 'Timetable Coordinator', 'Administration (Academic & Student)'
            FROM tenants t
            WHERE NOT EXISTS (SELECT 1 FROM roles r WHERE r.tenant_id = t.id AND r.office_n = 43)
        """))


def downgrade(engine):
    return None
