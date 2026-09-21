VERSION = "0065_department_hod_appointments"


def upgrade(engine):
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS department_hod_appointments (
              id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, department_id VARCHAR NOT NULL,
              staff_id VARCHAR NOT NULL, requested_by VARCHAR NOT NULL, status VARCHAR NOT NULL,
              rationale TEXT DEFAULT '', effective_from TIMESTAMP NOT NULL, decided_by VARCHAR,
              decided_at TIMESTAMP, decision_reason TEXT DEFAULT '', status_version INTEGER NOT NULL DEFAULT 1,
              created_at TIMESTAMP NOT NULL, updated_at TIMESTAMP NOT NULL
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_hod_appointments_tenant_dept_status ON department_hod_appointments (tenant_id, department_id, status)"))


def downgrade(engine):
    return None
