"""Associate sections with term-specific course offerings."""
VERSION = "v0011_section_offering"
from sqlalchemy import inspect, text

def upgrade(engine):
    with engine.begin() as conn:
        if "sections" in inspect(engine).get_table_names() and "offering_id" not in {c["name"] for c in inspect(engine).get_columns("sections") }:
            conn.execute(text("ALTER TABLE sections ADD COLUMN offering_id VARCHAR"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sections_offering_id ON sections (offering_id)"))

def downgrade(engine):
    return None
