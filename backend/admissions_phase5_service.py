"""Phase 5 applicant finance, final approval, and atomic conversion services."""
from datetime import datetime, timedelta
import json

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

import domain_models as D
from admissions_service import transition_application
from core import uid, write_audit
from models import Approval, Notification, Person, Role, User, UserRole, WorkflowInstance


ACTIVE_ALLOCATIONS = {"RESERVED", "ALLOCATED"}


def _app(session, ctx, application_id, statuses=None, expected_version=None, lock=False):
    app = (session.query(D.Application).filter_by(id=application_id).with_for_update().first()
           if lock else session.get(D.Application, application_id))
    if not app or app.tenant_id != ctx["tenant_id"]:
        raise HTTPException(404, "Application not found")
    if ctx.get("scope_level") == "campus" and ctx.get("scope_ref") and not ctx["scope_ref"].startswith("scope_") and app.campus != ctx["scope_ref"]:
        raise HTTPException(403, "Application is outside your authorized campus")
    if expected_version is not None and app.status_version != expected_version:
        raise HTTPException(409, "Application changed; reload")
    if statuses and app.current_status not in statuses:
        raise HTTPException(409, "Application is not at the required Phase 5 stage")
    return app


def _office(ctx, allowed):
    if ctx.get("office_n") not in allowed:
        raise HTTPException(403, "Not authorized for this Phase 5 action")


def _accepted_offer_allocation(session, app):
    offer = session.query(D.AdmissionOffer).filter_by(application_id=app.id, status="ACCEPTED").first()
    allocation = session.query(D.AdmissionSeatAllocation).filter(
        D.AdmissionSeatAllocation.application_id == app.id,
        D.AdmissionSeatAllocation.status.in_(ACTIVE_ALLOCATIONS)).first()
    if not offer or not allocation:
        raise HTTPException(409, "An accepted offer and active allocation are required")
    return offer, allocation


def _quota_id(session, app):
    allocation = session.query(D.AdmissionSeatAllocation).filter(
        D.AdmissionSeatAllocation.application_id == app.id,
        D.AdmissionSeatAllocation.status.in_(ACTIVE_ALLOCATIONS)).first()
    pool = session.get(D.AdmissionSeatPool, allocation.seat_pool_id) if allocation else None
    return pool.quota_id if pool else None


def _structure(session, app, structure_id=None):
    if structure_id:
        row = session.get(D.FeeStructure, structure_id)
        if not row or row.tenant_id != app.tenant_id:
            raise HTTPException(404, "Fee structure not found")
        if ((row.academic_year and row.academic_year != (session.get(D.AdmissionCycle, app.cycle_id).academic_year if session.get(D.AdmissionCycle, app.cycle_id) else ""))
                or (row.campus and row.campus != app.campus) or (row.program_id and row.program_id != app.selected_program_id)
                or (row.cycle_program_id and row.cycle_program_id != app.cycle_program_id)
                or (row.quota_id and row.quota_id != _quota_id(session, app))):
            raise HTTPException(422, "Fee structure is outside application scope")
        return row
    cycle = session.get(D.AdmissionCycle, app.cycle_id)
    academic_year = cycle.academic_year if cycle else ""
    quota_id = _quota_id(session, app)
    rows = session.query(D.FeeStructure).filter_by(tenant_id=app.tenant_id, academic_year=academic_year, status="active").all()
    candidates = [r for r in rows if (not r.campus or r.campus == app.campus) and (not r.program_id or r.program_id == app.selected_program_id) and (not r.cycle_program_id or r.cycle_program_id == app.cycle_program_id) and (not r.quota_id or r.quota_id == quota_id)]
    if not candidates:
        raise HTTPException(409, "No active fee structure matches this application")
    return sorted(candidates, key=lambda r: sum(bool(v) for v in (r.campus, r.program_id, r.quota_id, r.cycle_program_id)), reverse=True)[0]


def resolve_fees(session, ctx, application_id, expected_version, structure_id=None, due_at=None):
    _office(ctx, {22})
    app = _app(session, ctx, application_id, {"OFFER_ACCEPTED"}, expected_version)
    _accepted_offer_allocation(session, app)
    structure = _structure(session, app, structure_id)
    existing = session.query(D.ApplicantFeeAssignment).filter_by(application_id=app.id).count()
    if existing:
        raise HTTPException(409, "Fees have already been resolved")
    app = transition_application(session, ctx, app.id, "start_fee_resolution", app.status_version, "Admission fees resolved", skip_capability=True)
    components = session.query(D.FeeStructureComponent).filter_by(structure_id=structure.id).order_by(D.FeeStructureComponent.sort_order).all()
    if not components:
        raise HTTPException(409, "Fee structure has no components")
    for item in components:
        component = session.get(D.FeeComponent, item.component_id)
        amount = float(item.amount or 0)
        resolution = D.AdmissionFeeResolution(id=uid(), tenant_id=app.tenant_id, application_id=app.id,
            resolution_type=component.code if component else "component", approved_amount=amount,
            due_at=due_at, status="resolved", decided_by_user_id=ctx["sub"], notes=component.name if component else "")
        session.add(resolution); session.flush()
        session.add(D.ApplicantFeeAssignment(id=uid(), tenant_id=app.tenant_id, application_id=app.id,
            component_id=item.component_id, component_name=component.name if component else "Fee component",
            amount=max(amount, 0), waived_amount=max(-amount, 0), status="resolved", resolution_id=resolution.id))
    session.commit()
    write_audit(session, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.fee.resolve", f"application:{app.id}", "", "FEE_RESOLUTION_PENDING", structure.id)
    return app


def issue_applicant_invoice(session, ctx, application_id, expected_version, due_date=None):
    _office(ctx, {22, 23})
    app = _app(session, ctx, application_id, expected_version=expected_version)
    existing = session.query(D.FeeInvoice).filter_by(application_id=app.id, invoice_type="admission_fee").first()
    if existing:
        return app, existing, session.query(D.AdmissionChallan).filter_by(invoice_id=existing.id).first()
    if app.current_status != "FEE_RESOLUTION_PENDING":
        raise HTTPException(409, "Application is not at the required Phase 5 stage")
    assignments = session.query(D.ApplicantFeeAssignment).filter_by(application_id=app.id).all()
    if not assignments:
        raise HTTPException(409, "Fee resolution is required before invoicing")
    total = round(sum(float(x.amount or 0) - float(x.waived_amount or 0) for x in assignments), 2)
    due_at = due_date or (datetime.utcnow() + timedelta(days=14))
    invoice = D.FeeInvoice(id=uid(), tenant_id=app.tenant_id, student_id=None, application_id=app.id,
        term=(session.get(D.AdmissionCycle, app.cycle_id).academic_year if session.get(D.AdmissionCycle, app.cycle_id) else "Admission"),
        invoice_type="admission_fee", issued_at=datetime.utcnow(), issued_by_user_id=ctx["sub"], amount=total, paid=0, status="due", due_date=due_at.date())
    session.add(invoice); session.flush()
    challan = D.AdmissionChallan(id=uid(), tenant_id=app.tenant_id, application_id=app.id, invoice_id=invoice.id,
        challan_no=f"CH-{datetime.utcnow().year}-{uid().upper()}", amount=total, due_at=due_at, status="GENERATED")
    invoice.challan_no = challan.challan_no
    for assignment in assignments: assignment.invoice_id = invoice.id
    session.add(challan); session.commit()
    app = transition_application(session, ctx, app.id, "issue_invoice", app.status_version, "Applicant invoice issued", skip_capability=True)
    app = transition_application(session, ctx, app.id, "await_payment", app.status_version, "Awaiting verified payment", skip_capability=True)
    write_audit(session, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.invoice.issue", f"invoice:{invoice.id}", "", "PAYMENT_PENDING", challan.challan_no)
    return app, invoice, challan


def record_applicant_payment(session, ctx, application_id, expected_version, amount, reference, method="challan", challan_id=None):
    _office(ctx, {23})
    app = _app(session, ctx, application_id, {"PAYMENT_PENDING"}, expected_version)
    invoice = session.query(D.FeeInvoice).filter_by(application_id=app.id, invoice_type="admission_fee").first()
    if not invoice or amount <= 0 or amount > max(0, invoice.amount - invoice.paid):
        raise HTTPException(422, "Payment amount is invalid for this invoice")
    if session.query(D.Payment).filter_by(tenant_id=app.tenant_id, reference=reference).first():
        raise HTTPException(409, "Payment reference already exists")
    challan = session.get(D.AdmissionChallan, challan_id) if challan_id else session.query(D.AdmissionChallan).filter_by(invoice_id=invoice.id).first()
    if challan and (challan.application_id != app.id or challan.status not in {"GENERATED", "PENDING"}):
        raise HTTPException(409, "Challan cannot receive this payment")
    payment = D.Payment(id=uid(), tenant_id=app.tenant_id, invoice_id=invoice.id, student_id="", amount=amount,
        method=method, reference=reference, status="RECORDED", recorded_by_user_id=ctx["sub"])
    session.add(payment)
    if challan: challan.status="PENDING"; challan.payment_reference=reference
    session.commit()
    app = transition_application(session, ctx, app.id, "record_payment", app.status_version, "Payment recorded pending Accounts verification", skip_capability=True)
    write_audit(session, ctx["sub"], ctx["sub"], ctx["office_n"], "admission.payment.record", f"payment:{payment.id}", "", "PAYMENT_RECORDED", reference)
    return app, payment


def verify_payment(session, ctx, application_id, payment_id, expected_version, status="VERIFIED", note=""):
    _office(ctx, {23})
    app = _app(session, ctx, application_id, {"PAYMENT_RECORDED"}, expected_version)
    invoice = session.query(D.FeeInvoice).filter_by(application_id=app.id, invoice_type="admission_fee").first()
    payment = session.get(D.Payment, payment_id)
    if not invoice or not payment or payment.invoice_id != invoice.id:
        raise HTTPException(404, "Payment not found for this application")
    if payment.status == "VERIFIED":
        return app, payment
    if status not in {"VERIFIED", "BOUNCED"}:
        raise HTTPException(422, "Unsupported verification status")
    payment.status=status; payment.verified_by_user_id=ctx["sub"]; payment.verified_at=datetime.utcnow(); payment.verification_note=note
    challan=session.query(D.AdmissionChallan).filter_by(invoice_id=invoice.id, payment_reference=payment.reference).first()
    if challan: challan.status="PAID" if status == "VERIFIED" else "BOUNCED"; challan.verified_by_user_id=ctx["sub"]; challan.verified_at=datetime.utcnow()
    if status != "VERIFIED": session.commit(); raise HTTPException(409, "Bounced payments cannot clear an admission")
    invoice.paid=round(sum(float(p.amount or 0) for p in session.query(D.Payment).filter_by(invoice_id=invoice.id,status="VERIFIED").all()),2)
    invoice.status="paid" if invoice.paid >= invoice.amount else "partial"
    if invoice.paid < invoice.amount:
        session.commit(); raise HTTPException(409, "Verified payments do not settle the invoice")
    clearance=session.query(D.AdmissionFinanceClearance).filter_by(application_id=app.id).first() or D.AdmissionFinanceClearance(id=uid(),tenant_id=app.tenant_id,application_id=app.id,invoice_id=invoice.id)
    clearance.accounts_status="VERIFIED"; clearance.accounts_user_id=ctx["sub"]; clearance.updated_at=datetime.utcnow(); session.add(clearance); session.commit()
    app=transition_application(session,ctx,app.id,"verify_accounts",app.status_version,"Accounts verified settled payment",skip_capability=True)
    write_audit(session,ctx["sub"],ctx["sub"],ctx["office_n"],"admission.payment.verify",f"payment:{payment.id}","RECORDED","VERIFIED",note)
    return app,payment


def clear_finance(session, ctx, application_id, expected_version):
    _office(ctx,{22})
    app=_app(session,ctx,application_id,expected_version=expected_version)
    existing=session.query(D.AdmissionFinanceClearance).filter_by(application_id=app.id,finance_status="CLEARED").first()
    if existing: return app,existing
    if app.current_status != "ACCOUNTS_VERIFIED": raise HTTPException(409,"Application is not at the required Phase 5 stage")
    invoice=session.query(D.FeeInvoice).filter_by(application_id=app.id,invoice_type="admission_fee").first()
    if not invoice: raise HTTPException(409,"Applicant invoice is required")
    verified=sum(float(p.amount or 0) for p in session.query(D.Payment).filter_by(invoice_id=invoice.id,status="VERIFIED").all())
    assignments=session.query(D.ApplicantFeeAssignment).filter_by(application_id=app.id).all()
    waived=sum(float(x.waived_amount or 0) for x in assignments); payable=round(sum(float(x.amount or 0)-float(x.waived_amount or 0) for x in assignments),2); balance=round(payable-verified,2)
    if balance > 0: raise HTTPException(409,"Verified payment does not settle the calculated balance")
    row=session.query(D.AdmissionFinanceClearance).filter_by(application_id=app.id).first() or D.AdmissionFinanceClearance(id=uid(),tenant_id=app.tenant_id,application_id=app.id,invoice_id=invoice.id)
    row.accounts_status="VERIFIED";row.finance_status="CLEARED";row.finance_user_id=ctx["sub"];row.total_payable=payable;row.total_paid=verified;row.total_waived=waived;row.balance=balance;row.cleared_at=datetime.utcnow();row.updated_at=datetime.utcnow();session.add(row);session.commit()
    app=transition_application(session,ctx,app.id,"clear_finance",app.status_version,"Finance clearance calculated server-side",skip_capability=True)
    write_audit(session,ctx["sub"],ctx["sub"],ctx["office_n"],"admission.finance.clear",f"application:{app.id}","ACCOUNTS_VERIFIED","FINANCE_CLEARED",str(payable))
    return app,row


def request_final_approval(session,ctx,application_id,expected_version):
    _office(ctx,{15})
    app=_app(session,ctx,application_id,{"FINANCE_CLEARED"},expected_version)
    if not session.query(D.AdmissionFinanceClearance).filter_by(application_id=app.id,finance_status="CLEARED").first(): raise HTTPException(409,"Finance clearance is required")
    app=transition_application(session,ctx,app.id,"request_final_approval",app.status_version,"Final admission approval requested",skip_capability=True)
    workflow=WorkflowInstance(id=uid(),tenant_id=app.tenant_id,process_key="student_admission",label="Final admission",office_n=15,title=f"Final admission {app.application_no}",state="submitted",initiator_id=ctx["sub"],initiator_name=ctx["sub"],current_stage=1,scope_level=ctx.get("scope_level","campus"))
    session.add(workflow);session.add(D.AdmissionWorkflowLink(id=uid(),tenant_id=app.tenant_id,application_id=app.id,workflow_id=workflow.id,purpose="final_admission",status="active"));session.commit()
    write_audit(session,ctx["sub"],ctx["sub"],ctx["office_n"],"admission.final.request",f"application:{app.id}","FINANCE_CLEARED","FINAL_APPROVAL_PENDING",workflow.id)
    return app,workflow


def complete_final_approval(session,ctx,application_id,expected_version):
    _office(ctx,{4})
    app=_app(session,ctx,application_id,{"FINAL_APPROVAL_PENDING"},expected_version)
    link=session.query(D.AdmissionWorkflowLink).filter_by(application_id=app.id,purpose="final_admission",status="active").first(); workflow=session.get(WorkflowInstance,link.workflow_id) if link else None
    approved=workflow and workflow.state in {"approved","executed"}
    approved=approved or bool(workflow and session.query(Approval).filter_by(workflow_id=workflow.id,decision="ALLOW").first())
    if not approved: raise HTTPException(409,"Final admission workflow is not approved")
    app=transition_application(session,ctx,app.id,"approve_final",app.status_version,"Final admission workflow approved",skip_capability=True)
    app=transition_application(session,ctx,app.id,"ready_to_admit",app.status_version,"Ready-to-Admit checklist completed",skip_capability=True)
    write_audit(session,ctx["sub"],ctx["sub"],ctx["office_n"],"admission.final.approve",f"application:{app.id}","FINAL_APPROVAL_PENDING","READY_TO_ADMIT",workflow.id)
    return app


def checklist(session,ctx,application_id):
    app=_app(session,ctx,application_id)
    offer=session.query(D.AdmissionOffer).filter_by(application_id=app.id,status="ACCEPTED").first()
    allocation=session.query(D.AdmissionSeatAllocation).filter(D.AdmissionSeatAllocation.application_id==app.id,D.AdmissionSeatAllocation.status.in_(ACTIVE_ALLOCATIONS)).first()
    docs=session.query(D.ApplicationDocument).filter_by(application_id=app.id,verification_status="verified").count() if hasattr(D,"ApplicationDocument") else 1
    eligibility=app.current_status not in {"INELIGIBLE","WAITLISTED","OFFERED","OFFER_DECLINED","OFFER_EXPIRED"}
    finance=bool(session.query(D.AdmissionFinanceClearance).filter_by(application_id=app.id,finance_status="CLEARED").first())
    link=session.query(D.AdmissionWorkflowLink).filter_by(application_id=app.id,purpose="final_admission",status="active").first()
    workflow=session.get(WorkflowInstance,link.workflow_id) if link else None
    final=bool(workflow and (workflow.state in {"approved","executed"} or session.query(Approval).filter_by(workflow_id=workflow.id,decision="ALLOW").first()))
    conversion=session.query(D.AdmissionConversion).filter_by(application_id=app.id,status="completed").first()
    return {"documents_verified":bool(docs),"eligibility_passed":eligibility,"active_allocation":bool(allocation),"offer_accepted":bool(offer),"finance_cleared":finance,"final_approval_complete":final,"no_existing_conversion":not bool(conversion),"ready":app.current_status=="READY_TO_ADMIT" and bool(finance) and not bool(conversion)}


def convert_to_student(session,ctx,application_id,expected_version):
    _office(ctx,{15})
    app=_app(session,ctx,application_id,expected_version=expected_version,lock=True)
    existing=session.query(D.AdmissionConversion).filter_by(application_id=application_id,status="completed").first()
    if existing: return existing,session.get(D.Student,existing.student_id)
    if app.current_status != "READY_TO_ADMIT": raise HTTPException(409,"Application is not at the required Phase 5 stage")
    checks=checklist(session,ctx,app.id)
    if not checks["ready"]: raise HTTPException(409,"Ready-to-Admit checklist is incomplete")
    try:
        program=session.get(D.Program,app.selected_program_id); cycle=session.get(D.AdmissionCycle,app.cycle_id)
        prefix=f"{(cycle.academic_year if cycle else str(datetime.utcnow().year))[-2:]}{(program.code if program else 'STU').replace('-','')[:6]}"
        roll=f"{prefix}{app.id.upper()[-8:]}"
        person=Person(id=uid(),tenant_id=app.tenant_id,name=app.applicant_name,email=app.email,contact=app.phone or "");session.add(person)
        user=User(id=uid(),tenant_id=app.tenant_id,person_id=person.id,username=f"student-{app.application_no or app.id}",password_hash="pending_activation",office_n=36,role="Student",scope_level="individual",scope_ref="")
        session.add(user);session.flush()
        role=session.query(Role).filter_by(tenant_id=app.tenant_id,office_n=36).first()
        if not role: role=Role(id=uid(),tenant_id=app.tenant_id,office_n=36,name="Student",category="individual");session.add(role);session.flush()
        session.add(UserRole(id=uid(),user_id=user.id,role_id=role.id,org_scope_id=app.tenant_id))
        student=D.Student(id=uid(),tenant_id=app.tenant_id,roll_no=roll,name=app.applicant_name,email=app.email,program_id=app.selected_program_id,dept_id=program.dept_id if program else None,campus=app.campus,batch=cycle.academic_year if cycle else str(datetime.utcnow().year),semester=1,user_id=user.id);session.add(student);session.flush()
        section=session.query(D.Section).filter_by(tenant_id=app.tenant_id,dept_id=student.dept_id).first()
        if not section:
            raise HTTPException(409,"An academic section is required before student conversion")
        session.add(D.Enrollment(id=uid(),tenant_id=app.tenant_id,student_id=student.id,section_id=section.id,status="enrolled"))
        for link in session.query(D.ApplicationGuardian).filter_by(application_id=app.id).all(): session.add(D.StudentGuardian(id=uid(),tenant_id=app.tenant_id,student_id=student.id,guardian_id=link.guardian_id,relationship=link.relationship,is_primary=link.is_primary))
        for invoice in session.query(D.FeeInvoice).filter_by(application_id=app.id).all(): invoice.student_id=student.id
        allocation=session.query(D.AdmissionSeatAllocation).filter(D.AdmissionSeatAllocation.application_id==app.id,D.AdmissionSeatAllocation.status.in_(ACTIVE_ALLOCATIONS)).first()
        if allocation: allocation.status="ALLOCATED"
        conversion=D.AdmissionConversion(id=uid(),tenant_id=app.tenant_id,application_id=app.id,student_id=student.id,user_id=user.id,status="completed",student_identifier=roll,converted_by_user_id=ctx["sub"],converted_at=datetime.utcnow());session.add(conversion)
        app=transition_application(session,ctx,app.id,"enroll",app.status_version,"Atomically converted to student",skip_capability=True,commit=False)
        session.add(Notification(id=uid(),tenant_id=app.tenant_id,user_id=user.id,severity="info",title="Enrollment confirmed",body=f"Your student identifier is {roll}"))
        write_audit(session,ctx["sub"],ctx["sub"],ctx["office_n"],"admission.convert",f"application:{app.id}","READY_TO_ADMIT","ENROLLED",roll,commit=False)
        session.commit(); return conversion,student
    except IntegrityError:
        session.rollback()
        existing=session.query(D.AdmissionConversion).filter_by(application_id=application_id,status="completed").first()
        if existing:
            return existing,session.get(D.Student,existing.student_id)
        raise HTTPException(409,"Conversion conflicted; retry safely")
    except Exception:
        session.rollback(); raise
