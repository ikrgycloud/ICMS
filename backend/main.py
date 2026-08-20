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
<<<<<<< HEAD
from datetime import datetime, timedelta, timezone
=======
from datetime import datetime, timedelta
>>>>>>> 22ee34d (updated code to branch)

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
<<<<<<< HEAD
from sqlalchemy import desc, func, or_
=======
from sqlalchemy import desc, func
>>>>>>> 22ee34d (updated code to branch)

import authority as A
from authority import (issue_token, decode_token, pwhash, audit_hash, authorize,
                       Decision, ALLOW, DENY, ESCALATE, RECOMMEND_OUT, VERBS,
                       NOT_ALLOWED)
import matrices as M
from matrices import (APPROVAL_MATRIX, WF_VALID, WF_STATES, approval_limit_for,
                      APPROVAL_LIMITS, rbac_for, scope_for)
from database import (SessionLocal, seed, CATALOG, OFFICES, LEVELS, office,
<<<<<<< HEAD
                      DEMO_USERNAMES, TENANT, slug)
from models import (User, Person, Role, RolePermission, Delegation, WorkflowInstance,
                    WorkflowProfile, Approval, Notification, AuditLog, ApprovalLimit,
                    DelegationPolicy, DelegationProfile, DelegationOption,
                    DelegationContext)
=======
                      DEMO_USERNAMES, TENANT)
from models import (User, Person, Role, RolePermission, Delegation, WorkflowInstance,
                    Approval, Notification, AuditLog, ApprovalLimit)
>>>>>>> 22ee34d (updated code to branch)

from domain_api import router as domain_router
from portal_api import router as portal_router
from integrations_api import router as integrations_router
from domain_seed import seed_domain

app = FastAPI(title="ICMS — Integrated College/University Management System",
              version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])
app.include_router(domain_router)
app.include_router(portal_router)
app.include_router(integrations_router)


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


def auth(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        return decode_token(authorization.split(" ", 1)[1])
    except Exception:
        raise HTTPException(401, "Invalid or expired token")


def uid() -> str:
    return uuid.uuid4().hex[:12]


# --------------------------------------------------------------------------- #
#  Audit (hash-chained, append-only)                                          #
# --------------------------------------------------------------------------- #
def write_audit(s, actor, actor_name, office_n, action, entity,
                prev_state="", new_state="", reason="", auth_level="mfa"):
    last = s.query(AuditLog).order_by(desc(AuditLog.id)).first()
    prev = last.hash if last else "0" * 64
    rec = {"actor": actor, "action": action, "entity": entity, "new_state": new_state}
    h = audit_hash(prev, rec)
    row = AuditLog(tenant_id=TENANT, actor=actor, actor_name=actor_name, office_n=office_n,
                   action=action, entity=entity, prev_state=prev_state, new_state=new_state,
                   reason=reason, auth_level=auth_level, prev_hash=prev, hash=h)
    s.add(row)
    s.commit()
    return row


def notify(s, user_id, title, body, severity="info"):
    s.add(Notification(id=uid(), tenant_id=TENANT, user_id=user_id, severity=severity,
                       title=title, body=body))
    s.commit()


def rbac_authority(s, office_n, level, verb) -> str:
    return rbac_for(office_n, level, verb)


<<<<<<< HEAD
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
=======
def active_delegation_for(s, user_id):
    d = (s.query(Delegation)
         .filter(Delegation.to_user == user_id, Delegation.status == "active")
         .order_by(desc(Delegation.created_at)).first())
    if not d:
        return None
    return {"status": d.status, "authority": d.authority, "limit": d.limit,
            "start": d.start.isoformat(), "end": d.end.isoformat()}
>>>>>>> 22ee34d (updated code to branch)


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
<<<<<<< HEAD
    active_delegations = active_delegations_for(s, u.id)
    write_audit(s, u.id, p.name if p else u.username, u.office_n, "auth.login",
                "session", "", "active", "login ok")
    return {
        "token": tok,
        "user": _user_payload(u, p, o, active_delegations=active_delegations),
        "active_delegation": active_delegations[0] if active_delegations else None,
        "active_delegations": active_delegations,
    }
=======
    write_audit(s, u.id, p.name if p else u.username, u.office_n, "auth.login",
                "session", "", "active", "login ok")
    return {"token": tok, "user": _user_payload(u, p, o)}
>>>>>>> 22ee34d (updated code to branch)


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


<<<<<<< HEAD
def _user_payload(u, p, o, active_role=None, active_delegations=None):
    active_delegations = active_delegations or []
=======
def _user_payload(u, p, o, active_role=None):
>>>>>>> 22ee34d (updated code to branch)
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
<<<<<<< HEAD
        "active_delegation_count": len(active_delegations),
        "active_delegation": active_delegations[0] if active_delegations else None,
        "active_delegations": active_delegations,
=======
>>>>>>> 22ee34d (updated code to branch)
    }


@app.get("/api/me")
def me(ctx=Depends(auth), s=Depends(db)):
    u = s.query(User).get(ctx["sub"])
    p = s.query(Person).get(u.person_id)
    o = office(u.office_n)
<<<<<<< HEAD
    active_delegations = active_delegations_for(s, u.id)
    return {
        "user": _user_payload(u, p, o, ctx.get("role"), active_delegations=active_delegations),
        "auth_context": ctx,
        "active_delegation": active_delegations[0] if active_delegations else None,
        "active_delegations": active_delegations,
    }
=======
    return {"user": _user_payload(u, p, o, ctx.get("role")), "auth_context": ctx,
            "active_delegation": active_delegation_for(s, u.id)}
>>>>>>> 22ee34d (updated code to branch)


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
<<<<<<< HEAD
    active_delegations = active_delegations_for(s, u.id)
=======
>>>>>>> 22ee34d (updated code to branch)
    tok = issue_token(u.id, u.tenant_id, u.office_n, body.role, u.scope_level,
                      u.scope_ref, "mfa" if u.mfa_enabled else "password")
    write_audit(s, u.id, p.name if p else u.username, u.office_n, "auth.switch_role",
                "session", u.role, body.role, f"Assumed role: {body.role}")
<<<<<<< HEAD
    return {
        "token": tok,
        "user": _user_payload(u, p, o, body.role, active_delegations=active_delegations),
        "active_delegation": active_delegations[0] if active_delegations else None,
        "active_delegations": active_delegations,
    }
=======
    return {"token": tok, "user": _user_payload(u, p, o, body.role)}
>>>>>>> 22ee34d (updated code to branch)


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
    return {"processes": APPROVAL_MATRIX}


<<<<<<< HEAD
PROCESS_CATEGORY_MAP = {
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
    "approved": {"label": "Approved", "tone": "approved"},
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
    proc = _workflow_process(process_key)
    if not proc:
        raise HTTPException(404, "Unknown process")
    clean_title = (title or "").strip()
    if not clean_title:
        raise HTTPException(400, "Describe the request")
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
        current_stage=1, scope_level=ctx.get("scope_level", "campus"))
    s.add(wf)
    s.commit()
    _ensure_workflow_profile(s, wf, semester_key=semester_key, semester_label=semester_label, notes=notes)
    write_audit(s, u.id, p.name if p else u.username, ctx["office_n"],
                f"workflow.start:{proc['key']}", f"wf:{wf.id}", "draft", "submitted",
                f"Initiated {proc['label']}")
    _notify_stage(s, wf, proc)
    return wf, proc


=======
>>>>>>> 22ee34d (updated code to branch)
class StartWF(BaseModel):
    process_key: str
    title: str
    amount: float | None = None


@app.post("/api/workflows/start")
def start_workflow(body: StartWF, ctx=Depends(auth), s=Depends(db)):
<<<<<<< HEAD
    wf, proc = _start_workflow_record(s, ctx, body.process_key, body.title, body.amount)
    return _wf_payload(s, wf, proc)
=======
>>>>>>> 22ee34d (updated code to branch)
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
<<<<<<< HEAD
    recipients = []
    owner = s.query(User).filter(User.office_n == proc["office_n"]).first()
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
=======
>>>>>>> 22ee34d (updated code to branch)
    # Notify the owning office head as a representative approver.
    owner = s.query(User).filter(User.office_n == proc["office_n"]).first()
    if owner:
        notify(s, owner.id, f"Action needed: {proc['label']}",
               f"{wf.title} — awaiting {label}", severity="action")


class DecideWF(BaseModel):
    workflow_id: str
    action: str          # approve / reject / review / escalate / execute
    reason: str = ""


@app.post("/api/workflows/decide")
def decide_workflow(body: DecideWF, ctx=Depends(auth), s=Depends(db)):
    wf = s.query(WorkflowInstance).get(body.workflow_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    proc = next((p for p in APPROVAL_MATRIX if p["key"] == wf.process_key), None)
    u = s.query(User).get(ctx["sub"])
    p = s.query(Person).get(u.person_id)
    o = office(ctx["office_n"])

    # Resolve RBAC authority for this action.
    verb = "approve" if body.action in ("approve", "execute") else body.action
    if body.action == "reject":
        verb = "reject"
    rbac = rbac_for(ctx["office_n"], o["level"], verb if verb in VERBS else "approve")

    # Approval limit for this process & the actor's scope.
    limit = approval_limit_for(ctx.get("scope_level", "campus"), wf.process_key) \
        if proc and proc.get("amount") else None

    # Run the authority gate (Document §7 steps 8-13).
    dec = authorize(
        ctx=ctx, action=body.action if body.action in VERBS else "approve",
        resource=f"workflow:{wf.process_key}",
        rbac_authority=rbac,
        workflow_state=wf.state,
        workflow_valid_states=WF_VALID.get(body.action),
        amount=wf.amount, approval_limit=limit,
        requester_id=wf.initiator_id,
<<<<<<< HEAD
        active_delegation=active_delegations_for(s, u.id),
=======
        active_delegation=active_delegation_for(s, u.id),
>>>>>>> 22ee34d (updated code to branch)
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
    if dec.outcome == ALLOW:
        if body.action == "reject":
            wf.state = "rejected"
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
    elif dec.outcome == ESCALATE:
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
    if proc:
        _notify_stage(s, wf, proc)

    return {"decision": dec.as_dict(), "workflow": _wf_payload(s, wf, proc)}


def _wf_payload(s, wf, proc):
    approvals = (s.query(Approval).filter(Approval.workflow_id == wf.id)
                 .order_by(Approval.created_at).all())
<<<<<<< HEAD
    profile = s.query(WorkflowProfile).filter(WorkflowProfile.workflow_id == wf.id).first()
=======
>>>>>>> 22ee34d (updated code to branch)
    return {
        "id": wf.id, "process_key": wf.process_key, "label": wf.label,
        "office_n": wf.office_n, "title": wf.title, "state": wf.state,
        "amount": wf.amount, "initiator": wf.initiator_name,
        "current_stage": wf.current_stage, "escalated": wf.escalated,
        "scope_level": wf.scope_level,
        "chain": proc["chain"] if proc else [],
        "escalation": proc["escalation"] if proc else "",
        "created_at": wf.created_at.isoformat(),
<<<<<<< HEAD
        "profile": {
            "semester_key": profile.semester_key if profile else "",
            "semester_label": profile.semester_label if profile else "",
            "category": profile.category if profile else _approval_category(wf.process_key, wf.label),
            "reference_code": profile.reference_code if profile else _generate_reference_code(s, wf.process_key, wf.label, wf.created_at),
            "notes": profile.notes if profile else "",
        },
=======
>>>>>>> 22ee34d (updated code to branch)
        "history": [{"stage": a.stage, "stage_label": a.stage_label, "actor": a.actor_name,
                     "decision": a.decision, "authority": a.authority, "reason": a.reason,
                     "at": a.created_at.isoformat()} for a in approvals],
    }


<<<<<<< HEAD
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
    q = s.query(WorkflowInstance)
    pending_states = ["submitted", "under_review", "reviewed", "escalated"]
    if scope == "mine":
        q = q.filter(WorkflowInstance.initiator_id == ctx["sub"])
    elif scope == "inbox":
        own_rows = (q.filter(WorkflowInstance.office_n == ctx["office_n"],
                             WorkflowInstance.state.in_(pending_states))
                     .order_by(desc(WorkflowInstance.updated_at)).all())
        delegated = active_delegations_for(s, ctx["sub"])
        if not delegated:
            rows = own_rows[:100]
        else:
            candidate_rows = (s.query(WorkflowInstance)
                              .filter(WorkflowInstance.state.in_(pending_states))
                              .order_by(desc(WorkflowInstance.updated_at)).limit(220).all())
            seen = {row.id for row in own_rows}
            rows = list(own_rows)
            for wf in candidate_rows:
                if wf.id in seen:
                    continue
                if _delegation_matches_workflow(delegated, wf, ctx.get("scope_level", "individual")):
                    rows.append(wf)
                    seen.add(wf.id)
            rows = sorted(rows, key=lambda item: item.updated_at or item.created_at, reverse=True)[:100]
    else:
        rows = q.order_by(desc(WorkflowInstance.updated_at)).limit(100).all()
=======
@app.get("/api/workflows")
def list_workflows(scope: str = "all", ctx=Depends(auth), s=Depends(db)):
    q = s.query(WorkflowInstance)
    if scope == "mine":
        q = q.filter(WorkflowInstance.initiator_id == ctx["sub"])
    elif scope == "inbox":
        # Items owned by this office awaiting action.
        q = q.filter(WorkflowInstance.office_n == ctx["office_n"],
                     WorkflowInstance.state.in_(["submitted", "under_review", "reviewed", "escalated"]))
    rows = q.order_by(desc(WorkflowInstance.updated_at)).limit(100).all()
>>>>>>> 22ee34d (updated code to branch)
    out = []
    for wf in rows:
        proc = next((p for p in APPROVAL_MATRIX if p["key"] == wf.process_key), None)
        out.append(_wf_payload(s, wf, proc))
    return {"workflows": out}


@app.get("/api/workflows/{wid}")
def get_workflow(wid: str, ctx=Depends(auth), s=Depends(db)):
    wf = s.query(WorkflowInstance).get(wid)
    if not wf:
        raise HTTPException(404, "Not found")
    proc = next((p for p in APPROVAL_MATRIX if p["key"] == wf.process_key), None)
    return _wf_payload(s, wf, proc)


<<<<<<< HEAD
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


=======
>>>>>>> 22ee34d (updated code to branch)
# --------------------------------------------------------------------------- #
#  Delegation (Document §2, §12) — time-bound, scoped, revocable, audited      #
# --------------------------------------------------------------------------- #
class DelegateIn(BaseModel):
    to_username: str
    authority: str = "*"
    days: int = 7
    limit: float | None = None
    reason: str = ""


@app.post("/api/delegations")
def create_delegation(body: DelegateIn, ctx=Depends(auth), s=Depends(db)):
    o = office(ctx["office_n"])
    can = rbac_for(ctx["office_n"], o["level"], "delegate")
    if can in (A.NOT_ALLOWED,):
        raise HTTPException(403, "This office cannot delegate authority")
    target = s.query(User).filter(User.username == body.to_username).first()
    if not target:
        raise HTTPException(404, "Target user not found")
    u = s.query(User).get(ctx["sub"])
    p = s.query(Person).get(u.person_id)
    d = Delegation(id=uid(), tenant_id=TENANT, from_user=u.id, to_user=target.id,
                   authority=body.authority, scope_ref=ctx.get("scope_ref", "scope_global"),
                   limit=body.limit, start=datetime.utcnow(),
                   end=datetime.utcnow() + timedelta(days=body.days),
                   status="active", reason=body.reason)
    s.add(d)
    s.commit()
    write_audit(s, u.id, p.name if p else u.username, ctx["office_n"],
                "delegation.create", f"deleg:{d.id}", "", "active",
                f"Delegated {body.authority} to {body.to_username} for {body.days}d")
    notify(s, target.id, "Authority delegated to you",
           f"You received '{body.authority}' authority for {body.days} days", "action")
    return _deleg_payload(s, d)


@app.get("/api/delegations")
def list_delegations(ctx=Depends(auth), s=Depends(db)):
    rows = (s.query(Delegation)
<<<<<<< HEAD
            .filter(or_(Delegation.from_user == ctx["sub"], Delegation.to_user == ctx["sub"]))
=======
            .filter((Delegation.from_user == ctx["sub"]) | (Delegation.to_user == ctx["sub"]))
>>>>>>> 22ee34d (updated code to branch)
            .order_by(desc(Delegation.created_at)).all())
    return {"delegations": [_deleg_payload(s, d) for d in rows]}


@app.post("/api/delegations/{did}/revoke")
def revoke_delegation(did: str, ctx=Depends(auth), s=Depends(db)):
    d = s.query(Delegation).get(did)
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
                "Revoked — stops immediately")
    return _deleg_payload(s, d)


def _deleg_payload(s, d):
<<<<<<< HEAD
    return _delegation_payload(s, d)
=======
    fu = s.query(User).get(d.from_user)
    tu = s.query(User).get(d.to_user)
    return {"id": d.id, "from": fu.username if fu else d.from_user,
            "to": tu.username if tu else d.to_user, "authority": d.authority,
            "limit": d.limit, "status": d.status,
            "start": d.start.isoformat(), "end": d.end.isoformat(),
            "reason": d.reason,
            "active": d.status == "active" and d.end > datetime.utcnow()}
>>>>>>> 22ee34d (updated code to branch)


# --------------------------------------------------------------------------- #
#  Authority check (Document §7 step 8) — live "may I?" probe for the UI       #
# --------------------------------------------------------------------------- #
<<<<<<< HEAD
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


=======
>>>>>>> 22ee34d (updated code to branch)
class CheckIn(BaseModel):
    action: str
    resource: str = "*"
    amount: float | None = None


@app.post("/api/authz/check")
def authz_check(body: CheckIn, ctx=Depends(auth), s=Depends(db)):
    o = office(ctx["office_n"])
    rbac = rbac_for(ctx["office_n"], o["level"], body.action if body.action in VERBS else "view")
    dec = authorize(ctx=ctx, action=body.action, resource=body.resource,
                    rbac_authority=rbac, amount=body.amount,
<<<<<<< HEAD
                    active_delegation=active_delegations_for(s, ctx["sub"]),
=======
                    active_delegation=active_delegation_for(s, ctx["sub"]),
>>>>>>> 22ee34d (updated code to branch)
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
            "scope_level": ctx["scope_level"],
            "approval_limit": lim,
            "all_verbs": list(VERBS),
            "permissions": granted}


# --------------------------------------------------------------------------- #
#  Notifications                                                               #
# --------------------------------------------------------------------------- #
@app.get("/api/notifications")
def get_notifications(ctx=Depends(auth), s=Depends(db)):
    rows = (s.query(Notification).filter(Notification.user_id == ctx["sub"])
            .order_by(desc(Notification.created_at)).limit(50).all())
    return {"notifications": [{"id": n.id, "severity": n.severity, "title": n.title,
                               "body": n.body, "read": n.read,
                               "at": n.created_at.isoformat()} for n in rows],
            "unread": s.query(Notification).filter(Notification.user_id == ctx["sub"],
                                                   Notification.read == False).count()}


@app.post("/api/notifications/{nid}/read")
def read_notification(nid: str, ctx=Depends(auth), s=Depends(db)):
    n = s.query(Notification).get(nid)
    if n and n.user_id == ctx["sub"]:
        n.read = True
        s.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- #
#  Audit (Document §2, §12) — with hash-chain verifier (Gap #7)               #
# --------------------------------------------------------------------------- #
@app.get("/api/audit")
def get_audit(limit: int = 60, ctx=Depends(auth), s=Depends(db)):
    rows = s.query(AuditLog).order_by(desc(AuditLog.id)).limit(limit).all()
    return {"entries": [{"id": r.id, "actor": r.actor_name or r.actor, "office_n": r.office_n,
                         "action": r.action, "entity": r.entity, "new_state": r.new_state,
                         "outcome": r.new_state, "reason": r.reason, "auth_level": r.auth_level,
                         "hash": r.hash, "prev_hash": r.prev_hash,
                         "at": r.created_at.isoformat()} for r in rows]}


@app.get("/api/audit/verify")
def verify_audit(ctx=Depends(auth), s=Depends(db)):
    rows = s.query(AuditLog).order_by(AuditLog.id).all()
    prev = "0" * 64
    broken = None
    for r in rows:
        rec = {"actor": r.actor, "action": r.action, "entity": r.entity, "new_state": r.new_state}
        expect = audit_hash(prev, rec)
        if r.prev_hash != prev or r.hash != expect:
            broken = r.id
            break
        prev = r.hash
    return {"chain_length": len(rows), "count": len(rows),
            "intact": broken is None, "broken_at": broken}


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
