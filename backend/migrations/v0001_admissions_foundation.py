"""Admissions Phase 1 foundation; additive and safe for existing applications."""
from sqlalchemy import inspect, text

VERSION = "0001_admissions_foundation"


def upgrade(engine):
    # Import registers Phase 1 domain tables on the shared SQLAlchemy metadata.
    import domain_models  # noqa: F401
    from models import Base

    Base.metadata.create_all(engine)
    additions = {
        "applications": [
            ("current_status", "VARCHAR DEFAULT 'SUBMITTED'"),
            ("status_version", "INTEGER DEFAULT 0"),
            ("cycle_id", "VARCHAR"), ("application_no", "VARCHAR"),
            ("phone", "VARCHAR DEFAULT ''"), ("date_of_birth", "DATE"),
            ("gender", "VARCHAR DEFAULT ''"), ("campus", "VARCHAR DEFAULT ''"),
            ("category_code", "VARCHAR DEFAULT ''"), ("quota_code", "VARCHAR DEFAULT ''"),
            ("selected_program_id", "VARCHAR"), ("allocated_program_id", "VARCHAR"),
            ("submitted_at", "TIMESTAMP"),
        ],
        "fee_invoices": [
            ("application_id", "VARCHAR"), ("invoice_type", "VARCHAR DEFAULT 'student_fee'"),
            ("challan_no", "VARCHAR DEFAULT ''"), ("issued_at", "TIMESTAMP"),
            ("issued_by_user_id", "VARCHAR"),
        ],
        "payments": [
            ("status", "VARCHAR DEFAULT 'recorded'"), ("recorded_by_user_id", "VARCHAR"),
            ("verified_by_user_id", "VARCHAR"), ("verified_at", "TIMESTAMP"),
            ("verification_note", "TEXT DEFAULT ''"),
        ],
    }
    with engine.begin() as conn:
        inspector = inspect(conn)
        for table, columns in additions.items():
            if not inspector.has_table(table):
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        # Legacy lifecycle values remain available in Application.status, while
        # current_status becomes the canonical state for all new transitions.
        conn.execute(text("UPDATE applications SET current_status = CASE lower(coalesce(status, 'submitted')) "
                          "WHEN 'verified' THEN 'DOCUMENT_VERIFIED' WHEN 'offered' THEN 'OFFERED' "
                          "WHEN 'admitted' THEN 'ENROLLED' WHEN 'rejected' THEN 'REJECTED' "
                          "ELSE 'SUBMITTED' END WHERE current_status IS NULL OR current_status = '' "
                          "OR (current_status = 'SUBMITTED' AND lower(coalesce(status, 'submitted')) <> 'submitted')"))


def downgrade(engine):
    # Tables/columns are intentionally retained: SQLite cannot safely drop
    # columns and production admissions records must never be removed by rollback.
    return None
