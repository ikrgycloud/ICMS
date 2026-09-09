from sqlalchemy import text

VERSION = "0020_outcome_assessment_mapping"


def upgrade(engine):
    with engine.begin() as conn:
        conn.execute(text("""CREATE TABLE IF NOT EXISTS assessment_outcome_mappings (
            id VARCHAR PRIMARY KEY, tenant_id VARCHAR, assessment_id VARCHAR,
            course_outcome_id VARCHAR, weight FLOAT DEFAULT 1, target FLOAT DEFAULT 60)"""))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS outcome_attainment_targets (
            id VARCHAR PRIMARY KEY, tenant_id VARCHAR, outcome_type VARCHAR,
            outcome_id VARCHAR, aggregation_level VARCHAR DEFAULT 'course',
            target FLOAT DEFAULT 60, threshold FLOAT DEFAULT 50, term VARCHAR DEFAULT '')"""))


def downgrade(engine):
    return None