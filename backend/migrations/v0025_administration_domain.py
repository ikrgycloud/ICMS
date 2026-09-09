"""Register Dean Administration bounded-domain tables."""
VERSION = "0025_administration_domain"

def upgrade(engine):
    import administration_models  # noqa: F401 - registers shared Base metadata
    from models import Base
    Base.metadata.create_all(engine)

def downgrade(engine):
    return None
