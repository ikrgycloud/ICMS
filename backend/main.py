# -*- coding: utf-8 -*-
"""
ICMS API — Integrated College/University Management System.
Single consolidated service exposing the Identity & Authority plane and every
office/domain as a thin consumer of the same authorize() gate (Document §5, §7, §12).

Runs as a modular monolith with clean domain seams (Document §5 recommendation).
Every mutating endpoint calls authorize(actor, action, resource, context) then
emits one hash-chained audit event.
"""
import os
import sys
import uuid
import time
import json
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import desc, func, or_

import authority as A
from authority import (issue_token, decode_token, pwhash, audit_hash, authorize,
                       Decision, ALLOW, DENY, ESCALATE, RECOMMEND_OUT, VERBS,
                       NOT_ALLOWED)
import matrices as M
from matrices import (APPROVAL_MATRIX, WF_VALID, WF_STATES, approval_limit_for,
                      APPROVAL_LIMITS, rbac_for, scope_for)
from database import (SessionLocal, seed, CATALOG, OFFICES, LEVELS, office,
                      DEMO_USERNAMES, TENANT, slug)
from models import (User, Person, OrgScope, Role, RolePermission, Delegation, WorkflowInstance,
                    WorkflowProfile, Approval, Notification, AuditLog, ApprovalLimit,
                    DelegationPolicy, DelegationProfile, DelegationOption,
                    DelegationContext)

from domain_api import router as domain_router
from portal_api import router as portal_router
from integrations_api import router as integrations_router
from sms_api import router as sms_router
from domain_seed import seed_domain
import domain_models as D

# Use the same named security scheme as modular routers. Swagger UI now has a
# single Authorize action which applies the bearer token to protected APIs.
bearer_scheme = HTTPBearer(scheme_name="BearerAuth", auto_error=False)

app = FastAPI(title="ICMS — Integrated College/University Management System",
              version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])
app.include_router(domain_router)
app.include_router(portal_router)
app.include_router(integrations_router)
app.include_router(sms_router)


@app.on_event("startup")
def _startup():
    for _ in range(30):
        try:
            print("seed:", seed())
            print("domain:", seed_domain())
            return
        except Exception as e:
            print("waiting for db...", e)
            time.sleep(2)


def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def auth(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Missing token")
    try:
        return decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(401, "Invalid or expired token")


def non_front_office(ctx=Depends(auth)) -> dict:
    """Protect shared modules from the Front Office-only account."""
    if ctx["office_n"] == 35:
        raise HTTPException(403, "This generic module is not available to Front Office")
    return ctx


def uid() -> str:
    return uuid.uuid4().hex[:12]


# --------------------------------------------------------------------------- #
#  Audit (hash-chained, append-only)                                          #
# --------------------------------------------------------------------------- #
def write_audit(s, actor, actor_name, office_n, action, entity,
                prev_state="", new_state="", reason="", auth_level="mfa",
                tenant_id=None, campus_scope_id=None):
    tenant = tenant_id or TENANT
    last = (s.query(AuditLog).filter(AuditLog.tenant_id == tenant)
            .order_by(desc(AuditLog.id)).first())
    prev = last.hash if last else "0" * 64
    rec = {"actor": actor, "action": action, "entity": entity, "new_state": new_state}
    h = audit_hash(prev, rec)
    row = AuditLog(tenant_id=tenant, campus_scope_id=campus_scope_id, actor=actor, actor_name=actor_name, office_n=office_n,
                   action=action, entity=entity, prev_state=prev_state, new_state=new_state,
                   reason=reason, auth_level=auth_level, prev_hash=prev, hash=h)
    s.add(row)
    s.commit()
    return row


def notify(s, user_id, title, body, severity="info", tenant_id=None):
    s.add(Notification(id=uid(), tenant_id=tenant_id or TENANT, user_id=user_id, severity=severity,
                       title=title, body=body))
    s.commit()


def rbac_authority(s, office_n, level, verb) -> str:
    return rbac_for(office_n, level, verb)


def _utc_now():
    return datetime.now(timezone.utc)


def _ensure_utc(dt_value):
    if dt_value is None:
        return None
    return dt_value if getattr(dt_value, "tzinfo", None) else dt_value.replace(tzinfo=timezone.utc)


def _format_date_short(dt_value):
    stamp = _ensure_utc(dt_value)
    return stamp.strftime("%d %b %Y") if stamp else ""


def _delegation_profile_policy(s, d):
    profile = s.query(DelegationProfile).filter(DelegationProfile.delegation_id == d.id).first()
    policy = None
    if profile and profile.policy_key:
        policy = (s.query(DelegationPolicy)
                  .filter(DelegationPolicy.policy_key == profile.policy_key)
                  .first())
    return profile, policy


def _delegation_context_for(s, delegation_id: str):
    return (s.query(DelegationContext)
            .filter(DelegationContext.delegation_id == delegation_id)
            .first())


def _delegation_options(s, group_key: str):
    return (s.query(DelegationOption)
            .filter(DelegationOption.group_key == group_key,
                    DelegationOption.active == True)
            .order_by(DelegationOption.sort_order, DelegationOption.label).all())


def _delegation_option_payload(row):
    return {
        "key": row.option_key,
        "label": row.label,
        "description": row.description or "",
    }


def _delegation_option_map(s, group_key: str):
    return {row.option_key: row for row in _delegation_options(s, group_key)}


def _delegation_option_by_description(s, group_key: str, description: str):
    clean = (description or "").strip()
    if not clean:
        return None
    rows = _delegation_options(s, group_key)
    for row in rows:
        if (row.description or "").strip() == clean:
            return row
    return None


def _ensure_delegation_option(s, group_key: str, label: str, description: str = "",
                              sort_order: int | None = None):
    clean_label = (label or "").strip()
    if not clean_label:
        return None
    option_key = slug(clean_label)
    next_sort = (s.query(func.max(DelegationOption.sort_order))
                 .filter(DelegationOption.group_key == group_key)
                 .scalar() or 0) + 1
    row = (s.query(DelegationOption)
           .filter(DelegationOption.group_key == group_key,
                   DelegationOption.option_key == option_key)
           .first())
    if not row:
        row = DelegationOption(
            id=uid(),
            tenant_id=TENANT,
            group_key=group_key,
            option_key=option_key,
            label=clean_label,
        )
        s.add(row)
    row.tenant_id = TENANT
    row.group_key = group_key
    row.option_key = option_key
    row.label = clean_label
    row.description = (description or "").strip()
    row.active = True
    row.sort_order = sort_order if sort_order is not None else (row.sort_order or next_sort)
    row.updated_at = datetime.utcnow()
    s.flush()
    return row


def _delegation_policy_key(s, policy_type: str, subject: str):
    base = slug(f"{policy_type}_{subject}") or "delegation"
    policy_key = base
    suffix = 2
    while (s.query(DelegationPolicy)
           .filter(DelegationPolicy.policy_key == policy_key).first()):
        policy_key = f"{base}_{suffix}"
        suffix += 1
    return policy_key


def _delegation_action_for_access(access_key: str):
    raw = (access_key or "").strip().lower()
    if not raw or raw == "*":
        return "*"
    return raw.split(":", 1)[0]


def _delegation_icon_for_type(policy_type: str):
    key = slug(policy_type or "")
    if any(token in key for token in ("finance", "budget", "fund", "scholar")):
        return "finance"
    if any(token in key for token in ("academic", "curriculum", "exam", "faculty")):
        return "academy"
    if any(token in key for token in ("research", "grant")):
        return "science"
    if any(token in key for token in ("human", "people", "hr", "recruit")):
        return "people"
    if any(token in key for token in ("admin", "operation", "infrastructure")):
        return "operations"
    return "shield"


def _resolve_delegation_policy_type(s, option_key: str, new_label: str = ""):
    if option_key and option_key != "__new__":
        row = (s.query(DelegationOption)
               .filter(DelegationOption.group_key == "policy_type",
                       DelegationOption.option_key == option_key,
                       DelegationOption.active == True).first())
        if row:
            return row
    if (new_label or "").strip():
        existing = (s.query(DelegationOption)
                    .filter(DelegationOption.group_key == "policy_type",
                            func.lower(DelegationOption.label) == (new_label or "").strip().lower())
                    .first())
        if existing:
            return existing
        return _ensure_delegation_option(s, "policy_type", new_label)
    return None


def _delegation_status_key(d, now=None):
    now = now or _utc_now()
    start = _ensure_utc(d.start)
    end = _ensure_utc(d.end)
    raw = str(d.status or "active").lower()
    if raw == "revoked":
        return "revoked"
    if end and end < now:
        return "expired"
    if start and start > now:
        return "scheduled"
    if end and end <= now + timedelta(days=30):
        return "expiring_soon"
    return "active"


def _delegation_status_meta(status_key: str):
    mapping = {
        "active": {"key": "active", "label": "Active", "tone": "green"},
        "expiring_soon": {"key": "expiring_soon", "label": "Expiring Soon", "tone": "amber"},
        "expired": {"key": "expired", "label": "Expired", "tone": "slate"},
        "revoked": {"key": "revoked", "label": "Revoked", "tone": "red"},
        "scheduled": {"key": "scheduled", "label": "Scheduled", "tone": "blue"},
    }
    return mapping.get(status_key, {"key": status_key, "label": status_key.replace("_", " ").title(), "tone": "slate"})


def _delegation_reference_code(s, policy_type: str):
    clean = "".join(ch for ch in (policy_type or "DEL").upper() if ch.isalpha())[:3] or "DEL"
    year = datetime.utcnow().year
    prefix = f"{clean}-POL-{year}-"
    count = (s.query(DelegationProfile)
             .filter(DelegationProfile.reference_code.like(f"{prefix}%"))
             .count()) + 1
    return f"{prefix}{count:02d}"


def _delegation_payload(s, d):
    profile, policy = _delegation_profile_policy(s, d)
    context = _delegation_context_for(s, d.id)
    grantor = s.query(User).get(d.from_user)
    recipient = s.query(User).get(d.to_user)
    grantor_person = s.query(Person).get(grantor.person_id) if grantor else None
    recipient_person = s.query(Person).get(recipient.person_id) if recipient else None
    recipient_office = office(recipient.office_n) if recipient else {}
    status_key = _delegation_status_key(d)
    status_meta = _delegation_status_meta(status_key)
    start = _ensure_utc(d.start)
    end = _ensure_utc(d.end)
    expiring_in_days = max((end.date() - _utc_now().date()).days, 0) if end and status_key == "expiring_soon" else None
    access_label = ""
    if context and context.access_label:
        access_label = context.access_label
    elif policy and policy.authority:
        access_opt = (s.query(DelegationOption)
                      .filter(DelegationOption.group_key == "delegation_access",
                              DelegationOption.option_key == policy.authority,
                              DelegationOption.active == True).first())
        access_label = access_opt.label if access_opt else policy.authority
    scope_label = ""
    if context and context.scope_label:
        scope_label = context.scope_label
    elif policy and policy.resource_scope:
        scope_opt = _delegation_option_by_description(s, "delegation_scope", policy.resource_scope)
        scope_label = scope_opt.label if scope_opt else policy.resource_scope
    review_frequency_label = ""
    if context and context.review_frequency_label:
        review_frequency_label = context.review_frequency_label
    description = context.policy_description if context and context.policy_description else ""
    notes = context.notes if context and context.notes else (d.reason or "")
    attachment = None
    if context and context.attachment_name:
        attachment = {
            "name": context.attachment_name,
            "mime_type": context.attachment_mime_type or "",
            "size": context.attachment_size,
            "data_b64": context.attachment_data or "",
        }

    return {
        "id": d.id,
        "from_user_id": d.from_user,
        "from": grantor.username if grantor else d.from_user,
        "from_name": grantor_person.name if grantor_person else (grantor.role if grantor else d.from_user),
        "to_user_id": d.to_user,
        "to": recipient.username if recipient else d.to_user,
        "to_name": recipient_person.name if recipient_person else (recipient.role if recipient else d.to_user),
        "to_role": recipient.role if recipient else "",
        "to_office_n": recipient.office_n if recipient else None,
        "to_office": recipient_office.get("name", ""),
        "authority": d.authority,
        "authority_label": access_label or (policy.authority if policy and policy.authority else (d.authority or "*")),
        "action": policy.action if policy and policy.action else (d.authority or "approve"),
        "resource_scope": policy.resource_scope if policy and policy.resource_scope else "*",
        "resource_scope_label": scope_label or (policy.resource_scope if policy and policy.resource_scope else "*"),
        "policy_key": profile.policy_key if profile else "",
        "policy_type": profile.policy_type if profile else (policy.policy_type if policy else "General"),
        "subject": profile.subject if profile else (policy.subject if policy else "Delegated authority"),
        "reference_code": profile.reference_code if profile else "",
        "delegated_to_type": profile.delegated_to_type if profile else (policy.delegated_to_type_default if policy else "Individual"),
        "icon": policy.icon if policy and policy.icon else "shield",
        "limit": d.limit,
        "status": d.status,
        "status_meta": status_meta,
        "start": start.isoformat() if start else "",
        "end": end.isoformat() if end else "",
        "window_label": f"{_format_date_short(start)} to {_format_date_short(end)}",
        "reason": d.reason,
        "description": description,
        "notes": notes,
        "scope_key": context.scope_key if context else "",
        "review_frequency_key": context.review_frequency_key if context else "",
        "review_frequency_label": review_frequency_label,
        "access_key": context.access_key if context and context.access_key else (policy.authority if policy else d.authority),
        "attachment": attachment,
        "active": status_key in ("active", "expiring_soon"),
        "expiring_in_days": expiring_in_days,
    }


def active_delegations_for(s, user_id):
    rows = (s.query(Delegation)
            .filter(Delegation.to_user == user_id)
            .order_by(desc(Delegation.created_at)).all())
    return [payload for payload in (_delegation_payload(s, row) for row in rows)
            if payload["status_meta"]["key"] in ("active", "expiring_soon")]


def active_delegation_for(s, user_id):
    active = active_delegations_for(s, user_id)
    return active[0] if active else None


def _delegation_matches_action(action: str, resource: str, amount: float | None,
                               payloads: list[dict], scope_level: str = "individual"):
    decision = authorize(
        ctx={"sub": "delegated", "scope_level": scope_level},
        action=action,
        resource=resource,
        rbac_authority=A.NOT_ALLOWED,
        amount=amount,
        active_delegation=payloads,
        target_scope_level=scope_level,
    )
    return decision.outcome in (ALLOW, ESCALATE, RECOMMEND_OUT)


def _delegation_matches_workflow(payloads: list[dict], wf, scope_level: str = "individual"):
    resource = f"workflow:{wf.process_key}"
    for action in ("approve", "review", "reject", "escalate"):
        if _delegation_matches_action(action, resource, wf.amount, payloads, scope_level):
            return True
    return False


def _delegation_targets_for_workflow(s, wf):
    targets = []
    active_rows = (s.query(Delegation)
                   .filter(Delegation.status == "active")
                   .order_by(desc(Delegation.created_at)).all())
    for row in active_rows:
        payload = _delegation_payload(s, row)
        if not payload["active"]:
            continue
        recipient = s.query(User).get(row.to_user)
        if recipient and _delegation_matches_workflow([payload], wf, recipient.scope_level):
            targets.append(recipient)
    return targets


def _delegation_recipient_options(s):
    rows = (s.query(User)
            .filter(User.username.in_(list(DEMO_USERNAMES.values())))
            .order_by(User.office_n).all())
    options = []
    for row in rows:
        if row.office_n == 1:
            continue
        person = s.query(Person).get(row.person_id)
        office_meta = office(row.office_n)
        options.append({
            "id": row.id,
            "username": row.username,
            "label": person.name if person and person.name else row.role,
            "description": f"{office_meta.get('name', 'Office')} · {row.username}",
            "office_n": row.office_n,
            "office": office_meta.get("name", ""),
            "role": row.role,
            "delegated_to_type": "Office" if row.office_n <= 10 else "Individual",
        })
    return options


# --------------------------------------------------------------------------- #
#  Auth pipeline (Document §7 steps 1-6)                                       #
# --------------------------------------------------------------------------- #
class LoginIn(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
def login(body: LoginIn, s=Depends(db)):
    u = s.query(User).filter(User.username == body.username).first()
    if not u or u.password_hash != pwhash(body.password):
        raise HTTPException(401, "Invalid credentials")
    o = office(u.office_n)
    tok = issue_token(u.id, u.tenant_id, u.office_n, u.role, u.scope_level,
                      u.scope_ref, "mfa" if u.mfa_enabled else "password")
    p = s.query(Person).get(u.person_id)
    active_delegations = active_delegations_for(s, u.id)
    write_audit(s, u.id, p.name if p else u.username, u.office_n, "auth.login",
                "session", "", "active", "login ok")
    return {
        "token": tok,
        "user": _user_payload(u, p, o, active_delegations=active_delegations),
        "active_delegation": active_delegations[0] if active_delegations else None,
        "active_delegations": active_delegations,
    }


def _persona_for(office_n):
    """Coarse persona that decides which home dashboard the frontend renders."""
    if office_n == 36:
        return "student"
    if office_n == 37:
        return "parent"
    if office_n in (11, 12, 13, 14):
        return "faculty"
    if office_n in (1, 2, 40):
        return "governance"
    if office_n in (3, 4, 5, 6, 7, 8, 9, 10):
        return "leadership"
    if office_n == 38:
        return "alumni"
    if office_n == 39:
        return "auditor"
    return "staff"


def _user_payload(u, p, o, active_role=None, active_delegations=None):
    active_delegations = active_delegations or []
    return {
        "id": u.id, "username": u.username, "name": p.name if p else u.username,
        "office_n": u.office_n, "office": o["name"], "level": o["level"],
        "level_name": LEVELS[str(o["level"])]["name"],
        "level_color": LEVELS[str(o["level"])]["color"],
        "role": u.role, "active_role": active_role or u.role,
        "persona": _persona_for(u.office_n),
        "scope_level": u.scope_level, "mfa": u.mfa_enabled,
        "modules": o["modules"], "functionalities": o["functionalities"],
        "workflows": o["workflows"], "purpose": o["purpose"],
        "reports_to": o["reports_to"], "internal_roles": o["internal_roles"],
        "scope": o["scope"],
        "active_delegation_count": len(active_delegations),
        "active_delegation": active_delegations[0] if active_delegations else None,
        "active_delegations": active_delegations,
    }


@app.get("/api/me")
def me(ctx=Depends(auth), s=Depends(db)):
    u = s.query(User).get(ctx["sub"])
    p = s.query(Person).get(u.person_id)
    o = office(u.office_n)
    active_delegations = active_delegations_for(s, u.id)
    return {
        "user": _user_payload(u, p, o, ctx.get("role"), active_delegations=active_delegations),
        "auth_context": ctx,
        "active_delegation": active_delegations[0] if active_delegations else None,
        "active_delegations": active_delegations,
    }


class SwitchRoleIn(BaseModel):
    role: str


@app.post("/api/auth/switch-role")
def switch_role(body: SwitchRoleIn, ctx=Depends(auth), s=Depends(db)):
    """Re-issue a token bound to a different internal role of the same office.
    The office's scope is preserved; the active role changes which internal-role
    lens the workspace presents. Authority per verb is the office's RBAC row."""
    u = s.query(User).get(ctx["sub"])
    o = office(u.office_n)
    if body.role not in o["internal_roles"]:
        raise HTTPException(400, "Role not available for this office")
    p = s.query(Person).get(u.person_id)
    active_delegations = active_delegations_for(s, u.id)
    tok = issue_token(u.id, u.tenant_id, u.office_n, body.role, u.scope_level,
                      u.scope_ref, "mfa" if u.mfa_enabled else "password")
    write_audit(s, u.id, p.name if p else u.username, u.office_n, "auth.switch_role",
                "session", u.role, body.role, f"Assumed role: {body.role}")
    return {
        "token": tok,
        "user": _user_payload(u, p, o, body.role, active_delegations=active_delegations),
        "active_delegation": active_delegations[0] if active_delegations else None,
        "active_delegations": active_delegations,
    }


# --------------------------------------------------------------------------- #
#  Directory / catalog (Document §3, §8)                                       #
# --------------------------------------------------------------------------- #
@app.get("/api/catalog")
def catalog():
    return CATALOG


@app.get("/api/directory/offices")
def offices():
    return [{"n": o["n"], "name": o["name"], "level": o["level"],
             "level_name": LEVELS[str(o["level"])]["name"],
             "color": LEVELS[str(o["level"])]["color"],
             "purpose": o.get("purpose", ""),
             "roles": len(o["internal_roles"]), "modules": o["modules"],
             "scope": o["scope"], "reports_to": o["reports_to"]}
            for o in OFFICES]


@app.get("/api/directory/office/{n}")
def office_detail(n: int, s=Depends(db)):
    o = office(n)
    if not o:
        raise HTTPException(404, "Office not found")
    # RBAC row for this office (representative verbs).
    rbac = {v: rbac_for(n, o["level"], v) for v in
            ["view", "create", "edit", "delete", "approve", "reject", "verify",
             "publish", "export", "configure", "delegate", "audit"]}
    return {"n": o["n"], "name": o["name"], "level": o["level"],
            "level_name": LEVELS[str(o["level"])]["name"],
            "color": LEVELS[str(o["level"])]["color"],
            "purpose": o.get("purpose", ""),
            "internal_roles": o["internal_roles"],
            "functionalities": o.get("functionalities", []),
            "workflows": o.get("workflows", []),
            "modules": o.get("modules", []),
            "scope": o.get("scope", ""),
            "reports_to": o.get("reports_to", ""),
            "rbac": rbac, "scope_level": scope_for(n)}


@app.get("/api/directory/roles")
def all_roles(s=Depends(db)):
    rows = s.query(Role).all()
    return [{"office_n": r.office_n, "name": r.name, "category": r.category}
            for r in rows]


@app.get("/api/stats")
def stats(s=Depends(db)):
    return {
        "offices": len(OFFICES), "levels": len(LEVELS),
        "roles": s.query(Role).count(),
        "users": s.query(User).count(),
        "workflows": s.query(WorkflowInstance).count(),
        "audit_events": s.query(AuditLog).count(),
        "approval_processes": len(APPROVAL_MATRIX),
    }


# --------------------------------------------------------------------------- #
#  Matrices (Document §9, §10, §11)                                            #
# --------------------------------------------------------------------------- #
@app.get("/api/matrices/rbac")
def rbac_matrix():
    verbs = ["view", "create", "edit", "delete", "approve", "reject", "verify",
             "publish", "export", "configure", "delegate", "audit"]
    rows = []
    for o in OFFICES:
        rows.append({"n": o["n"], "office": o["name"], "level": o["level"],
                     "cells": {v: rbac_for(o["n"], o["level"], v) for v in verbs}})
    return {"verbs": verbs, "rows": rows}


@app.get("/api/matrices/approval")
def approval_matrix():
    return {"processes": APPROVAL_MATRIX}


@app.get("/api/matrices/scope")
def scope_matrix():
    return {"levels": A.SCOPE_LEVELS,
            "offices": [{"n": o["n"], "office": o["name"], "scope": scope_for(o["n"])}
                        for o in OFFICES]}


# --------------------------------------------------------------------------- #
#  Workflows & approvals (Document §7, §10) — the end-to-end engine            #
# --------------------------------------------------------------------------- #
@app.get("/api/workflows/processes")
def workflow_processes(ctx=Depends(auth)):
    """Processes this office can initiate or participate in."""
    processes = [proc for proc in APPROVAL_MATRIX
                 if proc["key"] != "branch_operational_plan" or ctx.get("office_n") in (2, 3)]
    return {"processes": processes}


PROCESS_CATEGORY_MAP = {
    "branch_operational_plan": "Campus Management",
    "branch_creation": "Administrative",
    "purchase_request": "Finance",
    "payroll_approval": "Finance",
    "infrastructure_capex": "Infrastructure",
    "fee_waiver": "Finance",
    "refund": "Finance",
    "recruitment": "Human Resources",
    "disciplinary_action": "Governance",
    "student_grievance": "Student Affairs",
    "question_paper": "Academic Operations",
    "result_publication": "Academic Operations",
    "marks_submission": "Academic Operations",
    "certificate": "Academic Records",
    "hostel_allocation": "Campus Life",
    "transport_allocation": "Campus Life",
    "placement": "Career Services",
    "student_admission": "Admissions",
    "course_registration": "Academics",
    "attendance_correction": "Academics",
    "faculty_leave": "Human Resources",
    "revaluation": "Academic Records",
    "it_access": "Technology",
}

PROCESS_REF_PREFIX = {
    "branch_operational_plan": "BOP",
    "branch_creation": "PRU",
    "purchase_request": "FIN",
    "payroll_approval": "PAY",
    "infrastructure_capex": "CAP",
    "fee_waiver": "FEE",
    "refund": "REF",
    "recruitment": "HR",
    "disciplinary_action": "GOV",
    "student_grievance": "STU",
    "question_paper": "EXM",
    "result_publication": "EXM",
    "marks_submission": "EXM",
    "certificate": "REG",
    "hostel_allocation": "HOS",
    "transport_allocation": "TRN",
    "placement": "PLC",
    "student_admission": "ADM",
    "course_registration": "ACA",
    "attendance_correction": "ACA",
    "faculty_leave": "HR",
    "revaluation": "EXM",
    "it_access": "IT",
}

STATE_FILTER_META = {
    "submitted": {"label": "Pending", "tone": "pending"},
    "under_review": {"label": "Under Review", "tone": "review"},
    "reviewed": {"label": "Reviewed", "tone": "reviewed"},
    "returned": {"label": "Returned", "tone": "rejected"},
    "approved": {"label": "Approved", "tone": "approved"},
    "active": {"label": "Active", "tone": "approved"},
    "executed": {"label": "Approved", "tone": "approved"},
    "rejected": {"label": "Rejected", "tone": "rejected"},
    "escalated": {"label": "Escalated", "tone": "escalated"},
}

STAGE_META = {
    "submission": {"label": "Submission", "tone": "submission"},
    "review": {"label": "Review", "tone": "review"},
    "approval": {"label": "Approval", "tone": "approval"},
    "final_approval": {"label": "Final Approval", "tone": "final"},
}


def _workflow_process(process_key: str):
    return next((p for p in APPROVAL_MATRIX if p["key"] == process_key), None)


def _semester_meta_for_date(dt_value: datetime | None):
    current = dt_value or datetime.utcnow()
    year = current.year
    if current.month >= 7:
        start_year = year
        end_year = year + 1
        semester_name = "Odd"
        semester_key = "odd"
    else:
        start_year = year - 1
        end_year = year
        semester_name = "Even"
        semester_key = "even"
    return {
        "key": f"{semester_key}_{start_year}_{end_year}",
        "label": f"{semester_name} Semester {start_year}-{str(end_year)[-2:]}",
    }


def _semester_meta_from_key(semester_key: str, fallback_at: datetime | None = None):
    raw = (semester_key or "").strip().lower()
    parts = raw.split("_")
    if len(parts) == 3 and parts[0] in ("odd", "even") and parts[1].isdigit() and parts[2].isdigit():
        start_year = int(parts[1])
        end_year = int(parts[2])
        semester_name = "Odd" if parts[0] == "odd" else "Even"
        return {
            "key": raw,
            "label": f"{semester_name} Semester {start_year}-{str(end_year)[-2:]}",
        }
    return _semester_meta_for_date(fallback_at)


def _approval_category(process_key: str, label: str = ""):
    if process_key in PROCESS_CATEGORY_MAP:
        return PROCESS_CATEGORY_MAP[process_key]
    lower = label.lower()
    if "budget" in lower or "payroll" in lower or "fee" in lower or "refund" in lower:
        return "Finance"
    if "exam" in lower or "result" in lower:
        return "Academic Operations"
    if "recruit" in lower or "leave" in lower:
        return "Human Resources"
    return "Operations"


def _reference_prefix(process_key: str, label: str = ""):
    if process_key in PROCESS_REF_PREFIX:
        return PROCESS_REF_PREFIX[process_key]
    parts = [part[:3].upper() for part in process_key.split("_") if part]
    if parts:
        return "".join(parts)[:4]
    clean = "".join(ch for ch in label.upper() if ch.isalpha())
    return (clean[:4] or "REQ").ljust(3, "Q")


def _generate_reference_code(s, process_key: str, label: str = "", created_at: datetime | None = None):
    stamp = created_at or datetime.utcnow()
    prefix = _reference_prefix(process_key, label)
    year = stamp.year
    count = (s.query(WorkflowProfile)
             .filter(WorkflowProfile.reference_code.like(f"{prefix}-{year}-%"))
             .count()) + 1
    return f"{prefix}-{year}-{count:03d}"


def _ensure_workflow_profile(
    s,
    wf,
    semester_key: str = "",
    semester_label: str = "",
    category: str = "",
    notes: str = "",
    reference_code: str = "",
):
    profile = s.query(WorkflowProfile).filter(WorkflowProfile.workflow_id == wf.id).first()
    if profile is None:
        profile = WorkflowProfile(id=f"profile_{wf.id}", tenant_id=TENANT, workflow_id=wf.id)
        s.add(profile)
    fallback = _semester_meta_for_date(wf.created_at)
    semester_meta = _semester_meta_from_key(semester_key, wf.created_at) if semester_key else fallback
    profile.semester_key = semester_key or profile.semester_key or semester_meta["key"]
    profile.semester_label = semester_label or profile.semester_label or semester_meta["label"]
    profile.category = category or profile.category or _approval_category(wf.process_key, wf.label)
    profile.reference_code = profile.reference_code or reference_code or _generate_reference_code(s, wf.process_key, wf.label, wf.created_at)
    if notes:
        profile.notes = notes
    profile.updated_at = datetime.utcnow()
    s.commit()
    return profile


def _bop_process():
    return _workflow_process("branch_operational_plan")


def _actor_name(s, ctx):
    user = s.query(User).get(ctx["sub"])
    person = s.query(Person).get(user.person_id) if user else None
    return person.name if person else (user.username if user else ctx["sub"])


def _require_bop_owner(ctx):
    if ctx.get("office_n") != 3 or ctx.get("scope_level") != "campus":
        raise HTTPException(403, "Branch Operational Plans are available only to Campus Head offices")
    campus = (ctx.get("scope_ref") or "").strip()
    if not campus or campus.startswith("scope_"):
        raise HTTPException(403, "Your Campus Head account has no assigned campus scope")
    return campus


def _bop_data(profile):
    if not profile or not profile.notes:
        return {}
    try:
        data = json.loads(profile.notes)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def _bop_scope_matches(s, wf, ctx):
    if wf.process_key != "branch_operational_plan" or ctx.get("scope_level") != "campus":
        return True
    profile = s.query(WorkflowProfile).filter(WorkflowProfile.workflow_id == wf.id).first()
    return _bop_data(profile).get("campus") == ctx.get("scope_ref")


def _resolve_campus_scope(s, ctx):
    if ctx.get("scope_level") != "campus":
        return None
    scope_ref = (ctx.get("scope_ref") or "").strip()
    if not scope_ref or scope_ref.startswith("scope_"):
        row = s.query(OrgScope).filter(OrgScope.tenant_id == ctx.get("tenant_id", TENANT),
                                        OrgScope.id == scope_ref,
                                        OrgScope.level == "campus").first()
    else:
        row = s.query(OrgScope).filter(OrgScope.tenant_id == ctx.get("tenant_id", TENANT),
                                        OrgScope.name == scope_ref,
                                        OrgScope.level == "campus").first()
    return row


def _capex_scope_matches(s, wf, ctx):
    if wf.process_key not in ("infrastructure_capex", "infrastructure_capex_v2") or ctx.get("office_n") != 3:
        return True
    campus_scope = _resolve_campus_scope(s, ctx)
    return bool(campus_scope and wf.scope_level == "campus" and wf.campus_scope_id == campus_scope.id)


def _bop_payload(s, wf):
    proc = _bop_process()
    profile = s.query(WorkflowProfile).filter(WorkflowProfile.workflow_id == wf.id).first()
    data = _bop_data(profile)
    return {
        "id": wf.id,
        "workflow_id": wf.id,
        "title": wf.title,
        "campus": data.get("campus", ""),
        "planning_period": data.get("planning_period", ""),
        "strategic_alignment": data.get("strategic_alignment", ""),
        "initiatives": data.get("initiatives", []),
        "activities": data.get("activities", []),
        "responsible_areas": data.get("responsible_areas", []),
        "resources": data.get("resources", []),
        "timeline": data.get("timeline", ""),
        "kpi_references": data.get("kpi_references", []),
        "risks": data.get("risks", []),
        "notes": data.get("notes", ""),
        "status": wf.state,
        "created_by": wf.initiator_name,
        "created_at": wf.created_at.isoformat(),
        "updated_at": wf.updated_at.isoformat() if wf.updated_at else wf.created_at.isoformat(),
        "submission": data.get("submission", {}),
        "vc_review": data.get("vc_review", {}),
        "chain": proc["chain"],
    }


class BOPBody(BaseModel):
    title: str
    planning_period: str = ""
    strategic_alignment: str = ""
    initiatives: list[str] = []
    activities: list[str] = []
    responsible_areas: list[str] = []
    resources: list[str] = []
    timeline: str = ""
    kpi_references: list[str] = []
    risks: list[str] = []
    notes: str = ""


def _clean_bop_body(body: BOPBody, campus: str):
    return {
        "campus": campus,
        "planning_period": body.planning_period.strip(),
        "strategic_alignment": body.strategic_alignment.strip(),
        "initiatives": [item.strip() for item in body.initiatives if item.strip()],
        "activities": [item.strip() for item in body.activities if item.strip()],
        "responsible_areas": [item.strip() for item in body.responsible_areas if item.strip()],
        "resources": [item.strip() for item in body.resources if item.strip()],
        "timeline": body.timeline.strip(),
        "kpi_references": [item.strip() for item in body.kpi_references if item.strip()],
        "risks": [item.strip() for item in body.risks if item.strip()],
        "notes": body.notes.strip(),
    }


@app.get("/api/bop")
def list_bop(ctx=Depends(auth), s=Depends(db)):
    campus = _require_bop_owner(ctx)
    rows = (s.query(WorkflowInstance)
            .filter(WorkflowInstance.tenant_id == ctx.get("tenant_id", TENANT),
                    WorkflowInstance.process_key == "branch_operational_plan",
                    WorkflowInstance.initiator_id == ctx["sub"])
            .order_by(desc(WorkflowInstance.updated_at)).all())
    plans = []
    for wf in rows:
        if _bop_scope_matches(s, wf, {**ctx, "scope_ref": campus}):
            plans.append(_bop_payload(s, wf))
    return {"plans": plans, "plan": plans[0] if plans else None, "campus": campus}


@app.post("/api/bop")
def create_bop(body: BOPBody, ctx=Depends(auth), s=Depends(db)):
    campus = _require_bop_owner(ctx)
    title = body.title.strip()
    if not title:
        raise HTTPException(400, "Plan title is required")
    u = s.query(User).get(ctx["sub"])
    p = s.query(Person).get(u.person_id)
    wf = WorkflowInstance(id=uid(), tenant_id=TENANT, process_key="branch_operational_plan",
                          label="Branch Operational Plan", office_n=3, title=title,
                          state="draft", initiator_id=u.id,
                          initiator_name=p.name if p else u.username, current_stage=0,
                          scope_level="campus")
    s.add(wf)
    s.commit()
    profile = _ensure_workflow_profile(s, wf, category="Campus Management")
    profile.notes = json.dumps(_clean_bop_body(body, campus), sort_keys=True)
    s.commit()
    write_audit(s, u.id, p.name if p else u.username, 3,
                "bop.create", f"bop:{wf.id}", "", "draft", "Created Branch Operational Plan")
    return _bop_payload(s, wf)


@app.put("/api/bop/{wid}")
def update_bop(wid: str, body: BOPBody, ctx=Depends(auth), s=Depends(db)):
    campus = _require_bop_owner(ctx)
    wf = s.query(WorkflowInstance).get(wid)
    if not wf or wf.process_key != "branch_operational_plan" or wf.initiator_id != ctx["sub"]:
        raise HTTPException(404, "Branch Operational Plan not found")
    if not _bop_scope_matches(s, wf, {**ctx, "scope_ref": campus}):
        raise HTTPException(403, "Branch Operational Plan is outside your authorized campus")
    if wf.state not in ("draft", "returned"):
        raise HTTPException(409, "Only draft or returned plans can be edited")
    profile = s.query(WorkflowProfile).filter(WorkflowProfile.workflow_id == wf.id).first()
    wf.title = body.title.strip()
    if not wf.title:
        raise HTTPException(400, "Plan title is required")
    previous = wf.state
    profile.notes = json.dumps(_clean_bop_body(body, campus), sort_keys=True)
    wf.updated_at = datetime.utcnow()
    s.commit()
    write_audit(s, ctx["sub"], _actor_name(s, ctx), 3,
                "bop.edit", f"bop:{wf.id}", previous, wf.state, "Edited Branch Operational Plan")
    return _bop_payload(s, wf)


def _submit_bop(wid: str, ctx, s, action: str):
    campus = _require_bop_owner(ctx)
    wf = s.query(WorkflowInstance).get(wid)
    if not wf or wf.process_key != "branch_operational_plan" or wf.initiator_id != ctx["sub"]:
        raise HTTPException(404, "Branch Operational Plan not found")
    if not _bop_scope_matches(s, wf, {**ctx, "scope_ref": campus}):
        raise HTTPException(403, "Branch Operational Plan is outside your authorized campus")
    valid = ("draft",) if action == "submit" else ("returned",)
    if wf.state not in valid:
        raise HTTPException(409, f"Cannot {action} a plan in the '{wf.state}' state")
    profile = s.query(WorkflowProfile).filter(WorkflowProfile.workflow_id == wf.id).first()
    data = _bop_data(profile)
    u = s.query(User).get(ctx["sub"])
    previous = wf.state
    wf.state = "submitted"
    wf.current_stage = 1
    wf.updated_at = datetime.utcnow()
    data["submission"] = {"submitted_by": _actor_name(s, ctx), "submitted_at": wf.updated_at.isoformat()}
    profile.notes = json.dumps(data, sort_keys=True)
    s.commit()
    write_audit(s, u.id, _actor_name(s, ctx), 3, f"bop.{action}", f"bop:{wf.id}",
                previous, wf.state, f"{action.title()}d Branch Operational Plan")
    _notify_stage(s, wf, _bop_process())
    return _bop_payload(s, wf)


@app.post("/api/bop/{wid}/submit")
def submit_bop(wid: str, ctx=Depends(auth), s=Depends(db)):
    return _submit_bop(wid, ctx, s, "submit")


@app.post("/api/bop/{wid}/resubmit")
def resubmit_bop(wid: str, ctx=Depends(auth), s=Depends(db)):
    return _submit_bop(wid, ctx, s, "resubmit")


def _start_workflow_record(
    s,
    ctx,
    process_key: str,
    title: str,
    amount: float | None = None,
    semester_key: str = "",
    semester_label: str = "",
    notes: str = "",
):
    effective_process_key = "infrastructure_capex_v2" if process_key == "infrastructure_capex" else process_key
    proc = _workflow_process(effective_process_key)
    if not proc:
        raise HTTPException(404, "Unknown process")
    clean_title = (title or "").strip()
    if not clean_title:
        raise HTTPException(400, "Describe the request")
    campus_scope = None
    if effective_process_key == "infrastructure_capex_v2":
        campus_scope = _resolve_campus_scope(s, ctx)
        if not campus_scope:
            raise HTTPException(403, "Infrastructure CAPEX requires a valid authenticated campus scope")
    u = s.query(User).get(ctx["sub"])
    p = s.query(Person).get(u.person_id)
    verdict = rbac_for(ctx["office_n"], office(ctx["office_n"])["level"], "create")
    if verdict == A.NOT_ALLOWED:
        # Students can still initiate their own requests (create=Limited).
        pass
    wf = WorkflowInstance(
        id=uid(), tenant_id=TENANT, process_key=proc["key"], label=proc["label"],
        office_n=proc["office_n"], title=clean_title, state="submitted",
        amount=amount, initiator_id=u.id, initiator_name=p.name if p else u.username,
        current_stage=1, scope_level=ctx.get("scope_level", "campus"),
        campus_scope_id=campus_scope.id if campus_scope else None)
    s.add(wf)
    s.commit()
    _ensure_workflow_profile(s, wf, semester_key=semester_key, semester_label=semester_label, notes=notes)
    write_audit(s, u.id, p.name if p else u.username, ctx["office_n"],
                f"workflow.start:{proc['key']}", f"wf:{wf.id}", "draft", "submitted",
                f"Initiated {proc['label']}")
    _notify_stage(s, wf, proc)
    return wf, proc


class StartWF(BaseModel):
    process_key: str
    title: str
    amount: float | None = None


@app.post("/api/workflows/start")
def start_workflow(body: StartWF, ctx=Depends(auth), s=Depends(db)):
    wf, proc = _start_workflow_record(s, ctx, body.process_key, body.title, body.amount)
    return _wf_payload(s, wf, proc)
    proc = next((p for p in APPROVAL_MATRIX if p["key"] == body.process_key), None)
    if not proc:
        raise HTTPException(404, "Unknown process")
    u = s.query(User).get(ctx["sub"])
    p = s.query(Person).get(u.person_id)
    # Permission: can this office 'submit'/'create'?
    verdict = rbac_for(ctx["office_n"], office(ctx["office_n"])["level"], "create")
    if verdict == A.NOT_ALLOWED:
        # students can still initiate their own requests (create=Limited)
        pass
    wf = WorkflowInstance(
        id=uid(), tenant_id=TENANT, process_key=proc["key"], label=proc["label"],
        office_n=proc["office_n"], title=body.title, state="submitted",
        amount=body.amount, initiator_id=u.id, initiator_name=p.name if p else u.username,
        current_stage=1, scope_level=ctx.get("scope_level", "campus"))
    s.add(wf)
    s.commit()
    write_audit(s, u.id, p.name if p else u.username, ctx["office_n"],
                f"workflow.start:{proc['key']}", f"wf:{wf.id}", "draft", "submitted",
                f"Initiated {proc['label']}")
    # notify next approver stage (best-effort: notify all users whose office head
    # matches the stage — simplified to the process-owning office).
    _notify_stage(s, wf, proc)
    return _wf_payload(s, wf, proc)


def _notify_stage(s, wf, proc):
    stage = wf.current_stage
    if stage >= len(proc["chain"]):
        return
    label = proc["chain"][stage]
    recipients = []
    recipient_office = proc["office_n"]
    if wf.process_key == "infrastructure_capex_v2" and wf.state == "escalated":
        recipient_office = 1
        label = "Chairman"
    elif wf.process_key == "branch_operational_plan" and "vice chairman" in label.lower():
        recipient_office = 2
    elif wf.process_key == "infrastructure_capex_v2" and "campus head" in label.lower():
        recipient_office = 3
    owner = s.query(User).filter(User.office_n == recipient_office).first()
    if owner:
        recipients.append(owner)
    recipients.extend(_delegation_targets_for_workflow(s, wf))

    seen = set()
    for recipient in recipients:
        if not recipient or recipient.id in seen:
            continue
        seen.add(recipient.id)
        notify(s, recipient.id, f"Action needed: {proc['label']}",
               f"{wf.title} - awaiting {label}", severity="action")
    return
    # Notify the owning office head as a representative approver.
    owner = s.query(User).filter(User.office_n == proc["office_n"]).first()
    if owner:
        notify(s, owner.id, f"Action needed: {proc['label']}",
               f"{wf.title} — awaiting {label}", severity="action")


class DecideWF(BaseModel):
    workflow_id: str
    action: str          # approve / reject / review / escalate / execute
    reason: str = ""


def _principal_workflow_actions(wf, proc, ctx):
    """Return the actions a Principal may be offered at this exact workflow stage.

    The final decision remains with authorize() in decide_workflow; this only
    prevents the UI from advertising decisions for another office's stage.
    """
    if ctx.get("office_n") != 4 or wf.state in ("approved", "executed", "rejected"):
        return [], "This workflow has reached a terminal state."
    stage_label = proc["chain"][wf.current_stage] if proc and 0 <= wf.current_stage < len(proc["chain"]) else ""
    if "principal" not in stage_label.lower():
        return [], f"Decision unavailable at the current workflow stage. It is awaiting {stage_label or 'the configured approver'}."
    if wf.process_key == "compliance_requirement":
        return ["review", "return", "escalate"], "Principal action is available at the current workflow stage."
    return ["review", "approve", "reject", "escalate"], "Principal decision is available at the current workflow stage."


def _bop_workflow_actions(wf, ctx):
    if ctx.get("office_n") != 2:
        return [], "Only the Vice Chairman may review a Branch Operational Plan."
    if wf.state == "submitted" and wf.current_stage == 1:
        return ["review", "return"], "Review or return this Branch Operational Plan."
    if wf.state in ("reviewed", "under_review") and wf.current_stage >= 2:
        return ["approve", "return"], "Approve or return this Branch Operational Plan."
    return [], "This Branch Operational Plan is not awaiting Vice Chairman action."


def _campus_head_workflow_actions(s, wf, proc, ctx):
    if ctx.get("office_n") != 3 or ctx.get("scope_level") != "campus":
        return [], "Campus Head approval is unavailable."
    if wf.process_key != "infrastructure_capex_v2":
        return [], "Campus Head approval is only available for the v2 infrastructure CAPEX process."
    if wf.initiator_id == ctx.get("sub"):
        return [], "Segregation of duties: requester cannot approve own request."
    if wf.state not in ("submitted", "under_review", "reviewed", "escalated"):
        return [], "Workflow is not actionable by the Campus Head."
    if wf.current_stage != 3:
        return [], "Campus Head approval is only available at the v2 stage 3 action point."
    if not wf.campus_scope_id:
        return [], "Campus Head action requires a resolved campus scope."
    campus_scope = _resolve_campus_scope(s, ctx)
    if not campus_scope or wf.campus_scope_id != campus_scope.id:
        return [], "Infrastructure CAPEX is outside your authorized campus."
    if proc is None:
        return [], "Workflow process is unavailable."
    stage_label = proc["chain"][wf.current_stage] if 0 <= wf.current_stage < len(proc["chain"]) else ""
    if "campus head" not in stage_label.lower() and "branch director" not in stage_label.lower():
        return [], f"Decision unavailable at the current workflow stage. It is awaiting {stage_label or 'the configured approver'}."
    user = s.query(User).get(ctx["sub"])
    office_config = office(ctx["office_n"])
    approval_limit = approval_limit_for(ctx.get("scope_level", "campus"), wf.process_key)
    actions = []
    escalation = None
    for action in ("review", "approve", "reject", "escalate"):
        if action == "escalate" and wf.amount is not None and approval_limit is not None and wf.amount <= approval_limit:
            continue
        rbac = rbac_for(ctx["office_n"], office_config["level"], action if action in VERBS else "approve")
        decision = authorize(
            ctx=ctx, action=action, resource=f"workflow:{wf.process_key}",
            rbac_authority=rbac, workflow_state=wf.state,
            workflow_valid_states=WF_VALID.get(action), amount=wf.amount,
            approval_limit=approval_limit,
            requester_id=wf.initiator_id,
            active_delegation=active_delegations_for(s, user.id),
            target_scope_level=wf.scope_level, escalate_to=proc.get("escalation") if proc else None,
        )
        if decision.outcome == ALLOW:
            if action not in actions:
                actions.append(action)
        elif action == "approve" and decision.outcome in (ESCALATE, RECOMMEND_OUT):
            if "escalate" not in actions:
                actions.append("escalate")
            escalation = decision.reason
    if escalation:
        return actions, escalation
    return actions, "Campus Head actions are available at the current workflow stage." if actions else "No authorized action is available at the current workflow stage."


def _campus_head_workflow_scope(s, wf, ctx):
    if ctx.get("office_n") != 3:
        return True
    if ctx.get("scope_level") != "campus":
        return False
    if wf.process_key == "infrastructure_capex_v2":
        campus_scope = _resolve_campus_scope(s, ctx)
        return bool(campus_scope and wf.scope_level == "campus" and wf.campus_scope_id == campus_scope.id and wf.campus_scope_id is not None)
    if wf.process_key == "infrastructure_capex":
        return _capex_scope_matches(s, wf, ctx)
    profile = s.query(WorkflowProfile).filter(WorkflowProfile.workflow_id == wf.id).first()
    return _bop_data(profile).get("campus") == ctx.get("scope_ref")


@app.post("/api/workflows/decide")
def decide_workflow(body: DecideWF, ctx=Depends(auth), s=Depends(db)):
    wf = s.query(WorkflowInstance).get(body.workflow_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    if wf.tenant_id != ctx.get("tenant_id", TENANT):
        raise HTTPException(403, "Workflow is outside your authorized tenant")
    proc = next((p for p in APPROVAL_MATRIX if p["key"] == wf.process_key), None)
    if wf.process_key == "branch_operational_plan":
        allowed_actions, unavailable_reason = _bop_workflow_actions(wf, ctx)
        if body.action not in allowed_actions:
            raise HTTPException(403, unavailable_reason)
        if body.action == "return" and not body.reason.strip():
            raise HTTPException(400, "Please provide feedback before returning this plan.")
    if ctx["office_n"] == 3 and wf.process_key != "branch_operational_plan":
        if wf.process_key == "infrastructure_capex" and not _capex_scope_matches(s, wf, ctx):
            raise HTTPException(403, "Infrastructure CAPEX is outside your authorized campus")
        campus_actions, campus_reason = _campus_head_workflow_actions(s, wf, proc, ctx)
        if body.action not in campus_actions:
            raise HTTPException(403, campus_reason)
    if ctx["office_n"] == 4:
        allowed_actions, unavailable_reason = _principal_workflow_actions(wf, proc, ctx)
        if body.action not in allowed_actions:
            raise HTTPException(403, unavailable_reason)
    compliance = s.query(D.ComplianceRequirement).filter(D.ComplianceRequirement.workflow_id == wf.id).first()
    if compliance:
        if ctx["office_n"] != 4:
            raise HTTPException(403, "Only the Principal may act on a compliance requirement")
        if compliance.tenant_id != ctx.get("tenant_id") or (ctx.get("scope_level") == "campus" and compliance.campus != ctx.get("scope_ref")):
            raise HTTPException(403, "Compliance requirement is outside your authorized campus")
        if wf.current_stage != 2:
            raise HTTPException(403, "Compliance requirement is not at the Principal workflow stage")
        if body.action not in ("review", "return", "escalate"):
            raise HTTPException(400, "Unsupported compliance workflow action")
        if body.action == "return" and not body.reason.strip():
            raise HTTPException(400, "Please provide a reason before returning this requirement.")
    u = s.query(User).get(ctx["sub"])
    p = s.query(Person).get(u.person_id)
    o = office(ctx["office_n"])

    # Resolve RBAC authority for this action.
    verb = "review" if wf.process_key == "branch_operational_plan" and body.action == "return" else ("approve" if body.action in ("approve", "execute", "return") else body.action)
    if body.action == "reject":
        verb = "reject"
    rbac = rbac_for(ctx["office_n"], o["level"], verb if verb in VERBS else "approve")

    # Approval limit for this process & the actor's scope.
    limit = approval_limit_for(ctx.get("scope_level", "campus"), wf.process_key) \
        if proc and proc.get("amount") else None

    # Run the authority gate (Document §7 steps 8-13).
    dec = authorize(
        ctx=ctx, action=("review" if wf.process_key == "branch_operational_plan" and body.action == "return" else ("reject" if body.action == "return" else body.action)) if body.action in VERBS or body.action == "return" else "approve",
        resource=f"workflow:{wf.process_key}",
        rbac_authority=rbac,
        workflow_state=wf.state,
        workflow_valid_states=WF_VALID.get("return") if wf.process_key == "branch_operational_plan" and body.action == "return" else WF_VALID.get(body.action),
        amount=wf.amount, approval_limit=limit,
        requester_id=wf.initiator_id,
        active_delegation=active_delegations_for(s, u.id),
        target_scope_level=wf.scope_level,
        escalate_to=proc["escalation"] if proc else None,
    )

    # Record the approval decision.
    stage_label = proc["chain"][min(wf.current_stage, len(proc["chain"]) - 1)] if proc else body.action
    s.add(Approval(id=uid(), tenant_id=TENANT, workflow_id=wf.id, actor_id=u.id,
                   actor_name=p.name if p else u.username, stage=wf.current_stage,
                   stage_label=stage_label, decision=dec.outcome, authority=dec.authority,
                   reason=body.reason or dec.reason))

    # Apply the decision to workflow state.
    prev_state = wf.state
    bop_profile = None
    bop_data = {}
    if wf.process_key == "branch_operational_plan":
        bop_profile = s.query(WorkflowProfile).filter(WorkflowProfile.workflow_id == wf.id).first()
        bop_data = _bop_data(bop_profile)
    if dec.outcome == ALLOW and wf.process_key == "branch_operational_plan":
        if body.action == "review":
            wf.state = "reviewed"
            wf.current_stage = 2
        elif body.action == "return":
            wf.state = "returned"
            wf.current_stage = 0
        else:
            wf.state = "active"
            wf.current_stage = 2
        bop_data["vc_review"] = {
            "reviewed_by": _actor_name(s, ctx),
            "reviewed_at": datetime.utcnow().isoformat(),
            "decision": "returned" if body.action == "return" else "approved",
            "feedback": body.reason.strip(),
        }
        if bop_profile:
            bop_profile.notes = json.dumps(bop_data, sort_keys=True)
    elif dec.outcome == ALLOW:
        if body.action == "reject":
            wf.state = "rejected"
        elif body.action == "return":
            wf.state = "submitted"
            wf.current_stage = 1
        elif compliance and body.action == "escalate":
            wf.state = "escalated"
            wf.escalated = True
        elif body.action == "execute":
            wf.state = "executed"
        elif body.action == "review":
            wf.state = "reviewed"
            wf.current_stage = min(wf.current_stage + 1, len(proc["chain"]) if proc else 4)
        else:  # approve
            wf.current_stage += 1
            if proc and wf.current_stage >= len(proc["chain"]):
                wf.state = "approved"
            else:
                wf.state = "under_review"
    elif dec.outcome == ESCALATE or (compliance and body.action == "escalate" and dec.outcome == RECOMMEND_OUT):
        wf.state = "escalated"
        wf.escalated = True
    elif dec.outcome == RECOMMEND_OUT:
        wf.state = "under_review"
        wf.current_stage += 1
    else:  # DENY
        pass  # state unchanged; decision recorded

    wf.updated_at = datetime.utcnow()
    s.commit()

    write_audit(s, u.id, p.name if p else u.username, ctx["office_n"],
                f"workflow.{body.action}:{wf.process_key}", f"wf:{wf.id}",
                prev_state, wf.state, dec.reason, ctx.get("auth_level", "mfa"))

    # Notify initiator of outcome.
    if dec.outcome in (ALLOW, ESCALATE, RECOMMEND_OUT) and wf.state in ("approved", "executed", "escalated", "rejected"):
        sev = "critical" if wf.state == "escalated" else "info"
        notify(s, wf.initiator_id, f"{wf.label}: {wf.state}",
               f"{wf.title} — {dec.reason}", severity=sev)
        if wf.process_key == "branch_operational_plan" and dec.outcome == ALLOW and wf.state == "returned":
         notify(s, wf.initiator_id, f"{wf.label}: returned",
             f"{wf.title} — {body.reason or 'Vice Chairman feedback is available.'}", severity="action")
    if (wf.process_key == "branch_operational_plan" and body.action == "approve"
            and dec.outcome == ALLOW and wf.state == "active"):
        notify(s, wf.initiator_id, f"{wf.label}: approved",
               f"{wf.title} — approved by {p.name if p else u.username}. {dec.reason}", severity="info")
    if proc:
        _notify_stage(s, wf, proc)

    return {"decision": dec.as_dict(), "workflow": _wf_payload(s, wf, proc)}


def _wf_payload(s, wf, proc):
    approvals = (s.query(Approval).filter(Approval.workflow_id == wf.id)
                 .order_by(Approval.created_at).all())
    profile = s.query(WorkflowProfile).filter(WorkflowProfile.workflow_id == wf.id).first()
    return {
        "id": wf.id, "process_key": wf.process_key, "label": wf.label,
        "office_n": wf.office_n, "title": wf.title, "state": wf.state,
        "amount": wf.amount, "initiator": wf.initiator_name,
        "current_stage": wf.current_stage, "escalated": wf.escalated,
        "scope_level": wf.scope_level,
        "chain": proc["chain"] if proc else [],
        "escalation": proc["escalation"] if proc else "",
        "created_at": wf.created_at.isoformat(),
        "profile": {
            "semester_key": profile.semester_key if profile else "",
            "semester_label": profile.semester_label if profile else "",
            "category": profile.category if profile else _approval_category(wf.process_key, wf.label),
            "reference_code": profile.reference_code if profile else _generate_reference_code(s, wf.process_key, wf.label, wf.created_at),
            "notes": profile.notes if profile else "",
        },
        "history": [{"stage": a.stage, "stage_label": a.stage_label, "actor": a.actor_name,
                     "decision": a.decision, "authority": a.authority, "reason": a.reason,
                     "at": a.created_at.isoformat()} for a in approvals],
    }


def _workflow_stage_meta(wf, proc):
    total = max(len(proc["chain"]) if proc else 4, 1)
    step = min(max(wf.current_stage or 1, 1), total)
    if wf.state in ("approved", "executed", "rejected") or step >= total:
        key = "final_approval"
    elif step == 1:
        key = "submission"
    elif step == 2:
        key = "review"
    else:
        key = "approval"
    return {
        "key": key,
        "label": STAGE_META[key]["label"],
        "tone": STAGE_META[key]["tone"],
        "step": step,
        "total": total,
    }


def _workflow_state_meta(state: str):
    meta = STATE_FILTER_META.get(state, {"label": state.replace("_", " ").title(), "tone": "neutral"})
    return {"key": state, **meta}


def _chairman_can_review(proc, wf):
    if wf.state not in ("submitted", "under_review", "reviewed", "escalated"):
        return False
    if wf.office_n == 1:
        return True
    if wf.escalated:
        return True
    if not proc:
        return False
    return proc.get("escalation") == "Chairman" or any("Chairman" in stage for stage in proc.get("chain", []))


def _chairman_request_row(s, wf):
    proc = _workflow_process(wf.process_key)
    payload = _wf_payload(s, wf, proc)
    stage = _workflow_stage_meta(wf, proc)
    state = _workflow_state_meta(wf.state)
    profile = payload.get("profile", {})
    return {
        "id": wf.id,
        "process_key": wf.process_key,
        "process_label": wf.label,
        "category": profile.get("category") or _approval_category(wf.process_key, wf.label),
        "title": wf.title,
        "reference_code": profile.get("reference_code") or "",
        "initiator_id": wf.initiator_id,
        "initiator": wf.initiator_name,
        "amount": wf.amount,
        "stage": stage,
        "state": state,
        "received_on": wf.created_at.isoformat(),
        "updated_at": wf.updated_at.isoformat() if wf.updated_at else wf.created_at.isoformat(),
        "semester_key": profile.get("semester_key") or "",
        "semester_label": profile.get("semester_label") or "",
        "notes": profile.get("notes") or "",
        "workflow": payload,
    }


def _chairman_process_options():
    return [{
        "key": proc["key"],
        "label": proc["label"],
        "amount": proc.get("amount", False),
        "chain": proc.get("chain", []),
        "escalation": proc.get("escalation", ""),
        "category": _approval_category(proc["key"], proc["label"]),
    } for proc in APPROVAL_MATRIX]


def _visible_page_numbers(page: int, total_pages: int):
    start = max(1, page - 2)
    end = min(total_pages, start + 4)
    start = max(1, end - 4)
    return list(range(start, end + 1))


@app.get("/api/workflows")
def list_workflows(scope: str = "all", ctx=Depends(auth), s=Depends(db)):
    if scope not in ("inbox", "mine", "all"):
        raise HTTPException(400, "Unknown workflow view")

    def in_authorized_scope(workflow):
        return (A.scope_covers(ctx.get("scope_level", "individual"), workflow.scope_level or "individual")
            and _bop_scope_matches(s, workflow, ctx)
            and _campus_head_workflow_scope(s, workflow, ctx))

    q = s.query(WorkflowInstance).filter(WorkflowInstance.tenant_id == ctx.get("tenant_id", TENANT))
    pending_states = ["submitted", "under_review", "reviewed", "escalated"]
    if scope == "mine":
        rows = (q.filter(WorkflowInstance.initiator_id == ctx["sub"])
                .order_by(desc(WorkflowInstance.updated_at)).limit(100).all())
    elif scope == "inbox":
        candidates = (q.filter(WorkflowInstance.state.in_(pending_states))
                      .order_by(desc(WorkflowInstance.updated_at)).limit(220).all())
        if ctx["office_n"] == 4:
            # A Principal inbox is defined by the current approval stage, not
            # by the office which originally owned the workflow process.
            rows = [wf for wf in candidates
                    if in_authorized_scope(wf) and _principal_workflow_actions(wf, _workflow_process(wf.process_key), ctx)[0]][:100]
        else:
            own_rows = [wf for wf in candidates if wf.office_n == ctx["office_n"] and in_authorized_scope(wf)]
            if ctx["office_n"] == 2:
                own_rows.extend(wf for wf in candidates
                                if wf.process_key == "branch_operational_plan"
                                and wf.current_stage == 1
                                and "vice chairman" in (_workflow_process(wf.process_key)["chain"][1]).lower()
                                and in_authorized_scope(wf)
                                and wf.id not in {row.id for row in own_rows})
            if ctx["office_n"] == 3:
                own_rows.extend(wf for wf in candidates
                                if wf.process_key == "infrastructure_capex_v2"
                                and wf.current_stage == 3
                                and in_authorized_scope(wf)
                                and wf.id not in {row.id for row in own_rows})
            delegated = active_delegations_for(s, ctx["sub"])
            seen = {row.id for row in own_rows}
            rows = list(own_rows)
            for wf in candidates:
                if wf.id in seen or not in_authorized_scope(wf):
                    continue
                if delegated and _delegation_matches_workflow(delegated, wf, ctx.get("scope_level", "individual")):
                    rows.append(wf)
                    seen.add(wf.id)
            rows = sorted(rows, key=lambda item: item.updated_at or item.created_at, reverse=True)[:100]
            if ctx["office_n"] == 3:
                rows = [wf for wf in rows if _campus_head_workflow_actions(s, wf, _workflow_process(wf.process_key), ctx)[0]]
    else:
        rows = [wf for wf in q.order_by(desc(WorkflowInstance.updated_at)).limit(220).all() if in_authorized_scope(wf)][:100]
    rows = [wf for wf in rows if in_authorized_scope(wf)]
    out = []
    for wf in rows:
        proc = next((p for p in APPROVAL_MATRIX if p["key"] == wf.process_key), None)
        payload = _wf_payload(s, wf, proc)
        if ctx["office_n"] == 4:
            payload["available_actions"], payload["action_message"] = _principal_workflow_actions(wf, proc, ctx)
        elif wf.process_key == "branch_operational_plan":
            payload["available_actions"], payload["action_message"] = _bop_workflow_actions(wf, ctx)
        elif ctx["office_n"] == 3:
            payload["available_actions"], payload["action_message"] = _campus_head_workflow_actions(s, wf, proc, ctx)
        out.append(payload)
    return {"workflows": out, "total": len(out), "scope": scope}


@app.get("/api/workflows/{wid}")
def get_workflow(wid: str, ctx=Depends(auth), s=Depends(db)):
    wf = s.query(WorkflowInstance).get(wid)
    if not wf:
        raise HTTPException(404, "Not found")
    if wf.tenant_id != ctx.get("tenant_id", TENANT):
        raise HTTPException(403, "Workflow is outside your authorized tenant")
    if (not A.scope_covers(ctx.get("scope_level", "individual"), wf.scope_level or "individual")
            or not _bop_scope_matches(s, wf, ctx)
            or not _campus_head_workflow_scope(s, wf, ctx)):
        raise HTTPException(403, "Workflow is outside your authorized scope")
    proc = next((p for p in APPROVAL_MATRIX if p["key"] == wf.process_key), None)
    payload = _wf_payload(s, wf, proc)
    if ctx["office_n"] == 4:
        payload["available_actions"], payload["action_message"] = _principal_workflow_actions(wf, proc, ctx)
    elif ctx["office_n"] == 3:
        payload["available_actions"], payload["action_message"] = _campus_head_workflow_actions(s, wf, proc, ctx)
    return payload


class ChairmanStartWF(BaseModel):
    process_key: str
    title: str
    semester_key: str = ""
    semester_label: str = ""
    notes: str = ""
    amount: float | None = None


@app.get("/api/approvals/chairman")
def chairman_approvals(
    tab: str = "inbox",
    semester: str = "all",
    status: str = "all",
    stage: str = "all",
    process: str = "all",
    q: str = "",
    page: int = 1,
    page_size: int = 5,
    ctx=Depends(auth),
    s=Depends(db),
):
    if ctx["office_n"] != 1:
        raise HTTPException(403, "This approvals dashboard is available only in the chairman workspace")

    page = max(1, page)
    page_size = min(20, max(5, page_size))

    rows = (s.query(WorkflowInstance)
            .join(WorkflowProfile, WorkflowProfile.workflow_id == WorkflowInstance.id)
            .order_by(desc(WorkflowInstance.updated_at)).all())
    workflow_rows = [(wf, _workflow_process(wf.process_key)) for wf in rows]
    mapped = [_chairman_request_row(s, wf) for wf, _ in workflow_rows]
    inbox_rows = [mapped[index] for index, (wf, proc) in enumerate(workflow_rows) if _chairman_can_review(proc, wf)]
    mine_rows = [row for row in mapped if row["initiator_id"] == ctx["sub"]]

    selected_tab = tab if tab in ("inbox", "mine", "all") else "inbox"
    if selected_tab == "mine":
        scoped = mine_rows
    elif selected_tab == "all":
        scoped = mapped
    else:
        scoped = inbox_rows

    query = (q or "").strip().lower()
    filtered = []
    for row in scoped:
        if semester != "all" and row["semester_key"] != semester:
            continue
        if status != "all" and row["state"]["key"] != status:
            continue
        if stage != "all" and row["stage"]["key"] != stage:
            continue
        if process != "all" and row["process_key"] != process:
            continue
        haystack = " ".join([
            row["process_label"], row["category"], row["title"], row["reference_code"],
            row["initiator"], row["semester_label"], row["notes"],
        ]).lower()
        if query and query not in haystack:
            continue
        filtered.append(row)

    total = len(filtered)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    start_index = (page - 1) * page_size
    page_rows = filtered[start_index:start_index + page_size]
    month_key = datetime.utcnow().strftime("%Y-%m")

    approved_this_month = sum(
        1 for row in mapped
        if row["state"]["key"] in ("approved", "executed") and row["updated_at"].startswith(month_key)
    )
    rejected_this_month = sum(
        1 for row in mapped
        if row["state"]["key"] == "rejected" and row["updated_at"].startswith(month_key)
    )
    under_review_count = sum(
        1 for row in mapped if row["state"]["key"] in ("submitted", "under_review", "reviewed", "escalated")
    )

    semester_pairs = sorted(
        {(row["semester_key"], row["semester_label"]) for row in mapped if row["semester_key"]},
        key=lambda item: item[0],
        reverse=True,
    )
    semester_options = [{"key": "all", "label": "All Semesters"}] + [
        {"key": key, "label": label} for key, label in semester_pairs
    ]

    status_options = [{"key": "all", "label": "All Status"}]
    seen_status = set()
    for row in mapped:
        state_key = row["state"]["key"]
        if state_key in seen_status:
            continue
        seen_status.add(state_key)
        status_options.append({"key": state_key, "label": row["state"]["label"]})

    stage_options = [{"key": "all", "label": "All Stages"}]
    seen_stage = set()
    for row in mapped:
        stage_key = row["stage"]["key"]
        if stage_key in seen_stage:
            continue
        seen_stage.add(stage_key)
        stage_options.append({"key": stage_key, "label": row["stage"]["label"]})

    process_options = [{"key": "all", "label": "All Processes"}]
    seen_process = set()
    for row in mapped:
        if row["process_key"] in seen_process:
            continue
        seen_process.add(row["process_key"])
        process_options.append({"key": row["process_key"], "label": row["process_label"]})

    fallback_semester = _semester_meta_for_date(datetime.utcnow())
    return {
        "title": "Approvals",
        "subtitle": "Every request runs through the approval chain — permission, limit, delegation, workflow-state and segregation of duties, then audit.",
        "summary": {
            "pending": len(inbox_rows),
            "approved": approved_this_month,
            "rejected": rejected_this_month,
            "under_review": under_review_count,
        },
        "tabs": [
            {"key": "inbox", "label": "My office inbox", "count": len(inbox_rows)},
            {"key": "mine", "label": "My requests", "count": len(mine_rows)},
            {"key": "all", "label": "All workflows", "count": len(mapped)},
        ],
        "filters": {
            "semesters": semester_options,
            "statuses": status_options,
            "stages": stage_options,
            "processes": process_options,
        },
        "form": {
            "processes": _chairman_process_options(),
            "semesters": semester_options[1:] or [fallback_semester],
        },
        "requests": page_rows,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "visible_pages": _visible_page_numbers(page, total_pages),
            "showing_from": (start_index + 1) if total else 0,
            "showing_to": min(total, start_index + len(page_rows)),
        },
        "selected": {
            "tab": selected_tab,
            "semester": semester,
            "status": status,
            "stage": stage,
            "process": process,
            "query": q,
        },
        "can_initiate": rbac_for(ctx["office_n"], office(ctx["office_n"])["level"], "create") != A.NOT_ALLOWED,
    }


@app.post("/api/approvals/chairman/initiate")
def initiate_chairman_request(body: ChairmanStartWF, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] != 1:
        raise HTTPException(403, "This request form is available only in the chairman workspace")
    semester_meta = _semester_meta_from_key(body.semester_key, datetime.utcnow())
    wf, proc = _start_workflow_record(
        s,
        ctx,
        body.process_key,
        body.title,
        body.amount,
        semester_key=body.semester_key or semester_meta["key"],
        semester_label=body.semester_label or semester_meta["label"],
        notes=(body.notes or "").strip(),
    )
    return {"workflow": _wf_payload(s, wf, proc)}


# --------------------------------------------------------------------------- #
#  Delegation (Document §2, §12) — time-bound, scoped, revocable, audited      #
# --------------------------------------------------------------------------- #
class DelegateIn(BaseModel):
    to_username: str
    authority: str = "*"
    days: int = 7
    limit: float | None = None
    reason: str = ""


GENERIC_DELEGATION_AUTHORITIES = {"approve", "review"}
MAX_GENERIC_DELEGATION_DAYS = 90


@app.post("/api/delegations")
def create_delegation(body: DelegateIn, ctx=Depends(auth), s=Depends(db)):
    o = office(ctx["office_n"])
    can = rbac_for(ctx["office_n"], o["level"], "delegate")
    if can in (A.NOT_ALLOWED,):
        raise HTTPException(403, "This office cannot delegate authority")
    tenant_id = ctx.get("tenant_id", TENANT)
    target = (s.query(User)
              .filter(User.username == body.to_username, User.tenant_id == tenant_id,
                      User.status == "active")
              .first())
    if not target:
        raise HTTPException(404, "Target user not found")
    if body.authority not in GENERIC_DELEGATION_AUTHORITIES:
        raise HTTPException(400, "Delegation authority must be approve or review")
    if not 1 <= body.days <= MAX_GENERIC_DELEGATION_DAYS:
        raise HTTPException(400, f"Delegation duration must be 1-{MAX_GENERIC_DELEGATION_DAYS} days")
    if ctx.get("office_n") == 3 and (ctx.get("scope_level") != "campus" or target.scope_level != "campus" or target.scope_ref != ctx.get("scope_ref")):
        raise HTTPException(403, "Campus Head delegations must remain within the assigned campus")
    grantor_authority = rbac_for(ctx["office_n"], o["level"], body.authority)
    target_office = office(target.office_n)
    target_authority = rbac_for(target.office_n, target_office["level"], body.authority)
    if grantor_authority in (A.NOT_ALLOWED,) or target_authority in (A.NOT_ALLOWED,):
        raise HTTPException(403, "Delegation authority is not compatible with the grantor or delegatee")
    if body.limit is not None and body.limit <= 0:
        raise HTTPException(400, "Delegation monetary limit must be positive")
    if body.authority == "approve":
        campus_limit = max(APPROVAL_LIMITS.get("campus", {}).values(), default=0)
        if body.limit is None or body.limit > campus_limit:
            raise HTTPException(400, "Approval delegation requires a permitted monetary limit")
    u = s.query(User).get(ctx["sub"])
    p = s.query(Person).get(u.person_id)
    d = Delegation(id=uid(), tenant_id=tenant_id, from_user=u.id, to_user=target.id,
                   authority=body.authority, scope_ref=ctx.get("scope_ref", "scope_global"),
                   limit=body.limit, start=datetime.utcnow(),
                   end=datetime.utcnow() + timedelta(days=body.days),
                   status="active", reason=body.reason)
    s.add(d)
    s.commit()
    write_audit(s, u.id, p.name if p else u.username, ctx["office_n"],
                "delegation.create", f"deleg:{d.id}", "", "active",
                f"Delegated {body.authority} to {body.to_username} for {body.days}d", tenant_id=tenant_id)
    notify(s, target.id, "Authority delegated to you",
           f"You received '{body.authority}' authority for {body.days} days", "action", tenant_id=tenant_id)
    return _deleg_payload(s, d)


@app.get("/api/delegations")
def list_delegations(ctx=Depends(auth), s=Depends(db)):
    rows = (s.query(Delegation)
            .filter(Delegation.tenant_id == ctx.get("tenant_id", TENANT),
                    or_(Delegation.from_user == ctx["sub"], Delegation.to_user == ctx["sub"]))
            .order_by(desc(Delegation.created_at)).all())
    return {"delegations": [_deleg_payload(s, d) for d in rows]}


@app.post("/api/delegations/{did}/revoke")
def revoke_delegation(did: str, ctx=Depends(auth), s=Depends(db)):
    tenant_id = ctx.get("tenant_id", TENANT)
    d = s.query(Delegation).filter(Delegation.id == did, Delegation.tenant_id == tenant_id).first()
    if not d:
        raise HTTPException(404, "Not found")
    if d.from_user != ctx["sub"]:
        raise HTTPException(403, "Only the grantor can revoke")
    d.status = "revoked"
    s.commit()
    u = s.query(User).get(ctx["sub"])
    p = s.query(Person).get(u.person_id)
    write_audit(s, u.id, p.name if p else u.username, ctx["office_n"],
                "delegation.revoke", f"deleg:{d.id}", "active", "revoked",
                "Revoked — stops immediately", tenant_id=tenant_id)
    return _deleg_payload(s, d)


def _deleg_payload(s, d):
    return _delegation_payload(s, d)


# --------------------------------------------------------------------------- #
#  Authority check (Document §7 step 8) — live "may I?" probe for the UI       #
# --------------------------------------------------------------------------- #
class DelegationAttachmentIn(BaseModel):
    name: str = ""
    mime_type: str = ""
    size: int | None = None
    data_b64: str = ""


class ChairmanDelegationIn(BaseModel):
    subject: str
    policy_type_key: str
    new_policy_type: str = ""
    description: str = ""
    to_user_id: str
    delegation_scope_key: str
    access_key: str
    start: str
    end: str
    delegated_to_type: str = ""
    limit: float | None = None
    review_frequency_key: str = ""
    notes: str = ""
    attachment: DelegationAttachmentIn | None = None


def _chairman_delegation_form(s):
    policies = (s.query(DelegationPolicy)
                .filter(DelegationPolicy.active == True)
                .order_by(DelegationPolicy.sort_order, DelegationPolicy.subject).all())
    scope_options = _delegation_options(s, "delegation_scope")
    access_options = _delegation_options(s, "delegation_access")
    review_options = _delegation_options(s, "review_frequency")
    policy_type_options = _delegation_options(s, "policy_type")
    return {
        "policy_templates": [{
            "key": row.policy_key,
            "policy_type": row.policy_type,
            "subject": row.subject,
            "authority": row.authority,
            "action": row.action,
            "resource_scope": row.resource_scope,
            "default_limit": row.default_limit,
            "delegated_to_type_default": row.delegated_to_type_default,
            "icon": row.icon,
        } for row in policies],
        "policy_types": [_delegation_option_payload(row) for row in policy_type_options] + [
            {"key": "__new__", "label": "Add new policy type", "description": "Create a new policy type for this delegation"},
        ],
        "delegation_scopes": [_delegation_option_payload(row) for row in scope_options],
        "access_levels": [_delegation_option_payload(row) for row in access_options],
        "review_frequencies": [_delegation_option_payload(row) for row in review_options],
        "recipients": _delegation_recipient_options(s),
        "subject_suggestions": [{
            "subject": row.subject,
            "policy_type": row.policy_type,
            "policy_type_key": slug(row.policy_type or ""),
            "access_key": row.authority,
            "scope_key": (_delegation_option_by_description(s, "delegation_scope", row.resource_scope).option_key
                          if _delegation_option_by_description(s, "delegation_scope", row.resource_scope) else ""),
            "default_limit": row.default_limit,
            "description": "",
            "delegated_to_type_default": row.delegated_to_type_default,
        } for row in policies],
        "defaults": {
            "start": datetime.utcnow().date().isoformat(),
            "end": (datetime.utcnow().date() + timedelta(days=120)).isoformat(),
            "review_frequency_key": "none",
        },
    }


def _delegation_overlaps_range(row: dict, start: str = "", end: str = ""):
    if not start and not end:
        return True
    row_start = datetime.fromisoformat(row["start"]).date() if row.get("start") else None
    row_end = datetime.fromisoformat(row["end"]).date() if row.get("end") else None
    query_start = datetime.fromisoformat(start).date() if start else row_start
    query_end = datetime.fromisoformat(end).date() if end else row_end
    if row_start is None or row_end is None or query_start is None or query_end is None:
        return True
    return row_start <= query_end and row_end >= query_start


@app.get("/api/delegations/chairman")
def chairman_delegations(
    tab: str = "all",
    policy_type: str = "all",
    delegated_to: str = "all",
    status: str = "all",
    start: str = "",
    end: str = "",
    q: str = "",
    page: int = 1,
    page_size: int = 5,
    ctx=Depends(auth),
    s=Depends(db),
):
    if ctx["office_n"] != 1:
        raise HTTPException(403, "This delegation workspace is available only in the chairman login")

    page = max(1, page)
    page_size = min(20, max(5, page_size))

    rows = (s.query(Delegation)
            .filter(Delegation.from_user == ctx["sub"])
            .order_by(desc(Delegation.created_at)).all())
    mapped = [_delegation_payload(s, row) for row in rows]

    tabs = {
        "all": mapped,
        "active": [row for row in mapped if row["status_meta"]["key"] == "active"],
        "expiring": [row for row in mapped if row["status_meta"]["key"] == "expiring_soon"],
        "inactive": [row for row in mapped if row["status_meta"]["key"] in ("expired", "revoked")],
    }
    selected_tab = tab if tab in tabs else "all"
    scoped = tabs[selected_tab]

    query = (q or "").strip().lower()
    filtered = []
    for row in scoped:
        if policy_type != "all" and row["policy_type"] != policy_type:
            continue
        if delegated_to != "all" and row["to_user_id"] != delegated_to:
            continue
        if status != "all" and row["status_meta"]["key"] != status:
            continue
        if not _delegation_overlaps_range(row, start, end):
            continue
        haystack = " ".join([
            row["policy_type"], row["subject"], row["reference_code"], row["to_name"],
            row["to_role"], row["to_office"], row["authority_label"], row["reason"],
            row.get("description", ""), row.get("notes", ""), row.get("resource_scope_label", ""),
        ]).lower()
        if query and query not in haystack:
            continue
        filtered.append(row)

    total = len(filtered)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    start_index = (page - 1) * page_size
    page_rows = filtered[start_index:start_index + page_size]

    form = _chairman_delegation_form(s)
    recipient_map = {item["id"]: item for item in form["recipients"]}
    policy_pairs = {row["policy_type"] for row in mapped if row["policy_type"]}
    policy_pairs.update(item["label"] for item in form["policy_types"] if item["key"] != "__new__")
    status_map = {}
    for row in mapped:
        status_map[row["status_meta"]["key"]] = row["status_meta"]["label"]

    return {
        "title": "Delegation",
        "subtitle": "Create policies and delegate authority to specific offices or staff. Delegated authority is time-bound, scoped, revocable and auditable.",
        "summary": {
            "total": len(mapped),
            "active": len(tabs["active"]),
            "expiring": len(tabs["expiring"]),
            "inactive": len(tabs["inactive"]),
        },
        "tabs": [
            {"key": "all", "label": "All Delegations", "count": len(tabs["all"])},
            {"key": "active", "label": "Active", "count": len(tabs["active"])},
            {"key": "expiring", "label": "Expiring Soon", "count": len(tabs["expiring"])},
            {"key": "inactive", "label": "Expired / Revoked", "count": len(tabs["inactive"])},
        ],
        "filters": {
            "policy_types": [{"key": "all", "label": "All"}] + [
                {"key": entry, "label": entry} for entry in sorted(policy_pairs)
            ],
            "delegated_to": [{"key": "all", "label": "All"}] + [
                {"key": key, "label": value["label"]} for key, value in recipient_map.items()
            ],
            "statuses": [{"key": "all", "label": "All"}] + [
                {"key": key, "label": label} for key, label in status_map.items()
            ],
        },
        "form": form,
        "delegations": page_rows,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "visible_pages": _visible_page_numbers(page, total_pages),
            "showing_from": (start_index + 1) if total else 0,
            "showing_to": min(total, start_index + len(page_rows)),
        },
        "selected": {
            "tab": selected_tab,
            "policy_type": policy_type,
            "delegated_to": delegated_to,
            "status": status,
            "start": start,
            "end": end,
            "query": q,
        },
    }


@app.post("/api/delegations/chairman")
def create_chairman_delegation(body: ChairmanDelegationIn, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] != 1:
        raise HTTPException(403, "This delegation form is available only in the chairman login")

    subject = (body.subject or "").strip()
    if not subject:
        raise HTTPException(400, "Enter a policy or delegation subject")

    policy_type_row = _resolve_delegation_policy_type(s, body.policy_type_key, body.new_policy_type)
    if not policy_type_row:
        raise HTTPException(400, "Choose or create a policy type")

    scope_row = (s.query(DelegationOption)
                 .filter(DelegationOption.group_key == "delegation_scope",
                         DelegationOption.option_key == body.delegation_scope_key,
                         DelegationOption.active == True).first())
    if not scope_row:
        raise HTTPException(404, "Delegation scope not found")

    access_row = (s.query(DelegationOption)
                  .filter(DelegationOption.group_key == "delegation_access",
                          DelegationOption.option_key == body.access_key,
                          DelegationOption.active == True).first())
    if not access_row:
        raise HTTPException(404, "Delegated access not found")

    review_row = None
    if body.review_frequency_key and body.review_frequency_key != "none":
        review_row = (s.query(DelegationOption)
                      .filter(DelegationOption.group_key == "review_frequency",
                              DelegationOption.option_key == body.review_frequency_key,
                              DelegationOption.active == True).first())
        if not review_row:
            raise HTTPException(404, "Review frequency not found")

    target = s.query(User).get(body.to_user_id)
    if not target:
        raise HTTPException(404, "Recipient not found")
    if target.id == ctx["sub"]:
        raise HTTPException(400, "The chairman cannot delegate authority to the same login")

    try:
        start_at = datetime.fromisoformat(body.start)
        end_at = datetime.fromisoformat(f"{body.end}T23:59:59")
    except Exception:
        raise HTTPException(400, "Enter a valid delegation date range")
    if end_at < start_at:
        raise HTTPException(400, "Delegation end date must be after the start date")

    attachment = body.attachment or DelegationAttachmentIn()
    attachment_name = (attachment.name or "").strip()
    attachment_mime = (attachment.mime_type or "").strip()
    attachment_data = (attachment.data_b64 or "").strip()
    attachment_size = attachment.size
    if attachment_name:
        if not attachment_name.lower().endswith((".pdf", ".doc", ".docx")):
            raise HTTPException(400, "Only PDF, DOC or DOCX attachments are supported")
        if attachment_size and attachment_size > 10 * 1024 * 1024:
            raise HTTPException(400, "Attachments must be 10MB or smaller")
        if not attachment_data:
            raise HTTPException(400, "The attachment payload is incomplete")

    u = s.query(User).get(ctx["sub"])
    p = s.query(Person).get(u.person_id)
    delegated_to_type = (body.delegated_to_type or ("Office" if target.office_n <= 10 else "Individual")).strip() or "Individual"
    description = (body.description or "").strip()
    notes = (body.notes or "").strip()
    reason = notes or description or f"{subject} delegated to {target.username}"
    normalized_limit = body.limit if body.limit is not None else None

    policy = (s.query(DelegationPolicy)
              .filter(func.lower(DelegationPolicy.policy_type) == policy_type_row.label.lower(),
                      func.lower(DelegationPolicy.subject) == subject.lower(),
                      DelegationPolicy.authority == access_row.option_key,
                      DelegationPolicy.resource_scope == (scope_row.description or "*"),
                      DelegationPolicy.active == True)
              .first())
    if not policy:
        policy = DelegationPolicy(
            id=uid(),
            tenant_id=TENANT,
            policy_key=_delegation_policy_key(s, policy_type_row.label, subject),
            policy_type=policy_type_row.label,
            subject=subject,
            authority=access_row.option_key,
            action=_delegation_action_for_access(access_row.option_key),
            resource_scope=scope_row.description or "*",
            default_limit=normalized_limit,
            delegated_to_type_default=delegated_to_type,
            icon=_delegation_icon_for_type(policy_type_row.label),
            sort_order=((s.query(func.max(DelegationPolicy.sort_order)).scalar() or 0) + 1),
            active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        s.add(policy)
        s.flush()

    d = Delegation(
        id=uid(), tenant_id=TENANT, from_user=u.id, to_user=target.id,
        authority=policy.authority or policy.action or "approve",
        scope_ref=ctx.get("scope_ref", "scope_global"),
        limit=normalized_limit if normalized_limit is not None else policy.default_limit,
        start=start_at, end=end_at, status="active", reason=reason,
    )
    s.add(d)
    s.flush()

    profile = DelegationProfile(
        id=f"profile_{d.id}",
        tenant_id=TENANT,
        delegation_id=d.id,
        policy_key=policy.policy_key,
        policy_type=policy.policy_type,
        subject=policy.subject,
        reference_code=_delegation_reference_code(s, policy.policy_type),
        delegated_to_type=delegated_to_type,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    s.add(profile)

    context_row = DelegationContext(
        id=f"context_{d.id}",
        tenant_id=TENANT,
        delegation_id=d.id,
        policy_description=description,
        scope_key=scope_row.option_key,
        scope_label=scope_row.label,
        access_key=access_row.option_key,
        access_label=access_row.label,
        review_frequency_key=review_row.option_key if review_row else "none",
        review_frequency_label=review_row.label if review_row else "None",
        notes=notes,
        attachment_name=attachment_name,
        attachment_mime_type=attachment_mime,
        attachment_size=attachment_size,
        attachment_data=attachment_data,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    s.add(context_row)
    s.commit()

    payload = _delegation_payload(s, d)
    write_audit(
        s, u.id, p.name if p else u.username, ctx["office_n"],
        "delegation.create", f"deleg:{d.id}", "", payload["status_meta"]["key"],
        f"Delegated {policy.subject} to {target.username} from {body.start} to {body.end}",
    )
    notify(
        s, target.id, "Authority delegated to you",
        f"{policy.subject} is now delegated to your login from {body.start} to {body.end}.",
        "action",
    )
    return {"delegation": payload}


class CheckIn(BaseModel):
    action: str
    resource: str = "*"
    amount: float | None = None

FRONT_OFFICE_REMOVED_RESOURCES = {"students", "calendar", "academic_calendar", "academic-calendar", "workflows", "delegation", "audit", "matrices", "directory"}


@app.post("/api/authz/check")
def authz_check(body: CheckIn, ctx=Depends(auth), s=Depends(db)):
    if ctx["office_n"] == 35 and body.resource in FRONT_OFFICE_REMOVED_RESOURCES:
        return {"rbac_authority": NOT_ALLOWED, "outcome": DENY,
                "reason": "This resource is not available to Front Office", "authority": NOT_ALLOWED,
                "escalate_to": None}
    o = office(ctx["office_n"])
    rbac = rbac_for(ctx["office_n"], o["level"], body.action if body.action in VERBS else "view")
    dec = authorize(ctx=ctx, action=body.action, resource=body.resource,
                    rbac_authority=rbac, amount=body.amount,
                    active_delegation=active_delegations_for(s, ctx["sub"]),
                    target_scope_level=ctx.get("scope_level", "individual"))
    d = dec.as_dict()
    return {"rbac_authority": rbac, **d}


@app.get("/api/authz/my-permissions")
def my_permissions(ctx=Depends(auth), s=Depends(db)):
    o = office(ctx["office_n"])
    granted = [{"verb": v, "authority": rbac_for(ctx["office_n"], o["level"], v)}
               for v in VERBS
               if rbac_for(ctx["office_n"], o["level"], v) != NOT_ALLOWED]
    scope_limits = APPROVAL_LIMITS.get(ctx["scope_level"], {})
    lim = max(scope_limits.values()) if scope_limits else None
    return {"office": o["name"], "level": o["level"],
            "scope_level": ctx["scope_level"], "tenant_id": ctx.get("tenant_id"),
            "scope_ref": ctx.get("scope_ref"),
            "approval_limit": lim,
            "all_verbs": list(VERBS),
            "permissions": granted}


# --------------------------------------------------------------------------- #
#  Notifications                                                               #
# --------------------------------------------------------------------------- #
@app.get("/api/notifications")
def get_notifications(ctx=Depends(auth), s=Depends(db)):
    tenant_id = ctx.get("tenant_id", TENANT)
    rows = (s.query(Notification).filter(Notification.user_id == ctx["sub"], Notification.tenant_id == tenant_id)
            .order_by(desc(Notification.created_at)).limit(50).all())
    return {"notifications": [{"id": n.id, "severity": n.severity, "title": n.title,
                               "body": n.body, "read": n.read,
                               "at": n.created_at.isoformat()} for n in rows],
            "unread": s.query(Notification).filter(Notification.user_id == ctx["sub"],
                                                   Notification.tenant_id == tenant_id,
                                                   Notification.read == False).count()}


@app.post("/api/notifications/{nid}/read")
def read_notification(nid: str, ctx=Depends(auth), s=Depends(db)):
    tenant_id = ctx.get("tenant_id", TENANT)
    n = s.query(Notification).filter(Notification.id == nid, Notification.tenant_id == tenant_id).first()
    if n and n.user_id == ctx["sub"]:
        n.read = True
        s.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- #
#  Audit (Document §2, §12) — with hash-chain verifier (Gap #7)               #
# --------------------------------------------------------------------------- #
@app.get("/api/audit")
def get_audit(limit: int = 60, ctx=Depends(auth), s=Depends(db)):
    tenant_id = ctx.get("tenant_id", TENANT)
    if ctx.get("office_n") == 3:
        ref = (ctx.get("scope_ref") or "").strip()
        campus = (s.query(OrgScope).filter(OrgScope.tenant_id == tenant_id,
                  OrgScope.level == "campus", or_(OrgScope.id == ref, OrgScope.name == ref)).limit(2).all())
        if len(campus) != 1:
            raise HTTPException(403, "A canonical campus scope is required")
        rows = (s.query(AuditLog).filter(AuditLog.tenant_id == tenant_id,
                AuditLog.campus_scope_id == campus[0].id).order_by(desc(AuditLog.id)).limit(limit).all())
    else:
        rows = s.query(AuditLog).filter(AuditLog.tenant_id == tenant_id).order_by(desc(AuditLog.id)).limit(limit).all()
    return {"entries": [{"id": r.id, "actor": r.actor_name or r.actor, "office_n": r.office_n,
                         "action": r.action, "entity": r.entity, "new_state": r.new_state,
                         "outcome": r.new_state, "reason": r.reason, "auth_level": r.auth_level,
                         "campus_scope_id": r.campus_scope_id,
                         "hash": r.hash, "prev_hash": r.prev_hash,
                         "at": r.created_at.isoformat()} for r in rows], "data_status": "available"}


@app.get("/api/audit/verify")
def verify_audit(ctx=Depends(auth), s=Depends(db)):
    tenant_id = ctx.get("tenant_id", TENANT)
    rows = s.query(AuditLog).filter(AuditLog.tenant_id == tenant_id).order_by(AuditLog.id).all()
    prev = "0" * 64
    broken = None
    for r in rows:
        rec = {"actor": r.actor, "action": r.action, "entity": r.entity, "new_state": r.new_state}
        expect = audit_hash(prev, rec)
        if r.prev_hash != prev or r.hash != expect:
            broken = r.id
            break
        prev = r.hash
    result = {"chain_length": len(rows), "count": len(rows),
              "intact": broken is None, "broken_at": broken}
    if ctx.get("office_n") == 3:
        ref = (ctx.get("scope_ref") or "").strip()
        campus = (s.query(OrgScope).filter(OrgScope.tenant_id == tenant_id,
                  OrgScope.level == "campus", or_(OrgScope.id == ref, OrgScope.name == ref)).limit(2).all())
        if len(campus) != 1:
            raise HTTPException(403, "A canonical campus scope is required")
        result.update({"scope_count": sum(r.campus_scope_id == campus[0].id for r in rows),
                       "campus_scope_id": campus[0].id, "data_status": "available"})
    return result


# --------------------------------------------------------------------------- #
#  Dashboard aggregate                                                         #
# --------------------------------------------------------------------------- #
@app.get("/api/dashboard")
def dashboard(ctx=Depends(auth), s=Depends(db)):
    o = office(ctx["office_n"])
    mine = s.query(WorkflowInstance).filter(WorkflowInstance.initiator_id == ctx["sub"]).count()
    inbox = s.query(WorkflowInstance).filter(
        WorkflowInstance.office_n == ctx["office_n"],
        WorkflowInstance.state.in_(["submitted", "under_review", "reviewed", "escalated"])).count()
    pending = s.query(WorkflowInstance).filter(
        WorkflowInstance.state.in_(["submitted", "under_review", "reviewed"])).count()
    approved = s.query(WorkflowInstance).filter(WorkflowInstance.state == "approved").count()
    escalated = s.query(WorkflowInstance).filter(WorkflowInstance.state == "escalated").count()
    unread = s.query(Notification).filter(Notification.user_id == ctx["sub"],
                                          Notification.read == False).count()
    # processes this office owns
    owned = [p for p in APPROVAL_MATRIX if p["office_n"] == ctx["office_n"]]
    return {
        "office": o["name"], "level": o["level"],
        "kpis": {"my_requests": mine, "inbox": inbox, "pending_all": pending,
                 "approved": approved, "escalated": escalated, "unread": unread},
        "owned_processes": owned,
        "workflows_by_state": _wf_state_counts(s),
    }


def _wf_state_counts(s):
    rows = s.query(WorkflowInstance.state, func.count(WorkflowInstance.id)).group_by(
        WorkflowInstance.state).all()
    return {state: cnt for state, cnt in rows}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ICMS", "time": datetime.utcnow().isoformat()}
