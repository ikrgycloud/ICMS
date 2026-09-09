"""Add category link to issued fee invoices."""
from sqlalchemy import inspect, text

VERSION = "0008_category_based_fees"

def upgrade(engine):
    with engine.begin() as conn:
        if not inspect(engine).has_table("fee_invoices"):
            return
        cols = {c["name"] for c in inspect(engine).get_columns("fee_invoices")}
        if "fee_head_id" not in cols:
            conn.execute(text("ALTER TABLE fee_invoices ADD COLUMN fee_head_id VARCHAR"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fee_invoices_fee_head_id ON fee_invoices (fee_head_id)"))
