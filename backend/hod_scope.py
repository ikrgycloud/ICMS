"""Server-side department scope helpers for the Head of Department office."""
from fastapi import HTTPException

import domain_models as D


def hod_department(s, ctx):
    """Return the authoritative HOD department or fail closed for office 10."""
    if ctx.get("office_n") != 10:
        return None
    staff_rows = s.query(D.StaffMember).filter(D.StaffMember.user_id == ctx.get("sub")).all()
    if len(staff_rows) != 1:
        raise HTTPException(403, "A unique StaffMember link is required for HOD department access")
    staff = staff_rows[0]
    if not staff.dept_id:
        raise HTTPException(403, "The authenticated HOD has no department assignment")
    department = s.query(D.Department).get(staff.dept_id)
    if not department:
        raise HTTPException(403, "The authenticated HOD department is unavailable")
    if department.hod_person_id != staff.id:
        raise HTTPException(403, "The authenticated staff record is not the configured HOD for this department")
    token_scope = (ctx.get("scope_ref") or "").strip()
    if token_scope and not token_scope.startswith("scope_") and token_scope != department.id:
        raise HTTPException(403, "The HOD token scope conflicts with the configured department")
    return department


def hod_department_id(s, ctx):
    department = hod_department(s, ctx)
    return department.id if department else None


def require_hod_department_resource(s, ctx, department_id, message="This resource belongs to another department"):
    """Reject cross-department HOD access; retain behavior for all other roles."""
    hod_id = hod_department_id(s, ctx)
    if hod_id is not None and department_id != hod_id:
        raise HTTPException(403, message)
    return hod_id
