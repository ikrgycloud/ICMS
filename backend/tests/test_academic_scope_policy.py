import unittest
from unittest.mock import Mock
from fastapi import HTTPException
from academic_scope import authorize_object


class AcademicScopePolicyTests(unittest.TestCase):
    def test_tenant_mismatch_is_denied(self):
        obj = Mock(tenant_id="tenant-b", dept_id="d1")
        session = Mock()
        session.query.return_value.filter.return_value.first.return_value = Mock(dept_id="d1")
        with self.assertRaises(HTTPException) as error:
            authorize_object({"sub": "u", "tenant_id": "tenant-a", "office_n": 10}, session, obj)
        self.assertEqual(error.exception.status_code, 403)

    def test_unrelated_office_is_denied(self):
        obj = Mock(tenant_id="tenant-a", dept_id="d1")
        session = Mock()
        with self.assertRaises(HTTPException):
            authorize_object({"sub": "u", "tenant_id": "tenant-a", "office_n": 36}, session, obj)

    def test_hod_cannot_access_another_department(self):
        obj = Mock(tenant_id="tenant-a", dept_id="dept-b")
        session = Mock()
        session.query.return_value.filter.return_value.first.return_value = Mock(dept_id="dept-a")
        with self.assertRaises(HTTPException) as error:
            authorize_object({"sub": "u", "tenant_id": "tenant-a", "office_n": 10}, session, obj)
        self.assertEqual(error.exception.status_code, 403)

    def test_faculty_section_scope_fails_closed(self):
        obj = Mock(tenant_id="tenant-a", dept_id="dept-a", section_id="section-b")
        session = Mock()
        session.query.return_value.filter.return_value.first.return_value = Mock(dept_id="dept-a")
        with self.assertRaises(HTTPException) as error:
            authorize_object({"sub": "u", "tenant_id": "tenant-a", "office_n": 11}, session, obj)
        self.assertEqual(error.exception.status_code, 403)

    def test_scoped_actor_without_department_is_denied(self):
        obj = Mock(tenant_id="tenant-a", dept_id="dept-a")
        session = Mock()
        session.query.return_value.filter.return_value.first.return_value = None
        session.get.return_value = None
        with self.assertRaises(HTTPException) as error:
            authorize_object({"sub": "u", "tenant_id": "tenant-a", "office_n": 10}, session, obj)
        self.assertEqual(error.exception.status_code, 403)

    def test_coordinator_without_assignment_is_denied(self):
        obj = Mock(tenant_id="tenant-a", dept_id="dept-a", school_id="school-a")
        session = Mock()
        session.query.return_value.filter.return_value.first.return_value = None
        session.get.side_effect = lambda model, key: Mock(id="school-a") if key == "school-a" else None
        with self.assertRaises(HTTPException) as error:
            authorize_object({"sub": "u", "tenant_id": "tenant-a", "office_n": 17, "scope_ref": "school-a"}, session, obj)
        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
