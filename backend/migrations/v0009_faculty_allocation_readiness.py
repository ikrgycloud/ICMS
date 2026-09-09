"""Faculty allocation and timetable readiness entities."""
from sqlalchemy import text
VERSION = "0009_faculty_allocation_readiness"
def upgrade(engine):
    statements = [
        """CREATE TABLE IF NOT EXISTS faculty_allocations (id VARCHAR PRIMARY KEY, tenant_id VARCHAR, section_id VARCHAR NOT NULL, faculty_person_id VARCHAR NOT NULL, term VARCHAR, workload_units FLOAT DEFAULT 0, status VARCHAR DEFAULT 'PROPOSED', proposal_id VARCHAR, created_by VARCHAR DEFAULT '', approved_by VARCHAR DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS timetable_exceptions (id VARCHAR PRIMARY KEY, tenant_id VARCHAR, section_id VARCHAR, kind VARCHAR, severity VARCHAR DEFAULT 'warning', message TEXT, status VARCHAR DEFAULT 'OPEN', detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, resolved_at TIMESTAMP, resolved_by VARCHAR DEFAULT '')""",
        "CREATE INDEX IF NOT EXISTS ix_faculty_allocations_term ON faculty_allocations (term, faculty_person_id)",
        "CREATE INDEX IF NOT EXISTS ix_timetable_exceptions_status ON timetable_exceptions (status, severity)",
    ]
    with engine.begin() as conn:
        for statement in statements: conn.execute(text(statement))
