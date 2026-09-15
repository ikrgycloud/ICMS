"""Persist the SLA policy selected at routing time."""
from sqlalchemy import inspect, text
VERSION="0030_administration_sla_policy_link"
def upgrade(engine):
    import administration_models  # noqa
    from models import Base
    Base.metadata.create_all(engine)
    if "policy_id" not in {c["name"] for c in inspect(engine).get_columns("administrative_slas")}:
        with engine.begin() as conn: conn.execute(text("ALTER TABLE administrative_slas ADD COLUMN policy_id VARCHAR"))
def downgrade(engine): return None
