"""Add scoped declarative evidence policies for Administration closure."""
VERSION="0032_administration_evidence_policy"
def upgrade(engine):
    import administration_models  # noqa
    from models import Base
    Base.metadata.create_all(engine)
def downgrade(engine): return None
