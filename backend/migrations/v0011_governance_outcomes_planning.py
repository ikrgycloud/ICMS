from sqlalchemy import text
VERSION='0011_governance_outcomes_planning'
def upgrade(engine):
    sql=[
    "CREATE TABLE IF NOT EXISTS academic_committees (id VARCHAR PRIMARY KEY, tenant_id VARCHAR, name VARCHAR, committee_type VARCHAR, chair_id VARCHAR DEFAULT '', status VARCHAR DEFAULT 'active')",
    "CREATE TABLE IF NOT EXISTS committee_meetings (id VARCHAR PRIMARY KEY, tenant_id VARCHAR, committee_id VARCHAR, meeting_at TIMESTAMP, agenda TEXT DEFAULT '', minutes TEXT DEFAULT '', status VARCHAR DEFAULT 'SCHEDULED', created_by VARCHAR DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS committee_resolutions (id VARCHAR PRIMARY KEY, tenant_id VARCHAR, meeting_id VARCHAR, title VARCHAR, decision TEXT, linked_proposal_id VARCHAR, status VARCHAR DEFAULT 'OPEN', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
    "CREATE TABLE IF NOT EXISTS program_outcomes (id VARCHAR PRIMARY KEY, tenant_id VARCHAR, program_id VARCHAR, code VARCHAR, description TEXT, active BOOLEAN DEFAULT TRUE)",
    "CREATE TABLE IF NOT EXISTS course_outcomes (id VARCHAR PRIMARY KEY, tenant_id VARCHAR, course_id VARCHAR, code VARCHAR, description TEXT, active BOOLEAN DEFAULT TRUE)",
    "CREATE TABLE IF NOT EXISTS outcome_mappings (id VARCHAR PRIMARY KEY, tenant_id VARCHAR, course_outcome_id VARCHAR, program_outcome_id VARCHAR, weight FLOAT DEFAULT 1)",
    "CREATE TABLE IF NOT EXISTS next_semester_plans (id VARCHAR PRIMARY KEY, tenant_id VARCHAR, source_term VARCHAR, target_term VARCHAR, summary TEXT DEFAULT '', risks_json TEXT DEFAULT '[]', actions_json TEXT DEFAULT '[]', state VARCHAR DEFAULT 'DRAFT', created_by VARCHAR DEFAULT '', approved_by VARCHAR DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    ]
    with engine.begin() as c:
        for q in sql:c.execute(text(q))
