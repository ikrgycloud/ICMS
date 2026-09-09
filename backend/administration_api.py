"""Typed Dean Administration APIs; the generic workflow is not used as storage."""
from datetime import datetime, timedelta
import json
import csv
import io
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func
import administration_models as A
import domain_models as D
from database import TENANT
from core import auth, db, uid, write_audit
from models import User, Person, Delegation
from administration_policy import can_view_requirement, require_view_requirement, require_dean_scope, require_specialist_stage, require_approver, require_scope_values, require_plan_scope
from evidence_storage import EvidenceStorageAdapter
from evidence_policy import resolve_evidence_policy
from administration_jobs import emit_outbox, pause_sla, resume_sla, complete_sla
from administration_state import require_transition

router = APIRouter(prefix="/api", tags=["administration"])
CATEGORIES = {"WORKFORCE", "BUDGET", "PROCUREMENT", "FACILITIES", "IT", "ASSETS", "INVENTORY", "SERVICES", "OTHER"}
EVIDENCE_TYPES={"COMPLETION","WORK_ORDER","PO","GOODS_RECEIPT","ASSET_HANDOFF","STAFFING","RESOLUTION","FINANCE_DECISION","OTHER"}
ALLOWED_EVIDENCE_CONTENT_TYPES={"application/pdf","image/png","image/jpeg","text/plain","application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
SPECIALIST_OFFICES = {"WORKFORCE": 24, "BUDGET": 22, "PROCUREMENT": 32, "FACILITIES": 29, "IT": 27, "ASSETS": 33, "INVENTORY": 33, "SERVICES": 26, "OTHER": 26}
DEAN, PRINCIPAL, CAMPUS_HEAD = 7, 4, 3

def _actor(s, ctx):
    user = s.get(User, ctx["sub"]); person = s.get(Person, user.person_id) if user else None
    return person.name if person else ctx.get("sub", "Unknown")

def _tenant(ctx): return ctx.get("tenant_id", TENANT)
def _is_dean(ctx): return ctx["office_n"] == DEAN
def _is_leader(ctx): return ctx["office_n"] in {DEAN, PRINCIPAL, CAMPUS_HEAD}

def _visible(row, ctx):
    # Callers needing this predicate should use _visible_with_session below.
    return row.tenant_id == _tenant(ctx)

def _visible_with_session(s, row, ctx):
    return can_view_requirement(s, ctx, row)

def _require_visible(s, row, ctx):
    require_view_requirement(s, ctx, row)

def _require_dean(s, ctx, row=None):
    if row is not None: return require_dean_scope(s, ctx, row)
    if not _is_dean(ctx): raise HTTPException(403, "Dean Administration authority required")

def _require_version(row, expected):
    if expected != row.version: raise HTTPException(409, "This record changed. Refresh before retrying.")

def _transition(s, row, ctx, target, reason=""):
    previous = row.state
    require_transition(previous, target)
    row.state, row.version, row.updated_at, row.updated_by = target, row.version + 1, datetime.utcnow(), ctx["sub"]
    s.add(A.AdministrativeTransition(id=uid(), tenant_id=row.tenant_id, requirement_id=row.id,
          from_state=previous, to_state=target, actor_id=ctx["sub"], actor_office_n=ctx["office_n"], reason=reason, version=row.version))
    s.flush()
    write_audit(s, ctx["sub"], _actor(s, ctx), ctx["office_n"], f"administration.requirement.{target.lower()}",
                f"administrative_requirement:{row.id}", previous, target, reason, ctx.get("auth_level", "mfa"), commit=False)

def _payload(s, row):
    assignments = s.query(A.AdministrativeAssignment).filter_by(requirement_id=row.id, tenant_id=row.tenant_id).order_by(A.AdministrativeAssignment.created_at).all()
    sla = s.query(A.AdministrativeSla).filter_by(requirement_id=row.id, tenant_id=row.tenant_id).first()
    execution = s.query(A.AdministrativeExecution).filter_by(requirement_id=row.id, tenant_id=row.tenant_id).first()
    return {"id": row.id, "reference_code": row.reference_code, "plan_id": row.plan_id, "school_id": row.school_id, "department_id": row.department_id,
      "source_office_n": row.source_office_n, "requester_id": row.requester_id, "category": row.category, "subcategory": row.subcategory,
      "title": row.title, "description": row.description, "justification": row.justification, "quantity": row.quantity, "estimated_cost": row.estimated_cost,
      "priority": row.priority, "urgency": row.urgency, "state": row.state, "responsible_office_n": row.responsible_office_n,
      "assigned_user_id": row.assigned_user_id, "due_at": row.due_at.isoformat() if row.due_at else None, "version": row.version,
      "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat(),
    "assignments": [{"id":x.id,"office_n":x.office_n,"user_id":x.user_id,"status":x.status,"due_at":x.due_at.isoformat() if x.due_at else None,"previous_office_n":x.previous_office_n,"previous_user_id":x.previous_user_id,"assigned_by":x.assigned_by,"reason":x.reason,"accepted_at":x.accepted_at.isoformat() if x.accepted_at else None,"created_at":x.created_at.isoformat()} for x in assignments],
      "sla": {"due_at":sla.due_at.isoformat(),"original_due_at":sla.original_due_at.isoformat() if sla.original_due_at else None,"status":sla.status,"paused_at":sla.paused_at.isoformat() if sla.paused_at else None,"paused_seconds":sla.paused_seconds,"breached_at":sla.breached_at.isoformat() if sla.breached_at else None,"completed_at":sla.completed_at.isoformat() if sla.completed_at else None} if sla else None,
      "execution": {"status":execution.status,"reference":execution.external_reference,"notes":execution.completion_notes} if execution else None}

class PlanIn(BaseModel):
    title: str; period_start: str = ""; period_end: str = ""; objectives: str = ""; school_id: str = ""; department_id: str = ""; expected_version: Optional[int] = None
class ActivityIn(BaseModel): title: str; milestone: str = ""; responsible_office_n: Optional[int] = None; due_at: Optional[datetime] = None
class RequirementIn(BaseModel):
    title: str; category: str; description: str = ""; justification: str = ""; subcategory: str = ""; school_id: str = ""; department_id: str = ""; plan_id: Optional[str] = None
    quantity: int = Field(default=1, ge=1); estimated_cost: float = Field(default=0, ge=0); priority: str = "MEDIUM"; urgency: str = "NORMAL"; due_at: Optional[datetime] = None; expected_version: Optional[int] = None
class ActionIn(BaseModel): expected_version: int; reason: str = ""
class CategorizeIn(ActionIn): category: str; subcategory: str = ""; priority: str = "MEDIUM"; due_at: Optional[datetime] = None
class AssignIn(ActionIn): office_n: int; user_id: Optional[str] = None; due_at: Optional[datetime] = None
class EvidenceIn(BaseModel): expected_version: int; evidence_type: str; description: str = ""; file_name: str = ""; checksum: str = ""
class ClosureIn(ActionIn): evidence_verified: bool; budget_verified: bool; execution_verified: bool
class PolicyIn(BaseModel): category: str; approver_office_n: int; escalate_to_office_n: Optional[int] = None; min_amount: float = 0; max_amount: Optional[float] = None; school_id: str = ""; department_id: str = ""; priority: str = ""; policy_priority: int = 0
class RoutingRuleIn(BaseModel): category: str; responsible_office_n: int; sla_hours: int = Field(default=72, ge=1, le=8760); school_id: str = ""
class ExecutionIn(ActionIn): status: str; external_reference: str = ""; completion_notes: str = ""
class SlaPolicyIn(BaseModel): category:str; duration_hours:int=Field(ge=1,le=8760); school_id:str=""; department_id:str=""; priority:str=""; responsible_office_n:Optional[int]=None; approaching_percent:int=Field(default=80,ge=1,le=99); policy_priority:int=0; pause_allowed:bool=False
class EvidencePolicyIn(BaseModel): category:str; required_types:list; school_id:str=""; department_id:str=""; priority:str=""; responsible_office_n:Optional[int]=None; policy_priority:int=0
class AdministrationDelegationIn(BaseModel):
    to_user_id: str
    authority: str = "approve:administration"
    school_id: str = ""
    department_id: str = ""
    category: str = ""
    priority: str = ""
    start: datetime
    end: datetime
    reason: str = ""
class FinanceReservationIn(ActionIn): budget_line_id: str

def _approval_policy(s, row):
    now = datetime.utcnow()
    rows = (s.query(A.AdministrativeApprovalPolicy)
            .filter(A.AdministrativeApprovalPolicy.tenant_id == row.tenant_id, A.AdministrativeApprovalPolicy.category == row.category,
                    A.AdministrativeApprovalPolicy.active == True, A.AdministrativeApprovalPolicy.min_amount <= row.estimated_cost)
            .all())
    rows = [x for x in rows if (not x.school_id or x.school_id == row.school_id) and (not x.department_id or x.department_id == row.department_id) and (not x.priority or x.priority == row.priority) and (x.max_amount is None or row.estimated_cost <= x.max_amount) and (x.effective_from is None or x.effective_from <= now) and (x.effective_to is None or now <= x.effective_to)]
    if not rows: return None
    score=lambda x:(bool(x.school_id),bool(x.department_id),bool(x.priority),x.min_amount,x.policy_priority)
    rows=sorted(rows,key=score,reverse=True)
    if len(rows)>1 and score(rows[0])==score(rows[1]): raise HTTPException(409,{"code":"APPROVAL_POLICY_CONFLICT","policy_ids":[rows[0].id,rows[1].id]})
    return rows[0]

def _routing_rule(s, row):
    rows = s.query(A.AdministrativeRoutingRule).filter_by(tenant_id=row.tenant_id, category=row.category, active=True).all()
    rows = [x for x in rows if not x.school_id or x.school_id == row.school_id]
    return sorted(rows, key=lambda x: bool(x.school_id), reverse=True)[0] if rows else None

def _sla_policy(s, row, office_n):
    rows=s.query(A.AdministrativeSlaPolicy).filter_by(tenant_id=row.tenant_id,category=row.category,active=True).all()
    rows=[x for x in rows if (not x.school_id or x.school_id==row.school_id) and (not x.department_id or x.department_id==row.department_id) and (not x.priority or x.priority==row.priority) and (x.responsible_office_n is None or x.responsible_office_n==office_n)]
    if not rows:return None
    score=lambda x:(bool(x.school_id),bool(x.department_id),bool(x.priority),x.responsible_office_n is not None,x.policy_priority)
    rows=sorted(rows,key=score,reverse=True)
    if len(rows)>1 and score(rows[0])==score(rows[1]):raise HTTPException(409,{"code":"SLA_POLICY_CONFLICT","policy_ids":[rows[0].id,rows[1].id]})
    return rows[0]

@router.post("/administration/approval-policies")
def create_approval_policy(body: PolicyIn, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] not in {3, 4}: raise HTTPException(403, "Campus Head or Principal authority required")
    if body.category.upper() not in CATEGORIES: raise HTTPException(422, "Unsupported category")
    if body.max_amount is not None and body.max_amount < body.min_amount: raise HTTPException(422, "Maximum amount must not be below minimum")
    row=A.AdministrativeApprovalPolicy(id=uid(),tenant_id=_tenant(ctx),school_id=body.school_id,department_id=body.department_id,priority=body.priority.upper(),policy_priority=body.policy_priority,category=body.category.upper(),min_amount=body.min_amount,max_amount=body.max_amount,approver_office_n=body.approver_office_n,escalate_to_office_n=body.escalate_to_office_n)
    s.add(row); s.flush(); write_audit(s,ctx["sub"],_actor(s,ctx),ctx["office_n"],"administration.policy.create",f"administrative_approval_policy:{row.id}","","ACTIVE",row.category,commit=False);s.commit();return {"id":row.id}

@router.post("/administration/routing-rules")
def create_routing_rule(body: RoutingRuleIn, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] not in {3, 4, 7}: raise HTTPException(403, "Leadership authority required")
    if body.category.upper() not in CATEGORIES: raise HTTPException(422, "Unsupported category")
    existing=s.query(A.AdministrativeRoutingRule).filter_by(tenant_id=_tenant(ctx),school_id=body.school_id,category=body.category.upper()).first()
    if existing: existing.responsible_office_n,existing.sla_hours,existing.updated_at=body.responsible_office_n,body.sla_hours,datetime.utcnow(); row=existing
    else: row=A.AdministrativeRoutingRule(id=uid(),tenant_id=_tenant(ctx),school_id=body.school_id,category=body.category.upper(),responsible_office_n=body.responsible_office_n,sla_hours=body.sla_hours);s.add(row)
    s.commit();return {"id":row.id,"office_n":row.responsible_office_n,"sla_hours":row.sla_hours}

@router.post("/administration/sla-policies")
def create_sla_policy(body:SlaPolicyIn,ctx=Depends(auth),s=Depends(db)):
    if ctx["office_n"] not in {3,4}:raise HTTPException(403,"Campus Head or Principal authority required")
    if body.category.upper() not in CATEGORIES:raise HTTPException(422,"Unsupported category")
    row=A.AdministrativeSlaPolicy(id=uid(),tenant_id=_tenant(ctx),school_id=body.school_id,department_id=body.department_id,category=body.category.upper(),priority=body.priority.upper(),responsible_office_n=body.responsible_office_n,duration_hours=body.duration_hours,approaching_percent=body.approaching_percent,policy_priority=body.policy_priority,pause_allowed=body.pause_allowed)
    s.add(row);s.commit();return {"id":row.id}

@router.post("/administration/evidence-policies")
def create_evidence_policy(body:EvidencePolicyIn,ctx=Depends(auth),s=Depends(db)):
    if ctx["office_n"] not in {3,4}:raise HTTPException(403,"Campus Head or Principal authority required")
    if body.category.upper() not in CATEGORIES or not body.required_types:raise HTTPException(422,"Category and required evidence types are required")
    row=A.AdministrativeEvidencePolicy(id=uid(),tenant_id=_tenant(ctx),school_id=body.school_id,department_id=body.department_id,category=body.category.upper(),priority=body.priority.upper(),responsible_office_n=body.responsible_office_n,required_types=__import__("json").dumps(body.required_types),policy_priority=body.policy_priority)
    s.add(row);s.commit();return {"id":row.id}

@router.post("/administration/delegations")
def create_administration_delegation(body:AdministrationDelegationIn,ctx=Depends(auth),s=Depends(db)):
    if ctx["office_n"] not in {3,4,7}: raise HTTPException(403,"Leadership authority required")
    if body.end <= body.start: raise HTTPException(422,"Delegation end must be after start")
    if body.to_user_id == ctx["sub"]: raise HTTPException(422,"Self-delegation is not allowed")
    target=s.get(User,body.to_user_id)
    if not target or target.tenant_id!=_tenant(ctx): raise HTTPException(404,"Delegate not found")
    scope={"school_id":body.school_id,"department_id":body.department_id,"category":body.category.upper(),"priority":body.priority.upper()}
    row=Delegation(id=uid(),tenant_id=_tenant(ctx),from_user=ctx["sub"],to_user=target.id,authority=body.authority,scope_ref=json.dumps(scope),start=body.start,end=body.end,status="active",reason=body.reason)
    s.add(row); write_audit(s,ctx["sub"],_actor(s,ctx),ctx["office_n"],"administration.delegation.create",f"delegation:{row.id}","","active",body.reason,commit=False); s.commit()
    return {"id":row.id,"from_user_id":row.from_user,"to_user_id":row.to_user,"authority":row.authority,"scope":scope,"start":row.start.isoformat(),"end":row.end.isoformat(),"status":row.status}

def _active_approval_delegation(s,row,ctx,pending):
    if pending.approver_office_n==ctx["office_n"]: return None
    now=datetime.utcnow()
    candidates=(s.query(Delegation).join(User,User.id==Delegation.from_user)
        .filter(Delegation.tenant_id==row.tenant_id,Delegation.to_user==ctx["sub"],Delegation.status=="active",User.office_n==pending.approver_office_n).all())
    for delegation in candidates:
        if not delegation.start or not delegation.end or not (delegation.start<=now<=delegation.end): continue
        try: scope=json.loads(delegation.scope_ref or "{}")
        except (TypeError,ValueError): scope={}
        if scope.get("school_id") and scope["school_id"]!=row.school_id: continue
        if scope.get("department_id") and scope["department_id"]!=row.department_id: continue
        if scope.get("category") and scope["category"]!=row.category: continue
        if scope.get("priority") and scope["priority"]!=row.priority: continue
        if delegation.authority not in {"*","approve:administration","approve"}: continue
        return delegation
    return None

def _require_finance_owner(s, row, ctx):
    require_specialist_stage(s, ctx, row)
    if ctx["office_n"] != 22 or row.category != "BUDGET": raise HTTPException(403,"Finance specialist authority required")

def _finance_payload(s, row):
    reservation=s.query(A.AdministrativeFinanceReservation).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).first()
    commitment=s.query(A.AdministrativeFinanceCommitment).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).first()
    budget=s.get(D.BudgetLine,reservation.budget_line_id) if reservation else None
    return {"requested":row.estimated_cost,"approved":row.estimated_cost if row.state not in {"REJECTED","CANCELLED"} else 0,"reserved":budget.reserved if budget else 0,"committed":budget.committed if budget else 0,"spent":budget.spent if budget else 0,"available":(budget.allocated-budget.spent-budget.reserved-budget.committed) if budget else None,"reservation":{"id":reservation.id,"status":reservation.status,"amount":reservation.amount} if reservation else None,"commitment":{"id":commitment.id,"status":commitment.status,"amount":commitment.amount} if commitment else None}

@router.get("/administrative-plans")
def list_plans(search:str="",state:str="",school_id:str="",department_id:str="",page:int=1,page_size:int=50,ctx=Depends(auth), s=Depends(db)):
    page=max(1,page); page_size=min(200,max(1,page_size))
    rows=s.query(A.AdministrativePlan).filter(A.AdministrativePlan.tenant_id==_tenant(ctx)).order_by(A.AdministrativePlan.updated_at.desc()).all()
    rows=[x for x in rows if (not search or search.lower() in x.title.lower()) and (not state or x.state==state.upper()) and (not school_id or x.school_id==school_id) and (not department_id or x.department_id==department_id)]
    if not _is_leader(ctx): rows=[x for x in rows if x.created_by==ctx["sub"]]
    total=len(rows); start=(page-1)*page_size
    return {"plans":[{"id":x.id,"title":x.title,"state":x.state,"version":x.version,"period_start":x.period_start,"period_end":x.period_end,"school_id":x.school_id,"department_id":x.department_id,"updated_at":x.updated_at.isoformat()} for x in rows[start:start+page_size]],"page":page,"page_size":page_size,"total":total}

@router.post("/administrative-plans")
def create_plan(body:PlanIn, ctx=Depends(auth), s=Depends(db)):
    _require_dean(s,ctx); school_id,department_id=require_scope_values(s,ctx,body.school_id,body.department_id); row=A.AdministrativePlan(id=uid(),tenant_id=_tenant(ctx),title=body.title.strip(),period_start=body.period_start,period_end=body.period_end,objectives=body.objectives,school_id=school_id,department_id=department_id,created_by=ctx["sub"],updated_by=ctx["sub"])
    if not row.title: raise HTTPException(422,"Plan title is required")
    s.add(row); s.flush(); write_audit(s,ctx["sub"],_actor(s,ctx),DEAN,"administration.plan.create",f"administrative_plan:{row.id}","","DRAFT",row.title,commit=False); s.commit(); return {"id":row.id,"state":row.state,"version":row.version}

@router.patch("/administrative-plans/{plan_id}")
def update_plan(plan_id:str, body:PlanIn, ctx=Depends(auth), s=Depends(db)):
    row=s.get(A.AdministrativePlan,plan_id)
    if not row or row.tenant_id!=_tenant(ctx): raise HTTPException(404,"Plan not found")
    _require_dean(s,ctx); require_plan_scope(s,ctx,row)
    if row.state not in {"DRAFT","RETURNED"}: raise HTTPException(409,"Only draft or returned plans can be edited")
    _require_version(row,body.expected_version)
    school_id,department_id=require_scope_values(s,ctx,body.school_id,body.department_id)
    row.title,row.period_start,row.period_end,row.objectives,row.school_id,row.department_id,row.version,row.updated_at,row.updated_by=body.title,body.period_start,body.period_end,body.objectives,school_id,department_id,row.version+1,datetime.utcnow(),ctx["sub"]
    s.commit(); return {"id":row.id,"version":row.version}

@router.post("/administrative-plans/{plan_id}/activities")
def add_activity(plan_id:str,body:ActivityIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativePlan,plan_id)
    if not row or row.tenant_id!=_tenant(ctx): raise HTTPException(404,"Plan not found")
    _require_dean(s,ctx); require_plan_scope(s,ctx,row)
    if row.state not in {"DRAFT","RETURNED"}: raise HTTPException(409,"Plan is not editable")
    x=A.AdministrativePlanActivity(id=uid(),tenant_id=row.tenant_id,plan_id=row.id,title=body.title,milestone=body.milestone,responsible_office_n=body.responsible_office_n,due_at=body.due_at);s.add(x);s.commit();return {"id":x.id}

@router.post("/administrative-plans/{plan_id}/submit")
def submit_plan(plan_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativePlan,plan_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Plan not found")
    _require_dean(s,ctx); require_plan_scope(s,ctx,row);_require_version(row,body.expected_version)
    if row.state not in {"DRAFT","RETURNED"}:raise HTTPException(409,"Plan cannot be submitted")
    old=row.state;row.state="SUBMITTED";row.version+=1;row.updated_by=ctx["sub"];row.updated_at=datetime.utcnow();s.add(A.AdministrativePlanTransition(id=uid(),tenant_id=row.tenant_id,plan_id=row.id,from_state=old,to_state=row.state,actor_id=ctx["sub"],reason=body.reason));write_audit(s,ctx["sub"],_actor(s,ctx),DEAN,"administration.plan.submit",f"administrative_plan:{row.id}",old,row.state,body.reason,commit=False);emit_outbox(s,row.tenant_id,"PlanSubmitted",row.id,{"recipient":"user_7","title":f"Plan submitted: {row.title}","body":body.reason,"severity":"action"},f"plan-submitted:{row.id}:{row.version}");s.commit();return {"state":row.state,"version":row.version}

@router.get("/administrative-plans/{plan_id}")
def get_plan(plan_id:str,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativePlan,plan_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Plan not found")
    require_plan_scope(s,ctx,row)
    if not _is_leader(ctx) and row.created_by!=ctx["sub"]:raise HTTPException(403,"Plan is outside your scope")
    activities=s.query(A.AdministrativePlanActivity).filter_by(plan_id=row.id,tenant_id=row.tenant_id).all()
    requirements=s.query(A.AdministrativeRequirement).filter_by(plan_id=row.id,tenant_id=row.tenant_id).all()
    return {"id":row.id,"title":row.title,"state":row.state,"version":row.version,"objectives":row.objectives,"activities":[{"id":x.id,"title":x.title,"milestone":x.milestone,"status":x.status} for x in activities],"requirements":[_payload(s,x) for x in requirements]}

@router.post("/administrative-plans/{plan_id}/withdraw")
def withdraw_plan(plan_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativePlan,plan_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Plan not found")
    _require_dean(s,ctx); require_plan_scope(s,ctx,row);_require_version(row,body.expected_version)
    if row.state!="SUBMITTED":raise HTTPException(409,"Only submitted plans can be withdrawn")
    old=row.state;row.state="DRAFT";row.version+=1;row.updated_by=ctx["sub"];row.updated_at=datetime.utcnow();s.add(A.AdministrativePlanTransition(id=uid(),tenant_id=row.tenant_id,plan_id=row.id,from_state=old,to_state=row.state,actor_id=ctx["sub"],reason=body.reason));write_audit(s,ctx["sub"],_actor(s,ctx),DEAN,"administration.plan.withdraw",f"administrative_plan:{row.id}",old,row.state,body.reason,commit=False);emit_outbox(s,row.tenant_id,"PlanWithdrawn",row.id,{"recipient":"user_7","title":f"Plan withdrawn: {row.title}","body":body.reason,"severity":"info"},f"plan-withdrawn:{row.id}:{row.version}");s.commit();return {"state":row.state,"version":row.version}

@router.get("/administrative-plans/{plan_id}/history")
def plan_history(plan_id:str,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativePlan,plan_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Plan not found")
    require_plan_scope(s,ctx,row)
    if not _is_leader(ctx) and row.created_by!=ctx["sub"]:raise HTTPException(403,"Plan is outside your scope")
    return {"history":[{"from_state":x.from_state,"to_state":x.to_state,"actor_id":x.actor_id,"reason":x.reason,"at":x.created_at.isoformat()} for x in s.query(A.AdministrativePlanTransition).filter_by(plan_id=row.id,tenant_id=row.tenant_id).order_by(A.AdministrativePlanTransition.created_at).all()]}

@router.get("/administrative-requirements")
def list_requirements(mine:bool=False,reviews:bool=False,state:str="",categories:str="",ctx=Depends(auth),s=Depends(db)):
    q=s.query(A.AdministrativeRequirement).filter(A.AdministrativeRequirement.tenant_id==_tenant(ctx))
    if state:q=q.filter(A.AdministrativeRequirement.state==state)
    if categories:
        requested={x.strip().upper() for x in categories.split(",") if x.strip()}
        if not requested or not requested.issubset(CATEGORIES):raise HTTPException(422,"Unsupported requirement category filter")
        q=q.filter(A.AdministrativeRequirement.category.in_(requested))
    rows=q.order_by(A.AdministrativeRequirement.updated_at.desc()).all()
    if mine: rows=[x for x in rows if x.created_by==ctx["sub"]]
    elif reviews: rows=[x for x in rows if _visible_with_session(s,x,ctx) and (x.assigned_user_id==ctx["sub"] or x.responsible_office_n==ctx["office_n"] or (_is_leader(ctx) and x.state in {"SUBMITTED","VALIDATING","PENDING_APPROVAL","READY_FOR_REVIEW"}))]
    else: rows=[x for x in rows if _visible_with_session(s,x,ctx)]
    return {"requirements":[_payload(s,x) for x in rows],"categories":sorted(CATEGORIES)}

@router.post("/administrative-requirements")
def create_requirement(body:RequirementIn,ctx=Depends(auth),s=Depends(db)):
    category=body.category.upper()
    if category not in CATEGORIES:raise HTTPException(422,"Unsupported requirement category")
    if ctx["office_n"] not in {3,4,6,7,10,26}:raise HTTPException(403,"Your office cannot create administrative requirements")
    school_id,department_id=require_scope_values(s,ctx,body.school_id,body.department_id)
    if body.plan_id:
        plan=s.get(A.AdministrativePlan,body.plan_id)
        if not plan or plan.tenant_id!=_tenant(ctx):raise HTTPException(404,"Plan not found")
        require_plan_scope(s,ctx,plan)
        if (school_id,department_id)!=(plan.school_id or "",plan.department_id or ""): raise HTTPException(422,"Requirement scope must match its administrative plan")
    duplicate=s.query(A.AdministrativeRequirement).filter_by(tenant_id=_tenant(ctx),department_id=department_id,title=body.title.strip(),category=category).filter(A.AdministrativeRequirement.state.notin_(("REJECTED","CANCELLED","CLOSED"))).first()
    if duplicate:raise HTTPException(409,f"Possible duplicate requirement: {duplicate.reference_code}")
    sequence=s.query(A.AdministrativeRequirement).filter(A.AdministrativeRequirement.tenant_id==_tenant(ctx)).count()+1
    row=A.AdministrativeRequirement(id=uid(),tenant_id=_tenant(ctx),reference_code=f"ADM-{datetime.utcnow().year}-{sequence:04d}",plan_id=body.plan_id,school_id=school_id,department_id=department_id,source_office_n=ctx["office_n"],requester_id=ctx["sub"],category=category,subcategory=body.subcategory,title=body.title.strip(),description=body.description,justification=body.justification,quantity=body.quantity,estimated_cost=body.estimated_cost,budget_impact=body.estimated_cost,priority=body.priority.upper(),urgency=body.urgency.upper(),due_at=body.due_at,created_by=ctx["sub"],updated_by=ctx["sub"])
    s.add(row);s.flush();write_audit(s,ctx["sub"],_actor(s,ctx),ctx["office_n"],"administration.requirement.create",f"administrative_requirement:{row.id}","","DRAFT",row.reference_code,commit=False);s.commit();return _payload(s,row)

@router.get("/administrative-requirements/{requirement_id}")
def get_requirement(requirement_id:str,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    _require_visible(s,row,ctx);return _payload(s,row)

@router.post("/administrative-requirements/{requirement_id}/submit")
def submit_requirement(requirement_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    if row.created_by!=ctx["sub"] or row.state not in {"DRAFT","RETURNED"}:raise HTTPException(403,"Only the requester can submit this draft")
    _require_version(row,body.expected_version);_transition(s,row,ctx,"SUBMITTED",body.reason);emit_outbox(s,row.tenant_id,"RequirementSubmitted",row.id,{"recipient":"user_7","title":f"Validation required: {row.reference_code}","body":row.title,"severity":"action"},f"submitted:{row.id}");s.commit();return _payload(s,row)

def _dean_action(requirement_id,body,ctx,s,target,allowed,reason_required=False):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    _require_dean(s,ctx,row);_require_version(row,body.expected_version)
    if row.state not in allowed:raise HTTPException(409,f"Cannot move {row.state} to {target}")
    if reason_required and not body.reason.strip():raise HTTPException(422,"Reason is required")
    _transition(s,row,ctx,target,body.reason);s.commit();return _payload(s,row)

@router.post("/administrative-requirements/{requirement_id}/validate")
def validate(requirement_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)): return _dean_action(requirement_id,body,ctx,s,"VALIDATED",{"SUBMITTED","VALIDATING"})
@router.post("/administrative-requirements/{requirement_id}/return")
def return_requirement(requirement_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)): return _dean_action(requirement_id,body,ctx,s,"RETURNED",{"SUBMITTED","VALIDATING","VALIDATED"},True)
@router.post("/administrative-requirements/{requirement_id}/reject")
def reject_requirement(requirement_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)): return _dean_action(requirement_id,body,ctx,s,"REJECTED",{"SUBMITTED","VALIDATING","VALIDATED","CATEGORIZED"},True)

@router.post("/administrative-requirements/{requirement_id}/categorize")
def categorize(requirement_id:str,body:CategorizeIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    _require_dean(s,ctx,row);_require_version(row,body.expected_version)
    if row.state!="VALIDATED":raise HTTPException(409,"Only validated requirements can be categorized")
    if body.category.upper() not in CATEGORIES:raise HTTPException(422,"Unsupported category")
    row.category,row.subcategory,row.priority,row.due_at=body.category.upper(),body.subcategory,body.priority.upper(),body.due_at
    _transition(s,row,ctx,"CATEGORIZED",body.reason);s.commit();return _payload(s,row)

@router.post("/administrative-requirements/{requirement_id}/resource-review")
def resource_review(requirement_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)):
    return _dean_action(requirement_id,body,ctx,s,"RESOURCE_REVIEW",{"CATEGORIZED"})

@router.post("/administrative-requirements/{requirement_id}/budget-review")
def budget_review(requirement_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    _require_dean(s,ctx,row);_require_version(row,body.expected_version)
    if row.state not in {"CATEGORIZED","RESOURCE_REVIEW"}:raise HTTPException(409,"Requirement is not ready for budget review")
    policy=_approval_policy(s,row)
    if not policy: raise HTTPException(409,{"code":"APPROVAL_POLICY_MISSING","category":row.category,"school_id":row.school_id})
    _transition(s,row,ctx,"PENDING_APPROVAL",body.reason)
    s.add(A.AdministrativeApproval(id=uid(),tenant_id=row.tenant_id,requirement_id=row.id,policy_id=policy.id,approver_office_n=policy.approver_office_n,decision="PENDING",actor_id=ctx["sub"],reason="Awaiting policy approval"))
    emit_outbox(s,row.tenant_id,"ApprovalRequired",row.id,{"recipient":f"user_{policy.approver_office_n}","title":f"Approval required: {row.reference_code}","body":row.title,"severity":"action"},f"approval-required:{row.id}");s.commit();return _payload(s,row)

def _route_with_rule(s,row,ctx,reason=""):
    rule=_routing_rule(s,row)
    if not rule:raise HTTPException(409,{"code":"ROUTING_RULE_MISSING","category":row.category,"school_id":row.school_id})
    sla_policy=_sla_policy(s,row,rule.responsible_office_n)
    if not sla_policy:raise HTTPException(409,{"code":"SLA_POLICY_MISSING","category":row.category,"school_id":row.school_id,"responsible_office_n":rule.responsible_office_n})
    due=datetime.utcnow()+timedelta(hours=sla_policy.duration_hours)
    row.responsible_office_n,row.assigned_user_id,row.due_at=rule.responsible_office_n,None,due
    s.add(A.AdministrativeAssignment(id=uid(),tenant_id=row.tenant_id,requirement_id=row.id,office_n=rule.responsible_office_n,user_id=None,due_at=row.due_at,assigned_by=ctx["sub"]))
    s.add(A.AdministrativeSla(id=uid(),tenant_id=row.tenant_id,requirement_id=row.id,routing_rule_id=rule.id,policy_id=sla_policy.id,duration_hours=sla_policy.duration_hours,due_at=row.due_at,original_due_at=row.due_at,approaching_percent=sla_policy.approaching_percent,pause_allowed=sla_policy.pause_allowed))
    _transition(s,row,ctx,"ROUTED",reason);emit_outbox(s,row.tenant_id,"RequirementRouted",row.id,{"recipient":f"user_{rule.responsible_office_n}","title":f"Assignment: {row.reference_code}","body":row.title,"severity":"action"},f"routed:{row.id}:{row.version}")

@router.post("/administrative-requirements/{requirement_id}/approve")
def approve(requirement_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    _require_version(row,body.expected_version)
    pending=s.query(A.AdministrativeApproval).filter_by(requirement_id=row.id,tenant_id=row.tenant_id,decision="PENDING").order_by(A.AdministrativeApproval.created_at.desc()).first()
    delegation=_active_approval_delegation(s,row,ctx,pending) if pending else None
    # Always perform object-level scope validation; a matching office number is
    # not by itself authority to approve another school's requirement.
    _require_visible(s,row,ctx)
    if row.state not in {"PENDING_APPROVAL","ESCALATED"} or not pending or (pending.approver_office_n!=ctx["office_n"] and not delegation) or row.requester_id==ctx["sub"]:raise HTTPException(403,"Only the current policy approver or active scoped delegate may approve")
    pending.decision="APPROVED";pending.actor_id=ctx["sub"];pending.delegated_from_user_id=delegation.from_user if delegation else None;pending.delegation_id=delegation.id if delegation else None;pending.reason=body.reason
    policy=s.get(A.AdministrativeApprovalPolicy,pending.policy_id)
    if row.state == "PENDING_APPROVAL" and policy and policy.escalate_to_office_n:
        _transition(s,row,ctx,"ESCALATED",body.reason)
        s.add(A.AdministrativeApproval(id=uid(),tenant_id=row.tenant_id,requirement_id=row.id,policy_id=policy.id,approver_office_n=policy.escalate_to_office_n,decision="PENDING",actor_id=ctx["sub"],reason="Escalated by policy"));emit_outbox(s,row.tenant_id,"RequirementEscalated",row.id,{"recipient":f"user_{policy.escalate_to_office_n}","title":f"Escalated approval: {row.reference_code}","body":row.title,"severity":"critical"},f"escalated:{row.id}")
    else:
        _transition(s,row,ctx,"APPROVED",body.reason);emit_outbox(s,row.tenant_id,"ApprovalApproved",row.id,{"recipient":row.requester_id,"title":f"Requirement approved: {row.reference_code}","body":row.title,"severity":"info"},f"approval-approved:{row.id}:{pending.id}");_route_with_rule(s,row,ctx,"Approved and routed")
    s.commit();return _payload(s,row)

@router.post("/administrative-requirements/{requirement_id}/approve-reject")
def reject_approval(requirement_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx): raise HTTPException(404,"Requirement not found")
    _require_version(row,body.expected_version)
    pending=s.query(A.AdministrativeApproval).filter_by(requirement_id=row.id,tenant_id=row.tenant_id,decision="PENDING").order_by(A.AdministrativeApproval.created_at.desc()).first()
    delegation=_active_approval_delegation(s,row,ctx,pending) if pending else None
    _require_visible(s,row,ctx)
    if not body.reason.strip(): raise HTTPException(422,"Rejection reason is required")
    if row.state not in {"PENDING_APPROVAL","ESCALATED"} or not pending or (pending.approver_office_n!=ctx["office_n"] and not delegation) or row.requester_id==ctx["sub"]: raise HTTPException(403,"Only the current policy approver or active scoped delegate may reject")
    pending.decision="REJECTED"; pending.actor_id=ctx["sub"]; pending.delegated_from_user_id=delegation.from_user if delegation else None; pending.delegation_id=delegation.id if delegation else None; pending.reason=body.reason
    _transition(s,row,ctx,"REJECTED",body.reason); emit_outbox(s,row.tenant_id,"ApprovalRejected",row.id,{"recipient":row.requester_id,"title":f"Requirement rejected: {row.reference_code}","body":body.reason,"severity":"critical"},f"approval-rejected:{row.id}:{pending.id}"); s.commit(); return _payload(s,row)

@router.post("/administrative-requirements/{requirement_id}/reject-assignment")
def reject_assignment(requirement_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    _require_version(row,body.expected_version)
    require_specialist_stage(s,ctx,row)
    if not body.reason.strip() or row.state not in {"ROUTED","IN_EXECUTION"}:raise HTTPException(403,"Only the current office may return an assignment with a reason")
    assignment=s.query(A.AdministrativeAssignment).filter_by(requirement_id=row.id,tenant_id=row.tenant_id,status="ASSIGNED").order_by(A.AdministrativeAssignment.created_at.desc()).first()
    if assignment:assignment.status="RETURNED"
    row.responsible_office_n,row.assigned_user_id=None,None;_transition(s,row,ctx,"RETURNED",body.reason);emit_outbox(s,row.tenant_id,"AssignmentReturned",row.id,{"recipient":"user_7","title":f"Assignment returned: {row.reference_code}","body":body.reason,"severity":"action"},f"assignment-returned:{row.id}:{row.version}");s.commit();return _payload(s,row)

@router.post("/administrative-requirements/{requirement_id}/assign")
@router.post("/administrative-requirements/{requirement_id}/reassign")
def assign(requirement_id:str,body:AssignIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    _require_dean(s,ctx,row);_require_version(row,body.expected_version)
    # Initial routing is only performed by policy approval (_route_with_rule),
    # which creates an SLA snapshot.  This endpoint is deliberately limited to
    # reassigning an already-routed item so it cannot bypass approval controls.
    if row.state!="ROUTED":raise HTTPException(409,"Only an already routed requirement may be reassigned")
    if body.office_n not in {22,23,24,26,27,29,32,33}:raise HTTPException(422,"Office cannot own specialist execution")
    if body.user_id:
        user=s.get(User,body.user_id)
        if not user or user.tenant_id!=row.tenant_id or user.office_n!=body.office_n:raise HTTPException(422,"Assignee must belong to the responsible office")
    previous_office, previous_user = row.responsible_office_n, row.assigned_user_id
    if body.due_at is None: body.due_at=row.due_at
    row.responsible_office_n,row.assigned_user_id,row.due_at=body.office_n,body.user_id,body.due_at
    s.add(A.AdministrativeAssignment(id=uid(),tenant_id=row.tenant_id,requirement_id=row.id,office_n=body.office_n,user_id=body.user_id,due_at=body.due_at,assigned_by=ctx["sub"],previous_office_n=previous_office,previous_user_id=previous_user,reason=body.reason))
    # Reassignment remains in ROUTED, so write an explicit history event
    # without attempting an invalid ROUTED -> ROUTED state transition.
    row.version,row.updated_at,row.updated_by=row.version+1,datetime.utcnow(),ctx["sub"]
    s.add(A.AdministrativeTransition(id=uid(),tenant_id=row.tenant_id,requirement_id=row.id,from_state="ROUTED",to_state="ROUTED",actor_id=ctx["sub"],actor_office_n=ctx["office_n"],reason=body.reason or "Assignment reassigned",version=row.version))
    emit_outbox(s,row.tenant_id,"AssignmentCreated",row.id,{"recipient":body.user_id or f"user_{body.office_n}","title":f"Assignment: {row.reference_code}","body":row.title,"severity":"action"},f"assignment:{row.id}:{row.version}");s.commit();return _payload(s,row)

@router.post("/administrative-requirements/{requirement_id}/accept")
def accept(requirement_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    require_specialist_stage(s,ctx,row);_require_version(row,body.expected_version)
    if row.state!="ROUTED":raise HTTPException(403,"Only the current assigned office/user may accept")
    assignment=s.query(A.AdministrativeAssignment).filter_by(requirement_id=row.id,tenant_id=row.tenant_id,status="ASSIGNED").order_by(A.AdministrativeAssignment.created_at.desc()).first()
    if assignment:assignment.status="ACCEPTED";assignment.accepted_at=datetime.utcnow()
    s.add(A.AdministrativeExecution(id=uid(),tenant_id=row.tenant_id,requirement_id=row.id,owning_office_n=ctx["office_n"],updated_by=ctx["sub"]))
    _transition(s,row,ctx,"IN_EXECUTION",body.reason);emit_outbox(s,row.tenant_id,"AssignmentAccepted",row.id,{"recipient":"user_7","title":f"Assignment accepted: {row.reference_code}","body":row.title,"severity":"info"},f"assignment-accepted:{row.id}");s.commit();return _payload(s,row)

@router.post("/administrative-requirements/{requirement_id}/execution")
def update_execution(requirement_id:str,body:ExecutionIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    require_specialist_stage(s,ctx,row);_require_version(row,body.expected_version)
    execution=s.query(A.AdministrativeExecution).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).first()
    if not execution or execution.owning_office_n!=ctx["office_n"]:raise HTTPException(403,"Only the specialist owner may update execution")
    if body.status not in {"IN_PROGRESS","COMPLETED","ON_HOLD"}:raise HTTPException(422,"Invalid execution status")
    target={"IN_PROGRESS":"IN_PROGRESS","ON_HOLD":"ON_HOLD","COMPLETED":"PENDING_EVIDENCE"}[body.status]
    require_transition(row.state,target)
    execution.status,execution.external_reference,execution.completion_notes,execution.updated_by,execution.updated_at=body.status,body.external_reference,body.completion_notes,ctx["sub"],datetime.utcnow()
    if body.status=="ON_HOLD": pause_sla(s,row.id,row.tenant_id)
    elif body.status=="IN_PROGRESS": resume_sla(s,row.id,row.tenant_id)
    elif body.status=="COMPLETED": complete_sla(s,row.id,row.tenant_id)
    _transition(s,row,ctx,target,body.completion_notes);s.commit();return _payload(s,row)

@router.get("/administrative-requirements/{requirement_id}/finance")
def finance_detail(requirement_id:str,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx): raise HTTPException(404,"Requirement not found")
    _require_visible(s,row,ctx)
    return _finance_payload(s,row)

@router.post("/administrative-requirements/{requirement_id}/finance/reserve")
def reserve_finance(requirement_id:str,body:FinanceReservationIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx): raise HTTPException(404,"Requirement not found")
    _require_finance_owner(s,row,ctx); _require_version(row,body.expected_version)
    if row.state not in {"IN_EXECUTION","IN_PROGRESS"}: raise HTTPException(409,"Requirement is not in Finance execution")
    existing=s.query(A.AdministrativeFinanceReservation).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).first()
    if existing: return _finance_payload(s,row)
    budget=s.get(D.BudgetLine,body.budget_line_id)
    if not budget or budget.tenant_id!=row.tenant_id: raise HTTPException(404,"Budget line not found")
    amount=float(row.estimated_cost or 0)
    if amount<=0: raise HTTPException(422,"Finance reservation requires a positive approved amount")
    available=(budget.allocated or 0)-(budget.spent or 0)-(budget.reserved or 0)-(budget.committed or 0)
    if available<amount: raise HTTPException(409,{"code":"INSUFFICIENT_BUDGET","available":available,"requested":amount})
    budget.reserved=(budget.reserved or 0)+amount
    reservation=A.AdministrativeFinanceReservation(id=uid(),tenant_id=row.tenant_id,requirement_id=row.id,budget_line_id=budget.id,amount=amount,reserved_by=ctx["sub"])
    s.add(reservation); write_audit(s,ctx["sub"],_actor(s,ctx),ctx["office_n"],"administration.finance.reserve",f"administrative_requirement:{row.id}","","RESERVED",str(amount),commit=False)
    emit_outbox(s,row.tenant_id,"FinanceReserved",row.id,{"recipient":"user_7","title":f"Finance reserved: {row.reference_code}","body":str(amount),"severity":"info"},f"finance-reserved:{reservation.id}"); s.commit(); return _finance_payload(s,row)

@router.post("/administrative-requirements/{requirement_id}/finance/commit")
def commit_finance(requirement_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx): raise HTTPException(404,"Requirement not found")
    _require_finance_owner(s,row,ctx); _require_version(row,body.expected_version)
    reservation=s.query(A.AdministrativeFinanceReservation).filter_by(requirement_id=row.id,tenant_id=row.tenant_id,status="RESERVED").first()
    if not reservation: raise HTTPException(409,"An active Finance reservation is required")
    budget=s.get(D.BudgetLine,reservation.budget_line_id)
    reservation.status="COMMITTED"; budget.reserved=max(0,(budget.reserved or 0)-reservation.amount); budget.committed=(budget.committed or 0)+reservation.amount
    commitment=A.AdministrativeFinanceCommitment(id=uid(),tenant_id=row.tenant_id,requirement_id=row.id,reservation_id=reservation.id,amount=reservation.amount,committed_by=ctx["sub"])
    s.add(commitment); write_audit(s,ctx["sub"],_actor(s,ctx),ctx["office_n"],"administration.finance.commit",f"administrative_requirement:{row.id}","RESERVED","COMMITTED",body.reason,commit=False)
    emit_outbox(s,row.tenant_id,"FinanceCommitted",row.id,{"recipient":"user_7","title":f"Finance committed: {row.reference_code}","body":str(commitment.amount),"severity":"info"},f"finance-committed:{commitment.id}"); s.commit(); return _finance_payload(s,row)

@router.post("/administrative-requirements/{requirement_id}/comments")
def comment(requirement_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    _require_visible(s,row,ctx)
    if not body.reason.strip():raise HTTPException(422,"Comment is required")
    s.add(A.AdministrativeComment(id=uid(),tenant_id=row.tenant_id,requirement_id=row.id,body=body.reason,created_by=ctx["sub"]));s.commit();return {"ok":True}

@router.post("/administrative-requirements/{requirement_id}/evidence")
def evidence(requirement_id:str,body:EvidenceIn,ctx=Depends(auth),s=Depends(db)):
    # Metadata-only evidence cannot be verified or used for closure.  Keep the
    # route to return a deterministic migration error for old clients.
    raise HTTPException(410,"Use the multipart evidence/upload endpoint; metadata-only evidence is not accepted")

@router.post("/administrative-requirements/{requirement_id}/evidence/upload")
def upload_evidence(requirement_id:str, expected_version:int, evidence_type:str, file:UploadFile=File(...), description:str="", ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    _require_visible(s,row,ctx);_require_version(row,expected_version)
    if not _is_dean(ctx):require_specialist_stage(s,ctx,row)
    if evidence_type.upper() not in EVIDENCE_TYPES:raise HTTPException(422,"Unsupported evidence type")
    if (file.content_type or "").lower() not in ALLOWED_EVIDENCE_CONTENT_TYPES:raise HTTPException(422,"Unsupported evidence content type")
    content=file.file.read()
    if not content or len(content)>10*1024*1024:raise HTTPException(422,"Evidence must be between 1 byte and 10MB")
    storage=EvidenceStorageAdapter(); key,checksum=storage.put(content,file.filename or "evidence",row.tenant_id)
    item=A.AdministrativeEvidence(id=uid(),tenant_id=row.tenant_id,requirement_id=row.id,evidence_type=evidence_type.upper(),description=description,file_name=storage.normalize_filename(file.filename or "evidence"),content_type=file.content_type.lower(),size_bytes=len(content),storage_key=key,checksum=checksum,uploaded_by=ctx["sub"],verification_status="UNDER_REVIEW")
    s.add(item);emit_outbox(s,row.tenant_id,"EvidenceUploaded",row.id,{"recipient":"user_7","title":f"Evidence uploaded: {row.reference_code}","body":row.title,"severity":"info"},f"evidence:{item.id}");_transition(s,row,ctx,"PENDING_EVIDENCE","Evidence uploaded");s.commit();return {"id":item.id,"checksum":checksum,"size_bytes":item.size_bytes}

@router.get("/administrative-requirements/{requirement_id}/evidence")
def list_evidence(requirement_id:str,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    _require_visible(s,row,ctx)
    rows=s.query(A.AdministrativeEvidence).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).filter(A.AdministrativeEvidence.deleted_at.is_(None)).all()
    return {"evidence":[{"id":x.id,"type":x.evidence_type,"file_name":x.file_name,"content_type":x.content_type,"size_bytes":x.size_bytes,"checksum":x.checksum,"uploaded_at":x.uploaded_at.isoformat(),"description":x.description,"verification_status":x.verification_status,"verified_by":x.verified_by,"verified_at":x.verified_at.isoformat() if x.verified_at else None,"rejection_reason":x.rejection_reason} for x in rows]}

@router.post("/administrative-evidence/{evidence_id}/verify")
def verify_evidence(evidence_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)):
    item=s.get(A.AdministrativeEvidence,evidence_id)
    if not item or item.tenant_id!=_tenant(ctx) or item.deleted_at is not None: raise HTTPException(404,"Evidence not found")
    row=s.get(A.AdministrativeRequirement,item.requirement_id)
    if not row: raise HTTPException(404,"Requirement not found")
    _require_dean(s,ctx,row); _require_version(row,body.expected_version)
    if item.verification_status not in {"UPLOADED","UNDER_REVIEW"}: raise HTTPException(409,"Evidence is not awaiting verification")
    item.verification_status="VERIFIED"; item.verified_by=ctx["sub"]; item.verified_at=datetime.utcnow(); row.version+=1; row.updated_at=datetime.utcnow(); row.updated_by=ctx["sub"]
    write_audit(s, ctx["sub"], _actor(s, ctx), ctx["office_n"], "administration.evidence.verify", f"administrative_evidence:{item.id}", "UNDER_REVIEW", "VERIFIED", body.reason, commit=False)
    emit_outbox(s,row.tenant_id,"EvidenceVerified",row.id,{"recipient":row.requester_id,"title":f"Evidence verified: {row.reference_code}","body":row.title,"severity":"info"},f"evidence-verified:{item.id}")
    s.commit(); return {"id":item.id,"verification_status":item.verification_status,"version":row.version}

@router.post("/administrative-evidence/{evidence_id}/reject")
def reject_evidence(evidence_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)):
    item=s.get(A.AdministrativeEvidence,evidence_id)
    if not item or item.tenant_id!=_tenant(ctx) or item.deleted_at is not None: raise HTTPException(404,"Evidence not found")
    row=s.get(A.AdministrativeRequirement,item.requirement_id)
    if not row: raise HTTPException(404,"Requirement not found")
    _require_dean(s,ctx,row); _require_version(row,body.expected_version)
    if not body.reason.strip(): raise HTTPException(422,"A rejection reason is required")
    if item.verification_status not in {"UPLOADED","UNDER_REVIEW"}: raise HTTPException(409,"Evidence is not awaiting verification")
    item.verification_status="REJECTED"; item.verified_by=ctx["sub"]; item.verified_at=datetime.utcnow(); item.rejection_reason=body.reason; row.version+=1; row.updated_at=datetime.utcnow(); row.updated_by=ctx["sub"]
    write_audit(s,ctx["sub"],_actor(s,ctx),ctx["office_n"],"administration.evidence.reject",f"administrative_evidence:{item.id}","UNDER_REVIEW","REJECTED",body.reason,commit=False)
    emit_outbox(s,row.tenant_id,"EvidenceRejected",row.id,{"recipient":row.requester_id,"title":f"Evidence rejected: {row.reference_code}","body":body.reason,"severity":"action"},f"evidence-rejected:{item.id}")
    s.commit(); return {"id":item.id,"verification_status":item.verification_status,"version":row.version}

@router.get("/administrative-requirements/{requirement_id}/evidence-policy")
def evidence_policy(requirement_id:str,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    _require_visible(s,row,ctx); return resolve_evidence_policy(s,row)

@router.get("/administrative-evidence/{evidence_id}/download")
def download_evidence(evidence_id:str,ctx=Depends(auth),s=Depends(db)):
    item=s.get(A.AdministrativeEvidence,evidence_id)
    if not item or item.tenant_id!=_tenant(ctx) or item.deleted_at is not None:raise HTTPException(404,"Evidence not found")
    row=s.get(A.AdministrativeRequirement,item.requirement_id)
    if not row:raise HTTPException(404,"Requirement not found")
    _require_visible(s,row,ctx)
    if not item.storage_key:raise HTTPException(404,"Stored file is not available for this legacy evidence")
    try:content=EvidenceStorageAdapter().get(item.storage_key)
    except FileNotFoundError:raise HTTPException(404,"Evidence content is unavailable")
    return Response(content,media_type=item.content_type,headers={"Content-Disposition":f'attachment; filename="{item.file_name}"'})

@router.delete("/administrative-evidence/{evidence_id}")
def delete_evidence(evidence_id:str,ctx=Depends(auth),s=Depends(db)):
    item=s.get(A.AdministrativeEvidence,evidence_id)
    if not item or item.tenant_id!=_tenant(ctx) or item.deleted_at is not None:raise HTTPException(404,"Evidence not found")
    row=s.get(A.AdministrativeRequirement,item.requirement_id)
    if not row:raise HTTPException(404,"Requirement not found")
    _require_visible(s,row,ctx)
    if row.state in {"COMPLETED","CLOSED"} or s.query(A.AdministrativeClosure).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).first():raise HTTPException(409,"Evidence used for review or closure cannot be deleted")
    if not _is_dean(ctx) and item.uploaded_by!=ctx["sub"]:raise HTTPException(403,"Only the uploader or scoped Dean may delete evidence")
    item.deleted_at=datetime.utcnow(); item.deleted_by=ctx["sub"]
    # Remove content only after the final active reference is deleted.  This
    # handles duplicate uploads safely while preserving an audit-only row.
    if item.storage_key:
        active_refs=s.query(A.AdministrativeEvidence).filter(A.AdministrativeEvidence.storage_key==item.storage_key,A.AdministrativeEvidence.id!=item.id,A.AdministrativeEvidence.deleted_at.is_(None)).count()
        if not active_refs:
            try: EvidenceStorageAdapter().delete(item.storage_key)
            except FileNotFoundError: pass
    write_audit(s,ctx["sub"],_actor(s,ctx),ctx["office_n"],"administration.evidence.delete",f"administrative_evidence:{evidence_id}","ACTIVE","DELETED",row.reference_code,commit=False)
    emit_outbox(s,row.tenant_id,"EvidenceDeleted",row.id,{"recipient":"user_7","title":f"Evidence deleted: {row.reference_code}","body":row.title,"severity":"info"},f"evidence-deleted:{evidence_id}")
    s.commit();return {"ok":True}

@router.post("/administrative-requirements/{requirement_id}/ready-for-review")
def ready(requirement_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    require_specialist_stage(s,ctx,row);_require_version(row,body.expected_version)
    if row.state not in {"IN_EXECUTION","IN_PROGRESS","PENDING_EVIDENCE"}:raise HTTPException(403,"Only the executing office can request review")
    policy=resolve_evidence_policy(s,row)
    if not policy["satisfied"]:raise HTTPException(409,{"code":policy["reason"],**policy})
    sla=s.query(A.AdministrativeSla).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).first()
    if sla:complete_sla(s,row.id,row.tenant_id)
    _transition(s,row,ctx,"READY_FOR_REVIEW",body.reason);emit_outbox(s,row.tenant_id,"ClosureReviewRequired",row.id,{"recipient":"user_7","title":f"Closure review: {row.reference_code}","body":row.title,"severity":"action"},f"closure-review:{row.id}");s.commit();return _payload(s,row)

@router.post("/administrative-requirements/{requirement_id}/complete")
def complete(requirement_id:str,body:ActionIn,ctx=Depends(auth),s=Depends(db)): return _dean_action(requirement_id,body,ctx,s,"COMPLETED",{"READY_FOR_REVIEW"})

@router.post("/administrative-requirements/{requirement_id}/close")
def close(requirement_id:str,body:ClosureIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    _require_dean(s,ctx,row);_require_version(row,body.expected_version)
    if row.state!="COMPLETED":raise HTTPException(409,"Only completed requirements can close")
    if not (body.evidence_verified and body.execution_verified):raise HTTPException(422,"Evidence and execution verification are mandatory")
    if row.category=="BUDGET" and not s.query(A.AdministrativeFinanceCommitment).filter_by(requirement_id=row.id,tenant_id=row.tenant_id,status="COMMITTED").first():
        raise HTTPException(409,{"code":"FINANCE_COMMITMENT_REQUIRED","message":"A committed Finance record is required before closure"})
    policy=resolve_evidence_policy(s,row)
    if not policy["satisfied"]:raise HTTPException(409,{"code":policy["reason"],**policy})
    s.add(A.AdministrativeClosure(id=uid(),tenant_id=row.tenant_id,requirement_id=row.id,closure_reason=body.reason or "Administrative closure",evidence_verified=body.evidence_verified,budget_verified=body.budget_verified,execution_verified=body.execution_verified,closed_by=ctx["sub"]));_transition(s,row,ctx,"CLOSED",body.reason);emit_outbox(s,row.tenant_id,"RequirementClosed",row.id,{"recipient":row.requester_id,"title":f"Requirement closed: {row.reference_code}","body":row.title,"severity":"info"},f"closed:{row.id}");s.commit();return _payload(s,row)

@router.get("/administrative-requirements/{requirement_id}/timeline")
def timeline(requirement_id:str,ctx=Depends(auth),s=Depends(db)):
    row=s.get(A.AdministrativeRequirement,requirement_id)
    if not row or row.tenant_id!=_tenant(ctx):raise HTTPException(404,"Requirement not found")
    _require_visible(s,row,ctx)
    return {"transitions":[{"from":x.from_state,"to":x.to_state,"actor_id":x.actor_id,"office_n":x.actor_office_n,"reason":x.reason,"version":x.version,"at":x.created_at.isoformat()} for x in s.query(A.AdministrativeTransition).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).order_by(A.AdministrativeTransition.created_at).all()]}

def _dashboard_rows(s,ctx,school_id="",department_id="",category="",priority="",office_n=None,assignee_id="",date_from="",date_to=""):
    rows=s.query(A.AdministrativeRequirement).filter_by(tenant_id=_tenant(ctx)).all()
    rows=[r for r in rows if _visible_with_session(s,r,ctx)]
    start=datetime.fromisoformat(date_from) if date_from else None
    end=datetime.fromisoformat(date_to) if date_to else None
    return [r for r in rows if (not school_id or r.school_id==school_id) and (not department_id or r.department_id==department_id) and (not category or r.category==category.upper()) and (not priority or r.priority==priority.upper()) and (office_n is None or r.responsible_office_n==office_n) and (not assignee_id or r.assigned_user_id==assignee_id) and (not start or r.created_at>=start) and (not end or r.created_at<=end)]

def _administration_alerts(s,rows):
    alerts=[]
    for row in rows:
        sla=s.query(A.AdministrativeSla).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).first()
        execution=s.query(A.AdministrativeExecution).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).first()
        def add(kind,severity,title,due_at=None):
            alerts.append({"id":f"{kind}:{row.id}","type":kind,"severity":severity,"requirement_id":row.id,"reference_code":row.reference_code,"title":title,"school_id":row.school_id,"department_id":row.department_id,"office_n":row.responsible_office_n,"assignee_id":row.assigned_user_id,"created_at":row.updated_at.isoformat(),"due_at":due_at.isoformat() if due_at else None,"status":"OPEN","state":row.state,"category":row.category,"priority":row.priority})
        if row.state in {"PENDING_APPROVAL","ESCALATED"}:add("PENDING_APPROVAL","action",f"Approval required: {row.title}",row.due_at)
        if row.state=="ROUTED":add("UNACCEPTED_ASSIGNMENT","action",f"Assignment awaiting acceptance: {row.title}",row.due_at)
        if sla and sla.status=="APPROACHING":add("SLA_APPROACHING","action",f"SLA approaching: {row.title}",sla.due_at)
        if sla and sla.breached_at: add("SLA_BREACHED","critical",f"SLA breached: {row.title}",sla.due_at)
        if row.state=="OVERDUE":add("OVERDUE_EXECUTION","critical",f"Execution overdue: {row.title}",row.due_at)
        if execution and execution.status=="ON_HOLD":add("SPECIALIST_BLOCKED","action",f"Specialist work is on hold: {row.title}",row.due_at)
        if row.state=="PENDING_EVIDENCE":
            evidence=resolve_evidence_policy(s,row)
            if not evidence["satisfied"]:add("EVIDENCE_MISSING","action",f"Evidence required: {row.title}",row.due_at)
        if row.state in {"READY_FOR_REVIEW","COMPLETED"}:add("CLOSURE_WAITING","action",f"Dean closure review required: {row.title}",row.due_at)
    severity_order={"critical":0,"action":1,"info":2}
    return sorted(alerts,key=lambda x:(severity_order.get(x["severity"],3),x["due_at"] or "9999",x["created_at"]))

@router.get("/administration/alerts")
def administration_alerts(school_id:str="",department_id:str="",category:str="",priority:str="",office_n:Optional[int]=None,assignee_id:str="",severity:str="",status:str="OPEN",date_from:str="",date_to:str="",page:int=1,page_size:int=50,ctx=Depends(auth),s=Depends(db)):
    if not _is_leader(ctx):raise HTTPException(403,"Administrative alerts are restricted to leadership")
    try: alerts=_administration_alerts(s,_dashboard_rows(s,ctx,school_id,department_id,category,priority,office_n,assignee_id,date_from,date_to))
    except ValueError: raise HTTPException(422,"Invalid date filter")
    if severity:alerts=[a for a in alerts if a["severity"]==severity]
    if status:alerts=[a for a in alerts if a["status"]==status]
    total=len(alerts); start=(page-1)*page_size
    return {"alerts":alerts[start:start+page_size],"page":page,"page_size":page_size,"total":total}

@router.get("/administration/dashboard")
def dashboard(school_id:str="",department_id:str="",category:str="",priority:str="",office_n:Optional[int]=None,ctx=Depends(auth),s=Depends(db)):
    if not _is_leader(ctx):raise HTTPException(403,"Administrative dashboard is restricted to leadership")
    rows=_dashboard_rows(s,ctx,school_id,department_id,category,priority,office_n); alerts=_administration_alerts(s,rows)
    count=lambda kind:sum(1 for a in alerts if a["type"]==kind)
    status={x:sum(1 for r in rows if r.state==x) for x in sorted({r.state for r in rows})}
    budget_lines=s.query(D.BudgetLine).filter(D.BudgetLine.tenant_id==_tenant(ctx)).all()
    financial={"available":bool(budget_lines),"requested":sum(r.estimated_cost or 0 for r in rows if r.category=="BUDGET"),"approved":sum(r.estimated_cost or 0 for r in rows if r.category=="BUDGET" and r.state not in {"REJECTED","CANCELLED"}),"reserved":sum(x.reserved or 0 for x in budget_lines),"committed":sum(x.committed or 0 for x in budget_lines),"spent":sum(x.spent or 0 for x in budget_lines),"available_balance":sum((x.allocated or 0)-(x.spent or 0)-(x.reserved or 0)-(x.committed or 0) for x in budget_lines),"reason":None if budget_lines else "No authoritative BudgetLine records are configured"}
    return {"financial":financial,"kpis":{"open_requirements":sum(1 for r in rows if r.state not in {"CLOSED","REJECTED","CANCELLED"}),"pending_validation":sum(1 for r in rows if r.state in {"SUBMITTED","VALIDATING"}),"pending_approval":count("PENDING_APPROVAL"),"unaccepted_assignments":count("UNACCEPTED_ASSIGNMENT"),"active_specialist_work":sum(1 for r in rows if r.state in {"IN_EXECUTION","IN_PROGRESS","ON_HOLD"}),"sla_approaching":count("SLA_APPROACHING"),"sla_breached":count("SLA_BREACHED"),"overdue":count("OVERDUE_EXECUTION"),"evidence_missing":count("EVIDENCE_MISSING"),"closure_waiting":count("CLOSURE_WAITING")},"alerts":alerts[:12],"alert_count":len(alerts),"requests_by_status":status,"filters":{"school_id":school_id,"department_id":department_id,"category":category,"priority":priority,"office_n":office_n}}


REPORT_TYPES={"requirements","approval-aging","assignment-aging","specialist-execution","sla-performance","overdue","evidence-compliance","completion","closure","facilities","workforce","procurement","it"}


def _report_rows(s,ctx,report_type,**filters):
    if report_type in {"finance","store-assets"}: return None
    rows=_dashboard_rows(s,ctx,**filters)
    if report_type=="approval-aging": rows=[r for r in rows if r.state in {"PENDING_APPROVAL","ESCALATED"}]
    elif report_type=="assignment-aging": rows=[r for r in rows if r.state in {"ROUTED","RETURNED"}]
    elif report_type=="specialist-execution": rows=[r for r in rows if r.state in {"IN_EXECUTION","IN_PROGRESS","ON_HOLD","PENDING_EVIDENCE"}]
    elif report_type=="sla-performance": rows=[r for r in rows if s.query(A.AdministrativeSla).filter_by(requirement_id=r.id,tenant_id=r.tenant_id).first()]
    elif report_type=="overdue": rows=[r for r in rows if r.state=="OVERDUE"]
    elif report_type=="evidence-compliance": rows=[r for r in rows if r.state in {"PENDING_EVIDENCE","READY_FOR_REVIEW","COMPLETED","CLOSED"}]
    elif report_type=="completion": rows=[r for r in rows if r.state in {"PENDING_EVIDENCE","READY_FOR_REVIEW","COMPLETED","CLOSED"}]
    elif report_type=="closure": rows=[r for r in rows if r.state in {"READY_FOR_REVIEW","COMPLETED","CLOSED"}]
    elif report_type in {"facilities","workforce","procurement","it"}: rows=[r for r in rows if r.category=={"facilities":"FACILITIES","workforce":"WORKFORCE","procurement":"PROCUREMENT","it":"IT"}[report_type]]
    return rows


def _report_item(s,row):
    sla=s.query(A.AdministrativeSla).filter_by(requirement_id=row.id,tenant_id=row.tenant_id).first()
    policy=resolve_evidence_policy(s,row) if row.state in {"PENDING_EVIDENCE","READY_FOR_REVIEW","COMPLETED","CLOSED"} else None
    return {"id":row.id,"reference_code":row.reference_code,"title":row.title,"school_id":row.school_id,"department_id":row.department_id,"category":row.category,"priority":row.priority,"state":row.state,"office_n":row.responsible_office_n,"assignee_id":row.assigned_user_id,"created_at":row.created_at.isoformat(),"updated_at":row.updated_at.isoformat(),"due_at":row.due_at.isoformat() if row.due_at else None,"sla_status":sla.status if sla else None,"evidence_missing":policy["missing"] if policy and not policy["satisfied"] else []}


@router.get("/administration/reports/{report_type}")
def administration_report(report_type:str,school_id:str="",department_id:str="",category:str="",priority:str="",office_n:Optional[int]=None,assignee_id:str="",date_from:str="",date_to:str="",sort:str="updated_at",descending:bool=True,page:int=1,page_size:int=50,ctx=Depends(auth),s=Depends(db)):
    if not _is_leader(ctx): raise HTTPException(403,"Administration reports are restricted to leadership")
    if report_type not in REPORT_TYPES and report_type not in {"finance","store-assets"}: raise HTTPException(404,"Unknown administration report")
    if report_type in {"finance","store-assets"}: return {"available":False,"reason":"Authoritative domain integration is unavailable","items":[],"total":0}
    try: rows=_report_rows(s,ctx,report_type,school_id=school_id,department_id=department_id,category=category,priority=priority,office_n=office_n,assignee_id=assignee_id,date_from=date_from,date_to=date_to)
    except ValueError: raise HTTPException(422,"Invalid report filter")
    if sort not in {"created_at","updated_at","priority","state","category"}: raise HTTPException(422,"Unsupported report sort")
    rows=sorted(rows,key=lambda row:(getattr(row,sort) or ""),reverse=descending); total=len(rows); start=(page-1)*page_size
    return {"available":True,"report_type":report_type,"items":[_report_item(s,row) for row in rows[start:start+page_size]],"page":page,"page_size":page_size,"total":total}


@router.get("/administration/reports/{report_type}/export.csv")
def administration_report_export(report_type:str,school_id:str="",department_id:str="",category:str="",priority:str="",office_n:Optional[int]=None,assignee_id:str="",date_from:str="",date_to:str="",ctx=Depends(auth),s=Depends(db)):
    result=administration_report(report_type,school_id,department_id,category,priority,office_n,assignee_id,date_from,date_to,"updated_at",True,1,200,ctx,s)
    if not result.get("available"): raise HTTPException(409,result["reason"])
    output=io.StringIO(); fields=["reference_code","title","school_id","department_id","category","priority","state","office_n","assignee_id","created_at","updated_at","due_at","sla_status","evidence_missing"]
    writer=csv.DictWriter(output,fieldnames=fields);writer.writeheader()
    for item in result["items"]: writer.writerow({key: ",".join(item[key]) if isinstance(item[key],list) else item[key] for key in fields})
    return Response(output.getvalue(),media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="icms-administration-{report_type}.csv"'})
