"""Department-scoped presentation endpoints for the Head of Department portal.

These endpoints deliberately do not create a second approval workflow.  They
only present records that the existing specialist workflow routing has assigned
to the authenticated HOD.
"""
import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, StrictInt, field_validator
from sqlalchemy import func, or_

import domain_models as D
from core import db, notify, uid, write_audit
from database import TENANT, office
from domain_api import auth
from hod_scope import hod_department
from hod_dashboard_api import hod_dashboard_data
from campus_leadership import (PRINCIPAL_OFFICE_N, VICE_PRINCIPAL_OFFICE_N,
                                 DEAN_ACADEMICS_OFFICE_N, DEAN_ADMINISTRATION_OFFICE_N,
                                 hod_campus, resolve_academic_dean,
                                 resolve_administration_dean, resolve_campus_leader,
                                 resolve_staffing_reviewers, resolve_student_affairs_dean,
                                 STAFFING_REVIEW_STAGES, DEAN_STUDENT_AFFAIRS_OFFICE_N)
from teaching import ACTIVE_ALLOCATION_STATUSES
from faculty_api import (_correction_payload, _correction_reviewer, _leave_dates,
                         _leave_overlap, _leave_payload, _leave_reviewer,
                         _marks_reviewer, _marks_submission_payload,
                         LEAVE_ACTIVE_STATUSES)
from models import Approval, AuditLog, User, WorkflowInstance


router = APIRouter(prefix="/api/portal/hod")
leadership_router = APIRouter(prefix="/api/portal/leadership")
logger = logging.getLogger(__name__)


def _resolved_hod_department(s, ctx):
    department = hod_department(s, ctx)
    if not department:
        raise HTTPException(403, "Only the configured department HOD can access this portal")
    return department


def _active_allocations_query(s, department_id):
    today = date.today()
    return (s.query(D.TeachingAllocation)
            .join(D.Section, D.TeachingAllocation.section_id == D.Section.id)
            .filter(D.Section.dept_id == department_id,
                    D.TeachingAllocation.status.in_(ACTIVE_ALLOCATION_STATUSES),
                    or_(D.TeachingAllocation.effective_from == None,
                        D.TeachingAllocation.effective_from <= today),
                    or_(D.TeachingAllocation.effective_to == None,
                        D.TeachingAllocation.effective_to >= today)))


def _actionable_reviews(s, ctx, department):
    """Use the specialist workflows' existing current-reviewer rules.

    Each source query is constrained to the resolved department before the
    current-reviewer helper is evaluated.  This avoids institution-wide fetches
    followed by Python filtering.
    """
    marks = []
    assessments = (s.query(D.Assessment)
                   .join(D.Section, D.Assessment.section_id == D.Section.id)
                   .filter(D.Section.dept_id == department.id,
                           D.Assessment.marks_state.in_({"submitted", "under_review"}),
                           D.Assessment.workflow_instance_id.isnot(None))
                   .order_by(D.Assessment.marks_submitted_at.desc()).all())
    for assessment in assessments:
        workflow = s.query(WorkflowInstance).get(assessment.workflow_instance_id)
        if workflow and _marks_reviewer(s, assessment, workflow.current_stage) == ctx["sub"]:
            marks.append({"kind": "marks", "id": assessment.id, "payload": _marks_submission_payload(s, assessment)})

    corrections = []
    correction_rows = (s.query(D.AttendanceCorrectionRequest)
                       .join(D.Section, D.AttendanceCorrectionRequest.section_id == D.Section.id)
                       .filter(D.Section.dept_id == department.id,
                               D.AttendanceCorrectionRequest.status.in_({"submitted", "under_review"}))
                       .order_by(D.AttendanceCorrectionRequest.updated_at.desc()).all())
    for row in correction_rows:
        workflow = s.query(WorkflowInstance).get(row.workflow_instance_id)
        if workflow and _correction_reviewer(s, row, workflow.current_stage) == ctx["sub"]:
            corrections.append({"kind": "attendance_correction", "id": row.id, "payload": _correction_payload(s, row)})

    leave = []
    leave_rows = (s.query(D.LeaveRequest)
                   .join(D.StaffMember, D.LeaveRequest.staff_id == D.StaffMember.id)
                   .join(WorkflowInstance, D.LeaveRequest.workflow_instance_id == WorkflowInstance.id)
                   .filter(D.StaffMember.dept_id == department.id,
                           D.LeaveRequest.status.in_({"submitted", "resubmitted", "under_review"}),
                           WorkflowInstance.process_key == "faculty_leave")
                  .order_by(D.LeaveRequest.updated_at.desc()).all())
    for row in leave_rows:
        workflow = s.query(WorkflowInstance).get(row.workflow_instance_id)
        if workflow and _leave_reviewer(s, row, workflow.current_stage) == ctx["sub"]:
            leave.append({"kind": "faculty_leave", "id": row.id, "payload": _leave_payload(s, row)})

    mentoring = []
    case_rows = (s.query(D.MentoringCase)
                 .filter(D.MentoringCase.department_id == department.id,
                         D.MentoringCase.referred_to_office == "hod",
                         D.MentoringCase.referred_to_user_id == ctx["sub"],
                         D.MentoringCase.status == "referred")
                 .order_by(D.MentoringCase.updated_at.desc()).all())
    for case in case_rows:
        # A referral is an inbox notification, not a HOD decision workflow.  Do
        # not use the faculty case serializer here: even its list form contains
        # a mentoring summary and action plan that are not needed in a generic
        # review queue.
        student = s.get(D.Student, case.student_id)
        mentoring.append({
            "kind": "mentoring_referral", "id": case.id,
            "payload": {
                "student": {
                    "id": student.id if student else case.student_id,
                    "name": student.name if student else "Student",
                    "roll_no": student.roll_no if student else "",
                },
                "status": case.status,
                "referred_at": case.referred_at.isoformat() if case.referred_at else "",
                "updated_at": case.updated_at.isoformat() if case.updated_at else "",
                "actionability": "view_only",
            },
        })
    return {"marks": marks, "attendance_corrections": corrections, "faculty_leave": leave, "mentoring_referrals": mentoring}


def _review_counts(reviews):
    return {
        "marks_pending": len(reviews["marks"]),
        "attendance_corrections_pending": len(reviews["attendance_corrections"]),
        "leave_pending": len(reviews["faculty_leave"]),
        "mentoring_referrals_pending": len(reviews["mentoring_referrals"]),
        "total_pending": sum(len(rows) for rows in reviews.values()),
    }


@router.get("/reviews")
def hod_reviews(kind: str = "all", ctx=Depends(auth), s=Depends(db)):
    department = _resolved_hod_department(s, ctx)
    if kind not in {"all", "marks", "attendance_corrections", "faculty_leave", "mentoring_referrals"}:
        raise HTTPException(422, "Choose all, marks, attendance_corrections, faculty_leave, or mentoring_referrals")
    categories = _actionable_reviews(s, ctx, department)
    rows = [item for values in categories.values() for item in values] if kind == "all" else categories[kind]
    return {"department": {"id": department.id, "code": department.code, "name": department.name},
            "reviews": rows, "counts": _review_counts(categories)}


# These are deliberately limited to workflow families where an HOD can make an
# actual persisted decision.  Mentoring referrals remain view-only and are not
# Approval records, while HOD-originated requests belong in requester tracking.
_HOD_PROCESSED_REVIEW_TYPES = {"faculty_leave", "attendance_correction", "marks_submission"}


def _processed_review_stage(process_key, workflow):
    """Return presentation-only stage labels; routing remains in specialist APIs."""
    if workflow.state in {"approved", "rejected", "cancelled", "returned"}:
        return "Final decision" if workflow.state in {"approved", "rejected"} else workflow.state.replace("_", " ").title()
    labels = {
        "faculty_leave": {1: "HOD Review", 2: "Vice Principal Review", 3: "Principal Review"},
        "attendance_correction": {1: "Class Coordinator Review", 2: "HOD Review", 3: "Vice Principal Review"},
        "marks_submission": {1: "Evaluation Coordinator Review", 2: "HOD Review", 3: "Controller of Exams Review"},
    }
    return labels.get(process_key, {}).get(workflow.current_stage, "Current review")


def _processed_review_record(s, approval, department):
    """Resolve one HOD decision to its scoped domain record and safe metadata.

    Never use a broad workflow record as authority: the domain query below is
    what proves the processed decision belongs to the authenticated HOD's
    present department scope.
    """
    workflow = s.get(WorkflowInstance, approval.workflow_id)
    if not workflow or workflow.process_key not in _HOD_PROCESSED_REVIEW_TYPES:
        return None
    row = None
    workflow_type = workflow.process_key
    if workflow_type == "faculty_leave":
        row = (s.query(D.LeaveRequest).join(D.StaffMember, D.LeaveRequest.staff_id == D.StaffMember.id)
               .filter(D.LeaveRequest.workflow_instance_id == workflow.id,
                       D.StaffMember.dept_id == department.id).one_or_none())
        if not row:
            return None
        requester = row.staff_name or "Faculty member"
        subject = f"{row.kind or 'Faculty'} leave · {row.from_date.isoformat()} to {row.to_date.isoformat()}"
        status = row.status
    elif workflow_type == "attendance_correction":
        row = (s.query(D.AttendanceCorrectionRequest).join(D.Section, D.AttendanceCorrectionRequest.section_id == D.Section.id)
               .filter(D.AttendanceCorrectionRequest.workflow_instance_id == workflow.id,
                       D.Section.dept_id == department.id).one_or_none())
        if not row:
            return None
        student = s.get(D.Student, row.student_id)
        requester = workflow.initiator_name or "Faculty member"
        subject = f"Attendance correction · {student.name if student else 'Student'}"
        status = row.status
    else:  # marks_submission
        row = (s.query(D.Assessment).join(D.Section, D.Assessment.section_id == D.Section.id)
               .filter(D.Assessment.workflow_instance_id == workflow.id,
                       D.Section.dept_id == department.id).one_or_none())
        if not row:
            return None
        requester = workflow.initiator_name or "Faculty member"
        subject = row.name or "Marks submission"
        status = row.marks_state

    decision = (approval.decision or "").lower()
    final = workflow.state in {"approved", "rejected", "cancelled"}
    return {
        "id": approval.id,
        "workflow_id": workflow.id,
        "domain_id": row.id,
        "workflow_type": workflow_type,
        "requester": requester,
        "subject": subject,
        "decision": decision,
        # This is the HOD's own persisted decision comment, not a source-record
        # narrative.  Welfare and mentoring are never serialized here.
        "decision_reason": approval.reason or "",
        "decision_at": approval.created_at.isoformat() if approval.created_at else "",
        "decision_stage": approval.stage_label or "HOD Review",
        "resulting_stage": _processed_review_stage(workflow_type, workflow),
        "status": status or workflow.state,
        "workflow_state": workflow.state,
        "final": final,
    }


@router.get("/processed-reviews")
def hod_processed_reviews(ctx=Depends(auth), s=Depends(db)):
    """Read-only history of decisions actually recorded by this HOD.

    `Approval.actor_id`, not initiator ownership or current reviewer state, is
    the sole actor predicate.  Each row then has to pass its own department
    source query in `_processed_review_record`.
    """
    department = _resolved_hod_department(s, ctx)
    approvals = (s.query(Approval).join(WorkflowInstance, Approval.workflow_id == WorkflowInstance.id)
                 .filter(Approval.actor_id == ctx["sub"],
                         WorkflowInstance.process_key.in_(_HOD_PROCESSED_REVIEW_TYPES))
                 .order_by(Approval.created_at.desc(), Approval.id.desc()).all())
    rows = [item for approval in approvals if (item := _processed_review_record(s, approval, department))]
    counts = {
        "approved": sum(item["decision"] in {"approve", "approved", "allow"} for item in rows),
        "returned": sum(item["decision"] == "return" for item in rows),
        "rejected": sum(item["decision"] in {"reject", "rejected", "deny"} for item in rows),
    }
    return {"department": {"id": department.id, "code": department.code, "name": department.name},
            "processed": rows, "counts": counts}


@router.get("/faculty-workload")
def hod_faculty_workload(q: str = "", designation: str = "", ctx=Depends(auth), s=Depends(db)):
    department = _resolved_hod_department(s, ctx)
    query = s.query(D.StaffMember).filter(D.StaffMember.dept_id == department.id, D.StaffMember.status == "active")
    if q.strip():
        like = f"%{q.strip()}%"; query = query.filter(D.StaffMember.name.ilike(like) | D.StaffMember.emp_id.ilike(like))
    if designation.strip(): query = query.filter(D.StaffMember.designation == designation.strip())
    allocations = _active_allocations_query(s, department.id).all()
    by_faculty = {}
    for row in allocations: by_faculty.setdefault(row.faculty_id, []).append(row)
    rows = []
    for staff in query.order_by(D.StaffMember.name).all():
        assigned = by_faculty.get(staff.id, [])
        section_ids = {row.section_id for row in assigned}; course_ids = {row.course_id for row in assigned}
        mentoring = s.query(D.MentorAssignment).filter(D.MentorAssignment.faculty_id == staff.id, D.MentorAssignment.status == "active").count()
        functions = s.query(D.FacultyFunctionalAssignment).filter(D.FacultyFunctionalAssignment.faculty_id == staff.id, D.FacultyFunctionalAssignment.status == "active").all()
        rows.append({"id": staff.id, "name": staff.name, "employee_id": staff.emp_id, "designation": staff.designation,
                     "department": department.code, "active_courses": len(course_ids), "active_sections": len(section_ids),
                     "active_allocations": len(assigned), "workload_units": round(sum(float(row.workload_units or 0) for row in assigned), 2),
                     "mentoring_load": mentoring, "functional_assignments": [row.role_key for row in functions], "workload_status": None})
    return {"department": {"id": department.id, "code": department.code, "name": department.name}, "faculty": rows,
            "workload_status_deferred": "No institutional workload threshold is configured."}


@router.get("/programs-courses")
def hod_programs_courses(q: str = "", ctx=Depends(auth), s=Depends(db)):
    department = _resolved_hod_department(s, ctx)
    programs = s.query(D.Program).filter(D.Program.dept_id == department.id).order_by(D.Program.code).all()
    query = s.query(D.Course).filter(D.Course.dept_id == department.id)
    if q.strip():
        like = f"%{q.strip()}%"; query = query.filter(D.Course.code.ilike(like) | D.Course.title.ilike(like))
    courses = query.order_by(D.Course.code).all()
    return {"department": {"id": department.id, "code": department.code, "name": department.name},
            "programs": [{"id": row.id, "code": row.code, "name": row.name, "level": row.level,
                          "duration_years": row.duration_years} for row in programs],
            "courses": [{"id": row.id, "program_id": row.program_id or "", "code": row.code, "title": row.title,
                         "credits": row.credits, "semester": row.semester, "status": row.status,
                         "course_type": row.course_type or "", "ltp": row.ltp or "",
                         "prerequisite": row.prerequisite or "", "regulation": row.regulation or "",
                         "section_count": s.query(D.Section).filter(D.Section.course_id == row.id).count()} for row in courses]}


@router.get("/sections")
def hod_sections(ctx=Depends(auth), s=Depends(db)):
    department = _resolved_hod_department(s, ctx)
    active_ids = {row.section_id for row in _active_allocations_query(s, department.id).all()}
    sections = s.query(D.Section).filter(D.Section.dept_id == department.id).order_by(D.Section.term, D.Section.section_code).all()
    course_map = {row.id: row for row in s.query(D.Course).filter(D.Course.id.in_([section.course_id for section in sections])).all()} if sections else {}
    enrollment_counts = dict(s.query(D.Enrollment.section_id, func.count(D.Enrollment.id))
                             .filter(D.Enrollment.section_id.in_([section.id for section in sections]), D.Enrollment.status == "enrolled")
                             .group_by(D.Enrollment.section_id).all()) if sections else {}
    timetable_by_section = {}
    if sections:
        entries = (s.query(D.TimetableEntry)
                   .filter(D.TimetableEntry.section_id.in_([section.id for section in sections]),
                           D.TimetableEntry.status == "active",
                           or_(D.TimetableEntry.effective_from.is_(None), D.TimetableEntry.effective_from <= date.today()),
                           or_(D.TimetableEntry.effective_to.is_(None), D.TimetableEntry.effective_to >= date.today()))
                   .order_by(D.TimetableEntry.day_of_week, D.TimetableEntry.start_time).all())
        for entry in entries:
            timetable_by_section.setdefault(entry.section_id, []).append({"id": entry.id, "day_of_week": entry.day_of_week,
                "start_time": entry.start_time, "end_time": entry.end_time, "room": entry.room or "", "building": entry.building or "", "status": entry.status})
    rows = []
    for section in sections:
        course = course_map.get(section.course_id)
        timetable = timetable_by_section.get(section.id, [])
        rows.append({"id": section.id, "course_id": section.course_id, "course_code": course.code if course else "", "course_title": course.title if course else "",
                      "term": section.term, "section": section.section_code,
                      "student_count": enrollment_counts.get(section.id, 0),
                      "active": section.id in active_ids,
                     "timetable_entries": len(timetable), "timetable": timetable, "conflicts": None})
    return {"department": {"id": department.id, "code": department.code, "name": department.name}, "sections": rows}


@router.get("/students")
def hod_students(course_id: str = "", section_id: str = "", q: str = "", semester: int = 0,
                 status: str = "", ctx=Depends(auth), s=Depends(db)):
    """Return a register only for an authenticated HOD's selected course-section.

    Course and section choices are shared academic metadata.  Membership is
    always resolved from active Enrollment rows, rather than Student's cohort
    section or a department-wide list filtered in the browser.
    """
    department = _resolved_hod_department(s, ctx)
    courses = (s.query(D.Course)
               .filter(D.Course.dept_id == department.id)
               .order_by(D.Course.code).all())
    course_rows = [{"id": row.id, "code": row.code, "title": row.title,
                    "semester": row.semester, "program_id": row.program_id or ""}
                   for row in courses]
    response = {"department": {"id": department.id, "code": department.code, "name": department.name},
                "courses": course_rows, "sections": [], "students": []}
    if not course_id:
        return response

    course = next((row for row in courses if row.id == course_id), None)
    if not course:
        raise HTTPException(404, "Selected course is not available in your department")
    sections = (s.query(D.Section)
                .filter(D.Section.dept_id == department.id, D.Section.course_id == course.id)
                .order_by(D.Section.term, D.Section.section_code).all())
    response["sections"] = [{"id": row.id, "section": row.section_code, "term": row.term or ""} for row in sections]
    if not section_id:
        return response

    selected_section = next((row for row in sections if row.id == section_id), None)
    if not selected_section:
        raise HTTPException(422, "Selected section does not belong to the selected course")

    query = (s.query(D.Student)
             .join(D.Enrollment, D.Enrollment.student_id == D.Student.id)
             .filter(D.Student.dept_id == department.id,
                     D.Enrollment.section_id == selected_section.id,
                     D.Enrollment.status == "enrolled"))
    if q.strip():
        like = f"%{q.strip()}%"; query = query.filter(D.Student.name.ilike(like) | D.Student.roll_no.ilike(like))
    if semester:
        query = query.filter(D.Student.semester == semester)
    if status:
        query = query.filter(D.Student.status == status)
    students = query.distinct().order_by(D.Student.roll_no).all()
    student_ids = [student.id for student in students]
    enrollment_by_student = {}
    if student_ids:
        enrollment_rows = (s.query(D.Enrollment, D.Section, D.Course)
                           .join(D.Section, D.Enrollment.section_id == D.Section.id)
                           .join(D.Course, D.Section.course_id == D.Course.id)
                           .filter(D.Enrollment.student_id.in_(student_ids),
                                   D.Enrollment.status == "enrolled",
                                   D.Section.dept_id == department.id)
                           .order_by(D.Course.code, D.Section.section_code).all())
        for enrollment, section_row, enrollment_course in enrollment_rows:
            enrollment_by_student.setdefault(enrollment.student_id, []).append({
                "id": enrollment.id, "section_id": section_row.id, "course_code": enrollment_course.code,
                "course_title": enrollment_course.title, "section": section_row.section_code,
                "term": section_row.term or "",
            })
    program_map = {program.id: program for program in s.query(D.Program).filter(D.Program.dept_id == department.id).all()}
    rows = []
    for student in students:
        records = s.query(D.AttendanceRecord).filter(D.AttendanceRecord.student_id == student.id).all()
        pct = round(100 * sum(1 for record in records if record.present) / len(records), 1) if records else None
        latest = {}
        for result in s.query(D.StudentSubjectResult).filter(D.StudentSubjectResult.student_id == student.id).order_by(D.StudentSubjectResult.attempt).all(): latest[result.subject_code] = result
        backlogs = sum(1 for result in latest.values() if result.outcome == "failed")
        program = program_map.get(student.program_id)
        active_enrollments = enrollment_by_student.get(student.id, [])
        rows.append({"id": student.id, "roll_no": student.roll_no, "name": student.name, "program": program.name if program else "Not available",
                      "program_id": student.program_id or "", "program_code": program.code if program else "", "batch": student.batch or "",
                      "semester": student.semester, "study_year": (student.semester + 1) // 2 if student.semester else None,
                      "section": student.section, "status": student.status,
                      "cgpa": student.cgpa, "attendance_pct": pct, "backlogs": backlogs,
                      "active_enrollment_count": len(active_enrollments), "enrollments": active_enrollments,
                      "risk_codes": [code for code, _, condition in [("attendance", "Attendance below 75%", pct is not None and pct < 75), ("academic", "CGPA below 6.50", student.cgpa is not None and student.cgpa < 6.5), ("backlog", "Published backlog", backlogs > 0)] if condition],
                      "risk_indicators": [label for _, label, condition in [("attendance", "Attendance below 75%", pct is not None and pct < 75), ("academic", "CGPA below 6.50", student.cgpa is not None and student.cgpa < 6.5), ("backlog", "Published backlog", backlogs > 0)] if condition]})
    response["selection"] = {"course_id": course.id, "course_code": course.code,
                             "course_title": course.title, "section_id": selected_section.id,
                             "section": selected_section.section_code, "term": selected_section.term or ""}
    response["student_count"] = len(rows)
    response["students"] = rows
    return response


@router.get("/attendance-monitoring")
def hod_attendance_monitoring(ctx=Depends(auth), s=Depends(db)):
    department = _resolved_hod_department(s, ctx)
    allocations = _active_allocations_query(s, department.id).all()
    allocation_by_section = {row.section_id: row for row in allocations}
    active_ids = set(allocation_by_section)
    sections = s.query(D.Section).filter(D.Section.dept_id == department.id).all()
    section_ids = [section.id for section in sections]
    courses = {course.id: course for course in s.query(D.Course).filter(D.Course.id.in_([section.course_id for section in sections])).all()} if sections else {}
    sessions = (s.query(D.ClassSession).filter(D.ClassSession.section_id.in_(section_ids)).order_by(D.ClassSession.session_date.desc(), D.ClassSession.scheduled_start.desc()).all()) if section_ids else []
    records = s.query(D.AttendanceRecord).filter(D.AttendanceRecord.section_id.in_(section_ids)).all() if section_ids else []
    sessions_by_section, records_by_section, record_count_by_session = {}, {}, {}
    for session in sessions:
        sessions_by_section.setdefault(session.section_id, []).append(session)
    for record in records:
        records_by_section.setdefault(record.section_id, []).append(record)
        if record.class_session_id:
            record_count_by_session[record.class_session_id] = record_count_by_session.get(record.class_session_id, 0) + 1
    enrollment_counts = dict(s.query(D.Enrollment.section_id, func.count(D.Enrollment.id))
                             .filter(D.Enrollment.section_id.in_(section_ids), D.Enrollment.status == "enrolled")
                             .group_by(D.Enrollment.section_id).all()) if section_ids else {}
    faculty_ids = {row.faculty_id for row in allocations} | {row.faculty_id for row in sessions if row.faculty_id}
    faculty_map = {staff.id: staff.name for staff in s.query(D.StaffMember).filter(D.StaffMember.id.in_(faculty_ids)).all()} if faculty_ids else {}
    section_rows = []
    for section in sections:
        section_sessions = sessions_by_section.get(section.id, [])
        finalized_records = [record for record in records_by_section.get(section.id, []) if record.finalized_at]
        student_finalized_records = {}
        for record in finalized_records:
            student_finalized_records.setdefault(record.student_id, []).append(record)
        students_below_threshold = sum(1 for student_records in student_finalized_records.values()
                                       if 100 * sum(1 for record in student_records if record.present) / len(student_records) < 75)
        course = courses.get(section.course_id)
        allocation = allocation_by_section.get(section.id)
        section_rows.append({"section_id": section.id, "course_code": course.code if course else "", "section": section.section_code,
                              "course_title": course.title if course else "", "term": section.term or "",
                              "faculty": faculty_map.get(allocation.faculty_id, "Not assigned") if allocation else "Not assigned",
                              "active": section.id in active_ids, "sessions_total": len(section_sessions),
                              "sessions_scheduled": sum(1 for row in section_sessions if row.status == "scheduled"),
                              "sessions_conducted": sum(1 for row in section_sessions if row.checked_in_at),
                              "attendance_pending": sum(1 for row in section_sessions if row.checked_in_at and not row.finalized_at),
                              "attendance_finalized": sum(1 for row in section_sessions if row.finalized_at),
                              "today_attendance_pending": sum(1 for row in section_sessions if row.session_date == date.today() and row.checked_in_at and not row.finalized_at),
                              "today_attendance_finalized": sum(1 for row in section_sessions if row.session_date == date.today() and row.finalized_at),
                              "finalized_record_count": len(finalized_records),
                              "students_below_75": students_below_threshold,
                              "attendance_pct": round(100 * sum(1 for row in finalized_records if row.present) / len(finalized_records), 1) if finalized_records else None})
    department_students = s.query(D.Student).filter(D.Student.dept_id == department.id).order_by(D.Student.roll_no).all()
    student_map = {student.id: student for student in department_students}
    student_records = {}
    for record in records:
        if record.student_id in student_map and record.finalized_at:
            student_records.setdefault(record.student_id, []).append(record)
    program_map = {program.id: program for program in s.query(D.Program).filter(D.Program.dept_id == department.id).all()}
    student_rows = []
    for student in department_students:
        finalized = student_records.get(student.id, [])
        present = sum(1 for record in finalized if record.present)
        attendance_pct = round(100 * present / len(finalized), 1) if finalized else None
        program = program_map.get(student.program_id)
        student_rows.append({"id": student.id, "roll_no": student.roll_no, "name": student.name,
                             "program": program.name if program else "Not available", "semester": student.semester,
                             "section": student.section, "attendance_pct": attendance_pct,
                             "sessions_attended": present, "sessions_considered": len(finalized)})
    session_rows = []
    section_map = {section.id: section for section in sections}
    for session in sessions:
        section = section_map.get(session.section_id)
        course = courses.get(section.course_id) if section else None
        session_rows.append({"id": session.id, "section_id": session.section_id, "course_code": course.code if course else "",
                             "course_title": course.title if course else "", "section": section.section_code if section else "",
                             "session_date": session.session_date.isoformat() if session.session_date else None,
                             "scheduled_start": session.scheduled_start.isoformat() if session.scheduled_start else None,
                             "scheduled_end": session.scheduled_end.isoformat() if session.scheduled_end else None,
                             "faculty": faculty_map.get(session.faculty_id, "Not assigned"), "status": session.status,
                             "checked_in": bool(session.checked_in_at), "finalized": bool(session.finalized_at),
                             "attendance_record_count": record_count_by_session.get(session.id, 0),
                             "active_roster_count": enrollment_counts.get(session.section_id, 0)})
    return {"department": {"id": department.id, "code": department.code, "name": department.name}, "sections": section_rows, "sessions": session_rows, "students": student_rows}


@router.get("/at-risk-students")
def hod_at_risk_students(q: str = "", ctx=Depends(auth), s=Depends(db)):
    department = _resolved_hod_department(s, ctx)
    query = s.query(D.Student).filter(D.Student.dept_id == department.id, D.Student.status == "active")
    if q.strip():
        like = f"%{q.strip()}%"; query = query.filter(D.Student.name.ilike(like) | D.Student.roll_no.ilike(like))
    rows = []
    for student in query.order_by(D.Student.roll_no).all():
        attendance = s.query(D.AttendanceRecord).filter(D.AttendanceRecord.student_id == student.id).all()
        pct = round(100 * sum(1 for row in attendance if row.present) / len(attendance), 1) if attendance else None
        latest = {}
        for result in s.query(D.StudentSubjectResult).filter(D.StudentSubjectResult.student_id == student.id).order_by(D.StudentSubjectResult.attempt).all(): latest[result.subject_code] = result
        backlog_count = sum(1 for row in latest.values() if row.outcome == "failed")
        marks = s.query(D.Mark).filter(D.Mark.student_id == student.id, D.Mark.is_valid == True, D.Mark.status == "published").all()
        assessments = {row.id: row for row in s.query(D.Assessment).filter(D.Assessment.id.in_([mark.assessment_id for mark in marks])).all()} if marks else {}
        values = [100 * mark.score / assessments[mark.assessment_id].max_marks for mark in marks if assessments.get(mark.assessment_id) and assessments[mark.assessment_id].max_marks]
        average = round(sum(values) / len(values), 1) if values else None
        risk_checks = [("attendance", "Attendance below 75%", pct is not None and pct < 75),
                       ("academic", "CGPA below 6.50", student.cgpa is not None and student.cgpa < 6.5),
                       ("backlog", "Published backlog", backlog_count > 0),
                       ("assessment", "Assessment average below 50%", average is not None and average < 50)]
        reasons = [label for _, label, enabled in risk_checks if enabled]
        risk_codes = [code for code, _, enabled in risk_checks if enabled]
        if not reasons: continue
        referral = (s.query(D.MentoringCase)
                    .filter(D.MentoringCase.student_id == student.id,
                            D.MentoringCase.department_id == department.id,
                            D.MentoringCase.referred_to_office == "hod",
                            D.MentoringCase.referred_to_user_id == ctx["sub"],
                            D.MentoringCase.status == "referred")
                    .order_by(D.MentoringCase.updated_at.desc()).first())
        program = s.query(D.Program).get(student.program_id) if student.program_id else None
        rows.append({"id": student.id, "name": student.name, "roll_no": student.roll_no,
                     "program": program.name if program else "Not available", "program_id": student.program_id or "",
                     "semester": student.semester, "section": student.section, "attendance_pct": pct,
                     "cgpa": student.cgpa, "backlog_count": backlog_count, "assessment_average": average,
                     "risk_codes": risk_codes, "risk_reasons": reasons,
                     "mentoring_referral": {"status": referral.status,
                                             "referred_at": referral.referred_at.isoformat() if referral.referred_at else ""} if referral else None})
    return {"department": {"id": department.id, "code": department.code, "name": department.name}, "students": rows}


@router.get("/examinations")
def hod_examinations(ctx=Depends(auth), s=Depends(db)):
    department = _resolved_hod_department(s, ctx)
    rows = (s.query(D.Assessment).join(D.Section, D.Assessment.section_id == D.Section.id)
            .filter(D.Section.dept_id == department.id).order_by(D.Assessment.scheduled_at).all())
    reviews = _actionable_reviews(s, ctx, department)["marks"]
    awaiting_hod_ids = {item["id"] for item in reviews}
    out = []
    for assessment in rows:
        section = s.get(D.Section, assessment.section_id)
        course = s.get(D.Course, section.course_id) if section else None
        schedule = (s.query(D.ExamScheduleEntry)
                    .filter(D.ExamScheduleEntry.assessment_id == assessment.id,
                            D.ExamScheduleEntry.is_active == True)
                    .order_by(D.ExamScheduleEntry.version_no.desc(), D.ExamScheduleEntry.updated_at.desc()).first())
        on_date = assessment.scheduled_at.date() if assessment.scheduled_at else date.today()
        allocation = (s.query(D.TeachingAllocation)
                      .filter(D.TeachingAllocation.section_id == assessment.section_id,
                              D.TeachingAllocation.course_id == (course.id if course else ""),
                              D.TeachingAllocation.status.in_(ACTIVE_ALLOCATION_STATUSES),
                              or_(D.TeachingAllocation.effective_from == None, D.TeachingAllocation.effective_from <= on_date),
                              or_(D.TeachingAllocation.effective_to == None, D.TeachingAllocation.effective_to >= on_date))
                      .order_by(D.TeachingAllocation.is_coordinator.desc(), D.TeachingAllocation.created_at.desc()).first())
        faculty = s.get(D.StaffMember, allocation.faculty_id) if allocation else None
        schedule_ready = bool(schedule and schedule.start_at and schedule.status in {"scheduled", "rescheduled", "completed"})
        marks_state = assessment.marks_state or "draft"
        out.append({
            "id": assessment.id, "assessment": assessment.name, "assessment_type": assessment.assessment_type or "",
            "course_code": course.code if course else "", "course_title": course.title if course else "",
            "section": section.section_code if section else "", "term": section.term if section else "",
            "scheduled_at": schedule.start_at.isoformat() if schedule and schedule.start_at else "",
            "scheduled_end": schedule.end_at.isoformat() if schedule and schedule.end_at else "",
            "schedule_status": schedule.status if schedule else "not_scheduled", "venue": schedule.venue if schedule else "",
            "mode": schedule.mode if schedule else "", "schedule_ready": schedule_ready,
            "faculty": faculty.name if faculty else "", "faculty_assigned": bool(faculty),
            "marks_state": marks_state, "marks_submitted": marks_state in {"submitted", "under_review", "published"},
            "published": bool(assessment.published), "awaiting_hod": assessment.id in awaiting_hod_ids,
        })
    total = len(out)
    scheduled = sum(row["schedule_ready"] for row in out)
    faculty_covered = sum(row["faculty_assigned"] for row in out)
    marks_submitted = sum(row["marks_submitted"] for row in out)
    attention = []
    for row in out:
        if not row["schedule_ready"]:
            attention.append({"type": "schedule", "assessment": row["assessment"], "course_code": row["course_code"], "section": row["section"], "message": "No active scheduled timetable entry", "target": "hod_exams"})
        if not row["faculty_assigned"]:
            attention.append({"type": "faculty", "assessment": row["assessment"], "course_code": row["course_code"], "section": row["section"], "message": "No active teaching allocation for this assessment date", "target": "hod_allocations"})
        if row["marks_state"] in {"draft", "returned"}:
            attention.append({"type": "marks", "assessment": row["assessment"], "course_code": row["course_code"], "section": row["section"], "message": "Marks are not currently submitted for review", "target": "hod_exams"})
        if row["awaiting_hod"]:
            attention.append({"type": "review", "assessment": row["assessment"], "course_code": row["course_code"], "section": row["section"], "message": "Marks are currently awaiting HOD review", "target": "hod_reviews_marks"})
    return {
        "department": {"id": department.id, "code": department.code, "name": department.name, "campus": department.campus or ""},
        "exams": out,
        "summary": {"assessments": total, "scheduled_papers": scheduled, "unscheduled_papers": total - scheduled,
                    "faculty_covered": faculty_covered, "marks_submitted": marks_submitted,
                    "marks_pending": total - marks_submitted, "hod_reviews_pending": len(reviews)},
        "readiness": {"timetable": {"numerator": scheduled, "denominator": total},
                      "faculty": {"numerator": faculty_covered, "denominator": total},
                      "marks_submission": {"numerator": marks_submitted, "denominator": total}},
        "attention": attention,
    }


@router.get("/reports")
def hod_reports(ctx=Depends(auth), s=Depends(db)):
    # The dashboard aggregation is the single source of truth for shared HOD
    # definitions.  Call its service helper, never a route handler.
    dashboard = hod_dashboard_data(s, ctx)
    return {
        "department": dashboard["department"],
        "kpis": dashboard["kpis"],
        "readiness": dashboard["readiness"],
        "reviews": dashboard["reviews"],
        "operations": dashboard["operations"],
        "student_health": dashboard["student_health"],
        "attention": dashboard["attention"],
    }


def _audit_refs(prefix, ids):
    return [f"{prefix}:{row_id}" for row_id in ids]


def _department_audit_query(s, department):
    """Build an AuditLog query from direct department-owned entity references.

    AuditLog has no department key and its reason field is not safe to expose.
    This deliberately narrows each source record in SQL before using its stable
    entity reference in the AuditLog query.  Generic workflow and approval
    histories are excluded: their scope is not independently authoritative and
    would duplicate the same actions already represented by AuditLog.
    """
    allocation_refs = _audit_refs("allocation", [row.id for row in
        s.query(D.TeachingAllocation.id).join(D.Section, D.TeachingAllocation.section_id == D.Section.id)
        .filter(D.Section.dept_id == department.id).all()])
    session_refs = _audit_refs("session", [row.id for row in
        s.query(D.ClassSession.id).join(D.Section, D.ClassSession.section_id == D.Section.id)
        .filter(D.Section.dept_id == department.id).all()])
    correction_refs = _audit_refs("correction", [row.id for row in
        s.query(D.AttendanceCorrectionRequest.id).join(D.Section, D.AttendanceCorrectionRequest.section_id == D.Section.id)
        .filter(D.Section.dept_id == department.id).all()])
    assessment_refs = _audit_refs("assessment", [row.id for row in
        s.query(D.Assessment.id).join(D.Section, D.Assessment.section_id == D.Section.id)
        .filter(D.Section.dept_id == department.id).all()])
    leave_refs = _audit_refs("leave", [row.id for row in
        s.query(D.LeaveRequest.id).join(D.StaffMember, D.LeaveRequest.staff_id == D.StaffMember.id)
        .filter(D.StaffMember.dept_id == department.id).all()])
    mentoring_refs = _audit_refs("mentoring", [row.id for row in
        s.query(D.MentoringCase.id).filter(D.MentoringCase.department_id == department.id).all()])
    curriculum_refs = _audit_refs("curriculum_request", [row.id for row in
        s.query(D.CurriculumRequest.id).filter(D.CurriculumRequest.department_id == department.id).all()])
    resource_refs = _audit_refs("department_resource_request", [row.id for row in
        s.query(D.DepartmentResourceRequest.id).filter(D.DepartmentResourceRequest.department_id == department.id).all()])
    staffing_refs = _audit_refs("staffing_request", [row.id for row in
        s.query(D.StaffingRequest.id).filter(D.StaffingRequest.department_id == department.id).all()])
    welfare_refs = _audit_refs("student_welfare_escalation", [row.id for row in
        s.query(D.StudentWelfareEscalation.id).filter(D.StudentWelfareEscalation.department_id == department.id).all()])
    hod_staff = s.query(D.StaffMember).filter(D.StaffMember.id == department.hod_person_id).one_or_none()
    profile_refs = _audit_refs("staff", [hod_staff.id]) if hod_staff else []
    conditions = []
    if allocation_refs: conditions.append(AuditLog.entity.in_(allocation_refs) & AuditLog.action.like("allocation.%"))
    if session_refs: conditions.append(AuditLog.entity.in_(session_refs) & AuditLog.action.in_({"class_session.check_in", "attendance.finalize"}))
    if correction_refs: conditions.append(AuditLog.entity.in_(correction_refs) & AuditLog.action.like("attendance.correction.%"))
    if assessment_refs: conditions.append(AuditLog.entity.in_(assessment_refs) & AuditLog.action.in_({"marks.submit", "marks.review"}))
    if leave_refs: conditions.append(AuditLog.entity.in_(leave_refs) & (AuditLog.action.like("leave.%") | AuditLog.action.like("hod_leave.%")))
    # Follow-up/note audit records are excluded even though the case is scoped.
    if mentoring_refs: conditions.append(AuditLog.entity.in_(mentoring_refs) & (AuditLog.action == "mentoring.case.refer"))
    if curriculum_refs: conditions.append(AuditLog.entity.in_(curriculum_refs) & AuditLog.action.like("curriculum_request.%"))
    if resource_refs: conditions.append(AuditLog.entity.in_(resource_refs) & AuditLog.action.like("department_resource_request.%"))
    if staffing_refs: conditions.append(AuditLog.entity.in_(staffing_refs) & AuditLog.action.like("staffing_request.%"))
    if welfare_refs: conditions.append(AuditLog.entity.in_(welfare_refs) & AuditLog.action.like("student_welfare_escalation.%"))
    if profile_refs: conditions.append(AuditLog.entity.in_(profile_refs) & (AuditLog.action == "hod.profile.update"))
    return s.query(AuditLog).filter(or_(*conditions)) if conditions else s.query(AuditLog).filter(AuditLog.id == -1)


def _department_audit_type(row):
    if row.entity.startswith("allocation:"): return "teaching_allocation"
    if row.entity.startswith("session:"): return "attendance"
    if row.entity.startswith("correction:"): return "attendance_correction"
    if row.entity.startswith("assessment:"): return "marks"
    if row.entity.startswith("leave:"): return "hod_leave" if row.action.startswith("hod_leave.") else "faculty_leave"
    if row.entity.startswith("mentoring:"): return "mentoring_referral"
    if row.entity.startswith("curriculum_request:"): return "curriculum_request"
    if row.entity.startswith("department_resource_request:"): return "resource_request"
    if row.entity.startswith("staffing_request:"): return "staffing_request"
    if row.entity.startswith("student_welfare_escalation:"): return "student_welfare"
    return "profile"


def _department_audit_payload(row):
    office_name = office(row.office_n or 0).get("name") or f"Office {row.office_n or 'not recorded'}"
    return {
        "id": row.id, "timestamp": row.created_at.isoformat() if row.created_at else "",
        "actor": row.actor_name or "Recorded actor", "actor_office": office_name,
        "event_type": _department_audit_type(row), "action": row.action,
        "resource": row.entity.split(":", 1)[0].replace("_", " ").title(),
        "reference_id": row.entity.split(":", 1)[1] if ":" in row.entity else row.entity,
        "result": row.new_state or "Recorded",
    }


@router.get("/department-audit")
def hod_department_audit(event_type: str = "", action: str = "", actor: str = "", search: str = "",
                         from_date: date | None = None, to_date: date | None = None,
                         page: int = 1, page_size: int = 25, ctx=Depends(auth), s=Depends(db)):
    department = _resolved_hod_department(s, ctx)
    if page < 1 or page_size < 1 or page_size > 100: raise HTTPException(422, "Page must be positive and page_size must be between 1 and 100")
    if from_date and to_date and from_date > to_date: raise HTTPException(422, "From date cannot be after to date")
    query = _department_audit_query(s, department)
    if event_type.strip():
        allowed = {"teaching_allocation", "attendance", "attendance_correction", "marks", "faculty_leave", "hod_leave", "mentoring_referral", "curriculum_request", "resource_request", "staffing_request", "student_welfare", "profile"}
        if event_type not in allowed: raise HTTPException(422, "Unknown department audit event type")
        # Type is inferred from a scoped entity/action pair; keep this filter in SQL.
        prefixes = {"teaching_allocation": "allocation:", "attendance": "session:", "attendance_correction": "correction:", "marks": "assessment:", "mentoring_referral": "mentoring:", "curriculum_request": "curriculum_request:", "resource_request": "department_resource_request:", "staffing_request": "staffing_request:", "student_welfare": "student_welfare_escalation:", "profile": "staff:"}
        if event_type in {"faculty_leave", "hod_leave"}:
            query = query.filter(AuditLog.entity.like("leave:%"), AuditLog.action.like("hod_leave.%") if event_type == "hod_leave" else AuditLog.action.like("leave.%"))
        else: query = query.filter(AuditLog.entity.like(f"{prefixes[event_type]}%"))
    if action.strip(): query = query.filter(AuditLog.action == action.strip())
    if actor.strip(): query = query.filter(AuditLog.actor_name.ilike(f"%{actor.strip()}%"))
    if search.strip():
        like = f"%{search.strip()}%"; query = query.filter(AuditLog.actor_name.ilike(like) | AuditLog.action.ilike(like) | AuditLog.entity.ilike(like) | AuditLog.new_state.ilike(like))
    if from_date: query = query.filter(AuditLog.created_at >= datetime.combine(from_date, datetime.min.time()))
    if to_date: query = query.filter(AuditLog.created_at <= datetime.combine(to_date, datetime.max.time()))
    total = query.count()
    rows = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"department": {"id": department.id, "code": department.code, "name": department.name},
            "events": [_department_audit_payload(row) for row in rows],
            "pagination": {"page": page, "page_size": page_size, "total": total},
            "filters": {"event_types": ["teaching_allocation", "attendance", "attendance_correction", "marks", "faculty_leave", "hod_leave", "mentoring_referral", "curriculum_request", "resource_request", "staffing_request", "student_welfare", "profile"]}}


@router.get("/department-audit/{event_id}")
def hod_department_audit_event(event_id: int, ctx=Depends(auth), s=Depends(db)):
    department = _resolved_hod_department(s, ctx)
    row = _department_audit_query(s, department).filter(AuditLog.id == event_id).one_or_none()
    if not row: raise HTTPException(403, "This department audit event is not available")
    return {"event": _department_audit_payload(row)}


@router.get("/research-iqac")
def hod_research_iqac(ctx=Depends(auth), s=Depends(db)):
    """Return the safe, read-only research snapshot for the HOD's department.

    Research projects are department-visible only through their authoritative
    staff owner.  Legacy projects without an owner, and every draft/proposed
    item, are deliberately excluded rather than guessed into a department.
    There is no departmental IQAC/evidence domain or authoritative office-9
    reviewer assignment yet, so IQAC submissions are explicitly unavailable.
    """
    department = _resolved_hod_department(s, ctx)
    visible_project_statuses = {"active", "ongoing", "completed", "closed"}
    project_rows = (s.query(D.ResearchProject, D.StaffMember)
                    .join(D.StaffMember, D.ResearchProject.owner_id == D.StaffMember.id)
                    .filter(D.StaffMember.dept_id == department.id,
                            D.ResearchProject.status.in_(visible_project_statuses))
                    .order_by(D.ResearchProject.updated_at.desc()).all())
    publication_rows = (s.query(D.ResearchPublication, D.StaffMember)
                        .join(D.StaffMember, D.ResearchPublication.owner_id == D.StaffMember.id)
                        .filter(D.StaffMember.dept_id == department.id,
                                D.ResearchPublication.status == "published")
                        .order_by(D.ResearchPublication.publication_date.desc(),
                                  D.ResearchPublication.updated_at.desc()).all())
    project_owner_ids = {project.owner_id for project, _ in project_rows if project.owner_id}
    publication_owner_ids = {publication.owner_id for publication, _ in publication_rows if publication.owner_id}
    return {
        "department": {"id": department.id, "code": department.code, "name": department.name,
                       "campus": department.campus or ""},
        "research": {
            "summary": {
                "projects": len(project_rows),
                "active_projects": sum(1 for project, _ in project_rows if project.status in {"active", "ongoing"}),
                "published_publications": len(publication_rows),
                "participating_faculty": len(project_owner_ids | publication_owner_ids),
            },
            # Do not expose summaries, progress notes, milestones, grant data,
            # draft/proposed records, authorship, or publication identifiers.
            "projects": [{
                "id": project.id, "title": project.title, "category": project.category or "",
                "status": project.status, "start_date": project.start_date.isoformat() if project.start_date else "",
                "expected_end_date": project.expected_end_date.isoformat() if project.expected_end_date else "",
                "faculty_name": staff.name,
            } for project, staff in project_rows],
            "publications": [{
                "id": publication.id, "title": publication.title,
                "publication_type": publication.publication_type or "",
                "venue": publication.venue or "",
                "publication_date": publication.publication_date.isoformat() if publication.publication_date else "",
                "faculty_name": staff.name,
            } for publication, staff in publication_rows],
        },
        "iqac": {
            "available": False,
            "message": "IQAC records and submissions are not available because no department IQAC domain or authoritative reviewer routing is configured.",
        },
        "submissions": {
            "available": False,
            "message": "Research and IQAC submissions are unavailable until an authoritative Dean R&D/IQAC routing model is configured.",
        },
    }


@router.get("/department-planning")
def hod_department_planning(semester: int = 0, ctx=Depends(auth), s=Depends(db)):
    """A read-only, department-scoped readiness view.

    Courses and sections do not have a reliable relation to AcademicYear/Semester
    records.  The optional filter therefore uses the persisted Course.semester
    (and the matching Student.semester), not an inferred "current" period.
    """
    if semester < 0:
        raise HTTPException(422, "Semester must be a positive stored semester value")
    department = _resolved_hod_department(s, ctx)
    course_query = s.query(D.Course).filter(D.Course.dept_id == department.id)
    if semester:
        course_query = course_query.filter(D.Course.semester == semester)
    courses = course_query.order_by(D.Course.code).all()
    course_ids = [row.id for row in courses]
    programs = {row.id: row for row in s.query(D.Program).filter(D.Program.dept_id == department.id).all()}
    sections = (s.query(D.Section)
                .filter(D.Section.dept_id == department.id,
                        D.Section.course_id.in_(course_ids))
                .order_by(D.Section.term, D.Section.section_code).all()) if course_ids else []
    section_ids = [row.id for row in sections]
    allocations = (_active_allocations_query(s, department.id)
                   .filter(D.TeachingAllocation.section_id.in_(section_ids)).all()) if section_ids else []
    allocation_by_section = {row.section_id: row for row in allocations}
    timetable_counts = dict(s.query(D.TimetableEntry.section_id, func.count(D.TimetableEntry.id))
                            .filter(D.TimetableEntry.section_id.in_(section_ids),
                                    D.TimetableEntry.status == "active")
                            .group_by(D.TimetableEntry.section_id).all()) if section_ids else {}
    enrollment_counts = dict(s.query(D.Enrollment.section_id, func.count(D.Enrollment.id))
                             .filter(D.Enrollment.section_id.in_(section_ids),
                                     D.Enrollment.status == "enrolled")
                             .group_by(D.Enrollment.section_id).all()) if section_ids else {}
    staff = (s.query(D.StaffMember)
             .filter(D.StaffMember.dept_id == department.id, D.StaffMember.status == "active")
             .order_by(D.StaffMember.name).all())
    faculty_by_id = {row.id: row for row in staff}
    sections_by_course = {}
    for row in sections:
        sections_by_course.setdefault(row.course_id, []).append(row)
    attention = []
    course_rows = []
    for course in courses:
        course_sections = sections_by_course.get(course.id, [])
        section_rows = []
        if not course_sections and str(course.status or "").lower() == "active":
            attention.append({"kind": "course_without_section", "course_id": course.id,
                              "label": f"{course.code} has no stored section", "view": "hod_courses"})
        for row in course_sections:
            allocation = allocation_by_section.get(row.id)
            timetable_entries = int(timetable_counts.get(row.id, 0))
            if not allocation:
                attention.append({"kind": "section_without_faculty", "section_id": row.id, "course_id": course.id,
                                  "label": f"{course.code} / Section {row.section_code} has no current faculty allocation", "view": "hod_allocations"})
            if not timetable_entries:
                attention.append({"kind": "section_without_timetable", "section_id": row.id, "course_id": course.id,
                                  "label": f"{course.code} / Section {row.section_code} has no active timetable entry", "view": "hod_sections"})
            section_rows.append({"id": row.id, "section": row.section_code, "term": row.term or "",
                                 "faculty_id": allocation.faculty_id if allocation else "",
                                 "faculty": faculty_by_id.get(allocation.faculty_id).name if allocation and faculty_by_id.get(allocation.faculty_id) else "",
                                 "has_current_faculty": bool(allocation), "active_timetable_entries": timetable_entries,
                                 "enrolled_students": int(enrollment_counts.get(row.id, 0))})
        program = programs.get(course.program_id)
        course_rows.append({"id": course.id, "code": course.code, "title": course.title,
                            "program_id": course.program_id or "", "program": {"id": program.id, "code": program.code, "name": program.name} if program else None, "semester": course.semester,
                            "credits": course.credits, "status": course.status, "sections": section_rows})
    allocated_faculty_ids = {row.faculty_id for row in allocations}
    students_query = s.query(D.Student).filter(D.Student.dept_id == department.id, D.Student.status == "active")
    if semester:
        students_query = students_query.filter(D.Student.semester == semester)
    active_students = students_query.count()
    faculty_rows = []
    for row in staff:
        assigned = [allocation for allocation in allocations if allocation.faculty_id == row.id]
        faculty_rows.append({"id": row.id, "name": row.name, "employee_id": row.emp_id,
                             "designation": row.designation, "active_allocations": len(assigned),
                             "active_sections": len({allocation.section_id for allocation in assigned}),
                             "workload_units": round(sum(float(allocation.workload_units or 0) for allocation in assigned), 2)})
    sections_with_faculty = sum(1 for row in sections if row.id in allocation_by_section)
    sections_with_timetable = sum(1 for row in sections if timetable_counts.get(row.id, 0))
    return {"department": {"id": department.id, "code": department.code, "name": department.name},
            "period": {"semester": semester or None, "label": f"Semester {semester}" if semester else "All stored semesters",
                       "available_semesters": sorted({row.semester for row in s.query(D.Course).filter(D.Course.dept_id == department.id).all() if row.semester is not None}),
                       "stored_terms": sorted({row.term for row in s.query(D.Section).filter(D.Section.dept_id == department.id).all() if row.term})},
            "summary": {"courses": len(courses), "active_courses": sum(1 for row in courses if str(row.status or "").lower() == "active"),
                        "sections": len(sections), "sections_with_faculty": sections_with_faculty,
                        "sections_without_faculty": len(sections) - sections_with_faculty,
                        "sections_with_timetable": sections_with_timetable,
                        "sections_without_timetable": len(sections) - sections_with_timetable,
                        "active_faculty": len(staff), "allocated_faculty": len(allocated_faculty_ids),
                        "unallocated_faculty": max(0, len(staff) - len(allocated_faculty_ids)),
                        "active_allocations": len(allocations), "active_students": active_students,
                        "attention_count": len(attention)},
            "courses": course_rows, "faculty": faculty_rows, "attention": attention,
            "mode": "read_only"}


def _hod_profile_payload(s, ctx):
    department = _resolved_hod_department(s, ctx)
    staff = s.query(D.StaffMember).filter(D.StaffMember.user_id == ctx["sub"]).one()
    from models import User
    user = s.query(User).get(ctx["sub"])
    return {"profile": {"name": staff.name, "employee_id": staff.emp_id, "designation": staff.designation,
                         "leadership_role": "Head of Department" if department.hod_person_id == staff.id else "",
                          "department": department.name, "campus": staff.campus, "email": staff.email,
                          "phone": staff.phone, "office_hours": staff.office_hours,
                          "date_joined": staff.date_joined.isoformat() if staff.date_joined else "",
                         "status": staff.status, "username": user.username if user else "",
                         "office": user.role if user and user.role else "Head of Department"}}


@router.get("/profile")
def hod_profile(ctx=Depends(auth), s=Depends(db)):
    return _hod_profile_payload(s, ctx)


@router.get("/my-requests")
def hod_my_requests(ctx=Depends(auth), s=Depends(db)):
    """Consolidated register of domain requests submitted by this HOD only.

    This is deliberately not a generic WorkflowInstance search: reviewer-owned
    work remains in My Reviews, and welfare narratives never enter this list.
    Each row is backed by one of the authoritative HOD request models.
    """
    department = _resolved_hod_department(s, ctx)
    staff = s.query(D.StaffMember).filter(D.StaffMember.user_id == ctx["sub"]).one_or_none()
    rows = []

    def item(kind, row_id, subject, subject_meta, workflow, submitted_at, updated_at,
             stage_label, reviewer):
        state = workflow.state if workflow else ""
        pending = state in {"submitted", "under_review"}
        rows.append({
            "id": row_id, "kind": kind, "subject": subject, "subject_meta": subject_meta,
            "status": state, "current_stage": workflow.current_stage if workflow else 0,
            "stage_label": stage_label if pending else "Completed",
            "current_reviewer": reviewer if pending else "",
            "submitted_at": submitted_at.isoformat() if submitted_at else "",
            "updated_at": updated_at.isoformat() if updated_at else "",
        })

    curriculum = (s.query(D.CurriculumRequest).join(WorkflowInstance, D.CurriculumRequest.workflow_instance_id == WorkflowInstance.id)
                  .filter(D.CurriculumRequest.requester_user_id == ctx["sub"],
                          D.CurriculumRequest.department_id == department.id,
                          WorkflowInstance.process_key == "curriculum_request").all())
    for row in curriculum:
        workflow = s.get(WorkflowInstance, row.workflow_instance_id)
        program = s.get(D.Program, row.program_id)
        course = s.get(D.Course, row.course_id) if row.course_id else None
        context = f"{course.code} · {course.title}" if course else (program.name if program else "Department program")
        item("curriculum", row.id, f"Curriculum · {row.request_type.replace('_', ' ')}", context,
             workflow, row.created_at, row.updated_at, CURRICULUM_STAGE_NAME, CURRICULUM_STAGE_NAME)

    resources = (s.query(D.DepartmentResourceRequest).join(WorkflowInstance, D.DepartmentResourceRequest.workflow_instance_id == WorkflowInstance.id)
                 .filter(D.DepartmentResourceRequest.requester_user_id == ctx["sub"],
                         D.DepartmentResourceRequest.department_id == department.id,
                         WorkflowInstance.process_key == "department_resource_request").all())
    for row in resources:
        workflow = s.get(WorkflowInstance, row.workflow_instance_id)
        item("resource", row.id, row.title, row.category.replace('_', ' '), workflow,
             row.created_at, row.updated_at, RESOURCE_STAGE_NAME, RESOURCE_STAGE_NAME)

    staffing = (s.query(D.StaffingRequest).join(WorkflowInstance, D.StaffingRequest.workflow_instance_id == WorkflowInstance.id)
                .filter(D.StaffingRequest.requester_user_id == ctx["sub"],
                        D.StaffingRequest.department_id == department.id,
                        WorkflowInstance.process_key == "staffing_request").all())
    for row in staffing:
        workflow = s.get(WorkflowInstance, row.workflow_instance_id)
        stage = workflow.current_stage if workflow else 0
        stage_name = STAFFING_REVIEW_STAGES.get(stage, "Completed")
        item("staffing", row.id, row.designation_or_role, row.request_type.replace('_', ' '), workflow,
             row.created_at, row.updated_at, stage_name, stage_name)

    welfare = (s.query(D.StudentWelfareEscalation).join(WorkflowInstance, D.StudentWelfareEscalation.workflow_instance_id == WorkflowInstance.id)
               .filter(D.StudentWelfareEscalation.requester_user_id == ctx["sub"],
                       D.StudentWelfareEscalation.department_id == department.id,
                       WorkflowInstance.process_key == "student_welfare_escalation").all())
    for row in welfare:
        workflow = s.get(WorkflowInstance, row.workflow_instance_id)
        student = _welfare_student_identity(s, row.student_id)
        # Explicit metadata boundary: do not put summary/reason/history on this row.
        item("welfare", row.id, student["name"], f"{student['roll_no']} · {row.concern_type.replace('_', ' ')}",
             workflow, row.created_at, row.updated_at, WELFARE_STAGE_NAME, WELFARE_STAGE_NAME)

    leaves = (s.query(D.LeaveRequest).join(WorkflowInstance, D.LeaveRequest.workflow_instance_id == WorkflowInstance.id)
              .filter(D.LeaveRequest.requested_by == ctx["sub"], WorkflowInstance.process_key == "hod_leave").all())
    for row in leaves:
        workflow = s.get(WorkflowInstance, row.workflow_instance_id)
        stage = workflow.current_stage if workflow else 0
        stage_name = HOD_LEAVE_STAGE_NAMES.get(stage, "Completed")
        item("hod_leave", row.id, f"HOD leave · {row.kind}",
             f"{row.from_date.isoformat()} to {row.to_date.isoformat()}", workflow,
             row.submitted_at, row.updated_at, stage_name, stage_name)

    rows.sort(key=lambda row: (row["updated_at"], row["submitted_at"]), reverse=True)
    return {"department": {"id": department.id, "code": department.code, "name": department.name,
                           "campus": department.campus or ""},
            "hod_name": staff.name if staff else "Head of Department", "requests": rows[:100]}


class HodSelfProfileUpdate(BaseModel):
    """The self-service contact allowlist; employment and authority data is immutable here."""
    model_config = ConfigDict(extra="forbid")
    email: str | None = None
    phone: str | None = None
    office_hours: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        if value is None:
            return value
        clean = value.strip().lower()
        if clean and ("@" not in clean or clean.startswith("@") or clean.endswith("@")):
            raise ValueError("Enter a valid email address")
        return clean

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value):
        if value is None:
            return value
        clean = value.strip()
        digits = "".join(character for character in clean if character.isdigit())
        if clean and (len(digits) < 7 or len(digits) > 20):
            raise ValueError("Enter a valid phone number")
        if clean and any(not (character.isdigit() or character in "+-() ") for character in clean):
            raise ValueError("Enter a valid phone number")
        return clean

    @field_validator("office_hours")
    @classmethod
    def validate_office_hours(cls, value):
        if value is None:
            return value
        clean = value.strip()
        if len(clean) > 250:
            raise ValueError("Office hours must be 250 characters or fewer")
        return clean


@router.put("/profile")
def update_hod_profile(body: HodSelfProfileUpdate, ctx=Depends(auth), s=Depends(db)):
    _resolved_hod_department(s, ctx)
    staff = s.query(D.StaffMember).filter(D.StaffMember.user_id == ctx["sub"]).one()
    before = {"email": staff.email or "", "phone": staff.phone or "", "office_hours": staff.office_hours or ""}
    changed_fields = []
    if body.email is not None and body.email != before["email"]:
        staff.email = body.email; changed_fields.append("email")
    if body.phone is not None and body.phone != before["phone"]:
        staff.phone = body.phone; changed_fields.append("phone")
    if body.office_hours is not None and body.office_hours != before["office_hours"]:
        staff.office_hours = body.office_hours; changed_fields.append("office_hours")
    if changed_fields:
        s.commit()
        write_audit(s, ctx["sub"], staff.name, ctx["office_n"], "hod.profile.update", f"staff:{staff.id}",
                    "Changed fields", ", ".join(changed_fields), "Updated self-service profile fields")
    return _hod_profile_payload(s, ctx)


@router.get("/digital-id")
def hod_digital_id(ctx=Depends(auth), s=Depends(db)):
    # Keep the card identity on the same authoritative StaffMember/Person path as
    # My Profile. The frontend uses the established faculty card field contract.
    profile = _hod_profile_payload(s, ctx)["profile"]
    employee_id = profile["employee_id"] or ""
    initials = "".join(part[:1] for part in (profile["name"] or "").split()[:2]).upper()
    return {"digital_id": {
        "full_name": profile["name"],
        "employee_id": employee_id,
        "designation": profile["designation"],
        "leadership_role": profile["leadership_role"],
        "department": profile["department"],
        "campus": profile["campus"],
        "avatar_initials": initials,
        "valid_until": "",
        "validity_label": "Not specified",
        # Preserve the existing non-sensitive staff-identity payload semantics.
        "verification_payload": f"ICMS:{employee_id}",
        "barcode_value": employee_id,
    }}


HOD_LEAVE_STAGE_NAMES = {1: "Vice Principal Review", 2: "Principal Review"}
HOD_LEAVE_MUTABLE_STATUSES = {"submitted", "under_review"}


class HodLeaveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    from_date: str
    to_date: str
    reason: str
    half_day: bool = False


class HodLeaveDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str
    comment: str = ""


CURRICULUM_REQUEST_TYPES = {
    "course_revision", "course_deactivation", "credit_change", "semester_change",
    "prerequisite_change", "syllabus_revision", "program_curriculum_change",
}
CURRICULUM_COURSE_TYPES = CURRICULUM_REQUEST_TYPES - {"program_curriculum_change"}
CURRICULUM_STAGE_NAME = "Dean Academics Review"
RESOURCE_REQUEST_CATEGORIES = {
    "lab_equipment", "classroom_equipment", "software_license", "it_equipment",
    "furniture", "maintenance_repair", "teaching_academic_resource",
    "department_infrastructure", "other_operational_resource",
}
RESOURCE_STAGE_NAME = "Dean Administration Review"
STAFFING_REQUEST_TYPES = {
    "faculty_requirement", "temporary_faculty", "technical_staff",
    "administrative_support", "other",
}
WELFARE_CONCERN_TYPES = {
    "academic_risk", "attendance_concern", "mentoring_concern",
    "behavioral_concern", "welfare_concern", "safety_concern",
    "grievance_referral", "other_student_support",
}
WELFARE_STAGE_NAME = "Dean Student Affairs Review"


class CurriculumRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_type: str
    program_id: str
    course_id: str = ""
    proposed_change: str
    rationale: str
    effective_semester: int | None = None


class CurriculumDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str
    comment: str = ""


class DepartmentResourceRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str
    title: str
    description: str
    quantity: int | None = None
    estimated_cost: float | None = None
    justification: str


class DepartmentResourceDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str
    comment: str = ""


class StaffingRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_type: str
    designation_or_role: str
    number_required: StrictInt
    required_by_date: date | None = None
    justification: str


class StaffingDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str
    comment: str = ""


class StudentWelfareEscalationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: str
    concern_type: str
    summary: str
    escalation_reason: str
    source_mentoring_case_id: str = ""


class StudentWelfareDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str
    comment: str = ""


def _hod_staff(s, ctx):
    department = _resolved_hod_department(s, ctx)
    staff = s.query(D.StaffMember).filter(D.StaffMember.user_id == ctx["sub"]).one_or_none()
    if not staff or staff.id != department.hod_person_id:
        raise HTTPException(403, "The authenticated user is not the configured HOD")
    return staff


def _hod_leave_reviewer(s, workflow):
    if workflow.current_stage == 1:
        return resolve_campus_leader(s, hod_campus_for_workflow(s, workflow).id, VICE_PRINCIPAL_OFFICE_N)
    if workflow.current_stage == 2:
        return resolve_campus_leader(s, hod_campus_for_workflow(s, workflow).id, PRINCIPAL_OFFICE_N)
    raise HTTPException(409, "Leave request is not awaiting a campus reviewer")


def hod_campus_for_workflow(s, workflow):
    row = s.query(D.LeaveRequest).filter(D.LeaveRequest.workflow_instance_id == workflow.id).one_or_none()
    staff = s.get(D.StaffMember, row.staff_id) if row else None
    department = s.get(D.Department, staff.dept_id) if staff else None
    campus_name = (department.campus or "").strip() if department else ""
    campuses = s.query(D.Campus).filter(D.Campus.name == campus_name, D.Campus.is_active == True).all() if campus_name else []
    if len(campuses) != 1:
        raise HTTPException(409, "The leave request campus routing is not configured")
    return campuses[0]


def _hod_leave_payload(s, row):
    workflow = s.get(WorkflowInstance, row.workflow_instance_id) if row.workflow_instance_id else None
    approvals = (s.query(Approval).filter(Approval.workflow_id == workflow.id).order_by(Approval.created_at).all()
                 if workflow else [])
    reviewer = ""
    stage = workflow.current_stage if workflow else 0
    if workflow and row.status in HOD_LEAVE_MUTABLE_STATUSES:
        reviewer = HOD_LEAVE_STAGE_NAMES.get(stage, "")
    return {
        "id": row.id, "workflow_instance_id": row.workflow_instance_id or "", "staff_id": row.staff_id,
        "staff": row.staff_name, "kind": row.kind, "from_date": row.from_date.isoformat(),
        "to_date": row.to_date.isoformat(), "days": row.days, "reason": row.reason,
        "status": row.status, "current_stage": stage,
        "stage_label": HOD_LEAVE_STAGE_NAMES.get(stage, "Completed" if row.status in {"approved", "rejected", "cancelled"} else ""),
        "current_reviewer": reviewer,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else "",
        "cancellable": row.status in HOD_LEAVE_MUTABLE_STATUSES,
        "history": [{"stage": item.stage, "stage_label": item.stage_label, "actor": item.actor_name,
                     "decision": item.decision, "reason": item.reason, "at": item.created_at.isoformat()}
                    for item in approvals],
    }


def _hod_leave_or_403(s, leave_id, ctx):
    row = s.get(D.LeaveRequest, leave_id)
    if not row or row.requested_by != ctx["sub"]:
        raise HTTPException(403, "This leave request does not belong to the authenticated HOD")
    workflow = s.get(WorkflowInstance, row.workflow_instance_id) if row.workflow_instance_id else None
    if not workflow or workflow.process_key != "hod_leave":
        raise HTTPException(404, "HOD leave request not found")
    return row, workflow


@router.get("/leave-requests")
def hod_leave_requests(ctx=Depends(auth), s=Depends(db)):
    _hod_staff(s, ctx)
    rows = (s.query(D.LeaveRequest).join(WorkflowInstance, D.LeaveRequest.workflow_instance_id == WorkflowInstance.id)
            .filter(D.LeaveRequest.requested_by == ctx["sub"], WorkflowInstance.process_key == "hod_leave")
            .order_by(D.LeaveRequest.updated_at.desc()).all())
    return {"leave_requests": [_hod_leave_payload(s, row) for row in rows]}


@router.get("/leave-requests/{leave_id}")
def hod_leave_request(leave_id: str, ctx=Depends(auth), s=Depends(db)):
    _hod_staff(s, ctx)
    row, _ = _hod_leave_or_403(s, leave_id, ctx)
    return {"leave_request": _hod_leave_payload(s, row)}


@router.post("/leave-requests")
def create_hod_leave(body: HodLeaveIn, ctx=Depends(auth), s=Depends(db)):
    staff = _hod_staff(s, ctx)
    # Complete all authority prechecks before adding any stateful row.
    campus = hod_campus(s, ctx)
    vp = resolve_campus_leader(s, campus.id, VICE_PRINCIPAL_OFFICE_N)
    resolve_campus_leader(s, campus.id, PRINCIPAL_OFFICE_N)
    start, end = _leave_dates(body)
    if _leave_overlap(s, staff.id, start, end):
        raise HTTPException(409, "An overlapping submitted or approved leave request already exists")
    checkpoint = "create_workflow"
    try:
        row = D.LeaveRequest(id=uid(), tenant_id=TENANT, staff_id=staff.id, staff_name=staff.name,
            kind=body.kind.strip(), from_date=start, to_date=end, days=(end - start).days + 1,
            reason=body.reason.strip(), status="submitted", requested_by=ctx["sub"], half_day=False,
            submitted_at=datetime.utcnow(), updated_at=datetime.utcnow())
        workflow = WorkflowInstance(id=uid(), tenant_id=TENANT, process_key="hod_leave", label="HOD Leave Request",
            office_n=10, title=f"HOD leave: {row.kind} {start.isoformat()} to {end.isoformat()}", state="submitted",
            initiator_id=ctx["sub"], initiator_name=staff.name, current_stage=1, scope_level="campus")
        s.add(row); s.add(workflow); s.flush(); row.workflow_instance_id = workflow.id
        write_audit(s, ctx["sub"], staff.name, ctx["office_n"], "hod_leave.submit", f"leave:{row.id}",
                    "draft", "submitted", row.reason, commit=False)
        s.commit()
    except HTTPException:
        s.rollback(); raise
    except Exception:
        s.rollback()
        raise HTTPException(409, "Leave request could not be submitted")
    notify(s, vp.id, "HOD leave review", f"{staff.name} submitted a {row.kind} leave request", severity="action")
    return {"leave_request": _hod_leave_payload(s, row)}


@router.post("/leave-requests/{leave_id}/cancel")
def cancel_hod_leave(leave_id: str, ctx=Depends(auth), s=Depends(db)):
    _hod_staff(s, ctx)
    row, workflow = _hod_leave_or_403(s, leave_id, ctx)
    if row.status not in HOD_LEAVE_MUTABLE_STATUSES:
        raise HTTPException(409, "This leave request cannot be cancelled")
    before = row.status; row.status = "cancelled"; row.updated_at = datetime.utcnow()
    workflow.state = "cancelled"; workflow.updated_at = datetime.utcnow()
    write_audit(s, ctx["sub"], row.staff_name, ctx["office_n"], "hod_leave.cancel", f"leave:{row.id}",
                before, "cancelled", "Cancelled by requester", commit=False)
    s.commit()
    return {"leave_request": _hod_leave_payload(s, row)}


def _leadership_hod_leave_or_403(s, leave_id, ctx):
    if ctx.get("office_n") not in {VICE_PRINCIPAL_OFFICE_N, PRINCIPAL_OFFICE_N}:
        raise HTTPException(403, "Only the routed campus leader can review this leave request")
    row = s.get(D.LeaveRequest, leave_id)
    workflow = s.get(WorkflowInstance, row.workflow_instance_id) if row and row.workflow_instance_id else None
    if not row or not workflow or workflow.process_key != "hod_leave":
        raise HTTPException(404, "HOD leave request not found")
    if row.status not in HOD_LEAVE_MUTABLE_STATUSES:
        raise HTTPException(409, "Leave request is not awaiting review")
    reviewer = _hod_leave_reviewer(s, workflow)
    if reviewer.id != ctx["sub"]:
        raise HTTPException(403, "You are not the eligible reviewer for the current leave stage")
    return row, workflow


@leadership_router.get("/hod-leave-requests")
def leadership_hod_leave_requests(ctx=Depends(auth), s=Depends(db)):
    if ctx.get("office_n") not in {VICE_PRINCIPAL_OFFICE_N, PRINCIPAL_OFFICE_N}:
        raise HTTPException(403, "Only campus Vice Principals and Principals can access this inbox")
    rows = (s.query(D.LeaveRequest).join(WorkflowInstance, D.LeaveRequest.workflow_instance_id == WorkflowInstance.id)
            .filter(WorkflowInstance.process_key == "hod_leave", D.LeaveRequest.status.in_(HOD_LEAVE_MUTABLE_STATUSES)).all())
    out = []
    for row in rows:
        workflow = s.get(WorkflowInstance, row.workflow_instance_id)
        try:
            if _hod_leave_reviewer(s, workflow).id == ctx["sub"]:
                out.append(_hod_leave_payload(s, row))
        except HTTPException:
            continue
    return {"leave_requests": out}


@leadership_router.post("/hod-leave-requests/{leave_id}/decide")
def decide_hod_leave(leave_id: str, body: HodLeaveDecisionIn, ctx=Depends(auth), s=Depends(db)):
    row, workflow = _leadership_hod_leave_or_403(s, leave_id, ctx)
    action = body.action.lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(422, "Choose approve or reject")
    if action == "reject" and not body.comment.strip():
        raise HTTPException(422, "A comment is required when rejecting leave")
    actor = s.get(User, ctx["sub"]); actor_name = actor.role if actor else "Campus reviewer"
    before = row.status; stage = workflow.current_stage
    s.add(Approval(id=uid(), tenant_id=TENANT, workflow_id=workflow.id, actor_id=ctx["sub"], actor_name=actor_name,
        stage=stage, stage_label=HOD_LEAVE_STAGE_NAMES[stage], decision=action.upper(), authority="FULL", reason=body.comment.strip()))
    if action == "reject":
        row.status = "rejected"; row.decided_by = actor_name; workflow.state = "rejected"
        notify(s, row.requested_by, "HOD leave rejected", body.comment.strip(), severity="info")
    elif stage == 1:
        workflow.current_stage = 2; workflow.state = "under_review"; row.status = "under_review"
        principal = _hod_leave_reviewer(s, workflow)
        notify(s, principal.id, "HOD leave review", f"{row.staff_name}'s leave request awaits your review", severity="action")
    else:
        row.status = "approved"; row.decided_by = actor_name; workflow.state = "approved"; workflow.current_stage = 3
        notify(s, row.requested_by, "HOD leave approved", "Your leave request received final approval.", severity="info")
    row.updated_at = datetime.utcnow(); workflow.updated_at = datetime.utcnow()
    write_audit(s, ctx["sub"], actor_name, ctx["office_n"], f"hod_leave.{action}", f"leave:{row.id}",
                before, row.status, body.comment.strip(), commit=False)
    s.commit()
    return {"leave_request": _hod_leave_payload(s, row)}


def _curriculum_payload(s, row):
    workflow = s.get(WorkflowInstance, row.workflow_instance_id)
    program = s.get(D.Program, row.program_id)
    course = s.get(D.Course, row.course_id) if row.course_id else None
    history = (s.query(Approval).filter(Approval.workflow_id == row.workflow_instance_id)
               .order_by(Approval.created_at).all())
    pending = workflow and workflow.state in {"submitted", "under_review"}
    return {"id": row.id, "workflow_instance_id": row.workflow_instance_id,
            "request_type": row.request_type, "program": {"id": program.id, "code": program.code, "name": program.name} if program else None,
            "course": {"id": course.id, "code": course.code, "title": course.title} if course else None,
            "proposed_change": row.proposed_change, "rationale": row.rationale,
            "effective_semester": row.effective_semester, "status": workflow.state if workflow else "",
            "current_stage": workflow.current_stage if workflow else 0,
            "stage_label": CURRICULUM_STAGE_NAME if pending else "Completed",
            "current_reviewer": CURRICULUM_STAGE_NAME if pending else "",
            "submitted_at": row.created_at.isoformat(),
            "history": [{"stage": item.stage, "stage_label": item.stage_label, "actor": item.actor_name,
                         "decision": item.decision, "reason": item.reason, "at": item.created_at.isoformat()} for item in history]}


def _curriculum_request_or_403(s, request_id, ctx):
    row = s.get(D.CurriculumRequest, request_id)
    workflow = s.get(WorkflowInstance, row.workflow_instance_id) if row else None
    if not row or not workflow or workflow.process_key != "curriculum_request":
        raise HTTPException(404, "Curriculum request not found")
    if row.requester_user_id != ctx["sub"]:
        raise HTTPException(403, "This curriculum request does not belong to the authenticated HOD")
    return row, workflow


@router.get("/curriculum-requests")
def hod_curriculum_requests(ctx=Depends(auth), s=Depends(db)):
    department = _resolved_hod_department(s, ctx)
    rows = (s.query(D.CurriculumRequest).join(WorkflowInstance, D.CurriculumRequest.workflow_instance_id == WorkflowInstance.id)
            .filter(D.CurriculumRequest.requester_user_id == ctx["sub"], D.CurriculumRequest.department_id == department.id,
                    WorkflowInstance.process_key == "curriculum_request").order_by(D.CurriculumRequest.updated_at.desc()).all())
    programs = s.query(D.Program).filter(D.Program.dept_id == department.id).order_by(D.Program.code).all()
    courses = s.query(D.Course).filter(D.Course.dept_id == department.id).order_by(D.Course.code).all()
    return {"department": {"id": department.id, "code": department.code, "name": department.name, "campus": department.campus or ""},
            "requests": [_curriculum_payload(s, row) for row in rows],
            "options": {"programs": [{"id": row.id, "code": row.code, "name": row.name} for row in programs],
                        "courses": [{"id": row.id, "program_id": row.program_id or "", "code": row.code, "title": row.title, "semester": row.semester} for row in courses],
                        "request_types": sorted(CURRICULUM_REQUEST_TYPES)}}


@router.get("/curriculum-requests/{request_id}")
def hod_curriculum_request(request_id: str, ctx=Depends(auth), s=Depends(db)):
    _hod_staff(s, ctx)
    row, _ = _curriculum_request_or_403(s, request_id, ctx)
    return {"request": _curriculum_payload(s, row)}


@router.post("/curriculum-requests")
def create_curriculum_request(body: CurriculumRequestIn, ctx=Depends(auth), s=Depends(db)):
    staff = _hod_staff(s, ctx)
    department = _resolved_hod_department(s, ctx)
    request_type = body.request_type.strip().lower()
    if request_type not in CURRICULUM_REQUEST_TYPES:
        raise HTTPException(422, "Choose a supported curriculum request type")
    if not body.proposed_change.strip() or not body.rationale.strip():
        raise HTTPException(422, "Proposed change and rationale are required")
    if body.effective_semester is not None and body.effective_semester < 1:
        raise HTTPException(422, "Effective semester must use a positive stored semester value")
    # Every precondition is completed before any persistent row is added.
    dean = resolve_academic_dean(s, ctx)
    program = s.get(D.Program, body.program_id)
    if not program or program.dept_id != department.id:
        raise HTTPException(403, "The selected program belongs to another department")
    course = s.get(D.Course, body.course_id) if body.course_id else None
    if request_type in CURRICULUM_COURSE_TYPES and not course:
        raise HTTPException(422, "This request type requires a department course")
    if course and (course.dept_id != department.id or course.program_id != program.id):
        raise HTTPException(403, "The selected course does not belong to the selected department program")
    if request_type == "program_curriculum_change" and body.course_id:
        raise HTTPException(422, "Program curriculum change must not select a course")
    checkpoint = "create_workflow"
    try:
        workflow = WorkflowInstance(id=uid(), tenant_id=TENANT, process_key="curriculum_request", label="Curriculum Request",
            office_n=DEAN_ACADEMICS_OFFICE_N, title=f"Curriculum request: {request_type.replace('_', ' ')}", state="submitted",
            initiator_id=ctx["sub"], initiator_name=staff.name, current_stage=1, scope_level="campus")
        row = D.CurriculumRequest(id=uid(), tenant_id=TENANT, requester_user_id=ctx["sub"], department_id=department.id,
            program_id=program.id, course_id=course.id if course else None, request_type=request_type,
            proposed_change=body.proposed_change.strip(), rationale=body.rationale.strip(), effective_semester=body.effective_semester,
            workflow_instance_id=workflow.id)
        # These models intentionally keep only scalar FK fields (no ORM
        # relationship), so persist the referenced workflow before flushing
        # the dependent domain request.  Both flushes remain in this one
        # transaction; neither is a commit.
        s.add(workflow)
        checkpoint = "flush_workflow"
        s.flush()
        s.add(row)
        checkpoint = "flush_curriculum_request"
        s.flush()
        checkpoint = "write_audit"
        write_audit(s, ctx["sub"], staff.name, ctx["office_n"], "curriculum_request.submit", f"curriculum_request:{row.id}",
                    "draft", "submitted", row.rationale, commit=False)
        checkpoint = "commit"
        s.commit()
    except HTTPException:
        s.rollback(); raise
    except Exception as exc:
        # The session must be reset before returning the public conflict response.
        s.rollback()
        original = getattr(exc, "orig", None) or getattr(exc, "__cause__", None) or exc
        diagnostics = getattr(original, "diag", None)
        logger.error(
            "curriculum_request.submit_failed process_key=curriculum_request checkpoint=%s "
            "department_id=%s program_id=%s course_id=%s error_type=%s sqlstate=%s constraint=%s",
            checkpoint, department.id, program.id, course.id if course else "", type(original).__name__,
            getattr(original, "pgcode", None), getattr(diagnostics, "constraint_name", None),
        )
        raise HTTPException(409, "Curriculum request could not be submitted")
    notify(s, dean.id, "Curriculum request review", f"{staff.name} submitted a curriculum request", severity="action")
    return {"request": _curriculum_payload(s, row)}


def _dean_curriculum_request_or_403(s, request_id, ctx):
    if ctx.get("office_n") != DEAN_ACADEMICS_OFFICE_N:
        raise HTTPException(403, "Only the routed Dean Academics can review curriculum requests")
    row = s.get(D.CurriculumRequest, request_id)
    workflow = s.get(WorkflowInstance, row.workflow_instance_id) if row else None
    if not row or not workflow or workflow.process_key != "curriculum_request":
        raise HTTPException(404, "Curriculum request not found")
    if workflow.state not in {"submitted", "under_review"} or workflow.current_stage != 1:
        raise HTTPException(409, "Curriculum request is no longer actionable")
    department = s.get(D.Department, row.department_id)
    campuses = s.query(D.Campus).filter(D.Campus.name == (department.campus if department else ""), D.Campus.is_active == True).all()
    if len(campuses) != 1:
        raise HTTPException(409, "Curriculum request campus routing is not configured")
    dean = resolve_campus_leader(s, campuses[0].id, DEAN_ACADEMICS_OFFICE_N)
    if dean.id != ctx["sub"]:
        raise HTTPException(403, "You are not the eligible Dean Academics reviewer")
    return row, workflow


@leadership_router.get("/curriculum-requests")
def dean_curriculum_requests(ctx=Depends(auth), s=Depends(db)):
    if ctx.get("office_n") != DEAN_ACADEMICS_OFFICE_N:
        raise HTTPException(403, "Only Dean Academics can access this inbox")
    rows = (s.query(D.CurriculumRequest).join(D.Department, D.CurriculumRequest.department_id == D.Department.id)
            .join(WorkflowInstance, D.CurriculumRequest.workflow_instance_id == WorkflowInstance.id)
            .filter(WorkflowInstance.process_key == "curriculum_request", WorkflowInstance.state.in_({"submitted", "under_review"})).all())
    out = []
    for row in rows:
        try:
            _dean_curriculum_request_or_403(s, row.id, ctx); out.append(_curriculum_payload(s, row))
        except HTTPException:
            continue
    return {"requests": out}


@leadership_router.post("/curriculum-requests/{request_id}/decide")
def decide_curriculum_request(request_id: str, body: CurriculumDecisionIn, ctx=Depends(auth), s=Depends(db)):
    row, workflow = _dean_curriculum_request_or_403(s, request_id, ctx)
    action = body.action.strip().lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(422, "Choose approve or reject")
    if action == "reject" and not body.comment.strip():
        raise HTTPException(422, "A comment is required when rejecting a curriculum request")
    actor = s.get(User, ctx["sub"]); actor_name = actor.role if actor else "Dean Academics"
    before = workflow.state
    s.add(Approval(id=uid(), tenant_id=TENANT, workflow_id=workflow.id, actor_id=ctx["sub"], actor_name=actor_name,
                  stage=1, stage_label=CURRICULUM_STAGE_NAME, decision=action.upper(), authority="FULL", reason=body.comment.strip()))
    workflow.state = "approved" if action == "approve" else "rejected"; workflow.current_stage = 2; workflow.updated_at = datetime.utcnow()
    write_audit(s, ctx["sub"], actor_name, ctx["office_n"], f"curriculum_request.{action}", f"curriculum_request:{row.id}",
                before, workflow.state, body.comment.strip(), commit=False)
    s.commit()
    notify(s, row.requester_user_id, f"Curriculum request {workflow.state}", body.comment.strip() or "Dean Academics recorded a decision.", severity="info")
    return {"request": _curriculum_payload(s, row)}


def _resource_request_payload(s, row):
    workflow = s.get(WorkflowInstance, row.workflow_instance_id)
    history = (s.query(Approval).filter(Approval.workflow_id == row.workflow_instance_id)
               .order_by(Approval.created_at).all())
    pending = workflow and workflow.state in {"submitted", "under_review"}
    return {
        "id": row.id, "workflow_instance_id": row.workflow_instance_id,
        "category": row.category, "title": row.title, "description": row.description,
        "quantity": row.quantity, "estimated_cost": row.estimated_cost,
        "justification": row.justification,
        "status": workflow.state if workflow else "",
        "current_stage": workflow.current_stage if workflow else 0,
        "stage_label": RESOURCE_STAGE_NAME if pending else "Completed",
        "current_reviewer": RESOURCE_STAGE_NAME if pending else "",
        "submitted_at": row.created_at.isoformat(),
        "history": [{"stage": item.stage, "stage_label": item.stage_label,
                     "actor": item.actor_name, "decision": item.decision,
                     "reason": item.reason, "at": item.created_at.isoformat()}
                    for item in history],
    }


def _resource_request_or_403(s, request_id, ctx):
    row = s.get(D.DepartmentResourceRequest, request_id)
    workflow = s.get(WorkflowInstance, row.workflow_instance_id) if row else None
    if not row or not workflow or workflow.process_key != "department_resource_request":
        raise HTTPException(404, "Department resource request not found")
    if row.requester_user_id != ctx["sub"]:
        raise HTTPException(403, "This department resource request does not belong to the authenticated HOD")
    return row, workflow


@router.get("/resource-requests")
def hod_resource_requests(ctx=Depends(auth), s=Depends(db)):
    department = _resolved_hod_department(s, ctx)
    rows = (s.query(D.DepartmentResourceRequest)
            .join(WorkflowInstance, D.DepartmentResourceRequest.workflow_instance_id == WorkflowInstance.id)
            .filter(D.DepartmentResourceRequest.requester_user_id == ctx["sub"],
                    D.DepartmentResourceRequest.department_id == department.id,
                    WorkflowInstance.process_key == "department_resource_request")
            .order_by(D.DepartmentResourceRequest.updated_at.desc()).all())
    return {"department": {"id": department.id, "code": department.code, "name": department.name, "campus": department.campus or ""},
            "requests": [_resource_request_payload(s, row) for row in rows],
            "options": {"categories": sorted(RESOURCE_REQUEST_CATEGORIES)}}


@router.get("/resource-requests/{request_id}")
def hod_resource_request(request_id: str, ctx=Depends(auth), s=Depends(db)):
    _hod_staff(s, ctx)
    row, _ = _resource_request_or_403(s, request_id, ctx)
    return {"request": _resource_request_payload(s, row)}


@router.post("/resource-requests")
def create_resource_request(body: DepartmentResourceRequestIn, ctx=Depends(auth), s=Depends(db)):
    staff = _hod_staff(s, ctx)
    department = _resolved_hod_department(s, ctx)
    category = body.category.strip().lower()
    if category not in RESOURCE_REQUEST_CATEGORIES:
        raise HTTPException(422, "Choose a supported resource request category")
    if not body.title.strip() or not body.description.strip() or not body.justification.strip():
        raise HTTPException(422, "Title, requirement, and justification are required")
    if body.quantity is not None and body.quantity < 1:
        raise HTTPException(422, "Quantity must be a positive whole number when provided")
    if body.estimated_cost is not None and body.estimated_cost < 0:
        raise HTTPException(422, "Estimated cost cannot be negative")
    # Resolve the reviewer before any persistent row exists.  This derives the
    # HOD campus on the server and fails closed for missing/ambiguous mappings.
    dean = resolve_administration_dean(s, ctx)
    checkpoint = "create_workflow"
    try:
        workflow = WorkflowInstance(
            id=uid(), tenant_id=TENANT, process_key="department_resource_request",
            label="Department Resource Request", office_n=DEAN_ADMINISTRATION_OFFICE_N,
            title=f"Department resource request: {body.title.strip()}", state="submitted",
            amount=body.estimated_cost, initiator_id=ctx["sub"], initiator_name=staff.name,
            current_stage=1, scope_level="campus",
        )
        row = D.DepartmentResourceRequest(
            id=uid(), tenant_id=TENANT, requester_user_id=ctx["sub"],
            department_id=department.id, category=category, title=body.title.strip(),
            description=body.description.strip(), quantity=body.quantity,
            estimated_cost=body.estimated_cost, justification=body.justification.strip(),
            workflow_instance_id=workflow.id,
        )
        # The scalar FK has no ORM relationship.  Preserve the explicit,
        # all-or-nothing flush ordering established for curriculum requests.
        s.add(workflow)
        checkpoint = "flush_workflow"
        s.flush()
        s.add(row)
        checkpoint = "flush_resource_request"
        s.flush()
        checkpoint = "write_audit"
        write_audit(s, ctx["sub"], staff.name, ctx["office_n"], "department_resource_request.submit",
                    f"department_resource_request:{row.id}", "draft", "submitted",
                    row.justification, commit=False)
        checkpoint = "commit"
        s.commit()
    except HTTPException:
        s.rollback()
        raise
    except Exception as exc:
        s.rollback()
        original = getattr(exc, "orig", None) or getattr(exc, "__cause__", None) or exc
        diagnostics = getattr(original, "diag", None)
        logger.error(
            "department_resource_request.submit_failed process_key=department_resource_request checkpoint=%s "
            "department_id=%s error_type=%s sqlstate=%s constraint=%s",
            checkpoint, department.id, type(original).__name__, getattr(original, "pgcode", None),
            getattr(diagnostics, "constraint_name", None),
        )
        raise HTTPException(409, "Department resource request could not be submitted")
    notify(s, dean.id, "Department resource request review",
           f"{staff.name} submitted a department resource request", severity="action")
    return {"request": _resource_request_payload(s, row)}


def _dean_resource_request_or_403(s, request_id, ctx):
    if ctx.get("office_n") != DEAN_ADMINISTRATION_OFFICE_N:
        raise HTTPException(403, "Only the routed Dean Administration can review department resource requests")
    row = s.get(D.DepartmentResourceRequest, request_id)
    workflow = s.get(WorkflowInstance, row.workflow_instance_id) if row else None
    if not row or not workflow or workflow.process_key != "department_resource_request":
        raise HTTPException(404, "Department resource request not found")
    if workflow.state not in {"submitted", "under_review"} or workflow.current_stage != 1:
        raise HTTPException(409, "Department resource request is no longer actionable")
    department = s.get(D.Department, row.department_id)
    campuses = (s.query(D.Campus).filter(D.Campus.name == (department.campus if department else ""),
                                         D.Campus.is_active == True).all())
    if len(campuses) != 1:
        raise HTTPException(409, "Department resource request campus routing is not configured")
    dean = resolve_campus_leader(s, campuses[0].id, DEAN_ADMINISTRATION_OFFICE_N)
    if dean.id != ctx["sub"]:
        raise HTTPException(403, "You are not the eligible Dean Administration reviewer")
    return row, workflow


@leadership_router.get("/resource-requests")
def dean_resource_requests(ctx=Depends(auth), s=Depends(db)):
    if ctx.get("office_n") != DEAN_ADMINISTRATION_OFFICE_N:
        raise HTTPException(403, "Only Dean Administration can access this inbox")
    rows = (s.query(D.DepartmentResourceRequest)
            .join(WorkflowInstance, D.DepartmentResourceRequest.workflow_instance_id == WorkflowInstance.id)
            .filter(WorkflowInstance.process_key == "department_resource_request",
                    WorkflowInstance.state.in_({"submitted", "under_review"})).all())
    out = []
    for row in rows:
        try:
            _dean_resource_request_or_403(s, row.id, ctx)
            out.append(_resource_request_payload(s, row))
        except HTTPException:
            continue
    return {"requests": out}


@leadership_router.post("/resource-requests/{request_id}/decide")
def decide_resource_request(request_id: str, body: DepartmentResourceDecisionIn,
                            ctx=Depends(auth), s=Depends(db)):
    row, workflow = _dean_resource_request_or_403(s, request_id, ctx)
    action = body.action.strip().lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(422, "Choose approve or reject")
    if action == "reject" and not body.comment.strip():
        raise HTTPException(422, "A comment is required when rejecting a resource request")
    actor = s.get(User, ctx["sub"])
    actor_name = actor.role if actor else "Dean Administration"
    before = workflow.state
    s.add(Approval(id=uid(), tenant_id=TENANT, workflow_id=workflow.id, actor_id=ctx["sub"],
                   actor_name=actor_name, stage=1, stage_label=RESOURCE_STAGE_NAME,
                   decision=action.upper(), authority="FULL", reason=body.comment.strip()))
    workflow.state = "approved" if action == "approve" else "rejected"
    workflow.current_stage = 2
    workflow.updated_at = datetime.utcnow()
    write_audit(s, ctx["sub"], actor_name, ctx["office_n"], f"department_resource_request.{action}",
                f"department_resource_request:{row.id}", before, workflow.state,
                body.comment.strip(), commit=False)
    s.commit()
    notify(s, row.requester_user_id, f"Department resource request {workflow.state}",
           body.comment.strip() or "Dean Administration recorded a decision.", severity="info")
    return {"request": _resource_request_payload(s, row)}


def _staffing_payload(s, row):
    workflow = s.get(WorkflowInstance, row.workflow_instance_id)
    history = (s.query(Approval).filter(Approval.workflow_id == row.workflow_instance_id)
               .order_by(Approval.created_at).all())
    pending = workflow and workflow.state in {"submitted", "under_review"}
    stage = workflow.current_stage if workflow else 0
    return {
        "id": row.id, "workflow_instance_id": row.workflow_instance_id,
        "request_type": row.request_type, "designation_or_role": row.designation_or_role,
        "number_required": row.number_required,
        "required_by_date": row.required_by_date.isoformat() if row.required_by_date else "",
        "justification": row.justification, "status": workflow.state if workflow else "",
        "current_stage": stage,
        "stage_label": STAFFING_REVIEW_STAGES.get(stage, "Completed") if pending else "Completed",
        "current_reviewer": STAFFING_REVIEW_STAGES.get(stage, "") if pending else "",
        "submitted_at": row.created_at.isoformat(),
        "history": [{"stage": item.stage, "stage_label": item.stage_label,
                     "actor": item.actor_name, "decision": item.decision,
                     "reason": item.reason, "at": item.created_at.isoformat()}
                    for item in history],
    }


def _staffing_request_or_403(s, request_id, ctx):
    row = s.get(D.StaffingRequest, request_id)
    workflow = s.get(WorkflowInstance, row.workflow_instance_id) if row else None
    if not row or not workflow or workflow.process_key != "staffing_request":
        raise HTTPException(404, "Staffing request not found")
    if row.requester_user_id != ctx["sub"]:
        raise HTTPException(403, "This staffing request does not belong to the authenticated HOD")
    return row, workflow


def _staffing_request_campus(s, row):
    department = s.get(D.Department, row.department_id)
    campuses = (s.query(D.Campus)
                .filter(D.Campus.name == (department.campus if department else ""),
                        D.Campus.is_active == True).all())
    if len(campuses) != 1:
        raise HTTPException(409, "Staffing approval routing is not configured")
    return campuses[0]


def _staffing_reviewer(s, row, workflow):
    if workflow.state not in {"submitted", "under_review"}:
        raise HTTPException(409, "Staffing request is no longer actionable")
    office_by_stage = {1: DEAN_ADMINISTRATION_OFFICE_N, 2: PRINCIPAL_OFFICE_N}
    office_n = office_by_stage.get(workflow.current_stage)
    if not office_n:
        raise HTTPException(409, "Staffing request is no longer actionable")
    return resolve_campus_leader(s, _staffing_request_campus(s, row).id, office_n)


@router.get("/staffing-requests")
def hod_staffing_requests(ctx=Depends(auth), s=Depends(db)):
    department = _resolved_hod_department(s, ctx)
    rows = (s.query(D.StaffingRequest)
            .join(WorkflowInstance, D.StaffingRequest.workflow_instance_id == WorkflowInstance.id)
            .filter(D.StaffingRequest.requester_user_id == ctx["sub"],
                    D.StaffingRequest.department_id == department.id,
                    WorkflowInstance.process_key == "staffing_request")
            .order_by(D.StaffingRequest.updated_at.desc()).all())
    return {"department": {"id": department.id, "code": department.code, "name": department.name, "campus": department.campus or ""},
            "requests": [_staffing_payload(s, row) for row in rows],
            "options": {"request_types": sorted(STAFFING_REQUEST_TYPES)}}


@router.get("/staffing-requests/{request_id}")
def hod_staffing_request(request_id: str, ctx=Depends(auth), s=Depends(db)):
    _hod_staff(s, ctx)
    row, _ = _staffing_request_or_403(s, request_id, ctx)
    return {"request": _staffing_payload(s, row)}


@router.post("/staffing-requests")
def create_staffing_request(body: StaffingRequestIn, ctx=Depends(auth), s=Depends(db)):
    staff = _hod_staff(s, ctx)
    department = _resolved_hod_department(s, ctx)
    request_type = body.request_type.strip().lower()
    designation = body.designation_or_role.strip()
    justification = body.justification.strip()
    if request_type not in STAFFING_REQUEST_TYPES:
        raise HTTPException(422, "Choose a supported staffing request type")
    if not designation or len(designation) > 120:
        raise HTTPException(422, "Requested designation / role is required and must be at most 120 characters")
    if body.number_required < 1:
        raise HTTPException(422, "Number required must be at least 1")
    if not justification:
        raise HTTPException(422, "Justification is required")
    # Both current reviewers must resolve before a row is persisted.
    chain = resolve_staffing_reviewers(s, ctx)
    checkpoint = "create_workflow"
    try:
        workflow = WorkflowInstance(
            id=uid(), tenant_id=TENANT, process_key="staffing_request",
            label="Staffing Request", office_n=DEAN_ADMINISTRATION_OFFICE_N,
            title=f"Staffing request: {designation}", state="submitted",
            initiator_id=ctx["sub"], initiator_name=staff.name,
            current_stage=1, scope_level="campus",
        )
        row = D.StaffingRequest(
            id=uid(), tenant_id=TENANT, requester_user_id=ctx["sub"],
            department_id=department.id, request_type=request_type,
            designation_or_role=designation, number_required=body.number_required,
            required_by_date=body.required_by_date, justification=justification,
            workflow_instance_id=workflow.id,
        )
        # Explicit ordering is required because the model uses a scalar FK.
        s.add(workflow); checkpoint = "flush_workflow"; s.flush()
        s.add(row); checkpoint = "flush_staffing_request"; s.flush()
        checkpoint = "write_audit"
        write_audit(s, ctx["sub"], staff.name, ctx["office_n"], "staffing_request.submit",
                    f"staffing_request:{row.id}", "draft", "submitted", justification, commit=False)
        checkpoint = "commit"; s.commit()
    except HTTPException:
        s.rollback(); raise
    except Exception as exc:
        s.rollback()
        original = getattr(exc, "orig", None) or getattr(exc, "__cause__", None) or exc
        diagnostics = getattr(original, "diag", None)
        logger.error("staffing_request.submit_failed process_key=staffing_request checkpoint=%s department_id=%s error_type=%s sqlstate=%s constraint=%s",
                     checkpoint, department.id, type(original).__name__, getattr(original, "pgcode", None),
                     getattr(diagnostics, "constraint_name", None))
        raise HTTPException(409, "Staffing request could not be submitted")
    notify(s, chain["dean_administration"].id, "Staffing request review",
           f"{staff.name} submitted a department staffing requirement", severity="action")
    return {"request": _staffing_payload(s, row)}


def _leadership_staffing_request_or_403(s, request_id, ctx):
    if ctx.get("office_n") not in {DEAN_ADMINISTRATION_OFFICE_N, PRINCIPAL_OFFICE_N}:
        raise HTTPException(403, "Only the routed campus reviewer can review staffing requests")
    row = s.get(D.StaffingRequest, request_id)
    workflow = s.get(WorkflowInstance, row.workflow_instance_id) if row else None
    if not row or not workflow or workflow.process_key != "staffing_request":
        raise HTTPException(404, "Staffing request not found")
    reviewer = _staffing_reviewer(s, row, workflow)
    if reviewer.id != ctx["sub"]:
        raise HTTPException(403, "You are not the eligible reviewer for the current staffing stage")
    return row, workflow


@leadership_router.get("/staffing-requests")
def leadership_staffing_requests(ctx=Depends(auth), s=Depends(db)):
    if ctx.get("office_n") not in {DEAN_ADMINISTRATION_OFFICE_N, PRINCIPAL_OFFICE_N}:
        raise HTTPException(403, "Only campus Dean Administration and Principals can access this inbox")
    rows = (s.query(D.StaffingRequest)
            .join(WorkflowInstance, D.StaffingRequest.workflow_instance_id == WorkflowInstance.id)
            .filter(WorkflowInstance.process_key == "staffing_request",
                    WorkflowInstance.state.in_({"submitted", "under_review"})).all())
    requests = []
    for row in rows:
        workflow = s.get(WorkflowInstance, row.workflow_instance_id)
        try:
            if _staffing_reviewer(s, row, workflow).id == ctx["sub"]:
                requests.append(_staffing_payload(s, row))
        except HTTPException:
            continue
    return {"requests": requests}


@leadership_router.post("/staffing-requests/{request_id}/decide")
def decide_staffing_request(request_id: str, body: StaffingDecisionIn, ctx=Depends(auth), s=Depends(db)):
    row, workflow = _leadership_staffing_request_or_403(s, request_id, ctx)
    action = body.action.strip().lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(422, "Choose approve or reject")
    if action == "reject" and not body.comment.strip():
        raise HTTPException(422, "A comment is required when rejecting a staffing request")
    stage = workflow.current_stage
    actor = s.get(User, ctx["sub"])
    actor_name = actor.role if actor else STAFFING_REVIEW_STAGES[stage]
    before = workflow.state
    s.add(Approval(id=uid(), tenant_id=TENANT, workflow_id=workflow.id,
                   actor_id=ctx["sub"], actor_name=actor_name, stage=stage,
                   stage_label=STAFFING_REVIEW_STAGES[stage], decision=action.upper(),
                   authority="FULL", reason=body.comment.strip()))
    if action == "reject":
        workflow.state = "rejected"; workflow.current_stage = 3
    elif stage == 1:
        workflow.state = "under_review"; workflow.current_stage = 2
    else:
        workflow.state = "approved"; workflow.current_stage = 3
    workflow.updated_at = datetime.utcnow()
    write_audit(s, ctx["sub"], actor_name, ctx["office_n"], f"staffing_request.{action}",
                f"staffing_request:{row.id}", before, workflow.state,
                body.comment.strip(), commit=False)
    s.commit()
    if action == "approve" and stage == 1:
        principal = _staffing_reviewer(s, row, workflow)
        notify(s, principal.id, "Staffing request review",
               "A department staffing requirement awaits your review", severity="action")
    else:
        notify(s, row.requester_user_id, f"Staffing request {workflow.state}",
               body.comment.strip() or "A campus reviewer recorded a decision.", severity="info")
    return {"request": _staffing_payload(s, row)}


# --------------------------------------------------------------------------- #
# Restricted Student Welfare Escalations
# --------------------------------------------------------------------------- #
def _welfare_student_identity(s, student_id):
    student = s.get(D.Student, student_id)
    if not student:
        raise HTTPException(404, "Student not found")
    program = s.get(D.Program, student.program_id) if student.program_id else None
    return {
        "id": student.id, "name": student.name, "roll_no": student.roll_no,
        "program": program.name if program else "", "semester": student.semester,
        "section": student.section,
    }


def _welfare_history(s, workflow_id):
    return [{"stage": item.stage, "stage_label": item.stage_label, "actor": item.actor_name,
             "decision": item.decision, "comment": item.reason,
             "at": item.created_at.isoformat() if item.created_at else ""}
            for item in s.query(Approval).filter(Approval.workflow_id == workflow_id)
            .order_by(Approval.created_at).all()]


def _welfare_payload(s, row, *, detail=False):
    workflow = s.get(WorkflowInstance, row.workflow_instance_id)
    pending = workflow and workflow.state in {"submitted", "under_review"} and workflow.current_stage == 1
    payload = {
        "id": row.id, "workflow_instance_id": row.workflow_instance_id,
        "student": _welfare_student_identity(s, row.student_id),
        "concern_type": row.concern_type, "status": workflow.state if workflow else "",
        "current_stage": workflow.current_stage if workflow else 0,
        "stage_label": WELFARE_STAGE_NAME if pending else "Completed",
        "current_reviewer": WELFARE_STAGE_NAME if pending else "",
        "submitted_at": row.created_at.isoformat() if row.created_at else "",
    }
    if detail:
        # Only protected HOD/Dean detail endpoints call this branch.  No source
        # case notes or follow-ups are ever joined or serialized here.
        payload.update({"summary": row.summary, "escalation_reason": row.escalation_reason,
                        "source_mentoring_case_id": row.source_mentoring_case_id or "",
                        "source_mentoring_case": bool(row.source_mentoring_case_id),
                        "history": _welfare_history(s, row.workflow_instance_id)})
    return payload


def _welfare_options(s, department, ctx):
    students = (s.query(D.Student).filter(D.Student.dept_id == department.id)
                .order_by(D.Student.name).all())
    source_cases = (s.query(D.MentoringCase)
                    .filter(D.MentoringCase.department_id == department.id,
                            D.MentoringCase.referred_to_office == "hod",
                            D.MentoringCase.referred_to_user_id == ctx["sub"])
                    .order_by(D.MentoringCase.updated_at.desc()).all())
    return {
        "students": [_welfare_student_identity(s, student.id) for student in students],
        # Reference only: deliberately no mentoring category, summary, notes,
        # follow-up data, or private observations.
        "source_mentoring_cases": [{"id": case.id, "student_id": case.student_id,
                                    "status": case.status} for case in source_cases],
        "concern_types": sorted(WELFARE_CONCERN_TYPES),
    }


def _welfare_request_or_403(s, request_id, ctx):
    row = s.get(D.StudentWelfareEscalation, request_id)
    workflow = s.get(WorkflowInstance, row.workflow_instance_id) if row else None
    if not row or not workflow or workflow.process_key != "student_welfare_escalation":
        raise HTTPException(404, "Student welfare escalation not found")
    if row.requester_user_id != ctx["sub"]:
        raise HTTPException(403, "This student welfare escalation does not belong to the authenticated HOD")
    department = _resolved_hod_department(s, ctx)
    if row.department_id != department.id:
        raise HTTPException(403, "This student welfare escalation is outside the authenticated HOD department")
    return row, workflow


def _welfare_request_campus(s, row):
    department = s.get(D.Department, row.department_id)
    campuses = (s.query(D.Campus)
                .filter(D.Campus.name == (department.campus if department else ""),
                        D.Campus.is_active == True).all())
    if len(campuses) != 1:
        raise HTTPException(409, "Student welfare escalation campus routing is not configured")
    return campuses[0]


def _welfare_reviewer(s, row, workflow):
    if workflow.state not in {"submitted", "under_review"} or workflow.current_stage != 1:
        raise HTTPException(409, "Student welfare escalation is no longer actionable")
    return resolve_campus_leader(s, _welfare_request_campus(s, row).id, DEAN_STUDENT_AFFAIRS_OFFICE_N)


@router.get("/student-welfare-escalations")
def hod_student_welfare_escalations(ctx=Depends(auth), s=Depends(db)):
    department = _resolved_hod_department(s, ctx)
    rows = (s.query(D.StudentWelfareEscalation)
            .join(WorkflowInstance, D.StudentWelfareEscalation.workflow_instance_id == WorkflowInstance.id)
            .filter(D.StudentWelfareEscalation.requester_user_id == ctx["sub"],
                    D.StudentWelfareEscalation.department_id == department.id,
                    WorkflowInstance.process_key == "student_welfare_escalation")
            .order_by(D.StudentWelfareEscalation.updated_at.desc()).all())
    # List data is safe operational metadata; restricted narrative requires the detail API.
    return {"department": {"id": department.id, "name": department.name,
                           "code": department.code, "campus": department.campus or ""},
            "escalations": [_welfare_payload(s, row) for row in rows],
            "options": _welfare_options(s, department, ctx)}


@router.get("/student-welfare-escalations/{request_id}")
def hod_student_welfare_escalation(request_id: str, ctx=Depends(auth), s=Depends(db)):
    _hod_staff(s, ctx)
    row, _ = _welfare_request_or_403(s, request_id, ctx)
    return {"escalation": _welfare_payload(s, row, detail=True)}


@router.post("/student-welfare-escalations")
def create_student_welfare_escalation(body: StudentWelfareEscalationIn, ctx=Depends(auth), s=Depends(db)):
    staff = _hod_staff(s, ctx)
    department = _resolved_hod_department(s, ctx)
    concern_type = body.concern_type.strip().lower()
    summary = body.summary.strip()
    reason = body.escalation_reason.strip()
    if concern_type not in WELFARE_CONCERN_TYPES:
        raise HTTPException(422, "Choose a supported welfare concern type")
    if not summary or not reason:
        raise HTTPException(422, "Summary and escalation reason are required")
    if len(summary) > 2000 or len(reason) > 4000:
        raise HTTPException(422, "Welfare escalation text exceeds the permitted length")
    student = s.get(D.Student, body.student_id)
    if not student or student.dept_id != department.id:
        raise HTTPException(403, "The selected student does not belong to your department")
    source_case_id = body.source_mentoring_case_id.strip()
    if source_case_id:
        source = s.get(D.MentoringCase, source_case_id)
        if (not source or source.student_id != student.id or source.department_id != department.id
                or source.referred_to_office != "hod" or source.referred_to_user_id != ctx["sub"]):
            raise HTTPException(403, "The selected mentoring source is not available for this welfare escalation")
    # Resolve before persistence.  Context derives HOD campus server-side and
    # never accepts campus/reviewer fields from the request body.
    dean = resolve_student_affairs_dean(s, ctx)
    checkpoint = "create_workflow"
    try:
        workflow = WorkflowInstance(
            id=uid(), tenant_id=TENANT, process_key="student_welfare_escalation",
            label="Student Welfare Escalation", office_n=DEAN_STUDENT_AFFAIRS_OFFICE_N,
            # The generic workflow surface must remain non-sensitive.
            title="Student Welfare Escalation", state="submitted", initiator_id=ctx["sub"],
            initiator_name=staff.name, current_stage=1, scope_level="campus",
        )
        row = D.StudentWelfareEscalation(
            id=uid(), tenant_id=TENANT, requester_user_id=ctx["sub"],
            department_id=department.id, student_id=student.id,
            source_mentoring_case_id=source_case_id or None, concern_type=concern_type,
            summary=summary, escalation_reason=reason, workflow_instance_id=workflow.id,
        )
        s.add(workflow); checkpoint = "flush_workflow"; s.flush()
        s.add(row); checkpoint = "flush_student_welfare_escalation"; s.flush()
        checkpoint = "write_audit"
        # Audit only stable identifiers and state; no protected narrative or review comments.
        write_audit(s, ctx["sub"], staff.name, ctx["office_n"], "student_welfare_escalation.submit",
                    f"student_welfare_escalation:{row.id}", "draft", "submitted",
                    f"workflow:{workflow.id}", commit=False)
        checkpoint = "commit"; s.commit()
    except HTTPException:
        s.rollback(); raise
    except Exception as exc:
        s.rollback()
        original = getattr(exc, "orig", None) or getattr(exc, "__cause__", None) or exc
        diagnostics = getattr(original, "diag", None)
        logger.error("student_welfare_escalation.submit_failed checkpoint=%s department_id=%s error_type=%s sqlstate=%s constraint=%s",
                     checkpoint, department.id, type(original).__name__, getattr(original, "pgcode", None),
                     getattr(diagnostics, "constraint_name", None))
        raise HTTPException(409, "Student welfare escalation could not be submitted")
    notify(s, dean.id, "Student welfare escalation review",
           "A department student welfare escalation requires review.", severity="action")
    return {"escalation": _welfare_payload(s, row, detail=True)}


def _leadership_welfare_request_or_403(s, request_id, ctx):
    if ctx.get("office_n") != DEAN_STUDENT_AFFAIRS_OFFICE_N:
        raise HTTPException(403, "Only the routed Dean Student Affairs can review student welfare escalations")
    row = s.get(D.StudentWelfareEscalation, request_id)
    workflow = s.get(WorkflowInstance, row.workflow_instance_id) if row else None
    if not row or not workflow or workflow.process_key != "student_welfare_escalation":
        raise HTTPException(404, "Student welfare escalation not found")
    reviewer = _welfare_reviewer(s, row, workflow)
    if reviewer.id != ctx["sub"]:
        raise HTTPException(403, "You are not the eligible Dean Student Affairs reviewer")
    return row, workflow


@leadership_router.get("/student-welfare-escalations")
def dean_student_welfare_escalations(ctx=Depends(auth), s=Depends(db)):
    if ctx.get("office_n") != DEAN_STUDENT_AFFAIRS_OFFICE_N:
        raise HTTPException(403, "Only Dean Student Affairs can access this inbox")
    rows = (s.query(D.StudentWelfareEscalation)
            .join(WorkflowInstance, D.StudentWelfareEscalation.workflow_instance_id == WorkflowInstance.id)
            .filter(WorkflowInstance.process_key == "student_welfare_escalation",
                    WorkflowInstance.state.in_({"submitted", "under_review"}),
                    WorkflowInstance.current_stage == 1).all())
    out = []
    for row in rows:
        try:
            if _welfare_reviewer(s, row, s.get(WorkflowInstance, row.workflow_instance_id)).id == ctx["sub"]:
                # This is a protected specialized review inbox, not generic workflow data.
                out.append(_welfare_payload(s, row, detail=True))
        except HTTPException:
            continue
    return {"escalations": out}


@leadership_router.post("/student-welfare-escalations/{request_id}/decide")
def decide_student_welfare_escalation(request_id: str, body: StudentWelfareDecisionIn,
                                      ctx=Depends(auth), s=Depends(db)):
    row, workflow = _leadership_welfare_request_or_403(s, request_id, ctx)
    action = body.action.strip().lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(422, "Choose approve or reject")
    if action == "reject" and not body.comment.strip():
        raise HTTPException(422, "A comment is required when rejecting a student welfare escalation")
    actor = s.get(User, ctx["sub"]); actor_name = actor.role if actor else "Dean Student Affairs"
    before = workflow.state
    s.add(Approval(id=uid(), tenant_id=TENANT, workflow_id=workflow.id, actor_id=ctx["sub"],
                   actor_name=actor_name, stage=1, stage_label=WELFARE_STAGE_NAME,
                   decision=action.upper(), authority="FULL", reason=body.comment.strip()))
    workflow.state = "approved" if action == "approve" else "rejected"
    workflow.current_stage = 2; workflow.updated_at = datetime.utcnow()
    # Do not copy a reviewer comment into the broad audit surface.
    write_audit(s, ctx["sub"], actor_name, ctx["office_n"], f"student_welfare_escalation.{action}",
                f"student_welfare_escalation:{row.id}", before, workflow.state,
                f"workflow:{workflow.id}", commit=False)
    s.commit()
    notify(s, row.requester_user_id, f"Student welfare escalation {workflow.state}",
           "Dean Student Affairs recorded a decision. Open the protected escalation for details.", severity="info")
    return {"escalation": _welfare_payload(s, row, detail=True)}
