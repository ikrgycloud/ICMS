from sqlalchemy import text

VERSION = "0018_governance_completion"

TABLES = {
    "curriculum_versions": "id VARCHAR PRIMARY KEY, tenant_id VARCHAR, program_id VARCHAR, regulation VARCHAR, effective_term VARCHAR, version INTEGER DEFAULT 1, status VARCHAR DEFAULT 'draft', snapshot_json TEXT DEFAULT '[]', source_proposal_id VARCHAR, created_by VARCHAR, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, effective_at TIMESTAMP",
    "curriculum_snapshots": "id VARCHAR PRIMARY KEY, tenant_id VARCHAR, curriculum_version_id VARCHAR, course_set_json TEXT DEFAULT '[]', checksum VARCHAR, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "program_assessments": "id VARCHAR PRIMARY KEY, tenant_id VARCHAR, proposal_id VARCHAR, capacity INTEGER DEFAULT 0, intake INTEGER DEFAULT 0, faculty_workload FLOAT DEFAULT 0, faculty_ready BOOLEAN DEFAULT FALSE, infrastructure_ready BOOLEAN DEFAULT FALSE, infrastructure_requirements_json TEXT DEFAULT '[]', principal_escalation_required BOOLEAN DEFAULT FALSE, assessed_by VARCHAR, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "calendar_versions": "id VARCHAR PRIMARY KEY, tenant_id VARCHAR, term VARCHAR, version INTEGER DEFAULT 1, status VARCHAR DEFAULT 'draft', snapshot_json TEXT DEFAULT '[]', source_proposal_id VARCHAR, effective_at TIMESTAMP, created_by VARCHAR, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "calendar_impact_tasks": "id VARCHAR PRIMARY KEY, tenant_id VARCHAR, calendar_version_id VARCHAR, downstream VARCHAR, status VARCHAR DEFAULT 'pending', acknowledged_by VARCHAR DEFAULT '', acknowledged_at TIMESTAMP, reason TEXT DEFAULT ''",
    "faculty_availability": "id VARCHAR PRIMARY KEY, tenant_id VARCHAR, faculty_id VARCHAR, term VARCHAR, available_units FLOAT DEFAULT 0, unavailable_slots_json TEXT DEFAULT '[]', status VARCHAR DEFAULT 'available', updated_by VARCHAR, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "faculty_workload_rules": "id VARCHAR PRIMARY KEY, tenant_id VARCHAR, term VARCHAR, min_units FLOAT DEFAULT 0, max_units FLOAT DEFAULT 1, overload_threshold FLOAT DEFAULT 1, underload_threshold FLOAT DEFAULT 0, active BOOLEAN DEFAULT TRUE",
    "faculty_conflict_exceptions": "id VARCHAR PRIMARY KEY, tenant_id VARCHAR, faculty_id VARCHAR, assignment_ids_json TEXT DEFAULT '[]', reason TEXT DEFAULT '', evidence_document_ids TEXT DEFAULT '[]', state VARCHAR DEFAULT 'OPEN', approved_by VARCHAR DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "teaching_plans": "id VARCHAR PRIMARY KEY, tenant_id VARCHAR, section_id VARCHAR, term VARCHAR, objectives TEXT DEFAULT '', status VARCHAR DEFAULT 'draft', version INTEGER DEFAULT 1, created_by VARCHAR, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "syllabus_progress": "id VARCHAR PRIMARY KEY, tenant_id VARCHAR, teaching_plan_id VARCHAR, topic VARCHAR, planned_date DATE, completed_date DATE, status VARCHAR DEFAULT 'planned', evidence_document_ids TEXT DEFAULT '[]'",
    "academic_milestones": "id VARCHAR PRIMARY KEY, tenant_id VARCHAR, term VARCHAR, title VARCHAR, due_at TIMESTAMP, status VARCHAR DEFAULT 'planned', owner_id VARCHAR DEFAULT '', completed_at TIMESTAMP",
    "course_completions": "id VARCHAR PRIMARY KEY, tenant_id VARCHAR, section_id VARCHAR, term VARCHAR, completion_pct FLOAT DEFAULT 0, verified_by VARCHAR DEFAULT '', status VARCHAR DEFAULT 'in_progress', updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "delivery_exceptions": "id VARCHAR PRIMARY KEY, tenant_id VARCHAR, section_id VARCHAR, kind VARCHAR, description TEXT DEFAULT '', state VARCHAR DEFAULT 'OPEN', owner_id VARCHAR DEFAULT '', evidence_document_ids TEXT DEFAULT '[]', status_version INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}


def upgrade(engine):
    with engine.begin() as conn:
        for name, definition in TABLES.items():
            conn.execute(text(f"CREATE TABLE IF NOT EXISTS {name} ({definition})"))


def downgrade(engine):
    return None
