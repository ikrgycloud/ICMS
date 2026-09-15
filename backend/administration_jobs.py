"""Durable SLA/outbox processors used by the existing worker process."""
import json
import os
from datetime import datetime, timedelta
import administration_models as A
from core import notify, write_audit, uid
from administration_state import require_transition
from models import User, Person
from sqlalchemy import and_, or_

def emit_outbox(s, tenant_id, event_type, aggregate_id, payload, key):
    if s.query(A.AdministrativeOutboxEvent).filter_by(tenant_id=tenant_id,idempotency_key=key).first(): return False
    s.add(A.AdministrativeOutboxEvent(id=uid(),tenant_id=tenant_id,event_type=event_type,aggregate_type="administrative_requirement",aggregate_id=aggregate_id,payload=json.dumps(payload),idempotency_key=key))
    return True

def pause_sla(s, requirement_id, tenant_id, now=None):
    """Pause only the selected SLA snapshot; repeated holds are a no-op."""
    sla=s.query(A.AdministrativeSla).filter_by(requirement_id=requirement_id,tenant_id=tenant_id).first()
    if not sla or not sla.pause_allowed or sla.completed_at or sla.paused_at: return False
    sla.paused_at=now or datetime.utcnow(); sla.status="PAUSED"; sla.pause_count+=1
    return True

def resume_sla(s, requirement_id, tenant_id, now=None):
    """Move the deadline by paused wall time, preserving the original commitment."""
    sla=s.query(A.AdministrativeSla).filter_by(requirement_id=requirement_id,tenant_id=tenant_id).first()
    if not sla or not sla.paused_at or sla.completed_at: return False
    now=now or datetime.utcnow(); elapsed=max(0, int((now-sla.paused_at).total_seconds()))
    sla.paused_seconds+=elapsed; sla.due_at+=timedelta(seconds=elapsed); sla.resumed_at=now; sla.paused_at=None
    sla.status="BREACHED" if sla.breached_at else "ACTIVE"
    return True

def complete_sla(s, requirement_id, tenant_id, now=None):
    sla=s.query(A.AdministrativeSla).filter_by(requirement_id=requirement_id,tenant_id=tenant_id).first()
    if not sla or sla.completed_at: return False
    now=now or datetime.utcnow()
    if sla.paused_at:
        sla.paused_seconds+=max(0,int((now-sla.paused_at).total_seconds())); sla.paused_at=None
    sla.completed_at=now; sla.status="COMPLETED"
    return True

def process_slas(s, now=None):
    now=now or datetime.utcnow(); changed=0
    rows=s.query(A.AdministrativeSla).filter(A.AdministrativeSla.status.in_(("ACTIVE","APPROACHING")),A.AdministrativeSla.completed_at==None).all()
    for sla in rows:
        req=s.get(A.AdministrativeRequirement,sla.requirement_id)
        if not req or req.tenant_id!=sla.tenant_id or sla.paused_at: continue
        # The threshold is a routing-time commitment, never a live policy lookup.
        duration=max(1,((sla.original_due_at or sla.due_at)-sla.started_at).total_seconds())
        elapsed=(now-sla.started_at).total_seconds()-sla.paused_seconds
        threshold=sla.approaching_percent/100
        recipient=req.assigned_user_id or (f"user_{req.responsible_office_n}" if req.responsible_office_n else "user_7")
        if now >= sla.due_at and not sla.breached_at:
            previous=req.state
            # A terminal/review state must never be overwritten by a late
            # worker tick.  Record an authoritative transition for the rest.
            if previous in {"ROUTED","IN_EXECUTION","IN_PROGRESS","ON_HOLD"}:
                require_transition(previous,"OVERDUE")
                req.state="OVERDUE";req.version+=1;req.updated_at=now
                s.add(A.AdministrativeTransition(id=uid(),tenant_id=req.tenant_id,requirement_id=req.id,from_state=previous,to_state="OVERDUE",actor_id="system",actor_office_n=0,reason="SLA deadline breached",version=req.version))
            sla.breached_at=now;sla.status="BREACHED"
            emit_outbox(s,sla.tenant_id,"SLABreached",req.id,{"recipient":recipient,"title":f"SLA breached: {req.reference_code}","body":req.title,"severity":"critical"},f"sla-breached:{sla.id}")
            write_audit(s,"system","SLA Worker",0,"administration.sla.breached",f"administrative_requirement:{req.id}","ACTIVE","OVERDUE","SLA deadline breached",commit=False);changed+=1
        elif elapsed >= duration*threshold and not sla.approaching_notified_at:
            sla.approaching_notified_at=now;sla.status="APPROACHING"
            emit_outbox(s,sla.tenant_id,"SLAApproaching",req.id,{"recipient":recipient,"title":f"SLA approaching: {req.reference_code}","body":req.title,"severity":"action"},f"sla-approaching:{sla.id}");changed+=1
    if changed:s.commit()
    return changed

def claim_outbox_events(s, now=None, limit=50, worker_id=None, lease_seconds=300):
    """Atomically lease due events, including abandoned claims.

    `skip_locked` maps to row-level locks on PostgreSQL and is harmless on
    SQLite test databases.  The state change is committed before delivery so
    another worker cannot concurrently send the same notification.
    """
    now=now or datetime.utcnow(); worker_id=worker_id or os.getenv("HOSTNAME", "administration-worker")
    due = or_(
        and_(A.AdministrativeOutboxEvent.status=="PENDING", A.AdministrativeOutboxEvent.available_at<=now),
        and_(A.AdministrativeOutboxEvent.status=="PROCESSING", A.AdministrativeOutboxEvent.lease_expires_at < now),
    )
    events=(s.query(A.AdministrativeOutboxEvent).filter(due)
        .order_by(A.AdministrativeOutboxEvent.created_at).with_for_update(skip_locked=True).limit(limit).all())
    lease_until=now+timedelta(seconds=lease_seconds)
    ids=[]
    for event in events:
        event.status="PROCESSING"; event.locked_by=worker_id; event.locked_at=now; event.lease_expires_at=lease_until
        ids.append(event.id)
    if ids: s.commit()
    return ids

def process_outbox(s, now=None, limit=50, worker_id=None):
    now=now or datetime.utcnow(); processed=0
    ids=claim_outbox_events(s,now,limit,worker_id)
    for event_id in ids:
        event=s.get(A.AdministrativeOutboxEvent,event_id)
        if not event or event.status!="PROCESSING": continue
        try:
            data=json.loads(event.payload); notify(s,data["recipient"],data["title"],data.get("body",""),data.get("severity","info"))
            event.status="PROCESSED";event.processed_at=now;event.locked_by=None;event.locked_at=None;event.lease_expires_at=None;processed+=1
        except Exception as exc:
            event.attempt_count+=1;event.last_error=str(exc);event.available_at=now+timedelta(seconds=min(3600,2**event.attempt_count));event.status="DEAD" if event.attempt_count>=5 else "PENDING";event.locked_by=None;event.locked_at=None;event.lease_expires_at=None
    s.commit();return processed
