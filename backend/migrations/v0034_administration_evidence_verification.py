"""Persist evidence verification state for Administration closure."""
VERSION = "0034_administration_evidence_verification"


def upgrade(engine):
    from sqlalchemy import inspect, text

    columns = {column["name"] for column in inspect(engine).get_columns("administrative_evidence")}
    additions = {
        "verification_status": "VARCHAR(32) DEFAULT 'UPLOADED' NOT NULL",
        "verified_by": "VARCHAR(255)",
        "verified_at": "TIMESTAMP",
        "rejection_reason": "TEXT DEFAULT ''",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE administrative_evidence ADD COLUMN {name} {definition}"))


def downgrade(engine):
    return None