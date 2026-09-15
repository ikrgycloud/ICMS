"""Central object-level policy for the Administration bounded domain.

It composes the existing identity, delegation and academic-hierarchy data; it
does not create a second RBAC catalogue.
"""
from dataclasses import dataclass
from fastapi import HTTPException
from academic_scope import actor_hierarchy
from core import active_delegation_for

DEAN_ADMINISTRATION = 7
LEADERSHIP = {3, 4, 7}

@dataclass(frozen=True)
class AdministrationScope:
    tenant_id: str
    office_n: int
    school_id: str | None
    department_id: str | None
    delegated: bool

def resolve_administration_scope(session, ctx):
    hierarchy = actor_hierarchy(ctx, session)
    return AdministrationScope(ctx.get("tenant_id", ""), ctx["office_n"], hierarchy.school_id,
        hierarchy.dept_id, bool(active_delegation_for(session, ctx["sub"])))

def _in_org_scope(scope, row):
    # A bound department/school is an enforceable restriction.  Leadership
    # accounts without a persisted staff binding retain their configured broad
    # organisation scope until the identity migration supplies that binding.
    if scope.department_id and row.department_id and scope.department_id != row.department_id:
        return False
    if scope.school_id and row.school_id and scope.school_id != row.school_id:
        return False
    return True

def require_scope_values(session, ctx, school_id: str | None, department_id: str | None):
    """Validate a requested organisational scope and return its safe values.

    A scoped actor may never manufacture a record in another school or
    department.  Empty client values inherit the actor's persisted scope so a
    client cannot accidentally create an unscoped record.
    """
    scope = resolve_administration_scope(session, ctx)
    school_id, department_id = school_id or "", department_id or ""
    if scope.school_id and school_id and school_id != scope.school_id:
        raise HTTPException(403, "Requested school is outside your organisational scope")
    if scope.department_id and department_id and department_id != scope.department_id:
        raise HTTPException(403, "Requested department is outside your organisational scope")
    return school_id or (scope.school_id or ""), department_id or (scope.department_id or "")

def require_plan_scope(session, ctx, plan):
    school_id, department_id = require_scope_values(session, ctx, plan.school_id, plan.department_id)
    if school_id != (plan.school_id or "") or department_id != (plan.department_id or ""):
        raise HTTPException(403, "Plan is outside your organisational scope")

def can_view_requirement(session, ctx, row):
    scope = resolve_administration_scope(session, ctx)
    if row.tenant_id != scope.tenant_id or not _in_org_scope(scope, row):
        return False
    return scope.office_n in LEADERSHIP or row.created_by == ctx["sub"] or row.requester_id == ctx["sub"] or row.assigned_user_id == ctx["sub"] or row.responsible_office_n == scope.office_n

def require_view_requirement(session, ctx, row):
    if not can_view_requirement(session, ctx, row):
        raise HTTPException(403, "Requirement is outside your tenant or organisational scope")

def require_dean_scope(session, ctx, row):
    scope = resolve_administration_scope(session, ctx)
    if scope.office_n != DEAN_ADMINISTRATION or row.tenant_id != scope.tenant_id or not _in_org_scope(scope, row):
        raise HTTPException(403, "Dean Administration authority in the requirement scope is required")

def require_specialist_stage(session, ctx, row):
    require_view_requirement(session, ctx, row)
    if row.responsible_office_n != ctx["office_n"] or (row.assigned_user_id and row.assigned_user_id != ctx["sub"]):
        raise HTTPException(403, "Only the current specialist office/assignee may act")

def require_approver(session, ctx, row, pending_approval):
    require_view_requirement(session, ctx, row)
    if not pending_approval or pending_approval.approver_office_n != ctx["office_n"] or row.requester_id == ctx["sub"]:
        raise HTTPException(403, "Only the current policy approver may act")
