"""Canonical campus ownership for budget oversight."""
from sqlalchemy import inspect, text

VERSION = "0059_budget_campus_scope"


def upgrade(engine):
    inspector = inspect(engine)
    if not inspector.has_table("budget_lines"):
        return
    columns = {column["name"] for column in inspector.get_columns("budget_lines")}
    with engine.begin() as conn:
        if "campus_scope_id" not in columns:
            conn.execute(text("ALTER TABLE budget_lines ADD COLUMN campus_scope_id VARCHAR"))
        conn.execute(text("""
            UPDATE budget_lines
            SET campus_scope_id = (
                SELECT org_scopes.id FROM org_scopes
                WHERE org_scopes.tenant_id = budget_lines.tenant_id
                  AND org_scopes.level = 'campus'
                  AND org_scopes.name = budget_lines.campus
                LIMIT 1
            )
            WHERE campus_scope_id IS NULL OR campus_scope_id = ''
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_budget_lines_campus_scope_id ON budget_lines (campus_scope_id)"))
