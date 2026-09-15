"""Regression coverage for the HOD command-centre contract and access boundary."""
import json
import os
import unittest
from urllib import error, request


class HodDashboardNavigationTests(unittest.TestCase):
    @staticmethod
    def _request(path, token=""):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        base = os.environ.get("ICMS_TEST_API_URL", "http://127.0.0.1:8000")
        req = request.Request(f"{base}/api{path}", headers=headers)
        try:
            with request.urlopen(req, timeout=15) as response:
                return response.status, json.loads(response.read() or b"{}")
        except error.HTTPError as exc:
            try:
                return exc.code, json.loads(exc.read() or b"{}")
            finally:
                exc.close()

    @classmethod
    def _login(cls, username):
        body = json.dumps({"username": username, "password": "demo123"}).encode()
        base = os.environ.get("ICMS_TEST_API_URL", "http://127.0.0.1:8000")
        req = request.Request(f"{base}/api/auth/login", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with request.urlopen(req, timeout=15) as response:
            return json.loads(response.read())["token"]

    def test_hod_dashboard_is_department_scoped_and_complete(self):
        status, payload = self._request("/portal/hod/dashboard", self._login("hod"))
        self.assertEqual(status, 200)
        self.assertEqual(set(payload["kpis"]), {"active_faculty", "department_students", "active_sections", "at_risk_students", "pending_reviews", "attendance_pending", "sections_without_faculty", "upcoming_exams"})
        self.assertEqual(set(payload["reviews"]), {"marks_reviews", "attendance_corrections", "faculty_leave", "mentoring_referrals"})
        self.assertEqual(set(payload["student_health"]), {"at_risk", "backlogs", "attendance_risk", "academic_risk", "multiple_risks"})
        self.assertTrue(all("reason" not in row for row in payload["activity"]))

    def test_non_hod_cannot_read_dashboard(self):
        status, _ = self._request("/portal/hod/dashboard", self._login("lecturer"))
        self.assertEqual(status, 403)
