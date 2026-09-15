"""Normalize legacy governance-policy rows created before active had a default."""
from sqlalchemy import text

VERSION = "0024_governance_policy_repair"


def upgrade(engine):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE governance_policies
            SET active = TRUE
            WHERE active IS NULL
        """))


def downgrade(engine):
    return None
