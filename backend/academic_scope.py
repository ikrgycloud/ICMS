"""Central academic hierarchy and action-scope policy.

All governance services should call ``authorize_object`` before returning or
mutating an academic object.  The resolver follows section/course/program/
department links instead of trusting IDs supplied by clients.
"""
from dataclasses import dataclass
from typing import Any
from datetime import datetime

from fastapi import HTTPException
import domain_models as D
from database import demo_data_enabled


@dataclass(frozen=True)
class AcademicHierarchy:
    tenant_id: str | None = None
    school_id: str | None = None
    dept_id: str | None = None
    program_id: str | None = None
    section_id: str | None = None


def hierarchy(session, obj: Any) -> AcademicHierarchy:
    """Resolve an object's complete academic hierarchy from persisted rows."""
    if obj is None:
        return AcademicHierarchy()
    tenant = getattr(obj, "tenant_id", None)
    dept = getattr(obj, "dept_id", None)
    program = getattr(obj, "program_id", None)
    section = getattr(obj, "section_id", None)
    school = getattr(obj, "school_id", None)
    scope_ref = getattr(obj, "scope_ref", "") or ""
    if not dept and session.get(D.Department, scope_ref):
        dept = scope_ref
    if not dept and scope_ref.startswith("scope_dept_"):
        candidate = scope_ref.removeprefix("scope_")
        dept = candidate if session.get(D.Department, candidate) else None
    if not dept and scope_ref.startswith("dept_"):
        candidate = scope_ref.removeprefix("dept_")
        dept = candidate if session.get(D.Department, candidate) else None
    if section and not program:
        row = session.get(D.Section, section)
        if row:
            dept, program = row.dept_id, getattr(row, "program_id", None)
    if program:
        row = session.get(D.Program, program)
        if row:
            dept = dept or row.dept_id
    if not dept and hasattr(obj, "course_id"):
        row = session.get(D.Course, getattr(obj, "course_id"))
        if row:
            dept, program = row.dept_id, program or row.program_id
    for linked_model, linked_attr in ((D.AcademicQualityReview, "review_id"),
                                      (D.AcademicCommittee, "committee_id"),
                                      (D.CommitteeMeeting, "meeting_id"),
                                      (D.CommitteeResolution, "resolution_id")):
        linked_id = getattr(obj, linked_attr, None)
        if linked_id and not dept:
            linked = session.get(linked_model, linked_id)
            if linked:
                parent = hierarchy(session, linked)
                dept = dept or parent.dept_id
                program = program or parent.program_id
                section = section or parent.section_id
    if dept:
        department = session.get(D.Department, dept)
        if department:
            # The current schema stores campus on departments; until a formal
            # faculty relation exists, campus is the only persisted parent scope.
            school = school or getattr(department, "school_id", None) or department.campus
    return AcademicHierarchy(tenant, school, dept, program, section)


def actor_hierarchy(ctx: dict, session) -> AcademicHierarchy:
    staff = session.query(D.StaffMember).filter(D.StaffMember.user_id == ctx.get("sub")).first()
    department = getattr(staff, "dept_id", None)
    scope_ref = (ctx.get("scope_ref") or "").strip()
    school = getattr(staff, "school_id", None)
    if not school and scope_ref.startswith("school_") and session.get(D.School, scope_ref):
        school = scope_ref
    if not department:
        # ``dept_cse`` is both a conventional department ID and a possible
        # scope prefix.  Check the persisted ID first so a valid department
        # scope is never reduced to ``cse`` before resolution.
        if scope_ref and session.get(D.Department, scope_ref):
            department = scope_ref
        else:
            ref = scope_ref.removeprefix("dept_").removeprefix("scope_")
            if session.get(D.Department, ref):
                department = ref
    program = getattr(staff, "program_id", None)
    section = getattr(staff, "section_id", None)
    if department:
        row = session.get(D.Department, department)
        school = school or (getattr(row, "school_id", None) if row else None) or (getattr(row, "campus", None) if row else None)
    return AcademicHierarchy(ctx.get("tenant_id"), school, department, program, section)


def dean_scope_assignments(ctx: dict, session) -> list[D.DeanScopeAssignment]:
    """Return only currently-effective persisted assignments for this Dean."""
    if ctx.get("office_n") != 6:
        return []
    now = datetime.utcnow()
    return session.query(D.DeanScopeAssignment).filter(
        D.DeanScopeAssignment.tenant_id == ctx.get("tenant_id"),
        D.DeanScopeAssignment.dean_user_id == ctx.get("sub"),
        D.DeanScopeAssignment.active == True,
        D.DeanScopeAssignment.effective_from <= now,
        (D.DeanScopeAssignment.effective_to == None) | (D.DeanScopeAssignment.effective_to >= now),
    ).all()


def dean_scope_allows(ctx: dict, session, target: AcademicHierarchy) -> bool:
    """Resolve a target against the Dean's persisted assignment rows.

    Development keeps legacy data readable until administrators have created
    assignments. Production deliberately fails closed when no assignment exists.
    """
    assignments = dean_scope_assignments(ctx, session)
    if not assignments:
        return demo_data_enabled()
    for assignment in assignments:
        if assignment.school_id and assignment.school_id != target.school_id:
            continue
        if assignment.dept_id and assignment.dept_id != target.dept_id:
            continue
        if assignment.program_id and assignment.program_id != target.program_id:
            continue
        if assignment.section_id and assignment.section_id != target.section_id:
            continue
        return True
    return False


def authorize_object(ctx: dict, session, obj: Any, action: str = "read", *, allow_dean: bool = True) -> bool:
    """Return whether actor may perform action on obj; raise 403 on denial."""
    actor = actor_hierarchy(ctx, session)
    target = hierarchy(session, obj)
    if not target.tenant_id or target.tenant_id != ctx.get("tenant_id"):
        raise HTTPException(403, "Academic object is outside the tenant scope")
    office = ctx.get("office_n")
    if allow_dean and office == 6:
        if dean_scope_allows(ctx, session, target):
            return True
        raise HTTPException(403, "Academic object is outside the Dean's assigned scope")
    if office not in {10, 17, 11, 12, 13, 14, 41, 42, 43}:
        raise HTTPException(403, "Academic object is outside the actor scope")
    if not actor.dept_id:
        if office == 17 and actor.school_id and target.school_id == actor.school_id:
            return True
        raise HTTPException(403, "Actor academic department scope is unavailable")
    if target.dept_id and target.dept_id != actor.dept_id:
        raise HTTPException(403, "Academic object is outside the department scope")
    if office in {11, 12, 13, 14} and target.section_id:
        if not actor.section_id or target.section_id != actor.section_id:
            raise HTTPException(403, "Academic object is outside the section scope")
    if actor.school_id and target.school_id and actor.school_id != target.school_id:
        raise HTTPException(403, "Academic object is outside the faculty scope")
    if actor.program_id and target.program_id and actor.program_id != target.program_id:
        raise HTTPException(403, "Academic object is outside the program scope")
    if action in {"approve", "reject", "publish"} and office != 6:
        raise HTTPException(403, "Actor cannot approve this academic object")
    return True
