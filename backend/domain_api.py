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
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func

from core import db, auth, uid, write_audit, notify, active_delegation_for
from database import office, TENANT, slug
from authority import authorize, ALLOW
from matrices import rbac_for, scope_for, approval_limit_for, APPROVAL_LIMITS
from capabilities import (modules_for_office, module_meta, MODULE_ACTIONS,
                          MODULES, action_allowed_for_office)
import domain_models as D
from models import User, Person, OrgScope, WorkflowInstance, Notification

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
    student_query = s.query(D.Student).filter(D.Student.status == "active")
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


@router.get("/academic-calendar")
def academic_calendar(term: str = "", ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academic_calendar", "view")[0])
    term_rows = (s.query(D.AcademicCalendarEntry.term)
                 .filter(D.AcademicCalendarEntry.status != "deleted")
                 .distinct().order_by(D.AcademicCalendarEntry.term.desc()).all())
    term_options = [row[0] for row in term_rows]
    selected_term = term if term in term_options else (term_options[0] if term_options else "")

    query = s.query(D.AcademicCalendarEntry).filter(D.AcademicCalendarEntry.status != "deleted")
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


def _student_scope(query, ctx):
    """Apply the authenticated campus scope; never accept campus from the browser."""
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
#  ACADEMICS: courses & sections
# --------------------------------------------------------------------------- #
@router.get("/academics/courses")
def list_courses(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "academics", "view")[0])
    dept_map = {d.id: d.code for d in s.query(D.Department).all()}
    rows = s.query(D.Course).order_by(D.Course.code).all()
    return {"courses": [{
        "id": r.id, "code": r.code, "title": r.title, "credits": r.credits,
        "semester": r.semester, "dept": dept_map.get(r.dept_id, ""),
    } for r in rows]}


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
    for sid in body.present_ids:
        s.add(D.AttendanceRecord(id=uid(), tenant_id=TENANT, section_id=body.section_id,
                                 student_id=sid, on_date=d, present=True, marked_by=who))
    for sid in body.absent_ids:
        s.add(D.AttendanceRecord(id=uid(), tenant_id=TENANT, section_id=body.section_id,
                                 student_id=sid, on_date=d, present=False, marked_by=who))
    s.commit()
    n = len(body.present_ids) + len(body.absent_ids)
    write_audit(s, ctx["sub"], who, ctx["office_n"], "attendance.mark",
                f"section:{body.section_id}", "", "recorded",
                f"Marked {n} students on {d.isoformat()}")
    return {"marked": n, "decision": dec.as_dict()}


# --------------------------------------------------------------------------- #
#  EXAMINATIONS: marks entry + result publication (SoD-separated)
# --------------------------------------------------------------------------- #
@router.get("/exams/sections")
def exam_sections(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "examinations", "view")[0])
    course_map = {c.id: (c.code, c.title) for c in s.query(D.Course).all()}
    rows = s.query(D.Section).limit(100).all()
    out = []
    for r in rows:
        cc, ct = course_map.get(r.course_id, ("", ""))
        asmts = s.query(D.Assessment).filter(D.Assessment.section_id == r.id).count()
        rs = s.query(D.ResultSheet).filter(D.ResultSheet.section_id == r.id).first()
        out.append({"id": r.id, "course_code": cc, "course_title": ct,
                    "section": r.section_code, "assessments": asmts,
                    "result_status": rs.status if rs else "none"})
    return {"sections": out,
            "can_enter_marks": can(s, ctx, "examinations", "enter_marks"),
            "can_publish": can(s, ctx, "examinations", "publish_result")}


@router.get("/exams/assessments/{section_id}")
def exam_assessments(section_id: str, ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "examinations", "view")[0])
    rows = s.query(D.Assessment).filter(D.Assessment.section_id == section_id).all()
    return {"assessments": [{"id": a.id, "name": a.name, "max_marks": a.max_marks,
                             "locked": a.locked,
                             "entered": s.query(D.Mark).filter(D.Mark.assessment_id == a.id).count()}
                            for a in rows]}


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
    if a.locked:
        raise HTTPException(409, "Assessment is locked; marks cannot be changed")
    who = actor_name(s, ctx)
    for stu_id, score in body.marks.items():
        existing = s.query(D.Mark).filter(D.Mark.assessment_id == a.id,
                                          D.Mark.student_id == stu_id).first()
        if existing:
            existing.score = float(score)
        else:
            s.add(D.Mark(id=uid(), tenant_id=TENANT, assessment_id=a.id,
                         student_id=stu_id, score=float(score), entered_by=who))
    s.commit()
    write_audit(s, ctx["sub"], who, ctx["office_n"], "marks.enter",
                f"assessment:{a.id}", "", "entered", f"Entered {len(body.marks)} marks for {a.name}")
    return {"entered": len(body.marks), "decision": dec.as_dict()}


class PublishResultIn(BaseModel):
    section_id: str


@router.post("/exams/publish")
def publish_result(body: PublishResultIn, ctx=Depends(auth), s=Depends(db)):
    # Result publication is a distinct authority from marks entry (SoD invariant).
    dec, verb = gate(s, ctx, "examinations", "publish_result")
    require(dec)
    who = actor_name(s, ctx)
    rs = s.query(D.ResultSheet).filter(D.ResultSheet.section_id == body.section_id).first()
    if not rs:
        rs = D.ResultSheet(id=uid(), tenant_id=TENANT, section_id=body.section_id,
                           term="2025-Odd")
        s.add(rs)
    rs.status = "published"
    rs.published_by = who
    rs.published_at = datetime.utcnow()
    s.commit()
    write_audit(s, ctx["sub"], who, ctx["office_n"], "result.publish",
                f"section:{body.section_id}", "moderated", "published",
                "Result published")
    return {"status": "published", "decision": dec.as_dict()}


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
    stu_map = {st.id: (st.roll_no, st.name) for st in s.query(D.Student).all()}
    rows = s.query(D.FeeInvoice).limit(300).all()
    out = []
    for r in rows:
        roll, name = stu_map.get(r.student_id, ("", ""))
        out.append({"id": r.id, "roll_no": roll, "name": name, "term": r.term,
                    "amount": r.amount, "paid": r.paid, "balance": r.amount - r.paid,
                    "status": r.status})
    summary = {
        "total_billed": s.query(func.coalesce(func.sum(D.FeeInvoice.amount), 0)).scalar() or 0,
        "total_collected": s.query(func.coalesce(func.sum(D.FeeInvoice.paid), 0)).scalar() or 0,
        "outstanding": s.query(func.coalesce(func.sum(D.FeeInvoice.amount - D.FeeInvoice.paid), 0)).scalar() or 0,
    }
    return {"invoices": out, "summary": summary,
            "can_record": can(s, ctx, "finance", "record_payment"),
            "can_waive": can(s, ctx, "finance", "waive")}


@router.get("/finance/budget")
def list_budget(ctx=Depends(auth), s=Depends(db)):
    require(gate(s, ctx, "finance", "view")[0])
    rows = s.query(D.BudgetLine).all()
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
    s.add(D.BookLoan(id=uid(), tenant_id=TENANT, book_id=b.id, borrower=body.borrower,
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
    rows = s.query(D.LeaveRequest).order_by(desc(D.LeaveRequest.id)).all()
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
    rows = s.query(D.Asset).all()
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
        return _governance_live_fallback(s, can_edit_dashboard)

    semesters = [{"key": row.semester_key, "label": row.semester_label} for row in snapshots]
    payload = _governance_payload_from_snapshot(selected, compliance_rows, performance_rows, semesters)
    payload["can_edit"] = can_edit_dashboard
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
