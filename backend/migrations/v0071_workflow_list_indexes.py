VERSION = "0071_workflow_list_indexes"


def upgrade(engine):
    """Indexes for tenant/campus-scoped workflow inbox and history reads."""
    from sqlalchemy import inspect, text

    tables = set(inspect(engine).get_table_names())
    statements = []
    if "workflow_instances" in tables:
        statements.extend([
            "CREATE INDEX IF NOT EXISTS ix_workflows_tenant_scope_updated ON workflow_instances (tenant_id, scope_level, scope_ref, updated_at)",
            "CREATE INDEX IF NOT EXISTS ix_workflows_tenant_initiator_updated ON workflow_instances (tenant_id, initiator_id, updated_at)",
        ])
    if "approvals" in tables:
        statements.append("CREATE INDEX IF NOT EXISTS ix_approvals_actor_workflow ON approvals (actor_id, workflow_id)")
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
