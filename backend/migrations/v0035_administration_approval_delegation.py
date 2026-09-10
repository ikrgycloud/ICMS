"""Persist Administration approval delegation provenance."""
VERSION = "0035_administration_approval_delegation"


def upgrade(engine):
    from sqlalchemy import inspect, text

    columns = {column["name"] for column in inspect(engine).get_columns("administrative_approvals")}
    with engine.begin() as connection:
        if "delegated_from_user_id" not in columns:
            connection.execute(text("ALTER TABLE administrative_approvals ADD COLUMN delegated_from_user_id VARCHAR(255)"))
        if "delegation_id" not in columns:
            connection.execute(text("ALTER TABLE administrative_approvals ADD COLUMN delegation_id VARCHAR(255)"))


def downgrade(engine):
    return None