# -*- coding: utf-8 -*-
"""
Domain model (Document §12 "Core entities").

These are the academic + administrative entities that make the 40 offices
*functional* — students, courses, sections, enrollment, attendance, marks,
results, fees, payments, library, HR/leave, hostel, transport, placements,
research, grievances, assets. They reuse the same Base/tenant_id convention
as the authority core in models.py.

Every table carries tenant_id; scoped tables also carry a scope_ref
(campus/department/program/section) so the authority engine's scope filter
applies uniformly.
"""
from datetime import datetime, date
from sqlalchemy import (Column, Integer, String, Boolean, Float, DateTime,
                        Date, Text, ForeignKey)
from models import Base


# --------------------------------------------------------------------------- #
#  Academic structure
# --------------------------------------------------------------------------- #
class Department(Base):
    __tablename__ = "departments"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    code = Column(String)              # CSE, ECE, MEC, ...
    name = Column(String)
    campus = Column(String)            # scope_ref (campus)
    hod_person_id = Column(String, nullable=True)


class School(Base):
    __tablename__ = "schools"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    code = Column(String, index=True)
    name = Column(String)
    dean_name = Column(String, default="")
    status = Column(String, default="active")


class Program(Base):
    __tablename__ = "programs"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    dept_id = Column(String, ForeignKey("departments.id"))
    code = Column(String)              # BTECH-CSE, MTECH-CSE, PHD-CSE
    name = Column(String)
    level = Column(String)             # UG / PG / Doctoral
    duration_years = Column(Integer, default=4)


class Course(Base):
    __tablename__ = "courses"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    dept_id = Column(String, ForeignKey("departments.id"))
    code = Column(String)              # CS101
    title = Column(String)
    credits = Column(Integer, default=3)
    semester = Column(Integer, default=1)
    description = Column(Text, default="")


class Section(Base):
    """A running class: a course offered in a term by a faculty member."""
    __tablename__ = "sections"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    course_id = Column(String, ForeignKey("courses.id"))
    dept_id = Column(String, ForeignKey("departments.id"))
    term = Column(String)              # 2025-Odd
    section_code = Column(String)      # A / B
    faculty_person_id = Column(String, nullable=True)
    room = Column(String, default="")
    schedule = Column(String, default="")   # "Mon 10:00, Wed 10:00"
    capacity = Column(Integer, default=60)
    scope_ref = Column(String, default="")  # department scope


# --------------------------------------------------------------------------- #
#  People: students & staff (distinct from auth Users)
# --------------------------------------------------------------------------- #
class Student(Base):
    __tablename__ = "students"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    roll_no = Column(String, index=True)
    name = Column(String)
    email = Column(String, default="")
    program_id = Column(String, ForeignKey("programs.id"))
    dept_id = Column(String, ForeignKey("departments.id"))
    campus = Column(String, default="Main Campus")
    batch = Column(String)             # 2023
    semester = Column(Integer, default=1)
    section = Column(String, default="A")
    status = Column(String, default="active")   # active / graduated / suspended
    cgpa = Column(Float, default=0.0)
    hosteller = Column(Boolean, default=False)
    scholarship = Column(Boolean, default=False)
    user_id = Column(String, nullable=True)     # link to portal login if any


class StaffMember(Base):
    __tablename__ = "staff_members"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    emp_id = Column(String, index=True)
    name = Column(String)
    email = Column(String, default="")
    dept_id = Column(String, nullable=True)
    designation = Column(String)       # Professor, Assistant Professor, Clerk...
    office_n = Column(Integer, nullable=True)
    campus = Column(String, default="Main Campus")
    status = Column(String, default="active")
    date_joined = Column(Date, default=date.today)
    user_id = Column(String, nullable=True)


# --------------------------------------------------------------------------- #
#  Enrollment · attendance · assessment · results
# --------------------------------------------------------------------------- #
class Enrollment(Base):
    __tablename__ = "enrollments"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    student_id = Column(String, ForeignKey("students.id"))
    section_id = Column(String, ForeignKey("sections.id"))
    status = Column(String, default="enrolled")  # requested/enrolled/dropped
    requested_at = Column(DateTime, default=datetime.utcnow)
    grade = Column(String, default="")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    section_id = Column(String, ForeignKey("sections.id"))
    student_id = Column(String, ForeignKey("students.id"))
    on_date = Column(Date, default=date.today)
    present = Column(Boolean, default=True)
    marked_by = Column(String, default="")


class Assessment(Base):
    __tablename__ = "assessments"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    section_id = Column(String, ForeignKey("sections.id"))
    name = Column(String)              # Midterm / Endterm / Quiz 1
    max_marks = Column(Float, default=100)
    weight = Column(Float, default=1.0)
    locked = Column(Boolean, default=False)


class Mark(Base):
    __tablename__ = "marks"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    assessment_id = Column(String, ForeignKey("assessments.id"))
    student_id = Column(String, ForeignKey("students.id"))
    score = Column(Float, default=0)
    entered_by = Column(String, default="")
    entered_at = Column(DateTime, default=datetime.utcnow)


class ResultSheet(Base):
    """A published result for a section/term (result publication ≠ marks entry)."""
    __tablename__ = "result_sheets"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    section_id = Column(String, ForeignKey("sections.id"))
    term = Column(String)
    status = Column(String, default="draft")   # draft/moderated/published
    published_by = Column(String, default="")
    published_at = Column(DateTime, nullable=True)


class StudentSubjectResult(Base):
    """Subject-level published outcomes; backlog state is derived, never manually cleared."""
    __tablename__ = "student_subject_results"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    student_id = Column(String, ForeignKey("students.id"), index=True)
    academic_year = Column(String, index=True)
    semester = Column(Integer, index=True)
    subject_code = Column(String)
    subject_title = Column(String)
    attempt = Column(Integer, default=1)
    outcome = Column(String)  # passed / failed / result_pending
    published_at = Column(DateTime, nullable=True)
    source = Column(String, default="examination")  # examination / development_sample


# --------------------------------------------------------------------------- #
#  Admissions
# --------------------------------------------------------------------------- #
class Application(Base):
    __tablename__ = "applications"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    applicant_name = Column(String)
    email = Column(String, default="")
    program_id = Column(String, nullable=True)
    program_name = Column(String, default="")
    score = Column(Float, default=0)   # entrance rank/score
    status = Column(String, default="submitted")  # submitted/verified/offered/admitted/rejected
    created_at = Column(DateTime, default=datetime.utcnow)


# --------------------------------------------------------------------------- #
#  Finance
# --------------------------------------------------------------------------- #
class FeeInvoice(Base):
    __tablename__ = "fee_invoices"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    student_id = Column(String, ForeignKey("students.id"))
    term = Column(String)
    amount = Column(Float, default=0)
    paid = Column(Float, default=0)
    status = Column(String, default="due")    # due/partial/paid/waived
    due_date = Column(Date, nullable=True)


class Payment(Base):
    __tablename__ = "payments"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    invoice_id = Column(String, ForeignKey("fee_invoices.id"))
    student_id = Column(String, default="")
    amount = Column(Float, default=0)
    method = Column(String, default="online")
    at = Column(DateTime, default=datetime.utcnow)
    reference = Column(String, default="")


class BudgetLine(Base):
    __tablename__ = "budget_lines"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    campus = Column(String, default="Main Campus")
    category = Column(String)          # Salaries / Infrastructure / Labs ...
    allocated = Column(Float, default=0)
    spent = Column(Float, default=0)
    fiscal_year = Column(String, default="2025-26")


class FinancialEntry(Base):
    __tablename__ = "financial_entries"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    entry_type = Column(String, default="income")   # income / expense
    category = Column(String)
    amount = Column(Float, default=0)
    campus = Column(String, default="Group")
    source = Column(String, default="")
    recorded_on = Column(Date, default=date.today)
    note = Column(String, default="")


class InstitutionSnapshot(Base):
    __tablename__ = "institution_snapshots"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    snapshot_month = Column(Date, index=True)
    total_staff = Column(Integer, default=0)
    non_teaching_staff = Column(Integer, default=0)
    active_users = Column(Integer, default=0)
    outstanding_fees = Column(Float, default=0)
    system_uptime = Column(Float, default=99.0)


class OutstandingFeeSnapshot(Base):
    __tablename__ = "outstanding_fee_snapshots"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    snapshot_month = Column(Date, index=True)
    outstanding_amount = Column(Float, default=0)
    students_with_dues = Column(Integer, default=0)
    overdue_over_60 = Column(Float, default=0)
    notices_sent = Column(Integer, default=0)


# --------------------------------------------------------------------------- #
#  Governance dashboards
# --------------------------------------------------------------------------- #
class GovernanceDashboardSnapshot(Base):
    __tablename__ = "governance_dashboard_snapshots"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    semester_key = Column(String, index=True)
    semester_label = Column(String)
    is_default = Column(Boolean, default=False)
    student_count = Column(Integer, default=0)
    faculty_count = Column(Integer, default=0)
    student_faculty_ratio = Column(Float, default=0)
    fee_collection_pct = Column(Float, default=0)
    research_grants = Column(Float, default=0)
    placement_offers = Column(Integer, default=0)
    average_cgpa = Column(Float, default=0)
    total_budget = Column(Float, default=0)
    utilized_budget = Column(Float, default=0)
    compliance_score = Column(Float, default=0)
    compliance_label = Column(String, default="Healthy")
    as_of_date = Column(Date, default=date.today)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class GovernanceComplianceMetric(Base):
    __tablename__ = "governance_compliance_metrics"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    snapshot_id = Column(String, ForeignKey("governance_dashboard_snapshots.id"), index=True)
    metric_key = Column(String, default="")
    category = Column(String, default="All")
    label = Column(String)
    score = Column(Float, default=0)
    status = Column(String, default="healthy")
    sort_order = Column(Integer, default=0)


class GovernancePerformanceMetric(Base):
    __tablename__ = "governance_performance_metrics"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    snapshot_id = Column(String, ForeignKey("governance_dashboard_snapshots.id"), index=True)
    area = Column(String)
    metric = Column(String)
    current_value = Column(String, default="")
    target_value = Column(String, default="")
    status = Column(String, default="On Track")
    trend_pct = Column(Float, default=0)
    trend_direction = Column(String, default="up")
    icon = Column(String, default="")
    sort_order = Column(Integer, default=0)


# --------------------------------------------------------------------------- #
#  Calendar hub
# --------------------------------------------------------------------------- #
class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    title = Column(String)
    category = Column(String, default="Institution")
    audience = Column(String, default="all")   # all/students/parents/staff/leadership/operations
    start_at = Column(DateTime, nullable=False)
    end_at = Column(DateTime, nullable=True)
    all_day = Column(Boolean, default=True)
    location = Column(String, default="")
    description = Column(Text, default="")
    owner_office_n = Column(Integer, nullable=True)
    source_type = Column(String, default="manual")   # manual/academic/placement/finance/library/hr
    source_ref = Column(String, default="")
    color = Column(String, default="")
    status = Column(String, default="published")
    created_by = Column(String, default="")
    updated_by = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class AcademicCalendarEntry(Base):
    __tablename__ = "academic_calendar_entries"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    term = Column(String, index=True)
    title = Column(String)
    category = Column(String, default="Teaching")
    campus = Column(String, default="All Campuses")
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    description = Column(Text, default="")
    status = Column(String, default="published")
    owner_office_n = Column(Integer, nullable=True)
    created_by = Column(String, default="")
    updated_by = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


# --------------------------------------------------------------------------- #
#  Library
# --------------------------------------------------------------------------- #
class Book(Base):
    __tablename__ = "books"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    isbn = Column(String, default="")
    title = Column(String)
    author = Column(String, default="")
    category = Column(String, default="")
    copies_total = Column(Integer, default=1)
    copies_available = Column(Integer, default=1)


class BookLoan(Base):
    __tablename__ = "book_loans"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    book_id = Column(String, ForeignKey("books.id"))
    borrower = Column(String)          # roll_no or emp_id
    borrower_name = Column(String, default="")
    issued_on = Column(Date, default=date.today)
    due_on = Column(Date, nullable=True)
    returned = Column(Boolean, default=False)
    fine = Column(Float, default=0)


# --------------------------------------------------------------------------- #
#  HR
# --------------------------------------------------------------------------- #
class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    staff_id = Column(String, ForeignKey("staff_members.id"))
    staff_name = Column(String, default="")
    kind = Column(String, default="Casual")   # Casual/Medical/Earned
    from_date = Column(Date, default=date.today)
    to_date = Column(Date, default=date.today)
    days = Column(Integer, default=1)
    reason = Column(String, default="")
    status = Column(String, default="pending")  # pending/approved/rejected
    decided_by = Column(String, default="")


class JobPosting(Base):
    __tablename__ = "job_postings"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    title = Column(String)
    dept = Column(String, default="")
    kind = Column(String, default="Faculty")   # Faculty/Staff
    openings = Column(Integer, default=1)
    status = Column(String, default="open")


# --------------------------------------------------------------------------- #
#  Hostel · Transport · Facilities
# --------------------------------------------------------------------------- #
class HostelRoom(Base):
    __tablename__ = "hostel_rooms"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    block = Column(String)             # A-Block
    room_no = Column(String)
    capacity = Column(Integer, default=2)
    occupied = Column(Integer, default=0)


class HostelAllocation(Base):
    __tablename__ = "hostel_allocations"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    room_id = Column(String, ForeignKey("hostel_rooms.id"))
    student_id = Column(String, default="")
    student_name = Column(String, default="")
    status = Column(String, default="requested")   # requested/allocated/vacated


class TransportRoute(Base):
    __tablename__ = "transport_routes"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    name = Column(String)
    stops = Column(String, default="")
    vehicle_no = Column(String, default="")
    seats = Column(Integer, default=40)
    seats_taken = Column(Integer, default=0)


class Asset(Base):
    __tablename__ = "assets"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    tag = Column(String)
    name = Column(String)
    category = Column(String, default="")
    location = Column(String, default="")
    status = Column(String, default="in-service")   # in-service/maintenance/retired
    value = Column(Float, default=0)


# --------------------------------------------------------------------------- #
#  Research · Placements
# --------------------------------------------------------------------------- #
class ResearchProject(Base):
    __tablename__ = "research_projects"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    title = Column(String)
    pi_name = Column(String, default="")     # principal investigator
    dept = Column(String, default="")
    agency = Column(String, default="")
    grant_amount = Column(Float, default=0)
    status = Column(String, default="ongoing")  # proposed/ongoing/completed


class Accreditation(Base):
    __tablename__ = "accreditations"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    title = Column(String)
    agency = Column(String, default="")
    entity_name = Column(String, default="")
    status = Column(String, default="active")
    awarded_on = Column(Date, nullable=True)
    valid_until = Column(Date, nullable=True)


class Partner(Base):
    __tablename__ = "partners"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    name = Column(String)
    kind = Column(String, default="")
    scope = Column(String, default="")
    status = Column(String, default="active")
    started_on = Column(Date, nullable=True)


class PlacementDrive(Base):
    __tablename__ = "placement_drives"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    company = Column(String)
    role = Column(String, default="")
    ctc = Column(Float, default=0)           # in LPA
    date = Column(Date, nullable=True)
    eligible_cgpa = Column(Float, default=6.0)
    status = Column(String, default="scheduled")
    offers = Column(Integer, default=0)


# --------------------------------------------------------------------------- #
#  Student affairs: grievance · discipline
# --------------------------------------------------------------------------- #
class Complaint(Base):
    __tablename__ = "complaints"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    kind = Column(String, default="Grievance")   # Grievance/Ragging/Discipline
    raised_by = Column(String, default="")
    subject = Column(String)
    detail = Column(Text, default="")
    status = Column(String, default="open")      # open/investigating/resolved
    severity = Column(String, default="normal")
    created_at = Column(DateTime, default=datetime.utcnow)
