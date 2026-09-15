import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import administration_models as A
import domain_models as D
import specialist_models as S
from models import Base, Person, User, WorkflowInstance
from workflow_dispatcher import apply_decision


class PrincipalHandoffTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.session.add_all([
            Person(id="principal_person", tenant_id="t_main", name="Principal"),
            Person(id="requester_person", tenant_id="t_main", name="Requester"),
            User(id="principal", tenant_id="t_main", person_id="principal_person", username="principal", office_n=4, scope_level="campus"),
            User(id="requester", tenant_id="t_main", person_id="requester_person", username="requester", office_n=21, scope_level="campus"),
        ])
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def _workflow(self, process_key, source_type, source_id):
        row = WorkflowInstance(id=f"wf-{source_id}", tenant_id="t_main", process_key=process_key,
                               label=process_key, office_n=21, title=process_key,
                               state="under_review", current_stage=2, scope_level="campus",
                               scope_ref="Main Campus", version_no=1, initiator_id="requester",
                               initiator_name="Requester", source_type=source_type, source_id=source_id)
        self.session.add(row)
        return row

    def test_discipline_decision_updates_source_and_outbox(self):
        complaint = D.Complaint(id="case-1", tenant_id="t_main", kind="Discipline", raised_by="requester", subject="Serious case", status="open")
        self.session.add(complaint)
        self._workflow("disciplinary_action", "complaint", complaint.id)
        self.session.flush()
        apply_decision(self.session, self.session.get(WorkflowInstance, "wf-case-1"), "approve", "principal", "Principal")
        self.session.commit()
        self.assertEqual(complaint.status, "resolved")
        self.assertEqual(complaint.decision, "APPROVE")
        self.assertEqual(self.session.query(A.AdministrativeOutboxEvent).count(), 1)

    def test_condonation_decision_updates_source_without_touching_attendance(self):
        request = D.AttendanceCondonationRequest(id="cond-1", tenant_id="t_main", student_id="student-1", section_id="section-1", requested_by="requester", status="submitted")
        self.session.add(request)
        self._workflow("attendance_condonation", "attendance_condonation", request.id)
        self.session.flush()
        apply_decision(self.session, self.session.get(WorkflowInstance, "wf-cond-1"), "approve", "principal", "Principal")
        self.session.commit()
        self.assertEqual(request.status, "APPROVED")
        self.assertIsNone(request.invoice_id)

    def test_procurement_decision_only_activates_requisition(self):
        requisition = S.ProcurementRequisition(id="pr-1", tenant_id="t_main", requirement_id="req-1", status="DRAFT", requisition_no="PR-2026-0001", created_by="requester", updated_by="requester")
        self.session.add(requisition)
        self._workflow("purchase_request", "procurement_requisition", requisition.id)
        self.session.flush()
        apply_decision(self.session, self.session.get(WorkflowInstance, "wf-pr-1"), "approve", "principal", "Principal")
        self.session.commit()
        self.assertEqual(requisition.status, "APPROVED")
        self.assertEqual(requisition.purchase_order_no, "")

    def test_hr_promotion_rejects_past_effective_date(self):
        promotion = S.HRPromotionRequest(id="promo-1", tenant_id="t_main", staff_id="staff-1", proposed_title="Professor", effective_date=datetime.utcnow() - timedelta(days=1), requested_by="requester")
        self.session.add(promotion)
        self._workflow("recruitment", "hr_promotion_request", promotion.id)
        self.session.flush()
        with self.assertRaises(Exception):
            apply_decision(self.session, self.session.get(WorkflowInstance, "wf-promo-1"), "approve", "principal", "Principal")

    def test_targeted_workflow_without_source_reference_fails_closed(self):
        workflow = self._workflow("purchase_request", "", "")
        self.session.flush()
        with self.assertRaises(Exception):
            apply_decision(self.session, workflow, "approve", "principal", "Principal")

    def test_request_final_approval_creates_principal_stage_workflow(self):
        from admissions_phase5_service import request_final_approval

        application = D.Application(
            id="app-2", tenant_id="t_main", applicant_name="Applicant 2",
            application_no="APP-2", campus="Main Campus", current_status="FINANCE_CLEARED", status_version=2,
        )
        clearance = D.AdmissionFinanceClearance(
            id="clearance-2", tenant_id="t_main", application_id=application.id,
            finance_status="CLEARED"
        )
        self.session.add_all([application, clearance])
        self.session.add(User(id="admissions-user", tenant_id="t_main", username="admissions", office_n=15,
                              scope_level="campus", scope_ref="Main Campus"))
        self.session.commit()

        ctx = {"sub": "admissions-user", "tenant_id": "t_main", "office_n": 15,
               "scope_level": "campus", "scope_ref": "Main Campus", "auth_level": "mfa"}
        app, workflow = request_final_approval(self.session, ctx, application.id, 2)

        self.assertEqual(app.current_status, "FINAL_APPROVAL_PENDING")
        self.assertEqual(workflow.current_stage, 3)
        self.assertEqual(workflow.source_type, "application")
        self.assertEqual(workflow.source_id, application.id)

    def test_admission_decision_transitions_application_source(self):
        application = D.Application(id="app-1", tenant_id="t_main", applicant_name="Applicant", application_no="APP-1", campus="Main Campus", current_status="FINAL_APPROVAL_PENDING", status_version=0)
        self.session.add(application)
        self._workflow("student_admission", "application", application.id)
        self.session.get(WorkflowInstance, "wf-app-1").scope_ref = "Main Campus"
        self.session.flush()
        apply_decision(self.session, self.session.get(WorkflowInstance, "wf-app-1"), "approve", "principal", "Principal")
        self.session.commit()
        self.assertEqual(application.current_status, "READY_TO_ADMIT")

    def test_course_registration_decision_updates_existing_enrollment(self):
        student = D.Student(id="student-reg", tenant_id="t_main", name="Student", campus="Main Campus")
        enrollment = D.Enrollment(id="enr-reg", tenant_id="t_main", student_id=student.id, section_id="section-1", status="requested")
        self.session.add_all([student, enrollment])
        self._workflow("course_registration", "enrollment", enrollment.id)
        workflow = self.session.get(WorkflowInstance, "wf-enr-reg")
        workflow.current_stage = 4
        workflow.scope_ref = "Main Campus"
        self.session.flush()
        apply_decision(self.session, workflow, "approve", "principal", "Principal")
        self.session.commit()
        self.assertEqual(enrollment.status, "enrolled")


if __name__ == "__main__":
    unittest.main()
