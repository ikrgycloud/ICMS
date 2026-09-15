"""Lease Administration outbox events so concurrent workers cannot claim one event."""
VERSION = "0037_administration_outbox_lease"


def upgrade(engine):
    from sqlalchemy import inspect, text
    columns = {column["name"] for column in inspect(engine).get_columns("administrative_outbox_events")}
    additions = {
        "locked_by": "VARCHAR(255)",
        "locked_at": "TIMESTAMP",
        "lease_expires_at": "TIMESTAMP",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE administrative_outbox_events ADD COLUMN {name} {definition}"))


def downgrade(engine):
    return None
