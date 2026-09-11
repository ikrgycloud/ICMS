"""Phase 4 assessment, counselling, allocation and offer audit fields; additive only."""
from sqlalchemy import inspect, text

VERSION = "0006_admissions_phase4"


def upgrade(engine):
    import domain_models  # register models before create_all
    from models import Base
    Base.metadata.create_all(engine)
    additions = {
        "application_assessments": [("max_score", "FLOAT"), ("merit_score", "FLOAT"), ("merit_context_json", "TEXT DEFAULT '{}'")],
        "application_counselling": [("recommended_program_id", "VARCHAR"), ("recommended_quota_id", "VARCHAR"), ("preference_rank", "INTEGER"), ("remarks", "TEXT DEFAULT ''")],
        "admission_seat_allocations": [("waitlist_position", "INTEGER"), ("released_at", "TIMESTAMP"), ("release_reason", "TEXT DEFAULT ''")],
        "admission_offers": [("workflow_id", "VARCHAR"), ("program_id", "VARCHAR"), ("campus", "VARCHAR DEFAULT ''"), ("quota_id", "VARCHAR")],
    }
    with engine.begin() as conn:
        inspector = inspect(conn)
        for table, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_application_assessments_merit ON application_assessments (merit_score)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_admission_allocations_waitlist ON admission_seat_allocations (seat_pool_id, waitlist_position)"))


def downgrade(engine):
    return None
