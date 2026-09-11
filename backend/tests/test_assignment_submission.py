import json
import os
import unittest
from datetime import datetime, timedelta
from urllib import error, request

from database import SessionLocal, TENANT
import domain_models as D
from models import User


class AssignmentSubmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.tokens = {name: cls._login(name) for name in ("aarav_kulkarni", "lecturer")}
        staff = cls.db.query(D.StaffMember).filter(D.StaffMember.id == "staff_fac_1").one()
        allocation = next(row for row in cls.db.query(D.TeachingAllocation).filter(D.TeachingAllocation.faculty_id == staff.id, D.TeachingAllocation.status == "active").all() if cls.db.query(D.Enrollment).filter(D.Enrollment.section_id == row.section_id, D.Enrollment.status == "enrolled").count())
        cls.section_id = allocation.section_id
        cls.test_student = cls.db.query(D.Student).filter(D.Student.user_id == "user_36").one()
        cls.test_enrollment_id = "test_phase4_enrollment"
        if not cls.db.query(D.Enrollment).get(cls.test_enrollment_id):
            cls.db.add(D.Enrollment(id=cls.test_enrollment_id, tenant_id=TENANT, student_id=cls.test_student.id, section_id=cls.section_id, status="enrolled")); cls.db.commit()
        cls.students = [cls.test_student.id]
        cls.enrolled_count = cls.db.query(D.Enrollment).filter(D.Enrollment.section_id == cls.section_id, D.Enrollment.status == "enrolled").count()
        cls.assignment_id = "test_phase4_assignment"
        cls.student_users = {cls.test_student.id: "25ECE072"}

    @classmethod
    def tearDownClass(cls):
        ids = [row[0] for row in cls.db.query(D.AssignmentSubmission.id).filter(D.AssignmentSubmission.assignment_id == cls.assignment_id).all()]
        if ids: cls.db.query(D.AssignmentEvaluation).filter(D.AssignmentEvaluation.submission_id.in_(ids)).delete(synchronize_session=False)
        cls.db.query(D.AssignmentSubmission).filter(D.AssignmentSubmission.assignment_id == cls.assignment_id).delete(synchronize_session=False)
        cls.db.query(D.Assignment).filter(D.Assignment.id == cls.assignment_id).delete(synchronize_session=False)
        cls.db.query(D.Enrollment).filter(D.Enrollment.id == cls.test_enrollment_id).delete(synchronize_session=False)
        cls.db.commit(); cls.db.close()

    @classmethod
    def _request(cls, method, path, token=None, body=None):
        headers = {"Content-Type": "application/json"}
        if token: headers["Authorization"] = f"Bearer {token}"
        base_url = os.environ.get("ICMS_TEST_API_URL", "http://127.0.0.1:8000")
        req = request.Request(f"{base_url}/api{path}", data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=15) as response: return response.status, json.loads(response.read() or b"{}")
        except error.HTTPError as exc: return exc.code, json.loads(exc.read() or b"{}")

    @classmethod
    def _login(cls, username):
        status, payload = cls._request("POST", "/auth/login", body={"username": username, "password": "demo123"})
        if status != 200: raise AssertionError(payload)
        return payload["token"]

    def setUp(self):
        self.tearDownAssignment()
        due = (datetime.utcnow() + timedelta(days=1)).isoformat()
        self.body = {"section_id": self.section_id, "title": "Phase 4 verification", "instructions": "Explain the design.", "max_marks": 10, "due_at": due, "allow_late": True, "action": "draft"}

    def tearDownAssignment(self):
        ids = [row[0] for row in self.db.query(D.AssignmentSubmission.id).filter(D.AssignmentSubmission.assignment_id == self.assignment_id).all()]
        if ids: self.db.query(D.AssignmentEvaluation).filter(D.AssignmentEvaluation.submission_id.in_(ids)).delete(synchronize_session=False)
        self.db.query(D.AssignmentSubmission).filter(D.AssignmentSubmission.assignment_id == self.assignment_id).delete(synchronize_session=False)
        self.db.query(D.Assignment).filter(D.Assignment.id == self.assignment_id).delete(synchronize_session=False)
        self.db.commit()

    def _create(self):
        status, payload = self._request("POST", "/faculty/assignments", self.tokens["aarav_kulkarni"], self.body)
        self.assertEqual(status, 200, payload)
        generated = payload["assignment"]["id"]
        assignment = self.db.query(D.Assignment).get(generated); assignment.id = self.assignment_id; self.db.commit()
        return self.assignment_id

    def test_assignment_restrictions_visibility_and_submission(self):
        assignment_id = self._create()
        self.assertEqual(self._request("POST", "/faculty/assignments", self.tokens["lecturer"], self.body)[0], 403)
        student_id = self.students[0]
        username = self.student_users[student_id]
        student_token = self._login(username)
        self.assertNotIn(assignment_id, [row["id"] for row in self._request("GET", "/portal/student/assignments", student_token)[1]["assignments"]])
        published = dict(self.body, action="publish")
        self.assertEqual(self._request("PUT", f"/faculty/assignments/{assignment_id}", self.tokens["aarav_kulkarni"], published)[0], 200)
        self.assertEqual(self._request("POST", f"/portal/student/assignments/{assignment_id}/submit", student_token, {"submission_text": "My answer"})[0], 200)
        roster = self._request("GET", f"/faculty/assignments/{assignment_id}/submissions", self.tokens["aarav_kulkarni"])[1]
        self.assertEqual(len(roster["roster"]), self.enrolled_count); self.assertIn("missing", [row["status"] for row in roster["roster"]])

    def test_late_return_resubmit_evaluate_and_student_isolation(self):
        self.body["due_at"] = (datetime.utcnow() - timedelta(days=1)).isoformat(); assignment_id = self._create()
        self.assertEqual(self._request("PUT", f"/faculty/assignments/{assignment_id}", self.tokens["aarav_kulkarni"], dict(self.body, action="publish"))[0], 200)
        student = self.db.query(D.Student).get(self.students[0]); token = self._login(self.student_users[student.id])
        self.assertEqual(self._request("POST", f"/portal/student/assignments/{assignment_id}/submit", token, {"submission_text": "First attempt"})[0], 200)
        roster = self._request("GET", f"/faculty/assignments/{assignment_id}/submissions", self.tokens["aarav_kulkarni"])[1]["roster"]
        current = next(row for row in roster if row["student_id"] == student.id); self.assertTrue(current["late"])
        self.assertEqual(self._request("POST", f"/faculty/assignment-submissions/{current['submission_id']}/evaluate", self.tokens["aarav_kulkarni"], {"action": "return", "feedback": "Add evidence."})[0], 200)
        self.assertEqual(self._request("POST", f"/portal/student/assignments/{assignment_id}/submit", token, {"submission_text": "Revised answer"})[0], 200)
        current = next(row for row in self._request("GET", f"/faculty/assignments/{assignment_id}/submissions", self.tokens["aarav_kulkarni"])[1]["roster"] if row["student_id"] == student.id)
        self.assertEqual(current["attempt_no"], 2)
        self.assertEqual(self._request("POST", f"/faculty/assignment-submissions/{current['submission_id']}/evaluate", self.tokens["aarav_kulkarni"], {"action": "evaluate", "marks_awarded": 0, "feedback": "Corrected."})[0], 200)
        detail = self._request("GET", f"/portal/student/assignments/{assignment_id}", token)[1]["assignment"]
        self.assertEqual(detail["marks_awarded"], 0); self.assertEqual(detail["feedback"], "Corrected.")
        self.assertEqual(self._request("POST", f"/faculty/assignment-submissions/{current['submission_id']}/evaluate", self.tokens["aarav_kulkarni"], {"action": "evaluate", "marks_awarded": 11, "feedback": "bad"})[0], 422)


