VERSION = "v0016_curriculum_execution"

def upgrade(engine):
    import domain_models
    from models import Base
    Base.metadata.create_all(engine)

def downgrade(engine):
    return None
