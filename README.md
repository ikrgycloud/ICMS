# ICMS — Integrated College / University Management System

A full-stack, enterprise-grade university management platform built from the ICMS
developer blueprint: **40 offices across 8 authority levels, 268 internal roles**,
on a single **authority engine** that computes every decision from role, permission,
organizational scope, approval limit, delegation, workflow state and time-validity —
never hardcoded. Every decision is written to an **append-only, hash-chained audit ledger**.

Unlike a static portal, **every office gets its own workspace and can do its real job.**
The sidebar, the modules, and the actions available inside each module are computed per
login from the office, the selected internal role, and the authority matrices — modeled on
how large institutions (IITs, Ivy-League universities) actually separate duties.

---

## What makes this role-differentiated (the core idea)

Sign in as different demo accounts and the app is genuinely different each time:

| Sign in as | Sidebar & abilities |
|------------|--------------------|
| **Lecturer** | Academics, Attendance (mark today's roster), Examinations (enter marks — but *cannot* publish results) |
| **Examination Controller** | Examinations with authority to **publish results** (segregation of duties) |
| **Admissions Officer** | Admissions pipeline — verify, offer, reject applicants |
| **Finance Manager** | Fee invoices, record payments, approve waivers (auto-escalates above the scope limit), budgets |
| **Librarian** | Catalogue + circulation — issue and return books |
| **HOD** | Department academics, students, attendance, examinations, staff leave approvals |
| **Hostel Warden** | Room occupancy and allocation approvals |
| **Principal / Governing Body** | Institution-wide governance dashboard, analytics, approvals |
| **Student** | Personal portal — courses, attendance, results, fees, library, hostel, transport, placements, grievance |

---

## Persona-scoped portals (v3 — every login sees *its own* data)

Earlier versions differentiated the sidebar, but every module still rendered the
same institution-wide data to everyone. v3 fixes this at the data layer: key
logins are bound to real domain records and get a **personalized home dashboard
scoped to themselves**, not an admin roster.

| Persona | Home experience | Data scope |
|---------|-----------------|------------|
| **Student** (`student`) | Profile band with live CGPA / attendance, tabs for My Courses, Attendance-by-course, Results, and Fees | Only *their own* enrollments, attendance, marks, invoices, library loans |
| **Faculty** (`professor`, `lecturer`, …) | "My sections" list → click a section → live class roster with per-student attendance | Only the sections *they* teach; a 403 is returned for any other section |
| **Parent** (`parent`) | Guardian summary for one linked ward — academic standing + fee status | Exactly one student; cannot see any other record |

The binding is enforced server-side in `portal_api.py` (`/api/portal/...`) via a
`persona()` resolver that maps the signed-in user to a `Student` / `StaffMember`
row and filters every query by it. The frontend renders the matching home from
`src/personas/` based on a `persona` field returned by `/api/me`.

## Integrations (`/api/integrations`)

A first-class **Integrations** module (visible to IT Manager, System Admin and
the Chairman) modeling the external systems a real university runs: SSO/OIDC
identity, LMS (Canvas/Moodle via LTI), payment gateway, email/SMS, library
federation (Z39.50), biometric attendance, HR/payroll, finance ERP, BI, video
conferencing, anti-plagiarism and accreditation feeds. Each connector shows
health, owner office and protocol; the owning office (or IT/SysAdmin) can toggle
or sync it — every action is written to the audit ledger. Other offices get
read-only visibility, enforced by `_can_manage()`.


Each office also has an in-app **role picker** (top-right): one account, many internal roles.
Switching role re-issues an authority-bound token and re-renders the workspace for that role.

Every action button reflects a **live authority decision** — permitted actions run and show the
engine's verdict (`ALLOW` / `ESCALATE` / `DENY`); actions your role can't take are disabled with
the reason. Try entering marks as a student: the engine returns *not authorized*. Try a Rs 6,00,000
fee waiver as Finance Manager: it **escalates to the Vice-Chancellor** per the approval matrix.

---

## Architecture

```
icms/
├── backend/                FastAPI + SQLAlchemy
│   ├── authority.py          authority engine — authorize() gate, token, hash-chain
│   ├── matrices.py           RBAC, approval chains, scope, limits
│   ├── capabilities.py       office → modules map + per-action office reservations
│   ├── models.py             authority-core entities
│   ├── domain_models.py      academic/admin entities (students, courses, marks, fees, …)
│   ├── database.py           engine + seed (40 offices, 268 roles, 40 demo users)
│   ├── domain_seed.py        realistic data (8 depts, 30 courses, 367 students, …)
│   ├── core.py               shared helpers (db, auth, audit, notify)
│   ├── domain_api.py         functional module APIs — every mutation authority-gated
│   ├── main.py               auth + workflow + directory APIs
│   └── catalog.json          40 offices → 268 roles (source of record)
├── frontend/               React + Vite + TypeScript
│   ├── src/App.tsx           workspace-driven shell: dynamic sidebar + role picker
│   ├── src/modules/          19 functional module views (Students, Attendance, Exams, …)
│   └── src/views/            authority views (Workflows, Delegation, Audit, Matrices, …)
├── database/               schema.sql reference
└── docker-compose.yml
```

**How role differentiation works technically.** `capabilities.py` maps each office to a set of
functional modules and reserves sensitive actions to the offices that own them (e.g. only the
Exam Controller publishes results; only faculty enter marks; only Admissions/Front-office admit
students). `GET /api/workspace` returns the modules + per-action booleans for the signed-in
session. The React shell builds the sidebar from that response. Every mutating endpoint calls
`authorize()` again server-side, so the UI flags and the API enforcement can never diverge.

---

## Run it — Docker (recommended)

```bash
docker compose up --build
```

- **Frontend** → http://localhost:8080
- **Backend API** → http://localhost:8000 (interactive docs at `/docs`)
- **PostgreSQL** → localhost:5432 (`icms` / `icms_secret`)

The backend waits for Postgres, creates all tables, and seeds the 40 offices, 268 roles,
40 demo accounts **and** the full academic dataset automatically on first boot.

---

## Run it — local dev (no Docker)

**Backend** (Python 3.12+, falls back to SQLite when `DATABASE_URL` is unset):

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend** (Node 20+):

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173, proxies /api → :8000
```

---

## Signing in

Every demo account uses password **`demo123`**. The login screen lets you filter demo accounts
by authority level (L1–L8) and fills the credentials in for you. One head account per office;
a few good starting points:

| Username | Office | What you can do |
|----------|--------|-----------------|
| `principal` | Principal (L3) | Governance, academics, finance, approvals |
| `hod` | HOD Office (L5) | Dept academics, attendance, exams, leave approvals |
| `lecturer` | Lecturer (L5) | Mark attendance, enter marks |
| `exam_controller` | Exam Controller (L6) | Enter marks **and** publish results |
| `admissions` | Admission Office (L6) | Verify / offer / reject applicants |
| `finance_manager` | Finance Manager (L7) | Payments, waivers (with escalation), budgets |
| `librarian` | Library (L6) | Issue / return books |
| `hostel_warden` | Hostel Warden (L7) | Allocate hostel rooms |
| `student` | Student Portal (L8) | Personal academic & campus services |
| `governing_body` | Governing Body (L8) | Institution-wide dashboards |

…and 30 more, one for each office.

---

## Seeing the authority engine work

- **Segregation of duties** — as `lecturer`, open Examinations: you can enter marks but the
  *Publish result* button is disabled. As `exam_controller`, it's enabled. The same invariant
  is enforced server-side.
- **Approval-limit escalation** — as `finance_manager`, waive Rs 6,00,000 of a fee: the engine
  routes it as **ESCALATE → Vice-Chancellor**. Waive Rs 50,000: approved in place.
- **Scope & least privilege** — only IT / System Admin see the System Administration module.
- **Audit integrity** — open **Audit** and press *Verify chain integrity*; every decision is
  hash-chained to the previous one.
- **Role picker** — switch internal roles (top-right) to see the working lens change.

---

## Tech stack

FastAPI · SQLAlchemy 2 · PostgreSQL 16 (SQLite fallback) · React 18 · Vite 5 · TypeScript ·
Nginx (production frontend) · Docker Compose.
