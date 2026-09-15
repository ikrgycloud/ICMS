VERSION = "v0015_session_checkins"
def upgrade(engine):
    import domain_models
    from models import Base
    Base.metadata.create_all(engine)
def downgrade(engine): return None
