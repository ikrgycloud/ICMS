"""Governed, campus-scoped authority appointments."""
from sqlalchemy import text

VERSION = "0058_authority_memberships"


def upgrade(engine):
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS authority_memberships (
              id VARCHAR(64) PRIMARY KEY,
              tenant_id VARCHAR(255) NOT NULL,
              user_id VARCHAR(255) NOT NULL,
              org_scope_id VARCHAR(255) NOT NULL,
              office_n INTEGER NOT NULL,
              status VARCHAR(32) NOT NULL DEFAULT 'active',
              active_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
              active_to TIMESTAMP NULL,
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_authority_memberships_scope ON authority_memberships (tenant_id, org_scope_id, office_n, status)"))
