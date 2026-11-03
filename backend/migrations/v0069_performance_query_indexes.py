VERSION = "0069_performance_query_indexes"


def upgrade(engine):
    """Indexes supporting scoped dashboard, timetable, and finance list reads."""
    from sqlalchemy import inspect, text

    tables = set(inspect(engine).get_table_names())
    statements = []
    if "timetable_plan_workflows" in tables:
        statements.append("CREATE INDEX IF NOT EXISTS ix_timetable_plans_tenant_updated ON timetable_plan_workflows (tenant_id, updated_at)")
    if "attendance_records" in tables:
        statements.append("CREATE INDEX IF NOT EXISTS ix_attendance_tenant_student_date ON attendance_records (tenant_id, student_id, on_date)")
    if "fee_invoices" in tables:
        statements.append("CREATE INDEX IF NOT EXISTS ix_fee_invoices_tenant_student ON fee_invoices (tenant_id, student_id)")
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
