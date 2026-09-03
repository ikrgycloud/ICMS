import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import domain_models as D
from authority import pwhash
from domain_seed import _seed_student_portal_accounts
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


if __name__ == "__main__":
    unittest.main()
