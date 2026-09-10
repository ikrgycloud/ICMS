"""Shared academic governance policy and transaction primitives."""
import json
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import desc

from core import uid, write_audit
from database import TENANT
from models import GovernancePolicy, GovernanceNotification, Notification, User, AuditLog
import domain_models as D

STATES = ("DRAFT", "SUBMITTED", "UNDER_REVIEW", "CLARIFICATION_REQUIRED", "RETURNED", "RESUBMITTED", "APPROVED", "REJECTED", "ESCALATED", "IMPLEMENTED", "ARCHIVED")


def policy_for(s, proposal_type):
    policy = s.query(GovernancePolicy).filter(GovernancePolicy.tenant_id == TENANT, GovernancePolicy.proposal_type == proposal_type, GovernancePolicy.active == True).first()
    if not policy:
        raise HTTPException(422, f"No governance policy configured for {proposal_type}")
    return policy


def transition(s, proposal, target, expected_version, actor, reason="", reviewer_id=None, evidence_ids=None):
    """Apply one policy transition and all side effects in the caller transaction."""
    policy = policy_for(s, proposal.proposal_type)
    transitions = json.loads(policy.allowed_transitions_json or "{}")
    required = set(json.loads(policy.required_reason_states_json or "[]"))
    if target not in transitions.get(proposal.state, []):
        raise HTTPException(409, f"Transition {proposal.state} -> {target} is not allowed")
    if proposal.status_version != expected_version:
        raise HTTPException(409, "Proposal changed; reload before transitioning")
    if target in required and not reason.strip():
        raise HTTPException(422, "A reason is required for this transition")
    if target in {"APPROVED", "REJECTED", "ESCALATED", "IMPLEMENTED", "ARCHIVED"} and proposal.submitted_by == actor["sub"]:
        raise HTTPException(403, "Segregation of duties prevents the submitter from deciding this proposal")
    if policy.reviewer_office_n and target in {"UNDER_REVIEW", "APPROVED", "REJECTED", "RETURNED", "CLARIFICATION_REQUIRED", "ESCALATED"} and actor.get("office_n") != policy.reviewer_office_n:
        raise HTTPException(403, "Only the assigned reviewer office may perform this transition")
    if target in {"UNDER_REVIEW", "APPROVED", "REJECTED", "RETURNED", "CLARIFICATION_REQUIRED", "ESCALATED"} and not (reviewer_id or proposal.assigned_reviewer_id):
        if target not in {"UNDER_REVIEW", "APPROVED", "REJECTED"}:
            raise HTTPException(422, "An assigned reviewer is required")
    previous = proposal.state
    proposal.state = target
    proposal.status_version += 1
    proposal.updated_at = datetime.utcnow()
    if reviewer_id:
        proposal.assigned_reviewer_id = reviewer_id
    event = D.AcademicProposalEvent(id=uid(), tenant_id=TENANT, proposal_id=proposal.id, from_state=previous, to_state=target, actor_id=actor["sub"], actor_office_n=actor["office_n"], reason=reason.strip())
    s.add(event)
    evidence_ids = evidence_ids or []
    audit = write_audit(s, actor["sub"], actor.get("actor_name", actor["sub"]), actor["office_n"], f"governance.proposal.{target.lower()}", f"academic_proposal:{proposal.id}", previous, target, reason.strip(), commit=False)
    audit.entity_version = proposal.status_version
    audit.workflow_id = proposal.id
    audit.evidence_document_ids = json.dumps(evidence_ids)
    if target in {"SUBMITTED", "RESUBMITTED"}:
        recipients = s.query(User).filter(User.tenant_id == TENANT, User.office_n == (policy.reviewer_office or 6), User.status == "active").all()
        event_name = "submission"
    else:
        recipients = [s.get(User, proposal.submitted_by)] if proposal.submitted_by else []
        event_name = target.lower()
    for recipient in [item for item in recipients if item]:
        notification = Notification(id=uid(), tenant_id=TENANT, user_id=recipient.id, severity="action", title=f"Governance proposal {event_name}", body=proposal.title)
        s.add(notification)
        s.flush()
        s.add(GovernanceNotification(id=uid(), tenant_id=TENANT, notification_id=notification.id, workflow_id=proposal.id, recipient_id=recipient.id, event=event_name, outcome="queued"))
    return proposal


def validate_transition(s, proposal, target, expected_version, actor, reason=""):
    """Validate a legacy route against the same policy before its own side effects."""
    policy = policy_for(s, proposal.proposal_type)
    transitions = json.loads(policy.allowed_transitions_json or "{}")
    if target not in transitions.get(proposal.state, []):
        raise HTTPException(409, f"Transition {proposal.state} -> {target} is not allowed")
    if proposal.status_version != expected_version:
        raise HTTPException(409, "Proposal changed; reload before transitioning")
    if target in set(json.loads(policy.required_reason_states_json or "[]")) and not reason.strip():
        raise HTTPException(422, "A reason is required for this transition")
    if target in {"APPROVED", "REJECTED", "ESCALATED", "IMPLEMENTED", "ARCHIVED"} and proposal.submitted_by == actor["sub"]:
        raise HTTPException(403, "Segregation of duties prevents the submitter from deciding this proposal")
    return True


def payload(s, proposal):
    version = s.query(D.AcademicProposalVersion).filter(D.AcademicProposalVersion.proposal_id == proposal.id, D.AcademicProposalVersion.version_no == proposal.version_no).first()
    return {"id": proposal.id, "type": proposal.proposal_type, "title": proposal.title, "state": proposal.state, "status_version": proposal.status_version, "version_no": proposal.version_no, "assigned_reviewer_id": proposal.assigned_reviewer_id, "due_at": proposal.due_at.isoformat() if proposal.due_at else None, "payload": json.loads(version.payload_json or "{}") if version else {}, "implementation_ref": proposal.implementation_ref}
