"""Persist Vice Chairman decisions for the Campus Head report lifecycle."""
VERSION = "0062_campus_report_vc_review"


def upgrade(engine):
    statement = """CREATE TABLE IF NOT EXISTS campus_report_decisions (
      id VARCHAR(64) PRIMARY KEY, tenant_id VARCHAR(64) NOT NULL,
      report_id VARCHAR(64) NOT NULL, report_version INTEGER NOT NULL,
      action VARCHAR(32) NOT NULL, actor_id VARCHAR(128) NOT NULL,
      actor_name VARCHAR(500) NOT NULL, actor_office_n INTEGER NOT NULL,
      reason TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
    with engine.begin() as conn:
        conn.exec_driver_sql(statement)
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_campus_report_decisions_report ON campus_report_decisions (report_id, created_at)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_campus_report_decisions_tenant ON campus_report_decisions (tenant_id)")


def downgrade(engine):
    return None
