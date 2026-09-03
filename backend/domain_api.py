# -*- coding: utf-8 -*-
"""
Domain API — the functional modules that let every office do its job.

Every read is scope-filtered; every mutation passes through the authority engine
(authorize()) using the office's RBAC authority for the verb the action maps to,
and is written to the hash-chained audit log. Actions the office may not perform
return 403 with the engine's reason — the same verdict the UI uses to disable
the control.
"""
import json
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, desc, func, or_

from core import db, auth, uid, write_audit, notify, active_delegation_for
from database import office, TENANT, slug
from authority import authorize, ALLOW, scope_covers
from matrices import (rbac_for, scope_for, approval_limit_for, APPROVAL_LIMITS,
                       APPROVAL_MATRIX, RISK_ESCALATION_TARGETS)
from capabilities import (modules_for_office, module_meta, MODULE_ACTIONS,
                          MODULES, action_allowed_for_office)
import domain_models as D
from models import User, Person, OrgScope, WorkflowInstance, WorkflowProfile, Approval, Notification

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
    if ctx.get("office_n") == 35 and module in {"students", "calendar", "academic_calendar"}:
        from authority import Decision, DENY
        return Decision(DENY, "This module is not available to Front Office"), "view"
    verb = MODULE_ACTIONS.get(module, {}).get(action, "view")
    o = office(ctx["office_n"])
    rbac = rbac_for(ctx["office_n"], o["level"], verb)
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
                    active_delegation=active_delegation_for(
                        s, ctx["sub"], ctx.get("tenant_id", TENANT), ctx.get("scope_ref")),
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
        return True
    staff = _staff_profile(s, ctx)
    if ctx["office_n"] in {10, 17}:
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
    if ctx.get("office_n") == 35:
        raise HTTPException(403, "This generic module is not available to Front Office")
    # The generic overview predates the Campus Head portal. Campus Head must
    # never receive tenant-wide aggregates as a campus dashboard.
    if ctx.get("office_n") == 3:
        require(gate(s, ctx, "analytics", "view")[0])
        campus = _campus_scope_for_campus_head(s, ctx)
        tenant_id = ctx.get("tenant_id", TENANT)
        students = s.query(D.Student).filter(D.Student.tenant_id == tenant_id,
                                             D.Student.campus == campus.name)
        staff = s.query(D.StaffMember).filter(D.StaffMember.tenant_id == tenant_id,
                                              D.StaffMember.campus == campus.name)
        dept_counts = dict(s.query(D.Department.code, func.count(D.Student.id))
                           .join(D.Student, D.Student.dept_id == D.Department.id)
                           .filter(D.Student.tenant_id == tenant_id,
                                   D.Student.campus == campus.name)
                           .group_by(D.Department.code).all())
        # No authoritative campus ownership exists for the remaining sources.
        # `None` means unavailable; it must not be rendered as a real zero.
        return {"stats": {"students": students.count(), "faculty": staff.count(),
                "courses": None, "sections": None, "applications": None,
                "fees_due": None, "books": None, "projects": None,
                "open_complaints": None, "pending_leave": None,
                "placement_offers": None}, "dept_distribution": dept_counts,
                "campus_scope_id": campus.id, "data_status": "partial"}

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
    # Batches are the same academic-year dimension used by the student risk
    # register. Keeping this source shared makes the dashboard drill-down exact.
    student_query = _student_scope(s, s.query(D.Student).filter(D.Student.status == "active"), ctx)
    scoped_students = student_query.all()
    years = sorted({_academic_year_label(row.batch) for row in scoped_students if row.batch}, reverse=True)
    selected_year = academic_year if academic_year in years else ("2026-27" if "2026-27" in years else (years[0] if years else ""))
    if selected_year:
        batches = [row.batch for row in scoped_students if _academic_year_label(row.batch) == selected_year]
        student_query = student_query.filter(D.Student.batch.in_(batches))
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
    risk_backlogs = _backlog_summary(s, student_ids)
    attendance_totals = _attendance_totals(s, student_ids)
    risk_ids = {row.id for row in students if _student_risk_payload(row, risk_backlogs[row.id], attendance_totals)["at_risk"]}
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
        "kpis": {"students": len(students), "faculty": s.query(D.StaffMember).filter(D.StaffMember.status == "active").count(), "attendance": attendance_pct, "decisions": len(pending_workflows), "risk_students": len(risk_ids), "critical_alerts": sum(1 for n in notifications if n.severity == "critical")},
        "attendance": {"today": attendance_pct, "today_records": len(today_rows), "trend": trend},
        "performance": {"average_cgpa": avg_cgpa, "pass_rate": pass_rate, "bands": bands, "at_risk": len(risk_ids), "backlogs": sum(1 for item in risk_backlogs.values() if item["current"] > 0)},
        "examinations": {"sections": s.query(D.Section).count(), "assessments": assessments, "marks_submitted": marks, "pending_moderation": s.query(D.ResultSheet).filter(D.ResultSheet.status != "published").count()},
        "welfare": {"at_risk": len(risk_ids), "grievances": s.query(D.Complaint).filter(D.Complaint.kind == "Grievance", D.Complaint.status != "resolved").count(), "discipline": s.query(D.Complaint).filter(D.Complaint.kind == "Discipline", D.Complaint.status != "resolved").count(), "critical": s.query(D.Complaint).filter(D.Complaint.severity == "high", D.Complaint.status != "resolved").count()},
        "operations": {"maintenance": asset_maintenance, "procurement": 0, "asset_requests": asset_maintenance, "facilities": asset_maintenance},
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
CALENDAR_ACADEMIC_EDITORS = {1, 2, 4, 5}


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
    title: str
    category: str = "Teaching"
    campus: str = "All Campuses"
    start_date: str
    end_date: str = ""
    description: str = ""
    status: str = "published"


@router.get("/calendar")
def calendar_view(start: str = "", ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "calendar", "view")[0])
    campus = _campus_scope_for_campus_head(s, ctx) if ctx.get("office_n") == 3 else None
    tenant_id = ctx.get("tenant_id", TENANT)
    month_start = _parse_month(start)
    month_end = _month_end(month_start)
    start_dt = datetime.combine(month_start, datetime.min.time())
    end_dt = datetime.combine(month_end, datetime.max.time())
    viewer_tokens = _audiences_for_office(ctx["office_n"])

    events = []

    manual_query = (s.query(D.CalendarEvent)
                   .filter(D.CalendarEvent.status != "deleted",
                           D.CalendarEvent.start_at <= end_dt,
                           func.coalesce(D.CalendarEvent.end_at, D.CalendarEvent.start_at) >= start_dt,
                           D.CalendarEvent.tenant_id == tenant_id))
    manual_rows = [] if campus else manual_query.order_by(D.CalendarEvent.start_at, D.CalendarEvent.title).all()
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

    academic_query = (s.query(D.AcademicCalendarEntry)
                     .filter(D.AcademicCalendarEntry.status != "deleted",
                             D.AcademicCalendarEntry.start_date <= month_end,
                             func.coalesce(D.AcademicCalendarEntry.end_date, D.AcademicCalendarEntry.start_date) >= month_start,
                             D.AcademicCalendarEntry.tenant_id == tenant_id))
    if campus:
        academic_query = academic_query.filter(D.AcademicCalendarEntry.campus.in_([campus.name, "All Campuses"]))
    academic_rows = academic_query.order_by(D.AcademicCalendarEntry.start_date, D.AcademicCalendarEntry.title).all()
    for row in academic_rows:
        acad_start = datetime.combine(row.start_date, datetime.min.time())
        acad_end = datetime.combine(row.end_date or row.start_date, datetime.max.time())
        events.append(_event_payload(
            f"acv_{row.id}", row.title, row.category, "all", acad_start, acad_end,
            all_day=True, location=row.campus, description=row.description,
            source_type="academic", source_ref=row.id, color="#2c5fb3",
            status=row.status, editable=False, module_key="academic_calendar"
        ))

    drive_rows = ([] if campus else s.query(D.PlacementDrive)
                  .filter(D.PlacementDrive.date >= month_start,
                          D.PlacementDrive.date <= month_end,
                          D.PlacementDrive.tenant_id == tenant_id).all())
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


@router.get("/academic-calendar")
def academic_calendar(term: str = "", ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academic_calendar", "view")[0])
    campus = _campus_scope_for_campus_head(s, ctx) if ctx.get("office_n") == 3 else None
    tenant_id = ctx.get("tenant_id", TENANT)
    base_query = s.query(D.AcademicCalendarEntry).filter(
        D.AcademicCalendarEntry.status != "deleted",
        D.AcademicCalendarEntry.tenant_id == tenant_id)
    if campus:
        base_query = base_query.filter(D.AcademicCalendarEntry.campus.in_([campus.name, "All Campuses"]))
    term_rows = (base_query.with_entities(D.AcademicCalendarEntry.term)
                 .distinct().order_by(D.AcademicCalendarEntry.term.desc()).all())
    term_options = [row[0] for row in term_rows]
    selected_term = term if term in term_options else (term_options[0] if term_options else "")

    query = base_query
    if selected_term:
        query = query.filter(D.AcademicCalendarEntry.term == selected_term)
    rows = query.order_by(D.AcademicCalendarEntry.start_date, D.AcademicCalendarEntry.title).all()

    summary = {
        "milestones": len(rows),
        "exam_windows": sum(1 for row in rows if "exam" in row.category.lower()),
        "breaks": sum(1 for row in rows if row.category.lower() == "break"),
        "governed_by": "Vice Chairman, Principal, Vice Principal, Chairman",
    }

    months = {}
    for row in rows:
        label = row.start_date.strftime("%b %Y")
        months[label] = months.get(label, 0) + 1

    term_window = {
        "start": rows[0].start_date.isoformat() if rows else "",
        "end": (rows[-1].end_date or rows[-1].start_date).isoformat() if rows else "",
    }

    return {
        "selected_term": selected_term,
        "term_options": term_options,
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
        } for row in rows],
    }


@router.post("/academic-calendar")
def create_academic_calendar_entry(body: AcademicCalendarIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academic_calendar", "create")
    require(dec)
    if ctx["office_n"] not in CALENDAR_ACADEMIC_EDITORS:
        raise HTTPException(403, "This office cannot manage the academic calendar")
    now = datetime.utcnow()
    row = D.AcademicCalendarEntry(
        id=uid(), tenant_id=TENANT, term=body.term, title=body.title,
        category=body.category, campus=body.campus,
        start_date=date.fromisoformat(body.start_date),
        end_date=date.fromisoformat(body.end_date) if body.end_date else date.fromisoformat(body.start_date),
        description=body.description, status=body.status or "published",
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


@router.put("/academic-calendar/{entry_id}")
def update_academic_calendar_entry(entry_id: str, body: AcademicCalendarIn, ctx=Depends(auth), s=Depends(db)):
    row = s.get(D.AcademicCalendarEntry, entry_id)
    if not row or row.status == "deleted":
        raise HTTPException(404, "Academic calendar entry not found")
    dec, _ = gate(s, ctx, "academic_calendar", "edit")
    require(dec)
    if ctx["office_n"] not in CALENDAR_ACADEMIC_EDITORS:
        raise HTTPException(403, "This office cannot manage the academic calendar")
    prev = row.status
    row.term = body.term
    row.title = body.title
    row.category = body.category
    row.campus = body.campus
    row.start_date = date.fromisoformat(body.start_date)
    row.end_date = date.fromisoformat(body.end_date) if body.end_date else row.start_date
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


@router.delete("/academic-calendar/{entry_id}")
def delete_academic_calendar_entry(entry_id: str, ctx=Depends(auth), s=Depends(db)):
    row = s.get(D.AcademicCalendarEntry, entry_id)
    if not row or row.status == "deleted":
        raise HTTPException(404, "Academic calendar entry not found")
    dec, _ = gate(s, ctx, "academic_calendar", "delete")
    require(dec)
    if ctx["office_n"] not in CALENDAR_ACADEMIC_EDITORS:
        raise HTTPException(403, "This office cannot manage the academic calendar")
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


def _student_scope(s, query, ctx):
    """Apply the authenticated campus scope using the canonical OrgScope record."""
    scope = (ctx.get("scope_ref") or "").strip()
    if ctx.get("scope_level") != "campus" or not scope:
        return query
    tenant_id = ctx.get("tenant_id", TENANT)
    campus_query = s.query(OrgScope).filter(OrgScope.tenant_id == tenant_id, OrgScope.level == "campus")
    scope_row = campus_query.filter(OrgScope.id == scope).first() if scope.startswith("scope_") else campus_query.filter(OrgScope.name == scope).first()
    if scope_row is not None:
        return query.filter(D.Student.campus == scope_row.name)
    if not scope.startswith("scope_"):
        return query.filter(D.Student.campus == scope)
    return query


def _campus_scope_for_campus_head(s, ctx):
    """Resolve Office #3 to one canonical tenant-local campus OrgScope.

    Older Campus Head identities use the verified campus name as ``scope_ref``
    (for example, ``Main Campus``).  That label is not itself authorization:
    it must resolve to exactly one campus OrgScope in the authenticated tenant.
    Canonical IDs continue to resolve directly.
    """
    if ctx.get("office_n") != 3 or ctx.get("scope_level") != "campus":
        raise HTTPException(403, "A Campus Head campus scope is required")
    tenant_id = ctx.get("tenant_id", TENANT)
    scope_id = (ctx.get("scope_ref") or "").strip()
    scopes = (s.query(OrgScope)
              .filter(OrgScope.tenant_id == tenant_id, OrgScope.level == "campus")
              .filter((OrgScope.id == scope_id) | (OrgScope.name == scope_id))
              .limit(2).all())
    if len(scopes) != 1:
        raise HTTPException(403, "A canonical campus scope is required")
    return scopes[0]


def _validated_campus_scope_assignment(s, tenant_id, campus_scope_id):
    """Validate an authoritative Asset/PlacementDrive ownership assignment.

    Assignment is nullable for legacy records, but any non-null value must be a
    campus OrgScope in the same tenant.  There are currently no asset or drive
    write endpoints; this is the server-side validation boundary for any
    future write path rather than accepting a browser-provided scope blindly.
    """
    if not campus_scope_id:
        return None
    scope = (s.query(OrgScope)
             .filter(OrgScope.id == campus_scope_id, OrgScope.tenant_id == tenant_id,
                     OrgScope.level == "campus")
             .first())
    if not scope:
        raise HTTPException(422, "campus_scope_id must reference a campus in the authenticated tenant")
    return scope


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


def _student_risk_payload(student, backlog, attendance):
    """One authoritative, explainable risk evaluation for dashboard/list/detail."""
    reasons = []
    attendance_pct = None
    if student.id in attendance:
        present, total = attendance[student.id]
        attendance_pct = round(100 * present / total, 1) if total else None
        if attendance_pct is not None and attendance_pct < 75:
            reasons.append("Attendance below 75%")
    if (student.cgpa or 0) < 6.5:
        reasons.append("CGPA below 6.5")
    if backlog.get("current", 0) > 0:
        reasons.append("Active examination backlog")
    return {"at_risk": bool(reasons), "risk_level": "At Risk" if reasons else "Normal",
            "risk_reasons": reasons, "attendance_pct": attendance_pct}


@router.get("/students")
def list_students(q: str = "", dept: str = "", program: str = "", academic_year: str = "", study_year: int = 0, semester: int = 0, section: str = "", risk: str = "", page: int = 1, page_size: int = 25, ctx=Depends(auth), s=Depends(db)):
    study_year = int(study_year or 0)
    semester = int(semester or 0)
    page = int(page or 1)
    page_size = int(page_size or 25)
    if page_size < 10: page_size = 10
    if page_size > 100: page_size = 100
    require(gate(s, ctx, "students", "view")[0])
    base_query = _student_scope(s, s.query(D.Student), ctx)
    scoped_students = base_query.all()
    query = base_query
    # Keep Principal student analytics aligned with the dashboard's current
    # academic-year scope when a caller does not explicitly choose a year.
    if not academic_year and ctx.get("office_n") == 4:
        years = {_academic_year_label(student.batch) for student in scoped_students if student.batch}
        academic_year = "2026-27" if "2026-27" in years else (max(years) if years else "")
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
            candidates = {student.id: student for student in query.all()}
            at_risk_ids = [sid for sid, student in candidates.items()
                           if _student_risk_payload(student, summaries[sid], attendance)["at_risk"]]
            query = query.filter(D.Student.id.in_(at_risk_ids))
    total = query.count()
    rows = (query.order_by(D.Student.roll_no)
            .offset((page - 1) * page_size)
            .limit(page_size).all())
    dept_map = {d.id: d for d in s.query(D.Department).all()}
    program_map = {p.id: p for p in s.query(D.Program).all()}
    all_students = query.all()
    all_backlogs = _backlog_summary(s, [student.id for student in all_students])
    attendance_totals = _attendance_totals(s, [student.id for student in all_students])
    risk_summary = {"at_risk": 0, "academic_risk": 0, "attendance_risk": 0, "attendance_available": len(attendance_totals), "average_attendance": None, "average_cgpa": None,
                    "backlogs": 0, "no_backlogs": 0}
    attendance_values = []
    cgpas = []
    for student in all_students:
        risk = _student_risk_payload(student, all_backlogs[student.id], attendance_totals)
        academic = (student.cgpa or 0) < 6.5
        current_backlogs = all_backlogs[student.id]["current"]
        if academic: risk_summary["academic_risk"] += 1
        if current_backlogs: risk_summary["backlogs"] += 1
        else: risk_summary["no_backlogs"] += 1
        if risk["attendance_pct"] is not None:
            pct = risk["attendance_pct"]
            attendance_values.append(pct)
            if pct < 75: risk_summary["attendance_risk"] += 1
        if student.cgpa is not None: cgpas.append(student.cgpa)
        if risk["at_risk"]: risk_summary["at_risk"] += 1
    if attendance_values: risk_summary["average_attendance"] = round(sum(attendance_values) / len(attendance_values), 1)
    if cgpas: risk_summary["average_cgpa"] = round(sum(cgpas) / len(cgpas), 2)
    page_backlogs = _backlog_summary(s, [row.id for row in rows])
    page_attendance = _attendance_totals(s, [row.id for row in rows])
    student_rows = []
    for r in rows:
        risk = _student_risk_payload(r, page_backlogs[r.id], page_attendance)
        student_rows.append({
            "id": r.id, "roll_no": r.roll_no, "name": r.name, "email": r.email, "dept": dept_map.get(r.dept_id).code if r.dept_id in dept_map else "", "department_name": dept_map.get(r.dept_id).name if r.dept_id in dept_map else "",
            "program": program_map.get(r.program_id).name if r.program_id in program_map else "", "program_code": program_map.get(r.program_id).code if r.program_id in program_map else "",
            "batch": r.batch, "semester": r.semester, "section": r.section, "cgpa": r.cgpa,
            "status": r.status, "hosteller": r.hosteller, "scholarship": r.scholarship,
            "current_backlogs": page_backlogs[r.id]["current"], "backlog_status": "Outstanding" if page_backlogs[r.id]["current"] else ("Cleared" if page_backlogs[r.id]["cleared"] else "No history"),
            **risk,
        })
    return {"students": student_rows, "total": total, "page": page, "page_size": page_size,
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
    student = _student_scope(s, s.query(D.Student), ctx).filter(D.Student.id == student_id).first()
    if not student:
        raise HTTPException(404, "Student was not found in your authorized campus")
    department = s.query(D.Department).get(student.dept_id)
    program = s.query(D.Program).get(student.program_id)
    attendance = s.query(D.AttendanceRecord).filter(D.AttendanceRecord.student_id == student.id).all()
    enrollments = s.query(D.Enrollment).filter(D.Enrollment.student_id == student.id).all()
    sections = {row.id: row for row in s.query(D.Section).filter(D.Section.id.in_([e.section_id for e in enrollments])).all()} if enrollments else {}
    marks = s.query(D.Mark).filter(D.Mark.student_id == student.id).all()
    backlog = _backlog_summary(s, [student.id])[student.id]
    risk = _student_risk_payload(student, backlog, _attendance_totals(s, [student.id]))
    return {"student": {"id": student.id, "name": student.name, "roll_no": student.roll_no, "email": student.email,
            "campus": student.campus, "department": department.name if department else "", "department_code": department.code if department else "",
            "program": program.name if program else "", "program_code": program.code if program else "", "semester": student.semester,
            "study_year": (student.semester + 1) // 2, "section": student.section, "status": student.status, "cgpa": student.cgpa,
            "attendance_pct": risk["attendance_pct"], "current_backlogs": backlog["current"], "cleared_backlogs": backlog["cleared"],
            "academic_year": _academic_year_label(student.batch), **risk},
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
#  ACADEMICS: courses & sections
# --------------------------------------------------------------------------- #
@router.get("/academics/courses")
def list_courses(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    dept_map = {d.id: d.code for d in s.query(D.Department).all()}
    program_map = {p.id: p.name for p in s.query(D.Program).all()}
    rows = s.query(D.Course).order_by(D.Course.code).all()
    return {"courses": [{
        "id": r.id, "code": r.code, "title": r.title, "credits": r.credits,
        "semester": r.semester, "dept": dept_map.get(r.dept_id, ""),
        "program": program_map.get(r.program_id, "B.Tech"), "regulation": r.regulation or "R2023",
        "course_type": r.course_type or "Core", "category": r.category or "Professional Core",
        "ltp": r.ltp or "", "prerequisite": r.prerequisite or "", "status": r.status or "Active",
        "description": r.description or "",
    } for r in rows], "can_create": can(s, ctx, "academics", "create_course")}


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


@router.post("/academics/courses")
def create_course(body: CourseIn, ctx=Depends(auth), s=Depends(db)):
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


@router.get("/academics/sections")
def list_sections(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    course_map = {c.id: (c.code, c.title) for c in s.query(D.Course).all()}
    fac_map = {f.id: f.name for f in s.query(D.StaffMember).all()}
    rows = s.query(D.Section).limit(200).all()
    out = []
    for r in rows:
        cc, ct = course_map.get(r.course_id, ("", ""))
        enrolled = s.query(D.Enrollment).filter(D.Enrollment.section_id == r.id,
                                                D.Enrollment.status == "enrolled").count()
        out.append({"id": r.id, "course_code": cc, "course_title": ct,
                    "section": r.section_code, "term": r.term,
                    "faculty": fac_map.get(r.faculty_person_id, "—"),
                    "room": r.room, "schedule": r.schedule,
                    "enrolled": enrolled, "capacity": r.capacity})
    return {"sections": out,
            "can_create": can(s, ctx, "academics", "create_section"),
            "can_assign": can(s, ctx, "academics", "assign_faculty")}


class SectionIn(BaseModel):
    course_id: str
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
    sid = uid()
    s.add(D.Section(id=sid, tenant_id=TENANT, course_id=c.id, dept_id=c.dept_id,
                    term="2025-Odd", section_code=body.section_code,
                    faculty_person_id=body.faculty_id or None, room=body.room,
                    schedule=body.schedule, capacity=60, scope_ref=c.dept_id))
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "section.create",
                f"section:{sid}", "", "open", f"Section {c.code}-{body.section_code}")
    return {"id": sid, "decision": dec.as_dict()}


@router.get("/academics/section/{section_id}/timetable")
def section_timetable(section_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    section = _section_or_404(s, section_id)
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


class TimetableEntryIn(BaseModel):
    day_of_week: int
    start_time: str
    end_time: str
    room: str = ""
    building: str = ""
    effective_from: str = ""
    effective_to: str = ""


@router.post("/academics/section/{section_id}/timetable")
def create_timetable_entry(section_id: str, body: TimetableEntryIn, ctx=Depends(auth), s=Depends(db)):
    dec, _ = gate(s, ctx, "academics", "manage_timetable")
    require(dec)
    section = _section_or_404(s, section_id)
    if not _can_manage_section_for_timetable(s, ctx, section):
        raise HTTPException(403, "You are not authorized to manage the timetable for this section")
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
    row = s.query(D.TimetableEntry).get(entry_id)
    if not row:
        raise HTTPException(404, "Timetable entry not found")
    section = _section_or_404(s, row.section_id)
    if not _can_manage_section_for_timetable(s, ctx, section):
        raise HTTPException(403, "You are not authorized to manage the timetable for this section")
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
    row = s.query(D.TimetableEntry).get(entry_id)
    if not row:
        raise HTTPException(404, "Timetable entry not found")
    section = _section_or_404(s, row.section_id)
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


@router.get("/academics/section/{section_id}/assignments")
def section_assignments(section_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    rows = (s.query(D.Assignment)
            .filter(D.Assignment.section_id == section_id)
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
    section = _section_or_404(s, section_id)
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
    row = s.query(D.Assignment).get(assignment_id)
    if not row:
        raise HTTPException(404, "Assignment not found")
    section = _section_or_404(s, row.section_id)
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
    course_map = {c.id: (c.code, c.title) for c in s.query(D.Course).all()}
    rows = s.query(D.Section).limit(100).all()
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
    enr = s.query(D.Enrollment).filter(D.Enrollment.section_id == section_id,
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
    present_ids: list[str] = []
    absent_ids: list[str] = []
    on_date: str = ""


@router.post("/attendance/mark")
def mark_attendance(body: MarkAttendanceIn, ctx=Depends(auth), s=Depends(db)):
    dec, verb = gate(s, ctx, "attendance", "mark")
    require(dec)
    d = date.fromisoformat(body.on_date) if body.on_date else date.today()
    who = actor_name(s, ctx)

    def upsert(student_id: str, present: bool):
        row = (
            s.query(D.AttendanceRecord)
            .filter(
                D.AttendanceRecord.section_id == body.section_id,
                D.AttendanceRecord.student_id == student_id,
                D.AttendanceRecord.on_date == d,
            )
            .first()
        )
        if row is None:
            row = D.AttendanceRecord(
                id=uid(),
                tenant_id=TENANT,
                section_id=body.section_id,
                student_id=student_id,
                on_date=d,
            )
            s.add(row)
        row.present = present
        row.status = "present" if present else "absent"
        row.note = ""
        row.marked_by = who
        row.updated_at = datetime.utcnow()

    for sid in body.present_ids:
        upsert(sid, True)
    for sid in body.absent_ids:
        upsert(sid, False)
    s.commit()
    n = len(body.present_ids) + len(body.absent_ids)
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
    section = _section_or_404(s, section_id)
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
    section = _section_or_404(s, body.section_id)
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
        existing = s.query(D.Mark).filter(D.Mark.assessment_id == a.id,
                                          D.Mark.student_id == stu_id).first()
        if existing:
            existing.score = float(score)
            existing.status = "draft"
            existing.updated_at = datetime.utcnow()
        else:
            s.add(D.Mark(id=uid(), tenant_id=TENANT, assessment_id=a.id,
                         student_id=stu_id, score=float(score), entered_by=who,
                         status="draft", updated_at=datetime.utcnow()))
    s.commit()
    write_audit(s, ctx["sub"], who, ctx["office_n"], "marks.enter",
                f"assessment:{a.id}", "", "entered", f"Entered {len(body.marks)} marks for {a.name}")
    return {"entered": len(body.marks), "decision": dec.as_dict()}


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


@router.post("/exams/publish")
def publish_result(body: PublishResultIn, ctx=Depends(auth), s=Depends(db)):
    # Result publication is a distinct authority from marks entry (SoD invariant).
    dec, verb = gate(s, ctx, "examinations", "publish_result")
    require(dec)
    who = actor_name(s, ctx)
    section = _section_or_404(s, body.section_id)
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
    s.commit()
    write_audit(s, ctx["sub"], who, ctx["office_n"], "result.publish",
                f"section:{body.section_id}", "moderated", "published",
                "Result published")
    return {"status": "published", "published_results": published_rows, "decision": dec.as_dict()}


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
@router.get("/finance/invoices")
def list_invoices(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "view")[0])
    tenant_id = ctx.get("tenant_id", TENANT)
    invoice_query = s.query(D.FeeInvoice).filter(D.FeeInvoice.tenant_id == tenant_id)
    student_query = s.query(D.Student).filter(D.Student.tenant_id == tenant_id)
    if ctx.get("office_n") == 3:
        campus = _campus_scope_for_campus_head(s, ctx)
        student_query = student_query.filter(D.Student.campus == campus.name)
        invoice_query = invoice_query.join(D.Student, D.FeeInvoice.student_id == D.Student.id).filter(
            D.Student.tenant_id == tenant_id, D.Student.campus == campus.name)
    stu_map = {st.id: (st.roll_no, st.name) for st in student_query.all()}
    rows = invoice_query.limit(300).all()
    out = []
    for r in rows:
        roll, name = stu_map.get(r.student_id, ("", ""))
        out.append({"id": r.id, "roll_no": roll, "name": name, "term": r.term,
                    "amount": r.amount, "paid": r.paid, "balance": r.amount - r.paid,
                    "status": r.status})
    summary = {
        "total_billed": invoice_query.with_entities(func.coalesce(func.sum(D.FeeInvoice.amount), 0)).scalar() or 0,
        "total_collected": invoice_query.with_entities(func.coalesce(func.sum(D.FeeInvoice.paid), 0)).scalar() or 0,
        "outstanding": invoice_query.with_entities(func.coalesce(func.sum(D.FeeInvoice.amount - D.FeeInvoice.paid), 0)).scalar() or 0,
    }
    return {"invoices": out, "summary": summary,
            "can_record": can(s, ctx, "finance", "record_payment"),
            "can_waive": can(s, ctx, "finance", "waive")}


@router.get("/finance/budget")
def list_budget(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "view")[0])
    query = s.query(D.BudgetLine).filter(D.BudgetLine.tenant_id == ctx.get("tenant_id", TENANT))
    if ctx.get("office_n") == 3 and ctx.get("scope_level") == "campus":
        campus = _campus_scope_for_campus_head(s, ctx)
        query = query.filter(D.BudgetLine.campus == campus.name)
    rows = query.all()
    return {"budget": [{"category": b.category, "allocated": b.allocated,
                        "spent": b.spent, "remaining": b.allocated - b.spent,
                        "fiscal_year": b.fiscal_year} for b in rows],
            "can_approve": can(s, ctx, "finance", "approve_budget")}


class RecordPaymentIn(BaseModel):
    invoice_id: str
    amount: float


@router.post("/finance/payment")
def record_payment(body: RecordPaymentIn, ctx=Depends(auth), s=Depends(db)):
    dec, verb = gate(s, ctx, "finance", "record_payment", amount=body.amount)
    require(dec)
    inv = s.query(D.FeeInvoice).get(body.invoice_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    inv.paid = min(inv.amount, inv.paid + body.amount)
    inv.status = "paid" if inv.paid >= inv.amount else "partial"
    s.add(D.Payment(id=uid(), tenant_id=TENANT, invoice_id=inv.id, student_id=inv.student_id,
                    amount=body.amount, method="counter", reference=f"RC{uid().upper()}"))
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "fee.payment",
                f"invoice:{inv.id}", "", inv.status, f"Recorded ₹{body.amount:,.0f}")
    return {"status": inv.status, "paid": inv.paid, "decision": dec.as_dict()}


class WaiveIn(BaseModel):
    invoice_id: str
    amount: float
    reason: str = ""


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
    rows = (s.query(D.LeaveRequest)
            .filter(D.LeaveRequest.tenant_id == ctx.get("tenant_id", TENANT))
            .order_by(desc(D.LeaveRequest.id)).all())
    staff = {row.id: row for row in s.query(D.StaffMember).filter(D.StaffMember.tenant_id == ctx.get("tenant_id", TENANT)).all()}
    if ctx.get("scope_level") == "campus":
        rows = [row for row in rows if staff.get(row.staff_id) and staff[row.staff_id].campus == ctx.get("scope_ref")]
    return {"leave": [{"id": l.id, "staff": l.staff_name, "kind": l.kind,
                       "from": l.from_date.isoformat(), "to": l.to_date.isoformat(),
                       "days": l.days, "reason": l.reason, "status": l.status}
                      for l in rows],
            "can_approve": can(s, ctx, "hr", "approve_leave")}


@router.get("/hr/jobs")
def list_jobs(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "hr", "view")[0])
    rows = s.query(D.JobPosting).all()
    return {"jobs": [{"id": j.id, "title": j.title, "dept": j.dept, "kind": j.kind,
                      "openings": j.openings, "status": j.status} for j in rows],
              "can_post": can(s, ctx, "hr", "post_job")}


@router.get("/faculty-staff")
def faculty_staff(q: str = "", dept: str = "", kind: str = "", designation: str = "", status: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=10, le=100), ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "hr", "view")[0])
    tenant_id = ctx.get("tenant_id", TENANT)
    query = s.query(D.StaffMember).filter(D.StaffMember.tenant_id == tenant_id)
    if ctx.get("office_n") == 3:
        campus = _campus_scope_for_campus_head(s, ctx)
        query = query.filter(D.StaffMember.campus == campus.name)
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
    all_rows = query.all()
    teaching = sum(1 for row in all_rows if "professor" in (row.designation or "").lower())
    scoped_leave_ids = {row.id for row in all_rows if row.id in on_leave_ids}
    scoped_dept_ids = {row.dept_id for row in all_rows if row.dept_id}
    summary = {"total": len(all_rows), "teaching": teaching,
               "non_teaching": len(all_rows) - teaching,
               "on_leave": len(scoped_leave_ids),
               "vacancies": None if ctx.get("office_n") == 3 else sum(job.openings for job in s.query(D.JobPosting).filter(D.JobPosting.status == "open").all())}
    return {"staff": [{"id": row.id, "employee_id": row.emp_id, "name": row.name, "email": row.email, "department": departments[row.dept_id].name if row.dept_id in departments else "Administration", "department_code": departments[row.dept_id].code if row.dept_id in departments else "", "designation": row.designation, "type": "Teaching" if "professor" in (row.designation or "").lower() else "Non-Teaching", "status": row.status, "campus": row.campus, "on_leave": row.id in on_leave_ids} for row in rows], "total": total, "page": page, "page_size": page_size, "total_pages": max(1, (total + page_size - 1) // page_size), "summary": summary, "departments": [{"code": d.code, "name": d.name} for d in departments.values() if d.id in scoped_dept_ids], "designations": sorted(set(row.designation for row in all_rows if row.designation)), "statuses": sorted(set(row.status for row in all_rows if row.status))}


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
    if body.action not in ("approve", "reject"):
        raise HTTPException(400, "Invalid leave decision")
    act = "approve_leave" if body.action == "approve" else "reject_leave"
    dec, verb = gate(s, ctx, "hr", act)
    require(dec)
    l = s.query(D.LeaveRequest).get(body.leave_id)
    if not l:
        raise HTTPException(404, "Leave request not found")
    if l.tenant_id != ctx.get("tenant_id", TENANT):
        raise HTTPException(403, "Leave request is outside your authorized tenant")
    staff = s.query(D.StaffMember).get(l.staff_id)
    if ctx.get("scope_level") == "campus" and (not staff or staff.campus != ctx.get("scope_ref")):
        raise HTTPException(403, "Leave request is outside your authorized campus")
    if l.status != "pending":
        raise HTTPException(409, "This leave request has already been decided")
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
def list_assets(q: str = "", category: str = "", status: str = "", ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "assets", "view")[0])
    tenant_id = ctx.get("tenant_id", TENANT)
    campus = None
    if ctx.get("office_n") == 3:
        campus = _campus_scope_for_campus_head(s, ctx)
    scope_query = s.query(D.Asset).filter(D.Asset.tenant_id == tenant_id)
    if campus:
        scope_query = scope_query.filter(D.Asset.campus_scope_id == campus.id)
    query = scope_query
    if q:
        like = f"%{q}%"
        query = query.filter((D.Asset.tag.ilike(like)) | (D.Asset.name.ilike(like)) | (D.Asset.location.ilike(like)))
    if category:
        query = query.filter(D.Asset.category == category)
    if status:
        query = query.filter(D.Asset.status == status)
    rows = query.order_by(D.Asset.tag).all()
    all_rows = scope_query.order_by(D.Asset.tag).all()
    if campus and not all_rows:
        return {"assets": [], "categories": [], "statuses": [], "category_summary": [],
                "summary": {}, "can_add": False, "data_status": "unavailable",
                "reason": "No campus-owned asset records are available."}
    assets = [{"id": a.id, "tag": a.tag, "name": a.name, "category": a.category,
                        "location": a.location, "status": a.status, "value": a.value}
                       for a in rows]
    return {"assets": assets,
            "categories": sorted({a.category for a in all_rows if a.category}),
            "statuses": sorted({a.status for a in all_rows if a.status}),
            "category_summary": [{"category": category_name, "count": sum(a.category == category_name for a in all_rows),
                                  "book_value": sum(a.value or 0 for a in all_rows if a.category == category_name)}
                                 for category_name in sorted({a.category for a in all_rows if a.category})],
            "summary": {"total": len(all_rows), "book_value": sum(a.value or 0 for a in all_rows), "in_service": sum(a.status == "in-service" for a in all_rows), "maintenance": sum(a.status == "maintenance" for a in all_rows)},
            "can_add": can(s, ctx, "assets", "add"),
            "campus_scope_id": campus.id if campus else None,
            "data_status": "available"}


@router.get("/procurement")
def procurement(ctx=Depends(auth), s=Depends(db)):
    """Completed procurement records from the existing asset register.

    The schema has no requisition or PO table, so those arrays remain honestly
    empty instead of fabricating operational records.
    """
    require(gate(s, ctx, "procurement", "view")[0])
    rows = (s.query(D.Asset).filter(D.Asset.tenant_id == ctx.get("tenant_id", TENANT))
            .order_by(D.Asset.id.desc()).all())
    requests = (s.query(WorkflowInstance).filter(WorkflowInstance.tenant_id == ctx.get("tenant_id", TENANT), WorkflowInstance.process_key == "purchase_request")
                .order_by(WorkflowInstance.updated_at.desc()).all())
    return {"assets": [{"id": a.id, "tag": a.tag, "item": a.name, "category": a.category,
                         "location": a.location, "value": a.value, "status": a.status}
                        for a in rows],
            "requisitions": [{"id": item.id, "title": item.title, "amount": item.amount,
                                "state": item.state, "escalated": item.escalated,
                                "initiator": item.initiator_name, "updated_at": item.updated_at.isoformat()}
                               for item in requests],
            "purchase_orders": []}


@router.get("/approval-history")
def approval_history(q: str = "", action: str = "", ctx=Depends(auth), s=Depends(db)):
    """Actual approval decisions relevant to the signed-in Principal."""
    require(gate(s, ctx, "approvals", "view")[0])
    query = (s.query(Approval, WorkflowInstance)
             .join(WorkflowInstance, Approval.workflow_id == WorkflowInstance.id)
             .filter(WorkflowInstance.tenant_id == ctx.get("tenant_id", TENANT)))
    if action:
        query = query.filter(Approval.decision == action.upper())
    if q:
        like = f"%{q}%"
        query = query.filter(or_(WorkflowInstance.title.ilike(like), WorkflowInstance.label.ilike(like), Approval.actor_name.ilike(like)))
    rows = query.order_by(Approval.created_at.desc()).limit(200).all()
    return {"events": [{"id": approval.id, "workflow_id": workflow.id, "request": workflow.title,
                         "module": workflow.label, "requested_by": workflow.initiator_name,
                         "action": approval.decision, "approver": approval.actor_name,
                         "reason": approval.reason, "at": approval.created_at.isoformat(),
                         "state": workflow.state}
                        for approval, workflow in rows]}


@router.get("/escalations")
def escalations(q: str = "", state: str = "", ctx=Depends(auth), s=Depends(db)):
    """Workflow escalation views, plus Principal-visible campus risk escalations."""
    require(gate(s, ctx, "approvals", "view")[0])
    if ctx.get("office_n") == 3:
        return phase5d_escalations(status=state, ctx=ctx, s=s)
    query = s.query(WorkflowInstance).filter(WorkflowInstance.tenant_id == ctx.get("tenant_id", TENANT), WorkflowInstance.escalated.is_(True))
    if state:
        query = query.filter(WorkflowInstance.state == state)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(WorkflowInstance.title.ilike(like), WorkflowInstance.label.ilike(like), WorkflowInstance.initiator_name.ilike(like)))
    workflows = query.order_by(WorkflowInstance.updated_at.desc()).all()
    destinations = {item["key"]: item.get("escalation", "") for item in APPROVAL_MATRIX}
    outgoing_ids = {row[0] for row in s.query(Approval.workflow_id).filter(Approval.actor_id == ctx["sub"], Approval.decision == "ESCALATE").all()}
    def row(workflow):
        return {"id": workflow.id, "reference": workflow.id, "module": workflow.label,
                "title": workflow.title, "from": workflow.initiator_name,
                "to": destinations.get(workflow.process_key, ""), "status": workflow.state,
                "created_at": workflow.created_at.isoformat(), "updated_at": workflow.updated_at.isoformat()}
    incoming = [row(item) for item in workflows if "principal" in destinations.get(item.process_key, "").lower()]

    # Campus risk escalations are persisted separately from workflow-state
    # escalations.  A Principal must see only records explicitly routed to the
    # Principal; this supplements the existing workflow list without changing
    # its outgoing behaviour or any other office's visibility.
    if ctx.get("office_n") == 4:
        risk_query = s.query(D.EscalationRecord).filter(
            D.EscalationRecord.tenant_id == ctx.get("tenant_id", TENANT),
            D.EscalationRecord.destination_office_n == 4,
        )
        if state and state.upper() in ESCALATION_STATUSES:
            risk_query = risk_query.filter(D.EscalationRecord.status == state.upper())
        risk_rows = risk_query.order_by(desc(D.EscalationRecord.updated_at)).all()
        for escalation in risk_rows:
            risk = (s.query(D.RiskRecord)
                    .filter(D.RiskRecord.id == escalation.source_ref,
                            D.RiskRecord.tenant_id == escalation.tenant_id)
                    .first()) if escalation.source_type == "risk" else None
            initiator = actor_name(s, {"sub": escalation.created_by})
            item = {
                "id": escalation.id,
                "reference": escalation.id,
                "module": "Campus risk escalation",
                "title": risk.title if risk else escalation.reason,
                "from": initiator,
                "to": office(escalation.destination_office_n).get("name", ""),
                "status": escalation.status,
                "created_at": escalation.created_at.isoformat(),
                "updated_at": escalation.updated_at.isoformat(),
            }
            if not q or any(q.lower() in str(value).lower() for value in (
                item["title"], item["from"], item["module"], escalation.reason,
            )):
                incoming.append(item)
        incoming.sort(key=lambda item: item["updated_at"], reverse=True)
    return {"incoming": incoming,
            "outgoing": [row(item) for item in workflows if item.id in outgoing_ids]}


# --------------------------------------------------------------------------- #
#  HOSTEL / TRANSPORT
# --------------------------------------------------------------------------- #
def _hostel_scoped(query, model, ctx):
    """Apply server-side tenant/campus scope; the browser never supplies either."""
    query = query.filter(model.tenant_id == ctx.get("tenant_id", TENANT))
    if ctx.get("scope_level") == "campus":
        query = query.filter(model.campus == ctx.get("scope_ref"))
    return query


def _hostel_request_or_404(s, alloc_id: str, ctx, lock: bool = False):
    query = _hostel_scoped(s.query(D.HostelAllocation), D.HostelAllocation, ctx).filter(D.HostelAllocation.id == alloc_id)
    if lock:
        query = query.with_for_update()
    allocation = query.first()
    if not allocation:
        raise HTTPException(404, "Allocation request was not found in your authorized tenant or campus")
    return allocation


@router.get("/hostel")
def hostel(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "hostel", "view")[0])
    rooms = _hostel_scoped(s.query(D.HostelRoom), D.HostelRoom, ctx).all()
    allocs = (_hostel_scoped(s.query(D.HostelAllocation), D.HostelAllocation, ctx)
              .filter(D.HostelAllocation.status == "requested").all())
    cap = sum(r.capacity for r in rooms)
    occ = sum(r.occupied for r in rooms)
    return {"summary": {"rooms": len(rooms), "capacity": cap, "occupied": occ,
                        "vacant": cap - occ},
            "requests": [{"id": a.id, "student": a.student_name, "status": a.status}
                         for a in allocs],
            "can_allocate": can(s, ctx, "hostel", "allocate")}


@router.get("/hostel/available-rooms/{alloc_id}")
def available_hostel_rooms(alloc_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "hostel", "allocate")[0])
    allocation = _hostel_request_or_404(s, alloc_id, ctx)
    if allocation.status != "requested":
        raise HTTPException(409, "This allocation request has already been decided")
    rooms = (_hostel_scoped(s.query(D.HostelRoom), D.HostelRoom, ctx)
             .filter(D.HostelRoom.occupied < D.HostelRoom.capacity)
             .order_by(D.HostelRoom.block, D.HostelRoom.room_no).all())
    return {"request": {"id": allocation.id, "student": allocation.student_name},
            "rooms": [{"id": room.id, "block": room.block, "room_no": room.room_no,
                       "capacity": room.capacity, "occupied": room.occupied,
                       "vacant": room.capacity - room.occupied} for room in rooms]}


class HostelAllocationIn(BaseModel):
    room_id: str


@router.post("/hostel/allocate/{alloc_id}")
def allocate_hostel(alloc_id: str, body: HostelAllocationIn, ctx=Depends(auth), s=Depends(db)):
    dec, verb = gate(s, ctx, "hostel", "allocate")
    require(dec)
    a = _hostel_request_or_404(s, alloc_id, ctx, lock=True)
    if a.status != "requested":
        raise HTTPException(409, "This allocation request has already been decided")
    if a.student_id and (s.query(D.HostelAllocation)
                         .filter(D.HostelAllocation.tenant_id == ctx.get("tenant_id", TENANT),
                                 D.HostelAllocation.student_id == a.student_id,
                                 D.HostelAllocation.status == "allocated",
                                 D.HostelAllocation.id != a.id).first()):
        raise HTTPException(409, "This student already has an active hostel allocation")
    room = (_hostel_scoped(s.query(D.HostelRoom), D.HostelRoom, ctx)
            .filter(D.HostelRoom.id == body.room_id).with_for_update().first())
    if not room:
        raise HTTPException(404, "Room was not found in your authorized tenant or campus")
    if room.occupied >= room.capacity:
        raise HTTPException(409, "This room is no longer available")
    a.room_id = room.id
    a.status = "allocated"
    room.occupied += 1
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "hostel.allocate",
                f"alloc:{alloc_id}", "requested", "allocated",
                f"Allocated {room.block} {room.room_no} to {a.student_name}")
    return {"status": "allocated", "room": {"id": room.id, "block": room.block, "room_no": room.room_no},
            "decision": dec.as_dict()}


@router.get("/transport")
def transport(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "transport", "view")[0])
    rows = s.query(D.TransportRoute).all()
    return {"routes": [{"id": r.id, "name": r.name, "stops": r.stops,
                        "vehicle": r.vehicle_no, "seats": r.seats,
                        "taken": r.seats_taken, "free": r.seats - r.seats_taken}
                       for r in rows]}


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
    tenant_id = ctx.get("tenant_id", TENANT)
    campus = None
    if ctx.get("office_n") == 3:
        campus = _campus_scope_for_campus_head(s, ctx)
    rows = s.query(D.PlacementDrive).filter(D.PlacementDrive.tenant_id == tenant_id)
    if campus:
        rows = rows.filter(D.PlacementDrive.campus_scope_id == campus.id)
    rows = rows.order_by(desc(D.PlacementDrive.ctc)).all()
    if campus and not rows:
        return {"drives": [], "summary": {}, "can_add": False,
                "data_status": "unavailable",
                "reason": "No campus-owned placement drive records are available."}
    placed = sum(d.offers or 0 for d in rows)
    top = max([r.ctc for r in rows], default=0)
    return {"drives": [{"id": d.id, "company": d.company, "role": d.role, "ctc": d.ctc,
                        "date": d.date.isoformat() if d.date else "", "eligible_cgpa": d.eligible_cgpa,
                        "status": d.status, "offers": d.offers} for d in rows],
            "summary": {"offers": placed, "top_ctc": top, "drives": len(rows)},
            "can_add": can(s, ctx, "placements", "add_drive"),
            "campus_scope_id": campus.id if campus else None,
            "data_status": "available"}


# --------------------------------------------------------------------------- #
#  GRIEVANCE
# --------------------------------------------------------------------------- #
@router.get("/grievance")
def grievance(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "grievance", "view")[0])
    if ctx.get("office_n") == 3:
        _campus_scope_for_campus_head(s, ctx)
        # Complaints contain no campus or authoritative linked owner.
        return {"complaints": [], "can_resolve": False, "can_raise": False,
                "data_status": "unavailable",
                "reason": "Campus ownership is not recorded for grievances."}
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
#  CAMPUS ESCALATIONS & REPORTING
# ---------------------------------------------------------------------------
ESCALATION_PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
ESCALATION_STATUSES = {"DRAFT", "SUBMITTED", "RECEIVED", "FOLLOW_UP", "RESOLVED", "CLOSED"}
REPORT_TYPES = {"MONTHLY_CAMPUS_REPORT", "IMMEDIATE_RISK_EXCEPTION_REPORT"}
REPORT_STATUSES = {"DRAFT", "SUBMITTED", "VC_REVIEW", "RETURNED", "RESUBMITTED", "APPROVED"}


def _phase5d_scope(s, ctx):
    if ctx.get("office_n") not in (1, 2, 3, 4):
        raise HTTPException(403, "This action is restricted to authorized escalation/report offices")
    tenant_id = ctx.get("tenant_id", TENANT)
    query = s.query(OrgScope).filter(OrgScope.tenant_id == tenant_id, OrgScope.level == "campus")
    ref = (ctx.get("scope_ref") or "").strip()
    scope = query.filter(OrgScope.id == ref).first() if ref.startswith("scope_") else query.filter(OrgScope.name == ref).first()
    if ctx.get("office_n") in (3, 4) and not scope:
        raise HTTPException(403, "A canonical campus scope is required")
    return scope


def _phase5d_gate(s, ctx, module, action):
    decision, _ = gate(s, ctx, module, action)
    require(decision)
    return decision


def _escalation_destination(s, source_type, source_ref, priority, ctx):
    category = ""
    if source_type == "risk":
        risk, _ = _risk_or_404(s, source_ref, ctx)
        category = risk.category
    if priority == "CRITICAL":
        if category == "Operations":
            return 2, "Vice Chairman", [4]
        if category in ("Safety", "Compliance", "Administration"):
            return 1, "Chairman", [2]
        return 2, "Vice Chairman", [4]
    if priority == "HIGH":
        if category in ("Academic", "Student", "Faculty/Workforce", "Compliance"):
            return 4, "Principal", []
        return 2, "Vice Chairman", []
    return 4, "Principal", []


def _escalation_event(s, row, ctx, event_type, previous, current, reason=""):
    event = D.EscalationEvent(id=uid(), tenant_id=ctx.get("tenant_id", TENANT), escalation_id=row.id,
                              actor_id=ctx["sub"], event_type=event_type, reason=reason,
                              previous_status=previous, new_status=current)
    s.add(event); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], f"escalation.{event_type}", f"escalation:{row.id}", previous, current, reason, ctx.get("auth_level", "mfa"))


def _escalation_payload(s, row):
    return {"id": row.id, "tenant_id": row.tenant_id, "campus_scope_id": row.campus_scope_id,
            "created_by": row.created_by, "owner_id": row.owner_id, "owner": _risk_owner_name(s, row.owner_id),
            "source_type": row.source_type, "source_ref": row.source_ref, "reason": row.reason,
            "priority": row.priority, "destination_office_n": row.destination_office_n,
            "destination_user_id": row.destination_user_id, "destination": office(row.destination_office_n).get("name", ""),
            "status": row.status, "due_at": row.due_at.isoformat() if row.due_at else None,
            "received_at": row.received_at.isoformat() if row.received_at else None,
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
            "closed_at": row.closed_at.isoformat() if row.closed_at else None,
            "resolution_notes": row.resolution_notes, "workflow_id": row.workflow_id,
            "overdue": bool(row.due_at and row.due_at < datetime.utcnow() and row.status not in ("RESOLVED", "CLOSED")),
            "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}


class EscalationCreateIn(BaseModel):
    source_type: str
    source_ref: str
    reason: str
    priority: str
    owner_id: str | None = None
    due_at: datetime | None = None


class EscalationUpdateIn(BaseModel):
    reason: str | None = None
    owner_id: str | None = None
    due_at: datetime | None = None


class Phase5DReasonIn(BaseModel):
    reason: str = ""
    feedback: str = ""


class ReportCreateIn(BaseModel):
    report_type: str
    period_start: date
    period_end: date
    title: str


class ReportUpdateIn(BaseModel):
    title: str | None = None
    period_start: date | None = None
    period_end: date | None = None


class ReportFeedbackIn(BaseModel):
    feedback: str = ""


def _escalation_or_404(s, escalation_id, ctx):
    campus = _phase5d_scope(s, ctx)
    query = s.query(D.EscalationRecord).filter(D.EscalationRecord.id == escalation_id,
                                               D.EscalationRecord.tenant_id == ctx.get("tenant_id", TENANT))
    if ctx.get("office_n") == 3:
        query = query.filter(D.EscalationRecord.campus_scope_id == campus.id)
    row = query.first()
    if not row:
        raise HTTPException(404, "Escalation not found")
    return row


@router.get("/escalations")
def phase5d_escalations(status: str = "", priority: str = "", source_type: str = "", destination_office_n: int | None = None, ctx=Depends(auth), s=Depends(db)):
    _phase5d_gate(s, ctx, "escalations", "view")
    query = s.query(D.EscalationRecord).filter(D.EscalationRecord.tenant_id == ctx.get("tenant_id", TENANT))
    campus = _phase5d_scope(s, ctx)
    if ctx.get("office_n") == 3:
        query = query.filter(D.EscalationRecord.campus_scope_id == campus.id)
    if status:
        if status not in ESCALATION_STATUSES: raise HTTPException(400, "Unknown escalation status")
        query = query.filter(D.EscalationRecord.status == status)
    if priority:
        if priority not in ESCALATION_PRIORITIES: raise HTTPException(400, "Unknown escalation priority")
        query = query.filter(D.EscalationRecord.priority == priority)
    if source_type: query = query.filter(D.EscalationRecord.source_type == source_type)
    if destination_office_n: query = query.filter(D.EscalationRecord.destination_office_n == destination_office_n)
    rows = query.order_by(desc(D.EscalationRecord.updated_at)).all()
    return {"escalations": [_escalation_payload(s, row) for row in rows], "total": len(rows)}


@router.post("/escalations")
def create_escalation(body: EscalationCreateIn, ctx=Depends(auth), s=Depends(db)):
    decision = _phase5d_gate(s, ctx, "escalations", "create")
    campus = _phase5d_scope(s, ctx)
    if body.priority not in ESCALATION_PRIORITIES or body.source_type != "risk":
        raise HTTPException(400, "Escalations must reference a supported risk source and priority")
    risk, _ = _risk_or_404(s, body.source_ref, ctx)
    destination_office, _, additional_offices = _escalation_destination(s, body.source_type, body.source_ref, body.priority, ctx)
    owner = _risk_owner_for_scope(s, body.owner_id, campus, ctx.get("tenant_id", TENANT)) if body.owner_id else None
    escalation_id = uid()
    row = D.EscalationRecord(id=escalation_id, tenant_id=ctx.get("tenant_id", TENANT), campus_scope_id=campus.id,
                             created_by=ctx["sub"], owner_id=owner.id if owner else risk.owner_id,
                             source_type=body.source_type, source_ref=body.source_ref, reason=body.reason.strip(),
                             priority=body.priority, destination_office_n=destination_office, status="DRAFT", due_at=body.due_at)
    s.add(row); s.commit(); _escalation_event(s, row, ctx, "create", "", "DRAFT", row.reason)
    return {"escalation": _escalation_payload(s, row), "decision": decision.as_dict(), "additional_destinations": additional_offices}


@router.post("/risks/{risk_id}/escalations")
def create_risk_escalation(risk_id: str, body: EscalationCreateIn, ctx=Depends(auth), s=Depends(db)):
    body.source_type = "risk"; body.source_ref = risk_id
    return create_escalation(body, ctx, s)


@router.get("/escalations/{escalation_id}")
def get_escalation(escalation_id: str, ctx=Depends(auth), s=Depends(db)):
    _phase5d_gate(s, ctx, "escalations", "view")
    row = _escalation_or_404(s, escalation_id, ctx)
    events = s.query(D.EscalationEvent).filter(D.EscalationEvent.escalation_id == row.id).order_by(D.EscalationEvent.created_at).all()
    return {"escalation": _escalation_payload(s, row), "events": [{"id": e.id, "event_type": e.event_type, "reason": e.reason, "previous_status": e.previous_status, "new_status": e.new_status, "created_at": e.created_at.isoformat()} for e in events]}


@router.patch("/escalations/{escalation_id}")
def update_escalation(escalation_id: str, body: EscalationUpdateIn, ctx=Depends(auth), s=Depends(db)):
    decision = _phase5d_gate(s, ctx, "escalations", "edit")
    row = _escalation_or_404(s, escalation_id, ctx)
    if row.created_by != ctx["sub"] or row.status not in ("DRAFT", "FOLLOW_UP"):
        raise HTTPException(403, "Only the creator may edit a draft or follow-up escalation")
    if body.reason is not None: row.reason = body.reason.strip()
    if body.due_at is not None: row.due_at = body.due_at
    if body.owner_id is not None: row.owner_id = _risk_owner_for_scope(s, body.owner_id, _phase5d_scope(s, ctx), ctx.get("tenant_id", TENANT)).id
    row.updated_at = datetime.utcnow(); s.commit(); _escalation_event(s, row, ctx, "follow_up", row.status, row.status, row.reason)
    return {"escalation": _escalation_payload(s, row), "decision": decision.as_dict()}


def _change_escalation(escalation_id, target, event_type, body, ctx, s):
    action = ("submit" if target == "SUBMITTED" else
              "receive" if target == "RECEIVED" else
              "follow_up" if target == "FOLLOW_UP" else
              "resolve" if target == "RESOLVED" else
              "close")
    decision = _phase5d_gate(s, ctx, "escalations", action)
    row = _escalation_or_404(s, escalation_id, ctx); previous = row.status
    allowed = {"SUBMITTED": {"DRAFT"}, "RECEIVED": {"SUBMITTED"}, "FOLLOW_UP": {"RECEIVED", "SUBMITTED"}, "RESOLVED": {"FOLLOW_UP", "RECEIVED", "SUBMITTED"}, "CLOSED": {"RESOLVED"}}
    if previous not in allowed[target]: raise HTTPException(409, f"Cannot transition escalation from {previous} to {target}")
    if target == "CLOSED" and row.created_by == ctx["sub"] and ctx.get("office_n") == 3:
        raise HTTPException(403, "Independent review is required before creator closure")
    row.status = target; row.updated_at = datetime.utcnow()
    if target == "RECEIVED": row.received_at = row.updated_at
    if target == "RESOLVED": row.resolved_at = row.updated_at
    if target == "CLOSED": row.closed_at = row.updated_at; row.resolution_notes = body.feedback if hasattr(body, "feedback") else body.reason
    s.commit(); _escalation_event(s, row, ctx, event_type, previous, target, getattr(body, "reason", "") or getattr(body, "feedback", ""))
    if target == "SUBMITTED":
        recipients = [row.destination_user_id] if row.destination_user_id else []
        additional_offices = []
        if row.source_type == "risk":
            _, _, additional_offices = _escalation_destination(
                s, row.source_type, row.source_ref, row.priority, ctx)
        recipients.extend(user.id for office_n in ([row.destination_office_n] + additional_offices)
                          for user in s.query(User).filter(User.tenant_id == row.tenant_id, User.office_n == office_n, User.status == "active").all())
        for recipient_id in set(recipients):
            notify(s, recipient_id, "Escalation received", f"escalation:{row.id} — {row.reason}", severity="critical" if row.priority == "CRITICAL" else "action")
    elif target in ("FOLLOW_UP", "RESOLVED", "CLOSED") and row.created_by != ctx["sub"]:
        notify(s, row.created_by, f"Escalation {target.lower()}", f"escalation:{row.id} — {getattr(body, 'reason', '') or getattr(body, 'feedback', '')}", severity="info")
    return {"escalation": _escalation_payload(s, row), "decision": decision.as_dict()}


@router.post("/escalations/{escalation_id}/submit")
def submit_escalation(escalation_id: str, body: Phase5DReasonIn, ctx=Depends(auth), s=Depends(db)):
    return _change_escalation(escalation_id, "SUBMITTED", "submit", body, ctx, s)


@router.post("/escalations/{escalation_id}/receive")
def receive_escalation(escalation_id: str, body: Phase5DReasonIn, ctx=Depends(auth), s=Depends(db)):
    row = _escalation_or_404(s, escalation_id, ctx)
    if ctx.get("office_n") != row.destination_office_n:
        raise HTTPException(403, "Only the configured destination office may receive this escalation")
    return _change_escalation(escalation_id, "RECEIVED", "receive", body, ctx, s)


@router.post("/escalations/{escalation_id}/follow-up")
def follow_up_escalation(escalation_id: str, body: Phase5DReasonIn, ctx=Depends(auth), s=Depends(db)):
    return _change_escalation(escalation_id, "FOLLOW_UP", "follow_up", body, ctx, s)


@router.post("/escalations/{escalation_id}/resolve")
def resolve_escalation(escalation_id: str, body: Phase5DReasonIn, ctx=Depends(auth), s=Depends(db)):
    return _change_escalation(escalation_id, "RESOLVED", "resolve", body, ctx, s)


@router.post("/escalations/{escalation_id}/close")
def close_escalation(escalation_id: str, body: Phase5DReasonIn, ctx=Depends(auth), s=Depends(db)):
    return _change_escalation(escalation_id, "CLOSED", "close", body, ctx, s)


def _report_scope_or_404(s, report_id, ctx):
    campus = _phase5d_scope(s, ctx)
    query = s.query(D.CampusReport).filter(D.CampusReport.id == report_id, D.CampusReport.tenant_id == ctx.get("tenant_id", TENANT))
    if ctx.get("office_n") == 3: query = query.filter(D.CampusReport.campus_scope_id == campus.id)
    row = query.first()
    if not row: raise HTTPException(404, "Campus report not found")
    return row, campus


def _report_payload(row, snapshot=None):
    return {"id": row.id, "tenant_id": row.tenant_id, "campus_scope_id": row.campus_scope_id, "created_by": row.created_by,
            "owner_id": row.owner_id, "report_type": row.report_type, "period_start": row.period_start.isoformat(),
            "period_end": row.period_end.isoformat(), "title": row.title, "status": row.status, "version": row.version,
            "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None, "returned_at": row.returned_at.isoformat() if row.returned_at else None,
            "approved_at": row.approved_at.isoformat() if row.approved_at else None, "vc_feedback": row.vc_feedback,
            "workflow_id": row.workflow_id, "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat(), "snapshot": snapshot}


def _report_data_snapshot(s, campus, ctx):
    risks = s.query(D.RiskRecord).filter(D.RiskRecord.tenant_id == ctx.get("tenant_id", TENANT), D.RiskRecord.campus_scope_id == campus.id).all()
    actions = s.query(D.CorrectiveAction).join(D.RiskRecord, D.CorrectiveAction.risk_id == D.RiskRecord.id).filter(D.CorrectiveAction.tenant_id == ctx.get("tenant_id", TENANT), D.RiskRecord.campus_scope_id == campus.id).all()
    escalations = s.query(D.EscalationRecord).filter(D.EscalationRecord.tenant_id == ctx.get("tenant_id", TENANT), D.EscalationRecord.campus_scope_id == campus.id).all()
    now = datetime.utcnow().isoformat()
    unavailable = {"status": "unavailable", "source_as_of": now, "notes": "No verified campus-scoped provider is available."}
    return {"source_as_of": now, "sections": {
        "risks": {"status": "available", "source_as_of": now, "items": [_risk_payload(s, r, ctx) for r in risks]},
        "corrective_actions": {"status": "available", "source_as_of": now, "items": [_action_payload(s, a) for a in actions]},
        "escalations": {"status": "available", "source_as_of": now, "items": [_escalation_payload(s, e) for e in escalations]},
        "executive_summary": unavailable, "academic": unavailable, "students": unavailable, "attendance": unavailable,
        "workforce": unavailable, "finance": unavailable, "infrastructure": unavailable, "placements": unavailable,
        "approvals": unavailable, "kpis": unavailable, "bop_status": unavailable,
        "requests_for_decision": {"status": "available", "source_as_of": now, "items": []},
    }}


def _report_snapshot(s, row):
    return s.query(D.CampusReportSnapshot).filter(D.CampusReportSnapshot.report_id == row.id, D.CampusReportSnapshot.version == row.version).first()


@router.get("/campus-reports")
def list_campus_reports(ctx=Depends(auth), s=Depends(db)):
    _phase5d_gate(s, ctx, "campus_reports", "view"); campus = _phase5d_scope(s, ctx)
    query = s.query(D.CampusReport).filter(D.CampusReport.tenant_id == ctx.get("tenant_id", TENANT))
    if ctx.get("office_n") == 3: query = query.filter(D.CampusReport.campus_scope_id == campus.id)
    rows = query.order_by(desc(D.CampusReport.updated_at)).all()
    return {"reports": [_report_payload(row) for row in rows], "total": len(rows)}


@router.post("/campus-reports")
def create_campus_report(body: ReportCreateIn, ctx=Depends(auth), s=Depends(db)):
    decision = _phase5d_gate(s, ctx, "campus_reports", "create"); campus = _phase5d_scope(s, ctx)
    if body.report_type not in REPORT_TYPES or body.period_end < body.period_start or not body.title.strip(): raise HTTPException(400, "Invalid report type, period, or title")
    row = D.CampusReport(id=uid(), tenant_id=ctx.get("tenant_id", TENANT), campus_scope_id=campus.id, created_by=ctx["sub"], owner_id=ctx["sub"], report_type=body.report_type, period_start=body.period_start, period_end=body.period_end, title=body.title.strip(), status="DRAFT", version=1)
    s.add(row); s.commit(); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "report.create", f"report:{row.id}", "", "DRAFT", row.title, ctx.get("auth_level", "mfa"))
    return {"report": _report_payload(row), "decision": decision.as_dict()}


@router.get("/campus-reports/{report_id}")
def get_campus_report(report_id: str, ctx=Depends(auth), s=Depends(db)):
    _phase5d_gate(s, ctx, "campus_reports", "view"); row, _ = _report_scope_or_404(s, report_id, ctx); snapshot = _report_snapshot(s, row)
    payload = json.loads(snapshot.snapshot_payload) if snapshot else None
    return {"report": _report_payload(row, payload)}


@router.patch("/campus-reports/{report_id}")
def update_campus_report(report_id: str, body: ReportUpdateIn, ctx=Depends(auth), s=Depends(db)):
    decision = _phase5d_gate(s, ctx, "campus_reports", "edit"); row, _ = _report_scope_or_404(s, report_id, ctx)
    if row.created_by != ctx["sub"] or row.status not in ("DRAFT", "RETURNED"): raise HTTPException(403, "Only draft or returned reports may be edited")
    values = body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else body.dict(exclude_unset=True)
    for key, value in values.items(): setattr(row, key, value.strip() if isinstance(value, str) else value)
    if row.period_end < row.period_start: raise HTTPException(400, "Report period is invalid")
    row.updated_at = datetime.utcnow(); s.commit(); write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "report.edit", f"report:{row.id}", row.status, row.status, row.title, ctx.get("auth_level", "mfa"))
    return {"report": _report_payload(row), "decision": decision.as_dict()}


def _submit_report(report_id, resubmit, ctx, s):
    decision = _phase5d_gate(s, ctx, "campus_reports", "resubmit" if resubmit else "submit"); row, campus = _report_scope_or_404(s, report_id, ctx)
    allowed = ("RETURNED",) if resubmit else ("DRAFT",)
    if row.created_by != ctx["sub"] or row.status not in allowed: raise HTTPException(409, "Report is not eligible for submission")
    row.version += 1 if resubmit else 0; row.status = "VC_REVIEW"; row.submitted_at = datetime.utcnow(); row.updated_at = row.submitted_at
    snapshot = D.CampusReportSnapshot(id=uid(), report_id=row.id, version=row.version, snapshot_payload=json.dumps(_report_data_snapshot(s, campus, ctx), sort_keys=True), source_as_of=datetime.utcnow())
    s.add(snapshot)
    wf = WorkflowInstance(id=uid(), tenant_id=ctx.get("tenant_id", TENANT), process_key="campus_report_v1", label="Campus report", office_n=3, title=row.title, state="under_review", initiator_id=ctx["sub"], initiator_name=actor_name(s, ctx), current_stage=1, scope_level="campus", campus_scope_id=campus.id)
    s.add(wf); row.workflow_id = wf.id; s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "report.resubmit" if resubmit else "report.submit", f"report:{row.id}", "RETURNED" if resubmit else "DRAFT", row.status, row.title, ctx.get("auth_level", "mfa"))
    vc = s.query(User).filter(User.tenant_id == ctx.get("tenant_id", TENANT), User.office_n == 2, User.status == "active").first()
    if vc: notify(s, vc.id, "Campus report submitted", f"report:{row.id} — {row.title}", severity="action")
    return {"report": _report_payload(row, json.loads(snapshot.snapshot_payload)), "decision": decision.as_dict()}


@router.post("/campus-reports/{report_id}/submit")
def submit_campus_report(report_id: str, ctx=Depends(auth), s=Depends(db)):
    return _submit_report(report_id, False, ctx, s)


@router.post("/campus-reports/{report_id}/resubmit")
def resubmit_campus_report(report_id: str, ctx=Depends(auth), s=Depends(db)):
    return _submit_report(report_id, True, ctx, s)


@router.get("/campus-reports/{report_id}/snapshot")
def get_campus_report_snapshot(report_id: str, ctx=Depends(auth), s=Depends(db)):
    _phase5d_gate(s, ctx, "campus_reports", "view"); row, _ = _report_scope_or_404(s, report_id, ctx); snapshot = _report_snapshot(s, row)
    if not snapshot: raise HTTPException(404, "Report snapshot not found")
    return {"report_id": row.id, "version": snapshot.version, "snapshot": json.loads(snapshot.snapshot_payload), "source_as_of": snapshot.source_as_of.isoformat()}


@router.get("/campus-reports/vc/inbox")
def vc_campus_report_inbox(ctx=Depends(auth), s=Depends(db)):
    if ctx.get("office_n") != 2: raise HTTPException(403, "Only the Vice Chairman may review campus reports")
    rows = s.query(D.CampusReport).filter(D.CampusReport.tenant_id == ctx.get("tenant_id", TENANT), D.CampusReport.status == "VC_REVIEW").order_by(desc(D.CampusReport.submitted_at)).all()
    return {"reports": [_report_payload(row) for row in rows], "total": len(rows)}


@router.post("/campus-reports/{report_id}/return")
def return_campus_report(report_id: str, body: ReportFeedbackIn, ctx=Depends(auth), s=Depends(db)):
    if ctx.get("office_n") != 2: raise HTTPException(403, "Only the Vice Chairman may return reports")
    decision = _phase5d_gate(s, ctx, "campus_reports", "return")
    if not body.feedback.strip(): raise HTTPException(400, "Feedback is required when returning a report")
    row, _ = _report_scope_or_404(s, report_id, {**ctx, "office_n": 2, "scope_level": "university", "scope_ref": "scope_global"}); previous = row.status
    if previous != "VC_REVIEW": raise HTTPException(409, "Report is not awaiting VC review")
    row.status = "RETURNED"; row.returned_at = datetime.utcnow(); row.vc_feedback = body.feedback.strip(); row.updated_at = row.returned_at; s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "report.return", f"report:{row.id}", previous, row.status, body.feedback, ctx.get("auth_level", "mfa"))
    notify(s, row.created_by, "Campus report returned", f"report:{row.id} — {body.feedback}", severity="action")
    return {"report": _report_payload(row), "decision": decision.as_dict()}


@router.post("/campus-reports/{report_id}/approve")
def approve_campus_report(report_id: str, ctx=Depends(auth), s=Depends(db)):
    if ctx.get("office_n") != 2: raise HTTPException(403, "Only the Vice Chairman may approve reports")
    row, _ = _report_scope_or_404(s, report_id, {**ctx, "office_n": 2, "scope_level": "university", "scope_ref": "scope_global"}); previous = row.status
    if previous != "VC_REVIEW": raise HTTPException(409, "Report is not awaiting VC review")
    decision = authorize(ctx=ctx, action="approve", resource="campus_reports", rbac_authority=rbac_for(2, 2, "approve"), workflow_state=previous, workflow_valid_states=["VC_REVIEW"], target_scope_level="campus")
    require(decision); row.status = "APPROVED"; row.approved_at = datetime.utcnow(); row.updated_at = row.approved_at; s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "report.approve", f"report:{row.id}", previous, row.status, row.title, ctx.get("auth_level", "mfa")); notify(s, row.created_by, "Campus report approved", f"report:{row.id} — {row.title}", severity="info")
    return {"report": _report_payload(row), "decision": decision.as_dict()}


# --------------------------------------------------------------------------- #
#  CAMPUS RISK & ISSUES
# --------------------------------------------------------------------------- #
RISK_CATEGORIES = {
    "Academic", "Student", "Faculty/Workforce", "Finance", "Infrastructure",
    "Operations", "Compliance", "Safety", "Administration",
}
RISK_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
RISK_LEVELS = {"LOW", "MEDIUM", "HIGH"}
RISK_STATUSES = {"OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"}
ACTION_STATUSES = {"OPEN", "IN_PROGRESS", "COMPLETED", "VERIFIED"}
RISK_TRANSITIONS = {
    "OPEN": {"OPEN", "IN_PROGRESS", "RESOLVED"},
    "IN_PROGRESS": {"IN_PROGRESS", "RESOLVED"},
    "RESOLVED": {"RESOLVED", "CLOSED"},
    "CLOSED": {"CLOSED"},
}
ACTION_TRANSITIONS = {
    "OPEN": {"OPEN", "IN_PROGRESS", "COMPLETED"},
    "IN_PROGRESS": {"IN_PROGRESS", "COMPLETED"},
    "COMPLETED": {"COMPLETED", "VERIFIED"},
    "VERIFIED": {"VERIFIED"},
}


def _risk_campus_scope(s, ctx):
    if ctx.get("office_n") != 3 or ctx.get("scope_level") != "campus":
        raise HTTPException(403, "Only a Campus Head may access campus risks")
    tenant_id = ctx.get("tenant_id", TENANT)
    scope_ref = (ctx.get("scope_ref") or "").strip()
    query = s.query(OrgScope).filter(OrgScope.tenant_id == tenant_id,
                                     OrgScope.level == "campus")
    if scope_ref.startswith("scope_"):
        scope = query.filter(OrgScope.id == scope_ref).first()
    else:
        scope = query.filter(OrgScope.name == scope_ref).first()
    if not scope:
        raise HTTPException(403, "A canonical campus scope is required")
    return scope


def _risk_gate(s, ctx, action):
    _risk_campus_scope(s, ctx)
    decision, _ = gate(s, ctx, "risks", action)
    require(decision)
    return decision


def _risk_owner_for_scope(s, owner_id, campus_scope, tenant_id):
    if not owner_id:
        return None
    owner = (s.query(User)
             .filter(User.id == owner_id, User.tenant_id == tenant_id, User.status == "active")
             .first())
    if not owner or not scope_covers(owner.scope_level or "individual", "campus"):
        raise HTTPException(400, "Owner is not authorized for this campus")
    if owner.scope_level == "campus":
        ref = (owner.scope_ref or "").strip()
        owner_scope = s.query(OrgScope).filter(OrgScope.tenant_id == tenant_id,
                                                OrgScope.level == "campus")
        owner_scope = (owner_scope.filter(OrgScope.id == ref).first()
                       if ref.startswith("scope_") else owner_scope.filter(OrgScope.name == ref).first())
        if not owner_scope or owner_scope.id != campus_scope.id:
            raise HTTPException(400, "Owner is outside the authorized campus")
    return owner


def _risk_owner_name(s, owner_id):
    if not owner_id:
        return "Unassigned"
    owner = s.query(User).get(owner_id)
    if not owner:
        return "Unknown"
    person = s.query(Person).get(owner.person_id)
    return person.name if person else owner.username


def _risk_overdue(row, now=None):
    return bool(row.due_at and row.due_at < (now or datetime.utcnow()) and row.status != "CLOSED")


def _risk_payload(s, row, ctx):
    actions = []
    if row.status in ("OPEN", "IN_PROGRESS"):
        actions.extend(["edit", "assign", "resolve"])
    elif row.status == "RESOLVED":
        actions.append("close")
    if row.status != "CLOSED" and row.severity in ("HIGH", "CRITICAL") and not row.escalated_at:
        actions.append("escalate")
    action_rows = s.query(D.CorrectiveAction).filter(
        D.CorrectiveAction.tenant_id == ctx.get("tenant_id", TENANT),
        D.CorrectiveAction.risk_id == row.id).order_by(D.CorrectiveAction.created_at).all()
    return {
        "id": row.id, "tenant_id": row.tenant_id, "campus_scope_id": row.campus_scope_id,
        "created_by": row.created_by, "owner_id": row.owner_id,
        "owner": _risk_owner_name(s, row.owner_id), "category": row.category,
        "title": row.title, "description": row.description, "severity": row.severity,
        "likelihood": row.likelihood, "impact": row.impact, "priority": row.priority,
        "status": row.status, "source_type": row.source_type, "source_ref": row.source_ref,
        "due_at": row.due_at.isoformat() if row.due_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        "resolution_notes": row.resolution_notes, "escalated_at": row.escalated_at.isoformat() if row.escalated_at else None,
        "escalation_destination": row.escalation_destination,
        "escalation_reason": row.escalation_reason, "overdue": _risk_overdue(row),
        "actions": [_action_payload(s, item) for item in action_rows],
        "available_actions": actions,
    }


def _action_payload(s, row):
    return {
        "id": row.id, "risk_id": row.risk_id, "owner_id": row.owner_id,
        "owner": _risk_owner_name(s, row.owner_id), "description": row.description,
        "status": row.status, "progress": row.progress,
        "due_at": row.due_at.isoformat() if row.due_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "verified_by": row.verified_by, "verified_at": row.verified_at.isoformat() if row.verified_at else None,
        "completion_notes": row.completion_notes, "overdue": bool(row.due_at and row.due_at < datetime.utcnow() and row.status != "VERIFIED"),
    }


def _risk_or_404(s, risk_id, ctx):
    campus = _risk_campus_scope(s, ctx)
    row = (s.query(D.RiskRecord)
           .filter(D.RiskRecord.id == risk_id,
                   D.RiskRecord.tenant_id == ctx.get("tenant_id", TENANT),
                   D.RiskRecord.campus_scope_id == campus.id).first())
    if not row:
        raise HTTPException(404, "Risk not found")
    return row, campus


def _risk_notify_owner(s, row, title, body):
    if row.owner_id:
        notify(s, row.owner_id, title, body, severity="action")


class RiskCreateIn(BaseModel):
    title: str
    description: str = ""
    category: str
    severity: str
    likelihood: str
    impact: str
    priority: str | None = None
    owner_id: str | None = None
    due_at: datetime | None = None
    source_type: str = "manual"
    source_ref: str = ""


class RiskUpdateIn(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    severity: str | None = None
    likelihood: str | None = None
    impact: str | None = None
    priority: str | None = None
    due_at: datetime | None = None


class RiskOwnerIn(BaseModel):
    owner_id: str


class RiskReasonIn(BaseModel):
    reason: str = ""
    resolution_notes: str = ""


class ActionCreateIn(BaseModel):
    description: str
    owner_id: str
    due_at: datetime | None = None


class ActionUpdateIn(BaseModel):
    description: str | None = None
    owner_id: str | None = None
    due_at: datetime | None = None
    status: str | None = None
    progress: int | None = None
    completion_notes: str | None = None


class ActionCompleteIn(BaseModel):
    completion_notes: str = ""


@router.get("/risks/owners")
def risk_owners(ctx=Depends(auth), s=Depends(db)):
    campus = _risk_campus_scope(s, ctx)
    owners = []
    for owner in s.query(User).filter(User.tenant_id == ctx.get("tenant_id", TENANT), User.status == "active").all():
        try:
            eligible = _risk_owner_for_scope(s, owner.id, campus, ctx.get("tenant_id", TENANT))
        except HTTPException:
            eligible = None
        if eligible:
            owners.append({"id": owner.id, "name": _risk_owner_name(s, owner.id), "office_n": owner.office_n, "role": owner.role})
    return {"owners": owners}


@router.get("/risks/summary")
def risk_summary(ctx=Depends(auth), s=Depends(db)):
    _risk_gate(s, ctx, "view")
    campus = _risk_campus_scope(s, ctx)
    rows = s.query(D.RiskRecord).filter(D.RiskRecord.tenant_id == ctx.get("tenant_id", TENANT), D.RiskRecord.campus_scope_id == campus.id).all()
    actions = s.query(D.CorrectiveAction).join(D.RiskRecord, D.CorrectiveAction.risk_id == D.RiskRecord.id).filter(
        D.CorrectiveAction.tenant_id == ctx.get("tenant_id", TENANT), D.RiskRecord.campus_scope_id == campus.id).all()
    return {"summary": {
        "open": sum(row.status in ("OPEN", "IN_PROGRESS") for row in rows),
        "high_critical": sum(row.severity in ("HIGH", "CRITICAL") and row.status != "CLOSED" for row in rows),
        "overdue_actions": sum(bool(action.due_at and action.due_at < datetime.utcnow() and action.status != "VERIFIED") for action in actions),
        "escalated": sum(row.escalated_at is not None and row.status != "CLOSED" for row in rows),
        "resolved": sum(row.status in ("RESOLVED", "CLOSED") for row in rows),
    }, "campus_scope_id": campus.id}


@router.get("/risks")
def list_risks(status: str = "", severity: str = "", category: str = "", owner_id: str = "", ctx=Depends(auth), s=Depends(db)):
    _risk_gate(s, ctx, "view")
    campus = _risk_campus_scope(s, ctx)
    query = s.query(D.RiskRecord).filter(D.RiskRecord.tenant_id == ctx.get("tenant_id", TENANT), D.RiskRecord.campus_scope_id == campus.id)
    if status:
        if status not in RISK_STATUSES:
            raise HTTPException(400, "Unknown risk status")
        query = query.filter(D.RiskRecord.status == status)
    if severity:
        if severity not in RISK_SEVERITIES:
            raise HTTPException(400, "Unknown risk severity")
        query = query.filter(D.RiskRecord.severity == severity)
    if category:
        if category not in RISK_CATEGORIES:
            raise HTTPException(400, "Unknown risk category")
        query = query.filter(D.RiskRecord.category == category)
    if owner_id:
        query = query.filter(D.RiskRecord.owner_id == owner_id)
    rows = query.order_by(desc(D.RiskRecord.updated_at)).all()
    return {"risks": [_risk_payload(s, row, ctx) for row in rows], "total": len(rows), "campus_scope_id": campus.id,
            "categories": sorted(RISK_CATEGORIES), "severities": sorted(RISK_SEVERITIES)}


@router.post("/risks")
def create_risk(body: RiskCreateIn, ctx=Depends(auth), s=Depends(db)):
    decision = _risk_gate(s, ctx, "create")
    campus = _risk_campus_scope(s, ctx)
    if body.category not in RISK_CATEGORIES or body.severity not in RISK_SEVERITIES or body.likelihood not in RISK_LEVELS or body.impact not in RISK_LEVELS:
        raise HTTPException(400, "Invalid risk category, severity, likelihood, or impact")
    priority = body.priority or body.severity
    if priority not in RISK_SEVERITIES:
        raise HTTPException(400, "Invalid risk priority")
    owner = _risk_owner_for_scope(s, body.owner_id, campus, ctx.get("tenant_id", TENANT))
    risk_id = uid()
    row = D.RiskRecord(id=risk_id, tenant_id=ctx.get("tenant_id", TENANT), campus_scope_id=campus.id,
                       created_by=ctx["sub"], owner_id=owner.id if owner else None, category=body.category,
                       title=body.title.strip(), description=body.description.strip(), severity=body.severity,
                       likelihood=body.likelihood, impact=body.impact, priority=priority, status="OPEN",
                       source_type=body.source_type, source_ref=body.source_ref, due_at=body.due_at)
    if not row.title:
        raise HTTPException(400, "Risk title is required")
    s.add(row); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "risk.create", f"risk:{risk_id}", "", "OPEN", row.title)
    _risk_notify_owner(s, row, "Risk owner assignment", f"{row.title} — you are responsible for this campus risk.")
    return {"risk": _risk_payload(s, row, ctx), "decision": decision.as_dict()}


@router.get("/risks/{risk_id}")
def get_risk(risk_id: str, ctx=Depends(auth), s=Depends(db)):
    _risk_gate(s, ctx, "view")
    row, _ = _risk_or_404(s, risk_id, ctx)
    return {"risk": _risk_payload(s, row, ctx)}


@router.patch("/risks/{risk_id}")
@router.put("/risks/{risk_id}")
def update_risk(risk_id: str, body: RiskUpdateIn, ctx=Depends(auth), s=Depends(db)):
    decision = _risk_gate(s, ctx, "edit")
    row, _ = _risk_or_404(s, risk_id, ctx)
    if row.status == "CLOSED":
        raise HTTPException(409, "Closed risks cannot be edited")
    values = body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else body.dict(exclude_unset=True)
    for key, value in values.items():
        if key == "category" and value not in RISK_CATEGORIES:
            raise HTTPException(400, "Invalid risk category")
        if key in ("severity", "priority") and value not in RISK_SEVERITIES:
            raise HTTPException(400, "Invalid risk severity or priority")
        if key in ("likelihood", "impact") and value not in RISK_LEVELS:
            raise HTTPException(400, "Invalid likelihood or impact")
        if key == "title" and not value.strip():
            raise HTTPException(400, "Risk title is required")
        setattr(row, key, value.strip() if isinstance(value, str) else value)
    row.updated_at = datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "risk.edit", f"risk:{row.id}", row.status, row.status, row.title)
    return {"risk": _risk_payload(s, row, ctx), "decision": decision.as_dict()}


@router.post("/risks/{risk_id}/assign")
def assign_risk(risk_id: str, body: RiskOwnerIn, ctx=Depends(auth), s=Depends(db)):
    decision = _risk_gate(s, ctx, "assign")
    row, campus = _risk_or_404(s, risk_id, ctx)
    if row.status == "CLOSED":
        raise HTTPException(409, "Closed risks cannot be reassigned")
    owner = _risk_owner_for_scope(s, body.owner_id, campus, ctx.get("tenant_id", TENANT))
    row.owner_id = owner.id; row.updated_at = datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "risk.assign", f"risk:{row.id}", "", owner.id, row.title)
    _risk_notify_owner(s, row, "Risk owner assignment", f"{row.title} — you are now responsible for this campus risk.")
    return {"risk": _risk_payload(s, row, ctx), "decision": decision.as_dict()}


def _set_risk_status(row, status, reason, ctx, s, action):
    if status not in RISK_TRANSITIONS[row.status]:
        raise HTTPException(409, f"Cannot transition risk from {row.status} to {status}")
    previous = row.status; row.status = status; row.updated_at = datetime.utcnow()
    if status == "RESOLVED": row.resolved_at = row.updated_at
    if status == "CLOSED": row.closed_at = row.updated_at
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "risk.status_change", f"risk:{row.id}", previous, status, reason)
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], action, f"risk:{row.id}", previous, status, reason)


@router.post("/risks/{risk_id}/resolve")
def resolve_risk(risk_id: str, body: RiskReasonIn, ctx=Depends(auth), s=Depends(db)):
    decision = _risk_gate(s, ctx, "resolve")
    row, _ = _risk_or_404(s, risk_id, ctx)
    _set_risk_status(row, "RESOLVED", body.resolution_notes or body.reason, ctx, s, "risk.resolve")
    row.resolution_notes = body.resolution_notes or body.reason; s.commit()
    _risk_notify_owner(s, row, "Risk resolved", f"{row.title} — risk resolved by Campus Head.")
    return {"risk": _risk_payload(s, row, ctx), "decision": decision.as_dict()}


@router.post("/risks/{risk_id}/close")
def close_risk(risk_id: str, body: RiskReasonIn, ctx=Depends(auth), s=Depends(db)):
    decision = _risk_gate(s, ctx, "close")
    row, _ = _risk_or_404(s, risk_id, ctx)
    actions = s.query(D.CorrectiveAction).filter(D.CorrectiveAction.risk_id == row.id).all()
    if any(action.status != "VERIFIED" for action in actions):
        raise HTTPException(409, "All corrective actions must be verified before closure")
    _set_risk_status(row, "CLOSED", body.reason, ctx, s, "risk.close")
    _risk_notify_owner(s, row, "Risk closed", f"{row.title} — risk closed by Campus Head.")
    return {"risk": _risk_payload(s, row, ctx), "decision": decision.as_dict()}


@router.post("/risks/{risk_id}/escalate")
def escalate_risk(risk_id: str, body: RiskReasonIn, ctx=Depends(auth), s=Depends(db)):
    decision = _risk_gate(s, ctx, "escalate")
    row, _ = _risk_or_404(s, risk_id, ctx)
    if row.status == "CLOSED":
        raise HTTPException(409, "Closed risks cannot be escalated")
    if row.severity not in RISK_ESCALATION_TARGETS and not _risk_overdue(row):
        raise HTTPException(409, "Only high, critical, or overdue risks may be escalated")
    office_n, destination = RISK_ESCALATION_TARGETS.get(row.severity, (2, "Vice Chairman"))
    row.escalated_at = datetime.utcnow(); row.escalated_by = ctx["sub"]; row.escalation_destination = destination
    row.escalation_reason = body.reason; row.updated_at = row.escalated_at; s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "risk.escalate", f"risk:{row.id}", row.status, row.status, body.reason or destination)
    target = s.query(User).filter(User.tenant_id == ctx.get("tenant_id", TENANT), User.office_n == office_n, User.status == "active").first()
    if target:
        notify(s, target.id, "Campus risk escalated", f"{row.title} — escalated by Campus Head to {destination}.", severity="critical")
    return {"risk": _risk_payload(s, row, ctx), "destination": destination, "decision": decision.as_dict()}


@router.get("/risks/{risk_id}/actions")
def list_risk_actions(risk_id: str, ctx=Depends(auth), s=Depends(db)):
    _risk_gate(s, ctx, "view")
    row, _ = _risk_or_404(s, risk_id, ctx)
    actions = s.query(D.CorrectiveAction).filter(D.CorrectiveAction.tenant_id == ctx.get("tenant_id", TENANT), D.CorrectiveAction.risk_id == row.id).all()
    return {"actions": [_action_payload(s, action) for action in actions]}


@router.post("/risks/{risk_id}/actions")
def create_risk_action(risk_id: str, body: ActionCreateIn, ctx=Depends(auth), s=Depends(db)):
    decision = _risk_gate(s, ctx, "corrective_action")
    row, campus = _risk_or_404(s, risk_id, ctx)
    if row.status == "CLOSED":
        raise HTTPException(409, "Closed risks cannot receive corrective actions")
    if not body.description.strip():
        raise HTTPException(400, "Corrective action description is required")
    owner = _risk_owner_for_scope(s, body.owner_id, campus, ctx.get("tenant_id", TENANT))
    action_id = uid()
    action = D.CorrectiveAction(id=action_id, tenant_id=ctx.get("tenant_id", TENANT), risk_id=row.id,
                                owner_id=owner.id, description=body.description.strip(), due_at=body.due_at)
    s.add(action); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "risk.corrective_action.create", f"risk-action:{action_id}", "", "OPEN", row.title)
    notify(s, owner.id, "Corrective action assigned", f"{row.title} — {action.description}", severity="action")
    return {"action": _action_payload(s, action), "decision": decision.as_dict()}


def _risk_action_or_404(s, action_id, ctx):
    _risk_gate(s, ctx, "view")
    action = s.query(D.CorrectiveAction).filter(D.CorrectiveAction.id == action_id, D.CorrectiveAction.tenant_id == ctx.get("tenant_id", TENANT)).first()
    if not action:
        raise HTTPException(404, "Corrective action not found")
    risk, campus = _risk_or_404(s, action.risk_id, ctx)
    return action, risk, campus


@router.patch("/risk-actions/{action_id}")
@router.put("/risk-actions/{action_id}")
def update_risk_action(action_id: str, body: ActionUpdateIn, ctx=Depends(auth), s=Depends(db)):
    decision = _risk_gate(s, ctx, "corrective_update")
    action, risk, campus = _risk_action_or_404(s, action_id, ctx)
    values = body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else body.dict(exclude_unset=True)
    if "owner_id" in values:
        owner = _risk_owner_for_scope(s, values["owner_id"], campus, ctx.get("tenant_id", TENANT)); values["owner_id"] = owner.id
    if "status" in values:
        if values["status"] not in ACTION_STATUSES or values["status"] not in ACTION_TRANSITIONS[action.status]:
            raise HTTPException(409, f"Cannot transition action from {action.status} to {values['status']}")
        if values["status"] == "COMPLETED": action.completed_at = datetime.utcnow()
    if "progress" in values and not 0 <= values["progress"] <= 100:
        raise HTTPException(400, "Progress must be between 0 and 100")
    for key, value in values.items():
        setattr(action, key, value.strip() if isinstance(value, str) else value)
    action.updated_at = datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "risk.corrective_action.update", f"risk-action:{action.id}", "", action.status, risk.title)
    if action.owner_id:
        notify(s, action.owner_id, "Corrective action updated", f"{risk.title} — {action.description}", severity="action")
    return {"action": _action_payload(s, action), "decision": decision.as_dict()}


@router.post("/risk-actions/{action_id}/complete")
def complete_risk_action(action_id: str, body: ActionCompleteIn, ctx=Depends(auth), s=Depends(db)):
    decision = _risk_gate(s, ctx, "corrective_update")
    action, risk, _ = _risk_action_or_404(s, action_id, ctx)
    if "COMPLETED" not in ACTION_TRANSITIONS[action.status]:
        raise HTTPException(409, f"Cannot complete action from {action.status}")
    action.status = "COMPLETED"; action.progress = 100; action.completed_at = datetime.utcnow(); action.completion_notes = body.completion_notes
    action.updated_at = datetime.utcnow(); s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "risk.corrective_action.update", f"risk-action:{action.id}", "", "COMPLETED", risk.title)
    return {"action": _action_payload(s, action), "decision": decision.as_dict()}


@router.post("/risk-actions/{action_id}/verify")
def verify_risk_action(action_id: str, ctx=Depends(auth), s=Depends(db)):
    decision = _risk_gate(s, ctx, "corrective_update")
    action, risk, _ = _risk_action_or_404(s, action_id, ctx)
    if "VERIFIED" not in ACTION_TRANSITIONS[action.status]:
        raise HTTPException(409, f"Cannot verify action from {action.status}")
    action.status = "VERIFIED"; action.verified_by = ctx["sub"]; action.verified_at = datetime.utcnow(); action.updated_at = action.verified_at
    s.commit()
    write_audit(s, ctx["sub"], actor_name(s, ctx), ctx["office_n"], "risk.corrective_action.update", f"risk-action:{action.id}", "COMPLETED", "VERIFIED", risk.title)
    return {"action": _action_payload(s, action), "decision": decision.as_dict()}


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


def _principal_compliance_requirement(s, ctx, requirement_id: str):
    if ctx.get("office_n") != 4:
        raise HTTPException(403, "Compliance requirements are available to the Principal only")
    requirement = (s.query(D.ComplianceRequirement)
                   .filter(D.ComplianceRequirement.id == requirement_id,
                           D.ComplianceRequirement.tenant_id == ctx.get("tenant_id", TENANT)).first())
    if not requirement or (ctx.get("scope_level") == "campus" and requirement.campus != ctx.get("scope_ref")):
        raise HTTPException(404, "Compliance requirement was not found in your authorized campus")
    return requirement


def _compliance_requirement_payload(s, requirement, include_history=False):
    workflow = (s.query(WorkflowInstance)
                .filter(WorkflowInstance.id == requirement.workflow_id,
                        WorkflowInstance.tenant_id == requirement.tenant_id).first())
    payload = {"id": requirement.id, "reference_code": requirement.reference_code,
               "title": requirement.title, "description": requirement.description,
               "category": requirement.category, "responsible_department": requirement.responsible_department,
               "campus": requirement.campus, "priority": requirement.priority,
               "due_date": requirement.due_date.isoformat() if requirement.due_date else None,
               "evidence_reference": requirement.evidence_reference,
               "workflow_id": requirement.workflow_id, "status": workflow.state if workflow else "unavailable",
               "escalated": bool(workflow and workflow.escalated),
               "updated_at": requirement.updated_at.isoformat() if requirement.updated_at else None}
    if include_history:
        history = (s.query(Approval).filter(Approval.workflow_id == requirement.workflow_id)
                   .order_by(Approval.created_at.desc()).all())
        payload["history"] = [{"id": item.id, "actor": item.actor_name, "stage": item.stage_label,
                               "decision": item.decision, "reason": item.reason,
                               "at": item.created_at.isoformat()} for item in history]
    return payload


@router.get("/compliance-requirements")
def compliance_requirements(q: str = "", category: str = "", status: str = "", priority: str = "", ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "governance", "view")[0])
    if ctx.get("office_n") != 4:
        raise HTTPException(403, "Compliance requirements are available to the Principal only")
    base_query = s.query(D.ComplianceRequirement).filter(D.ComplianceRequirement.tenant_id == ctx.get("tenant_id", TENANT))
    if ctx.get("scope_level") == "campus": base_query = base_query.filter(D.ComplianceRequirement.campus == ctx.get("scope_ref"))
    authorized_rows = base_query.order_by(D.ComplianceRequirement.due_date).all()
    query = base_query
    if q:
        like = f"%{q}%"; query = query.filter(or_(D.ComplianceRequirement.title.ilike(like), D.ComplianceRequirement.reference_code.ilike(like)))
    if category: query = query.filter(D.ComplianceRequirement.category == category)
    if priority: query = query.filter(D.ComplianceRequirement.priority == priority)
    rows = query.order_by(D.ComplianceRequirement.due_date).all()
    payloads = [_compliance_requirement_payload(s, row) for row in rows]
    if status: payloads = [row for row in payloads if row["status"] == status]
    authorized_payloads = [_compliance_requirement_payload(s, row) for row in authorized_rows]
    return {"requirements": payloads,
            "filters": {"categories": sorted({row.category for row in authorized_rows}), "priorities": sorted({row.priority for row in authorized_rows}),
                        "statuses": sorted({row["status"] for row in authorized_payloads})}}


@router.get("/compliance-requirements/{requirement_id}")
def compliance_requirement(requirement_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "governance", "view")[0])
    return {"requirement": _compliance_requirement_payload(s, _principal_compliance_requirement(s, ctx, requirement_id), True)}


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
