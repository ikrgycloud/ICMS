"""Repair legacy-state backfill on SQLite databases upgraded by v0001."""
from sqlalchemy import text

VERSION = "0002_repair_legacy_application_status"


def upgrade(engine):
    with engine.begin() as conn:
        conn.execute(text("UPDATE applications SET current_status = CASE lower(coalesce(status, 'submitted')) "
                          "WHEN 'verified' THEN 'DOCUMENT_VERIFIED' WHEN 'offered' THEN 'OFFERED' "
                          "WHEN 'admitted' THEN 'ENROLLED' WHEN 'rejected' THEN 'REJECTED' "
                          "ELSE current_status END "
                          "WHERE current_status = 'SUBMITTED' AND lower(coalesce(status, 'submitted')) <> 'submitted'"))


def downgrade(engine):
    return None
