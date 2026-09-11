"""Backfill the required course-offering parent for legacy running sections."""
import hashlib
import re

from sqlalchemy import text

VERSION = "0040_course_offering_lineage"


def _academic_year(term: str) -> str:
    match = re.match(r"^(\d{4})", term or "")
    if not match:
        return term or "legacy"
    start = int(match.group(1))
    return f"{start}-{str(start + 1)[-2:]}"


def _offering_id(tenant_id: str, course_id: str, program_id: str, term: str) -> str:
    key = f"{tenant_id}|{course_id}|{program_id}|{term}".encode()
    return f"legacy_offering_{hashlib.sha256(key).hexdigest()[:20]}"


def upgrade(engine):
    # Tables are created by the normal additive schema path before migrations;
    # use only portable SQL here so fresh SQLite and PostgreSQL installations
    # receive the same repair.
    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT s.id AS section_id, s.tenant_id, s.course_id, s.dept_id, s.term,
                   c.program_id AS course_program_id, c.semester
            FROM sections s
            JOIN courses c ON c.id = s.course_id
            WHERE s.offering_id IS NULL OR s.offering_id = ''
        """)).mappings().all()
        for row in rows:
            program_id = row["course_program_id"]
            if not program_id:
                program_id = conn.execute(text("""
                    SELECT id FROM programs
                    WHERE tenant_id = :tenant_id AND dept_id = :dept_id
                    ORDER BY CASE WHEN level = 'UG' THEN 0 ELSE 1 END, id
                    LIMIT 1
                """), {"tenant_id": row["tenant_id"], "dept_id": row["dept_id"]}).scalar()
            if not program_id:
                # Preserve the row rather than invent an invalid relationship.
                # A section without a programme remains visible for manual repair.
                continue
            offering_id = conn.execute(text("""
                SELECT id FROM course_offerings
                WHERE tenant_id = :tenant_id AND course_id = :course_id
                  AND program_id = :program_id AND academic_year = :academic_year
                  AND term = :term
            """), {
                "tenant_id": row["tenant_id"], "course_id": row["course_id"],
                "program_id": program_id, "academic_year": _academic_year(row["term"]),
                "term": row["term"],
            }).scalar()
            if not offering_id:
                offering_id = _offering_id(row["tenant_id"], row["course_id"], program_id, row["term"])
                conn.execute(text("""
                    INSERT INTO course_offerings
                        (id, tenant_id, course_id, program_id, academic_year, term, semester,
                         status, created_by, updated_by, created_at, updated_at)
                    VALUES
                        (:id, :tenant_id, :course_id, :program_id, :academic_year, :term, :semester,
                         'Published', 'migration', 'migration', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """), {
                    "id": offering_id, "tenant_id": row["tenant_id"], "course_id": row["course_id"],
                    "program_id": program_id, "academic_year": _academic_year(row["term"]),
                    "term": row["term"], "semester": row["semester"],
                })
            conn.execute(text("UPDATE sections SET offering_id = :offering_id WHERE id = :section_id"), {
                "offering_id": offering_id, "section_id": row["section_id"],
            })
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_course_offerings_business_key
            ON course_offerings (tenant_id, course_id, program_id, academic_year, term)
        """))


def downgrade(engine):
    return None
