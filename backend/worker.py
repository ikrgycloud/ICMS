"""Standalone production worker for durable academic jobs.

The queue is database-backed so API and worker processes share retries, leases,
idempotency keys, and a dead-letter state without requiring an in-process thread.
"""
import json
import os
import time
import urllib.request
from datetime import datetime, timedelta
from sqlalchemy import text
from database import engine, SessionLocal
import domain_models as D
from administration_jobs import process_slas, process_outbox

POLL_SECONDS = int(os.getenv("ICMS_WORKER_POLL_SECONDS", "5"))
MAX_ATTEMPTS = int(os.getenv("ICMS_WORKER_MAX_ATTEMPTS", "5"))
WORKER_ID = os.getenv("HOSTNAME", "icms-worker")
MONITORING_WEBHOOK = os.getenv("ICMS_MONITORING_WEBHOOK", "")


def heartbeat(status, processed=0, failed=0, error=""):
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO icms_worker_heartbeats
            (worker_id,status,processed,failed,last_error,updated_at) VALUES
            (:id,:status,:processed,:failed,:error,:now)
            ON CONFLICT (worker_id) DO UPDATE SET
            status=EXCLUDED.status,
            processed=icms_worker_heartbeats.processed + EXCLUDED.processed,
            failed=icms_worker_heartbeats.failed + EXCLUDED.failed,
            last_error=EXCLUDED.last_error,
            updated_at=EXCLUDED.updated_at"""),
                     {"id": WORKER_ID, "status": status, "processed": processed,
                      "failed": failed, "error": error, "now": datetime.utcnow()})


def monitor(event, details):
    if not MONITORING_WEBHOOK:
        return
    try:
        request=urllib.request.Request(MONITORING_WEBHOOK, data=json.dumps({"event":event,"worker":WORKER_ID,"details":details}).encode(), headers={"Content-Type":"application/json"}, method="POST")
        urllib.request.urlopen(request, timeout=5).read()
    except Exception:
        pass


def ensure_queue():
    with engine.begin() as conn:
        conn.execute(text("""CREATE TABLE IF NOT EXISTS icms_jobs (
            id VARCHAR(64) PRIMARY KEY, queue VARCHAR(80) NOT NULL,
            payload TEXT DEFAULT '{}', idempotency_key VARCHAR(160) UNIQUE,
            attempts INTEGER DEFAULT 0, available_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            locked_until TIMESTAMP, status VARCHAR(20) DEFAULT 'queued',
            last_error TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        """))


def claim(session):
    now = datetime.utcnow()
    lease=now + timedelta(minutes=5)
    session.execute(text("""UPDATE icms_jobs SET locked_until=:until, status='running'
        WHERE id=(SELECT id FROM icms_jobs WHERE status='queued' AND available_at <= :now
        AND (locked_until IS NULL OR locked_until < :now) ORDER BY created_at LIMIT 1)
        AND status='queued'"""), {"now": now, "until": lease})
    job = session.execute(text("SELECT id, payload, attempts FROM icms_jobs WHERE status='running' AND locked_until=:until"), {"until": lease}).first()
    if not job: return None
    session.commit()
    return job


def execute(job):
    """Dispatch durable maintenance jobs in the worker process."""
    payload = json.loads(job.payload or "{}")
    if payload.get("operation") == "noop":
        return
    if payload.get("operation") == "refresh_quality_sla":
        session=SessionLocal()
        try:
            now=datetime.utcnow()
            for action in session.query(D.CorrectiveAction).filter(D.CorrectiveAction.deadline < now, D.CorrectiveAction.state.in_(("OPEN", "IN_PROGRESS"))).all():
                action.state="OVERDUE"
            session.commit()
        finally:
            session.close()
        return
    if payload.get("operation") == "process_administration_sla":
        session=SessionLocal()
        try: process_slas(session); process_outbox(session, worker_id=WORKER_ID)
        finally: session.close()
        return
    raise RuntimeError(f"No handler registered for queue job {payload.get('operation', 'unknown')}")


def run_once():
    session = SessionLocal()
    try:
        job = claim(session)
        if not job:
            return False
        try:
            execute(job)
            session.execute(text("UPDATE icms_jobs SET status='completed', locked_until=NULL WHERE id=:id"), {"id": job.id})
        except Exception as exc:
            attempts = job.attempts + 1
            status = "dead_letter" if attempts >= MAX_ATTEMPTS else "queued"
            delay = min(3600, 2 ** attempts)
            session.execute(text("""UPDATE icms_jobs SET status=:status, attempts=:attempts,
                last_error=:error, locked_until=NULL, available_at=:available WHERE id=:id"""),
                {"status": status, "attempts": attempts, "error": str(exc),
                 "available": datetime.utcnow() + timedelta(seconds=delay), "id": job.id})
            heartbeat("error", failed=1, error=str(exc)); monitor("job_failed", {"job_id": job.id, "attempts": attempts, "dead_letter": status == "dead_letter"})
        else:
            heartbeat("running", processed=1)
        session.commit()
        return True
    finally:
        session.close()


def main():
    ensure_queue()
    heartbeat("healthy")
    while True:
        ran = run_once()
        # Administration SLA and outbox processing are durable DB scans, so a
        # worker restart simply resumes pending work without frontend polling.
        admin_session = SessionLocal()
        try:
            process_slas(admin_session)
            process_outbox(admin_session, worker_id=WORKER_ID)
        finally:
            admin_session.close()
        if not ran:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
