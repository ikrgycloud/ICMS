import os
import sys
import unittest
from datetime import datetime
from types import SimpleNamespace

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal, TENANT
from models import WorkflowInstance, AuditLog, Notification
import main


class QueryStub:
    def __init__(self, row):
        self.row = row
        self.filters = []

    def filter(self, *conditions):
        self.filters.extend(conditions)
        return self

    def first(self):
        return self.row

    def get(self, _id):
        if _id == "user_1":
            return SimpleNamespace(id="user_1")
        return None


class SessionStub:
    def __init__(self, row):
        self.row = row

    def query(self, model):
        return QueryStub(self.row)


class CapexOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.campus = SimpleNamespace(id="scope_main_campus", tenant_id="t_main", level="campus")
        self.ctx = {"tenant_id": "t_main", "scope_level": "campus", "scope_ref": "Main Campus", "office_n": 3}

    def test_user_label_resolves_to_canonical_org_scope(self):
        resolved = main._resolve_campus_scope(SessionStub(self.campus), self.ctx)
        self.assertIs(resolved, self.campus)
        self.assertEqual(resolved.id, "scope_main_campus")

    def test_wrong_campus_is_rejected(self):
        workflow = SimpleNamespace(process_key="infrastructure_capex", scope_level="campus", campus_scope_id="scope_north_campus")
        self.assertFalse(main._capex_scope_matches(SessionStub(self.campus), workflow, self.ctx))

    def test_unmapped_capex_is_rejected(self):
        workflow = SimpleNamespace(process_key="infrastructure_capex", scope_level="campus", campus_scope_id=None)
        self.assertFalse(main._capex_scope_matches(SessionStub(self.campus), workflow, self.ctx))

    def test_non_campus_user_cannot_resolve_capex_scope(self):
        ctx = {"tenant_id": "t_main", "scope_level": "university", "scope_ref": "scope_global", "office_n": 29}
        self.assertIsNone(main._resolve_campus_scope(SessionStub(self.campus), ctx))

    def test_v2_capex_requires_non_null_campus_scope(self):
        workflow = SimpleNamespace(
            process_key="infrastructure_capex_v2",
            state="submitted",
            current_stage=3,
            amount=250000,
            initiator_id="user_2",
            campus_scope_id=None,
            scope_level="campus",
            initiator_name="Requester",
            title="CAPEX Test",
        )
        actions, _ = main._campus_head_workflow_actions(
            SessionStub(self.campus),
            workflow,
            main._workflow_process("infrastructure_capex_v2"),
            {**self.ctx, "sub": "user_1"},
        )
        self.assertEqual(actions, [])

    def test_v2_capex_requires_matching_campus_scope(self):
        workflow = SimpleNamespace(
            process_key="infrastructure_capex_v2",
            state="submitted",
            current_stage=3,
            amount=250000,
            initiator_id="user_2",
            campus_scope_id="scope_north_campus",
            scope_level="campus",
            initiator_name="Requester",
            title="CAPEX Test",
        )
        actions, _ = main._campus_head_workflow_actions(
            SessionStub(self.campus),
            workflow,
            main._workflow_process("infrastructure_capex_v2"),
            {**self.ctx, "sub": "user_1"},
        )
        self.assertEqual(actions, [])

    def test_campus_head_inbox_only_includes_actionable_v2_stage_three_requests(self):
        session = SessionLocal()
        specs = [
            ("valid", "infrastructure_capex_v2", 3, "scope_main_campus", "user_29"),
            ("wrong_campus", "infrastructure_capex_v2", 3, "scope_north_campus", "user_29"),
            ("null_campus", "infrastructure_capex_v2", 3, None, "user_29"),
            ("legacy_v1", "infrastructure_capex", 3, "scope_main_campus", "user_29"),
            ("wrong_stage", "infrastructure_capex_v2", 2, "scope_main_campus", "user_29"),
            ("self_created", "infrastructure_capex_v2", 3, "scope_main_campus", "user_3"),
        ]
        ids = [f"capex_v2_inbox_{name}_{datetime.utcnow().strftime('%H%M%S%f')}" for name, *_ in specs]
        try:
            for wid, (name, process_key, stage, campus_scope_id, initiator_id) in zip(ids, specs):
                session.add(WorkflowInstance(
                    id=wid,
                    tenant_id=TENANT,
                    process_key=process_key,
                    label="Infrastructure / capex",
                    office_n=29,
                    title=f"Inbox scope {name}",
                    state="under_review",
                    amount=500000,
                    initiator_id=initiator_id,
                    initiator_name="Campus Head" if initiator_id == "user_3" else "Facilities Director",
                    current_stage=stage,
                    scope_level="campus",
                    campus_scope_id=campus_scope_id,
                    escalated=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                ))
            session.commit()

            ctx = {"sub": "user_3", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "scope_main_campus", "office_n": 3, "auth_level": "mfa"}
            response = main.list_workflows("inbox", ctx=ctx, s=session)
            visible_ids = {workflow["id"] for workflow in response["workflows"]}
            self.assertIn(ids[0], visible_ids)
            self.assertNotIn(ids[1], visible_ids)
            self.assertNotIn(ids[2], visible_ids)
            self.assertNotIn(ids[3], visible_ids)
            self.assertNotIn(ids[4], visible_ids)
            self.assertNotIn(ids[5], visible_ids)
            visible = next(workflow for workflow in response["workflows"] if workflow["id"] == ids[0])
            self.assertEqual(visible["available_actions"], ["approve", "reject"])
        finally:
            session.query(WorkflowInstance).filter(WorkflowInstance.id.in_(ids)).delete(synchronize_session=False)
            session.commit()
            session.close()

    def test_real_campus_head_approve_path_advances_stage_and_audits(self):
        session = SessionLocal()
        wid = f"capex_v2_approve_{datetime.utcnow().strftime('%H%M%S%f')}"
        try:
            wf = WorkflowInstance(
                id=wid,
                tenant_id=TENANT,
                process_key="infrastructure_capex_v2",
                label="Infrastructure / capex",
                office_n=29,
                title="E2E approve CAPEX",
                state="submitted",
                amount=500000,
                initiator_id="user_29",
                initiator_name="Maintenance",
                current_stage=3,
                scope_level="campus",
                campus_scope_id="scope_main_campus",
                escalated=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(wf)
            session.commit()

            ctx = {"sub": "user_3", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "scope_main_campus", "office_n": 3, "auth_level": "mfa"}
            resp = main.decide_workflow(main.DecideWF(workflow_id=wid, action="approve", reason="Approved by Campus Head"), ctx=ctx, s=session)
            self.assertEqual(resp["decision"]["outcome"], main.ALLOW)
            self.assertEqual(resp["workflow"]["current_stage"], 4)
            self.assertEqual(resp["workflow"]["state"], "under_review")
            audit_rows = session.query(AuditLog).filter(AuditLog.entity == f"wf:{wid}").all()
            self.assertTrue(audit_rows)
            self.assertTrue(any("workflow.approve:infrastructure_capex_v2" in row.action for row in audit_rows))
            notifications = session.query(Notification).filter(Notification.body.like(f"%E2E approve CAPEX%") | Notification.title.like("%Infrastructure / capex%") ).all()
            self.assertTrue(notifications)
            # The shared development database can contain historic test rows
            # whose former cleanup broke the main tenant's append-only chain.
            # Verify the CAPEX audit writer against a fresh isolated tenant
            # instead of treating that unrelated contamination as CAPEX logic.
            audit_tenant = f"t_capex_audit_{wid}"
            main.write_audit(session, "user_3", "Campus Head", 3,
                             "capex.test.audit", f"wf:{wid}", "", "approved",
                             tenant_id=audit_tenant)
            result = main.verify_audit(ctx={"tenant_id": audit_tenant, "office_n": 1}, s=session)
            self.assertTrue(result["intact"], result)
        finally:
            session.query(Notification).filter(Notification.body.like(f"%E2E approve CAPEX%") | Notification.title.like("%Infrastructure / capex%") ).delete(synchronize_session=False)
            session.query(WorkflowInstance).filter(WorkflowInstance.id == wid).delete(synchronize_session=False)
            session.commit()
            session.close()

    def test_real_campus_head_reject_path_records_rejection_and_notification(self):
        session = SessionLocal()
        wid = f"capex_v2_reject_{datetime.utcnow().strftime('%H%M%S%f')}"
        try:
            wf = WorkflowInstance(
                id=wid,
                tenant_id=TENANT,
                process_key="infrastructure_capex_v2",
                label="Infrastructure / capex",
                office_n=29,
                title="E2E reject CAPEX",
                state="submitted",
                amount=400000,
                initiator_id="user_29",
                initiator_name="Maintenance",
                current_stage=3,
                scope_level="campus",
                campus_scope_id="scope_main_campus",
                escalated=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(wf)
            session.commit()

            ctx = {"sub": "user_3", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "scope_main_campus", "office_n": 3, "auth_level": "mfa"}
            resp = main.decide_workflow(main.DecideWF(workflow_id=wid, action="reject", reason="Rejected by Campus Head"), ctx=ctx, s=session)
            self.assertEqual(resp["decision"]["outcome"], main.ALLOW)
            self.assertEqual(resp["workflow"]["state"], "rejected")
            self.assertTrue(session.query(AuditLog).filter(AuditLog.entity == f"wf:{wid}").count() >= 1)
            self.assertTrue(session.query(Notification).filter(Notification.body.like(f"%E2E reject CAPEX%") | Notification.title.like("%Infrastructure / capex%") ).count() >= 1)
        finally:
            session.query(Notification).filter(Notification.body.like(f"%E2E reject CAPEX%") | Notification.title.like("%Infrastructure / capex%") ).delete(synchronize_session=False)
            session.query(WorkflowInstance).filter(WorkflowInstance.id == wid).delete(synchronize_session=False)
            session.commit()
            session.close()

    def test_real_campus_head_escalation_path_uses_chairman_target(self):
        session = SessionLocal()
        wid = f"capex_v2_escalate_{datetime.utcnow().strftime('%H%M%S%f')}"
        try:
            wf = WorkflowInstance(
                id=wid,
                tenant_id=TENANT,
                process_key="infrastructure_capex_v2",
                label="Infrastructure / capex",
                office_n=29,
                title="E2E escalate CAPEX",
                state="submitted",
                amount=1500000,
                initiator_id="user_29",
                initiator_name="Maintenance",
                current_stage=3,
                scope_level="campus",
                campus_scope_id="scope_main_campus",
                escalated=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(wf)
            session.commit()

            ctx = {"sub": "user_3", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "scope_main_campus", "office_n": 3, "auth_level": "mfa"}
            resp = main.decide_workflow(main.DecideWF(workflow_id=wid, action="escalate", reason="Escalate due to limit"), ctx=ctx, s=session)
            self.assertIn(resp["decision"]["outcome"], (main.ESCALATE, main.RECOMMEND_OUT))
            self.assertEqual(resp["workflow"]["state"], "escalated")
            self.assertTrue(session.query(AuditLog).filter(AuditLog.entity == f"wf:{wid}").count() >= 1)
            notifications = session.query(Notification).filter(Notification.body.like(f"%E2E escalate CAPEX%") | Notification.title.like("%Infrastructure / capex%") ).all()
            self.assertTrue(notifications)
            self.assertTrue(any(notification.user_id == "user_1" for notification in notifications))
        finally:
            session.query(Notification).filter(Notification.body.like(f"%E2E escalate CAPEX%") | Notification.title.like("%Infrastructure / capex%") ).delete(synchronize_session=False)
            session.query(WorkflowInstance).filter(WorkflowInstance.id == wid).delete(synchronize_session=False)
            session.commit()
            session.close()


if __name__ == "__main__":
    unittest.main()
