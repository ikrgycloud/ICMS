import os
import sys
import unittest
from datetime import datetime

from fastapi.security import HTTPAuthorizationCredentials

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from authority import pwhash
from core import auth
from database import OFFICES, SessionLocal, scope_for
from models import AuditLog, AuthorityMembership, OrgScope, Person, Tenant, User
import main


class AuthenticationRoleMatrixTests(unittest.TestCase):
    """Every configured office receives a real, isolated authentication check."""

    def setUp(self):
        self.s = SessionLocal()
        self.stamp = datetime.utcnow().strftime("%H%M%S%f")
        self.tenant_id = f"auth_matrix_{self.stamp}"
        self.root_scope = f"scope_auth_root_{self.stamp}"
        self.university_scope = f"scope_auth_university_{self.stamp}"
        self.campus_scope = f"scope_auth_campus_{self.stamp}"
        self.password = "TemporaryAuth@123"
        self.user_ids = []
        self._create_fixture()

    def tearDown(self):
        self.s.rollback()
        self.s.query(AuditLog).filter(AuditLog.tenant_id == self.tenant_id).delete(synchronize_session=False)
        self.s.query(AuthorityMembership).filter(AuthorityMembership.user_id.in_(self.user_ids)).delete(synchronize_session=False)
        self.s.query(User).filter(User.id.in_(self.user_ids)).delete(synchronize_session=False)
        self.s.query(Person).filter(Person.tenant_id == self.tenant_id).delete(synchronize_session=False)
        self.s.query(OrgScope).filter(OrgScope.tenant_id == self.tenant_id).delete(synchronize_session=False)
        self.s.query(Tenant).filter(Tenant.id == self.tenant_id).delete(synchronize_session=False)
        self.s.commit()
        self.s.close()

    def _create_fixture(self):
        self.s.add(Tenant(id=self.tenant_id, institution_id="inst_icms", name=f"Auth Matrix {self.stamp}"))
        self.s.add_all([
            OrgScope(id=self.root_scope, tenant_id=self.tenant_id, level="global", name="Auth Matrix Root"),
            OrgScope(id=self.university_scope, tenant_id=self.tenant_id, level="university", name="Auth Matrix University", parent_id=self.root_scope),
            OrgScope(id=self.campus_scope, tenant_id=self.tenant_id, level="campus", name="Auth Matrix Campus", parent_id=self.university_scope),
        ])
        for item in OFFICES:
            office_n = item["n"]
            user_id = f"auth_user_{office_n}_{self.stamp}"
            person_id = f"auth_person_{office_n}_{self.stamp}"
            username = f"auth_{office_n}_{self.stamp[-8:]}"
            is_institution_authority = office_n in (1, 2)
            scope_id = self.root_scope if office_n == 1 else (self.university_scope if office_n == 2 else self.campus_scope)
            self.user_ids.append(user_id)
            self.s.add_all([
                Person(id=person_id, tenant_id=self.tenant_id, name=f"Auth Office {office_n}", email="", contact=""),
                User(id=user_id, tenant_id=self.tenant_id, person_id=person_id, username=username,
                     password_hash=pwhash(self.password), status="active", mfa_enabled=True,
                     office_n=office_n, role=item["internal_roles"][0],
                     scope_level=scope_for(office_n), scope_ref=scope_id),
                AuthorityMembership(
                    id=f"auth_membership_{office_n}_{self.stamp}", user_id=user_id,
                    institution_id="inst_icms", tenant_id=None if is_institution_authority else self.tenant_id,
                    org_scope_id=None if is_institution_authority else scope_id,
                    office_n=office_n, role_template_key=f"office_{office_n}",
                    jurisdiction_type="institution" if is_institution_authority else "scope", status="active",
                ),
            ])
        inactive_id = f"auth_inactive_{self.stamp}"
        self.user_ids.append(inactive_id)
        self.s.add_all([
            Person(id=f"auth_inactive_person_{self.stamp}", tenant_id=self.tenant_id, name="Inactive", email="", contact=""),
            User(id=inactive_id, tenant_id=self.tenant_id, person_id=f"auth_inactive_person_{self.stamp}",
                 username=f"auth_inactive_{self.stamp[-8:]}", password_hash=pwhash(self.password),
                 status="inactive", mfa_enabled=True, office_n=3, role="Campus Head",
                 scope_level="campus", scope_ref=self.campus_scope),
            AuthorityMembership(id=f"auth_inactive_membership_{self.stamp}", user_id=inactive_id,
                institution_id="inst_icms", tenant_id=self.tenant_id, org_scope_id=self.campus_scope,
                office_n=3, role_template_key="office_3", jurisdiction_type="scope", status="active"),
        ])
        self.s.commit()

    def test_every_office_login_has_authoritative_tenant_and_scope(self):
        for item in OFFICES:
            office_n = item["n"]
            username = f"auth_{office_n}_{self.stamp[-8:]}"
            response = main.login(main.LoginIn(username=username, password=self.password), s=self.s)
            self.assertEqual(response["auth_context"]["tenant_id"], self.tenant_id)
            self.assertEqual(response["auth_context"]["office_n"], office_n)
            context = auth(HTTPAuthorizationCredentials(scheme="Bearer", credentials=response["token"]))
            self.assertEqual(context["tenant_id"], self.tenant_id)
            self.assertEqual(context["office_n"], office_n)
            self.assertTrue(context["institution_id"])
            self.assertTrue(context["scope_ref"])

    def test_invalid_credentials_and_inactive_account_are_rejected(self):
        with self.assertRaises(Exception) as invalid_username:
            main.login(main.LoginIn(username="does-not-exist", password=self.password), s=self.s)
        self.assertEqual(getattr(invalid_username.exception, "status_code", None), 401)
        with self.assertRaises(Exception) as invalid_password:
            main.login(main.LoginIn(username=f"auth_3_{self.stamp[-8:]}", password="wrong-password"), s=self.s)
        self.assertEqual(getattr(invalid_password.exception, "status_code", None), 401)
        with self.assertRaises(Exception) as inactive:
            main.login(main.LoginIn(username=f"auth_inactive_{self.stamp[-8:]}", password=self.password), s=self.s)
        self.assertEqual(getattr(inactive.exception, "status_code", None), 403)


if __name__ == "__main__":
    unittest.main()
