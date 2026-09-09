"""Classify legacy invoices that predate fee-head-based fee structures."""
from sqlalchemy import inspect, text

VERSION = "0010_classify_legacy_fee_invoices"


def upgrade(engine):
    with engine.begin() as conn:
        if not inspect(conn).has_table("fee_invoices") or not inspect(conn).has_table("fee_heads"):
            return

        # Old student invoices represented the complete tuition charge in one
        # record. Admission invoices likewise represented the admission fee.
        # Assign only unclassified rows so explicit/newer classifications win.
        conn.execute(text("""
            UPDATE fee_invoices
            SET fee_head_id = (
                SELECT id FROM fee_heads
                WHERE fee_heads.tenant_id = fee_invoices.tenant_id
                  AND fee_heads.code = CASE
                      WHEN fee_invoices.invoice_type = 'admission_fee' THEN 'ADMISSION'
                      ELSE 'TUITION'
                  END
                LIMIT 1
            )
            WHERE fee_head_id IS NULL
              AND fee_structure_id IS NULL
              AND (invoice_type = 'admission_fee' OR student_id IS NOT NULL)
        """))
