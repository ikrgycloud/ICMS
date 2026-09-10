"""Persist SLA commitment and pause lifecycle fields."""
from sqlalchemy import inspect, text
VERSION="0031_administration_sla_lifecycle"

def upgrade(engine):
    import administration_models  # noqa
    from models import Base
    Base.metadata.create_all(engine)
    additions={
        "administrative_slas": {"original_due_at":"TIMESTAMP","approaching_percent":"INTEGER NOT NULL DEFAULT 80","pause_allowed":"BOOLEAN NOT NULL DEFAULT 0","paused_seconds":"INTEGER NOT NULL DEFAULT 0","pause_count":"INTEGER NOT NULL DEFAULT 0"},
        "administrative_sla_policies":{"pause_allowed":"BOOLEAN NOT NULL DEFAULT 0"},
    }
    for table, columns in additions.items():
        existing={c["name"] for c in inspect(engine).get_columns(table)}
        with engine.begin() as conn:
            for name, ddl in columns.items():
                if name not in existing: conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))

def downgrade(engine): return None
