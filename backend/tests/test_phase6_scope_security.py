import os
import sys
import unittest
from datetime import date, datetime

from fastapi import HTTPException

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal, TENANT
from models import AuditLog, Delegation, Notification, OrgScope, Person, User
import domain_api
import domain_models as D
import main


class Phase6ScopeSecurityTests(unittest.TestCase):
    campus_ctx = {"sub": "user_3", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "scope_main_campus", "office_n": 3, "auth_level": "mfa"}
    human_campus_ctx = {**campus_ctx, "scope_ref": "Main Campus"}
    principal_ctx = {"sub": "user_4", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "Main Campus", "office_n": 4, "auth_level": "mfa"}
    vc_ctx = {"sub": "user_2", "tenant_id": TENANT, "scope_level": "university", "scope_ref": "scope_univ", "office_n": 2, "auth_level": "mfa"}

    def setUp(self):
        self.s = SessionLocal()
        self.stamp = datetime.utcnow().strftime("%H%M%S%f")
        self.ids = []

    def tearDown(self):
        self.s.rollback()
        self.s.query(Delegation).filter(Delegation.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.FeeInvoice).filter(D.FeeInvoice.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.BudgetLine).filter(D.BudgetLine.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.AcademicCalendarEntry).filter(D.AcademicCalendarEntry.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.StaffMember).filter(D.StaffMember.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(D.Student).filter(D.Student.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(Notification).filter(Notification.user_id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(User).filter(User.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.query(Person).filter(Person.id.in_(self.ids)).delete(synchronize_session=False)
        self.s.commit(); self.s.close()

    def add_student_invoice(self, campus, tenant=TENANT):
        sid, iid = f"p6stu{len(self.ids)}{self.stamp}", f"p6inv{len(self.ids)}{self.stamp}"
        student = D.Student(id=sid, tenant_id=tenant, roll_no=sid[-8:], name=campus,
                            email=f"{sid}@test", campus=campus, batch="2025", semester=1,
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
        self.add_student_invoice("Main Campus")
        north_student, _ = self.add_student_invoice("North Campus")
        main_staff, north_staff = f"p6staffmain{self.stamp}", f"p6staffnorth{self.stamp}"
        self.s.add_all([
            D.StaffMember(id=main_staff, tenant_id=TENANT, emp_id=main_staff[-8:], name="Main", campus="Main Campus", designation="Professor", status="active"),
            D.StaffMember(id=north_staff, tenant_id=TENANT, emp_id=north_staff[-8:], name="North", campus="North Campus", designation="Professor", status="active"),
        ])
        main_budget, north_budget = f"p6budgetmain{self.stamp}", f"p6budgetnorth{self.stamp}"
        self.s.add_all([
            D.BudgetLine(id=main_budget, tenant_id=TENANT, campus="Main Campus", category="Main", allocated=100, spent=10),
            D.BudgetLine(id=north_budget, tenant_id=TENANT, campus="North Campus", category="North", allocated=100, spent=10),
        ])
        self.s.commit(); self.ids.extend([main_staff, north_staff, main_budget, north_budget])
        overview = domain_api.overview(ctx=self.campus_ctx, s=self.s)
        self.assertEqual(overview["stats"]["students"], main_students_before + 1)
        self.assertEqual(overview["stats"]["faculty"], main_staff_before + 1)
        self.assertIsNone(overview["stats"]["courses"])
        staff = domain_api.faculty_staff(page=1, page_size=20, ctx=self.campus_ctx, s=self.s)
        self.assertIn(main_staff, [row["id"] for row in staff["staff"]])
        self.assertNotIn(north_staff, [row["id"] for row in staff["staff"]])
        invoices = domain_api.list_invoices(ctx=self.campus_ctx, s=self.s)
        self.assertIn("Main Campus", [row["name"] for row in invoices["invoices"]])
        self.assertNotIn("North Campus", [row["name"] for row in invoices["invoices"]])
        budget = domain_api.list_budget(ctx=self.campus_ctx, s=self.s)
        self.assertEqual([row["category"] for row in budget["budget"]], ["Main"])

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
        self.assertEqual(domain_api.grievance(ctx=self.human_campus_ctx, s=self.s)["data_status"], "unavailable")

    def test_non_campus_head_scope_semantics_are_unchanged(self):
        self.assertIsNotNone(domain_api.overview(ctx=self.principal_ctx, s=self.s))
        self.assertIsNotNone(domain_api.overview(ctx=self.vc_ctx, s=self.s))

    def test_unowned_grievances_remain_unavailable_and_scoped_assets_audit_are_available(self):
        assets = domain_api.list_assets(ctx=self.campus_ctx, s=self.s)
        grievances = domain_api.grievance(ctx=self.campus_ctx, s=self.s)
        placements = domain_api.placements(ctx=self.campus_ctx, s=self.s)
        audit = main.get_audit(ctx=self.campus_ctx, s=self.s)
        verification = main.verify_audit(ctx=self.campus_ctx, s=self.s)
        self.assertEqual(assets["data_status"], "available")
        self.assertEqual(grievances["data_status"], "unavailable")
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


if __name__ == "__main__":
    unittest.main()
