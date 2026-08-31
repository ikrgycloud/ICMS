"""Configuration-driven Phase 3 mandatory and quota eligibility evaluation."""
import json
from datetime import datetime
from fastapi import HTTPException
from admissions_service import transition_application
from core import uid, write_audit
import domain_models as D

SUPPORTED_RULE_TYPES = {"FIELD_COMPARISON", "MINIMUM_VALUE", "MAXIMUM_VALUE", "EQUALS", "REQUIRED_DOCUMENT"}
SUPPORTED_OPERATORS = {">=", "<=", "=="}

def _profile(app): return json.loads(app.profile_json or "{}")
def _value(app, field):
    return _profile(app).get(field)

def evaluate_rule(session, app, rule):
    c=json.loads(rule.criteria_json or "{}")
    typ=(c.get("rule_type") or rule.rule_key or "").upper()
    if typ == "REQUIRED_DOCUMENT":
        wanted=c.get("document_type") or c.get("value")
        docs=session.query(D.ApplicationDocument).filter_by(application_id=app.id).all()
        found=next((d for d in docs if d.document_type==wanted), None)
        if not found: return "MISSING_DATA", None, f"Missing document: {wanted}"
        return ("PASS" if found.verification_status=="verified" else "MISSING_DATA", found.verification_status, "Document is not verified")
    field=c.get("field"); observed=_value(app, field)
    if observed in (None, ""): return "MISSING_DATA", observed, f"Missing profile field: {field}"
    expected=c.get("value")
    op = c.get("operator", "==")
    if typ == "MINIMUM_VALUE": op = ">="
    elif typ == "MAXIMUM_VALUE": op = "<="
    elif typ == "EQUALS": op = "=="
    try:
        if op==">=": ok=float(observed)>=float(expected)
        elif op=="<=": ok=float(observed)<=float(expected)
        else: ok=str(observed).lower()==str(expected).lower()
    except (TypeError, ValueError): return "MISSING_DATA", observed, f"Invalid value for {field}"
    return ("PASS" if ok else "FAIL"), observed, f"{field} {op} {expected}"

def evaluate_application(session, ctx, application_id, expected_version):
    app=session.get(D.Application, application_id)
    if not app or app.tenant_id != ctx["tenant_id"]: raise HTTPException(404,"Application not found")
    if app.status_version != expected_version: raise HTTPException(409,"Application changed; reload")
    if app.current_status != "DOCUMENT_VERIFIED": raise HTTPException(409,"Eligibility starts only after document verification")
    # Start is recorded by the shared lifecycle service; individual results retain their own run.
    transition_application(session, ctx, app.id, "start_eligibility", expected_version, "Eligibility evaluation started")
    app=session.get(D.Application, app.id)
    run=D.EligibilityEvaluationRun(id=uid(), tenant_id=app.tenant_id, application_id=app.id, initiated_by_user_id=ctx["sub"], outcome="pending")
    session.add(run); session.flush()
    rules=session.query(D.AdmissionEligibilityRule).filter(D.AdmissionEligibilityRule.tenant_id==app.tenant_id,D.AdmissionEligibilityRule.cycle_id==app.cycle_id,D.AdmissionEligibilityRule.active==True).all()
    rules=[r for r in rules if r.program_id in (None, "", app.selected_program_id)]
    mandatory=[r for r in rules if not r.quota_code]
    quotas=session.query(D.AdmissionQuota).filter(D.AdmissionQuota.tenant_id==app.tenant_id,D.AdmissionQuota.cycle_id==app.cycle_id,D.AdmissionQuota.active==True).all()
    quotas=[q for q in quotas if q.program_id in (None, "", app.selected_program_id)]
    results=[]
    def persist(rule, quota=None):
        outcome, observed, reason=evaluate_rule(session,app,rule)
        session.add(D.ApplicationEligibilityCheck(id=uid(),tenant_id=app.tenant_id,application_id=app.id,rule_id=rule.id,quota_id=quota.id if quota else None,evaluation_run_id=run.id,check_type=rule.rule_key,outcome=outcome,evaluated_values_json=json.dumps({"expected":json.loads(rule.criteria_json or "{}"),"observed":observed}),reason=reason,evaluated_by_user_id=ctx["sub"],evaluated_at=datetime.utcnow(),rule_version=rule.version))
        return outcome
    mandatory_outcomes=[persist(r) for r in mandatory]
    mandatory_pass=all(x=="PASS" for x in mandatory_outcomes)
    quota_summary=[]
    for q in quotas:
        qr=[r for r in rules if r.quota_code==q.code and r.program_id in (None,"",app.selected_program_id)]
        outcomes=[persist(r,q) for r in qr]
        qualified=mandatory_pass and (not qr or all(x=="PASS" for x in outcomes))
        quota_summary.append({"quota":q.code,"qualified":qualified,"outcomes":outcomes})
    # No configured quotas means mandatory eligibility is the valid path.
    eligible=mandatory_pass and (not quotas or any(x["qualified"] for x in quota_summary))
    target="mark_eligible" if eligible else "mark_ineligible"
    run.outcome="ELIGIBLE" if eligible else "INELIGIBLE"; run.context_json=json.dumps({"mandatory":mandatory_outcomes,"quotas":quota_summary}); run.completed_at=datetime.utcnow()
    session.commit()
    transition_application(session,ctx,app.id,target,app.status_version,"Eligibility evaluation completed")
    write_audit(session,ctx["sub"],ctx["sub"],ctx["office_n"],"admission.eligibility.evaluate",f"application:{app.id}","ELIGIBILITY_PENDING",run.outcome,"Eligibility run " + run.id)
    return session.get(D.Application,app.id), run
