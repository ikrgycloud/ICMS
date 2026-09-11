import os
import sys
import unittest
from datetime import datetime

from fastapi import HTTPException

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from authority import pwhash
from database import SessionLocal
from models import (Approval, AuditLog, AuthorityMembership, Notification, OrgScope,
                    Person, Tenant, User, WorkflowInstance)
import domain_api
import domain_models as D
import main


class ExaminationLifecycleTests(unittest.TestCase):
    """Direct API coverage for the scoped Faculty -> HOD -> Controller flow."""

    def setUp(self):
        self.s = SessionLocal()
        self.stamp = datetime.utcnow().strftime("%H%M%S%f")
        self.tenant = f"exam_lifecycle_{self.stamp}"
        self.scope = f"exam_scope_{self.stamp}"
        self.other_scope = f"exam_other_scope_{self.stamp}"
        self.ids = {}
        self._fixture()

    def tearDown(self):
        tenant = self.tenant
        self.s.rollback()
        workflow_ids = [row[0] for row in self.s.query(WorkflowInstance.id).filter(WorkflowInstance.tenant_id == tenant).all()]
        self.s.query(Notification).filter(Notification.tenant_id == tenant).delete(synchronize_session=False)
        self.s.query(AuditLog).filter(AuditLog.tenant_id == tenant).delete(synchronize_session=False)
        if workflow_ids:
            self.s.query(Approval).filter(Approval.workflow_id.in_(workflow_ids)).delete(synchronize_session=False)
        for model in (D.StudentSubjectResult, D.ResultSheet, D.Mark, D.Assessment,
                      D.Enrollment, D.Section, D.Student, D.Course, D.Program, D.Department,
                      D.StaffMember):
            self.s.query(model).filter(model.tenant_id == tenant).delete(synchronize_session=False)
        self.s.query(WorkflowInstance).filter(WorkflowInstance.tenant_id == tenant).delete(synchronize_session=False)
        self.s.query(AuthorityMembership).filter(AuthorityMembership.tenant_id == tenant).delete(synchronize_session=False)
        self.s.query(User).filter(User.tenant_id == tenant).delete(synchronize_session=False)
        self.s.query(Person).filter(Person.tenant_id == tenant).delete(synchronize_session=False)
        self.s.query(OrgScope).filter(OrgScope.tenant_id == tenant).delete(synchronize_session=False)
        self.s.query(Tenant).filter(Tenant.id == tenant).delete(synchronize_session=False)
        self.s.commit()
        self.s.close()

    def _add_user(self, key, office_n, role):
        person_id, user_id = f"exam_person_{key}_{self.stamp}", f"exam_user_{key}_{self.stamp}"
        self.s.add_all([
            Person(id=person_id, tenant_id=self.tenant, name=role, email=f"{key}@exam.test", contact=""),
            User(id=user_id, tenant_id=self.tenant, person_id=person_id, username=user_id,
                 password_hash=pwhash("Test@1234"), status="active", mfa_enabled=True,
                 office_n=office_n, role=role, scope_level="campus", scope_ref=self.scope),
        ])
        self.s.flush()
        self.s.add(AuthorityMembership(id=f"exam_membership_{key}_{self.stamp}", user_id=user_id,
                   institution_id="inst_icms", tenant_id=self.tenant, org_scope_id=self.scope,
                   office_n=office_n, role_template_key=f"office_{office_n}",
                   jurisdiction_type="scope", status="active"))
        self.ids[key] = (person_id, user_id)

    def _fixture(self):
        self.s.add_all([
            Tenant(id=self.tenant, institution_id="inst_icms", name="Exam lifecycle tenant"),
            OrgScope(id=self.scope, tenant_id=self.tenant, level="campus", name="Exam lifecycle campus"),
            OrgScope(id=self.other_scope, tenant_id=self.tenant, level="campus", name="Other exam campus"),
        ])
        self.s.flush()
        self._add_user("faculty", 11, "Faculty")
        self._add_user("hod", 10, "Head of Department")
        self._add_user("controller", 16, "Examination Controller")
        student_person, student_user = f"exam_person_student_{self.stamp}", f"exam_user_student_{self.stamp}"
        self.s.add_all([
            Person(id=student_person, tenant_id=self.tenant, name="Exam Student", email="student@exam.test", contact=""),
            User(id=student_user, tenant_id=self.tenant, person_id=student_person, username=student_user,
                 password_hash=pwhash("Test@1234"), status="active", mfa_enabled=True,
                 office_n=35, role="Student", scope_level="campus", scope_ref=self.scope),
        ])
        self.ids["student_user"] = student_user
        self.s.flush()
        department, program, course, section = (f"exam_dept_{self.stamp}", f"exam_program_{self.stamp}",
                                                f"exam_course_{self.stamp}", f"exam_section_{self.stamp}")
        self.s.add(D.Department(id=department, tenant_id=self.tenant, code="EXM", name="Examination", campus="Exam lifecycle campus"))
        self.s.flush()
        self.s.add(D.Program(id=program, tenant_id=self.tenant, dept_id=department, code="EXM-UG", name="Exam UG", level="UG"))
        self.s.flush()
        self.s.add(D.Course(id=course, tenant_id=self.tenant, dept_id=department, program_id=program, code="EXM101", title="Lifecycle Course", semester=1))
        self.s.flush()
        faculty_staff, hod_staff = f"exam_staff_faculty_{self.stamp}", f"exam_staff_hod_{self.stamp}"
        other_section, other_assessment = f"exam_other_section_{self.stamp}", f"exam_other_assessment_{self.stamp}"
        self.s.add_all([
            D.StaffMember(id=faculty_staff, tenant_id=self.tenant, emp_id="EXM-F", name="Faculty", designation="Professor", user_id=self.ids["faculty"][1], dept_id=department, campus="Exam lifecycle campus", campus_scope_id=self.scope),
            D.StaffMember(id=hod_staff, tenant_id=self.tenant, emp_id="EXM-H", name="HOD", designation="HOD", user_id=self.ids["hod"][1], dept_id=department, campus="Exam lifecycle campus", campus_scope_id=self.scope),
            D.Section(id=section, tenant_id=self.tenant, campus_scope_id=self.scope, course_id=course, dept_id=department, term="2026-Odd", section_code="A", faculty_person_id=faculty_staff),
            D.Section(id=other_section, tenant_id=self.tenant, campus_scope_id=self.other_scope, course_id=course, dept_id=department, term="2026-Odd", section_code="B"),
        ])
        self.s.flush()
        student = f"exam_student_{self.stamp}"
        assessment = f"exam_assessment_{self.stamp}"
        # PostgreSQL enforces the Student -> Enrollment foreign key immediately.
        # Flush the student parent before constructing the enrolment fixture.
        self.s.add(D.Student(id=student, tenant_id=self.tenant, roll_no="EXM-001", name="Exam Student",
                             user_id=self.ids["student_user"], dept_id=department, program_id=program,
                             campus="Exam lifecycle campus", campus_scope_id=self.scope, batch="2026", semester=1))
        self.s.flush()
        self.s.add_all([
            D.Enrollment(id=f"exam_enrollment_{self.stamp}", tenant_id=self.tenant, student_id=student, section_id=section),
            D.Assessment(id=assessment, tenant_id=self.tenant, section_id=section, name="Midterm", max_marks=100, published=True, status="published", marks_state="draft"),
            D.Assessment(id=other_assessment, tenant_id=self.tenant, section_id=other_section, name="Other campus midterm", max_marks=100, published=True, status="published", marks_state="draft"),
        ])
        self.s.commit()
        self.ids.update({"department": department, "section": section, "student": student,
                         "assessment": assessment, "other_assessment": other_assessment})

    def _ctx(self, key, office_n):
        return {"sub": self.ids[key][1], "tenant_id": self.tenant, "institution_id": "inst_icms",
                "scope_level": "campus", "scope_ref": self.scope, "office_n": office_n, "auth_level": "mfa"}

    def test_draft_submit_return_resubmit_verify_approve_publish(self):
        faculty, hod, controller = self._ctx("faculty", 11), self._ctx("hod", 10), self._ctx("controller", 16)
        assessment_id, student_id, section_id = self.ids["assessment"], self.ids["student"], self.ids["section"]

        domain_api.enter_marks(domain_api.EnterMarksIn(assessment_id=assessment_id, marks={student_id: 76}), ctx=faculty, s=self.s)
        submitted = domain_api.submit_marks(domain_api.SubmitMarksIn(assessment_id=assessment_id), ctx=faculty, s=self.s)
        workflow = self.s.get(WorkflowInstance, submitted["workflow_id"])
        self.assertEqual((workflow.current_owner_user_id, workflow.current_stage), (hod["sub"], 1))
        self.assertEqual(self.s.get(D.Assessment, assessment_id).marks_state, "submitted")
        self.assertTrue(self.s.query(Notification).filter(Notification.user_id == hod["sub"], Notification.tenant_id == self.tenant).count())

        main.decide_workflow(main.DecideWF(workflow_id=workflow.id, action="return", reason="Please check the score."), ctx=hod, s=self.s)
        self.s.expire_all(); workflow = self.s.get(WorkflowInstance, workflow.id)
        self.assertEqual((workflow.state, workflow.current_owner_user_id, self.s.get(D.Assessment, assessment_id).marks_state), ("returned", faculty["sub"], "returned"))
        with self.assertRaises(HTTPException) as blocked_controller:
            main.decide_workflow(main.DecideWF(workflow_id=workflow.id, action="approve", reason=""), ctx=controller, s=self.s)
        self.assertEqual(blocked_controller.exception.status_code, 403)

        domain_api.enter_marks(domain_api.EnterMarksIn(assessment_id=assessment_id, marks={student_id: 78}), ctx=faculty, s=self.s)
        domain_api.submit_marks(domain_api.SubmitMarksIn(assessment_id=assessment_id), ctx=faculty, s=self.s)
        self.s.expire_all(); workflow = self.s.get(WorkflowInstance, workflow.id)
        main.decide_workflow(main.DecideWF(workflow_id=workflow.id, action="approve", reason="Verified"), ctx=hod, s=self.s)
        self.s.expire_all(); workflow = self.s.get(WorkflowInstance, workflow.id)
        self.assertEqual((workflow.current_owner_user_id, workflow.current_stage, self.s.get(D.Assessment, assessment_id).marks_state), (controller["sub"], 2, "verified"))
        main.decide_workflow(main.DecideWF(workflow_id=workflow.id, action="approve", reason="Approved for publication"), ctx=controller, s=self.s)
        self.assertEqual(self.s.get(D.Assessment, assessment_id).marks_state, "approved_for_publication")
        published = domain_api.publish_result(domain_api.PublishResultIn(section_id=section_id), ctx=controller, s=self.s)
        self.assertEqual((published["status"], self.s.get(D.Assessment, assessment_id).marks_state), ("published", "published"))
        self.assertEqual(self.s.query(D.StudentSubjectResult).filter(
            D.StudentSubjectResult.tenant_id == self.tenant,
            D.StudentSubjectResult.student_id == student_id,
        ).count(), 1)
        self.assertEqual(self.s.query(Notification).filter(
            Notification.tenant_id == self.tenant,
            Notification.user_id == self.ids["student_user"],
            Notification.title == "Examination result published",
        ).count(), 1)
        actions = {row.action for row in self.s.query(AuditLog).filter(AuditLog.tenant_id == self.tenant).all()}
        self.assertTrue({"marks.draft_save", "marks.submit", "marks.return", "marks.approve", "result.publish"}.issubset(actions))

    def test_invalid_range_and_cross_stage_edits_are_rejected(self):
        faculty = self._ctx("faculty", 11)
        with self.assertRaises(HTTPException) as range_error:
            domain_api.enter_marks(domain_api.EnterMarksIn(assessment_id=self.ids["assessment"], marks={self.ids["student"]: 101}), ctx=faculty, s=self.s)
        self.assertEqual(range_error.exception.status_code, 422)
        with self.assertRaises(HTTPException) as other_campus:
            domain_api.enter_marks(domain_api.EnterMarksIn(
                assessment_id=self.ids["other_assessment"], marks={self.ids["student"]: 75}),
                ctx=faculty, s=self.s)
        self.assertEqual(other_campus.exception.status_code, 404)

        # A hostile direct request cannot select a foreign tenant's assessment,
        # even if the caller knows its identifier.
        foreign_assessment = f"exam_foreign_assessment_{self.stamp}"
        self.s.add(D.Assessment(id=foreign_assessment, tenant_id=f"foreign_{self.stamp}",
                                section_id=self.ids["section"], name="Foreign", max_marks=100,
                                published=True, status="published", marks_state="draft"))
        self.s.commit()
        try:
            with self.assertRaises(HTTPException) as other_tenant:
                domain_api.enter_marks(domain_api.EnterMarksIn(
                    assessment_id=foreign_assessment, marks={self.ids["student"]: 75}),
                    ctx=faculty, s=self.s)
            # The API intentionally treats an unknown authenticated-tenant ID
            # as invalid input.  It never loads or mutates the foreign row.
            self.assertEqual(other_tenant.exception.status_code, 400)
        finally:
            self.s.query(D.Assessment).filter(D.Assessment.id == foreign_assessment).delete(synchronize_session=False)
            self.s.commit()


if __name__ == "__main__":
    unittest.main()
