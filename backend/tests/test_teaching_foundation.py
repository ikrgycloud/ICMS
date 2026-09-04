import json
import os
import sys
import unittest
from datetime import date, datetime, timedelta
from urllib import error, request

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal, TENANT
from models import User
import domain_models as D
from teaching import class_session_for_timetable, faculty_owns_section


class TeachingFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.professor_token = cls._login("professor")
        cls.hod_token = cls._login("hod")
        cls.lecturer_token = cls._login("lecturer")
        user = cls.db.query(User).filter(User.username == "professor").first()
        cls.professor = cls.db.query(D.StaffMember).filter(D.StaffMember.user_id == user.id).first()
        cls.allocation = (cls.db.query(D.TeachingAllocation)
                          .filter(D.TeachingAllocation.faculty_id == cls.professor.id,
                                  D.TeachingAllocation.status == "active")
                          .first())
        if not cls.allocation:
            raise AssertionError("Professor seed data has no active teaching allocation")
        cls.section = cls.db.query(D.Section).get(cls.allocation.section_id)
        cls.roster = (cls.db.query(D.Enrollment)
                      .filter(D.Enrollment.section_id == cls.section.id,
                              D.Enrollment.status == "enrolled").all())
        if not cls.roster:
            raise AssertionError("Professor seed allocation has no enrolled students")
        now = datetime.utcnow()
        cls.session_id = "test_phase1_session"
        cls.db.query(D.AttendanceRecord).filter(D.AttendanceRecord.class_session_id == cls.session_id).delete(synchronize_session=False)
        cls.db.query(D.ClassSession).filter(D.ClassSession.id == cls.session_id).delete(synchronize_session=False)
        cls.db.add(D.ClassSession(
            id=cls.session_id, tenant_id=TENANT, allocation_id=cls.allocation.id,
            section_id=cls.section.id, faculty_id=cls.professor.id, session_date=date.today(),
            scheduled_start=now - timedelta(minutes=5), scheduled_end=now + timedelta(minutes=30),
            room=cls.section.room, status="scheduled",
        ))
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.query(D.AttendanceRecord).filter(D.AttendanceRecord.class_session_id == cls.session_id).delete(synchronize_session=False)
        cls.db.query(D.ClassSession).filter(D.ClassSession.id == cls.session_id).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()

    @classmethod
    def _login(cls, username):
        status, payload = cls._request("POST", "/api/auth/login", body={"username": username, "password": "demo123"})
        if status != 200:
            raise AssertionError(f"Login failed for {username}: {payload}")
        return payload["token"]

    @classmethod
    def _request(cls, method, path, token=None, body=None):
        raw = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        base_url = os.environ.get("ICMS_TEST_API_URL", "http://127.0.0.1:8000")
        req = request.Request(f"{base_url}{path}", data=raw, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=15) as response:
                payload = response.read().decode("utf-8")
                return response.getcode(), json.loads(payload) if payload else {}
        except error.HTTPError as exc:
            payload = exc.read().decode("utf-8")
            return exc.code, json.loads(payload) if payload else {}

    def _attendance_body(self, ids=None):
        ids = ids or [row.student_id for row in self.roster]
        return {"section_id": self.section.id, "class_session_id": self.session_id,
                "present_ids": ids, "absent_ids": [], "on_date": date.today().isoformat()}

    def test_professor_demo_context_resolves_to_existing_aarav_account(self):
        status, payload = self._request(
            "POST", "/api/auth/login",
            body={"username": "professor", "password": "demo123", "demo_context": "professor"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["user"]["id"], "user_demo_aarav_kulkarni")
        self.assertEqual(payload["user"]["username"], "aarav_kulkarni")
        self.assertEqual(payload["user"]["name"], "Aarav Kulkarni")

    def test_faculty_digital_id_is_authenticated_and_staff_scoped(self):
        status, login = self._request(
            "POST", "/api/auth/login",
            body={"username": "professor", "password": "demo123", "demo_context": "professor"},
        )
        self.assertEqual(status, 200)
        status, payload = self._request("GET", "/api/portal/faculty/digital-id", login["token"])
        self.assertEqual(status, 200)
        card = payload["digital_id"]
        self.assertEqual(card["full_name"], "Aarav Kulkarni")
        self.assertEqual(card["employee_id"], "FAC0001")
        self.assertEqual(card["designation"], "Professor")
        self.assertTrue(card["verification_payload"].startswith("ICMS:FAC:"))

    def test_active_allocation_preserves_legacy_section_owner(self):
        self.assertEqual(self.section.faculty_person_id, self.professor.id)
        status, payload = self._request("GET", "/api/academics/teaching-allocations", self.professor_token)
        self.assertEqual(status, 200, payload)
        self.assertTrue(any(row["id"] == self.allocation.id for row in payload["allocations"]))

    def test_allocation_creation_is_hod_only(self):
        body = {"faculty_id": self.professor.id, "course_id": self.section.course_id, "section_id": self.section.id}
        status, _ = self._request("POST", "/api/academics/teaching-allocations", self.professor_token, body)
        self.assertEqual(status, 403)

    def test_hod_can_update_active_allocation_and_sync_owner(self):
        hod_user = self.db.query(User).filter(User.username == "hod").first()
        hod = self.db.query(D.StaffMember).filter(D.StaffMember.user_id == hod_user.id).first()
        allocation = (self.db.query(D.TeachingAllocation)
                      .join(D.Section, D.TeachingAllocation.section_id == D.Section.id)
                      .filter(D.Section.dept_id == hod.dept_id, D.TeachingAllocation.status == "active")
                      .first())
        if not allocation:
            self.skipTest("Seed data has no HOD-scoped active allocation")
        replacements = (self.db.query(D.StaffMember)
                        .filter(D.StaffMember.dept_id == hod.dept_id,
                                D.StaffMember.status == "active",
                                D.StaffMember.id != allocation.faculty_id,
                                D.StaffMember.user_id.isnot(None))
                        .all())
        if not replacements:
            self.skipTest("Seed data has no second eligible HOD-scoped faculty member")
        original_faculty_id = allocation.faculty_id
        section = self.db.query(D.Section).get(allocation.section_id)

        def body(faculty_id):
            return {
                "faculty_id": faculty_id, "allocation_type": allocation.allocation_type, "lecture_hours": allocation.lecture_hours,
                "lab_hours": allocation.lab_hours, "tutorial_hours": allocation.tutorial_hours,
                "workload_units": allocation.workload_units,
                "effective_from": allocation.effective_from.isoformat() if allocation.effective_from else "",
                "effective_to": allocation.effective_to.isoformat() if allocation.effective_to else "",
                "is_coordinator": allocation.is_coordinator,
            }

        disabled_slot_ids = []
        try:
            replacement = None
            for candidate in replacements:
                status, payload = self._request("PUT", f"/api/academics/teaching-allocations/{allocation.id}", self.hod_token, body(candidate.id))
                if status == 200:
                    replacement = candidate
                    break
                self.assertEqual(status, 409, payload)
            if not replacement:
                # The compact demo timetable can make every eligible faculty
                # member overlap. Disable only this fixture's slots to verify
                # ownership transfer; the next test covers conflict rejection.
                target_slots = self.db.query(D.TimetableEntry).filter(
                    D.TimetableEntry.section_id == allocation.section_id,
                    D.TimetableEntry.status == "active",
                ).all()
                disabled_slot_ids = [entry.id for entry in target_slots]
                for entry in target_slots:
                    entry.status = "inactive"
                self.db.commit()
                replacement = replacements[0]
                status, payload = self._request("PUT", f"/api/academics/teaching-allocations/{allocation.id}", self.hod_token, body(replacement.id))
                self.assertEqual(status, 200, payload)
            self.db.expire_all()
            self.assertEqual(self.db.query(D.Section).get(section.id).faculty_person_id, replacement.id)
            self.assertTrue(faculty_owns_section(self.db, replacement.id, section.id))
            self.assertFalse(faculty_owns_section(self.db, original_faculty_id, section.id))
        finally:
            self._request("PUT", f"/api/academics/teaching-allocations/{allocation.id}", self.hod_token, body(original_faculty_id))
            if disabled_slot_ids:
                self.db.query(D.TimetableEntry).filter(D.TimetableEntry.id.in_(disabled_slot_ids)).update(
                    {"status": "active"}, synchronize_session=False)
            self.db.commit()

    def test_active_allocation_update_rejects_timetable_conflict(self):
        hod_user = self.db.query(User).filter(User.username == "hod").first()
        hod = self.db.query(D.StaffMember).filter(D.StaffMember.user_id == hod_user.id).first()
        allocation = (self.db.query(D.TeachingAllocation)
                      .join(D.Section, D.TeachingAllocation.section_id == D.Section.id)
                      .filter(D.Section.dept_id == hod.dept_id, D.TeachingAllocation.status == "active")
                      .first())
        slot = (self.db.query(D.TimetableEntry)
                .filter(D.TimetableEntry.section_id == allocation.section_id, D.TimetableEntry.status == "active")
                .first()) if allocation else None
        conflict_allocation = (self.db.query(D.TeachingAllocation)
                               .join(D.StaffMember, D.TeachingAllocation.faculty_id == D.StaffMember.id)
                               .filter(D.TeachingAllocation.status == "active",
                                       D.TeachingAllocation.section_id != allocation.section_id,
                                       D.TeachingAllocation.faculty_id != allocation.faculty_id,
                                       D.StaffMember.dept_id == hod.dept_id)
                               .first()) if allocation else None
        if not allocation or not slot or not conflict_allocation:
            self.skipTest("Seed data cannot create an active allocation conflict fixture")
        fixture_id = f"test_phase1_conflict_{allocation.id}"
        self.db.query(D.TimetableEntry).filter(D.TimetableEntry.id == fixture_id).delete(synchronize_session=False)
        self.db.add(D.TimetableEntry(
            id=fixture_id, tenant_id=TENANT, section_id=conflict_allocation.section_id,
            day_of_week=slot.day_of_week, start_time=slot.start_time, end_time=slot.end_time,
            room="Test conflict room", status="active",
        ))
        self.db.commit()
        body = {
            "faculty_id": conflict_allocation.faculty_id, "allocation_type": allocation.allocation_type,
            "lecture_hours": allocation.lecture_hours,
            "lab_hours": allocation.lab_hours, "tutorial_hours": allocation.tutorial_hours,
            "workload_units": allocation.workload_units,
            "effective_from": allocation.effective_from.isoformat() if allocation.effective_from else "",
            "effective_to": allocation.effective_to.isoformat() if allocation.effective_to else "",
            "is_coordinator": allocation.is_coordinator,
        }
        try:
            status, _ = self._request("PUT", f"/api/academics/teaching-allocations/{allocation.id}", self.hod_token, body)
            self.assertEqual(status, 409)
        finally:
            self.db.query(D.TimetableEntry).filter(D.TimetableEntry.id == fixture_id).delete(synchronize_session=False)
            self.db.commit()

    def test_update_schema_preserves_zero_hours_and_false_coordinator_flag(self):
        hod_user = self.db.query(User).filter(User.username == "hod").first()
        hod = self.db.query(D.StaffMember).filter(D.StaffMember.user_id == hod_user.id).first()
        allocation = (self.db.query(D.TeachingAllocation)
                      .join(D.Section, D.TeachingAllocation.section_id == D.Section.id)
                      .filter(D.Section.dept_id == hod.dept_id, D.TeachingAllocation.status == "active")
                      .first())
        if not allocation:
            self.skipTest("Seed data has no HOD-scoped active allocation")
        original = {
            "faculty_id": allocation.faculty_id, "allocation_type": allocation.allocation_type,
            "lecture_hours": allocation.lecture_hours, "lab_hours": allocation.lab_hours,
            "tutorial_hours": allocation.tutorial_hours, "workload_units": allocation.workload_units,
            "effective_from": allocation.effective_from.isoformat() if allocation.effective_from else "",
            "effective_to": allocation.effective_to.isoformat() if allocation.effective_to else "",
            "is_coordinator": allocation.is_coordinator,
        }
        edited = {**original, "lab_hours": 0, "tutorial_hours": 0, "is_coordinator": False}
        try:
            status, payload = self._request("PUT", f"/api/academics/teaching-allocations/{allocation.id}", self.hod_token, edited)
            self.assertEqual(status, 200, payload)
            self.assertEqual(payload["allocation"]["lab_hours"], 0)
            self.assertEqual(payload["allocation"]["tutorial_hours"], 0)
            self.assertFalse(payload["allocation"]["is_coordinator"])
        finally:
            self._request("PUT", f"/api/academics/teaching-allocations/{allocation.id}", self.hod_token, original)

    def test_duplicate_timetable_session_generation_returns_same_record(self):
        entry = self.db.query(D.TimetableEntry).filter(D.TimetableEntry.section_id == self.section.id, D.TimetableEntry.status == "active").first()
        if not entry:
            self.skipTest("Seed section has no timetable entry")
        first = class_session_for_timetable(self.db, entry, date.today(), self.allocation)
        second = class_session_for_timetable(self.db, entry, date.today(), self.allocation)
        self.assertEqual(first.id, second.id)
        self.db.rollback()

    def test_session_checkin_and_attendance_guards(self):
        status, _ = self._request("POST", f"/api/attendance/mark", self.professor_token, self._attendance_body())
        self.assertEqual(status, 409)
        status, _ = self._request("POST", f"/api/faculty/class-sessions/{self.session_id}/check-in", self.lecturer_token)
        self.assertEqual(status, 403)
        status, payload = self._request("POST", f"/api/faculty/class-sessions/{self.session_id}/check-in", self.professor_token)
        self.assertEqual(status, 200, payload)
        outsider = self.db.query(D.Student).filter(~D.Student.id.in_([row.student_id for row in self.roster])).first()
        status, _ = self._request("POST", "/api/attendance/mark", self.professor_token, self._attendance_body([outsider.id]))
        self.assertEqual(status, 422)
        status, payload = self._request("POST", "/api/attendance/mark", self.professor_token, self._attendance_body())
        self.assertEqual(status, 200, payload)
        status, payload = self._request("POST", f"/api/faculty/class-sessions/{self.session_id}/finalize-attendance", self.professor_token)
        self.assertEqual(status, 200, payload)
        status, _ = self._request("POST", "/api/attendance/mark", self.professor_token, self._attendance_body())
        self.assertEqual(status, 409)


if __name__ == "__main__":
    unittest.main()


