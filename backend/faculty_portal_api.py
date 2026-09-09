# -*- coding: utf-8 -*-
"""Faculty/student self-service APIs ported from the local development branch."""
from datetime import date, datetime, timedelta
import hashlib
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, desc, func, or_

from core import auth, db, notify, uid, write_audit
from database import TENANT, office
import domain_models as D
from teaching import (active_allocations_for_faculty, faculty_active_sections,
                      faculty_owns_section, class_session_for_timetable)
from models import Person, User, Notification, WorkflowInstance
from portal_api import (_student_attendance_pct, _student_tasks_payload,
                        _student_today_classes_payload)

router = APIRouter(prefix="/api/portal")


def _student_or_404(s, ctx):
    student = s.query(D.Student).filter(D.Student.user_id == ctx["sub"]).first()
    if not student and ctx.get("scope_ref"):
        student = s.query(D.Student).get(ctx["scope_ref"])
    if not student:
        raise HTTPException(404, "No student linked to this login")
    return student


def _staff_or_404(s, ctx):
    staff = s.query(D.StaffMember).filter(D.StaffMember.user_id == ctx["sub"]).first()
    if not staff:
        raise HTTPException(404, "No staff profile linked to this login")
    return staff

def _faculty_digital_id_payload(s, ctx):
    if ctx.get("office_n") not in {11, 12, 13, 14}:
        raise HTTPException(403, "Professor access required")
    staff = _staff_or_404(s, ctx)
    user = s.query(User).get(ctx["sub"])
    person = s.query(Person).get(user.person_id) if user else None
    department = s.query(D.Department).get(staff.dept_id) if staff.dept_id else None
    safe_token = hashlib.sha256(f"{TENANT}:FACULTY:{staff.emp_id}".encode("utf-8")).hexdigest()[:16].upper()
    return {
        "full_name": person.name if person else staff.name,
        "employee_id": staff.emp_id or "",
        "designation": staff.designation or (user.role if user else "Professor"),
        "department": department.name if department else "",
        "department_code": department.code if department else "",
        "campus": staff.campus or (department.campus if department else "") or "Main Campus",
        "avatar_initials": "".join(part[:1] for part in (staff.name or "Faculty").split()[:2]).upper(),
        "valid_until": "",
        "validity_label": "Not specified",
        "verification_payload": f"ICMS:FAC:{safe_token}",
        "barcode_value": staff.emp_id or safe_token,
    }


def _active_functional_roles(s, staff):
    now = datetime.utcnow()
    rows = (s.query(D.FacultyFunctionalAssignment)
            .filter(D.FacultyFunctionalAssignment.faculty_id == staff.id,
                    D.FacultyFunctionalAssignment.status == "active",
                    D.FacultyFunctionalAssignment.valid_from <= now,
                    or_(D.FacultyFunctionalAssignment.valid_to == None,
                        D.FacultyFunctionalAssignment.valid_to >= now))
            .all())
    return rows


def _require_associate_feature(s, ctx, staff, feature):
    """Conditional faculty routes always require an effective assignment."""
    if ctx["office_n"] not in {11, 12, 13, 14}:
        raise HTTPException(403, "This feature is available only to teaching faculty")
    rows = _active_functional_roles(s, staff)
    roles = {row.role_key.lower() for row in rows}
    permissions = {row.permission_key.lower() for row in rows if row.permission_key}
    has_advisees = s.query(D.MentorAssignment).filter(D.MentorAssignment.faculty_id == staff.id, D.MentorAssignment.status == "active").count() > 0
    allowed = {
        "advisees": has_advisees,
        "academic_risk": has_advisees,
        "course_registrations": has_advisees and "advisor_registration_review" in permissions,
        "course_coordination": "course_coordinator" in roles,
    }.get(feature, False)
    if not allowed:
        raise HTTPException(403, "No active functional assignment grants this faculty feature")


@router.get("/faculty/self-check-in")
def faculty_self_check_in_status(ctx=Depends(auth), s=Depends(db)):
    staff = _staff_or_404(s, ctx)
    row = (s.query(D.StaffCheckIn)
           .filter(D.StaffCheckIn.staff_id == staff.id, D.StaffCheckIn.on_date == date.today())
           .first())
    return {"checked_in": bool(row), "on_date": date.today().isoformat(),
            "checked_in_at": row.checked_in_at.isoformat() if row and row.checked_in_at else ""}


class FacultySelfCheckInIn(BaseModel):
    note: str = ""


@router.post("/faculty/self-check-in")
def faculty_self_check_in(body: FacultySelfCheckInIn, ctx=Depends(auth), s=Depends(db)):
    staff = _staff_or_404(s, ctx)
    today = date.today()
    row = (s.query(D.StaffCheckIn)
           .filter(D.StaffCheckIn.staff_id == staff.id, D.StaffCheckIn.on_date == today)
           .first())
    if not row:
        row = D.StaffCheckIn(id=str(uuid4()), tenant_id=TENANT, staff_id=staff.id,
                             on_date=today, checked_in_at=datetime.utcnow(), note=body.note.strip())
        s.add(row)
        s.commit()
    return {"checked_in": True, "on_date": today.isoformat(),
            "checked_in_at": row.checked_in_at.isoformat() if row.checked_in_at else ""}
@router.get("/faculty/digital-id")
def faculty_digital_id(ctx=Depends(auth), s=Depends(db)):
    return {"digital_id": _faculty_digital_id_payload(s, ctx)}


class StudentAssignmentSubmissionIn(BaseModel):
    submission_text: str = ""


def _student_assignment_payload(s, assignment, student):
    section = s.query(D.Section).get(assignment.section_id)
    course = s.query(D.Course).get(section.course_id) if section else None
    faculty = s.query(D.StaffMember).get(assignment.faculty_id) if assignment.faculty_id else None
    if not faculty and section and section.faculty_person_id:
        faculty = s.query(D.StaffMember).get(section.faculty_person_id)
    attempts = s.query(D.AssignmentSubmission).filter(D.AssignmentSubmission.assignment_id == assignment.id, D.AssignmentSubmission.student_id == student.id).order_by(desc(D.AssignmentSubmission.attempt_no)).all()
    latest = attempts[0] if attempts else None
    evaluation = s.query(D.AssignmentEvaluation).filter(D.AssignmentEvaluation.submission_id == latest.id).first() if latest else None
    return {"id": assignment.id, "title": assignment.title, "instructions": assignment.description or "", "course_code": course.code if course else "", "course_title": course.title if course else "", "section": section.section_code if section else "", "professor": faculty.name if faculty else "-", "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else "", "due_at": assignment.due_at.isoformat() if assignment.due_at else "", "max_marks": assignment.max_marks, "allow_late": bool(assignment.allow_late), "assignment_status": assignment.status, "submission_id": latest.id if latest else "", "submission_status": latest.status if latest else "not_submitted", "submitted_at": latest.submitted_at.isoformat() if latest else "", "attempt_no": latest.attempt_no if latest else 0, "late": bool(latest and latest.is_late), "submission_text": latest.submission_text if latest else "", "marks_awarded": evaluation.marks_awarded if evaluation and latest.status == "evaluated" else None, "feedback": evaluation.feedback if evaluation and latest.status in {"evaluated", "returned"} else "", "can_submit": not latest or latest.status == "returned"}


def _student_assignment_or_404(s, ctx, assignment_id):
    student = _student_or_404(s, ctx)
    assignment = s.query(D.Assignment).get(assignment_id)
    if not assignment or assignment.status not in {"published", "closed"}: raise HTTPException(404, "Published assignment not found")
    enrolled = s.query(D.Enrollment).filter(D.Enrollment.section_id == assignment.section_id, D.Enrollment.student_id == student.id, D.Enrollment.status == "enrolled").first()
    if not enrolled: raise HTTPException(403, "You are not enrolled in this assignment section")
    return student, assignment


@router.get("/student/assignments")
def student_assignments(ctx=Depends(auth), s=Depends(db)):
    student = _student_or_404(s, ctx)
    section_ids = [row.section_id for row in s.query(D.Enrollment).filter(D.Enrollment.student_id == student.id, D.Enrollment.status == "enrolled").all()]
    rows = s.query(D.Assignment).filter(D.Assignment.section_id.in_(section_ids) if section_ids else False, D.Assignment.status.in_(["published", "closed"])).order_by(D.Assignment.due_at).all()
    return {"assignments": [_student_assignment_payload(s, row, student) for row in rows]}


@router.get("/student/assignments/{assignment_id}")
def student_assignment_detail(assignment_id: str, ctx=Depends(auth), s=Depends(db)):
    student, assignment = _student_assignment_or_404(s, ctx, assignment_id)
    return {"assignment": _student_assignment_payload(s, assignment, student)}


@router.post("/student/assignments/{assignment_id}/submit")
def submit_student_assignment(assignment_id: str, body: StudentAssignmentSubmissionIn, ctx=Depends(auth), s=Depends(db)):
    student, assignment = _student_assignment_or_404(s, ctx, assignment_id)
    if assignment.status != "published": raise HTTPException(409, "This assignment is closed")
    if not body.submission_text.strip(): raise HTTPException(422, "Submission text is required")
    prior = s.query(D.AssignmentSubmission).filter(D.AssignmentSubmission.assignment_id == assignment.id, D.AssignmentSubmission.student_id == student.id).order_by(desc(D.AssignmentSubmission.attempt_no)).first()
    if prior and prior.status != "returned":
        if prior.submission_text == body.submission_text.strip(): return {"submission": _student_assignment_payload(s, assignment, student), "idempotent": True}
        raise HTTPException(409, "A submission already exists and is not returned for resubmission")
    now = datetime.utcnow(); late = bool(assignment.due_at and now > assignment.due_at)
    if late and not assignment.allow_late: raise HTTPException(409, "Late submissions are not allowed")
    attempt = (prior.attempt_no + 1) if prior else 1
    status = "resubmitted" if prior else ("late" if late else "submitted")
    submission = D.AssignmentSubmission(id=uid(), tenant_id=TENANT, assignment_id=assignment.id, student_id=student.id, submitted_at=now, attempt_no=attempt, status=status, is_late=late, submission_text=body.submission_text.strip())
    s.add(submission); s.commit(); write_audit(s, ctx["sub"], student.name, ctx["office_n"], "assignment.resubmit" if prior else "assignment.submit", f"assignment_submission:{submission.id}", "", status, assignment.title)
    return {"submission": _student_assignment_payload(s, assignment, student), "idempotent": False}
def _material_payload(s, item):
    section = s.query(D.Section).get(item.section_id)
    course = s.query(D.Course).get(section.course_id) if section else None
    return {"id": item.id, "section_id": item.section_id, "course_code": course.code if course else "", "course_title": course.title if course else "", "section": section.section_code if section else "", "title": item.title, "description": item.description, "material_type": item.material_type, "resource_url": item.resource_url, "topic": item.topic, "status": item.status, "uploaded_by": item.uploaded_by, "uploaded_at": item.created_at.isoformat() if item.created_at else ""}


@router.get("/faculty/materials")
def faculty_materials(ctx=Depends(auth), s=Depends(db)):
    staff = _staff_or_404(s, ctx)
    ids = [row.id for row in faculty_active_sections(s, staff.id)]
    rows = s.query(D.CourseMaterial).filter(D.CourseMaterial.section_id.in_(ids)).order_by(desc(D.CourseMaterial.created_at)).all() if ids else []
    return {"materials": [_material_payload(s, item) for item in rows]}


@router.get("/faculty/assessment/{assessment_id}/marks")
def faculty_assessment_marks(assessment_id: str, ctx=Depends(auth), s=Depends(db)):
    staff = _staff_or_404(s, ctx)
    assessment = s.query(D.Assessment).get(assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    section = s.query(D.Section).get(assessment.section_id)
    if not section or not faculty_owns_section(s, staff.id, section.id):
        raise HTTPException(403, "This assessment is not in one of your assigned sections")
    marks = {row.student_id: row.score for row in s.query(D.Mark).filter(D.Mark.assessment_id == assessment.id).all()}
    students = {row.id: row for row in s.query(D.Student).all()}
    roster = []
    for enrollment in s.query(D.Enrollment).filter(D.Enrollment.section_id == section.id, D.Enrollment.status == "enrolled").all():
        student = students.get(enrollment.student_id)
        if student:
            roster.append({"student_id": student.id, "roll_no": student.roll_no, "name": student.name, "score": marks.get(student.id)})
    workflow = s.query(WorkflowInstance).get(assessment.workflow_instance_id) if assessment.workflow_instance_id else None
    return {"assessment_id": assessment.id, "max_marks": assessment.max_marks, "roster": roster,
            "marks_state": assessment.marks_state or "draft", "workflow_instance_id": assessment.workflow_instance_id or "",
            "current_stage": workflow.current_stage if workflow else 0,
            "return_comment": assessment.marks_return_comment or "",
            "published_at": assessment.marks_published_at.isoformat() if assessment.marks_published_at else ""}


class CourseMaterialIn(BaseModel):
    section_id: str
    title: str
    description: str = ""
    material_type: str = "document"
    resource_url: str = ""
    topic: str = ""
    status: str = "draft"


@router.post("/faculty/materials")
def create_faculty_material(body: CourseMaterialIn, ctx=Depends(auth), s=Depends(db)):
    staff = _staff_or_404(s, ctx)
    section = s.query(D.Section).get(body.section_id)
    if not section or not faculty_owns_section(s, staff.id, section.id):
        raise HTTPException(403, "You can add materials only to your assigned sections")
    item = D.CourseMaterial(id=str(uuid4()), tenant_id=TENANT, section_id=section.id, title=body.title.strip(), description=body.description.strip(), material_type=body.material_type.strip(), resource_url=body.resource_url.strip(), topic=body.topic.strip(), status="published" if body.status == "published" else "draft", uploaded_by=staff.name)
    s.add(item); s.commit()
    return {"material": _material_payload(s, item)}


@router.get("/student/materials")
def student_materials(ctx=Depends(auth), s=Depends(db)):
    student = _student_or_404(s, ctx)
    ids = [row.section_id for row in s.query(D.Enrollment).filter(D.Enrollment.student_id == student.id, D.Enrollment.status == "enrolled").all()]
    rows = s.query(D.CourseMaterial).filter(D.CourseMaterial.section_id.in_(ids), D.CourseMaterial.status == "published").order_by(desc(D.CourseMaterial.created_at)).all() if ids else []
    return {"materials": [_material_payload(s, item) for item in rows]}
def _mentee_payload(s, student):
    dept = s.query(D.Department).get(student.dept_id) if student.dept_id else None
    marks = s.query(D.Mark).filter(D.Mark.student_id == student.id).all()
    assessments = {row.id: row for row in s.query(D.Assessment).filter(D.Assessment.id.in_([mark.assessment_id for mark in marks])).all()} if marks else {}
    mark_values = [round(100 * mark.score / assessments[mark.assessment_id].max_marks, 1) for mark in marks if assessments.get(mark.assessment_id) and assessments[mark.assessment_id].max_marks]
    attendance = _student_attendance_pct(s, student)
    return {"id": student.id, "roll_no": student.roll_no, "name": student.name, "department": dept.code if dept else "â€”", "semester": student.semester, "study_year": (student.semester + 1) // 2 if student.semester else None, "section": student.section, "cgpa": student.cgpa, "attendance_pct": attendance, "marks_average": round(sum(mark_values) / len(mark_values), 1) if mark_values else None, "assessments_recorded": len(mark_values), "risk": "attention" if (attendance is not None and attendance < 75) or (student.cgpa is not None and student.cgpa < 6.5) else "on_track"}


def _mentee_with_indicators(s, student):
    """Expose the source facts behind risk without creating a composite score."""
    payload = _mentee_payload(s, student)
    backlogs = s.query(D.StudentSubjectResult).filter(
        D.StudentSubjectResult.student_id == student.id,
        D.StudentSubjectResult.outcome == "failed").count()
    payload["backlogs"] = backlogs
    indicators = []
    if payload["attendance_pct"] is not None and payload["attendance_pct"] < 75:
        indicators.append(f"Attendance below 75% ({payload['attendance_pct']}%)")
    if student.cgpa is not None and student.cgpa < 6.5:
        indicators.append(f"CGPA below 6.50 ({student.cgpa:.2f})")
    if backlogs:
        indicators.append(f"{backlogs} published backlog{'s' if backlogs != 1 else ''}")
    if payload["marks_average"] is not None and payload["marks_average"] < 50:
        indicators.append(f"Recorded assessment average below 50% ({payload['marks_average']}%)")
    payload["risk_indicators"] = indicators
    return payload


@router.get("/faculty/mentees")
def faculty_mentees(ctx=Depends(auth), s=Depends(db)):
    staff = _staff_or_404(s, ctx)
    _require_associate_feature(s, ctx, staff, "advisees")
    assignments = s.query(D.MentorAssignment).filter(D.MentorAssignment.faculty_id == staff.id, D.MentorAssignment.status == "active").all()
    students = [s.query(D.Student).get(row.student_id) for row in assignments]
    rows = [_mentee_with_indicators(s, student) for student in students if student]
    return {"mentees": rows}


@router.get("/faculty/mentees/{student_id}")
def faculty_mentee_detail(student_id: str, ctx=Depends(auth), s=Depends(db)):
    staff = _staff_or_404(s, ctx)
    _require_associate_feature(s, ctx, staff, "advisees")
    assignment = s.query(D.MentorAssignment).filter(D.MentorAssignment.faculty_id == staff.id, D.MentorAssignment.student_id == student_id, D.MentorAssignment.status == "active").first()
    if not assignment:
        raise HTTPException(403, "This student is not assigned to you for mentoring")
    student = s.query(D.Student).get(student_id)
    marks = s.query(D.Mark).filter(D.Mark.student_id == student_id).all()
    assessments = {row.id: row for row in s.query(D.Assessment).filter(D.Assessment.id.in_([mark.assessment_id for mark in marks])).all()} if marks else {}
    progress = [{"assessment": assessments[mark.assessment_id].name, "score": mark.score, "max_marks": assessments[mark.assessment_id].max_marks, "status": mark.status} for mark in marks if assessments.get(mark.assessment_id)]
    return {"student": _mentee_with_indicators(s, student), "marks_progress": progress}


CASE_CATEGORIES = {"Attendance", "Academic Performance", "Backlogs", "Behaviour/Discipline", "Personal/Wellbeing", "Career/Placement", "Other"}
CASE_RISK_LEVELS = {"low", "medium", "high"}
CASE_EDITABLE = {"open", "referred"}


class MentoringCaseIn(BaseModel):
    category: str
    risk_level: str
    summary: str
    action_plan: str = ""
    follow_up_date: str = ""


class MentoringCaseUpdateIn(BaseModel):
    category: str | None = None
    risk_level: str | None = None
    summary: str | None = None
    action_plan: str | None = None
    follow_up_date: str | None = None


class MentoringNoteIn(BaseModel):
    content: str


class MentoringFollowUpIn(BaseModel):
    scheduled_for: str


class MentoringFollowUpCompleteIn(BaseModel):
    outcome: str


class MentoringReferralIn(BaseModel):
    reason: str


def _mentoring_actor(s, ctx):
    staff = s.query(D.StaffMember).filter(D.StaffMember.user_id == ctx["sub"]).first()
    return staff.name if staff else ctx.get("role", "Faculty")


def _mentor_student_or_403(s, ctx, student_id):
    staff = _staff_or_404(s, ctx)
    _require_associate_feature(s, ctx, staff, "advisees")
    assignment = s.query(D.MentorAssignment).filter(
        D.MentorAssignment.faculty_id == staff.id,
        D.MentorAssignment.student_id == student_id,
        D.MentorAssignment.status == "active").first()
    if not assignment:
        raise HTTPException(403, "This student is not assigned to you for mentoring")
    student = s.query(D.Student).get(student_id)
    if not student:
        raise HTTPException(404, "Student not found")
    return staff, student


def _mentor_case_or_403(s, ctx, case_id):
    case = s.query(D.MentoringCase).get(case_id)
    if not case:
        raise HTTPException(404, "Mentoring case not found")
    staff, student = _mentor_student_or_403(s, ctx, case.student_id)
    if case.mentor_id != staff.id:
        raise HTTPException(403, "You do not own this mentoring case")
    return case, staff, student


def _case_payload(s, case, include_history=True):
    student = s.query(D.Student).get(case.student_id)
    mentor = s.query(D.StaffMember).get(case.mentor_id)
    payload = {
        "id": case.id, "student_id": case.student_id, "student": _mentee_with_indicators(s, student) if student else {},
        "mentor": mentor.name if mentor else "", "category": case.category, "risk_level": case.risk_level,
        "status": case.status, "summary": case.summary, "action_plan": case.action_plan,
        "follow_up_date": case.follow_up_date.isoformat() if case.follow_up_date else "",
        "referred_to_office": case.referred_to_office, "referred_at": case.referred_at.isoformat() if case.referred_at else "",
        "resolved_at": case.resolved_at.isoformat() if case.resolved_at else "",
        "closed_at": case.closed_at.isoformat() if case.closed_at else "",
        "created_at": case.created_at.isoformat() if case.created_at else "", "updated_at": case.updated_at.isoformat() if case.updated_at else "",
        "editable": case.status in CASE_EDITABLE,
    }

    if include_history:
        notes = s.query(D.MentoringNote).filter(D.MentoringNote.case_id == case.id).order_by(D.MentoringNote.created_at).all()
        follow_ups = s.query(D.MentoringFollowUp).filter(D.MentoringFollowUp.case_id == case.id).order_by(D.MentoringFollowUp.scheduled_for, D.MentoringFollowUp.created_at).all()
        payload["notes"] = [{"id": row.id, "author": row.author_name, "note_type": row.note_type, "content": row.content, "at": row.created_at.isoformat()} for row in notes]
        payload["follow_ups"] = [{"id": row.id, "scheduled_for": row.scheduled_for.isoformat(), "completed_at": row.completed_at.isoformat() if row.completed_at else "", "outcome": row.outcome} for row in follow_ups]
    return payload


@router.get("/faculty/announcements")
def faculty_announcements(ctx=Depends(auth), s=Depends(db)):
    stf = _staff_or_404(s, ctx)
    now = datetime.utcnow()
    rows = (s.query(D.Announcement)
            .filter(D.Announcement.status == "published",
                    or_(D.Announcement.published_at == None, D.Announcement.published_at <= now),
                    or_(D.Announcement.expires_at == None, D.Announcement.expires_at >= now),
                    or_(D.Announcement.audience.in_(["all", "faculty", "staff"]),
                        and_(D.Announcement.audience == "department", D.Announcement.department_id == stf.dept_id),
                        and_(D.Announcement.audience == "campus", D.Announcement.campus == stf.campus)))
            .order_by(desc(D.Announcement.published_at), desc(D.Announcement.created_at))
            .all())
    return {"announcements": [{"id": row.id, "title": row.title, "body": row.body,
                                "published_at": (row.published_at or row.created_at).isoformat() if (row.published_at or row.created_at) else ""}
                               for row in rows]}


def _case_follow_up(value):
    if not value:
        return None
    try:
        follow_up = date.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, "Follow-up date must use YYYY-MM-DD")
    if follow_up < date.today():
        raise HTTPException(422, "Follow-up date cannot be in the past")
    return follow_up


@router.get("/faculty/mentoring-cases")
def faculty_mentoring_cases(scope: str = "mine", ctx=Depends(auth), s=Depends(db)):
    if scope == "mine":
        staff = _staff_or_404(s, ctx)
        _require_associate_feature(s, ctx, staff, "advisees")
        rows = s.query(D.MentoringCase).filter(D.MentoringCase.mentor_id == staff.id).order_by(desc(D.MentoringCase.updated_at)).all()
    elif scope == "inbox":
        reviewer = _staff_or_404(s, ctx)
        if ctx["office_n"] != 10:
            raise HTTPException(403, "Only the department HOD can view referred mentoring cases")
        mentor_ids = [row.id for row in s.query(D.StaffMember).filter(D.StaffMember.dept_id == reviewer.dept_id).all()]
        rows = s.query(D.MentoringCase).filter(D.MentoringCase.mentor_id.in_(mentor_ids), D.MentoringCase.referred_to_office == "hod").order_by(desc(D.MentoringCase.updated_at)).all()
    else:
        raise HTTPException(422, "Scope must be mine or inbox")
    return {"cases": [_case_payload(s, row, include_history=False) for row in rows]}


@router.get("/faculty/mentoring-cases/{case_id}")
def faculty_mentoring_case(case_id: str, ctx=Depends(auth), s=Depends(db)):
    case = s.query(D.MentoringCase).get(case_id)
    if not case:
        raise HTTPException(404, "Mentoring case not found")
    if case.mentor_id == (_staff_or_404(s, ctx).id):
        _mentor_case_or_403(s, ctx, case_id)
    else:
        reviewer = _staff_or_404(s, ctx)
        if ctx["office_n"] != 10 or case.referred_to_office != "hod" or case.department_id != reviewer.dept_id:
            raise HTTPException(403, "You cannot view this mentoring case")
    return {"case": _case_payload(s, case)}


@router.post("/faculty/mentees/{student_id}/mentoring-cases")
def create_mentoring_case(student_id: str, body: MentoringCaseIn, ctx=Depends(auth), s=Depends(db)):
    staff, student = _mentor_student_or_403(s, ctx, student_id)
    if body.category not in CASE_CATEGORIES or body.risk_level.lower() not in CASE_RISK_LEVELS:
        raise HTTPException(422, "Choose a supported category and risk level")
    if not body.summary.strip():
        raise HTTPException(422, "Concern or summary is required")
    follow_up = _case_follow_up(body.follow_up_date)
    row = D.MentoringCase(id=uid(), tenant_id=TENANT, student_id=student.id, mentor_id=staff.id,
        department_id=staff.dept_id or student.dept_id, category=body.category, risk_level=body.risk_level.lower(),
        summary=body.summary.strip(), action_plan=body.action_plan.strip(), follow_up_date=follow_up)
    s.add(row); s.commit()
    write_audit(s, ctx["sub"], _mentoring_actor(s, ctx), ctx["office_n"], "mentoring.case.create", f"mentoring:{row.id}", "", "open", row.summary)
    return {"case": _case_payload(s, row)}


@router.put("/faculty/mentoring-cases/{case_id}")
def update_mentoring_case(case_id: str, body: MentoringCaseUpdateIn, ctx=Depends(auth), s=Depends(db)):
    row, _, _ = _mentor_case_or_403(s, ctx, case_id)
    if row.status not in CASE_EDITABLE:
        raise HTTPException(409, "Resolved or closed mentoring cases are read-only")
    if body.category is not None:
        if body.category not in CASE_CATEGORIES: raise HTTPException(422, "Choose a supported category")
        row.category = body.category
    if body.risk_level is not None:
        if body.risk_level.lower() not in CASE_RISK_LEVELS: raise HTTPException(422, "Choose low, medium, or high risk")
        row.risk_level = body.risk_level.lower()
    if body.summary is not None:
        if not body.summary.strip(): raise HTTPException(422, "Concern or summary is required")
        row.summary = body.summary.strip()
    if body.action_plan is not None and body.action_plan.strip() != row.action_plan:
        row.action_plan = body.action_plan.strip()
        s.add(D.MentoringNote(id=uid(), tenant_id=TENANT, case_id=row.id, author_user_id=ctx["sub"], author_name=_mentoring_actor(s, ctx), note_type="action_plan", content=row.action_plan))
    if body.follow_up_date is not None:
        row.follow_up_date = _case_follow_up(body.follow_up_date)
    row.updated_at = datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], _mentoring_actor(s, ctx), ctx["office_n"], "mentoring.case.update", f"mentoring:{row.id}", "", row.status, row.summary)
    return {"case": _case_payload(s, row)}


@router.post("/faculty/mentoring-cases/{case_id}/notes")
def add_mentoring_note(case_id: str, body: MentoringNoteIn, ctx=Depends(auth), s=Depends(db)):
    row, _, _ = _mentor_case_or_403(s, ctx, case_id)
    if row.status not in CASE_EDITABLE: raise HTTPException(409, "Resolved or closed mentoring cases are read-only")
    if not body.content.strip(): raise HTTPException(422, "A note is required")
    s.add(D.MentoringNote(id=uid(), tenant_id=TENANT, case_id=row.id, author_user_id=ctx["sub"], author_name=_mentoring_actor(s, ctx), note_type="note", content=body.content.strip()))
    row.updated_at = datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], _mentoring_actor(s, ctx), ctx["office_n"], "mentoring.note.add", f"mentoring:{row.id}", row.status, row.status, body.content.strip())
    return {"case": _case_payload(s, row)}


@router.post("/faculty/mentoring-cases/{case_id}/follow-ups")
def schedule_mentoring_follow_up(case_id: str, body: MentoringFollowUpIn, ctx=Depends(auth), s=Depends(db)):
    row, _, _ = _mentor_case_or_403(s, ctx, case_id)
    if row.status not in CASE_EDITABLE: raise HTTPException(409, "Resolved or closed mentoring cases are read-only")
    scheduled_for = _case_follow_up(body.scheduled_for)
    follow_up = D.MentoringFollowUp(id=uid(), tenant_id=TENANT, case_id=row.id, scheduled_for=scheduled_for, created_by=ctx["sub"])
    s.add(follow_up); row.follow_up_date = scheduled_for; row.updated_at = datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], _mentoring_actor(s, ctx), ctx["office_n"], "mentoring.follow_up.schedule", f"mentoring:{row.id}", "", "scheduled", scheduled_for.isoformat())
    return {"case": _case_payload(s, row)}


@router.post("/faculty/mentoring-cases/{case_id}/follow-ups/{follow_up_id}/complete")
def complete_mentoring_follow_up(case_id: str, follow_up_id: str, body: MentoringFollowUpCompleteIn, ctx=Depends(auth), s=Depends(db)):
    row, _, _ = _mentor_case_or_403(s, ctx, case_id)
    follow_up = s.query(D.MentoringFollowUp).filter(D.MentoringFollowUp.id == follow_up_id, D.MentoringFollowUp.case_id == row.id).first()
    if not follow_up: raise HTTPException(404, "Follow-up not found")
    if follow_up.completed_at: raise HTTPException(409, "Follow-up is already complete")
    if not body.outcome.strip(): raise HTTPException(422, "Follow-up outcome is required")
    follow_up.completed_at = datetime.utcnow(); follow_up.completed_by = ctx["sub"]; follow_up.outcome = body.outcome.strip(); row.updated_at = datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], _mentoring_actor(s, ctx), ctx["office_n"], "mentoring.follow_up.complete", f"mentoring:{row.id}", "scheduled", "complete", follow_up.outcome)
    return {"case": _case_payload(s, row)}


@router.post("/faculty/mentoring-cases/{case_id}/refer")
def refer_mentoring_case(case_id: str, body: MentoringReferralIn, ctx=Depends(auth), s=Depends(db)):
    row, staff, _ = _mentor_case_or_403(s, ctx, case_id)
    if row.status not in CASE_EDITABLE: raise HTTPException(409, "Resolved or closed mentoring cases cannot be referred")
    if not body.reason.strip(): raise HTTPException(422, "A referral reason is required")
    department = s.query(D.Department).get(staff.dept_id)
    hod_staff = s.query(D.StaffMember).get(department.hod_person_id) if department else None
    if not hod_staff or not hod_staff.user_id: raise HTTPException(409, "No HOD is configured for this department")
    row.status = "referred"; row.referred_to_office = "hod"; row.referred_to_user_id = hod_staff.user_id; row.referred_at = datetime.utcnow(); row.updated_at = datetime.utcnow()
    s.add(D.MentoringNote(id=uid(), tenant_id=TENANT, case_id=row.id, author_user_id=ctx["sub"], author_name=_mentoring_actor(s, ctx), note_type="referral", content=body.reason.strip()))
    s.commit(); notify(s, hod_staff.user_id, "Mentoring case referred", f"{staff.name} referred a {row.risk_level} risk case for review.", severity="action")
    write_audit(s, ctx["sub"], _mentoring_actor(s, ctx), ctx["office_n"], "mentoring.case.refer", f"mentoring:{row.id}", "open", "referred", body.reason.strip())
    return {"case": _case_payload(s, row)}


@router.post("/faculty/mentoring-cases/{case_id}/close")
def close_mentoring_case(case_id: str, action: str, ctx=Depends(auth), s=Depends(db)):
    row, _, _ = _mentor_case_or_403(s, ctx, case_id)
    if action not in {"resolve", "close"}: raise HTTPException(422, "Action must be resolve or close")
    if row.status in {"resolved", "closed"}: raise HTTPException(409, "Mentoring case is already finalized")
    before = row.status; row.status = "resolved" if action == "resolve" else "closed"; row.resolved_at = datetime.utcnow() if action == "resolve" else row.resolved_at; row.closed_at = datetime.utcnow() if action == "close" else row.closed_at; row.updated_at = datetime.utcnow()
    s.add(D.MentoringNote(id=uid(), tenant_id=TENANT, case_id=row.id, author_user_id=ctx["sub"], author_name=_mentoring_actor(s, ctx), note_type=action, content=f"Case {action}d by mentor."))
    s.commit(); write_audit(s, ctx["sub"], _mentoring_actor(s, ctx), ctx["office_n"], f"mentoring.case.{action}", f"mentoring:{row.id}", before, row.status, "")
    return {"case": _case_payload(s, row)}


@router.get("/faculty/academic-risk")
def faculty_academic_risk(ctx=Depends(auth), s=Depends(db)):
    staff = _staff_or_404(s, ctx)
    _require_associate_feature(s, ctx, staff, "academic_risk")
    student_ids = [row.student_id for row in s.query(D.MentorAssignment).filter(
        D.MentorAssignment.faculty_id == staff.id, D.MentorAssignment.status == "active").all()]
    students = [s.query(D.Student).get(student_id) for student_id in student_ids]
    return {"students": [payload for student in students if student for payload in [_mentee_with_indicators(s, student)] if payload["risk"] == "attention"]}


@router.get("/faculty/course-coordination")
def faculty_course_coordination(ctx=Depends(auth), s=Depends(db)):
    staff = _staff_or_404(s, ctx)
    _require_associate_feature(s, ctx, staff, "course_coordination")
    scopes = {row.scope_ref for row in _active_functional_roles(s, staff) if row.role_key.lower() == "course_coordinator" and row.scope_type == "section"}
    sections = s.query(D.Section).filter(D.Section.id.in_(scopes)).all() if scopes else []
    courses = {row.id: row for row in s.query(D.Course).all()}
    return {"sections": [{"id": row.id, "course_code": courses.get(row.course_id).code if courses.get(row.course_id) else "", "title": courses.get(row.course_id).title if courses.get(row.course_id) else "", "section": row.section_code, "term": row.term} for row in sections]}


@router.get("/faculty/course-registrations")
def faculty_course_registrations(ctx=Depends(auth), s=Depends(db)):
    staff = _staff_or_404(s, ctx)
    _require_associate_feature(s, ctx, staff, "course_registrations")
    advisee_ids = [row.student_id for row in s.query(D.MentorAssignment).filter(D.MentorAssignment.faculty_id == staff.id, D.MentorAssignment.status == "active").all()]
    rows = s.query(D.Enrollment).filter(D.Enrollment.student_id.in_(advisee_ids), D.Enrollment.status == "requested").all() if advisee_ids else []
    students = {row.id: row for row in s.query(D.Student).filter(D.Student.id.in_(advisee_ids)).all()} if advisee_ids else {}
    sections = {row.id: row for row in s.query(D.Section).filter(D.Section.id.in_([item.section_id for item in rows])).all()} if rows else {}
    courses = {row.id: row for row in s.query(D.Course).all()}
    return {"registrations": [{"id": row.id, "student": students.get(row.student_id).name if students.get(row.student_id) else "", "roll_no": students.get(row.student_id).roll_no if students.get(row.student_id) else "", "section": f"{courses.get(sections.get(row.section_id).course_id).code if sections.get(row.section_id) and courses.get(sections.get(row.section_id).course_id) else 'Course'} {sections.get(row.section_id).section_code if sections.get(row.section_id) else ''}".strip(), "status": row.status} for row in rows]}
