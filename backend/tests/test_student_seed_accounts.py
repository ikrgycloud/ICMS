import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import domain_models as D
from authority import pwhash
from domain_seed import _seed_fee_cohort_students, _seed_student_portal_accounts
from main import LoginIn, login
from models import Base, Person, Role, User, UserRole


class StudentSeedAccountTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine, autoflush=False)()
        self.session.add(Role(id="role_36_0", tenant_id="t_main", office_n=36,
                              name="Student", category="individual"))
        self.session.add(Person(id="person_36", tenant_id="t_main", name="Demo Student"))
        self.session.add(User(id="user_36", tenant_id="t_main", person_id="person_36",
                              username="student", password_hash=pwhash("demo123"), office_n=36,
                              role="Student", scope_level="individual", scope_ref="stu_demo"))
        self.session.add_all([
            D.Student(id="stu_demo", tenant_id="t_main", roll_no="23CSE001",
                      name="Ananya Rao", user_id="user_36"),
            D.Student(id="stu_other", tenant_id="t_main", roll_no="23CSE002",
                      name="Other Student", email="other@icms.edu"),
        ])
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_creates_roll_number_login_and_preserves_shared_login(self):
        _seed_student_portal_accounts(self.session)

        other = self.session.get(D.Student, "stu_other")
        account = self.session.get(User, other.user_id)
        self.assertEqual(account.username, "23cse002")
        self.assertEqual(account.password_hash, pwhash("demo123"))
        self.assertEqual(account.scope_ref, other.id)
        self.assertEqual(self.session.get(D.Student, "stu_demo").user_id, "user_36")
        self.assertIsNotNone(self.session.get(UserRole, "ur_student_stu_other"))

        _seed_student_portal_accounts(self.session)
        self.assertEqual(self.session.query(User).count(), 2)
        self.assertEqual(self.session.query(UserRole).count(), 1)

    def test_shared_student_login_works_without_roll_number_alias(self):
        result = login(LoginIn(username="student", password="demo123"), s=self.session)
        self.assertIn("token", result)
        self.assertEqual(result["user"]["username"], "student")

    def test_roll_number_login_creates_missing_alias_for_database_student(self):
        result = login(LoginIn(username="23cse002", password="demo123"), s=self.session)
        self.assertIn("token", result)
        self.assertEqual(result["user"]["username"], "23cse002")
        self.assertIsNotNone(self.session.query(User).filter(User.username.ilike("23cse002")).first())

    def test_fee_demo_cohorts_cover_all_semesters_and_student_types_with_logins(self):
        self.session.add(D.Department(id="dept_cse", tenant_id="t_main", code="CSE", name="Computing"))
        self.session.add(D.Program(id="prog_cse_btech", tenant_id="t_main", dept_id="dept_cse",
                                   code="BTECH-CSE", name="BTECH Computing", level="UG", duration_years=4))
        self.session.commit()

        _seed_fee_cohort_students(self.session)
        _seed_student_portal_accounts(self.session)

        students = self.session.query(D.Student).filter(
            D.Student.program_id == "prog_cse_btech",
            D.Student.id.like("student_fee_demo_%"),
        ).all()
        self.assertEqual(len(students), 80)
        self.assertEqual({(student.batch, student.semester, student.student_type) for student in students},
                         {(batch, semester, kind) for batch in ("2023", "2024", "2025", "2026", "2027")
                          for semester in range(1, 9) for kind in ("Regular", "Management")})
        for student in students:
            user = self.session.get(User, student.user_id)
            self.assertEqual(user.username, student.roll_no.lower())
            self.assertEqual(user.password_hash, pwhash("demo123"))

    def test_payroll_employee_code_variants_can_login_with_normalized_employee_id(self):
        employee = User(id="user_payroll_001", tenant_id="t_main", person_id="person_001",
                        username="acct_001", password_hash=pwhash("demo123"), office_n=23,
                        role="Accountant", status="active", scope_level="campus", scope_ref="Main Campus")
        self.session.add(employee)
        self.session.commit()

        result = login(LoginIn(username="ACCT-001", password="demo123"), s=self.session)
        self.assertIn("token", result)
        self.assertEqual(result["user"]["username"], "acct_001")


if __name__ == "__main__":
    unittest.main()
