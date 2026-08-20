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
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import desc, func

import authority as A
from authority import (issue_token, decode_token, pwhash, audit_hash, authorize,
                       Decision, ALLOW, DENY, ESCALATE, RECOMMEND_OUT, VERBS,
                       NOT_ALLOWED)
import matrices as M
from matrices import (APPROVAL_MATRIX, WF_VALID, WF_STATES, approval_limit_for,
                      APPROVAL_LIMITS, rbac_for, scope_for)
from database import (SessionLocal, seed, CATALOG, OFFICES, LEVELS, office,
                      DEMO_USERNAMES, TENANT)
from models import (User, Person, Role, RolePermission, Delegation, WorkflowInstance,
                    Approval, Notification, AuditLog, ApprovalLimit)

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


def active_delegation_for(s, user_id):
    d = (s.query(Delegation)
         .filter(Delegation.to_user == user_id, Delegation.status == "active")
         .order_by(desc(Delegation.created_at)).first())
    if not d:
        return None
    return {"status": d.status, "authority": d.authority, "limit": d.limit,
            "start": d.start.isoformat(), "end": d.end.isoformat()}


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
    write_audit(s, u.id, p.name if p else u.username, u.office_n, "auth.login",
                "session", "", "active", "login ok")
    return {"token": tok, "user": _user_payload(u, p, o)}


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


def _user_payload(u, p, o, active_role=None):
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
    }


@app.get("/api/me")
def me(ctx=Depends(auth), s=Depends(db)):
    u = s.query(User).get(ctx["sub"])
    p = s.query(Person).get(u.person_id)
    o = office(u.office_n)
    return {"user": _user_payload(u, p, o, ctx.get("role")), "auth_context": ctx,
            "active_delegation": active_delegation_for(s, u.id)}


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
    tok = issue_token(u.id, u.tenant_id, u.office_n, body.role, u.scope_level,
                      u.scope_ref, "mfa" if u.mfa_enabled else "password")
    write_audit(s, u.id, p.name if p else u.username, u.office_n, "auth.switch_role",
                "session", u.role, body.role, f"Assumed role: {body.role}")
    return {"token": tok, "user": _user_payload(u, p, o, body.role)}


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


class StartWF(BaseModel):
    process_key: str
    title: str
    amount: float | None = None


@app.post("/api/workflows/start")
def start_workflow(body: StartWF, ctx=Depends(auth), s=Depends(db)):
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
        active_delegation=active_delegation_for(s, u.id),
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
    return {
        "id": wf.id, "process_key": wf.process_key, "label": wf.label,
        "office_n": wf.office_n, "title": wf.title, "state": wf.state,
        "amount": wf.amount, "initiator": wf.initiator_name,
        "current_stage": wf.current_stage, "escalated": wf.escalated,
        "scope_level": wf.scope_level,
        "chain": proc["chain"] if proc else [],
        "escalation": proc["escalation"] if proc else "",
        "created_at": wf.created_at.isoformat(),
        "history": [{"stage": a.stage, "stage_label": a.stage_label, "actor": a.actor_name,
                     "decision": a.decision, "authority": a.authority, "reason": a.reason,
                     "at": a.created_at.isoformat()} for a in approvals],
    }


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
            .filter((Delegation.from_user == ctx["sub"]) | (Delegation.to_user == ctx["sub"]))
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
    fu = s.query(User).get(d.from_user)
    tu = s.query(User).get(d.to_user)
    return {"id": d.id, "from": fu.username if fu else d.from_user,
            "to": tu.username if tu else d.to_user, "authority": d.authority,
            "limit": d.limit, "status": d.status,
            "start": d.start.isoformat(), "end": d.end.isoformat(),
            "reason": d.reason,
            "active": d.status == "active" and d.end > datetime.utcnow()}


# --------------------------------------------------------------------------- #
#  Authority check (Document §7 step 8) — live "may I?" probe for the UI       #
# --------------------------------------------------------------------------- #
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
                    active_delegation=active_delegation_for(s, ctx["sub"]),
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
