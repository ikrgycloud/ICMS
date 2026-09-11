import os
import sys
import unittest
from datetime import datetime
from unittest.mock import patch
from sqlalchemy import select


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal, TENANT
from models import (AuditLog, AuthorityMembership, BranchOrganization, Notification,
                    OnboardingInvite, OrgScope, Person, Role, Tenant, User, UserRole,
                    WorkflowInstance)
import domain_models as D
import main


class NewTenantCleanProvisioningTests(unittest.TestCase):
    """A branch provision must create setup only, never operational records."""

    def setUp(self):
        self.s = SessionLocal()
        self.stamp = datetime.utcnow().strftime("%H%M%S%f")
        self.tenant_ids = []
        self.main_audit_ids = []

    def tearDown(self):
        self.s.rollback()
        if self.tenant_ids:
            # Provisioning is expected to leave every operational table empty.
            # These defensive cleanups keep a failed test from retaining its
            # isolated temporary tenant in the shared development database.
            report_ids = select(D.CampusReport.id).filter(D.CampusReport.tenant_id.in_(self.tenant_ids))
            self.s.query(D.CampusReportSnapshot).filter(D.CampusReportSnapshot.report_id.in_(report_ids)).delete(synchronize_session=False)
            for model in (
                D.StudentIdentityCard, D.StudentCourseViewPreference, D.StudentCalendarEvent,
                D.StudentSubjectResult, D.Mark, D.ExamSeatAssignment, D.ExamScheduleHistory,
                D.ExamScheduleEntry, D.ResultSheet, D.Assessment, D.AttendanceRecord,
                D.Enrollment, D.Payment, D.FeeInvoice, D.BookLoan, D.Book,
                D.HostelAllocation, D.HostelRoom, D.TransportRoute, D.LeaveRequest,
                D.PlacementDrive, D.ResearchProject, D.Complaint, D.EscalationEvent,
                D.EscalationRecord, D.RiskRecord, D.CampusReport,
                D.GovernanceComplianceMetric, D.GovernancePerformanceMetric,
                D.GovernanceDashboardSnapshot, D.Section, D.Course, D.Student,
                D.StaffMember, D.Program, D.Department, D.Application,
            ):
                self.s.query(model).filter(model.tenant_id.in_(self.tenant_ids)).delete(synchronize_session=False)
            self.s.query(WorkflowInstance).filter(WorkflowInstance.tenant_id.in_(self.tenant_ids)).delete(synchronize_session=False)
            self.s.query(Notification).filter(Notification.tenant_id.in_(self.tenant_ids)).delete(synchronize_session=False)
            self.s.query(OnboardingInvite).filter(OnboardingInvite.tenant_id.in_(self.tenant_ids)).delete(synchronize_session=False)
            self.s.query(AuditLog).filter(AuditLog.tenant_id.in_(self.tenant_ids)).delete(synchronize_session=False)
            role_ids = select(Role.id).filter(Role.tenant_id.in_(self.tenant_ids))
            self.s.query(UserRole).filter(UserRole.role_id.in_(role_ids)).delete(synchronize_session=False)
            self.s.query(AuthorityMembership).filter(AuthorityMembership.tenant_id.in_(self.tenant_ids)).delete(synchronize_session=False)
            self.s.query(User).filter(User.tenant_id.in_(self.tenant_ids)).delete(synchronize_session=False)
            self.s.query(Person).filter(Person.tenant_id.in_(self.tenant_ids)).delete(synchronize_session=False)
            self.s.query(Role).filter(Role.tenant_id.in_(self.tenant_ids)).delete(synchronize_session=False)
            self.s.query(BranchOrganization).filter(BranchOrganization.tenant_id.in_(self.tenant_ids)).delete(synchronize_session=False)
            self.s.query(OrgScope).filter(OrgScope.tenant_id.in_(self.tenant_ids)).delete(synchronize_session=False)
            self.s.query(Tenant).filter(Tenant.id.in_(self.tenant_ids)).delete(synchronize_session=False)
        if self.main_audit_ids:
            self.s.query(AuditLog).filter(AuditLog.id.in_(self.main_audit_ids)).delete(synchronize_session=False)
        self.s.commit()
        self.s.close()

    def _provision(self, suffix):
        code = f"clean_{suffix}_{self.stamp[-6:]}"
        response = main.provision_branch(
            main.BranchProvisionIn(
                name=f"Clean Tenant {suffix.upper()} {self.stamp[-6:]}",
                code=code,
                location="Temporary test branch",
                principal=main.BranchLeaderIn(name=f"Clean {suffix} Principal", email="", username=f"{code}_principal"),
                campus_head=main.BranchLeaderIn(name=f"Clean {suffix} Campus Head", email="", username=f"{code}_campus_head"),
                provision_all_offices=False,
            ),
            ctx={"sub": "user_1", "office_n": 1}, s=self.s,
        )
        self.tenant_ids.append(response["branch"]["tenant_id"])
        self.main_audit_ids.append(response["audit_reference"])
        return response

    def _operational_counts(self, tenant_id):
        models = {
            "departments": D.Department, "programs": D.Program, "students": D.Student,
            "staff": D.StaffMember, "courses": D.Course, "sections": D.Section,
            "attendance": D.AttendanceRecord, "assessments": D.Assessment,
            "examinations": D.ExamScheduleEntry, "admissions": D.Application,
            "invoices": D.FeeInvoice, "payments": D.Payment, "books": D.Book,
            "loans": D.BookLoan, "hostel_rooms": D.HostelRoom,
            "hostel_allocations": D.HostelAllocation, "transport_routes": D.TransportRoute,
            "leave_requests": D.LeaveRequest, "placements": D.PlacementDrive,
            "research_projects": D.ResearchProject, "complaints": D.Complaint,
            "risks": D.RiskRecord, "escalations": D.EscalationRecord,
            "governance_snapshots": D.GovernanceDashboardSnapshot,
            "governance_compliance_metrics": D.GovernanceComplianceMetric,
            "governance_performance_metrics": D.GovernancePerformanceMetric,
            "reports": D.CampusReport,
            "workflows": WorkflowInstance,
        }
        return {name: self.s.query(model).filter(model.tenant_id == tenant_id).count()
                for name, model in models.items()}

    def test_every_fresh_branch_starts_with_infrastructure_and_no_operational_data(self):
        main_counts_before = {
            "students": self.s.query(D.Student).filter(D.Student.tenant_id == TENANT).count(),
            "staff": self.s.query(D.StaffMember).filter(D.StaffMember.tenant_id == TENANT).count(),
            "courses": self.s.query(D.Course).filter(D.Course.tenant_id == TENANT).count(),
            "sections": self.s.query(D.Section).filter(D.Section.tenant_id == TENANT).count(),
            "invoices": self.s.query(D.FeeInvoice).filter(D.FeeInvoice.tenant_id == TENANT).count(),
            "books": self.s.query(D.Book).filter(D.Book.tenant_id == TENANT).count(),
            "workflows": self.s.query(WorkflowInstance).filter(WorkflowInstance.tenant_id == TENANT).count(),
        }
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            branch_a, branch_b = self._provision("a"), self._provision("b")

        for result in (branch_a, branch_b):
            tenant_id = result["branch"]["tenant_id"]
            self.assertTrue(tenant_id.startswith("tenant_clean_"))
            self.assertIsNotNone(self.s.get(Tenant, tenant_id))
            self.assertEqual(self.s.query(BranchOrganization).filter(BranchOrganization.tenant_id == tenant_id).count(), 1)
            self.assertEqual(self.s.query(OrgScope).filter(OrgScope.tenant_id == tenant_id).count(), 3)
            self.assertEqual(self.s.query(User).filter(User.tenant_id == tenant_id).count(), 2)
            self.assertEqual(self.s.query(Role).filter(Role.tenant_id == tenant_id).count(), 2)
            self.assertEqual(self.s.query(AuthorityMembership).filter(AuthorityMembership.tenant_id == tenant_id).count(), 2)
            self.assertEqual(self.s.query(Notification).filter(Notification.tenant_id == tenant_id).count(), 2)
            self.assertGreaterEqual(self.s.query(AuditLog).filter(AuditLog.tenant_id == tenant_id).count(), 2)
            counts = self._operational_counts(tenant_id)
            self.assertEqual(counts, {key: 0 for key in counts})

        self.assertEqual(main_counts_before, {
            "students": self.s.query(D.Student).filter(D.Student.tenant_id == TENANT).count(),
            "staff": self.s.query(D.StaffMember).filter(D.StaffMember.tenant_id == TENANT).count(),
            "courses": self.s.query(D.Course).filter(D.Course.tenant_id == TENANT).count(),
            "sections": self.s.query(D.Section).filter(D.Section.tenant_id == TENANT).count(),
            "invoices": self.s.query(D.FeeInvoice).filter(D.FeeInvoice.tenant_id == TENANT).count(),
            "books": self.s.query(D.Book).filter(D.Book.tenant_id == TENANT).count(),
            "workflows": self.s.query(WorkflowInstance).filter(WorkflowInstance.tenant_id == TENANT).count(),
        })


if __name__ == "__main__":
    unittest.main()
