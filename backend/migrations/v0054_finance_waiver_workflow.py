"""Create the source record used by the governed fee-waiver workflow."""
from sqlalchemy import inspect, text

VERSION = "0054_finance_waiver_workflow"


def upgrade(engine):
    if inspect(engine).has_table("fee_waiver_requests"):
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE fee_waiver_requests (
                id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, invoice_id VARCHAR NOT NULL,
                student_id VARCHAR NOT NULL, amount FLOAT NOT NULL DEFAULT 0,
                reason TEXT NOT NULL DEFAULT '', status VARCHAR NOT NULL DEFAULT 'pending_principal_approval',
                workflow_id VARCHAR UNIQUE, requested_by VARCHAR NOT NULL DEFAULT '',
                decided_by VARCHAR NOT NULL DEFAULT '', executed_by VARCHAR NOT NULL DEFAULT '',
                decision_remarks TEXT NOT NULL DEFAULT '', created_at TIMESTAMP,
                decided_at TIMESTAMP, executed_at TIMESTAMP
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fee_waiver_requests_tenant_id ON fee_waiver_requests (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fee_waiver_requests_invoice_id ON fee_waiver_requests (invoice_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fee_waiver_requests_status ON fee_waiver_requests (status)"))


def downgrade(engine):
    return None
