"""Central, scope-aware evidence policy resolver for Administration closure."""
import json
from fastapi import HTTPException
import administration_models as A
import specialist_models as S

# These are minimum domain semantics when an institution has not configured a
# scoped policy.  They are deliberately declarative, not closure-endpoint code.
DEFAULTS={
    "FACILITIES":[["COMPLETION","WORK_ORDER"]],
    "WORKFORCE":[["STAFFING","COMPLETION"]],
    "IT":[["RESOLUTION","COMPLETION"]],
    "PROCUREMENT":[["GOODS_RECEIPT","COMPLETION"]],
    "BUDGET":[["FINANCE_DECISION"]],
    "INVENTORY":[["GOODS_RECEIPT","ASSET_HANDOFF"]],
}
ERROR_BY_TYPE={"GOODS_RECEIPT":"RECEIPT_REQUIRED","ASSET_HANDOFF":"ASSET_HANDOFF_REQUIRED","FINANCE_DECISION":"FINANCE_DECISION_REQUIRED","PO":"PO_REQUIRED"}

def _selected_policy(s,row):
    rows=s.query(A.AdministrativeEvidencePolicy).filter_by(tenant_id=row.tenant_id,category=row.category,active=True).all()
    rows=[p for p in rows if (not p.school_id or p.school_id==row.school_id) and (not p.department_id or p.department_id==row.department_id) and (not p.priority or p.priority==row.priority) and (p.responsible_office_n is None or p.responsible_office_n==row.responsible_office_n)]
    if not rows:return None
    score=lambda p:(bool(p.school_id),bool(p.department_id),bool(p.priority),p.responsible_office_n is not None,p.policy_priority)
    rows=sorted(rows,key=score,reverse=True)
    if len(rows)>1 and score(rows[0])==score(rows[1]):raise HTTPException(409,{"code":"EVIDENCE_POLICY_CONFLICT","policy_ids":[rows[0].id,rows[1].id]})
    return rows[0]

def resolve_evidence_policy(s,row):
    execution=s.query(A.AdministrativeExecution).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).first()
    if not execution or execution.status!="COMPLETED":
        return {"required":True,"satisfied":False,"missing":["EXECUTION"],"reason":"EXECUTION_INCOMPLETE","policy_id":None}
    policy=_selected_policy(s,row)
    groups=json.loads(policy.required_types) if policy else DEFAULTS.get(row.category, [["COMPLETION"]])
    uploaded={x.evidence_type.upper() for x in s.query(A.AdministrativeEvidence).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).filter(A.AdministrativeEvidence.deleted_at.is_(None),A.AdministrativeEvidence.verification_status=="VERIFIED").all()}
    missing=[]
    for group in groups:
        choices=[group] if isinstance(group,str) else group
        if not any(x in uploaded for x in choices):missing.append(choices[0])
    # A requisition may claim receipt/asset handoff only through its own boundary.
    if row.category=="PROCUREMENT":
        rec=s.query(S.ProcurementRequisition).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).first()
        if rec and rec.purchase_order_no and "PO" not in uploaded:missing.append("PO")
        if rec and rec.receipt_reference and "GOODS_RECEIPT" not in uploaded:missing.append("GOODS_RECEIPT")
        if rec and rec.asset_handoff_reference and "ASSET_HANDOFF" not in uploaded:missing.append("ASSET_HANDOFF")
    reason=next((ERROR_BY_TYPE.get(x,"EVIDENCE_REQUIRED") for x in missing),"")
    pending=[x.evidence_type.upper() for x in s.query(A.AdministrativeEvidence).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).filter(A.AdministrativeEvidence.deleted_at.is_(None),A.AdministrativeEvidence.verification_status.in_(("UPLOADED","UNDER_REVIEW"))).all()]
    return {"required":bool(groups),"satisfied":not missing,"missing":missing,"pending_verification":sorted(set(pending)),"reason":reason,"policy_id":policy.id if policy else None}
