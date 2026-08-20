# -*- coding: utf-8 -*-
"""
Shared runtime helpers used by both the authority API (main.py) and the domain
API (domain_api.py): DB session dependency, auth dependency, id generation,
hash-chained audit writer, notifications, and delegation lookup.

Kept in one place so both routers behave identically and the audit chain stays
single-writer-consistent.
"""
import uuid
<<<<<<< HEAD
from datetime import datetime, timezone
=======
>>>>>>> 22ee34d (updated code to branch)
from fastapi import Header, HTTPException
from sqlalchemy import desc

from database import SessionLocal, TENANT
<<<<<<< HEAD
from models import AuditLog, Notification, Delegation, DelegationPolicy, DelegationProfile
=======
from models import AuditLog, Notification, Delegation
>>>>>>> 22ee34d (updated code to branch)
from authority import decode_token, audit_hash


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


<<<<<<< HEAD
def _delegation_active_window(d):
    now = datetime.now(timezone.utc)
    start = d.start if getattr(d.start, "tzinfo", None) else d.start.replace(tzinfo=timezone.utc)
    end = d.end if getattr(d.end, "tzinfo", None) else d.end.replace(tzinfo=timezone.utc)
    return d.status == "active" and start <= now <= end


def _delegation_payload(s, d):
    profile = s.query(DelegationProfile).filter(DelegationProfile.delegation_id == d.id).first()
    policy = None
    if profile and profile.policy_key:
        policy = s.query(DelegationPolicy).filter(DelegationPolicy.policy_key == profile.policy_key).first()
    return {
        "id": d.id,
        "status": d.status,
        "authority": d.authority,
        "action": policy.action if policy else d.authority,
        "resource_scope": policy.resource_scope if policy else "*",
        "policy_key": profile.policy_key if profile else "",
        "policy_type": profile.policy_type if profile else "",
        "subject": profile.subject if profile else "",
        "reference_code": profile.reference_code if profile else "",
        "delegated_to_type": profile.delegated_to_type if profile else "Individual",
        "limit": d.limit,
        "start": d.start.isoformat(),
        "end": d.end.isoformat(),
        "reason": d.reason,
        "active": _delegation_active_window(d),
    }


def active_delegations_for(s, user_id):
    rows = (s.query(Delegation)
            .filter(Delegation.to_user == user_id, Delegation.status == "active")
            .order_by(desc(Delegation.created_at)).all())
    return [payload for payload in (_delegation_payload(s, row) for row in rows) if payload["active"]]


def active_delegation_for(s, user_id):
    active = active_delegations_for(s, user_id)
    return active[0] if active else None
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
