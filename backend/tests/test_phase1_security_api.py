import json
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib import error, request


BASE = os.environ.get("ICMS_API_URL", "http://127.0.0.1:8010")
GOVERNANCE_READS = (
    "/api/academics/quality/risks",
    "/api/academics/committees",
    "/api/academics/outcomes",
    "/api/academics/next-semester-plans",
    "/api/academics/timetable/readiness",
)


class Phase1SecurityApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokens = {}
        for username in (
            "dean_academics", "hod", "academic_coordinator", "exam_controller",
            "lecturer", "student", "parent", "finance_manager",
        ):
            status, payload = cls.call("POST", "/api/auth/login", body={"username": username, "password": "demo123"})
            if status == 200:
                cls.tokens[username] = payload["token"]
        if "dean_academics" not in cls.tokens:
            raise unittest.SkipTest(f"ICMS API unavailable at {BASE}")

    @staticmethod
    def call(method, path, token=None, body=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        raw = json.dumps(body).encode() if body is not None else None
        try:
            with request.urlopen(request.Request(BASE + path, data=raw, headers=headers, method=method), timeout=15) as response:
                return response.status, json.loads(response.read() or b"{}")
        except error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")
        except OSError:
            return 0, {}

    def test_unauthenticated_governance_is_denied(self):
        status, _ = self.call("GET", GOVERNANCE_READS[0])
        self.assertEqual(status, 401)

    def test_non_governance_roles_are_denied(self):
        for username in ("exam_controller", "lecturer", "student", "parent", "finance_manager"):
            with self.subTest(username=username):
                for path in GOVERNANCE_READS:
                    status, _ = self.call("GET", path, self.tokens.get(username))
                    self.assertEqual(status, 403, (username, path))

    def test_academic_leadership_can_read_governance(self):
        for username in ("dean_academics", "hod", "academic_coordinator"):
            with self.subTest(username=username):
                for path in GOVERNANCE_READS:
                    status, _ = self.call("GET", path, self.tokens.get(username))
                    self.assertEqual(status, 200, (username, path))

    def test_invalid_governance_detail_ids_do_not_leak_or_mutate(self):
        dean = self.tokens["dean_academics"]
        checks = (
            ("GET", "/api/academics/outcomes?program_id=foreign-program"),
            ("GET", "/api/academics/committees/foreign-committee/members"),
            ("POST", "/api/academics/timetable/readiness/foreign-exception/resolve"),
        )
        for method, path in checks:
            with self.subTest(method=method, path=path):
                status, _ = self.call(method, path, dean, {} if method == "POST" else None)
                self.assertIn(status, (403, 404, 422))

    def test_foreign_allocation_targets_are_rejected(self):
        dean = self.tokens["dean_academics"]
        status, _ = self.call(
            "POST", "/api/academics/allocation/proposals", dean,
            {"section_id": "foreign-section", "faculty_person_id": "foreign-faculty", "rationale": "scope test"},
        )
        self.assertIn(status, (403, 404, 422))

    def test_foreign_section_detail_routes_are_rejected(self):
        hod = self.tokens["hod"]
        for path in (
            "/api/academics/section/does-not-belong/timetable",
            "/api/academics/section/does-not-belong/assignments",
            "/api/attendance/roster/does-not-belong",
            "/api/exams/assessments/does-not-belong",
        ):
            with self.subTest(path=path):
                status, _ = self.call("GET", path, hod)
                self.assertIn(status, (403, 404))

    def test_foreign_outcome_ids_are_rejected(self):
        dean = self.tokens["dean_academics"]
        status, _ = self.call("POST", "/api/academics/outcomes/program", dean, {
            "program_id": "does-not-belong", "code": "PO-X", "description": "scope test",
        })
        self.assertIn(status, (403, 404, 422))

    def test_concurrent_missing_decisions_are_conflicts_or_not_found(self):
        dean = self.tokens["dean_academics"]
        creator = self.tokens["hod"]
        status, created = self.call("POST", "/api/curriculum/proposals", creator, {
            "code": f"PH1-{uuid.uuid4().hex[:8].upper()}", "title": "Phase 1 concurrency fixture", "dept_code": "CSE",
            "credits": 3, "semester": 1, "effective_term": "2026-Odd", "rationale": "test fixture",
        })
        self.assertEqual(status, 200, created)
        submitted = created["proposal"]
        status, submitted = self.call("POST", f"/api/curriculum/proposals/{submitted['id']}/submit", creator, {
            "expected_status_version": submitted["status_version"], "reason": "test fixture submission",
        })
        self.assertEqual(status, 200, submitted)
        submitted = submitted["proposal"]
        path = f"/api/curriculum/proposals/{submitted['id']}/decision/reject"
        body = {"expected_status_version": submitted["status_version"], "reason": "concurrency test"}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.call("POST", path, dean, body)[0], range(2)))
        self.assertEqual(sum(result == 200 for result in results), 1)
        self.assertIn(next(result for result in results if result != 200), (403, 409))

    def test_duplicate_decision_is_rejected(self):
        dean = self.tokens["dean_academics"]
        creator = self.tokens["hod"]
        status, created = self.call("POST", "/api/curriculum/proposals", creator, {
            "code": f"PH1-{uuid.uuid4().hex[:8].upper()}", "title": "Phase 1 duplicate fixture", "dept_code": "CSE",
            "credits": 3, "semester": 1, "effective_term": "2026-Odd", "rationale": "test fixture",
        })
        self.assertEqual(status, 200, created)
        proposal = created["proposal"]
        status, submitted = self.call("POST", f"/api/curriculum/proposals/{proposal['id']}/submit", creator, {
            "expected_status_version": proposal["status_version"], "reason": "fixture submission",
        })
        self.assertEqual(status, 200, submitted)
        status, _ = self.call("POST", f"/api/curriculum/proposals/{proposal['id']}/decision/approve", dean, {
            "expected_status_version": submitted["proposal"]["status_version"], "reason": "first approval",
        })
        self.assertEqual(status, 200)
        status, _ = self.call("POST", f"/api/curriculum/proposals/{proposal['id']}/decision/approve", dean, {
            "expected_status_version": submitted["proposal"]["status_version"] + 1, "reason": "duplicate approval",
        })
        self.assertIn(status, (403, 409))

    def test_repeated_missing_or_stale_decisions_are_rejected(self):
        dean = self.tokens["dean_academics"]
        status, payload = self.call("GET", "/api/curriculum/proposals", dean)
        self.assertEqual(status, 200)
        submitted = next((row for row in payload.get("proposals", []) if row.get("state") in {"SUBMITTED", "RESUBMITTED"}), None)
        if not submitted:
            self.skipTest("No submitted curriculum proposal in the validation dataset")
        path = f"/api/curriculum/proposals/{submitted['id']}/decision/approve"
        stale = {"expected_status_version": max(0, submitted["status_version"] - 1), "reason": "stale version test"}
        first, _ = self.call("POST", path, dean, stale)
        self.assertIn(first, (403, 409))


if __name__ == "__main__":
    unittest.main()