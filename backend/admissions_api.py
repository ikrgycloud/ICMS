"""Phase 1 admissions API: compatibility read/decision endpoints plus actions."""
import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy import desc

from admissions_schemas import (AdmissionActionIn, LegacyAdmissionDecisionIn, CycleIn, CycleProgramIn,
                                ApplicantStartIn, ApplicantProfileIn, PreferenceIn, PreferenceOrderIn,
                                DocumentIn, ApplicantSubmitIn)
from admissions_schemas import (EligibilityRuleIn, QuotaIn, EligibilityEvaluateIn, AssessmentIn,
    CounsellingSessionIn, CounsellingIn, SeatPoolIn, AllocationIn, OfferActionIn, FeeResolutionIn,
    ApplicantInvoiceIn, ApplicantPaymentIn, PaymentVerificationIn, FinalAdmissionIn, ConvertApplicantIn)
from admissions_eligibility_service import evaluate_application, SUPPORTED_RULE_TYPES, SUPPORTED_OPERATORS
from admissions_service import legacy_decision, transition_application
from admissions_phase4_service import advance_eligible, record_assessment, calculate_merit, allocate, recommend_offer, issue_offer, release_allocation, expire_offers
from admissions_phase5_service import (resolve_fees, issue_applicant_invoice, record_applicant_payment,
    verify_payment, clear_finance, request_final_approval, complete_final_approval, checklist, convert_to_student)
from admissions_phase2_service import (application_for_token, application_payload, assert_editable,
    assert_version, create_access_token, cycle_program_or_404, now_utc, parse_datetime,
    save_application, submit_application, cycle_is_open, document_completeness)
from domain_api import gate, require
from capabilities import MODULE_ACTIONS, action_allowed_for_office
from core import auth, db, uid, write_audit
from database import office, TENANT
from matrices import rbac_for
from models import WorkflowInstance, User, Approval
import domain_models as D

router = APIRouter(prefix="/api", tags=["admissions"])


def _can(ctx, action):
    if not action_allowed_for_office("admissions", action, ctx["office_n"]):
        return False
    verb = MODULE_ACTIONS["admissions"].get(action)
    if not verb:
        return False
    return rbac_for(ctx["office_n"], office(ctx["office_n"])["level"], verb) != "Not Allowed"


def _application_payload(application):
    return {
        "id": application.id, "name": application.applicant_name, "email": application.email,
        "program": application.program_name, "program_id": application.selected_program_id, "score": application.score,
        "status": application.status,  # original frontend/API contract
        "current_status": application.current_status, "status_version": application.status_version,
    }


def _staff(s, ctx, action):
    if not _can(ctx, action):
        raise HTTPException(403, "Not authorized for this admissions action")
    require(gate(s, ctx, "admissions", action)[0])


def _token_application(s, application_id, token):
    return application_for_token(s, token, application_id)


def _assert_application_scope(application, ctx):
    actor_campus = ctx.get("scope_ref", "")
    if (ctx.get("scope_level") == "campus" and actor_campus
            and not actor_campus.startswith("scope_") and application.campus != actor_campus):
        raise HTTPException(403, "Application is outside your authorized campus")


def _validate_rule_body(s, body, tenant_id):
    cycle = s.get(D.AdmissionCycle, body.cycle_id)
    if not cycle or cycle.tenant_id != tenant_id:
        raise HTTPException(404, "Cycle not found")
    if body.program_id:
        program = s.get(D.Program, body.program_id)
        if not program or program.tenant_id != tenant_id:
            raise HTTPException(422, "Programme is outside this tenant")
        if not s.query(D.AdmissionCycleProgram).filter_by(tenant_id=tenant_id, cycle_id=cycle.id,
                                                           program_id=program.id, active=True).first():
            raise HTTPException(422, "Programme is not active for this cycle")
    criteria = body.criteria or {}
    rule_type = str(criteria.get("rule_type") or body.rule_key or "").upper()
    if rule_type not in SUPPORTED_RULE_TYPES:
        raise HTTPException(422, "Unsupported eligibility rule type")
    if rule_type == "REQUIRED_DOCUMENT":
        if not (criteria.get("document_type") or criteria.get("value")):
            raise HTTPException(422, "A required document type is needed")
    else:
        if not criteria.get("field") or "value" not in criteria:
            raise HTTPException(422, "A field and configured value are required")
        if criteria.get("operator", "==") not in SUPPORTED_OPERATORS:
            raise HTTPException(422, "Unsupported eligibility operator")
    if body.quota_code and not s.query(D.AdmissionQuota).filter_by(tenant_id=tenant_id,
            cycle_id=body.cycle_id, code=body.quota_code).first():
        raise HTTPException(422, "Quota is not configured for this cycle")
    return cycle


def _validate_quota_body(s, body, tenant_id):
    cycle = s.get(D.AdmissionCycle, body.cycle_id)
    if not cycle or cycle.tenant_id != tenant_id:
        raise HTTPException(404, "Cycle not found")
    if body.program_id:
        program = s.get(D.Program, body.program_id)
        if not program or program.tenant_id != tenant_id:
            raise HTTPException(422, "Programme is outside this tenant")
        if not s.query(D.AdmissionCycleProgram).filter_by(tenant_id=tenant_id, cycle_id=cycle.id,
                                                           program_id=program.id, active=True).first():
            raise HTTPException(422, "Programme is not active for this cycle")
    if not body.code.strip() or not body.name.strip():
        raise HTTPException(422, "Quota code and name are required")
    return cycle


@router.get("/admissions/cycles")
def list_cycles(ctx=Depends(auth), s=Depends(db)):
    _staff(s, ctx, "view_cycle")
    rows = s.query(D.AdmissionCycle).filter(D.AdmissionCycle.tenant_id == ctx["tenant_id"]).all()
    return {"cycles": [{"id": row.id, "code": row.code, "name": row.name,
            "academic_year": row.academic_year, "campus": row.campus, "status": row.status,
            "application_open_date": row.opens_at.isoformat() if row.opens_at else None,
            "application_close_date": row.closes_at.isoformat() if row.closes_at else None,
            "configuration": json.loads(row.configuration_json or "{}") } for row in rows]}


@router.get("/admissions/programmes")
def list_admission_programmes(ctx=Depends(auth), s=Depends(db)):
    """Existing programme master records for authorised cycle configuration."""
    _staff(s, ctx, "view_cycle")
    rows = s.query(D.Program).filter(D.Program.tenant_id == ctx["tenant_id"]).order_by(D.Program.name).all()
    return {"programmes": [{"id": row.id, "code": row.code, "name": row.name,
                               "level": row.level, "department_id": row.dept_id} for row in rows]}


@router.get("/admissions/program-intake")
def admission_program_intake(ctx=Depends(auth), s=Depends(db)):
    _staff(s, ctx, "view_cycle")
    rows=s.query(D.AdmissionCycleProgram).filter_by(tenant_id=ctx["tenant_id"]).all();out=[]
    for row in rows:
        cycle=s.get(D.AdmissionCycle,row.cycle_id);program=s.get(D.Program,row.program_id);dept=s.get(D.Department,program.dept_id) if program else None
        out.append({"id":row.id,"cycle":cycle.name if cycle else "","academic_year":cycle.academic_year if cycle else "","program":program.name if program else "","department":dept.name if dept else "","campus":row.campus,"intake":row.intake,"active":row.active})
    return {"program_intake":out}


@router.get("/admissions/document-status")
def admission_document_status(ctx=Depends(auth), s=Depends(db)):
    _staff(s,ctx,"view_application");out=[]
    for app in s.query(D.Application).filter_by(tenant_id=ctx["tenant_id"]).all():
        _assert_application_scope(app,ctx);docs=s.query(D.ApplicationDocument).filter_by(application_id=app.id).all();complete=document_completeness(s,app);verified=sum(1 for doc in docs if doc.verification_status=="verified");pending=sum(1 for doc in docs if doc.verification_status in {"pending","uploaded"});officers=[]
        for doc in docs:
            user=s.get(User,doc.verified_by_user_id) if doc.verified_by_user_id else None
            if user: officers.append(user.username)
        out.append({"id":app.id,"application_no":app.application_no,"applicant_name":app.applicant_name,"status":app.current_status,"required":complete.get("required",0),"verified":verified,"pending":pending,"correction_required":app.current_status=="CORRECTION_REQUIRED","verification_status":"verified" if complete.get("required",0) and verified>=complete.get("required",0) else "pending","officers":sorted(set(officers))})
    return {"documents":out}


@router.get("/admissions/phase5-status")
def admission_phase5_status(ctx=Depends(auth), s=Depends(db)):
    _staff(s,ctx,"view_assessment");out=[]
    states={"OFFER_ACCEPTED","FEE_RESOLUTION_PENDING","INVOICE_ISSUED","PAYMENT_PENDING","PAYMENT_RECORDED","ACCOUNTS_VERIFIED","FINANCE_CLEARED","FINAL_APPROVAL_PENDING","FINAL_APPROVED","READY_TO_ADMIT","ENROLLED"}
    for app in s.query(D.Application).filter(D.Application.tenant_id==ctx["tenant_id"],D.Application.current_status.in_(states)).all():
        _assert_application_scope(app,ctx);invoice=s.query(D.FeeInvoice).filter_by(application_id=app.id,invoice_type="admission_fee").first();challan=s.query(D.AdmissionChallan).filter_by(invoice_id=invoice.id).first() if invoice else None;clearance=s.query(D.AdmissionFinanceClearance).filter_by(application_id=app.id).first();conversion=s.query(D.AdmissionConversion).filter_by(application_id=app.id).first();program=s.get(D.Program,app.selected_program_id);checks=checklist(s,ctx,app.id)
        out.append({"id":app.id,"application_no":app.application_no,"applicant_name":app.applicant_name,"program":program.name if program else app.program_name,"campus":app.campus,"status":app.current_status,"status_version":app.status_version,"invoice_id":invoice.id if invoice else None,"invoice_amount":invoice.amount if invoice else 0,"paid":invoice.paid if invoice else 0,"balance":(invoice.amount-invoice.paid) if invoice else 0,"invoice_status":invoice.status if invoice else "","challan_no":challan.challan_no if challan else "","challan_status":challan.status if challan else "","accounts_status":clearance.accounts_status if clearance else "PENDING","finance_status":clearance.finance_status if clearance else "PENDING","total_payable":clearance.total_payable if clearance else 0,"total_paid":clearance.total_paid if clearance else 0,"total_waived":clearance.total_waived if clearance else 0,"cleared_at":clearance.cleared_at.isoformat() if clearance and clearance.cleared_at else None,"checklist":checks,"conversion_status":conversion.status if conversion else "PENDING","student_identifier":conversion.student_identifier if conversion else "","converted_at":conversion.converted_at.isoformat() if conversion and conversion.converted_at else None})
    return {"applications":out}


@router.get("/admissions/final-approvals")
def admission_final_approvals(ctx=Depends(auth), s=Depends(db)):
    """Read-only final-admission queue backed by the shared workflow engine."""
    _staff(s, ctx, "view_assessment")
    rows = (s.query(D.AdmissionWorkflowLink)
            .filter_by(tenant_id=ctx["tenant_id"], purpose="final_admission")
            .all())
    out = []
    for link in rows:
        app = s.get(D.Application, link.application_id)
        workflow = s.get(WorkflowInstance, link.workflow_id)
        if not app or not workflow:
            continue
        _assert_application_scope(app, ctx)
        approvals = (s.query(Approval).filter_by(workflow_id=workflow.id)
                     .order_by(Approval.created_at).all())
        out.append({
            "application_id": app.id, "application_no": app.application_no,
            "applicant_name": app.applicant_name, "program": app.program_name,
            "application_status": app.current_status, "workflow_id": workflow.id,
            "workflow_state": workflow.state, "workflow_title": workflow.title,
            "link_status": link.status,
            "approval_count": len(approvals),
            "latest_decision": approvals[-1].decision if approvals else None,
        })
    return {"final_approvals": out}


@router.get("/admissions/director-monitoring")
def admission_director_monitoring(ctx=Depends(auth), s=Depends(db)):
    """Read-only aggregates for the Director's admissions monitoring views."""
    _staff(s, ctx, "view_assessment")
    applications = []
    for app in s.query(D.Application).filter_by(tenant_id=ctx["tenant_id"]).all():
        _assert_application_scope(app, ctx)
        applications.append(app)
    application_ids = [app.id for app in applications]
    counselling = s.query(D.ApplicationCounselling).filter(D.ApplicationCounselling.tenant_id == ctx["tenant_id"]).all()
    pools = []
    for pool in s.query(D.AdmissionSeatPool).filter_by(tenant_id=ctx["tenant_id"]).all():
        active = s.query(D.AdmissionSeatAllocation).filter(D.AdmissionSeatAllocation.seat_pool_id == pool.id, D.AdmissionSeatAllocation.status.in_(["RESERVED", "ALLOCATED"])).count()
        waiting = s.query(D.AdmissionSeatAllocation).filter_by(seat_pool_id=pool.id, status="WAITLISTED").count()
        program = s.get(D.Program, pool.program_id); quota = s.get(D.AdmissionQuota, pool.quota_id) if pool.quota_id else None
        pools.append({"id": pool.id, "program": program.name if program else pool.program_id, "campus": pool.campus, "quota": quota.name if quota else "General", "capacity": pool.capacity, "active": active, "available": max(0, pool.capacity - active), "waitlisted": waiting})
    offers = s.query(D.AdmissionOffer).filter(D.AdmissionOffer.tenant_id == ctx["tenant_id"], D.AdmissionOffer.application_id.in_(application_ids)).all() if application_ids else []
    return {"counselling": [{"application_id": row.application_id, "attendance_status": row.attendance_status, "outcome": row.outcome, "recommended_program_id": row.recommended_program_id} for row in counselling if row.application_id in application_ids], "seat_pools": pools, "offers": [{"application_id": row.application_id, "status": row.status} for row in offers]}


@router.post("/admissions/cycles")
def create_cycle(body: CycleIn, ctx=Depends(auth), s=Depends(db)):
    _staff(s, ctx, "manage_cycle")
    state = body.status.upper()
    if state not in {"DRAFT", "PENDING_APPROVAL", "APPROVED", "PUBLISHED", "CLOSED"}:
        raise HTTPException(422, "Invalid admission cycle status")
    row = D.AdmissionCycle(id=uid(), tenant_id=ctx["tenant_id"], code=f"ADM-{uid().upper()}",
        name=body.name.strip(), academic_year=body.academic_year.strip(), campus=body.campus.strip(),
        opens_at=parse_datetime(body.application_open_date), closes_at=parse_datetime(body.application_close_date),
        status=state, configuration_json=json.dumps(body.configuration))
    s.add(row); s.commit()
    write_audit(s, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.cycle.create", f"admission_cycle:{row.id}", "", state, row.name)
    return {"id": row.id, "code": row.code, "status": row.status}


@router.put("/admissions/cycles/{cycle_id}")
def update_cycle(cycle_id: str, body: CycleIn, ctx=Depends(auth), s=Depends(db)):
    _staff(s, ctx, "manage_cycle")
    row = s.get(D.AdmissionCycle, cycle_id)
    if not row or row.tenant_id != ctx["tenant_id"]: raise HTTPException(404, "Admission cycle not found")
    previous = row.status
    row.name, row.academic_year, row.campus = body.name.strip(), body.academic_year.strip(), body.campus.strip()
    row.opens_at, row.closes_at, row.status = parse_datetime(body.application_open_date), parse_datetime(body.application_close_date), body.status.upper()
    row.configuration_json, row.updated_at = json.dumps(body.configuration), now_utc()
    s.commit(); write_audit(s, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.cycle.update", f"admission_cycle:{row.id}", previous, row.status, row.name)
    return {"id": row.id, "status": row.status}


@router.post("/admissions/cycles/{cycle_id}/publish")
def publish_cycle(cycle_id: str, ctx=Depends(auth), s=Depends(db)):
    _staff(s, ctx, "manage_cycle")
    row = s.get(D.AdmissionCycle, cycle_id)
    if not row or row.tenant_id != ctx["tenant_id"]: raise HTTPException(404, "Admission cycle not found")
    if not row.opens_at or not row.closes_at or row.closes_at < row.opens_at:
        raise HTTPException(422, "A valid application window is required before publishing")
    previous, row.status, row.updated_at = row.status, "PUBLISHED", now_utc()
    s.commit(); write_audit(s, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.cycle.publish", f"admission_cycle:{row.id}", previous, row.status, row.name)
    return {"id": row.id, "status": row.status}


@router.post("/admissions/cycles/{cycle_id}/close")
def close_cycle(cycle_id: str, ctx=Depends(auth), s=Depends(db)):
    _staff(s, ctx, "manage_cycle")
    row = s.get(D.AdmissionCycle, cycle_id)
    if not row or row.tenant_id != ctx["tenant_id"]: raise HTTPException(404, "Admission cycle not found")
    previous, row.status, row.updated_at = row.status, "CLOSED", now_utc()
    s.commit(); write_audit(s, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.cycle.close", f"admission_cycle:{row.id}", previous, row.status, row.name)
    return {"id": row.id, "status": row.status}


@router.post("/admissions/cycles/{cycle_id}/programs")
def configure_cycle_program(cycle_id: str, body: CycleProgramIn, ctx=Depends(auth), s=Depends(db)):
    _staff(s, ctx, "manage_cycle")
    cycle = s.get(D.AdmissionCycle, cycle_id)
    program = s.get(D.Program, body.program_id)
    if not cycle or cycle.tenant_id != ctx["tenant_id"] or not program or program.tenant_id != ctx["tenant_id"]:
        raise HTTPException(404, "Cycle or programme not found")
    row = D.AdmissionCycleProgram(id=uid(), tenant_id=ctx["tenant_id"], cycle_id=cycle.id, program_id=program.id,
        campus=body.campus or cycle.campus, application_fee=body.application_fee, admission_fee=body.admission_fee,
        intake=body.intake, assessment_mode="entrance" if body.entrance_required else "merit", active=body.active,
        settings_json=json.dumps({"entrance_required": body.entrance_required, "counselling_required": body.counselling_required}))
    s.add(row); s.commit()
    write_audit(s, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.cycle_program.create", f"admission_cycle_program:{row.id}", "", "active" if row.active else "inactive", program.name)
    return {"id": row.id}


@router.get("/admissions/open-programs")
def open_programs(s=Depends(db)):
    rows = s.query(D.AdmissionCycleProgram).filter(D.AdmissionCycleProgram.tenant_id == TENANT, D.AdmissionCycleProgram.active == True).all()
    out = []
    for row in rows:
        cycle = s.get(D.AdmissionCycle, row.cycle_id); program = s.get(D.Program, row.program_id)
        if cycle and program and cycle_is_open(cycle):
            out.append({"id": row.id, "cycle_id": cycle.id, "cycle": cycle.name, "program_id": program.id,
                        "program": program.name, "campus": row.campus, "application_fee": row.application_fee})
    return {"programmes": out}


@router.post("/admissions/applicant/start")
def start_applicant_application(body: ApplicantStartIn, s=Depends(db)):
    cycle, cycle_program = cycle_program_or_404(s, TENANT, body.cycle_program_id, True)
    program = s.get(D.Program, cycle_program.program_id)
    application = D.Application(id=uid(), tenant_id=TENANT, cycle_id=cycle.id, cycle_program_id=cycle_program.id,
        application_no=f"APP-{now_utc().year}-{uid().upper()}", applicant_name=body.applicant_name.strip(),
        email=body.email.strip().lower(), program_id=program.id if program else None, program_name=program.name if program else "",
        selected_program_id=program.id if program else None, campus=cycle_program.campus or cycle.campus,
        status="submitted", current_status="DRAFT", status_version=0)
    s.add(application); token = create_access_token(s, application); s.commit()
    write_audit(s, f"applicant:{application.id}", "Applicant", 0, "admission.application.create", f"application:{application.id}", "", "DRAFT", "Applicant draft created")
    return {"application_id": application.id, "application_no": application.application_no, "access_token": token}


@router.get("/admissions/applicant/{application_id}")
def applicant_detail(application_id: str, x_applicant_access_token: str = Header(default=""), s=Depends(db)):
    application, _ = _token_application(s, application_id, x_applicant_access_token)
    return application_payload(s, application)


@router.post("/admissions/applicant/{application_id}/access/revoke")
def revoke_applicant_access(application_id: str, ctx=Depends(auth), s=Depends(db)):
    _staff(s, ctx, "edit_application")
    application = s.get(D.Application, application_id)
    if not application or application.tenant_id != ctx["tenant_id"]: raise HTTPException(404, "Application not found")
    now = now_utc()
    (s.query(D.ApplicantAccessToken).filter(D.ApplicantAccessToken.application_id == application.id,
        D.ApplicantAccessToken.tenant_id == application.tenant_id, D.ApplicantAccessToken.revoked_at == None)
        .update({D.ApplicantAccessToken.revoked_at: now}, synchronize_session=False))
    s.commit(); write_audit(s, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.applicant_access.revoke", f"application:{application.id}", "", application.current_status, "Applicant access revoked")
    return {"status": "revoked"}


@router.put("/admissions/applicant/{application_id}/profile")
def save_applicant_profile(application_id: str, body: ApplicantProfileIn,
                           x_applicant_access_token: str = Header(default=""), s=Depends(db)):
    application, token = _token_application(s, application_id, x_applicant_access_token)
    dob = date.fromisoformat(body.date_of_birth) if body.date_of_birth else None
    application = save_application(s, application, token, body.expected_status_version, {
        "applicant_name": body.applicant_name.strip(), "email": body.email.strip().lower(), "phone": body.phone.strip(),
        "date_of_birth": dob, "gender": body.gender.strip(), "profile_json": json.dumps(body.profile),
    }, "admission.application.update")
    return application_payload(s, application)


@router.post("/admissions/applicant/{application_id}/preferences")
def add_preference(application_id: str, body: PreferenceIn, x_applicant_access_token: str = Header(default=""), s=Depends(db)):
    application, token = _token_application(s, application_id, x_applicant_access_token)
    assert_editable(application); assert_version(application, body.expected_status_version)
    cycle, cycle_program = cycle_program_or_404(s, application.tenant_id, application.cycle_program_id, True)
    programme = s.get(D.Program, body.program_id)
    if not programme or programme.tenant_id != application.tenant_id: raise HTTPException(404, "Programme not found")
    if s.query(D.ApplicationPreference).filter_by(application_id=application.id, program_id=body.program_id).first():
        raise HTTPException(409, "Programme is already a preference")
    rank = s.query(D.ApplicationPreference).filter_by(application_id=application.id).count() + 1
    s.add(D.ApplicationPreference(id=uid(), tenant_id=application.tenant_id, application_id=application.id,
                                  program_id=body.program_id, preference_rank=rank))
    application.status_version += 1
    write_audit(s, f"applicant-token:{token.id}", "Applicant", 0, "admission.preference.add", f"application:{application.id}", "", "DRAFT", programme.name, "token", commit=False)
    s.commit(); return application_payload(s, application)


@router.put("/admissions/applicant/{application_id}/preferences/order")
def reorder_preferences(application_id: str, body: PreferenceOrderIn, x_applicant_access_token: str = Header(default=""), s=Depends(db)):
    application, token = _token_application(s, application_id, x_applicant_access_token)
    assert_editable(application); assert_version(application, body.expected_status_version)
    rows = s.query(D.ApplicationPreference).filter_by(application_id=application.id).all()
    if set(body.preference_ids) != {row.id for row in rows} or len(body.preference_ids) != len(rows):
        raise HTTPException(422, "Preference order must contain each application preference exactly once")
    mapping = {row.id: row for row in rows}
    for index, pref_id in enumerate(body.preference_ids, 1): mapping[pref_id].preference_rank = index
    application.status_version += 1
    write_audit(s, f"applicant-token:{token.id}", "Applicant", 0, "admission.preference.reorder", f"application:{application.id}", "", "DRAFT", "Preferences reordered", "token", commit=False)
    s.commit(); return application_payload(s, application)


@router.delete("/admissions/applicant/{application_id}/preferences/{preference_id}")
def remove_preference(application_id: str, preference_id: str, expected_status_version: int = Query(ge=0),
                      x_applicant_access_token: str = Header(default=""), s=Depends(db)):
    application, token = _token_application(s, application_id, x_applicant_access_token)
    assert_editable(application); assert_version(application, expected_status_version)
    row = s.query(D.ApplicationPreference).filter_by(id=preference_id, application_id=application.id).first()
    if not row: raise HTTPException(404, "Preference not found")
    s.delete(row); s.flush()
    for index, pref in enumerate(s.query(D.ApplicationPreference).filter_by(application_id=application.id).order_by(D.ApplicationPreference.preference_rank), 1): pref.preference_rank = index
    application.status_version += 1
    write_audit(s, f"applicant-token:{token.id}", "Applicant", 0, "admission.preference.remove", f"application:{application.id}", "", "DRAFT", "Preference removed", "token", commit=False)
    s.commit(); return application_payload(s, application)


@router.get("/admissions/applicant/{application_id}/document-requirements")
def document_requirements(application_id: str, x_applicant_access_token: str = Header(default=""), s=Depends(db)):
    application, _ = _token_application(s, application_id, x_applicant_access_token)
    _, cycle_program = cycle_program_or_404(s, application.tenant_id, application.cycle_program_id, False)
    rows = (s.query(D.AdmissionDocumentRequirement)
            .filter(D.AdmissionDocumentRequirement.tenant_id == application.tenant_id,
                    D.AdmissionDocumentRequirement.cycle_id == application.cycle_id,
                    D.AdmissionDocumentRequirement.active == True).all())
    return {"requirements": [{"id": row.id, "document_type": row.document_type, "mandatory": row.mandatory,
            "allowed_mime_types": row.allowed_mime_types, "max_size_bytes": row.max_size_bytes}
            for row in rows if row.program_id in (None, "", cycle_program.program_id)]}


@router.post("/admissions/applicant/{application_id}/documents")
def upload_document_metadata(application_id: str, body: DocumentIn, x_applicant_access_token: str = Header(default=""), s=Depends(db)):
    application, token = _token_application(s, application_id, x_applicant_access_token)
    assert_editable(application); assert_version(application, body.expected_status_version)
    if not body.storage_key.strip() or not body.file_name.strip(): raise HTTPException(422, "storage_key and file_name are required")
    requirement = s.get(D.AdmissionDocumentRequirement, body.requirement_id) if body.requirement_id else None
    if requirement and (requirement.tenant_id != application.tenant_id or requirement.cycle_id != application.cycle_id):
        raise HTTPException(403, "Document requirement is outside this application cycle")
    existing = (s.query(D.ApplicationDocument).filter_by(application_id=application.id, requirement_id=body.requirement_id).first()
                if body.requirement_id else None)
    if existing:
        existing.document_type, existing.storage_key, existing.file_name = body.document_type, body.storage_key, body.file_name
        existing.mime_type, existing.checksum, existing.verification_status = body.mime_type, body.checksum, "pending"
        event = "admission.document.replace"
    else:
        s.add(D.ApplicationDocument(id=uid(), tenant_id=application.tenant_id, application_id=application.id,
              requirement_id=body.requirement_id, document_type=body.document_type, storage_key=body.storage_key,
              file_name=body.file_name, mime_type=body.mime_type, checksum=body.checksum))
        event = "admission.document.upload"
    application.status_version += 1
    write_audit(s, f"applicant-token:{token.id}", "Applicant", 0, event, f"application:{application.id}", "", "DRAFT", body.document_type, "token", commit=False)
    s.commit(); return application_payload(s, application)


@router.post("/admissions/applicant/{application_id}/submit")
def applicant_submit(application_id: str, body: ApplicantSubmitIn, x_applicant_access_token: str = Header(default=""), s=Depends(db)):
    application, token = _token_application(s, application_id, x_applicant_access_token)
    return application_payload(s, submit_application(s, application, token, body.expected_status_version))


@router.get("/admissions/review-queue")
def review_queue(cycle_id: str = "", program_id: str = "", campus: str = "", status: str = "",
                 search: str = "", ctx=Depends(auth), s=Depends(db)):
    _staff(s, ctx, "review_application")
    query = s.query(D.Application).filter(D.Application.tenant_id == ctx["tenant_id"],
        D.Application.current_status.in_(["SUBMITTED", "RESUBMITTED", "REVIEW_IN_PROGRESS"]))
    if cycle_id: query = query.filter(D.Application.cycle_id == cycle_id)
    if program_id: query = query.filter(D.Application.selected_program_id == program_id)
    if campus: query = query.filter(D.Application.campus == campus)
    if status: query = query.filter(D.Application.current_status == status.upper())
    if search:
        like = f"%{search}%"
        query = query.filter((D.Application.application_no.ilike(like)) | (D.Application.applicant_name.ilike(like)))
    actor_campus = ctx.get("scope_ref", "")
    if ctx.get("scope_level") == "campus" and actor_campus and not actor_campus.startswith("scope_"):
        query = query.filter(D.Application.campus == actor_campus)
    rows = query.order_by(D.Application.submitted_at.desc()).all()
    payload = []
    for application in rows:
        cycle = s.get(D.AdmissionCycle, application.cycle_id)
        prefs = s.query(D.ApplicationPreference).filter_by(application_id=application.id).count()
        documents = document_completeness(s, application)
        payload.append({"id": application.id, "application_no": application.application_no, "applicant_name": application.applicant_name,
          "cycle": cycle.name if cycle else "", "campus": application.campus, "submitted_at": application.submitted_at.isoformat() if application.submitted_at else None,
          "current_status": application.current_status, "status_version": application.status_version,
          "preferences_count": prefs, "documents": documents,
          "permitted_actions": {"start_review": _can(ctx, "start_review"), "request_correction": _can(ctx, "request_correction"), "verify": _can(ctx, "complete_document_verification")}})
    return {"applications": payload}


@router.get("/admissions/{application_id}/detail")
def staff_application_detail(application_id: str, ctx=Depends(auth), s=Depends(db)):
    _staff(s, ctx, "view_application")
    application = s.get(D.Application, application_id)
    if not application or application.tenant_id != ctx["tenant_id"]: raise HTTPException(404, "Application not found")
    actor_campus = ctx.get("scope_ref", "")
    if ctx.get("scope_level") == "campus" and actor_campus and not actor_campus.startswith("scope_") and application.campus != actor_campus:
        raise HTTPException(403, "Application is outside your authorized campus")
    result = application_payload(s, application)
    result["permitted_actions"] = {action: _can(ctx, capability) for action, capability in {
        "start_review": "start_review", "request_correction": "request_correction",
        "complete_document_verification": "complete_document_verification", "evaluate_eligibility": "evaluate_eligibility"}.items()}
    return result

@router.get("/admissions/eligibility/rules")
def eligibility_rules(cycle_id: str = "", ctx=Depends(auth), s=Depends(db)):
    _staff(s,ctx,"view_eligibility"); q=s.query(D.AdmissionEligibilityRule).filter_by(tenant_id=ctx["tenant_id"])
    if cycle_id: q=q.filter_by(cycle_id=cycle_id)
    return {"rules":[{"id":r.id,"cycle_id":r.cycle_id,"program_id":r.program_id,"quota_code":r.quota_code,"rule_key":r.rule_key,"criteria":json.loads(r.criteria_json or '{}'),"active":r.active,"version":r.version} for r in q.all()]}

@router.post("/admissions/eligibility/rules")
def create_eligibility_rule(body: EligibilityRuleIn,ctx=Depends(auth),s=Depends(db)):
    _staff(s,ctx,"manage_eligibility_rules"); _validate_rule_body(s, body, ctx["tenant_id"])
    r=D.AdmissionEligibilityRule(id=uid(),tenant_id=ctx["tenant_id"],cycle_id=body.cycle_id,program_id=body.program_id,quota_code=body.quota_code,rule_key=body.rule_key,criteria_json=json.dumps(body.criteria),active=body.active)
    s.add(r);s.commit();write_audit(s,ctx["sub"],ctx["sub"],ctx["office_n"],"admission.eligibility_rule.create",f"eligibility_rule:{r.id}","","active",r.rule_key);return {"id":r.id}

@router.put("/admissions/eligibility/rules/{rule_id}")
def update_eligibility_rule(rule_id:str,body:EligibilityRuleIn,ctx=Depends(auth),s=Depends(db)):
    _staff(s,ctx,"manage_eligibility_rules");r=s.get(D.AdmissionEligibilityRule,rule_id)
    if not r or r.tenant_id!=ctx["tenant_id"]:raise HTTPException(404,"Rule not found")
    _validate_rule_body(s, body, ctx["tenant_id"])
    r.cycle_id,r.program_id,r.quota_code,r.rule_key,r.criteria_json,r.active=body.cycle_id,body.program_id,body.quota_code,body.rule_key,json.dumps(body.criteria),body.active;r.version+=1
    s.commit();write_audit(s,ctx["sub"],ctx["sub"],ctx["office_n"],"admission.eligibility_rule.update",f"eligibility_rule:{r.id}","","active" if r.active else "inactive",r.rule_key);return {"id":r.id,"version":r.version}

@router.get("/admissions/eligibility/quotas")
def quotas(cycle_id:str="",ctx=Depends(auth),s=Depends(db)):
    _staff(s,ctx,"view_eligibility");q=s.query(D.AdmissionQuota).filter_by(tenant_id=ctx["tenant_id"])
    if cycle_id:q=q.filter_by(cycle_id=cycle_id)
    return {"quotas":[{"id":x.id,"cycle_id":x.cycle_id,"program_id":x.program_id,"code":x.code,"name":x.name,"category_code":x.category_code,"description":x.description,"priority":x.priority,"active":x.active} for x in q.all()]}

@router.post("/admissions/eligibility/quotas")
def create_quota(body:QuotaIn,ctx=Depends(auth),s=Depends(db)):
    _staff(s,ctx,"manage_quotas"); _validate_quota_body(s, body, ctx["tenant_id"])
    if s.query(D.AdmissionQuota).filter_by(tenant_id=ctx["tenant_id"],cycle_id=body.cycle_id,code=body.code).first():raise HTTPException(409,"Quota code already exists")
    q=D.AdmissionQuota(id=uid(),tenant_id=ctx["tenant_id"],cycle_id=body.cycle_id,program_id=body.program_id,code=body.code,name=body.name,category_code=body.category_code,description=body.description,priority=body.priority,active=body.active)
    s.add(q);s.commit();write_audit(s,ctx["sub"],ctx["sub"],ctx["office_n"],"admission.quota.create",f"quota:{q.id}","","active",q.code);return {"id":q.id}

@router.put("/admissions/eligibility/quotas/{quota_id}")
def update_quota(quota_id:str,body:QuotaIn,ctx=Depends(auth),s=Depends(db)):
    _staff(s,ctx,"manage_quotas");q=s.get(D.AdmissionQuota,quota_id)
    if not q or q.tenant_id!=ctx["tenant_id"]:raise HTTPException(404,"Quota not found")
    _validate_quota_body(s, body, ctx["tenant_id"])
    duplicate = s.query(D.AdmissionQuota).filter(D.AdmissionQuota.tenant_id == ctx["tenant_id"],
        D.AdmissionQuota.cycle_id == body.cycle_id, D.AdmissionQuota.code == body.code,
        D.AdmissionQuota.id != q.id).first()
    if duplicate: raise HTTPException(409, "Quota code already exists")
    q.cycle_id,q.program_id,q.code,q.name,q.category_code,q.description,q.priority,q.active=body.cycle_id,body.program_id,body.code,body.name,body.category_code,body.description,body.priority,body.active
    s.commit();write_audit(s,ctx["sub"],ctx["sub"],ctx["office_n"],"admission.quota.update",f"quota:{q.id}","","active" if q.active else "inactive",q.code);return {"id":q.id}

@router.post("/admissions/{application_id}/eligibility/evaluate")
def evaluate_eligibility(application_id:str,body:EligibilityEvaluateIn,ctx=Depends(auth),s=Depends(db)):
    _staff(s,ctx,"evaluate_eligibility"); existing=s.get(D.Application, application_id)
    if not existing or existing.tenant_id != ctx["tenant_id"]: raise HTTPException(404, "Application not found")
    _assert_application_scope(existing, ctx)
    app,run=evaluate_application(s,ctx,application_id,body.expected_status_version)
    return {"application_id":app.id,"current_status":app.current_status,"status_version":app.status_version,"run_id":run.id,"outcome":run.outcome}

@router.get("/admissions/{application_id}/eligibility")
def eligibility_detail(application_id:str,ctx=Depends(auth),s=Depends(db)):
    _staff(s,ctx,"view_eligibility");app=s.get(D.Application,application_id)
    if not app or app.tenant_id!=ctx["tenant_id"]:raise HTTPException(404,"Application not found")
    _assert_application_scope(app, ctx)
    runs=s.query(D.EligibilityEvaluationRun).filter_by(application_id=app.id).order_by(D.EligibilityEvaluationRun.started_at.desc()).all()
    checks=s.query(D.ApplicationEligibilityCheck).filter_by(application_id=app.id).order_by(D.ApplicationEligibilityCheck.evaluated_at.desc()).all()
    rules={r.id:r for r in s.query(D.AdmissionEligibilityRule).filter_by(tenant_id=ctx["tenant_id"]).all()}
    quotas={q.id:q for q in s.query(D.AdmissionQuota).filter_by(tenant_id=ctx["tenant_id"]).all()}
    cycle=s.get(D.AdmissionCycle, app.cycle_id); program=s.get(D.Program, app.selected_program_id)
    return {"application":{"id":app.id,"application_no":app.application_no,"applicant_name":app.applicant_name,
        "cycle":cycle.name if cycle else "","program":program.name if program else app.program_name,"campus":app.campus,
        "status":app.current_status,"status_version":app.status_version},"runs":[{"id":r.id,"outcome":r.outcome,
        "started_at":r.started_at.isoformat() if r.started_at else None,"completed_at":r.completed_at.isoformat() if r.completed_at else None,
        "actor_id":r.initiated_by_user_id,"context":json.loads(r.context_json or "{}")}for r in runs],"checks":[{"run_id":c.evaluation_run_id,"rule_id":c.rule_id,
        "rule":rules[c.rule_id].rule_key if c.rule_id in rules else c.check_type,"rule_version":c.rule_version,"quota_id":c.quota_id,
        "quota":{"id":quotas[c.quota_id].id,"code":quotas[c.quota_id].code,"name":quotas[c.quota_id].name} if c.quota_id in quotas else None,
        "type":c.check_type,"outcome":c.outcome,"reason":c.reason,"values":json.loads(c.evaluated_values_json or '{}'),
        "evaluated_at":c.evaluated_at.isoformat() if c.evaluated_at else None}for c in checks]}

@router.get("/admissions/eligibility/queue")
def eligibility_queue(cycle_id: str = "", program_id: str = "", campus: str = "", status: str = "", quota_code: str = "", search: str = "", ctx=Depends(auth),s=Depends(db)):
    _staff(s,ctx,"view_eligibility")
    query=s.query(D.Application).filter(D.Application.tenant_id==ctx["tenant_id"],D.Application.current_status.in_(["DOCUMENT_VERIFIED","ELIGIBILITY_PENDING","ELIGIBLE","INELIGIBLE"]))
    if cycle_id: query=query.filter(D.Application.cycle_id == cycle_id)
    if program_id: query=query.filter(D.Application.selected_program_id == program_id)
    if campus: query=query.filter(D.Application.campus == campus)
    if status: query=query.filter(D.Application.current_status == status.upper())
    if search:
        like=f"%{search}%"; query=query.filter((D.Application.application_no.ilike(like)) | (D.Application.applicant_name.ilike(like)))
    actor_campus=ctx.get("scope_ref", "")
    if ctx.get("scope_level") == "campus" and actor_campus and not actor_campus.startswith("scope_"): query=query.filter(D.Application.campus == actor_campus)
    rows=query.order_by(D.Application.submitted_at.desc()).all(); payload=[]
    for a in rows:
        last=s.query(D.EligibilityEvaluationRun).filter_by(application_id=a.id).order_by(D.EligibilityEvaluationRun.started_at.desc()).first()
        evaluated_quotas = [item.get("quota") for item in json.loads(last.context_json or "{}").get("quotas", [])] if last else []
        if quota_code and (not last or quota_code not in evaluated_quotas): continue
        cycle=s.get(D.AdmissionCycle,a.cycle_id); program=s.get(D.Program,a.selected_program_id)
        payload.append({"id":a.id,"application_no":a.application_no,"applicant_name":a.applicant_name,"cycle":cycle.name if cycle else "","program":program.name if program else a.program_name,"campus":a.campus,"status":a.current_status,"status_version":a.status_version,"documents":document_completeness(s,a),"last_evaluation_at":last.completed_at.isoformat() if last and last.completed_at else None,"eligibility_result":last.outcome if last else "PENDING","permitted_actions":{"evaluate":_can(ctx,"evaluate_eligibility") and a.current_status == "DOCUMENT_VERIFIED"}})
    return {"applications":payload}

@router.get("/admissions/applicant/{application_id}/eligibility-status")
def applicant_eligibility_status(application_id:str,x_applicant_access_token:str=Header(default=""),s=Depends(db)):
    app,_=_token_application(s,application_id,x_applicant_access_token)
    public={"ELIGIBLE":"Eligible","INELIGIBLE":"Ineligible","ELIGIBILITY_PENDING":"Pending"}.get(app.current_status,"Pending")
    return {"eligibility_status":public,"application_status":app.current_status}


@router.post("/admissions/{application_id}/phase4/advance")
def phase4_advance(application_id: str, body: EligibilityEvaluateIn, ctx=Depends(auth), s=Depends(db)):
    _staff(s, ctx, "record_assessment")
    app = advance_eligible(s, ctx, application_id, body.expected_status_version)
    return _application_payload(app)


@router.get("/admissions/assessments/queue")
def assessment_queue(ctx=Depends(auth), s=Depends(db)):
    _staff(s, ctx, "view_assessment")
    rows=s.query(D.Application).filter(D.Application.tenant_id==ctx["tenant_id"], D.Application.current_status.in_(["ELIGIBLE","ASSESSMENT_PENDING","ASSESSMENT_QUALIFIED","COUNSELLING_PENDING","ALLOCATION_PENDING"])).all()
    return {"applications":[_application_payload(a) for a in rows if not (ctx.get("scope_level")=="campus" and ctx.get("scope_ref") and not ctx["scope_ref"].startswith("scope_") and a.campus != ctx["scope_ref"])]}


@router.post("/admissions/{application_id}/assessments")
def save_assessment(application_id: str, body: AssessmentIn, ctx=Depends(auth), s=Depends(db)):
    _staff(s, ctx, "record_assessment"); app, row = record_assessment(s, ctx, application_id, body)
    return {"application":_application_payload(app),"assessment_id":row.id,"assessment_status":row.status}


@router.post("/admissions/{application_id}/merit")
def calculate_application_merit(application_id: str, ctx=Depends(auth), s=Depends(db)):
    _staff(s, ctx, "manage_merit"); row=calculate_merit(s,ctx,application_id)
    return {"id":row.id,"merit_score":row.merit_score,"rank":row.rank,"context":json.loads(row.merit_context_json or "{}")}


@router.get("/admissions/counselling/sessions")
def counselling_sessions(cycle_id: str = "", ctx=Depends(auth), s=Depends(db)):
    _staff(s,ctx,"view_assessment"); q=s.query(D.AdmissionCounsellingSession).filter_by(tenant_id=ctx["tenant_id"])
    if cycle_id:q=q.filter_by(cycle_id=cycle_id)
    return {"sessions":[{"id":x.id,"cycle_id":x.cycle_id,"campus":x.campus,"scheduled_at":x.scheduled_at.isoformat() if x.scheduled_at else None,"mode":x.mode,"location":x.location,"status":x.status} for x in q.all()]}

@router.get("/admissions/counselling/queue")
def counselling_queue(cycle_id: str = "", program_id: str = "", ctx=Depends(auth), s=Depends(db)):
    _staff(s,ctx,"record_counselling"); q=s.query(D.Application).filter(D.Application.tenant_id==ctx["tenant_id"],D.Application.current_status=="COUNSELLING_PENDING")
    if cycle_id:q=q.filter(D.Application.cycle_id==cycle_id)
    if program_id:q=q.filter(D.Application.selected_program_id==program_id)
    rows=[]
    for app in q.all():
        if ctx.get("scope_level")=="campus" and ctx.get("scope_ref") and not ctx["scope_ref"].startswith("scope_") and app.campus != ctx["scope_ref"]:continue
        merit=s.query(D.ApplicationAssessment).filter_by(application_id=app.id,assessment_type="ACADEMIC_MERIT").order_by(D.ApplicationAssessment.verified_at.desc()).first()
        prefs=s.query(D.ApplicationPreference).filter_by(application_id=app.id).order_by(D.ApplicationPreference.preference_rank).all()
        rows.append({**_application_payload(app),"merit_score":merit.merit_score if merit else None,"merit_rank":merit.rank if merit else None,"preferences":[{"program_id":p.program_id,"rank":p.preference_rank} for p in prefs]})
    return {"applications":rows}


@router.post("/admissions/counselling/sessions")
def create_counselling_session(body: CounsellingSessionIn, ctx=Depends(auth), s=Depends(db)):
    _staff(s,ctx,"schedule_counselling"); cycle=s.get(D.AdmissionCycle,body.cycle_id)
    if not cycle or cycle.tenant_id != ctx["tenant_id"]:raise HTTPException(404,"Cycle not found")
    row=D.AdmissionCounsellingSession(id=uid(),tenant_id=ctx["tenant_id"],cycle_id=body.cycle_id,campus=body.campus or cycle.campus,scheduled_at=parse_datetime(body.scheduled_at),mode=body.mode,location=body.location,status="scheduled")
    s.add(row);s.commit();write_audit(s,ctx["sub"],ctx["sub"],ctx["office_n"],"admission.counselling.session.create",f"counselling_session:{row.id}","","scheduled",row.location);return {"id":row.id}


@router.post("/admissions/{application_id}/counselling")
def record_counselling(application_id: str, body: CounsellingIn, ctx=Depends(auth), s=Depends(db)):
    _staff(s,ctx,"record_counselling"); app=s.get(D.Application,application_id)
    if not app or app.tenant_id != ctx["tenant_id"]:raise HTTPException(404,"Application not found")
    _assert_application_scope(app,ctx)
    if app.status_version != body.expected_status_version:raise HTTPException(409,"Application changed; reload")
    if app.current_status != "COUNSELLING_PENDING":raise HTTPException(409,"Counselling is not pending")
    row=D.ApplicationCounselling(id=uid(),tenant_id=app.tenant_id,application_id=app.id,session_id=body.session_id,attendance_status=body.attendance_status,outcome="COMPLETED",counsellor_user_id=ctx["sub"],recorded_at=now_utc(),recommended_program_id=body.recommended_program_id or app.selected_program_id,recommended_quota_id=body.recommended_quota_id,preference_rank=body.preference_rank,remarks=body.remarks)
    s.add(row);s.commit();app=transition_application(s,ctx,app.id,"complete_counselling",app.status_version,"Counselling outcome recorded");app=transition_application(s,ctx,app.id,"start_allocation",app.status_version,"Ready for allocation");return {"application":_application_payload(app),"counselling_id":row.id}


@router.get("/admissions/seat-pools")
def seat_pools(cycle_id: str = "", ctx=Depends(auth), s=Depends(db)):
    _staff(s,ctx,"view_assessment");q=s.query(D.AdmissionSeatPool).filter_by(tenant_id=ctx["tenant_id"])
    if cycle_id:q=q.filter_by(cycle_id=cycle_id)
    out=[]
    for x in q.all():
        used=s.query(D.AdmissionSeatAllocation).filter(D.AdmissionSeatAllocation.seat_pool_id==x.id,D.AdmissionSeatAllocation.status.in_(["RESERVED","ALLOCATED"])).count();wait=s.query(D.AdmissionSeatAllocation).filter_by(seat_pool_id=x.id,status="WAITLISTED").count()
        out.append({"id":x.id,"cycle_id":x.cycle_id,"campus":x.campus,"program_id":x.program_id,"quota_id":x.quota_id,"capacity":x.capacity,"used":used,"available":max(0,x.capacity-used),"waitlisted":wait,"status":x.status})
    return {"seat_pools":out}


@router.post("/admissions/seat-pools")
def configure_seat_pool(body: SeatPoolIn, ctx=Depends(auth), s=Depends(db)):
    _staff(s,ctx,"manage_seat_pool"); cycle=s.get(D.AdmissionCycle,body.cycle_id);program=s.get(D.Program,body.program_id)
    if not cycle or not program or cycle.tenant_id != ctx["tenant_id"] or program.tenant_id != ctx["tenant_id"]:raise HTTPException(404,"Cycle or programme not found")
    row=s.query(D.AdmissionSeatPool).filter_by(tenant_id=ctx["tenant_id"],cycle_id=body.cycle_id,campus=body.campus,program_id=body.program_id,quota_id=body.quota_id,category_code=body.category_code,intake_key=body.intake_key).first()
    if not row: row=D.AdmissionSeatPool(id=uid(),tenant_id=ctx["tenant_id"],cycle_id=body.cycle_id,campus=body.campus,program_id=body.program_id,quota_id=body.quota_id,category_code=body.category_code,intake_key=body.intake_key);s.add(row)
    used=s.query(D.AdmissionSeatAllocation).filter(D.AdmissionSeatAllocation.seat_pool_id==row.id,D.AdmissionSeatAllocation.status.in_(["RESERVED","ALLOCATED"])).count()
    if body.capacity < used:raise HTTPException(409,"Capacity cannot be below active allocations")
    row.capacity,row.status=body.capacity,body.status;s.commit();write_audit(s,ctx["sub"],ctx["sub"],ctx["office_n"],"admission.seat_pool.configure",f"seat_pool:{row.id}","",str(body.capacity),"Seat pool configuration");return {"id":row.id}


@router.post("/admissions/{application_id}/allocate")
def allocate_application(application_id: str, body: AllocationIn, ctx=Depends(auth), s=Depends(db)):
    _staff(s,ctx,"allocate_seat"); app,row=allocate(s,ctx,application_id,body.seat_pool_id,body.expected_status_version,body.round_no);return {"application":_application_payload(app),"allocation_id":row.id,"allocation_status":row.status,"waitlist_position":row.waitlist_position}


@router.post("/admissions/{application_id}/offer/recommend")
def recommend_application_offer(application_id: str, body: OfferActionIn, ctx=Depends(auth), s=Depends(db)):
    _staff(s,ctx,"recommend_offer");app,wf=recommend_offer(s,ctx,application_id,body.expected_status_version);return {"application":_application_payload(app),"workflow_id":wf.id}


@router.post("/admissions/{application_id}/offer/issue")
def issue_application_offer(application_id: str, body: OfferActionIn, ctx=Depends(auth), s=Depends(db)):
    _staff(s,ctx,"issue_offer");app,offer=issue_offer(s,ctx,application_id,body.expected_status_version,body.expiry_days);return {"application":_application_payload(app),"offer_no":offer.offer_no,"expires_at":offer.expires_at.isoformat()}

@router.post("/admissions/offers/expire")
def process_expired_offers(ctx=Depends(auth),s=Depends(db)):
    _staff(s,ctx,"manage_waitlist"); return {"expired":expire_offers(s,ctx)}

@router.get("/admissions/waitlist")
def waitlist_queue(ctx=Depends(auth),s=Depends(db)):
    _staff(s,ctx,"manage_waitlist"); rows=s.query(D.AdmissionSeatAllocation).filter_by(tenant_id=ctx["tenant_id"],status="WAITLISTED").order_by(D.AdmissionSeatAllocation.seat_pool_id,D.AdmissionSeatAllocation.waitlist_position).all()
    return {"waitlist":[{"id":r.id,"application_id":r.application_id,"application_no":s.get(D.Application,r.application_id).application_no,"applicant_name":s.get(D.Application,r.application_id).applicant_name,"seat_pool_id":r.seat_pool_id,"rank":r.merit_rank,"position":r.waitlist_position,"round_no":r.round_no,"created_at":r.created_at.isoformat() if r.created_at else None,"status":r.status} for r in rows]}

@router.get("/admissions/offers")
def offers_queue(status: str = "", ctx=Depends(auth),s=Depends(db)):
    _staff(s,ctx,"view_assessment"); q=s.query(D.Application).filter(D.Application.tenant_id==ctx["tenant_id"],D.Application.current_status.in_(["OFFER_RECOMMENDATION_PENDING","OFFER_APPROVAL_PENDING","OFFERED","OFFER_ACCEPTED","OFFER_DECLINED","OFFER_EXPIRED"]))
    if status:q=q.filter(D.Application.current_status==status)
    out=[]
    for app in q.all():
        offer=s.query(D.AdmissionOffer).filter_by(application_id=app.id).order_by(D.AdmissionOffer.issued_at.desc()).first();link=s.query(D.AdmissionWorkflowLink).filter_by(application_id=app.id,purpose="admission_offer",status="active").first();wf=s.get(WorkflowInstance,link.workflow_id) if link else None
        out.append({**_application_payload(app),"offer_no":offer.offer_no if offer else None,"offer_status":offer.status if offer else None,"expires_at":offer.expires_at.isoformat() if offer and offer.expires_at else None,"workflow_id":link.workflow_id if link else None,"workflow_state":wf.state if wf else None,"can_recommend":_can(ctx,"recommend_offer") and app.current_status=="ALLOCATED","can_issue":_can(ctx,"issue_offer") and app.current_status=="OFFER_APPROVAL_PENDING"})
    return {"offers":out}

@router.get("/admissions/applicant/{application_id}/offer")
def applicant_offer(application_id:str,x_applicant_access_token:str=Header(default=""),s=Depends(db)):
    app,_=_token_application(s,application_id,x_applicant_access_token);expire_offers(s,{"sub":"system","tenant_id":app.tenant_id,"office_n":15,"scope_level":"global","auth_level":"system"});app=s.get(D.Application,app.id);offer=s.query(D.AdmissionOffer).filter_by(application_id=app.id).order_by(D.AdmissionOffer.issued_at.desc()).first()
    if not offer:return {"offer":None}
    program=s.get(D.Program,offer.program_id);quota=s.get(D.AdmissionQuota,offer.quota_id) if offer.quota_id else None
    return {"offer":{"offer_no":offer.offer_no,"status":offer.status,"programme":program.name if program else app.program_name,"campus":offer.campus,"quota":quota.name if quota else None,"issued_at":offer.issued_at.isoformat() if offer.issued_at else None,"expires_at":offer.expires_at.isoformat() if offer.expires_at else None,"terms":json.loads(offer.conditions_json or "[]")},"application_status":app.current_status,"status_version":app.status_version}

@router.post("/admissions/applicant/{application_id}/offer/{response}")
def respond_to_offer(application_id:str,response:str,body:EligibilityEvaluateIn,x_applicant_access_token:str=Header(default=""),s=Depends(db)):
    app,token=_token_application(s,application_id,x_applicant_access_token);expire_offers(s,{"sub":"system","tenant_id":app.tenant_id,"office_n":15,"scope_level":"global","auth_level":"system"});app=s.get(D.Application,app.id);offer=s.query(D.AdmissionOffer).filter_by(application_id=app.id,status="ISSUED").first()
    if not offer or app.current_status != "OFFERED":raise HTTPException(409,"No active offer")
    if app.status_version != body.expected_status_version:raise HTTPException(409,"Application changed; reload")
    ctx={"sub":f"applicant-token:{token.id}","tenant_id":app.tenant_id,"office_n":0,"scope_level":"individual","auth_level":"token"}
    if response == "accept":offer.status="ACCEPTED";offer.accepted_at=now_utc();action="accept_offer"
    elif response == "decline":
        offer.status="DECLINED";offer.declined_at=now_utc();allocation=s.get(D.AdmissionSeatAllocation,offer.allocation_id);release_allocation(s,ctx,allocation,"Applicant declined offer");action="decline_offer"
    else:raise HTTPException(422,"Invalid offer response")
    s.commit();app=transition_application(s,ctx,app.id,action,app.status_version,f"Applicant {response}ed offer",skip_capability=True);write_audit(s,ctx["sub"],"Applicant",0,f"admission.offer.{response}",f"application:{app.id}","OFFERED",app.current_status,offer.offer_no,"token");return {"application_status":app.current_status,"status_version":app.status_version}


@router.post("/admissions/{application_id}/fees/resolve")
def resolve_admission_fees(application_id: str, body: FeeResolutionIn, ctx=Depends(auth), s=Depends(db)):
    app=resolve_fees(s,ctx,application_id,body.expected_status_version,body.fee_structure_id,parse_datetime(body.due_date));return {"application":_application_payload(app)}


@router.post("/admissions/{application_id}/invoice")
def issue_admission_invoice(application_id: str, body: ApplicantInvoiceIn, ctx=Depends(auth), s=Depends(db)):
    app,invoice,challan=issue_applicant_invoice(s,ctx,application_id,body.expected_status_version,parse_datetime(body.due_date));return {"application":_application_payload(app),"invoice_id":invoice.id,"challan_no":challan.challan_no if challan else None}


@router.post("/admissions/{application_id}/payments")
def record_admission_payment(application_id: str, body: ApplicantPaymentIn, ctx=Depends(auth), s=Depends(db)):
    app,payment=record_applicant_payment(s,ctx,application_id,body.expected_status_version,body.amount,body.reference,body.method,body.challan_id);return {"application":_application_payload(app),"payment_id":payment.id}


@router.post("/admissions/{application_id}/payments/{payment_id}/verify")
def verify_admission_payment(application_id: str, payment_id: str, body: PaymentVerificationIn, ctx=Depends(auth), s=Depends(db)):
    app,payment=verify_payment(s,ctx,application_id,payment_id,body.expected_status_version,body.status,body.note);return {"application":_application_payload(app),"payment_status":payment.status}


@router.post("/admissions/{application_id}/finance/clear")
def clear_admission_finance(application_id: str, body: FinalAdmissionIn, ctx=Depends(auth), s=Depends(db)):
    app,row=clear_finance(s,ctx,application_id,body.expected_status_version);return {"application":_application_payload(app),"clearance":{"status":row.finance_status,"balance":row.balance}}


@router.post("/admissions/{application_id}/final-approval")
def request_admission_final_approval(application_id: str, body: FinalAdmissionIn, ctx=Depends(auth), s=Depends(db)):
    app,wf=request_final_approval(s,ctx,application_id,body.expected_status_version);return {"application":_application_payload(app),"workflow_id":wf.id}


@router.post("/admissions/{application_id}/final-approval/complete")
def complete_admission_final_approval(application_id: str, body: FinalAdmissionIn, ctx=Depends(auth), s=Depends(db)):
    app=complete_final_approval(s,ctx,application_id,body.expected_status_version);return {"application":_application_payload(app)}


@router.get("/admissions/{application_id}/ready-to-admit")
def admission_ready_to_admit(application_id: str, ctx=Depends(auth), s=Depends(db)):
    _staff(s,ctx,"view_assessment");return checklist(s,ctx,application_id)


@router.post("/admissions/{application_id}/convert")
def convert_admission_to_student(application_id: str, body: ConvertApplicantIn, ctx=Depends(auth), s=Depends(db)):
    conversion,student=convert_to_student(s,ctx,application_id,body.expected_status_version);return {"conversion_id":conversion.id,"student_id":student.id,"roll_no":student.roll_no}


@router.get("/admissions/applicant/{application_id}/finance")
def applicant_finance(application_id: str, x_applicant_access_token: str=Header(default=""), s=Depends(db)):
    app,_=_token_application(s,application_id,x_applicant_access_token);invoice=s.query(D.FeeInvoice).filter_by(application_id=app.id,invoice_type="admission_fee").first();assignments=s.query(D.ApplicantFeeAssignment).filter_by(application_id=app.id).all();challan=s.query(D.AdmissionChallan).filter_by(invoice_id=invoice.id).first() if invoice else None;clearance=s.query(D.AdmissionFinanceClearance).filter_by(application_id=app.id).first()
    return {"application_status":app.current_status,"invoice":None if not invoice else {"id":invoice.id,"amount":invoice.amount,"paid":invoice.paid,"balance":invoice.amount-invoice.paid,"status":invoice.status,"due_date":invoice.due_date.isoformat() if invoice.due_date else None},"components":[{"name":x.component_name,"amount":x.amount,"waived":x.waived_amount} for x in assignments],"challan":None if not challan else {"number":challan.challan_no,"amount":challan.amount,"status":challan.status,"due_at":challan.due_at.isoformat() if challan.due_at else None},"finance_clearance":clearance.finance_status if clearance else "PENDING"}


@router.get("/admissions")
def list_applications(ctx=Depends(auth), s=Depends(db)):
    if not _can(ctx, "view"):
        raise HTTPException(403, "Not authorized to view admissions")
    rows = (s.query(D.Application)
            .filter(D.Application.tenant_id == ctx.get("tenant_id"))
            .order_by(desc(D.Application.score)).all())
    return {
        "applications": [_application_payload(application) for application in rows],
        "can_verify": _can(ctx, "complete_document_verification"),
        "can_offer": _can(ctx, "issue_offer"),
    }


@router.post("/admissions/decide")
def decide_application(body: LegacyAdmissionDecisionIn, ctx=Depends(auth), s=Depends(db)):
    application = legacy_decision(s, ctx, body.application_id, body.action, body.expected_status_version)
    return {"status": application.status, "current_status": application.current_status,
            "status_version": application.status_version,
            "decision": {"outcome": "ALLOW", "reason": "Transition applied", "authority": "Guarded"}}


@router.post("/admissions/{application_id}/actions")
def apply_admission_action(application_id: str, body: AdmissionActionIn, ctx=Depends(auth), s=Depends(db)):
    application = transition_application(s, ctx, application_id, body.action,
                                         body.expected_status_version, body.reason)
    return _application_payload(application)
