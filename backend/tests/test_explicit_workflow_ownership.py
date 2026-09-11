"""Regression coverage for the authoritative workflow-owner transition path."""
import os
import sys
import unittest
from datetime import datetime

from fastapi import HTTPException

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal
from models import Approval, AuditLog, Notification, OrgScope, Person, Tenant, User, WorkflowInstance, WorkflowProfile
import main


class ExplicitWorkflowOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.s = SessionLocal()
        self.stamp = datetime.utcnow().strftime("%H%M%S%f")
        self.tenant = f"workflow_owner_{self.stamp}"
        self.other_tenant = f"workflow_other_{self.stamp}"
        self.campus = f"scope_workflow_{self.stamp}"
        self.other_campus = f"scope_workflow_other_{self.stamp}"
        self._fixture()

    def tearDown(self):
        tenant_ids = [self.tenant, self.other_tenant]
        workflow_ids = [row[0] for row in self.s.query(WorkflowInstance.id).filter(WorkflowInstance.tenant_id.in_(tenant_ids)).all()]
        if workflow_ids:
            self.s.query(Approval).filter(Approval.workflow_id.in_(workflow_ids)).delete(synchronize_session=False)
            self.s.query(WorkflowProfile).filter(WorkflowProfile.workflow_id.in_(workflow_ids)).delete(synchronize_session=False)
        self.s.query(AuditLog).filter(AuditLog.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(Notification).filter(Notification.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(WorkflowInstance).filter(WorkflowInstance.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(User).filter(User.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(Person).filter(Person.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(OrgScope).filter(OrgScope.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(Tenant).filter(Tenant.id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.commit()
        self.s.close()

    def _user(self, tenant, label, office_n, scope_ref):
        person_id, user_id = f"person_{label}_{self.stamp}", f"user_{label}_{self.stamp}"
        self.s.add_all([
            Person(id=person_id, tenant_id=tenant, name=label, email=f"{label}@test", contact=""),
            User(id=user_id, tenant_id=tenant, person_id=person_id, username=user_id,
                 password_hash="test", status="active", mfa_enabled=True, office_n=office_n,
                 role=label, scope_level="campus", scope_ref=scope_ref),
        ])
        return user_id

    def _ctx(self, user_id, office_n, scope_ref=None, tenant=None):
        return {"sub": user_id, "tenant_id": tenant or self.tenant, "institution_id": "inst_workflow_test",
                "office_n": office_n, "scope_level": "campus", "scope_ref": scope_ref or self.campus,
                "auth_level": "mfa"}

    def _fixture(self):
        self.s.add_all([
            Tenant(id=self.tenant, institution_id="inst_workflow_test", name="Workflow test"),
            Tenant(id=self.other_tenant, institution_id="inst_workflow_test", name="Other workflow test"),
            OrgScope(id=self.campus, tenant_id=self.tenant, level="campus", name="Campus A"),
            OrgScope(id=self.other_campus, tenant_id=self.tenant, level="campus", name="Campus B"),
        ])
        self.requester = self._user(self.tenant, "requester", 3, self.campus)
        self.purchase = self._user(self.tenant, "purchase", 32, self.campus)
        self.procurement = self._user(self.tenant, "procurement", 26, self.campus)
        self.principal = self._user(self.tenant, "principal", 4, self.campus)
        self.principal_other = self._user(self.tenant, "principal_other", 4, self.other_campus)
        self.vice = self._user(self.tenant, "vice", 2, self.campus)
        self.iqac = self._user(self.tenant, "iqac", 9, self.campus)
        self.s.flush()
        self.s.commit()

    def _workflow(self, key, stage, title):
        proc = main._workflow_process(key)
        wf = WorkflowInstance(id=f"wf_{key}_{stage}_{self.stamp}_{len(title)}", tenant_id=self.tenant,
            process_key=key, label=proc["label"], office_n=proc["office_n"], title=title,
            state="submitted", initiator_id=self.requester, initiator_name="requester",
            current_stage=stage, scope_level="campus", campus_scope_id=self.campus)
        self.s.add(wf)
        main._assign_current_owner(self.s, wf, proc, require_owner=True)
        self.s.commit()
        return wf

    def test_principal_normal_reject_return_and_escalation_actions(self):
        approved = self._workflow("compliance_requirement", 2, "Principal normal approval")
        result = main.decide_workflow(main.DecideWF(workflow_id=approved.id, action="approve"), self._ctx(self.principal, 4), self.s)
        self.assertEqual(result["workflow"]["state"], "approved")

        rejected = self._workflow("compliance_requirement", 2, "Principal rejection")
        self.assertEqual(main.decide_workflow(main.DecideWF(workflow_id=rejected.id, action="reject"), self._ctx(self.principal, 4), self.s)["workflow"]["state"], "rejected")

        returned = self._workflow("compliance_requirement", 2, "Principal return")
        returned_result = main.decide_workflow(main.DecideWF(workflow_id=returned.id, action="return", reason="Clarify evidence"), self._ctx(self.principal, 4), self.s)
        self.assertEqual((returned_result["workflow"]["current_stage"], returned_result["workflow"]["current_owner_user_id"]), (1, self.iqac))

        escalated = self._workflow("compliance_requirement", 2, "Principal escalation")
        main.decide_workflow(main.DecideWF(workflow_id=escalated.id, action="escalate", reason="VC authority required"), self._ctx(self.principal, 4), self.s)
        self.assertEqual(main.get_workflow(escalated.id, self._ctx(self.principal, 4), self.s)["available_actions"], [])
        vice_view = main.get_workflow(escalated.id, self._ctx(self.vice, 2), self.s)
        self.assertEqual(vice_view["available_actions"], ["approve", "reject"])
        self.assertEqual(main.decide_workflow(main.DecideWF(workflow_id=escalated.id, action="approve"), self._ctx(self.vice, 2), self.s)["workflow"]["state"], "approved")
        history = main.get_workflow(escalated.id, self._ctx(self.vice, 2), self.s)["history"]
        self.assertIn("ESCALATE", [item["decision"] for item in history])
        self.assertEqual({row.campus_scope_id for row in self.s.query(AuditLog).filter(AuditLog.entity == f"wf:{escalated.id}")}, {self.campus})

    def test_purchase_routes_to_real_offices_and_is_scope_safe(self):
        payload = main.start_workflow(main.StartWF(process_key="purchase_request", title="Lab purchase", amount=1000), self._ctx(self.requester, 3), self.s)
        workflow_id = payload["id"]
        self.assertEqual(main.get_workflow(workflow_id, self._ctx(self.purchase, 32), self.s)["available_actions"], ["review", "approve", "reject", "return", "escalate"])
        main.decide_workflow(main.DecideWF(workflow_id=workflow_id, action="approve"), self._ctx(self.purchase, 32), self.s)
        self.assertEqual(main.get_workflow(workflow_id, self._ctx(self.procurement, 26), self.s)["current_owner_user_id"], self.procurement)
        main.decide_workflow(main.DecideWF(workflow_id=workflow_id, action="approve"), self._ctx(self.procurement, 26), self.s)
        self.assertEqual(main.get_workflow(workflow_id, self._ctx(self.principal, 4), self.s)["current_owner_user_id"], self.principal)
        with self.assertRaises(HTTPException):
            main.decide_workflow(main.DecideWF(workflow_id=workflow_id, action="approve"), self._ctx(self.principal_other, 4, self.other_campus), self.s)
        self.assertEqual(main.decide_workflow(main.DecideWF(workflow_id=workflow_id, action="approve"), self._ctx(self.principal, 4), self.s)["workflow"]["state"], "approved")
        notices = self.s.query(Notification).filter(Notification.tenant_id == self.tenant, Notification.body.like("%Lab purchase%")).all()
        self.assertTrue(any(row.user_id == self.purchase and row.severity == "action" for row in notices))
        self.assertTrue(any(row.user_id == self.procurement and row.severity == "action" for row in notices))
        self.assertTrue(any(row.user_id == self.principal and row.severity == "action" for row in notices))


if __name__ == "__main__":
    unittest.main()
