VERSION = "0052_curriculum_execution_upstream_gaps"

def upgrade(engine):
    from sqlalchemy import inspect, text
    with engine.begin() as conn:
        inspector = inspect(conn)
        if not inspector.has_table("curriculum_execution_issues"):
            return
        columns = {c["name"] for c in inspector.get_columns("curriculum_execution_issues")}
        for name in ("course_id", "curriculum_version_id"):
            if name not in columns:
                conn.execute(text(f"ALTER TABLE curriculum_execution_issues ADD COLUMN {name} VARCHAR"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_execution_issues_curriculum_course ON curriculum_execution_issues(curriculum_version_id, course_id)"))
