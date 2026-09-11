from sqlalchemy import text

VERSION = "0021_quality_effectiveness"


def upgrade(engine):
    with engine.begin() as conn:
        conn.execute(text("""CREATE TABLE IF NOT EXISTS quality_effectiveness_measurements (
            id VARCHAR PRIMARY KEY, tenant_id VARCHAR, review_id VARCHAR,
            measure TEXT, result TEXT, value FLOAT, measured_by VARCHAR,
            measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))


def downgrade(engine):
    return None