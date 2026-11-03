VERSION = "0068_sections_query_indexes"


def upgrade(engine):
    """Indexes for the tenant-scoped section register and enrollment aggregate."""
    from sqlalchemy import inspect, text

    tables = set(inspect(engine).get_table_names())
    statements = []
    if "sections" in tables:
        statements.extend([
            "CREATE INDEX IF NOT EXISTS ix_sections_tenant_dept ON sections (tenant_id, dept_id)",
            "CREATE INDEX IF NOT EXISTS ix_sections_tenant_offering ON sections (tenant_id, offering_id)",
        ])
    if "enrollments" in tables:
        statements.append(
            "CREATE INDEX IF NOT EXISTS ix_enrollments_tenant_section_status ON enrollments (tenant_id, section_id, status)"
        )
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
