import os
import sys
import unittest
from datetime import datetime

from fastapi import HTTPException

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from core import notify
from database import SessionLocal, TENANT
from models import AuditLog, Notification, OrgScope
import domain_api
import domain_models as D
import main


class Phase5ERegressionTests(unittest.TestCase):
    campus_ctx = {"sub": "user_3", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "scope_main_campus", "office_n": 3, "auth_level": "mfa"}
    principal_ctx = {"sub": "user_4", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "scope_main_campus", "office_n": 4, "auth_level": "mfa"}
    vc_ctx = {"sub": "user_2", "tenant_id": TENANT, "scope_level": "university", "scope_ref": "scope_univ", "office_n": 2, "auth_level": "mfa"}
    chairman_ctx = {"sub": "user_1", "tenant_id": TENANT, "scope_level": "university", "scope_ref": "scope_univ", "office_n": 1, "auth_level": "mfa"}

    def setUp(self):
        self.session = SessionLocal()
        self.risk_ids, self.escalation_ids, self.student_ids, self.notification_titles, self.audit_tenants = [], [], [], [], []

    def tearDown(self):
        self.session.rollback()
        self.session.query(D.EscalationEvent).filter(D.EscalationEvent.escalation_id.in_(self.escalation_ids)).delete(synchronize_session=False)
        self.session.query(D.EscalationRecord).filter(D.EscalationRecord.id.in_(self.escalation_ids)).delete(synchronize_session=False)
        self.session.query(D.RiskRecord).filter(D.RiskRecord.id.in_(self.risk_ids)).delete(synchronize_session=False)
        self.session.query(D.Student).filter(D.Student.id.in_(self.student_ids)).delete(synchronize_session=False)
        for title in self.notification_titles:
            self.session.query(Notification).filter(Notification.title == title).delete(synchronize_session=False)
        # These are dedicated disposable tenants. Removing their complete test
        # chains cannot affect the production tenant's append-only chain.
        self.session.query(AuditLog).filter(AuditLog.tenant_id.in_(self.audit_tenants)).delete(synchronize_session=False)
        self.session.commit()
        self.session.close()

    def create_risk(self, category="Student", severity="HIGH"):
        stamp = datetime.utcnow().strftime("%H%M%S%f")
        result = domain_api.create_risk(domain_api.RiskCreateIn(
            title=f"phase5e-risk-{stamp}", description="Phase 5E regression", category=category,
            severity=severity, likelihood="MEDIUM", impact="HIGH", owner_id="user_4"),
            ctx=self.campus_ctx, s=self.session)["risk"]
        self.risk_ids.append(result["id"])
        return result

    def create_submitted_escalation(self, category="Student", priority="HIGH"):
        risk = self.create_risk(category=category, severity=priority)
        created = domain_api.create_escalation(domain_api.EscalationCreateIn(
            source_type="risk", source_ref=risk["id"], reason=f"phase5e-escalation-{risk['id']}",
            priority=priority, owner_id="user_4"), ctx=self.campus_ctx, s=self.session)["escalation"]
        self.escalation_ids.append(created["id"])
        submitted = domain_api.submit_escalation(created["id"], domain_api.Phase5DReasonIn(reason="submit"), ctx=self.campus_ctx, s=self.session)["escalation"]
        return risk, submitted

    def test_destination_office_controls_receive_and_creator_cannot_close(self):
        _, escalation = self.create_submitted_escalation()
        with self.assertRaises(HTTPException) as wrong_vc:
            domain_api.receive_escalation(escalation["id"], domain_api.Phase5DReasonIn(), ctx=self.vc_ctx, s=self.session)
        self.assertEqual(wrong_vc.exception.status_code, 403)
        with self.assertRaises(HTTPException) as wrong_creator:
            domain_api.receive_escalation(escalation["id"], domain_api.Phase5DReasonIn(), ctx=self.campus_ctx, s=self.session)
        self.assertEqual(wrong_creator.exception.status_code, 403)

        received = domain_api.receive_escalation(escalation["id"], domain_api.Phase5DReasonIn(), ctx=self.principal_ctx, s=self.session)["escalation"]
        self.assertEqual(received["status"], "RECEIVED")
        resolved = domain_api.resolve_escalation(escalation["id"], domain_api.Phase5DReasonIn(reason="resolved"), ctx=self.principal_ctx, s=self.session)["escalation"]
        self.assertEqual(resolved["status"], "RESOLVED")
        with self.assertRaises(HTTPException) as close_error:
            domain_api.close_escalation(escalation["id"], domain_api.Phase5DReasonIn(reason="creator close"), ctx=self.campus_ctx, s=self.session)
        self.assertEqual(close_error.exception.status_code, 403)

    def test_tenant_and_campus_information_hiding(self):
        _, escalation = self.create_submitted_escalation()
        with self.assertRaises(HTTPException) as tenant_error:
            domain_api.get_escalation(escalation["id"], ctx={**self.campus_ctx, "tenant_id": "phase5e-other-tenant"}, s=self.session)
        self.assertEqual(tenant_error.exception.status_code, 403)
        with self.assertRaises(HTTPException) as campus_error:
            domain_api.get_escalation(escalation["id"], ctx={**self.campus_ctx, "scope_ref": "scope_north_campus"}, s=self.session)
        self.assertEqual(campus_error.exception.status_code, 404)  # intentional information hiding

    def test_critical_routing_and_required_principal_notification(self):
        _, operations = self.create_submitted_escalation(category="Operations", priority="CRITICAL")
        self.assertEqual(operations["destination_office_n"], 2)
        recipients = {row.user_id for row in self.session.query(Notification).filter(Notification.body.like(f"%escalation:{operations['id']}%")).all()}
        self.assertIn("user_2", recipients)
        self.assertIn("user_4", recipients)
        self.assertNotIn("user_1", recipients)

        _, safety = self.create_submitted_escalation(category="Safety", priority="CRITICAL")
        self.assertEqual(safety["destination_office_n"], 1)

    def test_canonical_student_scope(self):
        stamp = datetime.utcnow().strftime("%H%M%S%f")
        main_student = D.Student(id=f"phase5e-main-{stamp}", tenant_id=TENANT, roll_no=f"P5EM{stamp[-6:]}", name="Phase5E Main", email=f"main-{stamp}@example.test", campus="Main Campus", batch="2025", semester=1, section="A", status="active", cgpa=8.0)
        north_student = D.Student(id=f"phase5e-north-{stamp}", tenant_id=TENANT, roll_no=f"P5EN{stamp[-6:]}", name="Phase5E North", email=f"north-{stamp}@example.test", campus="North Campus", batch="2025", semester=1, section="A", status="active", cgpa=8.0)
        self.session.add_all([main_student, north_student]); self.session.commit()
        self.student_ids.extend([main_student.id, north_student.id])
        students = domain_api.list_students(ctx=self.campus_ctx, s=self.session)["students"]
        visible = {row["id"] for row in students}
        self.assertIn(main_student.id, visible)
        self.assertNotIn(north_student.id, visible)

    def test_audit_and_notification_tenant_isolation(self):
        stamp = datetime.utcnow().strftime("%H%M%S%f")
        tenant_a, tenant_b = f"phase5e-a-{stamp}", f"phase5e-b-{stamp}"
        self.audit_tenants.extend([tenant_a, tenant_b])
        main.write_audit(self.session, "phase5e-user", "Phase5E", 3, "phase5e.audit", f"audit-a-{stamp}", new_state="created", tenant_id=tenant_a)
        main.write_audit(self.session, "phase5e-user", "Phase5E", 3, "phase5e.audit", f"audit-b-{stamp}", new_state="created", tenant_id=tenant_b)
        audit_a = main.get_audit(ctx={"tenant_id": tenant_a}, s=self.session)["entries"]
        audit_b = main.get_audit(ctx={"tenant_id": tenant_b}, s=self.session)["entries"]
        self.assertEqual([row["entity"] for row in audit_a], [f"audit-a-{stamp}"])
        self.assertEqual([row["entity"] for row in audit_b], [f"audit-b-{stamp}"])
        self.assertTrue(main.verify_audit(ctx={"tenant_id": tenant_a}, s=self.session)["intact"])
        self.assertTrue(main.verify_audit(ctx={"tenant_id": tenant_b}, s=self.session)["intact"])

        title = f"phase5e-notification-{stamp}"; self.notification_titles.append(title)
        notify(self.session, "phase5e-user", title, "tenant A only", tenant_id=tenant_a)
        notify(self.session, "phase5e-user", title, "tenant B only", tenant_id=tenant_b)
        notifications_a = main.get_notifications(ctx={"sub": "phase5e-user", "tenant_id": tenant_a}, s=self.session)["notifications"]
        notifications_b = main.get_notifications(ctx={"sub": "phase5e-user", "tenant_id": tenant_b}, s=self.session)["notifications"]
        self.assertEqual([row["body"] for row in notifications_a], ["tenant A only"])
        self.assertEqual([row["body"] for row in notifications_b], ["tenant B only"])


if __name__ == "__main__":
    unittest.main()
