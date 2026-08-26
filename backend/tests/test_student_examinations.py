import os
import sys
import unittest
import json
from datetime import datetime
from urllib import error, request

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal, TENANT
from models import User
import domain_models as D


class StudentExaminationsPortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.base_url = "http://127.0.0.1:8000"
        cls.student_token = cls._login("student")
        cls.professor_token = cls._login("professor")

        student_user = cls.db.query(User).filter(User.username == "student").first()
        cls.student = cls.db.query(D.Student).filter(D.Student.user_id == student_user.id).first()
        cls.current_section_ids = {
            row.section_id
            for row in cls.db.query(D.Enrollment)
            .filter(D.Enrollment.student_id == cls.student.id, D.Enrollment.status == "enrolled")
            .all()
        }

        other_student = cls.db.query(D.Student).filter(D.Student.id != cls.student.id).first()
        cls.temp_mark_id = "test_portal_other_student_mark"
        existing = cls.db.query(D.Mark).get(cls.temp_mark_id)
        if existing is None:
            existing = D.Mark(
                id=cls.temp_mark_id,
                tenant_id=TENANT,
                assessment_id="asmt_portal_cs401_midterm",
                student_id=other_student.id,
                score=91,
                entered_by="Test Faculty",
                entered_at=datetime(2026, 8, 20, 13, 0),
                status="published",
                published_at=datetime(2026, 8, 20, 18, 45),
                published_by="Test Faculty",
                is_valid=True,
                updated_at=datetime(2026, 8, 20, 18, 45),
            )
            cls.db.add(existing)
        else:
            existing.assessment_id = "asmt_portal_cs401_midterm"
            existing.student_id = other_student.id
            existing.score = 91
            existing.status = "published"
            existing.published_at = datetime(2026, 8, 20, 18, 45)
            existing.published_by = "Test Faculty"
            existing.is_valid = True
            existing.updated_at = datetime(2026, 8, 20, 18, 45)
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.query(D.Mark).filter(D.Mark.id == cls.temp_mark_id).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()

    @classmethod
    def _login(cls, username: str) -> str:
        status_code, payload = cls._request("POST", "/api/auth/login", body={"username": username, "password": "demo123"})
        if status_code != 200:
            raise AssertionError(f"Login failed for {username}: {payload}")
        return payload["token"]

    @classmethod
    def _request(cls, method: str, path: str, token: str | None = None, body: dict | None = None):
        raw = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = request.Request(f"{cls.base_url}{path}", data=raw, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=15) as response:
                payload = response.read().decode("utf-8")
                return response.getcode(), json.loads(payload) if payload else {}
        except error.HTTPError as exc:
            payload = exc.read().decode("utf-8")
            return exc.code, json.loads(payload) if payload else {}

    def _headers(self, token: str):
        return {"Authorization": f"Bearer {token}"}

    def test_student_portal_examinations_are_scoped_to_logged_in_student(self):
        status_code, data = self._request("GET", "/api/portal/student/examinations", token=self.student_token)
        self.assertEqual(status_code, 200, data)

        visible_assessment_ids = {
            item["assessment_id"] for item in data.get("recent_published_marks", [])
        } | {
            item["id"] for item in data.get("upcoming_assessments", [])
        }
        assessment_rows = (
            self.db.query(D.Assessment)
            .filter(D.Assessment.id.in_(visible_assessment_ids) if visible_assessment_ids else False)
            .all()
        )
        self.assertTrue({row.section_id for row in assessment_rows}.issubset(self.current_section_ids))
        self.assertTrue(all("student_id" not in row for row in data.get("recent_published_marks", [])))
        self.assertEqual(
            sum(1 for row in data.get("recent_published_marks", []) if row["assessment_id"] == "asmt_portal_cs401_midterm"),
            1,
        )

    def test_draft_marks_hidden_and_cancelled_assessments_excluded(self):
        exams_status, examinations = self._request("GET", "/api/portal/student/examinations", token=self.student_token)
        scores_status, scores = self._request("GET", "/api/portal/student/scores", token=self.student_token)
        self.assertEqual(exams_status, 200, examinations)
        self.assertEqual(scores_status, 200, scores)

        upcoming_ids = {item["id"] for item in examinations.get("upcoming_assessments", [])}
        published_score_ids = {item["assessment_id"] for item in scores.get("published_marks", [])}

        self.assertNotIn("asmt_portal_cs402_surprise_cancelled", upcoming_ids)
        self.assertNotIn("asmt_portal_cs405_internal_draft", published_score_ids)
        self.assertIn("asmt_portal_cs404_midsem", upcoming_ids)

    def test_scores_include_multi_semester_history_and_pending_publications(self):
        status_code, scores = self._request("GET", "/api/portal/student/scores", token=self.student_token)
        self.assertEqual(status_code, 200, scores)

        semester_groups = scores.get("semester_groups", [])
        visible_terms = {(row.get("academic_year"), row.get("semester")) for row in semester_groups}
        self.assertIn(("2026-27", 7), visible_terms)
        self.assertIn(("2025-26", 6), visible_terms)
        self.assertTrue(any((row.get("summary") or {}).get("pending_publications", 0) > 0 for row in semester_groups))

    def test_home_and_academics_reflect_official_cgpa_and_catalog_history(self):
        home_status, home = self._request("GET", "/api/portal/student/home", token=self.student_token)
        courses_status, courses = self._request("GET", "/api/portal/student/courses", token=self.student_token)
        scores_status, scores = self._request("GET", "/api/portal/student/scores", token=self.student_token)
        exams_status, exams = self._request("GET", "/api/portal/student/examinations", token=self.student_token)

        self.assertEqual(home_status, 200, home)
        self.assertEqual(courses_status, 200, courses)
        self.assertEqual(scores_status, 200, scores)
        self.assertEqual(exams_status, 200, exams)

        official_cgpa = (scores.get("summary") or {}).get("cgpa")
        self.assertEqual((home.get("kpis") or {}).get("cgpa"), official_cgpa)
        self.assertEqual((courses.get("summary") or {}).get("cgpa"), official_cgpa)

        catalog_semesters = {row.get("semester") for row in courses.get("catalog", [])}
        self.assertIn(6, catalog_semesters)

        upcoming = {row.get("id"): row for row in exams.get("upcoming_assessments", [])}
        self.assertTrue((upcoming.get("asmt_portal_cs404_midsem") or {}).get("seat_label"))

    def test_unauthorized_faculty_cannot_enter_marks_for_unassigned_section(self):
        status_code, payload = self._request(
            "POST",
            "/api/exams/marks",
            token=self.professor_token,
            body={"assessment_id": "asmt_portal_cs401_midterm", "marks": {self.student.id: 86}},
        )
        self.assertEqual(status_code, 403, payload)

    def test_student_cannot_write_exam_data(self):
        status_code, payload = self._request(
            "POST",
            "/api/exams/timetable",
            token=self.student_token,
            body={
                "section_id": next(iter(self.current_section_ids)),
                "assessment_id": "asmt_portal_cs401_midterm",
                "academic_year": "2026-27",
                "semester": 7,
                "exam_type": "quiz",
                "start_at": "2026-09-02T10:00:00",
                "end_at": "2026-09-02T11:00:00",
                "venue": "Unauthorized Hall",
                "mode": "Offline",
                "status": "scheduled",
                "note": "student write should be blocked",
            },
        )
        self.assertEqual(status_code, 403, payload)


if __name__ == "__main__":
    unittest.main()
