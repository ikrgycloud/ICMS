import json
import os
import sys
import unittest
from urllib import error, request

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal
import domain_models as D


class FeeSetupTests(unittest.TestCase):
    code = "TEST-FEE-SETUP-2026-S1-V1"

    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.finance_token = cls._login("finance_manager")
        cls.student_token = cls._login("student")

    @classmethod
    def tearDownClass(cls):
        row = cls.db.query(D.FeeStructure).filter(D.FeeStructure.code == cls.code).first()
        if row:
            cls.db.query(D.FeeStructureLine).filter(D.FeeStructureLine.fee_structure_id == row.id).delete()
            cls.db.delete(row)
            cls.db.commit()
        cls.db.close()

    @classmethod
    def _request(cls, method, path, token=None, body=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        raw = json.dumps(body).encode() if body is not None else None
        try:
            with request.urlopen(request.Request(f"http://127.0.0.1:8000{path}", data=raw, headers=headers, method=method), timeout=15) as response:
                return response.status, json.loads(response.read().decode() or "{}")
        except error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode() or "{}")

    @classmethod
    def _download(cls, path, token=None):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        with request.urlopen(request.Request(f"http://127.0.0.1:8000{path}", headers=headers, method="GET"), timeout=15) as response:
            return response.status, response.headers.get_content_type(), response.read()

    @classmethod
    def _login(cls, username):
        status, payload = cls._request("POST", "/api/auth/login", body={"username": username, "password": "demo123"})
        if status != 200:
            raise AssertionError(payload)
        return payload["token"]

    def _payload(self):
        return {"name": "Fee setup test", "code": self.code,
                "academic_year_id": "academic_year_2026_27", "semester_id": "semester_2026_27_1",
                "campus_id": "campus_main_campus", "program_id": "prog_cse_btech", "batch_id": "batch_2026",
                "student_type_id": "student_type_regular", "version": 99,
                "lines": [{"fee_head_id": "fee_head_tuition", "amount": 25000, "installment_no": 1},
                          {"fee_head_id": "fee_head_tuition", "amount": 25000, "installment_no": 2},
                          {"fee_head_id": "fee_head_exam", "amount": 5000, "installment_no": 1},
                          {"fee_head_id": "fee_head_library", "amount": 2000, "installment_no": 1}]}

    def test_finance_manager_can_create_and_edit_a_draft_with_gross_total(self):
        status, created = self._request("POST", "/api/fee-structures", self.finance_token, self._payload())
        self.assertEqual(status, 200, created)
        structure = created["structure"]
        self.assertEqual(structure["status"], "DRAFT")
        self.assertEqual(float(structure["gross_total"]), 57000)
        payload = self._payload(); payload["lines"][2]["amount"] = 6000
        status, updated = self._request("PUT", f"/api/fee-structures/{structure['id']}", self.finance_token, payload)
        self.assertEqual(status, 200, updated)
        self.assertEqual(float(updated["structure"]["gross_total"]), 58000)

    def test_duplicate_line_and_unauthorized_role_are_rejected(self):
        payload = self._payload(); payload["code"] = "TEST-FEE-INVALID"
        payload["lines"].append({"fee_head_id": "fee_head_exam", "amount": 1, "installment_no": 1})
        status, _ = self._request("POST", "/api/fee-structures", self.finance_token, payload)
        self.assertEqual(status, 422)
        status, _ = self._request("GET", "/api/fees/heads", self.student_token)
        self.assertEqual(status, 403)

    def test_cash_payment_with_method_and_reference_is_recorded(self):
        status, invoices = self._request("GET", "/api/finance/invoices", self.finance_token)
        self.assertEqual(status, 200, invoices)
        invoice = next((item for item in invoices.get("invoices", []) if item.get("balance", 0) > 0), None)
        self.assertIsNotNone(invoice, invoices)
        amount = min(250, float(invoice["balance"]))
        status, result = self._request("POST", "/api/finance/payment", self.finance_token, {
            "invoice_id": invoice["id"],
            "amount": amount,
            "method": "cash",
            "reference": "CASH-TEST-001"
        })
        self.assertEqual(status, 200, result)
        self.assertEqual(result.get("method"), "cash")
        self.assertEqual(result.get("reference"), "CASH-TEST-001")

    def test_student_can_generate_duplicate_challan_and_download_pdf(self):
        status, summary = self._request("GET", "/api/portal/student/fees", self.student_token)
        self.assertEqual(status, 200, summary)
        invoice = next((item for item in summary.get("invoices", []) if float(item.get("balance", 0)) > 0), None)
        self.assertIsNotNone(invoice, summary)
        amount = min(float(invoice["balance"]), 2500.0)

        status, created = self._request("POST", "/api/portal/student/fees/challans", self.student_token, {
            "invoice_id": invoice["id"],
            "amount": amount,
        })
        self.assertEqual(status, 200, created)
        challan = created.get("challan")
        self.assertIsNotNone(challan, created)
        self.assertTrue((challan.get("challan_number") or "").startswith("CH-"))
        self.assertEqual(float(challan.get("amount") or 0), amount)

        status, duplicate = self._request("POST", "/api/portal/student/fees/challans", self.student_token, {
            "invoice_id": invoice["id"],
            "amount": amount,
        })
        self.assertEqual(status, 200, duplicate)
        self.assertEqual(duplicate.get("challan", {}).get("id"), challan.get("id"))

        status, content_type, body = self._download(f"/api/portal/student/fees/challans/{challan['id']}/pdf", self.student_token)
        self.assertEqual(status, 200)
        self.assertIn("pdf", content_type)
        self.assertGreater(len(body), 500)
