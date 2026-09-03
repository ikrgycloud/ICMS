import json
import os
import sys
import unittest
from datetime import date, datetime, timedelta

from fastapi import HTTPException

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal, TENANT
from models import AuditLog, Notification, OrgScope, WorkflowInstance
import domain_api
import domain_models as D


class Phase5DEscalationReportTests(unittest.TestCase):
    campus_ctx = {"sub": "user_3", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "scope_main_campus", "office_n": 3, "auth_level": "mfa"}
    vc_ctx = {"sub": "user_2", "tenant_id": TENANT, "scope_level": "university", "scope_ref": "scope_univ", "office_n": 2, "auth_level": "mfa"}
    principal_ctx = {"sub": "user_4", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "scope_main_campus", "office_n": 4, "auth_level": "mfa"}

    def setUp(self):
        self.session = SessionLocal()
        self.risk_ids = []
        self.escalation_ids = []
        self.report_ids = []
        self.action_ids = []
        self.workflow_ids = []

    def tearDown(self):
        self.session.rollback()
        escalation_ids = self.escalation_ids
        report_ids = self.report_ids
        risk_ids = self.risk_ids
        action_ids = self.action_ids
        workflow_ids = self.workflow_ids
        self.session.query(D.EscalationEvent).filter(D.EscalationEvent.escalation_id.in_(escalation_ids)).delete(synchronize_session=False)
        self.session.query(D.EscalationRecord).filter(D.EscalationRecord.id.in_(escalation_ids)).delete(synchronize_session=False)
        self.session.query(D.CampusReportSnapshot).filter(D.CampusReportSnapshot.report_id.in_(report_ids)).delete(synchronize_session=False)
        self.session.query(D.CampusReport).filter(D.CampusReport.id.in_(report_ids)).delete(synchronize_session=False)
        self.session.query(D.CorrectiveAction).filter(D.CorrectiveAction.id.in_(action_ids)).delete(synchronize_session=False)
        self.session.query(D.RiskRecord).filter(D.RiskRecord.id.in_(risk_ids)).delete(synchronize_session=False)
        self.session.query(WorkflowInstance).filter(WorkflowInstance.id.in_(workflow_ids)).delete(synchronize_session=False)
        # Keep audit evidence append-only. Removing only selected events here
        # breaks the tenant-wide audit hash chain.
        for marker in self.notification_markers:
            self.session.query(Notification).filter(Notification.body.like(f"%{marker}%")).delete(synchronize_session=False)
        self.session.commit()
        self.session.close()

    @property
    def notification_markers(self):
        return getattr(self, "_notification_markers", [])

    def mark(self, value):
        self._notification_markers = getattr(self, "_notification_markers", []) + [value]

    def create_risk(self, title="Phase 5D source risk", category="Academic", severity="HIGH"):
        title = f"{title} {datetime.utcnow().strftime('%H%M%S%f')}"
        self.mark(title)
        risk = domain_api.create_risk(domain_api.RiskCreateIn(title=title, description="Phase 5D test source", category=category, severity=severity, likelihood="MEDIUM", impact="HIGH", owner_id="user_4"), ctx=self.campus_ctx, s=self.session)["risk"]
        self.risk_ids.append(risk["id"])
        return risk

    def test_escalation_policy_and_lifecycle(self):
        risk = self.create_risk(category="Academic", severity="HIGH")
        body = domain_api.EscalationCreateIn(source_type="risk", source_ref=risk["id"], reason="Academic matter needs principal review", priority="HIGH", owner_id="user_4", due_at=datetime.utcnow() + timedelta(days=2))
        created = domain_api.create_escalation(body, ctx=self.campus_ctx, s=self.session)["escalation"]
        self.escalation_ids.append(created["id"])
        self.assertEqual(created["destination_office_n"], 4)
        submitted = domain_api.submit_escalation(created["id"], domain_api.Phase5DReasonIn(reason="Submitted"), ctx=self.campus_ctx, s=self.session)["escalation"]
        self.assertEqual(submitted["status"], "SUBMITTED")
        received = domain_api.receive_escalation(created["id"], domain_api.Phase5DReasonIn(reason="Received"), ctx=self.principal_ctx, s=self.session)["escalation"]
        self.assertEqual(received["status"], "RECEIVED")
        followed = domain_api.follow_up_escalation(created["id"], domain_api.Phase5DReasonIn(reason="Follow-up"), ctx=self.principal_ctx, s=self.session)["escalation"]
        self.assertEqual(followed["status"], "FOLLOW_UP")
        resolved = domain_api.resolve_escalation(created["id"], domain_api.Phase5DReasonIn(reason="Resolved"), ctx=self.principal_ctx, s=self.session)["escalation"]
        self.assertEqual(resolved["status"], "RESOLVED")
        closed = domain_api.close_escalation(created["id"], domain_api.Phase5DReasonIn(reason="Closed"), ctx=self.principal_ctx, s=self.session)["escalation"]
        self.assertEqual(closed["status"], "CLOSED")
        self.assertTrue(self.session.query(D.EscalationEvent).filter(D.EscalationEvent.escalation_id == created["id"]).count() >= 5)
        self.assertTrue(self.session.query(AuditLog).filter(AuditLog.entity == f"escalation:{created['id']}").count() >= 5)
        self.assertTrue(self.session.query(Notification).filter(Notification.body.like(f"%escalation:{created['id']}%")).count() >= 1)

    def test_principal_inbox_includes_submitted_campus_risk_escalation(self):
        risk = self.create_risk(title="Principal inbox risk", category="Student", severity="HIGH")
        created = domain_api.create_escalation(
            domain_api.EscalationCreateIn(
                source_type="risk", source_ref=risk["id"],
                reason="Student grievance backlog requires immediate institutional intervention.",
                priority="HIGH", owner_id="user_4"),
            ctx=self.campus_ctx, s=self.session)["escalation"]
        self.escalation_ids.append(created["id"])
        submitted = domain_api.submit_escalation(
            created["id"], domain_api.Phase5DReasonIn(reason="Submitted"),
            ctx=self.campus_ctx, s=self.session)["escalation"]
        self.assertEqual(submitted["status"], "SUBMITTED")
        self.assertTrue(self.session.query(Notification).filter(
            Notification.user_id == "user_4",
            Notification.body.like(f"%escalation:{created['id']}%")).count() >= 1)

        principal_inbox = domain_api.escalations(ctx=self.principal_ctx, s=self.session)
        principal_row = next(row for row in principal_inbox["incoming"] if row["id"] == created["id"])
        self.assertEqual(principal_row["to"], "Principal")
        self.assertEqual(principal_row["status"], "SUBMITTED")
        self.assertEqual(principal_row["title"], risk["title"])
        self.assertNotIn(created["id"], [row["id"] for row in principal_inbox["outgoing"]])

        filtered = domain_api.escalations(state="SUBMITTED", ctx=self.principal_ctx, s=self.session)
        self.assertIn(created["id"], [row["id"] for row in filtered["incoming"]])
        unrelated_inbox = domain_api.escalations(ctx=self.vc_ctx, s=self.session)
        self.assertNotIn(created["id"], [row["id"] for row in unrelated_inbox["incoming"]])

    def test_escalation_scope_and_destination_validation(self):
        risk = self.create_risk(category="Safety", severity="CRITICAL")
        with self.assertRaises(HTTPException):
            domain_api.create_escalation(domain_api.EscalationCreateIn(source_type="risk", source_ref=risk["id"], reason="bad", priority="HIGH", owner_id="user_4"), ctx={**self.campus_ctx, "scope_ref": "scope_north_campus"}, s=self.session)
        created = domain_api.create_escalation(domain_api.EscalationCreateIn(source_type="risk", source_ref=risk["id"], reason="Critical safety event", priority="CRITICAL", owner_id="user_4"), ctx=self.campus_ctx, s=self.session)["escalation"]
        self.escalation_ids.append(created["id"])
        self.assertEqual(created["destination_office_n"], 1)
        with self.assertRaises(HTTPException):
            domain_api.get_escalation(created["id"], ctx={**self.campus_ctx, "scope_ref": "scope_north_campus"}, s=self.session)
        with self.assertRaises(HTTPException):
            domain_api.create_escalation(domain_api.EscalationCreateIn(source_type="risk", source_ref=risk["id"], reason="bad", priority="HIGH", owner_id="user_36"), ctx=self.campus_ctx, s=self.session)

    def create_report(self):
        report = domain_api.create_campus_report(domain_api.ReportCreateIn(report_type="MONTHLY_CAMPUS_REPORT", period_start=date(2026, 9, 1), period_end=date(2026, 9, 30), title=f"Phase 5D report {datetime.utcnow().strftime('%H%M%S%f')}"), ctx=self.campus_ctx, s=self.session)["report"]
        self.report_ids.append(report["id"])
        self.mark(report["id"])
        return report

    def test_report_snapshot_and_vc_review_lifecycle(self):
        report = self.create_report()
        edited = domain_api.update_campus_report(report["id"], domain_api.ReportUpdateIn(title="Edited Phase 5D report"), ctx=self.campus_ctx, s=self.session)["report"]
        self.assertEqual(edited["title"], "Edited Phase 5D report")
        submitted = domain_api.submit_campus_report(report["id"], ctx=self.campus_ctx, s=self.session)["report"]
        self.workflow_ids.append(submitted["workflow_id"])
        self.assertEqual(submitted["status"], "VC_REVIEW")
        self.assertIsNotNone(submitted["snapshot"])
        with self.assertRaises(HTTPException):
            domain_api.update_campus_report(report["id"], domain_api.ReportUpdateIn(title="Blocked"), ctx=self.campus_ctx, s=self.session)
        inbox = domain_api.vc_campus_report_inbox(ctx=self.vc_ctx, s=self.session)
        self.assertIn(report["id"], [item["id"] for item in inbox["reports"]])
        returned = domain_api.return_campus_report(report["id"], domain_api.ReportFeedbackIn(feedback="Please add the VC decision request."), ctx=self.vc_ctx, s=self.session)["report"]
        self.assertEqual(returned["status"], "RETURNED")
        resubmitted = domain_api.resubmit_campus_report(report["id"], ctx=self.campus_ctx, s=self.session)["report"]
        self.workflow_ids.append(resubmitted["workflow_id"])
        self.assertEqual(resubmitted["status"], "VC_REVIEW")
        approved = domain_api.approve_campus_report(report["id"], ctx=self.vc_ctx, s=self.session)["report"]
        self.assertEqual(approved["status"], "APPROVED")
        with self.assertRaises(HTTPException):
            domain_api.update_campus_report(report["id"], domain_api.ReportUpdateIn(title="Immutable"), ctx=self.campus_ctx, s=self.session)
        snapshot = domain_api.get_campus_report_snapshot(report["id"], ctx=self.campus_ctx, s=self.session)
        payload = json.dumps(snapshot["snapshot"], sort_keys=True)
        self.assertIn("risks", payload)
        self.assertIn("unavailable", payload)
        self.assertTrue(self.session.query(AuditLog).filter(AuditLog.entity == f"report:{report['id']}").count() >= 4)
        self.assertTrue(self.session.query(Notification).filter(Notification.body.like(f"%report:{report['id']}%")).count() >= 1)

    def test_campus_head_receive_scope_and_routing_regressions(self):
        main_campus = self.session.query(OrgScope).get("scope_main_campus")
        if main_campus is None:
            self.skipTest("Main campus scope seed missing")
        self.session.add(D.Student(id=f"student_scope_main_{datetime.utcnow().strftime('%H%M%S%f')}", tenant_id=TENANT, roll_no="SMAIN01", name="Main Campus Student", email="main@example.com", dept_id=None, program_id=None, campus="Main Campus", batch="2025", semester=1, section="A", status="active", cgpa=8.5))
        self.session.add(D.Student(id=f"student_scope_north_{datetime.utcnow().strftime('%H%M%S%f')}", tenant_id=TENANT, roll_no="SNORTH01", name="North Campus Student", email="north@example.com", dept_id=None, program_id=None, campus="North Campus", batch="2025", semester=1, section="A", status="active", cgpa=7.5))
        self.session.commit()
        scoped = domain_api.list_students(ctx={**self.campus_ctx, "scope_ref": "scope_main_campus"}, s=self.session)
        self.assertTrue(scoped["students"])
        self.assertTrue(all(student.get("campus") in (None, "Main Campus") for student in scoped["students"]))
        self.assertFalse(any(student.get("campus") == "North Campus" for student in scoped["students"]))

        risk = self.create_risk(category="Operations", severity="CRITICAL")
        created = domain_api.create_escalation(domain_api.EscalationCreateIn(source_type="risk", source_ref=risk["id"], reason="Operations alert", priority="CRITICAL", owner_id="user_4"), ctx=self.campus_ctx, s=self.session)["escalation"]
        self.escalation_ids.append(created["id"])
        self.assertEqual(created["destination_office_n"], 2)

        submitted = domain_api.submit_escalation(created["id"], domain_api.Phase5DReasonIn(reason="Draft ready"), ctx=self.campus_ctx, s=self.session)["escalation"]
        self.assertEqual(submitted["status"], "SUBMITTED")
        received = domain_api.receive_escalation(created["id"], domain_api.Phase5DReasonIn(reason="Received"), ctx=self.vc_ctx, s=self.session)["escalation"]
        self.assertEqual(received["status"], "RECEIVED")

    def test_report_cross_tenant_access_is_rejected(self):
        report = self.create_report()
        with self.assertRaises(HTTPException):
            domain_api.get_campus_report(report["id"], ctx={**self.campus_ctx, "tenant_id": "other_tenant"}, s=self.session)


if __name__ == "__main__":
    unittest.main()
