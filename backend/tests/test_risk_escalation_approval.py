import os
import sys
import unittest
from datetime import datetime

from fastapi import HTTPException

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal, TENANT
from models import Approval, Notification, WorkflowInstance, WorkflowProfile
import domain_api
import domain_models as D
import main


CAMPUS_HEAD = {"sub": "user_3", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "scope_main_campus", "office_n": 3, "auth_level": "mfa"}
PRINCIPAL = {"sub": "user_4", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "scope_main_campus", "office_n": 4, "auth_level": "mfa"}
VICE_CHAIRMAN = {"sub": "user_2", "tenant_id": TENANT, "scope_level": "university", "scope_ref": "scope_univ", "office_n": 2, "auth_level": "mfa"}
CHAIRMAN = {"sub": "user_1", "tenant_id": TENANT, "scope_level": "global", "scope_ref": "scope_global", "office_n": 1, "auth_level": "mfa"}


class RiskEscalationApprovalTests(unittest.TestCase):
    def setUp(self):
        self.session = SessionLocal()
        self.risk_ids = []
        self.workflow_ids = []
        self.titles = []

    def tearDown(self):
        if self.workflow_ids:
            self.session.query(Approval).filter(Approval.workflow_id.in_(self.workflow_ids)).delete(synchronize_session=False)
            self.session.query(WorkflowProfile).filter(WorkflowProfile.workflow_id.in_(self.workflow_ids)).delete(synchronize_session=False)
            self.session.query(WorkflowInstance).filter(WorkflowInstance.id.in_(self.workflow_ids)).delete(synchronize_session=False)
        if self.risk_ids:
            self.session.query(D.RiskRecord).filter(D.RiskRecord.id.in_(self.risk_ids)).delete(synchronize_session=False)
        for title in self.titles:
            self.session.query(Notification).filter(Notification.body.like(f"%{title}%")).delete(synchronize_session=False)
        self.session.commit()
        self.session.close()

    def create_risk(self, severity="LOW"):
        title = f"regression-risk-{datetime.utcnow().strftime('%H%M%S%f')}"
        result = domain_api.create_risk(domain_api.RiskCreateIn(
            title=title, description="Workflow regression risk", category="Safety",
            severity=severity, likelihood="MEDIUM", impact="HIGH"),
            ctx=CAMPUS_HEAD, s=self.session)
        self.risk_ids.append(result["risk"]["id"])
        self.titles.append(title)
        return result["risk"]

    def test_campus_head_sees_initiated_purchase_request(self):
        title = f"purchase-{datetime.utcnow().strftime('%H%M%S%f')}"
        payload = main.start_workflow(main.StartWF(process_key="purchase_request", title=title), ctx=CAMPUS_HEAD, s=self.session)
        self.workflow_ids.append(payload["id"])
        rows = main.list_workflows(scope="mine", ctx=CAMPUS_HEAD, s=self.session)["workflows"]
        self.assertIn(payload["id"], {row["id"] for row in rows})

    def test_risk_creation_notifies_expected_oversight_offices(self):
        critical = self.create_risk("CRITICAL")
        principal = self.session.query(Notification).filter(Notification.user_id == "user_4", Notification.body.like(f"%{critical['title']}%")).count()
        self.assertGreaterEqual(principal, 1)
        self.assertEqual(self.session.query(Notification).filter(Notification.user_id.in_(["user_1", "user_2"]), Notification.body.like(f"%{critical['title']}%")).count(), 0)

        high = self.create_risk("HIGH")
        self.assertEqual(self.session.query(Notification).filter(Notification.user_id == "user_1", Notification.body.like(f"%{high['title']}%")).count(), 0)
        low = self.create_risk("LOW")
        self.assertEqual(self.session.query(Notification).filter(Notification.user_id.in_(["user_1", "user_2"]), Notification.body.like(f"%{low['title']}%")).count(), 0)

    def test_high_escalation_creates_principal_actionable_workflow_and_oversight(self):
        risk = self.create_risk("HIGH")
        result = domain_api.escalate_risk(risk["id"], domain_api.RiskReasonIn(reason="Needs governance review"), ctx=CAMPUS_HEAD, s=self.session)
        workflow_id = result["escalation_workflow_id"]
        self.workflow_ids.append(workflow_id)
        workflow = main.get_workflow(workflow_id, ctx=PRINCIPAL, s=self.session)
        self.assertIn("approve", workflow["available_actions"])
        inbox = main.list_workflows(scope="inbox", ctx=PRINCIPAL, s=self.session)["workflows"]
        self.assertIn(workflow_id, {row["id"] for row in inbox})
        self.assertEqual(main.get_workflow(workflow_id, ctx=VICE_CHAIRMAN, s=self.session)["available_actions"], [])
        self.assertIn(risk["id"], {row["id"] for row in domain_api.risk_oversight(ctx=VICE_CHAIRMAN, s=self.session)["risks"]})
        with self.assertRaises(HTTPException) as denied:
            domain_api.risk_oversight(ctx=CAMPUS_HEAD, s=self.session)
        self.assertEqual(denied.exception.status_code, 403)

    def test_critical_escalation_requires_vc_then_chairman(self):
        risk = self.create_risk("CRITICAL")
        result = domain_api.escalate_risk(risk["id"], domain_api.RiskReasonIn(reason="Critical review"), ctx=CAMPUS_HEAD, s=self.session)
        workflow_id = result["escalation_workflow_id"]
        self.workflow_ids.append(workflow_id)
        chairman_view = main.get_workflow(workflow_id, ctx=CHAIRMAN, s=self.session)
        self.assertEqual(chairman_view["available_actions"], [])
        with self.assertRaises(HTTPException):
            main.decide_workflow(main.DecideWF(workflow_id=workflow_id, action="approve"), ctx=CHAIRMAN, s=self.session)
        main.decide_workflow(main.DecideWF(workflow_id=workflow_id, action="escalate", reason="Exceptional authority"), ctx=PRINCIPAL, s=self.session)
        main.decide_workflow(main.DecideWF(workflow_id=workflow_id, action="escalate", reason="Chairman decision required"), ctx=VICE_CHAIRMAN, s=self.session)
        chairman_view = main.get_workflow(workflow_id, ctx=CHAIRMAN, s=self.session)
        self.assertIn("approve", chairman_view["available_actions"])
        final = main.decide_workflow(main.DecideWF(workflow_id=workflow_id, action="approve"), ctx=CHAIRMAN, s=self.session)
        self.assertEqual(final["workflow"]["state"], "approved")
        mine = main.list_workflows(scope="mine", ctx=CAMPUS_HEAD, s=self.session)["workflows"]
        self.assertEqual(next(row["state"] for row in mine if row["id"] == workflow_id), "approved")

    def test_governance_cannot_act_out_of_stage_or_on_own_request(self):
        title = f"governance-request-{datetime.utcnow().strftime('%H%M%S%f')}"
        payload = main.start_workflow(main.StartWF(process_key="purchase_request", title=title), ctx=VICE_CHAIRMAN, s=self.session)
        self.workflow_ids.append(payload["id"])
        with self.assertRaises(HTTPException):
            main.decide_workflow(main.DecideWF(workflow_id=payload["id"], action="approve"), ctx=VICE_CHAIRMAN, s=self.session)
        with self.assertRaises(HTTPException) as chairman_error:
            main.decide_workflow(main.DecideWF(workflow_id=payload["id"], action="approve"), ctx=CHAIRMAN, s=self.session)
        self.assertIn("Purchase Office", chairman_error.exception.detail)

    def test_high_risk_does_not_notify_chairman(self):
        before = self.session.query(Notification).filter(Notification.user_id == "user_1").count()
        risk = self.create_risk("HIGH")
        after = self.session.query(Notification).filter(Notification.user_id == "user_1").count()
        self.assertEqual(after, before)
        self.assertGreater(self.session.query(Notification).filter(
            Notification.user_id == "user_4", Notification.body.like(f"%{risk['title']}%")).count(), 0)

    def test_low_risk_notifies_no_governance_office(self):
        before = {user_id: self.session.query(Notification).filter(Notification.user_id == user_id).count()
                  for user_id in ("user_1", "user_2")}
        self.create_risk("LOW")
        after = {user_id: self.session.query(Notification).filter(Notification.user_id == user_id).count()
                 for user_id in ("user_1", "user_2")}
        self.assertEqual(after, before)

    def test_governance_cannot_approve_out_of_stage_or_own_escalation(self):
        out_of_stage = main.start_workflow(main.StartWF(process_key="purchase_request", title="out-of-stage"), ctx=CAMPUS_HEAD, s=self.session)
        self.workflow_ids.append(out_of_stage["id"])
        with self.assertRaises(HTTPException):
            main.decide_workflow(main.DecideWF(workflow_id=out_of_stage["id"], action="approve"), ctx=VICE_CHAIRMAN, s=self.session)

        own = main.start_workflow(main.StartWF(process_key="purchase_request", title="own-escalation"), ctx=VICE_CHAIRMAN, s=self.session)
        self.workflow_ids.append(own["id"])
        workflow = self.session.get(WorkflowInstance, own["id"])
        workflow.escalated = True
        self.session.commit()
        with self.assertRaises(HTTPException):
            main.decide_workflow(main.DecideWF(workflow_id=own["id"], action="approve"), ctx=VICE_CHAIRMAN, s=self.session)

    def test_oversight_offices_can_read_escalated_high_risks(self):
        risk = self.create_risk("HIGH")
        self.workflow_ids.append(domain_api.escalate_risk(
            risk["id"], domain_api.RiskReasonIn(reason="Oversight visibility"), ctx=CAMPUS_HEAD, s=self.session)["escalation_workflow_id"])
        for ctx in (PRINCIPAL, VICE_CHAIRMAN, CHAIRMAN):
            self.assertIn(risk["id"], {row["id"] for row in domain_api.risk_oversight(ctx=ctx, s=self.session)["risks"]})
        with self.assertRaises(HTTPException):
            domain_api.risk_oversight(ctx=CAMPUS_HEAD, s=self.session)


if __name__ == "__main__":
    unittest.main()
