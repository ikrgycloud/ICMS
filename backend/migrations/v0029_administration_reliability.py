"""SLA policy/outbox and safe evidence metadata extensions."""
from sqlalchemy import inspect, text
VERSION="0029_administration_reliability"
def upgrade(engine):
    import administration_models  # noqa
    from models import Base
    Base.metadata.create_all(engine)
    additions={
      "administrative_evidence":[("content_type","VARCHAR DEFAULT 'application/octet-stream'"),("size_bytes","INTEGER DEFAULT 0"),("storage_key","VARCHAR DEFAULT ''")],
      "administrative_slas":[("status","VARCHAR DEFAULT 'ACTIVE'")],
    }
    inspector=inspect(engine)
    with engine.begin() as conn:
        for table, columns in additions.items():
            known={c["name"] for c in inspector.get_columns(table)}
            for name,spec in columns:
                if name not in known:conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {spec}"))
def downgrade(engine): return None
