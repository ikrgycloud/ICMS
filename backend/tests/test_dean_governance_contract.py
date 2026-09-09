"""Smoke/authorization contract tests for Dean governance APIs.

Run against the Docker API with the stack up: ``python -m unittest ...``.
"""
import json
import os
import unittest
from urllib import request, error

# Docker exposes the API on the host's 8010 port.  Using 8000 can accidentally
# exercise an unrelated local service rather than the ICMS container.
BASE = os.getenv("ICMS_API_URL", "http://127.0.0.1:8010")

class DeanGovernanceContractTests(unittest.TestCase):
    def call(self, method, path, token=None, body=None):
        headers={"Content-Type":"application/json"}
        if token: headers["Authorization"]=f"Bearer {token}"
        raw=json.dumps(body).encode() if body is not None else None
        try:
            with request.urlopen(request.Request(BASE+path,data=raw,headers=headers,method=method),timeout=10) as r:
                return r.status,json.loads(r.read() or b"{}")
        except error.HTTPError as e:
            return e.code,json.loads(e.read() or b"{}")
    def token(self,user):
        status,p=self.call("POST","/api/auth/login",body={"username":user,"password":"demo123"})
        self.assertEqual(status,200,p); return p["token"]
    def test_student_cannot_manage_governance(self):
        student=self.token("student")
        status,_=self.call("POST","/api/academics/committees",student,{"name":"x","committee_type":"quality"})
        self.assertEqual(status,403)
    def test_dean_can_read_attainment_and_readiness(self):
        dean=self.token("dean_academics")
        self.assertEqual(self.call("GET","/api/academics/attainment",dean)[0],200)
        self.assertEqual(self.call("GET","/api/academics/timetable/readiness",dean)[0],200)

if __name__ == "__main__": unittest.main()
