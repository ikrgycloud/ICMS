VERSION = "0066_department_lifecycle"


def upgrade(engine):
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if not inspector.has_table("departments"):
        return
    columns = {column["name"] for column in inspector.get_columns("departments")}
    if "status" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE departments ADD COLUMN status VARCHAR NOT NULL DEFAULT 'active'"))
    with engine.begin() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_departments_status ON departments (status)"))


def downgrade(engine):
    return None
