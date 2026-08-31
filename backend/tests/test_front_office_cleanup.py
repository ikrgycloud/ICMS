import os
import sys
import unittest

from fastapi import HTTPException

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from capabilities import action_allowed_for_office, modules_for_office
from database import SessionLocal
from domain_api import gate, overview
from main import CheckIn, authz_check, get_notifications, non_front_office


FRONT_OFFICE_ROLES = [
    "Front Office Manager",
    "Reception Supervisor",
    "Receptionist",
    "Front Desk Executive",
    "Visitor Management Executive",
    "Telephone Operator",
    "Helpdesk Executive",
    "Concierge",
]


def context(office_n, role, scope_level="campus"):
    return {
        "sub": f"test-user-{office_n}",
        "office_n": office_n,
        "role": role,
        "scope_level": scope_level,
        "scope_ref": "Main Campus",
        "tenant_id": "tenant_icms",
        "auth_level": "password",
    }


class FrontOfficeCleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_all_front_office_roles_receive_only_dashboard_shell(self):
        for role in FRONT_OFFICE_ROLES:
            with self.subTest(role=role):
                self.assertEqual(modules_for_office(35), ["frontdesk_dashboard", "frontdesk_visitors", "frontdesk_appointments", "frontdesk_helpdesk", "frontdesk_calls", "frontdesk_directory", "frontdesk_delegations"])

    def test_removed_domain_modules_are_denied_for_every_front_office_role(self):
        removed = ["students", "calendar", "academic_calendar"]
        for role in FRONT_OFFICE_ROLES:
            for module in removed:
                with self.subTest(role=role, module=module):
                    decision, _ = gate(self.db, context(35, role), module, "view")
                    self.assertEqual(decision.outcome, "DENY")

    def test_front_office_student_mutations_are_no_longer_reserved(self):
        self.assertFalse(action_allowed_for_office("students", "add", 35))
        self.assertFalse(action_allowed_for_office("students", "edit", 35))

    def test_admissions_student_access_is_unchanged(self):
        self.assertTrue(action_allowed_for_office("students", "add", 15))
        self.assertTrue(action_allowed_for_office("students", "edit", 15))
        self.assertIn("students", modules_for_office(15))

    def test_representative_other_office_modules_are_unchanged(self):
        self.assertIn("students", modules_for_office(4))
        self.assertIn("workflows", modules_for_office(22))
        self.assertIn("academic_calendar", modules_for_office(14))
        self.assertIn("directory", modules_for_office(36))

    def test_generic_shared_screens_reject_front_office(self):
        for role in FRONT_OFFICE_ROLES:
            with self.subTest(role=role):
                with self.assertRaises(HTTPException) as caught:
                    non_front_office(context(35, role))
                self.assertEqual(caught.exception.status_code, 403)

    def test_non_front_office_passes_shared_screen_guard(self):
        ctx = context(15, "Admissions Manager")
        self.assertIs(non_front_office(ctx), ctx)

    def test_front_office_generic_overview_is_blocked(self):
        with self.assertRaises(HTTPException) as caught:
            overview(context(35, FRONT_OFFICE_ROLES[0]), self.db)
        self.assertEqual(caught.exception.status_code, 403)

    def test_front_office_unrelated_notifications_are_hidden(self):
        result = get_notifications(context(35, FRONT_OFFICE_ROLES[0]), self.db)
        self.assertEqual(result, {"notifications": [], "unread": 0})

    def test_authority_check_does_not_advertise_removed_resources(self):
        for resource in ("students", "calendar", "workflows", "directory", "audit"):
            with self.subTest(resource=resource):
                result = authz_check(
                    CheckIn(action="view", resource=resource),
                    context(35, FRONT_OFFICE_ROLES[0]),
                    self.db,
                )
                self.assertEqual(result["outcome"], "DENY")
                self.assertEqual(result["rbac_authority"], "Not Allowed")


if __name__ == "__main__":
    unittest.main()
