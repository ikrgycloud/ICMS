"""Attach offering-level faculty allocations to their course offering."""
from sqlalchemy import inspect, text

VERSION = "0047_faculty_allocation_offering"


def upgrade(engine):
    with engine.begin() as conn:
        columns = {column["name"] for column in inspect(conn).get_columns("faculty_allocations")}
        if "offering_id" not in columns:
            conn.execute(text("ALTER TABLE faculty_allocations ADD COLUMN offering_id VARCHAR"))

        # Recover only unambiguous legacy offering-level rows.
        rows = conn.execute(text("""
            SELECT fa.id, fa.tenant_id, fa.term
            FROM faculty_allocations fa
            WHERE fa.section_id IS NULL AND fa.offering_id IS NULL
        """)).mappings().all()
        for row in rows:
            matches = conn.execute(text("""
                SELECT id FROM course_offerings
                WHERE tenant_id = :tenant_id AND term = :term
            """), {"tenant_id": row["tenant_id"], "term": row["term"]}).scalars().all()
            if len(matches) == 1:
                conn.execute(text("""
                    UPDATE faculty_allocations
                    SET offering_id = :offering_id
                    WHERE id = :allocation_id
                """), {"offering_id": matches[0], "allocation_id": row["id"]})


def downgrade(engine):
    return None
