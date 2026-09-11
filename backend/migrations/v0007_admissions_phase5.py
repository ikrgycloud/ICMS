"""Additive Phase 5 admission finance structures, challans, and clearance totals."""
from sqlalchemy import inspect, text

VERSION = "0007_admissions_phase5"


def upgrade(engine):
    import domain_models
    from models import Base
    Base.metadata.create_all(engine)
    additions = {
        "admission_finance_clearances": [
            ("total_payable", "FLOAT DEFAULT 0"), ("total_paid", "FLOAT DEFAULT 0"),
            ("total_waived", "FLOAT DEFAULT 0"), ("balance", "FLOAT DEFAULT 0"),
            ("cleared_at", "TIMESTAMP"),
        ],
    }
    with engine.begin() as conn:
        inspector = inspect(conn)
        for table, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fee_structures_scope ON fee_structures (tenant_id, academic_year, campus, program_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_applicant_fee_assignment_application ON applicant_fee_assignments (application_id, invoice_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_admission_challans_application ON admission_challans (application_id, invoice_id)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_students_tenant_roll_no ON students (tenant_id, roll_no)"))


def downgrade(engine):
    return None
