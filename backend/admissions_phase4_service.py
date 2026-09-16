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


def _latest_merit(session, application_id):
    """Return the one current merit result for an applicant.

    Legacy data can contain more than one calculated merit row.  New writes are
    idempotent, while this selector keeps historical rows from affecting live
    allocation decisions.
    """
    return (session.query(D.ApplicationAssessment)
            .filter_by(application_id=application_id, assessment_type="ACADEMIC_MERIT",
                       status="CALCULATED")
            .order_by(D.ApplicationAssessment.verified_at.desc(), D.ApplicationAssessment.id.desc())
            .first())


def _rerank_merit_scope(session, tenant_id, cycle_id, program_id):
    """Rank one current merit result per applicant within a programme cycle."""
    rows = (session.query(D.ApplicationAssessment)
            .join(D.Application, D.Application.id == D.ApplicationAssessment.application_id)
            .filter(D.Application.tenant_id == tenant_id,
                    D.Application.cycle_id == cycle_id,
                    D.Application.selected_program_id == program_id,
                    D.ApplicationAssessment.assessment_type == "ACADEMIC_MERIT",
                    D.ApplicationAssessment.status == "CALCULATED")
            .order_by(D.ApplicationAssessment.verified_at.desc(), D.ApplicationAssessment.id.desc())
            .all())
    current = {}
    for row in rows:
        current.setdefault(row.application_id, row)
    for row in rows:
        if current[row.application_id].id != row.id:
            row.rank = None
            row.status = "SUPERSEDED"
    ranked = sorted(current.values(), key=lambda row: (-(row.merit_score or 0), row.application_id))
    for rank, row in enumerate(ranked, 1):
        row.rank = rank


def _rerank_merit(session, app):
    _rerank_merit_scope(session, app.tenant_id, app.cycle_id, app.selected_program_id)


def _require_verified_entrance(session, app):
    if not _settings(session, app).get("entrance_required"):
        return None
    row = (session.query(D.ApplicationAssessment)
           .filter_by(application_id=app.id, assessment_type="ENTRANCE_EXAM", status="VERIFIED")
           .order_by(D.ApplicationAssessment.verified_at.desc(), D.ApplicationAssessment.id.desc()).first())
    if not row:
        raise HTTPException(409, "A verified entrance assessment is required before merit can be calculated")
    return row


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
    if body.assessment_type not in {"ENTRANCE_EXAM", "OTHER"}: raise HTTPException(422, "Unsupported assessment type")
    if body.score is None or body.max_score is None or body.max_score <= 0 or body.score < 0 or body.score > body.max_score:
        raise HTTPException(422, "Score must be between zero and the maximum score")
    if not (body.source or "").strip():
        raise HTTPException(422, "An assessment evidence reference is required")
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
    entrance = _require_verified_entrance(session, app)
    academic_weight = float(merit.get("academic_weight", 1 if not settings.get("entrance_required") else .4))
    entrance_weight = float(merit.get("entrance_weight", 0 if not settings.get("entrance_required") else .6))
    profile = json.loads(app.profile_json or "{}"); academic = float(profile.get("qualifying_percentage", profile.get("percentage", 0)) or 0)
    entrance_value = (float(entrance.score or 0) / float(entrance.max_score or 100)) * 100 if entrance else 0
    score = round(academic * academic_weight + entrance_value * entrance_weight, 4)
    row = _latest_merit(session, app.id)
    if not row:
        row = D.ApplicationAssessment(id=uid(), tenant_id=app.tenant_id, application_id=app.id,
                                      assessment_type="ACADEMIC_MERIT")
        session.add(row)
    row.score, row.merit_score, row.status = academic, score, "CALCULATED"
    row.source, row.verified_by_user_id, row.verified_at = "phase4_merit", ctx["sub"], datetime.utcnow()
    row.merit_context_json = json.dumps({"academic":academic,"entrance":entrance_value,"academic_weight":academic_weight,"entrance_weight":entrance_weight,"policy":merit})
    session.flush()
    _rerank_merit(session, app)
    session.commit(); write_audit(session, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.merit.calculate", f"application:{app.id}", "", str(score), "Deterministic merit calculation")
    return row


def allocate(session, ctx, application_id, seat_pool_id, expected_version, round_no=1):
    app = session.get(D.Application, application_id)
    if not app: raise HTTPException(404, "Application not found")
    _scope(session, app, ctx)
    if app.status_version != expected_version: raise HTTPException(409, "Application changed; reload")
    if app.current_status != "ALLOCATION_PENDING": raise HTTPException(409, "Application is not ready for allocation")
    pool = session.query(D.AdmissionSeatPool).filter_by(id=seat_pool_id, tenant_id=app.tenant_id).with_for_update().first()
    merit = _latest_merit(session, app.id)
    if not merit or merit.rank is None:
        raise HTTPException(409, "A current calculated merit score and rank are required before seat allocation")
    counselling = (session.query(D.ApplicationCounselling)
                   .filter_by(application_id=app.id, outcome="COMPLETED")
                   .order_by(D.ApplicationCounselling.recorded_at.desc(), D.ApplicationCounselling.id.desc()).first())
    permitted_programmes = {app.selected_program_id}
    if counselling and counselling.recommended_program_id:
        permitted_programmes.add(counselling.recommended_program_id)
    if not pool or pool.cycle_id != app.cycle_id or pool.program_id not in permitted_programmes or pool.campus != app.campus: raise HTTPException(422, "Seat pool is outside the applicant's approved allocation scope")
    if pool.quota_id:
        qualified = session.query(D.ApplicationEligibilityCheck).filter_by(application_id=app.id, quota_id=pool.quota_id, outcome="PASS").first()
        if not qualified: raise HTTPException(422, "Applicant is not qualified for this quota")
    if pool.status.lower() != "open": raise HTTPException(409, "Seat pool is not open")
    active = session.query(D.AdmissionSeatAllocation).filter(D.AdmissionSeatAllocation.application_id == app.id, D.AdmissionSeatAllocation.status.in_(ACTIVE_ALLOCATION_STATUSES)).first()
    if active: raise HTTPException(409, "Application already has an active allocation")
    used = session.query(D.AdmissionSeatAllocation).filter(D.AdmissionSeatAllocation.seat_pool_id == pool.id, D.AdmissionSeatAllocation.status.in_(ACTIVE_ALLOCATION_STATUSES)).count()
    if pool.program_id != app.selected_program_id:
        programme = session.get(D.Program, pool.program_id)
        previous_programme = app.selected_program_id
        app.selected_program_id = pool.program_id
        app.allocated_program_id = pool.program_id
        app.program_id = pool.program_id
        app.program_name = programme.name if programme else app.program_name
        _rerank_merit_scope(session, app.tenant_id, app.cycle_id, previous_programme)
        _rerank_merit(session, app)
        write_audit(session, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.allocation.programme_change",
                    f"application:{app.id}", previous_programme or "", pool.program_id,
                    "Counselling-recommended programme selected for allocation", commit=False)
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
