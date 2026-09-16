"""Campus Head operational records (risk register and report lifecycle)."""
VERSION = "0056_campus_head_domains"


def upgrade(engine):
    # SQLAlchemy metadata creates these tables on new installations. Existing
    # databases use portable CREATE TABLE IF NOT EXISTS statements here.
    statements = [
        """CREATE TABLE IF NOT EXISTS risk_records (
          id VARCHAR(64) PRIMARY KEY, tenant_id VARCHAR(64) NOT NULL,
          campus_scope_id VARCHAR(128) NOT NULL, created_by VARCHAR(128) NOT NULL,
          owner_id VARCHAR(128), category VARCHAR(80) NOT NULL, title VARCHAR(500) NOT NULL,
          description TEXT DEFAULT '', severity VARCHAR(20) NOT NULL, likelihood VARCHAR(40) NOT NULL,
          impact VARCHAR(40) NOT NULL, priority VARCHAR(40) NOT NULL, status VARCHAR(40) DEFAULT 'OPEN',
          source_type VARCHAR(80) DEFAULT 'manual', source_ref VARCHAR(128) DEFAULT '', due_at TIMESTAMP,
          resolved_at TIMESTAMP, closed_at TIMESTAMP, resolution_notes TEXT DEFAULT '', escalated_at TIMESTAMP,
          escalated_by VARCHAR(128), escalation_destination VARCHAR(128) DEFAULT '', escalation_reason TEXT DEFAULT '',
          escalation_workflow_id VARCHAR(128), version_no INTEGER NOT NULL DEFAULT 1,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS campus_reports (
          id VARCHAR(64) PRIMARY KEY, tenant_id VARCHAR(64) NOT NULL, campus_scope_id VARCHAR(128) NOT NULL,
          created_by VARCHAR(128) NOT NULL, report_type VARCHAR(80) NOT NULL, period_start DATE NOT NULL,
          period_end DATE NOT NULL, title VARCHAR(500) NOT NULL, status VARCHAR(40) DEFAULT 'DRAFT',
          version INTEGER NOT NULL DEFAULT 1, submitted_at TIMESTAMP, returned_at TIMESTAMP, approved_at TIMESTAMP,
          vc_feedback TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS campus_report_snapshots (
          id VARCHAR(64) PRIMARY KEY, report_id VARCHAR(64) NOT NULL, version INTEGER NOT NULL,
          snapshot_payload TEXT DEFAULT '{}', source_as_of TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.exec_driver_sql(statement)
