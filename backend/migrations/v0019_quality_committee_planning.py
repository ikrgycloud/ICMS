from sqlalchemy import inspect, text

VERSION = "0019_quality_committee_planning"

TABLE_COLUMNS = {
    "academic_quality_reviews": {
        "effectiveness_measure": "TEXT DEFAULT ''", "effectiveness_result": "TEXT DEFAULT ''",
        "closed_at": "TIMESTAMP",
    },
    "corrective_actions": {
        "priority": "VARCHAR DEFAULT 'medium'", "progress": "FLOAT DEFAULT 0",
        "evidence_versions": "TEXT DEFAULT '[]'", "owner_acknowledged": "BOOLEAN DEFAULT FALSE",
        "escalation_target": "VARCHAR DEFAULT ''", "verification_result": "TEXT DEFAULT ''",
    },
    "academic_committees": {"permissions_json": "TEXT DEFAULT '[\"view\",\"record\",\"assign\",\"verify\"]'"},
    "committee_meetings": {"agenda_status": "VARCHAR DEFAULT 'DRAFT'", "minutes_status": "VARCHAR DEFAULT 'DRAFT'"},
    "committee_resolutions": {
        "linked_quality_action_id": "VARCHAR", "linked_planning_item_id": "VARCHAR",
        "approved_by": "VARCHAR DEFAULT ''", "approved_at": "TIMESTAMP",
    },
    "committee_action_items": {
        "verification_result": "TEXT DEFAULT ''", "verified_by": "VARCHAR DEFAULT ''",
        "verified_at": "TIMESTAMP",
    },
    "next_semester_plans": {
        "dependencies_json": "TEXT DEFAULT '[]'", "evidence_links_json": "TEXT DEFAULT '[]'",
        "updated_at": "TIMESTAMP",
    },
}


def upgrade(engine):
    inspector = inspect(engine)
    for table, columns in TABLE_COLUMNS.items():
        if not inspector.has_table(table):
            continue
        existing = {column["name"] for column in inspector.get_columns(table)}
        for name, definition in columns.items():
            if name not in existing:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))


def downgrade(engine):
    return None