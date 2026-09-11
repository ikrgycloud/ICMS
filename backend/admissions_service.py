"""Guarded Phase 1 admissions state transitions."""
from fastapi import HTTPException

from authority import ALLOW, authorize
from capabilities import MODULE_ACTIONS, action_allowed_for_office
from core import active_delegation_for, uid, write_audit
from database import office
from matrices import rbac_for
from models import Person, User
import domain_models as D
from admissions_policy import ACTION_CAPABILITIES, ACTION_TRANSITIONS, legacy_status_for


def _actor_name(session, ctx):
    user = session.get(User, ctx["sub"])
    if not user:
        return ctx["sub"]
    person = session.get(Person, user.person_id)
    return person.name if person else user.username


def _check_tenant_and_scope(application, ctx):
    if application.tenant_id != ctx.get("tenant_id"):
        raise HTTPException(404, "Application not found")
    if ctx.get("scope_level") != "campus":
        return
    actor_campus = (ctx.get("scope_ref") or "").strip()
    if actor_campus.startswith("scope_") or not actor_campus:
        return
    if application.campus and application.campus != actor_campus:
        raise HTTPException(403, "Application is outside your authorized campus")


def _require_capability(session, ctx, action):
    capability = ACTION_CAPABILITIES.get(action)
    if not capability:
        raise HTTPException(409, f"'{action}' is not available in Admissions Phase 1")
    if not action_allowed_for_office("admissions", capability, ctx["office_n"]):
        raise HTTPException(403, "This office is not authorized for this admissions action")
    verb = MODULE_ACTIONS["admissions"].get(capability)
    if not verb:
        raise HTTPException(403, "Admissions capability is not configured")
    office_meta = office(ctx["office_n"])
    decision = authorize(
        ctx=ctx, action=verb, resource="admissions",
        rbac_authority=rbac_for(ctx["office_n"], office_meta["level"], verb),
        active_delegation=active_delegation_for(session, ctx["sub"]),
        target_scope_level=ctx.get("scope_level", "individual"),
    )
    if decision.outcome != ALLOW:
        raise HTTPException(403, decision.reason)
    return decision


def transition_application(session, ctx, application_id, action, expected_status_version, reason="",
                            skip_capability=False, commit=True):
    """Apply one named action atomically; callers never supply a target state."""
    transition = ACTION_TRANSITIONS.get(action)
    if not transition:
        raise HTTPException(400, "Unknown admissions action")
    application = session.get(D.Application, application_id)
    if not application:
        raise HTTPException(404, "Application not found")
    _check_tenant_and_scope(application, ctx)
    if expected_status_version != application.status_version:
        raise HTTPException(409, "Application changed; reload before performing this action")
    if not skip_capability:
        _require_capability(session, ctx, action)
    allowed_from, target = transition
    current = application.current_status or "SUBMITTED"
    if current not in allowed_from:
        raise HTTPException(409, f"Action '{action}' is not valid from {current}")

    actor_name = _actor_name(session, ctx)
    next_version = application.status_version + 1
    try:
        application.current_status = target
        application.status_version = next_version
        application.status = legacy_status_for(target)
        session.add(D.ApplicationStatusHistory(
            id=uid(), tenant_id=application.tenant_id, application_id=application.id,
            from_status=current, to_status=target, action=action,
            status_version=next_version, actor_id=ctx["sub"], actor_name=actor_name,
            office_n=ctx["office_n"], reason=reason or "",
        ))
        write_audit(session, ctx["sub"], actor_name, ctx["office_n"],
                    f"admission.{action}", f"application:{application.id}",
                    current, target, reason or action, ctx.get("auth_level", "mfa"), commit=False)
        if commit:
            session.commit()
        else:
            session.flush()
    except Exception:
        session.rollback()
        raise
    return application


def legacy_decision(session, ctx, application_id, action, expected_status_version=None):
    """Compatibility adapter for the original verify/offer/reject endpoint."""
    mapping = {
        "verify": "complete_document_verification",
        "offer": "issue_offer",
        "reject": "reject",
    }
    business_action = mapping.get(action)
    if not business_action:
        raise HTTPException(400, "Invalid action")
    application = session.get(D.Application, application_id)
    if not application:
        raise HTTPException(404, "Application not found")
    version = application.status_version if expected_status_version is None else expected_status_version
    return transition_application(session, ctx, application_id, business_action, version,
                                  reason=f"Legacy admission decision: {action}")
