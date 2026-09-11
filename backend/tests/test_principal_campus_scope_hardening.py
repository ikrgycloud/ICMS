import os
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal, TENANT
from models import (AuditLog, AuthorityMembership, OrgScope, Person, Tenant, User,
                    WorkflowInstance, WorkflowProfile)
import domain_api
import domain_models as D
import main
from authority import pwhash


class PrincipalCampusScopeHardeningTests(unittest.TestCase):
    """Regression coverage for authenticated tenant + canonical campus scope."""

    def setUp(self):
        self.s = SessionLocal()
        self.stamp = datetime.utcnow().strftime("%H%M%S%f")
        self.tenants = [f"hard_a_{self.stamp}", f"hard_b_{self.stamp}", f"hard_empty_{self.stamp}"]
        self.scope_a = f"scope_hard_a_{self.stamp}"
        self.scope_a_other = f"scope_hard_a_other_{self.stamp}"
        self.scope_b = f"scope_hard_b_{self.stamp}"
        self.scope_empty = f"scope_hard_empty_{self.stamp}"
        self.users = {}
        self._add_fixture_identities()

    def tearDown(self):
        self.s.rollback()
        tenant_ids = self.tenants
        workflow_ids = [row[0] for row in self.s.query(WorkflowInstance.id).filter(
            WorkflowInstance.tenant_id.in_(tenant_ids)
        ).all()]
        if workflow_ids:
            self.s.query(WorkflowProfile).filter(WorkflowProfile.workflow_id.in_(workflow_ids)).delete(synchronize_session=False)
        self.s.query(AuditLog).filter(AuditLog.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        # Examination fixtures have child records.  Remove the children first
        # so the test remains valid on databases that enforce FK constraints.
        for model in (D.Mark, D.ResultSheet, D.ExamScheduleHistory,
                      D.ExamScheduleEntry, D.Assessment, D.Enrollment,
                      D.Section, D.Course,
                      D.ComplianceRequirement, D.HostelAllocation, D.HostelRoom,
                      D.LeaveRequest, D.AttendanceRecord, D.Student, D.Program,
                      D.Department, D.StaffMember,
                      D.Asset, D.ResearchProject, D.TransportRoute, D.Complaint):
            self.s.query(model).filter(model.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(WorkflowInstance).filter(WorkflowInstance.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(AuthorityMembership).filter(AuthorityMembership.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(User).filter(User.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(Person).filter(Person.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(OrgScope).filter(OrgScope.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.query(Tenant).filter(Tenant.id.in_(tenant_ids)).delete(synchronize_session=False)
        self.s.commit()
        self.s.close()

    def test_principal_exam_oversight_is_tenant_and_campus_scoped(self):
        """The Principal may inspect only their canonical campus's exam data."""
        tenant_a, tenant_b = self.tenants[:2]
        principal_a = self._ctx(tenant_a, 4)
        dept_a, dept_other, dept_b = (f"exam_dept_a_{self.stamp}", f"exam_dept_other_{self.stamp}", f"exam_dept_b_{self.stamp}")
        program_a, program_other, program_b = (f"exam_program_a_{self.stamp}", f"exam_program_other_{self.stamp}", f"exam_program_b_{self.stamp}")
        course_a, course_other, course_b = (f"exam_course_a_{self.stamp}", f"exam_course_other_{self.stamp}", f"exam_course_b_{self.stamp}")
        section_a, section_other, section_b = (f"exam_section_a_{self.stamp}", f"exam_section_other_{self.stamp}", f"exam_section_b_{self.stamp}")
        student_a, student_other = (f"exam_student_a_{self.stamp}", f"exam_student_other_{self.stamp}")
        assessment_a = f"exam_assessment_a_{self.stamp}"
        faculty_a, workflow_a = f"exam_faculty_a_{self.stamp}", f"exam_workflow_a_{self.stamp}"
        self.s.add_all([
            D.Department(id=dept_a, tenant_id=tenant_a, code="EXA", name="Exam A", campus="Tenant A Campus"),
            D.Department(id=dept_other, tenant_id=tenant_a, code="EXO", name="Exam Other", campus="Tenant A Other Campus"),
            D.Department(id=dept_b, tenant_id=tenant_b, code="EXB", name="Exam B", campus="Tenant B Campus"),
        ])
        self.s.flush()
        self.s.add_all([
            D.Program(id=program_a, tenant_id=tenant_a, dept_id=dept_a, code="EXA-UG", name="Exam A UG", level="UG"),
            D.Program(id=program_other, tenant_id=tenant_a, dept_id=dept_other, code="EXO-UG", name="Exam Other UG", level="UG"),
            D.Program(id=program_b, tenant_id=tenant_b, dept_id=dept_b, code="EXB-UG", name="Exam B UG", level="UG"),
        ])
        self.s.flush()
        self.s.add_all([
            D.Course(id=course_a, tenant_id=tenant_a, dept_id=dept_a, program_id=program_a, code="EXA101", title="Exam A Course", semester=1),
            D.Course(id=course_other, tenant_id=tenant_a, dept_id=dept_other, program_id=program_other, code="EXO101", title="Exam Other Course", semester=1),
            D.Course(id=course_b, tenant_id=tenant_b, dept_id=dept_b, program_id=program_b, code="EXB101", title="Exam B Course", semester=1),
        ])
        self.s.flush()
        self.s.add_all([
            D.StaffMember(id=faculty_a, tenant_id=tenant_a, emp_id="EXA-F", name="Exam A Faculty",
                          designation="Professor", dept_id=dept_a, campus_scope_id=self.scope_a),
            D.Section(id=section_a, tenant_id=tenant_a, campus_scope_id=self.scope_a, course_id=course_a, dept_id=dept_a, term="2026-Odd", section_code="A", faculty_person_id=faculty_a),
            D.Section(id=section_other, tenant_id=tenant_a, campus_scope_id=self.scope_a_other, course_id=course_other, dept_id=dept_other, term="2026-Odd", section_code="B"),
            D.Section(id=section_b, tenant_id=tenant_b, campus_scope_id=self.scope_b, course_id=course_b, dept_id=dept_b, term="2026-Odd", section_code="A"),
            D.Student(id=student_a, tenant_id=tenant_a, roll_no="EXA-001", name="Exam A Student", dept_id=dept_a, program_id=program_a, campus="Tenant A Campus", campus_scope_id=self.scope_a, batch="2026", semester=1),
            D.Student(id=student_other, tenant_id=tenant_a, roll_no="EXO-001", name="Exam Other Student", dept_id=dept_other, program_id=program_other, campus="Tenant A Other Campus", campus_scope_id=self.scope_a_other, batch="2026", semester=1),
        ])
        self.s.flush()
        self.s.add(WorkflowInstance(id=workflow_a, tenant_id=tenant_a, process_key="examination_marks",
                   label="Marks review", title="Midterm — Section A", state="submitted",
                   initiator_id=principal_a["sub"], initiator_name="Principal", current_stage=1,
                   scope_level="campus", campus_scope_id=self.scope_a,
                   current_owner_office_n=10, current_owner_user_id=principal_a["sub"]))
        self.s.flush()
        self.s.add_all([
            D.Enrollment(id=f"exam_enrollment_a_{self.stamp}", tenant_id=tenant_a, student_id=student_a, section_id=section_a),
            D.Enrollment(id=f"exam_enrollment_other_{self.stamp}", tenant_id=tenant_a, student_id=student_other, section_id=section_other),
            D.Assessment(id=assessment_a, tenant_id=tenant_a, section_id=section_a, name="Midterm", max_marks=100,
                         status="published", published=True, marks_state="submitted", workflow_id=workflow_a,
                         academic_year="2026-27"),
        ])
        self.s.flush()
        self.s.add_all([
            D.Mark(id=f"exam_mark_a_{self.stamp}", tenant_id=tenant_a, assessment_id=assessment_a, student_id=student_a, score=78, status="draft"),
        ])
        self.s.commit()

        register = domain_api.exam_sections(ctx=principal_a, s=self.s)
        self.assertEqual([row["id"] for row in register["sections"]], [section_a])
        self.assertEqual(register["sections"][0]["marks_lifecycle_statuses"], ["submitted"])
        self.assertEqual(register["sections"][0]["academic_years"], ["2026-27"])
        self.assertEqual(register["sections"][0]["faculty"]["name"], "Exam A Faculty")
        self.assertFalse(register["permissions"]["enter_marks"])
        self.assertFalse(register["permissions"]["publish_result"])

        detail = domain_api.exam_section_oversight(section_a, ctx=principal_a, s=self.s)
        self.assertEqual(detail["section"]["campus_scope_id"], self.scope_a)
        self.assertEqual(detail["section"]["students"], 1)
        self.assertEqual(detail["section"]["academic_year"], "2026-27")
        self.assertEqual(detail["section"]["faculty"]["name"], "Exam A Faculty")
        self.assertEqual(detail["assessments"][0]["entered"], 1)
        self.assertEqual(detail["assessments"][0]["marks_status"], "submitted")
        self.assertEqual(detail["exceptions"][0]["current_owner"], f"{tenant_a} Principal")

        for isolated_section in (section_other, section_b):
            with self.assertRaises(HTTPException) as blocked:
                domain_api.exam_section_oversight(isolated_section, ctx=principal_a, s=self.s)
            self.assertEqual(blocked.exception.status_code, 404)

        with self.assertRaises(HTTPException) as principal_write:
            domain_api.enter_marks(domain_api.EnterMarksIn(assessment_id=assessment_a, marks={student_a: 80}), ctx=principal_a, s=self.s)
        self.assertEqual(principal_write.exception.status_code, 403)

    def _add_identity(self, tenant_id, scope_id, office_n):
        person_id = f"person_{tenant_id}_{office_n}"
        user_id = f"user_{tenant_id}_{office_n}"
        role = {3: "Campus Head", 4: "Principal", 5: "Vice Principal", 10: "Head of Department"}.get(office_n, f"Office {office_n}")
        # The production schema enforces the User FK on AuthorityMembership.
        # Flush the identity parents before adding the membership so this
        # regression fixture is portable across SQLite and PostgreSQL.
        self.s.add_all([
            Person(id=person_id, tenant_id=tenant_id, name=f"{tenant_id} {role}", email=f"{person_id}@test", contact=""),
            User(id=user_id, tenant_id=tenant_id, person_id=person_id, username=user_id,
                 password_hash=pwhash("Test@1234"), status="active", mfa_enabled=True,
                 office_n=office_n, role=role, scope_level="campus", scope_ref=scope_id),
        ])
        self.s.flush()
        self.s.add(AuthorityMembership(id=f"membership_{user_id}", user_id=user_id,
            institution_id="inst_icms", tenant_id=tenant_id, org_scope_id=scope_id,
            office_n=office_n, role_template_key=f"office_{office_n}",
            jurisdiction_type="scope", status="active"))
        self.users[(tenant_id, office_n)] = user_id

    def _add_fixture_identities(self):
        self.s.add_all([
            Tenant(id=self.tenants[0], institution_id="inst_icms", name="Hardening Tenant A"),
            Tenant(id=self.tenants[1], institution_id="inst_icms", name="Hardening Tenant B"),
            Tenant(id=self.tenants[2], institution_id="inst_icms", name="Hardening Empty Tenant"),
            OrgScope(id=self.scope_a, tenant_id=self.tenants[0], level="campus", name="Tenant A Campus"),
            OrgScope(id=self.scope_a_other, tenant_id=self.tenants[0], level="campus", name="Tenant A Other Campus"),
            OrgScope(id=self.scope_b, tenant_id=self.tenants[1], level="campus", name="Tenant B Campus"),
            OrgScope(id=self.scope_empty, tenant_id=self.tenants[2], level="campus", name="Empty Campus"),
        ])
        self.s.flush()
        self._add_identity(self.tenants[0], self.scope_a, 3)
        self._add_identity(self.tenants[0], self.scope_a, 4)
        self._add_identity(self.tenants[1], self.scope_b, 3)
        self._add_identity(self.tenants[1], self.scope_b, 4)
        self._add_identity(self.tenants[2], self.scope_empty, 3)
        self._add_identity(self.tenants[2], self.scope_empty, 4)
        self.s.commit()

    def _ctx(self, tenant_id, office_n):
        scope = {self.tenants[0]: self.scope_a, self.tenants[1]: self.scope_b,
                 self.tenants[2]: self.scope_empty}[tenant_id]
        return {"sub": self.users[(tenant_id, office_n)], "tenant_id": tenant_id,
                "institution_id": "inst_icms", "scope_level": "campus",
                "scope_ref": scope, "office_n": office_n, "auth_level": "mfa"}

    def _campus_ctx(self, tenant_id, office_n, scope_ref):
        ctx = self._ctx(tenant_id, office_n)
        ctx["scope_ref"] = scope_ref
        return ctx

    def test_tenant_and_campus_records_are_isolated_and_bop_accepts_canonical_scope(self):
        tenant_a, tenant_b, tenant_empty = self.tenants
        principal_a, principal_b = self._ctx(tenant_a, 4), self._ctx(tenant_b, 4)
        head_a, head_b, head_empty = self._ctx(tenant_a, 3), self._ctx(tenant_b, 3), self._ctx(tenant_empty, 3)
        main_counts = {
            "transport": self.s.query(D.TransportRoute).filter(D.TransportRoute.tenant_id == TENANT).count(),
            "research": self.s.query(D.ResearchProject).filter(D.ResearchProject.tenant_id == TENANT).count(),
            "faculty": self.s.query(D.StaffMember).filter(D.StaffMember.tenant_id == TENANT).count(),
        }
        staff_a, staff_a_other, staff_b = (f"staff_a_{self.stamp}", f"staff_a_other_{self.stamp}", f"staff_b_{self.stamp}")
        self.s.add_all([
            D.TransportRoute(id=f"route_a_{self.stamp}", tenant_id=tenant_a, campus_scope_id=self.scope_a, name="A Route", vehicle_no="A-01"),
            D.TransportRoute(id=f"route_a_other_{self.stamp}", tenant_id=tenant_a, campus_scope_id=self.scope_a_other, name="A Other Route", vehicle_no="AO-01"),
            D.TransportRoute(id=f"route_a_legacy_{self.stamp}", tenant_id=tenant_a, name="Unassigned Legacy Route", vehicle_no="AL-01"),
            D.TransportRoute(id=f"route_b_{self.stamp}", tenant_id=tenant_b, campus_scope_id=self.scope_b, name="B Route", vehicle_no="B-01"),
            D.ResearchProject(id=f"research_a_{self.stamp}", tenant_id=tenant_a, campus_scope_id=self.scope_a, title="A Research", grant_amount=100),
            D.ResearchProject(id=f"research_a_other_{self.stamp}", tenant_id=tenant_a, campus_scope_id=self.scope_a_other, title="A Other Research", grant_amount=150),
            D.ResearchProject(id=f"research_a_legacy_{self.stamp}", tenant_id=tenant_a, title="Unassigned Legacy Research", grant_amount=175),
            D.ResearchProject(id=f"research_b_{self.stamp}", tenant_id=tenant_b, campus_scope_id=self.scope_b, title="B Research", grant_amount=200),
            D.StaffMember(id=staff_a, tenant_id=tenant_a, emp_id="A-01", name="A Faculty", designation="Professor", campus="Tenant A Campus", campus_scope_id=self.scope_a),
            D.StaffMember(id=staff_a_other, tenant_id=tenant_a, emp_id="A-02", name="A Other Faculty", designation="Professor", campus="Tenant A Other Campus", campus_scope_id=self.scope_a_other),
            D.StaffMember(id=staff_b, tenant_id=tenant_b, emp_id="B-01", name="B Faculty", designation="Professor", campus="Tenant B Campus", campus_scope_id=self.scope_b),
        ])
        # LeaveRequest has a strict foreign key to StaffMember in PostgreSQL.
        self.s.flush()
        self.s.add_all([
            D.LeaveRequest(id=f"leave_a_{self.stamp}", tenant_id=tenant_a, staff_id=staff_a, staff_name="A Faculty", campus_scope_id=self.scope_a, from_date=date.today(), to_date=date.today()),
            D.LeaveRequest(id=f"leave_b_{self.stamp}", tenant_id=tenant_b, staff_id=staff_b, staff_name="B Faculty", campus_scope_id=self.scope_b, from_date=date.today(), to_date=date.today()),
            D.HostelRoom(id=f"room_a_{self.stamp}", tenant_id=tenant_a, campus="Tenant A Campus", campus_scope_id=self.scope_a, block="A", room_no="101", capacity=2),
            D.HostelRoom(id=f"room_b_{self.stamp}", tenant_id=tenant_b, campus="Tenant B Campus", campus_scope_id=self.scope_b, block="B", room_no="101", capacity=2),
            D.ComplianceRequirement(id=f"compliance_a_{self.stamp}", tenant_id=tenant_a, campus="Tenant A Campus", campus_scope_id=self.scope_a, reference_code=f"A-{self.stamp}", title="A Compliance"),
            D.ComplianceRequirement(id=f"compliance_b_{self.stamp}", tenant_id=tenant_b, campus="Tenant B Campus", campus_scope_id=self.scope_b, reference_code=f"B-{self.stamp}", title="B Compliance"),
            D.Asset(id=f"asset_a_{self.stamp}", tenant_id=tenant_a, campus_scope_id=self.scope_a, tag="A-asset", name="A Asset", status="maintenance"),
            D.Asset(id=f"asset_a_other_{self.stamp}", tenant_id=tenant_a, campus_scope_id=self.scope_a_other, tag="AO-asset", name="A Other Asset", status="maintenance"),
            D.Student(id=f"student_a_{self.stamp}", tenant_id=tenant_a, roll_no="A-001", name="A Student", campus="Tenant A Campus", campus_scope_id=self.scope_a, batch="2026", semester=1, status="active"),
            D.Student(id=f"student_a_other_{self.stamp}", tenant_id=tenant_a, roll_no="AO-001", name="A Other Student", campus="Tenant A Other Campus", campus_scope_id=self.scope_a_other, batch="2026", semester=1, status="active"),
        ])
        self.s.commit()

        self.assertEqual([row["name"] for row in domain_api.transport(ctx=principal_a, s=self.s)["routes"]], ["A Route"])
        self.assertEqual([row["name"] for row in domain_api.transport(ctx=principal_b, s=self.s)["routes"]], ["B Route"])
        self.assertEqual([row["title"] for row in domain_api.research(ctx=principal_a, s=self.s)["projects"]], ["A Research"])
        self.assertEqual([row["title"] for row in domain_api.research(ctx=principal_b, s=self.s)["projects"]], ["B Research"])
        self.assertEqual([row["name"] for row in domain_api.transport(ctx=head_a, s=self.s)["routes"]], ["A Route"])
        self.assertEqual([row["title"] for row in domain_api.research(ctx=head_a, s=self.s)["projects"]], ["A Research"])
        principal_a_other = self._campus_ctx(tenant_a, 4, self.scope_a_other)
        self.assertEqual([row["name"] for row in domain_api.transport(ctx=principal_a_other, s=self.s)["routes"]], ["A Other Route"])
        self.assertEqual([row["title"] for row in domain_api.research(ctx=principal_a_other, s=self.s)["projects"]], ["A Other Research"])
        chairman_ctx = {**principal_a, "office_n": 1, "scope_level": "global", "scope_ref": "scope_global"}
        chairman_routes = {row["name"] for row in domain_api.transport(ctx=chairman_ctx, s=self.s)["routes"]}
        chairman_research = {row["title"] for row in domain_api.research(ctx=chairman_ctx, s=self.s)["projects"]}
        self.assertTrue({"A Route", "A Other Route", "Unassigned Legacy Route", "B Route"}.issubset(chairman_routes))
        self.assertTrue({"A Research", "A Other Research", "Unassigned Legacy Research", "B Research"}.issubset(chairman_research))
        self.assertEqual([row["id"] for row in domain_api.faculty_staff(page=1, page_size=20, ctx=principal_a, s=self.s)["staff"]], [staff_a])
        with self.assertRaises(HTTPException) as cross_profile:
            domain_api.faculty_profile(staff_b, ctx=principal_a, s=self.s)
        self.assertEqual(cross_profile.exception.status_code, 404)
        self.assertEqual(len(domain_api.list_leave(ctx=head_a, s=self.s)["leave"]), 1)
        self.assertEqual(domain_api.hostel(ctx=head_a, s=self.s)["summary"]["rooms"], 1)
        self.assertEqual(len(domain_api.compliance_requirements(ctx=principal_a, s=self.s)["requirements"]), 1)

        dashboard = domain_api.principal_overview(ctx=principal_a, s=self.s)
        self.assertEqual((dashboard["kpis"]["students"], dashboard["kpis"]["faculty"], dashboard["operations"]["maintenance"], dashboard["data_scope"]), (1, 1, 1, "campus"))
        self.assertIsNone(dashboard["examinations"]["sections"])
        self.assertIsNone(dashboard["welfare"]["grievances"])

        bop_a = main.create_bop(main.BOPBody(title="Tenant A BOP"), ctx=head_a, s=self.s)
        bop_b = main.create_bop(main.BOPBody(title="Tenant B BOP"), ctx=head_b, s=self.s)
        self.assertEqual((bop_a["campus_scope_id"], bop_b["campus_scope_id"]), (self.scope_a, self.scope_b))
        self.assertEqual([row["id"] for row in main.list_bop(ctx=head_a, s=self.s)["plans"]], [bop_a["id"]])
        with self.assertRaises(HTTPException) as cross_bop:
            main.update_bop(bop_a["id"], main.BOPBody(title="Not B"), ctx=head_b, s=self.s)
        self.assertEqual(cross_bop.exception.status_code, 404)

        self.assertEqual(domain_api.transport(ctx=self._ctx(tenant_empty, 4), s=self.s)["routes"], [])
        self.assertEqual(domain_api.research(ctx=self._ctx(tenant_empty, 4), s=self.s)["projects"], [])
        self.assertEqual(domain_api.faculty_staff(page=1, page_size=20, ctx=self._ctx(tenant_empty, 4), s=self.s)["staff"], [])
        self.assertEqual(domain_api.list_leave(ctx=head_empty, s=self.s)["leave"], [])
        self.assertEqual(domain_api.hostel(ctx=head_empty, s=self.s)["summary"]["rooms"], 0)
        self.assertEqual(domain_api.compliance_requirements(ctx=self._ctx(tenant_empty, 4), s=self.s)["requirements"], [])
        self.assertEqual(main.list_bop(ctx=head_empty, s=self.s)["plans"], [])
        self.assertEqual(main_counts, {
            "transport": self.s.query(D.TransportRoute).filter(D.TransportRoute.tenant_id == TENANT).count(),
            "research": self.s.query(D.ResearchProject).filter(D.ResearchProject.tenant_id == TENANT).count(),
            "faculty": self.s.query(D.StaffMember).filter(D.StaffMember.tenant_id == TENANT).count(),
        })

    def test_grievance_lifecycle_is_transactional_and_tenant_campus_scoped(self):
        tenant_a, tenant_b = self.tenants[:2]
        principal_a = self._ctx(tenant_a, 4)
        self._add_identity(tenant_a, self.scope_a, 20)
        self._add_identity(tenant_b, self.scope_b, 20)
        self.s.commit()
        grievance_a = self._ctx(tenant_a, 20)
        grievance_b = self._ctx(tenant_b, 20)

        created = domain_api.raise_complaint(
            domain_api.ComplaintIn(kind="Grievance", severity="high", subject="Scope-safe concern", detail="A complete complaint description."),
            ctx=principal_a, s=self.s,
        )
        complaint_id = created["id"]
        complaint = self.s.get(D.Complaint, complaint_id)
        self.assertEqual((complaint.tenant_id, complaint.campus_scope_id, complaint.status, complaint.severity),
                         (tenant_a, self.scope_a, "open", "high"))
        self.assertEqual([row["id"] for row in domain_api.grievance(ctx=principal_a, s=self.s)["complaints"]], [complaint_id])

        with self.assertRaises(HTTPException) as principal_cannot_investigate:
            domain_api.investigate_complaint(complaint_id, domain_api.ComplaintNotesIn(notes="Principal attempt"), ctx=principal_a, s=self.s)
        self.assertEqual(principal_cannot_investigate.exception.status_code, 403)
        with self.assertRaises(HTTPException) as no_notes:
            domain_api.investigate_complaint(complaint_id, domain_api.ComplaintNotesIn(notes=""), ctx=grievance_a, s=self.s)
        self.assertEqual(no_notes.exception.status_code, 422)
        with self.assertRaises(HTTPException) as invalid_transition:
            domain_api._resolve_complaint(complaint_id, "Cannot skip investigation", grievance_a, self.s)
        self.assertEqual(invalid_transition.exception.status_code, 409)

        # An audit error must roll back the state mutation as well.
        with patch("domain_api.write_audit", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                domain_api.investigate_complaint(complaint_id, domain_api.ComplaintNotesIn(notes="Will be rolled back"), ctx=grievance_a, s=self.s)
        self.s.expire_all()
        self.assertEqual(self.s.get(D.Complaint, complaint_id).status, "open")

        investigating = domain_api.investigate_complaint(
            complaint_id, domain_api.ComplaintNotesIn(notes="Reviewed supporting records."), ctx=grievance_a, s=self.s,
        )["complaint"]
        self.assertEqual((investigating["status"], investigating["investigation_notes"]),
                         ("investigating", "Reviewed supporting records."))
        resolved = domain_api._resolve_complaint(complaint_id, "Case resolved after corrective action.", grievance_a, self.s)["complaint"]
        self.assertEqual((resolved["status"], resolved["resolution_notes"]),
                         ("resolved", "Case resolved after corrective action."))
        with self.assertRaises(HTTPException) as repeated_resolve:
            domain_api._resolve_complaint(complaint_id, "Repeat", grievance_a, self.s)
        self.assertEqual(repeated_resolve.exception.status_code, 409)

        other_campus = D.Complaint(id=f"complaint_other_{self.stamp}", tenant_id=tenant_a,
                                   campus_scope_id=self.scope_a_other, kind="Grievance",
                                   raised_by="Other campus", subject="Other campus case", detail="Private", status="open")
        other_tenant = D.Complaint(id=f"complaint_tenant_b_{self.stamp}", tenant_id=tenant_b,
                                   campus_scope_id=self.scope_b, kind="Grievance",
                                   raised_by="Tenant B", subject="Other tenant case", detail="Private", status="open")
        self.s.add_all([other_campus, other_tenant]); self.s.commit()
        self.assertEqual([row["id"] for row in domain_api.grievance(ctx=principal_a, s=self.s)["complaints"]], [complaint_id])
        with self.assertRaises(HTTPException) as campus_isolation:
            domain_api.grievance_detail(other_campus.id, ctx=principal_a, s=self.s)
        self.assertEqual(campus_isolation.exception.status_code, 404)
        with self.assertRaises(HTTPException) as tenant_isolation:
            domain_api.grievance_detail(other_tenant.id, ctx=grievance_a, s=self.s)
        self.assertEqual(tenant_isolation.exception.status_code, 404)
        self.assertEqual([row["id"] for row in domain_api.grievance(ctx=grievance_b, s=self.s)["complaints"]], [other_tenant.id])

        audit_actions = [row.action for row in self.s.query(AuditLog).filter(
            AuditLog.tenant_id == tenant_a, AuditLog.entity == f"complaint:{complaint_id}"
        ).all()]
        self.assertEqual(audit_actions, ["grievance.raise", "grievance.investigate", "grievance.resolve"])

    def test_authenticated_context_never_uses_main_tenant_fallback(self):
        backend = Path(BACKEND_DIR)
        protected_context_keys = ("tenant_id", "scope_ref", "institution_id", "branch_id")
        for path in (backend / "main.py", backend / "domain_api.py", backend / "portal_api.py"):
            source = path.read_text(encoding="utf-8")
            for key in protected_context_keys:
                self.assertNotIn(f'ctx.get("{key}"', source, path.name)
                self.assertNotIn(f"ctx.get('{key}'", source, path.name)
        for path in (backend / "core.py", backend / "main.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("tenant_id or TENANT", source, path.name)
            self.assertNotIn("tenant_id=tenant_id or TENANT", source, path.name)

    def test_student_creation_requires_a_tenant_local_campus_department_and_program(self):
        tenant_a, tenant_b = self.tenants[:2]
        principal_a, principal_b = self._ctx(tenant_a, 4), self._ctx(tenant_b, 4)
        principal_a_other = self._campus_ctx(tenant_a, 4, self.scope_a_other)

        department_a = domain_api.create_department(
            domain_api.DepartmentIn(code="STUA", name="Student A"), ctx=principal_a, s=self.s
        )["department"]
        department_a_other = domain_api.create_department(
            domain_api.DepartmentIn(code="STUO", name="Student Other"), ctx=principal_a_other, s=self.s
        )["department"]
        department_b = domain_api.create_department(
            domain_api.DepartmentIn(code="STUB", name="Student B"), ctx=principal_b, s=self.s
        )["department"]
        program_a = domain_api.create_program(
            domain_api.ProgramIn(code="STUA-UG", name="Student A UG", dept_id=department_a["id"]), ctx=principal_a, s=self.s
        )["program"]
        program_a_other = domain_api.create_program(
            domain_api.ProgramIn(code="STUO-UG", name="Student Other UG", dept_id=department_a_other["id"]), ctx=principal_a_other, s=self.s
        )["program"]
        program_b = domain_api.create_program(
            domain_api.ProgramIn(code="STUB-UG", name="Student B UG", dept_id=department_b["id"]), ctx=principal_b, s=self.s
        )["program"]

        self.assertEqual([row["id"] for row in domain_api.list_departments(ctx=principal_a, s=self.s)["departments"]], [department_a["id"]])
        self.assertEqual([row["id"] for row in domain_api.list_programs(ctx=principal_a, s=self.s)["programs"]], [program_a["id"]])

        created = domain_api.add_student(
            domain_api.StudentIn(name="Isolated Student", roll_no="STUA-001", dept_code="STUA", program_id=program_a["id"], batch="2026", semester=1),
            ctx=principal_a, s=self.s,
        )
        row = self.s.query(D.Student).filter(D.Student.id == created["id"]).one()
        self.assertEqual(
            (row.tenant_id, row.campus_scope_id, row.dept_id, row.program_id, row.roll_no),
            (tenant_a, self.scope_a, department_a["id"], program_a["id"], "STUA-001"),
        )
        self.assertIn(created["id"], [item["id"] for item in domain_api.list_students(ctx=principal_a, s=self.s)["students"]])
        self.assertNotIn(created["id"], [item["id"] for item in domain_api.list_students(ctx=principal_b, s=self.s)["students"]])

        invalid_bodies = [
            domain_api.StudentIn(name="Missing Program", roll_no="STUA-002", dept_code="STUA", program_id="", batch="2026", semester=1),
            domain_api.StudentIn(name="Other Campus Department", roll_no="STUA-003", dept_code="STUO", program_id=program_a_other["id"], batch="2026", semester=1),
            domain_api.StudentIn(name="Other Campus Program", roll_no="STUA-004", dept_code="STUA", program_id=program_a_other["id"], batch="2026", semester=1),
            domain_api.StudentIn(name="Other Tenant Program", roll_no="STUA-005", dept_code="STUA", program_id=program_b["id"], batch="2026", semester=1),
            domain_api.StudentIn(name="Invalid Semester", roll_no="STUA-006", dept_code="STUA", program_id=program_a["id"], batch="2026", semester=9),
            domain_api.StudentIn(name="Duplicate Roll", roll_no="STUA-001", dept_code="STUA", program_id=program_a["id"], batch="2026", semester=1),
        ]
        for body in invalid_bodies:
            with self.assertRaises(HTTPException) as rejected:
                domain_api.add_student(body, ctx=principal_a, s=self.s)
            self.assertIn(rejected.exception.status_code, {400, 409})
        self.assertEqual(self.s.query(D.Student).filter(D.Student.tenant_id == tenant_a).count(), 1)

    def test_campus_head_catalog_and_leadership_are_authoritative_and_isolated(self):
        tenant_a, tenant_b = self.tenants[:2]
        head_a, head_b = self._ctx(tenant_a, 3), self._ctx(tenant_b, 3)
        self._add_identity(tenant_a, self.scope_a, 5)
        self._add_identity(tenant_a, self.scope_a, 10)
        self._add_identity(tenant_a, self.scope_a_other, 6)
        self._add_identity(tenant_b, self.scope_b, 5)
        dept_a = f"dept_a_{self.stamp}"
        dept_a_empty = f"dept_a_empty_{self.stamp}"
        dept_a_other = f"dept_a_other_{self.stamp}"
        dept_b = f"dept_b_{self.stamp}"
        vice_principal_a = self.users[(tenant_a, 5)]
        self.s.add_all([
            D.Department(id=dept_a, tenant_id=tenant_a, code="AENG", name="A Engineering", campus="Tenant A Campus"),
            D.Department(id=dept_a_empty, tenant_id=tenant_a, code="AZERO", name="A Zero Enrollment", campus="Tenant A Campus"),
            D.Department(id=dept_a_other, tenant_id=tenant_a, code="AOTH", name="A Other Campus", campus="Tenant A Other Campus"),
            D.Department(id=dept_b, tenant_id=tenant_b, code="BENG", name="B Engineering", campus="Tenant B Campus"),
            D.Program(id=f"program_a_1_{self.stamp}", tenant_id=tenant_a, dept_id=dept_a, code="AENG-UG", name="A Engineering UG", level="UG"),
            D.Program(id=f"program_a_2_{self.stamp}", tenant_id=tenant_a, dept_id=dept_a, code="AENG-PG", name="A Engineering PG", level="PG"),
            D.Program(id=f"program_a_other_{self.stamp}", tenant_id=tenant_a, dept_id=dept_a_other, code="AOTH-UG", name="A Other UG", level="UG"),
            D.Program(id=f"program_b_{self.stamp}", tenant_id=tenant_b, dept_id=dept_b, code="BENG-UG", name="B Engineering UG", level="UG"),
            D.Student(id=f"catalog_student_a_{self.stamp}", tenant_id=tenant_a, roll_no="A-CATALOG", name="A Catalog Student", dept_id=dept_a, campus="Tenant A Campus", campus_scope_id=self.scope_a, batch="2026", semester=1, status="active"),
            D.Student(id=f"catalog_student_a_other_{self.stamp}", tenant_id=tenant_a, roll_no="AO-CATALOG", name="A Other Student", dept_id=dept_a_other, campus="Tenant A Other Campus", campus_scope_id=self.scope_a_other, batch="2026", semester=1, status="active"),
            D.Student(id=f"catalog_student_b_{self.stamp}", tenant_id=tenant_b, roll_no="B-CATALOG", name="B Catalog Student", dept_id=dept_b, campus="Tenant B Campus", campus_scope_id=self.scope_b, batch="2026", semester=1, status="active"),
            D.StaffMember(id=f"leader_staff_a_{self.stamp}", tenant_id=tenant_a, emp_id="LEAD-A", name="A Vice Principal Staff", user_id=vice_principal_a, designation="Vice Principal", dept_id=dept_a, campus="Tenant A Campus", campus_scope_id=self.scope_a),
            D.StaffMember(id=f"ordinary_staff_a_{self.stamp}", tenant_id=tenant_a, emp_id="ORD-A", name="Ordinary Staff", designation="Professor", dept_id=dept_a, campus="Tenant A Campus", campus_scope_id=self.scope_a),
        ])
        self.s.commit()

        overview_a = domain_api.overview(ctx=head_a, s=self.s)
        overview_b = domain_api.overview(ctx=head_b, s=self.s)
        catalog_a = {row["code"]: row for row in overview_a["department_programs"]}
        catalog_b = {row["code"]: row for row in overview_b["department_programs"]}
        self.assertEqual(catalog_a["AENG"]["programs"], 2)
        self.assertEqual(catalog_a["AENG"]["students"], 1)
        self.assertEqual(catalog_a["AZERO"], {"id": dept_a_empty, "code": "AZERO", "name": "A Zero Enrollment", "students": 0, "programs": 0})
        self.assertNotIn("AOTH", catalog_a)
        self.assertNotIn("BENG", catalog_a)
        self.assertEqual(catalog_b["BENG"]["programs"], 1)
        self.assertNotIn("AENG", catalog_b)
        self.assertEqual(overview_a["program_mix"]["AENG"], 2)

        leadership_a = domain_api.campus_leadership(ctx=head_a, s=self.s)
        leadership_b = domain_api.campus_leadership(ctx=head_b, s=self.s)
        members_a = {row["user_id"]: row for row in leadership_a["members"]}
        self.assertIn(vice_principal_a, members_a)
        self.assertEqual(members_a[vice_principal_a]["employee_id"], "LEAD-A")
        self.assertEqual(members_a[vice_principal_a]["department_code"], "AENG")
        self.assertNotIn("Ordinary Staff", {row["name"] for row in leadership_a["members"]})
        self.assertTrue(all(row["campus_scope_id"] == self.scope_a for row in leadership_a["members"]))
        self.assertTrue(all(row["campus_scope_id"] == self.scope_b for row in leadership_b["members"]))
        self.assertNotIn(vice_principal_a, {row["user_id"] for row in leadership_b["members"]})
