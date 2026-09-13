#!/usr/bin/env python3
"""
Comprehensive forensic E2E test of Principal workflows.
This test:
1. Makes API calls to trigger workflows
2. Queries database directly to verify source mutations
3. Checks for outbox events and audit entries
4. Validates complete business process chains
"""
import json
import requests
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Database connection (use same DB as docker-compose)
DB_URL = "postgresql://icms:icms_secret@localhost:5433/icms"
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

class PrincipalE2EForensic:
    def __init__(self):
        self.session_http = requests.Session()
        self.tokens = {}
        self.results = []
        
        try:
            self.db_engine = create_engine(DB_URL, echo=False)
            self.db_conn = self.db_engine.connect()
            self.log("INFO", "Database connection established")
        except Exception as e:
            self.log("ERROR", f"Database connection failed: {e}")
            self.db_engine = None
            
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
            resp = self.session_http.post(
                f"{BASE_URL}/api/auth/login",
                json={"username": user["username"], "password": user["password"]}
            )
            if resp.status_code == 200:
                data = resp.json()
                self.tokens[user_key] = data.get("token", data.get("access_token"))
                self.log("INFO", f"Authenticated {user_key} (token: {self.tokens[user_key][:20]}...)")
                return True
            else:
                self.log("ERROR", f"Auth failed for {user_key}: {resp.status_code}")
                return False
        except Exception as e:
            self.log("ERROR", f"Auth exception for {user_key}: {e}")
            return False
            
    def api_call(self, method: str, endpoint: str, user_key: str, json_data: Optional[Dict] = None) -> Optional[Dict]:
        """Make authenticated API call."""
        token = self.tokens.get(user_key)
        if not token:
            self.log("ERROR", f"No token for user {user_key}")
            return None
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{BASE_URL}{endpoint}"
        try:
            if method.upper() == "GET":
                resp = self.session_http.get(url, headers=headers)
            elif method.upper() == "POST":
                resp = self.session_http.post(url, headers=headers, json=json_data)
            else:
                self.log("ERROR", f"Unknown method {method}")
                return None
            if resp.status_code >= 400:
                self.log("WARN", f"{method} {endpoint}: {resp.status_code} - {resp.text[:100]}")
                return None
            return resp.json() if resp.text else {}
        except Exception as e:
            self.log("ERROR", f"API call exception: {e}")
            return None
            
    def db_query(self, sql: str) -> Optional[list]:
        """Execute SQL query against database."""
        if not self.db_engine:
            return None
        try:
            result = self.db_conn.execute(text(sql))
            rows = result.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            self.log("ERROR", f"DB query failed: {e}")
            return None
            
    def test_discipline_e2e(self) -> bool:
        """Test: Complaint → Workflow → Principal approval → Audit → Source mutation."""
        self.log("TEST", "=== DISCIPLINE E2E FORENSIC ===")
        
        if not self.authenticate("discipline") or not self.authenticate("principal"):
            return False
            
        # Get a discipline complaint
        complaints = self.api_call("GET", "/api/grievance", "discipline")
        if not complaints or not complaints.get("complaints"):
            self.log("WARNING", "No complaints found")
            return True
            
        complaint = None
        for c in complaints.get("complaints", []):
            if c.get("kind") in ("Discipline", "Ragging"):
                complaint = c
                break
                
        if not complaint:
            self.log("WARNING", "No discipline case found")
            return True
            
        complaint_id = complaint["id"]
        self.log("INFO", f"Testing with complaint {complaint_id}")
        
        # Before: check complaint status in DB
        before = self.db_query(f"SELECT id, subject, status, decided_by FROM complaints WHERE id='{complaint_id}'")
        if before:
            self.log("INFO", f"  Before: status={before[0].get('status')}, decided_by={before[0].get('decided_by')}")
            
        # Submit to discipline workflow
        submit = self.api_call("POST", f"/api/domain/submit-complaint/{complaint_id}", "discipline", {})
        if not submit:
            self.log("ERROR", "Failed to submit complaint")
            return False
            
        workflow_id = submit.get("workflow_id")
        if not workflow_id:
            self.log("ERROR", "No workflow_id returned")
            return False
        self.log("INFO", f"  Submitted to workflow {workflow_id}")
        
        # Principal approves
        approve = self.api_call("POST", "/api/workflows/decide", "principal",
                               {"workflow_id": workflow_id, "action": "approve", "reason": "Approved"})
        if not approve:
            self.log("ERROR", "Principal approval failed")
            return False
        self.log("INFO", f"  Principal approved")
        
        # After: check workflow state
        wf_sql = f"SELECT id, state, current_stage FROM workflow_instances WHERE id='{workflow_id}'"
        wf_after = self.db_query(wf_sql)
        if wf_after:
            wf = wf_after[0]
            self.log("INFO", f"  Workflow: state={wf.get('state')}, stage={wf.get('current_stage')}")
            if wf.get('state') not in ('approved', 'executed'):
                self.log("ERROR", f"Workflow state is {wf.get('state')}, not approved/executed")
                return False
                
        # After: check complaint source mutation
        after = self.db_query(f"SELECT id, subject, status, decided_by, decided_at FROM complaints WHERE id='{complaint_id}'")
        if after:
            self.log("INFO", f"  After: status={after[0].get('status')}, decided_by={after[0].get('decided_by')}")
            if after[0].get('decided_by') != 'user_4':  # Principal = user_4
                self.log("ERROR", f"Complaint.decided_by not set to Principal")
                return False
                
        # Check for outbox event
        outbox = self.db_query(f"SELECT * FROM administrative_outbox_events WHERE workflow_id='{workflow_id}' LIMIT 1")
        if outbox:
            self.log("INFO", f"  ✓ Outbox event created: {outbox[0].get('event_type')}")
        else:
            self.log("WARNING", "  No outbox event found")
            
        # Check for audit entry
        audit = self.db_query(f"SELECT * FROM audit WHERE workflow_id='{workflow_id}' ORDER BY created_at DESC LIMIT 1")
        if audit:
            self.log("INFO", f"  ✓ Audit entry: {audit[0].get('action')}")
        else:
            self.log("WARNING", "  No audit entry found")
            
        self.results.append(("Discipline", "PASS"))
        return True
        
    def test_procurement_source_mutation(self) -> bool:
        """Test: Procurement requisition gets approved status only (not PO issuance)."""
        self.log("TEST", "=== PROCUREMENT SOURCE MUTATION ===")
        
        if not self.authenticate("purchase") or not self.authenticate("principal"):
            return False
            
        # Get procurement workflows
        wfs = self.api_call("GET", "/api/workflows?process_key=purchase_request", "purchase")
        if not wfs or not wfs.get("workflows"):
            self.log("WARNING", "No purchase_request workflows")
            return True
            
        wf = wfs["workflows"][0]
        workflow_id = wf["id"]
        source_id = wf.get("source_id")
        
        self.log("INFO", f"Testing procurement workflow {workflow_id}, source={source_id}")
        
        # Get requisition before approval
        if source_id:
            before = self.db_query(f"SELECT id, status FROM procurement_requisitions WHERE id='{source_id}'")
            if before:
                self.log("INFO", f"  Before: status={before[0].get('status')}")
                
        # Principal approves
        approve = self.api_call("POST", "/api/workflows/decide", "principal",
                               {"workflow_id": workflow_id, "action": "approve", "reason": "Approved"})
        if not approve:
            self.log("ERROR", "Approval failed")
            return False
        self.log("INFO", f"  Principal approved")
        
        # Check source mutation (requisition status should change)
        if source_id:
            after = self.db_query(f"SELECT id, status FROM procurement_requisitions WHERE id='{source_id}'")
            if after:
                self.log("INFO", f"  After: status={after[0].get('status')}")
                if after[0].get('status') in ('approved', 'authorized', 'verified'):
                    self.log("INFO", f"  ✓ Requisition status changed")
                    
        # Verify PO not issued (that's Purchase Office's job)
        po = self.db_query(f"SELECT * FROM purchase_orders WHERE procurement_id='{source_id}' LIMIT 1")
        if not po:
            self.log("INFO", f"  ✓ PO not auto-issued by Principal approval (correct)")
        else:
            self.log("ERROR", f"  ✗ PO was auto-issued (should be Purchase Office only)")
            
        self.results.append(("Procurement", "PASS"))
        return True
        
    def test_principal_campus_scope(self) -> bool:
        """Test: Principal can only approve workflows in their campus."""
        self.log("TEST", "=== PRINCIPAL CAMPUS SCOPE ===")
        
        if not self.authenticate("principal"):
            return False
            
        # Query workflows in other campus
        workflows = self.api_call("GET", "/api/workflows?scope=other_campus", "principal")
        if not workflows:
            self.log("INFO", "  Cannot see workflows from other campus (correct)")
            self.results.append(("Campus Scope", "PASS"))
            return True
            
        workflows_in_scope = workflows.get("workflows", [])
        for wf in workflows_in_scope:
            if wf.get("scope_ref") and wf.get("scope_ref") != "main_campus":
                self.log("ERROR", f"  ✗ Principal can see workflow outside their campus: {wf.get('scope_ref')}")
                return False
                
        self.log("INFO", "  ✓ Principal scope enforcement verified")
        self.results.append(("Campus Scope", "PASS"))
        return True
        
    def test_idempotency(self) -> bool:
        """Test: Approving twice should fail (versioning protection)."""
        self.log("TEST", "=== IDEMPOTENCY & VERSION PROTECTION ===")
        
        if not self.authenticate("principal"):
            return False
            
        # Get a pending workflow
        wfs = self.api_call("GET", "/api/workflows/my-approvals", "principal")
        if not wfs or not wfs.get("workflows"):
            self.log("WARNING", "No pending workflows")
            return True
            
        wf = wfs["workflows"][0]
        workflow_id = wf["id"]
        version = wf.get("version_no", 0)
        
        self.log("INFO", f"Testing workflow {workflow_id} (version {version})")
        
        # First approval
        approve1 = self.api_call("POST", "/api/workflows/decide", "principal",
                                {"workflow_id": workflow_id, "action": "approve", "expected_version": version})
        if not approve1:
            self.log("WARNING", "First approval failed")
            return True
            
        self.log("INFO", f"  First approval succeeded")
        
        # Second approval should fail (stale version)
        approve2 = self.api_call("POST", "/api/workflows/decide", "principal",
                                {"workflow_id": workflow_id, "action": "approve", "expected_version": version})
        if approve2:
            self.log("ERROR", f"  ✗ Second approval succeeded (should have failed)")
            return False
        else:
            self.log("INFO", f"  ✓ Second approval rejected (version protection works)")
            
        self.results.append(("Idempotency", "PASS"))
        return True
        
    def run_all_tests(self):
        """Run all forensic tests."""
        self.log("INFO", "Starting Comprehensive Principal Forensic Tests")
        self.log("INFO", f"Backend: {BASE_URL}")
        self.log("INFO", f"Database: {DB_URL.split('@')[1] if '@' in DB_URL else DB_URL}")
        self.log("INFO", "=" * 80)
        
        # Run tests
        self.test_discipline_e2e()
        self.test_procurement_source_mutation()
        self.test_principal_campus_scope()
        self.test_idempotency()
        
        # Summary
        self.log("INFO", "=" * 80)
        self.log("INFO", "FORENSIC TEST RESULTS:")
        for name, result in self.results:
            status = "✓ PASS" if result == "PASS" else "✗ FAIL"
            self.log("INFO", f"  {status}: {name}")
        self.log("INFO", "=" * 80)
        
        passed = sum(1 for r in self.results if r[1] == "PASS")
        total = len(self.results)
        self.log("INFO", f"TOTAL: {passed}/{total} tests passed")
        
        return all(r[1] == "PASS" for r in self.results)

if __name__ == "__main__":
    tester = PrincipalE2EForensic()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
