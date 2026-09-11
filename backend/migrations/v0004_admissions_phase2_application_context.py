"""Phase 2 applicant draft context and programme settings (additive)."""
from sqlalchemy import inspect, text

VERSION = "0004_admissions_phase2_application_context"


def upgrade(engine):
    import domain_models  # noqa: F401
    from models import Base
    Base.metadata.create_all(engine)
    additions = {
        "applications": [
            ("cycle_program_id", "VARCHAR"),
            ("profile_json", "TEXT DEFAULT '{}'"),
        ],
        "admission_cycle_programs": [("settings_json", "TEXT DEFAULT '{}'")],
    }
    with engine.begin() as conn:
        inspector = inspect(conn)
        for table, columns in additions.items():
            if not inspector.has_table(table):
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_application_number_tenant "
                          "ON applications (tenant_id, application_no)"))


def downgrade(engine):
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX IF EXISTS uq_application_number_tenant"))
