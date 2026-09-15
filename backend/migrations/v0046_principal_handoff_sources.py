"""Add source tables/columns used by Principal domain handoffs."""
from sqlalchemy import inspect, text

VERSION = "0046_principal_handoff_sources"


def upgrade(engine):
    inspector = inspect(engine)
    with engine.begin() as conn:
        if inspector.has_table("complaints"):
            columns = {column["name"] for column in inspector.get_columns("complaints")}
            for name, definition in (("decision", "VARCHAR DEFAULT ''"), ("decided_by", "VARCHAR DEFAULT ''"), ("decided_at", "TIMESTAMP")):
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE complaints ADD COLUMN {name} {definition}"))
        if not inspector.has_table("attendance_condonation_requests"):
            conn.execute(text("CREATE TABLE attendance_condonation_requests (id VARCHAR PRIMARY KEY, tenant_id VARCHAR, student_id VARCHAR, section_id VARCHAR, attendance_percent FLOAT DEFAULT 0, shortage_percent FLOAT DEFAULT 0, reason TEXT DEFAULT '', requested_by VARCHAR, workflow_id VARCHAR UNIQUE, status VARCHAR DEFAULT 'submitted', decided_by VARCHAR DEFAULT '', decided_at TIMESTAMP, invoice_id VARCHAR, created_at TIMESTAMP, updated_at TIMESTAMP)"))
        if not inspector.has_table("hr_promotion_requests"):
            conn.execute(text("CREATE TABLE hr_promotion_requests (id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, staff_id VARCHAR NOT NULL, current_title VARCHAR DEFAULT '', proposed_title VARCHAR NOT NULL, effective_date TIMESTAMP NOT NULL, status VARCHAR DEFAULT 'SUBMITTED', workflow_id VARCHAR, requested_by VARCHAR NOT NULL, decided_by VARCHAR DEFAULT '', created_at TIMESTAMP, updated_at TIMESTAMP)"))


def downgrade(engine):
    return None