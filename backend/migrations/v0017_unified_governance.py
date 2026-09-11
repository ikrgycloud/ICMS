import json
from sqlalchemy import inspect, text

VERSION = "0017_unified_governance"


def upgrade(engine):
    statements = [
        """CREATE TABLE IF NOT EXISTS governance_policies (
            id VARCHAR PRIMARY KEY, tenant_id VARCHAR, proposal_type VARCHAR UNIQUE,
            allowed_transitions_json TEXT DEFAULT '{}', required_reason_states_json TEXT DEFAULT '[]',
            reviewer_office_n INTEGER, active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS governance_documents (
            id VARCHAR PRIMARY KEY, tenant_id VARCHAR, owner_entity_type VARCHAR, owner_entity_id VARCHAR,
            file_name VARCHAR, mime_type VARCHAR, size_bytes INTEGER DEFAULT 0, object_storage_key VARCHAR,
            checksum VARCHAR UNIQUE, version INTEGER DEFAULT 1, access_scope VARCHAR DEFAULT 'governance',
            uploaded_by VARCHAR, uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, immutable BOOLEAN DEFAULT TRUE)""",
        """CREATE TABLE IF NOT EXISTS governance_notification_outcomes (
            id VARCHAR PRIMARY KEY, tenant_id VARCHAR, notification_id VARCHAR, workflow_id VARCHAR,
            recipient_id VARCHAR, event VARCHAR, outcome VARCHAR DEFAULT 'queued', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS controlled_academic_records (
            id VARCHAR PRIMARY KEY, tenant_id VARCHAR, record_type VARCHAR, entity_ref VARCHAR, version INTEGER DEFAULT 1,
            status VARCHAR DEFAULT 'effective', effective_from TIMESTAMP, effective_to TIMESTAMP, payload_json TEXT DEFAULT '{}',
            source_proposal_id VARCHAR, created_by VARCHAR, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS timetable_exception_workflows (
            id VARCHAR PRIMARY KEY, tenant_id VARCHAR, exception_id VARCHAR, state VARCHAR DEFAULT 'detected',
            assigned_to VARCHAR DEFAULT '', evidence_document_ids TEXT DEFAULT '[]', status_version INTEGER DEFAULT 0,
            reason TEXT DEFAULT '', updated_by VARCHAR DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
        inspector = inspect(engine)
        for table, column, definition in (
            ("audit_logs", "entity_version", "INTEGER DEFAULT 0"),
            ("audit_logs", "workflow_id", "VARCHAR"),
            ("audit_logs", "evidence_document_ids", "TEXT DEFAULT '[]'"),
            ("academic_proposals", "assigned_reviewer_id", "VARCHAR"),
        ):
            if inspector.has_table(table) and column not in {item["name"] for item in inspector.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        policies = {
            "calendar": {"DRAFT": ["SUBMITTED"], "SUBMITTED": ["UNDER_REVIEW", "CLARIFICATION_REQUIRED", "RETURNED", "APPROVED", "REJECTED", "ESCALATED"], "UNDER_REVIEW": ["CLARIFICATION_REQUIRED", "RETURNED", "APPROVED", "REJECTED", "ESCALATED"], "CLARIFICATION_REQUIRED": ["RESUBMITTED"], "RETURNED": ["RESUBMITTED"], "RESUBMITTED": ["UNDER_REVIEW", "APPROVED", "REJECTED", "ESCALATED"], "APPROVED": ["IMPLEMENTED"], "IMPLEMENTED": ["ARCHIVED"]},
            "curriculum": {"DRAFT": ["SUBMITTED"], "SUBMITTED": ["UNDER_REVIEW", "CLARIFICATION_REQUIRED", "RETURNED", "APPROVED", "REJECTED", "ESCALATED"], "UNDER_REVIEW": ["CLARIFICATION_REQUIRED", "RETURNED", "APPROVED", "REJECTED", "ESCALATED"], "CLARIFICATION_REQUIRED": ["RESUBMITTED"], "RETURNED": ["RESUBMITTED"], "RESUBMITTED": ["UNDER_REVIEW", "APPROVED", "REJECTED", "ESCALATED"], "APPROVED": ["IMPLEMENTED"], "IMPLEMENTED": ["ARCHIVED"]},
            "program": {"DRAFT": ["SUBMITTED"], "SUBMITTED": ["UNDER_REVIEW", "CLARIFICATION_REQUIRED", "RETURNED", "APPROVED", "REJECTED", "ESCALATED"], "UNDER_REVIEW": ["CLARIFICATION_REQUIRED", "RETURNED", "APPROVED", "REJECTED", "ESCALATED"], "CLARIFICATION_REQUIRED": ["RESUBMITTED"], "RETURNED": ["RESUBMITTED"], "RESUBMITTED": ["UNDER_REVIEW", "APPROVED", "REJECTED", "ESCALATED"], "APPROVED": ["IMPLEMENTED"], "IMPLEMENTED": ["ARCHIVED"]},
            "allocation": {"DRAFT": ["SUBMITTED"], "SUBMITTED": ["UNDER_REVIEW", "RETURNED", "APPROVED", "REJECTED", "ESCALATED"], "UNDER_REVIEW": ["RETURNED", "APPROVED", "REJECTED", "ESCALATED"], "RETURNED": ["RESUBMITTED"], "RESUBMITTED": ["UNDER_REVIEW", "APPROVED", "REJECTED", "ESCALATED"], "APPROVED": ["IMPLEMENTED"], "IMPLEMENTED": ["ARCHIVED"]},
        }
        for kind, transitions in policies.items():
            exists = conn.execute(text("SELECT 1 FROM governance_policies WHERE proposal_type = :kind"), {"kind": kind}).first()
            if not exists:
                conn.execute(text("INSERT INTO governance_policies (id, tenant_id, proposal_type, allowed_transitions_json, required_reason_states_json, reviewer_office_n) VALUES (:id, 't_main', :kind, :transitions, :reasons, 6)"), {"id": f"policy_{kind}", "kind": kind, "transitions": json.dumps(transitions), "reasons": json.dumps(["CLARIFICATION_REQUIRED", "RETURNED", "REJECTED", "ESCALATED", "ARCHIVED"])})


def downgrade(engine):
    return None