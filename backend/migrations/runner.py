"""Tiny migration runner shared by PostgreSQL and SQLite deployments."""
from sqlalchemy import inspect, text

from migrations import (v0001_admissions_foundation, v0002_repair_legacy_application_status,
                        v0003_admission_seat_pool_identity, v0004_admissions_phase2_application_context)
from migrations import v0005_admissions_eligibility
from migrations import v0006_admissions_phase4
from migrations import v0007_admissions_phase5
from migrations import v0008_academic_governance
from migrations import v0009_faculty_allocation_readiness
from migrations import v0010_quality_corrective_actions
from migrations import v0011_governance_outcomes_planning
from migrations import v0012_governance_completion
from migrations import v0013_legacy_schema_additions
from migrations import v0014_academic_hierarchy
from migrations import v0015_backfill_staff_scope
from migrations import v0016_governance_hierarchy
from migrations import v0017_unified_governance
from migrations import v0018_governance_completion
from migrations import v0019_quality_committee_planning
from migrations import v0020_outcome_assessment_mapping
from migrations import v0021_quality_effectiveness
from migrations import v0022_job_queue
from migrations import v0023_notification_delivery
from migrations import v0024_governance_policy_repair
from migrations import v0025_administration_domain
from migrations import v0026_administration_workflow_policy
from migrations import v0027_administration_scope_history
from migrations import v0028_specialist_execution_boundaries
from migrations import v0029_administration_reliability
from migrations import v0030_administration_sla_policy_link
from migrations import v0031_administration_sla_lifecycle
from migrations import v0032_administration_evidence_policy
from migrations import v0033_administration_evidence_retention
from migrations import v0034_administration_evidence_verification
from migrations import v0035_administration_approval_delegation
from migrations import v0036_administration_finance_controls
from migrations import v0037_administration_outbox_lease
from migrations import v0038_dean_scope_assignments
from migrations import v0008_transport_route_status
from migrations import v0009_faculty_teaching

MIGRATIONS = [v0001_admissions_foundation, v0002_repair_legacy_application_status,
              v0003_admission_seat_pool_identity, v0004_admissions_phase2_application_context]
MIGRATIONS.append(v0005_admissions_eligibility)
MIGRATIONS.append(v0006_admissions_phase4)
MIGRATIONS.append(v0007_admissions_phase5)
MIGRATIONS.append(v0008_academic_governance)
MIGRATIONS.append(v0009_faculty_allocation_readiness)
MIGRATIONS.append(v0010_quality_corrective_actions)
MIGRATIONS.append(v0011_governance_outcomes_planning)
MIGRATIONS.append(v0012_governance_completion)
MIGRATIONS.append(v0013_legacy_schema_additions)
MIGRATIONS.append(v0014_academic_hierarchy)
MIGRATIONS.append(v0015_backfill_staff_scope)
MIGRATIONS.append(v0016_governance_hierarchy)
MIGRATIONS.append(v0017_unified_governance)
MIGRATIONS.append(v0018_governance_completion)
MIGRATIONS.append(v0019_quality_committee_planning)
MIGRATIONS.append(v0020_outcome_assessment_mapping)
MIGRATIONS.append(v0021_quality_effectiveness)
MIGRATIONS.append(v0022_job_queue)
MIGRATIONS.append(v0023_notification_delivery)
MIGRATIONS.append(v0024_governance_policy_repair)
MIGRATIONS.append(v0025_administration_domain)
MIGRATIONS.append(v0026_administration_workflow_policy)
MIGRATIONS.append(v0027_administration_scope_history)
MIGRATIONS.append(v0028_specialist_execution_boundaries)
MIGRATIONS.append(v0029_administration_reliability)
MIGRATIONS.append(v0030_administration_sla_policy_link)
MIGRATIONS.append(v0031_administration_sla_lifecycle)
MIGRATIONS.append(v0032_administration_evidence_policy)
MIGRATIONS.append(v0033_administration_evidence_retention)
MIGRATIONS.append(v0034_administration_evidence_verification)
MIGRATIONS.append(v0035_administration_approval_delegation)
MIGRATIONS.append(v0036_administration_finance_controls)
MIGRATIONS.append(v0037_administration_outbox_lease)
MIGRATIONS.append(v0038_dean_scope_assignments)
MIGRATIONS.append(v0008_transport_route_status)
MIGRATIONS.append(v0009_faculty_teaching)


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
