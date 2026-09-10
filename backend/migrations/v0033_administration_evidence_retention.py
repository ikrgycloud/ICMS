"""Retain deleted administration evidence metadata for auditability."""
VERSION = "0033_administration_evidence_retention"


def upgrade(engine):
    from sqlalchemy import inspect, text

    columns = {column["name"] for column in inspect(engine).get_columns("administrative_evidence")}
    with engine.begin() as connection:
        if "deleted_at" not in columns:
            connection.execute(text("ALTER TABLE administrative_evidence ADD COLUMN deleted_at TIMESTAMP"))
        if "deleted_by" not in columns:
            connection.execute(text("ALTER TABLE administrative_evidence ADD COLUMN deleted_by VARCHAR(255)"))


def downgrade(engine):
    return None