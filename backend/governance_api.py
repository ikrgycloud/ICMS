"""Unified academic governance inbox, evidence, lifecycle and exception APIs."""
import hashlib
import json
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc

from core import db, auth, uid, write_audit
from database import TENANT
from models import GovernanceDocument, GovernancePolicy, GovernanceNotification, ControlledAcademicRecord, TimetableExceptionWorkflow, User
import domain_models as D
from governance_engine import STATES, payload, policy_for, transition

router = APIRouter(prefix="/api/academic-governance")
LEADERSHIP = {6, 10, 17}


def leadership(ctx):
    if ctx.get("office_n") not in LEADERSHIP:
        raise HTTPException(403, "Academic governance access denied")


class TransitionIn(BaseModel):
    target_state: str
    expected_status_version: int = Field(ge=0)
    reason: str = ""
    reviewer_id: str = ""
    evidence_document_ids: list[str] = []


class ReviewerIn(BaseModel):
    reviewer_id: str
    expected_status_version: int = Field(ge=0)
    reason: str = "Reviewer assignment"


class DocumentIn(BaseModel):
    owner_entity_type: str
    owner_entity_id: str
    file_name: str
    mime_type: str = "application/octet-stream"
    size_bytes: int = Field(default=0, ge=0)
    object_storage_key: str
    checksum: str
    access_scope: str = "governance"


class ControlledRecordIn(BaseModel):
    record_type: str
    entity_ref: str
    payload: dict = {}
    effective_from: str = ""


class ExceptionTransitionIn(BaseModel):
    target_state: str
    expected_status_version: int = Field(ge=0)
    assigned_to: str = ""
    reason: str = ""
    evidence_document_ids: list[str] = []


class CurriculumVersionIn(BaseModel):
    program_id: str = ""
    regulation: str
    effective_term: str
    course_ids: list[str] = []
    source_proposal_id: str = ""


class ProgramAssessmentIn(BaseModel):
    proposal_id: str
    capacity: int = Field(ge=0)
    intake: int = Field(ge=0)
    faculty_workload: float = Field(ge=0)
    faculty_ready: bool = False
    infrastructure_ready: bool = False
    infrastructure_requirements: list[str] = []


class CalendarVersionIn(BaseModel):
    term: str
    snapshot: list[dict] = []
    source_proposal_id: str = ""


class FacultyAvailabilityIn(BaseModel):
    faculty_id: str
    term: str
    available_units: float = Field(ge=0)
    unavailable_slots: list[dict] = []


class WorkloadRuleIn(BaseModel):
    term: str
    min_units: float = Field(ge=0)
    max_units: float = Field(ge=0)
    overload_threshold: float = Field(ge=0)
    underload_threshold: float = Field(ge=0)


class FacultyConflictIn(BaseModel):
    faculty_id: str
    assignment_ids: list[str] = []
    reason: str
    evidence_document_ids: list[str] = []


class TeachingPlanIn(BaseModel):
    section_id: str
    term: str
    objectives: str = ""


class ProgressIn(BaseModel):
    topic: str
    planned_date: str = ""
    completed_date: str = ""
    status: str = "planned"
    evidence_document_ids: list[str] = []


class MilestoneIn(BaseModel):
    term: str
    title: str
    due_at: str
    owner_id: str = ""


class CompletionIn(BaseModel):
    section_id: str
    term: str
    completion_pct: float = Field(ge=0, le=100)


class DeliveryExceptionIn(BaseModel):
    section_id: str = ""
    kind: str
    description: str = ""
    owner_id: str = ""


def audit_mutation(s, ctx, action, entity, previous, current, reason, version=0):
    audit = write_audit(s, ctx["sub"], ctx["sub"], ctx["office_n"], action, entity, previous, current, reason, commit=False)
    audit.entity_version = version
    return audit


@router.get("/policies")
def policies(ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    rows = s.query(GovernancePolicy).filter(GovernancePolicy.tenant_id == TENANT, GovernancePolicy.active == True).all()
    return {"policies": [{"proposal_type": row.proposal_type, "states": STATES, "transitions": json.loads(row.allowed_transitions_json or "{}"), "required_reason_states": json.loads(row.required_reason_states_json or "[]"), "reviewer_office_n": row.reviewer_office_n} for row in rows]}


@router.get("/inbox")
def decision_inbox(ctx=Depends(auth), s=Depends(db), state: str = ""):
    leadership(ctx)
    query = s.query(D.AcademicProposal).filter(D.AcademicProposal.tenant_id == TENANT)
    if ctx["office_n"] != 6:
        query = query.filter(D.AcademicProposal.assigned_to_office_n == ctx["office_n"])
        scope_ref = (ctx.get("scope_ref") or "").removeprefix("dept_").removeprefix("scope_")
        if scope_ref and s.get(D.Department, scope_ref):
            query = query.filter((D.AcademicProposal.dept_id == scope_ref) | (D.AcademicProposal.dept_id == None))
    if state:
        query = query.filter(D.AcademicProposal.state == state.upper())
    pending_states = ["SUBMITTED", "UNDER_REVIEW", "RESUBMITTED", "ESCALATED"]
    rows = query.filter(D.AcademicProposal.state.in_(pending_states)).order_by(desc(D.AcademicProposal.updated_at)).all()
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    all_rows = query.all()
    completed = [row for row in all_rows if row.state in {"APPROVED", "REJECTED", "RETURNED", "IMPLEMENTED", "ARCHIVED"} and row.updated_at and row.updated_at >= month_start]
    enriched = []
    for row in rows:
        item = payload(s, row)
        department = s.get(D.Department, row.dept_id) if row.dept_id else None
        requester = s.get(User, row.submitted_by) if row.submitted_by else None
        due = row.due_at
        overdue = bool(due and due < now)
        hours = ((due - now).total_seconds() / 3600) if due else None
        priority = "Critical" if overdue else "High" if hours is not None and hours <= 24 else "Medium" if hours is not None and hours <= 72 else "Low"
        item.update({"department": department.name if department else "Institution scope", "department_id": row.dept_id, "requester_id": row.submitted_by, "requester": requester.username if requester else row.submitted_by, "priority": priority, "overdue": overdue, "status_label": "Overdue" if overdue else "In Review" if row.state == "UNDER_REVIEW" else "Pending"})
        enriched.append(item)
    return {"proposals": enriched, "history": [payload(s, row) for row in completed], "states": STATES, "count": len(rows), "summary": {"pending": len(rows), "urgent": sum(1 for item in enriched if item["priority"] in {"Critical", "High"}), "due_today": sum(1 for item in enriched if item["due_at"] and item["due_at"][:10] == now.date().isoformat()), "completed_month": len(completed)}}


@router.get("/my-requests")
def my_requests(ctx=Depends(auth), s=Depends(db)):
    """Return only academic proposals created by the authenticated actor."""
    query = s.query(D.AcademicProposal).filter(
        D.AcademicProposal.tenant_id == ctx["tenant_id"],
        D.AcademicProposal.submitted_by == ctx["sub"],
    ).order_by(desc(D.AcademicProposal.updated_at))
    rows = query.all()
    result = []
    for row in rows:
        item = payload(s, row)
        version = s.query(D.AcademicProposalVersion).filter(
            D.AcademicProposalVersion.proposal_id == row.id,
            D.AcademicProposalVersion.version_no == row.version_no,
        ).first()
        events = s.query(D.AcademicProposalEvent).filter(
            D.AcademicProposalEvent.proposal_id == row.id,
        ).order_by(D.AcademicProposalEvent.created_at).all()
        department = s.get(D.Department, row.dept_id) if row.dept_id else None
        item.update({
            "department": department.name if department else "Institution scope",
            "department_id": row.dept_id,
            "submitted_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "payload": json.loads(version.payload_json or "{}") if version else {},
            "events": [{"from_state": event.from_state, "to_state": event.to_state, "actor_id": event.actor_id, "office_n": event.actor_office_n, "reason": event.reason, "at": event.created_at.isoformat() if event.created_at else None} for event in events],
        })
        result.append(item)
    completed = {"APPROVED", "IMPLEMENTED", "CLOSED", "REJECTED"}
    return {"requests": result, "summary": {
        "all": len(result),
        "drafts": sum(1 for row in result if row["state"] == "DRAFT"),
        "in_review": sum(1 for row in result if row["state"] in {"SUBMITTED", "RESUBMITTED", "UNDER_REVIEW", "ESCALATED"}),
        "needs_revision": sum(1 for row in result if row["state"] in {"RETURNED", "CLARIFICATION_REQUIRED"}),
        "completed": sum(1 for row in result if row["state"] in completed),
    }}


@router.post("/my-requests/{proposal_id}/transition")
def transition_my_request(proposal_id: str, body: TransitionIn, ctx=Depends(auth), s=Depends(db)):
    proposal = s.query(D.AcademicProposal).filter(
        D.AcademicProposal.id == proposal_id,
        D.AcademicProposal.tenant_id == ctx["tenant_id"],
        D.AcademicProposal.submitted_by == ctx["sub"],
    ).with_for_update().first()
    if not proposal:
        raise HTTPException(404, "Request not found")
    if body.target_state not in {"SUBMITTED", "RESUBMITTED"}:
        raise HTTPException(403, "Only submit and resubmit are available to request owners")
    transition(s, proposal, body.target_state, body.expected_status_version, {**ctx, "actor_name": ctx["sub"]}, body.reason)
    s.commit()
    return {"request": payload(s, proposal)}


@router.post("/proposals/{proposal_id}/reviewer")
def assign_reviewer(proposal_id: str, body: ReviewerIn, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    proposal = s.query(D.AcademicProposal).filter(D.AcademicProposal.id == proposal_id, D.AcademicProposal.tenant_id == TENANT).with_for_update().first()
    if not proposal:
        raise HTTPException(404, "Proposal not found")
    reviewer = s.query(User).filter(User.id == body.reviewer_id, User.tenant_id == TENANT, User.status == "active").first()
    if not reviewer:
        raise HTTPException(404, "Reviewer not found")
    transition(s, proposal, "UNDER_REVIEW", body.expected_status_version, {**ctx, "actor_name": ctx["sub"]}, body.reason, body.reviewer_id)
    s.commit()
    return {"proposal": payload(s, proposal)}


@router.post("/proposals/{proposal_id}/transition")
def proposal_transition(proposal_id: str, body: TransitionIn, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    target = body.target_state.upper()
    if target not in STATES:
        raise HTTPException(422, "Unknown governance state")
    proposal = s.query(D.AcademicProposal).filter(D.AcademicProposal.id == proposal_id, D.AcademicProposal.tenant_id == TENANT).with_for_update().first()
    if not proposal:
        raise HTTPException(404, "Proposal not found")
    transition(s, proposal, target, body.expected_status_version, {**ctx, "actor_name": ctx["sub"]}, body.reason, body.reviewer_id, body.evidence_document_ids)
    s.commit()
    return {"proposal": payload(s, proposal)}


@router.post("/documents")
def upload_document(body: DocumentIn, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    if len(body.checksum) < 32:
        raise HTTPException(422, "Immutable checksum is required")
    if s.query(GovernanceDocument).filter(GovernanceDocument.tenant_id == TENANT, GovernanceDocument.checksum == body.checksum).first():
        raise HTTPException(409, "Document checksum already exists")
    row = GovernanceDocument(id=uid(), tenant_id=TENANT, uploaded_by=ctx["sub"], uploaded_at=datetime.utcnow(), **body.model_dump())
    s.add(row)
    audit = write_audit(s, ctx["sub"], ctx["sub"], ctx["office_n"], "governance.document.upload", f"document:{row.id}", "", "uploaded", "Evidence uploaded", commit=False)
    audit.entity_version = row.version
    s.commit()
    return {"document": {"id": row.id, "checksum": row.checksum, "version": row.version, "owner_entity_type": row.owner_entity_type, "owner_entity_id": row.owner_entity_id}}


@router.get("/documents/{entity_type}/{entity_id}")
def documents(entity_type: str, entity_id: str, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    rows = s.query(GovernanceDocument).filter(GovernanceDocument.tenant_id == TENANT, GovernanceDocument.owner_entity_type == entity_type, GovernanceDocument.owner_entity_id == entity_id).order_by(GovernanceDocument.version).all()
    return {"documents": [{"id": row.id, "file_name": row.file_name, "mime_type": row.mime_type, "size_bytes": row.size_bytes, "object_storage_key": row.object_storage_key, "checksum": row.checksum, "version": row.version, "access_scope": row.access_scope, "uploaded_by": row.uploaded_by, "uploaded_at": row.uploaded_at.isoformat()} for row in rows]}


@router.get("/notifications/outcomes")
def notification_outcomes(ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    rows = s.query(GovernanceNotification).filter(GovernanceNotification.tenant_id == TENANT).order_by(desc(GovernanceNotification.created_at)).limit(100).all()
    return {"outcomes": [{"id": row.id, "workflow_id": row.workflow_id, "recipient_id": row.recipient_id, "event": row.event, "outcome": row.outcome, "created_at": row.created_at.isoformat()} for row in rows]}


@router.post("/records")
def create_controlled_record(body: ControlledRecordIn, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    now = datetime.utcnow()
    previous = s.query(ControlledAcademicRecord).filter(ControlledAcademicRecord.tenant_id == TENANT, ControlledAcademicRecord.record_type == body.record_type, ControlledAcademicRecord.entity_ref == body.entity_ref, ControlledAcademicRecord.status == "effective").all()
    for row in previous:
        row.status = "superseded"
        row.effective_to = now
    row = ControlledAcademicRecord(id=uid(), tenant_id=TENANT, record_type=body.record_type, entity_ref=body.entity_ref, version=len(previous) + 1, effective_from=datetime.fromisoformat(body.effective_from) if body.effective_from else now, payload_json=json.dumps(body.payload), source_proposal_id=body.entity_ref, created_by=ctx["sub"], created_at=now)
    s.add(row)
    audit = write_audit(s, ctx["sub"], ctx["sub"], ctx["office_n"], "governance.record.publish", f"controlled_record:{row.id}", "superseded" if previous else "", "effective", "Controlled academic record published", commit=False)
    audit.entity_version = row.version
    s.commit()
    return {"record": {"id": row.id, "record_type": row.record_type, "entity_ref": row.entity_ref, "version": row.version, "status": row.status, "effective_from": row.effective_from.isoformat()}}


@router.get("/records/{record_type}/{entity_ref}")
def controlled_records(record_type: str, entity_ref: str, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    rows = s.query(ControlledAcademicRecord).filter(ControlledAcademicRecord.tenant_id == TENANT, ControlledAcademicRecord.record_type == record_type, ControlledAcademicRecord.entity_ref == entity_ref).order_by(ControlledAcademicRecord.version.desc()).all()
    return {"records": [{"id": row.id, "version": row.version, "status": row.status, "payload": json.loads(row.payload_json or "{}"), "effective_from": row.effective_from.isoformat() if row.effective_from else None, "effective_to": row.effective_to.isoformat() if row.effective_to else None} for row in rows]}


@router.get("/exceptions")
def exception_workflows(ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    rows = s.query(TimetableExceptionWorkflow).filter(TimetableExceptionWorkflow.tenant_id == TENANT).order_by(desc(TimetableExceptionWorkflow.updated_at)).all()
    return {"exceptions": [{"id": row.id, "exception_id": row.exception_id, "state": row.state, "assigned_to": row.assigned_to, "evidence_document_ids": json.loads(row.evidence_document_ids or "[]"), "status_version": row.status_version, "reason": row.reason} for row in rows]}


@router.post("/exceptions/{exception_id}/transition")
def exception_transition(exception_id: str, body: ExceptionTransitionIn, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    exception = s.query(D.TimetableException).filter(D.TimetableException.id == exception_id, D.TimetableException.tenant_id == TENANT).first()
    if not exception:
        raise HTTPException(404, "Timetable exception not found")
    row = s.query(TimetableExceptionWorkflow).filter(TimetableExceptionWorkflow.exception_id == exception_id, TimetableExceptionWorkflow.tenant_id == TENANT).with_for_update().first()
    if not row:
        row = TimetableExceptionWorkflow(id=uid(), tenant_id=TENANT, exception_id=exception_id)
        s.add(row)
        s.flush()
    allowed = {"detected": {"assigned"}, "assigned": {"in_remediation"}, "in_remediation": {"evidence_submitted"}, "evidence_submitted": {"verified"}, "verified": {"closed", "reopened"}, "closed": {"reopened"}, "reopened": {"assigned"}}
    target = body.target_state.lower()
    if target not in allowed.get(row.state, set()):
        raise HTTPException(409, f"Exception transition {row.state} -> {target} is not allowed")
    if row.status_version != body.expected_status_version:
        raise HTTPException(409, "Exception changed; reload before transitioning")
    if target in {"evidence_submitted", "verified", "closed", "reopened"} and not body.reason.strip():
        raise HTTPException(422, "A reason is required for exception closure or evidence transitions")
    if target in {"verified", "closed", "reopened"} and ctx["office_n"] != 6:
        raise HTTPException(403, "Only Dean Academics may verify or close exceptions")
    row.state = target
    row.assigned_to = body.assigned_to or row.assigned_to
    row.evidence_document_ids = json.dumps(body.evidence_document_ids)
    row.reason = body.reason.strip()
    row.updated_by = ctx["sub"]
    row.status_version += 1
    row.updated_at = datetime.utcnow()
    if target == "closed":
        exception.status = "RESOLVED"
        exception.resolved_by = ctx["sub"]
        exception.resolved_at = datetime.utcnow()
    elif target == "reopened":
        exception.status = "OPEN"
    audit = write_audit(s, ctx["sub"], ctx["sub"], ctx["office_n"], "governance.exception." + target, f"timetable_exception:{exception_id}", "", target, body.reason, commit=False)
    audit.entity_version = row.status_version
    audit.workflow_id = row.id
    audit.evidence_document_ids = json.dumps(body.evidence_document_ids)
    s.commit()
    return {"exception": {"id": row.id, "exception_id": row.exception_id, "state": row.state, "status_version": row.status_version, "exception_status": exception.status}}


@router.post("/curriculum/versions")
def create_curriculum_version(body: CurriculumVersionIn, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    courses = s.query(D.Course).filter(D.Course.tenant_id == TENANT, D.Course.id.in_(body.course_ids)).all() if body.course_ids else []
    if len(courses) != len(set(body.course_ids)):
        raise HTTPException(404, "One or more curriculum courses were not found")
    active = s.query(D.CurriculumVersion).filter(D.CurriculumVersion.tenant_id == TENANT, D.CurriculumVersion.program_id == (body.program_id or None), D.CurriculumVersion.effective_term == body.effective_term, D.CurriculumVersion.status == "effective").first()
    version = (active.version + 1) if active else 1
    snapshot = [{"id": c.id, "code": c.code, "title": c.title, "credits": c.credits, "semester": c.semester} for c in courses]
    row = D.CurriculumVersion(id=uid(), tenant_id=TENANT, program_id=body.program_id or None, regulation=body.regulation, effective_term=body.effective_term, version=version, status="draft", snapshot_json=json.dumps(snapshot), source_proposal_id=body.source_proposal_id, created_by=ctx["sub"])
    s.add(row); s.flush()
    checksum = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    s.add(D.CurriculumSnapshot(id=uid(), tenant_id=TENANT, curriculum_version_id=row.id, course_set_json=json.dumps(snapshot), checksum=checksum))
    audit_mutation(s, ctx, "governance.curriculum.version.create", f"curriculum_version:{row.id}", "", "draft", "Curriculum snapshot created", version)
    s.commit()
    return {"version": {"id": row.id, "version": row.version, "status": row.status, "course_count": len(snapshot), "checksum": checksum}}


@router.get("/curriculum/versions")
def curriculum_versions(ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    rows = s.query(D.CurriculumVersion).filter(D.CurriculumVersion.tenant_id == TENANT).order_by(D.CurriculumVersion.effective_term.desc(), D.CurriculumVersion.version.desc()).all()
    return {"versions": [{"id": row.id, "program_id": row.program_id, "regulation": row.regulation, "effective_term": row.effective_term, "version": row.version, "status": row.status, "course_count": len(json.loads(row.snapshot_json or "[]"))} for row in rows]}


@router.get("/curriculum/versions/{version_id}/compare/{other_id}")
def compare_curriculum_versions(version_id: str, other_id: str, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    rows = [s.query(D.CurriculumVersion).filter(D.CurriculumVersion.id == item, D.CurriculumVersion.tenant_id == TENANT).first() for item in (version_id, other_id)]
    if any(row is None for row in rows):
        raise HTTPException(404, "Curriculum version not found")
    left, right = [set(item["id"] for item in json.loads(row.snapshot_json or "[]")) for row in rows]
    return {"from_version": version_id, "to_version": other_id, "added_course_ids": sorted(right - left), "removed_course_ids": sorted(left - right), "unchanged_course_ids": sorted(left & right)}


@router.post("/curriculum/versions/{version_id}/publish")
def publish_curriculum_version(version_id: str, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    row = s.query(D.CurriculumVersion).filter(D.CurriculumVersion.id == version_id, D.CurriculumVersion.tenant_id == TENANT).with_for_update().first()
    if not row: raise HTTPException(404, "Curriculum version not found")
    if row.status != "draft": raise HTTPException(409, "Only draft curriculum versions can be published")
    superseded = s.query(D.CurriculumVersion).filter(D.CurriculumVersion.tenant_id == TENANT, D.CurriculumVersion.program_id == row.program_id, D.CurriculumVersion.effective_term == row.effective_term, D.CurriculumVersion.status == "effective").all()
    for old in superseded: old.status = "archived"
    row.status = "effective"; row.effective_at = datetime.utcnow()
    audit_mutation(s, ctx, "governance.curriculum.version.publish", f"curriculum_version:{row.id}", "draft", "effective", "Curriculum version published", row.version)
    s.commit()
    return {"version": {"id": row.id, "status": row.status, "version": row.version}}


@router.post("/calendar/versions")
def create_calendar_version(body: CalendarVersionIn, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    previous = s.query(D.CalendarVersion).filter(D.CalendarVersion.tenant_id == TENANT, D.CalendarVersion.term == body.term).order_by(D.CalendarVersion.version.desc()).first()
    row = D.CalendarVersion(id=uid(), tenant_id=TENANT, term=body.term, version=(previous.version + 1 if previous else 1), snapshot_json=json.dumps(body.snapshot), source_proposal_id=body.source_proposal_id, created_by=ctx["sub"])
    s.add(row); s.flush()
    for downstream in ("timetable", "examinations", "results", "registration", "milestones"):
        s.add(D.CalendarImpactTask(id=uid(), tenant_id=TENANT, calendar_version_id=row.id, downstream=downstream))
    audit_mutation(s, ctx, "governance.calendar.version.create", f"calendar_version:{row.id}", "", "draft", "Calendar snapshot created", row.version); s.commit()
    return {"version": {"id": row.id, "term": row.term, "version": row.version, "status": row.status, "impact_tasks": 5}}


@router.get("/calendar/versions")
def calendar_versions(ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    rows = s.query(D.CalendarVersion).filter(D.CalendarVersion.tenant_id == TENANT).order_by(D.CalendarVersion.term.desc(), D.CalendarVersion.version.desc()).all()
    return {"versions": [{"id": row.id, "term": row.term, "version": row.version, "status": row.status, "effective_at": row.effective_at.isoformat() if row.effective_at else None} for row in rows]}


@router.post("/calendar/versions/{version_id}/publish")
def publish_calendar_version(version_id: str, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    row = s.query(D.CalendarVersion).filter(D.CalendarVersion.id == version_id, D.CalendarVersion.tenant_id == TENANT).with_for_update().first()
    if not row: raise HTTPException(404, "Calendar version not found")
    if row.status != "draft": raise HTTPException(409, "Only draft calendar versions can be published")
    old = s.query(D.CalendarVersion).filter(D.CalendarVersion.tenant_id == TENANT, D.CalendarVersion.term == row.term, D.CalendarVersion.status == "effective").all()
    for item in old: item.status = "archived"
    row.status = "effective"; row.effective_at = datetime.utcnow()
    audit_mutation(s, ctx, "governance.calendar.version.publish", f"calendar_version:{row.id}", "draft", "effective", "Calendar version published", row.version); s.commit()
    return {"version": {"id": row.id, "status": row.status, "version": row.version}}


@router.post("/calendar/versions/{version_id}/acknowledge/{downstream}")
def acknowledge_calendar_impact(version_id: str, downstream: str, reason: str = "", ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    task = s.query(D.CalendarImpactTask).filter(D.CalendarImpactTask.calendar_version_id == version_id, D.CalendarImpactTask.downstream == downstream, D.CalendarImpactTask.tenant_id == TENANT).first()
    if not task: raise HTTPException(404, "Calendar impact task not found")
    task.status = "acknowledged"; task.acknowledged_by = ctx["sub"]; task.acknowledged_at = datetime.utcnow(); task.reason = reason
    audit_mutation(s, ctx, "governance.calendar.impact.acknowledge", f"calendar_impact:{task.id}", "pending", "acknowledged", reason); s.commit()
    return {"task": {"id": task.id, "downstream": task.downstream, "status": task.status, "acknowledged_by": task.acknowledged_by}}


@router.post("/program/assessments")
def assess_program(body: ProgramAssessmentIn, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    proposal = s.query(D.AcademicProposal).filter(D.AcademicProposal.id == body.proposal_id, D.AcademicProposal.tenant_id == TENANT, D.AcademicProposal.proposal_type == "program").first()
    if not proposal: raise HTTPException(404, "Program proposal not found")
    required = len(body.infrastructure_requirements)
    escalation = body.intake > body.capacity or not body.faculty_ready or not body.infrastructure_ready or required > 0
    row = D.ProgramAssessment(id=uid(), tenant_id=TENANT, proposal_id=proposal.id, capacity=body.capacity, intake=body.intake, faculty_workload=body.faculty_workload, faculty_ready=body.faculty_ready, infrastructure_ready=body.infrastructure_ready, infrastructure_requirements_json=json.dumps(body.infrastructure_requirements), principal_escalation_required=escalation, assessed_by=ctx["sub"])
    s.add(row); audit_mutation(s, ctx, "governance.program.assess", f"program_assessment:{row.id}", "", "assessed", "Program capacity, workload, and infrastructure assessment")
    s.commit()
    return {"assessment": {"id": row.id, "capacity": row.capacity, "intake": row.intake, "faculty_ready": row.faculty_ready, "infrastructure_ready": row.infrastructure_ready, "principal_escalation_required": escalation}}


@router.get("/program/assessments/{proposal_id}")
def program_assessment(proposal_id: str, ctx=Depends(auth), s=Depends(db)):
    """Return the most recent feasibility evidence for a programme proposal."""
    leadership(ctx)
    proposal = s.query(D.AcademicProposal).filter(D.AcademicProposal.id == proposal_id, D.AcademicProposal.tenant_id == TENANT, D.AcademicProposal.proposal_type == "program").first()
    if not proposal:
        raise HTTPException(404, "Program proposal not found")
    row = s.query(D.ProgramAssessment).filter(D.ProgramAssessment.tenant_id == TENANT, D.ProgramAssessment.proposal_id == proposal_id).order_by(desc(D.ProgramAssessment.created_at)).first()
    if not row:
        return {"assessment": None}
    return {"assessment": {"id": row.id, "capacity": row.capacity, "intake": row.intake, "faculty_workload": row.faculty_workload, "faculty_ready": row.faculty_ready, "infrastructure_ready": row.infrastructure_ready, "infrastructure_requirements": json.loads(row.infrastructure_requirements_json or "[]"), "principal_escalation_required": row.principal_escalation_required, "assessed_by": row.assessed_by, "created_at": row.created_at.isoformat() if row.created_at else None}}


@router.post("/faculty/availability")
def set_faculty_availability(body: FacultyAvailabilityIn, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    faculty = s.query(D.StaffMember).filter(D.StaffMember.id == body.faculty_id, D.StaffMember.tenant_id == TENANT).first()
    if not faculty: raise HTTPException(404, "Faculty member not found")
    row = s.query(D.FacultyAvailability).filter(D.FacultyAvailability.faculty_id == body.faculty_id, D.FacultyAvailability.term == body.term, D.FacultyAvailability.tenant_id == TENANT).first()
    if not row: row = D.FacultyAvailability(id=uid(), tenant_id=TENANT, faculty_id=body.faculty_id, term=body.term); s.add(row)
    row.available_units = body.available_units; row.unavailable_slots_json = json.dumps(body.unavailable_slots); row.updated_by = ctx["sub"]; row.updated_at = datetime.utcnow()
    audit_mutation(s, ctx, "governance.faculty.availability", f"faculty_availability:{row.id}", "", "available", "Faculty availability updated")
    s.commit(); return {"availability": {"id": row.id, "faculty_id": row.faculty_id, "term": row.term, "available_units": row.available_units, "unavailable_slots": body.unavailable_slots}}


@router.post("/faculty/workload-rules")
def set_workload_rule(body: WorkloadRuleIn, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    if body.max_units < body.min_units or body.overload_threshold < body.max_units or body.underload_threshold > body.min_units:
        raise HTTPException(422, "Workload thresholds are inconsistent")
    row = D.FacultyWorkloadRule(id=uid(), tenant_id=TENANT, term=body.term, min_units=body.min_units, max_units=body.max_units, overload_threshold=body.overload_threshold, underload_threshold=body.underload_threshold)
    s.add(row); audit_mutation(s, ctx, "governance.faculty.workload_rule", f"faculty_workload_rule:{row.id}", "", "active", "Workload threshold configured"); s.commit()
    return {"rule": {"id": row.id, "term": row.term, "min_units": row.min_units, "max_units": row.max_units, "overload_threshold": row.overload_threshold, "underload_threshold": row.underload_threshold}}


@router.get("/faculty/workload/{term}")
def faculty_workload(term: str, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    rule = s.query(D.FacultyWorkloadRule).filter(D.FacultyWorkloadRule.tenant_id == TENANT, D.FacultyWorkloadRule.term == term, D.FacultyWorkloadRule.active == True).order_by(D.FacultyWorkloadRule.id.desc()).first()
    allocations = s.query(D.FacultyAllocation).filter(D.FacultyAllocation.tenant_id == TENANT, D.FacultyAllocation.term == term, D.FacultyAllocation.status == "APPROVED").all()
    totals = {}
    for item in allocations: totals[item.faculty_person_id] = totals.get(item.faculty_person_id, 0) + (item.workload_units or 0)
    return {"term": term, "rule": {"min_units": rule.min_units, "max_units": rule.max_units, "overload_threshold": rule.overload_threshold, "underload_threshold": rule.underload_threshold} if rule else None, "faculty": [{"faculty_id": key, "workload_units": value, "status": "overload" if rule and value > rule.overload_threshold else "underload" if rule and value < rule.underload_threshold else "within_threshold"} for key, value in totals.items()]}


@router.post("/faculty/conflicts")
def create_faculty_conflict(body: FacultyConflictIn, ctx=Depends(auth), s=Depends(db)):
    if ctx.get("office_n") not in LEADERSHIP and ctx.get("office_n") not in {10, 17}: raise HTTPException(403, "Faculty conflict access denied")
    faculty = s.query(D.StaffMember).filter(D.StaffMember.id == body.faculty_id, D.StaffMember.tenant_id == TENANT).first()
    if not faculty: raise HTTPException(404, "Faculty member not found")
    if not body.reason.strip(): raise HTTPException(422, "A conflict exception reason is required")
    row = D.FacultyConflictException(id=uid(), tenant_id=TENANT, faculty_id=body.faculty_id, assignment_ids_json=json.dumps(body.assignment_ids), reason=body.reason.strip(), evidence_document_ids=json.dumps(body.evidence_document_ids))
    s.add(row); audit_mutation(s, ctx, "governance.faculty.conflict.create", f"faculty_conflict:{row.id}", "", "OPEN", body.reason); s.commit()
    return {"exception": {"id": row.id, "faculty_id": row.faculty_id, "state": row.state, "evidence_document_ids": body.evidence_document_ids}}


@router.get("/faculty/conflicts")
def faculty_conflicts(ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    rows = s.query(D.FacultyConflictException).filter(D.FacultyConflictException.tenant_id == TENANT).order_by(D.FacultyConflictException.created_at.desc()).all()
    return {"exceptions": [{"id": row.id, "faculty_id": row.faculty_id, "assignment_ids": json.loads(row.assignment_ids_json or "[]"), "reason": row.reason, "state": row.state, "evidence_document_ids": json.loads(row.evidence_document_ids or "[]"), "approved_by": row.approved_by} for row in rows]}


@router.post("/faculty/conflicts/{exception_id}/approve")
def approve_faculty_conflict(exception_id: str, reason: str = "", ctx=Depends(auth), s=Depends(db)):
    if ctx.get("office_n") != 6: raise HTTPException(403, "Only Dean Academics may approve faculty conflict exceptions")
    row = s.query(D.FacultyConflictException).filter(D.FacultyConflictException.id == exception_id, D.FacultyConflictException.tenant_id == TENANT).first()
    if not row: raise HTTPException(404, "Faculty conflict exception not found")
    if row.state != "OPEN": raise HTTPException(409, "Faculty conflict exception is already decided")
    if not reason.strip(): raise HTTPException(422, "Approval reason is required")
    row.state = "APPROVED"; row.approved_by = ctx["sub"]
    audit_mutation(s, ctx, "governance.faculty.conflict.approve", f"faculty_conflict:{row.id}", "OPEN", "APPROVED", reason, 1); s.commit()
    return {"exception": {"id": row.id, "state": row.state, "approved_by": row.approved_by}}


@router.get("/timetable/conflicts")
def timetable_conflicts(term: str = "", ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    sections = s.query(D.Section).filter(D.Section.tenant_id == TENANT, *([D.Section.term == term] if term else [])).all()
    section_map = {item.id: item for item in sections}
    entries = s.query(D.TimetableEntry).filter(D.TimetableEntry.tenant_id == TENANT, D.TimetableEntry.status == "active", D.TimetableEntry.section_id.in_(section_map)).all() if sections else []
    faculty = {item.id: item for item in s.query(D.StaffMember).filter(D.StaffMember.tenant_id == TENANT).all()}
    availability = {(item.faculty_id, item.term): item for item in s.query(D.FacultyAvailability).filter(D.FacultyAvailability.tenant_id == TENANT).all()}
    conflicts = []
    def overlap(left, right): return left.day_of_week == right.day_of_week and left.start_time < right.end_time and right.start_time < left.end_time
    for index, left in enumerate(entries):
        section = section_map[left.section_id]
        for right in entries[index + 1:]:
            other = section_map[right.section_id]
            if not overlap(left, right): continue
            left_course = s.get(D.Course, section.course_id)
            right_course = s.get(D.Course, other.course_id)
            if left.room and left.room == right.room: conflicts.append({"kind": "room_overlap", "entry_ids": [left.id, right.id], "message": f"Room {left.room} is double-booked"})
            if section.faculty_person_id and section.faculty_person_id == other.faculty_person_id: conflicts.append({"kind": "faculty_overlap", "entry_ids": [left.id, right.id], "message": "Faculty assignment overlaps"})
            if section.section_code == other.section_code or (left_course and right_course and left_course.program_id and left_course.program_id == right_course.program_id): conflicts.append({"kind": "student_batch_overlap", "entry_ids": [left.id, right.id], "message": "Student or batch timetable overlap"})
        if not section.faculty_person_id: conflicts.append({"kind": "course_faculty_assignment", "entry_ids": [left.id], "message": "Course has no faculty assignment"})
        if section.capacity <= 0: conflicts.append({"kind": "capacity", "entry_ids": [left.id], "message": "Section capacity is not positive"})
        course = s.get(D.Course, section.course_id)
        if course and "lab" in (course.course_type or "").lower() and not left.room: conflicts.append({"kind": "lab_requirement", "entry_ids": [left.id], "message": "Lab course requires a room"})
        if section.faculty_person_id:
            available = availability.get((section.faculty_person_id, section.term))
            if available and available.status != "available": conflicts.append({"kind": "faculty_availability", "entry_ids": [left.id], "message": "Faculty is unavailable for this term"})
    return {"term": term, "conflicts": conflicts, "count": len(conflicts), "revalidated_at": datetime.utcnow().isoformat()}


@router.post("/delivery/plans")
def create_teaching_plan(body: TeachingPlanIn, ctx=Depends(auth), s=Depends(db)):
    if ctx.get("office_n") not in LEADERSHIP and ctx.get("office_n") not in {11, 12, 13, 14}: raise HTTPException(403, "Teaching plan access denied")
    section = s.query(D.Section).filter(D.Section.id == body.section_id, D.Section.tenant_id == TENANT).first()
    if not section: raise HTTPException(404, "Section not found")
    row = D.TeachingPlan(id=uid(), tenant_id=TENANT, section_id=body.section_id, term=body.term, objectives=body.objectives, created_by=ctx["sub"])
    s.add(row); audit_mutation(s, ctx, "delivery.teaching_plan.create", f"teaching_plan:{row.id}", "", "draft", "Teaching plan created", row.version); s.commit()
    return {"plan": {"id": row.id, "section_id": row.section_id, "term": row.term, "status": row.status, "version": row.version}}


@router.post("/delivery/plans/{plan_id}/progress")
def add_syllabus_progress(plan_id: str, body: ProgressIn, ctx=Depends(auth), s=Depends(db)):
    plan = s.query(D.TeachingPlan).filter(D.TeachingPlan.id == plan_id, D.TeachingPlan.tenant_id == TENANT).first()
    if not plan: raise HTTPException(404, "Teaching plan not found")
    row = D.SyllabusProgress(id=uid(), tenant_id=TENANT, teaching_plan_id=plan_id, topic=body.topic, planned_date=date.fromisoformat(body.planned_date) if body.planned_date else None, completed_date=date.fromisoformat(body.completed_date) if body.completed_date else None, status=body.status, evidence_document_ids=json.dumps(body.evidence_document_ids))
    s.add(row); audit_mutation(s, ctx, "delivery.syllabus.progress", f"syllabus_progress:{row.id}", "", row.status, body.topic); s.commit()
    return {"progress": {"id": row.id, "topic": row.topic, "status": row.status, "evidence_document_ids": body.evidence_document_ids}}


@router.post("/delivery/milestones")
def create_milestone(body: MilestoneIn, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    row = D.AcademicMilestone(id=uid(), tenant_id=TENANT, term=body.term, title=body.title, due_at=datetime.fromisoformat(body.due_at), owner_id=body.owner_id)
    s.add(row); audit_mutation(s, ctx, "delivery.milestone.create", f"milestone:{row.id}", "", "planned", body.title); s.commit()
    return {"milestone": {"id": row.id, "term": row.term, "title": row.title, "status": row.status, "due_at": row.due_at.isoformat()}}


@router.post("/delivery/completions")
def update_course_completion(body: CompletionIn, ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    section = s.query(D.Section).filter(D.Section.id == body.section_id, D.Section.tenant_id == TENANT).first()
    if not section: raise HTTPException(404, "Section not found")
    row = s.query(D.CourseCompletion).filter(D.CourseCompletion.section_id == body.section_id, D.CourseCompletion.term == body.term, D.CourseCompletion.tenant_id == TENANT).first()
    if not row: row = D.CourseCompletion(id=uid(), tenant_id=TENANT, section_id=body.section_id, term=body.term); s.add(row)
    row.completion_pct = body.completion_pct; row.status = "completed" if body.completion_pct == 100 else "in_progress"; row.verified_by = ctx["sub"]; row.updated_at = datetime.utcnow()
    audit_mutation(s, ctx, "delivery.course_completion.update", f"course_completion:{row.id}", "", row.status, "Course completion updated"); s.commit()
    return {"completion": {"id": row.id, "section_id": row.section_id, "term": row.term, "completion_pct": row.completion_pct, "status": row.status}}


@router.post("/delivery/exceptions")
def create_delivery_exception(body: DeliveryExceptionIn, ctx=Depends(auth), s=Depends(db)):
    if ctx.get("office_n") not in LEADERSHIP and ctx.get("office_n") not in {11, 12, 13, 14}: raise HTTPException(403, "Delivery exception access denied")
    row = D.DeliveryException(id=uid(), tenant_id=TENANT, section_id=body.section_id or None, kind=body.kind, description=body.description, owner_id=body.owner_id, created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    s.add(row); audit_mutation(s, ctx, "delivery.exception.create", f"delivery_exception:{row.id}", "", "OPEN", body.description); s.commit()
    return {"exception": {"id": row.id, "state": row.state, "status_version": row.status_version, "owner_id": row.owner_id}}


@router.get("/delivery/monitoring")
def delivery_monitoring(term: str = "", ctx=Depends(auth), s=Depends(db)):
    leadership(ctx)
    completions = s.query(D.CourseCompletion).filter(D.CourseCompletion.tenant_id == TENANT, *([D.CourseCompletion.term == term] if term else [])).all()
    exceptions = s.query(D.DeliveryException).filter(D.DeliveryException.tenant_id == TENANT, D.DeliveryException.state != "CLOSED").all()
    return {"term": term, "course_completions": [{"section_id": row.section_id, "completion_pct": row.completion_pct, "status": row.status} for row in completions], "open_exceptions": [{"id": row.id, "kind": row.kind, "state": row.state, "owner_id": row.owner_id} for row in exceptions], "actionable_exceptions": len(exceptions)}
