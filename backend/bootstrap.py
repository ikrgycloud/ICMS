# -*- coding: utf-8 -*-
"""
ICMS Payroll Bootstrap

Production-safe payroll reconciliation.

Responsibilities:
    1. Ensure the database schema/migrations are ready.
    2. Prevent multiple backend containers from running payroll provisioning
       concurrently.
    3. Ensure required non-teaching staff records exist.
    4. Reconcile payroll employee profiles for all staff records.
    5. Reconcile payroll logins independently.
    6. Backfill payroll entries for every payroll run.
    7. Verify the final payroll consistency.
"""

import os
import sys
import traceback

from sqlalchemy import text

from database import (
    SessionLocal,
    ensure_additive_schema,
    ensure_versioned_migrations,
    seed,
)

import domain_models as D

from domain_seed import (
    _ensure_payroll_staff_logins,
    _seed_non_teaching_staff_records,
    _seed_payroll_demo_data,
)

from portal_api import _ensure_payroll_run_entries


ADVISORY_LOCK_KEY = "icms_payroll_bootstrap"


def log(message):
    print(
        f"[payroll-bootstrap] {message}",
        flush=True,
    )


def acquire_lock(session):
    log("Acquiring PostgreSQL advisory lock...")

    session.execute(
        text(
            "SELECT pg_advisory_lock("
            "hashtext(:lock_name)"
            ")"
        ),
        {
            "lock_name": ADVISORY_LOCK_KEY,
        },
    )

    log("PostgreSQL advisory lock acquired.")


def release_lock(session):
    try:
        session.execute(
            text(
                "SELECT pg_advisory_unlock("
                "hashtext(:lock_name)"
                ")"
            ),
            {
                "lock_name": ADVISORY_LOCK_KEY,
            },
        )

        log("PostgreSQL advisory lock released.")

    except Exception as exc:
        log(
            f"Unable to release PostgreSQL advisory lock: {exc}"
        )


def get_counts(session):
    staff_count = (
        session.query(D.StaffMember)
        .count()
    )

    payroll_profile_count = (
        session.query(D.PayrollEmployee)
        .count()
    )

    payroll_run_count = (
        session.query(D.PayrollRun)
        .count()
    )

    payroll_entry_count = (
        session.query(D.PayrollEntry)
        .count()
    )

    return {
        "staff": staff_count,
        "payroll_profiles": payroll_profile_count,
        "payroll_runs": payroll_run_count,
        "payroll_entries": payroll_entry_count,
    }


def get_missing_payroll_count(session):
    """
    Count active staff members that do not have a payroll profile.
    """

    return (
        session.query(D.StaffMember)
        .outerjoin(
            D.PayrollEmployee,
            D.PayrollEmployee.staff_member_id
            == D.StaffMember.id,
        )
        .filter(
            D.StaffMember.status == "active",
            D.PayrollEmployee.id.is_(None),
        )
        .count()
    )


def print_counts(session, label):
    counts = get_counts(session)

    log(
        f"{label}: "
        f"staff={counts['staff']}, "
        f"payroll_profiles={counts['payroll_profiles']}, "
        f"payroll_runs={counts['payroll_runs']}, "
        f"payroll_entries={counts['payroll_entries']}"
    )

    return counts


def verify_payroll(session):
    """
    Verify that every active staff member has a payroll profile.
    """

    counts = print_counts(
        session,
        "Final payroll state",
    )

    missing_payroll = get_missing_payroll_count(
        session
    )

    log(
        f"Active staff without payroll profile: "
        f"{missing_payroll}"
    )

    if missing_payroll != 0:
        raise RuntimeError(
            "Payroll bootstrap verification failed: "
            f"{missing_payroll} active staff members "
            "do not have payroll profiles."
        )

    if counts["staff"] == 0:
        raise RuntimeError(
            "Payroll bootstrap verification failed: "
            "no staff members exist."
        )

    if counts["payroll_profiles"] < counts["staff"]:
        raise RuntimeError(
            "Payroll bootstrap verification failed: "
            "payroll profile count is lower than staff count."
        )

    log(
        "Payroll bootstrap verification PASSED."
    )


def bootstrap():
    provision_enabled = (
        os.environ.get(
            "PROVISION_PAYROLL_DATA",
            "",
        )
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "on",
        }
    )

    if not provision_enabled:
        log(
            "PROVISION_PAYROLL_DATA is disabled. "
            "Skipping payroll bootstrap."
        )
        return

    log("=" * 60)
    log("ICMS PAYROLL BOOTSTRAP START")
    log("=" * 60)

    session = None
    lock_acquired = False

    try:
        # ---------------------------------------------------------
        # 1. Base database initialization
        # ---------------------------------------------------------

        log("Running base identity/schema initialization...")

        seed()

        ensure_versioned_migrations()

        ensure_additive_schema()

        # ---------------------------------------------------------
        # 2. Create DB session
        # ---------------------------------------------------------

        session = SessionLocal()

        # ---------------------------------------------------------
        # 3. Prevent concurrent bootstrap execution
        # ---------------------------------------------------------

        acquire_lock(session)

        lock_acquired = True

        # ---------------------------------------------------------
        # 4. Existing staff must be preserved
        # ---------------------------------------------------------

        counts_before = print_counts(
            session,
            "Before payroll provisioning",
        )

        if counts_before["staff"] == 0:
            log(
                "WARNING: no StaffMember records exist. "
                "Payroll provisioning cannot create employee "
                "master records by itself."
            )

        # ---------------------------------------------------------
        # 5. Ensure support/non-teaching employees exist
        # ---------------------------------------------------------

        log(
            "Reconciling non-teaching/support staff..."
        )

        _seed_non_teaching_staff_records(
            session
        )

        session.commit()

        print_counts(
            session,
            "After support-staff reconciliation",
        )

        # ---------------------------------------------------------
        # 6. Payroll employee reconciliation
        # ---------------------------------------------------------

        log(
            "Reconciling payroll employee profiles..."
        )

        _seed_payroll_demo_data(
            session
        )

        # IMPORTANT:
        # Commit payroll profiles BEFORE touching logins.
        session.commit()

        log(
            "Payroll employee profiles committed."
        )

        print_counts(
            session,
            "After payroll profile reconciliation",
        )

        # ---------------------------------------------------------
        # 7. Payroll login reconciliation
        # ---------------------------------------------------------

        log(
            "Reconciling payroll staff logins..."
        )

        try:
            _ensure_payroll_staff_logins(
                session
            )

            session.commit()

            log(
                "Payroll staff login reconciliation completed."
            )

        except Exception as exc:
            session.rollback()

            log(
                "Payroll login reconciliation warning: "
                f"{exc}"
            )

            log(
                "Existing payroll profiles are preserved. "
                "Continuing with payroll run reconciliation."
            )

        # ---------------------------------------------------------
        # 8. Payroll run entry reconciliation
        # ---------------------------------------------------------

        log(
            "Reconciling payroll entries for all payroll runs..."
        )

        payroll_runs = (
            session.query(D.PayrollRun)
            .order_by(D.PayrollRun.payroll_month)
            .all()
        )

        log(
            f"Found {len(payroll_runs)} payroll runs."
        )

        for payroll_run in payroll_runs:
            log(
                "Backfilling payroll entries for "
                f"run={payroll_run.id}, "
                f"month={payroll_run.payroll_month}"
            )

            _ensure_payroll_run_entries(
                session,
                payroll_run,
            )

            # Commit each run separately.
            #
            # This prevents one problematic run from rolling back
            # entries already created for previous runs.
            session.commit()

        log(
            "Payroll run entry reconciliation completed."
        )

        # ---------------------------------------------------------
        # 9. Final verification
        # ---------------------------------------------------------

        verify_payroll(
            session
        )

        log("=" * 60)
        log("ICMS PAYROLL BOOTSTRAP SUCCESS")
        log("=" * 60)

    except Exception as exc:

        if session is not None:
            session.rollback()

        log("=" * 60)
        log("ICMS PAYROLL BOOTSTRAP FAILED")
        log("=" * 60)

        log(
            f"ERROR: {exc}"
        )

        traceback.print_exc()

        raise

    finally:

        if session is not None:

            if lock_acquired:
                release_lock(session)

            session.close()


if __name__ == "__main__":
    try:
        bootstrap()

    except Exception:
        sys.exit(1)
