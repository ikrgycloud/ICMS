import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import DecideWF, _workflow_stage_offices, decide_workflow, get_workflow
from models import Base, Person, User, WorkflowInstance


class WorkflowStageAccessTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.session.add(Person(id="principal_person", tenant_id="t_main", name="Principal"))
        self.session.add(User(id="principal", tenant_id="t_main", person_id="principal_person",
                              username="principal", office_n=4, scope_level="campus"))
        self.session.add(WorkflowInstance(
            id="fee_request", tenant_id="t_main", process_key="fee_structure",
            label="Fee structure approval", title="Test fee structure", office_n=22,
            initiator_id="finance", initiator_name="Finance Manager", current_stage=1,
            state="submitted", scope_level="campus"))
        self.session.commit()
        self.ctx = {"sub": "principal", "tenant_id": "t_main", "office_n": 4,
                    "scope_level": "campus"}

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_principal_can_open_and_approve_fee_request(self):
        self.assertEqual(get_workflow("fee_request", self.ctx, self.session)["id"], "fee_request")
        result = decide_workflow(DecideWF(workflow_id="fee_request", action="approve"),
                                 self.ctx, self.session)
        self.assertEqual(result["decision"]["outcome"], "ALLOW")
        self.assertEqual(result["workflow"]["state"], "approved")

    def test_unrelated_office_cannot_open_or_approve(self):
        ctx = {**self.ctx, "office_n": 11}
        with self.assertRaises(HTTPException) as read_error:
            get_workflow("fee_request", ctx, self.session)
        self.assertEqual(read_error.exception.status_code, 403)
        with self.assertRaises(HTTPException) as action_error:
            decide_workflow(DecideWF(workflow_id="fee_request", action="approve"), ctx, self.session)
        self.assertEqual(action_error.exception.status_code, 403)

    def test_alternative_roles_and_specific_titles(self):
        self.assertEqual(_workflow_stage_offices({"chain": ["Principal / Campus Head"]}, 0), {3, 4})
        self.assertEqual(_workflow_stage_offices({"chain": ["Vice Principal"]}, 0), {5})
        self.assertEqual(_workflow_stage_offices({"chain": ["Unknown"]}, 0), set())

    def test_academic_coordinator_request_routes_to_hod_only(self):
        proc = {"chain": ["Academic Coordinator", "HOD"]}
        self.assertEqual(_workflow_stage_offices(proc, 1), {10})
        self.assertEqual(_workflow_stage_offices(proc, 2), set())

    def test_other_tenant_cannot_read(self):
        with self.assertRaises(HTTPException) as error:
            get_workflow("fee_request", {**self.ctx, "tenant_id": "other"}, self.session)
        self.assertEqual(error.exception.status_code, 404)
