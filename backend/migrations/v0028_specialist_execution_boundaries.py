"""Create separate HR, facilities, IT and procurement execution records."""
VERSION="0028_specialist_execution_boundaries"
def upgrade(engine):
    import specialist_models  # noqa
    from models import Base
    Base.metadata.create_all(engine)
def downgrade(engine): return None
