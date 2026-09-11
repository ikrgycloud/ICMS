"""Specialist-office execution boundaries for Administration handoffs."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import administration_models as A
import specialist_models as S
from core import auth, db, uid, write_audit
from administration_policy import require_specialist_stage
from administration_jobs import pause_sla, resume_sla, complete_sla, emit_outbox
from administration_state import require_transition
from evidence_policy import resolve_evidence_policy
from models import User, Person

router=APIRouter(prefix="/api/specialist",tags=["specialist-execution"])
OWNER={"WORKFORCE":24,"PROCUREMENT":32,"FACILITIES":29,"IT":27,"BUDGET":22}
MODEL={"WORKFORCE":S.HRStaffingRequest,"PROCUREMENT":S.ProcurementRequisition,"FACILITIES":S.FacilityWorkOrder,"IT":S.ITServiceRequest}

def actor(s,ctx):
    u=s.get(User,ctx["sub"]); p=s.get(Person,u.person_id) if u else None
    return p.name if p else ctx["sub"]
def record_for(s,row): return s.query(MODEL[row.category]).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).first() if row.category in MODEL else None

def record_payload(record):
    if isinstance(record,S.FacilityWorkOrder):
        return {"id":record.id,"type":"FACILITIES","status":record.status,"technician_id":record.technician_id,"priority":record.priority,"due_at":record.due_at.isoformat() if record.due_at else None,"notes":record.completion_notes}
    if isinstance(record,S.ITServiceRequest):
        return {"id":record.id,"type":"IT","status":record.status,"assignee_id":record.assignee_id,"priority":record.priority,"service_category":record.service_category,"notes":record.resolution_notes}
    if isinstance(record,S.HRStaffingRequest):
        return {"id":record.id,"type":"WORKFORCE","status":record.status,"staffing_reference":record.staffing_reference,"notes":record.completion_notes}
    if isinstance(record,S.ProcurementRequisition):
        return {"id":record.id,"type":"PROCUREMENT","status":record.status,"requisition_no":record.requisition_no,"purchase_order_no":record.purchase_order_no,"receipt_reference":record.receipt_reference,"asset_handoff_reference":record.asset_handoff_reference}
    return None

class CreateIn(BaseModel): assignee_id:str=""; specialist_category:str=""
class UpdateIn(BaseModel): expected_version:int; status:str; notes:str=""; external_reference:str=""

@router.get("/queue")
def queue(ctx=Depends(auth),s=Depends(db)):
    categories=[key for key,value in OWNER.items() if value==ctx["office_n"]]
    if not categories: raise HTTPException(403,"This office has no specialist administration queue")
    rows=s.query(A.AdministrativeRequirement).filter(A.AdministrativeRequirement.tenant_id==ctx.get("tenant_id"),A.AdministrativeRequirement.category.in_(categories),A.AdministrativeRequirement.responsible_office_n==ctx["office_n"],A.AdministrativeRequirement.state.in_(("ROUTED","IN_EXECUTION","IN_PROGRESS","ON_HOLD","PENDING_EVIDENCE"))).all()
    rows=[x for x in rows if not x.assigned_user_id or x.assigned_user_id==ctx["sub"]]
    return {"items":[{"requirement_id":x.id,"reference":x.reference_code,"title":x.title,"category":x.category,"state":x.state,"priority":x.priority,"version":x.version,"requester_id":x.requester_id,"school_id":x.school_id,"department_id":x.department_id,"due_at":x.due_at.isoformat() if x.due_at else None,"assignee_id":x.assigned_user_id,"record_id":getattr(record_for(s,x),"id",None)} for x in rows]}

@router.get("/{requirement_id}")
def specialist_detail(requirement_id:str,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=ctx.get("tenant_id"): raise HTTPException(404,"Requirement not found")
    require_specialist_stage(s,ctx,row)
    record=record_for(s,row)
    transitions=s.query(A.AdministrativeTransition).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).order_by(A.AdministrativeTransition.created_at).all()
    return {"requirement":{"id":row.id,"reference_code":row.reference_code,"title":row.title,"category":row.category,"priority":row.priority,"state":row.state,"version":row.version,"school_id":row.school_id,"department_id":row.department_id,"requester_id":row.requester_id,"due_at":row.due_at.isoformat() if row.due_at else None},"record":record_payload(record),"evidence_policy":resolve_evidence_policy(s,row),"history":[{"from":x.from_state,"to":x.to_state,"actor_id":x.actor_id,"reason":x.reason,"at":x.created_at.isoformat()} for x in transitions]}

@router.post("/{requirement_id}")
def create_specialist_record(requirement_id:str,body:CreateIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=ctx.get("tenant_id"):raise HTTPException(404,"Requirement not found")
    if row.category not in OWNER or OWNER[row.category]!=ctx["office_n"]:raise HTTPException(403,"This office does not own the specialist category")
    if row.category=="BUDGET": raise HTTPException(409,"Finance requirements use the Finance reservation and commitment APIs")
    require_specialist_stage(s,ctx,row)
    if row.state not in {"IN_EXECUTION","IN_PROGRESS"}:raise HTTPException(409,"Requirement has not been accepted for execution")
    if record_for(s,row):raise HTTPException(409,"Specialist record already exists")
    if body.assignee_id:
        user=s.get(User,body.assignee_id)
        if not user or user.tenant_id!=row.tenant_id or user.office_n!=ctx["office_n"]:raise HTTPException(422,"Assignee must belong to the specialist office")
    common={"id":uid(),"tenant_id":row.tenant_id,"requirement_id":row.id,"created_by":ctx["sub"],"updated_by":ctx["sub"]}
    if row.category=="FACILITIES": rec=S.FacilityWorkOrder(**common,technician_id=body.assignee_id or None,priority=row.priority,due_at=row.due_at)
    elif row.category=="IT": rec=S.ITServiceRequest(**common,assignee_id=body.assignee_id or None,priority=row.priority,service_category=body.specialist_category or row.subcategory)
    elif row.category=="WORKFORCE": rec=S.HRStaffingRequest(**common)
    else: rec=S.ProcurementRequisition(**common,requisition_no=f"PR-{datetime.utcnow().year}-{row.reference_code[-4:]}")
    s.add(rec); execution=s.query(A.AdministrativeExecution).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).first()
    if execution: execution.external_reference=rec.id
    write_audit(s,ctx["sub"],actor(s,ctx),ctx["office_n"],"specialist.record.create",f"{rec.__tablename__}:{rec.id}","","OPEN",row.reference_code,commit=False);s.commit();return {"id":rec.id,"type":rec.__tablename__}

@router.post("/{requirement_id}/update")
def update_specialist_record(requirement_id:str,body:UpdateIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=ctx.get("tenant_id"):raise HTTPException(404,"Requirement not found")
    require_specialist_stage(s,ctx,row)
    if row.version!=body.expected_version:raise HTTPException(409,"This record changed. Refresh before retrying.")
    rec=record_for(s,row)
    if not rec:raise HTTPException(409,"Create the specialist record before updating execution")
    allowed={"OPEN","IN_PROGRESS","COMPLETED","ON_HOLD"}
    if body.status not in allowed:raise HTTPException(422,"Invalid specialist status")
    old=getattr(rec,"status")
    allowed_next={"OPEN":{"IN_PROGRESS","ON_HOLD"},"IN_PROGRESS":{"IN_PROGRESS","ON_HOLD","COMPLETED"},"ON_HOLD":{"IN_PROGRESS","COMPLETED"},"COMPLETED":set()}
    if body.status not in allowed_next.get(old,set()): raise HTTPException(409,f"Cannot move specialist record {old} to {body.status}")
    old_state=row.state; target="PENDING_EVIDENCE" if body.status=="COMPLETED" else "IN_PROGRESS" if body.status=="IN_PROGRESS" else "ON_HOLD"
    require_transition(old_state, target)
    if body.status=="IN_PROGRESS" and old_state=="IN_EXECUTION":
        pass
    rec.status,rec.updated_by,rec.updated_at=body.status,ctx["sub"],datetime.utcnow()
    if isinstance(rec,S.FacilityWorkOrder):rec.completion_notes=body.notes
    elif isinstance(rec,S.ITServiceRequest):rec.resolution_notes=body.notes
    elif isinstance(rec,S.HRStaffingRequest):rec.completion_notes=body.notes
    else:
        if body.status=="IN_PROGRESS":rec.status="REVIEW"
        if body.status=="COMPLETED":
            if not body.external_reference:raise HTTPException(422,"Procurement completion requires a receipt reference")
            rec.receipt_reference=body.external_reference
    execution=s.query(A.AdministrativeExecution).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).first()
    if execution: execution.status=body.status;execution.completion_notes=body.notes;execution.updated_by=ctx["sub"];execution.updated_at=datetime.utcnow()
    if body.status=="ON_HOLD": pause_sla(s,row.id,row.tenant_id)
    elif body.status=="IN_PROGRESS": resume_sla(s,row.id,row.tenant_id)
    elif body.status=="COMPLETED": complete_sla(s,row.id,row.tenant_id)
    row.state,row.version,row.updated_by,row.updated_at=target,row.version+1,ctx["sub"],datetime.utcnow()
    s.add(A.AdministrativeTransition(id=uid(),tenant_id=row.tenant_id,requirement_id=row.id,from_state=old_state,to_state=target,actor_id=ctx["sub"],actor_office_n=ctx["office_n"],reason=body.notes,version=row.version))
    event=("ExecutionResumed" if body.status=="IN_PROGRESS" and old_state=="ON_HOLD" else "ExecutionStarted" if body.status=="IN_PROGRESS" else "ExecutionHeld" if body.status=="ON_HOLD" else "ExecutionCompleted" if body.status=="COMPLETED" else None)
    if event:emit_outbox(s,row.tenant_id,event,row.id,{"recipient":"user_7","title":f"{event}: {row.reference_code}","body":row.title,"severity":"info"},f"{event}:{row.id}")
    write_audit(s,ctx["sub"],actor(s,ctx),ctx["office_n"],"specialist.record.update",f"{rec.__tablename__}:{rec.id}",old,target,body.notes,commit=False);s.commit();return {"status":rec.status,"requirement_state":row.state,"version":row.version}
