from sqlalchemy import text

VERSION = "0022_job_queue"


def upgrade(engine):
    with engine.begin() as conn:
        conn.execute(text("""CREATE TABLE IF NOT EXISTS icms_jobs (
            id VARCHAR(64) PRIMARY KEY, queue VARCHAR(80) NOT NULL,
            payload TEXT DEFAULT '{}', idempotency_key VARCHAR(160) UNIQUE,
            attempts INTEGER DEFAULT 0, available_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            locked_until TIMESTAMP, status VARCHAR(20) DEFAULT 'queued',
            last_error TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        """))


def downgrade(engine):
    return None
