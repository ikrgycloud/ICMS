"""Provision employee payroll demo data without enabling the full demo seed."""
from database import SessionLocal, ensure_additive_schema, ensure_versioned_migrations
from domain_seed import (
    _ensure_payroll_staff_logins,
    _seed_non_teaching_staff_records,
    _seed_payroll_demo_data,
)


def main():
    ensure_versioned_migrations()
    ensure_additive_schema()
    session = SessionLocal()
    try:
        _seed_non_teaching_staff_records(session)
        _seed_payroll_demo_data(session)
        _ensure_payroll_staff_logins(session)
        print("Payroll demo data provisioned")
    finally:
        session.close()


if __name__ == "__main__":
    main()
