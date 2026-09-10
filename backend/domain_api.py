# -*- coding: utf-8 -*-
"""
Domain API — the functional modules that let every office do its job.

Every read is scope-filtered; every mutation passes through the authority engine
(authorize()) using the office's RBAC authority for the verb the action maps to,
and is written to the hash-chained audit log. Actions the office may not perform
return 403 with the engine's reason — the same verdict the UI uses to disable
the control.
"""
from datetime import date, datetime, timedelta
import json
import csv
import io
import zipfile
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, desc, false, func, or_, text

from core import db, auth, uid, write_audit, notify, active_delegation_for
from database import office, TENANT, slug
from authority import authorize, ALLOW, pwhash
from matrices import rbac_for, scope_for, approval_limit_for, APPROVAL_LIMITS
from capabilities import (modules_for_office, module_meta, MODULE_ACTIONS,
                          MODULES, action_allowed_for_office)
import domain_models as D
from academic_scope import authorize_object, dean_scope_assignments, hierarchy
from governance_engine import validate_transition
from teaching import faculty_owns_section
from models import User, Person, OrgScope, WorkflowInstance, Notification

router = APIRouter(prefix="/api")

REPORTS = {
    "approval-aging": ("Approval aging", ["entity", "state", "updated_at"]),
    "curriculum-version-history": ("Curriculum version history", ["id", "program_id", "effective_term", "version", "status"]),
    "program-feasibility": ("Program feasibility", ["program_id", "capacity", "intake", "faculty_ready", "infrastructure_ready"]),
    "faculty-workload": ("Faculty workload", ["faculty_id", "term", "workload_units"]),
    "timetable-readiness": ("Timetable readiness", ["id", "kind", "severity", "status"]),
    "delivery-status": ("Delivery status", ["section_id", "term", "completion_pct", "status"]),
    "quality-action-aging": ("Quality action aging", ["id", "review_id", "priority", "state", "deadline"]),
    "co-po-attainment": ("CO/PO attainment", ["outcome", "code", "attainment"]),
    "semester-comparison": ("Semester comparison", ["term", "metric", "value"]),
}


@router.get("/academics/dean-dashboard")
def dean_dashboard(
    academic_year: str = "",
    semester: int | None = None,
    school_id: str = "",
    dept_id: str = "",
    program_id: str = "",
    ctx=Depends(auth),
    s=Depends(db),
):
    """Return the Dean's filtered executive view from authorized academic rows."""
    require(gate(s, ctx, "academics", "view", governance=True)[0])
    academic_year_options = [
        row.name for row in s.query(D.AcademicYear)
        .filter(D.AcademicYear.tenant_id == ctx["tenant_id"], D.AcademicYear.is_active == True)
        .order_by(D.AcademicYear.start_date.desc(), D.AcademicYear.name.desc()).all()
    ]
    semester_options = [
        row[0] for row in s.query(D.Semester.sequence)
        .join(D.AcademicYear, D.Semester.academic_year_id == D.AcademicYear.id)
        .filter(D.AcademicYear.tenant_id == ctx["tenant_id"], D.Semester.is_active == True)
        .distinct().order_by(D.Semester.sequence).all()
    ]
    courses = scoped_academic_query(s, D.Course, ctx)
    # Archived/inactive catalogue rows are not current academic delivery.
    courses = courses.filter(~D.Course.status.in_(["Archived", "Inactive", "Deleted"]))
    if school_id:
        courses = courses.filter(D.Course.school_id == school_id)
    if dept_id:
        courses = courses.filter(D.Course.dept_id == dept_id)
    if program_id:
        courses = courses.filter(D.Course.program_id == program_id)
    course_rows = courses.all()
    course_ids = {row.id for row in course_rows}
    schools = scoped_academic_query(s, D.School, ctx)
    if school_id:
        schools = schools.filter(D.School.id == school_id)
    school_rows = schools.all()
    departments = scoped_academic_query(s, D.Department, ctx)
    if school_id:
        departments = departments.filter(or_(D.Department.school_id == school_id, D.Department.campus == school_id))
    if dept_id:
        departments = departments.filter(D.Department.id == dept_id)
    department_rows = departments.all()
    department_ids = {row.id for row in department_rows}
    programs = scoped_academic_query(s, D.Program, ctx)
    if school_id:
        programs = programs.filter(D.Program.school_id == school_id)
    if dept_id:
        programs = programs.filter(D.Program.dept_id == dept_id)
    if program_id:
        programs = programs.filter(D.Program.id == program_id)
    program_rows = programs.all()
    program_ids = {row.id for row in program_rows}

    sections = scoped_academic_query(s, D.Section, ctx)
    if course_ids:
        sections = sections.filter(D.Section.course_id.in_(course_ids))
    else:
        sections = sections.filter(text("1=0"))
    if semester is not None:
        sections = sections.filter(D.Section.term.like(f"%{semester}%"))
    section_rows = sections.all()
    section_ids = {row.id for row in section_rows}

    proposals = s.query(D.AcademicProposal).filter(
        D.AcademicProposal.tenant_id == ctx["tenant_id"],
        D.AcademicProposal.assigned_to_office_n == ctx["office_n"],
        D.AcademicProposal.state.in_(["SUBMITTED", "RESUBMITTED"]),
    ).all()
    scoped_proposals = [row for row in proposals if not row.dept_id or row.dept_id in department_ids]
    curriculum_proposals = s.query(D.AcademicProposal).filter(
        D.AcademicProposal.tenant_id == ctx["tenant_id"],
        D.AcademicProposal.proposal_type == "curriculum",
        D.AcademicProposal.assigned_to_office_n == ctx["office_n"],
    ).all()
    scoped_curriculum_proposals = [row for row in curriculum_proposals if not row.dept_id or row.dept_id in department_ids]
    reviews = scoped_academic_query(s, D.AcademicQualityReview, ctx).all()
    actions = scoped_academic_query(s, D.CorrectiveAction, ctx).all()
    exceptions = scoped_academic_query(s, D.TimetableException, ctx).all()
    # Official Dean metrics use only Exam Controller-published result sheets.
    # Faculty draft marks and development samples are intentionally excluded.
    published_sheet_ids = [row[0] for row in s.query(D.ResultSheet.id).filter(
        D.ResultSheet.tenant_id == ctx["tenant_id"], D.ResultSheet.status == "published",
    ).all()]
    all_results = s.query(D.StudentSubjectResult).filter(
        D.StudentSubjectResult.tenant_id == ctx["tenant_id"],
        D.StudentSubjectResult.course_id.in_(course_ids) if course_ids else text("1=0"),
        D.StudentSubjectResult.source == "examination",
        D.StudentSubjectResult.published_at != None,
        D.StudentSubjectResult.result_sheet_id.in_(published_sheet_ids) if published_sheet_ids else text("1=0"),
    ).all()
    results = all_results
    if academic_year:
        results = [row for row in results if row.academic_year == academic_year]
    if semester is not None:
        results = [row for row in results if row.semester == semester]
    student_scope = scoped_academic_query(s, D.Student, ctx)
    if school_id:
        student_scope = student_scope.filter(D.Student.dept_id.in_([r.id for r in department_rows])) if department_rows else student_scope.filter(text("1=0"))
    if dept_id:
        student_scope = student_scope.filter(D.Student.dept_id == dept_id)
    if program_id:
        student_scope = student_scope.filter(D.Student.program_id == program_id)
    student_rows = student_scope.all()
    attendance = s.query(D.AttendanceRecord).filter(
        D.AttendanceRecord.tenant_id == ctx["tenant_id"],
        D.AttendanceRecord.section_id.in_(section_ids) if section_ids else text("1=0"),
    ).all()
    completions = s.query(D.CourseCompletion).filter(
        D.CourseCompletion.tenant_id == ctx["tenant_id"],
        D.CourseCompletion.section_id.in_(section_ids) if section_ids else text("1=0"),
    ).all()
    allocations = s.query(D.FacultyAllocation).filter(
        D.FacultyAllocation.tenant_id == ctx["tenant_id"],
        D.FacultyAllocation.section_id.in_(section_ids) if section_ids else text("1=0"),
    ).all()
    calendar = s.query(D.AcademicCalendarEntry).filter(
        D.AcademicCalendarEntry.tenant_id == ctx["tenant_id"],
        D.AcademicCalendarEntry.status == "published",
        D.AcademicCalendarEntry.start_date >= date.today(),
    ).order_by(D.AcademicCalendarEntry.start_date).limit(8).all()

    passed = sum(1 for row in results if row.outcome == "passed")
    attendance_rate = round(100 * sum(1 for row in attendance if row.present) / len(attendance), 1) if attendance else None
    pass_rate = round(100 * passed / len(results), 1) if results else None
    cgpa_values = [row.cgpa for row in student_rows if row.cgpa is not None]
    avg_cgpa = round(sum(cgpa_values) / len(cgpa_values), 2) if cgpa_values else None
    active_backlogs = sum(1 for row in results if row.outcome == "failed")
    at_risk_students = sum(1 for row in student_rows if row.cgpa is not None and row.cgpa < 6)
    department_map = {row.id: row.name for row in department_rows}
    course_map = {row.id: row for row in course_rows}
    department_scores = {}
    for row in results:
        course = course_map.get(row.course_id)
        if course:
            bucket = department_scores.setdefault(course.dept_id, [0, 0])
            bucket[0] += 1
            bucket[1] += row.outcome == "passed"
    department_performance = [
        {"id": key, "name": department_map.get(key, key), "pass_rate": round(100 * values[1] / values[0], 1)}
        for key, values in department_scores.items()
    ]
    curriculum_states = {}
    for row in scoped_curriculum_proposals:
        if row.state == "APPROVED":
            label = "Approved"
        elif row.state in {"SUBMITTED", "RESUBMITTED", "UNDER_REVIEW"}:
            label = "Overdue" if row.due_at and row.due_at < datetime.utcnow() else "In Review"
        elif row.state == "RETURNED":
            label = "Returned"
        else:
            continue
        curriculum_states[label] = curriculum_states.get(label, 0) + 1
    workload = {}
    for row in allocations:
        workload[row.faculty_person_id] = workload.get(row.faculty_person_id, 0) + float(row.workload_units or 0)
    average_workload_units = sum(workload.values()) / len(workload) if workload else 0
    workload_status = "Underloaded" if average_workload_units < 2 else "Balanced" if average_workload_units <= 4 else "Overloaded"
    workload_summary = {
        "underloaded": sum(1 for value in workload.values() if value < 2),
        "balanced": sum(1 for value in workload.values() if 2 <= value <= 4),
        "overloaded": sum(1 for value in workload.values() if value > 4),
        "avg_load": round(min(100, max(0, average_workload_units / 4 * 100)), 1),
        "status": workload_status if workload else None,
    }
    # Report pending work by proposal type.  Programme inventory is not the
    # same as programme changes awaiting a Dean decision.
    approval_counts = {
        proposal_type: sum(1 for row in scoped_proposals if row.proposal_type == proposal_type)
        for proposal_type in ("program", "curriculum", "calendar", "allocation")
    }
    faculty_query = scoped_academic_query(s, D.StaffMember, ctx).filter(D.StaffMember.status == "active")
    if school_id:
        faculty_query = faculty_query.filter(D.StaffMember.school_id == school_id)
    if dept_id:
        faculty_query = faculty_query.filter(D.StaffMember.dept_id == dept_id)
    if program_id:
        faculty_query = faculty_query.filter(D.StaffMember.program_id == program_id)
    # Include active faculty with no allocation in the denominator so the
    # average is representative and the gauge has a useful empty state.
    faculty_rows = faculty_query.all()
    faculty_ids = {row.id for row in faculty_rows}
    scoped_loads = {faculty_id: units for faculty_id, units in workload.items() if faculty_id in faculty_ids}
    average_workload_units = sum(scoped_loads.values()) / len(faculty_ids) if faculty_ids else 0
    max_units = 4.0
    workload_summary = {
        "underloaded": sum(1 for faculty_id in faculty_ids if scoped_loads.get(faculty_id, 0) < 2),
        "balanced": sum(1 for faculty_id in faculty_ids if 2 <= scoped_loads.get(faculty_id, 0) <= max_units),
        "overloaded": sum(1 for faculty_id in faculty_ids if scoped_loads.get(faculty_id, 0) > max_units),
        "assigned": sum(1 for faculty_id in faculty_ids if scoped_loads.get(faculty_id, 0) > 0),
        "unassigned": sum(1 for faculty_id in faculty_ids if scoped_loads.get(faculty_id, 0) <= 0),
        "faculty_count": len(faculty_ids), "total_units": round(sum(scoped_loads.values()), 1),
        "avg_units": round(average_workload_units, 2), "capacity_units": max_units,
        "avg_load": round(min(100, max(0, average_workload_units / max_units * 100)), 1),
        "status": "No allocation data" if not faculty_ids or not scoped_loads else "Underloaded" if average_workload_units < 2 else "Balanced" if average_workload_units <= max_units else "Overloaded",
    }
    def comparison(current, previous, unit, label):
        if current is None or previous is None:
            return None
        return {"change": round(current - previous, 1), "unit": unit, "label": label}

    result_years = sorted({row.academic_year for row in all_results if row.academic_year})
    previous_year = result_years[result_years.index(academic_year) - 1] if academic_year in result_years and result_years.index(academic_year) else None
    previous_results = [row for row in all_results if row.academic_year == previous_year] if previous_year else []
    previous_pass_rate = round(100 * sum(1 for row in previous_results if row.outcome == "passed") / len(previous_results), 1) if previous_results else None
    previous_backlogs = sum(1 for row in previous_results if row.outcome == "failed") if previous_results else None
    recent_start, prior_start = date.today() - timedelta(days=29), date.today() - timedelta(days=59)
    recent_attendance = [row for row in attendance if row.on_date and row.on_date >= recent_start]
    prior_attendance = [row for row in attendance if row.on_date and prior_start <= row.on_date < recent_start]
    recent_rate = round(100 * sum(1 for row in recent_attendance if row.present) / len(recent_attendance), 1) if recent_attendance else None
    prior_rate = round(100 * sum(1 for row in prior_attendance if row.present) / len(prior_attendance), 1) if prior_attendance else None
    backlog_rate = active_backlogs / max(1, len(student_rows))
    risk_rate = at_risk_students / max(1, len(cgpa_values))

    def health_status(key, value):
        if value is None:
            return "unavailable"
        if key == "avg_cgpa":
            return "on_track" if value >= 7 else "watch" if value >= 6 else "action"
        if key in {"pass_rate", "attendance"}:
            return "on_track" if value >= 75 else "watch" if value >= 60 else "action"
        rate = backlog_rate if key == "active_backlogs" else risk_rate
        return "on_track" if rate <= .03 else "watch" if rate <= .10 else "action"

    health_scorecard = [
        {"key": "avg_cgpa", "label": "Average CGPA", "value": avg_cgpa, "target": "Target ≥ 7.00", "status": health_status("avg_cgpa", avg_cgpa), "comparison": None, "route": "analytics"},
        {"key": "pass_rate", "label": "Pass rate", "value": pass_rate, "target": "Target ≥ 75%", "status": health_status("pass_rate", pass_rate), "comparison": comparison(pass_rate, previous_pass_rate, "points", f"vs {previous_year}") if academic_year else None, "route": "analytics"},
        {"key": "attendance", "label": "Attendance", "value": attendance_rate, "target": "Target ≥ 75%", "status": health_status("attendance", attendance_rate), "comparison": comparison(recent_rate, prior_rate, "points", "vs prior 30 days"), "route": "attendance"},
        {"key": "active_backlogs", "label": "Active backlogs", "value": active_backlogs, "target": "Target ≤ 3% of students", "status": health_status("active_backlogs", active_backlogs), "comparison": comparison(active_backlogs, previous_backlogs, "count", f"vs {previous_year}") if academic_year else None, "route": "students"},
        {"key": "at_risk_students", "label": "At-risk students", "value": at_risk_students, "target": "Target ≤ 3% of assessed students", "status": health_status("at_risk_students", at_risk_students), "comparison": None, "route": "students"},
    ]
    priority_metric = next((row for status in ("action", "watch") for row in health_scorecard if row["status"] == status), None)
    priority_messages = {
        "attendance": "Attendance is below the operating target. Review affected sections.",
        "pass_rate": "Pass rate needs attention. Review result and intervention data.",
        "avg_cgpa": "Average CGPA is below target. Review academic support actions.",
        "active_backlogs": "Backlogs exceed the operating threshold. Open the student risk list.",
        "at_risk_students": "At-risk student volume needs review. Open the intervention list.",
    }
    health_priority = {"status": priority_metric["status"], "metric": priority_metric["label"], "message": priority_messages[priority_metric["key"]], "route": priority_metric["route"]} if priority_metric else {"status": "on_track", "metric": "Academic health", "message": "All tracked academic health measures are on target.", "route": "analytics"}
    return {
        "filters": {"academic_year": academic_year, "semester": semester, "school_id": school_id, "dept_id": dept_id, "program_id": program_id},
        "options": {
            "academic_years": academic_year_options,
            "semesters": semester_options,
            "schools": [{"id": row.id, "name": row.name} for row in school_rows],
            "departments": [{"id": row.id, "name": row.name} for row in department_rows],
            "programs": [{"id": row.id, "name": row.name} for row in program_rows],
        },
        "kpis": {
            "programs": len(program_rows), "departments": len(department_rows), "courses": len(course_rows),
            "faculty": len(faculty_rows), "curriculum_reviews": approval_counts["curriculum"],
            "timetable_conflicts": sum(1 for row in exceptions if row.status != "RESOLVED"), "academic_actions": sum(1 for row in actions if row.state != "VERIFIED"),
            "academic_risks": len(reviews), "needs_my_decision": len(scoped_proposals),
        },
        "approvals": approval_counts,
        "health": {
            "attendance": attendance_rate,
            "pass_rate": pass_rate,
            "avg_cgpa": avg_cgpa,
            "active_backlogs": active_backlogs,
            "at_risk_students": at_risk_students,
            "active_actions": sum(1 for row in actions if row.state != "VERIFIED"),
            "risk_indicators": len(reviews),
        },
        "health_scorecard": health_scorecard,
        "health_priority": health_priority,
        "data_as_of": datetime.utcnow().isoformat(),
        "department_performance": department_performance,
        "curriculum_status": curriculum_states,
        "timetable_readiness": {"completed": sum(1 for row in completions if row.status == "completed"), "in_progress": sum(1 for row in completions if row.status == "in_progress"), "pending": max(0, len(section_rows) - len(completions)), "conflicts": sum(1 for row in exceptions if row.status != "RESOLVED")},
        "faculty_workload": workload_summary,
        "result_trends": [{"academic_year": year, "pass_rate": round(100 * sum(1 for row in rows if row.outcome == "passed") / len(rows), 1)} for year in sorted({row.academic_year for row in results}) for rows in [[item for item in results if item.academic_year == year]] if rows],
        "milestones": [{"id": row.id, "title": row.title, "category": row.category, "start_date": row.start_date.isoformat(), "end_date": row.end_date.isoformat() if row.end_date else None} for row in calendar],
    }


@router.post("/jobs")
def enqueue_job(body: dict, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "export")[0])
    if ctx.get("office_n") not in {6, 10, 17, 28, 40}: raise HTTPException(403, "Worker operations access denied")
    key=(body.get("idempotency_key") or "").strip()
    operation=(body.get("operation") or "").strip()
    if not key or not operation: raise HTTPException(422, "operation and idempotency_key are required")
    existing=s.execute(text("SELECT id, status FROM icms_jobs WHERE idempotency_key=:key"), {"key":key}).first()
    if existing: return {"id":existing.id,"status":existing.status,"duplicate":True}
    job_id=uid(); s.execute(text("INSERT INTO icms_jobs (id,queue,payload,idempotency_key) VALUES (:id,:queue,:payload,:key)"), {"id":job_id,"queue":body.get("queue","default"),"payload":json.dumps({"operation":operation,"payload":body.get("payload",{})}),"key":key}); s.commit()
    return {"id":job_id,"status":"queued","duplicate":False}


@router.get("/jobs")
def job_monitor(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    if ctx.get("office_n") not in {6, 10, 17, 28, 40}: raise HTTPException(403, "Worker monitoring access denied")
    try: rows=s.execute(text("SELECT id,queue,status,attempts,last_error,created_at FROM icms_jobs ORDER BY created_at DESC LIMIT 100")).all(); workers=s.execute(text("SELECT worker_id,status,processed,failed,last_error,updated_at FROM icms_worker_heartbeats ORDER BY updated_at DESC")).all()
    except Exception: return {"jobs":[]}
    return {"jobs":[dict(row._mapping) for row in rows],"dead_letter":sum(1 for row in rows if row.status=="dead_letter"),"workers":[dict(row._mapping) for row in workers]}


@router.get("/academics/reports/{report_type}.csv")
def academic_report(report_type: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "export", governance=True)[0])
    if report_type not in REPORTS: raise HTTPException(404, "Unknown academic report")
    _, headers=REPORTS[report_type]; rows=[]
    if report_type == "quality-action-aging":
        rows=[[x.id,x.review_id,x.priority,x.state,x.deadline.isoformat() if x.deadline else ""] for x in scoped_academic_query(s,D.CorrectiveAction,ctx).all()]
    elif report_type == "approval-aging":
        rows=[[x.id,x.state,x.updated_at.isoformat() if x.updated_at else ""] for x in s.query(D.AcademicProposal).filter(D.AcademicProposal.tenant_id==TENANT).all()]
    elif report_type == "timetable-readiness":
        rows=[[x.id,x.kind,x.severity,x.status] for x in scoped_academic_query(s,D.TimetableException,ctx).all()]
    elif report_type == "delivery-status":
        rows=[[x.section_id,x.term,x.completion_pct,x.status] for x in s.query(D.CourseCompletion).filter(D.CourseCompletion.tenant_id==TENANT).all()]
    elif report_type == "curriculum-version-history":
        rows=[[x.id,x.program_id,x.effective_term,x.version,x.status] for x in s.query(D.CurriculumVersion).filter(D.CurriculumVersion.tenant_id==TENANT).all()]
    elif report_type == "program-feasibility":
        rows=[[x.proposal_id,x.capacity,x.intake,x.faculty_ready,x.infrastructure_ready] for x in s.query(D.ProgramAssessment).filter(D.ProgramAssessment.tenant_id==TENANT).all()]
    elif report_type == "faculty-workload":
        rows=[[x.faculty_person_id,x.term,x.workload_units] for x in s.query(D.FacultyAllocation).filter(D.FacultyAllocation.tenant_id==TENANT).all()]
    elif report_type == "co-po-attainment":
        data=attainment("","",ctx,s); rows=[["CO",x["code"],x["attainment"]] for x in data["course_outcomes"]]+[["PO",x["code"],x["attainment"]] for x in data["program_outcomes"]]
    elif report_type == "semester-comparison":
        rows=[[x.academic_year,"results",x.percentage] for x in s.query(D.StudentSubjectResult).filter(D.StudentSubjectResult.tenant_id==TENANT,D.StudentSubjectResult.percentage!=None).all()]
    output=io.StringIO(); csv.writer(output).writerows([headers,*rows])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition":f'attachment; filename="icms-{report_type}.csv"'})


@router.get("/academics/reports/{report_type}.{file_format}")
def academic_report_file(report_type: str, file_format: str, ctx=Depends(auth), s=Depends(db)):
    if file_format not in {"pdf", "xlsx"}: raise HTTPException(404, "Unsupported report format")
    csv_response=academic_report(report_type,ctx,s)
    rows=list(csv.reader(io.StringIO(csv_response.body.decode())))
    if file_format == "pdf":
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        stream=io.BytesIO(); page=canvas.Canvas(stream,pagesize=letter); y=760
        for row in rows:
            page.drawString(36,y," | ".join(str(item)[:35] for item in row)); y-=16
            if y < 40: page.showPage(); y=760
        page.save(); content=stream.getvalue(); media="application/pdf"
    else:
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,"w",zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/><Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/></Types>")
            archive.writestr("_rels/.rels", "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/></Relationships>")
            archive.writestr("xl/_rels/workbook.xml.rels", "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/></Relationships>")
            archive.writestr("xl/workbook.xml", "<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"><sheets><sheet name=\"Report\" sheetId=\"1\" r:id=\"rId1\"/></sheets></workbook>")
            cells=[]
            for row_no,row in enumerate(rows,1):
                cells.append(f"<row r=\"{row_no}\">"+"".join(f"<c t=\"inlineStr\"><is><t>{str(value).replace('&','&amp;').replace('<','&lt;')}</t></is></c>" for value in row)+"</row>")
            archive.writestr("xl/worksheets/sheet1.xml", "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetData>"+"".join(cells)+"</sheetData></worksheet>")
        content=stream.getvalue(); media="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(content,media_type=media,headers={"Content-Disposition":f'attachment; filename="icms-{report_type}.{file_format}"'})


def _ensure_student_portal_account(s, student):
    """Give an invoiced student a portal account, without duplicating existing users."""
    username = (student.roll_no or "").strip().lower()
    if not username:
        return False
    user = s.query(User).filter(func.lower(User.username) == username).first()
    if user:
        if student.user_id != user.id:
            student.user_id = user.id
        return False

    person_id = f"person_student_{username}"
    if not s.get(Person, person_id):
        s.add(Person(id=person_id, tenant_id=TENANT, name=student.name,
                     email=student.email or f"{username}@icms.edu", contact=""))
    user = User(id=f"user_student_{username}", tenant_id=TENANT, person_id=person_id,
                username=username, password_hash=pwhash("demo123"), status="active",
                mfa_enabled=False, office_n=36, role="Student", scope_level="individual",
                scope_ref=student.id)
    s.add(user)
    student.user_id = user.id
    return True

# Which module actions are monetary approvals (limit-checked & escalatable).
MONETARY = {("finance", "waive"): ("fee_waiver", "Vice-Chancellor"),
            ("finance", "approve_budget"): ("purchase_request", "CFO"),
            ("procurement", "approve"): ("purchase_request", "CFO")}


# --------------------------------------------------------------------------- #
#  Authority gate for a module action                                         #
# --------------------------------------------------------------------------- #
ACADEMIC_GOVERNANCE_OFFICES = {6, 10, 17}


def academic_scope_allows(ctx, *, dept_id=None, program_id=None, section_id=None) -> bool:
    """Central academic-object scope policy used by governance endpoints."""
    office_n = ctx.get("office_n")
    if office_n == 6:
        return True
    if office_n not in ACADEMIC_GOVERNANCE_OFFICES:
        return False
    scope_ref = (ctx.get("scope_ref") or "").strip()
    # HOD/coordinator tokens carry department scope; tolerate legacy tokens
    # whose scope is represented by the staff profile (checked by callers).
    if dept_id and scope_ref and scope_ref not in {dept_id, f"dept_{dept_id}", f"scope_{dept_id}"}:
        return False
    return True


def actor_department_id(s, ctx):
    staff = _staff_profile(s, ctx)
    if staff and staff.dept_id:
        return staff.dept_id
    scope_ref = (ctx.get("scope_ref") or "").strip()
    # Department identifiers are commonly named ``dept_*``.  Resolve the
    # persisted identifier before treating that prefix as a scope wrapper.
    if scope_ref and s.get(D.Department, scope_ref):
        return scope_ref
    ref = scope_ref.removeprefix("dept_").removeprefix("scope_")
    return ref if s.get(D.Department, ref) else None


def scoped_academic_query(s, model, ctx):
    """Build a database-scoped query for academic models (never frontend-filtered)."""
    q = s.query(model).filter(getattr(model, "tenant_id") == ctx.get("tenant_id", TENANT))
    if ctx.get("office_n") == 6:
        assignments = dean_scope_assignments(ctx, s)
        # Development compatibility is intentionally temporary: a local legacy
        # database without assignments remains readable.  Production has no
        # equivalent fallback and fails closed.
        from database import demo_data_enabled
        if not assignments:
            return q if demo_data_enabled() else q.filter(false())
        clauses = []
        for assignment in assignments:
            filters = []
            unsupported_narrow_scope = False
            if assignment.school_id:
                if hasattr(model, "school_id"):
                    filters.append(getattr(model, "school_id") == assignment.school_id)
                elif getattr(model, "__tablename__", "") == "departments":
                    filters.append(or_(D.Department.school_id == assignment.school_id, D.Department.campus == assignment.school_id))
                elif getattr(model, "__tablename__", "") == "schools":
                    filters.append(D.School.id == assignment.school_id)
                else:
                    unsupported_narrow_scope = True
            if assignment.dept_id:
                if hasattr(model, "dept_id"):
                    filters.append(getattr(model, "dept_id") == assignment.dept_id)
                elif getattr(model, "__tablename__", "") == "departments":
                    filters.append(D.Department.id == assignment.dept_id)
                else:
                    unsupported_narrow_scope = True
            if assignment.program_id:
                if hasattr(model, "program_id"):
                    filters.append(getattr(model, "program_id") == assignment.program_id)
                elif getattr(model, "__tablename__", "") == "programs":
                    filters.append(D.Program.id == assignment.program_id)
                else:
                    unsupported_narrow_scope = True
            if assignment.section_id:
                if hasattr(model, "section_id"):
                    filters.append(getattr(model, "section_id") == assignment.section_id)
                elif getattr(model, "__tablename__", "") == "sections":
                    filters.append(D.Section.id == assignment.section_id)
                else:
                    unsupported_narrow_scope = True
            if not unsupported_narrow_scope:
                clauses.append(and_(*filters) if filters else false())
        return q.filter(or_(*clauses)) if clauses else q.filter(false())
    ref = (ctx.get("scope_ref") or "").strip()
    school_ref = ref if ref.startswith("school_") else None
    ref = actor_department_id(s, ctx) or ref.removeprefix("dept_").removeprefix("scope_")
    if school_ref and hasattr(model, "school_id"):
        return q.filter(getattr(model, "school_id") == school_ref)
    if ref and getattr(model, "__tablename__", "") == "departments":
        return q.filter(getattr(model, "id") == ref)
    if ref and hasattr(model, "dept_id"):
        q = q.filter(getattr(model, "dept_id") == ref)
    elif ref and hasattr(model, "scope_ref"):
        q = q.filter(getattr(model, "scope_ref") == ref)
    return q


def require_academic_object(s, ctx, obj, action="read", label="academic object", allow_dean=True):
    if not obj:
        raise HTTPException(404, f"{label} not found")
    authorize_object(ctx, s, obj, action, allow_dean=allow_dean)
    return obj


def gate(s, ctx, module: str, action: str, amount=None, governance: bool = False):
    """Return the Decision for (module, action); raise 403 if not ALLOW/ESCALATE."""
    verb = MODULE_ACTIONS.get(module, {}).get(action, "view")
    o = office(ctx["office_n"])
    if governance and ctx.get("office_n") not in ACADEMIC_GOVERNANCE_OFFICES:
        from authority import Decision, DENY
        return Decision(DENY, "Only Dean Academics, HOD, or Academic Coordinator may access academic governance", "Not Allowed"), "view"
    rbac = rbac_for(ctx["office_n"], o["level"], verb)
    # Front Office cleanup is enforced server-side. Hiding its sidebar alone
    # must never leave shared domain APIs reachable with a copied URL/token.
    if ctx["office_n"] == 35 and module not in modules_for_office(35):
        from authority import Decision, DENY
        return Decision(DENY, f"{module} is not available to Front Office", rbac), verb
    # Office-level reservation of sensitive actions (Document §9 invariants, §10).
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
    if ctx["office_n"] == 35 and module not in modules_for_office(35):
        return False
    if action != "view" and not action_allowed_for_office(module, action, ctx["office_n"]):
        return False
    return rbac_for(ctx["office_n"], o["level"], verb) not in ("Not Allowed",)


def require(dec):
    if dec.outcome not in ("ALLOW", "ESCALATE"):
        raise HTTPException(403, dec.reason)


def require_tenant(row, ctx, label="record"):
    if not row or getattr(row, "tenant_id", None) != ctx.get("tenant_id", TENANT):
           raise HTTPException(404, f"{label} not found")
    return row


class DeanScopeAssignmentIn(BaseModel):
    dean_user_id: str
    school_id: str = ""
    dept_id: str = ""
    program_id: str = ""
    section_id: str = ""
    effective_from: datetime | None = None
    effective_to: datetime | None = None


def _dean_scope_payload(row):
    return {
        "id": row.id, "dean_user_id": row.dean_user_id, "school_id": row.school_id,
        "dept_id": row.dept_id, "program_id": row.program_id, "section_id": row.section_id,
        "active": row.active, "effective_from": row.effective_from.isoformat() if row.effective_from else None,
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
    }


def _validate_dean_scope(s, ctx, body: DeanScopeAssignmentIn):
    dean = s.get(User, body.dean_user_id)
    if not dean or dean.tenant_id != ctx["tenant_id"] or dean.office_n != 6:
        raise HTTPException(422, "dean_user_id must identify an active Dean Academics user in this tenant")
    school = s.get(D.School, body.school_id) if body.school_id else None
    dept = s.get(D.Department, body.dept_id) if body.dept_id else None
    program = s.get(D.Program, body.program_id) if body.program_id else None
    section = s.get(D.Section, body.section_id) if body.section_id else None
    for label, row in (("school", school), ("department", dept), ("program", program), ("section", section)):
        if (getattr(body, f"{label}_id", "") if label != "department" else body.dept_id) and (not row or row.tenant_id != ctx["tenant_id"]):
            raise HTTPException(422, f"{label} is not in this tenant")
    if dept and school and dept.school_id and dept.school_id != school.id:
        raise HTTPException(422, "Department is not in the selected school")
    if program and dept and program.dept_id != dept.id:
        raise HTTPException(422, "Program is not in the selected department")
    if section and dept and section.dept_id != dept.id:
        raise HTTPException(422, "Section is not in the selected department")
    if section and program:
        course = s.get(D.Course, section.course_id)
        if not course or course.program_id != program.id:
            raise HTTPException(422, "Section is not in the selected program")
    if body.effective_to and body.effective_from and body.effective_to < body.effective_from:
        raise HTTPException(422, "effective_to cannot precede effective_from")


@router.get("/academics/dean-scope-assignments")
def list_dean_scope_assignments(ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] not in {6, 28}:
        raise HTTPException(403, "Only Dean Academics or System Administration may view Dean scope assignments")
    query = s.query(D.DeanScopeAssignment).filter(D.DeanScopeAssignment.tenant_id == ctx["tenant_id"])
    if ctx["office_n"] == 6:
        query = query.filter(D.DeanScopeAssignment.dean_user_id == ctx["sub"])
    return {"assignments": [_dean_scope_payload(row) for row in query.order_by(D.DeanScopeAssignment.created_at.desc()).all()]}


@router.post("/academics/dean-scope-assignments")
def create_dean_scope_assignment(body: DeanScopeAssignmentIn, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] != 28:
        raise HTTPException(403, "Only System Administration may assign Dean academic scope")
    _validate_dean_scope(s, ctx, body)
    now = datetime.utcnow()
    row = D.DeanScopeAssignment(
        id=uid(), tenant_id=ctx["tenant_id"], dean_user_id=body.dean_user_id,
        school_id=body.school_id or None, dept_id=body.dept_id or None,
        program_id=body.program_id or None, section_id=body.section_id or None,
        active=True, effective_from=body.effective_from or now, effective_to=body.effective_to,
        created_by=ctx["sub"], created_at=now, updated_at=now,
    )
    s.add(row)
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic.dean_scope.assign",
                f"dean_scope_assignment:{row.id}", "", "active", json.dumps(_dean_scope_payload(row)), commit=False)
    s.commit()
    return {"assignment": _dean_scope_payload(row)}


def prevent_self_approval(proposal, ctx):
    if proposal.submitted_by == ctx.get("sub"):
        raise HTTPException(403, "Proposal submitter cannot approve or reject their own proposal")


def claim_proposal_transition(s, proposal, expected_version, valid_states):
    updated = (s.query(D.AcademicProposal)
               .filter(D.AcademicProposal.id == proposal.id,
                       D.AcademicProposal.status_version == expected_version,
                       D.AcademicProposal.state.in_(valid_states))
               .update({D.AcademicProposal.status_version: D.AcademicProposal.status_version + 1},
                       synchronize_session=False))
    if updated != 1:
        raise HTTPException(409, "Proposal changed or is no longer awaiting this transition")
    s.refresh(proposal)


def actor_name(s, ctx):
    u = s.query(User).get(ctx["sub"])
    if not u:
        return ctx["sub"]
    p = s.query(Person).get(u.person_id)
    return p.name if p else u.username


def _staff_profile(s, ctx):
    return s.query(D.StaffMember).filter(D.StaffMember.user_id == ctx["sub"]).first()


def _faculty_or_403(s, ctx):
    staff = _staff_profile(s, ctx)
    if not staff or ctx["office_n"] not in {11, 12, 13, 14}:
        raise HTTPException(403, "Teaching faculty access required")
    return staff


def _session_or_404(s, session_id):
    session = s.query(D.ClassSession).get(session_id)
    if not session:
        raise HTTPException(404, "Class session not found")
    return session


def _checkin_window_open(session, now):
    if not session.scheduled_start or not session.scheduled_end:
        return True
    return session.scheduled_start - timedelta(minutes=30) <= now <= session.scheduled_end + timedelta(minutes=30)


def _section_or_404(s, section_id: str):
    row = s.query(D.Section).get(section_id)
    if not row:
        raise HTTPException(404, "Section not found")
    return row


def _section_course_payloads(s):
    return {c.id: c for c in s.query(D.Course).all()}


def _section_faculty_names(s):
    return {f.id: f.name for f in s.query(D.StaffMember).all()}


def _can_manage_section_for_timetable(s, ctx, section):
    if ctx["office_n"] == 6:
        try:
            authorize_object(ctx, s, section, "edit")
            return True
        except HTTPException:
            return False
    staff = _staff_profile(s, ctx)
    if ctx["office_n"] in {43}:
        return bool(staff and staff.dept_id == section.dept_id)
    return False


def _can_manage_section_for_tasks(s, ctx, section):
    staff = _staff_profile(s, ctx)
    if ctx["office_n"] in {11, 12, 13, 14}:
           return bool(staff and section.faculty_person_id == staff.id)
    if ctx["office_n"] in {10, 17}:
        return bool(staff and staff.dept_id == section.dept_id)
    return ctx["office_n"] == 6


def _can_manage_section_for_assessments(s, ctx, section):
    staff = _staff_profile(s, ctx)
    if ctx["office_n"] == 16:
        return True
    if ctx["office_n"] in {11, 12, 13, 14}:
           return bool(staff and section.faculty_person_id == staff.id)
    return bool(ctx["office_n"] in {10, 17} and staff and staff.dept_id == section.dept_id)


def _format_time_label(start_time: str, end_time: str) -> str:
    return f"{start_time} - {end_time}"


# --------------------------------------------------------------------------- #
#  Capabilities: what modules + actions this session has                       #
# --------------------------------------------------------------------------- #
@router.get("/workspace")
def workspace(ctx=Depends(auth), s=Depends(db)):
    """Modules + per-module allowed actions for the signed-in office/role."""
    o = office(ctx["office_n"])
    mods = []
    for key in modules_for_office(ctx["office_n"]):
        meta = module_meta(key)
        actions = {}
        for act in MODULE_ACTIONS.get(key, {}):
            actions[act] = can(s, ctx, key, act)
        mods.append({**meta, "actions": actions})
    return {"office_n": ctx["office_n"], "office": o.get("name"),
            "level": o.get("level"), "scope_level": ctx.get("scope_level"),
            "modules": mods}


# --------------------------------------------------------------------------- #
#  Overview / analytics counters                                              #
# --------------------------------------------------------------------------- #
@router.get("/overview")
def overview(ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] == 35:
           raise HTTPException(403, "The generic institutional overview is not available to Front Office.")
    def c(model):
        return s.query(model).count()
    stats = {
           "students": c(D.Student), "faculty": c(D.StaffMember),
        "courses": c(D.Course), "sections": c(D.Section),
        "applications": s.query(D.Application).filter(D.Application.status.in_(["submitted", "verified"])).count(),
        "fees_due": s.query(func.coalesce(func.sum(D.FeeInvoice.amount - D.FeeInvoice.paid), 0)).filter(D.FeeInvoice.status != "paid").scalar() or 0,
        "books": c(D.Book), "projects": s.query(D.ResearchProject).filter(D.ResearchProject.status == "ongoing").count(),
        "open_complaints": s.query(D.Complaint).filter(D.Complaint.status != "resolved").count(),
        "pending_leave": s.query(D.LeaveRequest).filter(D.LeaveRequest.status == "pending").count(),
        "placement_offers": s.query(func.coalesce(func.sum(D.PlacementDrive.offers), 0)).scalar() or 0,
    }
    # department distribution for charts
    dept_counts = dict(s.query(D.Department.code, func.count(D.Student.id))
                       .join(D.Student, D.Student.dept_id == D.Department.id)
                       .group_by(D.Department.code).all())
    return {"stats": stats, "dept_distribution": dept_counts}


@router.get("/overview/principal")
def principal_overview(academic_year: str = "", student_semester: str = "", ctx=Depends(auth), s=Depends(db)):
    """Branch-leadership dashboard aggregates, calculated only from domain records."""
    require(gate(s, ctx, "analytics", "view")[0])
    terms = [row[0] for row in s.query(D.AcademicCalendarEntry.term).distinct().all() if row[0]]
    def academic_year_for(term):
        try:
            y = int(str(term)[:4])
            return f"{y - 1 if str(term).lower().endswith('even') else y}-{str((y if str(term).lower().endswith('even') else y + 1))[-2:]}"
        except (TypeError, ValueError): return ""
    years = sorted(set(filter(None, (academic_year_for(t) for t in terms))), reverse=True)
    selected_year = academic_year if academic_year in years else (years[0] if years else "")
    student_query = _student_scope(
        s.query(D.Student).filter(D.Student.status == "active"), ctx
    )
    try:
        selected_student_semester = int(student_semester) if student_semester else 0
    except (TypeError, ValueError):
        selected_student_semester = 0
    selected_student_semester = selected_student_semester if selected_student_semester in range(1, 9) else 0
    if selected_student_semester: student_query = student_query.filter(D.Student.semester == selected_student_semester)
    students = student_query.all()
    student_ids = [row.id for row in students]
    attendance = s.query(D.AttendanceRecord).filter(D.AttendanceRecord.student_id.in_(student_ids)).all() if student_ids else []
    today = date.today()
    today_rows = [row for row in attendance if row.on_date == today]
    attendance_pct = round(100 * sum(1 for row in today_rows if row.present) / len(today_rows), 1) if today_rows else None
    # Monthly points use actual recorded attendance; no synthetic graph values.
    trend = []
    month_cursor = today.replace(day=1)
    months = []
    for _ in range(6):
        months.append(month_cursor)
        month_cursor = (month_cursor - timedelta(days=1)).replace(day=1)
    months.reverse()
    for month in months:
        next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
        rows = [r for r in attendance if month <= r.on_date < next_month]
        trend.append({"label": month.strftime("%b"), "value": round(100 * sum(1 for r in rows if r.present) / len(rows), 1) if rows else None})
    cgpas = [row.cgpa or 0 for row in students]
    avg_cgpa = round(sum(cgpas) / len(cgpas), 2) if cgpas else 0
    pass_rate = round(100 * sum(1 for x in cgpas if x >= 4.5) / len(cgpas), 1) if cgpas else None
    bands = {"distinction": sum(1 for x in cgpas if x >= 7.5), "first": sum(1 for x in cgpas if 6 <= x < 7.5), "second": sum(1 for x in cgpas if 4.5 <= x < 6), "others": sum(1 for x in cgpas if x < 4.5)}
    open_complaints = s.query(D.Complaint).filter(D.Complaint.status != "resolved").count()
    pending_workflows = s.query(WorkflowInstance).filter(WorkflowInstance.office_n == ctx["office_n"], WorkflowInstance.state.in_(["submitted", "under_review", "reviewed", "escalated"])).all()
    assessments = s.query(D.Assessment).count(); marks = s.query(D.Mark).count()
    asset_maintenance = s.query(D.Asset).filter(D.Asset.status == "maintenance").count()
    notifications = s.query(Notification).filter(Notification.user_id == ctx["sub"]).order_by(desc(Notification.created_at)).limit(6).all()
    return {
        "filters": {"academic_years": years, "selected_year": selected_year, "selected_student_semester": selected_student_semester, "student_semesters": list(range(1, 9))},
        "kpis": {"students": len(students), "faculty": s.query(D.StaffMember).filter(D.StaffMember.status == "active").count(), "attendance": attendance_pct, "decisions": len(pending_workflows), "risk_students": sum(1 for x in cgpas if x < 6), "critical_alerts": sum(1 for n in notifications if n.severity == "critical")},
        "attendance": {"today": attendance_pct, "today_records": len(today_rows), "trend": trend},
        "performance": {"average_cgpa": avg_cgpa, "pass_rate": pass_rate, "bands": bands, "at_risk": sum(1 for x in cgpas if x < 6), "backlogs": sum(1 for x in cgpas if x < 4.5)},
        "examinations": {"sections": s.query(D.Section).count(), "assessments": assessments, "marks_submitted": marks, "pending_moderation": s.query(D.ResultSheet).filter(D.ResultSheet.status != "published").count()},
        "welfare": {"at_risk": sum(1 for x in cgpas if x < 6), "grievances": s.query(D.Complaint).filter(D.Complaint.kind == "Grievance", D.Complaint.status != "resolved").count(), "discipline": s.query(D.Complaint).filter(D.Complaint.kind == "Discipline", D.Complaint.status != "resolved").count(), "critical": s.query(D.Complaint).filter(D.Complaint.severity == "high", D.Complaint.status != "resolved").count()},
        # Procurement and asset-request records are not modelled yet.  Return
        # an explicit unavailable value rather than presenting a fabricated 0.
        "operations": {"maintenance": asset_maintenance, "procurement": None, "asset_requests": None, "facilities": asset_maintenance},
        "workflows": [{"id": w.id, "title": w.title, "label": w.process_key.replace('_', ' ').title(), "state": w.state, "initiator": w.initiator_name or "Request"} for w in pending_workflows[:5]],
        "notifications": [{"id": n.id, "title": n.title, "severity": n.severity, "created_at": n.created_at.isoformat()} for n in notifications],
    }


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _month_end(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1) - timedelta(days=1)
    return date(d.year, d.month + 1, 1) - timedelta(days=1)


def _previous_month(d: date) -> date:
    return _month_start(d) - timedelta(days=1)


def _fmt_range(start: date, end: date) -> str:
    return f"{start.strftime('%d %b %Y')} - {end.strftime('%d %b %Y')}"


def _month_label(d: date) -> str:
    return d.strftime("%B %Y")


def _period_delta(current: int, previous: int) -> dict:
    delta = current - previous
    return {
        "change": abs(delta),
        "direction": "up" if delta >= 0 else "down",
    }


def _percent_delta(current: float, previous: float) -> dict:
    if not previous:
        return {"delta_pct": 0.0, "direction": "up"}
    delta = ((current - previous) / previous) * 100
    return {
        "delta_pct": round(abs(delta), 1),
        "direction": "up" if delta >= 0 else "down",
    }


@router.get("/overview/chairman")
def chairman_overview(start: str = "", end: str = "", ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "governance", "view")[0])

    available_snapshots = (s.query(D.InstitutionSnapshot)
                           .order_by(D.InstitutionSnapshot.snapshot_month.desc()).all())
    latest_snapshot = available_snapshots[0] if available_snapshots else None
    selected_start = date.fromisoformat(start) if start else (
        latest_snapshot.snapshot_month if latest_snapshot else _month_start(date.today())
    )
    selected_start = _month_start(selected_start)
    selected_end = date.fromisoformat(end) if end else _month_end(selected_start)
    previous_start = _month_start(_previous_month(selected_start))
    previous_end = _month_end(previous_start)

    snapshot = (s.query(D.InstitutionSnapshot)
                .filter(D.InstitutionSnapshot.snapshot_month == selected_start).first())
    previous_snapshot = (s.query(D.InstitutionSnapshot)
                         .filter(D.InstitutionSnapshot.snapshot_month == previous_start).first())

    current_outstanding = snapshot.outstanding_fees if snapshot else 0
    previous_outstanding = previous_snapshot.outstanding_fees if previous_snapshot else 0
    outstanding_delta = round(
        ((current_outstanding - previous_outstanding) / previous_outstanding) * 100, 1
    ) if previous_outstanding else 0

    acc_total = (s.query(D.Accreditation)
                 .filter(D.Accreditation.status == "active",
                         D.Accreditation.awarded_on <= selected_end).count())
    acc_current = (s.query(D.Accreditation)
                   .filter(D.Accreditation.awarded_on >= selected_start,
                           D.Accreditation.awarded_on <= selected_end).count())
    acc_previous = (s.query(D.Accreditation)
                    .filter(D.Accreditation.awarded_on >= previous_start,
                            D.Accreditation.awarded_on <= previous_end).count())

    partner_total = (s.query(D.Partner)
                     .filter(D.Partner.status == "active",
                             D.Partner.started_on <= selected_end).count())
    partner_current = (s.query(D.Partner)
                       .filter(D.Partner.started_on >= selected_start,
                               D.Partner.started_on <= selected_end).count())
    partner_previous = (s.query(D.Partner)
                        .filter(D.Partner.started_on >= previous_start,
                                D.Partner.started_on <= previous_end).count())

    esc_total = (s.query(WorkflowInstance)
                 .filter(WorkflowInstance.state == "escalated",
                         WorkflowInstance.updated_at <= datetime.combine(selected_end, datetime.max.time()))
                 .count())
    esc_current = (s.query(WorkflowInstance)
                   .filter(WorkflowInstance.state == "escalated",
                           WorkflowInstance.updated_at >= datetime.combine(selected_start, datetime.min.time()),
                           WorkflowInstance.updated_at <= datetime.combine(selected_end, datetime.max.time()))
                   .count())
    esc_previous = (s.query(WorkflowInstance)
                    .filter(WorkflowInstance.state == "escalated",
                            WorkflowInstance.updated_at >= datetime.combine(previous_start, datetime.min.time()),
                            WorkflowInstance.updated_at <= datetime.combine(previous_end, datetime.max.time()))
                    .count())

    institution = {
        "schools": s.query(D.School).filter(D.School.status == "active").count(),
        "departments": s.query(D.Department).count(),
        "programs": s.query(D.Program).count(),
        "campuses": s.query(OrgScope).filter(OrgScope.level == "campus").count(),
        "total_staff": snapshot.total_staff if snapshot else s.query(D.StaffMember).count(),
        "non_teaching_staff": snapshot.non_teaching_staff if snapshot else 0,
        "active_users": snapshot.active_users if snapshot else s.query(User).filter(User.status == "active").count(),
        "system_uptime": snapshot.system_uptime if snapshot else 99.0,
    }

    ytd_start = date(selected_end.year, 1, 1)
    entries = (s.query(D.FinancialEntry)
               .filter(D.FinancialEntry.recorded_on >= ytd_start,
                       D.FinancialEntry.recorded_on <= selected_end).all())
    income_entries = [row for row in entries if row.entry_type == "income"]
    expense_entries = [row for row in entries if row.entry_type == "expense"]
    total_income = sum(row.amount for row in income_entries)
    total_expense = sum(row.amount for row in expense_entries)
    category_order = ["Tuition Fees", "Grants & Funding", "Other Income", "Investments", "Other Sources"]
    category_totals = {name: 0 for name in category_order}
    for row in income_entries:
        category_totals[row.category] = category_totals.get(row.category, 0) + row.amount
    finance_segments = [{
        "name": name,
        "amount": category_totals.get(name, 0),
        "percent": round((category_totals.get(name, 0) / total_income) * 100, 1) if total_income else 0,
    } for name in category_order]

    pending_states = ["submitted", "under_review", "reviewed", "escalated"]
    approval_rows = (s.query(WorkflowInstance.title, func.count(WorkflowInstance.id))
                     .filter(WorkflowInstance.state.in_(pending_states))
                     .group_by(WorkflowInstance.title).all())
    preferred = [
        "Campus Development Plan",
        "Budget Proposals",
        "Policy & Regulation Updates",
        "Partnership & MoUs",
    ]
    approval_map = {title: count for title, count in approval_rows}
    key_approvals = [{
        "title": title,
        "count": approval_map.get(title, 0),
        "status": "Pending",
    } for title in preferred]

    chairman = s.query(User).filter(User.username == "chairman").first()
    alert_rows = []
    if chairman:
        alert_rows = (s.query(Notification)
                      .filter(Notification.user_id == chairman.id)
                      .order_by(Notification.created_at.desc()).limit(4).all())
    alerts = [{
        "title": row.title,
        "body": row.body,
        "severity": row.severity,
        "at": row.created_at.isoformat(),
    } for row in alert_rows]
    if not alerts:
        alerts = [{
            "title": "No active alerts",
            "body": "This executive workspace is currently clear of urgent notifications.",
            "severity": "info",
            "at": datetime.utcnow().isoformat(),
        }]

    ranges = [{
        "start": item.snapshot_month.isoformat(),
        "end": _month_end(item.snapshot_month).isoformat(),
        "label": _fmt_range(item.snapshot_month, _month_end(item.snapshot_month)),
    } for item in available_snapshots]
    if not ranges:
        ranges = [{
            "start": selected_start.isoformat(),
            "end": selected_end.isoformat(),
            "label": _fmt_range(selected_start, selected_end),
        }]

    return {
        "range": {
            "start": selected_start.isoformat(),
            "end": selected_end.isoformat(),
            "label": _fmt_range(selected_start, selected_end),
            "available_ranges": ranges,
        },
        "welcome": {
            "title": "Welcome, Chairman",
            "subtitle": "Real-time overview of the institution group across all campuses and entities.",
        },
        "kpis": {
            "outstanding_fees": {
                "value": current_outstanding,
                "delta": outstanding_delta,
                "direction": "up" if outstanding_delta >= 0 else "down",
                "tone": "positive",
            },
            "accreditations": {
                "value": acc_total,
                **_period_delta(acc_current, acc_previous),
                "tone": "positive",
            },
            "partners": {
                "value": partner_total,
                **_period_delta(partner_current, partner_previous),
                "tone": "positive",
            },
            "escalations": {
                "value": esc_total,
                **_period_delta(esc_current, esc_previous),
                "tone": "negative",
            },
        },
        "institution": institution,
        "financial": {
            "total_income": total_income,
            "total_expense": total_expense,
            "surplus": total_income - total_expense,
            "segments": finance_segments,
        },
        "key_approvals": key_approvals,
        "alerts": alerts,
    }


@router.get("/overview/chairman/outstanding-fees")
def chairman_outstanding_fees(start: str = "", ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "governance", "view")[0])

    available = (s.query(D.OutstandingFeeSnapshot)
                 .order_by(D.OutstandingFeeSnapshot.snapshot_month.desc()).all())
    latest = available[0] if available else None
    selected_start = date.fromisoformat(start) if start else (
        latest.snapshot_month if latest else _month_start(date.today())
    )
    selected_start = _month_start(selected_start)

    current = (s.query(D.OutstandingFeeSnapshot)
               .filter(D.OutstandingFeeSnapshot.snapshot_month == selected_start).first())
    if not current and latest:
        current = latest
        selected_start = latest.snapshot_month
    if not current:
        return {
            "range": {"start": selected_start.isoformat(), "label": _month_label(selected_start)},
            "summary": {
                "total_outstanding": {"value": 0, "delta_pct": 0, "direction": "up"},
                "students_with_dues": {"value": 0, "delta_pct": 0, "direction": "up"},
                "overdue_over_60": {"value": 0, "delta_pct": 0, "direction": "up"},
                "notices_sent": {"value": 0, "delta_pct": 0, "direction": "up"},
            },
            "trend": [],
        }

    previous = (s.query(D.OutstandingFeeSnapshot)
                .filter(D.OutstandingFeeSnapshot.snapshot_month < selected_start)
                .order_by(D.OutstandingFeeSnapshot.snapshot_month.desc()).first())

    trend_rows = (s.query(D.OutstandingFeeSnapshot)
                  .filter(D.OutstandingFeeSnapshot.snapshot_month <= selected_start)
                  .order_by(D.OutstandingFeeSnapshot.snapshot_month.desc()).limit(6).all())
    trend_rows = list(reversed(trend_rows))

    return {
        "range": {
            "start": selected_start.isoformat(),
            "end": _month_end(selected_start).isoformat(),
            "label": _fmt_range(selected_start, _month_end(selected_start)),
        },
        "summary": {
            "total_outstanding": {
                "value": current.outstanding_amount,
                **_percent_delta(current.outstanding_amount, previous.outstanding_amount if previous else 0),
            },
            "students_with_dues": {
                "value": current.students_with_dues,
                **_percent_delta(current.students_with_dues, previous.students_with_dues if previous else 0),
            },
            "overdue_over_60": {
                "value": current.overdue_over_60,
                **_percent_delta(current.overdue_over_60, previous.overdue_over_60 if previous else 0),
            },
            "notices_sent": {
                "value": current.notices_sent,
                **_percent_delta(current.notices_sent, previous.notices_sent if previous else 0),
            },
        },
        "trend": [{
            "label": row.snapshot_month.strftime("%b %Y"),
            "month": row.snapshot_month.isoformat(),
            "value": row.outstanding_amount,
        } for row in trend_rows],
    }


# --------------------------------------------------------------------------- #
#  CALENDAR HUB
# --------------------------------------------------------------------------- #
CALENDAR_ACADEMIC_EDITORS = {1, 2, 4, 5, 17}
# Calendar changes are governed by the Dean.  Operational staff submit proposals;
# the legacy CRUD routes below remain readable for already-published milestones.
CALENDAR_ACADEMIC_EDITORS = {6}
# Calendar changes are operational requests. The Dean independently reviews
# them and must never originate work that reaches their own approval queue.
CALENDAR_PROPOSERS = {42}
ACADEMIC_PROPOSAL_STATES = {"DRAFT", "SUBMITTED", "UNDER_REVIEW", "CLARIFICATION_REQUIRED", "RESUBMITTED", "APPROVED", "REJECTED", "RETURNED", "ESCALATED", "IMPLEMENTED", "CLOSED"}


def _month_label(d: date) -> str:
    return d.strftime("%B %Y")


def _parse_month(value: str = "") -> date:
    if not value:
        return _month_start(date.today())
    raw = date.fromisoformat(value)
    return _month_start(raw)


def _parse_datetime_value(value: str = "", end=False):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        day = date.fromisoformat(value)
        clock = datetime.max.time() if end else datetime.min.time()
        return datetime.combine(day, clock)


def _audiences_for_office(office_n: int) -> set:
    audiences = {"all"}
    if 1 <= office_n <= 35 or office_n == 40:
        audiences.add("staff")
    if office_n in {1, 2, 3, 4, 5, 6, 8, 9, 22, 24, 40}:
        audiences.add("leadership")
    if office_n in set(range(15, 36)) | {22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35}:
        audiences.add("operations")
    if office_n == 36:
        audiences.add("students")
    if office_n == 37:
        audiences.add("parents")
    return audiences


def _audience_visible(audience: str, tokens: set) -> bool:
    wanted = {item.strip().lower() for item in (audience or "all").split(",") if item.strip()}
    return bool(wanted & tokens) or "all" in wanted


def _calendar_event_editable(ctx, row) -> bool:
    if row.source_type != "manual" or row.status in ("deleted",):
        return False
    if ctx["office_n"] in {1, 2, 40}:
        return True
    return row.owner_office_n == ctx["office_n"] or row.created_by == ctx["sub"]


def _academic_entry_editable(ctx, row) -> bool:
    return ctx["office_n"] in CALENDAR_ACADEMIC_EDITORS and row.status != "deleted"


def _proposal_version(s, proposal):
    return (s.query(D.AcademicProposalVersion)
            .filter(D.AcademicProposalVersion.proposal_id == proposal.id,
                    D.AcademicProposalVersion.version_no == proposal.version_no).first())


def _proposal_payload(s, proposal):
    version = _proposal_version(s, proposal)
    data = json.loads(version.payload_json or "{}") if version else {}
    events = (s.query(D.AcademicProposalEvent)
              .filter(D.AcademicProposalEvent.proposal_id == proposal.id)
              .order_by(D.AcademicProposalEvent.created_at).all())
    return {"id": proposal.id, "type": proposal.proposal_type, "title": proposal.title,
            "state": proposal.state, "version_no": proposal.version_no,
            "status_version": proposal.status_version, "due_at": proposal.due_at.isoformat() if proposal.due_at else None,
            "submitted_by": proposal.submitted_by, "submitted_office_n": proposal.submitted_office_n,
            "implementation_ref": proposal.implementation_ref, "payload": data,
            "events": [{"from": item.from_state, "to": item.to_state, "reason": item.reason,
                        "actor_id": item.actor_id, "office_n": item.actor_office_n,
                        "at": item.created_at.isoformat() if item.created_at else None} for item in events]}


def _proposal_event(s, proposal, ctx, previous, target, reason=""):
    s.add(D.AcademicProposalEvent(id=uid(), tenant_id=TENANT, proposal_id=proposal.id,
                                  from_state=previous, to_state=target, actor_id=ctx["sub"],
                                  actor_office_n=ctx["office_n"], reason=reason))


def _proposal_notice(s, user_id, title, body, severity="action"):
    s.add(Notification(id=uid(), tenant_id=TENANT, user_id=user_id, severity=severity,
                       title=title, body=body))


def _calendar_impact(s, payload):
    """Identify affected published operational records before a Dean decision."""
    start = date.fromisoformat(payload["start_date"])
    end = date.fromisoformat(payload.get("end_date") or payload["start_date"])
    timetable = s.query(D.TimetableEntry).filter(D.TimetableEntry.status == "active").all()
    affected_timetable = [row.id for row in timetable if row.effective_from and row.effective_from <= end and (not row.effective_to or row.effective_to >= start)]
    exams = s.query(D.ExamScheduleEntry).filter(D.ExamScheduleEntry.status.in_(["scheduled", "rescheduled"])).all()
    affected_exams = [row.id for row in exams if row.start_at and start <= row.start_at.date() <= end]
    return {"timetable_entries": affected_timetable, "exam_schedule_entries": affected_exams,
            "requires_exception_review": bool(affected_timetable or affected_exams)}


def _event_payload(event_id, title, category, audience, start_dt, end_dt,
                   *, all_day=False, location="", description="", source_type="manual",
                   source_ref="", color="", status="published", editable=False,
                   module_key="calendar"):
    return {
        "id": event_id,
        "title": title,
        "category": category,
        "audience": audience,
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat() if end_dt else "",
        "all_day": all_day,
        "location": location,
        "description": description,
        "source_type": source_type,
        "source_ref": source_ref,
        "color": color,
        "status": status,
        "editable": editable,
        "module_key": module_key,
        "_start_dt": start_dt,
        "_end_dt": end_dt or start_dt,
    }


def _strip_event_meta(item: dict) -> dict:
    return {k: v for k, v in item.items() if not k.startswith("_")}


def _linked_student(s, ctx):
    st = s.query(D.Student).filter(D.Student.user_id == ctx["sub"]).first()
    if st:
        return st
    scope_ref = ctx.get("scope_ref", "")
    if ctx["office_n"] in {36, 37} and scope_ref and not scope_ref.startswith("scope_"):
        st = s.query(D.Student).get(scope_ref)
    if st:
        return st
    login = s.query(User).get(ctx["sub"])
    if login and login.username in {"student", "parent"}:
        return s.query(D.Student).order_by(D.Student.cgpa.desc()).first()
    return None


def _fanout_notification(s, audience: str, title: str, body: str, severity="info"):
    tokens = {item.strip().lower() for item in (audience or "all").split(",") if item.strip()}
    users = s.query(User).filter(User.status == "active").all()
    notified = set()
    for user in users:
        if user.id in notified:
            continue
        if _audience_visible(",".join(tokens) if tokens else "all", _audiences_for_office(user.office_n)):
            s.add(Notification(id=uid(), tenant_id=TENANT, user_id=user.id,
                               severity=severity, title=title, body=body))
            notified.add(user.id)
    if notified:
        s.commit()


class CalendarEventIn(BaseModel):
    title: str
    category: str = "Institution"
    audience: str = "all"
    start_at: str
    end_at: str = ""
    all_day: bool = True
    location: str = ""
    description: str = ""
    color: str = ""
    status: str = "published"


class AcademicCalendarIn(BaseModel):
    term: str
    academic_year: str = ""
    program_id: str | None = None
    department_id: str | None = None
    student_year: int | None = Field(default=None, ge=1, le=4)
    title: str
    category: str = "Teaching"
    campus: str = "All Campuses"
    start_date: str
    end_date: str = ""
    start_time: str = ""
    end_time: str = ""
    description: str = ""
    status: str = "published"


@router.get("/calendar")
def calendar_view(start: str = "", ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "calendar", "view")[0])
    month_start = _parse_month(start)
    month_end = _month_end(month_start)
    start_dt = datetime.combine(month_start, datetime.min.time())
    end_dt = datetime.combine(month_end, datetime.max.time())
    viewer_tokens = _audiences_for_office(ctx["office_n"])

    events = []

    manual_rows = (s.query(D.CalendarEvent)
                   .filter(D.CalendarEvent.status != "deleted",
                           D.CalendarEvent.start_at <= end_dt,
                           func.coalesce(D.CalendarEvent.end_at, D.CalendarEvent.start_at) >= start_dt)
                   .order_by(D.CalendarEvent.start_at, D.CalendarEvent.title).all())
    for row in manual_rows:
        if not _audience_visible(row.audience, viewer_tokens):
            continue
        events.append(_event_payload(
            row.id, row.title, row.category, row.audience, row.start_at,
            row.end_at or row.start_at, all_day=row.all_day, location=row.location,
            description=row.description, source_type=row.source_type,
            source_ref=row.source_ref, color=row.color, status=row.status,
            editable=_calendar_event_editable(ctx, row), module_key="calendar"
        ))

    academic_rows = (s.query(D.AcademicCalendarEntry)
                     .filter(D.AcademicCalendarEntry.status != "deleted",
                             D.AcademicCalendarEntry.start_date <= month_end,
                             func.coalesce(D.AcademicCalendarEntry.end_date, D.AcademicCalendarEntry.start_date) >= month_start)
                     .order_by(D.AcademicCalendarEntry.start_date, D.AcademicCalendarEntry.title).all())
    for row in academic_rows:
        acad_start = datetime.combine(row.start_date, datetime.min.time())
        acad_end = datetime.combine(row.end_date or row.start_date, datetime.max.time())
        events.append(_event_payload(
            f"acv_{row.id}", row.title, row.category, "all", acad_start, acad_end,
            all_day=True, location=row.campus, description=row.description,
            source_type="academic", source_ref=row.id, color="#2c5fb3",
            status=row.status, editable=False, module_key="academic_calendar"
        ))

    drive_rows = (s.query(D.PlacementDrive)
                  .filter(D.PlacementDrive.date >= month_start,
                          D.PlacementDrive.date <= month_end).all())
    for row in drive_rows:
        drive_dt = datetime.combine(row.date, datetime.min.time())
        events.append(_event_payload(
            f"drv_{row.id}", f"{row.company} placement drive", "Placements",
            "students,staff,leadership", drive_dt, drive_dt, all_day=True,
            location="Career Studio", description=f"{row.role} · eligible CGPA {row.eligible_cgpa}+",
            source_type="placement", source_ref=row.id, color="#0d9488",
            status=row.status, editable=False, module_key="placements"
        ))

    if ctx["office_n"] in {36, 37}:
        st = _linked_student(s, ctx)
        if st:
            for inv in (s.query(D.FeeInvoice)
                        .filter(D.FeeInvoice.student_id == st.id,
                                D.FeeInvoice.status != "paid",
                                D.FeeInvoice.due_date >= month_start,
                                D.FeeInvoice.due_date <= month_end).all()):
                due_dt = datetime.combine(inv.due_date, datetime.min.time())
                events.append(_event_payload(
                    f"fee_{inv.id}", f"Fee due · {inv.term}", "Finance", "students,parents",
                    due_dt, due_dt, all_day=True, location="Finance Office",
                    description=f"Outstanding balance: {inv.amount - inv.paid:,.0f}",
                    source_type="finance", source_ref=inv.id, color="#b97e1f",
                    status=inv.status, editable=False, module_key="finance"
                ))
            for loan in (s.query(D.BookLoan)
                         .filter(D.BookLoan.borrower == st.id,
                                 D.BookLoan.returned == False,
                                 D.BookLoan.due_on >= month_start,
                                 D.BookLoan.due_on <= month_end).all()):
                due_dt = datetime.combine(loan.due_on, datetime.min.time())
                events.append(_event_payload(
                    f"loan_{loan.id}", "Library return due", "Library", "students,parents",
                    due_dt, due_dt, all_day=True, location="Central Library",
                    description=f"{loan.borrower_name} must return borrowed material before fines apply.",
                    source_type="library", source_ref=loan.id, color="#162033",
                    status="scheduled", editable=False, module_key="library"
                ))
    else:
        fee_due_rows = (s.query(D.FeeInvoice.due_date, func.count(D.FeeInvoice.id),
                                func.coalesce(func.sum(D.FeeInvoice.amount - D.FeeInvoice.paid), 0))
                        .filter(D.FeeInvoice.status != "paid",
                                D.FeeInvoice.due_date >= month_start,
                                D.FeeInvoice.due_date <= month_end)
                        .group_by(D.FeeInvoice.due_date)
                        .order_by(D.FeeInvoice.due_date).limit(4).all())
        for due_date, count, amount in fee_due_rows:
            due_dt = datetime.combine(due_date, datetime.min.time())
            events.append(_event_payload(
                f"fee_rollup_{due_date.isoformat()}",
                f"Fee collection milestone · {count} invoices due", "Finance",
                "operations,leadership,staff", due_dt, due_dt, all_day=True,
                location="Finance Office",
                description=f"Pending collection exposure: {amount:,.0f}",
                source_type="finance", source_ref=due_date.isoformat(), color="#b97e1f",
                status="scheduled", editable=False, module_key="finance"
            ))

        loan_due_rows = (s.query(D.BookLoan.due_on, func.count(D.BookLoan.id))
                         .filter(D.BookLoan.returned == False,
                                 D.BookLoan.due_on >= month_start,
                                 D.BookLoan.due_on <= month_end)
                         .group_by(D.BookLoan.due_on)
                         .order_by(D.BookLoan.due_on).limit(3).all())
        for due_on, count in loan_due_rows:
            due_dt = datetime.combine(due_on, datetime.min.time())
            events.append(_event_payload(
                f"lib_rollup_{due_on.isoformat()}",
                f"Library returns due · {count} open loans", "Library",
                "staff,leadership,operations", due_dt, due_dt, all_day=True,
                location="Central Library",
                description="Open book-loan returns that can affect student clearances and penalty workflows.",
                source_type="library", source_ref=due_on.isoformat(), color="#334155",
                status="scheduled", editable=False, module_key="library"
            ))

    escalations = (s.query(func.date(WorkflowInstance.updated_at), func.count(WorkflowInstance.id))
                   .filter(WorkflowInstance.state == "escalated",
                           WorkflowInstance.updated_at >= start_dt,
                           WorkflowInstance.updated_at <= end_dt)
                   .group_by(func.date(WorkflowInstance.updated_at))
                   .order_by(func.date(WorkflowInstance.updated_at)).all())
    for day_value, count in escalations:
        esc_date = day_value if isinstance(day_value, date) else date.fromisoformat(str(day_value))
        esc_dt = datetime.combine(esc_date, datetime.min.time())
        events.append(_event_payload(
            f"esc_{esc_date.isoformat()}",
            f"Escalation review window · {count} workflows", "Governance",
            "leadership", esc_dt, esc_dt, all_day=True, location="Authority Queue",
            description="Escalated decisions awaiting governance visibility in the approval chain.",
            source_type="workflow", source_ref=esc_date.isoformat(), color="#d92d3a",
            status="action", editable=False, module_key="workflows"
        ))

    visible_events = [event for event in events if _audience_visible(event["audience"], viewer_tokens)]
    visible_events.sort(key=lambda item: (item["_start_dt"], item["title"]))

    today_dt = datetime.combine(date.today(), datetime.min.time())
    upcoming = [event for event in visible_events if event["_end_dt"] >= today_dt][:8]
    today_count = sum(1 for event in visible_events
                      if event["_start_dt"].date() <= date.today() <= event["_end_dt"].date())
    source_counts = {
        "manual": sum(1 for event in visible_events if event["source_type"] == "manual"),
        "academic": sum(1 for event in visible_events if event["source_type"] == "academic"),
        "linked": sum(1 for event in visible_events if event["source_type"] not in {"manual", "academic"}),
    }

    return {
        "range": {
            "start": month_start.isoformat(),
            "end": month_end.isoformat(),
            "label": _month_label(month_start),
        },
        "permissions": {
            "create": can(s, ctx, "calendar", "create"),
            "edit": can(s, ctx, "calendar", "edit"),
            "delete": can(s, ctx, "calendar", "delete"),
        },
        "summary": {
            "events": len(visible_events),
            "today": today_count,
            "upcoming": len(upcoming),
            "source_counts": source_counts,
        },
        "events": [_strip_event_meta(event) for event in visible_events],
        "upcoming": [_strip_event_meta(event) for event in upcoming],
    }


@router.post("/calendar")
def create_calendar_event(body: CalendarEventIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "calendar", "create")
    require(dec)
    now = datetime.utcnow()
    start_at = _parse_datetime_value(body.start_at)
    end_at = _parse_datetime_value(body.end_at, end=True) or start_at
    row = D.CalendarEvent(
        id=uid(), tenant_id=TENANT, title=body.title, category=body.category,
        audience=body.audience or "all", start_at=start_at, end_at=end_at,
        all_day=body.all_day, location=body.location, description=body.description,
        owner_office_n=ctx["office_n"], source_type="manual", source_ref="",
        color=body.color or "#8a1f2b", status=body.status or "published",
        created_by=ctx["sub"], updated_by=ctx["sub"], created_at=now, updated_at=now
    )
    s.add(row)
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "calendar.create",
                f"calendar:{row.id}", "", row.status,
                f"Created calendar event '{row.title}'")
    _fanout_notification(
        s, row.audience,
        f"Calendar updated: {row.title}",
        f"{row.category} event scheduled on {row.start_at.strftime('%d %b %Y %H:%M')}.",
        severity="info",
    )
    return {"event": _strip_event_meta(_event_payload(
        row.id, row.title, row.category, row.audience, row.start_at, row.end_at,
        all_day=row.all_day, location=row.location, description=row.description,
        source_type=row.source_type, source_ref=row.source_ref, color=row.color,
        status=row.status, editable=_calendar_event_editable(ctx, row)
    )), "decision": dec.as_dict()}


@router.put("/calendar/{event_id}")
def update_calendar_event(event_id: str, body: CalendarEventIn, ctx=Depends(auth), s=Depends(db)):
    row = s.get(D.CalendarEvent, event_id)
    if not row or row.status == "deleted":
        raise HTTPException(404, "Calendar event not found")
    if row.source_type != "manual":
        raise HTTPException(400, "Only custom calendar events can be edited here")
    dec, _ = gate(s, ctx, "calendar", "edit")
    require(dec)
    if not _calendar_event_editable(ctx, row):
        raise HTTPException(403, "You can edit only your office calendar events")
    prev = row.status
    row.title = body.title
    row.category = body.category
    row.audience = body.audience or "all"
    row.start_at = _parse_datetime_value(body.start_at)
    row.end_at = _parse_datetime_value(body.end_at, end=True) or row.start_at
    row.all_day = body.all_day
    row.location = body.location
    row.description = body.description
    row.color = body.color or row.color
    row.status = body.status or row.status
    row.updated_by = ctx["sub"]
    row.updated_at = datetime.utcnow()
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "calendar.edit",
                f"calendar:{row.id}", prev, row.status,
                f"Updated calendar event '{row.title}'")
    _fanout_notification(
        s, row.audience,
        f"Calendar revised: {row.title}",
        f"{row.category} event details were updated for {row.start_at.strftime('%d %b %Y %H:%M')}.",
        severity="action",
    )
    return {"event": _strip_event_meta(_event_payload(
        row.id, row.title, row.category, row.audience, row.start_at, row.end_at,
        all_day=row.all_day, location=row.location, description=row.description,
        source_type=row.source_type, source_ref=row.source_ref, color=row.color,
        status=row.status, editable=_calendar_event_editable(ctx, row)
    )), "decision": dec.as_dict()}


@router.delete("/calendar/{event_id}")
def delete_calendar_event(event_id: str, ctx=Depends(auth), s=Depends(db)):
    row = s.get(D.CalendarEvent, event_id)
    if not row or row.status == "deleted":
        raise HTTPException(404, "Calendar event not found")
    dec, _ = gate(s, ctx, "calendar", "delete")
    require(dec)
    if not _calendar_event_editable(ctx, row):
        raise HTTPException(403, "You can delete only your office calendar events")
    prev = row.status
    row.status = "deleted"
    row.updated_by = ctx["sub"]
    row.updated_at = datetime.utcnow()
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "calendar.delete",
                f"calendar:{row.id}", prev, row.status,
                f"Deleted calendar event '{row.title}'")
    return {"ok": True, "decision": dec.as_dict()}


class AcademicCalendarProposalIn(AcademicCalendarIn):
    rationale: str = ""
    due_at: str = ""


class AcademicProposalTransitionIn(BaseModel):
    expected_status_version: int = Field(ge=0)
    reason: str = ""


@router.get("/academic-calendar/proposals")
def academic_calendar_proposals(state: str = "", ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academic_calendar", "view", governance=True)[0])
    query = scoped_academic_query(s, D.AcademicProposal, ctx).filter(D.AcademicProposal.proposal_type == "calendar")
    if state:
        query = query.filter(D.AcademicProposal.state == state.upper())
    if ctx["office_n"] == 42:
        # Academic Office operates at faculty/institution scope and can create
        # a calendar proposal with no department reference.  Its own queue is
        # therefore ownership-scoped, not artificially filtered to a missing
        # department identifier.
        query = query.filter(D.AcademicProposal.submitted_by == ctx["sub"])
    elif ctx["office_n"] != 6:
        query = query.filter(D.AcademicProposal.scope_ref == (actor_department_id(s, ctx) or "__no_scope__"))
    rows = query.order_by(desc(D.AcademicProposal.updated_at)).all()
    return {"proposals": [_proposal_payload(s, row) for row in rows],
            "can_propose": ctx["office_n"] in CALENDAR_PROPOSERS,
            "can_decide": ctx["office_n"] == 6}


@router.get("/academic-calendar/proposals/{proposal_id}")
def academic_calendar_proposal_detail(proposal_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academic_calendar", "view", governance=True)[0])
    proposal = require_academic_object(s, ctx, s.get(D.AcademicProposal, proposal_id), "read", "Calendar proposal")
    if proposal.proposal_type != "calendar": raise HTTPException(404, "Calendar proposal not found")
    return {"proposal": _proposal_payload(s, proposal)}


@router.post("/academic-calendar/proposals")
def create_academic_calendar_proposal(body: AcademicCalendarProposalIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academic_calendar", "view", governance=True)[0])
    if ctx["office_n"] not in CALENDAR_PROPOSERS:
        raise HTTPException(403, "Only an authorized Academic Office or Academic Coordinator actor can propose calendar changes")
    if not body.title.strip() or not body.term.strip():
        raise HTTPException(422, "Title and term are required")
    start = date.fromisoformat(body.start_date)
    end = date.fromisoformat(body.end_date) if body.end_date else start
    if end < start:
        raise HTTPException(422, "End date cannot be before start date")
    payload = body.model_dump(exclude={"rationale", "due_at", "status"})
    payload["end_date"] = end.isoformat()
    payload["impact"] = _calendar_impact(s, payload)
    now = datetime.utcnow()
    proposal = D.AcademicProposal(id=uid(), tenant_id=TENANT, proposal_type="calendar",
                                  title=body.title.strip(), scope_level="department" if ctx["office_n"] != 6 else "faculty",
                                  scope_ref=actor_department_id(s, ctx) or "", state="DRAFT", version_no=1,
                                  submitted_by=ctx["sub"], submitted_office_n=ctx["office_n"],
                                  assigned_to_office_n=6,
                                  due_at=datetime.fromisoformat(body.due_at) if body.due_at else now + timedelta(days=5),
                                  created_at=now, updated_at=now)
    s.add(proposal); s.flush()
    s.add(D.AcademicProposalVersion(id=uid(), tenant_id=TENANT, proposal_id=proposal.id,
                                    version_no=1, payload_json=json.dumps(payload),
                                    rationale=body.rationale.strip(), created_by=ctx["sub"]))
    _proposal_event(s, proposal, ctx, "", "DRAFT", body.rationale)
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic.calendar.proposal.create",
                f"academic_proposal:{proposal.id}", "", "DRAFT", body.rationale)
    return {"proposal": _proposal_payload(s, proposal)}


@router.post("/academic-calendar/proposals/{proposal_id}/submit")
def submit_academic_calendar_proposal(proposal_id: str, body: AcademicProposalTransitionIn, ctx=Depends(auth), s=Depends(db)):
    proposal = require_tenant(s.get(D.AcademicProposal, proposal_id), ctx, "Calendar proposal")
    if proposal.proposal_type != "calendar": raise HTTPException(404, "Calendar proposal not found")
    if proposal.submitted_by != ctx["sub"] or proposal.state not in {"DRAFT", "RETURNED", "CLARIFICATION_REQUIRED"}: raise HTTPException(409, "Proposal cannot be submitted in its current state")
    if proposal.status_version != body.expected_status_version: raise HTTPException(409, "Proposal changed; reload before submitting")
    previous = proposal.state; proposal.state = "RESUBMITTED" if previous in {"RETURNED", "CLARIFICATION_REQUIRED"} else "SUBMITTED"; proposal.status_version += 1; proposal.updated_at = datetime.utcnow()
    _proposal_event(s, proposal, ctx, previous, proposal.state, body.reason)
    dean = s.query(User).filter(User.office_n == 6).first()
    if dean: _proposal_notice(s, dean.id, "Academic calendar decision required", proposal.title)
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic.calendar.proposal.submit", f"academic_proposal:{proposal.id}", previous, proposal.state, body.reason, commit=False); s.commit()
    return {"proposal": _proposal_payload(s, proposal)}


@router.post("/academic-calendar/proposals/{proposal_id}/decision/{decision}")
def decide_academic_calendar_proposal(proposal_id: str, decision: str, body: AcademicProposalTransitionIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academic_calendar", "approve_proposal" if decision.lower() == "approve" else "reject_proposal")[0])
    proposal = require_academic_object(s, ctx, s.query(D.AcademicProposal).filter(D.AcademicProposal.id == proposal_id).with_for_update().first(), "approve", "Calendar proposal")
    prevent_self_approval(proposal, ctx)
    if proposal.proposal_type != "calendar": raise HTTPException(404, "Calendar proposal not found")
    target = {"approve": "APPROVED", "reject": "REJECTED", "return": "RETURNED", "clarification": "CLARIFICATION_REQUIRED", "escalate": "ESCALATED"}.get(decision.lower())
    if not target or proposal.state not in {"SUBMITTED", "RESUBMITTED", "UNDER_REVIEW"}: raise HTTPException(409, "Invalid calendar decision")
    validate_transition(s, proposal, target, body.expected_status_version, ctx, body.reason)
    if proposal.status_version != body.expected_status_version: raise HTTPException(409, "Proposal changed; reload before deciding")
    claim_proposal_transition(s, proposal, body.expected_status_version, {"SUBMITTED", "RESUBMITTED", "UNDER_REVIEW"})
    if target in {"REJECTED", "RETURNED", "CLARIFICATION_REQUIRED", "ESCALATED"} and not body.reason.strip(): raise HTTPException(422, "A decision reason is required")
    if target == "APPROVED":
        data = json.loads(_proposal_version(s, proposal).payload_json)
        # Do not publish overlapping examination windows for the same scope.
        if "exam" in str(data.get("category", "")).lower():
            start = date.fromisoformat(data["start_date"]); end = date.fromisoformat(data["end_date"])
            conflicts = s.query(D.AcademicCalendarEntry).filter(
                D.AcademicCalendarEntry.tenant_id == ctx["tenant_id"],
                D.AcademicCalendarEntry.status != "deleted",
                D.AcademicCalendarEntry.category.ilike("%exam%"),
                D.AcademicCalendarEntry.start_date <= end,
                D.AcademicCalendarEntry.end_date >= start,
            ).all()
            campus = data.get("campus", "All Campuses")
            conflicts = [row for row in conflicts if campus == "All Campuses" or row.campus == "All Campuses" or row.campus == campus]
            if conflicts:
                raise HTTPException(409, f"Exam window overlaps existing event: {conflicts[0].title}")
    previous = proposal.state; proposal.state = target; proposal.status_version += 1; proposal.updated_at = datetime.utcnow()
    if target == "ESCALATED": proposal.escalated_to_office_n = 5
    if target == "APPROVED":
        entry = D.AcademicCalendarEntry(id=uid(), tenant_id=TENANT, term=data["term"], title=data["title"], category=data.get("category", "Teaching"), campus=data.get("campus", "All Campuses"), start_date=date.fromisoformat(data["start_date"]), end_date=date.fromisoformat(data["end_date"]), description=data.get("description", ""), status="published", owner_office_n=6, created_by=proposal.submitted_by, updated_by=ctx["sub"])
        s.add(entry); s.flush(); proposal.implementation_ref = entry.id
    _proposal_event(s, proposal, ctx, previous, target, body.reason)
    submitter = s.get(User, proposal.submitted_by)
    if submitter: _proposal_notice(s, submitter.id, f"Calendar proposal {target.lower().replace('_', ' ')}", proposal.title, "info" if target == "APPROVED" else "action")
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic.calendar.proposal.decision", f"academic_proposal:{proposal.id}", previous, target, body.reason, commit=False); s.commit()
    return {"proposal": _proposal_payload(s, proposal)}


@router.get("/academic-calendar")
def academic_calendar(term: str = "", academic_year: str = "", program_id: str = "", department_id: str = "", student_year: int | None = None, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academic_calendar", "view", governance=True)[0])
    term_rows = (s.query(D.AcademicCalendarEntry.term)
                 .filter(D.AcademicCalendarEntry.status != "deleted")
                 .distinct().order_by(D.AcademicCalendarEntry.term.desc()).all())
    term_options = [row[0] for row in term_rows]
    selected_term = term if term in term_options else (term_options[0] if term_options else "")

    query = s.query(D.AcademicCalendarEntry).filter(D.AcademicCalendarEntry.tenant_id == ctx["tenant_id"], D.AcademicCalendarEntry.status != "deleted")
    if selected_term:
        query = query.filter(D.AcademicCalendarEntry.term == selected_term)
    if academic_year:
        query = query.filter(D.AcademicCalendarEntry.academic_year == academic_year)
    if program_id:
        query = query.filter(D.AcademicCalendarEntry.program_id == program_id)
    if department_id:
        query = query.filter(D.AcademicCalendarEntry.department_id == department_id)
    if student_year is not None:
        query = query.filter(D.AcademicCalendarEntry.student_year == student_year)
    rows = query.order_by(D.AcademicCalendarEntry.start_date, D.AcademicCalendarEntry.title).all()

    summary = {
        "milestones": len(rows),
        "exam_windows": sum(1 for row in rows if "exam" in row.category.lower()),
        "breaks": sum(1 for row in rows if row.category.lower() == "break"),
        "governed_by": "Dean Academics",
    }

    months = {}
    for row in rows:
        label = row.start_date.strftime("%b %Y")
        months[label] = months.get(label, 0) + 1

    term_window = {
        "start": rows[0].start_date.isoformat() if rows else "",
        "end": (rows[-1].end_date or rows[-1].start_date).isoformat() if rows else "",
    }

    academic_year_options = sorted({row.academic_year for row in query.all() if row.academic_year})
    return {
        "selected_term": selected_term,
        "term_options": term_options,
        "academic_year_options": academic_year_options,
        "term_window": term_window,
        "permissions": {
            "create": can(s, ctx, "academic_calendar", "create"),
            "edit": can(s, ctx, "academic_calendar", "edit"),
            "delete": can(s, ctx, "academic_calendar", "delete"),
        },
        "editors": [
            "Chairman / Chairperson",
            "Vice Chairman",
            "Principal",
            "Vice Principal",
        ],
        "summary": summary,
        "months": [{"label": label, "count": count} for label, count in months.items()],
        "entries": [{
            "id": row.id,
            "academic_year": row.academic_year, "program_id": row.program_id, "department_id": row.department_id, "student_year": row.student_year,
            "term": row.term,
            "title": row.title,
            "category": row.category,
            "campus": row.campus,
            "start_date": row.start_date.isoformat(),
            "start_time": row.start_time, "end_time": row.end_time,
            "end_date": (row.end_date or row.start_date).isoformat(),
            "description": row.description,
            "status": row.status,
            "owner_office_n": row.owner_office_n,
            "editable": _academic_entry_editable(ctx, row),
        } for row in rows],
        "proposals": [_proposal_payload(s, row) for row in s.query(D.AcademicProposal).filter(D.AcademicProposal.tenant_id == ctx["tenant_id"], D.AcademicProposal.proposal_type == "calendar").order_by(desc(D.AcademicProposal.updated_at)).limit(25).all()],
        "workflow_permissions": {"propose": ctx["office_n"] in CALENDAR_PROPOSERS, "decide": ctx["office_n"] == 6},
    }


@router.post("/academic-calendar")
def create_academic_calendar_entry(body: AcademicCalendarIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academic_calendar", "create")
    require(dec)
    if ctx["office_n"] not in CALENDAR_ACADEMIC_EDITORS:
        raise HTTPException(403, "This office cannot manage the academic calendar")
    if not body.title.strip() or not body.term.strip() or not body.academic_year.strip():
        raise HTTPException(422, "Academic year, term, and title are required")
    start = date.fromisoformat(body.start_date)
    end = date.fromisoformat(body.end_date) if body.end_date else start
    if end < start:
        raise HTTPException(422, "End date cannot be earlier than start date")
    duplicate = s.query(D.AcademicCalendarEntry).filter(
        D.AcademicCalendarEntry.tenant_id == ctx["tenant_id"],
        D.AcademicCalendarEntry.term == body.term,
        D.AcademicCalendarEntry.title == body.title.strip(),
        D.AcademicCalendarEntry.start_date == start,
        D.AcademicCalendarEntry.status != "deleted",
    ).first()
    if duplicate:
        raise HTTPException(409, "A matching academic calendar entry already exists")
    now = datetime.utcnow()
    row = D.AcademicCalendarEntry(
        id=uid(), tenant_id=TENANT, term=body.term, academic_year=body.academic_year, program_id=body.program_id, department_id=body.department_id, student_year=body.student_year, title=body.title,
        category=body.category, campus=body.campus,
        start_date=start,
        end_date=end, start_time=body.start_time, end_time=body.end_time,
        description=body.description, status=("draft" if ctx["office_n"] == 17 else (body.status or "published")),
        owner_office_n=ctx["office_n"], created_by=ctx["sub"], updated_by=ctx["sub"],
        created_at=now, updated_at=now
    )
    s.add(row)
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic_calendar.create",
                f"academic_calendar:{row.id}", "", row.status,
                f"Created academic milestone '{row.title}'")
    _fanout_notification(
        s, "all",
        f"Academic calendar updated: {row.title}",
        f"{row.term} · {row.start_date.strftime('%d %b %Y')} to {(row.end_date or row.start_date).strftime('%d %b %Y')}.",
        severity="action",
    )
    return {"entry": {
        "id": row.id,
        "term": row.term, "academic_year": row.academic_year, "program_id": row.program_id, "department_id": row.department_id, "student_year": row.student_year,
        "title": row.title,
        "category": row.category,
        "campus": row.campus,
        "start_date": row.start_date.isoformat(), "start_time": row.start_time, "end_time": row.end_time,
        "end_date": (row.end_date or row.start_date).isoformat(),
        "description": row.description,
        "status": row.status,
        "owner_office_n": row.owner_office_n,
        "editable": _academic_entry_editable(ctx, row),
    }, "decision": dec.as_dict()}


@router.put("/academic-calendar/{entry_id}")
def update_academic_calendar_entry(entry_id: str, body: AcademicCalendarIn, ctx=Depends(auth), s=Depends(db)):
    row = s.get(D.AcademicCalendarEntry, entry_id)
    if not row or row.status == "deleted":
        raise HTTPException(404, "Academic calendar entry not found")
    dec, _ = gate(s, ctx, "academic_calendar", "edit")
    require(dec)
    if ctx["office_n"] not in CALENDAR_ACADEMIC_EDITORS or (ctx["office_n"] == 17 and row.owner_office_n != 17 and row.created_by != ctx["sub"]):
        raise HTTPException(403, "This office cannot manage the academic calendar")
    if row.status not in {"draft", "correction_required"}:
        raise HTTPException(409, "Only draft or correction-required entries can be edited")
    start = date.fromisoformat(body.start_date)
    end = date.fromisoformat(body.end_date) if body.end_date else start
    if end < start:
        raise HTTPException(422, "End date cannot be earlier than start date")
    prev = row.status
    row.term = body.term
    row.academic_year, row.program_id, row.department_id, row.student_year = body.academic_year, body.program_id, body.department_id, body.student_year
    row.title = body.title
    row.category = body.category
    row.campus = body.campus
    row.start_date = start
    row.end_date = end
    row.start_time, row.end_time = body.start_time, body.end_time
    row.description = body.description
    row.status = body.status or row.status
    row.updated_by = ctx["sub"]
    row.updated_at = datetime.utcnow()
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic_calendar.edit",
                f"academic_calendar:{row.id}", prev, row.status,
                f"Updated academic milestone '{row.title}'")
    _fanout_notification(
        s, "all",
        f"Academic calendar revised: {row.title}",
        f"{row.term} academic timeline was updated for {row.start_date.strftime('%d %b %Y')}.",
        severity="action",
    )
    return {"entry": {
        "id": row.id,
        "term": row.term,
        "title": row.title,
        "category": row.category,
        "campus": row.campus,
        "start_date": row.start_date.isoformat(),
        "end_date": (row.end_date or row.start_date).isoformat(),
        "description": row.description,
        "status": row.status,
        "owner_office_n": row.owner_office_n,
        "editable": _academic_entry_editable(ctx, row),
    }, "decision": dec.as_dict()}


@router.post("/academic-calendar/{entry_id}/submit")
def submit_academic_calendar_entry(entry_id: str, ctx=Depends(auth), s=Depends(db)):
    row = s.get(D.AcademicCalendarEntry, entry_id)
    if not row or row.status == "deleted": raise HTTPException(404, "Academic calendar entry not found")
    if ctx["office_n"] != 17 or row.created_by != ctx["sub"]: raise HTTPException(403, "Only the creating Academic Coordinator may submit this draft")
    dec, _ = gate(s, ctx, "academic_calendar", "edit"); require(dec)
    if row.status not in {"draft", "correction_required"}: raise HTTPException(409, "Only draft or correction-required calendar entries can be submitted")
    previous = row.status
    row.status, row.updated_by, row.updated_at = "pending_review", ctx["sub"], datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic_calendar.submit", f"academic_calendar:{row.id}", previous, row.status, "Submitted for academic calendar review")
    return {"status": row.status, "decision": dec.as_dict()}


class AcademicCalendarDecisionIn(BaseModel):
    action: str
    reason: str = ""


@router.post("/academic-calendar/{entry_id}/decision")
def decide_academic_calendar_entry(entry_id: str, body: AcademicCalendarDecisionIn, ctx=Depends(auth), s=Depends(db)):
    row = s.get(D.AcademicCalendarEntry, entry_id)
    if not row or row.status == "deleted":
        raise HTTPException(404, "Academic calendar entry not found")
    if ctx["office_n"] == 17 or ctx["office_n"] not in {1, 2, 4, 5}:
        raise HTTPException(403, "This office cannot approve academic calendar changes")
    dec, _ = gate(s, ctx, "academic_calendar", "edit"); require(dec)
    if row.status != "pending_review":
        raise HTTPException(409, "Only pending calendar changes can be decided")
    action = body.action.strip().lower()
    if action not in {"approve", "reject", "return", "publish"}:
        raise HTTPException(400, "Decision must be approve, reject, return, or publish")
    if action in {"reject", "return"} and not body.reason.strip():
        raise HTTPException(400, "A reason is required when rejecting or requesting correction")
    if action == "publish" and row.status != "approved":
        raise HTTPException(409, "Only approved calendar entries can be published")
    previous = row.status
    row.status = {"approve": "approved", "publish": "published", "return": "correction_required", "reject": "rejected"}[action]
    row.updated_by, row.updated_at = ctx["sub"], datetime.utcnow()
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic_calendar.decision",
                f"academic_calendar:{row.id}", previous, row.status,
                f"Academic calendar {action}: {body.reason.strip()}".strip())
    return {"status": row.status, "decision": dec.as_dict(), "reason": body.reason.strip()}


@router.delete("/academic-calendar/{entry_id}")
def delete_academic_calendar_entry(entry_id: str, ctx=Depends(auth), s=Depends(db)):
    row = s.get(D.AcademicCalendarEntry, entry_id)
    if not row or row.status == "deleted":
        raise HTTPException(404, "Academic calendar entry not found")
    dec, _ = gate(s, ctx, "academic_calendar", "delete")
    require(dec)
    if ctx["office_n"] not in CALENDAR_ACADEMIC_EDITORS or (ctx["office_n"] == 17 and row.owner_office_n != 17 and row.created_by != ctx["sub"]):
        raise HTTPException(403, "This office cannot manage the academic calendar")
    if row.status not in {"draft", "correction_required"}:
        raise HTTPException(409, "Only draft or correction-required entries can be deleted")
    prev = row.status
    row.status = "deleted"
    row.updated_by = ctx["sub"]
    row.updated_at = datetime.utcnow()
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic_calendar.delete",
                f"academic_calendar:{row.id}", prev, row.status,
                f"Deleted academic milestone '{row.title}'")
    return {"ok": True, "decision": dec.as_dict()}


# --------------------------------------------------------------------------- #
#  STUDENTS
# --------------------------------------------------------------------------- #
class StudentIn(BaseModel):
    name: str
    roll_no: str = ""
    dept_code: str = "CSE"
    batch: str = "2025"
    semester: int = 1
    program_level: str = "UG"


def _student_scope(query, ctx):
    """Apply the authenticated campus scope; never accept campus from the browser."""
    query = query.filter(D.Student.tenant_id == ctx.get("tenant_id", TENANT))
    scope = (ctx.get("scope_ref") or "").strip()
    if ctx.get("scope_level") == "campus" and scope and not scope.startswith("scope_"):
        return query.filter(D.Student.campus == scope)
    return query


def _academic_year_label(batch):
    """Represent a student's admission batch as the academic-year filter label."""
    try:
        start = int(str(batch)[:4])
        return f"{start}-{str(start + 1)[-2:]}"
    except (TypeError, ValueError):
        return str(batch or "")


def _attendance_totals(s, student_ids):
    rows = (s.query(D.AttendanceRecord.student_id, D.AttendanceRecord.present)
            .filter(D.AttendanceRecord.student_id.in_(student_ids)).all()) if student_ids else []
    totals = {}
    for student_id, present in rows:
        bucket = totals.setdefault(student_id, [0, 0])
        bucket[0] += 1
        bucket[1] += int(bool(present))
    return totals


def _backlog_summary(s, student_ids):
    rows = (s.query(D.StudentSubjectResult).filter(D.StudentSubjectResult.student_id.in_(student_ids))
            .order_by(D.StudentSubjectResult.student_id, D.StudentSubjectResult.subject_code, D.StudentSubjectResult.attempt).all()) if student_ids else []
    latest = {}
    history = {}
    for row in rows:
        latest[(row.student_id, row.subject_code)] = row
        history.setdefault(row.student_id, []).append(row)
    output = {}
    for student_id in student_ids:
        student_latest = [row for (sid, _), row in latest.items() if sid == student_id]
        outstanding = [row for row in student_latest if row.outcome == "failed"]
        cleared = [row for row in student_latest if row.outcome == "passed" and any(h.subject_code == row.subject_code and h.outcome == "failed" and h.attempt < row.attempt for h in history.get(student_id, []))]
        output[student_id] = {"current": len(outstanding), "cleared": len(cleared), "subjects": [row.subject_title for row in outstanding], "history": history.get(student_id, [])}
    return output


@router.get("/students")
def list_students(q: str = "", dept: str = "", program: str = "", academic_year: str = "", study_year: int = Query(0, ge=0), semester: int = Query(0, ge=0), section: str = "", risk: str = "", page: int = Query(1, ge=1), page_size: int = Query(25, ge=10, le=100), ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "students", "view")[0])
    base_query = _student_scope(s.query(D.Student), ctx)
    scoped_students = base_query.all()
    query = base_query
    if q:
        like = f"%{q}%"
        query = query.filter((D.Student.name.ilike(like)) | (D.Student.roll_no.ilike(like)) | (D.Student.email.ilike(like)))
    if dept:
        d = s.query(D.Department).filter(D.Department.code == dept).first()
        if d:
            query = query.filter(D.Student.dept_id == d.id)
    if program:
        query = query.join(D.Program, D.Student.program_id == D.Program.id).filter((D.Program.code == program) | (D.Program.name == program))
    if academic_year:
        matching_batches = [student.batch for student in scoped_students if _academic_year_label(student.batch) == academic_year]
        query = query.filter(D.Student.batch.in_(matching_batches)) if matching_batches else query.filter(False)
    if semester:
        query = query.filter(D.Student.semester == semester)
    if study_year:
        query = query.filter(D.Student.semester.between((study_year - 1) * 2 + 1, study_year * 2))
    if section:
        query = query.filter(D.Student.section == section)
    if risk == "academic":
        query = query.filter(D.Student.cgpa < 6.5)
    if risk in {"backlogs", "no-backlogs", "at-risk"}:
        scoped_ids = [row[0] for row in query.with_entities(D.Student.id).all()]
        summaries = _backlog_summary(s, scoped_ids)
        if risk == "backlogs":
            query = query.filter(D.Student.id.in_([sid for sid, item in summaries.items() if item["current"] > 0]))
        elif risk == "no-backlogs":
            query = query.filter(D.Student.id.in_([sid for sid, item in summaries.items() if item["current"] == 0]))
        else:
            attendance = _attendance_totals(s, scoped_ids)
            at_risk_ids = [sid for sid, item in summaries.items()
                           if item["current"] > 0
                           or (s.query(D.Student.cgpa).filter(D.Student.id == sid).scalar() or 0) < 6.5
                           or (sid in attendance and 100 * attendance[sid][1] / attendance[sid][0] < 75)]
            query = query.filter(D.Student.id.in_(at_risk_ids))
    total = query.count()
    rows = (query.order_by(D.Student.roll_no)
            .offset((page - 1) * page_size)
            .limit(page_size).all())
    dept_map = {d.id: d for d in s.query(D.Department).all()}
    program_map = {p.id: p for p in s.query(D.Program).all()}
    student_ids = [row.id for row in rows]
    backlogs = _backlog_summary(s, student_ids)
    attendance_by_student = _attendance_totals(s, student_ids)
    all_students = query.all()
    all_backlogs = _backlog_summary(s, [student.id for student in all_students])
    attendance_totals = _attendance_totals(s, [student.id for student in all_students])
    risk_summary = {"at_risk": 0, "academic_risk": 0, "attendance_risk": 0, "attendance_available": len(attendance_totals), "average_attendance": None, "average_cgpa": None,
                    "backlogs": 0, "no_backlogs": 0}
    attendance_values = []
    cgpas = []
    for student in all_students:
        academic = (student.cgpa or 0) < 6.5
        current_backlogs = all_backlogs[student.id]["current"]
        if academic: risk_summary["academic_risk"] += 1
        if current_backlogs: risk_summary["backlogs"] += 1
        else: risk_summary["no_backlogs"] += 1
        if student.id in attendance_totals:
            pct = 100 * attendance_totals[student.id][1] / attendance_totals[student.id][0]
            attendance_values.append(pct)
            if pct < 75: risk_summary["attendance_risk"] += 1
        if student.cgpa is not None: cgpas.append(student.cgpa)
        if academic or current_backlogs or (student.id in attendance_totals and 100 * attendance_totals[student.id][1] / attendance_totals[student.id][0] < 75): risk_summary["at_risk"] += 1
    if attendance_values: risk_summary["average_attendance"] = round(sum(attendance_values) / len(attendance_values), 1)
    if cgpas: risk_summary["average_cgpa"] = round(sum(cgpas) / len(cgpas), 2)
    return {"students": [{
        "id": r.id, "roll_no": r.roll_no, "name": r.name, "email": r.email, "dept": dept_map.get(r.dept_id).code if r.dept_id in dept_map else "", "department_name": dept_map.get(r.dept_id).name if r.dept_id in dept_map else "",
        "program": program_map.get(r.program_id).name if r.program_id in program_map else "", "program_code": program_map.get(r.program_id).code if r.program_id in program_map else "",
        "batch": r.batch, "semester": r.semester, "section": r.section, "cgpa": r.cgpa,
        "status": r.status, "hosteller": r.hosteller, "scholarship": r.scholarship,
        "attendance_pct": round(100 * attendance_by_student[r.id][1] / attendance_by_student[r.id][0], 1) if r.id in attendance_by_student else None,
        "current_backlogs": backlogs[r.id]["current"], "backlog_status": "Outstanding" if backlogs[r.id]["current"] else ("Cleared" if backlogs[r.id]["cleared"] else "No history"),
    } for r in rows], "total": total, "page": page, "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "filter_options": {
            "academic_years": sorted({_academic_year_label(row.batch) for row in scoped_students if row.batch}, reverse=True),
            "programs": sorted({(program_map[row.program_id].code, program_map[row.program_id].name) for row in scoped_students if row.program_id in program_map}, key=lambda item: item[1]),
            "departments": sorted({(dept_map[row.dept_id].code, dept_map[row.dept_id].name) for row in scoped_students if row.dept_id in dept_map}, key=lambda item: item[1]),
            "study_years": sorted({(row.semester + 1) // 2 for row in scoped_students if row.semester}),
            "semesters": sorted({row.semester for row in scoped_students if row.semester}),
            "sections": sorted({row.section for row in scoped_students if row.section}),
        },
        "departments": [
            {"code": code, "name": name, "count": sum(1 for student in scoped_students if student.dept_id in dept_map and dept_map[student.dept_id].code == code)}
            for code, name in sorted({(dept_map[row.dept_id].code, dept_map[row.dept_id].name) for row in scoped_students if row.dept_id in dept_map}, key=lambda item: item[1])
        ],
        "summary": {"all_students": total, **risk_summary},
        "can_add": can(s, ctx, "students", "add"),
        "can_edit": can(s, ctx, "students", "edit")}


@router.get("/students/{student_id}/profile")
def student_profile(student_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "students", "view")[0])
    student = _student_scope(s.query(D.Student), ctx).filter(D.Student.id == student_id).first()
    if not student:
        raise HTTPException(404, "Student was not found in your authorized campus")
    department = s.query(D.Department).get(student.dept_id)
    program = s.query(D.Program).get(student.program_id)
    attendance = s.query(D.AttendanceRecord).filter(D.AttendanceRecord.student_id == student.id).all()
    attendance_pct = round(100 * sum(1 for row in attendance if row.present) / len(attendance), 1) if attendance else None
    enrollments = s.query(D.Enrollment).filter(D.Enrollment.student_id == student.id).all()
    sections = {row.id: row for row in s.query(D.Section).filter(D.Section.id.in_([e.section_id for e in enrollments])).all()} if enrollments else {}
    marks = s.query(D.Mark).filter(D.Mark.student_id == student.id).all()
    backlog = _backlog_summary(s, [student.id])[student.id]
    return {"student": {"id": student.id, "name": student.name, "roll_no": student.roll_no, "email": student.email,
            "campus": student.campus, "department": department.name if department else "", "department_code": department.code if department else "",
            "program": program.name if program else "", "program_code": program.code if program else "", "semester": student.semester,
            "study_year": (student.semester + 1) // 2, "section": student.section, "status": student.status, "cgpa": student.cgpa,
            "attendance_pct": attendance_pct, "current_backlogs": backlog["current"], "cleared_backlogs": backlog["cleared"]},
            "attendance": [{"date": row.on_date.isoformat(), "present": row.present} for row in attendance],
            "enrollments": [{"section": sections[e.section_id].section_code if e.section_id in sections else "", "term": sections[e.section_id].term if e.section_id in sections else "", "status": e.status, "grade": e.grade} for e in enrollments],
            "marks": [{"assessment_id": row.assessment_id, "score": row.score, "entered_at": row.entered_at.isoformat() if row.entered_at else None} for row in marks],
            "backlog_history": [{"academic_year": row.academic_year, "semester": row.semester, "subject_code": row.subject_code, "subject_title": row.subject_title, "attempt": row.attempt, "outcome": row.outcome, "source": row.source} for row in backlog["history"]],
            "limitations": {"backlogs": "Development sample results are included only where labelled development_sample.", "welfare": "Unavailable: student-linked welfare records are not modelled."}}


@router.post("/students")
def add_student(body: StudentIn, ctx=Depends(auth), s=Depends(db)):
    dec, verb = gate(s, ctx, "students", "add")
    require(dec)
    d = s.query(D.Department).filter(D.Department.code == body.dept_code).first()
    if not d:
        raise HTTPException(400, "Unknown department")
    prog = s.query(D.Program).filter(D.Program.dept_id == d.id,
                                     D.Program.level == body.program_level).first()
    sid = uid()
    roll = body.roll_no or f"{body.batch[2:]}{body.dept_code}{s.query(D.Student).count()+1:03d}"
    s.add(D.Student(id=sid, tenant_id=TENANT, roll_no=roll, name=body.name,
                    email=f"{roll.lower()}@icms.edu", program_id=prog.id if prog else None,
                    dept_id=d.id, batch=body.batch, semester=body.semester,
                    section="A", status="active", cgpa=0.0))
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "student.create",
                f"student:{sid}", "", "active", f"Admitted {body.name} ({roll})")
    return {"id": sid, "roll_no": roll, "decision": dec.as_dict()}


# --------------------------------------------------------------------------- #
#  FACULTY ALLOCATION & TIMETABLE READINESS
# --------------------------------------------------------------------------- #
class FacultyAllocationProposalIn(BaseModel):
    section_id: str
    faculty_person_id: str
    rationale: str = ""


@router.get("/academics/allocation/proposals")
def allocation_proposals(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view", governance=True)[0])
    q = scoped_academic_query(s, D.AcademicProposal, ctx).filter(D.AcademicProposal.proposal_type == "allocation")
    if ctx["office_n"] != 6: q = q.filter(D.AcademicProposal.scope_ref == (actor_department_id(s, ctx) or "__no_scope__"))
    return {"proposals": [_proposal_payload(s, row) for row in q.order_by(desc(D.AcademicProposal.updated_at)).all()], "can_propose": ctx["office_n"] in {10, 17}, "can_decide": ctx["office_n"] == 6}


@router.get("/academics/allocation/proposals/{proposal_id}")
def allocation_proposal_detail(proposal_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view", governance=True)[0])
    proposal = require_academic_object(s, ctx, s.get(D.AcademicProposal, proposal_id), "read", "Allocation proposal")
    if proposal.proposal_type != "allocation": raise HTTPException(404, "Allocation proposal not found")
    return {"proposal": _proposal_payload(s, proposal)}


@router.post("/academics/allocation/proposals")
def create_allocation_proposal(body: FacultyAllocationProposalIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view", governance=True)[0])
    if ctx["office_n"] not in {10, 17}: raise HTTPException(403, "Only HOD or Academic Coordinator can propose allocations")
    section = require_academic_object(s, ctx, s.get(D.Section, body.section_id), "create", "Section")
    faculty = require_academic_object(s, ctx, s.get(D.StaffMember, body.faculty_person_id), "create", "Faculty member")
    if not section or not faculty: raise HTTPException(404, "Section or faculty member not found")
    payload = {"section_id": section.id, "faculty_person_id": faculty.id, "term": section.term, "course_id": section.course_id}
    course = s.get(D.Course, section.course_id)
    now = datetime.utcnow(); proposal = D.AcademicProposal(id=uid(), tenant_id=TENANT, proposal_type="allocation", title=f"Faculty allocation for {section.section_code}", scope_level="department", scope_ref=section.dept_id, school_id=section.school_id, dept_id=section.dept_id, program_id=getattr(course, "program_id", None), section_id=section.id, state="DRAFT", version_no=1, submitted_by=ctx["sub"], submitted_office_n=ctx["office_n"], assigned_to_office_n=6, due_at=now + timedelta(days=5), created_at=now, updated_at=now)
    s.add(proposal); s.flush(); s.add(D.AcademicProposalVersion(id=uid(), tenant_id=TENANT, proposal_id=proposal.id, version_no=1, payload_json=json.dumps(payload), rationale=body.rationale.strip(), created_by=ctx["sub"])); _proposal_event(s, proposal, ctx, "", "DRAFT", body.rationale); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic.allocation.proposal.create", f"academic_proposal:{proposal.id}", "", "DRAFT", body.rationale, commit=False); s.commit()
    return {"proposal": _proposal_payload(s, proposal)}


@router.post("/academics/allocation/proposals/{proposal_id}/submit")
def submit_allocation_proposal(proposal_id: str, body: AcademicProposalTransitionIn, ctx=Depends(auth), s=Depends(db)):
    proposal = require_academic_object(s, ctx, s.get(D.AcademicProposal, proposal_id), "submit", "Allocation proposal")
    if not proposal or proposal.proposal_type != "allocation": raise HTTPException(404, "Allocation proposal not found")
    if proposal.submitted_by != ctx["sub"] or proposal.state != "DRAFT" or proposal.status_version != body.expected_status_version: raise HTTPException(409, "Proposal cannot be submitted")
    proposal.state="SUBMITTED"; proposal.status_version += 1; proposal.updated_at=datetime.utcnow(); _proposal_event(s, proposal, ctx, "DRAFT", "SUBMITTED", body.reason); dean=s.query(User).filter(User.office_n==6).first()
    if dean: _proposal_notice(s, dean.id, "Faculty allocation decision required", proposal.title)
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic.allocation.proposal.submit", f"academic_proposal:{proposal.id}", "DRAFT", "SUBMITTED", body.reason, commit=False); s.commit(); return {"proposal": _proposal_payload(s, proposal)}


@router.post("/academics/allocation/proposals/{proposal_id}/decision/{decision}")
def decide_allocation_proposal(proposal_id: str, decision: str, body: AcademicProposalTransitionIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "approve_proposal" if decision.lower() == "approve" else "reject_proposal")[0])
    proposal=require_academic_object(s, ctx, s.query(D.AcademicProposal).filter(D.AcademicProposal.id == proposal_id).with_for_update().first(), "approve", "Allocation proposal")
    if proposal.submitted_by == ctx["sub"]:
        raise HTTPException(403, "Proposal submitter cannot approve or reject their own proposal")
    if not proposal or proposal.proposal_type != "allocation" or proposal.state != "SUBMITTED": raise HTTPException(409, "Invalid allocation proposal")
    if proposal.status_version != body.expected_status_version: raise HTTPException(409, "Proposal changed; reload before deciding")
    target={"approve":"APPROVED","reject":"REJECTED","return":"RETURNED"}.get(decision.lower())
    if not target: raise HTTPException(422, "Unsupported allocation decision")
    validate_transition(s, proposal, target, body.expected_status_version, ctx, body.reason)
    claim_proposal_transition(s, proposal, body.expected_status_version, {"SUBMITTED"})
    previous=proposal.state; proposal.state=target; proposal.status_version += 1; proposal.updated_at=datetime.utcnow()
    if target=="APPROVED":
        payload=json.loads(_proposal_version(s, proposal).payload_json); section=s.get(D.Section,payload["section_id"]); faculty=s.get(D.StaffMember,payload["faculty_person_id"])
        if not section or not faculty: raise HTTPException(409, "Allocation target no longer exists")
        section.faculty_person_id=faculty.id; s.add(D.FacultyAllocation(id=uid(),tenant_id=TENANT,section_id=section.id,faculty_person_id=faculty.id,term=section.term,workload_units=1,status="APPROVED",proposal_id=proposal.id,created_by=proposal.submitted_by,approved_by=ctx["sub"],created_at=datetime.utcnow(),updated_at=datetime.utcnow())); proposal.implementation_ref=section.id
    _proposal_event(s, proposal, ctx, previous, target, body.reason); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic.allocation.proposal.decision", f"academic_proposal:{proposal.id}", previous, target, body.reason, commit=False); s.commit(); return {"proposal": _proposal_payload(s, proposal)}


@router.get("/academics/timetable/readiness")
def timetable_readiness(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view", governance=True)[0]); resolve_decision, _ = gate(s, ctx, "academics", "resolve_exception"); sections=scoped_academic_query(s, D.Section, ctx).all(); entries=s.query(D.TimetableEntry).filter(D.TimetableEntry.tenant_id == ctx["tenant_id"], D.TimetableEntry.section_id.in_([section.id for section in sections]), D.TimetableEntry.status=="active").all(); staff={x.id:x for x in s.query(D.StaffMember).filter(D.StaffMember.tenant_id == ctx["tenant_id"]).all()}; out=[]
    for section in sections:
        slots=[x for x in entries if x.section_id==section.id]
        if not section.faculty_person_id: out.append({"kind":"UNASSIGNED_FACULTY","severity":"critical","section_id":section.id,"message":f"Section {section.section_code} has no faculty assignment"})
        for i,a in enumerate(slots):
            for b in slots[i+1:]:
                if a.day_of_week==b.day_of_week and a.start_time < b.end_time and b.start_time < a.end_time: out.append({"kind":"SECTION_CLASH","severity":"critical","section_id":section.id,"message":"Overlapping timetable slots"})
    for i,a in enumerate(entries):
        sa=s.get(D.Section,a.section_id)
        for b in entries[i+1:]:
            sb=s.get(D.Section,b.section_id)
            if sa and sb and a.day_of_week==b.day_of_week and a.start_time < b.end_time and b.start_time < a.end_time and a.room and a.room==b.room: out.append({"kind":"ROOM_CLASH","severity":"critical","section_id":sa.id,"message":f"Room {a.room} is double-booked"})
    unique_out = []
    seen_keys = set()
    for item in out:
        exception_key = f"ttx_{item['kind'].lower()}_{item.get('section_id') or 'global'}"
        if exception_key not in seen_keys:
            seen_keys.add(exception_key)
            unique_out.append(item)
    out = unique_out
    seen_exception_keys = set()
    for item in out:
        key=f"ttx_{item['kind'].lower()}_{item.get('section_id') or 'global'}"
        if key in seen_exception_keys:
            continue
        seen_exception_keys.add(key)
        existing=s.get(D.TimetableException,key)
        if existing is None:
            s.add(D.TimetableException(id=key,tenant_id=TENANT,section_id=item.get('section_id'),kind=item['kind'],severity=item['severity'],message=item['message']))
        elif existing.status != "RESOLVED":
            existing.message=item['message']; existing.severity=item['severity']; existing.detected_at=datetime.utcnow(); existing.status="OPEN"
    s.commit()
    persisted=[]
    for item in out:
        key=f"ttx_{item['kind'].lower()}_{item.get('section_id') or 'global'}"
        if any(x["id"] == key for x in persisted):
            continue
        row=s.get(D.TimetableException,key); persisted.append({**item,"id":row.id,"status":row.status})
    return {"exceptions": persisted, "summary":{"open":len(persisted),"critical":sum(1 for x in persisted if x["severity"]=="critical")}, "can_decide":resolve_decision.outcome in ("ALLOW", "ESCALATE"), "decision":resolve_decision.as_dict()}


@router.get("/academics/quality/risks")
def academic_quality_risks(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view", governance=True)[0]); departments=scoped_academic_query(s, D.Department, ctx).all(); result=[]
    for dept in departments:
        students=s.query(D.Student).filter(D.Student.tenant_id == ctx["tenant_id"], D.Student.dept_id==dept.id).all(); sections=s.query(D.Section).filter(D.Section.tenant_id == ctx["tenant_id"], D.Section.dept_id==dept.id).all()
        avg=round(sum(float(x.cgpa or 0) for x in students)/len(students),2) if students else None
        unassigned=sum(1 for x in sections if not x.faculty_person_id)
        if (avg is not None and avg < 6.5) or unassigned:
            result.append({"scope_level":"department","scope_ref":dept.id,"department":dept.name,"metric_key":"academic_readiness","metric_value":avg,"threshold":6.5,"deviation":f"Average CGPA {avg if avg is not None else 'N/A'}; {unassigned} unassigned sections"})
    return {"risks":result,"generated_at":datetime.utcnow().isoformat()}


class QualityReviewIn(BaseModel):
    title: str
    scope_level: str = "department"
    scope_ref: str = ""
    metric_key: str
    metric_value: float | None = None
    threshold: float | None = None
    deviation: str = ""
    root_cause: str = ""
    owner_id: str = ""
    due_at: str = ""
    effectiveness_measure: str = ""


class CorrectiveActionIn(BaseModel):
    title: str
    owner_id: str
    deadline: str
    priority: str = "medium"
    escalation_target: str = ""


@router.get("/academics/quality/reviews")
def quality_reviews(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view", governance=True)[0]); rows=scoped_academic_query(s, D.AcademicQualityReview, ctx).order_by(desc(D.AcademicQualityReview.updated_at)).all()
    # ACTION_ASSIGNED was emitted by an earlier workflow revision.  Expose it
    # as the equivalent current state so old records do not become unmanageable.
    legacy_states = {"ACTION_ASSIGNED": "ACTION_PLAN_APPROVED"}
    return {"states":["OPEN","INVESTIGATION","ROOT_CAUSE_CONFIRMED","ACTION_PLAN_APPROVED","ACTIONS_IN_PROGRESS","EFFECTIVENESS_REVIEW","CLOSED"],"reviews":[{"id":x.id,"title":x.title,"state":legacy_states.get(x.state, x.state),"metric_key":x.metric_key,"deviation":x.deviation,"root_cause":x.root_cause,"effectiveness_measure":x.effectiveness_measure,"effectiveness_result":x.effectiveness_result,"closed_at":x.closed_at.isoformat() if x.closed_at else None,"due_at":x.due_at.isoformat() if x.due_at else None,"status_version":x.status_version,"owner_id":x.owner_id,"scope_ref":x.scope_ref} for x in rows],"can_manage":ctx["office_n"]==6}


@router.post("/academics/quality/reviews")
def create_quality_review(body: QualityReviewIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view", governance=True)[0])
    if ctx["office_n"] not in {6,10,17}: raise HTTPException(403,"Only Dean, HOD, or Academic Coordinator can create quality reviews")
    if body.scope_ref and body.scope_level == "department":
        require_academic_object(s, ctx, s.get(D.Department, body.scope_ref), "create", "Department")
    now=datetime.utcnow(); row=D.AcademicQualityReview(id=uid(),tenant_id=TENANT,title=body.title.strip(),scope_level=body.scope_level,scope_ref=body.scope_ref,metric_key=body.metric_key,metric_value=body.metric_value,threshold=body.threshold,deviation=body.deviation,root_cause=body.root_cause,owner_id=body.owner_id,effectiveness_measure=body.effectiveness_measure,due_at=datetime.fromisoformat(body.due_at) if body.due_at else now+timedelta(days=14),created_by=ctx["sub"],created_at=now,updated_at=now); s.add(row); s.commit(); write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.quality.review.create",f"quality_review:{row.id}","","OPEN",body.deviation); return {"review_id":row.id,"state":row.state}


class QualityReviewTransitionIn(BaseModel):
    target_state: str
    expected_status_version: int = Field(ge=0)
    effectiveness_result: str = ""
    reason: str = ""


class EffectivenessMeasurementIn(BaseModel):
    measure: str
    result: str
    value: float | None = None


@router.post("/academics/quality/reviews/{review_id}/effectiveness")
def record_effectiveness(review_id: str, body: EffectivenessMeasurementIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "manage_quality")[0])
    review=require_academic_object(s, ctx, s.get(D.AcademicQualityReview, review_id), "verify", "Quality review")
    if review.state != "EFFECTIVENESS_REVIEW": raise HTTPException(409, "Review must be in effectiveness review")
    row=D.QualityEffectivenessMeasurement(id=uid(),tenant_id=TENANT,review_id=review.id,measure=body.measure.strip(),result=body.result.strip(),value=body.value,measured_by=ctx["sub"]); s.add(row); review.effectiveness_measure=body.measure.strip(); review.effectiveness_result=body.result.strip(); review.updated_at=datetime.utcnow(); s.commit()
    return {"id":row.id,"review_id":review.id,"measured_at":row.measured_at.isoformat()}


@router.get("/academics/quality/reviews/{review_id}/effectiveness")
def effectiveness_history(review_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view", governance=True)[0])
    review=require_academic_object(s, ctx, s.get(D.AcademicQualityReview, review_id), "read", "Quality review")
    rows=s.query(D.QualityEffectivenessMeasurement).filter(D.QualityEffectivenessMeasurement.tenant_id==TENANT,D.QualityEffectivenessMeasurement.review_id==review.id).order_by(D.QualityEffectivenessMeasurement.measured_at).all()
    return {"review_id":review.id,"measurements":[{"id":x.id,"measure":x.measure,"result":x.result,"value":x.value,"measured_by":x.measured_by,"measured_at":x.measured_at.isoformat()} for x in rows]}


@router.post("/academics/quality/reviews/{review_id}/transition")
def transition_quality_review(review_id: str, body: QualityReviewTransitionIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "manage_quality")[0])
    review=require_academic_object(s, ctx, s.get(D.AcademicQualityReview, review_id), "verify", "Quality review")
    target=body.target_state.upper()
    allowed={"OPEN":{"INVESTIGATION"},"INVESTIGATION":{"ROOT_CAUSE_CONFIRMED","OPEN"},"ROOT_CAUSE_CONFIRMED":{"ACTION_PLAN_APPROVED"},"ACTION_PLAN_APPROVED":{"ACTIONS_IN_PROGRESS"},"ACTIONS_IN_PROGRESS":{"EFFECTIVENESS_REVIEW"},"EFFECTIVENESS_REVIEW":{"CLOSED","ACTIONS_IN_PROGRESS"},"CLOSED":set()}
    if review.state == "ACTION_ASSIGNED":
        # Compatibility for records created before the state machine was
        # consolidated.  Persist the normalized state on their next action.
        review.state = "ACTION_PLAN_APPROVED"
    if target not in allowed.get(review.state, set()): raise HTTPException(409, f"Transition {review.state} -> {target} is not allowed")
    if review.status_version != body.expected_status_version: raise HTTPException(409, "Review changed; reload before transitioning")
    if target == "CLOSED":
        actions=s.query(D.CorrectiveAction).filter(D.CorrectiveAction.review_id==review.id, D.CorrectiveAction.tenant_id==TENANT).all()
        if not actions or any(action.state != "VERIFIED" for action in actions): raise HTTPException(409, "All corrective actions must be verified before closure")
        measurement=s.query(D.QualityEffectivenessMeasurement).filter(D.QualityEffectivenessMeasurement.review_id==review.id, D.QualityEffectivenessMeasurement.tenant_id==TENANT).first()
        if not measurement: raise HTTPException(409, "A post-action effectiveness measurement is required before closure")
        review.closed_at=datetime.utcnow()
    previous=review.state; review.state=target; review.status_version+=1; review.updated_at=datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], actor_name(s,ctx), ctx["office_n"], "academic.quality.review.transition", f"quality_review:{review.id}", previous, target, body.reason)
    return {"review_id":review.id,"state":review.state,"status_version":review.status_version}


@router.post("/academics/quality/reviews/{review_id}/actions")
def create_corrective_action(review_id: str, body: CorrectiveActionIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "manage_quality")[0])
    review=require_academic_object(s, ctx, s.get(D.AcademicQualityReview,review_id), "assign", "Quality review")
    if review.state == "ACTION_ASSIGNED": review.state = "ACTION_PLAN_APPROVED"
    if review.state not in {"ACTION_PLAN_APPROVED", "ACTIONS_IN_PROGRESS"}:
        raise HTTPException(409, "Corrective actions can be assigned only after the action plan is approved")
    review_scope = hierarchy(s, review)
    if body.priority not in {"low", "medium", "high", "critical"}: raise HTTPException(422, "Invalid action priority")
    action=D.CorrectiveAction(id=uid(),tenant_id=TENANT,review_id=review_id,school_id=review_scope.school_id,dept_id=review_scope.dept_id,program_id=review_scope.program_id,section_id=review_scope.section_id,title=body.title.strip(),owner_id=body.owner_id,deadline=datetime.fromisoformat(body.deadline),priority=body.priority,escalation_target=body.escalation_target,created_by=ctx["sub"]); s.add(action); review.state="ACTIONS_IN_PROGRESS"; review.status_version+=1; review.updated_at=datetime.utcnow(); s.commit(); write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.quality.action.create",f"corrective_action:{action.id}","ACTION_PLAN_APPROVED","ACTIONS_IN_PROGRESS",body.title); owner=s.get(User,body.owner_id); owner and _proposal_notice(s,owner.id,"Corrective action assigned",body.title); return {"action_id":action.id,"state":action.state}


@router.get("/academics/quality/actions")
def corrective_actions(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view", governance=True)[0]); rows=scoped_academic_query(s, D.CorrectiveAction, ctx).order_by(D.CorrectiveAction.deadline).all(); now=datetime.utcnow()
    return {"actions":[{"id":x.id,"review_id":x.review_id,"title":x.title,"owner_id":x.owner_id,"deadline":x.deadline.isoformat() if x.deadline else None,"state":"OVERDUE" if x.state in {"OPEN","IN_PROGRESS"} and x.deadline and x.deadline<now else x.state,"priority":x.priority,"progress":x.progress,"evidence_versions":json.loads(x.evidence_versions or "[]"),"owner_acknowledged":x.owner_acknowledged,"escalation_target":x.escalation_target,"verification_result":x.verification_result,"evidence":x.evidence,"status_version":x.status_version} for x in rows],"overdue":sum(1 for x in rows if x.state in {"OPEN","IN_PROGRESS"} and x.deadline and x.deadline<now)}


class ActionUpdateIn(BaseModel):
    evidence: str = ""
    expected_status_version: int = Field(ge=0)
    progress: float = Field(default=100, ge=0, le=100)
    owner_acknowledged: bool = False
    verification_result: str = ""


@router.post("/academics/quality/actions/{action_id}/submit")
def submit_corrective_action(action_id: str, body: ActionUpdateIn, ctx=Depends(auth), s=Depends(db)):
    action=require_tenant(s.get(D.CorrectiveAction,action_id), ctx, "Corrective action")
    if action.owner_id != ctx["sub"] or action.status_version != body.expected_status_version: raise HTTPException(403,"Only the action owner can submit current evidence")
    action.evidence=body.evidence.strip(); action.evidence_versions=json.dumps(json.loads(action.evidence_versions or "[]") + [{"version": len(json.loads(action.evidence_versions or "[]"))+1, "evidence": action.evidence, "at": datetime.utcnow().isoformat()}]); action.progress=body.progress; action.owner_acknowledged=body.owner_acknowledged; action.state="EVIDENCE_SUBMITTED"; action.status_version+=1; action.updated_at=datetime.utcnow(); s.commit(); return {"state":action.state,"progress":action.progress}


@router.post("/academics/quality/actions/{action_id}/verify")
def verify_corrective_action(action_id: str, body: ActionUpdateIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "manage_quality")[0])
    action=require_academic_object(s, ctx, s.get(D.CorrectiveAction,action_id), "verify", "Corrective action")
    if action.status_version != body.expected_status_version: raise HTTPException(409,"Action changed or not found")
    if not action.evidence.strip(): raise HTTPException(422,"Evidence is required before verification")
    action.state="VERIFIED"; action.verified_by=ctx["sub"]; action.verification_result=body.verification_result.strip() or "Evidence verified"; action.status_version+=1; action.updated_at=datetime.utcnow(); review=s.get(D.AcademicQualityReview,action.review_id); review.verified_by=ctx["sub"]; review.state="EFFECTIVENESS_REVIEW"; review.updated_at=datetime.utcnow(); s.commit(); write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.quality.action.verify",f"corrective_action:{action.id}","EVIDENCE_SUBMITTED","VERIFIED",body.evidence); return {"state":action.state,"review_state":review.state}


#  ACADEMICS: courses & sections
# --------------------------------------------------------------------------- #
@router.get("/academics/courses")
def list_courses(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    dept_map = {d.id: d.code for d in s.query(D.Department).all()}
    program_map = {p.id: p.name for p in s.query(D.Program).all()}
    course_query = s.query(D.Course)
    if ctx["office_n"] == 10:
        staff = _staff_profile(s, ctx)
        if staff and staff.dept_id: course_query = course_query.filter(D.Course.dept_id == staff.dept_id)
    rows = course_query.order_by(D.Course.code).all()
    course_ids = {row.id for row in rows}
    sections = s.query(D.Section).filter(D.Section.tenant_id == ctx["tenant_id"], D.Section.course_id.in_(course_ids) if course_ids else text("1=0")).all()
    staff_map = {row.id: row.name for row in s.query(D.StaffMember).filter(D.StaffMember.tenant_id == ctx["tenant_id"]).all()}
    result_rows = s.query(D.StudentSubjectResult).filter(D.StudentSubjectResult.tenant_id == ctx["tenant_id"], D.StudentSubjectResult.course_id.in_(course_ids) if course_ids else text("1=0"), D.StudentSubjectResult.outcome.in_(["passed", "failed"])).all()
    results_by_course = {}
    for result in result_rows: results_by_course.setdefault(result.course_id, []).append(result.outcome == "passed")
    outcomes_by_course = {course_id: 0 for course_id in course_ids}
    for outcome in s.query(D.CourseOutcome).filter(D.CourseOutcome.tenant_id == ctx["tenant_id"], D.CourseOutcome.course_id.in_(course_ids) if course_ids else text("1=0"), D.CourseOutcome.active == True).all(): outcomes_by_course[outcome.course_id] = outcomes_by_course.get(outcome.course_id, 0) + 1
    sections_by_course = {}
    for section in sections: sections_by_course.setdefault(section.course_id, []).append(section)
    return {"courses": [{
        "id": r.id, "code": r.code, "title": r.title, "credits": r.credits,
        "semester": r.semester, "dept": dept_map.get(r.dept_id, ""), "program_id": r.program_id,
        "program": program_map.get(r.program_id, "B.Tech"), "regulation": r.regulation or "R2023",
        "course_type": r.course_type or "Core", "category": r.category or "Professional Core",
        "ltp": r.ltp or "", "prerequisite": r.prerequisite or "", "status": r.status or "Active",
        "description": r.description or "",
        "sections": len(sections_by_course.get(r.id, [])),
        "faculty": sorted({staff_map.get(x.faculty_person_id, "Unassigned") for x in sections_by_course.get(r.id, [])}),
        "unassigned_sections": sum(1 for x in sections_by_course.get(r.id, []) if not x.faculty_person_id),
        "outcome_count": outcomes_by_course.get(r.id, 0),
        "pass_rate": round(100 * sum(results_by_course.get(r.id, [])) / len(results_by_course[r.id]), 1) if results_by_course.get(r.id) else None,
    } for r in rows], "can_create": can(s, ctx, "academics", "create_course")}


@router.get("/academics/programs")
def list_academic_programs(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    return {"programs": [{"id": p.id, "code": p.code, "name": p.name, "level": p.level} for p in s.query(D.Program).filter_by(tenant_id=TENANT).order_by(D.Program.code).all()]}


class CourseIn(BaseModel):
    code: str
    title: str
    dept_code: str
    credits: int = 3
    semester: int = 1
    program: str = "B.Tech"
    regulation: str = "R2023"
    course_type: str = "Core"
    category: str = "Professional Core"
    ltp: str = "3-0-0"
    prerequisite: str = ""
    description: str = ""


class CurriculumProposalIn(BaseModel):
    course_id: str = ""
    code: str
    title: str
    dept_code: str
    credits: int = Field(default=3, ge=1, le=30)
    semester: int = Field(default=1, ge=1, le=16)
    regulation: str = "R2023"
    course_type: str = "Core"
    category: str = "Professional Core"
    ltp: str = "3-0-0"
    prerequisite: str = ""
    description: str = ""
    effective_term: str
    rationale: str = ""


class ProgramProposalIn(BaseModel):
    program_id: str = ""
    code: str
    name: str
    dept_code: str
    level: str = "UG"
    duration_years: int = Field(default=4, ge=1, le=10)
    effective_term: str
    rationale: str = ""


@router.get("/programs/proposals")
def program_proposals(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view", governance=True)[0])
    query = scoped_academic_query(s, D.AcademicProposal, ctx).filter(
        D.AcademicProposal.proposal_type == "program",
    )
    if ctx["office_n"] != 6:
        query = query.filter(D.AcademicProposal.scope_ref == (actor_department_id(s, ctx) or "__no_scope__"))
    departments = scoped_academic_query(s, D.Department, ctx).order_by(D.Department.name).all()
    terms = s.query(D.AcademicYear, D.Semester).join(
        D.Semester, D.Semester.academic_year_id == D.AcademicYear.id
    ).filter(
        D.AcademicYear.tenant_id == ctx["tenant_id"],
        D.AcademicYear.is_active == True,
        D.Semester.is_active == True,
    ).order_by(D.AcademicYear.start_date.desc(), D.Semester.sequence).all()
    return {
        "proposals": [_proposal_payload(s, row) for row in query.order_by(desc(D.AcademicProposal.updated_at)).all()],
        "can_propose": ctx["office_n"] in {10, 17, 41},
        "can_decide": ctx["office_n"] == 6,
        "form_options": {
            "departments": [{"id": row.id, "code": row.code, "name": row.name} for row in departments],
            "effective_terms": [{"value": f"{year.name} · {semester.name}", "label": f"{year.name} · {semester.name}"} for year, semester in terms],
        },
    }


@router.get("/programs/proposals/{proposal_id}")
def program_proposal_detail(proposal_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view", governance=True)[0])
    proposal = require_academic_object(s, ctx, s.get(D.AcademicProposal, proposal_id), "read", "Programme proposal")
    if proposal.proposal_type != "program": raise HTTPException(404, "Programme proposal not found")
    return {"proposal": _proposal_payload(s, proposal)}


@router.post("/programs/proposals")
def create_program_proposal(body: ProgramProposalIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s,ctx,"academics","view", governance=True)[0])
    if ctx["office_n"] not in {10,17,41}: raise HTTPException(403,"Only HOD, Academic Coordinator, or Program Coordinator can propose programmes")
    dept=require_academic_object(s, ctx, s.query(D.Department).filter(D.Department.tenant_id == ctx["tenant_id"], D.Department.code==body.dept_code).first(), "create", "Department")
    staff=s.query(D.StaffMember).filter(D.StaffMember.dept_id==dept.id,D.StaffMember.status=="active").count(); courses=s.query(D.Course).filter(D.Course.dept_id==dept.id).count()
    payload=body.model_dump(); payload["dept_id"]=dept.id; payload["feasibility"]={"active_faculty":staff,"available_courses":courses,"ready":staff>=1 and courses>=1}
    now=datetime.utcnow(); p=D.AcademicProposal(id=uid(),tenant_id=TENANT,proposal_type="program",title=f"Programme proposal: {body.code.upper()} — {body.name}",scope_level="department",scope_ref=dept.id,school_id=dept.school_id,dept_id=dept.id,state="DRAFT",version_no=1,submitted_by=ctx["sub"],submitted_office_n=ctx["office_n"],assigned_to_office_n=6,due_at=now+timedelta(days=15),created_at=now,updated_at=now);s.add(p);s.flush();s.add(D.AcademicProposalVersion(id=uid(),tenant_id=TENANT,proposal_id=p.id,version_no=1,payload_json=json.dumps(payload),rationale=body.rationale,created_by=ctx["sub"]));_proposal_event(s,p,ctx,"","DRAFT",body.rationale);write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.program.proposal.create",f"academic_proposal:{p.id}","","DRAFT",body.rationale,commit=False);s.commit();return {"proposal":_proposal_payload(s,p)}


@router.post("/programs/proposals/{proposal_id}/submit")
def submit_program_proposal(proposal_id:str,body:AcademicProposalTransitionIn,ctx=Depends(auth),s=Depends(db)):
    p=require_academic_object(s, ctx, s.query(D.AcademicProposal).filter(D.AcademicProposal.id == proposal_id).with_for_update().first(), "submit", "Programme proposal")
    if not p or p.proposal_type!="program" or p.submitted_by!=ctx["sub"] or p.state!="DRAFT" or p.status_version!=body.expected_status_version: raise HTTPException(409,"Programme proposal cannot be submitted")
    p.state="SUBMITTED";p.status_version+=1;p.updated_at=datetime.utcnow();_proposal_event(s,p,ctx,"DRAFT","SUBMITTED",body.reason);write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.program.proposal.submit",f"academic_proposal:{p.id}","DRAFT","SUBMITTED",body.reason,commit=False);s.commit();return {"proposal":_proposal_payload(s,p)}


@router.post("/programs/proposals/{proposal_id}/decision/{decision}")
def decide_program_proposal(proposal_id:str,decision:str,body:AcademicProposalTransitionIn,ctx=Depends(auth),s=Depends(db)):
    require(gate(s, ctx, "academics", "approve_proposal" if decision.lower() == "approve" else "reject_proposal")[0])
    p=require_tenant(s.get(D.AcademicProposal,proposal_id), ctx, "Programme proposal")
    prevent_self_approval(p, ctx)
    if not p or p.proposal_type!="program" or p.state!="SUBMITTED" or p.status_version!=body.expected_status_version: raise HTTPException(409,"Invalid programme decision")
    target={"approve":"APPROVED","reject":"REJECTED","return":"RETURNED","escalate":"ESCALATED"}.get(decision.lower())
    if not target: raise HTTPException(422,"Unsupported decision")
    validate_transition(s, p, target, body.expected_status_version, ctx, body.reason)
    claim_proposal_transition(s, p, body.expected_status_version, {"SUBMITTED"})
    data=json.loads(_proposal_version(s,p).payload_json)
    if target=="APPROVED" and not data["feasibility"]["ready"]: raise HTTPException(409,"Programme lacks faculty or course readiness; escalate or revise")
    previous=p.state;p.state=target;p.status_version+=1;p.updated_at=datetime.utcnow()
    if target=="APPROVED":
        program=require_academic_object(s, ctx, s.get(D.Program,data.get("program_id")), "approve", "Program") if data.get("program_id") else None
        if not program: program=D.Program(id=uid(),tenant_id=TENANT,dept_id=data["dept_id"],code=data["code"].upper(),name=data["name"],level=data["level"],duration_years=data["duration_years"]);s.add(program);s.flush()
        else: program.code=data["code"].upper();program.name=data["name"];program.level=data["level"];program.duration_years=data["duration_years"]
        p.implementation_ref=program.id
    if target=="ESCALATED":p.escalated_to_office_n=4
    _proposal_event(s,p,ctx,previous,target,body.reason);write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.program.proposal.decision",f"academic_proposal:{p.id}",previous,target,body.reason,commit=False);s.commit();return {"proposal":_proposal_payload(s,p)}


@router.get("/academics/committees")
def committees(ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","view", governance=True)[0]); return {"committees":[{"id":x.id,"name":x.name,"type":x.committee_type,"chair_id":x.chair_id,"status":x.status,"permissions":json.loads(x.permissions_json or "[]")} for x in scoped_academic_query(s, D.AcademicCommittee, ctx).all()]}

class CommitteeIn(BaseModel): name:str; committee_type:str; chair_id:str=""; permissions:list[str]=["view","record","assign","verify"]
class CommitteeUpdateIn(BaseModel): name:str; committee_type:str; chair_id:str=""; status:str="active"; permissions:list[str]=["view","record","assign","verify"]
class MeetingIn(BaseModel): committee_id:str; meeting_at:str; agenda:str=""
class ResolutionIn(BaseModel): title:str; decision:str; linked_proposal_id:str=""; linked_quality_action_id:str=""; linked_planning_item_id:str=""

def require_committee_permission(s, ctx, committee_id, permission):
    committee=require_academic_object(s,ctx,s.get(D.AcademicCommittee,committee_id),"read","Committee")
    if ctx["office_n"] == 6: return committee
    member=s.query(D.CommitteeMember).filter(D.CommitteeMember.tenant_id==TENANT,D.CommitteeMember.committee_id==committee.id,D.CommitteeMember.user_id==ctx["sub"],D.CommitteeMember.active==True).first()
    if not member or permission not in json.loads(committee.permissions_json or "[]"):
        raise HTTPException(403,"Committee permission denied")
    return committee

@router.post("/academics/committees")
def create_committee(body:CommitteeIn,ctx=Depends(auth),s=Depends(db)):
    require(gate(s, ctx, "academics", "manage_committee", governance=True)[0])
    row=D.AcademicCommittee(id=uid(),tenant_id=TENANT,name=body.name,committee_type=body.committee_type,chair_id=body.chair_id,permissions_json=json.dumps(body.permissions));s.add(row);s.commit();write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.committee.create",f"committee:{row.id}","","active",body.name);return {"id":row.id,"status":row.status,"permissions":body.permissions}

@router.put("/academics/committees/{committee_id}")
def update_committee(committee_id:str,body:CommitteeUpdateIn,ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","manage_committee", governance=True)[0]); row=require_academic_object(s,ctx,s.get(D.AcademicCommittee,committee_id),"edit","Committee")
    if body.chair_id and not s.get(User,body.chair_id): raise HTTPException(404,"Chair user not found")
    previous=row.status; row.name=body.name.strip(); row.committee_type=body.committee_type.strip(); row.chair_id=body.chair_id.strip(); row.status=body.status; row.permissions_json=json.dumps(body.permissions); s.commit(); write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.committee.update",f"committee:{row.id}",previous,row.status,body.name); return {"id":row.id,"name":row.name,"type":row.committee_type,"chair_id":row.chair_id,"status":row.status,"permissions":body.permissions}

@router.post("/academics/committees/meetings")
def create_meeting(body:MeetingIn,ctx=Depends(auth),s=Depends(db)):
    require(gate(s, ctx, "academics", "manage_committee", governance=True)[0])
    require_committee_permission(s,ctx,body.committee_id,"record")
    row=D.CommitteeMeeting(id=uid(),tenant_id=TENANT,committee_id=body.committee_id,meeting_at=datetime.fromisoformat(body.meeting_at),agenda=body.agenda,created_by=ctx["sub"]);s.add(row);s.commit();write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.committee.meeting.create",f"committee_meeting:{row.id}","","SCHEDULED",body.agenda);return {"id":row.id,"status":row.status}

@router.get("/academics/committees/{committee_id}/meetings")
def committee_meetings(committee_id:str,ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","view", governance=True)[0]); require_academic_object(s,ctx,s.get(D.AcademicCommittee,committee_id),"read","Committee")
    rows=s.query(D.CommitteeMeeting).filter(D.CommitteeMeeting.tenant_id==TENANT,D.CommitteeMeeting.committee_id==committee_id).order_by(desc(D.CommitteeMeeting.meeting_at)).all()
    return {"meetings":[{"id":x.id,"meeting_at":x.meeting_at.isoformat(),"agenda":x.agenda,"minutes":x.minutes,"status":x.status,"agenda_status":x.agenda_status,"minutes_status":x.minutes_status} for x in rows]}

class CommitteeTransitionIn(BaseModel): target_status:str; reason:str=""; content:str=""

@router.post("/academics/committees/meetings/{meeting_id}/transition")
def transition_meeting(meeting_id:str,body:CommitteeTransitionIn,ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","manage_committee", governance=True)[0]); row=require_academic_object(s,ctx,s.get(D.CommitteeMeeting,meeting_id),"edit","Committee meeting"); require_committee_permission(s,ctx,row.committee_id,"record"); target=body.target_status.upper()
    if target not in {"AGENDA_APPROVED","HELD","MINUTES_DRAFT","MINUTES_FINAL"}: raise HTTPException(422,"Unknown meeting status")
    if target=="AGENDA_APPROVED" and not row.agenda.strip(): raise HTTPException(422,"Agenda is required")
    if target in {"MINUTES_DRAFT","MINUTES_FINAL"} and body.content.strip(): row.minutes=body.content.strip()
    if target=="AGENDA_APPROVED": row.agenda_status="APPROVED"
    if target=="MINUTES_DRAFT": row.minutes_status="DRAFT"
    if target=="MINUTES_FINAL": row.minutes_status="FINAL"
    row.status=target; s.commit(); return {"id":row.id,"status":row.status,"agenda_status":row.agenda_status,"minutes_status":row.minutes_status}

@router.post("/academics/committees/meetings/{meeting_id}/resolutions")
def create_resolution(meeting_id:str,body:ResolutionIn,ctx=Depends(auth),s=Depends(db)):
    require(gate(s, ctx, "academics", "manage_committee", governance=True)[0])
    require_academic_object(s, ctx, s.get(D.CommitteeMeeting,meeting_id), "create", "Committee meeting")
    meeting=require_academic_object(s,ctx,s.get(D.CommitteeMeeting,meeting_id),"create","Committee meeting")
    require_committee_permission(s,ctx,meeting.committee_id,"record")
    if meeting.minutes_status != "FINAL": raise HTTPException(409,"Minutes must be finalized before recording a resolution")
    row=D.CommitteeResolution(id=uid(),tenant_id=TENANT,meeting_id=meeting_id,title=body.title,decision=body.decision,linked_proposal_id=body.linked_proposal_id,linked_quality_action_id=body.linked_quality_action_id,linked_planning_item_id=body.linked_planning_item_id);s.add(row);s.commit();write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.committee.resolution.create",f"committee_resolution:{row.id}","","DRAFT",body.decision);return {"id":row.id,"status":row.status}

@router.get("/academics/committees/{committee_id}/resolutions")
def committee_resolutions(committee_id:str,ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","view", governance=True)[0]); require_academic_object(s,ctx,s.get(D.AcademicCommittee,committee_id),"read","Committee")
    rows=s.query(D.CommitteeResolution).join(D.CommitteeMeeting,D.CommitteeResolution.meeting_id==D.CommitteeMeeting.id).filter(D.CommitteeMeeting.committee_id==committee_id,D.CommitteeResolution.tenant_id==TENANT).all()
    return {"resolutions":[{"id":x.id,"meeting_id":x.meeting_id,"title":x.title,"decision":x.decision,"status":x.status,"linked_proposal_id":x.linked_proposal_id,"linked_quality_action_id":x.linked_quality_action_id,"linked_planning_item_id":x.linked_planning_item_id} for x in rows]}

@router.post("/academics/committees/resolutions/{resolution_id}/transition")
def transition_resolution(resolution_id:str,body:CommitteeTransitionIn,ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","manage_committee", governance=True)[0]); row=require_academic_object(s,ctx,s.get(D.CommitteeResolution,resolution_id),"approve","Committee resolution"); meeting=s.get(D.CommitteeMeeting,row.meeting_id); require_committee_permission(s,ctx,meeting.committee_id,"approve"); target=body.target_status.upper()
    if target not in {"APPROVED","REJECTED"}: raise HTTPException(422,"Resolution must be approved or rejected")
    row.status=target; row.approved_by=ctx["sub"]; row.approved_at=datetime.utcnow(); s.commit(); return {"id":row.id,"status":row.status}

class MemberIn(BaseModel): user_id:str; role:str="member"
@router.post("/academics/committees/{committee_id}/members")
def add_committee_member(committee_id:str,body:MemberIn,ctx=Depends(auth),s=Depends(db)):
    require(gate(s, ctx, "academics", "manage_committee", governance=True)[0])
    require_academic_object(s, ctx, s.get(D.AcademicCommittee,committee_id), "create", "Committee")
    if not s.get(User,body.user_id): raise HTTPException(404,"User not found")
    if s.query(D.CommitteeMember).filter(D.CommitteeMember.tenant_id == ctx["tenant_id"], D.CommitteeMember.committee_id == committee_id, D.CommitteeMember.user_id == body.user_id, D.CommitteeMember.active == True).first(): raise HTTPException(409,"User is already an active committee member")
    row=D.CommitteeMember(id=uid(),tenant_id=TENANT,committee_id=committee_id,user_id=body.user_id,role=body.role);s.add(row);s.commit();write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.committee.member.add",f"committee_member:{row.id}","","active",body.user_id);return {"id":row.id}

@router.delete("/academics/committees/{committee_id}/members/{member_id}")
def remove_committee_member(committee_id:str,member_id:str,ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","manage_committee", governance=True)[0]); require_committee_permission(s,ctx,committee_id,"assign")
    row=s.query(D.CommitteeMember).filter(D.CommitteeMember.tenant_id==TENANT,D.CommitteeMember.id==member_id,D.CommitteeMember.committee_id==committee_id,D.CommitteeMember.active==True).first()
    if not row: raise HTTPException(404,"Active committee member not found")
    row.active=False; s.commit(); return {"id":row.id,"active":False}

@router.get("/academics/committees/{committee_id}/members")
def committee_members(committee_id:str,ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","view", governance=True)[0]); committee=require_academic_object(s, ctx, s.get(D.AcademicCommittee, committee_id), "read", "Committee");return {"members":[{"id":x.id,"user_id":x.user_id,"role":x.role} for x in s.query(D.CommitteeMember).filter(D.CommitteeMember.tenant_id == ctx["tenant_id"], D.CommitteeMember.committee_id==committee.id,D.CommitteeMember.active==True).all()]}

class CommitteeActionIn(BaseModel): title:str; owner_id:str; deadline:str=""
@router.post("/academics/committees/resolutions/{resolution_id}/actions")
def committee_action(resolution_id:str,body:CommitteeActionIn,ctx=Depends(auth),s=Depends(db)):
    require(gate(s, ctx, "academics", "manage_committee", governance=True)[0])
    resolution=require_academic_object(s, ctx, s.get(D.CommitteeResolution,resolution_id), "create", "Committee resolution")
    meeting=s.get(D.CommitteeMeeting,resolution.meeting_id); require_committee_permission(s,ctx,meeting.committee_id,"assign")
    row=D.CommitteeActionItem(id=uid(),tenant_id=TENANT,resolution_id=resolution_id,title=body.title,owner_id=body.owner_id,deadline=datetime.fromisoformat(body.deadline) if body.deadline else None);s.add(row);s.commit();write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.committee.action.create",f"committee_action:{row.id}","","OPEN",body.title);return {"id":row.id,"status":row.status}

@router.get("/academics/committees/action-items")
def committee_action_items(ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","view", governance=True)[0]); rows=s.query(D.CommitteeActionItem).filter(D.CommitteeActionItem.tenant_id==TENANT).order_by(D.CommitteeActionItem.deadline).all()
    return {"actions":[{"id":x.id,"resolution_id":x.resolution_id,"title":x.title,"owner_id":x.owner_id,"deadline":x.deadline.isoformat() if x.deadline else None,"status":x.status,"evidence":x.evidence,"verification_result":x.verification_result} for x in rows]}

@router.post("/academics/committees/action-items/{action_id}/verify")
def verify_committee_action(action_id:str,body:CommitteeTransitionIn,ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","manage_committee", governance=True)[0]); row=require_academic_object(s,ctx,s.get(D.CommitteeActionItem,action_id),"verify","Committee action"); resolution=s.get(D.CommitteeResolution,row.resolution_id); meeting=s.get(D.CommitteeMeeting,resolution.meeting_id); require_committee_permission(s,ctx,meeting.committee_id,"verify")
    if not body.content.strip(): raise HTTPException(422,"Verification evidence is required")
    row.evidence=body.content.strip(); row.verification_result=body.reason.strip() or "Verified"; row.status="VERIFIED"; row.verified_by=ctx["sub"]; row.verified_at=datetime.utcnow(); s.commit(); return {"id":row.id,"status":row.status}

@router.get("/academics/attainment")
def attainment(program_id:str="",course_id:str="",ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","view", governance=True)[0]);
    if program_id: require_academic_object(s, ctx, s.get(D.Program, program_id), "read", "Program")
    courses=scoped_academic_query(s, D.Course, ctx).filter(D.Course.id==course_id).all() if course_id else scoped_academic_query(s, D.Course, ctx).all(); course_ids={x.id for x in courses}; co=s.query(D.CourseOutcome).filter(D.CourseOutcome.tenant_id == ctx["tenant_id"], D.CourseOutcome.course_id.in_(course_ids),D.CourseOutcome.active==True).all() if course_ids else []; mappings=s.query(D.OutcomeMapping).filter(D.OutcomeMapping.tenant_id == ctx["tenant_id"], D.OutcomeMapping.course_outcome_id.in_([x.id for x in co])).all() if co else []; results=s.query(D.StudentSubjectResult).filter(D.StudentSubjectResult.tenant_id == ctx["tenant_id"], D.StudentSubjectResult.course_id.in_(course_ids),D.StudentSubjectResult.outcome.in_(["passed","failed"])).all() if course_ids else []
    by_course={};
    for row in results: by_course.setdefault(row.course_id,[]).append(1 if row.outcome=="passed" else 0)
    sections=s.query(D.Section).filter(D.Section.course_id.in_(course_ids)).all() if course_ids else []
    assessments=s.query(D.Assessment).filter(D.Assessment.tenant_id==ctx["tenant_id"],D.Assessment.section_id.in_([x.id for x in sections])).all() if sections else []
    assessment_ids={x.id for x in assessments}; assessment_maps=s.query(D.AssessmentOutcomeMapping).filter(D.AssessmentOutcomeMapping.tenant_id==ctx["tenant_id"],D.AssessmentOutcomeMapping.assessment_id.in_(assessment_ids)).all() if assessment_ids else []
    marks=s.query(D.Mark).filter(D.Mark.tenant_id==ctx["tenant_id"],D.Mark.assessment_id.in_(assessment_ids),D.Mark.is_valid==True).all() if assessment_ids else []
    mark_by_assessment={}
    for mark in marks: mark_by_assessment.setdefault(mark.assessment_id,[]).append(mark)
    by_co={}
    for mapping in assessment_maps:
        assessment=next((item for item in assessments if item.id==mapping.assessment_id),None)
        values=[100*mark.score/max(assessment.max_marks,1) for mark in mark_by_assessment.get(mapping.assessment_id,[])] if assessment else []
        if values: by_co.setdefault(mapping.course_outcome_id,[]).extend((value,mapping.weight) for value in values)
    co_out=[]
    for row in co:
        values=by_co.get(row.id,[]); vals=by_course.get(row.course_id,[]); value=(sum(score*weight for score,weight in values)/sum(weight for _,weight in values)) if values else (100*sum(vals)/len(vals) if vals else None); co_out.append({"id":row.id,"code":row.code,"course_id":row.course_id,"attainment":round(value,2) if value is not None else None,"evidence":"assessment_marks" if values else "published_results"})
    po_ids={x.program_outcome_id for x in mappings}; po=s.query(D.ProgramOutcome).filter(D.ProgramOutcome.id.in_(po_ids)).all() if po_ids else []
    po_out=[{"id":x.id,"code":x.code,"description":x.description,"attainment":round(sum(y["attainment"] for y in co_out if y["attainment"] is not None and any(m.program_outcome_id==x.id and m.course_outcome_id==y["id"] for m in mappings))/max(1,sum(1 for y in co_out if y["attainment"] is not None and any(m.program_outcome_id==x.id and m.course_outcome_id==y["id"] for m in mappings))),2) if any(m.program_outcome_id==x.id for m in mappings) else None} for x in po]
    return {"course_outcomes":co_out,"program_outcomes":po_out,"mapping_count":len(mappings)}

@router.get("/academics/attainment/alerts")
def attainment_alerts(program_id:str="",course_id:str="",ctx=Depends(auth),s=Depends(db)):
    data=attainment(program_id,course_id,ctx,s); alerts=[]
    targets={x.outcome_id:x for x in s.query(D.OutcomeAttainmentTarget).filter(D.OutcomeAttainmentTarget.tenant_id==TENANT).all()}
    for outcome in data["course_outcomes"] + data["program_outcomes"]:
        target=targets.get(outcome["id"]); threshold=target.threshold if target else 50
        if outcome["attainment"] is not None and outcome["attainment"] < threshold:
            alerts.append({"outcome_id":outcome["id"],"code":outcome["code"],"attainment":outcome["attainment"],"threshold":threshold,"severity":"critical" if outcome["attainment"] < threshold-10 else "warning"})
    return {"alerts":alerts,"count":len(alerts),"linked_quality_reviews":sum(1 for x in s.query(D.AcademicQualityReview).filter(D.AcademicQualityReview.metric_key=="outcome_attainment").all())}


@router.post("/academics/attainment/alerts/link-quality-reviews")
def link_attainment_alerts(ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","manage_quality", governance=True)[0])
    data=attainment_alerts("","",ctx,s); created=[]
    for alert in data["alerts"]:
        existing=s.query(D.AcademicQualityReview).filter(D.AcademicQualityReview.tenant_id==TENANT,D.AcademicQualityReview.metric_key=="outcome_attainment",D.AcademicQualityReview.scope_ref==alert["outcome_id"],D.AcademicQualityReview.state!="CLOSED").first()
        if existing: continue
        row=D.AcademicQualityReview(id=uid(),tenant_id=TENANT,title=f"Attainment gap: {alert['code']}",scope_level="course",scope_ref=alert["outcome_id"],metric_key="outcome_attainment",metric_value=alert["attainment"],threshold=alert["threshold"],deviation=f"{alert['code']} is below threshold",state="OPEN",created_by=ctx["sub"],updated_at=datetime.utcnow()); s.add(row); created.append(row.id)
    s.commit(); return {"created_review_ids":created,"count":len(created)}


@router.get("/academics/attainment/aggregate")
def attainment_aggregate(level:str="course",term:str="",ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","view", governance=True)[0])
    levels={"student","section","course","program","department","semester"}
    if level not in levels: raise HTTPException(422,"Unknown attainment aggregation level")
    sections=s.query(D.Section).filter(D.Section.tenant_id==TENANT).all(); section_map={x.id:x for x in sections}; course_map={x.id:x for x in s.query(D.Course).filter(D.Course.tenant_id==TENANT).all()}; students={x.id:x for x in s.query(D.Student).filter(D.Student.tenant_id==TENANT).all()}
    assessments=s.query(D.Assessment).filter(D.Assessment.tenant_id==TENANT).all(); assessment_map={x.id:x for x in assessments}; marks=s.query(D.Mark).filter(D.Mark.tenant_id==TENANT,D.Mark.is_valid==True).all(); aggregates={}
    for mark in marks:
        assessment=assessment_map.get(mark.assessment_id); section=section_map.get(assessment.section_id) if assessment else None
        if not section: continue
        course=course_map.get(section.course_id); student_key=mark.student_id
        if level=="student": key=student_key; label=students.get(student_key).name if students.get(student_key) else student_key
        elif level=="section": key=section.id; label=section.section_code
        elif level=="course": key=course.id if course else section.course_id; label=course.code if course else section.course_id
        elif level=="program": key=course.program_id if course else ""; label=key
        elif level=="department": key=course.dept_id if course else ""; label=key
        else: key=assessment.academic_year or term or "unspecified"; label=key
        if term and level!="semester" and (assessment.academic_year or "") != term: continue
        score=100*mark.score/max(assessment.max_marks,1); bucket=aggregates.setdefault(key,{"id":key,"label":label,"scores":[]}); bucket["scores"].append(score)
    result=[{"id":x["id"],"label":x["label"],"attainment":round(sum(x["scores"])/len(x["scores"]),2),"evidence_count":len(x["scores"]),"term":term} for x in aggregates.values()]
    return {"level":level,"term":term,"aggregates":result}


@router.get("/academics/attainment/validation")
def attainment_validation(term:str="",ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","view", governance=True)[0])
    assessments=s.query(D.Assessment).filter(D.Assessment.tenant_id==TENANT).all(); assessment_ids={x.id for x in assessments}
    mappings=s.query(D.AssessmentOutcomeMapping).filter(D.AssessmentOutcomeMapping.tenant_id==TENANT,D.AssessmentOutcomeMapping.assessment_id.in_(assessment_ids)).all() if assessment_ids else []
    marks=s.query(D.Mark).filter(D.Mark.tenant_id==TENANT,D.Mark.assessment_id.in_(assessment_ids),D.Mark.is_valid==True).all() if assessment_ids else []
    duplicate_keys={}
    for mark in marks: duplicate_keys[(mark.assessment_id,mark.student_id)]=duplicate_keys.get((mark.assessment_id,mark.student_id),0)+1
    unmapped_assessments=[x.id for x in assessments if not any(m.assessment_id==x.id for m in mappings)]
    return {"term":term,"assessments":len(assessments),"mapped_assessments":len(assessments)-len(unmapped_assessments),"marks":len(marks),"unmapped_assessment_ids":unmapped_assessments,"duplicate_mark_keys":[{"assessment_id":key[0],"student_id":key[1],"count":count} for key,count in duplicate_keys.items() if count>1],"valid":not unmapped_assessments and not any(count>1 for count in duplicate_keys.values())}

@router.post("/academics/timetable/readiness/{exception_id}/resolve")
def resolve_timetable_exception(exception_id:str,ctx=Depends(auth),s=Depends(db)):
    require(gate(s, ctx, "academics", "resolve_exception")[0])
    row=require_academic_object(s, ctx, s.get(D.TimetableException,exception_id), "resolve", "Timetable exception")
    if row.status == "RESOLVED": raise HTTPException(409,"Timetable exception is already resolved")
    previous=row.status; row.status="RESOLVED";row.resolved_by=ctx["sub"];row.resolved_at=datetime.utcnow();s.commit();write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.timetable.exception.resolve",f"timetable_exception:{row.id}",previous,row.status,"");return {"id":row.id,"status":row.status}

@router.get("/academics/outcomes")
def outcomes(program_id:str="",course_id:str="",ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","view", governance=True)[0]);
    if program_id: require_academic_object(s, ctx, s.get(D.Program, program_id), "read", "Program")
    if course_id: require_academic_object(s, ctx, s.get(D.Course, course_id), "read", "Course")
    po=s.query(D.ProgramOutcome).filter(D.ProgramOutcome.tenant_id == ctx["tenant_id"],D.ProgramOutcome.program_id==program_id).all() if program_id else []; co=s.query(D.CourseOutcome).filter(D.CourseOutcome.tenant_id == ctx["tenant_id"],D.CourseOutcome.course_id==course_id).all() if course_id else []; return {"program_outcomes":[{"id":x.id,"code":x.code,"description":x.description} for x in po],"course_outcomes":[{"id":x.id,"code":x.code,"description":x.description} for x in co]}

class OutcomeIn(BaseModel): code:str; description:str; program_id:str=""; course_id:str=""
@router.post("/academics/outcomes/program")
def add_program_outcome(body:OutcomeIn,ctx=Depends(auth),s=Depends(db)):
    require(gate(s, ctx, "academics", "manage_outcomes", governance=True)[0])
    program=require_academic_object(s, ctx, s.get(D.Program, body.program_id), "create", "Program"); row=D.ProgramOutcome(id=uid(),tenant_id=TENANT,program_id=program.id,code=body.code,description=body.description);s.add(row);s.commit();write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.outcome.program.create",f"program_outcome:{row.id}","","active",body.code);return {"id":row.id}
@router.post("/academics/outcomes/course")
def add_course_outcome(body:OutcomeIn,ctx=Depends(auth),s=Depends(db)):
    require(gate(s, ctx, "academics", "manage_outcomes", governance=True)[0])
    course=require_academic_object(s, ctx, s.get(D.Course, body.course_id), "create", "Course"); row=D.CourseOutcome(id=uid(),tenant_id=TENANT,course_id=course.id,code=body.code,description=body.description);s.add(row);s.commit();write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.outcome.course.create",f"course_outcome:{row.id}","","active",body.code);return {"id":row.id}
@router.post("/academics/outcomes/map")
def map_outcomes(body:dict,ctx=Depends(auth),s=Depends(db)):
    require(gate(s, ctx, "academics", "manage_outcomes", governance=True)[0])
    course_outcome=require_academic_object(s, ctx, s.get(D.CourseOutcome, body["course_outcome_id"]), "create", "Course outcome")
    program_outcome=require_academic_object(s, ctx, s.get(D.ProgramOutcome, body["program_outcome_id"]), "create", "Program outcome")
    row=D.OutcomeMapping(id=uid(),tenant_id=TENANT,course_outcome_id=course_outcome.id,program_outcome_id=program_outcome.id,weight=float(body.get("weight",1)));s.add(row);s.commit();write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.outcome.mapping.create",f"outcome_mapping:{row.id}","","active",f"{course_outcome.id}->{program_outcome.id}");return {"id":row.id}

@router.post("/academics/outcomes/assessment-map")
def map_assessment_outcome(body:dict,ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","manage_outcomes", governance=True)[0])
    assessment=require_tenant(s.get(D.Assessment,body.get("assessment_id")),ctx,"Assessment")
    outcome=require_tenant(s.get(D.CourseOutcome,body.get("course_outcome_id")),ctx,"Course outcome")
    weight=float(body.get("weight",1))
    if weight <= 0: raise HTTPException(422,"Weight must be positive")
    row=D.AssessmentOutcomeMapping(id=uid(),tenant_id=TENANT,assessment_id=assessment.id,course_outcome_id=outcome.id,weight=weight,target=float(body.get("target",60)));s.add(row);s.commit();return {"id":row.id}

@router.post("/academics/outcomes/targets")
def set_outcome_target(body:dict,ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","manage_outcomes", governance=True)[0])
    target=float(body.get("target",60)); threshold=float(body.get("threshold",50))
    if not 0 <= threshold <= target <= 100: raise HTTPException(422,"Targets must satisfy 0 <= threshold <= target <= 100")
    row=D.OutcomeAttainmentTarget(id=uid(),tenant_id=TENANT,outcome_type=body["outcome_type"],outcome_id=body["outcome_id"],aggregation_level=body.get("aggregation_level","course"),target=target,threshold=threshold,term=body.get("term",""));s.add(row);s.commit();return {"id":row.id,"target":row.target,"threshold":row.threshold}

class PlanIn(BaseModel):
    source_term:str
    target_term:str
    summary:str=""
    risks:list[str]=[]
    actions:list[str]=[]
    dependencies:list[str]=[]
    evidence_links:list[str]=[]
    quality_review_ids:list[str]=[]
    corrective_action_ids:list[str]=[]
    curriculum_revision_ids:list[str]=[]
    program_change_ids:list[str]=[]
    faculty_allocation_ids:list[str]=[]
    calendar_milestone_ids:list[str]=[]
    timetable_resource_ids:list[str]=[]
@router.post("/academics/next-semester-plans")
def create_next_plan(body:PlanIn,ctx=Depends(auth),s=Depends(db)):
    require(gate(s, ctx, "academics", "manage_planning", governance=True)[0])
    links={key:getattr(body,key) for key in ("quality_review_ids","corrective_action_ids","curriculum_revision_ids","program_change_ids","faculty_allocation_ids","calendar_milestone_ids","timetable_resource_ids")}
    row=D.NextSemesterPlan(id=uid(),tenant_id=TENANT,source_term=body.source_term,target_term=body.target_term,summary=body.summary,risks_json=json.dumps(body.risks),actions_json=json.dumps(body.actions),dependencies_json=json.dumps(body.dependencies),evidence_links_json=json.dumps({"evidence":body.evidence_links,"links":links}),created_by=ctx["sub"]);s.add(row);s.commit();write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"academic.plan.create",f"next_semester_plan:{row.id}","","DRAFT",body.summary);return {"id":row.id,"state":row.state}
@router.get("/academics/next-semester-plans")
def next_plans(ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","view", governance=True)[0]);return {"states":["DRAFT","SUBMITTED","REVIEWED","APPROVED","EXECUTING","COMPLETED"],"plans":[{"id":x.id,"source_term":x.source_term,"target_term":x.target_term,"summary":x.summary,"state":x.state,"risks":json.loads(x.risks_json or '[]'),"actions":json.loads(x.actions_json or '[]'),"dependencies":json.loads(x.dependencies_json or '[]'),"evidence_links":json.loads(x.evidence_links_json or '[]')} for x in s.query(D.NextSemesterPlan).filter(D.NextSemesterPlan.tenant_id == ctx["tenant_id"]).order_by(desc(D.NextSemesterPlan.created_at)).all()]}

@router.get("/academics/next-semester-plans/compare")
def compare_next_plans(source_term:str, target_term:str,ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","view", governance=True)[0])
    rows=s.query(D.NextSemesterPlan).filter(D.NextSemesterPlan.tenant_id==TENANT,D.NextSemesterPlan.source_term==source_term,D.NextSemesterPlan.target_term==target_term).all()
    return {"source_term":source_term,"target_term":target_term,"plans":[{"id":x.id,"state":x.state,"actions":json.loads(x.actions_json or '[]'),"dependencies":json.loads(x.dependencies_json or '[]'),"evidence_links":json.loads(x.evidence_links_json or '[]')} for x in rows],"summary":{"plans":len(rows),"approved":sum(1 for x in rows if x.state=="APPROVED"),"completed":sum(1 for x in rows if x.state=="COMPLETED")}}

@router.post("/academics/next-semester-plans/{plan_id}/transition")
def transition_next_plan(plan_id:str,body:CommitteeTransitionIn,ctx=Depends(auth),s=Depends(db)):
    require(gate(s,ctx,"academics","manage_planning", governance=True)[0]); row=require_tenant(s.get(D.NextSemesterPlan,plan_id),ctx,"Next-semester plan"); target=body.target_status.upper()
    allowed={"DRAFT":"SUBMITTED","SUBMITTED":"REVIEWED","REVIEWED":"APPROVED","APPROVED":"EXECUTING","EXECUTING":"COMPLETED"}
    if allowed.get(row.state)!=target: raise HTTPException(409,f"Transition {row.state} -> {target} is not allowed")
    if target=="APPROVED" and (not json.loads(row.evidence_links_json or "{}")): raise HTTPException(409,"Prior-semester evidence is required before approval")
    row.state=target; row.approved_by=ctx["sub"] if target=="APPROVED" else row.approved_by; row.updated_at=datetime.utcnow(); s.commit(); return {"id":row.id,"state":row.state}


# Curriculum ownership sits with the academic unit.  The Dean is the
# independent academic authority that reviews and decides proposals, rather
# than routinely originating the requests they must approve.
CURRICULUM_PROPOSERS = {10, 17}


def _curriculum_proposal_payload(s, proposal):
    result = _proposal_payload(s, proposal)
    course = s.get(D.Course, proposal.implementation_ref) if proposal.implementation_ref else None
    # Implementation readiness is derived from the records created after the
    # governed decision.  Do not present workflow guidance as if it were a
    # completed CO/PO or delivery configuration.
    if not course:
        result["implementation_status"] = {
            "course": {"complete": False, "detail": "Created only after approval"},
            "outcomes": {"complete": False, "detail": "Not available until a course record is created"},
            "delivery": {"complete": False, "detail": "Not available until a course record is created"},
        }
        return result
    outcomes = s.query(D.CourseOutcome).filter(
        D.CourseOutcome.tenant_id == course.tenant_id,
        D.CourseOutcome.course_id == course.id,
        D.CourseOutcome.active == True,
    ).all()
    outcome_ids = {row.id for row in outcomes}
    mapped_outcome_ids = {
        row.course_outcome_id for row in s.query(D.OutcomeMapping).filter(
            D.OutcomeMapping.tenant_id == course.tenant_id,
            D.OutcomeMapping.course_outcome_id.in_(outcome_ids) if outcome_ids else text("1=0"),
        ).all()
    }
    sections = s.query(D.Section).filter(
        D.Section.tenant_id == course.tenant_id, D.Section.course_id == course.id,
    ).all()
    section_ids = {row.id for row in sections}
    scheduled_section_ids = {
        row.section_id for row in s.query(D.TimetableEntry).filter(
            D.TimetableEntry.tenant_id == course.tenant_id,
            D.TimetableEntry.section_id.in_(section_ids) if section_ids else text("1=0"),
            D.TimetableEntry.status == "active",
        ).all()
    }
    assigned = sum(1 for row in sections if row.faculty_person_id)
    scheduled = sum(1 for row in sections if row.id in scheduled_section_ids)
    result["implementation_status"] = {
        "course": {"complete": True, "detail": f"{course.code} — {course.title} ({course.id})"},
        "outcomes": {
            "complete": bool(outcomes) and len(mapped_outcome_ids) == len(outcome_ids),
            "detail": f"{len(outcomes)} COs; {len(mapped_outcome_ids)}/{len(outcomes)} mapped to PO",
        },
        "delivery": {
            "complete": bool(sections) and assigned == len(sections) and scheduled == len(sections),
            "detail": f"{len(sections)} section(s); {assigned}/{len(sections)} faculty assigned; {scheduled}/{len(sections)} timetabled",
        },
    }
    return result


@router.get("/curriculum/proposals")
def curriculum_proposals(state: str = "", ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    query = s.query(D.AcademicProposal).filter(D.AcademicProposal.tenant_id == ctx["tenant_id"], D.AcademicProposal.proposal_type == "curriculum")
    if state:
        query = query.filter(D.AcademicProposal.state == state.upper())
    if ctx["office_n"] != 6:
        query = query.filter(D.AcademicProposal.scope_ref == (actor_department_id(s, ctx) or "__no_scope__"))
    allowed_departments = s.query(D.Department).filter(D.Department.tenant_id == ctx["tenant_id"])
    if ctx["office_n"] != 6:
        department_id = actor_department_id(s, ctx)
        allowed_departments = allowed_departments.filter(D.Department.id == (department_id or "__no_scope__"))
    available_programs = scoped_academic_query(s, D.Program, ctx).order_by(D.Program.name).all()
    return {"proposals": [_curriculum_proposal_payload(s, row) for row in query.order_by(desc(D.AcademicProposal.updated_at)).all()],
            "can_propose": ctx["office_n"] in CURRICULUM_PROPOSERS, "can_decide": ctx["office_n"] == 6,
            "proposal_departments": [{"id": row.id, "code": row.code, "name": row.name} for row in allowed_departments.order_by(D.Department.code).all()],
            "programs": [{"id": row.id, "code": row.code, "name": row.name} for row in available_programs]}


@router.get("/curriculum/proposals/{proposal_id}")
def curriculum_proposal_detail(proposal_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view", governance=True)[0])
    proposal = require_academic_object(s, ctx, s.get(D.AcademicProposal, proposal_id), "read", "Curriculum proposal")
    if proposal.proposal_type != "curriculum": raise HTTPException(404, "Curriculum proposal not found")
    return {"proposal": _curriculum_proposal_payload(s, proposal)}


@router.post("/curriculum/proposals")
def create_curriculum_proposal(body: CurriculumProposalIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    if ctx["office_n"] not in CURRICULUM_PROPOSERS:
        raise HTTPException(403, "Only an HOD or Academic Coordinator can propose curriculum changes")
    dept = require_academic_object(s, ctx, s.query(D.Department).filter(D.Department.tenant_id == ctx["tenant_id"], D.Department.code == body.dept_code.strip()).first(), "create", "Department")
    existing = require_academic_object(s, ctx, s.get(D.Course, body.course_id), "create", "Course") if body.course_id else None
    if existing and existing.dept_id != dept.id: raise HTTPException(403, "Course is outside the selected department scope")
    code = body.code.strip().upper()
    duplicate = s.query(D.Course).filter(D.Course.code == code).first()
    if duplicate and (not existing or duplicate.id != existing.id): raise HTTPException(409, "Course code already exists")
    payload = body.model_dump()
    payload["code"] = code; payload["dept_id"] = dept.id
    title = f"{'Revise' if existing else 'Add'} {code} — {body.title.strip()}"
    now = datetime.utcnow()
    proposal = D.AcademicProposal(id=uid(), tenant_id=TENANT, proposal_type="curriculum", title=title,
                                  scope_level="department", scope_ref=dept.id, school_id=dept.school_id, dept_id=dept.id, program_id=getattr(existing, "program_id", None), state="DRAFT", version_no=1, submitted_by=ctx["sub"], submitted_office_n=ctx["office_n"],
                                  assigned_to_office_n=6, due_at=now + timedelta(days=10), created_at=now, updated_at=now)
    s.add(proposal); s.flush()
    s.add(D.AcademicProposalVersion(id=uid(), tenant_id=TENANT, proposal_id=proposal.id, version_no=1,
                                    payload_json=json.dumps(payload), rationale=body.rationale.strip(), created_by=ctx["sub"]))
    _proposal_event(s, proposal, ctx, "", "DRAFT", body.rationale)
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic.curriculum.proposal.create", f"academic_proposal:{proposal.id}", "", "DRAFT", body.rationale, commit=False); s.commit()
    return {"proposal": _curriculum_proposal_payload(s, proposal)}


@router.post("/curriculum/proposals/{proposal_id}/submit")
def submit_curriculum_proposal(proposal_id: str, body: AcademicProposalTransitionIn, ctx=Depends(auth), s=Depends(db)):
    proposal = require_academic_object(s, ctx, s.get(D.AcademicProposal, proposal_id), "submit", "Curriculum proposal")
    if not proposal or proposal.proposal_type != "curriculum": raise HTTPException(404, "Curriculum proposal not found")
    if proposal.submitted_by != ctx["sub"] or proposal.state not in {"DRAFT", "RETURNED", "CLARIFICATION_REQUIRED"}: raise HTTPException(409, "Proposal cannot be submitted in its current state")
    if proposal.status_version != body.expected_status_version: raise HTTPException(409, "Proposal changed; reload before submitting")
    previous = proposal.state; proposal.state = "RESUBMITTED" if previous != "DRAFT" else "SUBMITTED"; proposal.status_version += 1; proposal.updated_at = datetime.utcnow()
    _proposal_event(s, proposal, ctx, previous, proposal.state, body.reason)
    dean = s.query(User).filter(User.office_n == 6).first()
    if dean: _proposal_notice(s, dean.id, "Curriculum decision required", proposal.title)
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic.curriculum.proposal.submit", f"academic_proposal:{proposal.id}", previous, proposal.state, body.reason, commit=False); s.commit()
    return {"proposal": _curriculum_proposal_payload(s, proposal)}


@router.post("/curriculum/proposals/{proposal_id}/decision/{decision}")
def decide_curriculum_proposal(proposal_id: str, decision: str, body: AcademicProposalTransitionIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "approve_proposal" if decision.lower() == "approve" else "reject_proposal")[0])
    proposal = require_academic_object(s, ctx, s.query(D.AcademicProposal).filter(D.AcademicProposal.id == proposal_id).with_for_update().first(), "approve", "Curriculum proposal")
    prevent_self_approval(proposal, ctx)
    if proposal.proposal_type != "curriculum": raise HTTPException(404, "Curriculum proposal not found")
    target = {"approve": "APPROVED", "reject": "REJECTED", "return": "RETURNED", "clarification": "CLARIFICATION_REQUIRED", "escalate": "ESCALATED"}.get(decision.lower())
    if not target or proposal.state not in {"SUBMITTED", "RESUBMITTED"}: raise HTTPException(409, "Invalid curriculum decision")
    validate_transition(s, proposal, target, body.expected_status_version, ctx, body.reason)
    if proposal.status_version != body.expected_status_version: raise HTTPException(409, "Proposal changed; reload before deciding")
    claim_proposal_transition(s, proposal, body.expected_status_version, {"SUBMITTED", "RESUBMITTED"})
    if target != "APPROVED" and not body.reason.strip(): raise HTTPException(422, "A decision reason is required")
    previous = proposal.state; proposal.state = target; proposal.status_version += 1; proposal.updated_at = datetime.utcnow()
    if target == "APPROVED":
        payload = json.loads(_proposal_version(s, proposal).payload_json)
        required_fields = ("dept_id", "code", "title", "credits", "semester")
        missing_fields = [field for field in required_fields if payload.get(field) in (None, "")]
        if missing_fields:
            s.rollback()
            raise HTTPException(422, f"Curriculum proposal is missing required fields: {', '.join(missing_fields)}")
        course = s.get(D.Course, payload.get("course_id")) if payload.get("course_id") else None
        if not course:
            course = D.Course(id=uid(), tenant_id=TENANT, dept_id=payload["dept_id"]); s.add(course)
        for key in ("code", "title", "credits", "semester", "regulation", "course_type", "category", "ltp", "prerequisite", "description"):
            setattr(course, key, payload.get(key, getattr(course, key, "")))
        course.status = "Active"; s.flush(); proposal.implementation_ref = course.id
    elif target == "ESCALATED": proposal.escalated_to_office_n = 4
    _proposal_event(s, proposal, ctx, previous, target, body.reason)
    submitter = s.get(User, proposal.submitted_by)
    if submitter: _proposal_notice(s, submitter.id, f"Curriculum proposal {target.lower().replace('_', ' ')}", proposal.title, "info" if target == "APPROVED" else "action")
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic.curriculum.proposal.decision", f"academic_proposal:{proposal.id}", previous, target, body.reason, commit=False); s.commit()
    return {"proposal": _curriculum_proposal_payload(s, proposal)}


@router.post("/academics/courses")
def create_course(body: CourseIn, ctx=Depends(auth), s=Depends(db)):
    raise HTTPException(410, "Curriculum changes must be submitted as governed proposals")
    dec, _ = gate(s, ctx, "academics", "create_course")
    require(dec)
    code = body.code.strip().upper()
    if not code or not body.title.strip() or body.credits < 1 or body.semester not in range(1, 9):
        raise HTTPException(400, "Provide a course code, title, valid credits, and semester (1–8).")
    if s.query(D.Course).filter(D.Course.code == code).first():
        raise HTTPException(400, "A course with this code already exists.")
    dept = s.query(D.Department).filter(D.Department.code == body.dept_code).first()
    if not dept:
        raise HTTPException(400, "Choose a valid department.")
    program = s.query(D.Program).filter(D.Program.dept_id == dept.id, D.Program.level == "UG").first()
    course = D.Course(id=uid(), tenant_id=TENANT, dept_id=dept.id, program_id=program.id if program else None,
                      code=code, title=body.title.strip(), credits=body.credits, semester=body.semester,
                      description=body.description.strip(), regulation=body.regulation.strip() or "R2023",
                      course_type=body.course_type, category=body.category.strip() or "Professional Core",
                      ltp=body.ltp.strip(), prerequisite=body.prerequisite.strip(), status="Active")
    s.add(course); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "course.create", f"course:{course.id}", "", "Active", f"Created {code} — {course.title}")
    return {"id": course.id, "decision": dec.as_dict()}


class CourseOfferingIn(BaseModel):
    course_id: str
    program_id: str
    academic_year: str
    term: str
    semester: int


class CourseOfferingStatusIn(BaseModel):
    status: str


def _course_offering_payload(s, row):
    course, program = s.get(D.Course, row.course_id), s.get(D.Program, row.program_id)
    hod = s.query(D.HODInput).filter_by(offering_id=row.id).first()
    sections = s.query(D.Section).filter_by(offering_id=row.id).all()
    section_ids = [x.id for x in sections]
    allocations = s.query(D.FacultyAllocation).filter(
        D.FacultyAllocation.section_id.in_(section_ids) if section_ids else text("1=0")
    ).all()
    section_capacity = sum(x.capacity or 0 for x in sections)
    faculty_complete = bool(hod and len([a for a in allocations if str(a.status).upper() in {"ASSIGNED", "CONFIRMED", "APPROVED"}]) >= hod.required_faculty_count)
    sections_defined = bool(hod and len(sections) >= hod.required_sections and section_capacity >= hod.expected_capacity)
    ready = bool(hod and hod.status == "Submitted" and sections_defined and faculty_complete)
    return {"id": row.id, "course_id": row.course_id, "course_code": course.code if course else "",
            "course_title": course.title if course else "", "program_id": row.program_id,
            "program": program.name if program else "", "program_code": program.code if program else "",
            "academic_year": row.academic_year, "term": row.term, "semester": row.semester,
            "course_start_date": row.course_start_date.isoformat() if row.course_start_date else "",
            "expected_completion_date": row.expected_completion_date.isoformat() if row.expected_completion_date else "",
            "lab_marks": row.lab_marks, "mid_marks": row.mid_marks, "semester_marks": row.semester_marks,
            "status": row.status, "created_by": row.created_by, "updated_by": row.updated_by,
            "created_at": row.created_at.isoformat() if row.created_at else "",
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
            "hod_input": {"id": hod.id, "required_faculty_count": hod.required_faculty_count, "required_sections": hod.required_sections, "expected_capacity": hod.expected_capacity, "delivery_type": hod.delivery_type, "remarks": hod.remarks, "status": hod.status} if hod else None,
            "faculty_allocations": [{"id": a.id, "faculty_id": a.faculty_person_id, "section_id": a.section_id, "status": a.status, "faculty": (s.get(D.StaffMember, a.faculty_person_id).name if s.get(D.StaffMember, a.faculty_person_id) else "")} for a in allocations],
            "sections": [{"id": x.id, "section": x.section_code, "faculty": s.get(D.StaffMember, x.faculty_person_id).name if x.faculty_person_id and s.get(D.StaffMember, x.faculty_person_id) else "—", "room": x.room, "schedule": x.schedule, "capacity": x.capacity, "enrolled": s.query(D.Enrollment).filter_by(section_id=x.id, status="enrolled").count(), "status": "Ready" if x.faculty_person_id else "Pending"} for x in sections],
            "section_readiness": {"required_sections": hod.required_sections if hod else 0, "created_sections": len(sections), "required_capacity": hod.expected_capacity if hod else 0, "total_capacity": section_capacity, "faculty_assigned": faculty_complete},
            "readiness": {"ready": ready, "hod_submitted": bool(hod and hod.status == "Submitted"), "faculty_complete": faculty_complete, "sections_defined": sections_defined}}


def _hod_department_ids(s, ctx):
    if ctx.get("office_n") != 10:
        return None
    person = s.query(Person).join(User, User.person_id == Person.id).filter(User.id == ctx.get("sub")).first()
    if not person:
        return set()
    return {d.id for d in s.query(D.Department).filter(D.Department.hod_person_id == person.id).all()}


def _offering_in_academic_scope(s, offering, ctx):
    allowed = _hod_department_ids(s, ctx)
    if allowed is None:
        return True
    program = s.get(D.Program, offering.program_id) if offering else None
    course = s.get(D.Course, offering.course_id) if offering else None
    return bool((program and program.dept_id in allowed) or (course and course.dept_id in allowed))


class HODInputIn(BaseModel):
    required_faculty_count: int = Field(ge=0)
    required_sections: int = Field(ge=0)
    expected_capacity: int = Field(ge=0)
    delivery_type: str = "theory"
    remarks: str = ""


class FacultyAllocationIn(BaseModel):
    faculty_id: str
    section_id: str = ""


@router.get("/academics/course-offerings/{offering_id}/hod-input")
def get_hod_input(offering_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0]); row = s.query(D.HODInput).filter_by(offering_id=offering_id).first()
    return {"hod_input": {"id": row.id, "required_faculty_count": row.required_faculty_count, "required_sections": row.required_sections, "expected_capacity": row.expected_capacity, "delivery_type": row.delivery_type, "remarks": row.remarks, "status": row.status} if row else None}


@router.put("/academics/course-offerings/{offering_id}/hod-input")
def save_hod_input(offering_id: str, body: HODInputIn, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] not in {10, 17}: raise HTTPException(403, "Only HOD or Academic Coordinator may maintain HOD input")
    dec, _ = gate(s, ctx, "academics", "edit"); require(dec); offering = s.query(D.CourseOffering).filter_by(id=offering_id).first()
    if not offering: raise HTTPException(404, "Course offering not found")
    row = s.query(D.HODInput).filter_by(offering_id=offering_id).first() or D.HODInput(id=uid(), tenant_id=TENANT, offering_id=offering_id, created_by=ctx["sub"])
    row.required_faculty_count, row.required_sections, row.expected_capacity, row.delivery_type, row.remarks = body.required_faculty_count, body.required_sections, body.expected_capacity, body.delivery_type, body.remarks.strip()
    row.updated_by, row.updated_at = ctx["sub"], datetime.utcnow(); s.add(row); s.commit(); return {"hod_input": {"id": row.id, "status": row.status}, "decision": dec.as_dict()}


@router.post("/academics/course-offerings/{offering_id}/hod-input/submit")
def submit_hod_input(offering_id: str, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] != 10: raise HTTPException(403, "HOD submission is restricted to the HOD office")
    dec, _ = gate(s, ctx, "academics", "edit"); require(dec); row = s.query(D.HODInput).filter_by(offering_id=offering_id).first()
    if not row: raise HTTPException(404, "Save HOD input before submitting")
    row.status, row.updated_by, row.updated_at = "Submitted", ctx["sub"], datetime.utcnow(); s.commit(); return {"status": row.status, "decision": dec.as_dict()}


@router.get("/academics/course-offerings/{offering_id}/faculty-allocations")
def list_faculty_allocations(offering_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0]); return {"allocations": _course_offering_payload(s, s.query(D.CourseOffering).get(offering_id))["faculty_allocations"]}


@router.post("/academics/course-offerings/{offering_id}/faculty-allocations")
def create_faculty_allocation(offering_id: str, body: FacultyAllocationIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "assign_faculty"); require(dec); offering = s.query(D.CourseOffering).filter_by(id=offering_id).first(); faculty = s.get(D.StaffMember, body.faculty_id)
    if not offering or not faculty: raise HTTPException(404, "Offering or faculty not found")
    if body.section_id and not s.query(D.Section).filter_by(id=body.section_id, offering_id=offering_id, course_id=offering.course_id).first(): raise HTTPException(400, "Section does not belong to this offering")
    existing = s.query(D.FacultyAllocation).filter(
        D.FacultyAllocation.section_id == body.section_id,
        D.FacultyAllocation.faculty_person_id == body.faculty_id,
        D.FacultyAllocation.status.in_(["PROPOSED", "APPROVED"]),
    ).first()
    if existing: raise HTTPException(409, "Faculty is already assigned to this section")
    row = D.FacultyAllocation(id=uid(), tenant_id=TENANT, section_id=body.section_id or None,
                              faculty_person_id=body.faculty_id, term=offering.term,
                              workload_units=1, status="PROPOSED", created_by=ctx["sub"])
    s.add(row); s.commit(); return {"id": row.id, "status": row.status, "decision": dec.as_dict()}


@router.get("/academics/course-offerings/{offering_id}/readiness")
def course_offering_readiness(offering_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0]); offering = s.query(D.CourseOffering).filter_by(id=offering_id).first()
    if not offering: raise HTTPException(404, "Course offering not found")
    return {"readiness": _course_offering_payload(s, offering)["readiness"]}


class CurriculumExecutionIssueIn(BaseModel):
    offering_id: str
    issue_type: str
    description: str = ""
    responsible_role: str = "Curriculum Officer"
    status: str = "Open"

class CurriculumExecutionUpdateIn(BaseModel):
    course_start_date: str | None = None
    expected_completion_date: str | None = None
    execution_duration_months: int | None = Field(default=None, ge=1, le=60)
    execution_status: str = ""
    execution_remarks: str = ""
    lab_marks: int | None = Field(default=None, ge=0)
    mid_marks: int | None = Field(default=None, ge=0)
    semester_marks: int | None = Field(default=None, ge=0)
    mid1_completion_percentage: int | None = Field(default=None, ge=0, le=100)
    mid2_remaining_syllabus_percentage: int | None = Field(default=None, ge=0, le=100)


def _execution_payload(s, offering):
    base = _course_offering_payload(s, offering)
    plans = s.query(D.TimetablePlanWorkflow).filter_by(offering_id=offering.id).all()
    timetable = "Ready" if any(p.status in {"Approved", "Published", "Closed"} for p in plans) else ("In Review" if plans else "Not Ready")
    issues = s.query(D.CurriculumExecutionIssue).filter_by(offering_id=offering.id).order_by(desc(D.CurriculumExecutionIssue.updated_at)).all()
    issue_payload = [{"id": i.id, "issue_type": i.issue_type, "description": i.description, "status": i.status,
                      "responsible_role": i.responsible_role, "created_by": i.created_by,
                      "created_at": i.created_at.isoformat() if i.created_at else "",
                      "updated_at": i.updated_at.isoformat() if i.updated_at else ""} for i in issues]
    readiness = base["readiness"]
    offering_section_ids = [x.id for x in s.query(D.Section.id).filter(D.Section.offering_id == offering.id).all()]
    sessions = s.query(D.ClassSession).filter(
        D.ClassSession.section_id.in_(offering_section_ids) if offering_section_ids else text("1=0")
    ).all()
    completed_sessions = sum(x.status in {"Completed", "Complete"} for x in sessions)
    progress = round(completed_sessions * 100 / len(sessions)) if sessions else 0
    open_issue = any(i.status != "Resolved" for i in issues)
    if offering.actual_completion_date:
        derived = "Completed"
    elif open_issue:
        derived = "Gap / Issue"
    elif offering.expected_completion_date and offering.expected_completion_date < date.today():
        derived = "Delayed"
    elif offering.execution_status in {"In Progress", "On Track"}:
        derived = offering.execution_status
    else:
        derived = "Not Started"
    allocations = base.get("faculty_allocations", [])
    faculty_names = ", ".join(dict.fromkeys(a["faculty"] for a in allocations if a.get("faculty")))
    return {**base, "curriculum_status": getattr(s.get(D.Course, offering.course_id), "status", "Unknown"),
            "department_id": s.get(D.Program, offering.program_id).dept_id if s.get(D.Program, offering.program_id) else "",
            "department": s.get(D.Department, s.get(D.Program, offering.program_id).dept_id).name if s.get(D.Program, offering.program_id) else "",
            "student_year": (int(offering.semester) + 1) // 2 if offering.semester else None,
            "faculty": faculty_names or "—",
            "faculty_readiness": "Ready" if readiness["faculty_complete"] else "Not Ready",
            "timetable_readiness": timetable, "execution_issues": issue_payload,
            "execution_status": derived, "course_start_date": offering.course_start_date.isoformat() if offering.course_start_date else "",
            "expected_completion_date": offering.expected_completion_date.isoformat() if offering.expected_completion_date else "",
            "execution_duration_months": offering.execution_duration_months,
            "lab_marks": offering.lab_marks,
            "mid_marks": offering.mid_marks,
            "semester_marks": offering.semester_marks,
            "mid1_completion_percentage": offering.mid1_completion_percentage,
            "mid2_remaining_syllabus_percentage": offering.mid2_remaining_syllabus_percentage,
            "actual_completion_date": offering.actual_completion_date.isoformat() if offering.actual_completion_date else "", "progress": progress,
            "execution_remarks": offering.execution_remarks or "", "class_sessions": [{"id": x.id, "status": x.status, "date": x.session_date.isoformat() if x.session_date else ""} for x in sessions]}


@router.get("/academics/curriculum-execution")
def curriculum_execution(academic_year: str = "", student_year: int | None = None, program_id: str = "", department_id: str = "", term: str = "", faculty_id: str = "", execution_status: str = "", ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    rows = s.query(D.CourseOffering).filter_by(tenant_id=TENANT).order_by(desc(D.CourseOffering.updated_at)).all()
    items = [_execution_payload(s, row) for row in rows if _offering_in_academic_scope(s, row, ctx)]
    items = [x for x in items if (not academic_year or x.get("academic_year") == academic_year) and (not student_year or x.get("student_year") == student_year) and (not program_id or x.get("program_id") == program_id) and (not department_id or x.get("department_id") == department_id) and (not term or x.get("term") == term) and (not faculty_id or any(str(a.get("faculty_id")) == str(faculty_id) for a in x.get("faculty_allocations", []))) and (not execution_status or x.get("execution_status") == execution_status)]
    return {"items": items, "can_manage": can(s, ctx, "academics", "edit"), "summary": {k: sum(1 for x in items if x["execution_status"] == v) for k,v in {"total":"__all__","not_started":"Not Started","in_progress":"In Progress","on_track":"On Track","delayed":"Delayed","completed":"Completed","gap":"Gap / Issue"}.items()}}

@router.put("/academics/curriculum-execution/{offering_id}")
def update_curriculum_execution(offering_id: str, body: CurriculumExecutionUpdateIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "edit"); require(dec)
    row = s.query(D.CourseOffering).filter_by(id=offering_id, tenant_id=TENANT).first()
    if not row or not _offering_in_academic_scope(s, row, ctx): raise HTTPException(404, "Course offering not found")
    try:
        start = date.fromisoformat(body.course_start_date) if body.course_start_date else row.course_start_date
        expected = date.fromisoformat(body.expected_completion_date) if body.expected_completion_date else row.expected_completion_date
    except ValueError:
        raise HTTPException(400, "Use valid ISO dates (YYYY-MM-DD)")
    if start and expected and expected < start: raise HTTPException(400, "Expected completion cannot be before the course start date")
    if body.course_start_date is not None and body.expected_completion_date is None:
        expected = row.expected_completion_date
    if body.expected_completion_date is not None and body.course_start_date is None:
        start = row.course_start_date
    if start and body.execution_duration_months:
        month = start.month - 1 + body.execution_duration_months
        year, month = start.year + month // 12, month % 12 + 1
        import calendar
        calculated = date(year, month, min(start.day, calendar.monthrange(year, month)[1]))
        if expected and expected != calculated: raise HTTPException(400, "Expected date conflicts with the configured duration")
        expected = calculated
    if body.course_start_date is not None or body.expected_completion_date is not None or body.execution_duration_months is not None:
        row.course_start_date, row.execution_duration_months, row.expected_completion_date = start, body.execution_duration_months, expected
    row.lab_marks, row.mid_marks, row.semester_marks = body.lab_marks, body.mid_marks, body.semester_marks
    row.mid1_completion_percentage = body.mid1_completion_percentage
    row.mid2_remaining_syllabus_percentage = body.mid2_remaining_syllabus_percentage
    if body.execution_remarks is not None: row.execution_remarks = body.execution_remarks.strip()
    if body.execution_status in {"Not Started", "In Progress", "On Track"}: row.execution_status = body.execution_status
    if body.execution_status == "Completed": row.actual_completion_date, row.execution_completed_by, row.execution_completed_at, row.execution_status = date.today(), ctx["sub"], datetime.utcnow(), "Completed"
    row.updated_by, row.updated_at = ctx["sub"], datetime.utcnow(); s.commit()
    return {"item": _execution_payload(s, row), "decision": dec.as_dict()}


@router.post("/academics/curriculum-execution/issues")
def create_curriculum_execution_issue(body: CurriculumExecutionIssueIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "edit"); require(dec)
    if body.status not in {"Open", "Under Review", "Resolved"}: raise HTTPException(400, "Invalid issue status")
    offering = s.query(D.CourseOffering).filter_by(id=body.offering_id, tenant_id=TENANT).first()
    if not offering: raise HTTPException(404, "Course offering not found")
    now, who = datetime.utcnow(), actor_name(s, ctx)
    row = D.CurriculumExecutionIssue(id=uid(), tenant_id=TENANT, offering_id=offering.id,
        issue_type=body.issue_type.strip(), description=body.description.strip(), status=body.status,
        responsible_role=body.responsible_role.strip() or "Curriculum Officer", created_by=who, updated_by=who,
        created_at=now, updated_at=now)
    s.add(row); s.commit()
    write_audit(s, ctx["sub"], who, ctx["office_n"], "curriculum_execution.issue", f"issue:{row.id}", "", row.status, row.issue_type)
    return {"issue": _execution_payload(s, offering)["execution_issues"][0], "decision": dec.as_dict()}


@router.put("/academics/curriculum-execution/issues/{issue_id}")
def update_curriculum_execution_issue(issue_id: str, body: CurriculumExecutionIssueIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "edit"); require(dec)
    if body.status not in {"Open", "Under Review", "Resolved"}: raise HTTPException(400, "Invalid issue status")
    row = s.query(D.CurriculumExecutionIssue).filter_by(id=issue_id, tenant_id=TENANT).first()
    if not row: raise HTTPException(404, "Issue not found")
    previous = row.status; row.issue_type, row.description, row.status, row.responsible_role = body.issue_type.strip(), body.description.strip(), body.status, body.responsible_role.strip() or row.responsible_role
    row.updated_by, row.updated_at = actor_name(s, ctx), datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], row.updated_by, ctx["office_n"], "curriculum_execution.issue", f"issue:{row.id}", previous, row.status, row.issue_type)
    return {"status": row.status, "decision": dec.as_dict()}


@router.get("/academics/course-offerings")
def list_course_offerings(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    rows = s.query(D.CourseOffering).filter_by(tenant_id=TENANT).order_by(D.CourseOffering.academic_year.desc(), D.CourseOffering.semester, D.CourseOffering.id).all()
    rows = [row for row in rows if _offering_in_academic_scope(s, row, ctx)]
    return {"offerings": [_course_offering_payload(s, row) for row in rows],
            "can_create": can(s, ctx, "academics", "create_course"), "can_edit": can(s, ctx, "academics", "edit"),
            "can_approve": False, "can_publish": False}


@router.get("/academics/course-offerings/{offering_id}")
def get_course_offering(offering_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    row = s.query(D.CourseOffering).filter_by(id=offering_id, tenant_id=TENANT).first()
    if not row: raise HTTPException(404, "Course offering not found")
    if not _offering_in_academic_scope(s, row, ctx): raise HTTPException(404, "Course offering not found")
    return {"offering": _course_offering_payload(s, row)}


@router.post("/academics/course-offerings")
def create_course_offering(body: CourseOfferingIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "create_course")
    require(dec)
    course, program = s.get(D.Course, body.course_id), s.get(D.Program, body.program_id)
    if not course or not program or course.program_id not in (None, program.id): raise HTTPException(400, "Choose a valid course and program")
    if body.semester != course.semester or body.semester not in range(1, 9): raise HTTPException(400, "Semester must match the catalog course")
    if not body.academic_year.strip() or not body.term.strip(): raise HTTPException(400, "Academic year and term are required")
    if s.query(D.CourseOffering).filter_by(tenant_id=TENANT, course_id=course.id, program_id=program.id, academic_year=body.academic_year.strip(), term=body.term.strip()).first(): raise HTTPException(409, "This course is already offered for the selected term")
    now, who = datetime.utcnow(), actor_name(s, ctx)
    row = D.CourseOffering(id=uid(), tenant_id=TENANT, course_id=course.id, program_id=program.id, academic_year=body.academic_year.strip(), term=body.term.strip(), semester=body.semester, status="Draft", created_by=who, updated_by=who, created_at=now, updated_at=now)
    s.add(row); s.commit(); write_audit(s, ctx["sub"], who, ctx["office_n"], "course_offering.create", f"course_offering:{row.id}", "", row.status, course.code)
    return {"offering": _course_offering_payload(s, row), "decision": dec.as_dict()}


@router.put("/academics/course-offerings/{offering_id}")
def update_course_offering(offering_id: str, body: CourseOfferingIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "edit")
    require(dec)
    row = s.query(D.CourseOffering).filter_by(id=offering_id, tenant_id=TENANT).first()
    if not row: raise HTTPException(404, "Course offering not found")
    if row.status not in {"Draft", "HOD Input Pending", "Ready"}: raise HTTPException(409, "Only editable offerings can be updated")
    course, program = s.get(D.Course, body.course_id), s.get(D.Program, body.program_id)
    if not course or not program or body.semester != course.semester: raise HTTPException(400, "Choose a valid course, program, and catalog semester")
    previous = row.status
    row.course_id, row.program_id, row.academic_year, row.term, row.semester = course.id, program.id, body.academic_year.strip(), body.term.strip(), body.semester
    row.updated_by, row.updated_at = actor_name(s, ctx), datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], row.updated_by, ctx["office_n"], "course_offering.update", f"course_offering:{row.id}", previous, row.status, course.code)
    return {"offering": _course_offering_payload(s, row), "decision": dec.as_dict()}


@router.post("/academics/course-offerings/{offering_id}/status")
def change_course_offering_status(offering_id: str, body: CourseOfferingStatusIn, ctx=Depends(auth), s=Depends(db)):
    allowed = {"Draft", "HOD Input Pending", "Ready", "Approved", "Published", "Closed"}
    if body.status not in allowed: raise HTTPException(400, "Invalid offering status")
    if body.status in {"Approved", "Published", "Closed"}: raise HTTPException(403, "This status requires an approval/publishing capability not granted to Office 17")
    dec, _ = gate(s, ctx, "academics", "edit"); require(dec)
    row = s.query(D.CourseOffering).filter_by(id=offering_id, tenant_id=TENANT).first()
    if not row: raise HTTPException(404, "Course offering not found")
    if row.status == "Closed": raise HTTPException(409, "Closed offerings cannot change status")
    previous = row.status; row.status, row.updated_by, row.updated_at = body.status, actor_name(s, ctx), datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], row.updated_by, ctx["office_n"], "course_offering.status", f"course_offering:{row.id}", previous, row.status, "Offering status changed")
    return {"offering": _course_offering_payload(s, row), "decision": dec.as_dict()}


@router.get("/academics/sections")
def list_sections(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    course_map = {c.id: (c.code, c.title, c.semester) for c in s.query(D.Course).all()}
    program_map = {p.id: p for p in s.query(D.Program).all()}
    offering_map = {o.id: o for o in s.query(D.CourseOffering).all()}
    department_map = {d.id: d for d in s.query(D.Department).all()}
    fac_map = {f.id: f.name for f in s.query(D.StaffMember).all()}
    rows = s.query(D.Section).limit(200).all()
    rows = [r for r in rows if not r.offering_id or _offering_in_academic_scope(s, s.get(D.CourseOffering, r.offering_id), ctx)]
    course_map = {c.id: (c.code, c.title, c.semester) for c in scoped_academic_query(s, D.Course, ctx).all()}
    fac_map = {f.id: f.name for f in s.query(D.StaffMember).filter(D.StaffMember.tenant_id == ctx["tenant_id"]).all()}
    section_query = scoped_academic_query(s, D.Section, ctx)
    rows = section_query.limit(200).all()
    out = []
    for r in rows:
        cc, ct, semester = course_map.get(r.course_id, ("", "", None))
        offering = offering_map.get(r.offering_id)
        program = program_map.get(offering.program_id) if offering else None
        department = department_map.get(program.dept_id) if program else department_map.get(r.dept_id)
        enrolled = s.query(D.Enrollment).filter(D.Enrollment.section_id == r.id,
                                                D.Enrollment.status == "enrolled").count()
        out.append({"id": r.id, "offering_id": r.offering_id, "course_code": cc, "course_title": ct, "semester": semester,
                    "program_id": program.id if program else "", "program_code": program.code if program else "",
                    "program": program.name if program else "", "department_id": department.id if department else "",
                    "department": department.name if department else "",
                    "section": r.section_code, "term": r.term,
                    "faculty": fac_map.get(r.faculty_person_id, "—"),
                    "room": r.room, "schedule": r.schedule,
                    "enrolled": enrolled, "capacity": r.capacity})
    return {"sections": out,
            "can_create": can(s, ctx, "academics", "create_section"),
            "can_assign": can(s, ctx, "academics", "assign_faculty")}


class SectionIn(BaseModel):
    course_id: str
    offering_id: str = ""
    section_code: str = "A"
    faculty_id: str = ""
    room: str = ""
    schedule: str = "Mon/Wed 10:00"


@router.post("/academics/sections")
def create_section(body: SectionIn, ctx=Depends(auth), s=Depends(db)):
    dec, verb = gate(s, ctx, "academics", "create_section")
    require(dec)
    c = s.query(D.Course).get(body.course_id)
    if not c:
        raise HTTPException(400, "Unknown course")
    offering = s.query(D.CourseOffering).filter_by(id=body.offering_id, tenant_id=TENANT).first() if body.offering_id else None
    if body.offering_id and (not offering or offering.course_id != c.id): raise HTTPException(400, "Section course does not match the selected offering")
    if offering and not _offering_in_academic_scope(s, offering, ctx): raise HTTPException(404, "Course offering not found")
    if offering:
        existing = s.query(D.Section).filter_by(offering_id=offering.id, section_code=body.section_code).first()
        if existing: raise HTTPException(409, "This section already exists for the offering")
        if not _course_offering_payload(s, offering)["readiness"]["ready"]: raise HTTPException(409, "Complete submitted HOD input, capacity, and faculty allocation before creating sections")
    c = require_academic_object(s, ctx, s.get(D.Course, body.course_id), "create", "Course")
    sid = uid()
    s.add(D.Section(id=sid, tenant_id=TENANT, course_id=c.id, offering_id=offering.id if offering else None, dept_id=c.dept_id,
                    term=offering.term if offering else "2025-Odd", section_code=body.section_code,
                    faculty_person_id=body.faculty_id or None, room=body.room,
                    schedule=body.schedule, capacity=60, scope_ref=c.dept_id))
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "section.create",
                f"section:{sid}", "", "open", f"Section {c.code}-{body.section_code}")
    return {"id": sid, "decision": dec.as_dict()}


@router.get("/academics/section/{section_id}/timetable")
def section_timetable(section_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    section = require_academic_object(s, ctx, _section_or_404(s, section_id), "read", "Section")
    rows = (s.query(D.TimetableEntry)
            .filter(D.TimetableEntry.section_id == section.id)
            .order_by(D.TimetableEntry.day_of_week, D.TimetableEntry.start_time).all())
    return {
        "entries": [{
            "id": row.id,
            "day_of_week": row.day_of_week,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "room": row.room,
            "building": row.building,
            "status": row.status,
            "effective_from": row.effective_from.isoformat() if row.effective_from else "",
            "effective_to": row.effective_to.isoformat() if row.effective_to else "",
            "slot": _format_time_label(row.start_time, row.end_time),
        } for row in rows],
        "can_manage": can(s, ctx, "academics", "manage_timetable"),
    }


def _clock_minutes(value: str) -> int:
    try:
        hours, minutes = (int(part) for part in str(value or '').split(':', 1))
        return hours * 60 + minutes
    except (TypeError, ValueError):
        return -1


@router.get("/academics/conflicts")
def academic_conflicts(academic_year: str = "", student_year: int | None = None, program_id: str = "", department_id: str = "", conflict_type: str = "", severity: str = "", status: str = "", resolved: str = "", ctx=Depends(auth), s=Depends(db)):
    """Compute current timetable conflicts from persisted active entries.

    This is deliberately read-only: re-planning remains subject to the existing
    timetable mutation capability and section ownership checks.
    """
    require(gate(s, ctx, "academics", "view")[0])
    sections = {row.id: row for row in s.query(D.Section).all()}
    courses = {row.id: row for row in s.query(D.Course).all()}
    entries = [row for row in s.query(D.TimetableEntry).filter(D.TimetableEntry.status == "active").all()
               if row.section_id in sections]
    conflicts = []
    for index, left in enumerate(entries):
        left_section = sections[left.section_id]
        left_course = courses.get(left_section.course_id)
        left_start, left_end = _clock_minutes(left.start_time), _clock_minutes(left.end_time)
        if left_start < 0 or left_end <= left_start:
            continue
        for right in entries[index + 1:]:
            if left.day_of_week != right.day_of_week:
                continue
            right_start, right_end = _clock_minutes(right.start_time), _clock_minutes(right.end_time)
            if right_start < 0 or right_end <= right_start or left_start >= right_end or right_start >= left_end:
                continue
            right_section = sections[right.section_id]
            right_course = courses.get(right_section.course_id)
            kinds = []
            if left_section.faculty_person_id and left_section.faculty_person_id == right_section.faculty_person_id:
                kinds.append("faculty_overlap")
            if left.room and right.room and left.room.strip().lower() == right.room.strip().lower():
                kinds.append("lab_conflict" if "lab" in left.room.lower() else "room_conflict")
            if left_section.dept_id == right_section.dept_id and left_section.term == right_section.term:
                kinds.append("student_cohort_overlap")
            kinds = list(dict.fromkeys(kinds))
            for kind in kinds:
                    key = f"{kind}:{min(left.id, right.id)}:{max(left.id, right.id)}"
                    severity_value = "Critical" if kind == "student_cohort_overlap" else ("High" if kind in {"faculty_overlap", "lab_conflict"} else "Medium")
                    saved = s.query(D.TimetableConflict).filter(D.TimetableConflict.conflict_key == key).first()
                    if not saved:
                        saved = D.TimetableConflict(id=uid(), tenant_id=TENANT, conflict_key=key, conflict_type=kind, severity=severity_value, left_entry_id=left.id, right_entry_id=right.id, detected_at=datetime.utcnow(), updated_at=datetime.utcnow())
                        s.add(saved)
                    elif saved.status != "Resolved":
                        saved.severity = severity_value
                    conflicts.append({
                    "id": saved.id, "conflict_key": key, "type": kind,
                    "severity": saved.severity, "status": saved.status, "detected_at": (saved.detected_at or datetime.utcnow()).isoformat(),
                    "day_of_week": left.day_of_week, "start_time": max(left.start_time, right.start_time),
                    "end_time": min(left.end_time, right.end_time),
                    "left": {"entry_id": left.id, "section_id": left.section_id,
                              "section": left_section.section_code, "course": left_course.code if left_course else ""},
                    "right": {"entry_id": right.id, "section_id": right.section_id,
                               "section": right_section.section_code, "course": right_course.code if right_course else ""},
                    "resolution_note": saved.resolution_note, "resolved_by": saved.resolved_by, "resolved_at": saved.resolved_at.isoformat() if saved.resolved_at else "",
                    "academic_year": getattr(left_section, "academic_year", "") or left_section.term, "student_year": getattr(left_section, "year", None),
                    "program_id": getattr(left_section, "program_id", "") or (s.get(D.CourseOffering, left_section.offering_id).program_id if left_section.offering_id and s.get(D.CourseOffering, left_section.offering_id) else ""), "department_id": left_section.dept_id,
                    "department_name": s.get(D.Department, left_section.dept_id).name if s.get(D.Department, left_section.dept_id) else "",
                    "program_name": s.get(D.Program, getattr(left_section, "program_id", "") or (s.get(D.CourseOffering, left_section.offering_id).program_id if left_section.offering_id and s.get(D.CourseOffering, left_section.offering_id) else "")).name if s.get(D.Program, getattr(left_section, "program_id", "") or (s.get(D.CourseOffering, left_section.offering_id).program_id if left_section.offering_id and s.get(D.CourseOffering, left_section.offering_id) else "")) else "",
                    "left": {"entry_id": left.id, "section_id": left.section_id, "section": left_section.section_code, "course": left_course.code if left_course else "", "course_name": left_course.title if left_course else "", "faculty": left_section.faculty_person_id or "", "room": left.room},
                    "right": {"entry_id": right.id, "section_id": right.section_id, "section": right_section.section_code, "course": right_course.code if right_course else "", "course_name": right_course.title if right_course else "", "faculty": right_section.faculty_person_id or "", "room": right.room},
                    })
    s.commit()
    if ctx.get("office_n") == 10:
        allowed = set(_hod_department_ids(s, ctx))
        conflicts = [x for x in conflicts if x["department_id"] in allowed or x["right"]["section_id"] in {z.section_id for z in entries if z.section_id and sections[z.section_id].dept_id in allowed}]
    if academic_year: conflicts = [x for x in conflicts if x["academic_year"] == academic_year]
    if student_year is not None: conflicts = [x for x in conflicts if x["student_year"] == student_year]
    if program_id: conflicts = [x for x in conflicts if x["program_id"] == program_id]
    if department_id: conflicts = [x for x in conflicts if x["department_id"] == department_id]
    if conflict_type: conflicts = [x for x in conflicts if x["type"] == conflict_type]
    if severity: conflicts = [x for x in conflicts if x["severity"] == severity]
    if status: conflicts = [x for x in conflicts if x["status"] == status]
    if resolved in {"true", "1", "yes"}: conflicts = [x for x in conflicts if x["status"] == "Resolved"]
    elif resolved in {"false", "0", "no"}: conflicts = [x for x in conflicts if x["status"] != "Resolved"]
    summary = {"total_active": sum(x["status"] != "Resolved" for x in conflicts), "critical": sum(x["severity"] == "Critical" for x in conflicts), "high": sum(x["severity"] == "High" for x in conflicts), "faculty": sum(x["type"] == "faculty_overlap" for x in conflicts), "room": sum(x["type"] == "room_conflict" for x in conflicts), "student": sum(x["type"] == "student_cohort_overlap" for x in conflicts), "lab": sum(x["type"] == "lab_conflict" for x in conflicts), "resolved": sum(x["status"] == "Resolved" for x in conflicts)}
    return {"conflicts": conflicts, "summary": summary, "can_manage": can(s, ctx, "academics", "manage_timetable")}


class ConflictResolveIn(BaseModel):
    note: str = ""

@router.post("/academics/conflicts/{conflict_id}/resolve")
def resolve_academic_conflict(conflict_id: str, body: ConflictResolveIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "manage_timetable"); require(dec)
    row = s.get(D.TimetableConflict, conflict_id)
    if not row: raise HTTPException(404, "Conflict not found")
    if ctx.get("office_n") == 10:
        allowed = set(_hod_department_ids(s, ctx)); left = s.get(D.TimetableEntry, row.left_entry_id); right = s.get(D.TimetableEntry, row.right_entry_id)
        if not left or not right or s.get(D.Section, left.section_id).dept_id not in allowed:
            raise HTTPException(403, "You are not authorized to resolve this conflict")
    if not body.note.strip(): raise HTTPException(400, "Resolution note is required")
    row.status, row.resolution_note, row.resolved_by, row.resolved_at, row.updated_at = "Resolved", body.note.strip(), ctx["sub"], datetime.utcnow(), datetime.utcnow()
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academics.conflict.resolve", f"conflict:{row.id}", "Active", "Resolved", body.note.strip())
    return {"status": row.status, "decision": dec.as_dict()}


class TimetableEntryIn(BaseModel):
    day_of_week: int
    start_time: str
    end_time: str
    room: str = ""
    building: str = ""
    effective_from: str = ""
    effective_to: str = ""


def _validate_timetable_slot(s, section, body, exclude_id=""):
    """Validate time ranges and prevent section, room, or faculty clashes."""
    from datetime import datetime as _dt
    try:
        start = _dt.strptime(body.start_time, "%H:%M").time()
        end = _dt.strptime(body.end_time, "%H:%M").time()
    except ValueError:
        raise HTTPException(422, "Start and end time must use HH:MM format")
    if end <= start:
        raise HTTPException(422, "End time must be later than start time")
    rows = s.query(D.TimetableEntry, D.Section).join(D.Section, D.Section.id == D.TimetableEntry.section_id).filter(
        D.TimetableEntry.tenant_id == section.tenant_id,
        D.TimetableEntry.status == "active",
        D.TimetableEntry.day_of_week == int(body.day_of_week),
    ).all()
    room = (body.room or section.room or "").strip().lower()
    for row, other in rows:
        if row.id == exclude_id or row.start_time >= body.end_time or row.end_time <= body.start_time:
            continue
        same_section = other.id == section.id
        same_room = room and (row.room or "").strip().lower() == room
        same_faculty = section.faculty_person_id and other.faculty_person_id == section.faculty_person_id
        if same_section or same_room or same_faculty:
            kind = "section" if same_section else ("room" if same_room else "faculty")
            raise HTTPException(409, f"Timetable conflict: overlapping {kind} slot")


@router.post("/academics/section/{section_id}/timetable")
def create_timetable_entry(section_id: str, body: TimetableEntryIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "manage_timetable")
    require(dec)
    section = require_academic_object(s, ctx, _section_or_404(s, section_id), "create", "Section")
    if not _can_manage_section_for_timetable(s, ctx, section):
        raise HTTPException(403, "You are not authorized to manage the timetable for this section")
    _validate_timetable_slot(s, section, body)
    who = actor_name(s, ctx)
    row = D.TimetableEntry(
        id=uid(), tenant_id=TENANT, section_id=section.id,
        day_of_week=max(0, min(6, int(body.day_of_week))),
        start_time=body.start_time, end_time=body.end_time,
        room=body.room or section.room, building=body.building,
        effective_from=date.fromisoformat(body.effective_from) if body.effective_from else None,
        effective_to=date.fromisoformat(body.effective_to) if body.effective_to else None,
        status="active", created_by=who, updated_by=who,
    )
    s.add(row)
    s.commit()
    write_audit(s, ctx["sub"], who, ctx["office_n"], "timetable.create",
                f"timetable:{row.id}", "", "active",
                f"Created timetable entry for section {section.section_code}")
    return {"id": row.id, "decision": dec.as_dict()}


@router.put("/academics/timetable/{entry_id}")
def update_timetable_entry(entry_id: str, body: TimetableEntryIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "manage_timetable")
    require(dec)
    row = s.query(D.TimetableEntry).filter(D.TimetableEntry.tenant_id == ctx["tenant_id"], D.TimetableEntry.id == entry_id).first()
    if not row:
        raise HTTPException(404, "Timetable entry not found")
    section = require_academic_object(s, ctx, _section_or_404(s, row.section_id), "edit", "Section")
    if not _can_manage_section_for_timetable(s, ctx, section):
        raise HTTPException(403, "You are not authorized to manage the timetable for this section")
    _validate_timetable_slot(s, section, body, row.id)
    prev_state = row.status
    row.day_of_week = max(0, min(6, int(body.day_of_week)))
    row.start_time = body.start_time
    row.end_time = body.end_time
    row.room = body.room or section.room
    row.building = body.building
    row.effective_from = date.fromisoformat(body.effective_from) if body.effective_from else None
    row.effective_to = date.fromisoformat(body.effective_to) if body.effective_to else None
    row.updated_by = actor_name(s, ctx)
    row.updated_at = datetime.utcnow()
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "timetable.update",
                f"timetable:{row.id}", prev_state, row.status,
                f"Updated timetable entry for section {section.section_code}")
    return {"id": row.id, "decision": dec.as_dict()}


@router.post("/academics/timetable/{entry_id}/deactivate")
def deactivate_timetable_entry(entry_id: str, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "manage_timetable")
    require(dec)
    row = s.query(D.TimetableEntry).filter(D.TimetableEntry.tenant_id == ctx["tenant_id"], D.TimetableEntry.id == entry_id).first()
    if not row:
        raise HTTPException(404, "Timetable entry not found")
    section = require_academic_object(s, ctx, _section_or_404(s, row.section_id), "edit", "Section")
    if not _can_manage_section_for_timetable(s, ctx, section):
        raise HTTPException(403, "You are not authorized to manage the timetable for this section")
    prev_state = row.status
    row.status = "inactive"
    row.updated_by = actor_name(s, ctx)
    row.updated_at = datetime.utcnow()
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "timetable.update",
                f"timetable:{row.id}", prev_state, row.status,
                f"Deactivated timetable entry for section {section.section_code}")
    return {"status": row.status, "decision": dec.as_dict()}


def _timetable_plan_payload(row):
    return {"id": row.id, "offering_id": row.offering_id, "section_id": row.section_id, "timetable_entry_id": row.timetable_entry_id, "status": row.status, "last_action": row.last_action, "reason": row.reason, "submitted_by": row.submitted_by, "updated_by": row.updated_by, "updated_at": row.updated_at.isoformat() if row.updated_at else ""}


@router.get("/academics/timetable-plans")
def list_timetable_plans(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    return {"plans": [_timetable_plan_payload(x) for x in s.query(D.TimetablePlanWorkflow).filter_by(tenant_id=TENANT).order_by(D.TimetablePlanWorkflow.updated_at.desc()).all()]}


@router.post("/academics/timetable-plans/submit")
def submit_timetable_plan(body: dict, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "manage_timetable"); require(dec)
    entry = s.get(D.TimetableEntry, body.get("timetable_entry_id")); section = s.get(D.Section, body.get("section_id"))
    if not entry or not section or entry.section_id != section.id or not section.faculty_person_id or not entry.room or not entry.day_of_week >= 0 or not entry.start_time or not entry.end_time: raise HTTPException(400, "A complete section timetable with assigned faculty is required")
    offering_id = body.get("offering_id") or section.offering_id
    if not offering_id: raise HTTPException(400, "Timetable plan must belong to a course offering")
    # Existing conflict engine is authoritative; reject any active overlap involving this entry.
    others = s.query(D.TimetableEntry).filter(D.TimetableEntry.status == "active", D.TimetableEntry.day_of_week == entry.day_of_week, D.TimetableEntry.id != entry.id).all()
    for other in others:
        if other.day_of_week == entry.day_of_week and _clock_minutes(entry.start_time) < _clock_minutes(other.end_time) and _clock_minutes(other.start_time) < _clock_minutes(entry.end_time):
            other_section = s.get(D.Section, other.section_id)
            if (entry.room and entry.room == other.room) or (section.faculty_person_id and other_section and section.faculty_person_id == other_section.faculty_person_id): raise HTTPException(409, "Unresolved timetable conflict exists")
    row = s.query(D.TimetablePlanWorkflow).filter_by(timetable_entry_id=entry.id).first() or D.TimetablePlanWorkflow(id=uid(), tenant_id=TENANT, offering_id=offering_id, section_id=section.id, timetable_entry_id=entry.id, created_at=datetime.utcnow())
    row.status, row.last_action, row.reason, row.submitted_by, row.updated_by, row.updated_at = "HOD Review", "Submitted for HOD review", "", ctx["sub"], ctx["sub"], datetime.utcnow(); s.add(row); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "timetable_plan.submit", f"timetable_plan:{row.id}", "Draft", row.status, "Submitted for HOD review")
    return {"plan": _timetable_plan_payload(row), "decision": dec.as_dict()}


@router.post("/academics/timetable-plans/{plan_id}/hod-decision")
def timetable_hod_decision(plan_id: str, body: dict, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] != 10: raise HTTPException(403, "Only the HOD office may review this stage")
    dec, _ = gate(s, ctx, "approvals", "approve" if body.get("action") == "approve" else "reject"); require(dec)
    row = s.get(D.TimetablePlanWorkflow, plan_id)
    if not row or row.status != "HOD Review": raise HTTPException(409, "Plan is not awaiting HOD review")
    action = body.get("action"); row.status = "VP Review" if action == "approve" else "HOD Returned"
    row.last_action, row.reason, row.updated_by, row.updated_at = f"HOD {action}", body.get("reason", "").strip(), ctx["sub"], datetime.utcnow(); s.commit(); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "timetable_plan.hod_decision", f"timetable_plan:{row.id}", "HOD Review", row.status, row.reason)
    return {"plan": _timetable_plan_payload(row), "decision": dec.as_dict()}


@router.post("/academics/timetable-plans/{plan_id}/vp-decision")
def timetable_vp_decision(plan_id: str, body: dict, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] != 5: raise HTTPException(403, "Only the Vice Principal office may review this stage")
    dec, _ = gate(s, ctx, "approvals", "approve" if body.get("action") == "approve" else "reject"); require(dec)
    row = s.get(D.TimetablePlanWorkflow, plan_id)
    if not row or row.status != "VP Review": raise HTTPException(409, "Plan is not awaiting VP review")
    action = body.get("action"); row.status = "Approved" if action == "approve" else "VP Returned"; row.last_action, row.reason, row.updated_by, row.updated_at = f"VP {action}", body.get("reason", "").strip(), ctx["sub"], datetime.utcnow(); s.commit(); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "timetable_plan.vp_decision", f"timetable_plan:{row.id}", "VP Review", row.status, row.reason)
    return {"plan": _timetable_plan_payload(row), "decision": dec.as_dict()}


@router.post("/academics/timetable-plans/{plan_id}/publish")
def publish_timetable_plan(plan_id: str, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] != 5: raise HTTPException(403, "Only the Vice Principal office may publish a timetable")
    dec, _ = gate(s, ctx, "approvals", "approve"); require(dec)
    row = s.get(D.TimetablePlanWorkflow, plan_id)
    if not row or row.status != "Approved": raise HTTPException(409, "Only approved plans can be published")
    row.status, row.last_action, row.updated_by, row.updated_at = "Published", "Timetable published", ctx["sub"], datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "timetable_plan.publish", f"timetable_plan:{row.id}", "Approved", "Published", "Timetable published")
    return {"plan": _timetable_plan_payload(row), "decision": dec.as_dict()}


@router.post("/academics/timetable-plans/{plan_id}/close")
def close_timetable_plan(plan_id: str, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] != 5: raise HTTPException(403, "Only the Vice Principal office may close a timetable")
    dec, _ = gate(s, ctx, "approvals", "approve"); require(dec)
    row = s.get(D.TimetablePlanWorkflow, plan_id)
    if not row or row.status != "Published": raise HTTPException(409, "Only published plans can be closed")
    row.status, row.last_action, row.updated_by, row.updated_at = "Closed", "Timetable closed", ctx["sub"], datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "timetable_plan.close", f"timetable_plan:{row.id}", "Published", "Closed", "Timetable closed")
    return {"plan": _timetable_plan_payload(row), "decision": dec.as_dict()}


def _session_payload(x):
    start = getattr(x, "start_time", None)
    end = getattr(x, "end_time", None)
    scheduled_start = getattr(x, "scheduled_start", None)
    scheduled_end = getattr(x, "scheduled_end", None)
    return {
        "id": x.id,
        "timetable_plan_id": getattr(x, "timetable_plan_id", None),
        "timetable_entry_id": getattr(x, "timetable_entry_id", None),
        "offering_id": getattr(x, "offering_id", None),
        "section_id": x.section_id,
        "faculty_id": x.faculty_id,
        "room": x.room or "",
        "session_date": x.session_date.isoformat() if x.session_date else "",
        "start_time": start or (scheduled_start.isoformat() if scheduled_start else ""),
        "end_time": end or (scheduled_end.isoformat() if scheduled_end else ""),
        "scheduled_start": scheduled_start.isoformat() if scheduled_start else None,
        "scheduled_end": scheduled_end.isoformat() if scheduled_end else None,
        "status": x.status,
        "created_by": getattr(x, "created_by", ""),
        "updated_at": x.updated_at.isoformat() if x.updated_at else "",
    }


@router.get("/academics/class-sessions")
def list_class_sessions(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0]); return {"sessions": [_session_payload(x) for x in s.query(D.ClassSession).filter_by(tenant_id=TENANT).order_by(D.ClassSession.session_date.desc()).all()]}


@router.get("/academics/class-sessions/{session_id}")
def get_class_session(session_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0]); x = s.query(D.ClassSession).get(session_id)
    if not x: raise HTTPException(404, "Class session not found")
    return {"session": _session_payload(x)}


@router.post("/academics/class-sessions/generate")
def generate_class_sessions(body: dict, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "manage_timetable"); require(dec)
    plan = s.query(D.TimetablePlanWorkflow).filter_by(id=body.get("timetable_plan_id"), status="Published").first()
    if not plan: raise HTTPException(409, "Only published timetable plans can generate class sessions")
    entry, section = s.get(D.TimetableEntry, plan.timetable_entry_id), s.get(D.Section, plan.section_id); d = date.fromisoformat(body.get("session_date", ""))
    if not entry or not section: raise HTTPException(404, "Timetable section not found")
    existing = s.query(D.ClassSession).filter_by(timetable_entry_id=entry.id, session_date=d).first()
    if existing: return {"session": _session_payload(existing), "decision": dec.as_dict()}
    x = D.ClassSession(id=uid(), tenant_id=TENANT, timetable_plan_id=plan.id, timetable_entry_id=entry.id, offering_id=plan.offering_id, section_id=section.id, faculty_id=section.faculty_person_id, room=entry.room, session_date=d, start_time=entry.start_time, end_time=entry.end_time, status="Planned", created_by=ctx["sub"], updated_by=ctx["sub"]); s.add(x); s.commit(); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "class_session.generate", f"class_session:{x.id}", "", x.status, "Generated from published timetable"); return {"session": _session_payload(x), "decision": dec.as_dict()}


@router.post("/academics/class-sessions/{session_id}/transition")
def transition_class_session(session_id: str, body: dict, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "manage_timetable"); require(dec); x = s.query(D.ClassSession).get(session_id)
    if not x: raise HTTPException(404, "Class session not found")
    allowed = {"Planned": {"Open", "Cancelled"}, "Open": {"In Progress", "Cancelled"}, "In Progress": {"Completed", "Cancelled"}, "Completed": set(), "Cancelled": set()}
    if body.get("status") not in allowed.get(x.status, set()): raise HTTPException(409, "Invalid class session transition")
    previous=x.status; x.status=body["status"]; x.updated_by=ctx["sub"]; x.updated_at=datetime.utcnow(); s.commit(); write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"class_session.status",f"class_session:{x.id}",previous,x.status,"Class session status changed"); return {"session": _session_payload(x), "decision": dec.as_dict()}


@router.get("/portal/faculty/class-sessions")
def faculty_class_sessions(ctx=Depends(auth), s=Depends(db)):
    staff = s.query(D.StaffMember).filter_by(user_id=ctx["sub"]).first()
    if not staff: raise HTTPException(403, "Faculty profile not found")
    rows = s.query(D.ClassSession).filter_by(tenant_id=TENANT, faculty_id=staff.id).order_by(D.ClassSession.session_date, D.ClassSession.start_time).all()
    return {"sessions": [_session_payload(x) for x in rows]}


@router.post("/portal/faculty/class-sessions/{session_id}/check-in")
def faculty_check_in_session(session_id: str, ctx=Depends(auth), s=Depends(db)):
    staff = s.query(D.StaffMember).filter_by(user_id=ctx["sub"]).first(); x = s.query(D.ClassSession).get(session_id)
    if not staff or not x or x.faculty_id != staff.id: raise HTTPException(403, "This class session is not assigned to you")
    if x.status != "Open": raise HTTPException(409, "Only open sessions can be checked in")
    if s.query(D.ClassSessionCheckIn).filter_by(session_id=x.id).first(): raise HTTPException(409, "Session is already checked in")
    s.add(D.ClassSessionCheckIn(id=uid(), tenant_id=TENANT, session_id=x.id, faculty_id=staff.id, created_by=ctx["sub"])); x.status="In Progress"; x.updated_by=ctx["sub"]; x.updated_at=datetime.utcnow(); s.commit(); write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"class_session.check_in",f"class_session:{x.id}","Open","In Progress","Faculty checked in"); return {"session": _session_payload(x)}


@router.post("/portal/faculty/class-sessions/{session_id}/complete")
def faculty_complete_session(session_id: str, ctx=Depends(auth), s=Depends(db)):
    staff = s.query(D.StaffMember).filter_by(user_id=ctx["sub"]).first(); x = s.query(D.ClassSession).get(session_id)
    if not staff or not x or x.faculty_id != staff.id: raise HTTPException(403, "This class session is not assigned to you")
    if x.status != "In Progress": raise HTTPException(409, "Only in-progress sessions can be completed")
    x.status="Completed"; x.updated_by=ctx["sub"]; x.updated_at=datetime.utcnow(); s.commit(); write_audit(s,ctx["sub"],actor_name(s,ctx),ctx["office_n"],"class_session.complete",f"class_session:{x.id}","In Progress","Completed","Faculty completed class session"); return {"session": _session_payload(x)}


@router.get("/academics/section/{section_id}/assignments")
def section_assignments(section_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    require_academic_object(s, ctx, _section_or_404(s, section_id), "read", "Section")
    rows = (s.query(D.Assignment)
            .filter(D.Assignment.tenant_id == ctx["tenant_id"], D.Assignment.section_id == section_id)
            .order_by(desc(D.Assignment.due_at), desc(D.Assignment.assigned_at)).all())
    return {"assignments": [{
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "assigned_at": row.assigned_at.isoformat() if row.assigned_at else "",
        "due_at": row.due_at.isoformat() if row.due_at else "",
    } for row in rows]}


class AssignmentIn(BaseModel):
    title: str
    description: str = ""
    due_at: str = ""
    status: str = "published"
    reference_url: str = ""


@router.post("/academics/section/{section_id}/assignments")
def create_assignment(section_id: str, body: AssignmentIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "create_task")
    require(dec)
    section = require_academic_object(s, ctx, _section_or_404(s, section_id), "create", "Section")
    if not _can_manage_section_for_tasks(s, ctx, section):
        raise HTTPException(403, "You cannot create tasks for this section")
    who = actor_name(s, ctx)
    row = D.Assignment(
        id=uid(), tenant_id=TENANT, section_id=section.id,
        title=body.title.strip(), description=body.description.strip(),
        assigned_at=datetime.utcnow(),
        due_at=datetime.fromisoformat(body.due_at) if body.due_at else None,
        status=body.status or "published", reference_url=body.reference_url.strip(),
        created_by=who, updated_by=who,
    )
    s.add(row)
    s.commit()
    write_audit(s, ctx["sub"], who, ctx["office_n"], "assignment.create",
                f"assignment:{row.id}", "", row.status,
                f"Created task '{row.title}' for section {section.section_code}")
    return {"id": row.id, "decision": dec.as_dict()}


@router.put("/academics/assignments/{assignment_id}")
def update_assignment(assignment_id: str, body: AssignmentIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "edit_task")
    require(dec)
    row = s.query(D.Assignment).filter(D.Assignment.tenant_id == ctx["tenant_id"], D.Assignment.id == assignment_id).first()
    if not row:
        raise HTTPException(404, "Assignment not found")
    section = require_academic_object(s, ctx, _section_or_404(s, row.section_id), "edit", "Section")
    if not _can_manage_section_for_tasks(s, ctx, section):
        raise HTTPException(403, "You cannot update tasks for this section")
    prev_state = row.status
    row.title = body.title.strip()
    row.description = body.description.strip()
    row.due_at = datetime.fromisoformat(body.due_at) if body.due_at else None
    row.status = body.status or row.status
    row.reference_url = body.reference_url.strip()
    row.updated_by = actor_name(s, ctx)
    row.updated_at = datetime.utcnow()
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "assignment.update",
                f"assignment:{row.id}", prev_state, row.status,
                f"Updated task '{row.title}'")
    return {"id": row.id, "decision": dec.as_dict()}


class AnnouncementIn(BaseModel):
    title: str
    body: str
    audience: str = "department"
    department_id: str | None = None
    program_id: str | None = None
    section_id: str | None = None
    student_id: str | None = None
    expires_at: str = ""


def _announcement_payload(s, row):
    department = s.get(D.Department, row.department_id) if row.department_id else None
    program = s.get(D.Program, row.program_id) if row.program_id else None
    section = s.get(D.Section, row.section_id) if row.section_id else None
    return {"id": row.id, "title": row.title, "body": row.body, "audience": row.audience,
            "department": department.name if department else "", "program": program.name if program else "",
            "section": section.section_code if section else "", "status": row.status,
            "created_by": row.created_by, "owner_office_n": row.owner_office_n,
            "published_at": row.published_at.isoformat() if row.published_at else "",
            "expires_at": row.expires_at.isoformat() if row.expires_at else "",
            "created_at": row.created_at.isoformat() if row.created_at else "",
            "updated_at": row.updated_at.isoformat() if row.updated_at else ""}


@router.get("/academics/announcements")
def list_academic_announcements(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    rows = s.query(D.Announcement).filter_by(tenant_id=TENANT).order_by(desc(D.Announcement.created_at)).all()
    return {"announcements": [_announcement_payload(s, row) for row in rows],
            "can_publish": can(s, ctx, "academics", "publish_announcement")}


@router.post("/academics/announcements")
def create_announcement(body: AnnouncementIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "publish_announcement")
    require(dec)
    who = actor_name(s, ctx)
    audience = (body.audience or "department").strip().lower()
    row = D.Announcement(
        id=uid(), tenant_id=TENANT, title=body.title.strip(), body=body.body.strip(),
        audience=audience, campus="", department_id=body.department_id, program_id=body.program_id,
        section_id=body.section_id, student_id=body.student_id, published_at=datetime.utcnow(),
        expires_at=datetime.fromisoformat(body.expires_at) if body.expires_at else None,
        status="published", created_by=who, owner_office_n=ctx["office_n"],
    )
    s.add(row)
    s.commit()
    write_audit(s, ctx["sub"], who, ctx["office_n"], "announcement.publish",
                f"announcement:{row.id}", "", row.status,
                f"Published announcement '{row.title}'")
    return {"id": row.id, "decision": dec.as_dict()}


# --------------------------------------------------------------------------- #
#  ATTENDANCE
# --------------------------------------------------------------------------- #
@router.get("/attendance/sections")
def attendance_sections(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "attendance", "view")[0])
    course_map = {c.id: (c.code, c.title) for c in scoped_academic_query(s, D.Course, ctx).all()}
    rows = scoped_academic_query(s, D.Section, ctx).limit(100).all()
    out = []
    for r in rows:
        cc, ct = course_map.get(r.course_id, ("", ""))
        total = s.query(D.AttendanceRecord).filter(D.AttendanceRecord.section_id == r.id).count()
        present = s.query(D.AttendanceRecord).filter(D.AttendanceRecord.section_id == r.id,
                                                     D.AttendanceRecord.present == True).count()
        pct = round(100 * present / total) if total else None
        out.append({"id": r.id, "course_code": cc, "course_title": ct,
                    "section": r.section_code, "schedule": r.schedule,
                    "records": total, "attendance_pct": pct})
    return {"sections": out, "can_mark": can(s, ctx, "attendance", "mark")}


@router.get("/attendance/roster/{section_id}")
def attendance_roster(section_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "attendance", "view")[0])
    require_academic_object(s, ctx, _section_or_404(s, section_id), "read", "Section")
    enr = s.query(D.Enrollment).filter(D.Enrollment.tenant_id == ctx["tenant_id"], D.Enrollment.section_id == section_id,
                                       D.Enrollment.status == "enrolled").all()
    stu_map = {st.id: st for st in s.query(D.Student).all()}
    out = []
    for e in enr:
        st = stu_map.get(e.student_id)
        if not st:
            continue
        total = s.query(D.AttendanceRecord).filter(D.AttendanceRecord.section_id == section_id,
                                                   D.AttendanceRecord.student_id == st.id).count()
        present = s.query(D.AttendanceRecord).filter(D.AttendanceRecord.section_id == section_id,
                                                     D.AttendanceRecord.student_id == st.id,
                                                     D.AttendanceRecord.present == True).count()
        out.append({"student_id": st.id, "roll_no": st.roll_no, "name": st.name,
                    "present": present, "total": total,
                    "pct": round(100 * present / total) if total else None})
    return {"roster": out, "can_mark": can(s, ctx, "attendance", "mark")}


class MarkAttendanceIn(BaseModel):
    section_id: str
    session_id: str = ""
    class_session_id: str
    present_ids: list[str] = []
    absent_ids: list[str] = []
    statuses: dict[str, str] = {}
    on_date: str = ""
@router.post("/attendance/mark")
def mark_attendance(body: MarkAttendanceIn, ctx=Depends(auth), s=Depends(db)):
    dec, verb = gate(s, ctx, "attendance", "mark")
    require(dec)
    section = require_academic_object(s, ctx, _section_or_404(s, body.section_id), "edit", "Section")
    enrolled_ids = {row.student_id for row in s.query(D.Enrollment).filter(D.Enrollment.tenant_id == ctx["tenant_id"], D.Enrollment.section_id == section.id, D.Enrollment.status == "enrolled").all()}
    if set(body.present_ids).union(body.absent_ids) - enrolled_ids:
        raise HTTPException(403, "Attendance includes a student outside this section")
    d = date.fromisoformat(body.on_date) if body.on_date else date.today()
    session = s.query(D.ClassSession).get(body.session_id) if body.session_id else None
    if body.session_id and (not session or session.section_id != body.section_id or session.status in {"Cancelled", "Completed"} or session.status != "In Progress"): raise HTTPException(409, "Attendance requires a valid in-progress class session for this section")
    if session:
        staff = s.query(D.StaffMember).filter_by(user_id=ctx["sub"]).first()
        if not staff or session.faculty_id != staff.id: raise HTTPException(403, "Only the assigned faculty may mark this session attendance")
    staff = _faculty_or_403(s, ctx)
    session = _session_or_404(s, body.class_session_id)
    if session.section_id != body.section_id:
        raise HTTPException(422, "Class session does not belong to this section")
    if session.faculty_id != staff.id or not faculty_owns_section(s, staff.id, body.section_id, session.session_date):
        raise HTTPException(403, "You are not assigned to this class session")
    if not session.checked_in_at:
        raise HTTPException(409, "Check in to this class session before marking attendance")
    if session.status == "attendance_finalized":
        raise HTTPException(409, "Attendance is finalized; use the correction workflow when it is available")
    if session.status in {"cancelled", "completed"}:
        raise HTTPException(409, "Attendance cannot be recorded for this session")
    d = date.fromisoformat(body.on_date) if body.on_date else session.session_date
    if d != session.session_date:
        raise HTTPException(422, "Attendance date must match the selected class session")
    if not _checkin_window_open(session, datetime.utcnow()):
        raise HTTPException(422, "Attendance marking is outside the allowed session window")
    who = actor_name(s, ctx)
    roster_ids = {row.student_id for row in s.query(D.Enrollment).filter(D.Enrollment.section_id == body.section_id, D.Enrollment.status == "enrolled").all()}
    raw_statuses = dict(body.statuses)
    raw_statuses.update({student_id: "present" for student_id in body.present_ids})
    raw_statuses.update({student_id: "absent" for student_id in body.absent_ids})
    allowed_statuses = {"present", "absent", "late", "excused"}
    if not raw_statuses or not set(raw_statuses).issubset(roster_ids):
        raise HTTPException(422, "Attendance may only be recorded for active students in this section")
    if any(status.lower() not in allowed_statuses for status in raw_statuses.values()):
        raise HTTPException(422, "Attendance status must be Present, Absent, Late or Excused")

    def upsert(student_id: str, status: str):
        row = (
            s.query(D.AttendanceRecord)
            .filter(D.AttendanceRecord.class_session_id == session.id,
                    D.AttendanceRecord.student_id == student_id)
            .first()
        )
        if row and row.finalized_at:
            raise HTTPException(409, "Attendance is finalized; use the correction workflow when it is available")
        if row is None:
            row = D.AttendanceRecord(
                id=uid(),
                tenant_id=TENANT,
                section_id=body.section_id,
                session_id=body.session_id or None,
                student_id=student_id,
                on_date=d,
                class_session_id=session.id,
            )
            s.add(row)
        normalized = status.lower()
        row.present = normalized in {"present", "late", "excused"}
        row.status = normalized
        row.note = ""
        row.marked_by = who
        row.version_no = (row.version_no or 0) + 1 if row.id else 1
        row.updated_at = datetime.utcnow()

    for sid, status in raw_statuses.items():
        upsert(sid, status)
    s.commit()
    n = len(raw_statuses)
    write_audit(s, ctx["sub"], who, ctx["office_n"], "attendance.mark",
                f"section:{body.section_id}", "", "recorded",
                f"Marked {n} students on {d.isoformat()}")
    return {"marked": n, "decision": dec.as_dict()}
# --------------------------------------------------------------------------- #
#  EXAMINATIONS: marks entry + result publication (SoD-separated)
# --------------------------------------------------------------------------- #
def _academic_year_for_datetime(dt_value):
    anchor = dt_value.date() if isinstance(dt_value, datetime) else dt_value
    anchor = anchor or date.today()
    start_year = anchor.year if anchor.month >= 6 else anchor.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _section_semester(s, section):
    course = s.query(D.Course).get(section.course_id) if section and section.course_id else None
    return course.semester if course else None


def _can_view_exam_section(s, ctx, section):
    if ctx["office_n"] in {4, 5, 6, 16}:
        return True
    staff = _staff_profile(s, ctx)
    if ctx["office_n"] in {10, 17}:
        return bool(staff and staff.dept_id == section.dept_id)
    if ctx["office_n"] in {11, 12, 13, 14}:
        return bool(staff and section.faculty_person_id == staff.id)
    return False


def _can_manage_section_for_exam_timetable(s, ctx, section):
    if ctx["office_n"] in {6, 16}:
        return True
    staff = _staff_profile(s, ctx)
    return bool(ctx["office_n"] in {10, 17} and staff and staff.dept_id == section.dept_id)


def _exam_scoped_sections(s, ctx):
    rows = s.query(D.Section).all()
    return [row for row in rows if _can_view_exam_section(s, ctx, row)]


def _assessment_pct(score: float | None, max_marks: float | None):
    if max_marks in (None, 0):
        return None
    return round((float(score or 0) / float(max_marks)) * 100, 1)


def _weighted_mark_average(mark_pairs):
    usable = [
        (assessment, mark, _assessment_pct(mark.score, assessment.max_marks))
        for assessment, mark in mark_pairs
    ]
    usable = [(assessment, mark, pct) for assessment, mark, pct in usable if pct is not None]
    if not usable:
        return None
    total_weight = sum(float(assessment.weight or 0) for assessment, _, _ in usable)
    if total_weight > 0:
        score = sum(pct * float(assessment.weight or 0) for assessment, _, pct in usable) / total_weight
    else:
        score = sum(pct for _, _, pct in usable) / len(usable)
    return round(score, 2)


def _grade_for_percentage(pct: float | None):
    if pct is None:
        return {"grade": "", "grade_point": None, "outcome": "result_pending"}
    if pct >= 90:
        return {"grade": "O", "grade_point": 10.0, "outcome": "passed"}
    if pct >= 80:
        return {"grade": "A+", "grade_point": 9.0, "outcome": "passed"}
    if pct >= 70:
        return {"grade": "A", "grade_point": 8.0, "outcome": "passed"}
    if pct >= 60:
        return {"grade": "B+", "grade_point": 7.0, "outcome": "passed"}
    if pct >= 55:
        return {"grade": "B", "grade_point": 6.0, "outcome": "passed"}
    if pct >= 50:
        return {"grade": "C", "grade_point": 5.0, "outcome": "passed"}
    return {"grade": "F", "grade_point": 0.0, "outcome": "failed"}


def _recompute_student_cgpa(s, student_id: str):
    rows = (
        s.query(D.StudentSubjectResult)
        .filter(D.StudentSubjectResult.student_id == student_id)
        .order_by(
            D.StudentSubjectResult.subject_code,
            D.StudentSubjectResult.attempt,
            D.StudentSubjectResult.published_at,
            D.StudentSubjectResult.updated_at,
        )
        .all()
    )
    latest = {}
    for row in rows:
        latest[row.subject_code] = row
    credit_rows = [row for row in latest.values() if (row.credits or 0) > 0 and row.grade_point is not None]
    student = s.query(D.Student).get(student_id)
    if not student or not credit_rows:
        return
    total_credits = sum(float(row.credits or 0) for row in credit_rows)
    if total_credits <= 0:
        return
    total_points = sum(float(row.grade_point or 0) * float(row.credits or 0) for row in credit_rows)
    student.cgpa = round(total_points / total_credits, 2)


def _sync_assessment_from_schedule(assessment, body, actor, section):
    if not assessment:
        return
    assessment.section_id = section.id
    assessment.scheduled_at = datetime.fromisoformat(body.start_at) if body.start_at else None
    assessment.end_at = datetime.fromisoformat(body.end_at) if body.end_at else None
    assessment.academic_year = (body.academic_year or assessment.academic_year or _academic_year_for_datetime(assessment.scheduled_at)).strip()
    assessment.updated_by = actor
    assessment.updated_at = datetime.utcnow()
    if body.status == "cancelled":
        assessment.status = "cancelled"
    elif body.status == "rescheduled":
        assessment.status = "rescheduled"


def _write_schedule_history(s, schedule, actor, change_type, previous_state, note=""):
    history = D.ExamScheduleHistory(
        id=uid(),
        tenant_id=TENANT,
        schedule_id=schedule.id,
        assessment_id=schedule.assessment_id,
        change_type=change_type,
        previous_start_at=previous_state.get("start_at"),
        previous_end_at=previous_state.get("end_at"),
        previous_venue=previous_state.get("venue", ""),
        previous_status=previous_state.get("status", ""),
        new_start_at=schedule.start_at,
        new_end_at=schedule.end_at,
        new_venue=schedule.venue or "",
        new_status=schedule.status or "",
        note=note or schedule.note or "",
        created_by=actor,
        created_at=datetime.utcnow(),
    )
    s.add(history)


def _publish_section_subject_results(s, section, result_sheet, actor):
    enrollments = (
        s.query(D.Enrollment)
        .filter(D.Enrollment.section_id == section.id, D.Enrollment.status == "enrolled")
        .all()
    )
    if not enrollments:
        return 0

    assessments = (
        s.query(D.Assessment)
        .filter(
            D.Assessment.section_id == section.id,
            D.Assessment.published == True,
            D.Assessment.status != "draft",
            D.Assessment.status != "cancelled",
        )
        .order_by(D.Assessment.scheduled_at, D.Assessment.id)
        .all()
    )
    assessment_ids = [row.id for row in assessments]
    if not assessment_ids:
        return 0

    marks = (
        s.query(D.Mark)
        .filter(
            D.Mark.assessment_id.in_(assessment_ids),
            D.Mark.status == "published",
            D.Mark.is_valid == True,
        )
        .all()
    )
    marks_by_student = {}
    marks_by_assessment = {row.id: row for row in assessments}
    for mark in marks:
        assessment = marks_by_assessment.get(mark.assessment_id)
        if not assessment:
            continue
        marks_by_student.setdefault(mark.student_id, []).append((assessment, mark))

    course = s.query(D.Course).get(section.course_id) if section.course_id else None
    published = 0
    now = datetime.utcnow()
    academic_year = (result_sheet.academic_year or _academic_year_for_datetime(now)).strip()
    semester = result_sheet.semester or (course.semester if course else None)

    for enrollment in enrollments:
        mark_pairs = marks_by_student.get(enrollment.student_id, [])
        if not mark_pairs:
            continue
        percentage = _weighted_mark_average(mark_pairs)
        grade_meta = _grade_for_percentage(percentage)
        total_score = round(sum(float(mark.score or 0) for _, mark in mark_pairs), 1)
        max_score = round(sum(float(assessment.max_marks or 0) for assessment, _ in mark_pairs), 1)
        previous_attempts = [
            row.attempt or 0
            for row in s.query(D.StudentSubjectResult)
            .filter(
                D.StudentSubjectResult.student_id == enrollment.student_id,
                D.StudentSubjectResult.subject_code == (course.code if course else section.id),
                D.StudentSubjectResult.result_sheet_id != result_sheet.id,
            )
            .all()
        ]
        result_id = f"ssr_{result_sheet.id}_{enrollment.student_id}"
        row = s.query(D.StudentSubjectResult).get(result_id)
        if row is None:
            row = D.StudentSubjectResult(
                id=result_id,
                tenant_id=TENANT,
                student_id=enrollment.student_id,
                attempt=(max(previous_attempts) if previous_attempts else 0) + 1,
            )
            s.add(row)
        row.academic_year = academic_year
        row.semester = semester
        row.subject_code = course.code if course else section.id
        row.subject_title = course.title if course else f"Section {section.section_code}"
        row.outcome = grade_meta["outcome"]
        row.published_at = now
        row.source = "examination"
        row.course_id = course.id if course else None
        row.section_id = section.id
        row.result_sheet_id = result_sheet.id
        row.credits = course.credits if course else 0
        row.grade = grade_meta["grade"]
        row.grade_point = grade_meta["grade_point"]
        row.percentage = percentage
        row.total_score = total_score
        row.max_score = max_score
        row.updated_at = now
        _recompute_student_cgpa(s, enrollment.student_id)
        published += 1
    return published


@router.get("/exams/sections")
def exam_sections(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "examinations", "view")[0])
    course_map = {c.id: (c.code, c.title) for c in s.query(D.Course).all()}
    rows = _exam_scoped_sections(s, ctx)
    out = []
    for r in rows:
        cc, ct = course_map.get(r.course_id, ("", ""))
        asmts = s.query(D.Assessment).filter(D.Assessment.section_id == r.id).count()
        rs = (s.query(D.ResultSheet)
              .filter(D.ResultSheet.section_id == r.id)
              .order_by(desc(D.ResultSheet.published_at), desc(D.ResultSheet.updated_at))
              .first())
        out.append({"id": r.id, "course_code": cc, "course_title": ct,
                    "section": r.section_code, "assessments": asmts,
                    "result_status": rs.status if rs else "none"})
    return {"sections": out,
            "can_enter_marks": can(s, ctx, "examinations", "enter_marks"),
            "can_publish": can(s, ctx, "examinations", "publish_result"),
            "can_publish_marks": can(s, ctx, "examinations", "publish_marks"),
            "can_manage_timetable": can(s, ctx, "examinations", "manage_timetable")}


@router.get("/exams/assessments/{section_id}")
def exam_assessments(section_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "examinations", "view")[0])
    section = require_academic_object(s, ctx, _section_or_404(s, section_id), "read", "Section")
    if not _can_view_exam_section(s, ctx, section):
        raise HTTPException(403, "You cannot view examinations for this section")
    schedule_by_assessment = {}
    for row in (s.query(D.ExamScheduleEntry)
                .filter(D.ExamScheduleEntry.section_id == section_id, D.ExamScheduleEntry.is_active == True)
                .order_by(desc(D.ExamScheduleEntry.version_no), desc(D.ExamScheduleEntry.updated_at))
                .all()):
        if row.assessment_id and row.assessment_id not in schedule_by_assessment:
            schedule_by_assessment[row.assessment_id] = row
    rows = s.query(D.Assessment).filter(D.Assessment.section_id == section_id).order_by(D.Assessment.scheduled_at, D.Assessment.id).all()
    return {"assessments": [{"id": a.id, "name": a.name, "max_marks": a.max_marks,
                             "locked": a.locked, "assessment_type": a.assessment_type,
                             "scheduled_at": a.scheduled_at.isoformat() if a.scheduled_at else "",
                             "end_at": a.end_at.isoformat() if a.end_at else "",
                             "published": a.published, "status": a.status,
                             "published_at": a.published_at.isoformat() if a.published_at else "",
                             "entered": s.query(D.Mark).filter(D.Mark.assessment_id == a.id).count(),
                             "published_marks": s.query(D.Mark).filter(D.Mark.assessment_id == a.id, D.Mark.status == "published").count(),
                             "timetable_status": schedule_by_assessment.get(a.id).status if schedule_by_assessment.get(a.id) else a.status}
                            for a in rows]}


class AssessmentUpsertIn(BaseModel):
    section_id: str
    name: str
    max_marks: float = 100
    assessment_type: str = "quiz"
    scheduled_at: str = ""
    end_at: str = ""
    published: bool = True
    instructions: str = ""
    academic_year: str = ""


@router.post("/exams/assessments")
def create_assessment(body: AssessmentUpsertIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "examinations", "create_assessment")
    require(dec)
    section = require_academic_object(s, ctx, _section_or_404(s, body.section_id), "create", "Section")
    if not _can_manage_section_for_assessments(s, ctx, section):
        raise HTTPException(403, "You cannot create assessments for this section")
    who = actor_name(s, ctx)
    row = D.Assessment(
        id=uid(), tenant_id=TENANT, section_id=section.id, name=body.name.strip(),
        max_marks=body.max_marks, weight=1.0, locked=False,
        assessment_type=(body.assessment_type or "quiz").strip().lower(),
        scheduled_at=datetime.fromisoformat(body.scheduled_at) if body.scheduled_at else None,
        end_at=datetime.fromisoformat(body.end_at) if body.end_at else None,
        published=body.published, instructions=body.instructions.strip(),
        status="published" if body.published else "draft",
        academic_year=(body.academic_year or _academic_year_for_datetime(datetime.fromisoformat(body.scheduled_at)) if body.scheduled_at else _academic_year_for_datetime(datetime.utcnow())).strip(),
        created_by=who,
        updated_by=who,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        published_at=datetime.utcnow() if body.published else None,
        published_by=who if body.published else "",
    )
    s.add(row)
    s.commit()
    write_audit(s, ctx["sub"], who, ctx["office_n"], "assessment.create",
                f"assessment:{row.id}", "", row.status,
                f"Created assessment '{row.name}' for section {section.section_code}")
    return {"id": row.id, "decision": dec.as_dict()}


@router.put("/exams/assessments/{assessment_id}")
def update_assessment(assessment_id: str, body: AssessmentUpsertIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "examinations", "edit_assessment")
    require(dec)
    row = s.query(D.Assessment).get(assessment_id)
    if not row:
        raise HTTPException(404, "Assessment not found")
    section = _section_or_404(s, row.section_id)
    if not _can_manage_section_for_assessments(s, ctx, section):
        raise HTTPException(403, "You cannot update assessments for this section")
    prev_state = row.status
    row.name = body.name.strip()
    row.max_marks = body.max_marks
    row.assessment_type = (body.assessment_type or row.assessment_type or "quiz").strip().lower()
    row.scheduled_at = datetime.fromisoformat(body.scheduled_at) if body.scheduled_at else None
    row.end_at = datetime.fromisoformat(body.end_at) if body.end_at else None
    row.published = body.published
    row.instructions = body.instructions.strip()
    row.status = "published" if body.published else "draft"
    row.academic_year = (body.academic_year or row.academic_year or _academic_year_for_datetime(row.scheduled_at or datetime.utcnow())).strip()
    row.updated_by = actor_name(s, ctx)
    row.updated_at = datetime.utcnow()
    if body.published and not row.published_at:
        row.published_at = datetime.utcnow()
        row.published_by = actor_name(s, ctx)
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "assessment.create",
                f"assessment:{row.id}", prev_state, row.status,
                f"Updated assessment '{row.name}'")
    return {"id": row.id, "decision": dec.as_dict()}


class EnterMarksIn(BaseModel):
    assessment_id: str
    marks: dict  # {student_id: score}
MARKS_EDITABLE_STATES = {"draft", "returned"}

@router.post("/exams/marks")
def enter_marks(body: EnterMarksIn, ctx=Depends(auth), s=Depends(db)):
    dec, verb = gate(s, ctx, "examinations", "enter_marks")
    require(dec)
    a = s.query(D.Assessment).get(body.assessment_id)
    if not a:
        raise HTTPException(400, "Unknown assessment")
    section = _section_or_404(s, a.section_id)
    if not _can_manage_section_for_assessments(s, ctx, section):
        raise HTTPException(403, "You cannot enter marks for this section")
    if a.locked:
        raise HTTPException(409, "Assessment is locked; marks cannot be changed")
    if (a.marks_state or "draft") not in MARKS_EDITABLE_STATES:
        raise HTTPException(409, "Marks are submitted for review and cannot be edited")
    who = actor_name(s, ctx)
    valid_student_ids = {
        row.student_id
        for row in s.query(D.Enrollment)
        .filter(D.Enrollment.section_id == section.id, D.Enrollment.status == "enrolled")
        .all()
    }
    for stu_id, score in body.marks.items():
        if stu_id not in valid_student_ids:
            raise HTTPException(400, "Marks can be entered only for students enrolled in this section")
        try:
            score = float(score)
        except (TypeError, ValueError):
            raise HTTPException(422, "Marks must be numeric")
        if score < 0 or score > a.max_marks:
            raise HTTPException(422, f"Marks must be between 0 and {a.max_marks}")
        existing = s.query(D.Mark).filter(D.Mark.assessment_id == a.id,
                                          D.Mark.student_id == stu_id).first()
        if existing:
            existing.score = score
            existing.status = "draft"
            existing.updated_at = datetime.utcnow()
        else:
            s.add(D.Mark(id=uid(), tenant_id=TENANT, assessment_id=a.id,
                          student_id=stu_id, score=score, entered_by=who,
                         status="draft", updated_at=datetime.utcnow()))
    s.commit()
    write_audit(s, ctx["sub"], who, ctx["office_n"], "marks.enter",
                f"assessment:{a.id}", "", "entered", f"Entered {len(body.marks)} marks for {a.name}")
    total_entered = s.query(D.Mark).filter(D.Mark.assessment_id == a.id).count()
    return {"assessment_id": a.id, "entered": len(body.marks), "total_entered": total_entered,
            "decision": dec.as_dict()}
class PublishMarksIn(BaseModel):
    assessment_id: str


@router.post("/exams/marks/publish")
def publish_marks(body: PublishMarksIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "examinations", "publish_marks")
    require(dec)
    assessment = s.query(D.Assessment).get(body.assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    section = _section_or_404(s, assessment.section_id)
    if not _can_manage_section_for_assessments(s, ctx, section):
        raise HTTPException(403, "You cannot publish marks for this section")
    who = actor_name(s, ctx)
    now = datetime.utcnow()
    rows = s.query(D.Mark).filter(D.Mark.assessment_id == assessment.id, D.Mark.is_valid == True).all()
    for row in rows:
        row.status = "published"
        row.published_at = now
        row.published_by = who
        row.updated_at = now
    assessment.published = True
    assessment.status = "published" if assessment.status != "cancelled" else assessment.status
    assessment.published_at = assessment.published_at or now
    assessment.published_by = assessment.published_by or who
    assessment.updated_at = now
    assessment.updated_by = who
    s.commit()
    write_audit(
        s, ctx["sub"], who, ctx["office_n"], "marks.publish",
        f"assessment:{assessment.id}", "draft", "published",
        f"Published {len(rows)} marks for {assessment.name}",
    )
    return {"published": len(rows), "decision": dec.as_dict()}


class PublishResultIn(BaseModel):
    section_id: str


def _auto_rollover_after_results(s, academic_year: str, semester: int | None, actor_id: str, actor_name_value: str):
    """Automatically progress a student only after every enrolled subject result is published.

    This is deliberately per-student and idempotent: publishing one course cannot
    move a student until all of that semester's enrolled courses have outcomes.
    """
    if not semester:
        return 0
    policy = s.query(D.AcademicProgressionPolicy).filter(D.AcademicProgressionPolicy.tenant_id == TENANT).first()
    if not policy:
        policy = D.AcademicProgressionPolicy(id=uid(), tenant_id=TENANT)
        s.add(policy); s.flush()
    target_semester = semester + 1
    target_year = s.query(D.AcademicYear).filter(D.AcademicYear.name == academic_year, D.AcademicYear.is_active == True).first()
    if not target_year or not s.query(D.Semester).filter(D.Semester.academic_year_id == target_year.id, D.Semester.sequence == target_semester, D.Semester.is_active == True).first():
        return 0
    row = (s.query(D.AcademicRollover).filter_by(source_academic_year=academic_year, source_semester=semester,
        target_academic_year=academic_year, target_semester=target_semester, status="completed").first())
    if not row:
        row = D.AcademicRollover(id=uid(), tenant_id=TENANT, source_academic_year=academic_year,
            source_semester=semester, target_academic_year=academic_year, target_semester=target_semester,
            status="completed", created_by=actor_id, approved_by=actor_id, executed_by=actor_id,
            approved_at=datetime.utcnow(), executed_at=datetime.utcnow(), remarks="Automatic rollover after final result publication")
        s.add(row); s.flush()
    progressed = 0
    for student in s.query(D.Student).filter(D.Student.status == "active", D.Student.semester == semester).all():
        enrolled = (s.query(D.Enrollment).join(D.Section, D.Enrollment.section_id == D.Section.id)
                    .join(D.Course, D.Section.course_id == D.Course.id)
                    .filter(D.Enrollment.student_id == student.id, D.Enrollment.status == "enrolled", D.Course.semester == semester).all())
        if not enrolled:
            continue
        section_ids = {enrollment.section_id for enrollment in enrolled}
        results = s.query(D.StudentSubjectResult).filter(D.StudentSubjectResult.student_id == student.id,
            D.StudentSubjectResult.academic_year == academic_year, D.StudentSubjectResult.semester == semester,
            D.StudentSubjectResult.section_id.in_(section_ids)).all()
        if len({result.section_id for result in results}) != len(section_ids):
            continue
        history = s.query(D.StudentAcademicHistory).filter_by(rollover_id=row.id, student_id=student.id).first()
        if history:
            continue
        backlog_count = sum(1 for result in results if result.outcome == "failed")
        attendance_rows = s.query(D.AttendanceRecord).filter(D.AttendanceRecord.student_id == student.id, D.AttendanceRecord.section_id.in_(section_ids)).all()
        attendance_pct = (100 * sum(1 for record in attendance_rows if record.present) / len(attendance_rows)) if attendance_rows else None
        outstanding = float(s.query(func.coalesce(func.sum(D.FeeInvoice.amount - D.FeeInvoice.paid), 0)).filter(D.FeeInvoice.student_id == student.id).scalar() or 0)
        active_discipline = s.query(D.Complaint).filter(D.Complaint.student_id == student.id, D.Complaint.kind == "Discipline", D.Complaint.status != "resolved", D.Complaint.severity == "high").first()
        eligible = (backlog_count <= policy.max_backlogs and
                    (attendance_pct is None or attendance_pct >= policy.minimum_attendance_pct) and
                    not active_discipline and
                    not (policy.fee_policy == "block" and outstanding > 0))
        decision = "promoted" if eligible else ("hold" if active_discipline or (attendance_pct is not None and attendance_pct < policy.minimum_attendance_pct) or (policy.fee_policy == "block" and outstanding > 0) else "repeating")
        s.add(D.StudentAcademicHistory(id=uid(), tenant_id=TENANT, student_id=student.id, rollover_id=row.id,
            source_academic_year=academic_year, source_semester=semester, target_academic_year=academic_year,
            target_semester=target_semester, decision=decision))
        s.add(D.AcademicRolloverDecision(id=uid(), rollover_id=row.id, student_id=student.id,
            decision=decision, academic_status="ELIGIBLE" if eligible else "NOT_ELIGIBLE", finance_status="DUE_EXISTS" if outstanding > 0 else "CLEAR", outstanding_amount=outstanding, carry_forward_amount=outstanding if eligible and outstanding > 0 else 0))
        if eligible:
            student.semester = target_semester
            notify(s, student.user_id, "Academic progression complete", f"You have been progressed to Semester {target_semester} after published results.", "info")
            progressed += 1
    return progressed


class ProgressionPolicyIn(BaseModel):
    max_backlogs: int = Field(0, ge=0, le=20)
    minimum_attendance_pct: float = Field(75, ge=0, le=100)
    fee_policy: str = "carry_forward"


def _progression_policy_payload(s):
    row = s.query(D.AcademicProgressionPolicy).filter(D.AcademicProgressionPolicy.tenant_id == TENANT).first()
    if not row:
        row = D.AcademicProgressionPolicy(id=uid(), tenant_id=TENANT); s.add(row); s.commit()
    return {"max_backlogs": row.max_backlogs, "minimum_attendance_pct": row.minimum_attendance_pct,
            "fee_policy": row.fee_policy, "discipline_policy": row.discipline_policy}


@router.get("/academic-rollover/policy")
def get_progression_policy(ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] not in {4, 6, 10, 17}: raise HTTPException(403, "Academic leadership may view progression policy")
    return _progression_policy_payload(s)


@router.put("/academic-rollover/policy")
def update_progression_policy(body: ProgressionPolicyIn, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] not in {4, 6, 10, 17}: raise HTTPException(403, "Academic leadership may update progression policy")
    if body.fee_policy not in {"carry_forward", "block"}: raise HTTPException(422, "Fee policy must be carry_forward or block")
    _progression_policy_payload(s)
    row = s.query(D.AcademicProgressionPolicy).filter(D.AcademicProgressionPolicy.tenant_id == TENANT).first()
    row.max_backlogs, row.minimum_attendance_pct, row.fee_policy = body.max_backlogs, body.minimum_attendance_pct, body.fee_policy
    row.updated_by, row.updated_at = ctx["sub"], datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic.progression_policy", "progression_policy", "", "updated", "Automatic progression policy updated")
    return _progression_policy_payload(s)


@router.post("/exams/publish")
def publish_result(body: PublishResultIn, ctx=Depends(auth), s=Depends(db)):
    # Result publication is a distinct authority from marks entry (SoD invariant).
    dec, verb = gate(s, ctx, "examinations", "publish_result")
    require(dec)
    who = actor_name(s, ctx)
    section = require_academic_object(s, ctx, _section_or_404(s, body.section_id), "edit", "Section")
    rs = (s.query(D.ResultSheet)
          .filter(D.ResultSheet.section_id == body.section_id)
          .order_by(desc(D.ResultSheet.published_at), desc(D.ResultSheet.updated_at))
          .first())
    if not rs:
        rs = D.ResultSheet(id=uid(), tenant_id=TENANT, section_id=body.section_id,
                           term="2025-Odd")
        s.add(rs)
    course = s.query(D.Course).get(section.course_id) if section.course_id else None
    rs.academic_year = rs.academic_year or _academic_year_for_datetime(datetime.utcnow())
    rs.semester = rs.semester or (course.semester if course else None)
    rs.status = "published"
    rs.published_by = who
    rs.published_at = datetime.utcnow()
    rs.updated_at = datetime.utcnow()
    section_assessment_ids = [row[0] for row in s.query(D.Assessment.id).filter(D.Assessment.section_id == section.id).all()]
    if section_assessment_ids:
        marks = s.query(D.Mark).filter(D.Mark.assessment_id.in_(section_assessment_ids), D.Mark.is_valid == True).all()
        for mark in marks:
            if mark.status != "published":
                mark.status = "published"
                mark.published_at = rs.published_at
                mark.published_by = who
                mark.updated_at = rs.published_at
    published_rows = _publish_section_subject_results(s, section, rs, who)
    auto_progressed = _auto_rollover_after_results(s, rs.academic_year, rs.semester, ctx["sub"], who)
    s.commit()
    write_audit(s, ctx["sub"], who, ctx["office_n"], "result.publish",
                f"section:{body.section_id}", "moderated", "published",
                "Result published")
    return {"status": "published", "published_results": published_rows, "automatically_progressed": auto_progressed, "decision": dec.as_dict()}


class ExamTimetableUpsertIn(BaseModel):
    section_id: str
    assessment_id: str = ""
    academic_year: str = ""
    semester: int | None = None
    exam_type: str = "exam"
    start_at: str = ""
    end_at: str = ""
    venue: str = ""
    mode: str = "Offline"
    status: str = "scheduled"
    note: str = ""


@router.get("/exams/timetable/{section_id}")
def exam_timetable(section_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "examinations", "view")[0])
    section = _section_or_404(s, section_id)
    if not _can_view_exam_section(s, ctx, section):
        raise HTTPException(403, "You cannot view timetable for this section")
    course = s.query(D.Course).get(section.course_id) if section.course_id else None
    rows = (
        s.query(D.ExamScheduleEntry)
        .filter(D.ExamScheduleEntry.section_id == section_id)
        .order_by(desc(D.ExamScheduleEntry.is_active), desc(D.ExamScheduleEntry.version_no), D.ExamScheduleEntry.start_at)
        .all()
    )
    return {
        "entries": [
            {
                "id": row.id,
                "section_id": row.section_id,
                "assessment_id": row.assessment_id,
                "course_code": course.code if course else "",
                "course_title": course.title if course else "",
                "academic_year": row.academic_year,
                "semester": row.semester,
                "exam_type": row.exam_type,
                "start_at": row.start_at.isoformat() if row.start_at else "",
                "end_at": row.end_at.isoformat() if row.end_at else "",
                "venue": row.venue,
                "mode": row.mode,
                "status": row.status,
                "version_no": row.version_no,
                "is_active": row.is_active,
                "note": row.note or "",
            }
            for row in rows
        ],
        "can_manage_timetable": can(s, ctx, "examinations", "manage_timetable"),
    }


@router.post("/exams/timetable")
def create_exam_timetable(body: ExamTimetableUpsertIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "examinations", "manage_timetable")
    require(dec)
    section = _section_or_404(s, body.section_id)
    if not _can_manage_section_for_exam_timetable(s, ctx, section):
        raise HTTPException(403, "You cannot manage exam timetable for this section")
    assessment = None
    if body.assessment_id:
        assessment = s.query(D.Assessment).get(body.assessment_id)
        if not assessment or assessment.section_id != section.id:
            raise HTTPException(400, "Assessment does not belong to this section")
    who = actor_name(s, ctx)
    row = D.ExamScheduleEntry(
        id=uid(),
        tenant_id=TENANT,
        assessment_id=assessment.id if assessment else None,
        section_id=section.id,
        academic_year=(body.academic_year or _academic_year_for_datetime(datetime.fromisoformat(body.start_at)) if body.start_at else _academic_year_for_datetime(datetime.utcnow())).strip(),
        semester=body.semester if body.semester is not None else _section_semester(s, section),
        exam_type=(body.exam_type or (assessment.assessment_type if assessment else "exam") or "exam").strip().lower(),
        start_at=datetime.fromisoformat(body.start_at) if body.start_at else None,
        end_at=datetime.fromisoformat(body.end_at) if body.end_at else None,
        venue=body.venue.strip(),
        mode=(body.mode or "Offline").strip(),
        status=(body.status or "scheduled").strip().lower(),
        version_no=1,
        is_active=True,
        managed_by_office_n=ctx["office_n"],
        note=body.note.strip(),
        created_by=who,
        updated_by=who,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    s.add(row)
    _sync_assessment_from_schedule(assessment, body, who, section)
    s.flush()
    _write_schedule_history(s, row, who, "created", {"start_at": None, "end_at": None, "venue": "", "status": ""}, body.note.strip())
    s.commit()
    write_audit(
        s, ctx["sub"], who, ctx["office_n"], "exam.timetable.create",
        f"exam_schedule:{row.id}", "", row.status,
        f"Created {row.exam_type} timetable entry for section {section.section_code}",
    )
    return {"id": row.id, "decision": dec.as_dict()}


@router.put("/exams/timetable/{schedule_id}")
def update_exam_timetable(schedule_id: str, body: ExamTimetableUpsertIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "examinations", "manage_timetable")
    require(dec)
    row = s.query(D.ExamScheduleEntry).get(schedule_id)
    if not row:
        raise HTTPException(404, "Exam timetable entry not found")
    section = _section_or_404(s, row.section_id)
    if not _can_manage_section_for_exam_timetable(s, ctx, section):
        raise HTTPException(403, "You cannot manage exam timetable for this section")
    assessment = s.query(D.Assessment).get(body.assessment_id or row.assessment_id) if (body.assessment_id or row.assessment_id) else None
    if body.assessment_id and (not assessment or assessment.section_id != section.id):
        raise HTTPException(400, "Assessment does not belong to this section")
    who = actor_name(s, ctx)
    previous = {
        "start_at": row.start_at,
        "end_at": row.end_at,
        "venue": row.venue,
        "status": row.status,
    }
    row.assessment_id = assessment.id if assessment else row.assessment_id
    row.academic_year = (body.academic_year or row.academic_year or _academic_year_for_datetime(row.start_at or datetime.utcnow())).strip()
    row.semester = body.semester if body.semester is not None else (row.semester or _section_semester(s, section))
    row.exam_type = (body.exam_type or row.exam_type or "exam").strip().lower()
    row.start_at = datetime.fromisoformat(body.start_at) if body.start_at else row.start_at
    row.end_at = datetime.fromisoformat(body.end_at) if body.end_at else row.end_at
    row.venue = body.venue.strip() or row.venue
    row.mode = (body.mode or row.mode or "Offline").strip()
    row.status = (body.status or row.status or "scheduled").strip().lower()
    row.version_no = int(row.version_no or 1) + 1
    row.is_active = True
    row.managed_by_office_n = ctx["office_n"]
    row.note = body.note.strip() or row.note
    row.updated_by = who
    row.updated_at = datetime.utcnow()
    _sync_assessment_from_schedule(assessment, body, who, section)
    change_type = "rescheduled" if row.status == "rescheduled" else ("cancelled" if row.status == "cancelled" else "updated")
    _write_schedule_history(s, row, who, change_type, previous, body.note.strip())
    s.commit()
    write_audit(
        s, ctx["sub"], who, ctx["office_n"], "exam.timetable.update",
        f"exam_schedule:{row.id}", previous.get("status", ""), row.status,
        f"Updated exam timetable entry for section {section.section_code}",
    )
    return {"id": row.id, "decision": dec.as_dict()}


# --------------------------------------------------------------------------- #
#  ADMISSIONS
# --------------------------------------------------------------------------- #
@router.get("/admissions")
def list_applications(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "admissions", "view")[0])
    rows = s.query(D.Application).order_by(desc(D.Application.score)).all()
    return {"applications": [{
        "id": a.id, "name": a.applicant_name, "email": a.email,
        "program": a.program_name, "score": a.score, "status": a.status,
    } for a in rows],
        "can_verify": can(s, ctx, "admissions", "verify"),
        "can_offer": can(s, ctx, "admissions", "offer")}


class AdmissionDecisionIn(BaseModel):
    application_id: str
    action: str  # verify / offer / reject


@router.post("/admissions/decide")
def decide_application(body: AdmissionDecisionIn, ctx=Depends(auth), s=Depends(db)):
    action_map = {"verify": "verify", "offer": "offer", "reject": "reject"}
    if body.action not in action_map:
        raise HTTPException(400, "Invalid action")
    dec, verb = gate(s, ctx, "admissions", action_map[body.action])
    require(dec)
    a = s.query(D.Application).get(body.application_id)
    if not a:
        raise HTTPException(404, "Application not found")
    new = {"verify": "verified", "offer": "offered", "reject": "rejected"}[body.action]
    a.status = new
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], f"admission.{body.action}",
                f"application:{a.id}", "", new, f"{body.action} {a.applicant_name}")
    return {"status": new, "decision": dec.as_dict()}


# --------------------------------------------------------------------------- #
#  FINANCE
# --------------------------------------------------------------------------- #
class RolloverStartIn(BaseModel):
    source_academic_year: str
    source_semester: int
    target_academic_year: str
    target_semester: int


class RolloverDecisionIn(BaseModel):
    student_id: str
    decision: str
    note: str = ""


def _rollover_payload(s, row):
    students = {student.id: student for student in s.query(D.Student).all()}
    decisions = s.query(D.AcademicRolloverDecision).filter(D.AcademicRolloverDecision.rollover_id == row.id).all()
    summary = {"total": len(decisions), "eligible": 0, "detained": 0, "on_hold": 0, "exceptions": 0, "outstanding": 0}
    items = []
    for item in decisions:
        summary["outstanding"] += float(item.outstanding_amount or 0)
        if item.decision == "promoted": summary["eligible"] += 1
        elif item.decision in {"detained", "repeating"}: summary["detained"] += 1
        elif item.decision == "hold": summary["on_hold"] += 1
        elif item.decision == "exception": summary["exceptions"] += 1
        student = students.get(item.student_id)
        items.append({"student_id": item.student_id, "roll_no": student.roll_no if student else "",
            "name": student.name if student else "", "decision": item.decision, "note": item.note,
            "academic_status": item.academic_status, "finance_status": item.finance_status,
            "outstanding_amount": item.outstanding_amount, "carry_forward_amount": item.carry_forward_amount})
    return {"id": row.id, "source_academic_year": row.source_academic_year, "source_semester": row.source_semester,
            "target_academic_year": row.target_academic_year, "target_semester": row.target_semester,
            "status": row.status, "created_at": row.created_at.isoformat() if row.created_at else "",
            "executed_at": row.executed_at.isoformat() if row.executed_at else "", "summary": summary, "decisions": items}


@router.get("/academic-rollover")
def academic_rollovers(ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] not in {4, 6, 10, 17, 22}:
        raise HTTPException(403, "Academic rollover is restricted to academic leadership and Finance")
    rows = s.query(D.AcademicRollover).order_by(desc(D.AcademicRollover.created_at)).all()
    years = [row.name for row in s.query(D.AcademicYear).filter(D.AcademicYear.is_active == True).order_by(D.AcademicYear.name).all()]
    return {"rollovers": [_rollover_payload(s, row) for row in rows], "academic_years": years,
            "can_review": ctx["office_n"] in {6, 10, 17}, "can_approve": ctx["office_n"] == 4,
            "finance_ready": [row.id for row in rows if row.status == "approved"]}


@router.post("/academic-rollover")
def start_academic_rollover(body: RolloverStartIn, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] not in {6, 10, 17}: raise HTTPException(403, "Only the Academic Coordinator or academic leadership may start rollover")
    students = s.query(D.Student).filter(D.Student.status == "active", D.Student.semester == body.source_semester).all()
    if not students: raise HTTPException(409, "No active students found in the selected source semester")
    row = D.AcademicRollover(id=uid(), tenant_id=TENANT, **body.model_dump(), created_by=ctx["sub"])
    s.add(row); s.flush()
    for student in students:
        outstanding = float(s.query(func.coalesce(func.sum(D.FeeInvoice.amount - D.FeeInvoice.paid), 0)).filter(D.FeeInvoice.student_id == student.id).scalar() or 0)
        result = s.query(D.StudentSubjectResult).filter(D.StudentSubjectResult.student_id == student.id, D.StudentSubjectResult.status == "published").first()
        academic_status = "ELIGIBLE" if result else "RESULT_PENDING"
        finance_status = "DUE_EXISTS" if outstanding > 0 else "CLEAR"
        s.add(D.AcademicRolloverDecision(id=uid(), rollover_id=row.id, student_id=student.id,
            academic_status=academic_status, finance_status=finance_status, outstanding_amount=outstanding,
            decision="pending"))
    s.commit(); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic.rollover.start", f"rollover:{row.id}", "", "draft", f"{len(students)} students selected")
    return _rollover_payload(s, row)


@router.post("/academic-rollover/{rollover_id}/decision")
def decide_academic_rollover(rollover_id: str, body: RolloverDecisionIn, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] not in {6, 10, 17}: raise HTTPException(403, "Only academic leadership may review progression")
    row = s.get(D.AcademicRollover, rollover_id); item = s.query(D.AcademicRolloverDecision).filter_by(rollover_id=rollover_id, student_id=body.student_id).first()
    if not row or not item or row.status != "draft": raise HTTPException(409, "This rollover is not open for review")
    if body.decision not in {"promoted", "detained", "repeating", "hold", "exception"}: raise HTTPException(422, "Choose a valid progression decision")
    item.decision, item.note = body.decision, body.note.strip(); s.commit()
    return _rollover_payload(s, row)


@router.post("/academic-rollover/{rollover_id}/submit")
def submit_academic_rollover(rollover_id: str, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] not in {6, 10, 17}: raise HTTPException(403, "Only academic leadership may submit rollover")
    row = s.get(D.AcademicRollover, rollover_id)
    if not row or row.status != "draft": raise HTTPException(409, "Rollover is not in draft")
    pending = s.query(D.AcademicRolloverDecision).filter_by(rollover_id=row.id, decision="pending").count()
    if pending: raise HTTPException(409, f"Review all students before submission ({pending} pending)")
    row.status = "awaiting_principal"; s.commit()
    for user in s.query(User).filter(User.office_n == 4, User.active == True).all(): notify(s, user.id, "Academic rollover approval", f"Review progression for Semester {row.source_semester} before Finance is notified.", "warning")
    return _rollover_payload(s, row)


@router.post("/academic-rollover/{rollover_id}/approve")
def approve_academic_rollover(rollover_id: str, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] != 4: raise HTTPException(403, "Principal approval is required")
    row = s.get(D.AcademicRollover, rollover_id)
    if not row or row.status != "awaiting_principal": raise HTTPException(409, "Rollover is not awaiting Principal approval")
    row.status, row.approved_by, row.approved_at = "approved", ctx["sub"], datetime.utcnow(); s.commit()
    for user in s.query(User).filter(User.office_n == 22, User.active == True).all(): notify(s, user.id, "Next-semester fee setup ready", f"Rollover approved: publish fee structure for {row.target_academic_year}, Semester {row.target_semester}.", "warning")
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic.rollover.approve", f"rollover:{row.id}", "awaiting_principal", "approved", "Finance notified")
    return _rollover_payload(s, row)


@router.post("/academic-rollover/{rollover_id}/execute")
def execute_academic_rollover(rollover_id: str, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] not in {4, 6, 10, 17}: raise HTTPException(403, "Academic leadership may execute an approved rollover")
    row = s.get(D.AcademicRollover, rollover_id)
    if not row or row.status != "approved": raise HTTPException(409, "Rollover must be approved before execution")
    target_year = s.query(D.AcademicYear).filter(D.AcademicYear.name == row.target_academic_year, D.AcademicYear.is_active == True).first()
    if not target_year: raise HTTPException(409, "NEXT_ACADEMIC_YEAR_NOT_ACTIVE")
    target_semester = s.query(D.Semester).filter(D.Semester.academic_year_id == target_year.id, D.Semester.sequence == row.target_semester, D.Semester.is_active == True).first()
    if not target_semester: raise HTTPException(409, "NEXT_SEMESTER_NOT_CONFIGURED")
    promoted = s.query(D.AcademicRolloverDecision).filter_by(rollover_id=row.id, decision="promoted").all()
    for item in promoted:
        student = s.get(D.Student, item.student_id)
        if not student or student.status != "active": continue
        history = s.query(D.StudentAcademicHistory).filter_by(rollover_id=row.id, student_id=student.id).first()
        if history: continue
        s.add(D.StudentAcademicHistory(id=uid(), tenant_id=TENANT, student_id=student.id, rollover_id=row.id,
            source_academic_year=row.source_academic_year, source_semester=row.source_semester,
            target_academic_year=row.target_academic_year, target_semester=row.target_semester, decision=item.decision))
        student.semester = row.target_semester
        item.carry_forward_amount = item.outstanding_amount
        item.processed_at = datetime.utcnow()
    row.status, row.executed_by, row.executed_at = "completed", ctx["sub"], datetime.utcnow()
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "academic.rollover.execute", f"rollover:{row.id}", "approved", "completed", f"Processed {len(promoted)} promoted students")
    return _rollover_payload(s, row)

def _format_fee_category(value: str | None):
    if not value:
        return "Uncategorised"
    return value.replace("_", " ").strip().title()


def _invoice_fee_category_details(s, invoice):
    lines = []
    if invoice and invoice.fee_structure_id:
        lines = s.query(D.FeeStructureLine).filter(D.FeeStructureLine.fee_structure_id == invoice.fee_structure_id).all()

    categories = {}
    for line in lines:
        head = s.get(D.FeeHead, line.fee_head_id)
        if not head:
            continue
        category = _format_fee_category(head.category)
        if category not in categories:
            categories[category] = {"fee_category_id": None, "fee_category": category,
                                    "assigned": 0.0, "paid": 0.0, "balance": 0.0}
        categories[category]["assigned"] += float(line.amount or 0)

    if not categories:
        summary = [{"fee_category_id": None, "fee_category": "Uncategorised",
                    "assigned": float(invoice.amount or 0), "paid": float(invoice.paid or 0),
                    "balance": float((invoice.amount or 0) - (invoice.paid or 0))}]
        return {"fee_category_id": None, "fee_category": "Uncategorised", "categories": summary}

    summaries = []
    for category in categories:
        assigned = round(categories[category]["assigned"], 2)
        paid = round(min(float(invoice.paid or 0), assigned), 2)
        balance = round(max(assigned - paid, 0), 2)
        summaries.append({"fee_category_id": None, "fee_category": category,
                          "assigned": assigned, "paid": paid, "balance": balance})

    summaries.sort(key=lambda x: x["fee_category"])
    primary = summaries[0]["fee_category"] if len(summaries) == 1 else "Mixed"
    return {"fee_category_id": None, "fee_category": primary, "categories": summaries}


@router.get("/finance/invoices")
def list_invoices(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "view")[0])
    stu_map = {st.id: (st.roll_no, st.name) for st in s.query(D.Student).all()}
    rows = s.query(D.FeeInvoice).limit(300).all()
    out = []
    category_buckets = {}
    for r in rows:
        roll, name = stu_map.get(r.student_id, ("", ""))
        invoice_details = _invoice_fee_category_details(s, r)
        row = {"id": r.id, "roll_no": roll, "name": name, "term": r.term,
               "amount": r.amount, "paid": r.paid, "balance": r.amount - r.paid,
               "status": r.status, "fee_category_id": invoice_details["fee_category_id"],
               "fee_category": invoice_details["fee_category"], "categories": invoice_details["categories"]}
        out.append(row)
        for category in invoice_details["categories"]:
            key = category["fee_category"]
            bucket = category_buckets.setdefault(key, {"fee_category_id": None, "fee_category": key,
                                                      "assigned": 0.0, "paid": 0.0, "balance": 0.0})
            bucket["assigned"] += category["assigned"]
            bucket["paid"] += category["paid"]
            bucket["balance"] += category["balance"]

    summary = {
        "total_billed": s.query(func.coalesce(func.sum(D.FeeInvoice.amount), 0)).scalar() or 0,
        "total_collected": s.query(func.coalesce(func.sum(D.FeeInvoice.paid), 0)).scalar() or 0,
        "outstanding": s.query(func.coalesce(func.sum(D.FeeInvoice.amount - D.FeeInvoice.paid), 0)).scalar() or 0,
    }
    payments = s.query(D.Payment).order_by(desc(D.Payment.at)).limit(300).all()
    payment_rows = []
    for payment in payments:
        roll, name = stu_map.get(payment.student_id, ("", ""))
        invoice_details = _invoice_fee_category_details(s, s.get(D.FeeInvoice, payment.invoice_id)) if payment.invoice_id else {"fee_category_id": None, "fee_category": "Uncategorised", "categories": []}
        payment_rows.append({"id": payment.id, "invoice_id": payment.invoice_id, "roll_no": roll,
                             "name": name, "amount": payment.amount, "method": payment.method,
                             "reference": payment.reference, "status": payment.status or "success",
                             "fee_category_id": invoice_details["fee_category_id"],
                             "fee_category": invoice_details["fee_category"],
                             "at": payment.at.isoformat() if payment.at else ""})
    return {"invoices": out, "payments": payment_rows, "summary": summary,
            "categories": sorted(category_buckets.values(), key=lambda x: x["fee_category"]),
            "can_record": can(s, ctx, "finance", "record_payment"),
            "can_waive": can(s, ctx, "finance", "waive")}


@router.get("/finance/budget")
def list_budget(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "view")[0])
    rows = s.query(D.BudgetLine).filter(D.BudgetLine.tenant_id == ctx.get("tenant_id", TENANT)).all()
    return {"budget": [{"category": b.category, "allocated": b.allocated,
                        "spent": b.spent, "remaining": b.allocated - b.spent,
                        "fiscal_year": b.fiscal_year} for b in rows],
            "can_approve": can(s, ctx, "finance", "approve_budget")}


class RecordPaymentIn(BaseModel):
    invoice_id: str
    amount: float
    method: str = "cash"
    reference: str = ""


@router.post("/finance/payment")
def record_payment(body: RecordPaymentIn, ctx=Depends(auth), s=Depends(db)):
    dec, verb = gate(s, ctx, "finance", "record_payment", amount=body.amount)
    require(dec)
    inv = s.query(D.FeeInvoice).get(body.invoice_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if body.amount <= 0:
        raise HTTPException(400, "Amount must be greater than zero")
    if body.amount > (inv.amount - inv.paid):
        body.amount = max(0, inv.amount - inv.paid)
    method = (body.method or "cash").strip().lower()
    if method not in {"cash", "cheque", "dd", "bank_transfer", "online", "counter"}:
        method = "cash"
    reference = (body.reference or "").strip() or f"{method.upper()}-{uid()[:8].upper()}"
    pending = method in {"cheque", "dd", "bank_transfer"}
    payment = D.Payment(id=uid(), tenant_id=TENANT, invoice_id=inv.id, student_id=inv.student_id,
                    amount=body.amount, method=method, reference=reference,
                    status="pending_clearance" if pending else "success")
    s.add(payment)
    s.flush()
    if not pending:
        from portal_api import _settle_payment
        _settle_payment(s, payment, ctx["sub"])
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee.payment",
                f"invoice:{inv.id}", "", inv.status,
                f"Recorded ₹{body.amount:,.0f} via {method} ({reference})")
    return {"status": "pending_clearance" if pending else inv.status, "paid": inv.paid, "payment_id": payment.id, "decision": dec.as_dict(), "method": method, "reference": reference}


@router.get("/finance/invoices/{invoice_id}/receipt.pdf")
def finance_payment_receipt(invoice_id: str, payment_id: str = "", ctx=Depends(auth), s=Depends(db)):
    """Finance may issue the same official receipt after a recorded cash payment."""
    require(gate(s, ctx, "finance", "view")[0])
    invoice = s.get(D.FeeInvoice, invoice_id)
    if not invoice or not invoice.paid:
        raise HTTPException(404, "A confirmed payment receipt is not available for this invoice")
    student = s.get(D.Student, invoice.student_id)
    if not student:
        raise HTTPException(404, "Student not found")
    from portal_api import _receipt_pdf
    payment = s.get(D.Payment, payment_id) if payment_id else None
    if payment and (payment.invoice_id != invoice.id or payment.status != "success"):
        raise HTTPException(404, "A confirmed receipt is not available for this payment")
    return Response(_receipt_pdf(student, invoice, s, payment.id if payment else None), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="ICMS-receipt-{student.roll_no}-{invoice.id}.pdf"'})

class ClearPaymentIn(BaseModel):
    action: str
    remarks: str = ""

@router.get("/finance/payments/pending")
def pending_payment_verification(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "record_payment")[0])
    rows = s.query(D.Payment).filter(D.Payment.status.in_(("pending_verification", "pending_clearance"))).order_by(desc(D.Payment.at)).all()
    out = []
    for p in rows:
        proof = s.query(D.PaymentProof).filter(D.PaymentProof.payment_id == p.id).first()
        student = s.get(D.Student, p.student_id)
        challan = s.get(D.FeeChallan, p.challan_id) if p.challan_id else None
        out.append({"id": p.id, "student": student.name if student else "", "roll_no": student.roll_no if student else "",
            "invoice_id": p.invoice_id, "challan_number": challan.challan_number if challan else "", "amount": p.amount,
            "method": p.method, "reference": p.reference, "status": p.status, "submitted_at": p.at.isoformat() if p.at else "",
            "proof": {"file_name": proof.file_name, "file_type": proof.file_type, "file_data": proof.file_data} if proof else None})
    return {"payments": out}

@router.post("/finance/payments/{payment_id}/clear")
def clear_payment(payment_id: str, body: ClearPaymentIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "finance", "record_payment")
    require(dec)
    payment = s.get(D.Payment, payment_id)
    if not payment or payment.status not in {"pending_verification", "pending_clearance"}:
        raise HTTPException(409, "Payment is not awaiting verification or clearance")
    actions = {"cleared", "bounced", "verified", "rejected"}
    if body.action not in actions: raise HTTPException(422, "Invalid payment action")
    if payment.status == "pending_verification" and body.action not in {"verified", "rejected"}:
        raise HTTPException(422, "Bank-transfer payments must be verified or rejected")
    if payment.status == "pending_clearance" and body.action not in {"cleared", "bounced"}:
        raise HTTPException(422, "Cheque/DD payments must be cleared or bounced")
    if body.action in {"bounced", "rejected"} and not body.remarks.strip(): raise HTTPException(422, "Remarks are required")
    if body.action in {"cleared", "verified"}:
        payment.status = "success"
        from portal_api import _settle_payment
        _settle_payment(s, payment, ctx["sub"])
    else:
        payment.status = "bounced" if body.action == "bounced" else "rejected"
    payment.remarks = body.remarks.strip()
    payment.cleared_at, payment.cleared_by = datetime.utcnow(), ctx["sub"]
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee.payment.clearance", f"payment:{payment.id}", "pending_clearance", payment.status, payment.reference)
    return {"payment_id": payment.id, "status": payment.status, "decision": dec.as_dict()}


class WaiveIn(BaseModel):
    invoice_id: str
    amount: float
    reason: str = ""


class InvoiceReviewIn(BaseModel):
    decision: str = "approved"
    remarks: str = ""


class FinanceAdjustmentIn(BaseModel):
    invoice_id: str
    adjustment_type: str = "credit"
    amount: float = Field(gt=0)
    reason: str = ""


class FinanceReconciliationIn(BaseModel):
    period_start: date | None = None
    period_end: date | None = None
    notes: str = ""


class FinanceRefundIn(BaseModel):
    invoice_id: str
    amount: float = Field(gt=0)
    reason: str = ""


class FinanceRefundDecisionIn(BaseModel):
    decision: str = "approved"
    remarks: str = ""


class VendorPaymentIn(BaseModel):
    vendor_name: str
    invoice_ref: str = ""
    amount: float = Field(gt=0)
    notes: str = ""


class VendorPaymentApprovalIn(BaseModel):
    approval_reference: str = ""


class FinanceDayCloseIn(BaseModel):
    notes: str = ""


@router.post("/finance/invoices/{invoice_id}/review")
def review_invoice(invoice_id: str, body: InvoiceReviewIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "view")[0])
    invoice = s.get(D.FeeInvoice, invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    decision = (body.decision or "approved").strip().lower()
    if decision not in {"approved", "pending_review", "rejected"}:
        raise HTTPException(422, "Invalid invoice review decision")
    review = D.FinanceInvoiceReview(id=uid(), tenant_id=TENANT, invoice_id=invoice.id,
        student_id=invoice.student_id, decision=decision, remarks=body.remarks or "",
        reviewed_by=ctx["sub"], reviewed_at=datetime.utcnow())
    s.add(review)
    invoice.status = "paid" if invoice.paid >= invoice.amount and invoice.amount else (
        "partial" if invoice.paid > 0 else invoice.status)
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee.invoice.review",
                f"invoice:{invoice.id}", invoice.status, decision, body.remarks or "Reviewed")
    return {"status": decision, "review": {"id": review.id, "decision": decision, "remarks": review.remarks}}


@router.get("/finance/adjustments")
def list_adjustments(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "view")[0])
    rows = s.query(D.FinanceAdjustment).order_by(desc(D.FinanceAdjustment.created_at)).all()
    return {"adjustments": [{
        "id": row.id,
        "invoice_id": row.invoice_id,
        "student_id": row.student_id,
        "adjustment_type": row.adjustment_type,
        "amount": row.amount,
        "reason": row.reason,
        "status": row.status,
        "created_by": row.created_by,
        "reviewed_by": row.reviewed_by,
        "remarks": row.remarks,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    } for row in rows]}


@router.post("/finance/adjustments")
def create_adjustment(body: FinanceAdjustmentIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "view")[0])
    invoice = s.get(D.FeeInvoice, body.invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if body.adjustment_type not in {"credit", "debit", "refund"}:
        raise HTTPException(422, "Invalid adjustment type")
    row = D.FinanceAdjustment(id=uid(), tenant_id=TENANT, invoice_id=invoice.id,
        student_id=invoice.student_id, adjustment_type=body.adjustment_type,
        amount=float(body.amount), reason=body.reason or "", status="pending_review",
        created_by=ctx["sub"])
    s.add(row)
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee.adjustment.create",
                f"invoice:{invoice.id}", "pending_review", row.adjustment_type,
                f"Adjustment requested: ₹{body.amount:,.0f}")
    return {"status": "pending_review", "adjustment": {"id": row.id, "invoice_id": row.invoice_id,
        "student_id": row.student_id, "adjustment_type": row.adjustment_type, "amount": row.amount,
        "status": row.status, "reason": row.reason}}


@router.get("/finance/reconciliations")
def list_reconciliations(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "view")[0])
    rows = s.query(D.FinanceReconciliation).order_by(desc(D.FinanceReconciliation.created_at)).all()
    return {"reconciliations": [{
        "id": row.id,
        "period_start": row.period_start.isoformat() if row.period_start else "",
        "period_end": row.period_end.isoformat() if row.period_end else "",
        "opening_balance": row.opening_balance,
        "total_collected": row.total_collected,
        "total_adjustments": row.total_adjustments,
        "closing_balance": row.closing_balance,
        "status": row.status,
        "notes": row.notes,
        "created_by": row.created_by,
        "closed_at": row.closed_at.isoformat() if row.closed_at else "",
    } for row in rows]}


@router.post("/finance/reconciliations")
def create_reconciliation(body: FinanceReconciliationIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "view")[0])
    start = body.period_start or date.today().replace(day=1)
    end = body.period_end or date.today()
    summary = {"total_billed": s.query(func.coalesce(func.sum(D.FeeInvoice.amount), 0)).scalar() or 0,
               "total_collected": s.query(func.coalesce(func.sum(D.FeeInvoice.paid), 0)).scalar() or 0,
               "outstanding": s.query(func.coalesce(func.sum(D.FeeInvoice.amount - D.FeeInvoice.paid), 0)).scalar() or 0}
    row = D.FinanceReconciliation(id=uid(), tenant_id=TENANT, period_start=datetime.combine(start, datetime.min.time()),
        period_end=datetime.combine(end, datetime.max.time()), opening_balance=0,
        total_collected=float(summary["total_collected"]), total_adjustments=0,
        closing_balance=float(summary["total_collected"]), status="closed",
        notes=body.notes or "", created_by=ctx["sub"])
    s.add(row)
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee.reconciliation.create",
                f"reconciliation:{row.id}", "draft", "closed", row.notes or "Generated reconciliation")
    return {"status": "closed", "reconciliation": {"id": row.id, "status": row.status, "notes": row.notes}}


@router.get("/finance/refunds")
def list_refunds(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "view")[0])
    rows = s.query(D.FinanceRefund).order_by(desc(D.FinanceRefund.created_at)).all()
    return {"refunds": [{
        "id": row.id,
        "invoice_id": row.invoice_id,
        "student_id": row.student_id,
        "amount": row.amount,
        "reason": row.reason,
        "status": row.status,
        "remarks": row.remarks,
        "created_by": row.created_by,
        "approved_by": row.approved_by,
        "executed_by": row.executed_by,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "approved_at": row.approved_at.isoformat() if row.approved_at else "",
        "executed_at": row.executed_at.isoformat() if row.executed_at else "",
    } for row in rows]}


@router.post("/finance/refunds")
def create_refund(body: FinanceRefundIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "view")[0])
    invoice = s.get(D.FeeInvoice, body.invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if float(body.amount or 0) <= 0:
        raise HTTPException(422, "Refund amount must be greater than zero")
    if float(body.amount or 0) > float(invoice.paid or 0):
        raise HTTPException(422, "Refund amount cannot exceed the invoice's paid amount")
    row = D.FinanceRefund(id=uid(), tenant_id=TENANT, invoice_id=invoice.id,
        student_id=invoice.student_id, amount=float(body.amount), reason=body.reason or "",
        status="pending_approval", created_by=ctx["sub"])
    s.add(row)
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee.refund.create",
                f"invoice:{invoice.id}", "pending_approval", "created", f"Refund requested: ₹{body.amount:,.0f}")
    return {"status": "pending_approval", "refund": {"id": row.id, "invoice_id": row.invoice_id, "student_id": row.student_id, "amount": row.amount, "status": row.status, "reason": row.reason}}


@router.post("/finance/refunds/{refund_id}/decision")
def decide_refund(refund_id: str, body: FinanceRefundDecisionIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "finance", "waive", amount=0)
    require(dec)
    refund = s.get(D.FinanceRefund, refund_id)
    if not refund:
        raise HTTPException(404, "Refund request not found")
    if refund.status not in {"pending_approval"}:
        raise HTTPException(409, "Refund request is not pending approval")
    decision = (body.decision or "approved").strip().lower()
    if decision not in {"approved", "rejected"}:
        raise HTTPException(422, "Invalid refund decision")
    refund.status = decision == "approved" and "approved" or "rejected"
    refund.approved_by = ctx["sub"]
    refund.approved_at = datetime.utcnow()
    refund.remarks = body.remarks or ""
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee.refund.approve",
                f"refund:{refund.id}", "pending_approval", refund.status, refund.remarks or "Refund decision recorded")
    return {"status": refund.status, "refund": {"id": refund.id, "status": refund.status, "remarks": refund.remarks}}


@router.post("/finance/refunds/{refund_id}/execute")
def execute_refund(refund_id: str, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "finance", "waive", amount=0)
    require(dec)
    refund = s.get(D.FinanceRefund, refund_id)
    if not refund:
        raise HTTPException(404, "Refund request not found")
    if refund.status != "approved":
        raise HTTPException(409, "Only approved refund requests can be executed")
    invoice = s.get(D.FeeInvoice, refund.invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    amount = float(refund.amount or 0)
    if amount <= 0:
        raise HTTPException(422, "Refund amount must be greater than zero")
    if amount > float(invoice.paid or 0):
        raise HTTPException(409, "Refund amount exceeds the invoice's paid balance")
    invoice.paid = max(float(invoice.paid or 0) - amount, 0)
    invoice.status = "paid" if invoice.paid >= invoice.amount else ("partial" if invoice.paid > 0 else "due")
    refund.status = "executed"
    refund.executed_by = ctx["sub"]
    refund.executed_at = datetime.utcnow()
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee.refund.execute",
                f"refund:{refund.id}", "approved", "executed", f"Executed refund: ₹{amount:,.0f}")
    return {"status": "executed", "refund": {"id": refund.id, "invoice_id": refund.invoice_id, "status": refund.status, "amount": refund.amount}}


@router.get("/finance/vendor-payments")
def list_vendor_payments(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "view")[0])
    rows = s.query(D.VendorPayment).order_by(desc(D.VendorPayment.created_at)).all()
    return {"vendor_payments": [{
        "id": row.id,
        "vendor_name": row.vendor_name,
        "invoice_ref": row.invoice_ref,
        "amount": row.amount,
        "status": row.status,
        "approval_reference": row.approval_reference,
        "notes": row.notes,
        "created_by": row.created_by,
        "approved_by": row.approved_by,
        "paid_by": row.paid_by,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "approved_at": row.approved_at.isoformat() if row.approved_at else "",
        "paid_at": row.paid_at.isoformat() if row.paid_at else "",
    } for row in rows]}


@router.post("/finance/vendor-payments")
def create_vendor_payment(body: VendorPaymentIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "view")[0])
    row = D.VendorPayment(id=uid(), tenant_id=TENANT, vendor_name=body.vendor_name.strip() or "",
        invoice_ref=body.invoice_ref.strip() or "", amount=float(body.amount), notes=body.notes or "",
        status="pending_approval", created_by=ctx["sub"])
    s.add(row)
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee.vendor_payment.create",
                f"vendor:{row.id}", "pending_approval", "created", f"Vendor payment requested: ₹{body.amount:,.0f}")
    return {"status": "pending_approval", "vendor_payment": {"id": row.id, "vendor_name": row.vendor_name, "invoice_ref": row.invoice_ref, "amount": row.amount, "status": row.status, "notes": row.notes}}


@router.post("/finance/vendor-payments/{vendor_payment_id}/approve")
def approve_vendor_payment(vendor_payment_id: str, body: VendorPaymentApprovalIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "finance", "waive", amount=0)
    require(dec)
    row = s.get(D.VendorPayment, vendor_payment_id)
    if not row:
        raise HTTPException(404, "Vendor payment not found")
    if row.status not in {"pending_approval"}:
        raise HTTPException(409, "Vendor payment is not pending approval")
    row.status = "approved"
    row.approval_reference = body.approval_reference.strip() or row.approval_reference or f"VP-{uid()[:8].upper()}"
    row.approved_by = ctx["sub"]
    row.approved_at = datetime.utcnow()
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee.vendor_payment.approve",
                f"vendor:{row.id}", "pending_approval", "approved", row.approval_reference)
    return {"status": "approved", "vendor_payment": {"id": row.id, "status": row.status, "approval_reference": row.approval_reference}}


@router.post("/finance/vendor-payments/{vendor_payment_id}/pay")
def pay_vendor_payment(vendor_payment_id: str, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "finance", "waive", amount=0)
    require(dec)
    row = s.get(D.VendorPayment, vendor_payment_id)
    if not row:
        raise HTTPException(404, "Vendor payment not found")
    if row.status != "approved":
        raise HTTPException(409, "Only approved vendor payments can be paid")
    row.status = "paid"
    row.paid_by = ctx["sub"]
    row.paid_at = datetime.utcnow()
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee.vendor_payment.pay",
                f"vendor:{row.id}", "approved", "paid", f"Vendor payment settled: ₹{row.amount:,.0f}")
    return {"status": "paid", "vendor_payment": {"id": row.id, "status": row.status, "amount": row.amount}}


@router.get("/finance/day-closes")
def list_day_closes(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "view")[0])
    rows = s.query(D.FinanceDayClose).order_by(desc(D.FinanceDayClose.close_date)).all()
    return {"day_closes": [{
        "id": row.id,
        "close_date": row.close_date.isoformat() if row.close_date else "",
        "total_collected": row.total_collected,
        "total_pending_verification": row.total_pending_verification,
        "total_pending_clearance": row.total_pending_clearance,
        "total_adjustments": row.total_adjustments,
        "total_refunds": row.total_refunds,
        "total_vendor_payments": row.total_vendor_payments,
        "opening_balance": row.opening_balance,
        "closing_balance": row.closing_balance,
        "status": row.status,
        "notes": row.notes,
        "created_by": row.created_by,
        "closed_at": row.closed_at.isoformat() if row.closed_at else "",
    } for row in rows]}


@router.post("/finance/day-close")
def create_day_close(body: FinanceDayCloseIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "view")[0])
    close_date = date.today()
    existing = s.query(D.FinanceDayClose).filter(D.FinanceDayClose.close_date == close_date).first()
    if existing:
        existing.notes = body.notes or existing.notes
        existing.status = "closed"
        existing.closed_at = datetime.utcnow()
        s.commit()
        return {"status": "closed", "day_close": {"id": existing.id, "close_date": existing.close_date.isoformat(), "status": existing.status}}

    total_collected = float(s.query(func.coalesce(func.sum(D.Payment.amount), 0)).filter(D.Payment.status == "success").scalar() or 0)
    total_pending_verification = float(s.query(func.coalesce(func.sum(D.Payment.amount), 0)).filter(D.Payment.status == "pending_verification").scalar() or 0)
    total_pending_clearance = float(s.query(func.coalesce(func.sum(D.Payment.amount), 0)).filter(D.Payment.status == "pending_clearance").scalar() or 0)
    total_adjustments = float(s.query(func.coalesce(func.sum(D.FinanceAdjustment.amount), 0)).filter(D.FinanceAdjustment.status == "approved").scalar() or 0)
    total_refunds = float(s.query(func.coalesce(func.sum(D.FinanceRefund.amount), 0)).filter(D.FinanceRefund.status == "executed").scalar() or 0)
    total_vendor_payments = float(s.query(func.coalesce(func.sum(D.VendorPayment.amount), 0)).filter(D.VendorPayment.status == "paid").scalar() or 0)
    opening_balance = total_collected - total_adjustments - total_refunds - total_vendor_payments
    closing_balance = opening_balance
    row = D.FinanceDayClose(id=uid(), tenant_id=TENANT, close_date=close_date,
        total_collected=total_collected, total_pending_verification=total_pending_verification,
        total_pending_clearance=total_pending_clearance, total_adjustments=total_adjustments,
        total_refunds=total_refunds, total_vendor_payments=total_vendor_payments,
        opening_balance=opening_balance, closing_balance=closing_balance,
        status="closed", notes=body.notes or "", created_by=ctx["sub"])
    s.add(row)
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee.day_close",
                f"day_close:{row.id}", "draft", "closed", row.notes or "Closed the day")
    return {"status": "closed", "day_close": {"id": row.id, "close_date": row.close_date.isoformat(), "status": row.status, "closing_balance": row.closing_balance}}


@router.post("/finance/waive")
def waive_fee(body: WaiveIn, ctx=Depends(auth), s=Depends(db)):
    # Waivers are monetary approvals — engine checks the approval limit for scope.
    dec, verb = gate(s, ctx, "finance", "waive", amount=body.amount)
    if dec.outcome == "DENY":
        raise HTTPException(403, dec.reason)
    inv = s.query(D.FeeInvoice).get(body.invoice_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if dec.outcome == "ESCALATE":
        # Record the escalation; do not apply the waiver yet.
        write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee.waive.escalate",
                    f"invoice:{inv.id}", "", "escalated",
                    f"Waiver ₹{body.amount:,.0f} exceeds limit → {dec.escalate_to}")
        return {"status": "escalated", "escalate_to": dec.escalate_to,
                "decision": dec.as_dict()}
    inv.amount = max(0, inv.amount - body.amount)
    inv.status = "waived" if inv.amount <= inv.paid else inv.status
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee.waive",
                f"invoice:{inv.id}", "", "waived", f"Waived ₹{body.amount:,.0f}: {body.reason}")
    return {"status": "waived", "decision": dec.as_dict()}


# --------------------------------------------------------------------------- #
#  FINANCE · Phase 1 fee setup (draft structures only)
# --------------------------------------------------------------------------- #
def _fee_setup_gate(s, ctx, action):
    if action == "view" and ctx["office_n"] in (3, 4, 22, 40):
        require(gate(s, ctx, "finance", "view")[0])
        return
    if ctx["office_n"] != 22:
        raise HTTPException(403, "Only the Finance Manager can manage fee setup")
    require(gate(s, ctx, "finance", action)[0])


def _fee_head_payload(row):
    return {"id": row.id, "code": row.code, "name": row.name, "description": row.description or "",
            "category": row.category, "is_mandatory": row.is_mandatory, "is_active": row.is_active,
            "display_order": row.display_order, "created_at": row.created_at, "updated_at": row.updated_at}


def _fee_structure_payload(s, row):
    years = {x.id: x.name for x in s.query(D.AcademicYear).all()}
    semesters = {x.id: x.name for x in s.query(D.Semester).all()}
    campuses = {x.id: x.name for x in s.query(D.Campus).all()}
    programs = {x.id: x.name for x in s.query(D.Program).all()}
    batches = {x.id: x.name for x in s.query(D.Batch).all()}
    student_types = {x.id: x.name for x in s.query(D.StudentType).all()}
    heads = {x.id: x for x in s.query(D.FeeHead).all()}
    lines = s.query(D.FeeStructureLine).filter(D.FeeStructureLine.fee_structure_id == row.id).order_by(D.FeeStructureLine.fee_head_id, D.FeeStructureLine.installment_no).all()
    line_payloads = [{"id": line.id, "fee_head_id": line.fee_head_id,
                      "fee_head_code": heads.get(line.fee_head_id).code if heads.get(line.fee_head_id) else "",
                      "fee_head_name": heads.get(line.fee_head_id).name if heads.get(line.fee_head_id) else "",
                      "amount": line.amount, "installment_no": line.installment_no,
                      "installment_name": line.installment_name or "", "due_date": line.due_date,
                      "is_mandatory": line.is_mandatory, "description": line.description or ""} for line in lines]
    return {"id": row.id, "name": row.name, "code": row.code, "academic_year_id": row.academic_year_id,
            "academic_year": years.get(row.academic_year_id, ""), "semester_id": row.semester_id,
            "semester": semesters.get(row.semester_id, ""), "campus_id": row.campus_id,
            "campus": campuses.get(row.campus_id, ""), "program_id": row.program_id,
            "program": programs.get(row.program_id, ""), "batch_id": row.batch_id,
            "batch": batches.get(row.batch_id, ""), "student_type_id": row.student_type_id,
            "student_type": student_types.get(row.student_type_id, ""), "version": row.version,
            "status": row.status, "effective_from": row.effective_from, "effective_to": row.effective_to,
            "description": row.description or "", "notes": row.notes or "", "created_at": row.created_at,
            "updated_at": row.updated_at,
            "gross_total": sum((Decimal(str(line.amount or 0)) for line in lines), Decimal("0")),
            "lines": line_payloads}


def _sync_fee_structure_workflow_status(s, rows):
    """Keep fee setup status aligned with its completed approval workflow.

    This also repairs structures approved before workflow/status synchronization
    was added. Published structures are never moved backwards.
    """
    workflow_ids = {row.workflow_id for row in rows if row.workflow_id}
    if not workflow_ids:
        return
    workflows = {row.id: row for row in s.query(WorkflowInstance).filter(WorkflowInstance.id.in_(workflow_ids)).all()}
    changed = False
    for row in rows:
        workflow = workflows.get(row.workflow_id)
        if not workflow or row.status == "PUBLISHED":
            continue
        target = "APPROVED" if workflow.state == "approved" else ("REJECTED" if workflow.state == "rejected" else None)
        if target and row.status != target:
            row.status = target
            row.updated_at = datetime.utcnow()
            changed = True
    if changed:
        s.commit()


class FeeHeadIn(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    category: str = "OTHER"
    is_mandatory: bool = True
    display_order: int = 0


class FeeHeadStatusIn(BaseModel):
    is_active: bool


class FeeStructureLineIn(BaseModel):
    fee_head_id: str
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    installment_no: int = Field(default=1, ge=1)
    installment_name: str = ""
    due_date: date | None = None
    is_mandatory: bool = True
    description: str = ""

    @field_validator("due_date", mode="before")
    @classmethod
    def blank_due_date_is_null(cls, value):
        return None if value == "" else value


class FeeStructureIn(BaseModel):
    name: str = Field(default="", max_length=160)
    code: str = Field(default="", max_length=80)
    academic_year_id: str
    semester_id: str
    campus_id: str
    program_id: str
    batch_id: str
    student_type_id: str
    version: int = Field(default=1, ge=1)
    effective_from: date | None = None
    effective_to: date | None = None
    description: str = ""
    notes: str = ""
    lines: list[FeeStructureLineIn] = Field(min_length=1)

    @field_validator("effective_from", "effective_to", mode="before")
    @classmethod
    def blank_effective_date_is_null(cls, value):
        return None if value == "" else value


def _validate_fee_structure(s, body, structure_id: str | None = None):
    references = ((D.AcademicYear, body.academic_year_id, "Academic year"), (D.Semester, body.semester_id, "Semester"),
                  (D.Campus, body.campus_id, "Campus"), (D.Program, body.program_id, "Program"),
                  (D.Batch, body.batch_id, "Batch"), (D.StudentType, body.student_type_id, "Student type"))
    for model, ref_id, label in references:
        item = s.get(model, ref_id)
        if not item or getattr(item, "is_active", True) is False:
            raise HTTPException(422, f"{label} does not exist or is inactive")
    semester = s.get(D.Semester, body.semester_id)
    if semester.academic_year_id != body.academic_year_id:
        raise HTTPException(422, "Semester does not belong to the selected academic year")
    if body.effective_from and body.effective_to and body.effective_to < body.effective_from:
        raise HTTPException(422, "Effective-to date cannot be before effective-from date")
    seen = set()
    for line in body.lines:
        key = (line.fee_head_id, line.installment_no)
        if key in seen:
            raise HTTPException(422, "Duplicate fee head installment in this structure")
        seen.add(key)
        head = s.get(D.FeeHead, line.fee_head_id)
        if not head:
            raise HTTPException(422, "Fee head does not exist")
        if not head.is_active:
            raise HTTPException(422, f"Inactive fee head '{head.code}' cannot be used")
    duplicate = s.query(D.FeeStructure).filter(
        D.FeeStructure.academic_year_id == body.academic_year_id, D.FeeStructure.semester_id == body.semester_id,
        D.FeeStructure.campus_id == body.campus_id, D.FeeStructure.program_id == body.program_id,
        D.FeeStructure.batch_id == body.batch_id, D.FeeStructure.student_type_id == body.student_type_id,
        D.FeeStructure.version == body.version).first()
    if duplicate and duplicate.id != structure_id:
        raise HTTPException(409, "A fee structure already exists for this context and version")


@router.get("/fees/reference-data")
def fee_reference_data(ctx=Depends(auth), s=Depends(db)):
    _fee_setup_gate(s, ctx, "view")
    return {"academic_years": [{"id": x.id, "name": x.name} for x in s.query(D.AcademicYear).filter(D.AcademicYear.is_active == True).all()],
            "semesters": [{"id": x.id, "academic_year_id": x.academic_year_id, "name": x.name, "sequence": x.sequence} for x in s.query(D.Semester).filter(D.Semester.is_active == True).all()],
            "campuses": [{"id": x.id, "name": x.name} for x in s.query(D.Campus).filter(D.Campus.is_active == True).all()],
            "programs": [{"id": x.id, "name": x.name, "code": x.code} for x in s.query(D.Program).all()],
            "batches": [{"id": x.id, "name": x.name} for x in s.query(D.Batch).filter(D.Batch.is_active == True).all()],
            "student_types": [{"id": x.id, "name": x.name} for x in s.query(D.StudentType).filter(D.StudentType.is_active == True).all()]}


@router.get("/fees/heads")
def list_fee_heads(include_inactive: bool = False, ctx=Depends(auth), s=Depends(db)):
    _fee_setup_gate(s, ctx, "view")
    query = s.query(D.FeeHead)
    if not include_inactive: query = query.filter(D.FeeHead.is_active == True)
    return {"heads": [_fee_head_payload(x) for x in query.order_by(D.FeeHead.display_order, D.FeeHead.name).all()]}


@router.post("/fees/heads")
def create_fee_head(body: FeeHeadIn, ctx=Depends(auth), s=Depends(db)):
    _fee_setup_gate(s, ctx, "create")
    code = body.code.strip().upper(); name = body.name.strip()
    if s.query(D.FeeHead).filter(D.FeeHead.code == code).first(): raise HTTPException(409, "Fee head code already exists")
    now = datetime.utcnow(); row = D.FeeHead(id=uid(), tenant_id=TENANT, code=code, name=name, description=body.description,
        category=body.category, is_mandatory=body.is_mandatory, display_order=body.display_order, created_at=now, updated_at=now, created_by=ctx["sub"], updated_by=ctx["sub"])
    s.add(row); s.commit(); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee_head.create", f"fee_head:{row.id}", "", "active", f"Created fee head {code}")
    return {"head": _fee_head_payload(row)}


@router.put("/fees/heads/{head_id}")
def update_fee_head(head_id: str, body: FeeHeadIn, ctx=Depends(auth), s=Depends(db)):
    _fee_setup_gate(s, ctx, "edit"); row = s.get(D.FeeHead, head_id)
    if not row: raise HTTPException(404, "Fee head not found")
    code = body.code.strip().upper(); existing = s.query(D.FeeHead).filter(D.FeeHead.code == code, D.FeeHead.id != head_id).first()
    if existing: raise HTTPException(409, "Fee head code already exists")
    row.code, row.name, row.description, row.category = code, body.name.strip(), body.description, body.category
    row.is_mandatory, row.display_order, row.updated_by, row.updated_at = body.is_mandatory, body.display_order, ctx["sub"], datetime.utcnow()
    s.commit(); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee_head.update", f"fee_head:{row.id}", "", "updated", f"Updated fee head {code}")
    return {"head": _fee_head_payload(row)}


@router.patch("/fees/heads/{head_id}/status")
def set_fee_head_status(head_id: str, body: FeeHeadStatusIn, ctx=Depends(auth), s=Depends(db)):
    _fee_setup_gate(s, ctx, "edit"); row = s.get(D.FeeHead, head_id)
    if not row: raise HTTPException(404, "Fee head not found")
    row.is_active, row.updated_by, row.updated_at = body.is_active, ctx["sub"], datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee_head.status", f"fee_head:{row.id}", "", "active" if body.is_active else "inactive", f"Changed fee head status")
    return {"head": _fee_head_payload(row)}


@router.get("/fee-structures")
def list_fee_structures(academic_year_id: str = "", semester_id: str = "", campus_id: str = "", program_id: str = "", batch_id: str = "", student_type_id: str = "", status: str = "", ctx=Depends(auth), s=Depends(db)):
    _fee_setup_gate(s, ctx, "view"); query = s.query(D.FeeStructure)
    for field, value in ((D.FeeStructure.academic_year_id, academic_year_id), (D.FeeStructure.semester_id, semester_id), (D.FeeStructure.campus_id, campus_id), (D.FeeStructure.program_id, program_id), (D.FeeStructure.batch_id, batch_id), (D.FeeStructure.student_type_id, student_type_id), (D.FeeStructure.status, status)):
        if value: query = query.filter(field == value)
    rows = query.order_by(desc(D.FeeStructure.updated_at)).all()
    _sync_fee_structure_workflow_status(s, rows)
    return {"structures": [_fee_structure_payload(s, x) for x in rows]}


@router.get("/fee-structures/{structure_id}")
def get_fee_structure(structure_id: str, ctx=Depends(auth), s=Depends(db)):
    _fee_setup_gate(s, ctx, "view"); row = s.get(D.FeeStructure, structure_id)
    if not row: raise HTTPException(404, "Fee structure not found")
    _sync_fee_structure_workflow_status(s, [row])
    return {"structure": _fee_structure_payload(s, row)}


@router.get("/fee-structures/{structure_id}/affected-students")
def fee_structure_affected_students(structure_id: str, ctx=Depends(auth), s=Depends(db)):
    """Students and invoices created by a published fee structure."""
    _fee_setup_gate(s, ctx, "view")
    row = s.get(D.FeeStructure, structure_id)
    if not row:
        raise HTTPException(404, "Fee structure not found")
    students = {student.id: student for student in s.query(D.Student).all()}
    invoices = (s.query(D.FeeInvoice)
                .filter(D.FeeInvoice.fee_structure_id == row.id)
                .order_by(D.FeeInvoice.student_id, D.FeeInvoice.due_date, D.FeeInvoice.id)
                .all())
    grouped = {}
    for invoice in invoices:
        student = students.get(invoice.student_id)
        if not student:
            continue
        item = grouped.setdefault(student.id, {
            "student_id": student.id, "roll_no": student.roll_no, "name": student.name,
            "email": student.email, "section": student.section, "semester": student.semester,
            "student_type": student.student_type, "invoiced": 0, "paid": 0,
            "balance": 0, "invoice_count": 0, "status": "due",
        })
        item["invoiced"] += float(invoice.amount or 0)
        item["paid"] += float(invoice.paid or 0)
        item["balance"] += float((invoice.amount or 0) - (invoice.paid or 0))
        item["invoice_count"] += 1
    for item in grouped.values():
        item["status"] = "paid" if item["balance"] <= 0 else ("partial" if item["paid"] else "due")
    return {"structure": _fee_structure_payload(s, row), "students": list(grouped.values()),
            "student_count": len(grouped), "invoice_count": len(invoices)}


def _save_fee_structure(s, row, body, ctx):
    _validate_fee_structure(s, body, row.id if row else None)
    now = datetime.utcnow()
    program = s.get(D.Program, body.program_id)
    year = s.get(D.AcademicYear, body.academic_year_id)
    semester = s.get(D.Semester, body.semester_id)
    batch = s.get(D.Batch, body.batch_id)
    student_type = s.get(D.StudentType, body.student_type_id)
    generated_name = f"{program.code if program else body.program_id} · {year.name if year else body.academic_year_id} · {semester.name if semester else body.semester_id} · {student_type.name if student_type else body.student_type_id}"
    generated_code = slug(f"{program.code if program else body.program_id}-{batch.name if batch else body.batch_id}-{semester.sequence if semester else body.semester_id}-{student_type.name if student_type else body.student_type_id}-v{body.version}").upper()
    name = (body.name or "").strip() or generated_name
    code = (body.code or "").strip().upper() or generated_code
    if not row and s.query(D.FeeStructure).filter(D.FeeStructure.code == code).first():
        code = f"{code}-{uid()[:4].upper()}"
    if not row:
        row = D.FeeStructure(id=uid(), tenant_id=TENANT, status="DRAFT", created_by=ctx["sub"], created_at=now)
        s.add(row)
    for field in ("name", "code", "academic_year_id", "semester_id", "campus_id", "program_id", "batch_id", "student_type_id", "version", "effective_from", "effective_to", "description", "notes"):
        setattr(row, field, getattr(body, field))
    row.name, row.code = name, code
    row.updated_by, row.updated_at = ctx["sub"], now
    s.flush()
    s.query(D.FeeStructureLine).filter(D.FeeStructureLine.fee_structure_id == row.id).delete(synchronize_session=False)
    for line in body.lines:
        s.add(D.FeeStructureLine(id=uid(), fee_structure_id=row.id, fee_head_id=line.fee_head_id, amount=line.amount,
              installment_no=line.installment_no, installment_name=line.installment_name, due_date=line.due_date,
              is_mandatory=line.is_mandatory, description=line.description, created_at=now, updated_at=now))
    return row


@router.post("/fee-structures")
def create_fee_structure(body: FeeStructureIn, ctx=Depends(auth), s=Depends(db)):
    _fee_setup_gate(s, ctx, "create")
    try:
        row = _save_fee_structure(s, None, body, ctx); s.commit()
    except HTTPException: s.rollback(); raise
    except Exception: s.rollback(); raise HTTPException(409, "Could not save fee structure; check uniqueness and references")
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee_structure.create", f"fee_structure:{row.id}", "", "DRAFT", f"Created draft {row.code}")
    return {"structure": _fee_structure_payload(s, row)}


@router.put("/fee-structures/{structure_id}")
def update_fee_structure(structure_id: str, body: FeeStructureIn, ctx=Depends(auth), s=Depends(db)):
    _fee_setup_gate(s, ctx, "edit"); row = s.get(D.FeeStructure, structure_id)
    if not row: raise HTTPException(404, "Fee structure not found")
    if row.status != "DRAFT": raise HTTPException(409, "Only DRAFT fee structures can be edited")
    try:
        row = _save_fee_structure(s, row, body, ctx); s.commit()
    except HTTPException: s.rollback(); raise
    except Exception: s.rollback(); raise HTTPException(409, "Could not update fee structure; check uniqueness and references")
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee_structure.update", f"fee_structure:{row.id}", "DRAFT", "DRAFT", f"Updated draft {row.code}")
    return {"structure": _fee_structure_payload(s, row)}


@router.post("/fee-structures/{structure_id}/submit")
def submit_fee_structure(structure_id: str, ctx=Depends(auth), s=Depends(db)):
    _fee_setup_gate(s, ctx, "edit")
    row = s.get(D.FeeStructure, structure_id)
    if not row:
        raise HTTPException(404, "Fee structure not found")
    if row.status != "DRAFT":
        raise HTTPException(409, "Only DRAFT fee structures can be submitted")
    if not s.query(D.FeeStructureLine).filter(D.FeeStructureLine.fee_structure_id == row.id).first():
        raise HTTPException(422, "A fee structure must contain at least one fee line")
    wf = WorkflowInstance(id=uid(), tenant_id=TENANT, process_key="fee_structure",
                          label="Fee structure approval", office_n=22,
                          title=f"Approve fee structure: {row.name}", state="submitted",
                          initiator_id=ctx["sub"], initiator_name=actor_name(s, ctx),
                          # A fee structure applies to its selected campus.  The Finance
                          # Manager may have university scope, but the Principal must be
                          # able to approve the campus-level request.
                          current_stage=1, scope_level="campus")
    s.add(wf); s.flush(); row.workflow_id = wf.id; row.status = "SUBMITTED"; row.updated_by = ctx["sub"]; row.updated_at = datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee_structure.submit", f"fee_structure:{row.id}", "DRAFT", "SUBMITTED", "Submitted for approval")
    return {"structure": _fee_structure_payload(s, row), "workflow_id": wf.id}


@router.post("/fee-structures/{structure_id}/publish")
def publish_fee_structure(structure_id: str, ctx=Depends(auth), s=Depends(db)):
    """Publish a reviewed structure and apply its installments to matching students.

    Existing invoices linked to this structure are reused, so retries cannot create duplicates.
    """
    _fee_setup_gate(s, ctx, "edit")
    row = s.get(D.FeeStructure, structure_id)
    if not row:
        raise HTTPException(404, "Fee structure not found")
    if row.status == "DRAFT":
        raise HTTPException(409, "Fee structure must be approved before publishing")
    if row.status == "PUBLISHED":
        published_students = (s.query(D.Student).join(D.FeeInvoice, D.FeeInvoice.student_id == D.Student.id)
                              .filter(D.FeeInvoice.fee_structure_id == row.id).distinct().all())
        accounts_created = sum(1 for student in published_students if _ensure_student_portal_account(s, student))
        if accounts_created:
            s.commit()
        return {"structure": _fee_structure_payload(s, row), "matched_students": len(published_students),
                "invoices_created": 0, "student_accounts_created": accounts_created}
    if row.status != "APPROVED":
        raise HTTPException(409, "Only APPROVED fee structures can be published")
    lines = s.query(D.FeeStructureLine).filter(D.FeeStructureLine.fee_structure_id == row.id).all()
    if not lines:
        raise HTTPException(422, "A fee structure must contain at least one fee line")
    students = s.query(D.Student).filter(
        D.Student.program_id == row.program_id,
        D.Student.batch == s.get(D.Batch, row.batch_id).name,
        D.Student.campus == s.get(D.Campus, row.campus_id).name,
        D.Student.student_type == s.get(D.StudentType, row.student_type_id).name,
        D.Student.status == "active",
    ).all()
    created = 0
    accounts_created = 0
    for student in students:
        accounts_created += int(_ensure_student_portal_account(s, student))
        for line in lines:
            existing = s.query(D.FeeInvoice).filter(
                D.FeeInvoice.student_id == student.id,
                D.FeeInvoice.fee_structure_id == row.id,
                D.FeeInvoice.term == f"{row.academic_year_id}:{row.semester_id}:line:{line.id}",
            ).first()
            if existing:
                continue
            s.add(D.FeeInvoice(id=uid(), tenant_id=TENANT, student_id=student.id,
                               term=f"{row.academic_year_id}:{row.semester_id}:line:{line.id}",
                               amount=float(line.amount), paid=0, status="due",
                               due_date=line.due_date, fee_structure_id=row.id))
            created += 1
    row.status = "PUBLISHED"
    row.updated_by, row.updated_at = ctx["sub"], datetime.utcnow()
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee_structure.publish",
                f"fee_structure:{row.id}", "DRAFT", "PUBLISHED",
                f"Applied fee structure to {len(students)} matching students")
    return {"structure": _fee_structure_payload(s, row), "matched_students": len(students),
            "invoices_created": created, "student_accounts_created": accounts_created}


# --------------------------------------------------------------------------- #
#  LIBRARY
# --------------------------------------------------------------------------- #
@router.get("/library/books")
def list_books(q: str = "", ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "library", "view")[0])
    query = s.query(D.Book)
    if q:
        like = f"%{q}%"
        query = query.filter((D.Book.title.ilike(like)) | (D.Book.author.ilike(like)))
    rows = query.all()
    return {"books": [{"id": b.id, "title": b.title, "author": b.author,
                       "category": b.category, "total": b.copies_total,
                       "available": b.copies_available} for b in rows],
            "can_issue": can(s, ctx, "library", "issue"),
            "can_add": can(s, ctx, "library", "add_book")}


@router.get("/library/loans")
def list_loans(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "library", "view")[0])
    book_map = {b.id: b.title for b in s.query(D.Book).all()}
    rows = s.query(D.BookLoan).filter(D.BookLoan.returned == False).all()
    out = []
    for l in rows:
        overdue = l.due_on and l.due_on < date.today()
        out.append({"id": l.id, "book": book_map.get(l.book_id, ""),
                    "borrower": l.borrower_name or l.borrower,
                    "issued_on": l.issued_on.isoformat() if l.issued_on else "",
                    "due_on": l.due_on.isoformat() if l.due_on else "",
                    "overdue": bool(overdue)})
    return {"loans": out, "can_return": can(s, ctx, "library", "return")}


class IssueBookIn(BaseModel):
    book_id: str
    borrower: str
    borrower_name: str = ""


@router.post("/library/issue")
def issue_book(body: IssueBookIn, ctx=Depends(auth), s=Depends(db)):
    dec, verb = gate(s, ctx, "library", "issue")
    require(dec)
    b = s.query(D.Book).get(body.book_id)
    if not b:
        raise HTTPException(404, "Book not found")
    if b.copies_available < 1:
        raise HTTPException(409, "No copies available")
    b.copies_available -= 1
    student = (s.query(D.Student)
               .filter(or_(D.Student.id == body.borrower, D.Student.roll_no == body.borrower))
               .first())
    s.add(D.BookLoan(id=uid(), tenant_id=TENANT, book_id=b.id, borrower=body.borrower,
                     student_id=student.id if student else None,
                     borrower_name=body.borrower_name, issued_on=date.today(),
                     due_on=date.today() + timedelta(days=14), returned=False))
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "library.issue",
                f"book:{b.id}", "", "issued", f"Issued '{b.title}' to {body.borrower}")
    return {"status": "issued", "decision": dec.as_dict()}


@router.post("/library/return/{loan_id}")
def return_book(loan_id: str, ctx=Depends(auth), s=Depends(db)):
    dec, verb = gate(s, ctx, "library", "return")
    require(dec)
    l = s.query(D.BookLoan).get(loan_id)
    if not l or l.returned:
        raise HTTPException(404, "Loan not found or already returned")
    l.returned = True
    b = s.query(D.Book).get(l.book_id)
    if b:
        b.copies_available += 1
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "library.return",
                f"loan:{loan_id}", "issued", "returned", "Book returned")
    return {"status": "returned", "decision": dec.as_dict()}


# --------------------------------------------------------------------------- #
#  HR: leave + jobs
# --------------------------------------------------------------------------- #
@router.get("/hr/leave")
def list_leave(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "hr", "view")[0])
    rows = s.query(D.LeaveRequest).filter(D.LeaveRequest.tenant_id == ctx.get("tenant_id", TENANT)).order_by(desc(D.LeaveRequest.id)).all()
    return {"leave": [{"id": l.id, "staff": l.staff_name, "kind": l.kind,
                       "from": l.from_date.isoformat(), "to": l.to_date.isoformat(),
                       "days": l.days, "reason": l.reason, "status": l.status}
                      for l in rows],
            "can_approve": can(s, ctx, "hr", "approve_leave")}


@router.get("/hr/jobs")
def list_jobs(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "hr", "view")[0])
    rows = s.query(D.JobPosting).filter(D.JobPosting.tenant_id == ctx.get("tenant_id", TENANT)).all()
    return {"jobs": [{"id": j.id, "title": j.title, "dept": j.dept, "kind": j.kind,
                      "openings": j.openings, "status": j.status} for j in rows],
              "can_post": can(s, ctx, "hr", "post_job")}


@router.get("/faculty-staff")
def faculty_staff(q: str = "", dept: str = "", kind: str = "", designation: str = "", status: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=10, le=100), ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "hr", "view")[0])
    query = s.query(D.StaffMember)
    if q:
        like = f"%{q}%"; query = query.filter((D.StaffMember.name.ilike(like)) | (D.StaffMember.emp_id.ilike(like)) | (D.StaffMember.email.ilike(like)))
    if dept:
        department = s.query(D.Department).filter(D.Department.code == dept).first()
        if department: query = query.filter(D.StaffMember.dept_id == department.id)
    today = date.today()
    on_leave_ids = [row[0] for row in s.query(D.LeaveRequest.staff_id).filter(D.LeaveRequest.status == "approved", D.LeaveRequest.from_date <= today, D.LeaveRequest.to_date >= today).all()]
    if kind == "teaching": query = query.filter(D.StaffMember.designation.ilike("%professor%"))
    if kind == "non_teaching": query = query.filter(~D.StaffMember.designation.ilike("%professor%"))
    if kind == "on_leave": query = query.filter(D.StaffMember.id.in_(on_leave_ids))
    if designation: query = query.filter(D.StaffMember.designation == designation)
    if status: query = query.filter(D.StaffMember.status == status)
    total = query.count(); rows = query.order_by(D.StaffMember.emp_id).offset((page - 1) * page_size).limit(page_size).all()
    departments = {row.id: row for row in s.query(D.Department).all()}
    all_rows = s.query(D.StaffMember).all()
    teaching = sum(1 for row in all_rows if "professor" in (row.designation or "").lower())
    return {"staff": [{"id": row.id, "employee_id": row.emp_id, "name": row.name, "email": row.email, "department": departments[row.dept_id].name if row.dept_id in departments else "Administration", "department_code": departments[row.dept_id].code if row.dept_id in departments else "", "designation": row.designation, "type": "Teaching" if "professor" in (row.designation or "").lower() else "Non-Teaching", "status": row.status, "campus": row.campus, "on_leave": row.id in on_leave_ids} for row in rows], "total": total, "page": page, "page_size": page_size, "total_pages": max(1, (total + page_size - 1) // page_size), "summary": {"total": len(all_rows), "teaching": teaching, "non_teaching": len(all_rows)-teaching, "on_leave": len(on_leave_ids), "vacancies": sum(job.openings for job in s.query(D.JobPosting).filter(D.JobPosting.status == "open").all())}, "departments": [{"code": d.code, "name": d.name} for d in departments.values() if s.query(D.StaffMember).filter(D.StaffMember.dept_id == d.id).count()], "designations": sorted(set(row.designation for row in all_rows if row.designation)), "statuses": sorted(set(row.status for row in all_rows if row.status))}


@router.get("/faculty-staff/{staff_id}")
def faculty_profile(staff_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "hr", "view")[0])
    row = s.query(D.StaffMember).get(staff_id)
    if not row: raise HTTPException(404, "Faculty or staff member not found")
    department = s.query(D.Department).get(row.dept_id)
    sections = s.query(D.Section).filter(D.Section.faculty_person_id == row.id).all()
    students = sum(s.query(D.Enrollment).filter(D.Enrollment.section_id == section.id, D.Enrollment.status == "enrolled").count() for section in sections)
    leave = s.query(D.LeaveRequest).filter(D.LeaveRequest.staff_id == row.id).order_by(D.LeaveRequest.from_date.desc()).all()
    return {"staff": {"id": row.id, "employee_id": row.emp_id, "name": row.name, "email": row.email, "department": department.name if department else "Administration", "designation": row.designation, "type": "Teaching" if "professor" in (row.designation or "").lower() else "Non-Teaching", "status": row.status, "campus": row.campus, "date_joined": row.date_joined.isoformat() if row.date_joined else None, "classes": len(sections), "students": students}, "sections": [{"code": section.section_code, "term": section.term, "schedule": section.schedule, "room": section.room} for section in sections], "leave": [{"kind": item.kind, "from": item.from_date.isoformat(), "to": item.to_date.isoformat(), "days": item.days, "status": item.status, "reason": item.reason} for item in leave]}


class LeaveDecisionIn(BaseModel):
    leave_id: str
    action: str  # approve / reject


@router.post("/hr/leave/decide")
def decide_leave(body: LeaveDecisionIn, ctx=Depends(auth), s=Depends(db)):
    act = "approve_leave" if body.action == "approve" else "reject_leave"
    dec, verb = gate(s, ctx, "hr", act)
    require(dec)
    l = s.query(D.LeaveRequest).get(body.leave_id)
    if not l:
        raise HTTPException(404, "Leave request not found")
    l.status = "approved" if body.action == "approve" else "rejected"
    l.decided_by = actor_name(s, ctx)
    s.commit()
    write_audit(s, ctx["sub"], l.decided_by, ctx["office_n"], f"leave.{body.action}",
                f"leave:{l.id}", "pending", l.status, f"{body.action} {l.staff_name}'s leave")
    return {"status": l.status, "decision": dec.as_dict()}


# --------------------------------------------------------------------------- #
#  PROCUREMENT / ASSETS
# --------------------------------------------------------------------------- #
@router.get("/assets")
def list_assets(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "assets", "view")[0])
    rows = s.query(D.Asset).filter(D.Asset.tenant_id == ctx.get("tenant_id", TENANT)).all()
    return {"assets": [{"id": a.id, "tag": a.tag, "name": a.name, "category": a.category,
                        "location": a.location, "status": a.status, "value": a.value}
                       for a in rows],
            "can_add": can(s, ctx, "assets", "add")}


# --------------------------------------------------------------------------- #
#  HOSTEL / TRANSPORT
# --------------------------------------------------------------------------- #
@router.get("/hostel")
def hostel(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "hostel", "view")[0])
    rooms = s.query(D.HostelRoom).all()
    allocs = s.query(D.HostelAllocation).filter(D.HostelAllocation.status == "requested").all()
    cap = sum(r.capacity for r in rooms)
    occ = sum(r.occupied for r in rooms)
    return {"summary": {"rooms": len(rooms), "capacity": cap, "occupied": occ,
                        "vacant": cap - occ},
            "requests": [{"id": a.id, "student": a.student_name, "status": a.status}
                         for a in allocs],
            "can_allocate": can(s, ctx, "hostel", "allocate")}


@router.post("/hostel/allocate/{alloc_id}")
def allocate_hostel(alloc_id: str, ctx=Depends(auth), s=Depends(db)):
    dec, verb = gate(s, ctx, "hostel", "allocate")
    require(dec)
    a = s.query(D.HostelAllocation).get(alloc_id)
    if not a:
        raise HTTPException(404, "Request not found")
    a.status = "allocated"
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "hostel.allocate",
                f"alloc:{alloc_id}", "requested", "allocated", f"Allocated room to {a.student_name}")
    return {"status": "allocated", "decision": dec.as_dict()}


class TransportRouteIn(BaseModel):
    name: str
    route_code: str = ""
    vehicle_no: str = ""
    seats: int = Field(40, ge=1, le=200)

class TransportStopIn(BaseModel):
    route_id: str
    name: str
    sequence: int = Field(1, ge=1)
    address: str = ""
    pickup_time: str = ""
    drop_time: str = ""
    latitude: float | None = None
    longitude: float | None = None

class TransportVehicleIn(BaseModel):
    number: str = ""
    vehicle_number: str = ""
    kind: str = "Bus"
    capacity: int = Field(40, ge=1, le=200)
    status: str = "available"
    driver_id: str | None = None

class TransportDriverIn(BaseModel):
    name: str
    employee_id: str = ""
    phone: str = ""
    license_no: str = ""
    license_number: str = ""
    license_expiry: date | None = None

class TransportRequestIn(BaseModel):
    route_id: str
    stop_id: str = ""
    pickup_stop_id: str = ""

class TransportAllocationIn(BaseModel):
    student_id: str
    route_id: str
    stop_id: str = ""
    pickup_stop_id: str = ""
    vehicle_id: str
    driver_id: str | None = None

def _transport_bundle(s):
    routes = s.query(D.TransportRoute).filter(D.TransportRoute.status != "inactive").all()
    vehicles = s.query(D.TransportVehicle).all()
    drivers = s.query(D.TransportDriver).all()
    reqs = s.query(D.TransportRequest).order_by(desc(D.TransportRequest.created_at)).all()
    allocs = s.query(D.TransportAllocation).filter(D.TransportAllocation.status == "active").all()
    students = s.query(D.Student).filter(D.Student.status == "active").all()
    student_map = {x.id: x for x in students}
    route_map = {x.id: x for x in routes}
    vehicle_map = {x.id: x for x in vehicles}
    driver_map = {x.id: x for x in drivers}
    def stop_id(body): return body.stop_id or body.pickup_stop_id
    def allocation_driver(a):
        vehicle = vehicle_map.get(a.vehicle_id)
        driver_id = a.driver_id or (vehicle.driver_id if vehicle else None)
        return driver_id, driver_map.get(driver_id)
    def allocation_payload(a):
        student = student_map.get(a.student_id)
        vehicle = vehicle_map.get(a.vehicle_id)
        driver_id, driver = allocation_driver(a)
        stop = s.get(D.TransportStop, a.stop_id)
        route = route_map.get(a.route_id)
        return {"id": a.id, "student_id": a.student_id, "student_name": student.name if student else a.student_id,
                "roll_no": student.roll_no if student else "", "route_id": a.route_id,
                "route": route.name if route else a.route_id, "stop_id": a.stop_id,
                "pickup_stop_id": a.stop_id, "pickup": stop.name if stop else "",
                "vehicle_id": a.vehicle_id, "vehicle": vehicle.number if vehicle else a.vehicle_id,
                "driver_id": driver_id, "driver": driver.name if driver else "", "status": a.status}
    return {
        "routes": [{"id": r.id, "name": r.name, "route_code": r.id[:6].upper(), "status": "ACTIVE", "vehicle_no": r.vehicle_no, "seats": r.seats,
                    "taken": sum(a.vehicle_id == r.vehicle_no for a in allocs),
                    "stops": [{"id": x.id, "name": x.name, "sequence": x.sequence, "address": x.address,
                               "pickup_time": x.pickup_time, "drop_time": x.drop_time,
                               "latitude": x.latitude, "longitude": x.longitude}
                              for x in s.query(D.TransportStop).filter(D.TransportStop.route_id == r.id).order_by(D.TransportStop.sequence).all()]}
                   for r in routes],
        "vehicles": [{"id": v.id, "number": v.number, "vehicle_number": v.number, "kind": v.kind, "vehicle_type": v.kind, "capacity": v.capacity,
                      "status": v.status, "occupied": sum(a.vehicle_id == v.id for a in allocs),
                      "driver_id": v.driver_id} for v in vehicles],
        "drivers": [{"id": d.id, "name": d.name, "employee_id": d.employee_id, "phone": d.phone,
                     "license_no": d.license_no, "license_expiry": d.license_expiry.isoformat() if d.license_expiry else "",
                     "status": d.status} for d in drivers],
        "requests": [{"id": q.id, "student_id": q.student_id, "student_name": (s.get(D.Student, q.student_id).name if s.get(D.Student, q.student_id) else q.student_id), "student": (s.get(D.Student, q.student_id).name if s.get(D.Student, q.student_id) else q.student_id),
                      "route_id": q.route_id, "stop_id": q.stop_id, "pickup_stop_id": q.stop_id, "status": q.status.upper()} for q in reqs],
        "allocations": [allocation_payload(a) for a in allocs],
        "students": [{"id": x.id, "roll_no": x.roll_no, "name": x.name} for x in students],
    }

@router.get("/transport")
def transport(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "transport", "view")[0])
    return _transport_bundle(s)

@router.post("/transport/routes")
def create_transport_route(body: TransportRouteIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "add_route"); require(dec)
    row = D.TransportRoute(id=uid(), tenant_id=TENANT, name=body.name, vehicle_no=body.vehicle_no, seats=body.seats, status="active")
    s.add(row); s.commit(); return {"id": row.id, "decision": dec.as_dict()}

@router.post("/transport/stops")
def create_transport_stop(body: TransportStopIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "add_route"); require(dec)
    if not s.get(D.TransportRoute, body.route_id): raise HTTPException(404, "Route not found")
    row = D.TransportStop(id=uid(), tenant_id=TENANT, **body.model_dump())
    s.add(row); s.commit(); return {"id": row.id, "decision": dec.as_dict()}

@router.post("/transport/vehicles")
def create_transport_vehicle(body: TransportVehicleIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "assign"); require(dec)
    number = body.number or body.vehicle_number
    if not number: raise HTTPException(422, "Vehicle number is required")
    if s.query(D.TransportVehicle).filter(D.TransportVehicle.number == number).first(): raise HTTPException(409, "Vehicle number already exists")
    if body.driver_id and not s.get(D.TransportDriver, body.driver_id):
        raise HTTPException(404, "Driver not found")
    row = D.TransportVehicle(id=uid(), tenant_id=TENANT, number=number, kind=body.kind, capacity=body.capacity, status=(body.status or "available").lower(), driver_id=body.driver_id); s.add(row); s.commit(); return {"id": row.id, "decision": dec.as_dict()}

@router.post("/transport/drivers")
def create_transport_driver(body: TransportDriverIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "assign"); require(dec)
    phone = body.phone.strip()
    if not phone:
        raise HTTPException(422, "Driver phone number is required for login")
    username = phone.replace(" ", "")
    if s.query(User).filter(func.lower(User.username) == username.lower()).first():
        raise HTTPException(409, "A login account already exists for this phone number")
    driver_id, person_id, user_id = uid(), uid(), uid()
    s.add(Person(id=person_id, tenant_id=TENANT, name=body.name.strip(), email=f"{username}@icms.edu", contact=phone))
    s.add(User(id=user_id, tenant_id=TENANT, person_id=person_id, username=username,
               password_hash=pwhash("demo123"), status="active", mfa_enabled=False,
               office_n=31, role="Driver", scope_level="individual", scope_ref=driver_id))
    row = D.TransportDriver(id=driver_id, tenant_id=TENANT, name=body.name.strip(), employee_id=body.employee_id,
                            phone=phone, license_no=body.license_no or body.license_number,
                            license_expiry=body.license_expiry, user_id=user_id)
    s.add(row); s.commit()
    return {"id": row.id, "login": {"username": username, "password": "demo123"}, "decision": dec.as_dict()}

@router.post("/transport/requests")
def create_transport_request(body: TransportRequestIn, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "transport", "view")[0])
    student = s.query(D.Student).filter(or_(D.Student.user_id == ctx["sub"], D.Student.id == ctx.get("scope_ref"))).first()
    if not student: raise HTTPException(403, "Student account required")
    if s.query(D.TransportRequest).filter(D.TransportRequest.student_id == student.id, D.TransportRequest.status == "pending").first(): raise HTTPException(409, "Request already pending")
    stop_id = body.stop_id or body.pickup_stop_id
    if not stop_id: raise HTTPException(422, "Pickup stop is required")
    row = D.TransportRequest(id=uid(), tenant_id=TENANT, student_id=student.id, route_id=body.route_id, stop_id=stop_id); s.add(row); s.commit(); return {"id": row.id, "status": row.status}

@router.post("/transport/allocations")
def create_transport_allocation(body: TransportAllocationIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "assign"); require(dec)
    v = s.get(D.TransportVehicle, body.vehicle_id) or s.query(D.TransportVehicle).filter(D.TransportVehicle.number == body.vehicle_id).first()
    # The UI historically used both ACTIVE and AVAILABLE (and older records
    # may use ASSIGNED). Only maintenance/inactive vehicles must be blocked;
    # assignment itself is a valid way to move an operational vehicle forward.
    if not v or (v.status or "").strip().lower() in ("maintenance", "inactive", "retired"): raise HTTPException(400, "Vehicle is not available")
    if s.query(D.TransportAllocation).filter(D.TransportAllocation.student_id == body.student_id, D.TransportAllocation.status == "active").first(): raise HTTPException(409, "Student already allocated")
    occupied = s.query(D.TransportAllocation).filter(D.TransportAllocation.vehicle_id == v.id, D.TransportAllocation.status == "active").count()
    if occupied >= v.capacity: raise HTTPException(400, "Vehicle has no available seats")
    stop_id = body.stop_id or body.pickup_stop_id
    row = D.TransportAllocation(id=uid(), tenant_id=TENANT, student_id=body.student_id, route_id=body.route_id, stop_id=stop_id, vehicle_id=body.vehicle_id, driver_id=body.driver_id); s.add(row); s.commit(); return {"id": row.id, "decision": dec.as_dict()}

@router.post("/transport/requests/{request_id}/approve")
def approve_transport_request(request_id: str, body: TransportAllocationIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "assign"); require(dec)
    q = s.get(D.TransportRequest, request_id)
    if not q or q.status != "pending": raise HTTPException(404, "Pending request not found")
    q.status = "approved"
    v = s.get(D.TransportVehicle, body.vehicle_id) or s.query(D.TransportVehicle).filter(D.TransportVehicle.number == body.vehicle_id).first()
    if not v: raise HTTPException(404, "Vehicle not found")
    s.add(D.TransportAllocation(id=uid(), tenant_id=TENANT, student_id=q.student_id, route_id=body.route_id, stop_id=body.stop_id or body.pickup_stop_id, vehicle_id=body.vehicle_id, driver_id=body.driver_id))
    s.commit(); return {"status": q.status, "decision": dec.as_dict()}

@router.post("/transport/requests/{request_id}/reject")
def reject_transport_request(request_id: str, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "assign"); require(dec)
    q=s.get(D.TransportRequest, request_id)
    if not q: raise HTTPException(404, "Request not found")
    q.status="rejected"; s.commit(); return {"status": q.status, "decision": dec.as_dict()}

@router.put("/transport/allocations/{allocation_id}")
def update_transport_allocation(allocation_id: str, body: TransportAllocationIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "assign"); require(dec)
    a=s.get(D.TransportAllocation, allocation_id)
    if not a: raise HTTPException(404, "Allocation not found")
    for k in ("student_id","route_id","vehicle_id","driver_id"): setattr(a,k,getattr(body,k))
    a.stop_id=body.stop_id or body.pickup_stop_id; s.commit(); return {"id":a.id,"decision":dec.as_dict()}

@router.delete("/transport/allocations/{allocation_id}")
def delete_transport_allocation(allocation_id: str, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "assign"); require(dec)
    a=s.get(D.TransportAllocation, allocation_id)
    if not a: raise HTTPException(404, "Allocation not found")
    a.status="inactive"; s.commit(); return {"status":"inactive","decision":dec.as_dict()}

@router.delete("/transport/routes/{route_id}")
def delete_transport_route(route_id: str, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "add_route"); require(dec)
    r=s.get(D.TransportRoute, route_id)
    if not r: raise HTTPException(404, "Route not found")
    # Keep the route for history, but atomically remove its operational links.
    # vehicle_no is the route assignment; clearing it leaves the vehicle and its
    # driver assignment intact while making the vehicle route-less.
    for allocation in s.query(D.TransportAllocation).filter(
        D.TransportAllocation.route_id == route_id,
        D.TransportAllocation.status == "active",
    ).all():
        allocation.status = "inactive"
    r.status = "inactive"
    r.vehicle_no = ""
    s.commit()
    return {"status":"inactive","decision":dec.as_dict()}

@router.put("/transport/routes/{route_id}")
def update_transport_route(route_id: str, body: TransportRouteIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "add_route"); require(dec)
    r = s.get(D.TransportRoute, route_id)
    if not r: raise HTTPException(404, "Route not found")
    r.name = body.name.strip() or r.name
    r.vehicle_no = body.vehicle_no.strip()
    r.seats = body.seats
    s.commit()
    return {"id": r.id, "decision": dec.as_dict()}

@router.put("/transport/stops/{stop_id}")
def update_transport_stop(stop_id: str, body: TransportStopIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "add_route"); require(dec)
    x=s.get(D.TransportStop, stop_id)
    if not x: raise HTTPException(404, "Stop not found")
    for k,v in body.model_dump().items(): setattr(x,k,v)
    s.commit(); return {"id":x.id,"decision":dec.as_dict()}

@router.delete("/transport/stops/{stop_id}")
def delete_transport_stop(stop_id: str, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "add_route"); require(dec)
    x=s.get(D.TransportStop, stop_id)
    if not x: raise HTTPException(404, "Stop not found")
    s.delete(x); s.commit(); return {"status":"deleted","decision":dec.as_dict()}

@router.put("/transport/vehicles/{vehicle_id}")
def update_transport_vehicle(vehicle_id: str, body: TransportVehicleIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "assign"); require(dec)
    v=s.get(D.TransportVehicle, vehicle_id)
    if not v: raise HTTPException(404, "Vehicle not found")
    if body.driver_id and not s.get(D.TransportDriver, body.driver_id):
        raise HTTPException(404, "Driver not found")
    v.number=body.number or body.vehicle_number or v.number; v.kind=body.kind; v.capacity=body.capacity; v.status=(body.status or "available").lower(); v.driver_id=body.driver_id
    s.commit(); return {"id":v.id,"decision":dec.as_dict()}

@router.delete("/transport/vehicles/{vehicle_id}")
def delete_transport_vehicle(vehicle_id: str, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "assign"); require(dec)
    v = s.get(D.TransportVehicle, vehicle_id)
    if not v: raise HTTPException(404, "Vehicle not found")
    v.status = "inactive"; s.commit()
    return {"status": "inactive", "decision": dec.as_dict()}

@router.put("/transport/drivers/{driver_id}")
def update_transport_driver(driver_id: str, body: TransportDriverIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "assign"); require(dec)
    d = s.get(D.TransportDriver, driver_id)
    if not d: raise HTTPException(404, "Driver not found")
    d.name, d.employee_id, d.phone = body.name, body.employee_id, body.phone
    d.license_no, d.license_expiry = body.license_no or body.license_number, body.license_expiry
    s.commit(); return {"id": d.id, "decision": dec.as_dict()}

@router.delete("/transport/drivers/{driver_id}")
def delete_transport_driver(driver_id: str, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "assign"); require(dec)
    d = s.get(D.TransportDriver, driver_id)
    if not d: raise HTTPException(404, "Driver not found")
    for v in s.query(D.TransportVehicle).filter(D.TransportVehicle.driver_id == driver_id).all(): v.driver_id = None
    d.status = "inactive"; s.commit()
    return {"status": "inactive", "decision": dec.as_dict()}

class TransportTripIn(BaseModel):
    vehicle_id: str
    driver_id: str
    trip_type: str

class TransportLocationIn(BaseModel):
    vehicle_id: str
    trip_id: str
    latitude: float
    longitude: float

@router.post("/transport/trips/start")
def start_transport_trip(body: TransportTripIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "assign"); require(dec)
    if body.trip_type not in ("PICKUP","DROP"): raise HTTPException(400,"Invalid trip type")
    if s.query(D.TransportTrip).filter(D.TransportTrip.vehicle_id==body.vehicle_id,D.TransportTrip.status=="running").first(): raise HTTPException(409,"Trip already running")
    t=D.TransportTrip(id=uid(),tenant_id=TENANT,vehicle_id=body.vehicle_id,driver_id=body.driver_id,trip_type=body.trip_type); s.add(t); s.commit(); return {"id":t.id,"status":t.status,"trip_type":t.trip_type}

@router.post("/transport/trips/{trip_id}/end")
def end_transport_trip(trip_id: str, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "transport", "assign"); require(dec)
    t=s.get(D.TransportTrip,trip_id)
    if not t: raise HTTPException(404,"Trip not found")
    t.status="ended"; t.ended_at=datetime.utcnow(); s.commit(); return {"status":t.status,"decision":dec.as_dict()}

@router.post("/transport/locations")
def send_transport_location(body: TransportLocationIn, ctx=Depends(auth), s=Depends(db)):
    t=s.get(D.TransportTrip,body.trip_id)
    if not t or t.status!="running" or t.vehicle_id!=body.vehicle_id: raise HTTPException(400,"No running trip")
    t.latitude=body.latitude; t.longitude=body.longitude; t.updated_at=datetime.utcnow(); s.commit(); return {"status":"recorded"}

@router.get("/transport/live-location/{vehicle_id}")
def live_transport_location(vehicle_id: str, ctx=Depends(auth), s=Depends(db)):
    t=s.query(D.TransportTrip).filter(D.TransportTrip.vehicle_id==vehicle_id).order_by(desc(D.TransportTrip.started_at)).first()
    if not t: return {"status":"NOT_STARTED","location":None}
    return {"status":t.status.upper(),"location":{"latitude":t.latitude,"longitude":t.longitude,"recorded_at":t.updated_at.isoformat() if t.updated_at else ""} if t.latitude is not None else None}

@router.get("/transport/my-allocation")
def my_transport_allocation(ctx=Depends(auth), s=Depends(db)):
    student=s.query(D.Student).filter(or_(D.Student.user_id==ctx["sub"],D.Student.id==ctx.get("scope_ref"))).first()
    a=s.query(D.TransportAllocation).filter(D.TransportAllocation.student_id==student.id,D.TransportAllocation.status=="active").first() if student else None
    return {"allocation": {"id":a.id,"student_id":a.student_id,"route_id":a.route_id,"pickup_stop_id":a.stop_id,"vehicle_id":a.vehicle_id,"status":a.status} if a else None}

@router.get("/transport/driver-dashboard")
def transport_driver_dashboard(ctx=Depends(auth), s=Depends(db)):
    d=s.query(D.TransportDriver).filter(D.TransportDriver.user_id==ctx["sub"]).first()
    if not d: raise HTTPException(403,"Driver account required")
    v=s.query(D.TransportVehicle).filter(D.TransportVehicle.driver_id==d.id).first()
    allocs=s.query(D.TransportAllocation).filter(D.TransportAllocation.vehicle_id==v.id,D.TransportAllocation.status=="active").all() if v else []
    route = s.get(D.TransportRoute, allocs[0].route_id) if allocs else None
    students = []
    for allocation in allocs:
        student = s.get(D.Student, allocation.student_id)
        students.append({
            "student_id": allocation.student_id,
            "student_name": student.name if student else allocation.student_id,
            "roll_no": student.roll_no if student else "",
        })
    route_payload = None
    if route:
        route_payload = {
            "id": route.id,
            "name": route.name,
            "vehicle_no": route.vehicle_no,
            "stops": [{
                "id": stop.id,
                "name": stop.name,
                "sequence": stop.sequence,
                "pickup_time": stop.pickup_time,
                "drop_time": stop.drop_time,
            } for stop in s.query(D.TransportStop).filter_by(route_id=route.id).order_by(D.TransportStop.sequence).all()],
        }
    trip = s.query(D.TransportTrip).filter(
        D.TransportTrip.driver_id == d.id,
        D.TransportTrip.status == "running",
    ).order_by(desc(D.TransportTrip.started_at)).first()
    return {
        "driver": {"id": d.id, "name": d.name, "phone": d.phone},
        "driver_id": d.id,
        "vehicle": {"id": v.id, "number": v.number, "vehicle_number": v.number, "capacity": v.capacity} if v else None,
        "route": route_payload,
        "students": students,
        "trip": {"id": trip.id, "trip_type": trip.trip_type, "status": trip.status} if trip else None,
    }


# --------------------------------------------------------------------------- #
#  RESEARCH
# --------------------------------------------------------------------------- #
@router.get("/research")
def research(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "research", "view")[0])
    rows = s.query(D.ResearchProject).all()
    total = s.query(func.coalesce(func.sum(D.ResearchProject.grant_amount), 0)).scalar() or 0
    return {"projects": [{"id": p.id, "title": p.title, "pi": p.pi_name, "dept": p.dept,
                          "agency": p.agency, "grant": p.grant_amount, "status": p.status}
                         for p in rows],
            "total_grants": total,
            "can_add": can(s, ctx, "research", "add")}


# --------------------------------------------------------------------------- #
#  PLACEMENTS
# --------------------------------------------------------------------------- #
@router.get("/placements")
def placements(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "placements", "view")[0])
    rows = s.query(D.PlacementDrive).order_by(desc(D.PlacementDrive.ctc)).all()
    placed = s.query(func.coalesce(func.sum(D.PlacementDrive.offers), 0)).scalar() or 0
    top = max([r.ctc for r in rows], default=0)
    return {"drives": [{"id": d.id, "company": d.company, "role": d.role, "ctc": d.ctc,
                        "date": d.date.isoformat() if d.date else "", "eligible_cgpa": d.eligible_cgpa,
                        "status": d.status, "offers": d.offers} for d in rows],
            "summary": {"offers": placed, "top_ctc": top, "drives": len(rows)},
            "can_add": can(s, ctx, "placements", "add_drive")}


# --------------------------------------------------------------------------- #
#  GRIEVANCE
# --------------------------------------------------------------------------- #
@router.get("/grievance")
def grievance(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "grievance", "view")[0])
    rows = s.query(D.Complaint).order_by(desc(D.Complaint.created_at)).all()
    return {"complaints": [{"id": c.id, "kind": c.kind, "raised_by": c.raised_by,
                            "subject": c.subject, "status": c.status,
                            "severity": c.severity,
                            "created_at": c.created_at.isoformat()} for c in rows],
            "can_resolve": can(s, ctx, "grievance", "resolve"),
            "can_raise": can(s, ctx, "grievance", "raise")}


class ComplaintIn(BaseModel):
    kind: str = "Grievance"
    subject: str
    detail: str = ""


@router.post("/grievance")
def raise_complaint(body: ComplaintIn, ctx=Depends(auth), s=Depends(db)):
    dec, verb = gate(s, ctx, "grievance", "raise")
    require(dec)
    cid = uid()
    s.add(D.Complaint(id=cid, tenant_id=TENANT, kind=body.kind,
                      raised_by=actor_name(s, ctx), subject=body.subject,
                      detail=body.detail, status="open"))
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "grievance.raise",
                f"complaint:{cid}", "", "open", body.subject)
    return {"id": cid, "decision": dec.as_dict()}


class ResolveIn(BaseModel):
    complaint_id: str
    status: str = "resolved"


@router.post("/grievance/resolve")
def resolve_complaint(body: ResolveIn, ctx=Depends(auth), s=Depends(db)):
    dec, verb = gate(s, ctx, "grievance", "resolve")
    require(dec)
    c = s.query(D.Complaint).get(body.complaint_id)
    if not c:
        raise HTTPException(404, "Complaint not found")
    c.status = body.status
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "grievance.resolve",
                f"complaint:{c.id}", "open", c.status, f"Set {c.subject} → {c.status}")
    return {"status": c.status, "decision": dec.as_dict()}


# --------------------------------------------------------------------------- #
#  GOVERNANCE (leadership analytics) & ADMIN
# --------------------------------------------------------------------------- #
def _fmt_day(d: date | None) -> str:
    return d.strftime("%d %b %Y") if d else ""


def _governance_rating(score: float) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 80:
        return "Strong"
    if score >= 70:
        return "On Track"
    return "Needs Attention"


def _governance_snapshots(s):
    return (
        s.query(D.GovernanceDashboardSnapshot)
        .order_by(desc(D.GovernanceDashboardSnapshot.is_default),
                  desc(D.GovernanceDashboardSnapshot.as_of_date),
                  D.GovernanceDashboardSnapshot.semester_label)
        .all()
    )


def _governance_period_range(s):
    snapshots = (s.query(D.InstitutionSnapshot)
                 .order_by(D.InstitutionSnapshot.snapshot_month.desc()).all())
    selected = snapshots[0].snapshot_month if snapshots else _month_start(date.today())
    ranges = [{
        "start": item.snapshot_month.isoformat(),
        "end": _month_end(item.snapshot_month).isoformat(),
        "label": _fmt_range(item.snapshot_month, _month_end(item.snapshot_month)),
    } for item in snapshots]
    if not ranges:
        ranges = [{
            "start": selected.isoformat(),
            "end": _month_end(selected).isoformat(),
            "label": _fmt_range(selected, _month_end(selected)),
        }]
    return {
        "start": selected.isoformat(),
        "end": _month_end(selected).isoformat(),
        "label": _fmt_range(selected, _month_end(selected)),
        "available_ranges": ranges,
    }


def _governance_snapshot_bundle(s, semester: str = ""):
    snapshots = _governance_snapshots(s)
    if not snapshots:
        return None, [], [], []

    selected = None
    if semester:
        selected = next((row for row in snapshots if row.semester_key == semester), None)
    if selected is None:
        selected = next((row for row in snapshots if row.is_default), snapshots[0])

    compliance_rows = (
        s.query(D.GovernanceComplianceMetric)
        .filter(D.GovernanceComplianceMetric.snapshot_id == selected.id)
        .order_by(D.GovernanceComplianceMetric.sort_order, D.GovernanceComplianceMetric.label)
        .all()
    )
    performance_rows = (
        s.query(D.GovernancePerformanceMetric)
        .filter(D.GovernancePerformanceMetric.snapshot_id == selected.id)
        .order_by(D.GovernancePerformanceMetric.sort_order, D.GovernancePerformanceMetric.area)
        .all()
    )
    return selected, snapshots, compliance_rows, performance_rows


def _governance_payload_from_snapshot(snapshot, compliance_rows, performance_rows, semesters):
    total_budget = snapshot.total_budget or 0
    utilized_budget = snapshot.utilized_budget or 0
    utilization_pct = round(100 * utilized_budget / total_budget, 1) if total_budget else 0

    categories = []
    seen = set()
    for row in compliance_rows:
        key = (row.category or "all").strip().lower()
        if key in seen:
            continue
        seen.add(key)
        categories.append({"value": key, "label": key.replace("_", " ").title()})

    return {
        "title": "Governance dashboard",
        "subtitle": "Institution-wide performance for leadership and trustees",
        "selected_semester": {"key": snapshot.semester_key, "label": snapshot.semester_label},
        "semesters": semesters,
        "kpis": {
            "students": snapshot.student_count,
            "faculty": snapshot.faculty_count,
            "student_faculty_ratio": snapshot.student_faculty_ratio,
            "fee_collection_pct": snapshot.fee_collection_pct,
            "research_grants": snapshot.research_grants,
            "placement_offers": snapshot.placement_offers,
            "average_cgpa": snapshot.average_cgpa,
        },
        "budget": {
            "total": total_budget,
            "utilized": utilized_budget,
            "utilization_pct": utilization_pct,
        },
        "compliance": {
            "score": snapshot.compliance_score,
            "label": snapshot.compliance_label,
            "filters": [{"value": "all", "label": "All"}] + categories,
            "items": [
                {
                    "id": row.id,
                    "metric_key": row.metric_key,
                    "category": (row.category or "all").strip().lower(),
                    "category_label": (row.category or "all").replace("_", " ").title(),
                    "label": row.label,
                    "score": round(row.score),
                    "status": row.status,
                }
                for row in compliance_rows
            ],
        },
        "performance_summary": [
            {
                "id": row.id,
                "area": row.area,
                "metric": row.metric,
                "current_value": row.current_value,
                "target_value": row.target_value,
                "status": row.status,
                "trend_pct": row.trend_pct,
                "trend_direction": row.trend_direction,
                "icon": row.icon,
            }
            for row in performance_rows
        ],
        "can_edit": False,
        "last_updated": snapshot.as_of_date.isoformat() if snapshot.as_of_date else "",
        "last_updated_label": _fmt_day(snapshot.as_of_date),
    }


def _governance_live_fallback(s, can_edit_dashboard=False):
    students = s.query(D.Student).count()
    faculty = s.query(D.StaffMember).count()
    ratio = round(students / faculty, 1) if faculty else 0
    collected = s.query(func.coalesce(func.sum(D.FeeInvoice.paid), 0)).scalar() or 0
    billed = s.query(func.coalesce(func.sum(D.FeeInvoice.amount), 0)).scalar() or 0
    grants = s.query(func.coalesce(func.sum(D.ResearchProject.grant_amount), 0)).scalar() or 0
    placed = s.query(func.coalesce(func.sum(D.PlacementDrive.offers), 0)).scalar() or 0
    avg_cgpa = round(s.query(func.coalesce(func.avg(D.Student.cgpa), 0)).scalar() or 0, 2)
    total_budget = s.query(func.coalesce(func.sum(D.BudgetLine.allocated), 0)).scalar() or 0
    utilized_budget = s.query(func.coalesce(func.sum(D.BudgetLine.spent), 0)).scalar() or 0
    utilization_pct = round(100 * utilized_budget / total_budget, 1) if total_budget else 0
    active_accreditations = s.query(D.Accreditation).filter(D.Accreditation.status == "active").count()
    open_risk = s.query(D.Complaint).filter(D.Complaint.status != "resolved").count()
    compliance_score = max(80, min(98, round((100 + min(active_accreditations * 6, 96) + 88 + max(82, 96 - open_risk)) / 4)))

    return {
        "title": "Governance dashboard",
        "subtitle": "Institution-wide performance for leadership and trustees",
        "selected_semester": {"key": "live", "label": "Live Institution View"},
        "semesters": [{"key": "live", "label": "Live Institution View"}],
        "kpis": {
            "students": students,
            "faculty": faculty,
            "student_faculty_ratio": ratio,
            "fee_collection_pct": round(100 * collected / billed, 1) if billed else 0,
            "research_grants": grants,
            "placement_offers": placed,
            "average_cgpa": avg_cgpa,
        },
        "budget": {
            "total": total_budget,
            "utilized": utilized_budget,
            "utilization_pct": utilization_pct,
        },
        "compliance": {
            "score": compliance_score,
            "label": "Healthy",
            "filters": [
                {"value": "all", "label": "All"},
                {"value": "regulatory", "label": "Regulatory"},
                {"value": "quality", "label": "Quality"},
                {"value": "policy", "label": "Policy"},
                {"value": "risk", "label": "Risk"},
            ],
            "items": [
                {"id": "live_comp_01", "metric_key": "statutory_compliance", "category": "regulatory", "category_label": "Regulatory", "label": "Statutory Compliance", "score": 100, "status": "healthy"},
                {"id": "live_comp_02", "metric_key": "accreditations", "category": "quality", "category_label": "Quality", "label": "Accreditations", "score": min(100, max(80, active_accreditations * 8)), "status": "healthy"},
                {"id": "live_comp_03", "metric_key": "policies_sops", "category": "policy", "category_label": "Policy", "label": "Policies & SOPs", "score": 88, "status": "healthy"},
                {"id": "live_comp_04", "metric_key": "audit_risk", "category": "risk", "category_label": "Risk", "label": "Audit & Risk", "score": max(82, 96 - open_risk), "status": "healthy"},
            ],
        },
        "performance_summary": [
            {"id": "live_perf_01", "area": "Academics", "metric": "Average CGPA", "current_value": f"{avg_cgpa:.2f}", "target_value": ">= 7.50", "status": "Achieved" if avg_cgpa >= 7.5 else "On Track", "trend_pct": 3, "trend_direction": "up", "icon": "academics"},
            {"id": "live_perf_02", "area": "Finance", "metric": "Budget Utilisation", "current_value": f"{utilization_pct:.1f}%", "target_value": "<= 60%", "status": "On Track" if utilization_pct <= 60 else "Attention", "trend_pct": 2, "trend_direction": "up", "icon": "finance"},
            {"id": "live_perf_03", "area": "Placements", "metric": "Placement Offers", "current_value": str(placed), "target_value": ">= 60", "status": "Achieved" if placed >= 60 else "On Track", "trend_pct": 4, "trend_direction": "up", "icon": "placements"},
            {"id": "live_perf_04", "area": "Research", "metric": "Research Grants", "current_value": f"{grants / 1e7:.2f} Cr", "target_value": ">= 12 Cr", "status": "Achieved" if grants >= 12 * 1e7 else "On Track", "trend_pct": 5, "trend_direction": "up", "icon": "research"},
        ],
        "can_edit": can_edit_dashboard,
        "last_updated": date.today().isoformat(),
        "last_updated_label": _fmt_day(date.today()),
    }


@router.get("/governance")
def governance(semester: str = Query("", description="Semester key"), ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "governance", "view")[0])
    can_edit_dashboard = can(s, ctx, "governance", "edit_dashboard")
    selected, snapshots, compliance_rows, performance_rows = _governance_snapshot_bundle(s, semester)
    if not snapshots or not selected:
        payload = _governance_live_fallback(s, can_edit_dashboard)
        payload["range"] = _governance_period_range(s)
        return payload

    semesters = [{"key": row.semester_key, "label": row.semester_label} for row in snapshots]
    payload = _governance_payload_from_snapshot(selected, compliance_rows, performance_rows, semesters)
    payload["can_edit"] = can_edit_dashboard
    payload["range"] = _governance_period_range(s)
    return payload


class GovernanceKpisIn(BaseModel):
    students: int
    faculty: int
    student_faculty_ratio: float = 0
    fee_collection_pct: float
    research_grants: float
    placement_offers: int
    average_cgpa: float


class GovernanceBudgetIn(BaseModel):
    total: float
    utilized: float


class GovernanceComplianceMetricIn(BaseModel):
    id: str
    category: str = "all"
    label: str
    score: float
    status: str = "healthy"


class GovernanceComplianceIn(BaseModel):
    score: float = 0
    label: str = ""
    items: list[GovernanceComplianceMetricIn]


class GovernancePerformanceMetricIn(BaseModel):
    id: str
    area: str
    metric: str
    current_value: str
    target_value: str
    status: str
    trend_pct: float
    trend_direction: str = "up"
    icon: str = ""


class GovernanceDashboardUpdateIn(BaseModel):
    kpis: GovernanceKpisIn
    budget: GovernanceBudgetIn
    compliance: GovernanceComplianceIn
    performance_summary: list[GovernancePerformanceMetricIn]
    last_updated: date | None = None


@router.put("/governance/{semester_key}")
def update_governance_dashboard(semester_key: str, body: GovernanceDashboardUpdateIn,
                                ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "governance", "edit_dashboard")
    require(dec)

    selected, snapshots, compliance_rows, performance_rows = _governance_snapshot_bundle(s, semester_key)
    if not snapshots or not selected:
        raise HTTPException(404, "Governance semester snapshot not found")

    if not body.compliance.items:
        raise HTTPException(400, "At least one compliance metric is required")
    if not body.performance_summary:
        raise HTTPException(400, "At least one performance summary row is required")

    prev_state = selected.updated_at.isoformat() if selected.updated_at else ""
    student_count = max(0, int(body.kpis.students))
    faculty_count = max(0, int(body.kpis.faculty))
    ratio = round(student_count / faculty_count, 1) if faculty_count else 0
    compliance_avg = round(sum(item.score for item in body.compliance.items) / len(body.compliance.items), 1)
    compliance_label = body.compliance.label.strip() or _governance_rating(compliance_avg)

    selected.student_count = student_count
    selected.faculty_count = faculty_count
    selected.student_faculty_ratio = ratio
    selected.fee_collection_pct = max(0, min(100, round(body.kpis.fee_collection_pct, 1)))
    selected.research_grants = max(0, body.kpis.research_grants)
    selected.placement_offers = max(0, int(body.kpis.placement_offers))
    selected.average_cgpa = round(max(0, body.kpis.average_cgpa), 2)
    selected.total_budget = max(0, body.budget.total)
    selected.utilized_budget = max(0, body.budget.utilized)
    selected.compliance_score = compliance_avg
    selected.compliance_label = compliance_label
    selected.as_of_date = body.last_updated or selected.as_of_date or date.today()
    selected.updated_at = datetime.utcnow()

    compliance_by_id = {row.id: row for row in compliance_rows}
    seen_compliance = set()
    for idx, item in enumerate(body.compliance.items, start=1):
        item_id = item.id or uid()
        row = compliance_by_id.get(item_id)
        if row is None:
            row = D.GovernanceComplianceMetric(
                id=item_id, tenant_id=TENANT, snapshot_id=selected.id
            )
            s.add(row)
        row.metric_key = slug(item.label)
        row.category = (item.category or "all").strip().lower() or "all"
        row.label = item.label.strip()
        row.score = max(0, min(100, round(item.score, 1)))
        row.status = item.status.strip().lower() or "healthy"
        row.sort_order = idx
        seen_compliance.add(item_id)
    for row in compliance_rows:
        if row.id not in seen_compliance:
            s.delete(row)

    performance_by_id = {row.id: row for row in performance_rows}
    seen_performance = set()
    for idx, item in enumerate(body.performance_summary, start=1):
        item_id = item.id or uid()
        row = performance_by_id.get(item_id)
        if row is None:
            row = D.GovernancePerformanceMetric(
                id=item_id, tenant_id=TENANT, snapshot_id=selected.id
            )
            s.add(row)
        row.area = item.area.strip()
        row.metric = item.metric.strip()
        row.current_value = item.current_value.strip()
        row.target_value = item.target_value.strip()
        row.status = item.status.strip()
        row.trend_pct = round(abs(item.trend_pct), 1)
        row.trend_direction = "down" if item.trend_direction == "down" else "up"
        row.icon = item.icon.strip() or "academics"
        row.sort_order = idx
        seen_performance.add(item_id)
    for row in performance_rows:
        if row.id not in seen_performance:
            s.delete(row)

    s.commit()
    write_audit(
        s, ctx["sub"], actor_name(s, ctx), ctx["office_n"],
        "governance.dashboard.update", f"governance:{selected.semester_key}",
        prev_state, selected.as_of_date.isoformat(),
        f"Updated governance dashboard for {selected.semester_label}",
        ctx.get("auth_level", "mfa"),
    )

    selected, snapshots, compliance_rows, performance_rows = _governance_snapshot_bundle(s, semester_key)
    semesters = [{"key": row.semester_key, "label": row.semester_label} for row in snapshots]
    payload = _governance_payload_from_snapshot(selected, compliance_rows, performance_rows, semesters)
    payload["can_edit"] = can(s, ctx, "governance", "edit_dashboard")
    return payload


@router.get("/admin/users")
def admin_users(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "admin", "view")[0])
    rows = s.query(User).limit(60).all()
    return {"users": [{"username": u.username, "office_n": u.office_n, "role": u.role,
                       "scope_level": u.scope_level, "mfa": u.mfa_enabled,
                       "status": u.status} for u in rows],
            "can_configure": can(s, ctx, "admin", "configure")}
