"""Create persisted term-specific course offerings."""
VERSION = "v0009_course_offerings"

from sqlalchemy import inspect, text


def upgrade(engine):
    import domain_models  # noqa: F401
    from models import Base
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_course_offerings_term_status ON course_offerings (academic_year, term, status)"))


def downgrade(engine):
    return None
