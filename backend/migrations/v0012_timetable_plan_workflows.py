"""Persist timetable plan review and approval state."""
VERSION = "v0012_timetable_plan_workflows"
def upgrade(engine):
    import domain_models  # noqa: F401
    from models import Base
    Base.metadata.create_all(engine)
def downgrade(engine):
    return None
