"""HTTP completion contracts for Phase 6-10 operational surfaces."""
import json
import os
import unittest
from urllib import error, request

BASE = os.getenv("ICMS_API_URL", "http://127.0.0.1:8010")


class Phase610EndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokens = {}
        for user in ("dean_academics", "student"):
            status, _, payload = cls.call("POST", "/api/auth/login", body={"username": user, "password": "demo123"})
            if status == 200:
                cls.tokens[user] = payload["token"]
        if "dean_academics" not in cls.tokens:
            raise unittest.SkipTest(f"ICMS API unavailable at {BASE}")
        status, _, _ = cls.call("GET", "/api/academics/attainment/validation", cls.tokens["dean_academics"])
        if status == 404:
            raise unittest.SkipTest("Running API does not include Phase 6-10 routes; rebuild the Docker image")

    @staticmethod
    def call(method, path, token=None, body=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            with request.urlopen(request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method), timeout=15) as response:
                raw=response.read(); return response.status, response.headers.get("Content-Type", ""), json.loads(raw or b"{}") if "json" in response.headers.get("Content-Type", "") else raw
        except error.HTTPError as exc:
            raw=exc.read(); return exc.code, exc.headers.get("Content-Type", ""), json.loads(raw or b"{}") if "json" in exc.headers.get("Content-Type", "") else raw
        except OSError:
            return 0, "", {}

    def test_read_only_phase_surfaces(self):
        token = self.tokens["dean_academics"]
        for path in ("/api/academics/attainment/aggregate?level=student", "/api/academics/attainment/validation", "/api/academics/committees", "/api/academics/next-semester-plans", "/api/jobs"):
            with self.subTest(path=path):
                self.assertEqual(self.call("GET", path, token)[0], 200)

    def test_student_cannot_access_operational_surfaces(self):
        token = self.tokens.get("student")
        if not token:
            self.skipTest("student account unavailable")
        self.assertEqual(self.call("GET", "/api/jobs", token)[0], 403)
        self.assertEqual(self.call("POST", "/api/academics/attainment/alerts/link-quality-reviews", token)[0], 403)

    def test_queue_idempotency_and_report_formats(self):
        token = self.tokens["dean_academics"]
        first = self.call("POST", "/api/jobs", token, {"operation": "noop", "idempotency_key": "phase610-contract"})
        second = self.call("POST", "/api/jobs", token, {"operation": "noop", "idempotency_key": "phase610-contract"})
        self.assertEqual(first[0], 200)
        self.assertTrue(second[2].get("duplicate"))
        for fmt, content in (("csv", "text/csv"), ("pdf", "application/pdf"), ("xlsx", "spreadsheetml")):
            status, content_type, _ = self.call("GET", f"/api/academics/reports/co-po-attainment.{fmt}", token)
            self.assertEqual(status, 200)
            self.assertIn(content, content_type)


if __name__ == "__main__":
    unittest.main()