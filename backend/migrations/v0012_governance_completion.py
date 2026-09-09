from sqlalchemy import text
VERSION='0012_governance_completion'
def upgrade(engine):
    sql=[
    "CREATE TABLE IF NOT EXISTS committee_members (id VARCHAR PRIMARY KEY, tenant_id VARCHAR, committee_id VARCHAR, user_id VARCHAR, role VARCHAR DEFAULT 'member', active BOOLEAN DEFAULT TRUE)",
    "CREATE TABLE IF NOT EXISTS committee_action_items (id VARCHAR PRIMARY KEY, tenant_id VARCHAR, resolution_id VARCHAR, title VARCHAR, owner_id VARCHAR, deadline TIMESTAMP, status VARCHAR DEFAULT 'OPEN', evidence TEXT DEFAULT '')"
    ]
    with engine.begin() as c:
        for q in sql:c.execute(text(q))
