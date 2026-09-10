"""Add offer-acceptance department requests and final class allocations."""
VERSION = "0008_admission_class_allocation"


def upgrade(engine):
    import domain_models
    from models import Base
    Base.metadata.create_all(engine)


def downgrade(engine):
    return None
