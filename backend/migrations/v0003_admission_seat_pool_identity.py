"""Enforce the immutable identity of a configured admission seat pool."""
from sqlalchemy import text

VERSION = "0003_admission_seat_pool_identity"


def upgrade(engine):
    # Works on both supported engines.  The index is additive; any pre-existing
    # duplicates are reported by the database rather than silently discarded.
    with engine.begin() as conn:
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_admission_seat_pool_scope "
                          "ON admission_seat_pools (tenant_id, cycle_id, campus, program_id, quota_id, category_code, intake_key)"))


def downgrade(engine):
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX IF EXISTS uq_admission_seat_pool_scope"))
