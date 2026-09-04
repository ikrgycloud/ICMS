import json
import os
import unittest
from datetime import date
from urllib import error, request

from database import SessionLocal
import domain_models as D
from models import Approval, WorkflowInstance


class FacultyLeaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.tokens = {name: cls._login(name) for name in ("aarav_kulkarni", "hod", "vice_principal", "principal", "lecturer")}
        cls.ids = []

    @classmethod
    def tearDownClass(cls):
        for leave_id in cls.ids:
            leave = cls.db.query(D.LeaveRequest).get(leave_id)
            if leave and leave.workflow_instance_id:
                cls.db.query(Approval).filter(Approval.workflow_id == leave.workflow_instance_id).delete(synchronize_session=False)
                cls.db.query(WorkflowInstance).filter(WorkflowInstance.id == leave.workflow_instance_id).delete(synchronize_session=False)
            cls.db.query(D.LeaveRequest).filter(D.LeaveRequest.id == leave_id).delete(synchronize_session=False)
        cls.db.commit(); cls.db.close()

    @classmethod
    def _request(cls, method, path, token=None, body=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        base_url = os.environ.get("ICMS_TEST_API_URL", "http://127.0.0.1:8000")
        req = request.Request(f"{base_url}/api{path}", data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=15) as response:
                return response.status, json.loads(response.read() or b"{}")
        except error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    @classmethod
    def _login(cls, username):
        status, payload = cls._request("POST", "/auth/login", body={"username": username, "password": "demo123"})
        if status != 200:
            raise AssertionError(payload)
        return payload["token"]

    def _body(self, start="2090-01-10", end="2090-01-11", action="draft"):
        return {"kind": "Casual", "from_date": start, "to_date": end, "half_day": False, "reason": "Phase 5 verification", "action": action}

    def _create(self, body):
        status, payload = self._request("POST", "/faculty/leave-requests", self.tokens["aarav_kulkarni"], body)
        self.assertEqual(status, 200, payload)
        leave_id = payload["leave_request"]["id"]; self.ids.append(leave_id)
        return leave_id, payload["leave_request"]

    def test_draft_submit_routing_final_approval_and_guards(self):
        self.assertEqual(self._request("POST", "/faculty/leave-requests", self.tokens["aarav_kulkarni"], self._body("2090-02-12", "2090-02-10"))[0], 422)
        self.assertEqual(self._request("POST", "/faculty/leave-requests", self.tokens["vice_principal"], self._body())[0], 403)
        leave_id, draft = self._create(self._body())
        self.assertEqual(draft["status"], "draft")
        self.assertEqual(self._request("PUT", f"/faculty/leave-requests/{leave_id}", self.tokens["aarav_kulkarni"], self._body("2090-01-10", "2090-01-12", "draft"))[0], 200)
        submitted = self._request("PUT", f"/faculty/leave-requests/{leave_id}", self.tokens["aarav_kulkarni"], self._body("2090-01-10", "2090-01-12", "submit"))[1]["leave_request"]
        self.assertEqual(submitted["status"], "submitted")
        self.assertEqual(self._request("POST", f"/faculty/leave-requests/{leave_id}/decide", self.tokens["vice_principal"], {"action": "approve"})[0], 403)
        self.assertEqual(self._request("POST", f"/faculty/leave-requests/{leave_id}/decide", self.tokens["aarav_kulkarni"], {"action": "approve"})[0], 403)
        self.assertEqual(self._request("POST", f"/faculty/leave-requests/{leave_id}/decide", self.tokens["hod"], {"action": "approve"})[1]["leave_request"]["current_stage"], 2)
        self.assertEqual(self._request("POST", f"/faculty/leave-requests/{leave_id}/decide", self.tokens["hod"], {"action": "approve"})[0], 403)
        self.assertEqual(self._request("POST", f"/faculty/leave-requests/{leave_id}/decide", self.tokens["vice_principal"], {"action": "approve"})[1]["leave_request"]["current_stage"], 3)
        final = self._request("POST", f"/faculty/leave-requests/{leave_id}/decide", self.tokens["principal"], {"action": "approve"})[1]["leave_request"]
        self.assertEqual(final["status"], "approved")
        self.assertGreaterEqual(len(final["history"]), 3)
        self.assertEqual(self._request("POST", f"/faculty/leave-requests/{leave_id}/decide", self.tokens["principal"], {"action": "approve"})[0], 409)
        self.assertEqual(self._request("PUT", f"/faculty/leave-requests/{leave_id}", self.tokens["aarav_kulkarni"], self._body(action="draft"))[0], 409)

    def test_overlap_return_resubmit_reject_and_inbox_scope(self):
        leave_id, _ = self._create(self._body("2090-03-10", "2090-03-11", "submit"))
        self.assertEqual(self._request("POST", "/faculty/leave-requests", self.tokens["aarav_kulkarni"], self._body("2090-03-11", "2090-03-12", "submit"))[0], 409)
        returned = self._request("POST", f"/faculty/leave-requests/{leave_id}/decide", self.tokens["hod"], {"action": "return", "comment": "Provide handover details."})[1]["leave_request"]
        workflow_id = returned["workflow_instance_id"]
        self.assertEqual(returned["status"], "returned")
        self.assertEqual(returned["reviewer_comment"], "Provide handover details.")
        resubmitted = self._request("PUT", f"/faculty/leave-requests/{leave_id}", self.tokens["aarav_kulkarni"], self._body("2090-03-10", "2090-03-11", "resubmit"))[1]["leave_request"]
        self.assertEqual(resubmitted["workflow_instance_id"], workflow_id)
        self.assertEqual(resubmitted["current_stage"], 1)
        self.assertEqual(resubmitted["reviewer_comment"], "Provide handover details.")
        inbox = self._request("GET", "/faculty/leave-requests?scope=inbox", self.tokens["hod"])[1]["leave_requests"]
        self.assertIn(leave_id, [row["id"] for row in inbox])
        self.assertNotIn(leave_id, [row["id"] for row in self._request("GET", "/faculty/leave-requests?scope=inbox", self.tokens["vice_principal"])[1]["leave_requests"]])
        rejected_id, _ = self._create(self._body("2090-04-10", "2090-04-10", "submit"))
        rejected = self._request("POST", f"/faculty/leave-requests/{rejected_id}/decide", self.tokens["hod"], {"action": "reject", "comment": "Teaching coverage is unavailable."})[1]["leave_request"]
        self.assertEqual(rejected["status"], "rejected")
        mine = self._request("GET", "/faculty/leave-requests?scope=mine", self.tokens["aarav_kulkarni"])[1]["leave_requests"]
        self.assertEqual(sum(row["id"] == leave_id for row in mine), 1)


