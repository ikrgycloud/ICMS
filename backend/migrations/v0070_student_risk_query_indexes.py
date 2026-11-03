VERSION = "0070_student_risk_query_indexes"


def upgrade(engine):
    """Indexes for paginated, campus-scoped student risk worklists."""
    from sqlalchemy import inspect, text

    tables = set(inspect(engine).get_table_names())
    statements = []
    if "students" in tables:
        statements.extend([
            "CREATE INDEX IF NOT EXISTS ix_students_tenant_campus_cgpa ON students (tenant_id, campus, cgpa)",
            "CREATE INDEX IF NOT EXISTS ix_students_tenant_scope_cgpa ON students (tenant_id, campus_scope_id, cgpa)",
        ])
    if "student_subject_results" in tables:
        statements.append("CREATE INDEX IF NOT EXISTS ix_subject_results_tenant_student_subject_attempt ON student_subject_results (tenant_id, student_id, subject_code, attempt)")
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
