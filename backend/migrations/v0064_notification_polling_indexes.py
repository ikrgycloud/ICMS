VERSION = "0064_notification_polling_indexes"


def upgrade(engine):
    """Indexes supporting the tenant-scoped notification bell queries."""
    from sqlalchemy import inspect, text
    if "notifications" not in inspect(engine).get_table_names():
        return
    with engine.begin() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_notifications_tenant_user_created ON notifications(tenant_id, user_id, created_at DESC)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_notifications_tenant_user_read ON notifications(tenant_id, user_id, read)"))


def downgrade(engine):
    return None
