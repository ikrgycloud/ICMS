"""Create HOD input and faculty allocation records for course offerings."""
VERSION = "v0010_offering_workflow"

def upgrade(engine):
    import domain_models  # noqa: F401
    from models import Base
    Base.metadata.create_all(engine)

def downgrade(engine):
    return None
