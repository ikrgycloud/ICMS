import unittest
import os
import sys
from datetime import datetime, timedelta

from fastapi import HTTPException

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal, TENANT
from models import AuditLog, Notification
import domain_api
import domain_models as D


class Phase5CRiskTests(unittest.TestCase):
    ctx = {
        "sub": "user_3", "tenant_id": TENANT, "scope_level": "campus",
        "scope_ref": "scope_main_campus", "office_n": 3, "auth_level": "mfa",
    }

    def setUp(self):
        self.session = SessionLocal()
        self.risk_ids = []
        self.action_ids = []
        self.risk_titles = []

    def tearDown(self):
        if self.risk_ids:
            self.session.query(D.CorrectiveAction).filter(D.CorrectiveAction.risk_id.in_(self.risk_ids)).delete(synchronize_session=False)
            self.session.query(D.RiskRecord).filter(D.RiskRecord.id.in_(self.risk_ids)).delete(synchronize_session=False)
            # Audit rows are append-only: deleting test activity here would
            # corrupt the tenant's hash chain for later audit verification.
            for title in self.risk_titles:
                self.session.query(Notification).filter(Notification.body.like(f"%{title}%")).delete(synchronize_session=False)
        self.session.commit()
        self.session.close()

    def create_risk(self, **overrides):
        values = {
            "title": f"Risk {datetime.utcnow().strftime('%H%M%S%f')}",
            "description": "Temporary Phase 5C test risk",
            "category": "Infrastructure", "severity": "MEDIUM",
            "likelihood": "MEDIUM", "impact": "MEDIUM", "owner_id": "user_4",
            "due_at": datetime.utcnow() + timedelta(days=1),
        }
        values.update(overrides)
        result = domain_api.create_risk(domain_api.RiskCreateIn(**values), ctx=self.ctx, s=self.session)
        risk_id = result["risk"]["id"]
        self.risk_ids.append(risk_id)
        self.risk_titles.append(result["risk"]["title"])
        return result["risk"]

    def test_create_risk_uses_authenticated_campus_and_controls_values(self):
        risk = self.create_risk()
        self.assertEqual(risk["campus_scope_id"], "scope_main_campus")
        self.assertEqual(risk["status"], "OPEN")
        self.assertEqual(risk["priority"], "MEDIUM")
        with self.assertRaises(HTTPException):
            domain_api.create_risk(domain_api.RiskCreateIn(
                title="Invalid category", description="x", category="Other",
                severity="LOW", likelihood="LOW", impact="LOW"),
                ctx=self.ctx, s=self.session)

    def test_wrong_campus_and_tenant_cannot_view_risk(self):
        risk = self.create_risk()
        wrong_campus = {**self.ctx, "scope_ref": "scope_north_campus"}
        with self.assertRaises(HTTPException) as campus_error:
            domain_api.get_risk(risk["id"], ctx=wrong_campus, s=self.session)
        self.assertEqual(campus_error.exception.status_code, 404)
        wrong_tenant = {**self.ctx, "tenant_id": "tenant_other"}
        with self.assertRaises(HTTPException) as tenant_error:
            domain_api.get_risk(risk["id"], ctx=wrong_tenant, s=self.session)
        self.assertEqual(tenant_error.exception.status_code, 403)

    def test_edit_and_owner_assignment_are_scoped(self):
        risk = self.create_risk()
        updated = domain_api.update_risk(risk["id"], domain_api.RiskUpdateIn(title="Updated campus risk"), ctx=self.ctx, s=self.session)
        self.assertEqual(updated["risk"]["title"], "Updated campus risk")
        assigned = domain_api.assign_risk(risk["id"], domain_api.RiskOwnerIn(owner_id="user_4"), ctx=self.ctx, s=self.session)
        self.assertEqual(assigned["risk"]["owner_id"], "user_4")
        with self.assertRaises(HTTPException):
            domain_api.assign_risk(risk["id"], domain_api.RiskOwnerIn(owner_id="user_36"), ctx=self.ctx, s=self.session)

    def test_corrective_action_lifecycle_and_risk_closure(self):
        risk = self.create_risk()
        with self.assertRaises(HTTPException):
            domain_api.list_risk_actions(risk["id"], ctx={**self.ctx, "scope_ref": "scope_north_campus"}, s=self.session)
        created = domain_api.create_risk_action(risk["id"], domain_api.ActionCreateIn(
            description="Repair the affected facility", owner_id="user_4",
            due_at=datetime.utcnow() + timedelta(days=1)), ctx=self.ctx, s=self.session)
        action_id = created["action"]["id"]
        self.action_ids.append(action_id)
        with self.assertRaises(HTTPException):
            domain_api.close_risk(risk["id"], domain_api.RiskReasonIn(reason="Too early"), ctx=self.ctx, s=self.session)
        domain_api.update_risk_action(action_id, domain_api.ActionUpdateIn(status="IN_PROGRESS", progress=40), ctx=self.ctx, s=self.session)
        domain_api.complete_risk_action(action_id, domain_api.ActionCompleteIn(completion_notes="Repair complete"), ctx=self.ctx, s=self.session)
        verified = domain_api.verify_risk_action(action_id, ctx=self.ctx, s=self.session)
        self.assertEqual(verified["action"]["status"], "VERIFIED")
        resolved = domain_api.resolve_risk(risk["id"], domain_api.RiskReasonIn(resolution_notes="Issue resolved"), ctx=self.ctx, s=self.session)
        self.assertEqual(resolved["risk"]["status"], "RESOLVED")
        closed = domain_api.close_risk(risk["id"], domain_api.RiskReasonIn(reason="Verified and closed"), ctx=self.ctx, s=self.session)
        self.assertEqual(closed["risk"]["status"], "CLOSED")
        with self.assertRaises(HTTPException):
            domain_api.update_risk(risk["id"], domain_api.RiskUpdateIn(title="No edit after close"), ctx=self.ctx, s=self.session)

    def test_invalid_risk_transition_and_high_risk_escalation(self):
        risk = self.create_risk(severity="CRITICAL", priority="CRITICAL")
        with self.assertRaises(HTTPException):
            domain_api.close_risk(risk["id"], domain_api.RiskReasonIn(reason="Invalid close"), ctx=self.ctx, s=self.session)
        escalated = domain_api.escalate_risk(risk["id"], domain_api.RiskReasonIn(reason="Critical campus risk"), ctx=self.ctx, s=self.session)
        self.assertEqual(escalated["destination"], "Chairman")
        self.assertEqual(escalated["risk"]["escalation_destination"], "Chairman")
        audits = self.session.query(AuditLog).filter(AuditLog.entity == f"risk:{risk['id']}").all()
        self.assertTrue(any(row.action == "risk.escalate" for row in audits))
        notifications = self.session.query(Notification).filter(Notification.title == "Campus risk escalated").all()
        self.assertTrue(any(row.user_id == "user_1" and risk["title"] in row.body for row in notifications))

    def test_summary_is_scoped_to_real_risk_records(self):
        risk = self.create_risk()
        action = domain_api.create_risk_action(risk["id"], domain_api.ActionCreateIn(
            description="Overdue test action", owner_id="user_4",
            due_at=datetime.utcnow() - timedelta(days=1)), ctx=self.ctx, s=self.session)["action"]
        self.action_ids.append(action["id"])
        summary = domain_api.risk_summary(ctx=self.ctx, s=self.session)["summary"]
        self.assertGreaterEqual(summary["open"], 1)
        self.assertGreaterEqual(summary["overdue_actions"], 1)
        self.assertIn("high_critical", summary)
        self.assertIn("overdue_actions", summary)


if __name__ == "__main__":
    unittest.main()
