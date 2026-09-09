# -*- coding: utf-8 -*-
"""Faculty/teaching administrative APIs ported from the local development branch."""
import os
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, desc, func, or_

from core import db, auth, uid, write_audit, notify, active_delegation_for
from database import office, TENANT, slug
from authority import authorize, ALLOW
from matrices import rbac_for, scope_for, approval_limit_for, APPROVAL_LIMITS
from capabilities import (modules_for_office, module_meta, MODULE_ACTIONS,
                           MODULES, action_allowed_for_office)
import domain_models as D
from teaching import (active_allocations_for_faculty, active_allocation_for_section,
                      faculty_active_sections, faculty_owns_section, faculty_workload,
                      class_session_for_timetable, sync_section_faculty,
                      timetable_conflicts)
from models import User, Person, OrgScope, WorkflowInstance, Notification, Approval
from domain_api import _can_manage_section_for_assessments, _section_or_404

router = APIRouter(prefix="/api")

CORRECTION_ACTIVE = {"submitted", "under_review", "returned"}
CORRECTION_STATUSES = {"present", "absent", "late", "excused"}
LEAVE_ACTIVE_STATUSES = {"submitted", "resubmitted", "under_review", "approved", "pending"}
LEAVE_EDITABLE_STATUSES = {"draft", "returned"}
LEAVE_STAGE_NAMES = {1: "HOD", 2: "Vice Principal", 3: "Principal"}

router = APIRouter(prefix="/api")

# Which module actions are monetary approvals (limit-checked & escalatable).
MONETARY = {("finance", "waive"): ("fee_waiver", "Vice-Chancellor"),
            ("finance", "approve_budget"): ("purchase_request", "CFO"),
            ("procurement", "approve"): ("purchase_request", "CFO")}


# --------------------------------------------------------------------------- #
#  Authority gate for a module action                                         #
# --------------------------------------------------------------------------- #
def gate(s, ctx, module: str, action: str, amount=None):
    """Return the Decision for (module, action); raise 403 if not ALLOW/ESCALATE."""
    verb = MODULE_ACTIONS.get(module, {}).get(action, "view")
    o = office(ctx["office_n"])
    rbac = rbac_for(ctx["office_n"], o["level"], verb)
    # Office-level reservation of sensitive actions (Document Â§9 invariants, Â§10).
    if action != "view" and not action_allowed_for_office(module, action, ctx["office_n"]):
        from authority import Decision, DENY
        return Decision(DENY, f"This office is not authorized to perform '{action}' in {module}", rbac), verb
    approval_limit = None
    escalate_to = None
    if amount is not None and (module, action) in MONETARY:
        proc, esc = MONETARY[(module, action)]
        escalate_to = esc
        scope_level = ctx.get("scope_level", "individual")
        if proc:
            approval_limit = approval_limit_for(scope_level, proc)
    dec = authorize(ctx=ctx, action=verb, resource=module, rbac_authority=rbac,
                    amount=amount, approval_limit=approval_limit,
                    active_delegation=active_delegation_for(s, ctx["sub"]),
                    target_scope_level=ctx.get("scope_level", "individual"),
                    escalate_to=escalate_to)
    return dec, verb


def can(s, ctx, module: str, action: str) -> bool:
    verb = MODULE_ACTIONS.get(module, {}).get(action, "view")
    o = office(ctx["office_n"])
    if action != "view" and not action_allowed_for_office(module, action, ctx["office_n"]):
        return False
    return rbac_for(ctx["office_n"], o["level"], verb) not in ("Not Allowed",)


def require(dec):
    if dec.outcome not in ("ALLOW", "ESCALATE"):
        raise HTTPException(403, dec.reason)


def actor_name(s, ctx):
    u = s.query(User).get(ctx["sub"])
    if not u:
        return ctx["sub"]
    p = s.query(Person).get(u.person_id)
    return p.name if p else u.username


def _staff_profile(s, ctx):
    return s.query(D.StaffMember).filter(D.StaffMember.user_id == ctx["sub"]).first()


def _active_faculty_assignments(s, ctx):
    """Only effective functional assignments may unlock faculty portal features."""
    staff = _staff_profile(s, ctx)
    if not staff:
        return []
    now = datetime.utcnow()
    return (s.query(D.FacultyFunctionalAssignment)
            .filter(D.FacultyFunctionalAssignment.faculty_id == staff.id,
                    D.FacultyFunctionalAssignment.status == "active",
                    D.FacultyFunctionalAssignment.valid_from <= now,
                    or_(D.FacultyFunctionalAssignment.valid_to == None,
                        D.FacultyFunctionalAssignment.valid_to >= now))
            .all())


def _faculty_feature_flags(s, ctx):
    assignments = _active_faculty_assignments(s, ctx)
    roles = {row.role_key.lower() for row in assignments}
    permissions = {row.permission_key.lower() for row in assignments if row.permission_key}
    staff = _staff_profile(s, ctx)
    advisor = bool(staff and s.query(D.MentorAssignment).filter(
        D.MentorAssignment.faculty_id == staff.id,
        D.MentorAssignment.status == "active",
    ).count())
    research = bool(roles & {"research_faculty", "pi", "principal_investigator", "co_pi", "research_supervisor"})
    return {
        "course_coordination": "course_coordinator" in roles,
        "advisees": advisor,
        "academic_risk": advisor,
        "course_registrations": advisor and "advisor_registration_review" in permissions,
        "research": research,
    }
def _allocation_payload(s, row):
    section = s.query(D.Section).get(row.section_id)
    course = s.query(D.Course).get(row.course_id)
    faculty = s.query(D.StaffMember).get(row.faculty_id)
    return {
        "id": row.id, "faculty_id": row.faculty_id, "faculty": faculty.name if faculty else "",
        "course_id": row.course_id, "course_code": course.code if course else "",
        "course_title": course.title if course else "", "section_id": row.section_id,
        "section": section.section_code if section else "", "term": row.term,
        "academic_year": row.academic_year, "allocation_type": row.allocation_type,
        "lecture_hours": row.lecture_hours, "lab_hours": row.lab_hours,
        "tutorial_hours": row.tutorial_hours, "workload_units": row.workload_units,
        "effective_from": row.effective_from.isoformat() if row.effective_from else "",
        "effective_to": row.effective_to.isoformat() if row.effective_to else "",
        "status": row.status, "is_coordinator": row.is_coordinator,
    }


def _can_manage_allocation(s, ctx, section):
    staff = _staff_profile(s, ctx)
    return bool(ctx["office_n"] in {6, 17} or (ctx["office_n"] == 10 and staff and staff.dept_id == section.dept_id))


class TeachingAllocationIn(BaseModel):
    faculty_id: str
    course_id: str
    section_id: str
    academic_year: str = ""
    term: str = ""
    allocation_type: str = "primary"
    lecture_hours: float = 0
    lab_hours: float = 0
    tutorial_hours: float = 0
    workload_units: float = 0
    effective_from: str = ""
    effective_to: str = ""
    is_coordinator: bool = False


class TeachingAllocationUpdate(BaseModel):
    faculty_id: str
    allocation_type: str = "primary"
    lecture_hours: float = 0
    lab_hours: float = 0
    tutorial_hours: float = 0
    workload_units: float = 0
    effective_from: str = ""
    effective_to: str = ""
    is_coordinator: bool = False


@router.get("/academics/teaching-allocations")
def list_teaching_allocations(faculty_id: str = "", ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    staff = _staff_profile(s, ctx)
    target = faculty_id or (staff.id if ctx["office_n"] in {11, 12, 13, 14} and staff else "")
    rows = s.query(D.TeachingAllocation).order_by(D.TeachingAllocation.updated_at.desc()).all()
    if target:
        rows = [row for row in rows if row.faculty_id == target]
    elif ctx["office_n"] == 10 and staff:
        rows = [row for row in rows if (s.query(D.Section).get(row.section_id) or D.Section(dept_id="")).dept_id == staff.dept_id]
    return {"allocations": [_allocation_payload(s, row) for row in rows],
            "workload": faculty_workload(s, target) if target else None}


@router.get("/academics/teaching-allocation-candidates")
def teaching_allocation_candidates(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "assign_faculty")[0])
    staff = _staff_profile(s, ctx)
    if ctx["office_n"] not in {6, 10, 17}:
        raise HTTPException(403, "Only academic allocation offices may view allocation candidates")
    sections = s.query(D.Section).all()
    faculty = s.query(D.StaffMember).filter(D.StaffMember.status == "active").all()
    if ctx["office_n"] == 10 and staff:
        sections = [row for row in sections if row.dept_id == staff.dept_id]
        faculty = [row for row in faculty if row.dept_id == staff.dept_id]
    return {"sections": [{"id": row.id, "course_id": row.course_id, "section": row.section_code, "term": row.term} for row in sections],
            "faculty": [{"id": row.id, "name": row.name, "workload": faculty_workload(s, row.id)} for row in faculty]}


@router.post("/academics/teaching-allocations")
def create_teaching_allocation(body: TeachingAllocationIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "assign_faculty")
    require(dec)
    section = _section_or_404(s, body.section_id)
    if not _can_manage_allocation(s, ctx, section):
        raise HTTPException(403, "You are not authorized to allocate this section")
    if section.course_id != body.course_id:
        raise HTTPException(422, "Allocation course must match the selected section")
    faculty = s.query(D.StaffMember).get(body.faculty_id)
    if not faculty or faculty.status != "active" or faculty.dept_id != section.dept_id:
        raise HTTPException(422, "Choose an active faculty member from the section department")
    row = D.TeachingAllocation(
        id=uid(), tenant_id=TENANT, faculty_id=faculty.id, course_id=section.course_id,
        section_id=section.id, academic_year=body.academic_year or "2025-2026",
        term=body.term or section.term, allocation_type=body.allocation_type or "primary",
        lecture_hours=max(0, body.lecture_hours), lab_hours=max(0, body.lab_hours),
        tutorial_hours=max(0, body.tutorial_hours),
        workload_units=max(0, body.workload_units or body.lecture_hours + body.lab_hours + body.tutorial_hours),
        assigned_by=actor_name(s, ctx),
        effective_from=date.fromisoformat(body.effective_from) if body.effective_from else date.today(),
        effective_to=date.fromisoformat(body.effective_to) if body.effective_to else None,
        status="pending", is_coordinator=body.is_coordinator,
    )
    s.add(row); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "allocation.create", f"allocation:{row.id}", "", "pending", "Teaching allocation created")
    return {"allocation": _allocation_payload(s, row), "decision": dec.as_dict()}


@router.put("/academics/teaching-allocations/{allocation_id}")
def update_teaching_allocation(allocation_id: str, body: TeachingAllocationUpdate, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "assign_faculty"); require(dec)
    row = s.query(D.TeachingAllocation).get(allocation_id)
    if not row: raise HTTPException(404, "Teaching allocation not found")
    section = _section_or_404(s, row.section_id)
    if not _can_manage_allocation(s, ctx, section): raise HTTPException(403, "You are not authorized to modify this allocation")
    if row.status in {"ended", "rejected"}: raise HTTPException(409, "This allocation can no longer be edited")
    faculty = s.query(D.StaffMember).get(body.faculty_id)
    if not faculty or faculty.status != "active" or faculty.dept_id != section.dept_id: raise HTTPException(422, "Choose an active faculty member from the section department")
    if row.status == "active" and faculty.id != row.faculty_id:
        for entry in s.query(D.TimetableEntry).filter(D.TimetableEntry.section_id == section.id, D.TimetableEntry.status == "active").all():
            if timetable_conflicts(s, faculty.id, entry.day_of_week, entry.start_time, entry.end_time, section.id):
                raise HTTPException(409, "Faculty has an overlapping active timetable entry")
    row.faculty_id = faculty.id; row.allocation_type = body.allocation_type or row.allocation_type
    row.lecture_hours = max(0, body.lecture_hours); row.lab_hours = max(0, body.lab_hours); row.tutorial_hours = max(0, body.tutorial_hours)
    row.workload_units = max(0, body.workload_units or row.lecture_hours + row.lab_hours + row.tutorial_hours)
    row.effective_from = date.fromisoformat(body.effective_from) if body.effective_from else row.effective_from
    row.effective_to = date.fromisoformat(body.effective_to) if body.effective_to else None; row.is_coordinator = body.is_coordinator; row.updated_at = datetime.utcnow()
    s.commit(); sync_section_faculty(s, section.id); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "allocation.update", f"allocation:{row.id}", "", row.status, "Teaching allocation updated")
    return {"allocation": _allocation_payload(s, row), "decision": dec.as_dict()}


@router.post("/academics/teaching-allocations/{allocation_id}/activate")
def activate_teaching_allocation(allocation_id: str, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "assign_faculty"); require(dec)
    row = s.query(D.TeachingAllocation).get(allocation_id)
    if not row: raise HTTPException(404, "Teaching allocation not found")
    section = _section_or_404(s, row.section_id)
    if not _can_manage_allocation(s, ctx, section): raise HTTPException(403, "You are not authorized to activate this allocation")
    for entry in s.query(D.TimetableEntry).filter(D.TimetableEntry.section_id == section.id, D.TimetableEntry.status == "active").all():
        if timetable_conflicts(s, row.faculty_id, entry.day_of_week, entry.start_time, entry.end_time, section.id):
            raise HTTPException(409, "Faculty has an overlapping active timetable entry")
    for other in s.query(D.TeachingAllocation).filter(D.TeachingAllocation.section_id == section.id, D.TeachingAllocation.status == "active").all():
        other.status = "ended"; other.effective_to = date.today(); other.updated_at = datetime.utcnow()
    row.status = "active"; row.effective_from = row.effective_from or date.today(); row.updated_at = datetime.utcnow()
    s.flush(); sync_section_faculty(s, section.id); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "allocation.activate", f"allocation:{row.id}", "pending", "active", "Teaching allocation activated")
    return {"allocation": _allocation_payload(s, row), "decision": dec.as_dict()}


@router.post("/academics/teaching-allocations/{allocation_id}/end")
def end_teaching_allocation(allocation_id: str, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "assign_faculty"); require(dec)
    row = s.query(D.TeachingAllocation).get(allocation_id)
    if not row: raise HTTPException(404, "Teaching allocation not found")
    section = _section_or_404(s, row.section_id)
    if not _can_manage_allocation(s, ctx, section): raise HTTPException(403, "You are not authorized to end this allocation")
    row.status = "ended"; row.effective_to = date.today(); row.updated_at = datetime.utcnow(); s.flush(); sync_section_faculty(s, section.id); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "allocation.end", f"allocation:{row.id}", "active", "ended", "Teaching allocation ended")
    return {"allocation": _allocation_payload(s, row), "decision": dec.as_dict()}
class FacultyAssignmentIn(BaseModel):
    section_id: str
    title: str
    instructions: str = ""
    max_marks: float
    due_at: str
    allow_late: bool = True
    action: str = "draft"  # draft / publish / close


class AssignmentEvaluationIn(BaseModel):
    action: str  # evaluate / return
    marks_awarded: float | None = None
    feedback: str = ""
    internal_comment: str = ""


def _assignment_counts(s, assignment_id: str, enrolled_ids: list[str]):
    latest = {}
    for row in s.query(D.AssignmentSubmission).filter(D.AssignmentSubmission.assignment_id == assignment_id).order_by(D.AssignmentSubmission.attempt_no.desc()).all():
        latest.setdefault(row.student_id, row)
    submissions = list(latest.values())
    evaluated = sum(row.status == "evaluated" for row in submissions)
    late = sum(row.is_late for row in submissions)
    return {"enrolled": len(enrolled_ids), "submitted": len(submissions), "missing": max(0, len(enrolled_ids) - len(submissions)), "late": late, "evaluated": evaluated}


def _faculty_assignment_payload(s, assignment, section=None):
    section = section or _section_or_404(s, assignment.section_id)
    course = s.query(D.Course).get(section.course_id)
    enrolled = [row.student_id for row in s.query(D.Enrollment).filter(D.Enrollment.section_id == section.id, D.Enrollment.status == "enrolled").all()]
    return {"id": assignment.id, "section_id": section.id, "course_code": course.code if course else "", "course_title": course.title if course else "",
            "section": section.section_code, "title": assignment.title, "instructions": assignment.description or "", "max_marks": assignment.max_marks,
            "due_at": assignment.due_at.isoformat() if assignment.due_at else "", "allow_late": bool(assignment.allow_late), "status": assignment.status,
            "reference_url": assignment.reference_url or "", "published_at": assignment.published_at.isoformat() if assignment.published_at else "", **_assignment_counts(s, assignment.id, enrolled)}


def _faculty_assignment_or_403(s, ctx, assignment_id):
    assignment = s.query(D.Assignment).get(assignment_id)
    if not assignment: raise HTTPException(404, "Assignment not found")
    section = _section_or_404(s, assignment.section_id)
    staff = _staff_profile(s, ctx)
    if not staff or ctx["office_n"] not in {11, 12, 13, 14} or not faculty_owns_section(s, staff.id, section.id):
        raise HTTPException(403, "You can manage assignments only for your active teaching allocations")
    return assignment, section, staff


@router.get("/faculty/assignments")
def faculty_assignments(ctx=Depends(auth), s=Depends(db)):
    staff = _staff_profile(s, ctx)
    if not staff or ctx["office_n"] not in {11, 12, 13, 14}: raise HTTPException(403, "Professor access required")
    section_ids = [row.id for row in faculty_active_sections(s, staff.id)]
    rows = s.query(D.Assignment).filter(D.Assignment.section_id.in_(section_ids) if section_ids else False).order_by(desc(D.Assignment.updated_at)).all()
    return {"assignments": [_faculty_assignment_payload(s, row) for row in rows]}


@router.post("/faculty/assignments")
def create_faculty_assignment(body: FacultyAssignmentIn, ctx=Depends(auth), s=Depends(db)):
    section = _section_or_404(s, body.section_id); staff = _staff_profile(s, ctx)
    if not staff or ctx["office_n"] not in {11, 12, 13, 14} or not faculty_owns_section(s, staff.id, section.id): raise HTTPException(403, "You can create assignments only for active assigned sections")
    if not body.title.strip() or body.max_marks <= 0 or not body.due_at: raise HTTPException(422, "Title, maximum marks, and due date are required")
    try: due_at = datetime.fromisoformat(body.due_at)
    except ValueError: raise HTTPException(422, "Due date must be ISO date-time")
    if body.action not in {"draft", "publish"}: raise HTTPException(422, "Invalid assignment action")
    allocation = active_allocation_for_section(s, section.id)
    now = datetime.utcnow(); who = actor_name(s, ctx)
    row = D.Assignment(id=uid(), tenant_id=TENANT, section_id=section.id, title=body.title.strip(), description=body.instructions.strip(), due_at=due_at,
        status="published" if body.action == "publish" else "draft", max_marks=body.max_marks, allow_late=body.allow_late, faculty_id=staff.id,
        teaching_allocation_id=allocation.id if allocation else None, created_by=who, updated_by=who, published_at=now if body.action == "publish" else None, published_by=who if body.action == "publish" else "")
    s.add(row); s.commit(); write_audit(s, ctx["sub"], who, ctx["office_n"], "assignment.publish" if row.status == "published" else "assignment.create", f"assignment:{row.id}", "", row.status, row.title)
    return {"assignment": _faculty_assignment_payload(s, row)}


@router.put("/faculty/assignments/{assignment_id}")
def update_faculty_assignment(assignment_id: str, body: FacultyAssignmentIn, ctx=Depends(auth), s=Depends(db)):
    row, section, staff = _faculty_assignment_or_403(s, ctx, assignment_id)
    if body.section_id != section.id: raise HTTPException(409, "Assignment section cannot be changed")
    submitted = s.query(D.AssignmentSubmission).filter(D.AssignmentSubmission.assignment_id == row.id).count()
    if submitted and (body.max_marks != row.max_marks or body.due_at != (row.due_at.isoformat() if row.due_at else "")):
        raise HTTPException(409, "Maximum marks and due date cannot change after submissions exist")
    if row.status == "closed": raise HTTPException(409, "Closed assignments cannot be edited")
    if body.action not in {"draft", "publish", "close"}: raise HTTPException(422, "Invalid assignment action")
    if body.action == "draft" and row.status == "published": raise HTTPException(409, "Published assignments cannot return to draft")
    if not body.title.strip() or body.max_marks <= 0 or not body.due_at: raise HTTPException(422, "Title, maximum marks, and due date are required")
    try: due_at = datetime.fromisoformat(body.due_at)
    except ValueError: raise HTTPException(422, "Due date must be ISO date-time")
    now = datetime.utcnow(); who = actor_name(s, ctx); previous = row.status
    row.title = body.title.strip(); row.description = body.instructions.strip(); row.max_marks = body.max_marks; row.due_at = due_at; row.allow_late = body.allow_late; row.updated_at = now; row.updated_by = who
    if body.action == "publish" and row.status == "draft": row.status = "published"; row.published_at = now; row.published_by = who
    if body.action == "close": row.status = "closed"; row.closed_at = now; row.closed_by = who
    s.commit(); write_audit(s, ctx["sub"], who, ctx["office_n"], "assignment.update", f"assignment:{row.id}", previous, row.status, row.title)
    return {"assignment": _faculty_assignment_payload(s, row)}


@router.get("/faculty/assignments/{assignment_id}/submissions")
def faculty_assignment_submissions(assignment_id: str, ctx=Depends(auth), s=Depends(db)):
    assignment, section, _ = _faculty_assignment_or_403(s, ctx, assignment_id)
    latest = {}; history = {}
    for submission in s.query(D.AssignmentSubmission).filter(D.AssignmentSubmission.assignment_id == assignment.id).order_by(D.AssignmentSubmission.attempt_no.desc()).all():
        history.setdefault(submission.student_id, []).append(submission); latest.setdefault(submission.student_id, submission)
    students = {row.id: row for row in s.query(D.Student).all()}
    roster = []
    for enrollment in s.query(D.Enrollment).filter(D.Enrollment.section_id == section.id, D.Enrollment.status == "enrolled").all():
        student = students.get(enrollment.student_id); submission = latest.get(enrollment.student_id)
        evaluation = s.query(D.AssignmentEvaluation).filter(D.AssignmentEvaluation.submission_id == submission.id).first() if submission else None
        roster.append({"student_id": enrollment.student_id, "roll_no": student.roll_no if student else "", "student": student.name if student else "", "submission_id": submission.id if submission else "", "submitted_at": submission.submitted_at.isoformat() if submission else "", "status": submission.status if submission else "missing", "late": bool(submission and submission.is_late), "attempt_no": submission.attempt_no if submission else 0, "submission_text": submission.submission_text if submission else "", "file_name": submission.file_name if submission else "", "marks_awarded": evaluation.marks_awarded if evaluation else None, "feedback": evaluation.feedback if evaluation else "", "history_count": len(history.get(enrollment.student_id, []))})
    return {"assignment": _faculty_assignment_payload(s, assignment, section), "roster": roster}


@router.post("/faculty/assignment-submissions/{submission_id}/evaluate")
def evaluate_assignment_submission(submission_id: str, body: AssignmentEvaluationIn, ctx=Depends(auth), s=Depends(db)):
    submission = s.query(D.AssignmentSubmission).get(submission_id)
    if not submission: raise HTTPException(404, "Submission not found")
    assignment, _, staff = _faculty_assignment_or_403(s, ctx, submission.assignment_id)
    if body.action not in {"evaluate", "return"}: raise HTTPException(422, "Invalid evaluation action")
    if body.action == "evaluate" and (body.marks_awarded is None or body.marks_awarded < 0 or body.marks_awarded > assignment.max_marks): raise HTTPException(422, f"Marks must be between 0 and {assignment.max_marks}")
    if body.action == "return" and not body.feedback.strip(): raise HTTPException(422, "Feedback is required when returning a submission")
    evaluation = s.query(D.AssignmentEvaluation).filter(D.AssignmentEvaluation.submission_id == submission.id).first()
    now = datetime.utcnow(); who = actor_name(s, ctx)
    if not evaluation: evaluation = D.AssignmentEvaluation(id=uid(), tenant_id=TENANT, submission_id=submission.id, evaluator_id=staff.id); s.add(evaluation)
    evaluation.marks_awarded = body.marks_awarded if body.action == "evaluate" else None; evaluation.feedback = body.feedback.strip(); evaluation.internal_comment = body.internal_comment.strip(); evaluation.status = "evaluated" if body.action == "evaluate" else "returned"; evaluation.evaluated_at = now; evaluation.updated_at = now
    submission.status = "evaluated" if body.action == "evaluate" else "returned"; submission.returned_at = now if body.action == "return" else None; submission.updated_at = now
    s.commit(); write_audit(s, ctx["sub"], who, ctx["office_n"], "assignment.evaluate" if body.action == "evaluate" else "assignment.return", f"assignment_submission:{submission.id}", "", submission.status, body.feedback.strip())
    return {"submission_id": submission.id, "status": submission.status, "marks_awarded": evaluation.marks_awarded, "feedback": evaluation.feedback}
def _faculty_or_403(s, ctx):
    staff = _staff_profile(s, ctx)
    if not staff:
        raise HTTPException(403, "A linked faculty profile is required")
    return staff


def _session_or_404(s, session_id: str):
    row = s.query(D.ClassSession).get(session_id)
    if not row:
        raise HTTPException(404, "Class session not found")
    return row


def _checkin_window_open(session: D.ClassSession, now: datetime):
    early = int(os.environ.get("ICMS_SESSION_CHECKIN_EARLY_MINUTES", "60"))
    late = int(os.environ.get("ICMS_SESSION_CHECKIN_LATE_MINUTES", "240"))
    if not session.scheduled_start or not session.scheduled_end:
        return True
    return session.scheduled_start - timedelta(minutes=early) <= now <= session.scheduled_end + timedelta(minutes=late)


def _session_payload(s, row):
    section = s.query(D.Section).get(row.section_id)
    course = s.query(D.Course).get(section.course_id) if section else None
    return {"id": row.id, "section_id": row.section_id, "section": section.section_code if section else "",
            "course_code": course.code if course else "", "course_title": course.title if course else "",
            "session_date": row.session_date.isoformat(), "scheduled_start": row.scheduled_start.isoformat() if row.scheduled_start else "",
            "scheduled_end": row.scheduled_end.isoformat() if row.scheduled_end else "", "room": row.room,
            "status": row.status, "checked_in_at": row.checked_in_at.isoformat() if row.checked_in_at else ""}


@router.get("/faculty/class-sessions")
def faculty_class_sessions(on_date: str = "", ctx=Depends(auth), s=Depends(db)):
    staff = _faculty_or_403(s, ctx)
    target = date.fromisoformat(on_date) if on_date else date.today()
    allocations = {row.id: row for row in active_allocations_for_faculty(s, staff.id, target)}
    sessions = []
    for entry in (s.query(D.TimetableEntry)
                  .filter(D.TimetableEntry.day_of_week == target.weekday(), D.TimetableEntry.status == "active")
                  .all()):
        allocation = active_allocation_for_section(s, entry.section_id, target)
        if allocation and allocation.id in allocations:
            sessions.append(class_session_for_timetable(s, entry, target, allocation))
    s.commit()
    return {"sessions": [_session_payload(s, row) for row in sessions if row]}


@router.post("/faculty/class-sessions/{session_id}/check-in")
def check_in_class_session(session_id: str, ctx=Depends(auth), s=Depends(db)):
    staff = _faculty_or_403(s, ctx)
    session = _session_or_404(s, session_id)
    if session.faculty_id != staff.id or not faculty_owns_section(s, staff.id, session.section_id, session.session_date):
        raise HTTPException(403, "You are not assigned to this class session")
    if session.status in {"attendance_finalized", "completed", "cancelled"}:
        raise HTTPException(409, "This session can no longer be checked in")
    now = datetime.utcnow()
    if not _checkin_window_open(session, now):
        raise HTTPException(422, "Session check-in is outside the allowed time window")
    if session.checked_in_at:
        return {"session": _session_payload(s, session), "already_checked_in": True}
    session.checked_in_at = now; session.checked_in_by = staff.id; session.actual_start = now; session.status = "checked_in"; session.updated_at = now
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "class_session.check_in", f"session:{session.id}", "scheduled", "checked_in", "Faculty checked into class session")
    return {"session": _session_payload(s, session), "already_checked_in": False}


@router.post("/faculty/class-sessions/{session_id}/finalize-attendance")
def finalize_class_session_attendance(session_id: str, ctx=Depends(auth), s=Depends(db)):
    staff = _faculty_or_403(s, ctx); session = _session_or_404(s, session_id)
    if session.faculty_id != staff.id or not faculty_owns_section(s, staff.id, session.section_id, session.session_date):
        raise HTTPException(403, "You are not assigned to this class session")
    if not session.checked_in_at: raise HTTPException(409, "Check in to this class session before finalizing attendance")
    if session.status == "attendance_finalized": return {"session": _session_payload(s, session), "already_finalized": True}
    roster_ids = {row.student_id for row in s.query(D.Enrollment).filter(D.Enrollment.section_id == session.section_id, D.Enrollment.status == "enrolled").all()}
    marked_ids = {row.student_id for row in s.query(D.AttendanceRecord).filter(D.AttendanceRecord.class_session_id == session.id).all()}
    if not roster_ids or marked_ids != roster_ids: raise HTTPException(422, "Every active student in the roster must have attendance before finalization")
    now = datetime.utcnow()
    s.query(D.AttendanceRecord).filter(D.AttendanceRecord.class_session_id == session.id).update({"finalized_at": now}, synchronize_session=False)
    session.status = "attendance_finalized"; session.finalized_at = now; session.finalized_by = staff.id; session.actual_end = now; session.updated_at = now
    s.commit(); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "attendance.finalize", f"session:{session.id}", "checked_in", "attendance_finalized", "Attendance finalized")
    return {"session": _session_payload(s, session), "already_finalized": False}
def _correction_reviewer(s, request, stage):
    section = _section_or_404(s, request.section_id)
    if stage == 1:
        coordinator = (s.query(D.FacultyFunctionalAssignment)
                       .filter(D.FacultyFunctionalAssignment.role_key == "course_coordinator",
                               D.FacultyFunctionalAssignment.scope_type == "section",
                               D.FacultyFunctionalAssignment.scope_ref == section.id,
                               D.FacultyFunctionalAssignment.status == "active")
                       .first())
        staff = s.query(D.StaffMember).get(coordinator.faculty_id) if coordinator else None
        return staff.user_id if staff else ""
    if stage == 2:
        department = s.query(D.Department).get(section.dept_id)
        staff = s.query(D.StaffMember).get(department.hod_person_id) if department else None
        return staff.user_id if staff else ""
    if stage == 3:
        user = s.query(User).filter(User.office_n == 5, User.status == "active").first()
        return user.id if user else ""
    return ""


def _correction_payload(s, row):
    record = s.query(D.AttendanceRecord).get(row.attendance_record_id)
    session = s.query(D.ClassSession).get(row.class_session_id)
    section = s.query(D.Section).get(row.section_id)
    student = s.query(D.Student).get(row.student_id)
    course = s.query(D.Course).get(section.course_id) if section else None
    wf = s.query(WorkflowInstance).get(row.workflow_instance_id)
    approvals = s.query(Approval).filter(Approval.workflow_id == row.workflow_instance_id).order_by(Approval.created_at).all()
    return {"id": row.id, "attendance_record_id": row.attendance_record_id, "workflow_instance_id": row.workflow_instance_id,
            "status": row.status, "original_status": row.original_status, "requested_status": row.requested_status,
            "reason": row.reason, "student": student.name if student else "", "student_id": row.student_id,
            "course_code": course.code if course else "", "course_title": course.title if course else "",
            "section": section.section_code if section else "", "section_id": row.section_id,
            "session_date": session.session_date.isoformat() if session else "", "session_time": session.scheduled_start.isoformat() if session and session.scheduled_start else "",
            "current_stage": wf.current_stage if wf else 0, "workflow_state": wf.state if wf else "",
            "created_at": row.created_at.isoformat() if row.created_at else "", "applied_at": row.applied_at.isoformat() if row.applied_at else "",
            "history": [{"actor": a.actor_name, "stage": a.stage_label, "decision": a.decision, "reason": a.reason} for a in approvals],
            "record_status": record.status if record else ""}


class AttendanceCorrectionIn(BaseModel):
    attendance_record_id: str
    requested_status: str
    reason: str


class CorrectionDecisionIn(BaseModel):
    action: str
    comment: str = ""


def _validate_correction_request(s, ctx, record, requested_status, reason):
    if ctx["office_n"] not in {11, 12, 13, 14}:
        raise HTTPException(403, "Only teaching faculty may request an attendance correction")
    staff = _faculty_or_403(s, ctx)
    session = _session_or_404(s, record.class_session_id)
    if not record.finalized_at or session.status != "attendance_finalized":
        raise HTTPException(409, "Attendance must be finalized before a correction can be requested")
    if session.faculty_id != staff.id or not faculty_owns_section(s, staff.id, record.section_id, session.session_date):
        raise HTTPException(403, "You do not own this finalized class session")
    enrolled = s.query(D.Enrollment).filter(D.Enrollment.section_id == record.section_id, D.Enrollment.student_id == record.student_id, D.Enrollment.status == "enrolled").first()
    if not enrolled: raise HTTPException(422, "Student is not on the session roster")
    if requested_status.lower() not in CORRECTION_STATUSES: raise HTTPException(422, "Choose a valid attendance status")
    if requested_status.lower() == record.status: raise HTTPException(422, "Requested attendance status must differ from the current status")
    if not reason.strip(): raise HTTPException(422, "A correction reason is required")
    return session


@router.post("/attendance/corrections")
def create_attendance_correction(body: AttendanceCorrectionIn, ctx=Depends(auth), s=Depends(db)):
    record = s.query(D.AttendanceRecord).get(body.attendance_record_id)
    if not record: raise HTTPException(404, "Attendance record not found")
    session = _validate_correction_request(s, ctx, record, body.requested_status, body.reason)
    duplicate = s.query(D.AttendanceCorrectionRequest).filter(D.AttendanceCorrectionRequest.attendance_record_id == record.id,
                D.AttendanceCorrectionRequest.status.in_({"submitted", "under_review", "returned"})).first()
    if duplicate: raise HTTPException(409, "An active correction request already exists for this attendance record")
    requester = actor_name(s, ctx)
    wf = WorkflowInstance(id=uid(), tenant_id=TENANT, process_key="attendance_correction", label="Attendance correction",
        office_n=10, title=f"Attendance correction for {record.student_id}", state="submitted", initiator_id=ctx["sub"], initiator_name=requester,
        current_stage=1, scope_level=ctx.get("scope_level", "department"))
    row = D.AttendanceCorrectionRequest(id=uid(), tenant_id=TENANT, attendance_record_id=record.id, class_session_id=session.id,
        student_id=record.student_id, section_id=record.section_id, requested_by=ctx["sub"], original_status=record.status,
        requested_status=body.requested_status.lower(), reason=body.reason.strip(), workflow_instance_id=wf.id, status="submitted")
    reviewer = _correction_reviewer(s, row, 1)
    if not reviewer: raise HTTPException(409, "No Class Coordinator is configured for this section")
    # Flush the parent workflow first so PostgreSQL can satisfy the correction
    # request's workflow foreign key in this single atomic transaction.
    s.add(wf); s.flush(); s.add(row); s.commit()
    notify(s, reviewer, "Attendance correction review", f"{requester} submitted a correction request", severity="action")
    write_audit(s, ctx["sub"], requester, ctx["office_n"], "attendance.correction.submit", f"correction:{row.id}", record.status, row.requested_status, row.reason)
    return {"correction": _correction_payload(s, row)}


@router.get("/attendance/corrections")
def list_attendance_corrections(scope: str = "mine", ctx=Depends(auth), s=Depends(db)):
    rows = s.query(D.AttendanceCorrectionRequest).order_by(desc(D.AttendanceCorrectionRequest.updated_at)).all()
    if scope == "mine": rows = [row for row in rows if row.requested_by == ctx["sub"]]
    elif scope == "inbox": rows = [row for row in rows if row.status in {"submitted", "under_review"} and _correction_reviewer(s, row, (s.query(WorkflowInstance).get(row.workflow_instance_id).current_stage)) == ctx["sub"]]
    return {"corrections": [_correction_payload(s, row) for row in rows]}


@router.put("/attendance/corrections/{correction_id}")
def update_returned_correction(correction_id: str, body: AttendanceCorrectionIn, ctx=Depends(auth), s=Depends(db)):
    row = s.query(D.AttendanceCorrectionRequest).get(correction_id)
    if not row: raise HTTPException(404, "Correction request not found")
    if row.requested_by != ctx["sub"]: raise HTTPException(403, "Only the requesting professor can edit this correction")
    if row.status != "returned": raise HTTPException(409, "Only returned correction requests may be edited")
    record = s.query(D.AttendanceRecord).get(row.attendance_record_id)
    if body.attendance_record_id != record.id: raise HTTPException(422, "Attendance record cannot be changed")
    _validate_correction_request(s, ctx, record, body.requested_status, body.reason)
    row.requested_status = body.requested_status.lower(); row.reason = body.reason.strip(); row.updated_at = datetime.utcnow(); s.commit()
    return {"correction": _correction_payload(s, row)}


@router.post("/attendance/corrections/{correction_id}/resubmit")
def resubmit_attendance_correction(correction_id: str, ctx=Depends(auth), s=Depends(db)):
    row = s.query(D.AttendanceCorrectionRequest).get(correction_id)
    if not row: raise HTTPException(404, "Correction request not found")
    if row.requested_by != ctx["sub"] or row.status != "returned": raise HTTPException(409, "Only a returned request may be resubmitted")
    wf = s.query(WorkflowInstance).get(row.workflow_instance_id); wf.state = "submitted"; wf.current_stage = 1; wf.updated_at = datetime.utcnow()
    row.status = "submitted"; row.updated_at = datetime.utcnow(); s.commit()
    notify(s, _correction_reviewer(s, row, 1), "Attendance correction review", "A correction request was resubmitted", severity="action")
    return {"correction": _correction_payload(s, row)}


@router.post("/attendance/corrections/{correction_id}/decide")
def decide_attendance_correction(correction_id: str, body: CorrectionDecisionIn, ctx=Depends(auth), s=Depends(db)):
    row = s.query(D.AttendanceCorrectionRequest).get(correction_id)
    if not row: raise HTTPException(404, "Correction request not found")
    wf = s.query(WorkflowInstance).get(row.workflow_instance_id)
    if row.status not in {"submitted", "under_review"} or not wf: raise HTTPException(409, "Correction is not awaiting review")
    if _correction_reviewer(s, row, wf.current_stage) != ctx["sub"]: raise HTTPException(403, "You are not the eligible reviewer for the current correction stage")
    action = body.action.lower()
    if action not in {"approve", "return", "reject"}: raise HTTPException(422, "Choose approve, return, or reject")
    if action in {"return", "reject"} and not body.comment.strip(): raise HTTPException(422, "A comment is required when returning or rejecting a correction")
    who = actor_name(s, ctx); stage_names = {1: "Class Coordinator", 2: "HOD", 3: "Vice Principal"}
    s.add(Approval(id=uid(), tenant_id=TENANT, workflow_id=wf.id, actor_id=ctx["sub"], actor_name=who, stage=wf.current_stage,
                   stage_label=stage_names[wf.current_stage], decision=action.upper(), authority="FULL", reason=body.comment.strip()))
    before = row.status
    if action == "return": row.status = "returned"; wf.state = "returned"; notify(s, row.requested_by, "Attendance correction returned", body.comment, severity="action")
    elif action == "reject": row.status = "rejected"; wf.state = "rejected"; notify(s, row.requested_by, "Attendance correction rejected", body.comment, severity="info")
    elif wf.current_stage < 3:
        wf.current_stage += 1; wf.state = "under_review"; row.status = "under_review"; notify(s, _correction_reviewer(s, row, wf.current_stage), "Attendance correction review", "A correction request awaits your review", severity="action")
    else:
        record = s.query(D.AttendanceRecord).get(row.attendance_record_id)
        if row.status == "applied": raise HTTPException(409, "Correction was already applied")
        record.status = row.requested_status; record.present = row.requested_status in {"present", "late", "excused"}; record.version_no = (record.version_no or 0) + 1; record.updated_at = datetime.utcnow()
        row.status = "applied"; row.applied_at = datetime.utcnow(); row.applied_by = ctx["sub"]; wf.state = "approved"; wf.current_stage = 4
    row.updated_at = datetime.utcnow(); wf.updated_at = datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], who, ctx["office_n"], "attendance.correction.decide", f"correction:{row.id}", before, row.status, body.comment or f"{row.original_status} -> {row.requested_status}")
    return {"correction": _correction_payload(s, row)}
class PublishMarksIn(BaseModel):
    assessment_id: str


MARKS_EDITABLE_STATES = {"draft", "returned"}


def _marks_reviewer(s, assessment, stage):
    section = _section_or_404(s, assessment.section_id)
    if stage == 1:
        assignments = (s.query(D.FacultyFunctionalAssignment)
                       .filter(D.FacultyFunctionalAssignment.role_key == "evaluation_coordinator",
                               D.FacultyFunctionalAssignment.status == "active")
                       .all())
        for assignment in assignments:
            if assignment.scope_type == "section" and assignment.scope_ref != section.id:
                continue
            if assignment.scope_type == "department" and assignment.scope_ref != section.dept_id:
                continue
            staff = s.query(D.StaffMember).get(assignment.faculty_id)
            if staff and staff.user_id:
                return staff.user_id
        coordinator = s.query(User).filter(User.office_n == 17, User.status == "active").first()
        return coordinator.id if coordinator else ""
    if stage == 2:
        department = s.query(D.Department).get(section.dept_id)
        staff = s.query(D.StaffMember).get(department.hod_person_id) if department else None
        return staff.user_id if staff else ""
    if stage == 3:
        controller = s.query(User).filter(User.office_n == 16, User.status == "active").first()
        return controller.id if controller else ""
    return ""


def _marks_submission_payload(s, assessment):
    section = _section_or_404(s, assessment.section_id)
    course = s.query(D.Course).get(section.course_id) if section.course_id else None
    workflow = s.query(WorkflowInstance).get(assessment.workflow_instance_id) if assessment.workflow_instance_id else None
    rows = s.query(D.Mark).filter(D.Mark.assessment_id == assessment.id).all()
    enrolled = s.query(D.Enrollment).filter(D.Enrollment.section_id == section.id, D.Enrollment.status == "enrolled").count()
    approvals = s.query(Approval).filter(Approval.workflow_id == assessment.workflow_instance_id).order_by(Approval.created_at).all() if assessment.workflow_instance_id else []
    return {"assessment_id": assessment.id, "workflow_instance_id": assessment.workflow_instance_id or "",
            "assessment": assessment.name, "assessment_type": assessment.assessment_type,
            "course_code": course.code if course else "", "course_title": course.title if course else "",
            "section": section.section_code, "section_id": section.id, "max_marks": assessment.max_marks,
            "student_count": enrolled, "entered_marks": len(rows), "missing_marks": max(0, enrolled - len(rows)),
            "out_of_range": any(row.score is None or row.score < 0 or row.score > assessment.max_marks for row in rows),
            "state": assessment.marks_state or "draft", "current_stage": workflow.current_stage if workflow else 0,
            "submitted_at": assessment.marks_submitted_at.isoformat() if assessment.marks_submitted_at else "",
            "published_at": assessment.marks_published_at.isoformat() if assessment.marks_published_at else "",
            "return_comment": assessment.marks_return_comment or "", "revision": assessment.marks_revision or 1,
            "history": [{"actor": row.actor_name, "stage": row.stage_label, "decision": row.decision, "reason": row.reason} for row in approvals]}


def _validate_marks_batch(s, assessment):
    enrolled = {row.student_id for row in s.query(D.Enrollment).filter(D.Enrollment.section_id == assessment.section_id, D.Enrollment.status == "enrolled").all()}
    marks = s.query(D.Mark).filter(D.Mark.assessment_id == assessment.id).all()
    if {row.student_id for row in marks} != enrolled:
        raise HTTPException(422, "Marks are required for every enrolled student before submission")
    if any(row.score is None or row.score < 0 or row.score > assessment.max_marks for row in marks):
        raise HTTPException(422, "All marks must be within the assessment range")


def _publish_marks_from_workflow(s, assessment, ctx, who):
    now = datetime.utcnow()
    rows = s.query(D.Mark).filter(D.Mark.assessment_id == assessment.id, D.Mark.is_valid == True).all()
    for row in rows:
        row.status = "published"; row.published_at = now; row.published_by = who; row.updated_at = now
    assessment.marks_state = "published"; assessment.marks_approved_at = now; assessment.marks_published_at = now
    assessment.published = True; assessment.status = "published"; assessment.published_at = now; assessment.published_by = who
    assessment.updated_at = now; assessment.updated_by = who
    return len(rows)


@router.post("/exams/marks/submit")
def submit_marks_for_review(body: PublishMarksIn, ctx=Depends(auth), s=Depends(db)):
    assessment = s.query(D.Assessment).get(body.assessment_id)
    if not assessment: raise HTTPException(404, "Assessment not found")
    section = _section_or_404(s, assessment.section_id)
    if not _can_manage_section_for_assessments(s, ctx, section):
        raise HTTPException(403, "You cannot submit marks for this section")
    if (assessment.marks_state or "draft") not in MARKS_EDITABLE_STATES:
        raise HTTPException(409, "Marks are already submitted or published")
    _validate_marks_batch(s, assessment)
    who = actor_name(s, ctx); now = datetime.utcnow()
    workflow = s.query(WorkflowInstance).get(assessment.workflow_instance_id) if assessment.workflow_instance_id else None
    if workflow and workflow.state not in {"returned"}:
        raise HTTPException(409, "An active marks workflow already exists")
    if workflow is None:
        workflow = WorkflowInstance(id=uid(), tenant_id=TENANT, process_key="marks_submission", label="Marks submission",
            office_n=16, title=f"{assessment.name} marks for {section.section_code}", state="submitted", initiator_id=ctx["sub"], initiator_name=who,
            current_stage=1, scope_level="department")
        s.add(workflow); s.flush(); assessment.workflow_instance_id = workflow.id
    else:
        workflow.state = "submitted"; workflow.current_stage = 1; workflow.updated_at = now
    reviewer = _marks_reviewer(s, assessment, 1)
    if not reviewer: raise HTTPException(409, "No Evaluation Coordinator is configured")
    assessment.marks_state = "submitted"; assessment.marks_submitted_by = ctx["sub"]; assessment.marks_submitted_at = now
    assessment.marks_return_comment = ""; assessment.marks_revision = (assessment.marks_revision or 0) + 1
    s.query(D.Mark).filter(D.Mark.assessment_id == assessment.id).update({"status": "submitted", "updated_at": now}, synchronize_session=False)
    s.commit(); notify(s, reviewer, "Marks submission review", f"{who} submitted {assessment.name} marks", severity="action")
    write_audit(s, ctx["sub"], who, ctx["office_n"], "marks.submit", f"assessment:{assessment.id}", "draft", "submitted", assessment.name)
    return {"submission": _marks_submission_payload(s, assessment)}


class MarksDecisionIn(BaseModel):
    action: str
    comment: str = ""


@router.get("/exams/marks/submissions")
def marks_submissions(scope: str = "mine", ctx=Depends(auth), s=Depends(db)):
    rows = s.query(D.Assessment).filter(D.Assessment.workflow_instance_id.isnot(None)).order_by(desc(D.Assessment.marks_submitted_at)).all()
    out = []
    for assessment in rows:
        workflow = s.query(WorkflowInstance).get(assessment.workflow_instance_id)
        if scope == "mine" and assessment.marks_submitted_by != ctx["sub"]: continue
        if scope == "inbox" and (not workflow or assessment.marks_state not in {"submitted", "under_review"} or _marks_reviewer(s, assessment, workflow.current_stage) != ctx["sub"]): continue
        out.append(_marks_submission_payload(s, assessment))
    return {"submissions": out}


@router.post("/exams/marks/submissions/{assessment_id}/decide")
def decide_marks_submission(assessment_id: str, body: MarksDecisionIn, ctx=Depends(auth), s=Depends(db)):
    assessment = s.query(D.Assessment).get(assessment_id)
    if not assessment or not assessment.workflow_instance_id: raise HTTPException(404, "Marks submission not found")
    workflow = s.query(WorkflowInstance).get(assessment.workflow_instance_id)
    if not workflow or assessment.marks_state not in {"submitted", "under_review"}: raise HTTPException(409, "Marks are not awaiting review")
    if _marks_reviewer(s, assessment, workflow.current_stage) != ctx["sub"]: raise HTTPException(403, "You are not the eligible reviewer for this stage")
    action = body.action.lower()
    if action not in {"approve", "return", "reject"}: raise HTTPException(422, "Choose approve, return, or reject")
    if action in {"return", "reject"} and not body.comment.strip(): raise HTTPException(422, "A comment is required")
    who = actor_name(s, ctx); before = assessment.marks_state; names = {1: "Evaluation Coordinator", 2: "HOD", 3: "Exam Controller"}
    s.add(Approval(id=uid(), tenant_id=TENANT, workflow_id=workflow.id, actor_id=ctx["sub"], actor_name=who, stage=workflow.current_stage,
        stage_label=names[workflow.current_stage], decision=action.upper(), authority="FULL", reason=body.comment.strip()))
    if action == "return":
        assessment.marks_state = "returned"; assessment.marks_return_comment = body.comment.strip(); workflow.state = "returned"
        s.query(D.Mark).filter(D.Mark.assessment_id == assessment.id).update({"status": "returned"}, synchronize_session=False)
    elif action == "reject":
        assessment.marks_state = "returned"; assessment.marks_return_comment = body.comment.strip(); workflow.state = "rejected"
        s.query(D.Mark).filter(D.Mark.assessment_id == assessment.id).update({"status": "returned"}, synchronize_session=False)
    elif workflow.current_stage < 3:
        workflow.current_stage += 1; workflow.state = "under_review"; assessment.marks_state = "under_review"
        notify(s, _marks_reviewer(s, assessment, workflow.current_stage), "Marks submission review", f"{assessment.name} marks await review", severity="action")
    else:
        _publish_marks_from_workflow(s, assessment, ctx, who); workflow.current_stage = 4; workflow.state = "approved"
    workflow.updated_at = datetime.utcnow(); assessment.updated_at = datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], who, ctx["office_n"], "marks.review", f"assessment:{assessment.id}", before, assessment.marks_state, body.comment or "Approved")
    return {"submission": _marks_submission_payload(s, assessment)}
class FacultyLeaveIn(BaseModel):
    kind: str
    from_date: str
    to_date: str
    half_day: bool = False
    reason: str
    action: str = "draft"


class LeaveWorkflowDecisionIn(BaseModel):
    action: str
    comment: str = ""


def _leave_staff_or_403(s, ctx):
    if ctx["office_n"] not in {11, 12, 13, 14}:
        raise HTTPException(403, "Only teaching faculty can create leave requests")
    staff = _staff_profile(s, ctx)
    if not staff:
        raise HTTPException(403, "No faculty profile is linked to this account")
    return staff


def _leave_reviewer(s, row, stage):
    staff = s.query(D.StaffMember).get(row.staff_id)
    if stage == 1:
        department = s.query(D.Department).get(staff.dept_id) if staff else None
        hod = s.query(D.StaffMember).get(department.hod_person_id) if department else None
        return hod.user_id if hod and hod.user_id else ""
    if stage == 2:
        reviewer = s.query(User).filter(User.office_n == 5, User.status == "active").first()
        return reviewer.id if reviewer else ""
    if stage == 3:
        reviewer = s.query(User).filter(User.office_n == 4, User.status == "active").first()
        return reviewer.id if reviewer else ""
    return ""


def _leave_dates(body):
    try:
        start, end = date.fromisoformat(body.from_date), date.fromisoformat(body.to_date)
    except ValueError:
        raise HTTPException(422, "Leave dates must use YYYY-MM-DD")
    if start > end:
        raise HTTPException(422, "From date cannot be after to date")
    if body.half_day and start != end:
        raise HTTPException(422, "Half-day leave must be for a single date")
    if not (body.kind or "").strip() or not (body.reason or "").strip():
        raise HTTPException(422, "Leave type and reason are required")
    return start, end


def _leave_overlap(s, staff_id, start, end, exclude_id=""):
    query = s.query(D.LeaveRequest).filter(
        D.LeaveRequest.staff_id == staff_id,
        D.LeaveRequest.status.in_(LEAVE_ACTIVE_STATUSES),
        D.LeaveRequest.from_date <= end,
        D.LeaveRequest.to_date >= start,
    )
    if exclude_id:
        query = query.filter(D.LeaveRequest.id != exclude_id)
    return query.first()


def _leave_payload(s, row):
    staff = s.query(D.StaffMember).get(row.staff_id)
    department = s.query(D.Department).get(staff.dept_id) if staff else None
    workflow = s.query(WorkflowInstance).get(row.workflow_instance_id) if row.workflow_instance_id else None
    approvals = (s.query(Approval).filter(Approval.workflow_id == workflow.id).order_by(Approval.created_at).all()
                 if workflow else [])
    return_approval = next((item for item in reversed(approvals)
                            if item.decision.upper() == "RETURN" and (item.reason or "").strip()), None)
    reviewer_comment = return_approval.reason.strip() if return_approval else (row.returned_comment or "")
    stage = workflow.current_stage if workflow else 0
    return {
        "id": row.id, "workflow_instance_id": row.workflow_instance_id or "", "staff_id": row.staff_id,
        "staff": row.staff_name, "department": department.name if department else "",
        "kind": row.kind, "from_date": row.from_date.isoformat(), "to_date": row.to_date.isoformat(),
        "days": 0.5 if row.half_day else row.days, "half_day": bool(row.half_day), "reason": row.reason,
        "status": row.status, "current_stage": stage,
        "stage_label": LEAVE_STAGE_NAMES.get(stage, "Complete" if row.status in {"approved", "rejected", "cancelled"} else "Draft"),
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else "",
        # Keep the existing response key while making the reviewer-facing meaning explicit.
        "returned_comment": reviewer_comment, "reviewer_comment": reviewer_comment,
        "editable": row.status in LEAVE_EDITABLE_STATUSES,
        "history": [{"stage": item.stage, "stage_label": item.stage_label, "actor": item.actor_name,
                     "decision": item.decision, "reason": item.reason, "at": item.created_at.isoformat()}
                    for item in approvals],
    }


def _submit_leave(s, row, ctx, resubmission=False):
    reviewer = _leave_reviewer(s, row, 1)
    if not reviewer:
        raise HTTPException(409, "No HOD is configured for this faculty department")
    who = actor_name(s, ctx)
    if row.workflow_instance_id:
        workflow = s.query(WorkflowInstance).get(row.workflow_instance_id)
        if not workflow:
            raise HTTPException(409, "Leave workflow is unavailable")
        workflow.state = "submitted"; workflow.current_stage = 1; workflow.updated_at = datetime.utcnow()
    else:
        workflow = WorkflowInstance(id=uid(), tenant_id=TENANT, process_key="faculty_leave", label="Faculty leave",
            office_n=25, title=f"{row.kind} leave: {row.from_date.isoformat()} to {row.to_date.isoformat()}",
            state="submitted", initiator_id=ctx["sub"], initiator_name=who, current_stage=1,
            scope_level="department")
        s.add(workflow); s.flush(); row.workflow_instance_id = workflow.id
    row.requested_by = ctx["sub"]; row.status = "resubmitted" if resubmission else "submitted"
    # Preserve the last return reason as part of this request's history after resubmission.
    row.submitted_at = datetime.utcnow(); row.updated_at = datetime.utcnow()
    s.commit()
    notify(s, reviewer, "Faculty leave review", f"{who} submitted a {row.kind} leave request", severity="action")
    write_audit(s, ctx["sub"], who, ctx["office_n"], "leave.resubmit" if resubmission else "leave.submit",
                f"leave:{row.id}", "returned" if resubmission else "draft", row.status, row.reason)
    return row


@router.get("/faculty/leave-requests")
def faculty_leave_requests(scope: str = "mine", ctx=Depends(auth), s=Depends(db)):
    rows = s.query(D.LeaveRequest).order_by(desc(D.LeaveRequest.updated_at), desc(D.LeaveRequest.id)).all()
    if scope == "mine":
        _leave_staff_or_403(s, ctx)
        rows = [row for row in rows if row.requested_by == ctx["sub"]]
    elif scope == "inbox":
        rows = [row for row in rows if row.status in {"submitted", "resubmitted", "under_review"}
                and row.workflow_instance_id and _leave_reviewer(s, row, s.query(WorkflowInstance).get(row.workflow_instance_id).current_stage) == ctx["sub"]]
    else:
        raise HTTPException(422, "Scope must be mine or inbox")
    return {"leave_requests": [_leave_payload(s, row) for row in rows]}


@router.post("/faculty/leave-requests")
def create_faculty_leave(body: FacultyLeaveIn, ctx=Depends(auth), s=Depends(db)):
    staff = _leave_staff_or_403(s, ctx)
    start, end = _leave_dates(body)
    if body.action not in {"draft", "submit"}:
        raise HTTPException(422, "Choose draft or submit")
    if body.action == "submit" and _leave_overlap(s, staff.id, start, end):
        raise HTTPException(409, "An overlapping submitted or approved leave request already exists")
    row = D.LeaveRequest(id=uid(), tenant_id=TENANT, staff_id=staff.id, staff_name=staff.name,
        kind=body.kind.strip(), from_date=start, to_date=end, days=(end - start).days + 1,
        reason=body.reason.strip(), status="draft", requested_by=ctx["sub"], half_day=body.half_day,
        updated_at=datetime.utcnow())
    s.add(row); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "leave.create", f"leave:{row.id}", "", "draft", row.reason)
    if body.action == "submit":
        row = _submit_leave(s, row, ctx)
    return {"leave_request": _leave_payload(s, row)}


@router.put("/faculty/leave-requests/{leave_id}")
def update_faculty_leave(leave_id: str, body: FacultyLeaveIn, ctx=Depends(auth), s=Depends(db)):
    row = s.query(D.LeaveRequest).get(leave_id)
    if not row:
        raise HTTPException(404, "Leave request not found")
    if row.requested_by != ctx["sub"]:
        raise HTTPException(403, "Only the requesting professor can edit this leave request")
    if row.status not in LEAVE_EDITABLE_STATUSES:
        raise HTTPException(409, "Only draft or returned leave requests can be edited")
    start, end = _leave_dates(body)
    if body.action not in {"draft", "submit", "resubmit"}:
        raise HTTPException(422, "Choose draft, submit, or resubmit")
    if body.action in {"submit", "resubmit"} and _leave_overlap(s, row.staff_id, start, end, row.id):
        raise HTTPException(409, "An overlapping submitted or approved leave request already exists")
    before = row.status; row.kind = body.kind.strip(); row.from_date = start; row.to_date = end
    row.days = (end - start).days + 1; row.half_day = body.half_day; row.reason = body.reason.strip(); row.updated_at = datetime.utcnow()
    s.commit(); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "leave.edit", f"leave:{row.id}", before, row.status, row.reason)
    if body.action in {"submit", "resubmit"}:
        row = _submit_leave(s, row, ctx, resubmission=row.workflow_instance_id is not None)
    return {"leave_request": _leave_payload(s, row)}


@router.post("/faculty/leave-requests/{leave_id}/cancel")
def cancel_faculty_leave(leave_id: str, ctx=Depends(auth), s=Depends(db)):
    row = s.query(D.LeaveRequest).get(leave_id)
    if not row:
        raise HTTPException(404, "Leave request not found")
    if row.requested_by != ctx["sub"]:
        raise HTTPException(403, "Only the requesting professor can cancel this leave request")
    if row.status not in {"draft", "returned", "submitted", "resubmitted", "under_review"}:
        raise HTTPException(409, "Finalized leave requests cannot be cancelled")
    before = row.status; row.status = "cancelled"; row.updated_at = datetime.utcnow()
    if row.workflow_instance_id:
        workflow = s.query(WorkflowInstance).get(row.workflow_instance_id)
        if workflow: workflow.state = "cancelled"; workflow.updated_at = datetime.utcnow()
    s.commit(); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "leave.cancel", f"leave:{row.id}", before, "cancelled", "Cancelled by requester")
    return {"leave_request": _leave_payload(s, row)}


@router.post("/faculty/leave-requests/{leave_id}/decide")
def decide_faculty_leave(leave_id: str, body: LeaveWorkflowDecisionIn, ctx=Depends(auth), s=Depends(db)):
    row = s.query(D.LeaveRequest).get(leave_id)
    if not row or not row.workflow_instance_id:
        raise HTTPException(404, "Leave workflow request not found")
    workflow = s.query(WorkflowInstance).get(row.workflow_instance_id)
    if row.status not in {"submitted", "resubmitted", "under_review"} or not workflow:
        raise HTTPException(409, "Leave request is not awaiting review")
    if _leave_reviewer(s, row, workflow.current_stage) != ctx["sub"]:
        raise HTTPException(403, "You are not the eligible reviewer for the current leave stage")
    action = body.action.lower()
    if action not in {"approve", "return", "reject"}:
        raise HTTPException(422, "Choose approve, return, or reject")
    if action in {"return", "reject"} and not body.comment.strip():
        raise HTTPException(422, "A comment is required when returning or rejecting leave")
    who = actor_name(s, ctx); before = row.status; stage = workflow.current_stage
    s.add(Approval(id=uid(), tenant_id=TENANT, workflow_id=workflow.id, actor_id=ctx["sub"], actor_name=who,
        stage=stage, stage_label=LEAVE_STAGE_NAMES[stage], decision=action.upper(), authority="FULL", reason=body.comment.strip()))
    if action == "return":
        row.status = "returned"; row.returned_comment = body.comment.strip(); workflow.state = "returned"
        notify(s, row.requested_by, "Faculty leave returned", body.comment.strip(), severity="action")
    elif action == "reject":
        row.status = "rejected"; row.decided_by = who; workflow.state = "rejected"
        notify(s, row.requested_by, "Faculty leave rejected", body.comment.strip(), severity="info")
    elif stage < 3:
        workflow.current_stage += 1; workflow.state = "under_review"; row.status = "under_review"
        next_reviewer = _leave_reviewer(s, row, workflow.current_stage)
        if not next_reviewer:
            raise HTTPException(409, "No reviewer is configured for the next leave stage")
        notify(s, next_reviewer, "Faculty leave review", f"{row.staff_name}'s leave request awaits your review", severity="action")
    else:
        row.status = "approved"; row.decided_by = who; workflow.state = "approved"; workflow.current_stage = 4
        notify(s, row.requested_by, "Faculty leave approved", "Your leave request received final approval.", severity="info")
    row.updated_at = datetime.utcnow(); workflow.updated_at = datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], who, ctx["office_n"], f"leave.{action}", f"leave:{row.id}", before, row.status, body.comment.strip())
    return {"leave_request": _leave_payload(s, row)}
class ResearchProjectIn(BaseModel):
    title: str
    category: str = ""
    summary: str = ""
    start_date: str = ""
    expected_end_date: str = ""
    agency: str = ""
    grant_amount: float = 0


class ResearchProgressIn(BaseModel):
    content: str


class ResearchMilestoneIn(BaseModel):
    title: str
    due_date: str = ""


class ResearchPublicationIn(BaseModel):
    title: str
    publication_type: str = "journal"
    venue: str = ""
    authors: str = ""
    publication_date: str = ""
    doi_url: str = ""
    volume_issue_pages: str = ""


def _research_staff_or_403(s, ctx):
    staff = _staff_profile(s, ctx)
    roles = {row.role_key.lower() for row in _active_faculty_assignments(s, ctx)}
    if not staff or not roles.intersection({"research_faculty", "pi", "principal_investigator", "co_pi", "research_supervisor"}):
        raise HTTPException(403, "An active research responsibility is required")
    return staff


def _research_date(value, label):
    if not value: return None
    try: return date.fromisoformat(value)
    except ValueError: raise HTTPException(422, f"{label} must use YYYY-MM-DD")


def _project_payload(s, row, include_history=False):
    payload = {"id": row.id, "title": row.title, "category": row.category or "", "summary": row.summary or "",
               "agency": row.agency or "", "grant_amount": row.grant_amount or 0, "status": row.status,
               "start_date": row.start_date.isoformat() if row.start_date else "", "expected_end_date": row.expected_end_date.isoformat() if row.expected_end_date else "",
               "created_at": row.created_at.isoformat() if row.created_at else "", "updated_at": row.updated_at.isoformat() if row.updated_at else "",
               "completed_at": row.completed_at.isoformat() if row.completed_at else "", "closed_at": row.closed_at.isoformat() if row.closed_at else ""}
    progress = s.query(D.ResearchProgress).filter(D.ResearchProgress.project_id == row.id).order_by(D.ResearchProgress.created_at).all()
    milestones = s.query(D.ResearchMilestone).filter(D.ResearchMilestone.project_id == row.id).order_by(D.ResearchMilestone.created_at).all()
    payload["progress_count"] = len(progress); payload["milestone_count"] = len(milestones)
    if include_history:
        payload["progress"] = [{"id": x.id, "content": x.content, "author": x.author_name, "at": x.created_at.isoformat()} for x in progress]
        payload["milestones"] = [{"id": x.id, "title": x.title, "due_date": x.due_date.isoformat() if x.due_date else "", "completed_at": x.completed_at.isoformat() if x.completed_at else ""} for x in milestones]
    return payload


def _own_project(s, ctx, project_id):
    staff = _research_staff_or_403(s, ctx); row = s.query(D.ResearchProject).get(project_id)
    if not row: raise HTTPException(404, "Research project not found")
    if row.owner_id != staff.id: raise HTTPException(403, "You can manage only your own research projects")
    return staff, row


@router.get("/faculty/research/projects")
def faculty_research_projects(ctx=Depends(auth), s=Depends(db)):
    staff = _research_staff_or_403(s, ctx)
    rows = s.query(D.ResearchProject).filter(D.ResearchProject.owner_id == staff.id).order_by(desc(D.ResearchProject.updated_at)).all()
    return {"projects": [_project_payload(s, row) for row in rows]}


@router.get("/faculty/research/projects/{project_id}")
def faculty_research_project(project_id: str, ctx=Depends(auth), s=Depends(db)):
    _, row = _own_project(s, ctx, project_id)
    return {"project": _project_payload(s, row, True)}


@router.post("/faculty/research/projects")
def create_research_project(body: ResearchProjectIn, ctx=Depends(auth), s=Depends(db)):
    staff = _research_staff_or_403(s, ctx)
    start, end = _research_date(body.start_date, "Start date"), _research_date(body.expected_end_date, "Expected end date")
    if not body.title.strip(): raise HTTPException(422, "Project title is required")
    if start and end and start > end: raise HTTPException(422, "Start date cannot be after expected end date")
    row = D.ResearchProject(id=uid(), tenant_id=TENANT, title=body.title.strip(), pi_name=staff.name, dept=staff.dept_id or "", owner_id=staff.id, category=body.category.strip(), summary=body.summary.strip(), start_date=start, expected_end_date=end, agency=body.agency.strip(), grant_amount=max(0, body.grant_amount), status="draft")
    s.add(row); s.commit(); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "research.project.create", f"research:{row.id}", "", "draft", row.title)
    return {"project": _project_payload(s, row)}


@router.put("/faculty/research/projects/{project_id}")
def update_research_project(project_id: str, body: ResearchProjectIn, ctx=Depends(auth), s=Depends(db)):
    _, row = _own_project(s, ctx, project_id)
    if row.status != "draft": raise HTTPException(409, "Only draft research projects can be edited")
    start, end = _research_date(body.start_date, "Start date"), _research_date(body.expected_end_date, "Expected end date")
    if not body.title.strip(): raise HTTPException(422, "Project title is required")
    if start and end and start > end: raise HTTPException(422, "Start date cannot be after expected end date")
    row.title=body.title.strip(); row.category=body.category.strip(); row.summary=body.summary.strip(); row.start_date=start; row.expected_end_date=end; row.agency=body.agency.strip(); row.grant_amount=max(0, body.grant_amount); row.updated_at=datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "research.project.edit", f"research:{row.id}", "draft", "draft", row.title)
    return {"project": _project_payload(s, row)}


@router.post("/faculty/research/projects/{project_id}/start")
def start_research_project(project_id: str, ctx=Depends(auth), s=Depends(db)):
    _, row = _own_project(s, ctx, project_id)
    if row.status != "draft": raise HTTPException(409, "Only draft research projects can be started")
    row.status="active"; row.updated_at=datetime.utcnow(); s.commit(); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "research.project.start", f"research:{row.id}", "draft", "active", "")
    return {"project": _project_payload(s, row)}


@router.post("/faculty/research/projects/{project_id}/progress")
def add_research_progress(project_id: str, body: ResearchProgressIn, ctx=Depends(auth), s=Depends(db)):
    _, row = _own_project(s, ctx, project_id)
    if row.status != "active": raise HTTPException(409, "Only active research projects can receive progress updates")
    if not body.content.strip(): raise HTTPException(422, "Progress update is required")
    s.add(D.ResearchProgress(id=uid(), tenant_id=TENANT, project_id=row.id, author_id=ctx["sub"], author_name=actor_name(s, ctx), content=body.content.strip())); row.updated_at=datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "research.progress.add", f"research:{row.id}", "active", "active", body.content.strip())
    return {"project": _project_payload(s, row, True)}


@router.post("/faculty/research/projects/{project_id}/milestones")
def add_research_milestone(project_id: str, body: ResearchMilestoneIn, ctx=Depends(auth), s=Depends(db)):
    _, row = _own_project(s, ctx, project_id)
    if row.status != "active": raise HTTPException(409, "Only active research projects can receive milestones")
    if not body.title.strip(): raise HTTPException(422, "Milestone title is required")
    s.add(D.ResearchMilestone(id=uid(), tenant_id=TENANT, project_id=row.id, title=body.title.strip(), due_date=_research_date(body.due_date, "Milestone due date"))); row.updated_at=datetime.utcnow(); s.commit()
    return {"project": _project_payload(s, row, True)}


@router.post("/faculty/research/projects/{project_id}/milestones/{milestone_id}/complete")
def complete_research_milestone(project_id: str, milestone_id: str, ctx=Depends(auth), s=Depends(db)):
    _, row = _own_project(s, ctx, project_id)
    milestone = s.query(D.ResearchMilestone).filter(D.ResearchMilestone.id == milestone_id, D.ResearchMilestone.project_id == row.id).first()
    if row.status != "active" or not milestone: raise HTTPException(409, "Active project milestone is required")
    if milestone.completed_at: raise HTTPException(409, "Milestone is already complete")
    milestone.completed_at=datetime.utcnow(); milestone.completed_by=ctx["sub"]; row.updated_at=datetime.utcnow(); s.commit()
    return {"project": _project_payload(s, row, True)}


@router.post("/faculty/research/projects/{project_id}/complete")
def complete_research_project(project_id: str, action: str, ctx=Depends(auth), s=Depends(db)):
    _, row = _own_project(s, ctx, project_id)
    if action not in {"complete", "close"}: raise HTTPException(422, "Action must be complete or close")
    if row.status != "active": raise HTTPException(409, "Only active research projects can be completed or closed")
    row.status="completed" if action == "complete" else "closed"; now=datetime.utcnow(); row.completed_at=now if action == "complete" else None; row.closed_at=now if action == "close" else None; row.updated_at=now; s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], f"research.project.{action}", f"research:{row.id}", "active", row.status, "")
    return {"project": _project_payload(s, row, True)}


def _publication_payload(row):
    return {"id": row.id, "title": row.title, "publication_type": row.publication_type, "venue": row.venue, "authors": row.authors, "publication_date": row.publication_date.isoformat() if row.publication_date else "", "doi_url": row.doi_url, "volume_issue_pages": row.volume_issue_pages, "status": row.status, "created_at": row.created_at.isoformat() if row.created_at else "", "updated_at": row.updated_at.isoformat() if row.updated_at else ""}


def _own_publication(s, ctx, publication_id):
    staff=_research_staff_or_403(s, ctx); row=s.query(D.ResearchPublication).get(publication_id)
    if not row: raise HTTPException(404, "Publication not found")
    if row.owner_id != staff.id: raise HTTPException(403, "You can manage only your own publications")
    return row


@router.get("/faculty/research/publications")
def faculty_research_publications(ctx=Depends(auth), s=Depends(db)):
    staff=_research_staff_or_403(s, ctx)
    return {"publications": [_publication_payload(x) for x in s.query(D.ResearchPublication).filter(D.ResearchPublication.owner_id == staff.id).order_by(desc(D.ResearchPublication.updated_at)).all()]}


@router.post("/faculty/research/publications")
def create_research_publication(body: ResearchPublicationIn, ctx=Depends(auth), s=Depends(db)):
    staff=_research_staff_or_403(s, ctx)
    if not body.title.strip(): raise HTTPException(422, "Publication title is required")
    row=D.ResearchPublication(id=uid(), tenant_id=TENANT, owner_id=staff.id, title=body.title.strip(), publication_type=body.publication_type.strip(), venue=body.venue.strip(), authors=body.authors.strip(), publication_date=_research_date(body.publication_date, "Publication date"), doi_url=body.doi_url.strip(), volume_issue_pages=body.volume_issue_pages.strip(), status="draft")
    s.add(row); s.commit(); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "research.publication.create", f"publication:{row.id}", "", "draft", row.title)
    return {"publication": _publication_payload(row)}


@router.put("/faculty/research/publications/{publication_id}")
def update_research_publication(publication_id: str, body: ResearchPublicationIn, ctx=Depends(auth), s=Depends(db)):
    row=_own_publication(s, ctx, publication_id)
    if row.status != "draft": raise HTTPException(409, "Published or archived publications are read-only")
    if not body.title.strip(): raise HTTPException(422, "Publication title is required")
    row.title=body.title.strip(); row.publication_type=body.publication_type.strip(); row.venue=body.venue.strip(); row.authors=body.authors.strip(); row.publication_date=_research_date(body.publication_date, "Publication date"); row.doi_url=body.doi_url.strip(); row.volume_issue_pages=body.volume_issue_pages.strip(); row.updated_at=datetime.utcnow(); s.commit()
    return {"publication": _publication_payload(row)}


@router.post("/faculty/research/publications/{publication_id}/publish")
def publish_research_publication(publication_id: str, ctx=Depends(auth), s=Depends(db)):
    row=_own_publication(s, ctx, publication_id)
    if row.status != "draft": raise HTTPException(409, "Only draft publications can be marked published")
    if not all([row.title.strip(), row.publication_type.strip(), row.venue.strip(), row.authors.strip(), row.publication_date]): raise HTTPException(422, "Title, type, venue, authors, and publication date are required before publishing")
    if row.doi_url and not (row.doi_url.startswith("http://") or row.doi_url.startswith("https://") or row.doi_url.lower().startswith("doi:")): raise HTTPException(422, "DOI or URL must be a DOI prefix or valid HTTP URL")
    row.status="published"; row.updated_at=datetime.utcnow(); s.commit(); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "research.publication.publish", f"publication:{row.id}", "draft", "published", row.title)
    return {"publication": _publication_payload(row)}
