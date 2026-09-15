"""Versioned academic-governance proposal foundation."""
from sqlalchemy import text

VERSION = "0008_academic_governance"


def upgrade(engine):
    statements = [
        """CREATE TABLE IF NOT EXISTS academic_proposals (
            id VARCHAR PRIMARY KEY, tenant_id VARCHAR, proposal_type VARCHAR, title VARCHAR,
            scope_level VARCHAR DEFAULT 'institution', scope_ref VARCHAR DEFAULT '',
            state VARCHAR DEFAULT 'DRAFT', version_no INTEGER DEFAULT 1, status_version INTEGER DEFAULT 0,
            submitted_by VARCHAR DEFAULT '', submitted_office_n INTEGER, assigned_to_office_n INTEGER,
            due_at TIMESTAMP, escalated_to_office_n INTEGER, implementation_ref VARCHAR DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS academic_proposal_versions (
            id VARCHAR PRIMARY KEY, tenant_id VARCHAR, proposal_id VARCHAR NOT NULL,
            version_no INTEGER NOT NULL, payload_json TEXT DEFAULT '{}', rationale TEXT DEFAULT '',
            created_by VARCHAR DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_academic_proposal_version UNIQUE (proposal_id, version_no)
        )""",
        """CREATE TABLE IF NOT EXISTS academic_proposal_events (
            id VARCHAR PRIMARY KEY, tenant_id VARCHAR, proposal_id VARCHAR NOT NULL,
            from_state VARCHAR DEFAULT '', to_state VARCHAR NOT NULL, actor_id VARCHAR,
            actor_office_n INTEGER, reason TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS ix_academic_proposals_type_state ON academic_proposals (proposal_type, state)",
        "CREATE INDEX IF NOT EXISTS ix_academic_proposal_events_proposal ON academic_proposal_events (proposal_id, created_at)",
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
