"""Add policy, routing, SLA and specialist-boundary tables for Administration."""
VERSION = "0026_administration_workflow_policy"

def upgrade(engine):
    import administration_models  # noqa
    from models import Base
    Base.metadata.create_all(engine)

def downgrade(engine):
    return None
