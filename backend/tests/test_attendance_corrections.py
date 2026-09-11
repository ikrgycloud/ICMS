import json
import os
import unittest
from datetime import date, datetime, timedelta
from urllib import error, request

from database import SessionLocal, TENANT
import domain_models as D
from models import Approval, AuditLog, WorkflowInstance


class AttendanceCorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.tokens = {name: cls._login(name) for name in (
            "aarav_kulkarni", "assistant_professor", "hod", "vice_principal", "lecturer", "professor"
        )}
        cls.session_id = "verify_phase2_session"
        cls.record_id = "verify_phase2_attendance"
        cls._fixture()

    @classmethod
    def tearDownClass(cls):
        cls._delete_fixture_corrections()
        cls.db.query(D.AttendanceRecord).filter(D.AttendanceRecord.id == cls.record_id).delete(synchronize_session=False)
        cls.db.query(D.ClassSession).filter(D.ClassSession.id == cls.session_id).delete(synchronize_session=False)
        cls.db.commit(); cls.db.close()

    @classmethod
    def _delete_fixture_corrections(cls):
        workflow_ids = [row[0] for row in cls.db.query(D.AttendanceCorrectionRequest.workflow_instance_id)
                        .filter(D.AttendanceCorrectionRequest.attendance_record_id == cls.record_id).all()]
        cls.db.query(D.AttendanceCorrectionRequest).filter(D.AttendanceCorrectionRequest.attendance_record_id == cls.record_id).delete(synchronize_session=False)
        if workflow_ids:
            cls.db.query(Approval).filter(Approval.workflow_id.in_(workflow_ids)).delete(synchronize_session=False)
            cls.db.query(WorkflowInstance).filter(WorkflowInstance.id.in_(workflow_ids)).delete(synchronize_session=False)

    @classmethod
    def _fixture(cls):
        allocation = (cls.db.query(D.TeachingAllocation)
                      .join(D.FacultyFunctionalAssignment,
                            D.FacultyFunctionalAssignment.scope_ref == D.TeachingAllocation.section_id)
                      .join(D.StaffMember, D.StaffMember.id == D.FacultyFunctionalAssignment.faculty_id)
                      .filter(D.TeachingAllocation.faculty_id == "staff_fac_1",
                              D.TeachingAllocation.status == "active",
                              D.FacultyFunctionalAssignment.role_key == "course_coordinator",
                              D.FacultyFunctionalAssignment.scope_type == "section",
                              D.FacultyFunctionalAssignment.status == "active",
                              D.StaffMember.user_id == "user_13")
                      .first())
        if not allocation:
            raise AssertionError("Aarav has no active allocation with the seeded Class Coordinator")
        section = cls.db.query(D.Section).get(allocation.section_id)
        enrollment = cls.db.query(D.Enrollment).filter(D.Enrollment.section_id == section.id, D.Enrollment.status == "enrolled").first()
        cls._delete_fixture_corrections()
        cls.db.query(D.AttendanceRecord).filter(D.AttendanceRecord.id == cls.record_id).delete(synchronize_session=False)
        cls.db.query(D.ClassSession).filter(D.ClassSession.id == cls.session_id).delete(synchronize_session=False)
        now = datetime.utcnow()
        cls.db.add(D.ClassSession(id=cls.session_id, tenant_id=TENANT, allocation_id=allocation.id, section_id=section.id, faculty_id=allocation.faculty_id, session_date=date.today(), scheduled_start=now-timedelta(hours=2), scheduled_end=now-timedelta(hours=1), checked_in_at=now-timedelta(hours=2), finalized_at=now-timedelta(hours=1), status="attendance_finalized"))
        cls.db.add(D.AttendanceRecord(id=cls.record_id, tenant_id=TENANT, section_id=section.id, student_id=enrollment.student_id, class_session_id=cls.session_id, on_date=date.today(), present=True, status="present", finalized_at=now-timedelta(hours=1)))
        cls.db.commit()

    @classmethod
    def _request(cls, method, path, token=None, body=None):
        raw = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if token: headers["Authorization"] = f"Bearer {token}"
        base_url = os.environ.get("ICMS_TEST_API_URL", "http://127.0.0.1:8000")
        req = request.Request(f"{base_url}/api{path}", data=raw, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=15) as response:
                return response.status, json.loads(response.read() or b"{}")
        except error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    @classmethod
    def _login(cls, username):
        status, payload = cls._request("POST", "/auth/login", body={"username": username, "password": "demo123"})
        if status != 200: raise AssertionError(payload)
        return payload["token"]

    def _create(self):
        return self._request("POST", "/attendance/corrections", self.tokens["aarav_kulkarni"], {"attendance_record_id": self.record_id, "requested_status": "absent", "reason": "Verification correction"})

    def setUp(self):
        self._fixture()

    def test_final_correction_workflow_and_guards(self):
        status, payload = self._create(); self.assertEqual(status, 200, payload)
        correction = payload["correction"]; cid = correction["id"]
        self.assertEqual(self.db.query(D.AttendanceRecord).get(self.record_id).status, "present")
        self.assertEqual(self._request("POST", "/attendance/corrections", self.tokens["aarav_kulkarni"], {"attendance_record_id": self.record_id, "requested_status":"absent", "reason":"duplicate"})[0], 409)
        self.assertEqual(self._request("POST", f"/attendance/corrections/{cid}/decide", self.tokens["hod"], {"action":"approve"})[0], 403)
        self.assertEqual(self._request("POST", f"/attendance/corrections/{cid}/decide", self.tokens["vice_principal"], {"action":"approve"})[0], 403)
        self.assertEqual(self._request("POST", f"/attendance/corrections/{cid}/decide", self.tokens["lecturer"], {"action":"approve"})[0], 403)
        self.assertEqual(self._request("POST", f"/attendance/corrections/{cid}/decide", self.tokens["assistant_professor"], {"action":"approve"})[0], 200)
        self.assertEqual(self.db.query(D.AttendanceRecord).get(self.record_id).status, "present")
        self.assertEqual(self._request("POST", f"/attendance/corrections/{cid}/decide", self.tokens["hod"], {"action":"approve"})[0], 200)
        status, result = self._request("POST", f"/attendance/corrections/{cid}/decide", self.tokens["vice_principal"], {"action":"approve"}); self.assertEqual(status, 200, result)
        self.db.expire_all(); self.assertEqual(self.db.query(D.AttendanceRecord).get(self.record_id).status, "absent")
        self.assertEqual(result["correction"]["status"], "applied")
        self.assertEqual(self._request("POST", f"/attendance/corrections/{cid}/decide", self.tokens["vice_principal"], {"action":"approve"})[0], 409)
        status, mine = self._request("GET", "/attendance/corrections?scope=mine", self.tokens["aarav_kulkarni"])
        self.assertEqual(status, 200); self.assertEqual(next(item for item in mine["corrections"] if item["id"] == cid)["status"], "applied")
        status, workflows = self._request("GET", "/workflows?scope=mine", self.tokens["aarav_kulkarni"])
        self.assertEqual(status, 200, workflows)
        linked = [item for item in workflows["workflows"] if item["id"] == correction["workflow_instance_id"]]
        student = self.db.query(D.Student).get(self.db.query(D.AttendanceRecord).get(self.record_id).student_id)
        self.assertEqual(len(linked), 1); self.assertEqual(linked[0]["request_student"], student.name)
        audit = self.db.query(AuditLog).filter(AuditLog.entity == f"correction:{cid}").all()
        self.assertTrue(any(row.prev_state == "present" and row.new_state == "absent" for row in audit))

    def test_request_validation_guards(self):
        self.assertEqual(self._request("POST", "/attendance/corrections", self.tokens["aarav_kulkarni"], {"attendance_record_id": self.record_id, "requested_status":"present", "reason":"same"})[0], 422)
        self.assertEqual(self._request("POST", "/attendance/corrections", self.tokens["aarav_kulkarni"], {"attendance_record_id": self.record_id, "requested_status":"absent", "reason":""})[0], 422)
        self.assertEqual(self._request("POST", "/attendance/corrections", self.tokens["professor"], {"attendance_record_id": self.record_id, "requested_status":"absent", "reason":"other professor"})[0], 403)
        record = self.db.query(D.AttendanceRecord).get(self.record_id)
        session = self.db.query(D.ClassSession).get(self.session_id)
        record.finalized_at = None; session.status = "checked_in"; self.db.commit()
        self.assertEqual(self._request("POST", "/attendance/corrections", self.tokens["aarav_kulkarni"], {"attendance_record_id": self.record_id, "requested_status":"absent", "reason":"not finalized"})[0], 409)

    def test_returned_request_can_be_edited_and_resubmitted(self):
        status, payload = self._create(); self.assertEqual(status, 200, payload)
        cid = payload["correction"]["id"]
        status, returned = self._request("POST", f"/attendance/corrections/{cid}/decide", self.tokens["assistant_professor"], {"action":"return", "comment":"Please clarify the correction."})
        self.assertEqual(status, 200, returned); self.assertEqual(returned["correction"]["status"], "returned")
        status, updated = self._request("PUT", f"/attendance/corrections/{cid}", self.tokens["aarav_kulkarni"], {"attendance_record_id": self.record_id, "requested_status":"absent", "reason":"Clarified correction reason"})
        self.assertEqual(status, 200, updated)
        status, resubmitted = self._request("POST", f"/attendance/corrections/{cid}/resubmit", self.tokens["aarav_kulkarni"])
        self.assertEqual(status, 200, resubmitted); self.assertEqual(resubmitted["correction"]["status"], "submitted")


