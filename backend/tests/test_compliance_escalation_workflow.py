import os
import sys
import unittest
from datetime import datetime

from fastapi import HTTPException

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal
from models import Approval, AuditLog, Notification, OrgScope, Person, Tenant, User, WorkflowInstance
import domain_models as D
import main


class ComplianceEscalationWorkflowTests(unittest.TestCase):
    """Principal-to-governance compliance escalation is tenant and campus safe."""

    def setUp(self):
        self.s = SessionLocal()
        self.stamp = datetime.utcnow().strftime("%H%M%S%f")
        self.tenant_a, self.tenant_b = f"comp_a_{self.stamp}", f"comp_b_{self.stamp}"
        self.scope_a = f"scope_comp_a_{self.stamp}"
        self.scope_a_other = f"scope_comp_a_other_{self.stamp}"
        self.scope_b = f"scope_comp_b_{self.stamp}"
        self._fixture()

    def tearDown(self):
        self.s.rollback()
        tenant_ids = (self.tenant_a, self.tenant_b)
        workflow_ids = [row[0] for row in self.s.query(WorkflowInstance.id).filter(WorkflowInstance.tenant_id.in_(tenant_ids)).all()]
        if workflow_ids:
            self.s.query(Approval).filter(Approval.workflow_id.in_(workflow_ids)).delete(synchronize_session=False)
        self.s.query(AuditLog).filter(AuditLog.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(Notification).filter(Notification.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(D.ComplianceRequirement).filter(D.ComplianceRequirement.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(WorkflowInstance).filter(WorkflowInstance.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(User).filter(User.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(Person).filter(Person.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(OrgScope).filter(OrgScope.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(Tenant).filter(Tenant.id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.commit()
        self.s.close()

    def _user(self, tenant_id, key, office_n, scope_level, scope_ref):
        person_id, user_id = f"person_{key}_{self.stamp}", f"user_{key}_{self.stamp}"
        self.s.add_all([
            Person(id=person_id, tenant_id=tenant_id, name=key, email=f"{key}@test", contact=""),
            User(id=user_id, tenant_id=tenant_id, person_id=person_id, username=user_id,
                 password_hash="test", status="active", mfa_enabled=True, office_n=office_n,
                 role=key, scope_level=scope_level, scope_ref=scope_ref),
        ])
        return user_id

    def _ctx(self, user_id, tenant_id, office_n, scope_level, scope_ref):
        return {"sub": user_id, "tenant_id": tenant_id, "institution_id": "inst_compliance_test",
                "office_n": office_n, "scope_level": scope_level, "scope_ref": scope_ref,
                "auth_level": "mfa"}

    def _fixture(self):
        self.s.add_all([
            Tenant(id=self.tenant_a, institution_id="inst_compliance_test", name="Compliance A"),
            Tenant(id=self.tenant_b, institution_id="inst_compliance_test", name="Compliance B"),
            OrgScope(id=self.scope_a, tenant_id=self.tenant_a, level="campus", name="Campus A"),
            OrgScope(id=self.scope_a_other, tenant_id=self.tenant_a, level="campus", name="Campus A Other"),
            OrgScope(id=self.scope_b, tenant_id=self.tenant_b, level="campus", name="Campus B"),
        ])
        self.principal_a = self._user(self.tenant_a, "principal_a", 4, "campus", self.scope_a)
        self.principal_a_other = self._user(self.tenant_a, "principal_a_other", 4, "campus", self.scope_a_other)
        self.vice_a = self._user(self.tenant_a, "vice_a", 2, "university", "scope_university")
        self.vice_b = self._user(self.tenant_b, "vice_b", 2, "university", "scope_university")
        self.initiator_a = self._user(self.tenant_a, "initiator_a", 9, "university", "scope_university")
        self.principal_b = self._user(self.tenant_b, "principal_b", 4, "campus", self.scope_b)
        self.s.flush()
        self.workflow_a = f"wf_comp_a_{self.stamp}"
        self.workflow_a_other = f"wf_comp_a_other_{self.stamp}"
        self.workflow_b = f"wf_comp_b_{self.stamp}"
        self.s.add_all([
            WorkflowInstance(id=self.workflow_a, tenant_id=self.tenant_a, process_key="compliance_requirement",
                label="Compliance requirement", office_n=4, title="Tenant A compliance", state="submitted",
                initiator_id=self.initiator_a, initiator_name="Initiator A", current_stage=2,
                scope_level="campus", campus_scope_id=self.scope_a),
            WorkflowInstance(id=self.workflow_a_other, tenant_id=self.tenant_a, process_key="compliance_requirement",
                label="Compliance requirement", office_n=4, title="Other campus compliance", state="submitted",
                initiator_id=self.initiator_a, initiator_name="Initiator A", current_stage=2,
                scope_level="campus", campus_scope_id=self.scope_a_other),
            WorkflowInstance(id=self.workflow_b, tenant_id=self.tenant_b, process_key="compliance_requirement",
                label="Compliance requirement", office_n=4, title="Tenant B compliance", state="submitted",
                initiator_id=self.principal_b, initiator_name="Principal B", current_stage=2,
                scope_level="campus", campus_scope_id=self.scope_b),
            D.ComplianceRequirement(id=f"requirement_a_{self.stamp}", tenant_id=self.tenant_a,
                campus="Campus A", campus_scope_id=self.scope_a, reference_code=f"COMP-A-{self.stamp}",
                title="Tenant A compliance", workflow_id=self.workflow_a),
        ])
        self.s.commit()

    def test_principal_escalation_transfers_to_vc_and_preserves_scope(self):
        principal_ctx = self._ctx(self.principal_a, self.tenant_a, 4, "campus", self.scope_a)
        vice_ctx = self._ctx(self.vice_a, self.tenant_a, 2, "university", "scope_university")

        escalated = main.decide_workflow(
            main.DecideWF(workflow_id=self.workflow_a, action="escalate", reason="Needs VC decision"),
            ctx=principal_ctx, s=self.s,
        )
        workflow = self.s.get(WorkflowInstance, self.workflow_a)
        self.assertEqual((workflow.state, workflow.current_stage, workflow.escalated, workflow.campus_scope_id),
                         ("escalated", 3, True, self.scope_a))
        self.assertEqual(escalated["workflow"]["available_actions"], [])

        principal_inbox = main.list_workflows(scope="inbox", ctx=principal_ctx, s=self.s)["workflows"]
        self.assertNotIn(self.workflow_a, {row["id"] for row in principal_inbox})
        vice_inbox = main.list_workflows(scope="inbox", ctx=vice_ctx, s=self.s)["workflows"]
        vice_row = next(row for row in vice_inbox if row["id"] == self.workflow_a)
        self.assertEqual(vice_row["available_actions"], ["approve", "reject"])
        self.assertEqual(vice_row["current_stage"], 3)

        with self.assertRaises(HTTPException) as principal_denied:
            main.decide_workflow(main.DecideWF(workflow_id=self.workflow_a, action="escalate"), ctx=principal_ctx, s=self.s)
        self.assertEqual(principal_denied.exception.status_code, 403)

        notifications = self.s.query(Notification).filter(Notification.tenant_id == self.tenant_a).all()
        self.assertTrue(any(row.user_id == self.vice_a and "awaiting Vice Chairman" in row.body for row in notifications))
        self.assertFalse(any(row.user_id == self.principal_a and "awaiting Principal" in row.body for row in notifications))
        self.assertFalse(any(row.user_id == self.vice_b for row in notifications))

        completed = main.decide_workflow(
            main.DecideWF(workflow_id=self.workflow_a, action="approve", reason="Approved by VC"),
            ctx=vice_ctx, s=self.s,
        )
        workflow = self.s.get(WorkflowInstance, self.workflow_a)
        self.assertEqual((workflow.state, workflow.current_stage), ("approved", 4))
        self.assertEqual(completed["decision"]["outcome"], "ALLOW")
        audit_rows = self.s.query(AuditLog).filter(AuditLog.entity == f"wf:{self.workflow_a}").all()
        self.assertEqual({row.campus_scope_id for row in audit_rows}, {self.scope_a})

    def test_principal_workflow_reads_fail_closed_by_tenant_and_campus(self):
        principal_a_ctx = self._ctx(self.principal_a, self.tenant_a, 4, "campus", self.scope_a)
        all_rows = main.list_workflows(scope="all", ctx=principal_a_ctx, s=self.s)["workflows"]
        visible = {row["id"] for row in all_rows}
        self.assertIn(self.workflow_a, visible)
        self.assertNotIn(self.workflow_a_other, visible)
        self.assertNotIn(self.workflow_b, visible)
        with self.assertRaises(HTTPException) as cross_campus:
            main.get_workflow(self.workflow_a_other, ctx=principal_a_ctx, s=self.s)
        self.assertEqual(cross_campus.exception.status_code, 403)
        with self.assertRaises(HTTPException) as cross_tenant:
            main.get_workflow(self.workflow_b, ctx=principal_a_ctx, s=self.s)
        self.assertEqual(cross_tenant.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
