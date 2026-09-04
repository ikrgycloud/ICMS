import json
import os
import unittest
from datetime import datetime
from urllib import error, request

from database import SessionLocal, TENANT
import domain_models as D
from models import Approval, User, WorkflowInstance


class MarksSubmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.tokens = {name: cls._login(name) for name in ("aarav_kulkarni", "academic_coordinator", "hod", "exam_controller", "lecturer", "25ECE072")}
        allocation = None
        for candidate in cls.db.query(D.TeachingAllocation).filter(D.TeachingAllocation.faculty_id == "staff_fac_1", D.TeachingAllocation.status == "active").all():
            students = [row.student_id for row in cls.db.query(D.Enrollment).filter(D.Enrollment.section_id == candidate.section_id, D.Enrollment.status == "enrolled").all()]
            if students:
                allocation, cls.students = candidate, students
                break
        if not allocation: raise AssertionError("Aarav has no active allocation with enrolled students")
        cls.section = cls.db.query(D.Section).get(allocation.section_id)
        cls.assessment_id = "test_phase3_marks_submission"

    @classmethod
    def tearDownClass(cls):
        cls._clear_fixture()
        cls.db.close()

    @classmethod
    def _clear_fixture(cls):
        assessment = cls.db.query(D.Assessment).get(cls.assessment_id)
        if assessment and assessment.workflow_instance_id:
            cls.db.query(Approval).filter(Approval.workflow_id == assessment.workflow_instance_id).delete(synchronize_session=False)
            cls.db.query(WorkflowInstance).filter(WorkflowInstance.id == assessment.workflow_instance_id).delete(synchronize_session=False)
        cls.db.query(D.Mark).filter(D.Mark.assessment_id == cls.assessment_id).delete(synchronize_session=False)
        cls.db.query(D.Assessment).filter(D.Assessment.id == cls.assessment_id).delete(synchronize_session=False)
        visibility_ids = [row[0] for row in cls.db.query(D.Assessment.id).filter(D.Assessment.id.like("test_phase3_visibility_%")).all()]
        if visibility_ids:
            cls.db.query(D.Mark).filter(D.Mark.assessment_id.in_(visibility_ids)).delete(synchronize_session=False)
            cls.db.query(D.Assessment).filter(D.Assessment.id.in_(visibility_ids)).delete(synchronize_session=False)
        cls.db.commit()

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
        self._clear_fixture()
        self.db = self.__class__.db
        self.db.add(D.Assessment(id=self.assessment_id, tenant_id=TENANT, section_id=self.section.id, name="Phase 3 verification", max_marks=20, assessment_type="quiz", status="draft", marks_state="draft", created_at=datetime.utcnow(), updated_at=datetime.utcnow()))
        self.db.commit()

    def test_marks_review_chain_and_guards(self):
        marks = {student_id: 10 for student_id in self.students}
        status, _ = self._request("POST", "/exams/marks", self.tokens["aarav_kulkarni"], {"assessment_id": self.assessment_id, "marks": marks})
        self.assertEqual(status, 200)
        self.assertEqual(self._request("POST", "/exams/marks", self.tokens["aarav_kulkarni"], {"assessment_id": self.assessment_id, "marks": {self.students[0]: 21}})[0], 422)
        status, submitted = self._request("POST", "/exams/marks/submit", self.tokens["aarav_kulkarni"], {"assessment_id": self.assessment_id})
        self.assertEqual(status, 200, submitted); self.assertEqual(submitted["submission"]["state"], "submitted")
        workflow_id = submitted["submission"]["workflow_instance_id"]
        status, mine = self._request("GET", "/workflows?scope=mine", self.tokens["aarav_kulkarni"])
        self.assertEqual(status, 200, mine)
        self.assertEqual(sum(1 for row in mine["workflows"] if row["id"] == workflow_id), 1)
        status, inbox = self._request("GET", "/exams/marks/submissions?scope=inbox", self.tokens["academic_coordinator"])
        self.assertEqual(status, 200, inbox); self.assertIn(self.assessment_id, [row["assessment_id"] for row in inbox["submissions"]])
        status, inbox = self._request("GET", "/exams/marks/submissions?scope=inbox", self.tokens["hod"])
        self.assertEqual(status, 200, inbox); self.assertNotIn(self.assessment_id, [row["assessment_id"] for row in inbox["submissions"]])
        self.assertEqual(self._request("POST", "/exams/marks/publish", self.tokens["aarav_kulkarni"], {"assessment_id": self.assessment_id})[0], 403)
        self.assertEqual(self._request("POST", "/exams/marks", self.tokens["aarav_kulkarni"], {"assessment_id": self.assessment_id, "marks": marks})[0], 409)
        self.assertEqual(self._request("POST", f"/exams/marks/submissions/{self.assessment_id}/decide", self.tokens["hod"], {"action": "approve"})[0], 403)
        self.assertEqual(self._request("POST", f"/exams/marks/submissions/{self.assessment_id}/decide", self.tokens["lecturer"], {"action": "approve"})[0], 403)
        self.assertEqual(self._request("POST", f"/exams/marks/submissions/{self.assessment_id}/decide", self.tokens["academic_coordinator"], {"action": "approve"})[0], 200)
        self.assertIn(self.assessment_id, [row["assessment_id"] for row in self._request("GET", "/exams/marks/submissions?scope=inbox", self.tokens["hod"])[1]["submissions"]])
        self.assertEqual(self._request("POST", f"/exams/marks/submissions/{self.assessment_id}/decide", self.tokens["hod"], {"action": "approve"})[0], 200)
        self.assertIn(self.assessment_id, [row["assessment_id"] for row in self._request("GET", "/exams/marks/submissions?scope=inbox", self.tokens["exam_controller"])[1]["submissions"]])
        status, final = self._request("POST", f"/exams/marks/submissions/{self.assessment_id}/decide", self.tokens["exam_controller"], {"action": "approve"})
        self.assertEqual(status, 200, final); self.assertEqual(final["submission"]["state"], "published")
        self.assertEqual(self._request("POST", f"/exams/marks/submissions/{self.assessment_id}/decide", self.tokens["exam_controller"], {"action": "approve"})[0], 409)

    def test_save_draft_persists_reopens_edits_and_keeps_blanks(self):
        first, second, blank = self.students[:3]
        workflow_count = self.db.query(WorkflowInstance).filter(WorkflowInstance.process_key == "marks_submission").count()
        payload = {"assessment_id": self.assessment_id, "marks": {first: 0, second: 8}}
        status, saved = self._request("POST", "/exams/marks", self.tokens["aarav_kulkarni"], payload)
        self.assertEqual(status, 200, saved)
        self.assertEqual(saved["assessment_id"], self.assessment_id)
        self.assertEqual(saved["entered"], 2)
        self.assertEqual(saved["total_entered"], 2)
        self.assertEqual(self.db.query(D.Mark).filter(D.Mark.assessment_id == self.assessment_id).count(), 2)
        self.assertEqual(self.db.query(WorkflowInstance).filter(WorkflowInstance.process_key == "marks_submission").count(), workflow_count)
        status, reopened = self._request("GET", f"/portal/faculty/assessment/{self.assessment_id}/marks", self.tokens["aarav_kulkarni"])
        self.assertEqual(status, 200, reopened)
        scores = {row["student_id"]: row["score"] for row in reopened["roster"]}
        self.assertEqual(scores[first], 0)
        self.assertEqual(scores[second], 8)
        self.assertIsNone(scores[blank])
        status, updated = self._request("POST", "/exams/marks", self.tokens["aarav_kulkarni"],
                                        {"assessment_id": self.assessment_id, "marks": {second: 12}})
        self.assertEqual(status, 200, updated)
        self.db.expire_all()
        self.assertEqual(self.db.query(D.Mark).filter(D.Mark.assessment_id == self.assessment_id, D.Mark.student_id == second).one().score, 12)
        self.assertEqual(self.db.query(D.Assessment).get(self.assessment_id).marks_state, "draft")
        self.assertIsNone(self.db.query(D.Assessment).get(self.assessment_id).workflow_instance_id)

    def test_returned_marks_can_be_edited_and_resubmitted_on_same_workflow(self):
        marks = {student_id: 9 for student_id in self.students}
        self.assertEqual(self._request("POST", "/exams/marks", self.tokens["aarav_kulkarni"], {"assessment_id": self.assessment_id, "marks": marks})[0], 200)
        status, submitted = self._request("POST", "/exams/marks/submit", self.tokens["aarav_kulkarni"], {"assessment_id": self.assessment_id})
        self.assertEqual(status, 200, submitted)
        workflow_id = submitted["submission"]["workflow_instance_id"]
        status, returned = self._request("POST", f"/exams/marks/submissions/{self.assessment_id}/decide", self.tokens["academic_coordinator"], {"action": "return", "comment": "Check the quiz rubric."})
        self.assertEqual(status, 200, returned); self.assertEqual(returned["submission"]["state"], "returned")
        self.assertEqual(returned["submission"]["return_comment"], "Check the quiz rubric.")
        self.assertEqual(self._request("POST", "/exams/marks", self.tokens["aarav_kulkarni"], {"assessment_id": self.assessment_id, "marks": {self.students[0]: 10}})[0], 200)
        status, resubmitted = self._request("POST", "/exams/marks/submit", self.tokens["aarav_kulkarni"], {"assessment_id": self.assessment_id})
        self.assertEqual(status, 200, resubmitted)
        self.assertEqual(resubmitted["submission"]["workflow_instance_id"], workflow_id)
        self.assertTrue(any(item["decision"] == "RETURN" for item in resubmitted["submission"]["history"]))

    def test_student_sees_only_published_marks(self):
        student_user = self.db.query(User).filter(User.username == "25ECE072").one()
        student = self.db.query(D.Student).filter(D.Student.user_id == student_user.id).one()
        section_id = (self.db.query(D.Enrollment.section_id)
                      .join(D.Section, D.Section.id == D.Enrollment.section_id)
                      .filter(D.Enrollment.student_id == student.id,
                              D.Enrollment.status == "enrolled",
                              D.Section.dept_id == student.dept_id,
                              D.Section.section_code == student.section)
                      .first()[0])
        for state in ("draft", "submitted", "returned", "under_review", "published"):
            assessment_id = f"test_phase3_visibility_{state}"
            self.db.add(D.Assessment(id=assessment_id, tenant_id=TENANT, section_id=section_id, name=f"Visibility {state}", max_marks=20,
                assessment_type="quiz", scheduled_at=datetime(2026, 8, 1), published=True, status="published", marks_state=state,
                published_by="Exam Controller" if state == "published" else "", created_at=datetime.utcnow(), updated_at=datetime.utcnow()))
            self.db.add(D.Mark(id=f"mark_{assessment_id}", tenant_id=TENANT, assessment_id=assessment_id, student_id=student.id, score=10,
                status=state, is_valid=True, entered_at=datetime.utcnow(), published_at=datetime.utcnow() if state == "published" else None,
                published_by="Exam Controller" if state == "published" else "", updated_at=datetime.utcnow()))
        self.db.commit()
        status, payload = self._request("GET", "/portal/student/examinations", self.tokens["25ECE072"])
        self.assertEqual(status, 200, payload)
        visible = {row["assessment_id"] for row in payload["recent_published_marks"]}
        self.assertIn("test_phase3_visibility_published", visible)
        for state in ("draft", "submitted", "returned", "under_review"):
            self.assertNotIn(f"test_phase3_visibility_{state}", visible)

