from sqlalchemy import text

VERSION = "0023_notification_delivery"


def upgrade(engine):
    with engine.begin() as conn:
        conn.execute(text("""CREATE TABLE IF NOT EXISTS notification_deliveries (
            id VARCHAR PRIMARY KEY, tenant_id VARCHAR, notification_id VARCHAR,
            channel VARCHAR DEFAULT 'in_app', status VARCHAR DEFAULT 'pending',
            attempts INTEGER DEFAULT 0, last_error TEXT DEFAULT '',
            delivered_at TIMESTAMP, next_attempt_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS icms_worker_heartbeats (
            worker_id VARCHAR(128) PRIMARY KEY, status VARCHAR(30),
            processed INTEGER DEFAULT 0, failed INTEGER DEFAULT 0,
            last_error TEXT DEFAULT '', updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))


def downgrade(engine):
    return None