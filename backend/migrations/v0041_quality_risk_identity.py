"""Add stable source identity for derived academic risks."""
from sqlalchemy import inspect, text

VERSION = "0041_quality_risk_identity"


def upgrade(engine):
    inspector = inspect(engine)
    if not inspector.has_table("academic_quality_reviews"):
        return
    columns = {column["name"] for column in inspector.get_columns("academic_quality_reviews")}
    with engine.begin() as conn:
        if "source_key" not in columns:
            conn.execute(text("ALTER TABLE academic_quality_reviews ADD COLUMN source_key VARCHAR DEFAULT ''"))
        # One active governed review may exist for a detected risk. Closed
        # reviews remain historical evidence and do not block a later cycle.
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_quality_reviews_active_source ON academic_quality_reviews (tenant_id, source_key) WHERE source_key <> '' AND state <> 'CLOSED'"))


def downgrade(engine):
    return None
