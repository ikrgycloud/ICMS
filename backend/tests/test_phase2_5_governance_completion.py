"""Completion-gate contract tests for the unified Phase 2-5 governance surface."""
import json
import os
import unittest
from urllib import error, request

BASE = os.getenv("ICMS_API_URL", "http://127.0.0.1:8010")


class GovernanceCompletionGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokens = {}
        for username in ("dean_academics", "hod", "student"):
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

    def test_dean_can_read_all_completion_surfaces(self):
        dean = self.tokens["dean_academics"]
        paths = (
            "/api/academic-governance/policies",
            "/api/academic-governance/inbox",
            "/api/academic-governance/curriculum/versions",
            "/api/academic-governance/calendar/versions",
            "/api/academic-governance/timetable/conflicts",
            "/api/academic-governance/faculty/workload/2026-Odd",
            "/api/academic-governance/faculty/conflicts",
            "/api/academic-governance/exceptions",
            "/api/academic-governance/delivery/monitoring",
            "/api/academic-governance/notifications/outcomes",
        )
        for path in paths:
            with self.subTest(path=path):
                status, _ = self.call("GET", path, dean)
                self.assertEqual(status, 200)

    def test_non_governance_user_cannot_read_completion_surfaces(self):
        student = self.tokens.get("student")
        if not student:
            self.skipTest("student account unavailable")
        for path in ("/api/academic-governance/inbox", "/api/academic-governance/delivery/monitoring"):
            with self.subTest(path=path):
                self.assertEqual(self.call("GET", path, student)[0], 403)

    def test_policy_contains_required_lifecycle_states(self):
        status, payload = self.call("GET", "/api/academic-governance/policies", self.tokens["dean_academics"])
        self.assertEqual(status, 200)
        expected = {"DRAFT", "SUBMITTED", "UNDER_REVIEW", "CLARIFICATION_REQUIRED", "RETURNED", "RESUBMITTED", "APPROVED", "REJECTED", "ESCALATED", "IMPLEMENTED", "ARCHIVED"}
        for policy in payload["policies"]:
            self.assertEqual(set(policy["states"]), expected)
            self.assertIn("SUBMITTED", policy["transitions"]["DRAFT"])

    def test_mutating_completion_surfaces_require_reason_or_valid_input(self):
        dean = self.tokens["dean_academics"]
        checks = (
            ("POST", "/api/academic-governance/documents", {"owner_entity_type": "proposal", "owner_entity_id": "missing", "file_name": "evidence.pdf", "object_storage_key": "missing/evidence.pdf", "checksum": "short"}),
            ("POST", "/api/academic-governance/faculty/workload-rules", {"term": "2026-Odd", "min_units": 5, "max_units": 2, "overload_threshold": 2, "underload_threshold": 0}),
        )
        for method, path, body in checks:
            with self.subTest(path=path):
                self.assertIn(self.call(method, path, dean, body)[0], (404, 422))


if __name__ == "__main__":
    unittest.main()
