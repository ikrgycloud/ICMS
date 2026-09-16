"""Source-domain transitions performed as part of generic workflow decisions."""
from datetime import datetime

import administration_models as A
import domain_models as D
import specialist_models as S
from administration_jobs import emit_outbox
from fastapi import HTTPException
from core import uid


def _event(s, wf, recipient, title, body, key, severity="info"):
    emit_outbox(s, wf.tenant_id, "WorkflowDecision", wf.id,
                {"recipient": recipient, "title": title, "body": body, "severity": severity}, key)


def apply_decision(s, wf, action, actor_id, actor_name):
    """Apply a source transition before the workflow transaction commits.

    Source references are optional for legacy seeded workflows. New domain
    workflows must provide one before an approval can claim execution.
    """
    if action not in {"approve", "reject", "return"}:
        return
    if wf.source_type == "campus_escalation":
        row = (s.query(D.EscalationRecord)
               .filter(D.EscalationRecord.id == wf.source_id, D.EscalationRecord.tenant_id == wf.tenant_id)
               .with_for_update().first())
        if not row:
            raise HTTPException(409, "Campus escalation source record is missing")
        previous = row.status
        row.status = {"approve": "RECEIVED", "return": "FOLLOW_UP", "reject": "CLOSED"}[action]
        if action == "approve":
            row.received_by = actor_id
        elif action == "reject":
            row.resolved_by = actor_id
        s.add(D.EscalationEvent(id=uid(), tenant_id=wf.tenant_id, escalation_id=row.id,
                                 actor_id=actor_id,
                                 event_type={"approve": "ACKNOWLEDGED", "return": "RETURNED", "reject": "CLOSED"}[action],
                                 reason="", previous_status=previous, new_status=row.status))
        _event(s, wf, wf.initiator_id, f"Campus escalation {row.status.lower()}",
               wf.title, f"workflow:{wf.id}:{action}", "action" if action == "return" else "info")
        return
    if wf.process_key == "fee_structure":
        structure = s.query(D.FeeStructure).filter(D.FeeStructure.workflow_id == wf.id).with_for_update().first()
        if structure:
            structure.status = {"approve": "APPROVED", "reject": "REJECTED", "return": "RETURNED"}[action]
            structure.updated_by = actor_id
            structure.updated_at = datetime.utcnow()
            _event(s, wf, wf.initiator_id, f"Fee structure {structure.status.lower()}", wf.title, f"workflow:{wf.id}:{action}")
        return
    if wf.source_type == "fee_waiver_request":
        row = (s.query(D.FeeWaiverRequest)
               .filter(D.FeeWaiverRequest.id == wf.source_id,
                       D.FeeWaiverRequest.tenant_id == wf.tenant_id)
               .with_for_update().first())
        if not row:
            raise HTTPException(409, "Fee waiver source record is missing")
        row.status = {
            "approve": "approved_pending_accounts",
            "reject": "rejected",
            "return": "returned_to_finance",
        }[action]
        row.decided_by = actor_id
        row.decided_at = datetime.utcnow()
        _event(s, wf, row.requested_by, f"Fee waiver {row.status.replace('_', ' ')}",
               wf.title, f"workflow:{wf.id}:{action}", "action" if action == "approve" else "info")
        if action == "approve":
            _event(s, wf, "office:23", "Fee waiver ready for Accounts execution",
                   f"{wf.title}; waiver request {row.id} is approved.",
                   f"fee-waiver:{row.id}:accounts", "action")
        return
    if wf.source_type == "application":
        from admissions_service import transition_application
        app = s.query(D.Application).filter(D.Application.id == wf.source_id, D.Application.tenant_id == wf.tenant_id).with_for_update().first()
        if not app:
            raise HTTPException(409, "Admission source record is missing")
        source_ctx = {"sub": actor_id, "tenant_id": wf.tenant_id, "office_n": 4,
                      "scope_level": "campus", "scope_ref": wf.scope_ref, "auth_level": "mfa"}
        if action == "approve":
            transition_application(s, source_ctx, app.id, "approve_final", app.status_version,
                                   "Principal final admission approval", skip_capability=True, commit=False)
            transition_application(s, source_ctx, app.id, "ready_to_admit", app.status_version,
                                   "Admission ready-to-admit transition", skip_capability=True, commit=False)
        elif action == "reject":
            transition_application(s, source_ctx, app.id, "reject", app.status_version,
                                   "Principal rejected final admission", skip_capability=True, commit=False)
        _event(s, wf, wf.initiator_id, f"Admission {action}d", wf.title, f"workflow:{wf.id}:{action}")
        return
    if wf.source_type == "enrollment":
        enrollment = s.query(D.Enrollment).filter(D.Enrollment.id == wf.source_id, D.Enrollment.tenant_id == wf.tenant_id).with_for_update().first()
        if not enrollment:
            raise HTTPException(409, "Registration source record is missing")
        student = s.get(D.Student, enrollment.student_id)
        if not student or (wf.scope_ref and student.campus != wf.scope_ref):
            raise HTTPException(403, "Registration is outside the workflow campus")
        enrollment.status = "enrolled" if action == "approve" else "requested" if action == "return" else "dropped"
        _event(s, wf, student.user_id or wf.initiator_id, f"Course registration {action}d", wf.title, f"workflow:{wf.id}:{action}")
        return
    if not wf.source_type or not wf.source_id:
        if wf.process_key in {"attendance_condonation", "disciplinary_action", "purchase_request", "recruitment", "infrastructure_capex"}:
            raise HTTPException(409, f"{wf.process_key} workflow has no source-domain reference")
        return
    if wf.source_type == "complaint":
        row = s.query(D.Complaint).filter(D.Complaint.id == wf.source_id, D.Complaint.tenant_id == wf.tenant_id).with_for_update().first()
        if not row:
            raise HTTPException(409, "Discipline source record is missing")
        row.decision = action.upper()
        row.decided_by = actor_id
        row.decided_at = datetime.utcnow()
        row.status = "resolved" if action == "approve" else "returned" if action == "return" else "rejected"
        _event(s, wf, row.raised_by, f"Discipline decision: {action}", row.subject, f"workflow:{wf.id}:{action}")
        return
    if wf.source_type == "hr_staffing_request":
        row = s.query(S.HRStaffingRequest).filter(S.HRStaffingRequest.id == wf.source_id, S.HRStaffingRequest.tenant_id == wf.tenant_id).with_for_update().first()
        if not row:
            raise HTTPException(409, "HR source record is missing")
        row.status = "APPROVED" if action == "approve" else "RETURNED" if action == "return" else "REJECTED"
        row.updated_by = actor_id
        row.updated_at = datetime.utcnow()
        _event(s, wf, row.created_by, f"HR request {row.status.lower()}", wf.title, f"workflow:{wf.id}:{action}")
        return
    if wf.source_type == "hr_promotion_request":
        row = s.query(S.HRPromotionRequest).filter(S.HRPromotionRequest.id == wf.source_id, S.HRPromotionRequest.tenant_id == wf.tenant_id).with_for_update().first()
        if not row:
            raise HTTPException(409, "HR promotion source record is missing")
        if action == "approve" and row.effective_date <= datetime.utcnow():
            raise HTTPException(409, "Promotion effective date must be in the future")
        row.status = "APPROVED" if action == "approve" else "RETURNED" if action == "return" else "REJECTED"
        row.decided_by = actor_id
        row.updated_at = datetime.utcnow()
        _event(s, wf, row.requested_by, f"Promotion {row.status.lower()}", wf.title, f"workflow:{wf.id}:{action}")
        return
    if wf.source_type == "procurement_requisition":
        row = s.query(S.ProcurementRequisition).filter(S.ProcurementRequisition.id == wf.source_id, S.ProcurementRequisition.tenant_id == wf.tenant_id).with_for_update().first()
        if not row:
            raise HTTPException(409, "Procurement source record is missing")
        row.status = "APPROVED" if action == "approve" else "RETURNED" if action == "return" else "REJECTED"
        row.updated_by = actor_id
        row.updated_at = datetime.utcnow()
        _event(s, wf, "user_32", f"Purchase requisition {row.status.lower()}", wf.title, f"workflow:{wf.id}:{action}", "action")
        return
    if wf.source_type == "attendance_condonation":
        row = s.query(D.AttendanceCondonationRequest).filter(D.AttendanceCondonationRequest.id == wf.source_id, D.AttendanceCondonationRequest.tenant_id == wf.tenant_id).with_for_update().first()
        if not row:
            raise HTTPException(409, "Condonation source record is missing")
        row.status = "APPROVED" if action == "approve" else "RETURNED" if action == "return" else "REJECTED"
        row.decided_by = actor_id
        row.decided_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        _event(s, wf, "user_22" if action == "approve" else row.requested_by,
               f"Condonation {row.status.lower()}",
               f"{wf.title}; condonation {row.id}; workflow {wf.id}.",
               f"workflow:{wf.id}:{action}", "action" if action == "approve" else "info")
        return
    raise HTTPException(409, f"No source handler registered for {wf.source_type}")
