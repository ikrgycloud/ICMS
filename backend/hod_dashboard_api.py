"""Department-scoped command-centre data for the HOD overview."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, or_

from core import auth, db
import domain_models as D
from models import AuditLog, WorkflowInstance
from hod_scope import hod_department
from faculty_api import _correction_reviewer, _leave_reviewer, _marks_reviewer

router = APIRouter(prefix="/api/portal/hod")


def _risk_summary(s, students):
    """Keep the HOD numbers aligned with the Students module's risk rules."""
    ids = [student.id for student in students]
    latest = {}
    for row in s.query(D.StudentSubjectResult).filter(D.StudentSubjectResult.student_id.in_(ids)).order_by(D.StudentSubjectResult.student_id, D.StudentSubjectResult.subject_code, D.StudentSubjectResult.attempt).all() if ids else []:
        latest[(row.student_id, row.subject_code)] = row
    backlogs = {student_id: 0 for student_id in ids}
    for (student_id, _), row in latest.items():
        if row.outcome == "failed":
            backlogs[student_id] += 1
    attendance = {}
    for student_id, present in s.query(D.AttendanceRecord.student_id, D.AttendanceRecord.present).filter(D.AttendanceRecord.student_id.in_(ids)).all() if ids else []:
        total, attended = attendance.get(student_id, (0, 0))
        attendance[student_id] = (total + 1, attended + int(bool(present)))
    result = {"at_risk": 0, "backlogs": 0, "attendance_risk": 0, "academic_risk": 0, "multiple_risks": 0}
    for student in students:
        academic = (student.cgpa or 0) < 6.5
        backlog = backlogs[student.id] > 0
        total, attended = attendance.get(student.id, (0, 0))
        attendance_risk = total > 0 and 100 * attended / total < 75
        risks = sum((academic, backlog, attendance_risk))
        result["academic_risk"] += int(academic)
        result["backlogs"] += int(backlog)
        result["attendance_risk"] += int(attendance_risk)
        result["at_risk"] += int(risks > 0)
        result["multiple_risks"] += int(risks > 1)
    return result


def hod_dashboard_data(s, ctx):
    department = hod_department(s, ctx)
    if not department:
        raise HTTPException(403, "This dashboard is available only to the department HOD")
    hod = s.query(D.StaffMember).filter(D.StaffMember.user_id == ctx["sub"], D.StaffMember.status == "active").one_or_none()
    if not hod:
        raise HTTPException(403, "No active HOD staff profile is configured")
    campus = hod.campus or ""
    sections_all = s.query(D.Section).filter(D.Section.dept_id == hod.dept_id).all()
    terms = sorted({row.term for row in sections_all if row.term})
    term = terms[-1] if terms else ""
    sections = [row for row in sections_all if not term or row.term == term]
    section_ids = [row.id for row in sections]
    students = s.query(D.Student).filter(D.Student.dept_id == hod.dept_id, D.Student.status == "active", D.Student.campus == campus).all()
    faculty = s.query(D.StaffMember).filter(D.StaffMember.dept_id == hod.dept_id, D.StaffMember.status == "active", D.StaffMember.campus == campus).count()
    active_allocations = {row.section_id for row in s.query(D.TeachingAllocation).filter(D.TeachingAllocation.section_id.in_(section_ids), D.TeachingAllocation.status == "active", or_(D.TeachingAllocation.effective_from.is_(None), D.TeachingAllocation.effective_from <= date.today()), or_(D.TeachingAllocation.effective_to.is_(None), D.TeachingAllocation.effective_to >= date.today())).all()} if section_ids else set()
    scheduled_sections = {row.section_id for row in s.query(D.TimetableEntry).filter(D.TimetableEntry.section_id.in_(section_ids), D.TimetableEntry.status == "active").all()} if section_ids else set()
    pending_sessions = s.query(D.ClassSession).filter(D.ClassSession.section_id.in_(section_ids), D.ClassSession.finalized_at.is_(None)).count() if section_ids else 0
    all_sessions = s.query(D.ClassSession).filter(D.ClassSession.section_id.in_(section_ids)).count() if section_ids else 0
    course_ids = {row.course_id for row in sections}
    department_courses = s.query(D.Course).filter(D.Course.dept_id == department.id, D.Course.status == "Active").count()
    marks_reviews = 0
    for assessment, workflow in s.query(D.Assessment, WorkflowInstance).join(WorkflowInstance, D.Assessment.workflow_instance_id == WorkflowInstance.id).filter(D.Assessment.section_id.in_(section_ids), D.Assessment.marks_state.in_(["submitted", "under_review"])).all() if section_ids else []:
        marks_reviews += int(_marks_reviewer(s, assessment, workflow.current_stage) == ctx["sub"])
    correction_reviews = 0
    for correction, workflow in s.query(D.AttendanceCorrectionRequest, WorkflowInstance).join(WorkflowInstance, D.AttendanceCorrectionRequest.workflow_instance_id == WorkflowInstance.id).filter(D.AttendanceCorrectionRequest.section_id.in_(section_ids), D.AttendanceCorrectionRequest.status.in_(["submitted", "under_review"])).all() if section_ids else []:
        correction_reviews += int(_correction_reviewer(s, correction, workflow.current_stage) == ctx["sub"])
    dept_staff_ids = [row.id for row in s.query(D.StaffMember.id).filter(D.StaffMember.dept_id == hod.dept_id, D.StaffMember.campus == campus).all()]
    leave_reviews = 0
    for leave, workflow in s.query(D.LeaveRequest, WorkflowInstance).join(WorkflowInstance, D.LeaveRequest.workflow_instance_id == WorkflowInstance.id).filter(D.LeaveRequest.staff_id.in_(dept_staff_ids), D.LeaveRequest.status.in_(["submitted", "resubmitted", "under_review"])).all() if dept_staff_ids else []:
        leave_reviews += int(_leave_reviewer(s, leave, workflow.current_stage) == ctx["sub"])
    mentoring_reviews = s.query(D.MentoringCase).filter(D.MentoringCase.department_id == hod.dept_id, D.MentoringCase.referred_to_office == "hod", D.MentoringCase.status != "closed").count()
    assessments = s.query(D.Assessment).filter(D.Assessment.section_id.in_(section_ids)).count() if section_ids else 0
    upcoming_exams = s.query(D.Assessment).filter(D.Assessment.section_id.in_(section_ids), D.Assessment.scheduled_at.isnot(None), D.Assessment.scheduled_at >= date.today()).count() if section_ids else 0
    risk = _risk_summary(s, students)
    initiated = s.query(WorkflowInstance).filter(WorkflowInstance.initiator_id == ctx["sub"]).order_by(desc(WorkflowInstance.updated_at)).limit(8).all()
    allowed_request_labels = {"curriculum": "Curriculum Request", "resource": "Department Resource Request", "staff": "Staffing Request", "welfare": "Student Welfare Escalation", "leave": "My Leave"}
    requests = []
    for row in initiated:
        text = f"{row.process_key} {row.label}".lower()
        label = next((value for key, value in allowed_request_labels.items() if key in text), None)
        if label:
            requests.append({"label": label, "status": row.state.replace("_", " "), "updated_at": row.updated_at.isoformat()})
    audits = (s.query(AuditLog).filter(AuditLog.actor == ctx["sub"], ~AuditLog.action.like("auth.%"))
              .order_by(desc(AuditLog.created_at)).limit(6).all())
    safe_audit = [{"at": row.created_at.isoformat(), "description": row.action.replace(".", " ").replace("_", " ").title(), "resource": row.entity.split(":", 1)[0].replace("_", " ").title(), "status": row.new_state or "recorded"} for row in audits]
    def readiness(numerator, denominator, definition):
        return {"numerator": numerator, "denominator": denominator,
                "percentage": None if not denominator else round(100 * numerator / denominator),
                "definition": definition}
    return {
        "department": {"name": department.name, "code": department.code, "campus": campus, "term": term},
        "kpis": {"active_faculty": faculty, "department_students": len(students), "active_sections": len(sections), "at_risk_students": risk["at_risk"], "pending_reviews": marks_reviews + correction_reviews + leave_reviews + mentoring_reviews, "attendance_pending": pending_sessions, "sections_without_faculty": len(set(section_ids) - active_allocations), "upcoming_exams": upcoming_exams},
        "readiness": {"faculty_allocation": readiness(len(active_allocations), len(sections), "Current-term sections with an active, in-effect teaching allocation ÷ current-term sections"), "timetable": readiness(len(scheduled_sections), len(sections), "Current-term sections with at least one active timetable entry ÷ current-term sections"), "attendance_finalization": readiness(all_sessions - pending_sessions, all_sessions, "Finalized class sessions ÷ all stored class sessions for the current term"), "course_coverage": readiness(len(course_ids), department_courses, "Active department courses represented by a current-term section ÷ active department courses")},
        "attention": [{"key": "sections_without_faculty", "count": len(set(section_ids) - active_allocations)}, {"key": "sections_missing_timetable", "count": len(set(section_ids) - scheduled_sections)}, {"key": "attendance_sessions_pending", "count": pending_sessions}, {"key": "at_risk_students", "count": risk["at_risk"]}, {"key": "marks_reviews", "count": marks_reviews}],
        "reviews": {"marks_reviews": marks_reviews, "attendance_corrections": correction_reviews, "faculty_leave": leave_reviews, "mentoring_referrals": mentoring_reviews},
        "operations": {"teaching_active": len(active_allocations), "teaching_pending": s.query(D.TeachingAllocation).filter(D.TeachingAllocation.section_id.in_(section_ids), D.TeachingAllocation.status == "draft").count() if section_ids else 0, "attendance_pending": pending_sessions, "attendance_finalized": all_sessions - pending_sessions, "assessments": assessments, "awaiting_hod_review": marks_reviews},
        "student_health": risk, "requests": requests[:5], "activity": safe_audit,
    }


@router.get("/dashboard")
def hod_dashboard(ctx=Depends(auth), s=Depends(db)):
    return hod_dashboard_data(s, ctx)
