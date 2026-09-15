"""Fail-closed campus leadership resolution for HOD-owned workflows."""
from datetime import date

from fastapi import HTTPException

import domain_models as D
from models import User

VICE_PRINCIPAL_OFFICE_N = 5
PRINCIPAL_OFFICE_N = 4
DEAN_ACADEMICS_OFFICE_N = 6
DEAN_ADMINISTRATION_OFFICE_N = 7
DEAN_STUDENT_AFFAIRS_OFFICE_N = 8
STAFFING_REVIEW_STAGES = {1: "Dean Administration", 2: "Principal"}


def resolve_campus_leader(s, campus_id, office_n):
    today = date.today()
    rows = (s.query(D.CampusLeadershipAssignment)
            .filter(D.CampusLeadershipAssignment.campus_id == campus_id,
                    D.CampusLeadershipAssignment.office_n == office_n,
                    D.CampusLeadershipAssignment.active.is_(True),
                    D.CampusLeadershipAssignment.effective_from <= today,
                    (D.CampusLeadershipAssignment.effective_to.is_(None)
                     | (D.CampusLeadershipAssignment.effective_to >= today)))
            .all())
    if len(rows) != 1:
        raise HTTPException(409, "A unique active campus leadership assignment is required")
    user = s.get(User, rows[0].user_id)
    if not user or user.office_n != office_n:
        raise HTTPException(409, "The campus leadership assignment is invalid")
    return user


def hod_campus(s, ctx):
    staff = s.query(D.StaffMember).filter(D.StaffMember.user_id == ctx.get("sub")).one_or_none()
    department = s.get(D.Department, staff.dept_id) if staff else None
    if not department or not department.campus:
        raise HTTPException(403, "The HOD department has no campus assignment")
    campus = (s.query(D.Campus).filter((D.Campus.id == department.campus) | (D.Campus.code == department.campus) | (D.Campus.name == department.campus)).one_or_none())
    if not campus:
        raise HTTPException(403, "The HOD campus is unavailable")
    return campus


def resolve_academic_dean(s, ctx):
    return resolve_campus_leader(s, hod_campus(s, ctx).id, DEAN_ACADEMICS_OFFICE_N)


def resolve_administration_dean(s, ctx):
    return resolve_campus_leader(s, hod_campus(s, ctx).id, DEAN_ADMINISTRATION_OFFICE_N)


def resolve_student_affairs_dean(s, ctx):
    return resolve_campus_leader(s, hod_campus(s, ctx).id, DEAN_STUDENT_AFFAIRS_OFFICE_N)


def resolve_staffing_reviewers(s, ctx):
    campus_id = hod_campus(s, ctx).id
    return {
        1: resolve_campus_leader(s, campus_id, DEAN_ADMINISTRATION_OFFICE_N),
        2: resolve_campus_leader(s, campus_id, PRINCIPAL_OFFICE_N),
    }
