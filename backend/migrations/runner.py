"""Tiny migration runner shared by PostgreSQL and SQLite deployments."""
from sqlalchemy import inspect, text

from migrations import (v0001_admissions_foundation, v0002_repair_legacy_application_status,
                        v0003_admission_seat_pool_identity, v0004_admissions_phase2_application_context)
from migrations import v0005_admissions_eligibility
from migrations import v0006_admissions_phase4
from migrations import v0007_admissions_phase5
from migrations import v0008_transport_route_status

MIGRATIONS = [v0001_admissions_foundation, v0002_repair_legacy_application_status,
              v0003_admission_seat_pool_identity, v0004_admissions_phase2_application_context]
MIGRATIONS.append(v0005_admissions_eligibility)
MIGRATIONS.append(v0006_admissions_phase4)
MIGRATIONS.append(v0007_admissions_phase5)
MIGRATIONS.append(v0008_transport_route_status)


def upgrade(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS icms_schema_migrations (version VARCHAR(64) PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
        applied = {row[0] for row in conn.execute(text("SELECT version FROM icms_schema_migrations"))}
    for migration in MIGRATIONS:
        if migration.VERSION in applied:
            continue
        migration.upgrade(engine)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO icms_schema_migrations (version) VALUES (:version)"), {"version": migration.VERSION})


def column_exists(engine, table, column):
    return inspect(engine).has_table(table) and column in {c["name"] for c in inspect(engine).get_columns(table)}
