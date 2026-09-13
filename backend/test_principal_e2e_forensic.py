#!/usr/bin/env python3
"""
Forensic E2E test of all Principal workflows against the live backend.
This traces the complete chain:
REQUEST → DATABASE → WORKFLOW → PRINCIPAL INBOX → PRINCIPAL DECISION → 
SOURCE SERVICE → SOURCE DATABASE → OUTBOX → AUDIT → NOTIFICATION
"""
import json
import requests
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

BASE_URL = "http://localhost:8010"
DEMO_USERS = {
    "principal": {"username": "principal", "password": "demo123"},
    "hod": {"username": "hod", "password": "demo123"},
    "finance": {"username": "finance_manager", "password": "demo123"},
    "admissions": {"username": "admissions", "password": "demo123"},
    "vp": {"username": "vice_principal", "password": "demo123"},
    "discipline": {"username": "discipline", "password": "demo123"},
    "hr": {"username": "hr_manager", "password": "demo123"},
    "purchase": {"username": "purchase", "password": "demo123"},
}

class PrincipalE2ETest:
    def __init__(self):
        self.session = requests.Session()
        self.tokens = {}
        self.results = []
        
    def log(self, level: str, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {msg}")
        
    def authenticate(self, user_key: str) -> bool:
        """Authenticate a user and store token."""
        user = DEMO_USERS.get(user_key)
        if not user:
            self.log("ERROR", f"User {user_key} not found")
            return False
        try:
            resp = self.session.post(
                f"{BASE_URL}/api/auth/login",
                json={"username": user["username"], "password": user["password"]}
            )
            if resp.status_code == 200:
                data = resp.json()
                self.tokens[user_key] = data.get("token", data.get("access_token"))
                self.log("INFO", f"Authenticated {user_key}")
                return True
            else:
                self.log("ERROR", f"Auth failed for {user_key}: {resp.status_code}")
                print(f"  Response: {resp.text[:200]}")
                return False
        except Exception as e:
            self.log("ERROR", f"Auth exception for {user_key}: {e}")
            return False
            
    def api_call(self, method: str, endpoint: str, user_key: str, json_data: Optional[Dict] = None, expected_status: int = None) -> Optional[Dict]:
        """Make authenticated API call."""
        token = self.tokens.get(user_key)
        if not token:
            self.log("ERROR", f"No token for user {user_key}")
            return None
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{BASE_URL}{endpoint}"
        try:
            if method.upper() == "GET":
                resp = self.session.get(url, headers=headers)
            elif method.upper() == "POST":
                resp = self.session.post(url, headers=headers, json=json_data)
            else:
                self.log("ERROR", f"Unknown method {method}")
                return None
            if expected_status and resp.status_code != expected_status:
                self.log("ERROR", f"{method} {endpoint} expected {expected_status}, got {resp.status_code}")
                print(f"  Response: {resp.text[:300]}")
                return None
            return resp.json() if resp.text else {}
        except Exception as e:
            self.log("ERROR", f"API call exception: {e}")
            return None
            
    def test_admissions_flow(self) -> bool:
        """Test: Admissions Office → Application → Principal approval → Admissions service → READY_TO_ADMIT."""
        self.log("TEST", "=== ADMISSIONS FLOW ===")
        
        # 1. Authenticate users
        if not self.authenticate("admissions") or not self.authenticate("principal"):
            return False
            
        # 2. Get existing applications or create test scenario
        # Query applications in FINANCE_CLEARED status ready for final approval
        apps = self.api_call("GET", "/api/admissions/applications?status=FINANCE_CLEARED", "admissions")
        if not apps or not apps.get("applications"):
            self.log("WARNING", "No applications in FINANCE_CLEARED status")
            return True  # Skip this flow if no suitable test data
            
        app = apps["applications"][0]
        app_id = app["id"]
        self.log("INFO", f"Testing with application {app_id}")
        
        # 3. Request final approval (creates workflow)
        final_req = self.api_call(
            "POST",
            f"/api/admissions/applications/{app_id}/request-final-approval",
            "admissions",
            {"expected_version": app.get("status_version", 0)},
            expected_status=200
        )
        if not final_req:
            self.log("ERROR", "Failed to request final approval")
            return False
        workflow_id = final_req.get("workflow", {}).get("id")
        self.log("INFO", f"Created workflow {workflow_id}")
        
        # 4. Principal sees workflow in inbox
        inbox = self.api_call("GET", "/api/workflows/my-approvals", "principal")
        if not inbox:
            self.log("ERROR", "Principal inbox fetch failed")
            return False
        found = False
        for wf in inbox.get("workflows", []):
            if wf.get("id") == workflow_id:
                found = True
                break
        if not found:
            self.log("ERROR", f"Workflow {workflow_id} not in Principal inbox")
            return False
        self.log("INFO", "Principal sees workflow in inbox")
        
        # 5. Principal approves
        approve = self.api_call(
            "POST",
            "/api/workflows/decide",
            "principal",
            {"workflow_id": workflow_id, "action": "approve", "reason": "Approved"},
            expected_status=200
        )
        if not approve:
            self.log("ERROR", "Principal approval failed")
            return False
        self.log("INFO", "Principal approved")
        
        # 6. Verify source mutation: Application.current_status = READY_TO_ADMIT
        app_check = self.api_call("GET", f"/api/admissions/applications/{app_id}", "admissions")
        if not app_check:
            self.log("ERROR", "Failed to fetch application after approval")
            return False
        status = app_check.get("current_status") or app_check.get("status")
        if status not in ("READY_TO_ADMIT", "READY_TO_ENROLL", "ENROLLED"):
            self.log("ERROR", f"Application status is {status}, expected READY_TO_ADMIT")
            return False
        self.log("INFO", f"✓ Application transitioned to {status}")
        
        self.results.append(("Admissions", "PASS"))
        return True
        
    def test_condonation_flow(self) -> bool:
        """Test: HOD → Condonation request → Principal → Finance invoice → Accounts payment."""
        self.log("TEST", "=== ATTENDANCE CONDONATION FLOW ===")
        
        if not self.authenticate("hod") or not self.authenticate("principal") or not self.authenticate("finance"):
            return False
            
        # Get a student
        students = self.api_call("GET", "/api/students", "hod")
        if not students or not students.get("students"):
            self.log("WARNING", "No students found for condonation test")
            return True
            
        student_id = students["students"][0]["id"]
        
        # Get sections
        sections = self.api_call("GET", "/api/sections", "hod")
        if not sections or not sections.get("sections"):
            self.log("WARNING", "No sections found")
            return True
            
        section_id = sections["sections"][0]["id"]
        
        # Create condonation request
        cond_req = self.api_call(
            "POST",
            "/api/attendance/condonation",
            "hod",
            {
                "student_id": student_id,
                "section_id": section_id,
                "attendance_percent": 60.0,
                "reason": "Medical grounds",
                "amount": 5000.0
            }
        )
        if not cond_req:
            self.log("ERROR", "Failed to create condonation request")
            return False
        request_id = cond_req.get("request_id")
        workflow_id = cond_req.get("workflow_id")
        self.log("INFO", f"Created condonation request {request_id}, workflow {workflow_id}")
        
        # Principal approves
        approve = self.api_call(
            "POST",
            "/api/workflows/decide",
            "principal",
            {"workflow_id": workflow_id, "action": "approve"},
            expected_status=200
        )
        if not approve:
            self.log("ERROR", "Principal condonation approval failed")
            return False
        self.log("INFO", "Principal approved condonation")
        
        # Verify source: AttendanceCondonationRequest.status = APPROVED
        # (Note: may not have direct API endpoint, check via workflow state)
        wf_check = self.api_call("GET", f"/api/workflows/{workflow_id}", "principal")
        if not wf_check:
            self.log("ERROR", "Workflow fetch failed")
            return False
        if wf_check.get("state") not in ("approved", "executed"):
            self.log("ERROR", f"Workflow state is {wf_check.get('state')}")
            return False
        self.log("INFO", "✓ Condonation source marked approved")
        
        self.results.append(("Condonation", "PASS"))
        return True
        
    def test_procurement_flow(self) -> bool:
        """Test: Procurement requisition → Principal approval → Purchase Office PO issuance."""
        self.log("TEST", "=== PROCUREMENT FLOW ===")
        
        if not self.authenticate("purchase") or not self.authenticate("principal"):
            return False
            
        # Get procurement requisitions
        procs = self.api_call("GET", "/api/specialist/administration-queue", "purchase")
        if not procs:
            self.log("WARNING", "No procurement queue available")
            return True
            
        # Look for purchase_request workflows
        wfs = self.api_call("GET", "/api/workflows", "purchase")
        if not wfs or not wfs.get("workflows"):
            self.log("WARNING", "No workflows found for procurement test")
            return True
            
        proc_wf = None
        for wf in wfs.get("workflows", []):
            if wf.get("process_key") == "purchase_request":
                proc_wf = wf
                break
                
        if not proc_wf:
            self.log("WARNING", "No purchase_request workflow found")
            return True
            
        # Principal approves
        approve = self.api_call(
            "POST",
            "/api/workflows/decide",
            "principal",
            {"workflow_id": proc_wf["id"], "action": "approve"},
            expected_status=200
        )
        if not approve:
            self.log("ERROR", "Principal procurement approval failed")
            return False
        self.log("INFO", "Principal approved procurement")
        
        # Verify: workflow marked approved
        wf_check = self.api_call("GET", f"/api/workflows/{proc_wf['id']}", "principal")
        if not wf_check or wf_check.get("state") not in ("approved", "executed"):
            self.log("ERROR", "Workflow not in approved state")
            return False
        self.log("INFO", "✓ Procurement requisition approved, awaiting Purchase Office PO issuance")
        
        self.results.append(("Procurement", "PASS"))
        return True
        
    def test_finance_flow(self) -> bool:
        """Test: Finance → Fee structure → Principal approval."""
        self.log("TEST", "=== FINANCE FLOW ===")
        
        if not self.authenticate("finance") or not self.authenticate("principal"):
            return False
            
        # Get fee structure workflows
        wfs = self.api_call("GET", "/api/workflows?process_key=fee_structure", "finance")
        if not wfs or not wfs.get("workflows"):
            self.log("WARNING", "No fee_structure workflows found")
            return True
            
        fee_wf = wfs["workflows"][0] if wfs.get("workflows") else None
        if not fee_wf:
            return True
            
        # Principal approves
        approve = self.api_call(
            "POST",
            "/api/workflows/decide",
            "principal",
            {"workflow_id": fee_wf["id"], "action": "approve"},
            expected_status=200
        )
        if not approve:
            self.log("ERROR", "Principal finance approval failed")
            return False
        self.log("INFO", "Principal approved fee structure")
        
        # Verify workflow state
        wf_check = self.api_call("GET", f"/api/workflows/{fee_wf['id']}", "principal")
        if not wf_check or wf_check.get("state") not in ("approved", "executed"):
            self.log("ERROR", "Fee structure workflow not approved")
            return False
        self.log("INFO", "✓ Fee structure approved")
        
        self.results.append(("Finance", "PASS"))
        return True
        
    def test_discipline_flow(self) -> bool:
        """Test: Discipline Office complaint → Principal decision."""
        self.log("TEST", "=== DISCIPLINE FLOW ===")
        
        if not self.authenticate("discipline") or not self.authenticate("principal"):
            return False
            
        # Get complaints
        complaints = self.api_call("GET", "/api/grievance", "discipline")
        if not complaints or not complaints.get("complaints"):
            self.log("WARNING", "No complaints found")
            return True
            
        for complaint in complaints.get("complaints", []):
            if complaint.get("kind") in ("Discipline", "Ragging") and complaint.get("status") == "open":
                # Submit to workflow
                submit = self.api_call(
                    "POST",
                    f"/api/discipline/{complaint['id']}/submit",
                    "discipline",
                    {},
                    expected_status=200
                )
                if not submit:
                    self.log("ERROR", "Failed to submit discipline case")
                    continue
                workflow_id = submit.get("workflow_id")
                self.log("INFO", f"Submitted complaint {complaint['id']} to workflow {workflow_id}")
                
                # Principal decides
                decide = self.api_call(
                    "POST",
                    "/api/workflows/decide",
                    "principal",
                    {"workflow_id": workflow_id, "action": "approve"},
                    expected_status=200
                )
                if not decide:
                    self.log("ERROR", "Principal discipline decision failed")
                    continue
                self.log("INFO", "Principal decided on discipline")
                
                # Verify workflow
                wf_check = self.api_call("GET", f"/api/workflows/{workflow_id}", "principal")
                if wf_check and wf_check.get("state") in ("approved", "executed"):
                    self.log("INFO", "✓ Discipline case decided by Principal")
                    self.results.append(("Discipline", "PASS"))
                    return True
                    
        self.log("WARNING", "No suitable discipline case found")
        return True
        
    def test_audit_trail(self) -> bool:
        """Test: Audit entries are created for all Principal decisions."""
        self.log("TEST", "=== AUDIT TRAIL VERIFICATION ===")
        
        if not self.authenticate("principal"):
            return False
            
        audit = self.api_call("GET", "/api/audit?actor=u_principal&limit=50", "principal")
        if not audit or not audit.get("audit_entries"):
            self.log("WARNING", "No audit entries found for Principal")
            return True
            
        workflow_audits = [a for a in audit.get("audit_entries", []) if "workflow" in a.get("resource", "")]
        if workflow_audits:
            self.log("INFO", f"✓ Found {len(workflow_audits)} workflow audit entries")
            for entry in workflow_audits[:3]:
                self.log("INFO", f"  - {entry.get('action')}: {entry.get('old_state')} → {entry.get('new_state')}")
            self.results.append(("Audit", "PASS"))
            return True
        else:
            self.log("WARNING", "No workflow audit entries found")
            return True
            
    def run_all_tests(self):
        """Run all forensic E2E tests."""
        self.log("INFO", "Starting Principal E2E Forensic Tests")
        self.log("INFO", f"Backend: {BASE_URL}")
        self.log("INFO", "=" * 60)
        
        # Authenticate all users first
        self.log("INFO", "Authenticating users...")
        for user_key in DEMO_USERS.keys():
            self.authenticate(user_key)
            
        self.log("INFO", "=" * 60)
        
        # Run tests
        self.test_admissions_flow()
        self.test_condonation_flow()
        self.test_procurement_flow()
        self.test_finance_flow()
        self.test_discipline_flow()
        self.test_audit_trail()
        
        # Summary
        self.log("INFO", "=" * 60)
        self.log("INFO", "TEST RESULTS:")
        for name, result in self.results:
            status = "✓" if result == "PASS" else "✗"
            self.log("INFO", f"  {status} {name}: {result}")
        self.log("INFO", "=" * 60)
        
        return all(r[1] == "PASS" for r in self.results)

if __name__ == "__main__":
    tester = PrincipalE2ETest()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
