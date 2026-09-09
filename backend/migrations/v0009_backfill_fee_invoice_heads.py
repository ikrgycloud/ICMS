"""Attach legacy published fee invoices to the Fee Head that created them."""
from sqlalchemy import inspect, text

VERSION = "0009_backfill_fee_invoice_heads"


def upgrade(engine):
    with engine.begin() as conn:
        required = {"fee_invoices", "fee_structure_lines"}
        if not all(inspect(conn).has_table(table) for table in required):
            return

        # Published structures identify each generated invoice with the source
        # fee-line ID in its term.  Reconstruct the missing category link for
        # records created before fee_head_id was persisted on invoices.
        invoices = conn.execute(text("""
            SELECT id, term, fee_structure_id
            FROM fee_invoices
            WHERE fee_head_id IS NULL
              AND fee_structure_id IS NOT NULL
        """)).mappings().all()
        lines = conn.execute(text("""
            SELECT id, fee_structure_id, fee_head_id
            FROM fee_structure_lines
        """)).mappings().all()
        line_heads = {(line["fee_structure_id"], line["id"]): line["fee_head_id"] for line in lines}

        for invoice in invoices:
            marker = ":line:"
            if marker not in (invoice["term"] or ""):
                continue
            line_id = invoice["term"].rsplit(marker, 1)[1]
            head_id = line_heads.get((invoice["fee_structure_id"], line_id))
            if head_id:
                conn.execute(text("UPDATE fee_invoices SET fee_head_id = :head_id WHERE id = :id"),
                             {"head_id": head_id, "id": invoice["id"]})
