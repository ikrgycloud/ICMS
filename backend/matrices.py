# -*- coding: utf-8 -*-
"""
Cross-cutting matrices (Document §9, §10, §11).
These are DATA, not code — the authority engine reads them. In production they
live in the Policy/Config service; here they seed the DB and drive authorize().
"""
from authority import (FULL, LIMITED, VIEW, RECOMMEND, DELEGATED, CONDITIONAL,
                       NOT_ALLOWED)

F, L, V, R, D, C, X = FULL, LIMITED, VIEW, RECOMMEND, DELEGATED, CONDITIONAL, NOT_ALLOWED

# ---------------------------------------------------------------------------
# §9  Office x Permission (RBAC) matrix — representative offices x core verbs.
#     Verbs beyond these default per-office from the office's "level".
# ---------------------------------------------------------------------------
# columns: view create edit delete approve reject verify publish export configure delegate audit
RBAC_MATRIX = {
    1:  {"view": F, "create": L, "edit": L, "delete": X, "approve": F, "reject": F, "verify": V, "publish": V, "export": F, "configure": L, "delegate": F, "audit": V},
    2:  {"view": F, "create": L, "edit": L, "delete": X, "approve": L, "reject": F, "verify": V, "publish": V, "export": F, "configure": L, "delegate": F, "audit": V},
    3:  {"view": F, "create": L, "edit": L, "delete": X, "approve": L, "reject": L, "verify": V, "publish": C, "export": F, "configure": X, "delegate": D, "audit": V},
    4:  {"view": F, "create": L, "edit": L, "delete": X, "approve": F, "reject": F, "verify": V, "publish": C, "export": F, "configure": X, "delegate": F, "audit": V},
    5:  {"view": F, "create": L, "edit": L, "delete": X, "approve": D, "reject": L, "verify": V, "publish": X, "export": L, "configure": X, "delegate": X, "audit": V},
    10: {"view": F, "create": F, "edit": L, "delete": X, "approve": L, "reject": L, "verify": V, "publish": X, "export": L, "configure": X, "delegate": X, "audit": V},
    14: {"view": L, "create": L, "edit": L, "delete": X, "approve": X, "reject": X, "verify": V, "publish": X, "export": L, "configure": X, "delegate": X, "audit": V},
    15: {"view": F, "create": F, "edit": L, "delete": X, "approve": L, "reject": L, "verify": F, "publish": X, "export": F, "configure": X, "delegate": X, "audit": V},
    16: {"view": F, "create": F, "edit": L, "delete": X, "approve": F, "reject": F, "verify": F, "publish": F, "export": F, "configure": L, "delegate": X, "audit": F},
    22: {"view": F, "create": F, "edit": L, "delete": X, "approve": F, "reject": F, "verify": F, "publish": X, "export": F, "configure": L, "delegate": X, "audit": F},
    24: {"view": F, "create": F, "edit": L, "delete": X, "approve": L, "reject": L, "verify": F, "publish": X, "export": F, "configure": X, "delegate": X, "audit": V},
    27: {"view": F, "create": F, "edit": F, "delete": L, "approve": L, "reject": L, "verify": V, "publish": X, "export": F, "configure": F, "delegate": X, "audit": F},
    28: {"view": F, "create": F, "edit": F, "delete": L, "approve": L, "reject": L, "verify": V, "publish": X, "export": F, "configure": F, "delegate": X, "audit": F},
    36: {"view": V, "create": L, "edit": X, "delete": X, "approve": X, "reject": X, "verify": X, "publish": X, "export": L, "configure": X, "delegate": X, "audit": X},
    37: {"view": V, "create": X, "edit": X, "delete": X, "approve": X, "reject": X, "verify": X, "publish": X, "export": X, "configure": X, "delegate": X, "audit": X},
    39: {"view": V, "create": X, "edit": X, "delete": X, "approve": X, "reject": X, "verify": V, "publish": X, "export": L, "configure": X, "delegate": X, "audit": V},
    40: {"view": F, "create": L, "edit": X, "delete": X, "approve": F, "reject": F, "verify": V, "publish": V, "export": F, "configure": L, "delegate": F, "audit": F},
}

# Default RBAC profile per organizational level (for offices not explicitly listed).
LEVEL_DEFAULT_RBAC = {
    1: {"view": F, "create": L, "edit": L, "delete": X, "approve": F, "reject": F, "verify": V, "publish": V, "export": F, "configure": L, "delegate": F, "audit": V},
    2: {"view": F, "create": L, "edit": L, "delete": X, "approve": L, "reject": F, "verify": V, "publish": V, "export": F, "configure": L, "delegate": F, "audit": V},
    3: {"view": F, "create": L, "edit": L, "delete": X, "approve": L, "reject": L, "verify": V, "publish": C, "export": F, "configure": X, "delegate": D, "audit": V},
    4: {"view": F, "create": L, "edit": L, "delete": X, "approve": L, "reject": L, "verify": V, "publish": C, "export": F, "configure": X, "delegate": D, "audit": V},
    5: {"view": F, "create": L, "edit": L, "delete": X, "approve": D, "reject": L, "verify": V, "publish": X, "export": L, "configure": X, "delegate": X, "audit": V},
    6: {"view": F, "create": F, "edit": L, "delete": X, "approve": L, "reject": L, "verify": F, "publish": X, "export": F, "configure": X, "delegate": X, "audit": V},
    7: {"view": F, "create": F, "edit": L, "delete": X, "approve": L, "reject": L, "verify": F, "publish": X, "export": F, "configure": L, "delegate": X, "audit": V},
    8: {"view": V, "create": L, "edit": X, "delete": X, "approve": X, "reject": X, "verify": X, "publish": X, "export": L, "configure": X, "delegate": X, "audit": X},
}


def rbac_for(office_n: int, level: int, verb: str) -> str:
    row = RBAC_MATRIX.get(office_n) or LEVEL_DEFAULT_RBAC.get(level, {})
    if verb in row:
        return row[verb]
    # Sensible defaults for verbs not in the 12-column representative matrix.
    if verb in ("submit", "review", "assign", "upload", "print", "download"):
        return LIMITED if level <= 7 else VIEW
    if verb in ("lock", "unlock", "override"):
        return LIMITED if office_n in (16, 27, 28) else NOT_ALLOWED
    return NOT_ALLOWED


# ---------------------------------------------------------------------------
# §10  Approval matrix — key processes: initiator -> reviewer -> approver ->
#      final approver, with an escalation target. Monetary limits (where they
#      apply) live in ApprovalLimit and auto-route above threshold.
# ---------------------------------------------------------------------------
# Each: key, label, chain[initiator, reviewer, approver, final], escalation,
#       owning office_n, valid workflow states for progression, has_amount
APPROVAL_MATRIX = [
    {"key": "student_admission", "label": "Student admission", "office_n": 15,
     "chain": ["Applicant", "Admissions Office", "Admissions Dir.", "Principal/Registrar"],
     "escalation": "VC", "amount": False},
    {"key": "course_registration", "label": "Course registration", "office_n": 36,
     "chain": ["Student", "Faculty Advisor", "HOD", "Vice Principal"],
     "escalation": "Principal", "amount": False},
    {"key": "attendance_correction", "label": "Attendance correction", "office_n": 10,
     "chain": ["Faculty", "Class Coordinator", "HOD", "Vice Principal"],
     "escalation": "Principal", "amount": False},
    {"key": "faculty_leave", "label": "Faculty leave", "office_n": 25,
     "chain": ["Faculty", "HOD", "Vice Principal", "Principal"],
     "escalation": "VC", "amount": False},
    {"key": "fee_waiver", "label": "Fee waiver / scholarship", "office_n": 22,
     "chain": ["Student", "Finance Office", "Finance Mgr", "CFO/Principal"],
     "escalation": "VC", "amount": True},
    {"key": "refund", "label": "Refund", "office_n": 23,
     "chain": ["Student", "Accounts Office", "Finance Mgr", "CFO"],
     "escalation": "VC", "amount": True},
    {"key": "purchase_request", "label": "Purchase request → PO", "office_n": 32,
     "chain": ["Any office", "Purchase Office", "Procurement Mgr", "CFO/Principal"],
     "escalation": "VC", "amount": True},
    {"key": "payroll_approval", "label": "Payroll approval", "office_n": 24,
     "chain": ["HR Executive", "HR Manager", "CFO", "CFO"],
     "escalation": "VC", "amount": True},
    {"key": "question_paper", "label": "Question paper approval", "office_n": 16,
     "chain": ["QP Setter", "QP Moderator", "QP Coordinator", "Controller of Exams"],
     "escalation": "VC", "amount": False},
    {"key": "marks_submission", "label": "Marks submission", "office_n": 16,
     "chain": ["Faculty", "Evaluation Coord.", "HOD", "Controller of Exams"],
     "escalation": "Principal", "amount": False},
    {"key": "result_publication", "label": "Result publication", "office_n": 16,
     "chain": ["Result Proc.", "Grade Verify", "Dy. Controller", "Controller of Exams"],
     "escalation": "VC", "amount": False},
    {"key": "revaluation", "label": "Revaluation", "office_n": 16,
     "chain": ["Student", "Scrutiny Officer", "Revaluator", "Controller of Exams"],
     "escalation": "VC", "amount": False},
    {"key": "certificate", "label": "Certificate / transcript", "office_n": 16,
     "chain": ["Student", "Cert/Transcript Officer", "Registrar", "Registrar"],
     "escalation": "VC", "amount": False},
    {"key": "hostel_allocation", "label": "Hostel allocation", "office_n": 30,
     "chain": ["Student", "Warden", "Chief Warden", "Hostel Dir."],
     "escalation": "Principal", "amount": False},
    {"key": "transport_allocation", "label": "Transport allocation", "office_n": 31,
     "chain": ["Student", "Route Coord.", "Transport Mgr", "Principal"],
     "escalation": "VC", "amount": False},
    {"key": "placement", "label": "Internship / placement", "office_n": 18,
     "chain": ["Student/Recruiter", "Placement Officer", "Placement Mgr", "Placement Dir."],
     "escalation": "Principal", "amount": False},
    {"key": "student_grievance", "label": "Student grievance", "office_n": 20,
     "chain": ["Student", "Grievance Office", "Dean Student Affairs", "Principal"],
     "escalation": "VC", "amount": False},
    {"key": "disciplinary_action", "label": "Disciplinary action", "office_n": 21,
     "chain": ["Discipline Office", "Dean Student Affairs", "Principal", "VC"],
     "escalation": "Chairman", "amount": False},
    {"key": "infrastructure_capex", "label": "Infrastructure / capex", "office_n": 29,
     "chain": ["Any office", "Maintenance/Facilities", "Principal", "VC/Chairman"],
     "escalation": "Chairman", "amount": True},
    {"key": "recruitment", "label": "Recruitment / promotion", "office_n": 24,
     "chain": ["HR", "HR Director", "Principal", "VC"],
     "escalation": "Chairman", "amount": False},
    {"key": "it_access", "label": "IT access / user creation", "office_n": 28,
     "chain": ["User", "System Admin", "Security Admin", "CIO"],
     "escalation": "Audit Admin", "amount": False},
    {"key": "branch_creation", "label": "Branch creation / closure", "office_n": 1,
     "chain": ["Chairman/VC", "VC", "Chairman", "Chairman"],
     "escalation": "—", "amount": False},
]

# Workflow states every request moves through (Document §7, office workflow images).
WF_STATES = ["draft", "submitted", "under_review", "reviewed", "approved",
             "executed", "rejected", "escalated"]

# Which state must an entity be in for each action to be valid (Document §7 step 11).
WF_VALID = {
    "submit": ["draft"],
    "review": ["submitted"],
    "approve": ["submitted", "under_review", "reviewed", "escalated"],
    "reject": ["submitted", "under_review", "reviewed", "escalated"],
    "execute": ["approved"],
    "escalate": ["submitted", "under_review", "reviewed"],
}

# Approval limits by process & scope level (Document §10 — configurable, never hardcoded).
# scope_level -> {process_key -> threshold}. Above threshold auto-escalates.
APPROVAL_LIMITS = {
    "campus":     {"fee_waiver": 100000, "refund": 100000, "purchase_request": 500000,
                   "payroll_approval": 2000000, "infrastructure_capex": 1000000},
    "university": {"fee_waiver": 500000, "refund": 500000, "purchase_request": 5000000,
                   "payroll_approval": 20000000, "infrastructure_capex": 10000000},
    "faculty":    {"fee_waiver": 50000, "refund": 50000, "purchase_request": 200000,
                   "infrastructure_capex": 300000},
    "department": {"fee_waiver": 20000, "refund": 20000, "purchase_request": 75000},
    "global":     {"fee_waiver": 10000000, "refund": 10000000, "purchase_request": 100000000,
                   "payroll_approval": 100000000, "infrastructure_capex": 100000000},
}


def approval_limit_for(scope_level: str, process_key: str):
    return APPROVAL_LIMITS.get(scope_level, {}).get(process_key)


# ---------------------------------------------------------------------------
# §11  Organizational scope matrix — role -> scope level. Broad -> narrow.
# ---------------------------------------------------------------------------
# Maps an office number to the scope level its head role acts over.
OFFICE_SCOPE = {
    1: "global", 40: "global",
    2: "university",
    3: "campus", 4: "campus", 5: "campus",
    6: "faculty", 7: "faculty", 8: "campus", 9: "university",
    10: "department", 11: "program", 12: "program", 13: "program", 14: "section",
    15: "campus", 16: "university", 17: "faculty", 18: "campus", 19: "campus",
    20: "campus", 21: "campus",
    22: "university", 23: "campus", 24: "university", 25: "campus", 26: "campus",
    27: "university", 28: "global", 29: "campus", 30: "campus", 31: "campus",
    32: "campus", 33: "campus", 34: "campus", 35: "campus",
    36: "individual", 37: "individual", 38: "individual", 39: "individual",
}


def scope_for(office_n: int) -> str:
    return OFFICE_SCOPE.get(office_n, "individual")
