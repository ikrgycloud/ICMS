import json
import os
import unittest
from urllib import error, request

from database import SessionLocal
import domain_models as D
from models import User


class MentoringCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        aarav = cls.db.query(User).filter(User.username == "aarav_kulkarni").first()
        cls.mentor = cls.db.query(D.StaffMember).filter(D.StaffMember.user_id == aarav.id).first()
        cls.student_id = cls.db.query(D.MentorAssignment).filter(
            D.MentorAssignment.faculty_id == cls.mentor.id,
            D.MentorAssignment.status == "active").first().student_id
        cls.case_ids = []
        cls.tokens = {name: cls._login(name) for name in ("aarav_kulkarni", "hod", "professor")}
        assigned_ids = {row.student_id for row in cls.db.query(D.MentorAssignment).filter(D.MentorAssignment.faculty_id == cls.mentor.id).all()}
        cls.foreign_student_id = cls.db.query(D.Student).filter(~D.Student.id.in_(assigned_ids)).first().id

    @classmethod
    def tearDownClass(cls):
        for case_id in cls.case_ids:
            cls.db.query(D.MentoringFollowUp).filter(D.MentoringFollowUp.case_id == case_id).delete(synchronize_session=False)
            cls.db.query(D.MentoringNote).filter(D.MentoringNote.case_id == case_id).delete(synchronize_session=False)
            cls.db.query(D.MentoringCase).filter(D.MentoringCase.id == case_id).delete(synchronize_session=False)
        cls.db.commit(); cls.db.close()

    @classmethod
    def _request(cls, method, path, token=None, body=None):
        headers = {"Content-Type": "application/json"}
        if token: headers["Authorization"] = f"Bearer {token}"
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
        if status != 200: raise AssertionError(payload)
        return payload["token"]

    def _create(self):
        body = {"category": "Attendance", "risk_level": "medium", "summary": "Phase 6 attendance support", "action_plan": "Weekly attendance review", "follow_up_date": "2090-06-10"}
        status, payload = self._request("POST", f"/portal/faculty/mentees/{self.student_id}/mentoring-cases", self.tokens["aarav_kulkarni"], body)
        self.assertEqual(status, 200, payload)
        self.case_ids.append(payload["case"]["id"])
        return payload["case"]

    def test_mentor_case_lifecycle_history_and_referral_scope(self):
        created = self._create()
        case_id = created["id"]
        self.assertEqual(created["status"], "open")
        self.assertEqual(self._request("PUT", f"/portal/faculty/mentoring-cases/{case_id}", self.tokens["aarav_kulkarni"], {"action_plan": "Updated plan", "risk_level": "high"})[0], 200)
        noted = self._request("POST", f"/portal/faculty/mentoring-cases/{case_id}/notes", self.tokens["aarav_kulkarni"], {"content": "Discussed attendance recovery plan."})[1]["case"]
        self.assertTrue(any(note["content"] == "Discussed attendance recovery plan." for note in noted["notes"]))
        followed = self._request("POST", f"/portal/faculty/mentoring-cases/{case_id}/follow-ups", self.tokens["aarav_kulkarni"], {"scheduled_for": "2090-06-12"})[1]["case"]
        follow_up = followed["follow_ups"][-1]
        completed = self._request("POST", f"/portal/faculty/mentoring-cases/{case_id}/follow-ups/{follow_up['id']}/complete", self.tokens["aarav_kulkarni"], {"outcome": "Student accepted the plan."})[1]["case"]
        self.assertTrue(any(item["completed_at"] for item in completed["follow_ups"]))
        referred = self._request("POST", f"/portal/faculty/mentoring-cases/{case_id}/refer", self.tokens["aarav_kulkarni"], {"reason": "Department support is needed."})[1]["case"]
        self.assertEqual(referred["status"], "referred")
        inbox = self._request("GET", "/portal/faculty/mentoring-cases?scope=inbox", self.tokens["hod"])[1]["cases"]
        self.assertIn(case_id, [row["id"] for row in inbox])
        resolved = self._request("POST", f"/portal/faculty/mentoring-cases/{case_id}/close?action=resolve", self.tokens["aarav_kulkarni"])[1]["case"]
        self.assertEqual(resolved["status"], "resolved")
        self.assertEqual(self._request("POST", f"/portal/faculty/mentoring-cases/{case_id}/notes", self.tokens["aarav_kulkarni"], {"content": "Must not be written."})[0], 409)

    def test_assigned_mentor_and_arbitrary_student_guards(self):
        self.assertEqual(self._request("GET", f"/portal/faculty/mentees/{self.foreign_student_id}", self.tokens["aarav_kulkarni"])[0], 403)
        self.assertEqual(self._request("POST", f"/portal/faculty/mentees/{self.foreign_student_id}/mentoring-cases", self.tokens["aarav_kulkarni"], {"category": "Other", "risk_level": "low", "summary": "Not assigned"})[0], 403)
        self.assertEqual(self._request("GET", "/portal/faculty/mentoring-cases/phase6_case_low_open", self.tokens["professor"])[0], 403)
        self.assertEqual(self._request("GET", "/portal/faculty/mentoring-cases?scope=inbox", self.tokens["aarav_kulkarni"])[0], 403)


