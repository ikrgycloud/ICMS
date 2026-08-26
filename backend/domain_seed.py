# -*- coding: utf-8 -*-
"""
Domain seed for ICMS.

The seed is intentionally idempotent so repeated app startups keep enriching an
existing local database instead of short-circuiting after the first run.
"""
import random
from datetime import date, datetime, timedelta

from database import (SessionLocal, TENANT, engine, DEMO_USERNAMES, CAMPUS_SCOPES,
                      slug, ensure_additive_schema)
from matrices import APPROVAL_MATRIX
from models import (Base, User, Delegation, DelegationPolicy, DelegationProfile,
                    WorkflowInstance, WorkflowProfile, Approval, Notification,
                    DelegationOption, DelegationContext)
import domain_models as D

R = random.Random(42)

DEPARTMENTS = [
    ("CSE", "Computer Science & Engineering"),
    ("ECE", "Electronics & Communication Engineering"),
    ("MEC", "Mechanical Engineering"),
    ("CIV", "Civil Engineering"),
    ("EEE", "Electrical & Electronics Engineering"),
    ("MAT", "Mathematics & Computing"),
    ("MGT", "School of Management"),
    ("HSS", "Humanities & Social Sciences"),
]

COURSE_BANK = {
    "CSE": [
        ("CS101", "Introduction to Programming", 4, 1),
        ("CS201", "Data Structures & Algorithms", 4, 3),
        ("CS202", "Computer Organization", 3, 3),
        ("CS301", "Operating Systems", 4, 5),
        ("CS302", "Database Management Systems", 4, 5),
        ("CS303", "Computer Networks", 3, 5),
        ("CS401", "Machine Learning", 4, 7),
        ("CS402", "Distributed Systems", 3, 7),
        ("CS403", "Cloud Computing Lab", 2, 7),
        ("CS404", "Compiler Design", 4, 7),
        ("CS405", "Information Security", 3, 7),
    ],
    "ECE": [
        ("EC101", "Basic Electronics", 4, 1),
        ("EC201", "Signals & Systems", 4, 3),
        ("EC301", "Digital Signal Processing", 4, 5),
        ("EC401", "VLSI Design", 4, 7),
    ],
    "MEC": [
        ("ME101", "Engineering Mechanics", 4, 1),
        ("ME201", "Thermodynamics", 4, 3),
        ("ME301", "Fluid Mechanics", 4, 5),
        ("ME401", "Robotics", 3, 7),
    ],
    "CIV": [
        ("CE101", "Surveying", 3, 1),
        ("CE201", "Structural Analysis", 4, 3),
        ("CE301", "Geotechnical Engineering", 4, 5),
    ],
    "EEE": [
        ("EE101", "Circuit Theory", 4, 1),
        ("EE201", "Electrical Machines", 4, 3),
        ("EE301", "Power Systems", 4, 5),
    ],
    "MAT": [
        ("MA101", "Calculus", 4, 1),
        ("MA201", "Linear Algebra", 4, 3),
        ("MA301", "Probability & Statistics", 3, 5),
    ],
    "MGT": [
        ("MG101", "Principles of Management", 3, 1),
        ("MG201", "Financial Accounting", 3, 3),
        ("MG301", "Operations Research", 3, 5),
    ],
    "HSS": [
        ("HS101", "Technical Communication", 2, 1),
        ("HS201", "Economics", 3, 3),
    ],
}

DEMO_ATTENDANCE_TODAY = date(2026, 8, 25)
DEMO_ATTENDANCE_NOW = datetime(2026, 8, 25, 16, 15)
STUDENT_PORTAL_ATTENDANCE_DEMO = [
    {
        "code": "CS401",
        "title": "Machine Learning",
        "credits": 4,
        "semester": 7,
        "section_code": "A",
        "day_of_week": 1,
        "start_time": "09:00",
        "end_time": "10:00",
        "room": "LH-2",
        "building": "AI Block",
        "faculty_id": "staff_portal_cs401",
        "faculty_name": "Dr. Meera Nair",
        "designation": "Professor",
        "statuses": ["present", "present", "present", "late", "present", "present", "present", "present"],
    },
    {
        "code": "CS402",
        "title": "Distributed Systems",
        "credits": 3,
        "semester": 7,
        "section_code": "A",
        "day_of_week": 3,
        "start_time": "10:00",
        "end_time": "11:00",
        "room": "LH-3",
        "building": "Systems Block",
        "faculty_id": "staff_portal_cs402",
        "faculty_name": "Prof. Arun Kumar",
        "designation": "Associate Professor",
        "statuses": ["present", "present", "present", "od", "present", "present", "absent", "present"],
    },
    {
        "code": "CS403",
        "title": "Cloud Computing Lab",
        "credits": 2,
        "semester": 7,
        "section_code": "A",
        "day_of_week": 1,
        "start_time": "11:15",
        "end_time": "12:15",
        "room": "Cloud Lab 2",
        "building": "Lab Complex",
        "faculty_id": "staff_portal_cs403",
        "faculty_name": "Dr. Priya Iyer",
        "designation": "Assistant Professor",
        "statuses": ["present", "present", "leave", "present", "present", "present", "present", "present"],
    },
    {
        "code": "CS404",
        "title": "Compiler Design",
        "credits": 4,
        "semester": 7,
        "section_code": "A",
        "day_of_week": 1,
        "start_time": "14:00",
        "end_time": "15:00",
        "room": "LH-5",
        "building": "Academic Block",
        "faculty_id": "staff_portal_cs404",
        "faculty_name": "Prof. Vivek Rao",
        "designation": "Professor",
        "statuses": ["present", "absent", "present", "present", "absent", "present", "present", "pending"],
    },
    {
        "code": "CS405",
        "title": "Information Security",
        "credits": 3,
        "semester": 7,
        "section_code": "A",
        "day_of_week": 4,
        "start_time": "15:15",
        "end_time": "16:15",
        "room": "LH-6",
        "building": "Security Wing",
        "faculty_id": "staff_portal_cs405",
        "faculty_name": "Dr. Sneha Nair",
        "designation": "Associate Professor",
        "statuses": ["present", "present", "present", "present", "late", "present", "present", "absent"],
    },
]

FIRST = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh",
    "Ananya", "Diya", "Aadhya", "Saanvi", "Ishaan", "Kabir", "Anaya",
    "Riya", "Kavya", "Aryan", "Nisha", "Rohan", "Meera", "Karthik",
    "Priya", "Rahul", "Sneha", "Vikram", "Divya", "Aditi", "Nikhil",
]
LAST = [
    "Sharma", "Verma", "Iyer", "Nair", "Reddy", "Rao", "Gupta", "Menon",
    "Kulkarni", "Bose", "Chatterjee", "Patel", "Singh", "Khan", "Das",
    "Mehta", "Joshi", "Pillai", "Banerjee", "Krishnan",
]

FACULTY_TITLES = ["Professor", "Associate Professor", "Assistant Professor"]
BOOK_TITLES = [
    ("Introduction to Algorithms", "Cormen et al.", "Computer Science"),
    ("Operating System Concepts", "Silberschatz", "Computer Science"),
    ("Database System Concepts", "Silberschatz", "Computer Science"),
    ("Computer Networks", "Tanenbaum", "Computer Science"),
    ("Artificial Intelligence: A Modern Approach", "Russell & Norvig", "AI"),
    ("Signals and Systems", "Oppenheim", "Electronics"),
    ("Fundamentals of Physics", "Halliday & Resnick", "Physics"),
    ("Higher Engineering Mathematics", "B.S. Grewal", "Mathematics"),
    ("Thermodynamics: An Engineering Approach", "Cengel", "Mechanical"),
    ("The Structure of Scientific Revolutions", "Kuhn", "Humanities"),
]
COMPANIES = [
    ("Google", "SDE", 45.0, 8.0), ("Microsoft", "SDE", 42.0, 7.5),
    ("Goldman Sachs", "Analyst", 30.0, 7.0), ("Qualcomm", "Hardware Eng.", 28.0, 7.0),
    ("Amazon", "SDE", 32.0, 6.5), ("Texas Instruments", "Design Eng.", 25.0, 7.0),
    ("McKinsey", "Associate", 27.0, 7.5), ("Tata Motors", "GET", 12.0, 6.0),
]
AGENCIES = ["DST", "DRDO", "ISRO", "DBT", "SERB", "Industry-Sponsored"]

SCHOOLS = [
    ("SCHBUS", "School of Business & Leadership", "Dr. Meera Kulkarni"),
    ("SCHCOM", "School of Computing & AI", "Dr. Arjun Menon"),
    ("SCHENG", "School of Core Engineering", "Dr. Sneha Reddy"),
    ("SCHSCI", "School of Applied Sciences", "Dr. Rohan Iyer"),
    ("SCHDES", "School of Design & Media", "Prof. Kavya Das"),
    ("SCHLAW", "School of Law & Policy", "Dr. Nikhil Gupta"),
    ("SCHMED", "School of Health Sciences", "Dr. Priya Rao"),
    ("SCHARC", "School of Architecture & Planning", "Dr. Divya Banerjee"),
    ("SCHEDU", "School of Education", "Dr. Rahul Nair"),
    ("SCHSOC", "School of Social Sciences", "Dr. Aditi Bose"),
    ("SCHPHR", "School of Pharmacy", "Dr. Aryan Patel"),
    ("SCHINT", "School of Interdisciplinary Studies", "Dr. Ishaan Joshi"),
]

EXTRA_DEPARTMENTS = [
    ("AID", "Artificial Intelligence & Data Science", CAMPUS_SCOPES[0]),
    ("CYB", "Cybersecurity & Digital Trust", CAMPUS_SCOPES[0]),
    ("IOT", "Internet of Things Systems", CAMPUS_SCOPES[0]),
    ("SWE", "Software Engineering", CAMPUS_SCOPES[0]),
    ("BME", "Biomedical Engineering", CAMPUS_SCOPES[1]),
    ("CHE", "Chemical Engineering", CAMPUS_SCOPES[1]),
    ("AER", "Aerospace Engineering", CAMPUS_SCOPES[1]),
    ("MIN", "Mining Engineering", CAMPUS_SCOPES[1]),
    ("DSN", "Design Innovation", CAMPUS_SCOPES[5]),
    ("ANM", "Animation & Visual Communication", CAMPUS_SCOPES[5]),
    ("FAS", "Fashion & Lifestyle Studies", CAMPUS_SCOPES[5]),
    ("UXD", "User Experience Design", CAMPUS_SCOPES[5]),
    ("ARC", "Architecture", CAMPUS_SCOPES[2]),
    ("URP", "Urban & Regional Planning", CAMPUS_SCOPES[2]),
    ("INT", "Interior Environments", CAMPUS_SCOPES[2]),
    ("CST", "Construction Technology", CAMPUS_SCOPES[2]),
    ("NUR", "Nursing", CAMPUS_SCOPES[3]),
    ("PHS", "Public Health", CAMPUS_SCOPES[3]),
    ("MLS", "Medical Laboratory Sciences", CAMPUS_SCOPES[3]),
    ("NTR", "Nutrition & Dietetics", CAMPUS_SCOPES[3]),
    ("PPR", "Pharmacy Practice", CAMPUS_SCOPES[3]),
    ("PCH", "Pharmaceutical Chemistry", CAMPUS_SCOPES[3]),
    ("PCL", "Pharmacology", CAMPUS_SCOPES[3]),
    ("PHA", "Pharmaceutics", CAMPUS_SCOPES[3]),
    ("LAW", "Corporate Law", CAMPUS_SCOPES[2]),
    ("POL", "Public Policy", CAMPUS_SCOPES[2]),
    ("GOV", "Governance & Compliance", CAMPUS_SCOPES[2]),
    ("CRJ", "Criminology & Justice", CAMPUS_SCOPES[2]),
    ("ECO", "Economics", CAMPUS_SCOPES[4]),
    ("PSY", "Psychology", CAMPUS_SCOPES[4]),
    ("SOC", "Sociology", CAMPUS_SCOPES[4]),
    ("JRN", "Journalism & Media Studies", CAMPUS_SCOPES[4]),
    ("EDU", "Teacher Education", CAMPUS_SCOPES[4]),
    ("LDG", "Learning Design", CAMPUS_SCOPES[4]),
    ("ELT", "Educational Leadership", CAMPUS_SCOPES[4]),
    ("SPC", "Special Education", CAMPUS_SCOPES[4]),
    ("ENT", "Entrepreneurship & Venture Design", CAMPUS_SCOPES[0]),
    ("FIN", "Finance & Fintech", CAMPUS_SCOPES[0]),
    ("MKT", "Marketing & Consumer Insight", CAMPUS_SCOPES[0]),
    ("OPS", "Operations & Supply Networks", CAMPUS_SCOPES[0]),
]

ACCREDITATION_ROWS = [
    ("acc_01", "NAAC Institutional Accreditation", "NAAC", "ICMS University Group", date(2023, 7, 15), date(2028, 7, 14)),
    ("acc_02", "NBA - Computer Science", "NBA", "School of Computing & AI", date(2024, 1, 20), date(2027, 1, 19)),
    ("acc_03", "NBA - Mechanical Engineering", "NBA", "School of Core Engineering", date(2024, 2, 10), date(2027, 2, 9)),
    ("acc_04", "NBA - Civil Engineering", "NBA", "School of Core Engineering", date(2024, 3, 5), date(2027, 3, 4)),
    ("acc_05", "ISO 21001 Educational Organizations", "ISO", "ICMS University Group", date(2024, 5, 25), date(2027, 5, 24)),
    ("acc_06", "ABET Readiness - Electrical Systems", "ABET", "School of Core Engineering", date(2025, 1, 18), date(2028, 1, 17)),
    ("acc_07", "NIRF Audit Validation", "NIRF", "ICMS University Group", date(2025, 4, 8), date(2027, 4, 7)),
    ("acc_08", "Pharmacy Council Compliance", "PCI", "School of Pharmacy", date(2025, 6, 14), date(2027, 6, 13)),
    ("acc_09", "Council of Architecture Approval", "COA", "School of Architecture & Planning", date(2025, 9, 2), date(2027, 9, 1)),
    ("acc_10", "Health Sciences Clinical Standards", "NABH", "School of Health Sciences", date(2026, 2, 11), date(2028, 2, 10)),
    ("acc_11", "Innovation & Incubation Readiness", "MSME", "Research Park Campus", date(2026, 8, 6), date(2028, 8, 5)),
    ("acc_12", "NBA - AI & Data Science", "NBA", "School of Computing & AI", date(2026, 8, 14), date(2029, 8, 13)),
]

PARTNER_ROWS = [
    ("partner_01", "Microsoft Learn Alliance", "Industry", "Global", date(2024, 1, 10)),
    ("partner_02", "Google Cloud Skills Academy", "Industry", "Global", date(2024, 2, 12)),
    ("partner_03", "AWS Educate", "Industry", "Global", date(2024, 3, 9)),
    ("partner_04", "Texas Instruments Design Center", "Industry", "Electronics", date(2024, 4, 15)),
    ("partner_05", "Bosch Mobility Lab", "Industry", "Mechanical", date(2024, 5, 21)),
    ("partner_06", "Tata Steel Research Cell", "Industry", "Materials", date(2024, 6, 5)),
    ("partner_07", "National Instruments Lab Program", "Industry", "Electronics", date(2024, 7, 18)),
    ("partner_08", "Siemens Smart Factory Initiative", "Industry", "Operations", date(2024, 8, 7)),
    ("partner_09", "Infosys Springboard", "Industry", "Global", date(2024, 9, 1)),
    ("partner_10", "ISRO Student Research Outreach", "Government", "Research", date(2024, 10, 14)),
    ("partner_11", "DRDO Innovation Partnership", "Government", "Research", date(2024, 11, 3)),
    ("partner_12", "DST Research Collaboration", "Government", "Research", date(2025, 1, 16)),
    ("partner_13", "Unnat Bharat Abhiyan Cluster", "Government", "Community", date(2025, 2, 4)),
    ("partner_14", "NASSCOM FutureSkills", "Industry", "Global", date(2025, 3, 11)),
    ("partner_15", "Oracle Academy", "Industry", "Computing", date(2025, 4, 8)),
    ("partner_16", "Adobe Creative Campus", "Industry", "Design", date(2025, 5, 12)),
    ("partner_17", "NVIDIA Academic Program", "Industry", "AI", date(2025, 7, 2)),
    ("partner_18", "KPMG Governance Lab", "Industry", "Policy", date(2025, 8, 19)),
    ("partner_19", "L&T Construction Studio", "Industry", "Infrastructure", date(2025, 10, 7)),
    ("partner_20", "Fortis Clinical Training Network", "Industry", "Health", date(2025, 12, 1)),
    ("partner_21", "UN Global Compact Chapter", "NGO", "Sustainability", date(2026, 2, 9)),
    ("partner_22", "Startup India Launchpad", "Government", "Entrepreneurship", date(2026, 4, 25)),
    ("partner_23", "AICTE Industry Skills Hub", "Government", "Global", date(2026, 6, 17)),
    ("partner_24", "UNESCO Design Futures Exchange", "International", "Design", date(2026, 8, 10)),
]

INCOME_TOTALS = {
    "Tuition Fees": 119.21 * 1e7,
    "Grants & Funding": 49.32 * 1e7,
    "Other Income": 31.99 * 1e7,
    "Investments": 27.13 * 1e7,
    "Other Sources": 36.10 * 1e7,
}

EXPENSE_TOTALS = {
    "Salaries & Benefits": 58.40 * 1e7,
    "Infrastructure": 24.70 * 1e7,
    "Research & Innovation": 18.60 * 1e7,
    "Technology Systems": 12.90 * 1e7,
    "Student Support": 10.30 * 1e7,
    "Compliance & Administration": 10.40 * 1e7,
}

MONTH_FACTORS = [0.10, 0.11, 0.12, 0.11, 0.12, 0.13, 0.14, 0.17]

SNAPSHOT_ROWS = [
    (date(2026, 3, 1), 3554, 782, 3996, 98.72 * 1e7, 99.2),
    (date(2026, 4, 1), 3572, 794, 4038, 105.34 * 1e7, 99.3),
    (date(2026, 5, 1), 3588, 801, 4072, 112.40 * 1e7, 99.4),
    (date(2026, 6, 1), 3614, 815, 4129, 116.85 * 1e7, 99.6),
    (date(2026, 7, 1), 3631, 823, 4186, 118.17 * 1e7, 99.7),
    (date(2026, 8, 1), 3642, 829, 4218, 128.45 * 1e7, 99.8),
]

OUTSTANDING_FEE_ROWS = [
    (date(2026, 3, 1), 98.72 * 1e7, 298, 22.41 * 1e7, 2410),
    (date(2026, 4, 1), 105.34 * 1e7, 304, 24.18 * 1e7, 2586),
    (date(2026, 5, 1), 112.68 * 1e7, 317, 26.92 * 1e7, 2738),
    (date(2026, 6, 1), 118.76 * 1e7, 326, 28.86 * 1e7, 2894),
    (date(2026, 7, 1), 120.94 * 1e7, 333, 29.52 * 1e7, 3016),
    (date(2026, 8, 1), 128.45 * 1e7, 348, 32.18 * 1e7, 3214),
]

GOVERNANCE_DASHBOARD_ROWS = [
    {
        "id": "gov_dash_even_2024_25",
        "semester_key": "even_2024_25",
        "semester_label": "Even Semester 2024-25",
        "is_default": True,
        "student_count": 365,
        "faculty_count": 44,
        "student_faculty_ratio": 8.3,
        "fee_collection_pct": 74.0,
        "research_grants": 14.74 * 1e7,
        "placement_offers": 69,
        "average_cgpa": 7.67,
        "total_budget": 52.00 * 1e7,
        "utilized_budget": 22.71 * 1e7,
        "compliance_score": 92,
        "compliance_label": "Excellent",
        "as_of_date": date(2025, 5, 15),
    },
    {
        "id": "gov_dash_odd_2025_26",
        "semester_key": "odd_2025_26",
        "semester_label": "Odd Semester 2025-26",
        "is_default": False,
        "student_count": 388,
        "faculty_count": 46,
        "student_faculty_ratio": 8.4,
        "fee_collection_pct": 77.0,
        "research_grants": 16.28 * 1e7,
        "placement_offers": 74,
        "average_cgpa": 7.74,
        "total_budget": 56.40 * 1e7,
        "utilized_budget": 25.98 * 1e7,
        "compliance_score": 94,
        "compliance_label": "Excellent",
        "as_of_date": date(2025, 11, 20),
    },
    {
        "id": "gov_dash_even_2025_26",
        "semester_key": "even_2025_26",
        "semester_label": "Even Semester 2025-26",
        "is_default": False,
        "student_count": 402,
        "faculty_count": 48,
        "student_faculty_ratio": 8.4,
        "fee_collection_pct": 81.0,
        "research_grants": 18.63 * 1e7,
        "placement_offers": 83,
        "average_cgpa": 7.81,
        "total_budget": 59.20 * 1e7,
        "utilized_budget": 28.31 * 1e7,
        "compliance_score": 95,
        "compliance_label": "Excellent",
        "as_of_date": date(2026, 5, 18),
    },
]

GOVERNANCE_COMPLIANCE_ROWS = {
    "gov_dash_even_2024_25": [
        ("gov_comp_01", "regulatory", "Statutory Compliance", 100, "healthy", 1),
        ("gov_comp_02", "quality", "Accreditations", 90, "healthy", 2),
        ("gov_comp_03", "policy", "Policies & SOPs", 88, "healthy", 3),
        ("gov_comp_04", "risk", "Audit & Risk", 91, "healthy", 4),
    ],
    "gov_dash_odd_2025_26": [
        ("gov_comp_05", "regulatory", "Statutory Compliance", 100, "healthy", 1),
        ("gov_comp_06", "quality", "Accreditations", 93, "healthy", 2),
        ("gov_comp_07", "policy", "Policies & SOPs", 91, "healthy", 3),
        ("gov_comp_08", "risk", "Audit & Risk", 92, "healthy", 4),
    ],
    "gov_dash_even_2025_26": [
        ("gov_comp_09", "regulatory", "Statutory Compliance", 100, "healthy", 1),
        ("gov_comp_10", "quality", "Accreditations", 95, "healthy", 2),
        ("gov_comp_11", "policy", "Policies & SOPs", 93, "healthy", 3),
        ("gov_comp_12", "risk", "Audit & Risk", 94, "healthy", 4),
    ],
}

GOVERNANCE_PERFORMANCE_ROWS = {
    "gov_dash_even_2024_25": [
        ("gov_perf_01", "Academics", "Pass Percentage", "82%", "\u2265 80%", "Achieved", 5, "up", "academics", 1),
        ("gov_perf_02", "Finance", "Budget Utilisation", "43.7%", "\u2264 60%", "On Track", 4, "up", "finance", 2),
        ("gov_perf_03", "Placements", "Placement Rate", "78%", "\u2265 75%", "Achieved", 6, "up", "placements", 3),
        ("gov_perf_04", "Research", "Research Grants", "\u20B914.74 Cr", "\u2265 \u20B912 Cr", "Achieved", 12, "up", "research", 4),
    ],
    "gov_dash_odd_2025_26": [
        ("gov_perf_05", "Academics", "Pass Percentage", "84%", "\u2265 80%", "Achieved", 4, "up", "academics", 1),
        ("gov_perf_06", "Finance", "Budget Utilisation", "46.1%", "\u2264 60%", "On Track", 3, "up", "finance", 2),
        ("gov_perf_07", "Placements", "Placement Rate", "80%", "\u2265 75%", "Achieved", 7, "up", "placements", 3),
        ("gov_perf_08", "Research", "Research Grants", "\u20B916.28 Cr", "\u2265 \u20B914 Cr", "Achieved", 10, "up", "research", 4),
    ],
    "gov_dash_even_2025_26": [
        ("gov_perf_09", "Academics", "Pass Percentage", "86%", "\u2265 82%", "Achieved", 6, "up", "academics", 1),
        ("gov_perf_10", "Finance", "Budget Utilisation", "47.8%", "\u2264 62%", "On Track", 5, "up", "finance", 2),
        ("gov_perf_11", "Placements", "Placement Rate", "82%", "\u2265 78%", "Achieved", 8, "up", "placements", 3),
        ("gov_perf_12", "Research", "Research Grants", "\u20B918.63 Cr", "\u2265 \u20B915 Cr", "Achieved", 14, "up", "research", 4),
    ],
}


def _name():
    return f"{R.choice(FIRST)} {R.choice(LAST)}"


def _ensure(s, model, pk, factory):
    row = s.get(model, pk)
    if row is None:
        row = factory()
        s.add(row)
    return row


def _program_prefix(name):
    lower = name.lower()
    if "law" in lower or "policy" in lower or "justice" in lower:
        return "BALLB"
    if "design" in lower or "media" in lower or "fashion" in lower or "animation" in lower:
        return "BDES"
    if "management" in lower or "marketing" in lower or "finance" in lower or "operations" in lower:
        return "BBA"
    if "education" in lower:
        return "BED"
    if "pharma" in lower:
        return "BPHARM"
    if "health" in lower or "nursing" in lower or "nutrition" in lower:
        return "BSC"
    return "BTECH"


def _schedule_slots(schedule: str):
    mapping = {
        "Mon/Wed 10:00": [(0, "10:00", "11:00"), (2, "10:00", "11:00")],
        "Tue/Thu 11:00": [(1, "11:00", "12:00"), (3, "11:00", "12:00")],
        "Mon/Wed 14:00": [(0, "14:00", "15:00"), (2, "14:00", "15:00")],
        "Wed/Fri 09:00": [(2, "09:00", "10:00"), (4, "09:00", "10:00")],
    }
    return mapping.get(schedule or "", [])


def _ensure_timetable_entries_for_section(s, section, created_by="seed"):
    slots = _schedule_slots(section.schedule)
    for day_of_week, start_time, end_time in slots:
        entry_id = f"tt_{section.id}_{day_of_week}_{start_time.replace(':', '')}"
        row = _ensure(
            s, D.TimetableEntry, entry_id,
            lambda entry_id=entry_id, section=section, day_of_week=day_of_week,
                   start_time=start_time, end_time=end_time, created_by=created_by: D.TimetableEntry(
                       id=entry_id, tenant_id=TENANT, section_id=section.id,
                       day_of_week=day_of_week, start_time=start_time, end_time=end_time,
                       room=section.room, building="Academic Block",
                       effective_from=date.today() - timedelta(days=120),
                       effective_to=date.today() + timedelta(days=240),
                       status="active", created_by=created_by, updated_by=created_by
                   ),
        )
        row.room = section.room
        row.status = row.status or "active"
        row.updated_by = created_by
        row.updated_at = datetime.utcnow()


def _ensure_identity_card(s, student, valid_until=None):
    valid_until = valid_until or (date.today() + timedelta(days=730))
    card_number = f"ICMS-{student.roll_no}"
    token = f"IC{student.roll_no[-10:]}".upper()
    row = (s.query(D.StudentIdentityCard)
           .filter(D.StudentIdentityCard.student_id == student.id)
           .first())
    if row is None:
        row = D.StudentIdentityCard(
            id=f"idc_{student.id}", tenant_id=TENANT, student_id=student.id,
            card_number=card_number, verification_token=token
        )
        s.add(row)
    row.card_number = row.card_number or card_number
    row.verification_token = row.verification_token or token
    row.blood_group = student.blood_group or row.blood_group or "O+"
    row.issued_on = row.issued_on or date.today()
    row.valid_until = valid_until
    row.status = "active"
    row.updated_at = datetime.utcnow()
    return row


def _recent_weekday_dates(weekday: int, count: int, end_date=DEMO_ATTENDANCE_TODAY):
    cursor = end_date
    while cursor.weekday() != weekday:
        cursor -= timedelta(days=1)
    dates = []
    for _ in range(count):
        dates.append(cursor)
        cursor -= timedelta(days=7)
    return list(reversed(dates))


def _attendance_demo_marked_by(status: str) -> str:
    if status == "late":
        return "Clerk Office"
    if status in {"leave", "od"}:
        return "Head of Department Office"
    return "Department Office"


def _attendance_demo_note(status: str) -> str:
    mapping = {
        "present": "Daily attendance verified by the department office.",
        "late": "Clerk office pushed a late verified update.",
        "absent": "Session closed as absent after faculty marking.",
        "leave": "Approved leave note posted by the office.",
        "od": "OD entry verified by the HOD office.",
    }
    return mapping.get(status, "Attendance status updated by the department office.")


def _ensure_student_portal_demo_sections(s, dept_id: str):
    term = f"{DEMO_ATTENDANCE_TODAY.year}-Odd"
    sections = []
    for spec in STUDENT_PORTAL_ATTENDANCE_DEMO:
        course_id = f"course_{spec['code'].lower()}"
        course = _ensure(
            s, D.Course, course_id,
            lambda spec=spec, course_id=course_id: D.Course(
                id=course_id,
                tenant_id=TENANT,
                dept_id=dept_id,
                code=spec["code"],
                title=spec["title"],
                credits=spec["credits"],
                semester=spec["semester"],
                description=f"{spec['title']} core course for semester {spec['semester']}.",
            ),
        )
        course.dept_id = dept_id
        course.code = spec["code"]
        course.title = spec["title"]
        course.credits = spec["credits"]
        course.semester = spec["semester"]
        course.description = f"{spec['title']} core course for semester {spec['semester']}."

        faculty = _ensure(
            s, D.StaffMember, spec["faculty_id"],
            lambda spec=spec, dept_id=dept_id: D.StaffMember(
                id=spec["faculty_id"],
                tenant_id=TENANT,
                emp_id=f"PORTAL-{spec['code']}",
                name=spec["faculty_name"],
                email=f"{spec['code'].lower()}@icms.edu",
                dept_id=dept_id,
                designation=spec["designation"],
                office_n=11,
                campus=CAMPUS_SCOPES[0],
                date_joined=date(2017, 6, 1),
            ),
        )
        faculty.dept_id = dept_id
        faculty.name = spec["faculty_name"]
        faculty.designation = spec["designation"]
        faculty.office_n = faculty.office_n or 11
        faculty.campus = faculty.campus or CAMPUS_SCOPES[0]

        section_id = f"sec_portal_{spec['code'].lower()}_{spec['section_code'].lower()}"
        section = _ensure(
            s, D.Section, section_id,
            lambda spec=spec, section_id=section_id, course=course, dept_id=dept_id, faculty=faculty: D.Section(
                id=section_id,
                tenant_id=TENANT,
                course_id=course.id,
                dept_id=dept_id,
                term=term,
                section_code=spec["section_code"],
                faculty_person_id=faculty.id,
                room=spec["room"],
                schedule=f"{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][spec['day_of_week']]} {spec['start_time']}-{spec['end_time']}",
                capacity=60,
                scope_ref=dept_id,
            ),
        )
        section.course_id = course.id
        section.dept_id = dept_id
        section.term = term
        section.section_code = spec["section_code"]
        section.faculty_person_id = faculty.id
        section.room = spec["room"]
        section.schedule = f"{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][spec['day_of_week']]} {spec['start_time']}-{spec['end_time']}"
        section.capacity = 60
        section.scope_ref = dept_id

        timetable_id = f"tt_portal_{spec['code'].lower()}"
        timetable = _ensure(
            s, D.TimetableEntry, timetable_id,
            lambda spec=spec, timetable_id=timetable_id, section=section: D.TimetableEntry(
                id=timetable_id,
                tenant_id=TENANT,
                section_id=section.id,
                day_of_week=spec["day_of_week"],
                start_time=spec["start_time"],
                end_time=spec["end_time"],
                room=spec["room"],
                building=spec["building"],
                effective_from=DEMO_ATTENDANCE_TODAY - timedelta(days=56),
                effective_to=DEMO_ATTENDANCE_TODAY + timedelta(days=120),
                status="active",
                created_by="Dean Academics Office",
                updated_by="Dean Academics Office",
                created_at=DEMO_ATTENDANCE_NOW,
                updated_at=DEMO_ATTENDANCE_NOW,
            ),
        )
        timetable.section_id = section.id
        timetable.day_of_week = spec["day_of_week"]
        timetable.start_time = spec["start_time"]
        timetable.end_time = spec["end_time"]
        timetable.room = spec["room"]
        timetable.building = spec["building"]
        timetable.effective_from = DEMO_ATTENDANCE_TODAY - timedelta(days=56)
        timetable.effective_to = DEMO_ATTENDANCE_TODAY + timedelta(days=120)
        timetable.status = "active"
        timetable.created_by = "Dean Academics Office"
        timetable.updated_by = "Dean Academics Office"
        timetable.updated_at = DEMO_ATTENDANCE_NOW

        sections.append({"spec": spec, "course": course, "faculty": faculty, "section": section})

    # These demo rows are linked later by assessments, timetable entries,
    # and attendance records during the same unit of work. Flush once here
    # so the live container startup seed can safely reference them.
    s.flush()
    return sections


def _seed_student_portal_attendance_demo(s, student, demo_sections):
    demo_section_ids = {item["section"].id for item in demo_sections}
    enrollments = s.query(D.Enrollment).filter(D.Enrollment.student_id == student.id).all()
    for row in enrollments:
        row.status = "enrolled" if row.section_id in demo_section_ids else "dropped"

    for item in demo_sections:
        section = item["section"]
        spec = item["spec"]
        enrollment_id = f"enr_portal_{student.id}_{section.id}"
        enrollment = _ensure(
            s, D.Enrollment, enrollment_id,
            lambda enrollment_id=enrollment_id, student=student, section=section: D.Enrollment(
                id=enrollment_id,
                tenant_id=TENANT,
                student_id=student.id,
                section_id=section.id,
                status="enrolled",
            ),
        )
        enrollment.student_id = student.id
        enrollment.section_id = section.id
        enrollment.status = "enrolled"

    s.query(D.AttendanceRecord).filter(D.AttendanceRecord.id.like(f"att_portal_{student.id}_%")).delete(synchronize_session=False)

    for course_index, item in enumerate(demo_sections, start=1):
        spec = item["spec"]
        section = item["section"]
        course = item["course"]
        session_dates = _recent_weekday_dates(spec["day_of_week"], len(spec["statuses"]))
        for index, (session_date, status) in enumerate(zip(session_dates, spec["statuses"]), start=1):
            if status == "pending":
                continue
            record_id = f"att_portal_{student.id}_{spec['code'].lower()}_{index:02d}"
            updated_at = datetime.combine(session_date, datetime.min.time()).replace(
                hour=16,
                minute=10 + min(index, 20),
            )
            row = D.AttendanceRecord(
                id=record_id,
                tenant_id=TENANT,
                section_id=section.id,
                student_id=student.id,
                on_date=session_date,
                present=status in {"present", "late"},
                status=status,
                note=_attendance_demo_note(status),
                marked_by=_attendance_demo_marked_by(status),
                updated_at=updated_at,
            )
            s.add(row)

        quiz_id = f"asmt_portal_{spec['code'].lower()}_quiz"
        quiz_date = DEMO_ATTENDANCE_NOW + timedelta(days=course_index)
        quiz = _ensure(
            s, D.Assessment, quiz_id,
            lambda quiz_id=quiz_id, section=section, course=course, quiz_date=quiz_date: D.Assessment(
                id=quiz_id,
                tenant_id=TENANT,
                section_id=section.id,
                name=f"{course.code} Attendance Review Quiz",
                max_marks=20,
                weight=1.0,
                assessment_type="quiz",
                scheduled_at=quiz_date,
                end_at=quiz_date + timedelta(hours=1),
                published=True,
                instructions="Bring your digital ID and be seated 15 minutes before the quiz.",
                status="published",
            ),
        )
        quiz.section_id = section.id
        quiz.name = f"{course.code} Attendance Review Quiz"
        quiz.max_marks = 20
        quiz.weight = 1.0
        quiz.assessment_type = "quiz"
        quiz.scheduled_at = quiz_date
        quiz.end_at = quiz_date + timedelta(hours=1)
        quiz.published = True
        quiz.instructions = "Bring your digital ID and be seated 15 minutes before the quiz."
        quiz.status = "published"

        task_id = f"task_portal_{student.id}_{section.id}"
        task = _ensure(
            s, D.Assignment, task_id,
            lambda task_id=task_id, section=section, course=course: D.Assignment(
                id=task_id,
                tenant_id=TENANT,
                section_id=section.id,
                title=f"{course.code} tutorial submission",
                description=f"Upload the latest {course.title.lower()} worksheet reviewed by the department office.",
                assigned_at=DEMO_ATTENDANCE_NOW - timedelta(days=2),
                due_at=DEMO_ATTENDANCE_NOW + timedelta(days=2 + course_index),
                status="published",
                created_by=item["faculty"].name,
                updated_by=item["faculty"].name,
                created_at=DEMO_ATTENDANCE_NOW - timedelta(days=2),
                updated_at=DEMO_ATTENDANCE_NOW - timedelta(days=2),
            ),
        )
        task.section_id = section.id
        task.title = f"{course.code} tutorial submission"
        task.description = f"Upload the latest {course.title.lower()} worksheet reviewed by the department office."
        task.assigned_at = DEMO_ATTENDANCE_NOW - timedelta(days=2)
        task.due_at = DEMO_ATTENDANCE_NOW + timedelta(days=2 + course_index)
        task.status = "published"
        task.created_by = item["faculty"].name
        task.updated_by = item["faculty"].name
        task.updated_at = DEMO_ATTENDANCE_NOW - timedelta(days=2)


def _seed_student_portal_examinations_demo(s, student, demo_sections):
    section_by_code = {item["course"].code: item for item in demo_sections}
    academic_year = "2026-27"

    s.query(D.ExamSeatAssignment).filter(D.ExamSeatAssignment.id.like("seat_portal_%")).delete(synchronize_session=False)
    s.query(D.ExamScheduleHistory).filter(D.ExamScheduleHistory.id.like("exhist_portal_%")).delete(synchronize_session=False)
    s.query(D.ExamScheduleEntry).filter(D.ExamScheduleEntry.id.like("exsched_portal_%")).delete(synchronize_session=False)

    exam_specs = [
        {
            "assessment_id": "asmt_portal_cs401_midterm",
            "code": "CS401",
            "name": "Mid Term Examination",
            "assessment_type": "mid_term",
            "max_marks": 100,
            "weight": 3.0,
            "start_at": datetime(2026, 8, 20, 9, 30),
            "end_at": datetime(2026, 8, 20, 11, 0),
            "venue": "Seminar Hall 1",
            "mode": "Offline",
            "assessment_status": "completed",
            "schedule_status": "completed",
            "managed_by_office_n": 16,
            "created_by": "Exam Controller Office",
            "faculty_publish_by": "Dr. Meera Nair",
            "score": 78,
            "mark_status": "published",
            "mark_published_at": datetime(2026, 8, 20, 18, 30),
            "note": "Published to enrolled students after faculty verification.",
        },
        {
            "assessment_id": "asmt_portal_cs402_assignment2",
            "code": "CS402",
            "name": "Assignment 2",
            "assessment_type": "assignment",
            "max_marks": 20,
            "weight": 1.5,
            "start_at": datetime(2026, 8, 18, 14, 0),
            "end_at": datetime(2026, 8, 18, 15, 0),
            "venue": "Systems Block 3",
            "mode": "Offline",
            "assessment_status": "completed",
            "schedule_status": "completed",
            "managed_by_office_n": 10,
            "created_by": "Head of Department Office",
            "faculty_publish_by": "Prof. Arun Kumar",
            "score": 18,
            "mark_status": "published",
            "mark_published_at": datetime(2026, 8, 18, 17, 45),
            "note": "Internal assessment venue confirmed by HOD office.",
        },
        {
            "assessment_id": "asmt_portal_cs403_labtest1",
            "code": "CS403",
            "name": "Lab Test 1",
            "assessment_type": "lab_test",
            "max_marks": 30,
            "weight": 2.0,
            "start_at": datetime(2026, 8, 15, 11, 0),
            "end_at": datetime(2026, 8, 15, 12, 30),
            "venue": "Cloud Lab 2",
            "mode": "Offline",
            "assessment_status": "completed",
            "schedule_status": "completed",
            "managed_by_office_n": 16,
            "created_by": "Exam Controller Office",
            "faculty_publish_by": "Dr. Priya Iyer",
            "score": 27,
            "mark_status": "published",
            "mark_published_at": datetime(2026, 8, 15, 18, 15),
            "note": "Venue revised by lab office before exam day.",
            "history": [
                {
                    "id": "exhist_portal_cs403_labtest1_created",
                    "change_type": "created",
                    "previous_start_at": None,
                    "previous_end_at": None,
                    "previous_venue": "",
                    "previous_status": "",
                    "new_start_at": datetime(2026, 8, 15, 11, 0),
                    "new_end_at": datetime(2026, 8, 15, 12, 30),
                    "new_venue": "Cloud Lab 1",
                    "new_status": "scheduled",
                    "note": "Initial lab slot released by exam office.",
                    "created_by": "Exam Controller Office",
                    "created_at": datetime(2026, 8, 10, 10, 0),
                },
                {
                    "id": "exhist_portal_cs403_labtest1_venue",
                    "change_type": "updated",
                    "previous_start_at": datetime(2026, 8, 15, 11, 0),
                    "previous_end_at": datetime(2026, 8, 15, 12, 30),
                    "previous_venue": "Cloud Lab 1",
                    "previous_status": "scheduled",
                    "new_start_at": datetime(2026, 8, 15, 11, 0),
                    "new_end_at": datetime(2026, 8, 15, 12, 30),
                    "new_venue": "Cloud Lab 2",
                    "new_status": "completed",
                    "note": "Venue moved after cloud rack maintenance.",
                    "created_by": "HOD Office",
                    "created_at": datetime(2026, 8, 12, 16, 0),
                },
            ],
        },
        {
            "assessment_id": "asmt_portal_cs404_quiz2",
            "code": "CS404",
            "name": "Quiz 2",
            "assessment_type": "quiz",
            "max_marks": 20,
            "weight": 1.0,
            "start_at": datetime(2026, 8, 14, 9, 0),
            "end_at": datetime(2026, 8, 14, 9, 30),
            "venue": "Academic Block LH-5",
            "mode": "Offline",
            "assessment_status": "completed",
            "schedule_status": "completed",
            "managed_by_office_n": 10,
            "created_by": "Head of Department Office",
            "faculty_publish_by": "Prof. Vivek Rao",
            "score": 14,
            "mark_status": "published",
            "mark_published_at": datetime(2026, 8, 14, 15, 10),
            "note": "Published after section-wise validation.",
        },
        {
            "assessment_id": "asmt_portal_cs405_viva1",
            "code": "CS405",
            "name": "Viva 1",
            "assessment_type": "viva",
            "max_marks": 20,
            "weight": 1.0,
            "start_at": datetime(2026, 8, 17, 15, 0),
            "end_at": datetime(2026, 8, 17, 16, 0),
            "venue": "Security Wing Seminar Room",
            "mode": "Offline",
            "assessment_status": "completed",
            "schedule_status": "completed",
            "managed_by_office_n": 16,
            "created_by": "Exam Controller Office",
            "faculty_publish_by": "Dr. Sneha Nair",
            "score": 17,
            "mark_status": "published",
            "mark_published_at": datetime(2026, 8, 17, 18, 5),
            "note": "Panel viva marks released by assigned faculty.",
        },
        {
            "assessment_id": "asmt_portal_cs401_quiz",
            "code": "CS401",
            "name": "Unit Test 2",
            "assessment_type": "quiz",
            "max_marks": 20,
            "weight": 1.0,
            "start_at": datetime(2026, 8, 26, 16, 15),
            "end_at": datetime(2026, 8, 26, 17, 15),
            "venue": "AI Block LH-2",
            "mode": "Offline",
            "assessment_status": "published",
            "schedule_status": "scheduled",
            "managed_by_office_n": 10,
            "created_by": "Head of Department Office",
            "faculty_publish_by": "Dr. Meera Nair",
            "score": None,
            "mark_status": "",
            "note": "Faculty released the quiz instructions for enrolled students.",
        },
        {
            "assessment_id": "asmt_portal_cs402_internal3",
            "code": "CS402",
            "name": "Internal Assessment 3",
            "assessment_type": "internal",
            "max_marks": 25,
            "weight": 2.0,
            "start_at": datetime(2026, 8, 27, 10, 30),
            "end_at": datetime(2026, 8, 27, 12, 0),
            "venue": "Systems Block LH-3",
            "mode": "Offline",
            "assessment_status": "published",
            "schedule_status": "scheduled",
            "managed_by_office_n": 16,
            "created_by": "Exam Controller Office",
            "faculty_publish_by": "Prof. Arun Kumar",
            "score": None,
            "mark_status": "",
            "note": "Exam office published the section-wise internal timetable.",
        },
        {
            "assessment_id": "asmt_portal_cs403_labreview",
            "code": "CS403",
            "name": "Lab Evaluation 2",
            "assessment_type": "lab_test",
            "max_marks": 25,
            "weight": 1.5,
            "start_at": datetime(2026, 8, 28, 11, 15),
            "end_at": datetime(2026, 8, 28, 12, 30),
            "venue": "Cloud Lab 2",
            "mode": "Offline",
            "assessment_status": "published",
            "schedule_status": "scheduled",
            "managed_by_office_n": 10,
            "created_by": "Head of Department Office",
            "faculty_publish_by": "Dr. Priya Iyer",
            "score": None,
            "mark_status": "",
            "note": "Lab batch schedule locked by HOD office.",
        },
        {
            "assessment_id": "asmt_portal_cs404_midsem",
            "code": "CS404",
            "name": "Mid Sem Examination",
            "assessment_type": "mid_term",
            "max_marks": 100,
            "weight": 3.0,
            "start_at": datetime(2026, 8, 29, 9, 0),
            "end_at": datetime(2026, 8, 29, 11, 0),
            "venue": "Academic Block LH-5",
            "mode": "Offline",
            "assessment_status": "rescheduled",
            "schedule_status": "rescheduled",
            "managed_by_office_n": 16,
            "created_by": "Exam Controller Office",
            "faculty_publish_by": "Prof. Vivek Rao",
            "score": None,
            "mark_status": "",
            "note": "Rescheduled after hall allocation update from the HOD office.",
            "history": [
                {
                    "id": "exhist_portal_cs404_midsem_created",
                    "change_type": "created",
                    "previous_start_at": None,
                    "previous_end_at": None,
                    "previous_venue": "",
                    "previous_status": "",
                    "new_start_at": datetime(2026, 8, 28, 9, 0),
                    "new_end_at": datetime(2026, 8, 28, 11, 0),
                    "new_venue": "Academic Block LH-5",
                    "new_status": "scheduled",
                    "note": "Initial mid sem slot shared with students.",
                    "created_by": "Exam Controller Office",
                    "created_at": datetime(2026, 8, 8, 12, 0),
                },
                {
                    "id": "exhist_portal_cs404_midsem_rescheduled",
                    "change_type": "rescheduled",
                    "previous_start_at": datetime(2026, 8, 28, 9, 0),
                    "previous_end_at": datetime(2026, 8, 28, 11, 0),
                    "previous_venue": "Academic Block LH-5",
                    "previous_status": "scheduled",
                    "new_start_at": datetime(2026, 8, 29, 9, 0),
                    "new_end_at": datetime(2026, 8, 29, 11, 0),
                    "new_venue": "Academic Block LH-5",
                    "new_status": "rescheduled",
                    "note": "Rescheduled because the HOD office moved the section slot.",
                    "created_by": "HOD Office",
                    "created_at": datetime(2026, 8, 22, 17, 30),
                },
            ],
        },
        {
            "assessment_id": "asmt_portal_cs405_viva2",
            "code": "CS405",
            "name": "Viva Voce 2",
            "assessment_type": "viva",
            "max_marks": 25,
            "weight": 1.5,
            "start_at": datetime(2026, 8, 30, 14, 30),
            "end_at": datetime(2026, 8, 30, 15, 30),
            "venue": "Security Wing Seminar Room",
            "mode": "Offline",
            "assessment_status": "published",
            "schedule_status": "scheduled",
            "managed_by_office_n": 10,
            "created_by": "Head of Department Office",
            "faculty_publish_by": "Dr. Sneha Nair",
            "score": None,
            "mark_status": "",
            "note": "Faculty panel list synced from department office.",
        },
        {
            "assessment_id": "asmt_portal_cs401_case_review",
            "code": "CS401",
            "name": "Case Review Assessment",
            "assessment_type": "internal",
            "max_marks": 25,
            "weight": 1.5,
            "start_at": datetime(2026, 8, 24, 10, 0),
            "end_at": datetime(2026, 8, 24, 11, 15),
            "venue": "AI Block Seminar Room",
            "mode": "Offline",
            "assessment_status": "completed",
            "schedule_status": "completed",
            "managed_by_office_n": 10,
            "created_by": "Head of Department Office",
            "faculty_publish_by": "Dr. Meera Nair",
            "score": 21,
            "mark_status": "draft",
            "mark_published_at": None,
            "note": "Faculty moderation is in progress. Marks are expected to publish after review on August 27, 2026.",
        },
        {
            "assessment_id": "asmt_portal_cs405_panel_review",
            "code": "CS405",
            "name": "Panel Review Practical",
            "assessment_type": "external_final",
            "max_marks": 50,
            "weight": 2.0,
            "start_at": datetime(2026, 8, 23, 14, 0),
            "end_at": datetime(2026, 8, 23, 16, 0),
            "venue": "Security Wing Practical Hall",
            "mode": "Offline",
            "assessment_status": "completed",
            "schedule_status": "completed",
            "managed_by_office_n": 16,
            "created_by": "Exam Controller Office",
            "faculty_publish_by": "Dr. Sneha Nair",
            "score": None,
            "mark_status": "",
            "note": "Panel sheets were submitted to the exam office on August 24, 2026. Publication is pending office verification.",
        },
        {
            "assessment_id": "asmt_portal_cs402_surprise_cancelled",
            "code": "CS402",
            "name": "Practice Test",
            "assessment_type": "test",
            "max_marks": 20,
            "weight": 1.0,
            "start_at": datetime(2026, 8, 31, 15, 0),
            "end_at": datetime(2026, 8, 31, 16, 0),
            "venue": "Systems Block LH-3",
            "mode": "Offline",
            "assessment_status": "cancelled",
            "schedule_status": "cancelled",
            "managed_by_office_n": 16,
            "created_by": "Exam Controller Office",
            "faculty_publish_by": "Prof. Arun Kumar",
            "score": None,
            "mark_status": "",
            "note": "Cancelled and excluded from student upcoming list.",
            "history": [
                {
                    "id": "exhist_portal_cs402_surprise_created",
                    "change_type": "created",
                    "previous_start_at": None,
                    "previous_end_at": None,
                    "previous_venue": "",
                    "previous_status": "",
                    "new_start_at": datetime(2026, 8, 31, 15, 0),
                    "new_end_at": datetime(2026, 8, 31, 16, 0),
                    "new_venue": "Systems Block LH-3",
                    "new_status": "scheduled",
                    "note": "Additional practice slot announced.",
                    "created_by": "Exam Controller Office",
                    "created_at": datetime(2026, 8, 19, 11, 0),
                },
                {
                    "id": "exhist_portal_cs402_surprise_cancelled",
                    "change_type": "cancelled",
                    "previous_start_at": datetime(2026, 8, 31, 15, 0),
                    "previous_end_at": datetime(2026, 8, 31, 16, 0),
                    "previous_venue": "Systems Block LH-3",
                    "previous_status": "scheduled",
                    "new_start_at": datetime(2026, 8, 31, 15, 0),
                    "new_end_at": datetime(2026, 8, 31, 16, 0),
                    "new_venue": "Systems Block LH-3",
                    "new_status": "cancelled",
                    "note": "Cancelled after timetable consolidation.",
                    "created_by": "Exam Controller Office",
                    "created_at": datetime(2026, 8, 24, 9, 20),
                },
            ],
        },
        {
            "assessment_id": "asmt_portal_cs405_internal_draft",
            "code": "CS405",
            "name": "Internal Draft Review",
            "assessment_type": "internal",
            "max_marks": 25,
            "weight": 1.0,
            "start_at": datetime(2026, 8, 19, 9, 30),
            "end_at": datetime(2026, 8, 19, 10, 30),
            "venue": "Security Wing LH-1",
            "mode": "Offline",
            "assessment_status": "draft",
            "schedule_status": "scheduled",
            "managed_by_office_n": 10,
            "created_by": "Head of Department Office",
            "faculty_publish_by": "Dr. Sneha Nair",
            "score": 19,
            "mark_status": "draft",
            "mark_published_at": None,
            "note": "Draft-only mark entry should stay hidden from student view.",
        },
    ]
    seat_plan = {
        "asmt_portal_cs401_midterm": ("A-12", "Seminar Hall 1 / Row A"),
        "asmt_portal_cs402_assignment2": ("B-08", "Systems Block 3 / Row B"),
        "asmt_portal_cs403_labtest1": ("Bench 14", "Cloud Lab 2 / Bay 3"),
        "asmt_portal_cs404_quiz2": ("C-04", "Academic Block LH-5 / Row C"),
        "asmt_portal_cs405_viva1": ("Panel 02", "Security Wing Seminar Room"),
        "asmt_portal_cs401_quiz": ("A-18", "AI Block LH-2 / Row A"),
        "asmt_portal_cs402_internal3": ("B-11", "Systems Block LH-3 / Row B"),
        "asmt_portal_cs403_labreview": ("Bench 09", "Cloud Lab 2 / Bay 2"),
        "asmt_portal_cs404_midsem": ("C-21", "Academic Block LH-5 / Row C"),
        "asmt_portal_cs405_viva2": ("Panel 04", "Security Wing Seminar Room"),
        "asmt_portal_cs401_case_review": ("A-09", "AI Block Seminar Room"),
        "asmt_portal_cs405_panel_review": ("Bench 06", "Security Wing Practical Hall"),
    }

    for spec in exam_specs:
        item = section_by_code[spec["code"]]
        section = item["section"]
        course = item["course"]
        faculty = item["faculty"]
        assessment = _ensure(
            s, D.Assessment, spec["assessment_id"],
            lambda spec=spec, section=section: D.Assessment(
                id=spec["assessment_id"],
                tenant_id=TENANT,
                section_id=section.id,
                name=spec["name"],
                max_marks=spec["max_marks"],
                weight=spec["weight"],
                locked=False,
                assessment_type=spec["assessment_type"],
                scheduled_at=spec["start_at"],
                end_at=spec["end_at"],
                published=spec["assessment_status"] != "draft",
                instructions=spec["note"],
                status=spec["assessment_status"],
            ),
        )
        assessment.section_id = section.id
        assessment.name = spec["name"]
        assessment.max_marks = spec["max_marks"]
        assessment.weight = spec["weight"]
        assessment.locked = False
        assessment.assessment_type = spec["assessment_type"]
        assessment.scheduled_at = spec["start_at"]
        assessment.end_at = spec["end_at"]
        assessment.published = spec["assessment_status"] != "draft"
        assessment.instructions = spec["note"]
        assessment.status = spec["assessment_status"]
        assessment.academic_year = academic_year
        assessment.created_by = faculty.name
        assessment.updated_by = spec["created_by"]
        assessment.created_at = min(spec["start_at"], DEMO_ATTENDANCE_NOW) - timedelta(days=7)
        assessment.updated_at = min(spec["start_at"], DEMO_ATTENDANCE_NOW) - timedelta(days=1)
        assessment.published_at = (min(spec["start_at"], DEMO_ATTENDANCE_NOW) - timedelta(days=5)) if assessment.published else None
        assessment.published_by = spec["created_by"] if assessment.published else ""

        schedule_id = f"exsched_portal_{spec['assessment_id']}"
        schedule = _ensure(
            s, D.ExamScheduleEntry, schedule_id,
            lambda schedule_id=schedule_id, assessment=assessment, section=section, spec=spec: D.ExamScheduleEntry(
                id=schedule_id,
                tenant_id=TENANT,
                assessment_id=assessment.id,
                section_id=section.id,
                academic_year=academic_year,
                semester=course.semester,
                exam_type=spec["assessment_type"],
                start_at=spec["start_at"],
                end_at=spec["end_at"],
                venue=spec["venue"],
                mode=spec["mode"],
                status=spec["schedule_status"],
                version_no=2 if spec["schedule_status"] == "rescheduled" else 1,
                is_active=True,
                managed_by_office_n=spec["managed_by_office_n"],
                note=spec["note"],
                created_by=spec["created_by"],
                updated_by=spec["created_by"],
                created_at=min(spec["start_at"], DEMO_ATTENDANCE_NOW) - timedelta(days=6),
                updated_at=min(spec["start_at"], DEMO_ATTENDANCE_NOW) - timedelta(days=1),
            ),
        )
        schedule.assessment_id = assessment.id
        schedule.section_id = section.id
        schedule.academic_year = academic_year
        schedule.semester = course.semester
        schedule.exam_type = spec["assessment_type"]
        schedule.start_at = spec["start_at"]
        schedule.end_at = spec["end_at"]
        schedule.venue = spec["venue"]
        schedule.mode = spec["mode"]
        schedule.status = spec["schedule_status"]
        schedule.version_no = 2 if spec["schedule_status"] == "rescheduled" else 1
        schedule.is_active = True
        schedule.managed_by_office_n = spec["managed_by_office_n"]
        schedule.note = spec["note"]
        schedule.created_by = spec["created_by"]
        schedule.updated_by = spec["created_by"]
        schedule.created_at = min(spec["start_at"], DEMO_ATTENDANCE_NOW) - timedelta(days=6)
        schedule.updated_at = min(spec["start_at"], DEMO_ATTENDANCE_NOW) - timedelta(days=1)

        history_specs = spec.get("history") or [
            {
                "id": f"exhist_portal_{spec['assessment_id']}_created",
                "change_type": "created",
                "previous_start_at": None,
                "previous_end_at": None,
                "previous_venue": "",
                "previous_status": "",
                "new_start_at": spec["start_at"],
                "new_end_at": spec["end_at"],
                "new_venue": spec["venue"],
                "new_status": spec["schedule_status"],
                "note": spec["note"],
                "created_by": spec["created_by"],
                "created_at": min(spec["start_at"], DEMO_ATTENDANCE_NOW) - timedelta(days=6),
            }
        ]
        for history_spec in history_specs:
            history = _ensure(
                s, D.ExamScheduleHistory, history_spec["id"],
                lambda history_spec=history_spec, schedule=schedule, assessment=assessment: D.ExamScheduleHistory(
                    id=history_spec["id"],
                    tenant_id=TENANT,
                    schedule_id=schedule.id,
                    assessment_id=assessment.id,
                    change_type=history_spec["change_type"],
                    previous_start_at=history_spec["previous_start_at"],
                    previous_end_at=history_spec["previous_end_at"],
                    previous_venue=history_spec["previous_venue"],
                    previous_status=history_spec["previous_status"],
                    new_start_at=history_spec["new_start_at"],
                    new_end_at=history_spec["new_end_at"],
                    new_venue=history_spec["new_venue"],
                    new_status=history_spec["new_status"],
                    note=history_spec["note"],
                    created_by=history_spec["created_by"],
                    created_at=history_spec["created_at"],
                ),
            )
            history.schedule_id = schedule.id
            history.assessment_id = assessment.id
            history.change_type = history_spec["change_type"]
            history.previous_start_at = history_spec["previous_start_at"]
            history.previous_end_at = history_spec["previous_end_at"]
            history.previous_venue = history_spec["previous_venue"]
            history.previous_status = history_spec["previous_status"]
            history.new_start_at = history_spec["new_start_at"]
            history.new_end_at = history_spec["new_end_at"]
            history.new_venue = history_spec["new_venue"]
            history.new_status = history_spec["new_status"]
            history.note = history_spec["note"]
            history.created_by = history_spec["created_by"]
            history.created_at = history_spec["created_at"]

        if spec["assessment_status"] != "draft" and spec["schedule_status"] != "cancelled":
            seat_label, seat_zone = seat_plan.get(spec["assessment_id"], ("", ""))
            if seat_label:
                seat_id = f"seat_portal_{student.id}_{assessment.id}"
                seat_assignment = _ensure(
                    s, D.ExamSeatAssignment, seat_id,
                    lambda seat_id=seat_id, schedule=schedule, assessment=assessment, spec=spec, seat_label=seat_label, seat_zone=seat_zone: D.ExamSeatAssignment(
                        id=seat_id,
                        tenant_id=TENANT,
                        schedule_id=schedule.id,
                        assessment_id=assessment.id,
                        student_id=student.id,
                        seat_label=seat_label,
                        seat_zone=seat_zone,
                        note=f"Seat released by {spec['created_by']} for the enrolled student only.",
                        assigned_by=spec["created_by"],
                        created_at=min(spec["start_at"], DEMO_ATTENDANCE_NOW) - timedelta(days=3),
                        updated_at=min(spec["start_at"], DEMO_ATTENDANCE_NOW) - timedelta(days=1),
                    ),
                )
                seat_assignment.schedule_id = schedule.id
                seat_assignment.assessment_id = assessment.id
                seat_assignment.student_id = student.id
                seat_assignment.seat_label = seat_label
                seat_assignment.seat_zone = seat_zone
                seat_assignment.note = f"Seat released by {spec['created_by']} for the enrolled student only."
                seat_assignment.assigned_by = spec["created_by"]
                seat_assignment.created_at = min(spec["start_at"], DEMO_ATTENDANCE_NOW) - timedelta(days=3)
                seat_assignment.updated_at = min(spec["start_at"], DEMO_ATTENDANCE_NOW) - timedelta(days=1)

        existing_mark = (
            s.query(D.Mark)
            .filter(D.Mark.assessment_id == assessment.id, D.Mark.student_id == student.id)
            .first()
        )
        if spec["score"] is None:
            if existing_mark:
                s.delete(existing_mark)
            continue

        mark_id = f"mk_portal_{student.id}_{assessment.id}"
        mark = _ensure(
            s, D.Mark, mark_id,
            lambda mark_id=mark_id, assessment=assessment, student=student, spec=spec: D.Mark(
                id=mark_id,
                tenant_id=TENANT,
                assessment_id=assessment.id,
                student_id=student.id,
                score=spec["score"],
                entered_by=faculty.name,
                entered_at=spec["end_at"] + timedelta(hours=2),
                status=spec["mark_status"] or "draft",
                published_at=spec.get("mark_published_at"),
                published_by=spec["faculty_publish_by"] if spec.get("mark_published_at") else "",
                is_valid=True,
                updated_at=spec["end_at"] + timedelta(hours=2),
            ),
        )
        mark.assessment_id = assessment.id
        mark.student_id = student.id
        mark.score = spec["score"]
        mark.entered_by = faculty.name
        mark.entered_at = spec["end_at"] + timedelta(hours=2)
        mark.status = spec["mark_status"] or "draft"
        mark.published_at = spec.get("mark_published_at")
        mark.published_by = spec["faculty_publish_by"] if spec.get("mark_published_at") else ""
        mark.is_valid = True
        mark.updated_at = spec["end_at"] + timedelta(hours=2)


def _seed_calendar_data(s):
    today = date.today()
    month_anchor = today.replace(day=1)

    def dt(day_offset, hour=9, minute=0):
        return datetime.combine(today + timedelta(days=day_offset), datetime.min.time()).replace(
            hour=hour, minute=minute
        )

    calendar_specs = [
        ("cal_01", "Chairman's monthly governance review", "Governance", "leadership",
         dt(2, 10, 0), dt(2, 12, 30), False, "Senate Hall",
         "Executive review across campuses covering finance, risk, approvals, and academic delivery.", 1, "#8a1f2b"),
        ("cal_02", "Academic council and timetable closure", "Academics", "staff,leadership",
         dt(3, 14, 0), dt(3, 16, 0), False, "Council Chamber",
         "Vice Chairman, Principal, and Vice Principal close the live timetable and semester readiness checklist.", 2, "#2c5fb3"),
        ("cal_03", "Foundation orientation week", "Students", "all",
         dt(5, 9, 0), dt(7, 17, 0), False, "Main Auditorium",
         "New-student orientation, campus onboarding, and society induction across all schools.", 35, "#12855b"),
        ("cal_04", "Research and innovation showcase", "Research", "all",
         dt(8, 11, 0), dt(8, 16, 0), False, "Innovation Hub",
         "Live demos from funded labs, startup teams, and interdisciplinary capstone cohorts.", 9, "#6b4ea8"),
        ("cal_05", "Fee helpdesk extended hours", "Finance", "students,parents,operations",
         dt(10, 9, 30), dt(10, 18, 0), False, "Finance Block",
         "Extended walk-in support for invoices, payment plans, scholarships, and receipts.", 22, "#b97e1f"),
        ("cal_06", "Placement readiness sprint", "Placements", "students,staff",
         dt(11, 13, 0), dt(11, 17, 30), False, "Career Studio",
         "Resume clinics, mock interviews, and recruiter briefings ahead of the placement cycle.", 18, "#0d9488"),
        ("cal_07", "Parent connect webcast", "Engagement", "parents,leadership",
         dt(15, 18, 0), dt(15, 19, 0), False, "Virtual",
         "Live webcast on academic progress, campus support, and scholarship updates for guardians.", 4, "#ef4444"),
        ("cal_08", "Library discovery week", "Library", "students,staff,parents",
         dt(18, 9, 0), dt(22, 18, 0), False, "Central Library",
         "Reading circles, database training, and reference desk workshops across campuses.", 19, "#162033"),
        ("cal_09", "Transport route optimization drill", "Operations", "operations,staff,leadership",
         dt(20, 8, 0), dt(20, 11, 0), False, "Transit Control Room",
         "Live route simulation for the new semester shuttle plan and peak-hour balancing.", 31, "#0b7a70"),
        ("cal_10", "Hostel move-in and mentor allocation", "Student Life", "students,parents,staff",
         dt(24, 8, 0), dt(25, 18, 0), False, "Residential Commons",
         "Room handover, mentor mapping, and support desk coordination for hostellers.", 30, "#3b82f6"),
        ("cal_11", "Global partnership signing window", "Governance", "leadership,staff",
         dt(28, 15, 0), dt(28, 16, 0), False, "Board Room",
         "Formal signing session for the latest industry and international collaboration portfolio.", 1, "#9333ea"),
        ("cal_12", "Convocation operations war room", "Operations", "staff,leadership",
         dt(40, 10, 0), dt(40, 12, 0), False, "Operations Center",
         "Cross-functional planning review for security, stage, guest management, and student flow.", 26, "#475569"),
    ]

    for (event_id, title, category, audience, start_at, end_at, all_day, location,
         description, owner_office_n, color) in calendar_specs:
        _ensure(
            s, D.CalendarEvent, event_id,
            lambda event_id=event_id, title=title, category=category, audience=audience,
            start_at=start_at, end_at=end_at, all_day=all_day, location=location,
            description=description, owner_office_n=owner_office_n, color=color: D.CalendarEvent(
                id=event_id, tenant_id=TENANT, title=title, category=category,
                audience=audience, start_at=start_at, end_at=end_at, all_day=all_day,
                location=location, description=description, owner_office_n=owner_office_n,
                source_type="manual", source_ref="", color=color, status="published",
                created_by=f"user_{owner_office_n}", updated_by=f"user_{owner_office_n}"
            ),
        )

    odd_term = f"{today.year}-Odd"
    even_term = f"{today.year + 1}-Even"
    academic_specs = [
        ("acad_01", odd_term, "Faculty reporting and timetable freeze", "Planning",
         month_anchor - timedelta(days=10), month_anchor - timedelta(days=8), "All Campuses",
         "Final faculty reporting, section balancing, and operational sign-off before classes open.", 5),
        ("acad_02", odd_term, "Semester commencement", "Teaching",
         month_anchor + timedelta(days=1), month_anchor + timedelta(days=1), "All Campuses",
         "Opening day of the odd semester for all schools and campuses.", 4),
        ("acad_03", odd_term, "Add/drop and late registration window", "Registration",
         month_anchor + timedelta(days=1), month_anchor + timedelta(days=7), "All Campuses",
         "Students can settle electives, hostels, fee exceptions, and timetable corrections.", 2),
        ("acad_04", odd_term, "Continuous assessment cycle I", "Assessment",
         month_anchor + timedelta(days=18), month_anchor + timedelta(days=24), "All Campuses",
         "Quiz, assignment, lab viva, and internal rubric capture across departments.", 5),
        ("acad_05", odd_term, "Mid-semester examinations", "Examinations",
         month_anchor + timedelta(days=32), month_anchor + timedelta(days=38), "All Campuses",
         "Coordinated mid-semester exam window with exam-cell controls and invigilation mapping.", 4),
        ("acad_06", odd_term, "Project review and industry jury week", "Review",
         month_anchor + timedelta(days=48), month_anchor + timedelta(days=54), "All Campuses",
         "Capstone and dissertation reviews with external mentors and school panels.", 2),
        ("acad_07", odd_term, "End-semester examinations", "Examinations",
         month_anchor + timedelta(days=88), month_anchor + timedelta(days=98), "All Campuses",
         "University-wide end-semester examination block for odd-term offerings.", 4),
        ("acad_08", odd_term, "Result publication and revaluation requests", "Results",
         month_anchor + timedelta(days=104), month_anchor + timedelta(days=108), "All Campuses",
         "Marks lock, result publication, and controlled revaluation intake window.", 2),
        ("acad_09", odd_term, "Winter term recess", "Break",
         month_anchor + timedelta(days=109), month_anchor + timedelta(days=122), "All Campuses",
         "Semester break, convocation rehearsals, and readiness for the even-term restart.", 1),
        ("acad_10", even_term, "Even semester registration and hostel reopening", "Registration",
         date(today.year + 1, 1, 5), date(today.year + 1, 1, 10), "All Campuses",
         "Return-to-campus registration, room revalidation, and support-desk reopening.", 5),
        ("acad_11", even_term, "Even semester commencement", "Teaching",
         date(today.year + 1, 1, 12), date(today.year + 1, 1, 12), "All Campuses",
         "Formal academic opening of the even semester across the institution group.", 4),
        ("acad_12", even_term, "National immersion and fieldwork week", "Experiential",
         date(today.year + 1, 2, 16), date(today.year + 1, 2, 21), "Selected Campuses",
         "Field immersion, social innovation, and internship-linked experiential modules.", 2),
    ]

    for (entry_id, term, title, category, start_date, end_date, campus,
         description, owner_office_n) in academic_specs:
        _ensure(
            s, D.AcademicCalendarEntry, entry_id,
            lambda entry_id=entry_id, term=term, title=title, category=category,
            start_date=start_date, end_date=end_date, campus=campus,
            description=description, owner_office_n=owner_office_n: D.AcademicCalendarEntry(
                id=entry_id, tenant_id=TENANT, term=term, title=title,
                category=category, campus=campus, start_date=start_date,
                end_date=end_date, description=description, status="published",
                owner_office_n=owner_office_n, created_by=f"user_{owner_office_n}",
                updated_by=f"user_{owner_office_n}"
            ),
        )

    s.commit()


def _seed_core_domain(s):
    if s.query(D.Student).count() > 0:
        return

    today = date.today()
    term = f"{today.year}-Odd"
    fiscal_year = f"{today.year}-{str(today.year + 1)[2:]}"

    dept_ids = {}
    for code, name in DEPARTMENTS:
        did = f"dept_{code.lower()}"
        dept_ids[code] = did
        s.add(D.Department(id=did, tenant_id=TENANT, code=code, name=name,
                           campus=CAMPUS_SCOPES[0]))
        for lvl, pfx, dur in [("UG", "BTECH", 4), ("PG", "MTECH", 2)]:
            s.add(D.Program(id=f"prog_{code.lower()}_{pfx.lower()}",
                            tenant_id=TENANT, dept_id=did,
                            code=f"{pfx}-{code}", name=f"{pfx} {name}",
                            level=lvl, duration_years=dur))

    # Persist the parent academic entities before inserting dependent rows.
    s.flush()

    course_rows = []
    for code, courses in COURSE_BANK.items():
        did = dept_ids[code]
        for ccode, title, credits, sem in courses:
            cid = f"course_{ccode.lower()}"
            course_rows.append((cid, did, code, sem))
            is_elective = sem == 7
            ltp = "3-1-0" if credits >= 4 else ("3-0-0" if credits == 3 else "2-0-0")
            s.add(D.Course(id=cid, tenant_id=TENANT, dept_id=did,
                           program_id=f"prog_{code.lower()}_btech", code=ccode,
                           title=title, credits=credits, semester=sem,
                           description=f"{title} course for semester {sem}.",
                           regulation="R2023", course_type="Elective" if is_elective else "Core",
                           category="Professional Elective" if is_elective else "Professional Core",
                           ltp=ltp, prerequisite="" if sem == 1 else f"Semester {sem - 2} foundation",
                           status="Active"))

    faculty_by_dept = {code: [] for code in dept_ids}
    fac_i = 0
    for code, did in dept_ids.items():
        n_fac = R.randint(4, 7)
        for _ in range(n_fac):
            fac_i += 1
            fid = f"staff_fac_{fac_i}"
            nm = _name()
            s.add(D.StaffMember(id=fid, tenant_id=TENANT, emp_id=f"FAC{fac_i:04d}",
                                name=nm, email=f"fac{fac_i}@icms.edu", dept_id=did,
                                phone=f"9{R.randint(100000000, 999999999)}",
                                office_hours="Mon–Fri 02:00 PM – 04:00 PM",
                                designation=R.choice(FACULTY_TITLES),
                                office_n=R.choice([11, 12, 13, 14]),
                                campus=CAMPUS_SCOPES[0],
                                date_joined=date(2015, 1, 1) + timedelta(days=R.randint(0, 3000))))
            faculty_by_dept[code].append((fid, nm))

    # PostgreSQL enforces these foreign keys immediately during later flushes,
    # so persist courses and faculty before creating sections and students.
    s.flush()

    section_rows = []
    for cid, did, code, sem in course_rows:
        for sec_code in (["A", "B"] if R.random() > 0.5 else ["A"]):
            fid, _ = R.choice(faculty_by_dept[code])
            sid = f"sec_{cid.split('_')[1]}_{sec_code.lower()}"
            section_rows.append((sid, cid, did, code, sem, fid, sec_code))
            s.add(D.Section(id=sid, tenant_id=TENANT, course_id=cid, dept_id=did,
                            term=term, section_code=sec_code,
                            faculty_person_id=fid, room=f"LH-{R.randint(1, 20)}",
                            schedule=R.choice(["Mon/Wed 10:00", "Tue/Thu 11:00",
                                               "Mon/Wed 14:00", "Wed/Fri 09:00"]),
                            capacity=60, scope_ref=did))

    student_rows = []
    stu_i = 0
    for code, did in dept_ids.items():
        prog_id = f"prog_{code.lower()}_btech"
        for batch, sem in [("2023", 7), ("2024", 5), ("2025", 3), ("2026", 1)]:
            for _ in range(R.randint(8, 14)):
                stu_i += 1
                sid = f"stu_{stu_i}"
                nm = _name()
                roll = f"{batch[2:]}{code}{stu_i:03d}"
                hosteller = R.random() > 0.5
                scholarship = R.random() > 0.8
                cgpa = round(R.uniform(5.5, 9.7), 2)
                student_rows.append((sid, code, did, sem, batch, cgpa))
                s.add(D.Student(id=sid, tenant_id=TENANT, roll_no=roll, name=nm,
                                email=f"{roll.lower()}@icms.edu", program_id=prog_id,
                                dept_id=did, campus=CAMPUS_SCOPES[0], batch=batch,
                                semester=sem, section=R.choice(["A", "B"]),
                                status="active", cgpa=cgpa, hosteller=hosteller,
                                scholarship=scholarship,
                                blood_group=R.choice(["A+", "A-", "B+", "B-", "AB+", "O+"]),
                                student_type="Regular"))

    # Flush again before inserting dependent enrollments, assessments and marks.
    s.flush()

    sections_by_key = {}
    for sid, cid, did, code, sem, fid, sec_code in section_rows:
        sections_by_key.setdefault((code, sem), []).append(sid)
        section = s.get(D.Section, sid)
        if section:
            _ensure_timetable_entries_for_section(s, section)

    enr_i = 0
    for stu_id, code, did, sem, batch, cgpa in student_rows:
        for sec_id in sections_by_key.get((code, sem), [])[:4]:
            enr_i += 1
            s.add(D.Enrollment(id=f"enr_{enr_i}", tenant_id=TENANT,
                               student_id=stu_id, section_id=sec_id,
                               status="enrolled"))

    asmt_i = 0
    for sid, cid, did, code, sem, fid, sec_code in section_rows[:30]:
        for aname, mx, assessment_type, days_out in [
            ("Midterm", 50, "test", -20),
            ("Quiz 1", 20, "quiz", 7),
        ]:
            asmt_i += 1
            s.add(D.Assessment(id=f"asmt_{asmt_i}", tenant_id=TENANT, section_id=sid,
                               name=aname, max_marks=mx, weight=1.0,
                               assessment_type=assessment_type,
                               scheduled_at=datetime.combine(date.today() + timedelta(days=days_out), datetime.min.time()).replace(hour=10),
                               end_at=datetime.combine(date.today() + timedelta(days=days_out), datetime.min.time()).replace(hour=11),
                               published=(days_out >= 0),
                               instructions="Carry your university ID card.",
                               status="published" if days_out >= 0 else "closed"))

    for i in range(1, 26):
        prog = R.choice(list(dept_ids.keys()))
        s.add(D.Application(id=f"app_{i}", tenant_id=TENANT,
                            applicant_name=_name(), email=f"applicant{i}@mail.com",
                            program_name=f"BTECH {prog}",
                            score=round(R.uniform(60, 99), 1),
                            status=R.choice(["submitted", "submitted", "verified", "offered"])))

    payment_rows = []
    for stu_id, code, did, sem, batch, cgpa in student_rows:
        amt = R.choice([120000, 135000, 150000])
        paid = amt if R.random() > 0.35 else (amt // 2 if R.random() > 0.5 else 0)
        status = "paid" if paid >= amt else ("partial" if paid > 0 else "due")
        inv_id = f"inv_{stu_id}"
        s.add(D.FeeInvoice(id=inv_id, tenant_id=TENANT, student_id=stu_id,
                           term=term, amount=amt, paid=paid, status=status,
                           due_date=date(today.year, 8, 31)))
        if paid > 0:
            payment_rows.append((inv_id, stu_id, paid, f"TXN{R.randint(10**7, 10**8)}"))

    s.flush()
    for inv_id, stu_id, paid, reference in payment_rows:
        s.add(D.Payment(id=f"pay_{stu_id}", tenant_id=TENANT, invoice_id=inv_id,
                        student_id=stu_id, amount=paid, method="online",
                        reference=reference))

    for cat, alloc in [
        ("Salaries", 240000000), ("Infrastructure", 90000000),
        ("Laboratories", 45000000), ("Library", 12000000),
        ("Research", 60000000), ("Scholarships", 30000000),
        ("Maintenance", 18000000), ("IT & Systems", 25000000),
    ]:
        s.add(D.BudgetLine(id=f"bud_{cat.lower().replace(' ', '_')}", tenant_id=TENANT,
                           campus=CAMPUS_SCOPES[0], category=cat, allocated=alloc,
                           spent=round(alloc * R.uniform(0.3, 0.85)), fiscal_year=fiscal_year))

    book_ids = []
    for i, (title, author, cat) in enumerate(BOOK_TITLES, 1):
        total = R.randint(3, 12)
        avail = R.randint(0, total)
        bid = f"book_{i}"
        book_ids.append(bid)
        s.add(D.Book(id=bid, tenant_id=TENANT, isbn=f"978-0-{R.randint(100000, 999999)}",
                     title=title, author=author, category=cat,
                     copies_total=total, copies_available=avail))
    s.flush()
    for i in range(1, 13):
        stu = R.choice(student_rows)
        s.add(D.BookLoan(id=f"loan_{i}", tenant_id=TENANT, book_id=R.choice(book_ids),
                         borrower=stu[0], student_id=stu[0], borrower_name=_name(),
                         issued_on=today - timedelta(days=R.randint(1, 40)),
                         due_on=today + timedelta(days=R.randint(-10, 14)),
                         returned=False, fine=0))

    all_faculty = [f for rows in faculty_by_dept.values() for f in rows]
    for i in range(1, 11):
        fid, fnm = R.choice(all_faculty)
        frm = today + timedelta(days=R.randint(-5, 20))
        days = R.randint(1, 5)
        s.add(D.LeaveRequest(id=f"leave_{i}", tenant_id=TENANT, staff_id=fid,
                             staff_name=fnm, kind=R.choice(["Casual", "Medical", "Earned"]),
                             from_date=frm, to_date=frm + timedelta(days=days - 1),
                             days=days, reason=R.choice(["Personal", "Medical", "Conference", "Family"]),
                             status=R.choice(["pending", "pending", "approved"])))
    for i, (title, dept, kind) in enumerate([
        ("Assistant Professor - CSE", "CSE", "Faculty"),
        ("Lab Technician - ECE", "ECE", "Staff"),
        ("Associate Professor - MGT", "MGT", "Faculty"),
        ("Junior Accountant", "Finance", "Staff"),
    ], 1):
        s.add(D.JobPosting(id=f"job_{i}", tenant_id=TENANT, title=title, dept=dept,
                           kind=kind, openings=R.randint(1, 3), status="open"))

    room_ids = []
    for block in ["A-Block", "B-Block", "C-Block"]:
        for rn in range(101, 121):
            rid = f"room_{block[0].lower()}{rn}"
            room_ids.append(rid)
            s.add(D.HostelRoom(id=rid, tenant_id=TENANT, block=block,
                               room_no=str(rn), capacity=2, occupied=R.randint(0, 2)))
    s.flush()
    for i in range(1, 16):
        s.add(D.HostelAllocation(id=f"halloc_{i}", tenant_id=TENANT,
                                 room_id=R.choice(room_ids), student_name=_name(),
                                 status=R.choice(["requested", "requested", "allocated"])))

    for i, (name, stops) in enumerate([
        ("Route 1 - City Center", "Gate, MG Road, Central, Campus"),
        ("Route 2 - Airport Line", "Gate, Airport Rd, Tech Park, Campus"),
        ("Route 3 - Suburb", "Gate, Lake View, Suburb, Campus"),
    ], 1):
        s.add(D.TransportRoute(id=f"route_{i}", tenant_id=TENANT, name=name, stops=stops,
                               vehicle_no=f"KA-01-{R.randint(1000, 9999)}", seats=40,
                               seats_taken=R.randint(15, 40)))

    for i in range(1, 21):
        cat = R.choice(["Lab Equipment", "Furniture", "IT Hardware", "Vehicle", "AV Equipment"])
        s.add(D.Asset(id=f"asset_{i}", tenant_id=TENANT, tag=f"AST{i:04d}",
                      name=f"{cat} #{i}", category=cat,
                      location=f"{R.choice(['CSE', 'ECE', 'MEC', 'Library', 'Admin'])} Block",
                      status=R.choice(["in-service", "in-service", "maintenance"]),
                      value=round(R.uniform(20000, 800000))))

    for i in range(1, 13):
        code = R.choice(list(dept_ids.keys()))
        fid, fnm = R.choice(faculty_by_dept[code])
        s.add(D.ResearchProject(id=f"proj_{i}", tenant_id=TENANT,
                                title=R.choice([
                                    "Deep Learning for Medical Imaging",
                                    "Low-power VLSI for IoT",
                                    "Sustainable Concrete Composites",
                                    "Smart Grid Optimization",
                                    "Autonomous Navigation Systems",
                                    "Quantum Algorithms",
                                    "Renewable Energy Forecasting",
                                    "Natural Language Understanding",
                                ]),
                                pi_name=fnm, dept=code, agency=R.choice(AGENCIES),
                                grant_amount=round(R.uniform(500000, 25000000)),
                                status=R.choice(["ongoing", "ongoing", "proposed", "completed"])))

    for i, (co, role, ctc, cg) in enumerate(COMPANIES, 1):
        s.add(D.PlacementDrive(id=f"drive_{i}", tenant_id=TENANT, company=co, role=role,
                               ctc=ctc, date=today + timedelta(days=R.randint(-30, 30)),
                               eligible_cgpa=cg, status=R.choice(["scheduled", "completed"]),
                               offers=R.randint(0, 12)))

    for i in range(1, 11):
        s.add(D.Complaint(id=f"cmp_{i}", tenant_id=TENANT,
                          kind=R.choice(["Grievance", "Grievance", "Ragging", "Discipline"]),
                          raised_by=f"{R.randint(23, 26)}CSE{R.randint(1, 200):03d}",
                          subject=R.choice([
                              "Hostel mess quality", "Re-evaluation delay",
                              "Lab access hours", "Fee receipt not generated",
                              "Ragging complaint", "Attendance discrepancy",
                              "Wi-Fi connectivity", "Scholarship disbursement",
                          ]),
                          detail="Auto-generated sample complaint for demo.",
                          status=R.choice(["open", "open", "investigating", "resolved"]),
                          severity=R.choice(["normal", "normal", "high"])))

    for student in s.query(D.Student).all():
        _ensure_identity_card(s, student, date.today() + timedelta(days=730))

    s.commit()


def _seed_reference_extensions(s):
    for code, name, dean in SCHOOLS:
        sid = f"school_{code.lower()}"
        _ensure(
            s, D.School, sid,
            lambda sid=sid, code=code, name=name, dean=dean: D.School(
                id=sid, tenant_id=TENANT, code=code, name=name, dean_name=dean
            ),
        )

    for code, name, campus in EXTRA_DEPARTMENTS:
        did = f"dept_{code.lower()}"
        _ensure(
            s, D.Department, did,
            lambda did=did, code=code, name=name, campus=campus: D.Department(
                id=did, tenant_id=TENANT, code=code, name=name, campus=campus
            ),
        )

    extra_codes = [code for code, _, _ in EXTRA_DEPARTMENTS]
    for code, name, campus in EXTRA_DEPARTMENTS:
        did = f"dept_{code.lower()}"
        pfx = _program_prefix(name)
        base_pid = f"prog_{code.lower()}_{pfx.lower()}"
        _ensure(
            s, D.Program, base_pid,
            lambda base_pid=base_pid, did=did, pfx=pfx, code=code, name=name: D.Program(
                id=base_pid, tenant_id=TENANT, dept_id=did,
                code=f"{pfx}-{code}", name=f"{pfx} {name}", level="UG", duration_years=4
            ),
        )
    for code in extra_codes[:8]:
        did = f"dept_{code.lower()}"
        pid = f"prog_{code.lower()}_mba" if code in {"ENT", "FIN", "MKT", "OPS"} else f"prog_{code.lower()}_mtech"
        pfx = "MBA" if code in {"ENT", "FIN", "MKT", "OPS"} else "MTECH"
        dname = next(name for dep_code, name, _ in EXTRA_DEPARTMENTS if dep_code == code)
        _ensure(
            s, D.Program, pid,
            lambda pid=pid, did=did, pfx=pfx, code=code, dname=dname: D.Program(
                id=pid, tenant_id=TENANT, dept_id=did,
                code=f"{pfx}-{code}", name=f"{pfx} {dname}", level="PG", duration_years=2
            ),
        )

    for acc_id, title, agency, entity_name, awarded_on, valid_until in ACCREDITATION_ROWS:
        _ensure(
            s, D.Accreditation, acc_id,
            lambda acc_id=acc_id, title=title, agency=agency, entity_name=entity_name,
            awarded_on=awarded_on, valid_until=valid_until: D.Accreditation(
                id=acc_id, tenant_id=TENANT, title=title, agency=agency,
                entity_name=entity_name, status="active",
                awarded_on=awarded_on, valid_until=valid_until
            ),
        )

    for partner_id, name, kind, scope, started_on in PARTNER_ROWS:
        _ensure(
            s, D.Partner, partner_id,
            lambda partner_id=partner_id, name=name, kind=kind, scope=scope,
            started_on=started_on: D.Partner(
                id=partner_id, tenant_id=TENANT, name=name, kind=kind, scope=scope,
                status="active", started_on=started_on
            ),
        )

    for month_idx, factor in enumerate(MONTH_FACTORS, start=1):
        month_day = date(2026, month_idx, 15)
        for category, total in INCOME_TOTALS.items():
            fid = f"fin_income_{slug(category)}_{month_idx:02d}"
            _ensure(
                s, D.FinancialEntry, fid,
                lambda fid=fid, category=category, total=total, factor=factor, month_day=month_day: D.FinancialEntry(
                    id=fid, tenant_id=TENANT, entry_type="income", category=category,
                    amount=round(total * factor, 2), campus="Group",
                    source=category, recorded_on=month_day, note="Executive income seed"
                ),
            )
        for category, total in EXPENSE_TOTALS.items():
            fid = f"fin_expense_{slug(category)}_{month_idx:02d}"
            _ensure(
                s, D.FinancialEntry, fid,
                lambda fid=fid, category=category, total=total, factor=factor, month_day=month_day: D.FinancialEntry(
                    id=fid, tenant_id=TENANT, entry_type="expense", category=category,
                    amount=round(total * factor, 2), campus="Group",
                    source=category, recorded_on=month_day, note="Executive expense seed"
                ),
            )

    for idx, (snapshot_month, total_staff, non_teaching_staff, active_users,
              outstanding_fees, system_uptime) in enumerate(SNAPSHOT_ROWS, start=1):
        sid = f"inst_snap_{idx}"
        _ensure(
            s, D.InstitutionSnapshot, sid,
            lambda sid=sid, snapshot_month=snapshot_month, total_staff=total_staff,
            non_teaching_staff=non_teaching_staff, active_users=active_users,
            outstanding_fees=outstanding_fees, system_uptime=system_uptime: D.InstitutionSnapshot(
                id=sid, tenant_id=TENANT, snapshot_month=snapshot_month,
                total_staff=total_staff, non_teaching_staff=non_teaching_staff,
                active_users=active_users, outstanding_fees=outstanding_fees,
                system_uptime=system_uptime
            ),
        )

    for idx, (snapshot_month, outstanding_amount, students_with_dues,
              overdue_over_60, notices_sent) in enumerate(OUTSTANDING_FEE_ROWS, start=1):
        sid = f"fee_snap_{idx}"
        _ensure(
            s, D.OutstandingFeeSnapshot, sid,
            lambda sid=sid, snapshot_month=snapshot_month,
            outstanding_amount=outstanding_amount, students_with_dues=students_with_dues,
            overdue_over_60=overdue_over_60, notices_sent=notices_sent: D.OutstandingFeeSnapshot(
                id=sid, tenant_id=TENANT, snapshot_month=snapshot_month,
                outstanding_amount=outstanding_amount,
                students_with_dues=students_with_dues,
                overdue_over_60=overdue_over_60,
                notices_sent=notices_sent
            ),
        )

    for row in GOVERNANCE_DASHBOARD_ROWS:
        _ensure(
            s, D.GovernanceDashboardSnapshot, row["id"],
            lambda row=row: D.GovernanceDashboardSnapshot(
                id=row["id"], tenant_id=TENANT,
                semester_key=row["semester_key"],
                semester_label=row["semester_label"],
                is_default=row["is_default"],
                student_count=row["student_count"],
                faculty_count=row["faculty_count"],
                student_faculty_ratio=row["student_faculty_ratio"],
                fee_collection_pct=row["fee_collection_pct"],
                research_grants=row["research_grants"],
                placement_offers=row["placement_offers"],
                average_cgpa=row["average_cgpa"],
                total_budget=row["total_budget"],
                utilized_budget=row["utilized_budget"],
                compliance_score=row["compliance_score"],
                compliance_label=row["compliance_label"],
                as_of_date=row["as_of_date"]
            ),
        )

    s.flush()

    for snapshot_id, rows in GOVERNANCE_COMPLIANCE_ROWS.items():
        for metric_id, category, label, score, status, sort_order in rows:
            _ensure(
                s, D.GovernanceComplianceMetric, metric_id,
                lambda metric_id=metric_id, snapshot_id=snapshot_id, category=category,
                label=label, score=score, status=status, sort_order=sort_order:
                D.GovernanceComplianceMetric(
                    id=metric_id, tenant_id=TENANT, snapshot_id=snapshot_id,
                    metric_key=slug(label), category=category, label=label,
                    score=score, status=status, sort_order=sort_order
                ),
            )

    for snapshot_id, rows in GOVERNANCE_PERFORMANCE_ROWS.items():
        for (metric_id, area, metric, current_value, target_value,
             status, trend_pct, trend_direction, icon, sort_order) in rows:
            _ensure(
                s, D.GovernancePerformanceMetric, metric_id,
                lambda metric_id=metric_id, snapshot_id=snapshot_id, area=area,
                metric=metric, current_value=current_value, target_value=target_value,
                status=status, trend_pct=trend_pct, trend_direction=trend_direction,
                icon=icon, sort_order=sort_order: D.GovernancePerformanceMetric(
                    id=metric_id, tenant_id=TENANT, snapshot_id=snapshot_id,
                    area=area, metric=metric, current_value=current_value,
                    target_value=target_value, status=status, trend_pct=trend_pct,
                    trend_direction=trend_direction, icon=icon, sort_order=sort_order
                ),
            )

    s.commit()


def _seed_chairman_workflows(s):
    proc_map = {p["key"]: p for p in APPROVAL_MATRIX}
    specs = [
        ("wf_exec_01", "infrastructure_capex", "Campus Development Plan", "under_review", 4.2e7, "user_29", "Facilities Director", 2, False, datetime(2026, 8, 2, 10, 0), datetime(2026, 8, 7, 16, 0)),
        ("wf_exec_02", "infrastructure_capex", "Campus Development Plan", "reviewed", 6.8e7, "user_3", "Campus Head", 3, False, datetime(2026, 8, 3, 11, 0), datetime(2026, 8, 9, 14, 0)),
        ("wf_exec_03", "infrastructure_capex", "Campus Development Plan", "escalated", 12.4e7, "user_4", "Principal", 3, True, datetime(2026, 7, 8, 9, 0), datetime(2026, 7, 25, 18, 0)),
        ("wf_exec_04", "purchase_request", "Budget Proposals", "submitted", 2.1e7, "user_22", "Finance Manager", 1, False, datetime(2026, 8, 1, 8, 30), datetime(2026, 8, 1, 8, 30)),
        ("wf_exec_05", "purchase_request", "Budget Proposals", "under_review", 3.6e7, "user_22", "Finance Manager", 2, False, datetime(2026, 8, 4, 9, 15), datetime(2026, 8, 5, 10, 45)),
        ("wf_exec_06", "purchase_request", "Budget Proposals", "reviewed", 1.7e7, "user_26", "Administrative Manager", 3, False, datetime(2026, 8, 5, 15, 0), datetime(2026, 8, 7, 12, 10)),
        ("wf_exec_07", "purchase_request", "Budget Proposals", "escalated", 9.8e7, "user_29", "Maintenance Manager", 3, True, datetime(2026, 7, 12, 10, 20), datetime(2026, 7, 29, 17, 20)),
        ("wf_exec_08", "purchase_request", "Budget Proposals", "escalated", 14.6e7, "user_3", "Campus Head", 3, True, datetime(2026, 7, 16, 13, 10), datetime(2026, 7, 31, 16, 0)),
        ("wf_exec_09", "branch_creation", "Policy & Regulation Updates", "under_review", None, "user_2", "Vice Chairman", 2, False, datetime(2026, 8, 6, 11, 50), datetime(2026, 8, 10, 13, 0)),
        ("wf_exec_10", "branch_creation", "Policy & Regulation Updates", "reviewed", None, "user_1", "Chairman", 3, False, datetime(2026, 8, 7, 9, 10), datetime(2026, 8, 12, 12, 40)),
        ("wf_exec_11", "recruitment", "Partnership & MoUs", "submitted", None, "user_24", "HR Director", 1, False, datetime(2026, 8, 8, 10, 0), datetime(2026, 8, 8, 10, 0)),
        ("wf_exec_12", "recruitment", "Partnership & MoUs", "under_review", None, "user_18", "Placement Director", 2, False, datetime(2026, 8, 9, 10, 15), datetime(2026, 8, 11, 11, 25)),
        ("wf_exec_13", "recruitment", "Partnership & MoUs", "escalated", None, "user_18", "Placement Director", 3, True, datetime(2026, 7, 18, 10, 0), datetime(2026, 7, 28, 15, 10)),
        ("wf_exec_14", "recruitment", "Partnership & MoUs", "escalated", None, "user_24", "HR Director", 3, True, datetime(2026, 7, 21, 11, 45), datetime(2026, 7, 30, 12, 20)),
        ("wf_exec_15", "disciplinary_action", "High-Risk Discipline Case", "escalated", None, "user_21", "Discipline Officer", 3, True, datetime(2026, 8, 13, 10, 5), datetime(2026, 8, 14, 16, 30)),
        ("wf_exec_16", "disciplinary_action", "Critical Campus Safety Review", "escalated", None, "user_21", "Discipline Officer", 3, True, datetime(2026, 8, 15, 8, 40), datetime(2026, 8, 16, 18, 5)),
        ("wf_exec_17", "student_grievance", "Women in STEM Grant Appeal", "approved", None, "user_20", "Grievance Officer", 4, False, datetime(2026, 8, 5, 8, 10), datetime(2026, 8, 13, 17, 40)),
        ("wf_exec_18", "question_paper", "Semester End Examination Security", "executed", None, "user_16", "Controller of Examinations", 4, False, datetime(2026, 8, 2, 8, 0), datetime(2026, 8, 12, 19, 0)),
        ("wf_exec_19", "payroll_approval", "August Payroll Release", "approved", 5.5e7, "user_24", "HR Director", 4, False, datetime(2026, 8, 10, 9, 0), datetime(2026, 8, 16, 11, 0)),
        ("wf_exec_20", "result_publication", "Autonomous Results Moderation", "rejected", None, "user_16", "Controller of Examinations", 2, False, datetime(2026, 7, 24, 14, 20), datetime(2026, 7, 27, 15, 0)),
    ]

    for wf_id, process_key, title, state, amount, initiator_id, initiator_name, stage, escalated, created_at, updated_at in specs:
        proc = proc_map[process_key]
        _ensure(
            s, WorkflowInstance, wf_id,
            lambda wf_id=wf_id, proc=proc, process_key=process_key, title=title,
            state=state, amount=amount, initiator_id=initiator_id,
            initiator_name=initiator_name, stage=stage, escalated=escalated,
            created_at=created_at, updated_at=updated_at: WorkflowInstance(
                id=wf_id, tenant_id=TENANT, process_key=process_key, label=proc["label"],
                office_n=proc["office_n"], title=title, state=state, amount=amount,
                initiator_id=initiator_id, initiator_name=initiator_name,
                current_stage=stage, scope_level="campus", escalated=escalated,
                created_at=created_at, updated_at=updated_at
            ),
        )

    s.flush()

    def semester_meta(created_at: datetime):
        year = created_at.year
        if created_at.month >= 7:
            start_year = year
            end_year = year + 1
            return f"odd_{start_year}_{end_year}", f"Odd Semester {start_year}-{str(end_year)[-2:]}"
        start_year = year - 1
        end_year = year
        return f"even_{start_year}_{end_year}", f"Even Semester {start_year}-{str(end_year)[-2:]}"

    profile_rows = [
        ("wf_exec_01", "Infrastructure", "CAP-2026-101", "Capital expansion pack for utilities, labs, and hostel upgrades."),
        ("wf_exec_02", "Infrastructure", "CAP-2026-102", "Follow-up tranche for the campus development and safety program."),
        ("wf_exec_03", "Infrastructure", "CAP-2026-103", "Escalated civil works package that exceeds branch authority."),
        ("wf_exec_04", "Finance", "FIN-2026-081", "Budget allocation round for shared procurement and branch upgrades."),
        ("wf_exec_05", "Finance", "FIN-2026-082", "Budget allocation package awaiting finance review."),
        ("wf_exec_06", "Finance", "FIN-2026-083", "Final procurement gate for the institutional budget refresh."),
        ("wf_exec_07", "Finance", "FIN-2026-084", "Escalated procurement request reserved for chairman visibility."),
        ("wf_exec_08", "Finance", "FIN-2026-085", "Strategic spend pack pushed upward after amount validation."),
        ("wf_exec_09", "Administrative", "PRU-2026-041", "Reserved governance update bundle covering policies and regulations."),
        ("wf_exec_10", "Administrative", "PRU-2026-042", "Chairman-originated governance amendment routed through final review."),
        ("wf_exec_11", "Human Resources", "HR-2026-031", "Faculty recruitment slate and panel approvals."),
        ("wf_exec_12", "Human Resources", "HR-2026-032", "Assistant professor and specialist recruitment package in review."),
        ("wf_exec_13", "Human Resources", "HR-2026-033", "Promotion and recruitment matter escalated for reserved sign-off."),
        ("wf_exec_14", "Partnerships", "MOU-2026-021", "Strategic partnership proposal requiring executive oversight."),
        ("wf_exec_15", "Governance", "GOV-2026-015", "Disciplinary action with reputational impact and board visibility."),
        ("wf_exec_16", "Governance", "GOV-2026-016", "Critical safety review escalated to the chairman office."),
        ("wf_exec_17", "Student Affairs", "STU-2026-011", "Research and scholarship appeal raised for final closure."),
        ("wf_exec_18", "Academic Operations", "EXM-2026-054", "Exam security approval and execution control pack."),
        ("wf_exec_19", "Finance", "PAY-2026-009", "Monthly payroll approval cycle for group release."),
        ("wf_exec_20", "Academic Operations", "EXM-2026-055", "Results moderation request rejected after evidence review."),
    ]
    spec_index = {wf_id: created_at for wf_id, _, _, _, _, _, _, _, _, created_at, _ in specs}
    for workflow_id, category, reference_code, notes in profile_rows:
        semester_key, semester_label = semester_meta(spec_index[workflow_id])
        _ensure(
            s, WorkflowProfile, f"profile_{workflow_id}",
            lambda workflow_id=workflow_id, category=category, reference_code=reference_code,
            notes=notes, semester_key=semester_key, semester_label=semester_label,
            created_at=spec_index[workflow_id]: WorkflowProfile(
                id=f"profile_{workflow_id}", tenant_id=TENANT, workflow_id=workflow_id,
                semester_key=semester_key, semester_label=semester_label, category=category,
                reference_code=reference_code, notes=notes,
                created_at=created_at, updated_at=created_at
            ),
        )

    approval_rows = [
        ("app_exec_01", "wf_exec_01", "user_29", "Facilities Director", 1, "Maintenance/Facilities", "ALLOW", "LIMITED", "Initial review completed", datetime(2026, 8, 4, 12, 0)),
        ("app_exec_02", "wf_exec_03", "user_4", "Principal", 3, "Principal", "ESCALATE", "FULL", "Capex exceeds branch authority", datetime(2026, 7, 25, 18, 0)),
        ("app_exec_03", "wf_exec_07", "user_22", "Finance Manager", 3, "Finance Mgr", "ESCALATE", "FULL", "Reserved for chairman review", datetime(2026, 7, 29, 17, 20)),
        ("app_exec_04", "wf_exec_09", "user_2", "Vice Chairman", 2, "VC", "ALLOW", "FULL", "Governance revisions incorporated", datetime(2026, 8, 10, 13, 0)),
        ("app_exec_05", "wf_exec_13", "user_24", "HR Director", 3, "Principal", "ESCALATE", "LIMITED", "Partnership proposal needs reserved sign-off", datetime(2026, 7, 28, 15, 10)),
        ("app_exec_06", "wf_exec_15", "user_4", "Principal", 3, "Principal", "ESCALATE", "FULL", "Escalated to chairman due to reputational risk", datetime(2026, 8, 14, 16, 30)),
        ("app_exec_07", "wf_exec_17", "user_4", "Principal", 4, "Principal", "ALLOW", "FULL", "Appeal approved after review", datetime(2026, 8, 13, 17, 40)),
        ("app_exec_08", "wf_exec_18", "user_16", "Controller of Examinations", 4, "Controller of Exams", "ALLOW", "FULL", "Result security controls executed", datetime(2026, 8, 12, 19, 0)),
        ("app_exec_09", "wf_exec_20", "user_16", "Controller of Examinations", 2, "Grade Verify", "DENY", "FULL", "Moderation evidence incomplete", datetime(2026, 7, 27, 15, 0)),
    ]
    for app_id, workflow_id, actor_id, actor_name, stage, stage_label, decision, authority, reason, created_at in approval_rows:
        _ensure(
            s, Approval, app_id,
            lambda app_id=app_id, workflow_id=workflow_id, actor_id=actor_id,
            actor_name=actor_name, stage=stage, stage_label=stage_label,
            decision=decision, authority=authority, reason=reason,
            created_at=created_at: Approval(
                id=app_id, tenant_id=TENANT, workflow_id=workflow_id, actor_id=actor_id,
                actor_name=actor_name, stage=stage, stage_label=stage_label,
                decision=decision, authority=authority, reason=reason,
                created_at=created_at
            ),
        )

    delegation_option_rows = [
        {"id": "deleg_opt_type_finance", "group_key": "policy_type", "option_key": "finance", "label": "Finance", "description": "Financial approvals, budgets and fund controls", "sort_order": 1},
        {"id": "deleg_opt_type_hr", "group_key": "policy_type", "option_key": "human_resources", "label": "Human Resources", "description": "People, hiring and staffing decisions", "sort_order": 2},
        {"id": "deleg_opt_type_infra", "group_key": "policy_type", "option_key": "infrastructure", "label": "Infrastructure", "description": "Infrastructure projects and facilities work", "sort_order": 3},
        {"id": "deleg_opt_type_academics", "group_key": "policy_type", "option_key": "academics", "label": "Academics", "description": "Academic programs, examination and quality controls", "sort_order": 4},
        {"id": "deleg_opt_type_governance", "group_key": "policy_type", "option_key": "governance", "label": "Governance", "description": "Policies, regulations and institutional governance", "sort_order": 5},
        {"id": "deleg_opt_scope_finance", "group_key": "delegation_scope", "option_key": "financial_approvals", "label": "Financial approvals", "description": "workflow:purchase_request,workflow:payroll_approval,workflow:fee_waiver,workflow:refund", "sort_order": 1},
        {"id": "deleg_opt_scope_hr", "group_key": "delegation_scope", "option_key": "recruitment_workflows", "label": "Recruitment workflows", "description": "workflow:recruitment", "sort_order": 2},
        {"id": "deleg_opt_scope_infra", "group_key": "delegation_scope", "option_key": "infrastructure_projects", "label": "Infrastructure projects", "description": "workflow:infrastructure_capex", "sort_order": 3},
        {"id": "deleg_opt_scope_academic", "group_key": "delegation_scope", "option_key": "academic_governance", "label": "Academic governance", "description": "workflow:branch_creation,workflow:result_publication,workflow:marks_submission,workflow:question_paper", "sort_order": 4},
        {"id": "deleg_opt_scope_scholarship", "group_key": "delegation_scope", "option_key": "scholarship_disbursement", "label": "Scholarship disbursement", "description": "workflow:fee_waiver,workflow:refund", "sort_order": 5},
        {"id": "deleg_opt_scope_governance", "group_key": "delegation_scope", "option_key": "policy_regulation_updates", "label": "Policy and regulation updates", "description": "workflow:branch_creation", "sort_order": 6},
        {"id": "deleg_opt_access_finance", "group_key": "delegation_access", "option_key": "approve:financial", "label": "Financial approvals", "description": "Approve financial items within the delegated limit", "sort_order": 1},
        {"id": "deleg_opt_access_hr", "group_key": "delegation_access", "option_key": "approve:hr", "label": "HR approvals", "description": "Approve staffing and recruitment actions", "sort_order": 2},
        {"id": "deleg_opt_access_projects", "group_key": "delegation_access", "option_key": "approve:projects", "label": "Project approvals", "description": "Approve infrastructure and capital projects", "sort_order": 3},
        {"id": "deleg_opt_access_academic", "group_key": "delegation_access", "option_key": "approve:academic", "label": "Academic approvals", "description": "Approve academic programs and result operations", "sort_order": 4},
        {"id": "deleg_opt_access_strategic", "group_key": "delegation_access", "option_key": "approve:strategic", "label": "Strategic approvals", "description": "Approve governance and strategic matters", "sort_order": 5},
        {"id": "deleg_opt_access_scholarships", "group_key": "delegation_access", "option_key": "approve:scholarships", "label": "Scholarship approvals", "description": "Approve scholarship releases and refunds", "sort_order": 6},
        {"id": "deleg_opt_access_review", "group_key": "delegation_access", "option_key": "review", "label": "Review only", "description": "Review and escalate without final approval", "sort_order": 7},
        {"id": "deleg_opt_access_view", "group_key": "delegation_access", "option_key": "view", "label": "View only", "description": "Read-only oversight access", "sort_order": 8},
        {"id": "deleg_opt_review_none", "group_key": "review_frequency", "option_key": "none", "label": "None", "description": "No recurring review scheduled", "sort_order": 1},
        {"id": "deleg_opt_review_monthly", "group_key": "review_frequency", "option_key": "monthly", "label": "Monthly", "description": "Review every month", "sort_order": 2},
        {"id": "deleg_opt_review_quarterly", "group_key": "review_frequency", "option_key": "quarterly", "label": "Quarterly", "description": "Review every quarter", "sort_order": 3},
        {"id": "deleg_opt_review_semesterly", "group_key": "review_frequency", "option_key": "semesterly", "label": "Semesterly", "description": "Review every semester", "sort_order": 4},
        {"id": "deleg_opt_review_annual", "group_key": "review_frequency", "option_key": "annual", "label": "Annual", "description": "Review once a year", "sort_order": 5},
    ]
    for item in delegation_option_rows:
        row = _ensure(
            s, DelegationOption, item["id"],
            lambda item=item: DelegationOption(id=item["id"], tenant_id=TENANT)
        )
        row.tenant_id = TENANT
        row.group_key = item["group_key"]
        row.option_key = item["option_key"]
        row.label = item["label"]
        row.description = item["description"]
        row.sort_order = item["sort_order"]
        row.active = True
        row.updated_at = datetime.utcnow()

    option_index = {(item["group_key"], item["option_key"]): item for item in delegation_option_rows}

    policy_rows = [
        {
            "id": "deleg_policy_budget",
            "policy_key": "budget_approval",
            "policy_type": "Finance",
            "subject": "Budget Approval",
            "authority": "approve:financial",
            "action": "approve",
            "resource_scope": "workflow:purchase_request,workflow:payroll_approval,workflow:fee_waiver,workflow:refund",
            "default_limit": 50000000,
            "delegated_to_type_default": "Office",
            "icon": "finance",
            "sort_order": 1,
        },
        {
            "id": "deleg_policy_faculty",
            "policy_key": "faculty_recruitment",
            "policy_type": "Human Resources",
            "subject": "Faculty Recruitment",
            "authority": "approve:hr",
            "action": "approve",
            "resource_scope": "workflow:recruitment",
            "default_limit": None,
            "delegated_to_type_default": "Individual",
            "icon": "people",
            "sort_order": 2,
        },
        {
            "id": "deleg_policy_infra",
            "policy_key": "infrastructure_projects",
            "policy_type": "Infrastructure",
            "subject": "Infrastructure Projects",
            "authority": "approve:projects",
            "action": "approve",
            "resource_scope": "workflow:infrastructure_capex",
            "default_limit": 20000000,
            "delegated_to_type_default": "Office",
            "icon": "shield",
            "sort_order": 3,
        },
        {
            "id": "deleg_policy_academic",
            "policy_key": "academic_program_approval",
            "policy_type": "Academics",
            "subject": "Academic Program Approval",
            "authority": "approve:academic",
            "action": "approve",
            "resource_scope": "workflow:branch_creation,workflow:result_publication,workflow:marks_submission,workflow:question_paper",
            "default_limit": None,
            "delegated_to_type_default": "Individual",
            "icon": "academy",
            "sort_order": 4,
        },
        {
            "id": "deleg_policy_scholarship",
            "policy_key": "scholarship_disbursement",
            "policy_type": "Finance",
            "subject": "Scholarship Disbursement",
            "authority": "approve:scholarships",
            "action": "approve",
            "resource_scope": "workflow:fee_waiver,workflow:refund",
            "default_limit": 5000000,
            "delegated_to_type_default": "Individual",
            "icon": "finance",
            "sort_order": 5,
        },
        {
            "id": "deleg_policy_governance",
            "policy_key": "policy_regulation_updates",
            "policy_type": "Governance",
            "subject": "Policy & Regulation Updates",
            "authority": "approve:strategic",
            "action": "approve",
            "resource_scope": "workflow:branch_creation",
            "default_limit": None,
            "delegated_to_type_default": "Office",
            "icon": "shield",
            "sort_order": 6,
        },
    ]
    for item in policy_rows:
        row = _ensure(
            s, DelegationPolicy, item["id"],
            lambda item=item: DelegationPolicy(id=item["id"], tenant_id=TENANT)
        )
        row.tenant_id = TENANT
        row.policy_key = item["policy_key"]
        row.policy_type = item["policy_type"]
        row.subject = item["subject"]
        row.authority = item["authority"]
        row.action = item["action"]
        row.resource_scope = item["resource_scope"]
        row.default_limit = item["default_limit"]
        row.delegated_to_type_default = item["delegated_to_type_default"]
        row.icon = item["icon"]
        row.sort_order = item["sort_order"]
        row.active = True
        row.updated_at = datetime.utcnow()

    delegation_rows = [
        {
            "id": "deleg_exec_01",
            "to_user": "user_2",
            "policy_key": "budget_approval",
            "limit": 50000000,
            "start": datetime(2026, 5, 1, 9, 0),
            "end": datetime(2026, 12, 31, 18, 0),
            "status": "active",
            "reason": "Vice Chairman handles strategic finance approvals during board travel.",
            "reference_code": "FIN-POL-2026-01",
            "delegated_to_type": "Office",
        },
        {
            "id": "deleg_exec_02",
            "to_user": "user_24",
            "policy_key": "faculty_recruitment",
            "limit": None,
            "start": datetime(2026, 4, 15, 9, 0),
            "end": datetime(2026, 10, 15, 18, 0),
            "status": "active",
            "reason": "HR Manager is covering faculty recruitment while the chairman focuses on board reviews.",
            "reference_code": "HR-POL-2026-02",
            "delegated_to_type": "Individual",
        },
        {
            "id": "deleg_exec_03",
            "to_user": "user_26",
            "policy_key": "infrastructure_projects",
            "limit": 20000000,
            "start": datetime(2026, 3, 10, 9, 0),
            "end": datetime(2027, 3, 10, 18, 0),
            "status": "active",
            "reason": "Admin Manager can clear operational infrastructure packages below the delegated ceiling.",
            "reference_code": "INF-POL-2026-03",
            "delegated_to_type": "Office",
        },
        {
            "id": "deleg_exec_04",
            "to_user": "user_6",
            "policy_key": "academic_program_approval",
            "limit": None,
            "start": datetime(2026, 1, 1, 9, 0),
            "end": datetime(2026, 8, 31, 18, 0),
            "status": "active",
            "reason": "Dean Academics is closing the current cycle of academic program reviews.",
            "reference_code": "ACA-POL-2026-04",
            "delegated_to_type": "Individual",
        },
        {
            "id": "deleg_exec_05",
            "to_user": "user_22",
            "policy_key": "scholarship_disbursement",
            "limit": 5000000,
            "start": datetime(2026, 2, 1, 9, 0),
            "end": datetime(2026, 7, 31, 18, 0),
            "status": "active",
            "reason": "Finance Manager was delegated scholarship disbursement authority for the summer release window.",
            "reference_code": "FIN-POL-2026-05",
            "delegated_to_type": "Individual",
        },
        {
            "id": "deleg_exec_06",
            "to_user": "user_5",
            "policy_key": "policy_regulation_updates",
            "limit": None,
            "start": datetime(2026, 3, 1, 9, 0),
            "end": datetime(2026, 12, 1, 18, 0),
            "status": "revoked",
            "reason": "Vice Principal delegation was revoked after the policy review committee changed its ownership.",
            "reference_code": "GOV-POL-2026-06",
            "delegated_to_type": "Office",
        },
    ]
    policy_map = {row["policy_key"]: row for row in policy_rows}
    delegation_context_rows = {
        "deleg_exec_01": {
            "description": "Delegates reserved finance approvals to the vice chairman during board travel and investor review periods.",
            "scope_key": "financial_approvals",
            "access_key": "approve:financial",
            "review_frequency_key": "monthly",
            "notes": "Requires weekly coordination with the finance manager for items above Rs 25 lakh.",
        },
        "deleg_exec_02": {
            "description": "Allows faculty hiring reviews to continue while the chairman is focused on board governance priorities.",
            "scope_key": "recruitment_workflows",
            "access_key": "approve:hr",
            "review_frequency_key": "quarterly",
            "notes": "Shortlist changes must still be shared in the monthly chairman HR review.",
        },
        "deleg_exec_03": {
            "description": "Supports time-bound infrastructure execution without waiting for daily chairman clearance.",
            "scope_key": "infrastructure_projects",
            "access_key": "approve:projects",
            "review_frequency_key": "quarterly",
            "notes": "Civil works exceeding the delegated ceiling must be escalated immediately.",
        },
        "deleg_exec_04": {
            "description": "Keeps academic program and examination governance moving during curriculum closeout.",
            "scope_key": "academic_governance",
            "access_key": "approve:academic",
            "review_frequency_key": "semesterly",
            "notes": "Any change impacting branch expansion should still be routed back to the chairman.",
        },
        "deleg_exec_05": {
            "description": "Covers scholarship releases and related refund actions for the summer cycle.",
            "scope_key": "scholarship_disbursement",
            "access_key": "approve:scholarships",
            "review_frequency_key": "monthly",
            "notes": "Release sheets must be filed with the chairman office after every disbursement batch.",
        },
        "deleg_exec_06": {
            "description": "Historical governance delegation retained for audit visibility after revocation.",
            "scope_key": "policy_regulation_updates",
            "access_key": "approve:strategic",
            "review_frequency_key": "none",
            "notes": "Revoked after ownership moved to a different executive office.",
        },
    }
    for item in delegation_rows:
        policy = policy_map[item["policy_key"]]
        row = _ensure(
            s, Delegation, item["id"],
            lambda item=item, policy=policy: Delegation(
                id=item["id"], tenant_id=TENANT, from_user="user_1", to_user=item["to_user"],
                authority=policy["authority"], scope_ref="scope_global", limit=item["limit"],
                start=item["start"], end=item["end"], status=item["status"], reason=item["reason"]
            ),
        )
        row.tenant_id = TENANT
        row.from_user = "user_1"
        row.to_user = item["to_user"]
        row.authority = policy["authority"]
        row.scope_ref = "scope_global"
        row.limit = item["limit"]
        row.start = item["start"]
        row.end = item["end"]
        row.status = item["status"]
        row.reason = item["reason"]

        profile = _ensure(
            s, DelegationProfile, f"profile_{item['id']}",
            lambda item=item: DelegationProfile(
                id=f"profile_{item['id']}", tenant_id=TENANT, delegation_id=item["id"]
            ),
        )
        profile.tenant_id = TENANT
        profile.delegation_id = item["id"]
        profile.policy_key = item["policy_key"]
        profile.policy_type = policy["policy_type"]
        profile.subject = policy["subject"]
        profile.reference_code = item["reference_code"]
        profile.delegated_to_type = item["delegated_to_type"]
        profile.updated_at = datetime.utcnow()

        context_item = delegation_context_rows[item["id"]]
        scope_meta = option_index[("delegation_scope", context_item["scope_key"])]
        access_meta = option_index[("delegation_access", context_item["access_key"])]
        review_meta = option_index[("review_frequency", context_item["review_frequency_key"])]
        context = _ensure(
            s, DelegationContext, f"context_{item['id']}",
            lambda item=item: DelegationContext(
                id=f"context_{item['id']}", tenant_id=TENANT, delegation_id=item["id"]
            ),
        )
        context.tenant_id = TENANT
        context.delegation_id = item["id"]
        context.policy_description = context_item["description"]
        context.scope_key = context_item["scope_key"]
        context.scope_label = scope_meta["label"]
        context.access_key = context_item["access_key"]
        context.access_label = access_meta["label"]
        context.review_frequency_key = context_item["review_frequency_key"]
        context.review_frequency_label = review_meta["label"]
        context.notes = context_item["notes"]
        context.attachment_name = ""
        context.attachment_mime_type = ""
        context.attachment_size = None
        context.attachment_data = ""
        context.updated_at = datetime.utcnow()

    chairman = s.get(User, "user_1")
    if chairman:
        notification_rows = [
            ("notif_exec_01", "critical", "Accreditation visit scheduled", "NAAC peer team visit is confirmed for City Campus on August 21, 2026.", False, datetime(2026, 8, 17, 9, 0)),
            ("notif_exec_02", "action", "Fee collection below target", "Engineering College fee realization is 12 percent below August plan.", False, datetime(2026, 8, 17, 7, 0)),
            ("notif_exec_03", "info", "New research proposal submitted", "AI & ML Research Center submitted a new multi-campus proposal.", False, datetime(2026, 8, 17, 5, 0)),
            ("notif_exec_04", "info", "Audit completed", "Internal controls audit was completed for the School of Arts & Science.", False, datetime(2026, 8, 16, 15, 0)),
            ("notif_exec_05", "action", "Reserved approval awaiting sign-off", "Two escalated strategic items are awaiting your review this week.", False, datetime(2026, 8, 16, 10, 30)),
            ("notif_exec_06", "info", "Placement milestone crossed", "North Campus reported 100 confirmed internship offers for the season.", True, datetime(2026, 8, 14, 12, 20)),
            ("notif_exec_07", "info", "Scholarship disbursement released", "Finance released the first tranche for merit scholarship recipients.", True, datetime(2026, 8, 11, 9, 40)),
        ]
        for nid, severity, title, body, read, created_at in notification_rows:
            _ensure(
                s, Notification, nid,
                lambda nid=nid, severity=severity, title=title, body=body,
                read=read, created_at=created_at, chairman=chairman: Notification(
                    id=nid, tenant_id=TENANT, user_id=chairman.id, severity=severity,
                    title=title, body=body, read=read, created_at=created_at
                ),
            )

    s.commit()


def _bind_portal_accounts(s):
    dept_ids = {d.code: d.id for d in s.query(D.Department).all()}

    def _user(uname):
        return s.query(User).filter(User.username == uname).first()

    stu_login = _user("student")
    if stu_login and "CSE" in dept_ids:
        existing_bound = s.query(D.Student).filter(D.Student.user_id == stu_login.id).order_by(D.Student.roll_no).all()
        pick = None
        if stu_login.scope_ref and not str(stu_login.scope_ref).startswith("scope_"):
            pick = s.query(D.Student).get(stu_login.scope_ref)
        if not pick and existing_bound:
            pick = existing_bound[0]
        if not pick:
            pick = (s.query(D.Student)
                    .filter(D.Student.dept_id == dept_ids["CSE"], D.Student.batch == "2023")
                    .order_by(D.Student.cgpa.desc()).first())
        if not pick:
            pick = (s.query(D.Student)
                    .filter(D.Student.dept_id == dept_ids["CSE"])
                    .order_by(D.Student.cgpa.desc()).first())
        if pick:
            demo_sections = _ensure_student_portal_demo_sections(s, dept_ids["CSE"])
            for row in existing_bound:
                if row.id != pick.id:
                    row.user_id = None
            pick.user_id = stu_login.id
            pick.name = "Ananya Rao"
            pick.semester = 7
            pick.section = "A"
            pick.batch = "2023"
            pick.status = "active"
            pick.campus = pick.campus or CAMPUS_SCOPES[0]
            pick.blood_group = pick.blood_group or "B+"
            pick.student_type = "Regular"
            stu_login.role = pick.name
            stu_login.scope_ref = pick.id
            _seed_student_portal_attendance_demo(s, pick, demo_sections)
            _seed_student_portal_examinations_demo(s, pick, demo_sections)
            any_book = s.query(D.Book).first()
            if any_book:
                _ensure(
                    s, D.BookLoan, f"loan_bound_{pick.id}",
                    lambda any_book=any_book, pick=pick: D.BookLoan(
                        id=f"loan_bound_{pick.id}", tenant_id=TENANT, book_id=any_book.id,
                        borrower=pick.id, student_id=pick.id, borrower_name=pick.name,
                        issued_on=DEMO_ATTENDANCE_TODAY - timedelta(days=6),
                        due_on=DEMO_ATTENDANCE_TODAY + timedelta(days=8), returned=False
                    ),
                )
            invoice = s.query(D.FeeInvoice).filter(D.FeeInvoice.student_id == pick.id).first()
            if invoice:
                invoice.paid = round(invoice.amount * 0.5)
                invoice.status = "partial"
                payments = (s.query(D.Payment)
                            .filter(D.Payment.student_id == pick.id)
                            .order_by(D.Payment.at).all())
                if payments:
                    payments[0].amount = round(invoice.amount * 0.35)
                    payments[0].method = "upi"
                    payments[0].reference = f"TXN-DEMO-{pick.roll_no}-1"
                    payments[0].at = datetime.combine(DEMO_ATTENDANCE_TODAY - timedelta(days=42), datetime.min.time())
                else:
                    _ensure(
                        s, D.Payment, f"pay_bound_{pick.id}_1",
                        lambda pick=pick, invoice=invoice: D.Payment(
                            id=f"pay_bound_{pick.id}_1", tenant_id=TENANT,
                            invoice_id=invoice.id, student_id=pick.id,
                            amount=round(invoice.amount * 0.35), method="upi",
                            reference=f"TXN-DEMO-{pick.roll_no}-1",
                            at=datetime.combine(DEMO_ATTENDANCE_TODAY - timedelta(days=42), datetime.min.time())
                        ),
                    )
                _ensure(
                    s, D.Payment, f"pay_bound_{pick.id}_2",
                    lambda pick=pick, invoice=invoice: D.Payment(
                        id=f"pay_bound_{pick.id}_2", tenant_id=TENANT,
                        invoice_id=invoice.id, student_id=pick.id,
                        amount=round(invoice.amount * 0.15), method="netbanking",
                        reference=f"TXN-DEMO-{pick.roll_no}-2",
                        at=datetime.combine(DEMO_ATTENDANCE_TODAY - timedelta(days=11), datetime.min.time())
                    ),
                )
            any_room = s.query(D.HostelRoom).first()
            if any_room:
                _ensure(
                    s, D.HostelAllocation, f"halloc_bound_{pick.id}",
                    lambda pick=pick, any_room=any_room: D.HostelAllocation(
                        id=f"halloc_bound_{pick.id}", tenant_id=TENANT,
                        room_id=any_room.id, student_id=pick.id,
                        student_name=pick.name, status="requested"
                    ),
                )
            _ensure(
                s, D.Complaint, f"cmp_bound_{pick.id}",
                lambda pick=pick: D.Complaint(
                    id=f"cmp_bound_{pick.id}", tenant_id=TENANT,
                    kind="Grievance", raised_by=pick.roll_no,
                    subject="Scholarship reimbursement status",
                    detail="Student portal showcase complaint used to verify grievance workflows.",
                    status="investigating", severity="high"
                ),
            )
            _ensure_identity_card(s, pick, DEMO_ATTENDANCE_TODAY + timedelta(days=640))
            program = s.query(D.Program).get(pick.program_id) if pick.program_id else None
            if demo_sections:
                _ensure(
                    s, D.Announcement, f"ann_section_{pick.id}",
                    lambda pick=pick, sec=demo_sections[0]["section"]: D.Announcement(
                        id=f"ann_section_{pick.id}", tenant_id=TENANT,
                        title="Section workshop on applied AI",
                        body="Your enrolled section has a faculty workshop this week. Attendance is recommended.",
                        audience="section", campus=pick.campus, department_id=pick.dept_id,
                        program_id=pick.program_id, section_id=sec.id, student_id=None,
                        published_at=DEMO_ATTENDANCE_NOW - timedelta(hours=3),
                        expires_at=DEMO_ATTENDANCE_NOW + timedelta(days=7),
                        status="published", created_by="Academic Coordinator Office", owner_office_n=17
                    ),
                )
            _ensure(
                s, D.Announcement, f"ann_dept_{pick.id}",
                lambda pick=pick: D.Announcement(
                    id=f"ann_dept_{pick.id}", tenant_id=TENANT,
                    title="Department mentoring slots open",
                    body="CSE mentoring bookings are now open for the current week.",
                    audience="department", campus=pick.campus, department_id=pick.dept_id,
                    program_id=None, section_id=None, student_id=None,
                    published_at=DEMO_ATTENDANCE_NOW - timedelta(days=1),
                    expires_at=DEMO_ATTENDANCE_NOW + timedelta(days=10),
                    status="published", created_by="Head of Department Office", owner_office_n=10
                ),
            )
            _ensure(
                s, D.Announcement, f"ann_program_{pick.id}",
                lambda pick=pick, program=program: D.Announcement(
                    id=f"ann_program_{pick.id}", tenant_id=TENANT,
                    title="Programme elective counselling window",
                    body="Programme electives counselling has opened for your cohort.",
                    audience="program", campus=pick.campus, department_id=pick.dept_id,
                    program_id=program.id if program else None, section_id=None, student_id=None,
                    published_at=DEMO_ATTENDANCE_NOW - timedelta(days=2),
                    expires_at=DEMO_ATTENDANCE_NOW + timedelta(days=12),
                    status="published", created_by="Dean Academics Office", owner_office_n=6
                ),
            )
            _ensure(
                s, D.Announcement, f"ann_direct_{pick.id}",
                lambda pick=pick: D.Announcement(
                    id=f"ann_direct_{pick.id}", tenant_id=TENANT,
                    title="Scholarship document reminder",
                    body="Please review your scholarship documentation before the due date.",
                    audience="student", campus=pick.campus, department_id=pick.dept_id,
                    program_id=pick.program_id, section_id=None, student_id=pick.id,
                    published_at=DEMO_ATTENDANCE_NOW - timedelta(hours=8),
                    expires_at=DEMO_ATTENDANCE_NOW + timedelta(days=5),
                    status="published", created_by="Dean Student Affairs Office", owner_office_n=8
                ),
            )

    parent_login = _user("parent")
    if parent_login and stu_login:
        bound = s.query(D.Student).filter(D.Student.user_id == stu_login.id).first()
        if bound:
            parent_login.scope_ref = bound.id
            parent_login.role = f"Parent / Guardian - {bound.name}"

    teaching_offices = {11, 12, 13, 14}
    used_staff = set()
    for office_n, uname in DEMO_USERNAMES.items():
        if office_n not in teaching_offices:
            continue
        login = _user(uname)
        if not login:
            continue
        candidate = None
        for staff in s.query(D.StaffMember).all():
            if staff.id in used_staff:
                continue
            if s.query(D.Section).filter(D.Section.faculty_person_id == staff.id).count() > 0:
                candidate = staff
                break
        if candidate:
            candidate.user_id = login.id
            candidate.office_n = office_n
            used_staff.add(candidate.id)
            login.role = candidate.name
            login.scope_ref = candidate.dept_id or login.scope_ref

    hod_login = _user("hod")
    if hod_login and "CSE" in dept_ids:
        dep = s.query(D.Department).filter(D.Department.code == "CSE").first()
        if dep:
            hod_login.scope_ref = dep.id
            candidate = (s.query(D.StaffMember)
                         .filter(D.StaffMember.dept_id == dep.id)
                         .order_by(D.StaffMember.date_joined).first())
            if candidate:
                candidate.user_id = hod_login.id
                dep.hod_person_id = candidate.id

    s.commit()


def _seed_principal_dashboard_data(s):
    """Populate idempotent, date-distributed demo records for the Principal view.

    These are normal AttendanceRecord/Notification/WorkflowInstance rows, not
    frontend fixtures, so the dashboard always uses the same API and database
    path as live deployments.
    """
    enrollments = s.query(D.Enrollment).filter(D.Enrollment.status == "enrolled").limit(90).all()
    today = date.today()
    for index, enrollment in enumerate(enrollments):
        for months_back in range(6):
            month = (today.replace(day=1) - timedelta(days=months_back * 31)).replace(day=1)
            day_offsets = (3, 11, 19, today.day) if months_back == 0 else (3, 11, 19)
            for day_offset in day_offsets:
                on_date = month + timedelta(days=day_offset)
                if on_date > today:
                    continue
                record_id = f"att_principal_{enrollment.id}_{on_date.isoformat()}"
                _ensure(
                    s, D.AttendanceRecord, record_id,
                    lambda record_id=record_id, enrollment=enrollment, on_date=on_date, index=index, day_offset=day_offset:
                        D.AttendanceRecord(
                            id=record_id, tenant_id=TENANT, section_id=enrollment.section_id,
                            student_id=enrollment.student_id, on_date=on_date,
                            present=((index + day_offset + on_date.month) % 11 != 0), marked_by="Faculty"
                        ),
                )

    principal = s.query(User).filter(User.username == "principal").first()
    if principal:
        notification_rows = [
            ("notif_principal_01", "critical", "Attendance threshold breach", "One section recorded attendance below the campus threshold.", False),
            ("notif_principal_02", "action", "Faculty leave request awaiting review", "A faculty leave request has reached the Principal review stage.", False),
            ("notif_principal_03", "action", "Maintenance escalation", "A laboratory equipment maintenance request requires campus attention.", False),
        ]
        for nid, severity, title, body, read in notification_rows:
            _ensure(s, Notification, nid, lambda nid=nid, severity=severity, title=title, body=body, read=read:
                    Notification(id=nid, tenant_id=TENANT, user_id=principal.id, severity=severity,
                                 title=title, body=body, read=read, created_at=datetime.utcnow()))
        _ensure(
            s, WorkflowInstance, "wf_principal_01",
            lambda: WorkflowInstance(id="wf_principal_01", tenant_id=TENANT,
                process_key="disciplinary_action", label="Disciplinary action",
                office_n=4, title="Faculty leave approval exception", state="under_review",
                amount=None, initiator_id="user_24", initiator_name="HR Manager",
                current_stage=3, scope_level="campus", escalated=False,
                created_at=datetime.utcnow(), updated_at=datetime.utcnow()),
        )
    s.commit()


def _seed_principal_schedule_events(s):
    """Personal agenda data for the Principal schedule; separate from the timetable."""
    today = date.today()
    def at(offset, hour, minute, duration=60):
        start = datetime.combine(today + timedelta(days=offset), datetime.min.time()).replace(hour=hour, minute=minute)
        return start, start + timedelta(minutes=duration)
    specs = [
        ("psched_01", "HOD Review Meeting", "Meetings", 0, 9, 30, 60, "Conference Room A", "#2878e6", "published"),
        ("psched_02", "Purchase Request Approval Review", "Approvals", 0, 11, 0, 60, "Principal Office", "#f28a16", "action"),
        ("psched_03", "Student Grievance Hearing", "Student Affairs", 0, 14, 0, 60, "Principal Office", "#8d48d7", "action"),
        ("psched_04", "IQAC Review Meeting", "Meetings", 0, 16, 0, 60, "IQAC Cell", "#159e9d", "published"),
        ("psched_05", "Recruitment Panel Interview", "HR", 1, 10, 0, 90, "Board Room", "#ed657e", "published"),
        ("psched_06", "Maintenance Review Meeting", "Operations", 1, 14, 30, 60, "Admin Block", "#d69e27", "published"),
        ("psched_07", "Dean Academics Meeting", "Meetings", 2, 9, 0, 60, "Conference Room B", "#2878e6", "published"),
        ("psched_08", "Academic Council Meeting", "Academics", 2, 11, 30, 60, "Seminar Hall", "#269a55", "published"),
        ("psched_09", "Faculty Leave Approvals", "Approvals", 2, 15, 0, 60, "Principal Office", "#e27f37", "action"),
        ("psched_10", "Exam Readiness Review", "Exams", 3, 9, 30, 60, "Exam Cell", "#1b9aa2", "published"),
        ("psched_11", "Disciplinary Committee Meeting", "Student Affairs", 3, 14, 0, 60, "Conference Room A", "#8d48d7", "action"),
        ("psched_12", "Personal Time (Planning & Review)", "Personal", 3, 16, 30, 60, "Principal Office", "#718096", "published"),
        ("psched_13", "Vendor Payment Approval Review", "Approvals", 4, 11, 0, 60, "Finance Office", "#e27f37", "action"),
        ("psched_14", "HOD – CSE Department Review", "Meetings", 4, 15, 0, 60, "CSE Department Office", "#2878e6", "published"),
        ("psched_15", "Campus Safety Walkthrough", "Operations", 5, 10, 0, 60, "North Gate", "#d69e27", "published"),
    ]
    for event_id, title, category, offset, hour, minute, duration, location, color, status in specs:
        start_at, end_at = at(offset, hour, minute, duration)
        _ensure(s, D.CalendarEvent, event_id, lambda event_id=event_id, title=title, category=category,
                start_at=start_at, end_at=end_at, location=location, color=color, status=status:
                D.CalendarEvent(id=event_id, tenant_id=TENANT, title=title, category=category,
                    audience="leadership", start_at=start_at, end_at=end_at, all_day=False,
                    location=location, description=f"Principal agenda item: {title}.", owner_office_n=4,
                    source_type="manual", source_ref="principal_schedule", color=color, status=status,
                    created_by="user_4", updated_by="user_4"))
    s.commit()


def _seed_development_backlog_history(s):
    """Clearly marked local-development sample records for backlog UI development.

    Replace these with published Examination data before any production use.
    """
    portal_student_id = None
    portal_login = s.query(User).filter(User.username == "student").first()
    if portal_login:
        if portal_login.scope_ref and not str(portal_login.scope_ref).startswith("scope_"):
            portal_student_id = portal_login.scope_ref
        else:
            student_row = s.query(D.Student).filter(D.Student.user_id == portal_login.id).first()
            portal_student_id = student_row.id if student_row else None
    students = s.query(D.Student).order_by(D.Student.roll_no).limit(12).all()
    subjects = [("MAT301", "Engineering Mathematics III"), ("CSE302", "Data Structures"), ("ECE303", "Digital Systems")]
    for index, student in enumerate(students):
        if portal_student_id and student.id == portal_student_id:
            continue
        if index % 3 == 0:
            code, title = subjects[index % len(subjects)]
            _ensure(s, D.StudentSubjectResult, f"dev_result_{student.id}_a1", lambda student=student, code=code, title=title:
                    D.StudentSubjectResult(id=f"dev_result_{student.id}_a1", tenant_id=TENANT, student_id=student.id,
                        academic_year="2025-26", semester=max(1, student.semester - 1), subject_code=code,
                        subject_title=title, attempt=1, outcome="failed", published_at=datetime.utcnow(), source="development_sample"))
        if index % 6 == 0:
            code, title = subjects[index % len(subjects)]
            _ensure(s, D.StudentSubjectResult, f"dev_result_{student.id}_a2", lambda student=student, code=code, title=title:
                    D.StudentSubjectResult(id=f"dev_result_{student.id}_a2", tenant_id=TENANT, student_id=student.id,
                        academic_year="2026-27", semester=student.semester, subject_code=code,
                        subject_title=title, attempt=2, outcome="passed", published_at=datetime.utcnow(), source="development_sample"))
        elif index % 3 == 0:
            code, title = subjects[(index + 1) % len(subjects)]
            _ensure(s, D.StudentSubjectResult, f"dev_result_{student.id}_current", lambda student=student, code=code, title=title:
                    D.StudentSubjectResult(id=f"dev_result_{student.id}_current", tenant_id=TENANT, student_id=student.id,
                        academic_year="2026-27", semester=student.semester, subject_code=code,
                        subject_title=title, attempt=1, outcome="failed", published_at=datetime.utcnow(), source="development_sample"))
    s.commit()


def _seed_student_portal_demo_profile(s):
    stu_login = s.query(User).filter(User.username == "student").first()
    if not stu_login:
        return

    student = None
    if stu_login.scope_ref and not str(stu_login.scope_ref).startswith("scope_"):
        student = s.query(D.Student).get(stu_login.scope_ref)
    if not student:
        student = s.query(D.Student).filter(D.Student.user_id == stu_login.id).order_by(D.Student.roll_no).first()
    if not student:
        return
    s.query(D.ExamScheduleHistory).filter(D.ExamScheduleHistory.id.like(f"exhist_scorehist_{student.id}_%")).delete(synchronize_session=False)
    s.query(D.ExamScheduleEntry).filter(D.ExamScheduleEntry.id.like(f"exsched_scorehist_{student.id}_%")).delete(synchronize_session=False)
    s.query(D.Mark).filter(D.Mark.id.like(f"mk_scorehist_{student.id}_%")).delete(synchronize_session=False)
    s.query(D.Assessment).filter(D.Assessment.id.like(f"asmt_scorehist_{student.id}_%")).delete(synchronize_session=False)
    s.query(D.Enrollment).filter(D.Enrollment.id.like(f"enr_scorehist_{student.id}_%")).delete(synchronize_session=False)
    s.query(D.ResultSheet).filter(D.ResultSheet.id.like(f"rsheet_scorehist_{student.id}_%")).delete(synchronize_session=False)
    s.query(D.StudentSubjectResult).filter(
        D.StudentSubjectResult.student_id == student.id,
        D.StudentSubjectResult.source == "development_sample",
    ).delete(synchronize_session=False)
    s.query(D.StudentSubjectResult).filter(
        D.StudentSubjectResult.student_id == student.id,
        D.StudentSubjectResult.id.like("student_demo_%"),
    ).delete(synchronize_session=False)
    s.query(D.StudentSubjectResult).filter(
        D.StudentSubjectResult.student_id == student.id,
        D.StudentSubjectResult.id.like(f"scorehist_result_{student.id}_%"),
    ).delete(synchronize_session=False)
    s.flush()

    academic_year_by_semester = {
        1: "2023-24",
        2: "2023-24",
        3: "2024-25",
        4: "2024-25",
        5: "2025-26",
        6: "2025-26",
    }
    result_publish_dates = {
        1: datetime(2024, 1, 12, 11, 0),
        2: datetime(2024, 7, 5, 11, 0),
        3: datetime(2025, 1, 10, 11, 0),
        4: datetime(2025, 7, 4, 11, 0),
        5: datetime(2026, 1, 11, 11, 0),
        6: datetime(2026, 7, 5, 11, 0),
    }
    assessment_months = {
        1: (2023, 10),
        2: (2024, 4),
        3: (2024, 10),
        4: (2025, 4),
        5: (2025, 10),
        6: (2026, 4),
    }
    semester_grade_profiles = {
        1: [(9.0, 89.0), (8.0, 84.0), (8.0, 82.0), (8.0, 80.0)],
        2: [(8.0, 83.0), (8.0, 81.0), (8.0, 79.0), (0.0, 46.0)],
        3: [(8.0, 84.0), (8.0, 82.0), (8.0, 80.0), (8.0, 78.0)],
        4: [(9.0, 88.0), (8.0, 84.0), (8.0, 82.0), (8.0, 80.0)],
        5: [(8.0, 83.0), (8.0, 81.0), (8.0, 79.0), (8.0, 78.0)],
        6: [(8.0, 82.0), (8.0, 80.0), (8.0, 78.0), (0.0, 44.0)],
    }

    def grade_for_point(point: float) -> str:
        if point >= 9:
            return "A+"
        if point >= 8:
            return "A"
        if point >= 7:
            return "B+"
        if point >= 6:
            return "B"
        if point > 0:
            return "C"
        return "F"

    all_offering_rows = (
        s.query(D.Section, D.Course)
        .join(D.Course, D.Course.id == D.Section.course_id)
        .order_by(D.Course.semester, D.Course.code, D.Section.section_code)
        .all()
    )
    all_offerings = []
    seen_courses = set()
    for section, course in all_offering_rows:
        if course.id in seen_courses:
            continue
        seen_courses.add(course.id)
        faculty = s.query(D.StaffMember).get(section.faculty_person_id) if section.faculty_person_id else None
        all_offerings.append({"section": section, "course": course, "faculty": faculty})

    def pick_semester_offerings(semester_value: int):
        if not all_offerings:
            return []
        start_index = (semester_value - 1) * 4
        rows = (
            all_offerings[start_index:start_index + 4]
            if start_index + 4 <= len(all_offerings)
            else all_offerings[start_index:] + all_offerings[:max(0, (start_index + 4) - len(all_offerings))]
        )
        return rows[:4]

    def ensure_completed_enrollment(item, grade: str = ""):
        enrollment_id = f"enr_scorehist_{student.id}_{item['section'].id}"
        enrollment = _ensure(
            s, D.Enrollment, enrollment_id,
            lambda enrollment_id=enrollment_id, item=item: D.Enrollment(
                id=enrollment_id,
                tenant_id=TENANT,
                student_id=student.id,
                section_id=item["section"].id,
                status="completed",
                grade=grade,
            ),
        )
        enrollment.student_id = student.id
        enrollment.section_id = item["section"].id
        enrollment.status = "completed"
        enrollment.grade = grade

    def create_archived_assessment(item, semester_value: int, academic_year: str, score_pct: float):
        year_value, month_value = assessment_months[semester_value]
        templates = [
            ("quiz", "Quiz 1", 20.0, 1.0, 9),
            ("mid_term", "Mid Semester", 30.0, 2.0, 17),
            ("external_final", "External Final", 50.0, 3.0, 24),
        ]
        for type_key, label, max_marks, weight, day_value in templates:
            start_at = datetime(year_value, month_value, day_value, 10, 0)
            end_at = start_at + timedelta(minutes=90 if type_key != "external_final" else 120)
            score_value = round((score_pct / 100.0) * max_marks, 1)
            assessment_id = f"asmt_scorehist_{student.id}_s{semester_value}_{item['course'].code.lower()}_{type_key}"
            assessment = _ensure(
                s, D.Assessment, assessment_id,
                lambda assessment_id=assessment_id, item=item: D.Assessment(
                    id=assessment_id,
                    tenant_id=TENANT,
                    section_id=item["section"].id,
                    name=f"{item['course'].code} {label}",
                    max_marks=max_marks,
                    weight=weight,
                    locked=False,
                    assessment_type=type_key,
                    scheduled_at=start_at,
                    end_at=end_at,
                    published=True,
                    instructions="Archived published score retained from official faculty upload.",
                    status="completed",
                ),
            )
            assessment.section_id = item["section"].id
            assessment.name = f"{item['course'].code} {label}"
            assessment.max_marks = max_marks
            assessment.weight = weight
            assessment.locked = False
            assessment.assessment_type = type_key
            assessment.scheduled_at = start_at
            assessment.end_at = end_at
            assessment.published = True
            assessment.instructions = "Archived published score retained from official faculty upload."
            assessment.status = "completed"
            assessment.academic_year = academic_year
            assessment.created_by = item["faculty"].name if item["faculty"] else "Faculty"
            assessment.updated_by = item["faculty"].name if item["faculty"] else "Faculty"
            assessment.created_at = start_at - timedelta(days=7)
            assessment.updated_at = end_at + timedelta(hours=1)
            assessment.published_at = end_at + timedelta(hours=5)
            assessment.published_by = item["faculty"].name if item["faculty"] else "Faculty"

            schedule_id = f"exsched_scorehist_{student.id}_{assessment_id}"
            schedule = _ensure(
                s, D.ExamScheduleEntry, schedule_id,
                lambda schedule_id=schedule_id, assessment=assessment, item=item: D.ExamScheduleEntry(
                    id=schedule_id,
                    tenant_id=TENANT,
                    assessment_id=assessment.id,
                    section_id=item["section"].id,
                    academic_year=academic_year,
                    semester=semester_value,
                    exam_type=type_key,
                    start_at=start_at,
                    end_at=end_at,
                    venue=item["section"].room or "Academic Block",
                    mode="Offline",
                    status="completed",
                    version_no=1,
                    is_active=True,
                    managed_by_office_n=16 if type_key == "external_final" else 10,
                    note="Archived examination timetable retained for student score history.",
                    created_by="Exam Controller Office" if type_key == "external_final" else "Head of Department Office",
                    updated_by="Exam Controller Office" if type_key == "external_final" else "Head of Department Office",
                    created_at=start_at - timedelta(days=7),
                    updated_at=end_at + timedelta(hours=1),
                ),
            )
            schedule.assessment_id = assessment.id
            schedule.section_id = item["section"].id
            schedule.academic_year = academic_year
            schedule.semester = semester_value
            schedule.exam_type = type_key
            schedule.start_at = start_at
            schedule.end_at = end_at
            schedule.venue = item["section"].room or "Academic Block"
            schedule.mode = "Offline"
            schedule.status = "completed"
            schedule.version_no = 1
            schedule.is_active = True
            schedule.managed_by_office_n = 16 if type_key == "external_final" else 10
            schedule.note = "Archived examination timetable retained for student score history."
            schedule.created_by = "Exam Controller Office" if type_key == "external_final" else "Head of Department Office"
            schedule.updated_by = "Exam Controller Office" if type_key == "external_final" else "Head of Department Office"
            schedule.created_at = start_at - timedelta(days=7)
            schedule.updated_at = end_at + timedelta(hours=1)

            mark_id = f"mk_scorehist_{student.id}_{assessment_id}"
            mark = _ensure(
                s, D.Mark, mark_id,
                lambda mark_id=mark_id, assessment=assessment: D.Mark(
                    id=mark_id,
                    tenant_id=TENANT,
                    assessment_id=assessment.id,
                    student_id=student.id,
                    score=score_value,
                    entered_by=item["faculty"].name if item["faculty"] else "Faculty",
                    entered_at=end_at + timedelta(hours=2),
                    status="published",
                    published_at=end_at + timedelta(hours=5),
                    published_by=item["faculty"].name if item["faculty"] else "Faculty",
                    is_valid=True,
                    updated_at=end_at + timedelta(hours=5),
                ),
            )
            mark.assessment_id = assessment.id
            mark.student_id = student.id
            mark.score = score_value
            mark.entered_by = item["faculty"].name if item["faculty"] else "Faculty"
            mark.entered_at = end_at + timedelta(hours=2)
            mark.status = "published"
            mark.published_at = end_at + timedelta(hours=5)
            mark.published_by = item["faculty"].name if item["faculty"] else "Faculty"
            mark.is_valid = True
            mark.updated_at = end_at + timedelta(hours=5)

    semester_offerings = {}
    semester_result_sheet_ids = {}
    backlog_seed = None

    for semester_value in range(1, 7):
        offerings = pick_semester_offerings(semester_value)
        if not offerings:
            continue
        semester_offerings[semester_value] = offerings
        academic_year = academic_year_by_semester[semester_value]
        publish_at = result_publish_dates[semester_value]
        result_sheet_id = f"rsheet_scorehist_{student.id}_s{semester_value}"
        semester_result_sheet_ids[semester_value] = result_sheet_id
        result_sheet = _ensure(
            s, D.ResultSheet, result_sheet_id,
            lambda result_sheet_id=result_sheet_id, offerings=offerings: D.ResultSheet(
                id=result_sheet_id,
                tenant_id=TENANT,
                section_id=offerings[0]["section"].id,
                term=f"{academic_year} Semester {semester_value}",
                status="published",
                published_by="Exam Controller Office",
                published_at=publish_at,
                academic_year=academic_year,
                semester=semester_value,
                updated_at=publish_at,
            ),
        )
        result_sheet.section_id = offerings[0]["section"].id
        result_sheet.term = f"{academic_year} Semester {semester_value}"
        result_sheet.status = "published"
        result_sheet.published_by = "Exam Controller Office"
        result_sheet.published_at = publish_at
        result_sheet.academic_year = academic_year
        result_sheet.semester = semester_value
        result_sheet.updated_at = publish_at

        for index, item in enumerate(offerings):
            grade_point, percentage = semester_grade_profiles[semester_value][min(index, len(semester_grade_profiles[semester_value]) - 1)]
            outcome = "failed" if grade_point <= 0 else "passed"
            grade = grade_for_point(grade_point)
            ensure_completed_enrollment(item, grade=grade)
            result_id = f"scorehist_result_{student.id}_s{semester_value}_{item['course'].code.lower()}"
            row = _ensure(
                s, D.StudentSubjectResult, result_id,
                lambda result_id=result_id, item=item: D.StudentSubjectResult(
                    id=result_id,
                    tenant_id=TENANT,
                    student_id=student.id,
                    academic_year=academic_year,
                    semester=semester_value,
                    subject_code=item["course"].code,
                    subject_title=item["course"].title,
                    attempt=1,
                    outcome=outcome,
                    published_at=publish_at,
                    source="examination",
                ),
            )
            row.student_id = student.id
            row.academic_year = academic_year
            row.semester = semester_value
            row.subject_code = item["course"].code
            row.subject_title = item["course"].title
            row.attempt = 1
            row.outcome = outcome
            row.published_at = publish_at
            row.source = "examination"
            row.course_id = item["course"].id
            row.section_id = item["section"].id
            row.result_sheet_id = result_sheet_id
            row.credits = item["course"].credits
            row.grade = grade
            row.grade_point = grade_point
            row.percentage = percentage
            row.total_score = percentage
            row.max_score = 100.0
            row.updated_at = publish_at

            if semester_value == 2 and outcome == "failed" and backlog_seed is None:
                backlog_seed = {
                    "course": item["course"],
                    "section": item["section"],
                    "title": item["course"].title,
                    "credits": item["course"].credits,
                }

            if semester_value != 6 or outcome != "failed":
                create_archived_assessment(item, semester_value, academic_year, percentage)

    if 5 in semester_offerings and backlog_seed:
        retake_publish_at = datetime(2026, 1, 18, 16, 0)
        retake_result_id = f"scorehist_result_{student.id}_s5_{backlog_seed['course'].code.lower()}_retake"
        retake = _ensure(
            s, D.StudentSubjectResult, retake_result_id,
            lambda retake_result_id=retake_result_id: D.StudentSubjectResult(
                id=retake_result_id,
                tenant_id=TENANT,
                student_id=student.id,
                academic_year="2025-26",
                semester=5,
                subject_code=backlog_seed["course"].code,
                subject_title=backlog_seed["title"],
                attempt=2,
                outcome="passed",
                published_at=retake_publish_at,
                source="examination",
            ),
        )
        retake.student_id = student.id
        retake.academic_year = "2025-26"
        retake.semester = 5
        retake.subject_code = backlog_seed["course"].code
        retake.subject_title = backlog_seed["title"]
        retake.attempt = 2
        retake.outcome = "passed"
        retake.published_at = retake_publish_at
        retake.source = "examination"
        retake.course_id = backlog_seed["course"].id
        retake.section_id = backlog_seed["section"].id
        retake.result_sheet_id = semester_result_sheet_ids.get(5, "")
        retake.credits = backlog_seed["credits"]
        retake.grade = "B+"
        retake.grade_point = 7.0
        retake.percentage = 72.0
        retake.total_score = 72.0
        retake.max_score = 100.0
        retake.updated_at = retake_publish_at

    result_rows = (
        s.query(D.StudentSubjectResult)
        .filter(
            D.StudentSubjectResult.student_id == student.id,
            D.StudentSubjectResult.source == "examination",
        )
        .order_by(
            D.StudentSubjectResult.subject_code,
            D.StudentSubjectResult.attempt,
            D.StudentSubjectResult.published_at,
            D.StudentSubjectResult.updated_at,
        )
        .all()
    )
    latest_by_subject = {}
    for row in result_rows:
        latest_by_subject[row.subject_code] = row
    credit_rows = [row for row in latest_by_subject.values() if row.grade_point is not None and (row.credits or 0) > 0]
    if credit_rows:
        total_credits = sum(float(row.credits or 0) for row in credit_rows)
        total_points = sum(float(row.grade_point or 0) * float(row.credits or 0) for row in credit_rows)
        student.cgpa = round(total_points / total_credits, 2) if total_credits else None
    else:
        student.cgpa = None

    s.commit()


def _seed_development_principal_coverage(s):
    """Fill missing development-only data coverage for Principal reporting.

    These rows are intentionally tagged ``development_sample`` where the
    model supports provenance.  They are idempotent and do not alter existing
    attendance or examination rows.  Replace them with imported records before
    any production deployment.
    """
    students = s.query(D.Student).order_by(D.Student.roll_no).all()
    portal_student_id = None
    portal_login = s.query(User).filter(User.username == "student").first()
    if portal_login:
        if portal_login.scope_ref and not str(portal_login.scope_ref).startswith("scope_"):
            portal_student_id = portal_login.scope_ref
        else:
            student_row = s.query(D.Student).filter(D.Student.user_id == portal_login.id).first()
            portal_student_id = student_row.id if student_row else None
    enrolled_sections = {}
    for enrollment in s.query(D.Enrollment).filter(D.Enrollment.status == "enrolled").all():
        enrolled_sections.setdefault(enrollment.student_id, enrollment.section_id)
    department_sections = {}
    for section in s.query(D.Section).order_by(D.Section.id).all():
        department_sections.setdefault(section.dept_id, section.id)

    existing_attendance = {row[0] for row in s.query(D.AttendanceRecord.student_id).distinct().all()}
    today = date.today()
    for index, student in enumerate(students):
        if portal_student_id and student.id == portal_student_id:
            continue
        # Do not overwrite real or previously seeded attendance.  Students
        # without records receive ten dated entries, with a controlled subset
        # below 75% so attendance-risk functionality can be exercised.
        attendance_section = enrolled_sections.get(student.id) or department_sections.get(student.dept_id)
        if student.id not in existing_attendance and attendance_section:
            present_days = 7 if index % 5 == 0 else 9
            for offset in range(10):
                record_id = f"dev_attendance_{student.id}_{offset}"
                _ensure(s, D.AttendanceRecord, record_id,
                        lambda record_id=record_id, student=student, offset=offset, present_days=present_days:
                        D.AttendanceRecord(id=record_id, tenant_id=TENANT,
                            section_id=attendance_section, student_id=student.id,
                            on_date=today - timedelta(days=10 - offset),
                            present=offset < present_days, marked_by="development_sample"))

        # Three published subject outcomes per student make the backlog list
        # and department/semester analysis useful in a development database.
        # Existing result history is left untouched.
        academic_year = f"{student.batch}-{str(int(student.batch) + 1)[-2:]}" if str(student.batch).isdigit() else "development"
        for subject_index, (suffix, title) in enumerate([
            ("101", "Core Academic Subject"),
            ("102", "Applied Academic Subject"),
            ("103", "Professional Practice"),
        ]):
            code = f"DEV{student.semester}{suffix}"
            # About one in eight students has an outstanding failed subject.
            outcome = "failed" if subject_index == 0 and index % 8 == 0 else "passed"
            result_id = f"dev_coverage_result_{student.id}_{subject_index}"
            _ensure(s, D.StudentSubjectResult, result_id,
                    lambda result_id=result_id, student=student, academic_year=academic_year, code=code, title=title, outcome=outcome:
                    D.StudentSubjectResult(id=result_id, tenant_id=TENANT,
                        student_id=student.id, academic_year=academic_year,
                        semester=student.semester, subject_code=code,
                        subject_title=title, attempt=1, outcome=outcome,
                        published_at=datetime.utcnow(), source="development_sample"))
    s.commit()


def seed_domain():
    ensure_additive_schema()
    s = SessionLocal()
    try:
        _seed_core_domain(s)
        _seed_reference_extensions(s)
        _seed_calendar_data(s)
        _seed_chairman_workflows(s)
        _bind_portal_accounts(s)
        _seed_student_portal_demo_profile(s)
        _seed_principal_dashboard_data(s)
        _seed_principal_schedule_events(s)
        _seed_development_backlog_history(s)
        _seed_development_principal_coverage(s)
        return {
            "status": "domain-seeded",
            "schools": s.query(D.School).count(),
            "departments": s.query(D.Department).count(),
            "programs": s.query(D.Program).count(),
            "courses": s.query(D.Course).count(),
            "sections": s.query(D.Section).count(),
            "faculty": s.query(D.StaffMember).count(),
            "students": s.query(D.Student).count(),
            "workflows": s.query(WorkflowInstance).count(),
            "partners": s.query(D.Partner).count(),
            "accreditations": s.query(D.Accreditation).count(),
        }
    finally:
        s.close()


if __name__ == "__main__":
    print(seed_domain())
