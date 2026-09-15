"""Central state graph for the Dean Administration requirement lifecycle."""

from fastapi import HTTPException


ALLOWED_TRANSITIONS = {
    "DRAFT": {"SUBMITTED"},
    "SUBMITTED": {"VALIDATING", "VALIDATED", "RETURNED", "REJECTED"},
    "VALIDATING": {"VALIDATED", "RETURNED", "REJECTED"},
    "VALIDATED": {"CATEGORIZED", "RETURNED", "REJECTED"},
    "CATEGORIZED": {"RESOURCE_REVIEW", "PENDING_APPROVAL", "ROUTED", "RETURNED", "REJECTED"},
    "RESOURCE_REVIEW": {"CATEGORIZED", "PENDING_APPROVAL", "RETURNED", "REJECTED"},
    "BUDGET_REVIEW": {"PENDING_APPROVAL", "RETURNED", "REJECTED"},
    "PENDING_APPROVAL": {"ESCALATED", "APPROVED", "REJECTED", "RETURNED"},
    "ESCALATED": {"APPROVED", "REJECTED", "RETURNED"},
    "APPROVED": {"ROUTED"},
    "ROUTED": {"IN_EXECUTION", "RETURNED", "OVERDUE"},
    "IN_EXECUTION": {"IN_PROGRESS", "ON_HOLD", "PENDING_EVIDENCE", "OVERDUE"},
    "IN_PROGRESS": {"IN_PROGRESS", "ON_HOLD", "PENDING_EVIDENCE", "OVERDUE"},
    "ON_HOLD": {"IN_PROGRESS", "PENDING_EVIDENCE", "OVERDUE"},
    "OVERDUE": {"IN_PROGRESS", "ON_HOLD", "PENDING_EVIDENCE"},
    "PENDING_EVIDENCE": {"PENDING_EVIDENCE", "READY_FOR_REVIEW"},
    "READY_FOR_REVIEW": {"COMPLETED", "PENDING_EVIDENCE", "RETURNED"},
    "COMPLETED": {"CLOSED", "READY_FOR_REVIEW"},
    "CLOSED": set(),
    "REJECTED": set(),
    "RETURNED": {"SUBMITTED", "DRAFT"},
}


def require_transition(current: str, target: str) -> None:
    """Reject transitions not represented by the authoritative state graph."""
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(409, f"Cannot move {current} to {target}")
