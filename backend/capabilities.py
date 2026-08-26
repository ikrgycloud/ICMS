# -*- coding: utf-8 -*-
"""
Capability map — the bridge between the 40 offices (Document Part B) and the
functional modules the app renders. It answers two questions:

  1. Which MODULES should this office see in its workspace?
  2. Within a module, which ACTIONS may this office (and selected internal role)
     perform — gated further by the RBAC matrix and the authority engine.

Modules are the app's functional applications (Students, Academics, Attendance,
Examinations, Finance, Library, HR, Hostel, Transport, Research, Placements,
Grievance, Governance, Admin). An office's blueprint "primary modules" (from the
catalog) are mapped onto these app modules here.

Nothing here grants authority by itself — every mutating action still passes
through authorize() in authority.py. This map only decides what is *offered*.
"""

# App module keys and their display metadata (icon is a glyph used by the UI).
MODULES = {
    "curriculum":   {"label": "Curriculum", "icon": "Curr", "group": "Academics"},
    "overview":     {"label": "Overview",      "icon": "◆", "group": "Workspace"},
    "my_schedule":  {"label": "My Schedule",   "icon": "📅", "group": "Workspace"},
    "calendar":     {"label": "Calendar",      "icon": "📆", "group": "Workspace"},
    "academic_calendar": {"label": "Academic Calendar", "icon": "🗓", "group": "Academics"},
    "students":     {"label": "Students",      "icon": "🎓", "group": "Academics"},
    "academics":    {"label": "Academics",     "icon": "📚", "group": "Academics"},
    "attendance":   {"label": "Attendance",    "icon": "✔", "group": "Academics"},
    "examinations": {"label": "Examinations",  "icon": "📝", "group": "Academics"},
    "admissions":   {"label": "Admissions",    "icon": "📥", "group": "Academics"},
    "research":     {"label": "Research",      "icon": "🔬", "group": "Academics"},
    "placements":   {"label": "Placements",    "icon": "💼", "group": "Academics"},
    "library":      {"label": "Library",       "icon": "📖", "group": "Services"},
    "hostel":       {"label": "Hostel",        "icon": "🏠", "group": "Services"},
    "transport":    {"label": "Transport",     "icon": "🚌", "group": "Services"},
    "grievance":    {"label": "Grievance",     "icon": "⚖", "group": "Services"},
    "finance":      {"label": "Finance",       "icon": "₹", "group": "Operations"},
    "hr":           {"label": "Human Resources","icon": "👥", "group": "Operations"},
    "procurement":  {"label": "Procurement",   "icon": "📦", "group": "Operations"},
    "assets":       {"label": "Assets",        "icon": "🖥", "group": "Operations"},
    "workflows":    {"label": "Workflows",     "icon": "⇅", "group": "Authority"},
    "delegation":   {"label": "Delegation",    "icon": "⤳", "group": "Authority"},
    "approvals":    {"label": "Approvals",     "icon": "✅", "group": "Authority"},
    "audit":        {"label": "Audit",         "icon": "⛓", "group": "Authority"},
    "directory":    {"label": "Directory",     "icon": "▦", "group": "Reference"},
    "matrices":     {"label": "Matrices",      "icon": "▩", "group": "Reference"},
    "governance":   {"label": "Governance",    "icon": "🏛", "group": "Authority"},
    "admin":        {"label": "System Admin",  "icon": "⚙", "group": "Authority"},
    "analytics":    {"label": "Analytics",     "icon": "📊", "group": "Workspace"},
    "integrations": {"label": "Integrations",  "icon": "🔌", "group": "Platform"},
}

# Modules every signed-in office gets.
BASE_MODULES = ["overview", "calendar", "academic_calendar",
                "workflows", "delegation", "audit", "directory", "matrices"]

# Per-office module assignment (office_n -> [module keys], in addition to BASE).
# Derived from each office's blueprint purpose + primary modules (Document Part B).
OFFICE_MODULES = {
    1:  ["governance", "analytics", "finance", "hr", "integrations", "approvals"], # Chairman
    2:  ["governance", "analytics", "finance", "approvals"],                       # Vice Chairman
    3:  ["analytics", "academics", "finance", "hr", "approvals"],                  # Campus Head
    4:  ["my_schedule", "analytics", "academics", "students", "admissions", "attendance", "examinations", "finance", "hr", "procurement", "assets", "hostel", "transport", "grievance", "approvals"],  # Principal: branch oversight views
    5:  ["academics", "students", "attendance", "examinations", "approvals"],      # Vice Principal
    6:  ["academics", "students", "examinations", "research", "approvals"],        # Dean Academics
    7:  ["hr", "procurement", "assets", "finance", "approvals"],                   # Dean Administration
    8:  ["students", "grievance", "hostel", "approvals"],                          # Dean Student Affairs
    9:  ["research", "analytics", "approvals"],                                    # Dean R&D / IQAC
    10: ["academics", "students", "attendance", "examinations", "hr", "approvals"],# HOD
    11: ["my_schedule", "academics", "attendance", "examinations", "research"], # Professor
    12: ["my_schedule", "academics", "attendance", "examinations", "research"], # Associate Professor
    13: ["my_schedule", "academics", "attendance", "examinations"],              # Assistant Professor
    14: ["my_schedule", "academics", "attendance", "examinations"],              # Lecturer
    15: ["admissions", "students", "approvals"],                                   # Admission Office
    16: ["examinations", "students", "approvals"],                                 # Exam Controller
    17: ["academics", "attendance", "approvals"],                                  # Academic Coordinator
    18: ["placements", "students", "analytics"],                                   # Placement Office
    19: ["library"],                                                              # Library
    20: ["grievance", "students"],                                                 # Grievance
    21: ["grievance", "students"],                                                 # Discipline
    22: ["finance", "students", "approvals", "analytics"],                         # Finance Manager
    23: ["finance", "students", "approvals"],                                      # Accounts
    24: ["hr", "approvals", "analytics"],                                          # HR Manager
    25: ["hr", "approvals"],                                                       # HR Executive
    26: ["procurement", "assets", "hr", "approvals"],                              # Admin Manager
    27: ["admin", "integrations", "assets", "approvals"],                          # IT Manager
    28: ["admin", "integrations", "assets", "approvals"],                          # System Admin
    29: ["assets", "approvals"],                                                   # Maintenance
    30: ["hostel", "students", "approvals"],                                       # Hostel Warden
    31: ["transport", "students", "approvals"],                                    # Transport
    32: ["procurement", "approvals"],                                              # Purchase
    33: ["assets", "procurement"],                                                 # Store / Inventory
    34: ["assets"],                                                               # Security
    35: ["students", "directory"],                                                 # Front Office
    36: ["students", "academics", "attendance", "examinations", "finance",         # Student Portal
         "library", "hostel", "transport", "placements", "grievance"],
    37: ["students", "finance"],                                                   # Parent Portal
    38: ["placements", "analytics"],                                               # Alumni
    39: ["finance", "audit", "analytics"],                                         # External Auditor
    40: ["governance", "analytics", "finance", "hr", "approvals"],                 # Governing Body
}

# Which verb (from the RBAC matrix) a module's key actions require. The UI uses
# this to decide whether to show an action as enabled; the API re-checks it.
# Format: module -> { action_name: verb }
MODULE_ACTIONS = {
    "calendar":     {"view": "view", "create": "create", "edit": "edit",
                     "delete": "delete"},
    "academic_calendar": {"view": "view", "create": "create", "edit": "edit",
                          "delete": "delete"},
    "students":     {"view": "view", "add": "create", "edit": "edit"},
    "academics":    {"view": "view", "create_section": "create", "create_course": "create", "edit": "edit",
                     "assign_faculty": "assign"},
    "attendance":   {"view": "view", "mark": "create", "correct": "edit"},
    "examinations": {"view": "view", "enter_marks": "create", "moderate": "verify",
                     "publish_result": "publish", "lock": "lock"},
    "admissions":   {"view": "view", "verify": "verify", "offer": "approve",
                     "reject": "reject"},
    "finance":      {"view": "view", "create_invoice": "create",
                     "record_payment": "create", "waive": "approve",
                     "approve_budget": "approve"},
    "hr":           {"view": "view", "post_job": "create", "approve_leave": "approve",
                     "reject_leave": "reject"},
    "library":      {"view": "view", "add_book": "create", "issue": "create",
                     "return": "edit"},
    "hostel":       {"view": "view", "allocate": "approve", "add_room": "create"},
    "transport":    {"view": "view", "assign": "approve", "add_route": "create"},
    "procurement":  {"view": "view", "raise": "create", "approve": "approve"},
    "assets":       {"view": "view", "add": "create", "retire": "edit"},
    "research":     {"view": "view", "add": "create", "approve": "approve"},
    "placements":   {"view": "view", "add_drive": "create"},
    "grievance":    {"view": "view", "raise": "create", "resolve": "edit",
                     "investigate": "verify"},
    "governance":   {"view": "view", "publish_policy": "publish", "edit_dashboard": "edit"},
    "admin":        {"view": "view", "configure": "configure"},
    "approvals":    {"view": "view", "approve": "approve", "reject": "reject"},
}


# Some actions are reserved to the offices that own the process (Document §10
# approval matrix + §9 invariants). Even if the RBAC verb is non-zero, an office
# not in this allow-list cannot perform the action. Absence here = no restriction
# beyond the RBAC verb + engine.
ACTION_OFFICE_ALLOW = {
    ("calendar", "create"): set(range(1, 36)) | {40},
    ("calendar", "edit"): set(range(1, 36)) | {40},
    ("calendar", "delete"): set(range(1, 36)) | {40},
    ("academic_calendar", "create"): {1, 2, 4, 5},
    ("academic_calendar", "edit"): {1, 2, 4, 5},
    ("academic_calendar", "delete"): {1, 2, 4, 5},
    ("students", "add"): {15, 35},                    # Admissions / Front office own creation
    ("students", "edit"): {10, 15, 35},               # Principal has oversight, not record editing
    ("academics", "create_section"): {6, 10, 17},     # Dean Acad, HOD, Acad Coordinator
    ("academics", "create_course"): {6, 10, 17},      # Curriculum owners
    ("academics", "assign_faculty"): {6, 10, 17},
    ("attendance", "mark"): {10, 11, 12, 13, 14, 17},  # HOD + faculty + coordinator
    ("attendance", "correct"): {10, 17},
    ("examinations", "enter_marks"): {11, 12, 13, 14, 16},  # faculty + exam cell
    ("examinations", "moderate"): {16},
    ("examinations", "publish_result"): {16},          # Exam Controller only (SoD)
    ("examinations", "lock"): {16},
    ("admissions", "verify"): {15},
    ("admissions", "offer"): {4, 15},
    ("admissions", "reject"): {4, 15},
    ("finance", "create_invoice"): {22, 23},
    ("finance", "record_payment"): {22, 23},
    ("finance", "waive"): {4, 22, 23},                 # Principal/CFO, Finance, Accounts
    ("finance", "approve_budget"): {1, 2, 3, 4, 22, 40},
    ("hr", "post_job"): {24, 25, 26},
    ("hr", "approve_leave"): {10, 24, 26},             # HOD, HR Mgr, Admin Mgr
    ("hr", "reject_leave"): {10, 24, 26},
    ("library", "add_book"): {19},
    ("library", "issue"): {19},
    ("library", "return"): {19},
    ("hostel", "allocate"): {8, 30},
    ("hostel", "add_room"): {30},
    ("transport", "assign"): {31},
    ("transport", "add_route"): {31},
    ("procurement", "raise"): {26, 29, 32, 33},
    ("procurement", "approve"): {4, 22, 26, 32},
    ("assets", "add"): {26, 27, 28, 29, 33},
    ("assets", "retire"): {26, 27, 28, 29, 33},
    ("research", "add"): {6, 9, 11, 12},
    ("research", "approve"): {6, 9},
    ("placements", "add_drive"): {18},
    ("grievance", "resolve"): {8, 20, 21},
    ("grievance", "investigate"): {8, 20, 21},
    ("governance", "publish_policy"): {1, 2, 40},
    ("governance", "edit_dashboard"): {1, 2, 40},
    ("admin", "configure"): {27, 28},
}


def action_allowed_for_office(module: str, action: str, office_n: int) -> bool:
    allow = ACTION_OFFICE_ALLOW.get((module, action))
    if allow is None:
        return True
    return office_n in allow


def modules_for_office(n: int) -> list:
    """Ordered, de-duplicated module list for an office."""
    mods = list(OFFICE_MODULES.get(n, []))
    if n in {4, 5, 6, 10, 17}:
        mods.append("curriculum")
    # base modules always available, appended after the office-specific ones
    ordered = []
    for m in ["overview"] + mods + [x for x in BASE_MODULES if x != "overview"]:
        if m not in ordered and m in MODULES:
            ordered.append(m)
    return ordered


def module_meta(key: str) -> dict:
    m = MODULES.get(key, {"label": key.title(), "icon": "•", "group": "Other"})
    return {"key": key, **m}
