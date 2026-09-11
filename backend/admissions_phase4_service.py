"""Server-side Phase 4 admissions assessment, merit, allocation and offer services."""
import json
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func

import domain_models as D
from admissions_service import transition_application
from core import uid, write_audit
from models import Approval, Person, User, WorkflowInstance


ACTIVE_ALLOCATION_STATUSES = {"RESERVED", "ALLOCATED"}


def _settings(session, app):
    binding = session.get(D.AdmissionCycleProgram, app.cycle_program_id)
    return json.loads(binding.settings_json or "{}") if binding else {}


def _scope(session, app, ctx):
    if app.tenant_id != ctx["tenant_id"]:
        raise HTTPException(404, "Application not found")
    campus = ctx.get("scope_ref", "")
    if ctx.get("scope_level") == "campus" and campus and not campus.startswith("scope_") and app.campus != campus:
        raise HTTPException(403, "Application is outside your authorized campus")


def advance_eligible(session, ctx, application_id, expected_version):
    app = session.get(D.Application, application_id)
    if not app: raise HTTPException(404, "Application not found")
    _scope(session, app, ctx)
    settings = _settings(session, app)
    if app.current_status == "ASSESSMENT_QUALIFIED":
        if settings.get("counselling_required"):
            return transition_application(session, ctx, app.id, "start_counselling", expected_version, "Counselling required after the qualified assessment")
        return transition_application(session, ctx, app.id, "start_allocation", expected_version, "Assessment qualified; ready for seat allocation")
    if app.current_status != "ELIGIBLE": raise HTTPException(409, "Application must be eligible or assessment-qualified to advance")
    if settings.get("entrance_required"):
        return transition_application(session, ctx, app.id, "start_assessment", expected_version, "Assessment required by programme policy")
    if settings.get("counselling_required"):
        return transition_application(session, ctx, app.id, "start_counselling", expected_version, "Counselling required by programme policy")
    # Explicit backend-controlled skip, never selected by React.
    return transition_application(session, ctx, app.id, "start_allocation", expected_version, "Assessment and counselling are not required by programme policy")


def record_assessment(session, ctx, application_id, body):
    app = session.get(D.Application, application_id)
    if not app: raise HTTPException(404, "Application not found")
    _scope(session, app, ctx)
    if app.status_version != body.expected_status_version: raise HTTPException(409, "Application changed; reload")
    if app.current_status == "ELIGIBLE":
        app = advance_eligible(session, ctx, app.id, app.status_version)
    if app.current_status != "ASSESSMENT_PENDING": raise HTTPException(409, "Assessment is not pending")
    if body.assessment_type not in {"ENTRANCE_EXAM", "ACADEMIC_MERIT", "OTHER"}: raise HTTPException(422, "Unsupported assessment type")
    row = D.ApplicationAssessment(id=uid(), tenant_id=app.tenant_id, application_id=app.id,
        assessment_type=body.assessment_type, score=body.score, max_score=body.max_score,
        percentile=body.percentile, source=body.source, status="VERIFIED", verified_by_user_id=ctx["sub"], verified_at=datetime.utcnow())
    session.add(row); session.commit()
    minimum = float(_settings(session, app).get("entrance_min_score", 0) or 0)
    if body.assessment_type == "ENTRANCE_EXAM" and (body.score is None or body.score < minimum):
        app = transition_application(session, ctx, app.id, "assessment_not_qualified", app.status_version, "Assessment score does not meet programme policy")
    else:
        app = transition_application(session, ctx, app.id, "qualify_assessment", app.status_version, "Verified assessment result")
        next_action = "start_counselling" if _settings(session, app).get("counselling_required") else "start_allocation"
        app = transition_application(session, ctx, app.id, next_action, app.status_version, "Advance under programme policy")
    write_audit(session, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.assessment.record", f"application:{app.id}", "", app.current_status, body.assessment_type)
    return app, row


def calculate_merit(session, ctx, application_id):
    app = session.get(D.Application, application_id)
    if not app: raise HTTPException(404, "Application not found")
    _scope(session, app, ctx)
    if app.current_status not in {"ELIGIBLE", "ASSESSMENT_PENDING", "ASSESSMENT_QUALIFIED", "COUNSELLING_PENDING", "COUNSELLING_COMPLETED", "ALLOCATION_PENDING"}:
        raise HTTPException(409, "Merit can only be calculated after eligibility")
    settings = _settings(session, app); merit = settings.get("merit", {})
    academic_weight = float(merit.get("academic_weight", 1 if not settings.get("entrance_required") else .4))
    entrance_weight = float(merit.get("entrance_weight", 0 if not settings.get("entrance_required") else .6))
    profile = json.loads(app.profile_json or "{}"); academic = float(profile.get("qualifying_percentage", profile.get("percentage", 0)) or 0)
    entrance = session.query(D.ApplicationAssessment).filter_by(application_id=app.id, assessment_type="ENTRANCE_EXAM", status="VERIFIED").order_by(D.ApplicationAssessment.verified_at.desc()).first()
    entrance_value = (float(entrance.score or 0) / float(entrance.max_score or 100)) * 100 if entrance else 0
    score = round(academic * academic_weight + entrance_value * entrance_weight, 4)
    row = D.ApplicationAssessment(id=uid(), tenant_id=app.tenant_id, application_id=app.id, assessment_type="ACADEMIC_MERIT", score=academic, merit_score=score, status="CALCULATED", source="phase4_merit", verified_by_user_id=ctx["sub"], verified_at=datetime.utcnow(), merit_context_json=json.dumps({"academic":academic,"entrance":entrance_value,"academic_weight":academic_weight,"entrance_weight":entrance_weight,"policy":merit}))
    session.add(row); session.flush()
    peers = session.query(D.ApplicationAssessment).join(D.Application, D.Application.id == D.ApplicationAssessment.application_id).filter(D.Application.tenant_id == app.tenant_id, D.Application.cycle_id == app.cycle_id, D.Application.selected_program_id == app.selected_program_id, D.ApplicationAssessment.assessment_type == "ACADEMIC_MERIT", D.ApplicationAssessment.status == "CALCULATED").order_by(D.ApplicationAssessment.merit_score.desc(), D.ApplicationAssessment.id.asc()).all()
    for rank, peer in enumerate(peers, 1): peer.rank = rank
    session.commit(); write_audit(session, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.merit.calculate", f"application:{app.id}", "", str(score), "Deterministic merit calculation")
    return row


def allocate(session, ctx, application_id, seat_pool_id, expected_version, round_no=1):
    app = session.get(D.Application, application_id)
    if not app: raise HTTPException(404, "Application not found")
    _scope(session, app, ctx)
    if app.status_version != expected_version: raise HTTPException(409, "Application changed; reload")
    if app.current_status != "ALLOCATION_PENDING": raise HTTPException(409, "Application is not ready for allocation")
    pool = session.query(D.AdmissionSeatPool).filter_by(id=seat_pool_id, tenant_id=app.tenant_id).with_for_update().first()
    if not pool or pool.cycle_id != app.cycle_id or pool.program_id != app.selected_program_id or pool.campus != app.campus: raise HTTPException(422, "Seat pool is outside application scope")
    if pool.quota_id:
        qualified = session.query(D.ApplicationEligibilityCheck).filter_by(application_id=app.id, quota_id=pool.quota_id, outcome="PASS").first()
        if not qualified: raise HTTPException(422, "Applicant is not qualified for this quota")
    if pool.status.lower() != "open": raise HTTPException(409, "Seat pool is not open")
    active = session.query(D.AdmissionSeatAllocation).filter(D.AdmissionSeatAllocation.application_id == app.id, D.AdmissionSeatAllocation.status.in_(ACTIVE_ALLOCATION_STATUSES)).first()
    if active: raise HTTPException(409, "Application already has an active allocation")
    used = session.query(D.AdmissionSeatAllocation).filter(D.AdmissionSeatAllocation.seat_pool_id == pool.id, D.AdmissionSeatAllocation.status.in_(ACTIVE_ALLOCATION_STATUSES)).count()
    merit = session.query(D.ApplicationAssessment).filter_by(application_id=app.id, assessment_type="ACADEMIC_MERIT").order_by(D.ApplicationAssessment.verified_at.desc()).first()
    # PostgreSQL holds the row lock above.  This conditional counter claim also
    # preserves the capacity invariant on SQLite, where FOR UPDATE is ignored.
    claimed = 0
    if used < pool.capacity:
        claimed = (session.query(D.AdmissionSeatPool)
                   .filter(D.AdmissionSeatPool.id == pool.id,
                           D.AdmissionSeatPool.reserved_capacity < D.AdmissionSeatPool.capacity)
                   .update({D.AdmissionSeatPool.reserved_capacity: D.AdmissionSeatPool.reserved_capacity + 1}, synchronize_session=False))
    if used >= pool.capacity or claimed != 1:
        position = (session.query(func.max(D.AdmissionSeatAllocation.waitlist_position)).filter_by(seat_pool_id=pool.id, status="WAITLISTED").scalar() or 0) + 1
        allocation = D.AdmissionSeatAllocation(id=uid(), tenant_id=app.tenant_id, application_id=app.id, seat_pool_id=pool.id, round_no=round_no, status="WAITLISTED", merit_rank=merit.rank if merit else None, waitlist_position=position)
        session.add(allocation); session.flush(); app = transition_application(session, ctx, app.id, "waitlist", app.status_version, f"No seat available; waitlist position {position}")
    else:
        allocation = D.AdmissionSeatAllocation(id=uid(), tenant_id=app.tenant_id, application_id=app.id, seat_pool_id=pool.id, round_no=round_no, status="RESERVED", merit_rank=merit.rank if merit else None)
        session.add(allocation); session.flush(); app = transition_application(session, ctx, app.id, "allocate", app.status_version, "Seat reserved")
    write_audit(session, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.allocate", f"application:{app.id}", "", allocation.status, allocation.id)
    return app, allocation


def promote_waitlist(session, ctx, pool_id):
    pool=session.query(D.AdmissionSeatPool).filter_by(id=pool_id).with_for_update().first()
    if not pool: return None
    used=session.query(D.AdmissionSeatAllocation).filter(D.AdmissionSeatAllocation.seat_pool_id==pool.id,D.AdmissionSeatAllocation.status.in_(ACTIVE_ALLOCATION_STATUSES)).count()
    if used >= pool.capacity: return None
    waiting=session.query(D.AdmissionSeatAllocation).filter_by(seat_pool_id=pool.id,status="WAITLISTED").order_by(D.AdmissionSeatAllocation.waitlist_position, D.AdmissionSeatAllocation.created_at).first()
    if not waiting: return None
    app=session.get(D.Application,waiting.application_id)
    if not app or app.current_status != "WAITLISTED": return None
    claimed=(session.query(D.AdmissionSeatPool).filter(D.AdmissionSeatPool.id==pool.id,
        D.AdmissionSeatPool.reserved_capacity < D.AdmissionSeatPool.capacity).update({D.AdmissionSeatPool.reserved_capacity: D.AdmissionSeatPool.reserved_capacity + 1}, synchronize_session=False))
    if claimed != 1: return None
    waiting.status="RESERVED"; waiting.waitlist_position=None; session.commit()
    app=transition_application(session,ctx,app.id,"allocate",app.status_version,"Waitlist promotion")
    write_audit(session,ctx["sub"],ctx["sub"],ctx["office_n"],"admission.waitlist.promote",f"application:{app.id}","WAITLISTED","ALLOCATED",waiting.id)
    return waiting

def release_allocation(session, ctx, allocation, reason):
    if not allocation or allocation.status not in ACTIVE_ALLOCATION_STATUSES: return
    allocation.status = "RELEASED"; allocation.released_at = datetime.utcnow(); allocation.release_reason = reason
    (session.query(D.AdmissionSeatPool).filter(D.AdmissionSeatPool.id == allocation.seat_pool_id,
        D.AdmissionSeatPool.reserved_capacity > 0).update({D.AdmissionSeatPool.reserved_capacity: D.AdmissionSeatPool.reserved_capacity - 1}, synchronize_session=False))
    session.commit()
    write_audit(session, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.seat.release", f"allocation:{allocation.id}", "RESERVED", "RELEASED", reason)
    promotion_ctx = ctx if ctx.get("office_n", 0) else {"sub":"system","tenant_id":allocation.tenant_id,"office_n":15,"scope_level":"global","auth_level":"system"}
    promote_waitlist(session,promotion_ctx,allocation.seat_pool_id)

def expire_offers(session, ctx):
    rows=session.query(D.AdmissionOffer).filter(D.AdmissionOffer.tenant_id==ctx["tenant_id"],D.AdmissionOffer.status=="ISSUED",D.AdmissionOffer.expires_at<=datetime.utcnow()).all(); count=0
    for offer in rows:
        app=session.get(D.Application,offer.application_id)
        if not app or app.current_status != "OFFERED": continue
        release_allocation(session,ctx,session.get(D.AdmissionSeatAllocation,offer.allocation_id),"Offer expired")
        offer.status="EXPIRED";session.commit();transition_application(session,ctx,app.id,"expire_offer",app.status_version,"Offer expiry processed");count+=1
    return count


def recommend_offer(session, ctx, application_id, expected_version):
    app = session.get(D.Application, application_id)
    if not app: raise HTTPException(404, "Application not found")
    _scope(session, app, ctx)
    allocation = session.query(D.AdmissionSeatAllocation).filter(D.AdmissionSeatAllocation.application_id == app.id, D.AdmissionSeatAllocation.status.in_(ACTIVE_ALLOCATION_STATUSES)).first()
    if not allocation: raise HTTPException(409, "A valid allocation is required")
    if app.status_version != expected_version:
        raise HTTPException(409, "Application changed; reload before performing this action")

    if app.current_status not in {"ALLOCATED", "OFFER_RECOMMENDATION_PENDING", "OFFER_APPROVAL_PENDING"}:
        raise HTTPException(409, "Direct offer issue is only available after seat allocation")

    try:
        # Institution policy: the Admissions Office sends offers directly after
        # allocation. Retain the canonical states, but do not create an approval workflow.
        if app.current_status == "ALLOCATED":
            app = transition_application(session, ctx, app.id, "recommend_offer", app.status_version,
                                         "Offer prepared for direct issue", skip_capability=True, commit=False)
        if app.current_status == "OFFER_RECOMMENDATION_PENDING":
            app = transition_application(session, ctx, app.id, "approve_offer", app.status_version,
                                         "Approval bypassed by direct-offer policy", skip_capability=True, commit=False)
        if app.current_status == "OFFER_APPROVAL_PENDING":
            app = transition_application(session, ctx, app.id, "issue_offer", app.status_version,
                                         "Offer issued directly by Admissions Office", skip_capability=True, commit=False)

        pool = session.get(D.AdmissionSeatPool, allocation.seat_pool_id)
        offer = D.AdmissionOffer(id=uid(), tenant_id=app.tenant_id, application_id=app.id,
                                 allocation_id=allocation.id, workflow_id=None,
                                 offer_no=f"OFF-{datetime.utcnow().year}-{uid().upper()}", status="ISSUED",
                                 issued_at=datetime.utcnow(), expires_at=datetime.utcnow() + timedelta(days=7),
                                 program_id=app.selected_program_id, campus=app.campus,
                                 quota_id=pool.quota_id if pool else None, conditions_json="[]")
        allocation.status = "ALLOCATED"
        session.add(offer)
        session.commit()
    except Exception:
        session.rollback()
        raise
    write_audit(session, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.offer.issue_direct",
                f"application:{app.id}", "ALLOCATED", "OFFERED", offer.offer_no)
    return app, offer


def issue_offer(session, ctx, application_id, expected_version, expiry_days=7):
    app = session.get(D.Application, application_id)
    if not app: raise HTTPException(404, "Application not found")
    _scope(session, app, ctx)
    allocation = session.query(D.AdmissionSeatAllocation).filter(D.AdmissionSeatAllocation.application_id == app.id, D.AdmissionSeatAllocation.status.in_(ACTIVE_ALLOCATION_STATUSES)).first()
    link = session.query(D.AdmissionWorkflowLink).filter_by(application_id=app.id, purpose="admission_offer", status="active").first()
    if not allocation or not link: raise HTTPException(409, "Approved allocation workflow is required")
    workflow=session.get(WorkflowInstance,link.workflow_id)
    approved=workflow and workflow.state in {"approved","executed"}
    approved = approved or session.query(Approval).filter_by(workflow_id=link.workflow_id,decision="ALLOW").first() is not None
    if not approved: raise HTTPException(409,"Offer workflow approval is required before issue")
    app = transition_application(session, ctx, app.id, "issue_offer", expected_version, "Offer issued")
    pool = session.get(D.AdmissionSeatPool, allocation.seat_pool_id)
    offer = D.AdmissionOffer(id=uid(), tenant_id=app.tenant_id, application_id=app.id, allocation_id=allocation.id, workflow_id=link.workflow_id, offer_no=f"OFF-{datetime.utcnow().year}-{uid().upper()}", status="ISSUED", issued_at=datetime.utcnow(), expires_at=datetime.utcnow()+timedelta(days=expiry_days), program_id=app.selected_program_id, campus=app.campus, quota_id=pool.quota_id if pool else None, conditions_json="[]")
    allocation.status="ALLOCATED"; session.add(offer); session.commit(); write_audit(session, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.offer.issue", f"application:{app.id}", "", "OFFERED", offer.offer_no)
    return app, offer
