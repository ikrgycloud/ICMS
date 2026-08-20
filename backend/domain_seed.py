# -*- coding: utf-8 -*-
"""
Domain seed for ICMS.

The seed is intentionally idempotent so repeated app startups keep enriching an
existing local database instead of short-circuiting after the first run.
"""
import random
from datetime import date, datetime, timedelta

from database import (SessionLocal, TENANT, engine, DEMO_USERNAMES, CAMPUS_SCOPES,
                      slug)
from matrices import APPROVAL_MATRIX
from models import (Base, User, Delegation, WorkflowInstance, Approval,
                    Notification)
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
            s.add(D.Course(id=cid, tenant_id=TENANT, dept_id=did, code=ccode,
                           title=title, credits=credits, semester=sem,
                           description=f"{title} core course for semester {sem}."))

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
                                scholarship=scholarship))

    # Flush again before inserting dependent enrollments, assessments and marks.
    s.flush()

    sections_by_key = {}
    for sid, cid, did, code, sem, fid, sec_code in section_rows:
        sections_by_key.setdefault((code, sem), []).append(sid)

    enr_i = 0
    for stu_id, code, did, sem, batch, cgpa in student_rows:
        for sec_id in sections_by_key.get((code, sem), [])[:4]:
            enr_i += 1
            s.add(D.Enrollment(id=f"enr_{enr_i}", tenant_id=TENANT,
                               student_id=stu_id, section_id=sec_id,
                               status="enrolled"))

    asmt_i = 0
    for sid, cid, did, code, sem, fid, sec_code in section_rows[:30]:
        for aname, mx in [("Midterm", 50), ("Quiz 1", 20)]:
            asmt_i += 1
            s.add(D.Assessment(id=f"asmt_{asmt_i}", tenant_id=TENANT, section_id=sid,
                               name=aname, max_marks=mx, weight=1.0))

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
                         borrower=stu[0], borrower_name=_name(),
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

    _ensure(
        s, Delegation, "deleg_exec_01",
        lambda: Delegation(
            id="deleg_exec_01", tenant_id=TENANT, from_user="user_1", to_user="user_2",
            authority="approve:strategic", scope_ref="scope_global", limit=50000000,
            start=datetime(2026, 8, 1, 9, 0), end=datetime(2026, 8, 31, 18, 0),
            status="active", reason="Acting authority during external board meetings"
        ),
    )

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
        pick = (s.query(D.Student)
                .filter(D.Student.dept_id == dept_ids["CSE"], D.Student.batch == "2023")
                .order_by(D.Student.cgpa.desc()).first())
        if not pick:
            pick = (s.query(D.Student)
                    .filter(D.Student.dept_id == dept_ids["CSE"])
                    .order_by(D.Student.cgpa.desc()).first())
        if pick:
            pick.user_id = stu_login.id
            stu_login.role = pick.name
            stu_login.scope_ref = pick.id
            sections = s.query(D.Section).filter(D.Section.dept_id == dept_ids["CSE"]).all()[:5]
            for sec in sections:
                enr_id = f"enr_bound_{pick.id}_{sec.id}"
                _ensure(
                    s, D.Enrollment, enr_id,
                    lambda enr_id=enr_id, sec=sec, pick=pick: D.Enrollment(
                        id=enr_id, tenant_id=TENANT, student_id=pick.id,
                        section_id=sec.id, status="enrolled"
                    ),
                )
                for k in range(30):
                    att_id = f"att_bound_{pick.id}_{sec.id}_{k}"
                    _ensure(
                        s, D.AttendanceRecord, att_id,
                        lambda att_id=att_id, sec=sec, pick=pick, k=k: D.AttendanceRecord(
                            id=att_id, tenant_id=TENANT, section_id=sec.id,
                            student_id=pick.id, on_date=date.today() - timedelta(days=k),
                            present=(k % 7 != 0), marked_by="Faculty"
                        ),
                    )
                for asmt in s.query(D.Assessment).filter(D.Assessment.section_id == sec.id).all():
                    mark_id = f"mk_bound_{pick.id}_{asmt.id}"
                    _ensure(
                        s, D.Mark, mark_id,
                        lambda mark_id=mark_id, asmt=asmt, pick=pick: D.Mark(
                            id=mark_id, tenant_id=TENANT, assessment_id=asmt.id,
                            student_id=pick.id,
                            score=round(asmt.max_marks * R.uniform(0.72, 0.96), 1),
                            entered_by="Faculty"
                        ),
                    )
            any_book = s.query(D.Book).first()
            if any_book:
                _ensure(
                    s, D.BookLoan, f"loan_bound_{pick.id}",
                    lambda any_book=any_book, pick=pick: D.BookLoan(
                        id=f"loan_bound_{pick.id}", tenant_id=TENANT, book_id=any_book.id,
                        borrower=pick.id, borrower_name=pick.name,
                        issued_on=date.today() - timedelta(days=6),
                        due_on=date.today() + timedelta(days=8), returned=False
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
                    payments[0].at = datetime.combine(date.today() - timedelta(days=42), datetime.min.time())
                else:
                    _ensure(
                        s, D.Payment, f"pay_bound_{pick.id}_1",
                        lambda pick=pick, invoice=invoice: D.Payment(
                            id=f"pay_bound_{pick.id}_1", tenant_id=TENANT,
                            invoice_id=invoice.id, student_id=pick.id,
                            amount=round(invoice.amount * 0.35), method="upi",
                            reference=f"TXN-DEMO-{pick.roll_no}-1",
                            at=datetime.combine(date.today() - timedelta(days=42), datetime.min.time())
                        ),
                    )
                _ensure(
                    s, D.Payment, f"pay_bound_{pick.id}_2",
                    lambda pick=pick, invoice=invoice: D.Payment(
                        id=f"pay_bound_{pick.id}_2", tenant_id=TENANT,
                        invoice_id=invoice.id, student_id=pick.id,
                        amount=round(invoice.amount * 0.15), method="netbanking",
                        reference=f"TXN-DEMO-{pick.roll_no}-2",
                        at=datetime.combine(date.today() - timedelta(days=11), datetime.min.time())
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
    students = s.query(D.Student).order_by(D.Student.roll_no).limit(12).all()
    subjects = [("MAT301", "Engineering Mathematics III"), ("CSE302", "Data Structures"), ("ECE303", "Digital Systems")]
    for index, student in enumerate(students):
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


def _seed_development_principal_coverage(s):
    """Fill missing development-only data coverage for Principal reporting.

    These rows are intentionally tagged ``development_sample`` where the
    model supports provenance.  They are idempotent and do not alter existing
    attendance or examination rows.  Replace them with imported records before
    any production deployment.
    """
    students = s.query(D.Student).order_by(D.Student.roll_no).all()
    enrolled_sections = {}
    for enrollment in s.query(D.Enrollment).filter(D.Enrollment.status == "enrolled").all():
        enrolled_sections.setdefault(enrollment.student_id, enrollment.section_id)
    department_sections = {}
    for section in s.query(D.Section).order_by(D.Section.id).all():
        department_sections.setdefault(section.dept_id, section.id)

    existing_attendance = {row[0] for row in s.query(D.AttendanceRecord.student_id).distinct().all()}
    today = date.today()
    for index, student in enumerate(students):
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
    Base.metadata.create_all(engine)
    s = SessionLocal()
    try:
        _seed_core_domain(s)
        _seed_reference_extensions(s)
        _seed_calendar_data(s)
        _seed_chairman_workflows(s)
        _bind_portal_accounts(s)
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
