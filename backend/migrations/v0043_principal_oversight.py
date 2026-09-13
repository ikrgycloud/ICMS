"""Add campus-scoped Principal compliance and escalation records."""
from sqlalchemy import inspect, text

VERSION = "0043_principal_oversight"


def upgrade(engine):
    inspector = inspect(engine)
    with engine.begin() as conn:
        if not inspector.has_table("compliance_requirements"):
            conn.execute(text("CREATE TABLE compliance_requirements (id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, campus VARCHAR DEFAULT '', reference_code VARCHAR NOT NULL UNIQUE, title VARCHAR NOT NULL, description TEXT DEFAULT '', category VARCHAR DEFAULT '', responsible_department VARCHAR DEFAULT '', priority VARCHAR DEFAULT 'normal', status VARCHAR DEFAULT 'OPEN', due_date DATE, evidence_reference TEXT DEFAULT '', created_by VARCHAR DEFAULT '', created_at TIMESTAMP, updated_at TIMESTAMP)"))
            conn.execute(text("CREATE INDEX ix_compliance_requirements_scope ON compliance_requirements (tenant_id, campus)"))
        if not inspector.has_table("escalation_records"):
            conn.execute(text("CREATE TABLE escalation_records (id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, campus VARCHAR DEFAULT '', source_type VARCHAR DEFAULT '', source_ref VARCHAR DEFAULT '', title VARCHAR NOT NULL, reason TEXT DEFAULT '', priority VARCHAR DEFAULT 'normal', destination_office_n INTEGER NOT NULL, status VARCHAR DEFAULT 'DRAFT', created_by VARCHAR NOT NULL, received_by VARCHAR DEFAULT '', resolved_by VARCHAR DEFAULT '', created_at TIMESTAMP, updated_at TIMESTAMP)"))
            conn.execute(text("CREATE INDEX ix_escalation_records_scope ON escalation_records (tenant_id, campus, status)"))
        if not inspector.has_table("escalation_events"):
            conn.execute(text("CREATE TABLE escalation_events (id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, escalation_id VARCHAR NOT NULL, actor_id VARCHAR NOT NULL, event_type VARCHAR NOT NULL, reason TEXT DEFAULT '', previous_status VARCHAR DEFAULT '', new_status VARCHAR DEFAULT '', created_at TIMESTAMP)"))
            conn.execute(text("CREATE INDEX ix_escalation_events_record ON escalation_events (escalation_id, created_at)"))


def downgrade(engine):
    return None
