import json
from datetime import datetime
from sqlalchemy import create_engine, text
import requests

BASE_URL = "http://localhost:8010"
DB_URL = "postgresql://icms:icms_secret@localhost:5433/icms"

DEMO_USERS = {
    "principal": {"username": "principal", "password": "demo123"},
    "hod": {"username": "hod", "password": "demo123"},
    "vp": {"username": "vice_principal", "password": "demo123"},
    "admissions": {"username": "admissions", "password": "demo123"},
    "finance": {"username": "finance_manager", "password": "demo123"},
}

engine = create_engine(DB_URL, echo=False)


def auth(user_key):
    user = DEMO_USERS[user_key]
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": user["username"], "password": user["password"]})
    print(f"[auth] {user_key}: {r.status_code}")
    data = r.json()
    return data.get("token") or data.get("access_token")


def api(token, method, endpoint, json_data=None):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.request(method, f"{BASE_URL}{endpoint}", headers=headers, json=json_data)
    print(f"[api] {method.upper()} {endpoint}: {r.status_code}")
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    if r.status_code >= 400:
        print(json.dumps(data, indent=2)[:1200])
    return data, r.status_code


def db_query(sql, params=None):
    params = params or {}
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]


def fmt(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False)


tokens = {k: auth(k) for k in DEMO_USERS}

print("\n=== 1) Admissions final approval fresh chain ===")
phase5, _ = api(tokens["admissions"], "GET", "/api/admissions/phase5-status")
apps = phase5.get("applications", []) if isinstance(phase5, dict) else []
finance_cleared = [a for a in apps if a.get("status") == "FINANCE_CLEARED"]
print("finance_cleared apps:", len(finance_cleared))
for a in finance_cleared[:10]:
    print(a.get("id"), a.get("status"), a.get("campus"))

if not finance_cleared:
    raise SystemExit("No FINANCE_CLEARED admissions found; cannot verify final-approval chain.")

app = finance_cleared[0]
app_id = app["id"]
print("Selected app", app_id)
req, _ = api(tokens["admissions"], "POST", f"/api/admissions/{app_id}/final-approval", {"expected_status_version": app["status_version"]})
print("request response", fmt(req))
workflow_id = req.get("workflow_id")
print("workflow_id", workflow_id)

principal_inbox, _ = api(tokens["principal"], "GET", "/api/workflows?scope=inbox")
principal_wfs = principal_inbox.get("workflows", [])
print("Principal inbox count", len(principal_wfs))
for wf in principal_wfs:
    print("WF in inbox", wf.get("id"), wf.get("process_key"), wf.get("source_type"), wf.get("source_id"))

approve, status = api(tokens["principal"], "POST", "/api/workflows/decide", {"workflow_id": workflow_id, "action": "approve", "reason": "Live verification"})
print("approve result status", status)
print(fmt(approve))

rows = db_query("SELECT id, current_status, status_version FROM applications WHERE id = :id", {"id": app_id})
print("DB app after approval", fmt(rows))

print("\n=== 2) Course registration escalation + principal approval ===")
rows = db_query("SELECT id, student_id, section_id, status FROM enrollments WHERE status = 'requested' ORDER BY created_at DESC LIMIT 20")
print("Requested enrollments", fmt(rows))
if not rows:
    print("No requested enrollments found; skipping course registration verification.")
else:
    enr = rows[0]
    enrollment_id = enr["id"]
    esc, esc_status = api(tokens["vp"], "POST", f"/api/portal/faculty/course-registrations/{enrollment_id}/escalate")
    print("Escalate response", fmt(esc), "status", esc_status)
    wf_id = esc.get("workflow_id") if isinstance(esc, dict) else None
    if wf_id:
        approve2, _ = api(tokens["principal"], "POST", "/api/workflows/decide", {"workflow_id": wf_id, "action": "approve", "reason": "Course registration live verification"})
        print("course registration approve response", fmt(approve2))
    rows2 = db_query("SELECT id, student_id, section_id, status FROM enrollments WHERE id = :id", {"id": enrollment_id})
    print("Enrollment after principal decision", fmt(rows2))

print("\n=== 3) Attendance condonation fresh chain ===")
students, _ = api(tokens["hod"], "GET", "/api/students")
students_rows = students.get("students", []) if isinstance(students, dict) else []
student = next((s for s in students_rows if s.get("attendance_pct", 100) < 75), None)
print("Selected student for condonation", student)
sections, _ = api(tokens["hod"], "GET", "/api/attendance/sections")
section_rows = sections.get("sections", []) if isinstance(sections, dict) else []
section = section_rows[0] if section_rows else None
print("Selected section", section)
if student and section:
    cond_body = {
        "student_id": student["id"],
        "section_id": section["id"],
        "attendance_percent": 70.0,
        "reason": "Live verification condonation",
        "amount": 5000.0,
    }
    cond, cond_status = api(tokens["hod"], "POST", "/api/attendance/condonation", cond_body)
    print("condonation create response", fmt(cond), "status", cond_status)
    wf_id = cond.get("workflow_id")
    if wf_id:
        approve3, _ = api(tokens["principal"], "POST", "/api/workflows/decide", {"workflow_id": wf_id, "action": "approve", "reason": "Condonation live verification"})
        print("condonation approve response", fmt(approve3))
    cond_rows = db_query("SELECT id, status, decided_by, decided_at FROM attendance_condonation_requests WHERE student_id = :sid ORDER BY created_at DESC LIMIT 20", {"sid": student["id"]})
    print("Condonation rows after approval", fmt(cond_rows))
else:
    print("Skipping condonation because no suitable student/section was available.")

print("\n=== 4) Existing seeded discipline workflow still fails closed ===")
principal_inbox, _ = api(tokens["principal"], "GET", "/api/workflows?scope=inbox")
for wf in principal_inbox.get("workflows", []):
    if wf.get("process_key") == "disciplinary_action":
        print("Existing discipline workflow in inbox:", wf.get("id"), wf.get("source_type"), wf.get("source_id"))
        res, code = api(tokens["principal"], "POST", "/api/workflows/decide", {"workflow_id": wf.get("id"), "action": "approve"})
        print("discipline approve result code", code)
        print(fmt(res))
        break

print("\n--- audit done ---")
