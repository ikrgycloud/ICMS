"""Local Phase 11 verification contracts for security and operational invariants."""
import json
from types import SimpleNamespace
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import domain_models as D
from authority import audit_hash
from core import notify, write_audit
from models import Base, AuditLog, Notification, NotificationDelivery, User
from worker import execute


def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    D.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_audit_chain_is_hash_linked():
    db = session()
    first = write_audit(db, "u1", "User", 6, "test.one", "entity:1", "", "OPEN", "")
    second = write_audit(db, "u1", "User", 6, "test.two", "entity:1", "OPEN", "CLOSED", "")
    assert second.prev_hash == first.hash
    expected = audit_hash(first.hash, {"actor": "u1", "action": "test.two", "entity": "entity:1", "new_state": "CLOSED"})
    assert second.hash == expected


def test_notification_creates_delivery_outcome():
    db = session()
    notify(db, "u1", "SLA escalation", "Action overdue", severity="critical")
    notification = db.query(Notification).one()
    delivery = db.query(NotificationDelivery).one()
    assert delivery.notification_id == notification.id
    assert delivery.status == "delivered"
    assert notification.severity == "critical"


def test_worker_handles_idempotent_noop_without_mutation():
    job = SimpleNamespace(payload=json.dumps({"operation": "noop"}))
    assert execute(job) is None


def test_worker_rejects_unknown_operation_for_retry():
    job = SimpleNamespace(payload=json.dumps({"operation": "unknown_test_operation"}))
    try:
        execute(job)
    except RuntimeError as error:
        assert "unknown_test_operation" in str(error)
    else:
        raise AssertionError("Unknown jobs must enter retry handling")


def test_self_approval_is_rejected_by_governance_rule():
    from fastapi import HTTPException
    from governance_engine import validate_transition
    db = session()
    from models import GovernancePolicy
    db.add(GovernancePolicy(id="p", tenant_id="t_main", proposal_type="curriculum", allowed_transitions_json=json.dumps({"SUBMITTED": ["APPROVED"]}), reviewer_office_n=6))
    db.commit()
    proposal = SimpleNamespace(proposal_type="curriculum", state="SUBMITTED", status_version=0, submitted_by="u1", assigned_reviewer_id="u1")
    try:
        validate_transition(db, proposal, "APPROVED", 0, {"sub": "u1", "office_n": 6})
    except HTTPException as error:
        assert error.status_code == 403
    else:
        raise AssertionError("Submitter must not approve own proposal")


def test_invalid_transition_and_version_conflict_are_rejected():
    from fastapi import HTTPException
    from governance_engine import validate_transition
    db = session()
    from models import GovernancePolicy
    db.add(GovernancePolicy(id="p", tenant_id="t_main", proposal_type="curriculum", allowed_transitions_json=json.dumps({"DRAFT": ["SUBMITTED"]})))
    db.commit()
    proposal = SimpleNamespace(proposal_type="curriculum", state="DRAFT", status_version=3, submitted_by="u1", assigned_reviewer_id=None)
    for target, version in (("APPROVED", 3), ("SUBMITTED", 2)):
        try:
            validate_transition(db, proposal, target, version, {"sub": "u2", "office_n": 6})
        except HTTPException as error:
            assert error.status_code == 409
        else:
            raise AssertionError("Invalid state or stale version must be rejected")
