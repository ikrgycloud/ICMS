# -*- coding: utf-8 -*-
"""
Portal API — persona-scoped views.

Where domain_api.py serves *administrative* module data (rosters, ledgers),
this router serves the signed-in person's OWN world:

  • a Student sees only their courses, attendance, marks, fees, library loans
  • a Parent/Guardian sees exactly one linked student
  • a Faculty member sees only the sections they teach and those students
  • a Dean/HOD sees only their school/department rollup

This is what makes every login genuinely different: two people with the same
module can see completely different, personally-relevant data.
"""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func

from core import db, auth
from database import office
import domain_models as D
from models import User, Notification

router = APIRouter(prefix="/api/portal")


# --------------------------------------------------------------------------- #
#  Persona resolution
# --------------------------------------------------------------------------- #
def persona(s, ctx):
    """Resolve the signed-in user into a concrete persona + linked entity."""
    uid = ctx["sub"]
    office_n = ctx["office_n"]
    student = s.query(D.Student).filter(D.Student.user_id == uid).first()
    if not student and office_n == 36:
        # Keep the demo student portal resilient even if the user-to-student
        # binding was created after an older token or database snapshot.
        scope_ref = ctx.get("scope_ref", "")
        if scope_ref and not scope_ref.startswith("scope_"):
            student = s.query(D.Student).get(scope_ref)
        if not student:
            login = s.query(User).get(uid)
            if login and login.username == "student":
                student = s.query(D.Student).order_by(D.Student.cgpa.desc()).first()
    if student:
        return {"kind": "student", "student": student}
    staff = s.query(D.StaffMember).filter(D.StaffMember.user_id == uid).first()
    if staff:
        return {"kind": "faculty", "staff": staff}
    # Parent watches a specific student (scope_ref holds the student id)
    if office_n == 37:
        sid = ctx.get("scope_ref", "")
        st = s.query(D.Student).get(sid) if sid else None
        if not st:
            st = s.query(D.Student).order_by(D.Student.cgpa.desc()).first()
        return {"kind": "parent", "student": st}
    return {"kind": "staff", "office_n": office_n}


@router.get("/whoami")
def whoami(ctx=Depends(auth), s=Depends(db)):
    p = persona(s, ctx)
    out = {"kind": p["kind"], "office_n": ctx["office_n"]}
    if p.get("student"):
        st = p["student"]
        out["profile"] = {"name": st.name, "roll_no": st.roll_no, "cgpa": st.cgpa,
                          "semester": st.semester, "batch": st.batch}
    if p.get("staff"):
        stf = p["staff"]
        out["profile"] = {"name": stf.name, "emp_id": stf.emp_id,
                          "designation": stf.designation}
    return out


# --------------------------------------------------------------------------- #
#  STUDENT portal — my academic world
# --------------------------------------------------------------------------- #
def _student_or_404(s, ctx):
    p = persona(s, ctx)
    st = p.get("student")
    if not st:
        raise HTTPException(404, "No student linked to this login")
    return st


@router.get("/student/home")
def student_home(ctx=Depends(auth), s=Depends(db)):
    st = _student_or_404(s, ctx)
    dept = s.query(D.Department).get(st.dept_id)
    enrolls = s.query(D.Enrollment).filter(D.Enrollment.student_id == st.id,
                                           D.Enrollment.status == "enrolled").all()
    sec_ids = [e.section_id for e in enrolls]

    # attendance across my sections
    total = s.query(D.AttendanceRecord).filter(
        D.AttendanceRecord.student_id == st.id).count()
    present = s.query(D.AttendanceRecord).filter(
        D.AttendanceRecord.student_id == st.id,
        D.AttendanceRecord.present == True).count()
    att_pct = round(100 * present / total) if total else None

    # fees
    inv = s.query(D.FeeInvoice).filter(D.FeeInvoice.student_id == st.id).first()
    fee = None
    if inv:
        fee = {"amount": inv.amount, "paid": inv.paid,
               "balance": inv.amount - inv.paid, "status": inv.status}

    # library
    loans = s.query(D.BookLoan).filter(D.BookLoan.borrower == st.id,
                                       D.BookLoan.returned == False).count()

    return {
        "profile": {"name": st.name, "roll_no": st.roll_no, "cgpa": st.cgpa,
                    "semester": st.semester, "batch": st.batch,
                    "department": dept.name if dept else "", "section": st.section,
                    "hosteller": st.hosteller, "scholarship": st.scholarship},
        "kpis": {"courses": len(sec_ids), "attendance_pct": att_pct,
                 "fee_balance": (inv.amount - inv.paid) if inv else 0,
                 "library_loans": loans},
        "fee": fee,
    }


@router.get("/student/courses")
def student_courses(ctx=Depends(auth), s=Depends(db)):
    st = _student_or_404(s, ctx)
    enrolls = s.query(D.Enrollment).filter(D.Enrollment.student_id == st.id).all()
    course_map = {c.id: c for c in s.query(D.Course).all()}
    fac_map = {f.id: f.name for f in s.query(D.StaffMember).all()}
    out = []
    for e in enrolls:
        sec = s.query(D.Section).get(e.section_id)
        if not sec:
            continue
        c = course_map.get(sec.course_id)
        # my attendance in this section
        tot = s.query(D.AttendanceRecord).filter(
            D.AttendanceRecord.student_id == st.id,
            D.AttendanceRecord.section_id == sec.id).count()
        pre = s.query(D.AttendanceRecord).filter(
            D.AttendanceRecord.student_id == st.id,
            D.AttendanceRecord.section_id == sec.id,
            D.AttendanceRecord.present == True).count()
        out.append({
            "course_code": c.code if c else "", "title": c.title if c else "",
            "credits": c.credits if c else 0, "section": sec.section_code,
            "faculty": fac_map.get(sec.faculty_person_id, "—"),
            "schedule": sec.schedule, "room": sec.room,
            "status": e.status, "grade": e.grade,
            "attendance_pct": round(100 * pre / tot) if tot else None,
        })
    return {"courses": out}


@router.get("/student/attendance")
def student_attendance(ctx=Depends(auth), s=Depends(db)):
    st = _student_or_404(s, ctx)
    recs = (s.query(D.AttendanceRecord)
            .filter(D.AttendanceRecord.student_id == st.id)
            .order_by(D.AttendanceRecord.on_date.desc()).limit(60).all())
    course_of = {}
    for sec in s.query(D.Section).all():
        c = s.query(D.Course).get(sec.course_id)
        course_of[sec.id] = c.code if c else sec.id
    by_course = {}
    for r in recs:
        cc = course_of.get(r.section_id, "?")
        b = by_course.setdefault(cc, {"present": 0, "total": 0})
        b["total"] += 1
        if r.present:
            b["present"] += 1
    summary = [{"course": k, "present": v["present"], "total": v["total"],
                "pct": round(100 * v["present"] / v["total"]) if v["total"] else 0}
               for k, v in by_course.items()]
    return {"summary": summary,
            "recent": [{"date": r.on_date.isoformat(),
                        "course": course_of.get(r.section_id, "?"),
                        "present": r.present} for r in recs[:20]]}


@router.get("/student/results")
def student_results(ctx=Depends(auth), s=Depends(db)):
    st = _student_or_404(s, ctx)
    marks = s.query(D.Mark).filter(D.Mark.student_id == st.id).all()
    out = []
    for m in marks:
        a = s.query(D.Assessment).get(m.assessment_id)
        if not a:
            continue
        sec = s.query(D.Section).get(a.section_id)
        c = s.query(D.Course).get(sec.course_id) if sec else None
        out.append({"course": c.code if c else "", "assessment": a.name,
                    "score": m.score, "max": a.max_marks})
    return {"marks": out, "cgpa": st.cgpa}


@router.get("/student/fees")
def student_fees(ctx=Depends(auth), s=Depends(db)):
    st = _student_or_404(s, ctx)
    invs = s.query(D.FeeInvoice).filter(D.FeeInvoice.student_id == st.id).all()
    pays = s.query(D.Payment).filter(D.Payment.student_id == st.id).all()
    return {
        "invoices": [{"term": i.term, "amount": i.amount, "paid": i.paid,
                      "balance": i.amount - i.paid, "status": i.status,
                      "due_date": i.due_date.isoformat() if i.due_date else ""} for i in invs],
        "payments": [{"amount": p.amount, "method": p.method,
                      "reference": p.reference,
                      "at": p.at.isoformat() if p.at else ""} for p in pays],
    }


# --------------------------------------------------------------------------- #
#  FACULTY portal — my teaching
# --------------------------------------------------------------------------- #
def _staff_or_404(s, ctx):
    p = persona(s, ctx)
    stf = p.get("staff")
    if not stf:
        raise HTTPException(404, "No staff profile linked to this login")
    return stf


@router.get("/faculty/home")
def faculty_home(ctx=Depends(auth), s=Depends(db)):
    stf = _staff_or_404(s, ctx)
    secs = s.query(D.Section).filter(D.Section.faculty_person_id == stf.id).all()
    sec_ids = [x.id for x in secs]
    n_students = 0
    if sec_ids:
        n_students = (s.query(D.Enrollment)
                      .filter(D.Enrollment.section_id.in_(sec_ids),
                              D.Enrollment.status == "enrolled").count())
    dept = s.query(D.Department).get(stf.dept_id) if stf.dept_id else None
    course_map = {course.id: course for course in s.query(D.Course).all()}
    enrollments = s.query(D.Enrollment).filter(D.Enrollment.section_id.in_(sec_ids), D.Enrollment.status == "enrolled").all() if sec_ids else []
    enrollment_by_section = {section.id: 0 for section in secs}
    for enrollment in enrollments: enrollment_by_section[enrollment.section_id] = enrollment_by_section.get(enrollment.section_id, 0) + 1
    attendance = s.query(D.AttendanceRecord).filter(D.AttendanceRecord.section_id.in_(sec_ids)).all() if sec_ids else []
    attendance_by_section = {section.id: [] for section in secs}
    for record in attendance: attendance_by_section.setdefault(record.section_id, []).append(record)
    assessments = s.query(D.Assessment).filter(D.Assessment.section_id.in_(sec_ids)).all() if sec_ids else []
    marks = s.query(D.Mark).filter(D.Mark.assessment_id.in_([item.id for item in assessments])).all() if assessments else []
    marks_by_assessment = {}
    for mark in marks: marks_by_assessment.setdefault(mark.assessment_id, []).append(mark)
    section_rows = []
    for section in secs:
        records = attendance_by_section.get(section.id, [])
        attendance_pct = round(100 * sum(1 for record in records if record.present) / len(records), 1) if records else None
        course = course_map.get(section.course_id)
        section_rows.append({"id": section.id, "course_code": course.code if course else "", "title": course.title if course else "", "section": section.section_code, "schedule": section.schedule, "room": section.room, "enrolled": enrollment_by_section.get(section.id, 0), "capacity": section.capacity, "attendance_pct": attendance_pct})
    total_attendance = sum(len(records) for records in attendance_by_section.values())
    present_attendance = sum(sum(1 for record in records if record.present) for records in attendance_by_section.values())
    average_attendance = round(100 * present_attendance / total_attendance, 1) if total_attendance else None
    max_marks_by_assessment = {assessment.id: assessment.max_marks for assessment in assessments}
    possible_marks = sum(max_marks_by_assessment.get(mark.assessment_id, 100) for mark in marks)
    average_score = round(10 * sum(mark.score for mark in marks) / possible_marks, 2) if possible_marks else None
    pending = []
    # A class on today's timetable still needs attendance when no record has
    # been saved for that section/date.  This derives the reminder from the
    # same assigned sections and attendance rows used by the rest of the page.
    today_short = date.today().strftime("%a")
    for section in secs:
        scheduled_days = (section.schedule or "").split(maxsplit=1)[0].split("/")
        has_class_today = any(day[:3].title() == today_short for day in scheduled_days)
        already_marked = any(record.on_date == date.today() for record in attendance_by_section.get(section.id, []))
        if has_class_today and not already_marked:
            course = course_map.get(section.course_id)
            pending.append({"id": f"attendance-{section.id}-{date.today().isoformat()}", "kind": "attendance",
                            "title": f"Mark attendance: {course.code if course else 'Section'} ({section.section_code})",
                            "course": course.title if course else "Assigned section", "count": 1,
                            "due": "Today"})
    marks_pending = 0
    for assessment in assessments:
        missing = max(0, enrollment_by_section.get(assessment.section_id, 0) - len(marks_by_assessment.get(assessment.id, [])))
        if missing:
            marks_pending += 1
            section = next((item for item in section_rows if item["id"] == assessment.section_id), None)
            pending.append({"id": assessment.id, "kind": "marks", "title": f"Enter marks: {assessment.name}", "course": f"{section['course_code']} ({section['section']})" if section else "Section", "count": missing, "due": "Marks pending"})
    notes = s.query(Notification).filter(Notification.user_id == ctx["sub"]).order_by(Notification.created_at.desc()).limit(4).all()
    day_indexes = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    teaching_schedule = []
    for section in secs:
        parts = (section.schedule or "").split(maxsplit=1)
        days, class_time = (parts[0], parts[1] if len(parts) > 1 else "Time pending") if parts else ("", "Time pending")
        course = course_map.get(section.course_id)
        for day_name in days.split("/"):
            day_index = day_indexes.get(day_name[:3].title())
            if day_index is None:
                continue
            class_date = week_start + timedelta(days=day_index)
            teaching_schedule.append({"id": f"{section.id}-{day_index}", "day": class_date.strftime("%a"),
                                      "date": class_date.isoformat(), "time": class_time,
                                      "section": section.section_code,
                                      "course_code": course.code if course else "",
                                      "subject": course.title if course else "Course unavailable",
                                      "room": section.room or "Room pending"})
    teaching_schedule.sort(key=lambda item: (item["date"], item["time"], item["course_code"]))
    classes_this_week = len(teaching_schedule)

    attendance_trend = []
    for offset in range(5, -1, -1):
        start = week_start - timedelta(weeks=offset)
        end = start + timedelta(days=6)
        records = [record for record in attendance if start <= record.on_date <= end]
        attendance_trend.append({"label": f"Wk {6 - offset}",
                                 "value": round(100 * sum(record.present for record in records) / len(records), 1) if records else None})
    distribution = {"80% and above": 0, "60% – 79%": 0, "40% – 59%": 0, "Below 40%": 0}
    for mark in marks:
        maximum = max_marks_by_assessment.get(mark.assessment_id, 0)
        if not maximum:
            continue
        score_pct = 100 * mark.score / maximum
        if score_pct >= 80: distribution["80% and above"] += 1
        elif score_pct >= 60: distribution["60% – 79%"] += 1
        elif score_pct >= 40: distribution["40% – 59%"] += 1
        else: distribution["Below 40%"] += 1
    return {
        "profile": {"name": stf.name, "emp_id": stf.emp_id,
                    "designation": stf.designation,
                    "department": dept.name if dept else "", "email": stf.email,
                    "phone": stf.phone or None, "office_hours": stf.office_hours or None},
        "kpis": {"sections": len(secs), "students": n_students, "classes_this_week": classes_this_week,
                 "pending_tasks": len(pending), "marks_entry_pending": marks_pending,
                 "average_attendance": average_attendance, "average_grade": average_score},
        "sections": section_rows, "pending_tasks": pending[:4],
        "announcements": [{"id": item.id, "title": item.title, "detail": item.detail, "date": item.created_at.date().isoformat()} for item in notes],
        "teaching_schedule": teaching_schedule,
        "attendance_trend": attendance_trend,
        "marks_distribution": [{"label": label, "value": value} for label, value in distribution.items()],
        "performance": {"assessments": len(assessments), "average_score": round(average_score * 10, 1) if average_score is not None else None,
                        "marks_entered": len(marks), "expected_marks": sum(enrollment_by_section.get(item.section_id, 0) for item in assessments)},
        "role_context": {"active_role": ctx.get("role"), "available_roles": office(ctx["office_n"])["internal_roles"]},
    }


@router.get("/faculty/sections")
def faculty_sections(ctx=Depends(auth), s=Depends(db)):
    stf = _staff_or_404(s, ctx)
    secs = s.query(D.Section).filter(D.Section.faculty_person_id == stf.id).all()
    course_map = {c.id: c for c in s.query(D.Course).all()}
    out = []
    for sec in secs:
        c = course_map.get(sec.course_id)
        enrolled = s.query(D.Enrollment).filter(
            D.Enrollment.section_id == sec.id,
            D.Enrollment.status == "enrolled").count()
        asmts = s.query(D.Assessment).filter(D.Assessment.section_id == sec.id).count()
        out.append({"id": sec.id, "course_code": c.code if c else "",
                    "title": c.title if c else "", "section": sec.section_code,
                    "schedule": sec.schedule, "room": sec.room,
                    "enrolled": enrolled, "assessments": asmts})
    return {"sections": out}


@router.get("/faculty/schedule")
def faculty_schedule(ctx=Depends(auth), s=Depends(db)):
    """Weekly schedule built from the faculty member's assigned sections and staff events."""
    stf = _staff_or_404(s, ctx)
    today = date.today(); week_start = today - timedelta(days=today.weekday()); week_end = week_start + timedelta(days=6)
    courses = {row.id: row for row in s.query(D.Course).all()}
    days = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
    events = []
    sections = s.query(D.Section).filter(D.Section.faculty_person_id == stf.id).all()
    for section in sections:
        parts = (section.schedule or "").split(maxsplit=1); names = parts[0] if parts else ""; class_time = parts[1] if len(parts) > 1 else "Time pending"
        course = courses.get(section.course_id)
        for name in names.split("/"):
            index = days.get(name[:3].title())
            if index is not None:
                events.append({"id": f"class-{section.id}-{index}", "date": (week_start + timedelta(days=index)).isoformat(), "time": class_time, "title": f"{course.code if course else 'Course'} ({section.section_code})", "detail": course.title if course else "Assigned section", "location": section.room or "Room pending", "type": "class", "route": "attendance"})
    for event in s.query(D.CalendarEvent).filter(D.CalendarEvent.status == "published").all():
        if not event.start_at or not (week_start <= event.start_at.date() <= week_end) or event.audience not in ("all", "staff", "leadership"):
            continue
        events.append({"id": f"event-{event.id}", "date": event.start_at.date().isoformat(), "time": "All day" if event.all_day else event.start_at.strftime("%H:%M"), "title": event.title, "detail": event.category, "location": event.location or "Campus", "type": "meeting", "route": "calendar"})
    events.sort(key=lambda item: (item["date"], item["time"], item["title"]))
    leaves = s.query(D.LeaveRequest).filter(D.LeaveRequest.staff_id == stf.id, D.LeaveRequest.status.in_(["pending", "approved"])).count()
    return {"profile": {"name": stf.name, "email": stf.email, "phone": stf.phone, "office_hours": stf.office_hours}, "role": ctx.get("role"), "week_start": week_start.isoformat(), "events": events, "summary": {"classes": sum(item["type"] == "class" for item in events), "meetings": sum(item["type"] == "meeting" for item in events), "sections": len(sections), "leave_requests": leaves}}


@router.get("/faculty/section/{section_id}/students")
def faculty_section_students(section_id: str, ctx=Depends(auth), s=Depends(db)):
    stf = _staff_or_404(s, ctx)
    sec = s.query(D.Section).get(section_id)
    if not sec or sec.faculty_person_id != stf.id:
        raise HTTPException(403, "Not your section")
    enrolls = s.query(D.Enrollment).filter(
        D.Enrollment.section_id == section_id,
        D.Enrollment.status == "enrolled").all()
    out = []
    for e in enrolls:
        st = s.query(D.Student).get(e.student_id)
        if not st:
            continue
        tot = s.query(D.AttendanceRecord).filter(
            D.AttendanceRecord.student_id == st.id,
            D.AttendanceRecord.section_id == section_id).count()
        pre = s.query(D.AttendanceRecord).filter(
            D.AttendanceRecord.student_id == st.id,
            D.AttendanceRecord.section_id == section_id,
            D.AttendanceRecord.present == True).count()
        out.append({"roll_no": st.roll_no, "name": st.name, "cgpa": st.cgpa,
                    "attendance_pct": round(100 * pre / tot) if tot else None})
    return {"students": out, "section": sec.section_code}


# --------------------------------------------------------------------------- #
#  PARENT portal — one linked student
# --------------------------------------------------------------------------- #
@router.get("/parent/home")
def parent_home(ctx=Depends(auth), s=Depends(db)):
    p = persona(s, ctx)
    st = p.get("student")
    if not st:
        raise HTTPException(404, "No ward linked to this login")
    dept = s.query(D.Department).get(st.dept_id)
    total = s.query(D.AttendanceRecord).filter(D.AttendanceRecord.student_id == st.id).count()
    present = s.query(D.AttendanceRecord).filter(
        D.AttendanceRecord.student_id == st.id,
        D.AttendanceRecord.present == True).count()
    inv = s.query(D.FeeInvoice).filter(D.FeeInvoice.student_id == st.id).first()
    return {
        "ward": {"name": st.name, "roll_no": st.roll_no, "cgpa": st.cgpa,
                 "semester": st.semester, "department": dept.name if dept else "",
                 "attendance_pct": round(100 * present / total) if total else None},
        "fee": {"amount": inv.amount, "paid": inv.paid,
                "balance": inv.amount - inv.paid, "status": inv.status} if inv else None,
    }
