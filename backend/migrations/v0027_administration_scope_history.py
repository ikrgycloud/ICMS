"""Add narrow fields needed for Administration policy specificity/history."""
from sqlalchemy import inspect, text
VERSION = "0027_administration_scope_history"

def upgrade(engine):
    import administration_models  # noqa
    from models import Base
    Base.metadata.create_all(engine)
    additions = {
      "administrative_assignments": [("previous_office_n", "INTEGER"), ("previous_user_id", "VARCHAR"), ("reason", "TEXT DEFAULT ''")],
      "administrative_approval_policies": [("department_id", "VARCHAR DEFAULT ''"), ("priority", "VARCHAR DEFAULT ''"), ("policy_priority", "INTEGER DEFAULT 0")],
      "administrative_routing_rules": [("department_id", "VARCHAR DEFAULT ''"), ("priority", "VARCHAR DEFAULT ''"), ("default_assignee_id", "VARCHAR")],
    }
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in additions.items():
            existing={x["name"] for x in inspector.get_columns(table)}
            for name, spec in columns:
                if name not in existing: conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {spec}"))

def downgrade(engine): return None
