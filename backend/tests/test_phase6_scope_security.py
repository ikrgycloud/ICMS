import os
import sys
import unittest
from datetime import date, datetime
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal, TENANT
from models import (AuditLog, AuthorityMembership, BranchOrganization, Delegation,
                    Notification, OnboardingInvite, OrgScope, Person, Role, Tenant, User)
import core
import domain_api
import domain_models as D
import main
from authority import issue_token, pwhash


class Phase6ScopeSecurityTests(unittest.TestCase):
    campus_ctx = {"sub": "user_3", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "scope_main_campus", "office_n": 3, "auth_level": "mfa"}
    human_campus_ctx = {**campus_ctx, "scope_ref": "Main Campus"}
    principal_ctx = {"sub": "user_4", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "Main Campus", "office_n": 4, "auth_level": "mfa"}
    vc_ctx = {"sub": "user_2", "tenant_id": TENANT, "scope_level": "university", "scope_ref": "scope_univ", "office_n": 2, "auth_level": "mfa"}

    def setUp(self):
        self.s = SessionLocal()
        self.stamp = datetime.utcnow().strftime("%H%M%S%f")
        self.ids = []
        self.lifecycle_tenants = []
        self.recruitment_tenants = []

    def tearDown(self):
        self.s.rollback()
        if self.recruitment_tenants:
            self.s.query(AuditLog).filter(AuditLog.tenant_id.in_(self.recruitment_tenants)).delete(synchronize_session=False)
            self.s.query(D.JobPosting).filter(D.JobPosting.tenant_id.in_(self.recruitment_tenants)).delete(synchronize_session=False)
        if self.lifecycle_tenants:
            self.s.query(AuditLog).filter(AuditLog.tenant_id.in_(self.lifecycle_tenants)).delete(synchronize_session=False)
            self.s.query(AuthorityMembership).filter(AuthorityMembership.tenant_id.in_(self.lifecycle_tenants)).delete(synchronize_session=False)
            self.s.query(BranchOrganization).filter(BranchOrganization.tenant_id.in_(self.lifecycle_tenants)).delete(synchronize_session=False)
        self.s.query(Delegation).filter(Delegation.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.Student).filter(D.Student.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.FeeInvoice).filter(D.FeeInvoice.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.BudgetLine).filter(D.BudgetLine.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.AcademicCalendarEntry).filter(D.AcademicCalendarEntry.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.GovernanceComplianceMetric).filter(D.GovernanceComplianceMetric.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.GovernancePerformanceMetric).filter(D.GovernancePerformanceMetric.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.GovernanceDashboardSnapshot).filter(D.GovernanceDashboardSnapshot.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.Section).filter(D.Section.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.Course).filter(D.Course.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.Program).filter(D.Program.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.Department).filter(D.Department.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(Role).filter(Role.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.StaffMember).filter(D.StaffMember.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.Student).filter(D.Student.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(Notification).filter(Notification.user_id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(OnboardingInvite).filter(OnboardingInvite.user_id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(User).filter(User.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(Person).filter(Person.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(OrgScope).filter(OrgScope.id.in_(self.ids)).delete(synchronize_session=False)
        if self.lifecycle_tenants:
            self.s.query(OrgScope).filter(OrgScope.tenant_id.in_(self.lifecycle_tenants)).delete(synchronize_session=False)
            self.s.query(Tenant).filter(Tenant.id.in_(self.lifecycle_tenants)).delete(synchronize_session=False)
        self.s.commit(); self.s.close()

    def add_student_invoice(self, campus, tenant=TENANT):
        sid, iid = f"p6stu{len(self.ids)}{self.stamp}", f"p6inv{len(self.ids)}{self.stamp}"
        campus_scope = self.s.query(OrgScope).filter(
            OrgScope.tenant_id == tenant, OrgScope.level == "campus", OrgScope.name == campus
        ).first()
        student = D.Student(id=sid, tenant_id=tenant, roll_no=sid[-8:], name=campus,
                            email=f"{sid}@test", campus=campus, batch="2025", semester=1,
                            campus_scope_id=campus_scope.id if campus_scope else None,
                            section="A", status="active", cgpa=7.0)
        invoice = D.FeeInvoice(id=iid, tenant_id=tenant, student_id=sid, term="2025", amount=100, paid=0, status="due")
        self.s.add_all([student, invoice]); self.s.commit(); self.ids.extend([sid, iid])
        return sid, iid

    def add_user(self, username, tenant, scope_ref):
        pid, uid = f"p6per{len(self.ids)}{self.stamp}", f"p6usr{len(self.ids)}{self.stamp}"
        self.s.add_all([
            Person(id=pid, tenant_id=tenant, name=username, email=f"{username}@test", contact=""),
            User(id=uid, tenant_id=tenant, person_id=pid, username=username, password_hash="x",
                 status="active", mfa_enabled=True, office_n=3, role="Campus Head",
                 scope_level="campus", scope_ref=scope_ref),
        ])
        self.s.commit(); self.ids.extend([pid, uid]); return uid

    def test_campus_overview_workforce_finance_and_budget_are_scoped(self):
        main_students_before = self.s.query(D.Student).filter(D.Student.tenant_id == TENANT, D.Student.campus == "Main Campus").count()
        main_staff_before = self.s.query(D.StaffMember).filter(D.StaffMember.tenant_id == TENANT, D.StaffMember.campus == "Main Campus").count()
        main_student, main_invoice = self.add_student_invoice("Main Campus")
        north_student, north_invoice = self.add_student_invoice("North Campus")
        main_staff, north_staff = f"p6staffmain{self.stamp}", f"p6staffnorth{self.stamp}"
        self.s.add_all([
            D.StaffMember(id=main_staff, tenant_id=TENANT, emp_id=main_staff[-8:], name="Main", campus="Main Campus", campus_scope_id="scope_main_campus", designation="Professor", status="active"),
            D.StaffMember(id=north_staff, tenant_id=TENANT, emp_id=north_staff[-8:], name="North", campus="North Campus", campus_scope_id="scope_north_campus", designation="Professor", status="active"),
        ])
        main_budget, north_budget = f"p6budgetmain{self.stamp}", f"p6budgetnorth{self.stamp}"
        self.s.add_all([
            D.BudgetLine(id=main_budget, tenant_id=TENANT, campus="Main Campus", campus_scope_id="scope_main_campus", category="Main", allocated=100, spent=10),
            D.BudgetLine(id=north_budget, tenant_id=TENANT, campus="North Campus", campus_scope_id="scope_north_campus", category="North", allocated=100, spent=10),
        ])
        self.s.commit(); self.ids.extend([main_staff, north_staff, main_budget, north_budget])
        overview = domain_api.overview(ctx=self.campus_ctx, s=self.s)
        self.assertEqual(overview["stats"]["students"], main_students_before + 1)
        self.assertEqual(overview["stats"]["faculty"], main_staff_before + 1)
        self.assertIsNone(overview["stats"]["courses"])
        staff = domain_api.faculty_staff(q="Main", page=1, page_size=20, ctx=self.campus_ctx, s=self.s)
        self.assertIn(main_staff, [row["id"] for row in staff["staff"]])
        self.assertNotIn(north_staff, [row["id"] for row in staff["staff"]])
        invoices = domain_api.list_invoices(student_id=main_student, ctx=self.campus_ctx, s=self.s)
        self.assertIn(main_invoice, [row["id"] for row in invoices["invoices"]])
        budget = domain_api.list_budget(ctx=self.campus_ctx, s=self.s)
        categories = [row["category"] for row in budget["budget"]]
        self.assertIn("Main", categories)
        self.assertNotIn("North", categories)

    def test_live_campus_head_name_scope_resolves_to_canonical_scope_for_supported_endpoints(self):
        scope = domain_api._campus_scope_for_campus_head(self.s, self.human_campus_ctx)
        self.assertEqual(scope.id, "scope_main_campus")
        self.assertEqual(scope.name, "Main Campus")
        self.assertIsNotNone(domain_api.overview(ctx=self.human_campus_ctx, s=self.s))
        self.assertIsNotNone(domain_api.faculty_staff(page=1, page_size=20, ctx=self.human_campus_ctx, s=self.s))
        self.assertIsNotNone(domain_api.list_invoices(ctx=self.human_campus_ctx, s=self.s))
        self.assertIsNotNone(domain_api.list_budget(ctx=self.human_campus_ctx, s=self.s))
        self.assertIsNotNone(domain_api.academic_calendar(ctx=self.human_campus_ctx, s=self.s))
        self.assertIsNotNone(domain_api.calendar_view(start="2026-09-01", ctx=self.human_campus_ctx, s=self.s))
        self.assertEqual(domain_api.list_assets(ctx=self.human_campus_ctx, s=self.s)["data_status"], "available")
        self.assertEqual(domain_api.grievance(ctx=self.human_campus_ctx, s=self.s)["data_status"], "available")

    def test_non_campus_head_scope_semantics_are_unchanged(self):
        self.assertIsNotNone(domain_api.overview(ctx=self.principal_ctx, s=self.s))
        self.assertIsNotNone(domain_api.overview(ctx=self.vc_ctx, s=self.s))

    def test_student_scoped_grievances_and_scoped_assets_audit_are_available(self):
        assets = domain_api.list_assets(ctx=self.campus_ctx, s=self.s)
        grievances = domain_api.grievance(ctx=self.campus_ctx, s=self.s)
        placements = domain_api.placements(ctx=self.campus_ctx, s=self.s)
        audit = main.get_audit(ctx=self.campus_ctx, s=self.s)
        verification = main.verify_audit(ctx=self.campus_ctx, s=self.s)
        self.assertEqual(assets["data_status"], "available")
        self.assertEqual(grievances["data_status"], "available")
        self.assertEqual(placements["data_status"], "available")
        self.assertEqual(audit["data_status"], "available")
        self.assertEqual(verification["data_status"], "available")

    def test_campus_calendar_includes_only_own_or_all_campuses_entries(self):
        main_id, north_id, all_id = (f"p6calmain{self.stamp}", f"p6calnorth{self.stamp}", f"p6calall{self.stamp}")
        self.s.add_all([
            D.AcademicCalendarEntry(id=main_id, tenant_id=TENANT, term="P6", title="P6 Main", campus="Main Campus", start_date=date(2026, 9, 10)),
            D.AcademicCalendarEntry(id=north_id, tenant_id=TENANT, term="P6", title="P6 North", campus="North Campus", start_date=date(2026, 9, 10)),
            D.AcademicCalendarEntry(id=all_id, tenant_id=TENANT, term="P6", title="P6 All", campus="All Campuses", start_date=date(2026, 9, 10)),
        ])
        self.s.commit(); self.ids.extend([main_id, north_id, all_id])
        result = domain_api.calendar_view(start="2026-09-01", ctx=self.campus_ctx, s=self.s)
        titles = [row["title"] for row in result["events"]]
        self.assertIn("P6 Main", titles)
        self.assertIn("P6 All", titles)
        self.assertNotIn("P6 North", titles)

    def test_delegation_enforces_tenant_campus_authority_duration_limit_listing_and_revoke(self):
        other_tenant_user = self.add_user(f"p6othertenant{self.stamp}", f"p6tenant{self.stamp}", "scope_main_campus")
        north_user = self.add_user(f"p6north{self.stamp}", TENANT, "scope_north_campus")
        same_user = self.add_user(f"p6main{self.stamp}", TENANT, "scope_main_campus")
        with self.assertRaises(HTTPException) as tenant_error:
            main.create_delegation(main.DelegateIn(to_username=f"p6othertenant{self.stamp}", authority="review", days=1), ctx=self.campus_ctx, s=self.s)
        self.assertEqual(tenant_error.exception.status_code, 404)
        with self.assertRaises(HTTPException) as campus_error:
            main.create_delegation(main.DelegateIn(to_username=f"p6north{self.stamp}", authority="review", days=1), ctx=self.campus_ctx, s=self.s)
        self.assertEqual(campus_error.exception.status_code, 403)
        for body in (
            main.DelegateIn(to_username=f"p6main{self.stamp}", authority="*", days=1),
            main.DelegateIn(to_username=f"p6main{self.stamp}", authority="review", days=0),
            main.DelegateIn(to_username=f"p6main{self.stamp}", authority="approve", days=1, limit=10000001),
        ):
            with self.assertRaises(HTTPException):
                main.create_delegation(body, ctx=self.campus_ctx, s=self.s)
        delegation = main.create_delegation(main.DelegateIn(to_username=f"p6main{self.stamp}", authority="approve", days=1, limit=1000), ctx=self.campus_ctx, s=self.s)
        self.ids.append(delegation["id"])
        self.assertEqual([row["id"] for row in main.list_delegations(ctx=self.campus_ctx, s=self.s)["delegations"] if row["id"] == delegation["id"]], [delegation["id"]])
        with self.assertRaises(HTTPException) as revoke_error:
            main.revoke_delegation(delegation["id"], ctx={**self.campus_ctx, "tenant_id": f"p6tenant{self.stamp}"}, s=self.s)
        self.assertEqual(revoke_error.exception.status_code, 404)
        self.assertEqual(main.revoke_delegation(delegation["id"], ctx=self.campus_ctx, s=self.s)["status"], "revoked")

    def test_academic_reads_and_section_resolution_are_tenant_bound(self):
        tenant_a, tenant_b = f"p6tenant_a_{self.stamp}", f"p6tenant_b_{self.stamp}"
        dept_a, dept_b = f"p6dept_a_{self.stamp}", f"p6dept_b_{self.stamp}"
        program_a, program_b = f"p6prog_a_{self.stamp}", f"p6prog_b_{self.stamp}"
        course_a, course_b = f"p6course_a_{self.stamp}", f"p6course_b_{self.stamp}"
        section_a, section_b = f"p6section_a_{self.stamp}", f"p6section_b_{self.stamp}"
        self.s.add_all([
            D.Department(id=dept_a, tenant_id=tenant_a, code=f"A{self.stamp[-5:]}", name="Tenant A"),
            D.Department(id=dept_b, tenant_id=tenant_b, code=f"B{self.stamp[-5:]}", name="Tenant B"),
            D.Program(id=program_a, tenant_id=tenant_a, dept_id=dept_a, code=f"PA{self.stamp[-5:]}", name="Tenant A Program", level="UG"),
            D.Program(id=program_b, tenant_id=tenant_b, dept_id=dept_b, code=f"PB{self.stamp[-5:]}", name="Tenant B Program", level="UG"),
            D.Course(id=course_a, tenant_id=tenant_a, dept_id=dept_a, program_id=program_a, code=f"CA{self.stamp[-5:]}", title="Tenant A Course", credits=3, semester=1),
            D.Course(id=course_b, tenant_id=tenant_b, dept_id=dept_b, program_id=program_b, code=f"CB{self.stamp[-5:]}", title="Tenant B Course", credits=3, semester=1),
            D.Section(id=section_a, tenant_id=tenant_a, course_id=course_a, dept_id=dept_a, section_code="A"),
            D.Section(id=section_b, tenant_id=tenant_b, course_id=course_b, dept_id=dept_b, section_code="B"),
        ])
        self.s.commit(); self.ids.extend([dept_a, dept_b, program_a, program_b, course_a, course_b, section_a, section_b])
        ctx_a = {**self.principal_ctx, "tenant_id": tenant_a}
        ctx_b = {**self.principal_ctx, "tenant_id": tenant_b}
        self.assertEqual([row["id"] for row in domain_api.list_courses(ctx=ctx_a, s=self.s)["courses"]], [course_a])
        self.assertEqual([row["id"] for row in domain_api.list_courses(ctx=ctx_b, s=self.s)["courses"]], [course_b])
        self.assertEqual(domain_api._section_or_404(self.s, ctx_a, section_a).id, section_a)
        with self.assertRaises(HTTPException) as cross_tenant:
            domain_api._section_or_404(self.s, ctx_a, section_b)
        self.assertEqual(cross_tenant.exception.status_code, 404)

    def test_governance_snapshot_and_metrics_never_fall_back_to_another_tenant(self):
        tenant_a, tenant_b = f"p6gov_a_{self.stamp}", f"p6gov_b_{self.stamp}"
        snapshot_id, compliance_id, performance_id = (
            f"p6gov_snap_{self.stamp}", f"p6gov_comp_{self.stamp}", f"p6gov_perf_{self.stamp}")
        self.s.add_all([
            D.GovernanceDashboardSnapshot(
                id=snapshot_id, tenant_id=tenant_a, semester_key="p6", semester_label="Tenant A",
                is_default=True, student_count=365, faculty_count=44, total_budget=520000000,
            ),
            D.GovernanceComplianceMetric(
                id=compliance_id, tenant_id=tenant_a, snapshot_id=snapshot_id,
                metric_key="tenant_a_only", label="Tenant A compliance", score=93,
            ),
            D.GovernancePerformanceMetric(
                id=performance_id, tenant_id=tenant_a, snapshot_id=snapshot_id,
                area="Tenant A", metric="Tenant A performance", current_value="365",
            ),
        ])
        self.s.commit(); self.ids.extend([snapshot_id, compliance_id, performance_id])
        ctx_a = {**self.principal_ctx, "tenant_id": tenant_a}
        ctx_b = {**self.principal_ctx, "tenant_id": tenant_b}
        tenant_a_payload = domain_api.governance(ctx=ctx_a, s=self.s)
        tenant_b_payload = domain_api.governance(ctx=ctx_b, s=self.s)
        self.assertEqual(tenant_a_payload["kpis"]["students"], 365)
        self.assertEqual(tenant_a_payload["kpis"]["faculty"], 44)
        self.assertEqual(tenant_a_payload["budget"]["total"], 520000000)
        self.assertEqual(len(tenant_a_payload["compliance"]["items"]), 1)
        self.assertEqual(len(tenant_a_payload["performance_summary"]), 1)
        self.assertEqual(tenant_b_payload["kpis"]["students"], 0)
        self.assertEqual(tenant_b_payload["kpis"]["faculty"], 0)
        self.assertEqual(tenant_b_payload["budget"]["total"], 0)
        self.assertEqual(tenant_b_payload["compliance"]["items"], [])
        self.assertEqual(tenant_b_payload["performance_summary"], [])

    def test_directory_roles_returns_only_the_authenticated_tenant_roles(self):
        tenant_a, tenant_b = f"p6role_a_{self.stamp}", f"p6role_b_{self.stamp}"
        role_a, role_b = f"p6role_a_{self.stamp}", f"p6role_b_{self.stamp}"
        self.s.add_all([
            Role(id=role_a, tenant_id=tenant_a, office_n=4, name="Tenant A Principal", category="Institution Heads"),
            Role(id=role_b, tenant_id=tenant_b, office_n=4, name="Tenant B Principal", category="Institution Heads"),
        ])
        self.s.commit(); self.ids.extend([role_a, role_b])
        ctx_a = {**self.principal_ctx, "tenant_id": tenant_a}
        ctx_b = {**self.principal_ctx, "tenant_id": tenant_b}
        self.assertEqual(main.all_roles(ctx=ctx_a, s=self.s), [{"office_n": 4, "name": "Tenant A Principal", "category": "Institution Heads"}])
        self.assertEqual(main.all_roles(ctx=ctx_b, s=self.s), [{"office_n": 4, "name": "Tenant B Principal", "category": "Institution Heads"}])

    def test_demo_branch_password_is_hashed_and_unavailable_outside_development(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            password = main._development_demo_password()
            self.assertEqual(password, "Demo@12345")
            self.assertEqual(pwhash(password), pwhash("Demo@12345"))
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            with self.assertRaises(HTTPException) as unavailable:
                main._development_demo_password()
        self.assertEqual(unavailable.exception.status_code, 404)

    def test_legacy_copy_mapping_is_development_only_and_hash_verified(self):
        demo = User(id="legacy-demo", tenant_id="tenant_demo_test_2026_d239c", password_hash=pwhash("Demo@1234"))
        changed = User(id="legacy-changed", tenant_id="tenant_demo_test_2026_d239c", password_hash=pwhash("ADifferent@2026"))
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            self.assertEqual(main._legacy_branch_copy_password(demo), "Demo@1234")
            self.assertIsNone(main._legacy_branch_copy_password(changed))
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            self.assertIsNone(main._legacy_branch_copy_password(demo))

    def test_principal_workspace_includes_academic_catalog(self):
        workspace = domain_api.workspace(ctx=self.principal_ctx, s=self.s)
        catalog = next((module for module in workspace["modules"] if module["key"] == "academic_catalog"), None)
        self.assertIsNotNone(catalog)
        self.assertEqual(catalog["label"], "Academic Setup")

    def test_chairman_can_softly_discontinue_then_deactivate_a_branch_without_deleting_data(self):
        tenant_id = f"p6lifecycle_{self.stamp}"
        root_id, campus_id, branch_id = (f"p6life_root_{self.stamp}", f"p6life_campus_{self.stamp}",
                                         f"p6life_branch_{self.stamp}")
        person_id, user_id, membership_id, student_id = (f"p6life_person_{self.stamp}", f"p6life_user_{self.stamp}",
                                                          f"p6life_membership_{self.stamp}", f"p6life_student_{self.stamp}")
        self.lifecycle_tenants.append(tenant_id)
        self.s.add_all([
            Tenant(id=tenant_id, institution_id="inst_icms", name="Lifecycle Test Institute"),
            OrgScope(id=root_id, tenant_id=tenant_id, level="global", name="Lifecycle Root"),
            OrgScope(id=campus_id, tenant_id=tenant_id, level="campus", name="Lifecycle Campus", parent_id=root_id),
            BranchOrganization(id=branch_id, institution_id="inst_icms", tenant_id=tenant_id,
                               root_scope_id=root_id, campus_scope_id=campus_id, code=f"life{self.stamp[-5:]}",
                               location="Test", status="active", created_by="user_1"),
            Person(id=person_id, tenant_id=tenant_id, name="Lifecycle Principal", email="", contact=""),
            User(id=user_id, tenant_id=tenant_id, person_id=person_id, username=f"p6life{self.stamp}",
                 password_hash=pwhash("Lifecycle@2026"), status="active", mfa_enabled=True, office_n=4,
                 role="Principal", scope_level="campus", scope_ref=campus_id),
            AuthorityMembership(id=membership_id, user_id=user_id, institution_id="inst_icms", tenant_id=tenant_id,
                                org_scope_id=campus_id, office_n=4, role_template_key="office_4",
                                jurisdiction_type="scope", status="active"),
            D.Student(id=student_id, tenant_id=tenant_id, roll_no=f"LIFE-{self.stamp[-5:]}",
                      name="Lifecycle Student", email="", campus="Lifecycle Campus", batch="2026",
                      semester=1, section="A", status="active", cgpa=0),
        ])
        self.s.commit(); self.ids.extend([person_id, user_id, student_id])

        with self.assertRaises(HTTPException) as unauthorized:
            main.update_branch_lifecycle(branch_id, main.BranchLifecycleIn(status="discontinued"),
                                         ctx=self.principal_ctx, s=self.s)
        self.assertEqual(unauthorized.exception.status_code, 403)

        chairman_ctx = {"sub": "user_1", "office_n": 1}
        discontinued = main.update_branch_lifecycle(
            branch_id, main.BranchLifecycleIn(status="discontinued"), ctx=chairman_ctx, s=self.s)
        self.assertEqual(discontinued["status"], "discontinued")
        self.assertIsNotNone(self.s.get(Tenant, tenant_id))
        self.assertIsNotNone(self.s.get(User, user_id))
        self.assertIsNotNone(self.s.get(D.Student, student_id))
        audit = (self.s.query(AuditLog).filter(AuditLog.tenant_id == tenant_id,
                                               AuditLog.action == "institute.discontinued").one())
        self.assertEqual((audit.actor, audit.new_state, audit.campus_scope_id), ("user_1", "discontinued", campus_id))

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=issue_token(user_id, tenant_id, 4, "Principal", "campus", campus_id, "mfa"))
        with self.assertRaises(HTTPException) as main_access:
            main.auth(credentials)
        self.assertEqual(main_access.exception.status_code, 403)
        with self.assertRaises(HTTPException) as domain_access:
            core.auth(credentials)
        self.assertEqual(domain_access.exception.status_code, 403)
        with self.assertRaises(HTTPException) as login_access:
            main.login(main.LoginIn(username=f"p6life{self.stamp}", password="Lifecycle@2026"), s=self.s)
        self.assertEqual(login_access.exception.status_code, 403)

        deactivated = main.update_branch_lifecycle(
            branch_id, main.BranchLifecycleIn(status="deactivated"), ctx=chairman_ctx, s=self.s)
        self.assertEqual(deactivated["status"], "deactivated")
        self.assertIsNotNone(self.s.get(Tenant, tenant_id))
        self.assertIsNotNone(self.s.get(D.Student, student_id))
        self.assertEqual(self.s.query(AuditLog).filter(AuditLog.tenant_id == tenant_id,
                         AuditLog.action == "institute.deactivated").count(), 1)

    def test_onboarding_link_then_activate_allows_development_copy_and_login(self):
        person_id, user_id = f"p6passwordperson{self.stamp}", f"p6passworduser{self.stamp}"
        self.s.add_all([
            Person(id=person_id, tenant_id=TENANT, name="Password Test", email="password-test@example.test", contact=""),
            User(id=user_id, tenant_id=TENANT, person_id=person_id, username=f"p6password{self.stamp}",
                 password_hash=pwhash("placeholder"), status="invited", mfa_enabled=True, office_n=4,
                 role="Principal", scope_level="campus", scope_ref="scope_main_campus"),
        ])
        self.s.commit(); self.ids.extend([person_id, user_id])
        tenant = self.s.get(main.Tenant, TENANT)
        with patch.object(main, "_chairman_branch_user", return_value=(self.s.get(User, user_id), tenant)), \
             patch.object(main, "write_audit"):
            with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
                before = main._branch_user_payload(self.s, self.s.get(User, user_id), tenant)
                self.assertEqual(before["credential_state"], "password_not_created")
                invitation = main.create_branch_account_password(user_id, ctx={"sub": "user_1"}, s=self.s)
                self.assertIn("/onboarding?token=", invitation["onboarding_url"])
                token = invitation["onboarding_url"].split("token=", 1)[1]
                self.assertEqual(main.onboarding_context(token, s=self.s)["username"], f"p6password{self.stamp}")
                completed = main.complete_onboarding(main.OnboardingCompleteIn(token=token, password="Future@2026"), s=self.s)
            self.assertEqual(completed["status"], "invited")
            user = self.s.get(User, user_id)
            self.assertIsNotNone(user.password_created_at)
            self.assertEqual(user.password_hash, pwhash("Future@2026"))
            waiting = main._branch_user_payload(self.s, user, tenant)
            self.assertEqual(waiting["credential_state"], "password_created")
            self.assertNotIn("password_hash", waiting)
            with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
                activated = main.activate_branch_user(user_id, ctx={"sub": "user_1"}, s=self.s)
                self.assertEqual(activated["status"], "active")
                refreshed = main._branch_user_payload(self.s, self.s.get(User, user_id), tenant)
                self.assertEqual(refreshed["credential_state"], "credential_available")
                copied = main.copy_development_branch_password(user_id, ctx={"sub": "user_1"}, s=self.s)
                self.assertEqual(copied, {"password": "Future@2026"})
            login = main.login(main.LoginIn(username=f"p6password{self.stamp}", password="Future@2026"), s=self.s)
            self.assertEqual(login["auth_context"]["tenant_id"], TENANT)
            self.assertEqual(login["auth_context"]["scope_id"], "scope_main_campus")

    def test_academic_catalog_crud_and_course_section_writes_are_tenant_bound(self):
        tenant_a, tenant_b = f"p6catalog_a_{self.stamp}", f"p6catalog_b_{self.stamp}"
        scope_a, scope_b = f"scope_p6catalog_a_{self.stamp}", f"scope_p6catalog_b_{self.stamp}"
        self.s.add_all([
            OrgScope(id=scope_a, tenant_id=tenant_a, level="campus", name="Catalog A Campus"),
            OrgScope(id=scope_b, tenant_id=tenant_b, level="campus", name="Catalog B Campus"),
        ])
        self.s.commit(); self.ids.extend([scope_a, scope_b])
        ctx_a = {**self.principal_ctx, "tenant_id": tenant_a, "scope_ref": scope_a}
        ctx_b = {**self.principal_ctx, "tenant_id": tenant_b, "scope_ref": scope_b}
        dept_a = domain_api.create_department(domain_api.DepartmentIn(code="CATA", name="Catalog A"), ctx=ctx_a, s=self.s)["department"]
        dept_b = domain_api.create_department(domain_api.DepartmentIn(code="CATB", name="Catalog B"), ctx=ctx_b, s=self.s)["department"]
        self.ids.extend([dept_a["id"], dept_b["id"]])
        self.assertEqual([row["id"] for row in domain_api.list_departments(ctx=ctx_a, s=self.s)["departments"]], [dept_a["id"]])
        self.assertEqual([row["id"] for row in domain_api.list_departments(ctx=ctx_b, s=self.s)["departments"]], [dept_b["id"]])
        with self.assertRaises(HTTPException) as update_error:
            domain_api.update_department(dept_a["id"], domain_api.DepartmentIn(code="NOPE", name="Nope"), ctx=ctx_b, s=self.s)
        self.assertEqual(update_error.exception.status_code, 404)
        prog_a = domain_api.create_program(domain_api.ProgramIn(code="CATA-UG", name="Catalog A UG", dept_id=dept_a["id"]), ctx=ctx_a, s=self.s)["program"]
        prog_b = domain_api.create_program(domain_api.ProgramIn(code="CATB-UG", name="Catalog B UG", dept_id=dept_b["id"]), ctx=ctx_b, s=self.s)["program"]
        self.ids.extend([prog_a["id"], prog_b["id"]])
        with self.assertRaises(HTTPException) as program_error:
            domain_api.create_program(domain_api.ProgramIn(code="CROSS-UG", name="Cross Tenant", dept_id=dept_a["id"]), ctx=ctx_b, s=self.s)
        self.assertEqual(program_error.exception.status_code, 404)
        course = domain_api.create_course(domain_api.CourseIn(code="CATB101", title="Tenant B Catalog Course", dept_code="CATB", program_id=prog_b["id"]), ctx=ctx_b, s=self.s)
        self.ids.append(course["id"])
        with self.assertRaises(HTTPException) as course_error:
            domain_api.create_course(domain_api.CourseIn(code="CROSS101", title="Cross Tenant", dept_code="CATA", program_id=prog_a["id"]), ctx=ctx_b, s=self.s)
        self.assertEqual(course_error.exception.status_code, 400)
        section = domain_api.create_section(domain_api.SectionIn(course_id=course["id"], section_code="A"), ctx=ctx_b, s=self.s)
        self.ids.append(section["id"])
        student = domain_api.add_student(domain_api.StudentIn(name="Tenant B Student", roll_no="CATB-001", dept_code="CATB", program_id=prog_b["id"], batch="2026"), ctx=ctx_b, s=self.s)
        self.ids.append(student["id"])
        student_row = self.s.query(D.Student).filter(D.Student.id == student["id"]).one()
        self.assertEqual((student_row.tenant_id, student_row.campus, student_row.dept_id, student_row.program_id), (tenant_b, "Catalog B Campus", dept_b["id"], prog_b["id"]))
        self.assertNotIn(student["id"], [row["id"] for row in domain_api.list_students(ctx=ctx_a, s=self.s)["students"]])
        self.assertEqual([row["id"] for row in domain_api.list_courses(ctx=ctx_b, s=self.s)["courses"]], [course["id"]])
        self.assertEqual([row["id"] for row in domain_api.list_sections(ctx=ctx_b, s=self.s)["sections"]], [section["id"]])

    def test_principal_recruitment_requirements_are_created_and_listed_per_tenant(self):
        tenant_a, tenant_b, tenant_empty = (f"p6jobs_a_{self.stamp}", f"p6jobs_b_{self.stamp}", f"p6jobs_empty_{self.stamp}")
        scope_a, scope_b = f"scope_p6jobs_a_{self.stamp}", f"scope_p6jobs_b_{self.stamp}"
        dept_a, dept_b = f"p6jobs_dept_a_{self.stamp}", f"p6jobs_dept_b_{self.stamp}"
        self.recruitment_tenants.extend([tenant_a, tenant_b, tenant_empty])
        self.s.add_all([
            OrgScope(id=scope_a, tenant_id=tenant_a, level="campus", name="Recruitment A Campus"),
            OrgScope(id=scope_b, tenant_id=tenant_b, level="campus", name="Recruitment B Campus"),
            D.Department(id=dept_a, tenant_id=tenant_a, code="RECA", name="Recruitment A"),
            D.Department(id=dept_b, tenant_id=tenant_b, code="RECB", name="Recruitment B"),
        ])
        self.s.commit(); self.ids.extend([scope_a, scope_b, dept_a, dept_b])
        ctx_a = {**self.principal_ctx, "tenant_id": tenant_a, "scope_ref": scope_a}
        ctx_b = {**self.principal_ctx, "tenant_id": tenant_b, "scope_ref": scope_b}
        ctx_empty = {**self.principal_ctx, "tenant_id": tenant_empty, "scope_ref": f"scope_{tenant_empty}"}

        main_before = self.s.query(D.JobPosting).filter(D.JobPosting.tenant_id == TENANT).count()
        self.assertEqual(domain_api.list_jobs(ctx=ctx_empty, s=self.s)["jobs"], [])

        vacancy_a = domain_api.create_job(domain_api.JobPostingIn(
            title="Tenant A Assistant Professor", dept_id=dept_a, kind="Faculty", openings=2,
            qualification="M.Tech / PhD", status="open"), ctx=ctx_a, s=self.s)["job"]
        vacancy_b = domain_api.create_job(domain_api.JobPostingIn(
            title="Tenant B Accounts Officer", dept_id=dept_b, kind="Administrative", openings=1,
            status="open"), ctx=ctx_b, s=self.s)["job"]
        self.ids.extend([vacancy_a["id"], vacancy_b["id"]])

        stored_a = self.s.get(D.JobPosting, vacancy_a["id"])
        self.assertEqual((stored_a.tenant_id, stored_a.dept_id, stored_a.dept), (tenant_a, dept_a, "Recruitment A"))
        self.assertEqual([row["id"] for row in domain_api.list_jobs(ctx=ctx_a, s=self.s)["jobs"]], [vacancy_a["id"]])
        self.assertEqual([row["id"] for row in domain_api.list_jobs(ctx=ctx_b, s=self.s)["jobs"]], [vacancy_b["id"]])
        self.assertEqual(self.s.query(D.JobPosting).filter(D.JobPosting.tenant_id == TENANT).count(), main_before)
        self.assertEqual(self.s.query(AuditLog).filter(AuditLog.tenant_id == tenant_a,
                         AuditLog.action == "recruitment_requirement.created",
                         AuditLog.entity == f"job_posting:{vacancy_a['id']}").count(), 1)

        with self.assertRaises(HTTPException) as cross_tenant:
            domain_api.create_job(domain_api.JobPostingIn(title="Cross tenant", dept_id=dept_b,
                                  kind="Faculty", openings=1), ctx=ctx_a, s=self.s)
        self.assertEqual(cross_tenant.exception.status_code, 404)
        with self.assertRaises(HTTPException) as unauthorized:
            domain_api.create_job(domain_api.JobPostingIn(title="Blocked", dept_id=dept_a,
                                  kind="Faculty", openings=1),
                                  ctx={**ctx_a, "office_n": 3}, s=self.s)
        self.assertEqual(unauthorized.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
