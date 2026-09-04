# -*- coding: utf-8 -*-
"""
Portal API - persona-scoped views.

Where domain_api.py serves administrative module data, this router serves the
signed-in person's own world.
"""
from datetime import date, timedelta
import base64
import hashlib
import hmac
from html import escape
from io import BytesIO
import json
import os
from urllib import request as urlrequest
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func
from datetime import date, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, desc, or_
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core import auth, db, uid, write_audit
from database import TENANT, office
import domain_models as D
from models import User, Notification

router = APIRouter(prefix="/api/portal")

PORTAL_TODAY = date(2026, 8, 25)
PORTAL_NOW = datetime(2026, 8, 25, 16, 15)
GST_RATE = 0.18


def _razorpay_configured():
    key = os.environ.get("RAZORPAY_KEY_ID", "")
    secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    if not key or not secret:
        raise HTTPException(503, "Online payments are not configured")
    return key, secret


def _razorpay_request(path, payload):
    key, secret = _razorpay_configured()
    token = base64.b64encode(f"{key}:{secret}".encode()).decode()
    req = urlrequest.Request(f"https://api.razorpay.com/v1{path}", data=json.dumps(payload).encode(), method="POST",
                             headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"})
    try:
        with urlrequest.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode())
    except Exception:
        raise HTTPException(502, "Could not create the Razorpay payment order")


def _gst(amount):
    return round(float(amount or 0) * GST_RATE, 2)


def _invoice_display_amounts(invoice, payment_total=None):
    """Return the authoritative fee-ledger values shown in student/parent portals.

    ``invoice.paid`` is updated by every confirmed Finance Manager payment.  Do
    not derive this from payment-history amounts: gateway rows can include GST
    while the invoice ledger is stored as the fee amount, causing a valid cash
    payment to appear not to reduce the student's balance.
    """
    base = round(float(invoice.amount or 0), 2)
    paid = round(min(float(invoice.paid or 0), base), 2)
    gst_amount = 0.0
    total = base
    balance = round(max(total - paid, 0), 2)
    return {"base_amount": base, "gst_rate": int(GST_RATE * 100), "gst_amount": gst_amount,
            "amount": total, "paid": paid, "balance": balance}


def _settle_payment(s, payment, actor=""):
    """Idempotently allocate a confirmed payment and create its official receipt."""
    if payment.status not in {"success", "cleared"}:
        raise HTTPException(409, "Only successful or cleared payments can be allocated")
    existing = s.query(D.PaymentAllocation).filter(D.PaymentAllocation.payment_id == payment.id).first()
    invoice = s.get(D.FeeInvoice, payment.invoice_id)
    if not invoice or invoice.student_id != payment.student_id:
        raise HTTPException(409, "Payment and invoice relationship is invalid")
    if not existing:
        available = round(max(float(invoice.amount or 0) - float(invoice.paid or 0), 0), 2)
        allocation = min(round(float(payment.amount or 0), 2), available)
        if allocation <= 0:
            raise HTTPException(409, "There is no outstanding balance to allocate")
        s.add(D.PaymentAllocation(id=uid(), tenant_id=TENANT, payment_id=payment.id,
                                  invoice_id=invoice.id, student_id=invoice.student_id, amount=allocation))
        invoice.paid = round(float(invoice.paid or 0) + allocation, 2)
        invoice.status = "paid" if invoice.paid >= invoice.amount else "partial"
        if payment.challan_id:
            challan = s.get(D.FeeChallan, payment.challan_id)
            if challan:
                challan.status = "PAID" if invoice.paid >= invoice.amount else "PARTIALLY_PAID"
                challan.updated_at = datetime.utcnow()
    receipt = s.query(D.PaymentReceipt).filter(D.PaymentReceipt.payment_id == payment.id).first()
    if not receipt:
        receipt = D.PaymentReceipt(id=uid(), tenant_id=TENANT,
            receipt_number=f"RCP-{datetime.utcnow():%Y}-{payment.id[:8].upper()}", payment_id=payment.id,
            invoice_id=payment.invoice_id, student_id=payment.student_id, challan_id=payment.challan_id)
        s.add(receipt)
    return invoice


def _receipt_pdf(student, invoice, s, payment_id=None):
    """Render a flow-based A4 receipt; tables calculate wrapping, row height and page splits."""
    dark_blue = colors.HexColor("#0f3564")
    muted = colors.HexColor("#526273")
    border = colors.HexColor("#d5dce6")
    pale_blue = colors.HexColor("#eef5fc")
    page_width, _ = A4
    content_width = page_width - (36 * mm)
    styles = getSampleStyleSheet()
    label = ParagraphStyle("receipt-label", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10, textColor=muted, spaceAfter=3)
    value = ParagraphStyle("receipt-value", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.5, leading=12, textColor=colors.black, splitLongWords=True)
    amount = ParagraphStyle("receipt-amount", parent=value, alignment=TA_RIGHT)
    section = ParagraphStyle("receipt-section", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=dark_blue, spaceBefore=2, spaceAfter=7)
    header_left = ParagraphStyle("receipt-header-left", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=20, leading=23, textColor=colors.white)
    header_subtitle = ParagraphStyle("receipt-header-subtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=12, leading=15, textColor=colors.white)
    header_right = ParagraphStyle("receipt-header-right", parent=styles["Normal"], fontName="Helvetica", fontSize=10, leading=14, alignment=TA_RIGHT, textColor=colors.white)
    footer = ParagraphStyle("receipt-footer", parent=styles["Normal"], fontSize=8, leading=10, textColor=muted, alignment=TA_LEFT)

    def p(text, style=value):
        return Paragraph(escape(str(text if text not in (None, "") else "-")), style)

    def field(field_label, field_value):
        return [p(field_label, label), p(field_value, value)]

    def money(number):
        return f"INR {float(number or 0):,.2f}"

    program = s.get(D.Program, student.program_id)
    department = s.get(D.Department, student.dept_id)
    structure = s.get(D.FeeStructure, invoice.fee_structure_id) if invoice.fee_structure_id else None
    academic_year = s.get(D.AcademicYear, structure.academic_year_id) if structure else None
    semester = s.get(D.Semester, structure.semester_id) if structure else None
    invoice_payments = s.query(D.Payment).filter(D.Payment.invoice_id == invoice.id).order_by(desc(D.Payment.at)).all()
    payment = next((row for row in invoice_payments if row.id == payment_id), None) if payment_id else (invoice_payments[0] if invoice_payments else None)
    # A receipt represents one transaction.  Older receipt links without a
    # payment ID use the latest successful transaction instead of invoice total.
    received_amount = float(payment.amount or 0) if payment else float(invoice.paid or 0)
    # Keep a receipt transaction-specific.  The invoice can have earlier payments,
    # but this document must only acknowledge the payment selected above.
    outstanding_balance = max(float(invoice.amount or 0) - float(invoice.paid or 0), 0)
    payment_id = payment.reference if payment else "Not available"
    payment_date = payment.at.strftime("%d %b %Y, %I:%M %p") if payment and payment.at else "Not available"

    # A receipt acknowledges what was received, not the full original fee demand.
    # This makes partial-payment receipts unambiguous.
    fee_rows = [(f"Payment received against {invoice.term or 'fee invoice'}", received_amount)]

    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm, bottomMargin=18 * mm, title="ICMS Fee Payment Receipt")
    story = []
    header = Table([[Paragraph("ICMS", header_left), Paragraph("Official Receipt<br/><b>Status: " + escape((invoice.status or "paid").upper()) + "</b>", header_right)], [Paragraph("FEE PAYMENT RECEIPT", header_subtitle), ""]], colWidths=[content_width * .62, content_width * .38])
    header.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), dark_blue), ("BOX", (0, 0), (-1, -1), 1, dark_blue), ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.extend([header, Spacer(1, 16)])

    story.append(Paragraph("PAYMENT DETAILS", section))
    payment_details = Table([[field("Receipt / Invoice No.", invoice.id), field("Payment ID", payment_id), field("Payment Date", payment_date)]], colWidths=[content_width * .34, content_width * .33, content_width * .33])
    payment_details.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 9), ("LINEBELOW", (0, 0), (-1, -1), .7, border)]))
    story.extend([payment_details, Spacer(1, 16)])

    story.append(Paragraph("STUDENT &amp; ACADEMIC DETAILS", section))
    programme = f"{program.code} - {program.name}" if program else "-"
    detail_rows = [
        [field("Student Name", student.name), field("Roll Number", student.roll_no), field("Programme / Branch", programme)],
        [field("Department", department.name if department else "-"), field("Academic Year", academic_year.name if academic_year else "-"), field("Semester", semester.name if semester else invoice.term)],
        [field("Batch", student.batch), field("Section", student.section), field("Payment Method", payment.method.upper() if payment else "ONLINE")],
    ]
    details_table = Table(detail_rows, colWidths=[content_width * .32, content_width * .32, content_width * .36])
    details_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), .6, border), ("BACKGROUND", (0, 0), (-1, -1), colors.white), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    story.extend([details_table, Spacer(1, 16)])

    story.append(Paragraph("PAYMENT RECEIVED", section))
    fee_data = [[p("Payment description", ParagraphStyle("fee-header", parent=value, textColor=colors.white)), p("Received amount", ParagraphStyle("fee-header-right", parent=amount, textColor=colors.white))]]
    for component, fee_amount in fee_rows:
        fee_data.append([p(component, ParagraphStyle("fee-cell", parent=value, fontName="Helvetica", fontSize=9, leading=12)), p(money(fee_amount), amount)])
    fee_table = Table(fee_data, colWidths=[content_width * .72, content_width * .28], repeatRows=1)
    fee_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), dark_blue), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), .6, border), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fc")])]))
    story.extend([fee_table, Spacer(1, 14)])

    summary_rows = [[p("Amount received", ParagraphStyle("paid-label", parent=value, textColor=dark_blue)), p(money(received_amount), ParagraphStyle("paid-amount", parent=amount, textColor=dark_blue))], [p("Outstanding balance", value), p(money(outstanding_balance), amount)]]
    summary = Table(summary_rows, colWidths=[content_width * .68, content_width * .32], hAlign="RIGHT")
    summary.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), pale_blue), ("BOX", (0, 0), (-1, -1), .7, border), ("INNERGRID", (0, 0), (-1, -1), .5, border), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story.extend([summary, Spacer(1, 20), Paragraph("Generated by ICMS<br/>Computer generated receipt", footer)])

    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(border)
        canvas.line(doc.leftMargin, 13 * mm, page_width - doc.rightMargin, 13 * mm)
        canvas.setFillColor(muted)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawRightString(page_width - doc.rightMargin, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return output.getvalue()


def _receipt_response(student, invoice_id, s, payment_id=None):
    invoice = s.get(D.FeeInvoice, invoice_id)
    if not invoice or invoice.student_id != student.id:
        raise HTTPException(404, "Fee invoice not found")
    if payment_id:
        payment = s.get(D.Payment, payment_id)
        if not payment or payment.invoice_id != invoice.id or payment.student_id != student.id:
            raise HTTPException(404, "Payment receipt not found")
    return Response(_receipt_pdf(student, invoice, s, payment_id), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="ICMS-receipt-{student.roll_no}-{invoice.id}.pdf"'})


def _generate_challan_number(s):
    year = date.today().year
    prefix = f"CH-{year}"
    last = s.query(D.FeeChallan).filter(D.FeeChallan.challan_number.like(f"{prefix}-%")).order_by(desc(D.FeeChallan.created_at)).first()
    next_no = 1
    if last and last.challan_number:
        try:
            next_no = int(last.challan_number.rsplit("-", 1)[-1]) + 1
        except ValueError:
            next_no = 1
    return f"{prefix}-{next_no:06d}"


def _challan_pdf(student, invoice, challan, s):
    dark_blue = colors.HexColor("#0f3564")
    muted = colors.HexColor("#526273")
    border = colors.HexColor("#d5dce6")
    pale_blue = colors.HexColor("#eef5fc")
    page_width, _ = A4
    content_width = page_width - (36 * mm)
    styles = getSampleStyleSheet()
    label = ParagraphStyle("challan-label", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10, textColor=muted, spaceAfter=3)
    value = ParagraphStyle("challan-value", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.5, leading=12, textColor=colors.black, splitLongWords=True)
    amount = ParagraphStyle("challan-amount", parent=value, alignment=TA_RIGHT)
    section = ParagraphStyle("challan-section", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=dark_blue, spaceBefore=2, spaceAfter=7)
    header_left = ParagraphStyle("challan-header-left", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=20, leading=23, textColor=colors.white)
    header_subtitle = ParagraphStyle("challan-header-subtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=12, leading=15, textColor=colors.white)
    header_right = ParagraphStyle("challan-header-right", parent=styles["Normal"], fontName="Helvetica", fontSize=10, leading=14, alignment=TA_RIGHT, textColor=colors.white)
    footer = ParagraphStyle("challan-footer", parent=styles["Normal"], fontSize=8, leading=10, textColor=muted, alignment=TA_LEFT)
    program = s.get(D.Program, student.program_id)
    department = s.get(D.Department, student.dept_id)
    structure = s.get(D.FeeStructure, invoice.fee_structure_id) if invoice.fee_structure_id else None
    academic_year = s.get(D.AcademicYear, structure.academic_year_id) if structure else None
    semester = s.get(D.Semester, structure.semester_id) if structure else None

    def p(text, style=value):
        return Paragraph(escape(str(text if text not in (None, "") else "-")), style)
    def field(label_text, field_value):
        return [p(label_text, label), p(field_value, value)]
    def money(number):
        return f"INR {float(number or 0):,.2f}"

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm, bottomMargin=18 * mm, title="ICMS Fee Payment Challan")
    story = []
    header = Table([[Paragraph("ICMS", header_left), Paragraph("FEE PAYMENT CHALLAN<br/><b>Status: " + escape((challan.status or "GENERATED").upper()) + "</b>", header_right)], [Paragraph("Institutional Fee Collection", header_subtitle), ""]], colWidths=[content_width * .62, content_width * .38])
    header.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), dark_blue), ("BOX", (0, 0), (-1, -1), 1, dark_blue), ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.extend([header, Spacer(1, 14)])
    story.append(Paragraph("STUDENT DETAILS", section))
    programme = f"{program.code} - {program.name}" if program else "-"
    detail_rows = [
        [field("Challan Number", challan.challan_number), field("Invoice Number", invoice.invoice_number or invoice.id), field("Generated Date", challan.issue_date.isoformat() if challan.issue_date else date.today().isoformat())],
        [field("Student Name", student.name), field("Roll Number", student.roll_no), field("Student ID", student.id)],
        [field("Programme", programme), field("Department", department.name if department else "-"), field("Academic Year", academic_year.name if academic_year else "-")],
        [field("Semester", semester.name if semester else str(student.semester or "-")), field("Batch", student.batch or "-"), field("Section", student.section or "-")],
    ]
    details_table = Table(detail_rows, colWidths=[content_width * .33, content_width * .33, content_width * .34])
    details_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), .6, border), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    story.extend([details_table, Spacer(1, 12)])
    story.append(Paragraph("FEE BREAKDOWN", section))
    fee_data = [[p("Fee component", ParagraphStyle("fee-header", parent=value, textColor=colors.white)), p("Amount", ParagraphStyle("fee-header-right", parent=amount, textColor=colors.white))], [p("Outstanding amount", value), p(money(float(challan.amount or 0)), amount)]]
    fee_table = Table(fee_data, colWidths=[content_width * .72, content_width * .28], repeatRows=1)
    fee_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), dark_blue), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), .6, border), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story.extend([fee_table, Spacer(1, 12)])
    summary_rows = [[p("Gross Amount", value), p(money(float(invoice.gross_amount or invoice.amount or 0)), amount)], [p("Scholarship", value), p(money(float(invoice.scholarship_amount or 0)), amount)], [p("Waiver", value), p(money(float(invoice.waiver_amount or 0)), amount)], [p("Paid Amount", value), p(money(float(invoice.paid or 0)), amount)], [p("Outstanding", value), p(money(max(float(invoice.amount or 0) - float(invoice.paid or 0), 0)), amount)], [p("Challan Amount", ParagraphStyle("challan-total", parent=value, textColor=dark_blue)), p(money(float(challan.amount or 0)), ParagraphStyle("challan-total-amount", parent=amount, textColor=dark_blue))]]
    summary = Table(summary_rows, colWidths=[content_width * .68, content_width * .32], hAlign="RIGHT")
    summary.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), pale_blue), ("BOX", (0, 0), (-1, -1), .7, border), ("INNERGRID", (0, 0), (-1, -1), .5, border), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story.extend([summary, Spacer(1, 14)])
    story.append(Paragraph("PAYMENT INFORMATION", section))
    note = Paragraph("THIS CHALLAN IS NOT A PAYMENT RECEIPT.<br/>An official receipt will be generated only after successful payment verification.", footer)
    story.extend([note, Spacer(1, 8)])
    story.append(Paragraph("Status: " + (challan.status or "GENERATED"), value))
    def draw_footer(canvas, doc):
        canvas.saveState(); canvas.setStrokeColor(border); canvas.line(doc.leftMargin, 13 * mm, page_width - doc.rightMargin, 13 * mm); canvas.setFillColor(muted); canvas.setFont("Helvetica", 7.5); canvas.drawRightString(page_width - doc.rightMargin, 8 * mm, f"Page {doc.page}"); canvas.restoreState()
    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return output.getvalue()


@router.post("/student/fees/challans")
def create_student_challan(body: dict, ctx=Depends(auth), s=Depends(db)):
    student = _student_or_404(s, ctx)
    invoice_id = str(body.get("invoice_id") or "")
    invoice = s.get(D.FeeInvoice, invoice_id)
    if not invoice or invoice.student_id != student.id:
        raise HTTPException(404, "Fee invoice not found")
    balance = max(float(invoice.amount or 0) - float(invoice.paid or 0), 0)
    if balance <= 0:
        raise HTTPException(409, "This invoice is already fully paid")
    amount = float(body.get("amount") or balance)
    if amount <= 0 or amount > balance:
        raise HTTPException(422, "Challan amount must be greater than zero and not exceed the outstanding balance")
    existing = s.query(D.FeeChallan).filter(D.FeeChallan.invoice_id == invoice_id, D.FeeChallan.status.in_("GENERATED,PENDING,PARTIALLY_PAID".split(","))).first()
    if existing:
        existing.amount = amount
        existing.issue_date = date.today()
        existing.due_date = existing.due_date or (date.today() + timedelta(days=7))
        existing.updated_at = datetime.utcnow()
        s.commit()
        return {"status": "ok", "challan": {"id": existing.id, "challan_number": existing.challan_number, "invoice_id": existing.invoice_id, "amount": existing.amount, "issue_date": existing.issue_date.isoformat() if existing.issue_date else "", "due_date": existing.due_date.isoformat() if existing.due_date else "", "status": existing.status}}
    challan_number = _generate_challan_number(s)
    challan = D.FeeChallan(id=uid(), tenant_id=TENANT, challan_number=challan_number, student_id=student.id, invoice_id=invoice.id,
                          amount=amount, issue_date=date.today(), due_date=date.today() + timedelta(days=7), status="GENERATED",
                          created_by=ctx["sub"], payment_reference=f"{invoice.id}:{challan_number}")
    s.add(challan)
    s.commit()
    write_audit(s, ctx["sub"], student.name, ctx["office_n"], "fee.challan.generated", f"challan:{challan.id}", "", "GENERATED", f"Generated challan {challan_number}")
    return {"status": "ok", "challan": {"id": challan.id, "challan_number": challan.challan_number, "invoice_id": challan.invoice_id, "amount": challan.amount, "issue_date": challan.issue_date.isoformat() if challan.issue_date else "", "due_date": challan.due_date.isoformat() if challan.due_date else "", "status": challan.status}}


@router.get("/student/fees/challans/{challan_id}/pdf")
def student_challan_pdf(challan_id: str, ctx=Depends(auth), s=Depends(db)):
    student = _student_or_404(s, ctx)
    challan = s.get(D.FeeChallan, challan_id)
    if not challan or challan.student_id != student.id:
        raise HTTPException(404, "Challan not found")
    invoice = s.get(D.FeeInvoice, challan.invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    return Response(_challan_pdf(student, invoice, challan, s), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="ICMS-challan-{challan.challan_number}.pdf"'})


@router.get("/student/fees/challans")
def student_challans(ctx=Depends(auth), s=Depends(db)):
    student = _student_or_404(s, ctx)
    rows = s.query(D.FeeChallan).filter(D.FeeChallan.student_id == student.id).order_by(desc(D.FeeChallan.created_at)).all()
    return {"challans": [{"id": row.id, "challan_number": row.challan_number, "invoice_id": row.invoice_id, "amount": row.amount, "issue_date": row.issue_date.isoformat() if row.issue_date else "", "due_date": row.due_date.isoformat() if row.due_date else "", "status": row.status} for row in rows]}


class OfflineProofIn(BaseModel):
    challan_id: str
    method: str
    amount: float
    reference_number: str
    transaction_date: date
    bank_name: str = ""
    remarks: str = ""
    file_name: str = ""
    file_type: str = ""
    file_data: str = ""  # base64; deployments should replace this with configured object storage.


@router.post("/student/fees/offline-proofs")
def submit_offline_proof(body: OfflineProofIn, ctx=Depends(auth), s=Depends(db)):
    student = _student_or_404(s, ctx)
    challan = s.get(D.FeeChallan, body.challan_id)
    allowed = {"bank_transfer", "neft", "rtgs", "imps", "cheque", "dd"}
    method = (body.method or "").lower()
    if not challan or challan.student_id != student.id or method not in allowed:
        raise HTTPException(404, "Eligible challan not found")
    invoice = s.get(D.FeeInvoice, challan.invoice_id)
    balance = max(float(invoice.amount or 0) - float(invoice.paid or 0), 0) if invoice else 0
    if body.amount <= 0 or body.amount > min(balance, float(challan.amount or 0)):
        raise HTTPException(422, "Payment amount must not exceed the challan or outstanding balance")
    if len(body.file_data or "") > 7_000_000 or body.file_type.lower() not in {"", "application/pdf", "image/jpeg", "image/png"}:
        raise HTTPException(422, "Proof must be a PDF, JPEG, or PNG under 5 MB")
    status = "pending_clearance" if method in {"cheque", "dd"} else "pending_verification"
    payment = D.Payment(id=uid(), tenant_id=TENANT, invoice_id=invoice.id, challan_id=challan.id,
                        student_id=student.id, amount=body.amount, method=method,
                        reference=body.reference_number.strip(), status=status, remarks=body.remarks.strip())
    s.add(payment); s.flush()
    s.add(D.PaymentProof(id=uid(), tenant_id=TENANT, payment_id=payment.id,
          reference_number=payment.reference, transaction_date=body.transaction_date, bank_name=body.bank_name.strip(),
          remarks=body.remarks.strip(), file_name=body.file_name[:255], file_type=body.file_type, file_data=body.file_data))
    challan.status = "PENDING"
    s.commit()
    write_audit(s, ctx["sub"], student.name, ctx["office_n"], "fee.payment.proof_submitted", f"payment:{payment.id}", "", status, payment.reference)
    return {"payment_id": payment.id, "status": status}


def persona(s, ctx):
    """Resolve the signed-in persona used by all portal endpoints."""
    uid = ctx["sub"]
    office_n = ctx["office_n"]
    student = s.query(D.Student).filter(D.Student.user_id == uid).first()
    if student:
        return {"kind": "student", "student": student}
    staff = s.query(D.StaffMember).filter(D.StaffMember.user_id == uid).first()
    if staff:
        return {"kind": "faculty", "staff": staff}
    if office_n == 36:
        return {"kind": "student"}
    if office_n == 37:
        sid = ctx.get("scope_ref", "")
        return {"kind": "parent", "student": s.query(D.Student).get(sid) if sid else None}
    return {"kind": "staff", "office_n": office_n}


@router.get("/whoami")
def whoami(ctx=Depends(auth), s=Depends(db)):
    p = persona(s, ctx)
    out = {"kind": p["kind"], "office_n": ctx["office_n"]}
    if p.get("student"):
        st = p["student"]
        out["profile"] = {
            "name": st.name,
            "roll_no": st.roll_no,
            "cgpa": st.cgpa,
            "semester": st.semester,
            "batch": st.batch,
        }
    if p.get("staff"):
        stf = p["staff"]
        out["profile"] = {
            "name": stf.name,
            "emp_id": stf.emp_id,
            "designation": stf.designation,
        }
    return out


def _student_or_404(s, ctx):
    st = s.query(D.Student).filter(D.Student.user_id == ctx["sub"]).first()
    if not st and ctx.get("scope_ref"):
        st = s.query(D.Student).get(ctx["scope_ref"])
    if not st:
        raise HTTPException(404, "No student linked to this login")
    return st


def _staff_or_404(s, ctx):
    stf = s.query(D.StaffMember).filter(D.StaffMember.user_id == ctx["sub"]).first()
    if not stf:
        raise HTTPException(404, "No staff profile linked to this login")
    return stf


def _study_year(semester: int | None) -> int | None:
    if not semester:
        return None
    return (semester + 1) // 2


def _student_program_and_department(s, st):
    program = s.query(D.Program).get(st.program_id) if st.program_id else None
    dept = s.query(D.Department).get(st.dept_id) if st.dept_id else None
    return program, dept


def _student_enrollments(s, st):
    return (
        s.query(D.Enrollment)
        .filter(D.Enrollment.student_id == st.id, D.Enrollment.status == "enrolled")
        .all()
    )


def _student_sections(s, enrollments):
    section_ids = [row.section_id for row in enrollments]
    if not section_ids:
        return {}
    return {row.id: row for row in s.query(D.Section).filter(D.Section.id.in_(section_ids)).all()}


def _student_courses_map(s, sections):
    course_ids = sorted({row.course_id for row in sections.values() if row.course_id})
    if not course_ids:
        return {}
    return {row.id: row for row in s.query(D.Course).filter(D.Course.id.in_(course_ids)).all()}


def _faculty_names(s):
    return {row.id: row.name for row in s.query(D.StaffMember).all()}


def _student_attendance_query(s, st, section_id: str | None = None):
    section_ids = sorted({row.section_id for row in _student_current_enrollments(s, st) if row.section_id})
    if not section_ids:
        return s.query(D.AttendanceRecord).filter(False)
    q = (
        s.query(D.AttendanceRecord)
        .filter(
            D.AttendanceRecord.student_id == st.id,
            D.AttendanceRecord.section_id.in_(section_ids),
        )
    )
    if section_id:
        if section_id not in section_ids:
            return s.query(D.AttendanceRecord).filter(False)
        q = q.filter(D.AttendanceRecord.section_id == section_id)
    return q


def _student_attendance_pct(s, st, section_id: str | None = None):
    q = _student_attendance_query(s, st, section_id)
    total = q.count()
    if not total:
        return None
    present = q.filter(D.AttendanceRecord.present == True).count()
    return round((100 * present) / total)


def _attendance_status_key(row: D.AttendanceRecord) -> str:
    status = (row.status or "").strip().lower()
    if status in {"present", "absent", "leave", "od", "late", "pending"}:
        return status
    return "present" if row.present else "absent"


def _attendance_status_meta(status_key: str):
    mapping = {
        "present": {
            "key": "present",
            "label": "Present",
            "tone": "present",
            "short_note": "Verified by department office",
        },
        "late": {
            "key": "late",
            "label": "Late Update",
            "tone": "late",
            "short_note": "Reflected after office correction",
        },
        "absent": {
            "key": "absent",
            "label": "Absent",
            "tone": "absent",
            "short_note": "Marked absent for the session",
        },
        "leave": {
            "key": "leave",
            "label": "Leave Approved",
            "tone": "leave",
            "short_note": "Approved leave recorded by office",
        },
        "od": {
            "key": "od",
            "label": "OD / Leave",
            "tone": "leave",
            "short_note": "Official duty or leave note posted",
        },
        "pending": {
            "key": "pending",
            "label": "Pending",
            "tone": "pending",
            "short_note": "Awaiting department office update",
        },
    }
    return mapping.get(
        status_key,
        {
            "key": status_key,
            "label": status_key.replace("_", " ").title(),
            "tone": "pending",
            "short_note": "Awaiting department office update",
        },
    )


def _attendance_updated_at(row: D.AttendanceRecord) -> datetime:
    if row.updated_at:
        return row.updated_at
    if row.on_date:
        return datetime.combine(row.on_date, datetime.min.time()).replace(hour=16, minute=15)
    return PORTAL_NOW


def _student_backlog_summary(s, student_id: str):
    rows = (
        s.query(D.StudentSubjectResult)
        .filter(D.StudentSubjectResult.student_id == student_id)
        .order_by(D.StudentSubjectResult.subject_code, D.StudentSubjectResult.attempt)
        .all()
    )
    latest = {}
    history = []
    for row in rows:
        latest[row.subject_code] = row
        history.append(row)

    outstanding = [row for row in latest.values() if (row.outcome or "").lower() == "failed"]
    outstanding.sort(key=lambda row: (-(row.semester or 0), row.subject_code or ""))
    cleared = [
        row for row in latest.values()
        if (row.outcome or "").lower() == "passed"
        and any(
            item.subject_code == row.subject_code
            and (item.outcome or "").lower() == "failed"
            and (item.attempt or 0) < (row.attempt or 0)
            for item in history
        )
    ]

    return {
        "current": len(outstanding),
        "cleared": len(cleared),
        "subjects": [
            {
                "subject_code": row.subject_code,
                "subject_title": row.subject_title,
                "semester": row.semester,
                "attempt": row.attempt,
                "academic_year": row.academic_year,
            }
            for row in outstanding
        ],
        "history": history,
    }


def _student_fee_summary(s, student_id: str):
    invoices = (
        s.query(D.FeeInvoice)
        .filter(D.FeeInvoice.student_id == student_id)
        .order_by(desc(D.FeeInvoice.due_date), desc(D.FeeInvoice.term))
        .all()
    )
    balance = sum(max((row.amount or 0) - (row.paid or 0), 0) for row in invoices if row.status != "paid")
    return invoices, balance


def _student_learning_context(s, st):
    enrolls = _student_enrollments(s, st)
    sections = _student_sections(s, enrolls)
    courses = _student_courses_map(s, sections)
    faculty_names = _faculty_names(s)
    return enrolls, sections, courses, faculty_names


def _student_current_enrollments(s, st):
    raw = _student_enrollments(s, st)
    seen_section_ids = set()
    deduped = []
    for row in raw:
        if not row.section_id or row.section_id in seen_section_ids:
            continue
        seen_section_ids.add(row.section_id)
        deduped.append(row)

    sections = _student_sections(s, deduped)
    scoped = []
    for row in deduped:
        section = sections.get(row.section_id)
        if not section:
            continue
        if st.dept_id and section.dept_id and section.dept_id != st.dept_id:
            continue
        scoped.append(row)

    target_section = (st.section or "").strip()
    same_section = [
        row for row in scoped
        if sections.get(row.section_id) and sections[row.section_id].section_code == target_section
    ]
    return same_section or scoped


def _student_exam_history_enrollments(s, st):
    raw = (
        s.query(D.Enrollment)
        .filter(
            D.Enrollment.student_id == st.id,
            D.Enrollment.status.in_(["enrolled", "completed"]),
        )
        .all()
    )
    seen_section_ids = set()
    deduped = []
    for row in raw:
        if not row.section_id or row.section_id in seen_section_ids:
            continue
        seen_section_ids.add(row.section_id)
        deduped.append(row)
    return deduped


def _student_course_pref_id(student_id: str, section_id: str) -> str:
    return f"scvp_{student_id}_{section_id}"


def _student_course_preferences(s, st, section_ids):
    if not section_ids:
        return {}
    rows = (
        s.query(D.StudentCourseViewPreference)
        .filter(
            D.StudentCourseViewPreference.student_id == st.id,
            D.StudentCourseViewPreference.section_id.in_(section_ids),
        )
        .all()
    )
    return {row.section_id: row for row in rows}


def _student_active_loans_query(s, st):
    return (
        s.query(D.BookLoan)
        .filter(
            D.BookLoan.returned == False,
            or_(
                D.BookLoan.student_id == st.id,
                D.BookLoan.borrower == st.id,
                D.BookLoan.borrower == st.roll_no,
            ),
        )
    )


def _student_card(s, st):
    row = s.query(D.StudentIdentityCard).filter(D.StudentIdentityCard.student_id == st.id).first()
    if row:
        return row
    valid_until = date(date.today().year + 2, date.today().month, min(date.today().day, 28))
    row = D.StudentIdentityCard(
        id=f"idc_{st.id}",
        tenant_id=TENANT,
        student_id=st.id,
        card_number=f"ICMS-{st.roll_no}",
        blood_group=st.blood_group or "O+",
        issued_on=date.today(),
        valid_until=valid_until,
        status="active",
        verification_token=f"IC{st.roll_no[-10:]}".upper(),
    )
    s.add(row)
    s.commit()
    return row


def _day_name(day_of_week: int) -> str:
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][max(0, min(6, day_of_week))]


def _ordinal(value: int | None) -> str:
    if not value:
        return ""
    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def _office_label(office_n: int | None) -> str:
    if not office_n:
        return ""
    return office(office_n).get("name", "")


def _source_label(created_by: str = "", owner_office_n: int | None = None, fallback: str = "") -> str:
    raw = (created_by or "").strip()
    if raw:
        key = raw.lower().replace("_", " ").replace("-", " ")
        known = {
            "dean demo": "Dean Academics Office",
            "dean academics": "Dean Academics Office",
            "academic coordinator": "Academic Coordinator Office",
            "academic coordinator office": "Academic Coordinator Office",
            "hod demo": "Head of Department Office",
            "head of department": "Head of Department Office",
            "student affairs demo": "Dean Student Affairs Office",
            "dean student affairs": "Dean Student Affairs Office",
            "faculty demo": "Faculty",
        }
        for token, label in known.items():
            if token in key:
                return label
        if key == "seed":
            return fallback or _office_label(owner_office_n) or "ICMS Academic Records"
        return raw
    return _office_label(owner_office_n) or fallback


def _section_schedule_string(s, section_id: str, fallback: str = ""):
    rows = (
        s.query(D.TimetableEntry)
        .filter(D.TimetableEntry.section_id == section_id, D.TimetableEntry.status == "active")
        .order_by(D.TimetableEntry.day_of_week, D.TimetableEntry.start_time)
        .all()
    )
    if not rows:
        return fallback
    return ", ".join(f"{_day_name(row.day_of_week)} {row.start_time}-{row.end_time}" for row in rows[:3])


def _student_course_view_row(s, st, enrollment, sections, course_map, faculty_names, pref_map):
    section = sections.get(enrollment.section_id)
    if not section:
        return None
    course = course_map.get(section.course_id)
    pref = pref_map.get(section.id)
    base_faculty = faculty_names.get(section.faculty_person_id, "-")
    base_schedule = _section_schedule_string(s, section.id, section.schedule)
    faculty = (pref.faculty_label or "").strip() if pref else ""
    schedule = (pref.schedule_label or "").strip() if pref else ""
    return {
        "section_id": section.id,
        "course_id": course.id if course else "",
        "course_code": course.code if course else "",
        "title": course.title if course else "",
        "credits": course.credits if course else 0,
        "semester": course.semester if course else None,
        "section": section.section_code,
        "faculty": faculty or base_faculty,
        "schedule": schedule or base_schedule,
        "base_faculty": base_faculty,
        "base_schedule": base_schedule,
        "room": section.room,
        "status": enrollment.status,
        "grade": enrollment.grade,
        "attendance_pct": _student_attendance_pct(s, st, section.id),
        "has_preference": bool(pref and ((pref.faculty_label or "").strip() or (pref.schedule_label or "").strip())),
    }


def _cgpa_label(cgpa: float | None) -> str:
    if cgpa is None:
        return "Current standing"
    if cgpa >= 9:
        return "Excellent"
    if cgpa >= 8:
        return "Strong standing"
    if cgpa >= 7:
        return "Good standing"
    return "Needs support"


def _attendance_label(att_pct: int | None) -> str:
    if att_pct is None:
        return "Attendance pending"
    if att_pct >= 85:
        return "Excellent attendance"
    if att_pct >= 75:
        return "Good standing"
    return "Needs attention"


def _student_today_classes_payload(s, st):
    _, sections, courses, faculty_names = _student_learning_context(s, st)
    section_ids = list(sections.keys())
    today = PORTAL_TODAY
    rows = (
        s.query(D.TimetableEntry)
        .filter(
            D.TimetableEntry.section_id.in_(section_ids) if section_ids else False,
            D.TimetableEntry.day_of_week == today.weekday(),
            D.TimetableEntry.status == "active",
            or_(D.TimetableEntry.effective_from == None, D.TimetableEntry.effective_from <= today),
            or_(D.TimetableEntry.effective_to == None, D.TimetableEntry.effective_to >= today),
        )
        .order_by(D.TimetableEntry.start_time)
        .all()
    )
    payload = []
    for row in rows:
        section = sections.get(row.section_id)
        course = courses.get(section.course_id) if section and section.course_id else None
        faculty = faculty_names.get(section.faculty_person_id, "-") if section else "-"
        payload.append(
            {
                "timetable_entry_id": row.id,
                "section_id": row.section_id,
                "course_id": course.id if course else "",
                "course_code": course.code if course else "",
                "course_title": course.title if course else "",
                "semester": course.semester if course else None,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "faculty": faculty,
                "room": row.room,
                "section": section.section_code if section else "",
                "slot": f"{row.start_time} - {row.end_time}",
                "source_label": _source_label(row.created_by, fallback="Dean Academics Office"),
                "source_hint": "Published through the timetable workflow",
            }
        )
    return payload


def _student_tasks_payload(s, st):
    _, sections, courses, faculty_names = _student_learning_context(s, st)
    section_ids = list(sections.keys())
    rows = (
        s.query(D.Assignment)
        .filter(
            D.Assignment.section_id.in_(section_ids) if section_ids else False,
            D.Assignment.status.in_(["published", "open"]),
        )
        .order_by(D.Assignment.due_at, D.Assignment.assigned_at.desc())
        .all()
    )
    payload = []
    for row in rows:
        section = sections.get(row.section_id)
        course = courses.get(section.course_id) if section and section.course_id else None
        faculty = faculty_names.get(section.faculty_person_id, "-") if section else "-"
        payload.append(
            {
                "id": row.id,
                "title": row.title,
                "description": row.description,
                "course_code": course.code if course else "",
                "course_title": course.title if course else "",
                "status": row.status,
                "due_at": row.due_at.isoformat() if row.due_at else "",
                "urgency": _task_urgency_label(row.due_at),
                "faculty": faculty,
                "source_label": faculty if faculty != "-" else _source_label(row.created_by, fallback="Faculty"),
                "reference_url": row.reference_url or "",
            }
        )
    return payload


def _student_upcoming_assessments_payload(s, st):
    _, sections, courses, faculty_names = _student_learning_context(s, st)
    section_ids = list(sections.keys())
    now = PORTAL_NOW
    rows = (
        s.query(D.Assessment)
        .filter(
            D.Assessment.section_id.in_(section_ids) if section_ids else False,
            D.Assessment.assessment_type.in_(["quiz", "test"]),
            D.Assessment.published == True,
            D.Assessment.scheduled_at != None,
            D.Assessment.scheduled_at >= now,
        )
        .order_by(D.Assessment.scheduled_at)
        .all()
    )
    payload = []
    for row in rows:
        section = sections.get(row.section_id)
        course = courses.get(section.course_id) if section and section.course_id else None
        faculty = faculty_names.get(section.faculty_person_id, "-") if section else "-"
        payload.append(
            {
                "id": row.id,
                "name": row.name,
                "type": row.assessment_type,
                "course_code": course.code if course else "",
                "course_title": course.title if course else "",
                "section": section.section_code if section else "",
                "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else "",
                "end_at": row.end_at.isoformat() if row.end_at else "",
                "faculty": faculty,
                "source_label": faculty if faculty != "-" else "Faculty / Examination Office",
            }
        )
    return payload


def _portal_academic_year(dt_value):
    anchor = dt_value.date() if isinstance(dt_value, datetime) else dt_value
    anchor = anchor or PORTAL_TODAY
    start_year = anchor.year if anchor.month >= 6 else anchor.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _exam_mark_pct(mark, assessment):
    if not mark or not assessment or not assessment.max_marks:
        return None
    return round((float(mark.score or 0) / float(assessment.max_marks)) * 100, 1)


def _weighted_exam_average(records):
    usable = [row for row in records if row.get("pct") is not None]
    if not usable:
        return None
    total_weight = sum(float(row.get("weight") or 0) for row in usable)
    if total_weight > 0:
        value = sum(float(row["pct"]) * float(row.get("weight") or 0) for row in usable) / total_weight
    else:
        value = sum(float(row["pct"]) for row in usable) / len(usable)
    return round(value, 2)


def _exam_status_meta(status_key: str):
    key = (status_key or "scheduled").strip().lower()
    mapping = {
        "scheduled": {"key": "scheduled", "label": "Scheduled", "tone": "info"},
        "upcoming": {"key": "upcoming", "label": "Scheduled", "tone": "info"},
        "pending_publication": {"key": "pending_publication", "label": "Publishing Soon", "tone": "warning"},
        "published": {"key": "published", "label": "Published", "tone": "success"},
        "completed": {"key": "completed", "label": "Completed", "tone": "success"},
        "ended": {"key": "completed", "label": "Completed", "tone": "success"},
        "cancelled": {"key": "cancelled", "label": "Cancelled", "tone": "danger"},
        "rescheduled": {"key": "rescheduled", "label": "Rescheduled", "tone": "warning"},
        "draft": {"key": "draft", "label": "Draft", "tone": "muted"},
    }
    return mapping.get(key, {"key": key, "label": key.replace("_", " ").title(), "tone": "muted"})


def _average_score_label(value: float | None):
    if value is None:
        return "Published scores will appear after faculty release"
    if value >= 85:
        return "Excellent score trend"
    if value >= 75:
        return "Good scoring pattern"
    if value >= 60:
        return "Steady progress"
    return "Needs academic support"


def _exam_grade_label(pct: float | None):
    if pct is None:
        return ""
    if pct >= 90:
        return "O"
    if pct >= 80:
        return "A+"
    if pct >= 70:
        return "A"
    if pct >= 60:
        return "B+"
    if pct >= 55:
        return "B"
    if pct >= 50:
        return "C"
    return "F"


def _student_result_history_rows(s, st):
    rows = (
        s.query(D.StudentSubjectResult)
        .filter(D.StudentSubjectResult.student_id == st.id)
        .order_by(
            D.StudentSubjectResult.academic_year,
            D.StudentSubjectResult.semester,
            D.StudentSubjectResult.subject_code,
            D.StudentSubjectResult.attempt,
            D.StudentSubjectResult.published_at,
            D.StudentSubjectResult.updated_at,
        )
        .all()
    )
    latest_by_subject = {}
    latest_by_term_subject = {}
    for row in rows:
        latest_by_subject[row.subject_code] = row
        latest_by_term_subject[(row.academic_year, row.semester, row.subject_code)] = row

    sgpa_rows = {}
    for row in latest_by_term_subject.values():
        if row.grade_point is None or (row.credits or 0) <= 0:
            continue
        key = (row.academic_year or "", row.semester or 0)
        bucket = sgpa_rows.setdefault(key, {"points": 0.0, "credits": 0.0})
        bucket["points"] += float(row.grade_point or 0) * float(row.credits or 0)
        bucket["credits"] += float(row.credits or 0)

    sgpa = [
        {
            "academic_year": academic_year,
            "semester": semester,
            "sgpa": round(bucket["points"] / bucket["credits"], 2) if bucket["credits"] else None,
        }
        for (academic_year, semester), bucket in sgpa_rows.items()
    ]
    sgpa.sort(key=lambda row: (row["academic_year"], row["semester"]), reverse=True)

    latest_credit_rows = [row for row in latest_by_subject.values() if row.grade_point is not None and (row.credits or 0) > 0]
    cgpa = None
    if latest_credit_rows:
        total_credits = sum(float(row.credits or 0) for row in latest_credit_rows)
        total_points = sum(float(row.grade_point or 0) * float(row.credits or 0) for row in latest_credit_rows)
        if total_credits > 0:
            cgpa = round(total_points / total_credits, 2)

    return {
        "rows": rows,
        "latest_by_subject": latest_by_subject,
        "latest_by_term_subject": latest_by_term_subject,
        "sgpa": sgpa,
        "cgpa": st.cgpa if st.cgpa is not None else cgpa,
    }


def _term_sort_key(academic_year: str = "", semester: int | None = None):
    try:
        year_value = int(str(academic_year or "").split("-", 1)[0])
    except ValueError:
        year_value = -1
    return year_value, int(semester or 0)


def _score_result_matches_course(row, course_id: str = ""):
    if not course_id:
        return True
    return course_id in {row.course_id or "", row.subject_code or ""}


def _score_filter_payload(bundle, records, result_rows, applied):
    academic_years = sorted(
        {
            *{row.get("academic_year") for row in records if row.get("academic_year")},
            *{row.academic_year for row in result_rows if row.academic_year},
        },
        key=lambda value: _term_sort_key(value, 0),
        reverse=True,
    )
    semesters = sorted(
        {
            *{row.get("semester") for row in records if row.get("semester")},
            *{row.semester for row in result_rows if row.semester},
        },
        reverse=True,
    )
    assessment_types = sorted({row.get("assessment_type") for row in records if row.get("assessment_type")})
    course_options = []
    seen_course_ids = set()
    for enrollment in bundle["enrollments"]:
        section = bundle["sections"].get(enrollment.section_id)
        course = bundle["courses"].get(section.course_id) if section and section.course_id else None
        if not course or course.id in seen_course_ids:
            continue
        seen_course_ids.add(course.id)
        course_options.append({"id": course.id, "code": course.code, "title": course.title})
    for row in result_rows:
        option_id = row.course_id or row.subject_code or ""
        if not option_id or option_id in seen_course_ids:
            continue
        seen_course_ids.add(option_id)
        course_options.append({"id": option_id, "code": row.subject_code, "title": row.subject_title})
    course_options.sort(key=lambda row: (row["code"], row["title"]))
    return {
        "applied": applied,
        "academic_years": academic_years,
        "semesters": semesters,
        "courses": course_options,
        "assessment_types": assessment_types,
        "statuses": ["all", "upcoming", "completed", "published", "cancelled", "rescheduled"],
    }


def _score_backlog_state(result_summary, row):
    latest = result_summary["latest_by_subject"].get(row.subject_code)
    if latest and latest.id == row.id and (row.outcome or "").lower() == "failed":
        return "active"
    if (row.outcome or "").lower() == "failed" and latest and latest.id != row.id and (latest.outcome or "").lower() == "passed":
        return "cleared"
    return "none"


def _serialize_exam_update(row):
    payload = dict(row)
    for field in [
        "updated_at",
        "scheduled_at",
        "end_at",
        "published_at",
        "mark_published_at",
        "previous_start_at",
        "previous_end_at",
        "new_start_at",
        "new_end_at",
    ]:
        payload[field] = payload[field].isoformat() if payload.get(field) else ""
    return payload


def _serialize_published_score_row(row):
    return {
        "assessment_id": row["assessment_id"],
        "course_id": row["course_id"],
        "course_code": row["course_code"],
        "course_title": row["course_title"],
        "assessment_name": row["assessment_name"],
        "assessment_type": row["assessment_type"],
        "score": row["score"],
        "max_marks": row["max_marks"],
        "percentage": row["pct"],
        "grade": _exam_grade_label(row["pct"]),
        "faculty": row["faculty"],
        "published_at": row["mark_published_at"].isoformat() if row["mark_published_at"] else "",
        "status": row["status"],
        "academic_year": row["academic_year"],
        "semester": row["semester"],
    }


def _serialize_pending_publication_row(row):
    return {
        "assessment_id": row["assessment_id"],
        "course_id": row["course_id"],
        "course_code": row["course_code"],
        "course_title": row["course_title"],
        "assessment_name": row["assessment_name"],
        "assessment_type": row["assessment_type"],
        "academic_year": row["academic_year"],
        "semester": row["semester"],
        "section": row["section"],
        "completed_at": row["end_at"].isoformat() if row.get("end_at") else (row["scheduled_at"].isoformat() if row.get("scheduled_at") else ""),
        "faculty": row["faculty"],
        "venue": row["venue"],
        "mode": row["mode"],
        "status": {
            "key": "pending_publication",
            "label": "Publishing Soon",
            "tone": "warning",
        },
        "note": row["note"] or "Awaiting faculty or examination office publication.",
        "source_label": row.get("source_label") or row["faculty"],
        "source_office": row.get("source_office") or "Examination Workflow",
        "updated_at": row["result_updated_at"].isoformat() if row.get("result_updated_at") else "",
    }


def _student_pending_score_publications(records):
    pending = []
    for row in records:
        if not row.get("published") or row.get("mark_visible"):
            continue
        if row.get("status_key") in {"cancelled", "upcoming", "rescheduled"}:
            continue
        if not row.get("completed_window"):
            continue
        pending.append(row)
    pending.sort(
        key=lambda row: row.get("result_updated_at") or row.get("end_at") or row.get("scheduled_at") or PORTAL_NOW,
        reverse=True,
    )
    return pending


def _student_exam_bundle(s, st, include_history: bool = False):
    enrollments = _student_exam_history_enrollments(s, st) if include_history else _student_current_enrollments(s, st)
    sections = _student_sections(s, enrollments)
    courses = _student_courses_map(s, sections)
    faculty_names = _faculty_names(s)
    section_ids = sorted({row.section_id for row in enrollments if row.section_id})
    assessments = (
        s.query(D.Assessment)
        .filter(D.Assessment.section_id.in_(section_ids) if section_ids else False)
        .order_by(D.Assessment.scheduled_at, D.Assessment.id)
        .all()
    )
    assessment_ids = [row.id for row in assessments]
    mark_rows = (
        s.query(D.Mark)
        .filter(
            D.Mark.student_id == st.id,
            D.Mark.assessment_id.in_(assessment_ids) if assessment_ids else False,
            D.Mark.is_valid == True,
        )
        .order_by(desc(D.Mark.published_at), desc(D.Mark.updated_at), desc(D.Mark.entered_at))
        .all()
    )
    marks_by_assessment = {row.assessment_id: row for row in mark_rows}
    schedules = (
        s.query(D.ExamScheduleEntry)
        .filter(D.ExamScheduleEntry.section_id.in_(section_ids) if section_ids else False)
        .order_by(desc(D.ExamScheduleEntry.is_active), desc(D.ExamScheduleEntry.version_no), desc(D.ExamScheduleEntry.updated_at))
        .all()
    )
    schedules_by_id = {row.id: row for row in schedules}
    schedule_by_assessment = {}
    schedule_ids = []
    for row in schedules:
        schedule_ids.append(row.id)
        if row.assessment_id and row.assessment_id not in schedule_by_assessment and row.is_active:
            schedule_by_assessment[row.assessment_id] = row

    histories = (
        s.query(D.ExamScheduleHistory)
        .filter(
            or_(
                D.ExamScheduleHistory.schedule_id.in_(schedule_ids) if schedule_ids else False,
                D.ExamScheduleHistory.assessment_id.in_(assessment_ids) if assessment_ids else False,
            )
        )
        .order_by(desc(D.ExamScheduleHistory.created_at))
        .all()
    )
    seat_rows = (
        s.query(D.ExamSeatAssignment)
        .filter(
            D.ExamSeatAssignment.student_id == st.id,
            or_(
                D.ExamSeatAssignment.schedule_id.in_(schedule_ids) if schedule_ids else False,
                D.ExamSeatAssignment.assessment_id.in_(assessment_ids) if assessment_ids else False,
            ),
        )
        .order_by(desc(D.ExamSeatAssignment.updated_at), desc(D.ExamSeatAssignment.created_at))
        .all()
    )
    seats_by_assessment = {}
    for row in seat_rows:
        assessment_key = row.assessment_id or (
            schedules_by_id.get(row.schedule_id).assessment_id
            if row.schedule_id and schedules_by_id.get(row.schedule_id)
            else None
        )
        if assessment_key and assessment_key not in seats_by_assessment:
            seats_by_assessment[assessment_key] = row
    results = _student_result_history_rows(s, st)
    return {
        "enrollments": enrollments,
        "sections": sections,
        "courses": courses,
        "faculty_names": faculty_names,
        "assessments": assessments,
        "marks_by_assessment": marks_by_assessment,
        "mark_rows": mark_rows,
        "schedule_by_assessment": schedule_by_assessment,
        "histories": histories,
        "seats_by_assessment": seats_by_assessment,
        "results": results,
    }


def _student_exam_records(bundle, st):
    rows = []
    for assessment in bundle["assessments"]:
        section = bundle["sections"].get(assessment.section_id)
        if not section:
            continue
        course = bundle["courses"].get(section.course_id) if section.course_id else None
        mark = bundle["marks_by_assessment"].get(assessment.id)
        schedule = bundle["schedule_by_assessment"].get(assessment.id)
        seat = bundle["seats_by_assessment"].get(assessment.id)
        if not schedule and not (assessment.academic_year or assessment.published_by):
            continue
        scheduled_at = schedule.start_at if schedule and schedule.start_at else assessment.scheduled_at
        end_at = schedule.end_at if schedule and schedule.end_at else assessment.end_at
        schedule_status = ((schedule.status if schedule else assessment.status) or "scheduled").strip().lower()
        academic_year = (
            assessment.academic_year
            or (schedule.academic_year if schedule and schedule.academic_year else "")
            or _portal_academic_year(scheduled_at)
        )
        semester = (schedule.semester if schedule and schedule.semester else (course.semester if course else st.semester))
        pct = _exam_mark_pct(mark, assessment)
        past_window = bool((end_at and end_at <= PORTAL_NOW) or (scheduled_at and scheduled_at < PORTAL_NOW))
        completed_window = past_window or schedule_status in {"completed", "ended"} or (assessment.status or "").lower() in {"completed", "ended"}
        source_label = _source_label(
            (schedule.updated_by if schedule and schedule.updated_by else "")
            or (schedule.created_by if schedule and schedule.created_by else "")
            or assessment.published_by
            or assessment.updated_by
            or assessment.created_by,
            schedule.managed_by_office_n if schedule else None,
            "Faculty / Examination Office",
        )
        source_office = _office_label(schedule.managed_by_office_n if schedule else None)
        visible_mark = bool(
            mark
            and (mark.status or "").lower() == "published"
            and bool(mark.is_valid)
            and assessment.published
            and completed_window
        )
        is_completed = visible_mark
        is_upcoming = bool(schedule and assessment.published and scheduled_at and scheduled_at >= PORTAL_NOW and schedule_status != "cancelled")
        if is_completed:
            status_key = "completed"
        elif schedule_status == "cancelled":
            status_key = "cancelled"
        elif schedule_status == "rescheduled" and is_upcoming:
            status_key = "rescheduled"
        elif is_upcoming:
            status_key = "upcoming"
        elif assessment.published and completed_window:
            status_key = "pending_publication"
        else:
            status_key = schedule_status or "published"
        rows.append(
            {
                "assessment_id": assessment.id,
                "section_id": section.id,
                "course_id": course.id if course else "",
                "course_code": course.code if course else "",
                "course_title": course.title if course else "",
                "faculty": bundle["faculty_names"].get(section.faculty_person_id, "-"),
                "assessment_name": assessment.name,
                "assessment_type": (assessment.assessment_type or (schedule.exam_type if schedule else "exam") or "exam").strip().lower(),
                "academic_year": academic_year,
                "semester": semester,
                "section": section.section_code,
                "scheduled_at": scheduled_at,
                "end_at": end_at,
                "schedule_status": schedule_status,
                "status_key": status_key,
                "status": _exam_status_meta(status_key),
                "venue": schedule.venue if schedule else section.room,
                "mode": schedule.mode if schedule else "Offline",
                "note": schedule.note if schedule else assessment.instructions,
                "seat_label": seat.seat_label if seat and seat.seat_label else "",
                "seat_zone": seat.seat_zone if seat and seat.seat_zone else "",
                "seat_note": seat.note if seat and seat.note else "",
                "seat_assigned_by": seat.assigned_by if seat and seat.assigned_by else "",
                "published": assessment.published,
                "published_at": assessment.published_at or (mark.published_at if mark else None),
                "published_by": assessment.published_by,
                "source_label": source_label,
                "source_office": source_office,
                "schedule_version": schedule.version_no if schedule else 1,
                "managed_by_office_n": schedule.managed_by_office_n if schedule else None,
                "assessment_created_by": assessment.created_by,
                "assessment_updated_by": assessment.updated_by,
                "mark_published_by": mark.published_by if mark else "",
                "completed_window": completed_window,
                "result_updated_at": (mark.updated_at if mark else None) or assessment.updated_at or assessment.created_at,
                "mark": mark,
                "mark_visible": visible_mark,
                "score": float(mark.score or 0) if visible_mark and mark else None,
                "max_marks": float(assessment.max_marks or 0),
                "pct": pct if visible_mark else None,
                "weight": float(assessment.weight or 0),
                "mark_published_at": mark.published_at if visible_mark and mark else None,
                "mark_status": (mark.status if mark else ""),
            }
        )
    return rows


def _apply_exam_filters(records, academic_year="", semester="", course_id="", assessment_type="", status="all"):
    out = records
    if academic_year:
        out = [row for row in out if row.get("academic_year") == academic_year]
    if semester:
        try:
            semester_value = int(semester)
            out = [row for row in out if row.get("semester") == semester_value]
        except ValueError:
            out = []
    if course_id:
        out = [row for row in out if row.get("course_id") == course_id]
    if assessment_type:
        match = assessment_type.strip().lower()
        out = [row for row in out if row.get("assessment_type") == match]
    status_key = (status or "all").strip().lower()
    if status_key == "upcoming":
        out = [row for row in out if row.get("status_key") in {"upcoming", "rescheduled"}]
    elif status_key == "completed":
        out = [row for row in out if row.get("status_key") == "completed"]
    elif status_key == "published":
        out = [row for row in out if row.get("mark_visible")]
    elif status_key == "cancelled":
        out = [row for row in out if row.get("status_key") == "cancelled"]
    elif status_key == "rescheduled":
        out = [row for row in out if row.get("status_key") == "rescheduled"]
    return out


def _exam_filter_payload(bundle, records, applied):
    academic_years = sorted({row.get("academic_year") for row in records if row.get("academic_year")}, reverse=True)
    semesters = sorted({row.get("semester") for row in records if row.get("semester")}, reverse=True)
    assessment_types = sorted({row.get("assessment_type") for row in records if row.get("assessment_type")})
    course_options = []
    seen_course_ids = set()
    for enrollment in bundle["enrollments"]:
        section = bundle["sections"].get(enrollment.section_id)
        course = bundle["courses"].get(section.course_id) if section and section.course_id else None
        if not course or course.id in seen_course_ids:
            continue
        seen_course_ids.add(course.id)
        course_options.append({"id": course.id, "code": course.code, "title": course.title})
    course_options.sort(key=lambda row: row["code"])
    return {
        "applied": applied,
        "academic_years": academic_years,
        "semesters": semesters,
        "courses": course_options,
        "assessment_types": assessment_types,
        "statuses": ["all", "upcoming", "completed", "published", "cancelled", "rescheduled"],
    }


def _student_recent_exam_updates(bundle, records):
    assessment_map = {row.id: row for row in bundle["assessments"]}
    record_map = {row["assessment_id"]: row for row in records}
    schedule_ids = {
        schedule.id: schedule
        for schedule in bundle["schedule_by_assessment"].values()
    }
    updates = []

    for row in records:
        assessment = assessment_map.get(row["assessment_id"])
        source_label = row.get("source_label") or row["faculty"]
        source_office = row.get("source_office") or "Examination Workflow"
        published_at = row.get("published_at")
        if row.get("published") and published_at:
            updates.append(
                {
                    "id": f"assessment_{row['assessment_id']}",
                    "kind": "assessment_published",
                    "updated_at": published_at,
                    "course_code": row["course_code"],
                    "course_title": row["course_title"],
                    "assessment_name": row["assessment_name"],
                    "message": f"{row['assessment_name']} published for students",
                    "status": _exam_status_meta("published"),
                    "academic_year": row["academic_year"],
                    "semester": row["semester"],
                    "section": row["section"],
                    "faculty": row["faculty"],
                    "scheduled_at": row["scheduled_at"],
                    "end_at": row["end_at"],
                    "venue": row["venue"],
                    "mode": row["mode"],
                    "seat_label": row.get("seat_label") or "",
                    "seat_zone": row.get("seat_zone") or "",
                    "seat_note": row.get("seat_note") or "",
                    "source_label": source_label,
                    "source_office": source_office,
                    "note": row["note"] or "Timetable entry published for your enrolled section.",
                    "detail_title": "Published for enrolled students",
                    "detail_body": "The examination timetable is now visible for your section only.",
                    "published_at": assessment.published_at if assessment else published_at,
                    "mark_published_at": None,
                    "previous_start_at": None,
                    "previous_end_at": None,
                    "previous_venue": "",
                    "previous_status": "",
                    "new_start_at": row["scheduled_at"],
                    "new_end_at": row["end_at"],
                    "new_venue": row["venue"],
                    "new_status": row.get("schedule_status") or "published",
                }
            )
        if row.get("mark_visible") and row.get("mark_published_at"):
            updates.append(
                {
                    "id": f"mark_{row['assessment_id']}",
                    "kind": "marks_published",
                    "updated_at": row["mark_published_at"],
                    "course_code": row["course_code"],
                    "course_title": row["course_title"],
                    "assessment_name": row["assessment_name"],
                    "message": f"{row['assessment_name']} marks published",
                    "status": _exam_status_meta("published"),
                    "academic_year": row["academic_year"],
                    "semester": row["semester"],
                    "section": row["section"],
                    "faculty": row["faculty"],
                    "scheduled_at": row["scheduled_at"],
                    "end_at": row["end_at"],
                    "venue": row["venue"],
                    "mode": row["mode"],
                    "seat_label": row.get("seat_label") or "",
                    "seat_zone": row.get("seat_zone") or "",
                    "seat_note": row.get("seat_note") or "",
                    "source_label": row.get("mark_published_by") or row["faculty"],
                    "source_office": "Faculty Evaluation",
                    "note": row["note"] or "Marks published after faculty verification.",
                    "detail_title": "Marks published",
                    "detail_body": "Only your own published mark is visible here.",
                    "published_at": published_at,
                    "mark_published_at": row["mark_published_at"],
                    "score": row["score"],
                    "max_marks": row["max_marks"],
                    "percentage": row["pct"],
                    "grade": _exam_grade_label(row["pct"]),
                    "previous_start_at": None,
                    "previous_end_at": None,
                    "previous_venue": "",
                    "previous_status": "",
                    "new_start_at": row["scheduled_at"],
                    "new_end_at": row["end_at"],
                    "new_venue": row["venue"],
                    "new_status": "published",
                }
            )

    for history in bundle["histories"]:
        record = record_map.get(history.assessment_id)
        if not record:
            schedule = schedule_ids.get(history.schedule_id)
            linked = next((row for row in records if row["assessment_id"] == schedule.assessment_id), None) if schedule and schedule.assessment_id else None
            record = linked
        if not record:
            continue
        change_key = (history.change_type or "updated").strip().lower()
        if change_key == "created":
            label = "Assessment assigned to your section"
        elif change_key == "cancelled":
            label = "Assessment cancelled by exam office"
        elif change_key == "rescheduled":
            label = "Assessment rescheduled"
        elif history.previous_venue and history.previous_venue != (history.new_venue or ""):
            change_key = "rescheduled"
            label = f"Venue updated to {history.new_venue}"
        else:
            label = "Assessment updated"
        updates.append(
            {
                "id": history.id,
                "kind": change_key,
                "updated_at": history.created_at,
                "course_code": record["course_code"],
                "course_title": record["course_title"],
                "assessment_name": record["assessment_name"],
                "message": label,
                "status": _exam_status_meta("cancelled" if change_key == "cancelled" else ("rescheduled" if change_key == "rescheduled" else "published")),
                "academic_year": record["academic_year"],
                "semester": record["semester"],
                "section": record["section"],
                "faculty": record["faculty"],
                "scheduled_at": record["scheduled_at"],
                "end_at": record["end_at"],
                "venue": record["venue"],
                "mode": record["mode"],
                "seat_label": record.get("seat_label") or "",
                "seat_zone": record.get("seat_zone") or "",
                "seat_note": record.get("seat_note") or "",
                "source_label": _source_label(
                    history.created_by,
                    schedule_ids.get(history.schedule_id).managed_by_office_n if history.schedule_id in schedule_ids else None,
                    "Examination Office",
                ),
                "source_office": _office_label(
                    schedule_ids.get(history.schedule_id).managed_by_office_n if history.schedule_id in schedule_ids else None
                ) or "Examination Office",
                "note": history.note or record.get("note") or "Examination update posted for your enrolled section.",
                "detail_title": label,
                "detail_body": history.note or "The examination office updated the timetable for your section.",
                "published_at": None,
                "mark_published_at": None,
                "previous_start_at": history.previous_start_at,
                "previous_end_at": history.previous_end_at,
                "previous_venue": history.previous_venue or "",
                "previous_status": history.previous_status or "",
                "new_start_at": history.new_start_at,
                "new_end_at": history.new_end_at,
                "new_venue": history.new_venue or "",
                "new_status": history.new_status or "",
            }
        )

    updates.sort(key=lambda row: row["updated_at"] or PORTAL_NOW, reverse=True)
    return updates[:8]


def _student_examinations_payload(s, st, academic_year="", semester="", course_id="", assessment_type="", status="all"):
    bundle = _student_exam_bundle(s, st)
    records = _student_exam_records(bundle, st)
    filtered = _apply_exam_filters(
        records,
        academic_year=academic_year,
        semester=semester,
        course_id=course_id,
        assessment_type=assessment_type,
        status=status,
    )
    upcoming = sorted(
        [row for row in filtered if row.get("status_key") in {"upcoming", "rescheduled"}],
        key=lambda row: row.get("scheduled_at") or PORTAL_NOW,
    )
    completed = [row for row in filtered if row.get("status_key") == "completed"]
    visible_marks = sorted(
        [row for row in filtered if row.get("mark_visible")],
        key=lambda row: row.get("mark_published_at") or row.get("published_at") or PORTAL_NOW,
        reverse=True,
    )
    result_summary = bundle["results"]
    backlog = _student_backlog_summary(s, st.id)
    current_sgpa = next((row["sgpa"] for row in result_summary["sgpa"] if row["semester"] == st.semester), None)
    average_score = _weighted_exam_average(visible_marks)
    updates = _student_recent_exam_updates(bundle, records)
    return {
        "student": {
            "name": st.name,
            "roll_no": st.roll_no,
            "semester": st.semester,
            "section": st.section,
        },
        "filters": _exam_filter_payload(
            bundle,
            records,
            {
                "academic_year": academic_year or "",
                "semester": semester or "",
                "course_id": course_id or "",
                "assessment_type": assessment_type or "",
                "status": status or "all",
            },
        ),
        "summary": {
            "upcoming_count": len(upcoming),
            "completed_count": len(completed),
            "average_score_pct": average_score,
            "average_score_label": _average_score_label(average_score),
            "cgpa": result_summary["cgpa"],
            "cgpa_label": _cgpa_label(result_summary["cgpa"]),
            "sgpa": current_sgpa,
            "backlogs": backlog["current"],
            "courses_enrolled": len(bundle["enrollments"]),
            "scores_published": len(visible_marks),
        },
        "upcoming_assessments": [
            {
                "id": row["assessment_id"],
                "course_id": row["course_id"],
                "course_code": row["course_code"],
                "course_title": row["course_title"],
                "assessment_name": row["assessment_name"],
                "assessment_type": row["assessment_type"],
                "academic_year": row["academic_year"],
                "semester": row["semester"],
                "section": row["section"],
                "scheduled_at": row["scheduled_at"].isoformat() if row["scheduled_at"] else "",
                "end_at": row["end_at"].isoformat() if row["end_at"] else "",
                "venue": row["venue"] or "",
                "mode": row["mode"] or "",
                "faculty": row["faculty"],
                "status": row["status"],
                "note": row["note"] or "",
                "seat_label": row.get("seat_label") or "",
                "seat_zone": row.get("seat_zone") or "",
                "seat_note": row.get("seat_note") or "",
                "source_label": row.get("source_label") or row["faculty"],
                "source_office": row.get("source_office") or "Examination Workflow",
                "schedule_version": row.get("schedule_version") or 1,
            }
            for row in upcoming[:8]
        ],
        "recent_published_marks": [_serialize_published_score_row(row) for row in visible_marks[:8]],
        "recent_updates": [_serialize_exam_update(row) for row in updates],
        "refreshed_at": PORTAL_NOW.isoformat(),
    }


def _student_scores_payload(s, st, academic_year="", semester="", course_id="", assessment_type=""):
    bundle = _student_exam_bundle(s, st, include_history=True)
    records = _student_exam_records(bundle, st)
    filtered_records = _apply_exam_filters(
        records,
        academic_year=academic_year,
        semester=semester,
        course_id=course_id,
        assessment_type=assessment_type,
        status="all",
    )
    result_summary = bundle["results"]
    backlog = _student_backlog_summary(s, st.id)
    published_marks = sorted(
        [row for row in filtered_records if row.get("mark_visible")],
        key=lambda row: row.get("mark_published_at") or PORTAL_NOW,
        reverse=True,
    )
    pending_publications = _student_pending_score_publications(filtered_records)
    semester_results = []
    for row in result_summary["latest_by_term_subject"].values():
        if academic_year and row.academic_year != academic_year:
            continue
        if semester:
            try:
                if row.semester != int(semester):
                    continue
            except ValueError:
                continue
        if not _score_result_matches_course(row, course_id):
            continue
        semester_results.append(row)
    semester_results.sort(
        key=lambda row: (_term_sort_key(row.academic_year, row.semester), row.subject_code or "", row.attempt or 0),
        reverse=True,
    )

    sgpa_lookup = {
        (row["academic_year"], row["semester"]): row["sgpa"]
        for row in result_summary["sgpa"]
    }
    term_buckets = {}

    def ensure_bucket(term_academic_year: str, term_semester: int | None):
        key = (term_academic_year or "", int(term_semester or 0))
        if key not in term_buckets:
            term_buckets[key] = {
                "academic_year": term_academic_year or "",
                "semester": int(term_semester or 0),
                "label": f"{term_academic_year or '--'} / Semester {int(term_semester or 0) if term_semester else '--'}",
                "sgpa": sgpa_lookup.get(key),
                "published_marks": [],
                "official_results": [],
                "coming_soon": [],
                "_mark_records": [],
                "_active_backlogs": 0,
                "_cleared_backlogs": 0,
                "_credits": 0.0,
            }
        return term_buckets[key]

    for row in published_marks:
        bucket = ensure_bucket(row["academic_year"], row["semester"])
        bucket["published_marks"].append(_serialize_published_score_row(row))
        bucket["_mark_records"].append(row)

    for row in semester_results:
        bucket = ensure_bucket(row.academic_year, row.semester)
        backlog_state = _score_backlog_state(result_summary, row)
        if backlog_state == "active":
            bucket["_active_backlogs"] += 1
        elif backlog_state == "cleared":
            bucket["_cleared_backlogs"] += 1
        bucket["_credits"] += float(row.credits or 0)
        bucket["official_results"].append(
            {
                "id": row.id,
                "course_id": row.course_id or row.subject_code or "",
                "subject_code": row.subject_code,
                "subject_title": row.subject_title,
                "attempt": row.attempt,
                "outcome": row.outcome,
                "grade": row.grade,
                "grade_point": row.grade_point,
                "credits": row.credits,
                "percentage": row.percentage,
                "total_score": row.total_score,
                "max_score": row.max_score,
                "published_at": row.published_at.isoformat() if row.published_at else "",
                "backlog_status": backlog_state,
            }
        )

    for row in pending_publications:
        bucket = ensure_bucket(row["academic_year"], row["semester"])
        bucket["coming_soon"].append(_serialize_pending_publication_row(row))

    for academic_key, semester_key in sgpa_lookup.keys():
        if academic_year and academic_key != academic_year:
            continue
        if semester:
            try:
                if int(semester_key or 0) != int(semester):
                    continue
            except ValueError:
                continue
        ensure_bucket(academic_key, semester_key)

    semester_groups = []
    for bucket in term_buckets.values():
        bucket["published_marks"].sort(key=lambda row: row.get("published_at") or "", reverse=True)
        bucket["official_results"].sort(key=lambda row: (row["subject_code"], row["attempt"] or 0))
        bucket["coming_soon"].sort(
            key=lambda row: row.get("updated_at") or row.get("completed_at") or "",
            reverse=True,
        )
        average_score = _weighted_exam_average(bucket["_mark_records"])
        published_result_count = len(
            [row for row in bucket["official_results"] if (row.get("outcome") or "").lower() in {"passed", "failed"}]
        )
        semester_groups.append(
            {
                "academic_year": bucket["academic_year"],
                "semester": bucket["semester"],
                "label": bucket["label"],
                "sgpa": bucket["sgpa"],
                "sgpa_label": "Official SGPA published" if bucket["sgpa"] is not None else "Awaiting official semester result",
                "summary": {
                    "published_scores": len(bucket["published_marks"]),
                    "official_results": published_result_count,
                    "pending_publications": len(bucket["coming_soon"]),
                    "average_score_pct": average_score,
                    "active_backlogs": bucket["_active_backlogs"],
                    "cleared_backlogs": bucket["_cleared_backlogs"],
                    "credits": round(bucket["_credits"], 1),
                },
                "published_marks": bucket["published_marks"],
                "official_results": bucket["official_results"],
                "coming_soon": bucket["coming_soon"],
            }
        )

    semester_groups.sort(
        key=lambda row: _term_sort_key(row["academic_year"], row["semester"]),
        reverse=True,
    )
    return {
        "filters": _score_filter_payload(
            bundle,
            records,
            result_summary["rows"],
            {
                "academic_year": academic_year or "",
                "semester": semester or "",
                "course_id": course_id or "",
                "assessment_type": assessment_type or "",
                "status": "published",
            },
        ),
        "summary": {
            "cgpa": result_summary["cgpa"],
            "cgpa_label": _cgpa_label(result_summary["cgpa"]),
            "sgpa_rows": result_summary["sgpa"],
            "published_marks": len(published_marks),
            "backlogs": backlog["current"],
            "cleared_backlogs": backlog["cleared"],
            "coming_soon": len(pending_publications),
            "visible_semesters": len(semester_groups),
        },
        "published_marks": [_serialize_published_score_row(row) for row in published_marks],
        "semester_results": [
            {
                "id": row.id,
                "academic_year": row.academic_year,
                "semester": row.semester,
                "course_id": row.course_id or row.subject_code or "",
                "subject_code": row.subject_code,
                "subject_title": row.subject_title,
                "attempt": row.attempt,
                "outcome": row.outcome,
                "grade": row.grade,
                "grade_point": row.grade_point,
                "credits": row.credits,
                "percentage": row.percentage,
                "total_score": row.total_score,
                "max_score": row.max_score,
                "published_at": row.published_at.isoformat() if row.published_at else "",
                "backlog_status": _score_backlog_state(result_summary, row),
            }
            for row in semester_results
        ],
        "coming_soon": [_serialize_pending_publication_row(row) for row in pending_publications[:8]],
        "semester_groups": semester_groups,
        "backlogs": backlog,
        "refreshed_at": PORTAL_NOW.isoformat(),
    }


def _student_announcements_payload(s, st):
    section_ids = [row.section_id for row in _student_enrollments(s, st)]
    now = PORTAL_NOW
    rows = (
        s.query(D.Announcement)
        .filter(
            D.Announcement.status == "published",
            or_(D.Announcement.published_at == None, D.Announcement.published_at <= now),
            or_(D.Announcement.expires_at == None, D.Announcement.expires_at >= now),
            or_(
                D.Announcement.audience.in_(["all", "all_students", "students"]),
                and_(D.Announcement.audience == "campus", D.Announcement.campus == st.campus),
                and_(D.Announcement.audience == "department", D.Announcement.department_id == st.dept_id),
                and_(D.Announcement.audience == "program", D.Announcement.program_id == st.program_id),
                and_(D.Announcement.audience == "section", D.Announcement.section_id.in_(section_ids) if section_ids else False),
                and_(D.Announcement.audience == "student", D.Announcement.student_id == st.id),
            ),
        )
        .order_by(desc(D.Announcement.published_at), desc(D.Announcement.created_at))
        .all()
    )
    payload = []
    for row in rows:
        payload.append(
            {
                "id": row.id,
                "title": row.title,
                "body": row.body,
                "audience": row.audience,
                "published_at": row.published_at.isoformat() if row.published_at else "",
                "is_new": bool(row.published_at and (now - row.published_at).total_seconds() <= 3 * 24 * 3600),
                "source_label": _source_label(row.created_by, row.owner_office_n, "Student Affairs"),
                "source_office": _office_label(row.owner_office_n),
            }
        )
    return payload


def _digital_id_payload(s, st):
    program, dept = _student_program_and_department(s, st)
    card = _student_card(s, st)
    return {
        "card_number": card.card_number,
        "status": card.status,
        "issued_on": card.issued_on.isoformat() if card.issued_on else "",
        "valid_until": card.valid_until.isoformat() if card.valid_until else "",
        "blood_group": card.blood_group or st.blood_group or "",
        "verification_token": card.verification_token,
        "verification_payload": f"ICMS:{card.verification_token}",
        "student_name": st.name,
        "student_id": st.roll_no,
        "programme": program.name if program else "",
        "department": dept.name if dept else "",
        "semester": st.semester,
        "study_year": _study_year(st.semester),
        "status_label": "Valid" if (card.valid_until and card.valid_until >= date.today()) else "Expired",
    }


def _month_start(raw_start: str = ""):
    try:
        base = date.fromisoformat((raw_start or "").strip()[:10]) if raw_start else date.today()
    except ValueError:
        base = date.today()
    return base.replace(day=1)


def _month_end(month_start: date):
    if month_start.month == 12:
        return date(month_start.year + 1, 1, 1) - timedelta(days=1)
    return date(month_start.year, month_start.month + 1, 1) - timedelta(days=1)


def _month_label(month_start: date):
    return month_start.strftime("%B %Y")


def _combine_day_time(day_value: date, raw_time: str, fallback_hour: int = 0):
    try:
        hour_text, minute_text = (raw_time or "").split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (TypeError, ValueError):
        hour = fallback_hour
        minute = 0
    return datetime.combine(day_value, datetime.min.time()).replace(hour=hour, minute=minute)


class StudentCalendarEventIn(BaseModel):
    title: str
    note: str = ""
    start_at: str
    end_at: str


class StudentCourseViewUpdateIn(BaseModel):
    faculty: str = ""
    schedule: str = ""


def _portal_uid() -> str:
    return uuid4().hex[:12]


def _parse_portal_datetime(raw_value: str, field_name: str) -> datetime:
    text = (raw_value or "").strip()
    if not text:
        raise HTTPException(400, f"{field_name} is required")
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(400, f"Invalid {field_name}") from exc
    return value.replace(tzinfo=None) if value.tzinfo else value


def _student_personal_time_label(start_at: datetime, end_at: datetime) -> str:
    if start_at.date() == end_at.date():
        return f"{start_at.strftime('%I:%M %p').lstrip('0')} to {end_at.strftime('%I:%M %p').lstrip('0')}"
    return (
        f"{start_at.strftime('%d %b, %I:%M %p').lstrip('0')} to "
        f"{end_at.strftime('%d %b, %I:%M %p').lstrip('0')}"
    )


def _catalog_term_key(base_course_id: str = "", semester: int | None = None, code: str = ""):
    root = (base_course_id or code or "").strip()
    if not root:
        return ""
    return f"{root}:{int(semester or 0)}"


def _student_personal_event_payload(row: D.StudentCalendarEvent):
    return {
        "id": f"personal_{row.id}",
        "personal_event_id": row.id,
        "title": row.title,
        "subtitle": row.note or "Personal event",
        "meta": "Student calendar",
        "category": "My Events",
        "kind": "personal",
        "module": "calendar",
        "start": row.start_at.isoformat(),
        "end": row.end_at.isoformat(),
        "all_day": False,
        "location": "",
        "source_label": "My calendar",
        "time_label": _student_personal_time_label(row.start_at, row.end_at),
        "description": row.note or "",
        "rawStartDate": row.start_at.date().isoformat(),
        "rawStartTime": row.start_at.strftime("%H:%M"),
        "rawEndDate": row.end_at.date().isoformat(),
        "rawEndTime": row.end_at.strftime("%H:%M"),
        "note": row.note or "",
    }


def _task_urgency_label(due_at: datetime | None):
    if not due_at:
        return ""
    today = PORTAL_TODAY
    due_date = due_at.date()
    if due_date < today:
        return "Overdue"
    if due_date == today:
        return "Due Today"
    tomorrow = today.fromordinal(today.toordinal() + 1)
    if due_date == tomorrow:
        return "Due Tomorrow"
    return f"Due in {(due_date - today).days} Days"


def _student_academics_payload(s, st):
    program, dept = _student_program_and_department(s, st)
    enrolls = _student_current_enrollments(s, st)
    sections = _student_sections(s, enrolls)
    course_map = _student_courses_map(s, sections)
    faculty_names = _faculty_names(s)
    pref_map = _student_course_preferences(s, st, list(sections.keys()))
    result_summary = _student_result_history_rows(s, st)

    ordered_enrolls = sorted(
        enrolls,
        key=lambda row: (
            -(course_map.get(sections.get(row.section_id).course_id).semester or 0)
            if sections.get(row.section_id) and course_map.get(sections.get(row.section_id).course_id)
            else 0,
            course_map.get(sections.get(row.section_id).course_id).code
            if sections.get(row.section_id) and course_map.get(sections.get(row.section_id).course_id)
            else "",
            sections.get(row.section_id).section_code if sections.get(row.section_id) else "",
        ),
    )

    courses = []
    for enrollment in ordered_enrolls:
        row = _student_course_view_row(s, st, enrollment, sections, course_map, faculty_names, pref_map)
        if row:
            courses.append(row)

    section_ids = list(sections.keys())
    current_course_codes = {row["course_code"] for row in courses}

    task_rows = (
        s.query(D.Assignment)
        .filter(
            D.Assignment.section_id.in_(section_ids) if section_ids else False,
            D.Assignment.status.in_(["published", "open"]),
        )
        .order_by(D.Assignment.due_at, D.Assignment.assigned_at.desc())
        .all()
    )
    pending_tasks = []
    for row in task_rows:
        section = sections.get(row.section_id)
        course = course_map.get(section.course_id) if section and section.course_id else None
        faculty = faculty_names.get(section.faculty_person_id, "-") if section else "-"
        pending_tasks.append(
            {
                "id": row.id,
                "title": row.title,
                "course_code": course.code if course else "",
                "course_title": course.title if course else "",
                "semester": course.semester if course else None,
                "urgency": _task_urgency_label(row.due_at),
                "due_at": row.due_at.isoformat() if row.due_at else "",
                "source_label": faculty if faculty != "-" else _source_label(row.created_by, fallback="Faculty"),
            }
        )

    now = datetime.utcnow()
    assessment_rows = (
        s.query(D.Assessment)
        .filter(
            D.Assessment.section_id.in_(section_ids) if section_ids else False,
            D.Assessment.assessment_type.in_(["quiz", "test"]),
            D.Assessment.published == True,
            D.Assessment.scheduled_at != None,
            D.Assessment.scheduled_at >= now,
        )
        .order_by(D.Assessment.scheduled_at)
        .all()
    )
    upcoming_assessments = []
    for row in assessment_rows:
        section = sections.get(row.section_id)
        course = course_map.get(section.course_id) if section and section.course_id else None
        faculty = faculty_names.get(section.faculty_person_id, "-") if section else "-"
        upcoming_assessments.append(
            {
                "id": row.id,
                "name": row.name,
                "type": row.assessment_type,
                "course_code": course.code if course else "",
                "course_title": course.title if course else "",
                "semester": course.semester if course else None,
                "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else "",
                "end_at": row.end_at.isoformat() if row.end_at else "",
                "source_label": faculty if faculty != "-" else "Faculty / Examination Office",
            }
        )

    dept_courses = (
        s.query(D.Course)
        .filter(D.Course.dept_id == st.dept_id if st.dept_id else False)
        .order_by(D.Course.semester, D.Course.code)
        .all()
    )
    current_load_by_catalog_key = {}
    for row in courses:
        key = _catalog_term_key(row.get("course_id") or "", row.get("semester"), row.get("course_code") or "")
        if key:
            current_load_by_catalog_key.setdefault(key, []).append(row)

    catalog_map = {}

    def ensure_catalog_entry(base_course_id: str, code: str, title: str, credits, semester_value, source_label: str):
        catalog_key = _catalog_term_key(base_course_id, semester_value, code)
        if not catalog_key:
            return None
        load_rows = current_load_by_catalog_key.get(catalog_key, [])
        entry = catalog_map.setdefault(
            catalog_key,
            {
                "course_id": catalog_key,
                "base_course_id": (base_course_id or code or "").strip(),
                "code": code,
                "title": title,
                "credits": credits,
                "semester": semester_value,
                "is_current_load": bool(load_rows),
                "current_sections": [item["section"] for item in load_rows],
                "faculty": load_rows[0]["faculty"] if load_rows else "",
                "schedule": load_rows[0]["schedule"] if load_rows else "",
                "source_label": "Current enrolment" if load_rows else source_label,
            },
        )
        entry["base_course_id"] = entry.get("base_course_id") or (base_course_id or code or "").strip()
        entry["code"] = entry.get("code") or code
        entry["title"] = entry.get("title") or title
        entry["credits"] = entry.get("credits") if entry.get("credits") not in (None, "") else credits
        entry["semester"] = entry.get("semester") or semester_value
        if load_rows:
            entry["is_current_load"] = True
            entry["current_sections"] = [item["section"] for item in load_rows]
            entry["faculty"] = load_rows[0]["faculty"]
            entry["schedule"] = load_rows[0]["schedule"]
            entry["source_label"] = "Current enrolment"
        elif source_label and source_label not in (entry.get("source_label") or ""):
            entry["source_label"] = (
                f"{entry['source_label']} / {source_label}"
                if entry.get("source_label")
                else source_label
            )
        return entry

    for row in dept_courses:
        ensure_catalog_entry(row.id, row.code, row.title, row.credits, row.semester, "Department catalogue")
    for row in course_map.values():
        if row and row.id:
            ensure_catalog_entry(row.id, row.code, row.title, row.credits, row.semester, "Department catalogue")
    for row in result_summary["latest_by_term_subject"].values():
        ensure_catalog_entry(
            row.course_id or row.subject_code or "",
            row.subject_code or "",
            row.subject_title or "",
            row.credits,
            row.semester,
            "Published result history",
        )

    catalog = sorted(
        catalog_map.values(),
        key=lambda row: (int(row.get("semester") or 0), row.get("code") or "", row.get("title") or ""),
    )

    attendance_values = [row["attendance_pct"] for row in courses if row["attendance_pct"] is not None]
    overall_attendance = round(sum(attendance_values) / len(attendance_values)) if attendance_values else None
    total_credits = sum(row["credits"] or 0 for row in courses)
    available_semesters = sorted({row["semester"] for row in courses if row.get("semester")}, reverse=True)
    official_cgpa = result_summary["cgpa"]

    return {
        "student": {
            "name": st.name,
            "roll_no": st.roll_no,
            "program": program.name if program else "",
            "department": dept.name if dept else "",
            "semester": st.semester,
            "batch": st.batch,
            "section": st.section,
        },
        "summary": {
            "enrolled_courses": len(courses),
            "total_credits": total_credits,
            "attendance_pct": overall_attendance,
            "attendance_label": _attendance_label(overall_attendance),
            "cgpa": official_cgpa,
            "cgpa_label": _cgpa_label(official_cgpa),
            "pending_tasks": len(pending_tasks),
            "upcoming_assessments": len(upcoming_assessments),
        },
        "filters": {
            "current_semester": st.semester,
            "available_semesters": available_semesters,
        },
        "courses": courses,
        "catalog": catalog,
        "pending_tasks": pending_tasks,
        "upcoming_assessments": upcoming_assessments,
        "current_course_codes": sorted(current_course_codes),
        "refreshed_at": datetime.utcnow().isoformat(),
    }


@router.get("/student/home")
def student_home(ctx=Depends(auth), s=Depends(db)):
    st = _student_or_404(s, ctx)
    program, dept = _student_program_and_department(s, st)
    enrolls = _student_enrollments(s, st)
    invoices, fee_balance = _student_fee_summary(s, st.id)
    att_pct = _student_attendance_pct(s, st)
    backlog = _student_backlog_summary(s, st.id)
    result_summary = _student_result_history_rows(s, st)
    official_cgpa = result_summary["cgpa"]
    loans = _student_active_loans_query(s, st).count()
    open_invoices = [
        row for row in invoices
        if row.status != "paid" and max((row.amount or 0) - (row.paid or 0), 0) > 0 and row.due_date
    ]
    next_due = sorted(open_invoices, key=lambda row: row.due_date)[0] if open_invoices else None
    study_year = _study_year(st.semester)
    backlog_subjects = [
        {
            "subject_code": item["subject_code"],
            "subject_title": item["subject_title"],
            "semester": item["semester"],
        }
        for item in backlog["subjects"]
    ]
    return {
        "profile": {
            "name": st.name,
            "roll_no": st.roll_no,
            "cgpa": official_cgpa,
            "semester": st.semester,
            "batch": st.batch,
            "department": dept.name if dept else "",
            "program": program.name if program else "",
            "section": st.section,
            "hosteller": st.hosteller,
            "scholarship": st.scholarship,
            "blood_group": st.blood_group or "",
            "student_type": st.student_type or "Regular",
            "study_year": study_year,
            "study_year_label": _ordinal(study_year),
            "current_backlogs": backlog["current"],
            "backlog_subjects": backlog_subjects,
        },
        "kpis": {
            "courses": len(enrolls),
            "attendance_pct": att_pct,
            "cgpa": official_cgpa,
            "current_backlogs": backlog["current"],
            "backlog_subjects": backlog_subjects,
            "fee_balance": fee_balance,
            "fee_due_date": next_due.due_date.isoformat() if next_due and next_due.due_date else "",
            "library_loans": loans,
            "loan_limit": 5,
            "attendance_label": _attendance_label(att_pct),
            "cgpa_label": _cgpa_label(official_cgpa),
            "backlog_label": "No active backlog" if backlog["current"] == 0 else f"{backlog['current']} subject{'s' if backlog['current'] != 1 else ''} pending",
            "fee_label": "Outstanding balance" if fee_balance else "No dues",
            "library_label": "Active loans" if loans else "No active loans",
        },
        "digital_id": _digital_id_payload(s, st),
    }


@router.get("/student/courses")
def student_courses(ctx=Depends(auth), s=Depends(db)):
    st = _student_or_404(s, ctx)
    return _student_academics_payload(s, st)


@router.put("/student/courses/{section_id}/view")
def update_student_course_view(section_id: str, body: StudentCourseViewUpdateIn, ctx=Depends(auth), s=Depends(db)):
    st = _student_or_404(s, ctx)
    enrolls = _student_current_enrollments(s, st)
    section_ids = {row.section_id for row in enrolls}
    if section_id not in section_ids:
        raise HTTPException(404, "Course section not found in this student academics view")

    pref_id = _student_course_pref_id(st.id, section_id)
    row = s.query(D.StudentCourseViewPreference).get(pref_id)
    faculty = (body.faculty or "").strip()
    schedule = (body.schedule or "").strip()

    if not faculty and not schedule:
        if row:
            s.delete(row)
            s.commit()
        return {"status": "reset"}

    if row is None:
        row = D.StudentCourseViewPreference(
            id=pref_id,
            tenant_id=TENANT,
            student_id=st.id,
            section_id=section_id,
            created_by=ctx["sub"],
        )
        s.add(row)

    row.faculty_label = faculty
    row.schedule_label = schedule
    row.updated_by = ctx["sub"]
    row.updated_at = datetime.utcnow()
    s.commit()

    sections = _student_sections(s, enrolls)
    course_map = _student_courses_map(s, sections)
    faculty_names = _faculty_names(s)
    pref_map = _student_course_preferences(s, st, [section_id])
    enrollment = next((item for item in enrolls if item.section_id == section_id), None)
    payload = _student_course_view_row(s, st, enrollment, sections, course_map, faculty_names, pref_map)
    return {"course": payload}


@router.get("/student/attendance")
def student_attendance(ctx=Depends(auth), s=Depends(db)):
    st = _student_or_404(s, ctx)
    program, dept = _student_program_and_department(s, st)
    enrolls = _student_current_enrollments(s, st)
    sections = _student_sections(s, enrolls)
    course_map = _student_courses_map(s, sections)
    faculty_names = _faculty_names(s)
    records = (
        _student_attendance_query(s, st)
        .order_by(D.AttendanceRecord.on_date.desc(), desc(D.AttendanceRecord.updated_at), D.AttendanceRecord.id.desc())
        .all()
    )

    totals_by_section = {}
    for row in records:
        bucket = totals_by_section.setdefault(row.section_id, {"present": 0, "total": 0})
        bucket["total"] += 1
        if row.present:
            bucket["present"] += 1

    def course_status(pct: int | None):
        if pct is None:
            return {"key": "pending", "label": "Pending", "tone": "pending"}
        if pct >= 80:
            return {"key": "good", "label": "Good", "tone": "good"}
        if pct >= 75:
            return {"key": "warning", "label": "Warning", "tone": "warning"}
        return {"key": "critical", "label": "Critical", "tone": "critical"}

    courses = []
    for enrollment in sorted(
        enrolls,
        key=lambda row: (
            -(course_map.get(sections.get(row.section_id).course_id).semester or 0)
            if sections.get(row.section_id) and course_map.get(sections.get(row.section_id).course_id)
            else 0,
            course_map.get(sections.get(row.section_id).course_id).code
            if sections.get(row.section_id) and course_map.get(sections.get(row.section_id).course_id)
            else "",
        ),
    ):
        section = sections.get(enrollment.section_id)
        course = course_map.get(section.course_id) if section and section.course_id else None
        if not section or not course:
            continue
        counts = totals_by_section.get(section.id, {"present": 0, "total": 0})
        pct = round((100 * counts["present"]) / counts["total"]) if counts["total"] else None
        status_meta = course_status(pct)
        courses.append(
            {
                "section_id": section.id,
                "course_id": course.id,
                "course_code": course.code,
                "course_title": course.title,
                "faculty": faculty_names.get(section.faculty_person_id, "-"),
                "semester": course.semester,
                "section": section.section_code,
                "room": section.room,
                "schedule": _section_schedule_string(s, section.id, section.schedule),
                "attended": counts["present"],
                "total": counts["total"],
                "attendance_pct": pct,
                "status": status_meta,
            }
        )

    record_rows = []
    for row in records:
        section = sections.get(row.section_id)
        course = course_map.get(section.course_id) if section and section.course_id else None
        if not section or not course:
            continue
        status_meta = _attendance_status_meta(_attendance_status_key(row))
        record_rows.append(
            {
                "id": row.id,
                "section_id": section.id,
                "course_id": course.id,
                "course_code": course.code,
                "course_title": course.title,
                "faculty": faculty_names.get(section.faculty_person_id, "-"),
                "semester": course.semester,
                "section": section.section_code,
                "on_date": row.on_date.isoformat() if row.on_date else "",
                "present": bool(row.present),
                "status": status_meta,
                "note": (row.note or "").strip(),
                "source_label": (row.marked_by or "").strip() or "Department Office",
                "updated_at": _attendance_updated_at(row).isoformat(),
            }
        )

    today = PORTAL_TODAY
    today_records = {}
    for row in records:
        if row.on_date == today and row.section_id not in today_records:
            today_records[row.section_id] = row

    today_rows = []
    for item in _student_today_classes_payload(s, st):
        row = today_records.get(item["section_id"])
        if row:
            status_meta = _attendance_status_meta(_attendance_status_key(row))
            note = (row.note or "").strip() or status_meta["short_note"]
            source_label = (row.marked_by or "").strip() or "Department Office"
        else:
            status_meta = _attendance_status_meta("pending")
            note = status_meta["short_note"]
            source_label = "Department Office"
        today_rows.append(
            {
                **item,
                "status": status_meta,
                "note": note,
                "source_label": source_label,
            }
        )

    available_semesters = sorted({row["semester"] for row in courses if row.get("semester")}, reverse=True)
    available_months = sorted(
        {
            (row["on_date"] or "")[:7]
            for row in record_rows
            if row.get("on_date")
        } | {today.replace(day=1).isoformat()[:7]},
        reverse=True,
    )
    last_synced_at = max(
        [_attendance_updated_at(row) for row in records],
        default=PORTAL_NOW,
    )
    return {
        "student": {
            "name": st.name,
            "roll_no": st.roll_no,
            "program": program.name if program else "",
            "department": dept.name if dept else "",
            "semester": st.semester,
            "batch": st.batch,
            "section": st.section,
        },
        "policy": {
            "minimum_attendance_pct": 75,
            "low_attendance_pct": 80,
        },
        "filters": {
            "current_semester": st.semester,
            "available_semesters": available_semesters,
            "available_months": available_months,
        },
        "courses": courses,
        "records": record_rows,
        "today": {
            "date": today.isoformat(),
            "label": today.strftime("%a, %d %b %Y"),
            "items": today_rows,
        },
        "refreshed_at": PORTAL_NOW.isoformat(),
        "last_synced_at": last_synced_at.isoformat(),
    }


@router.get("/student/results")
def student_results(ctx=Depends(auth), s=Depends(db)):
    st = _student_or_404(s, ctx)
    payload = _student_scores_payload(s, st)
    return {
        "marks": [
            {
                "course": row["course_code"],
                "assessment": row["assessment_name"],
                "score": row["score"],
                "max": row["max_marks"],
                "type": row["assessment_type"],
                "scheduled_at": "",
                "published_at": row["published_at"],
                "percentage": row["percentage"],
            }
            for row in payload["published_marks"]
        ],
        "cgpa": payload["summary"]["cgpa"],
    }


@router.get("/student/examinations")
def student_examinations(
    academic_year: str = "",
    semester: str = "",
    course_id: str = "",
    assessment_type: str = "",
    status: str = "all",
    ctx=Depends(auth),
    s=Depends(db),
):
    return _student_examinations_payload(
        s,
        _student_or_404(s, ctx),
        academic_year=academic_year,
        semester=semester,
        course_id=course_id,
        assessment_type=assessment_type,
        status=status,
    )


@router.get("/student/scores")
def student_scores(
    academic_year: str = "",
    semester: str = "",
    course_id: str = "",
    assessment_type: str = "",
    ctx=Depends(auth),
    s=Depends(db),
):
    return _student_scores_payload(
        s,
        _student_or_404(s, ctx),
        academic_year=academic_year,
        semester=semester,
        course_id=course_id,
        assessment_type=assessment_type,
    )


class RazorpayOrderIn(BaseModel):
    invoice_id: str
    # Fee amount before GST.  Omit it to pay the complete outstanding balance.
    amount: float | None = None


class RazorpayVerifyIn(BaseModel):
    invoice_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/student/fees/razorpay/order")
def create_razorpay_order(body: RazorpayOrderIn, ctx=Depends(auth), s=Depends(db)):
    student = _student_or_404(s, ctx)
    invoice = s.get(D.FeeInvoice, body.invoice_id)
    if not invoice or invoice.student_id != student.id:
        raise HTTPException(404, "Fee invoice not found")
    base_balance = round(max((invoice.amount or 0) - (invoice.paid or 0), 0), 2)
    if base_balance <= 0:
        raise HTTPException(409, "This invoice is already paid")
    base_amount = round(float(body.amount), 2) if body.amount is not None else base_balance
    if base_amount <= 0:
        raise HTTPException(422, "Payment amount must be greater than zero")
    if base_amount > base_balance:
        raise HTTPException(422, f"Payment amount cannot exceed the outstanding fee of ₹{base_balance:,.2f}")
    gst_amount = _gst(base_amount)
    charge_amount = round(base_amount + gst_amount, 2)
    key, _ = _razorpay_configured()
    remote = _razorpay_request("/orders", {"amount": int(charge_amount * 100), "currency": "INR", "receipt": f"ICMS-{invoice.id}", "notes": {"invoice_id": invoice.id, "student_id": student.id, "base_amount": str(base_amount), "gst_rate": "18", "gst_amount": str(gst_amount)}})
    order = D.RazorpayOrder(id=uid(), tenant_id=TENANT, invoice_id=invoice.id, student_id=student.id,
                            razorpay_order_id=remote["id"], amount=charge_amount)
    s.add(order); s.commit()
    return {"key_id": key, "order_id": order.razorpay_order_id, "amount": int(charge_amount * 100),
            "currency": "INR", "student": {"name": student.name, "email": student.email}, "description": f"{invoice.term} (includes 18% GST)", "base_amount": base_amount, "gst_amount": gst_amount, "total_amount": charge_amount}


@router.post("/student/fees/razorpay/verify")
def verify_razorpay_payment(body: RazorpayVerifyIn, ctx=Depends(auth), s=Depends(db)):
    student = _student_or_404(s, ctx)
    order = s.query(D.RazorpayOrder).filter(D.RazorpayOrder.razorpay_order_id == body.razorpay_order_id,
                                             D.RazorpayOrder.invoice_id == body.invoice_id,
                                             D.RazorpayOrder.student_id == student.id).first()
    if not order:
        raise HTTPException(404, "Payment order not found")
    if order.status == "paid":
        return {"status": "paid", "message": "Payment was already recorded"}
    _, secret = _razorpay_configured()
    expected = hmac.new(secret.encode(), f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, body.razorpay_signature):
        raise HTTPException(400, "Payment signature verification failed")
    invoice = s.get(D.FeeInvoice, order.invoice_id)
    if not invoice:
        raise HTTPException(404, "Fee invoice not found")
    order.status, order.razorpay_payment_id, order.paid_at = "paid", body.razorpay_payment_id, datetime.utcnow()
    base_paid_amount = min(round(float(order.amount or 0) / (1 + GST_RATE), 2), max((invoice.amount or 0) - (invoice.paid or 0), 0))
    payment = D.Payment(id=uid(), tenant_id=TENANT, invoice_id=invoice.id, student_id=student.id,
                    amount=base_paid_amount, method="razorpay", reference=body.razorpay_payment_id, status="success")
    s.add(payment); s.flush()
    _settle_payment(s, payment, ctx["sub"])
    s.commit()
    write_audit(s, ctx["sub"], student.name, ctx["office_n"], "fee.payment.razorpay", f"invoice:{invoice.id}", "due", invoice.status, f"Razorpay payment {body.razorpay_payment_id}")
    return {"status": invoice.status, **_invoice_display_amounts(invoice, order.amount)}


@router.get("/student/fees/invoices/{invoice_id}/receipt.pdf")
def student_fee_receipt(invoice_id: str, payment_id: str = "", ctx=Depends(auth), s=Depends(db)):
    return _receipt_response(_student_or_404(s, ctx), invoice_id, s, payment_id or None)


@router.get("/student/fees")
def student_fees(ctx=Depends(auth), s=Depends(db)):
    st = _student_or_404(s, ctx)
    invoices, balance = _student_fee_summary(s, st.id)
    structures = {row.id: row for row in s.query(D.FeeStructure).all()}
    semesters = {row.id: row.name for row in s.query(D.Semester).all()}
    payments = (
        s.query(D.Payment)
        .filter(D.Payment.student_id == st.id)
        .order_by(desc(D.Payment.at))
        .all()
    )
    invoice_data = []
    for row in invoices:
        amounts = _invoice_display_amounts(row)
        invoice_data.append({"id": row.id, "term": row.term, "semester": semesters.get(structures[row.fee_structure_id].semester_id, row.term) if row.fee_structure_id in structures else row.term, **amounts, "status": row.status, "due_date": row.due_date.isoformat() if row.due_date else ""})
    return {
        "summary": {"balance": round(sum(item["balance"] for item in invoice_data), 2)},
        "invoices": invoice_data,
        "payments": [
            {
                "id": row.id,
                "invoice_id": row.invoice_id,
                "amount": row.amount,
                "method": row.method,
                "reference": row.reference,
                "at": row.at.isoformat() if row.at else "",
            }
            for row in payments
        ],
    }


@router.get("/student/digital-id")
def student_digital_id(ctx=Depends(auth), s=Depends(db)):
    return {"digital_id": _digital_id_payload(s, _student_or_404(s, ctx))}


@router.get("/student/today-classes")
def student_today_classes(ctx=Depends(auth), s=Depends(db)):
    return {"classes": _student_today_classes_payload(s, _student_or_404(s, ctx))}


@router.get("/student/tasks")
def student_tasks(ctx=Depends(auth), s=Depends(db)):
    return {"tasks": _student_tasks_payload(s, _student_or_404(s, ctx))}


@router.get("/student/upcoming-assessments")
def student_upcoming_assessments(ctx=Depends(auth), s=Depends(db)):
    payload = _student_examinations_payload(s, _student_or_404(s, ctx))
    return {"assessments": payload["upcoming_assessments"]}


@router.get("/student/announcements")
def student_announcements(ctx=Depends(auth), s=Depends(db)):
    return {"announcements": _student_announcements_payload(s, _student_or_404(s, ctx))}


@router.get("/student/calendar")
def student_calendar(start: str = "", ctx=Depends(auth), s=Depends(db)):
    st = _student_or_404(s, ctx)
    month_start = _month_start(start)
    month_end = _month_end(month_start)
    month_start_dt = datetime.combine(month_start, datetime.min.time())
    month_end_dt = datetime.combine(month_end, datetime.max.time())
    now = datetime.utcnow()
    today = date.today()

    enrolls, sections, courses, faculty_names = _student_learning_context(s, st)
    section_ids = list(sections.keys())

    events = []
    month_assignment_count = 0
    month_assessment_count = 0

    timetable_rows = (
        s.query(D.TimetableEntry)
        .filter(
            D.TimetableEntry.section_id.in_(section_ids) if section_ids else False,
            D.TimetableEntry.status == "active",
            or_(D.TimetableEntry.effective_from == None, D.TimetableEntry.effective_from <= month_end),
            or_(D.TimetableEntry.effective_to == None, D.TimetableEntry.effective_to >= month_start),
        )
        .order_by(D.TimetableEntry.day_of_week, D.TimetableEntry.start_time)
        .all()
    )
    for row in timetable_rows:
        section = sections.get(row.section_id)
        course = courses.get(section.course_id) if section and section.course_id else None
        faculty = faculty_names.get(section.faculty_person_id, "-") if section else "-"
        first_live_day = max(month_start, row.effective_from or month_start)
        last_live_day = min(month_end, row.effective_to or month_end)
        cursor = first_live_day + timedelta(days=(row.day_of_week - first_live_day.weekday()) % 7)
        while cursor <= last_live_day:
            start_dt = _combine_day_time(cursor, row.start_time, 9)
            end_dt = _combine_day_time(cursor, row.end_time, 10)
            events.append(
                {
                    "id": f"tt_{row.id}_{cursor.isoformat()}",
                    "title": course.code if course and course.code else (course.title if course else "Class"),
                    "subtitle": course.title if course else "",
                    "meta": f"{faculty} · {row.room or (section.room if section else '')}".strip(" ·"),
                    "category": "Classes",
                    "kind": "class",
                    "module": "academics",
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                    "all_day": False,
                    "location": row.room or (section.room if section else ""),
                    "source_label": _source_label(row.created_by, fallback="Dean Academics Office"),
                    "time_label": f"{row.start_time} - {row.end_time}",
                    "description": f"{course.title if course else 'Class session'} with {faculty}",
                }
            )
            cursor += timedelta(days=7)

    academic_rows = (
        s.query(D.AcademicCalendarEntry)
        .filter(
            D.AcademicCalendarEntry.status != "deleted",
            D.AcademicCalendarEntry.start_date <= month_end,
            or_(D.AcademicCalendarEntry.end_date == None, D.AcademicCalendarEntry.end_date >= month_start),
        )
        .order_by(D.AcademicCalendarEntry.start_date, D.AcademicCalendarEntry.title)
        .all()
    )
    for row in academic_rows:
        start_dt = datetime.combine(row.start_date, datetime.min.time())
        end_dt = datetime.combine(row.end_date or row.start_date, datetime.max.time())
        events.append(
            {
                "id": f"acad_{row.id}",
                "title": row.title,
                "subtitle": row.category,
                "meta": row.campus,
                "category": "Academic Calendar",
                "kind": "academic",
                "module": "academic_calendar",
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "all_day": True,
                "location": row.campus,
                "source_label": _source_label(row.created_by, row.owner_office_n, "Dean Academics Office"),
                "time_label": "All day",
                "description": row.description,
            }
        )

    assignment_rows = (
        s.query(D.Assignment)
        .filter(
            D.Assignment.section_id.in_(section_ids) if section_ids else False,
            D.Assignment.status.in_(["published", "open"]),
            D.Assignment.due_at != None,
        )
        .order_by(D.Assignment.due_at, D.Assignment.assigned_at.desc())
        .all()
    )
    deadline_items = []
    for row in assignment_rows:
        section = sections.get(row.section_id)
        course = courses.get(section.course_id) if section and section.course_id else None
        faculty = faculty_names.get(section.faculty_person_id, "-") if section else "-"
        if month_start_dt <= row.due_at <= month_end_dt:
            if row.due_at >= now:
                month_assignment_count += 1
            events.append(
                {
                    "id": f"asg_{row.id}",
                    "title": row.title,
                    "subtitle": course.code if course and course.code else "Assignment",
                    "meta": course.title if course else faculty,
                    "category": "Assignments",
                    "kind": "assignment",
                    "module": "academics",
                    "start": row.due_at.isoformat(),
                    "end": row.due_at.isoformat(),
                    "all_day": False,
                    "location": "",
                    "source_label": faculty if faculty != "-" else _source_label(row.created_by, fallback="Faculty"),
                    "time_label": row.due_at.strftime("%I:%M %p").lstrip("0"),
                    "description": row.description,
                }
            )
        if row.due_at >= now:
            deadline_items.append(
                {
                    "id": f"deadline_asg_{row.id}",
                    "title": row.title,
                    "subtitle": course.title if course else "Course assignment",
                    "course_code": course.code if course else "",
                    "kind": "assignment",
                    "module": "academics",
                    "date": row.due_at.isoformat(),
                    "source_label": faculty if faculty != "-" else _source_label(row.created_by, fallback="Faculty"),
                    "badge": _task_urgency_label(row.due_at),
                    "_sort": row.due_at,
                }
            )

    assessment_rows = (
        s.query(D.Assessment)
        .filter(
            D.Assessment.section_id.in_(section_ids) if section_ids else False,
            D.Assessment.assessment_type.in_(["quiz", "test"]),
            D.Assessment.published == True,
            D.Assessment.scheduled_at != None,
        )
        .order_by(D.Assessment.scheduled_at)
        .all()
    )
    for row in assessment_rows:
        section = sections.get(row.section_id)
        course = courses.get(section.course_id) if section and section.course_id else None
        faculty = faculty_names.get(section.faculty_person_id, "-") if section else "-"
        if month_start_dt <= row.scheduled_at <= month_end_dt:
            if row.scheduled_at >= now:
                month_assessment_count += 1
            events.append(
                {
                    "id": f"asmt_{row.id}",
                    "title": row.name,
                    "subtitle": course.code if course and course.code else (row.assessment_type or "Assessment").title(),
                    "meta": course.title if course else faculty,
                    "category": "Quiz / Test",
                    "kind": "assessment",
                    "module": "examinations",
                    "start": row.scheduled_at.isoformat(),
                    "end": (row.end_at or row.scheduled_at).isoformat(),
                    "all_day": False,
                    "location": section.room if section else "",
                    "source_label": faculty if faculty != "-" else "Faculty / Examination Office",
                    "time_label": row.scheduled_at.strftime("%I:%M %p").lstrip("0"),
                    "description": row.instructions or "",
                }
            )
        if row.scheduled_at >= now:
            deadline_items.append(
                {
                    "id": f"deadline_asmt_{row.id}",
                    "title": row.name,
                    "subtitle": course.title if course else "Scheduled assessment",
                    "course_code": course.code if course else "",
                    "kind": "assessment",
                    "module": "examinations",
                    "date": row.scheduled_at.isoformat(),
                    "source_label": faculty if faculty != "-" else "Faculty / Examination Office",
                    "badge": f"{(row.assessment_type or 'quiz').title()}",
                    "_sort": row.scheduled_at,
                }
            )

    invoices = (
        s.query(D.FeeInvoice)
        .filter(D.FeeInvoice.student_id == st.id)
        .order_by(D.FeeInvoice.due_date, D.FeeInvoice.term)
        .all()
    )
    for row in invoices:
        balance = max((row.amount or 0) - (row.paid or 0), 0)
        if row.status == "paid" or balance <= 0 or not row.due_date:
            continue
        due_dt = datetime.combine(row.due_date, datetime.min.time())
        if month_start <= row.due_date <= month_end:
            events.append(
                {
                    "id": f"fee_{row.id}",
                    "title": "Fee Due",
                    "subtitle": row.term,
                    "meta": f"Outstanding {balance:,.0f}",
                    "category": "Fee Due",
                    "kind": "finance",
                    "module": "finance",
                    "start": due_dt.isoformat(),
                    "end": due_dt.isoformat(),
                    "all_day": True,
                    "location": "Finance Office",
                    "source_label": "Finance Office",
                    "time_label": "All day",
                    "description": f"Outstanding balance: {balance:,.0f}",
                }
            )
        if row.due_date >= today:
            deadline_items.append(
                {
                    "id": f"deadline_fee_{row.id}",
                    "title": f"Fee Due ({row.term})",
                    "subtitle": "Academic fees",
                    "course_code": "",
                    "kind": "finance",
                    "module": "finance",
                    "date": due_dt.isoformat(),
                    "source_label": "Finance Office",
                    "badge": f"{balance:,.0f}",
                    "_sort": due_dt,
                }
            )

    active_loans = _student_active_loans_query(s, st).order_by(D.BookLoan.due_on).all()
    loan_book_ids = sorted({row.book_id for row in active_loans if row.book_id})
    books = {}
    if loan_book_ids:
        books = {row.id: row for row in s.query(D.Book).filter(D.Book.id.in_(loan_book_ids)).all()}
    for row in active_loans:
        if not row.due_on:
            continue
        due_dt = datetime.combine(row.due_on, datetime.min.time())
        book = books.get(row.book_id)
        if month_start <= row.due_on <= month_end:
            events.append(
                {
                    "id": f"loan_{row.id}",
                    "title": "Library Return Due",
                    "subtitle": book.title if book else "Central Library",
                    "meta": "Borrowed item due back",
                    "category": "Library",
                    "kind": "library",
                    "module": "library",
                    "start": due_dt.isoformat(),
                    "end": due_dt.isoformat(),
                    "all_day": True,
                    "location": "Central Library",
                    "source_label": "Library Circulation",
                    "time_label": "All day",
                    "description": f"Return {book.title if book else 'your borrowed item'} before fines apply.",
                }
            )
        if row.due_on >= today:
            deadline_items.append(
                {
                    "id": f"deadline_loan_{row.id}",
                    "title": "Library Return",
                    "subtitle": book.title if book else "Borrowed library item",
                    "course_code": "",
                    "kind": "library",
                    "module": "library",
                    "date": due_dt.isoformat(),
                    "source_label": "Library Circulation",
                    "badge": "",
                    "_sort": due_dt,
                }
            )

    personal_rows = (
        s.query(D.StudentCalendarEvent)
        .filter(
            D.StudentCalendarEvent.student_id == st.id,
            D.StudentCalendarEvent.status != "deleted",
            D.StudentCalendarEvent.start_at <= month_end_dt,
            D.StudentCalendarEvent.end_at >= month_start_dt,
        )
        .order_by(D.StudentCalendarEvent.start_at, D.StudentCalendarEvent.title)
        .all()
    )
    for row in personal_rows:
        events.append(_student_personal_event_payload(row))

    deadline_items.sort(key=lambda item: (item["_sort"], item["title"]))
    for row in deadline_items:
        row.pop("_sort", None)

    upcoming_academic = (
        s.query(D.AcademicCalendarEntry)
        .filter(
            D.AcademicCalendarEntry.status != "deleted",
            or_(D.AcademicCalendarEntry.end_date == None, D.AcademicCalendarEntry.end_date >= today),
        )
        .order_by(D.AcademicCalendarEntry.start_date, D.AcademicCalendarEntry.title)
        .limit(6)
        .all()
    )

    events.sort(key=lambda item: (item["start"], item["title"]))

    return {
        "range": {
            "start": month_start.isoformat(),
            "end": month_end.isoformat(),
            "label": _month_label(month_start),
        },
        "summary": {
            "month_events": len(events),
            "classes_today": len(_student_today_classes_payload(s, st)),
            "due_assignments": month_assignment_count,
            "upcoming_assessments": month_assessment_count,
        },
        "events": events,
        "today_schedule": _student_today_classes_payload(s, st),
        "deadlines": deadline_items[:6],
        "upcoming_events": [
            {
                "id": row.id,
                "title": row.title,
                "category": row.category,
                "campus": row.campus,
                "start_date": row.start_date.isoformat(),
                "end_date": (row.end_date or row.start_date).isoformat(),
                "description": row.description,
                "source_label": _source_label(row.created_by, row.owner_office_n, "Dean Academics Office"),
                "module": "academic_calendar",
            }
            for row in upcoming_academic
        ],
    }


@router.post("/student/calendar/personal")
def create_student_calendar_personal_event(body: StudentCalendarEventIn, ctx=Depends(auth), s=Depends(db)):
    st = _student_or_404(s, ctx)
    start_at = _parse_portal_datetime(body.start_at, "From date and time")
    end_at = _parse_portal_datetime(body.end_at, "To date and time")
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(400, "Event title is required")
    if end_at < start_at:
        raise HTTPException(400, "To date and time must be after the from date and time")

    row = D.StudentCalendarEvent(
        id=_portal_uid(),
        tenant_id=TENANT,
        student_id=st.id,
        title=title,
        note=(body.note or "").strip(),
        start_at=start_at,
        end_at=end_at,
        created_by=ctx["sub"],
        updated_by=ctx["sub"],
    )
    s.add(row)
    s.commit()
    s.refresh(row)
    return {"event": _student_personal_event_payload(row)}


@router.put("/student/calendar/personal/{event_id}")
def update_student_calendar_personal_event(event_id: str, body: StudentCalendarEventIn, ctx=Depends(auth), s=Depends(db)):
    st = _student_or_404(s, ctx)
    row = (
        s.query(D.StudentCalendarEvent)
        .filter(
            D.StudentCalendarEvent.id == event_id,
            D.StudentCalendarEvent.student_id == st.id,
            D.StudentCalendarEvent.status != "deleted",
        )
        .first()
    )
    if not row:
        raise HTTPException(404, "Personal calendar event not found")

    start_at = _parse_portal_datetime(body.start_at, "From date and time")
    end_at = _parse_portal_datetime(body.end_at, "To date and time")
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(400, "Event title is required")
    if end_at < start_at:
        raise HTTPException(400, "To date and time must be after the from date and time")

    row.title = title
    row.note = (body.note or "").strip()
    row.start_at = start_at
    row.end_at = end_at
    row.updated_by = ctx["sub"]
    row.updated_at = datetime.utcnow()
    s.commit()
    s.refresh(row)
    return {"event": _student_personal_event_payload(row)}


@router.delete("/student/calendar/personal/{event_id}")
def delete_student_calendar_personal_event(event_id: str, ctx=Depends(auth), s=Depends(db)):
    st = _student_or_404(s, ctx)
    row = (
        s.query(D.StudentCalendarEvent)
        .filter(
            D.StudentCalendarEvent.id == event_id,
            D.StudentCalendarEvent.student_id == st.id,
            D.StudentCalendarEvent.status != "deleted",
        )
        .first()
    )
    if not row:
        raise HTTPException(404, "Personal calendar event not found")

    row.status = "deleted"
    row.updated_by = ctx["sub"]
    row.updated_at = datetime.utcnow()
    s.commit()
    return {"status": "deleted"}


@router.get("/student/library-loans")
def student_library_loans(ctx=Depends(auth), s=Depends(db)):
    st = _student_or_404(s, ctx)
    loans = _student_active_loans_query(s, st).order_by(desc(D.BookLoan.issued_on)).all()
    books = {row.id: row for row in s.query(D.Book).all()}
    return {
        "loans": [
            {
                "id": row.id,
                "book": books.get(row.book_id).title if books.get(row.book_id) else "",
                "issued_on": row.issued_on.isoformat() if row.issued_on else "",
                "due_on": row.due_on.isoformat() if row.due_on else "",
                "fine": row.fine,
            }
            for row in loans
        ]
    }


@router.get("/faculty/home")
def faculty_home(ctx=Depends(auth), s=Depends(db)):
    stf = _staff_or_404(s, ctx)
    sections = s.query(D.Section).filter(D.Section.faculty_person_id == stf.id).all()
    section_ids = [row.id for row in sections]
    enrolled_count = 0
    if section_ids:
        enrolled_count = (
            s.query(D.Enrollment)
            .filter(D.Enrollment.section_id.in_(section_ids), D.Enrollment.status == "enrolled")
            .count()
        )
    dept = s.query(D.Department).get(stf.dept_id) if stf.dept_id else None

    course_map = {course.id: course for course in s.query(D.Course).all()}
    enrollments = (
        s.query(D.Enrollment)
        .filter(
            D.Enrollment.section_id.in_(section_ids),
            D.Enrollment.status == "enrolled",
        )
        .all()
        if section_ids
        else []
    )
    enrollment_by_section = {section.id: 0 for section in sections}
    for enrollment in enrollments:
        enrollment_by_section[enrollment.section_id] = (
            enrollment_by_section.get(enrollment.section_id, 0) + 1
        )

    attendance = (
        s.query(D.AttendanceRecord)
        .filter(D.AttendanceRecord.section_id.in_(section_ids))
        .all()
        if section_ids
        else []
    )
    attendance_by_section = {section.id: [] for section in sections}
    for record in attendance:
        attendance_by_section.setdefault(record.section_id, []).append(record)

    assessments = (
        s.query(D.Assessment)
        .filter(D.Assessment.section_id.in_(section_ids))
        .all()
        if section_ids
        else []
    )
    marks = s.query(D.Mark).filter(D.Mark.assessment_id.in_([item.id for item in assessments])).all() if assessments else []
    marks_by_assessment = {}
    for mark in marks: marks_by_assessment.setdefault(mark.assessment_id, []).append(mark)
    section_rows = []
    for section in sections:
        records = attendance_by_section.get(section.id, [])
        attendance_pct = round(100 * sum(1 for record in records if record.present) / len(records), 1) if records else None
        course = course_map.get(section.course_id)
        section_rows.append({"id": section.id, "course_code": course.code if course else "", "title": course.title if course else "", "section": section.section_code, "schedule": section.schedule, "room": section.room, "enrolled": enrollment_by_section.get(section.id, 0), "capacity": section.capacity, "attendance_pct": attendance_pct})
    total_attendance = sum(len(records) for records in attendance_by_section.values())
    present_attendance = sum(sum(1 for record in records if record.present) for records in attendance_by_section.values())
    average_attendance = round(100 * present_attendance / total_attendance, 1) if total_attendance else None
    max_marks_by_assessment = {assessment.id: assessment.max_marks for assessment in assessments}
    possible_marks = sum(max_marks_by_assessment.get(mark.assessment_id, 100) for mark in marks)
    average_score = round(10 * sum(mark.score for mark in marks) / possible_marks, 2) if possible_marks else None
    pending = []
    # A class on today's timetable still needs attendance when no record has
    # been saved for that section/date.  This derives the reminder from the
    # same assigned sections and attendance rows used by the rest of the page.
    today_short = date.today().strftime("%a")
    for section in sections:
        scheduled_days = (section.schedule or "").split(maxsplit=1)[0].split("/")
        has_class_today = any(day[:3].title() == today_short for day in scheduled_days)
        already_marked = any(record.on_date == date.today() for record in attendance_by_section.get(section.id, []))
        if has_class_today and not already_marked:
            course = course_map.get(section.course_id)
            pending.append({"id": f"attendance-{section.id}-{date.today().isoformat()}", "kind": "attendance",
                            "title": f"Mark attendance: {course.code if course else 'Section'} ({section.section_code})",
                            "course": course.title if course else "Assigned section", "count": 1,
                            "due": "Today"})
    marks_pending = 0
    for assessment in assessments:
        missing = max(0, enrollment_by_section.get(assessment.section_id, 0) - len(marks_by_assessment.get(assessment.id, [])))
        if missing:
            marks_pending += 1
            section = next((item for item in section_rows if item["id"] == assessment.section_id), None)
            pending.append({"id": assessment.id, "kind": "marks", "title": f"Enter marks: {assessment.name}", "course": f"{section['course_code']} ({section['section']})" if section else "Section", "count": missing, "due": "Marks pending"})
    notes = s.query(Notification).filter(Notification.user_id == ctx["sub"]).order_by(Notification.created_at.desc()).limit(4).all()
    day_indexes = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    teaching_schedule = []
    for section in sections:
        parts = (section.schedule or "").split(maxsplit=1)
        days, class_time = (parts[0], parts[1] if len(parts) > 1 else "Time pending") if parts else ("", "Time pending")
        course = course_map.get(section.course_id)
        for day_name in days.split("/"):
            day_index = day_indexes.get(day_name[:3].title())
            if day_index is None:
                continue
            class_date = week_start + timedelta(days=day_index)
            teaching_schedule.append({"id": f"{section.id}-{day_index}", "day": class_date.strftime("%a"),
                                      "date": class_date.isoformat(), "time": class_time,
                                      "section": section.section_code,
                                      "course_code": course.code if course else "",
                                      "subject": course.title if course else "Course unavailable",
                                      "room": section.room or "Room pending"})
    teaching_schedule.sort(key=lambda item: (item["date"], item["time"], item["course_code"]))
    classes_this_week = len(teaching_schedule)

    attendance_trend = []
    for offset in range(5, -1, -1):
        start = week_start - timedelta(weeks=offset)
        end = start + timedelta(days=6)
        records = [record for record in attendance if start <= record.on_date <= end]
        attendance_trend.append({"label": f"Wk {6 - offset}",
                                 "value": round(100 * sum(record.present for record in records) / len(records), 1) if records else None})
    distribution = {"80% and above": 0, "60% – 79%": 0, "40% – 59%": 0, "Below 40%": 0}
    for mark in marks:
        maximum = max_marks_by_assessment.get(mark.assessment_id, 0)
        if not maximum:
            continue
        score_pct = 100 * mark.score / maximum
        if score_pct >= 80: distribution["80% and above"] += 1
        elif score_pct >= 60: distribution["60% – 79%"] += 1
        elif score_pct >= 40: distribution["40% – 59%"] += 1
        else: distribution["Below 40%"] += 1
    return {
        "profile": {"name": stf.name, "emp_id": stf.emp_id,
                    "designation": stf.designation,
                    "department": dept.name if dept else "", "email": stf.email,
                    "phone": stf.phone or None, "office_hours": stf.office_hours or None},
        "kpis": {"sections": len(sections), "students": enrolled_count, "classes_this_week": classes_this_week,
                 "pending_tasks": len(pending), "marks_entry_pending": marks_pending,
                 "average_attendance": average_attendance, "average_grade": average_score},
        "sections": section_rows, "pending_tasks": pending[:4],
        "announcements": [{"id": item.id, "title": item.title, "detail": item.detail, "date": item.created_at.date().isoformat()} for item in notes],
        "teaching_schedule": teaching_schedule,
        "attendance_trend": attendance_trend,
        "marks_distribution": [{"label": label, "value": value} for label, value in distribution.items()],
        "performance": {"assessments": len(assessments), "average_score": round(average_score * 10, 1) if average_score is not None else None,
                        "marks_entered": len(marks), "expected_marks": sum(enrollment_by_section.get(item.section_id, 0) for item in assessments)},
        "role_context": {"active_role": ctx.get("role"), "available_roles": office(ctx["office_n"])["internal_roles"]},
    }
    leave_rows = s.query(D.LeaveRequest).filter(D.LeaveRequest.staff_id == stf.id).all()
    
    return {
        "profile": {
            "name": stf.name,
            "emp_id": stf.emp_id,
            "designation": stf.designation,
            "department": dept.name if dept else "",
        },
        "kpis": {
            "sections": len(sections),
            "students": enrolled_count,
            "leave_requests": len(leave_rows),
        },
    }


@router.get("/faculty/sections")
def faculty_sections(ctx=Depends(auth), s=Depends(db)):
    stf = _staff_or_404(s, ctx)
    sections = s.query(D.Section).filter(D.Section.faculty_person_id == stf.id).all()
    course_map = {row.id: row for row in s.query(D.Course).all()}
    out = []
    for section in sections:
        course = course_map.get(section.course_id)
        enrolled = (
            s.query(D.Enrollment)
            .filter(D.Enrollment.section_id == section.id, D.Enrollment.status == "enrolled")
            .count()
        )
        assessments = s.query(D.Assessment).filter(D.Assessment.section_id == section.id).count()
        out.append(
            {
                "id": section.id,
                "course_code": course.code if course else "",
                "title": course.title if course else "",
                "section": section.section_code,
                "schedule": _section_schedule_string(s, section.id, section.schedule),
                "room": section.room,
                "enrolled": enrolled,
                "assessments": assessments,
            }
        )
    return {"sections": out}


@router.get("/faculty/schedule")
def faculty_schedule(ctx=Depends(auth), s=Depends(db)):
    """Weekly schedule built from the faculty member's assigned sections and staff events."""
    stf = _staff_or_404(s, ctx)
    today = date.today(); week_start = today - timedelta(days=today.weekday()); week_end = week_start + timedelta(days=6)
    courses = {row.id: row for row in s.query(D.Course).all()}
    days = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
    events = []
    sections = s.query(D.Section).filter(D.Section.faculty_person_id == stf.id).all()
    for section in sections:
        parts = (section.schedule or "").split(maxsplit=1); names = parts[0] if parts else ""; class_time = parts[1] if len(parts) > 1 else "Time pending"
        course = courses.get(section.course_id)
        for name in names.split("/"):
            index = days.get(name[:3].title())
            if index is not None:
                events.append({"id": f"class-{section.id}-{index}", "date": (week_start + timedelta(days=index)).isoformat(), "time": class_time, "title": f"{course.code if course else 'Course'} ({section.section_code})", "detail": course.title if course else "Assigned section", "location": section.room or "Room pending", "type": "class", "route": "attendance"})
    for event in s.query(D.CalendarEvent).filter(D.CalendarEvent.status == "published").all():
        if not event.start_at or not (week_start <= event.start_at.date() <= week_end) or event.audience not in ("all", "staff", "leadership"):
            continue
        events.append({"id": f"event-{event.id}", "date": event.start_at.date().isoformat(), "time": "All day" if event.all_day else event.start_at.strftime("%H:%M"), "title": event.title, "detail": event.category, "location": event.location or "Campus", "type": "meeting", "route": "calendar"})
    events.sort(key=lambda item: (item["date"], item["time"], item["title"]))
    leaves = s.query(D.LeaveRequest).filter(D.LeaveRequest.staff_id == stf.id, D.LeaveRequest.status.in_(["pending", "approved"])).count()
    return {"profile": {"name": stf.name, "email": stf.email, "phone": stf.phone, "office_hours": stf.office_hours}, "role": ctx.get("role"), "week_start": week_start.isoformat(), "events": events, "summary": {"classes": sum(item["type"] == "class" for item in events), "meetings": sum(item["type"] == "meeting" for item in events), "sections": len(sections), "leave_requests": leaves}}


@router.get("/faculty/section/{section_id}/students")
def faculty_section_students(section_id: str, ctx=Depends(auth), s=Depends(db)):
    stf = _staff_or_404(s, ctx)
    section = s.query(D.Section).get(section_id)
    if not section or section.faculty_person_id != stf.id:
        raise HTTPException(403, "Not your section")
    enrolls = (
        s.query(D.Enrollment)
        .filter(D.Enrollment.section_id == section_id, D.Enrollment.status == "enrolled")
        .all()
    )
    out = []
    for row in enrolls:
        st = s.query(D.Student).get(row.student_id)
        if not st:
            continue
        out.append(
            {
                "roll_no": st.roll_no,
                "name": st.name,
                "cgpa": st.cgpa,
                "attendance_pct": _student_attendance_pct(s, st, section_id),
            }
        )
    return {"students": out, "section": section.section_code}


@router.get("/parent/home")
def parent_home(ctx=Depends(auth), s=Depends(db)):
    p = persona(s, ctx)
    st = p.get("student")
    if not st:
        raise HTTPException(404, "No ward linked to this login")
    _, dept = _student_program_and_department(s, st)
    invoices, balance = _student_fee_summary(s, st.id)
    structures = {row.id: row for row in s.query(D.FeeStructure).all()}
    semesters = {row.id: row.name for row in s.query(D.Semester).all()}
    payments = s.query(D.Payment).filter(D.Payment.student_id == st.id).all()
    invoice_data = []
    for row in invoices:
        amounts = _invoice_display_amounts(row)
        invoice_data.append({"id": row.id, "term": row.term, "semester": semesters.get(structures[row.fee_structure_id].semester_id, row.term) if row.fee_structure_id in structures else row.term, **amounts, "status": row.status})
    return {
        "ward": {
            "name": st.name,
            "roll_no": st.roll_no,
            "cgpa": st.cgpa,
            "semester": st.semester,
            "department": dept.name if dept else "",
            "attendance_pct": _student_attendance_pct(s, st),
        },
        "fee": {"balance": round(sum(item["balance"] for item in invoice_data), 2), "invoices": invoice_data},
    }


@router.get("/parent/fees/invoices/{invoice_id}/receipt.pdf")
def parent_fee_receipt(invoice_id: str, ctx=Depends(auth), s=Depends(db)):
    student = persona(s, ctx).get("student")
    if not student:
        raise HTTPException(404, "No ward linked to this login")
    return _receipt_response(student, invoice_id, s)


@router.post("/parent/fees/razorpay/order")
def parent_create_razorpay_order(body: RazorpayOrderIn, ctx=Depends(auth), s=Depends(db)):
    student = persona(s, ctx).get("student")
    invoice = s.get(D.FeeInvoice, body.invoice_id)
    if not student or not invoice or invoice.student_id != student.id:
        raise HTTPException(404, "Ward fee invoice not found")
    base_balance = round(max((invoice.amount or 0) - (invoice.paid or 0), 0), 2)
    if base_balance <= 0: raise HTTPException(409, "This invoice is already paid")
    base_amount = round(float(body.amount), 2) if body.amount is not None else base_balance
    if base_amount <= 0 or base_amount > base_balance: raise HTTPException(422, f"Payment amount must be between ₹0.01 and ₹{base_balance:,.2f}")
    gst_amount, charge_amount = _gst(base_amount), round(base_amount + _gst(base_amount), 2)
    key, _ = _razorpay_configured(); remote = _razorpay_request("/orders", {"amount": int(charge_amount * 100), "currency": "INR", "receipt": f"ICMS-{invoice.id}", "notes": {"invoice_id": invoice.id, "student_id": student.id, "base_amount": str(base_amount), "gst_rate": "18", "gst_amount": str(gst_amount)}})
    s.add(D.RazorpayOrder(id=uid(), tenant_id=TENANT, invoice_id=invoice.id, student_id=student.id, razorpay_order_id=remote["id"], amount=charge_amount)); s.commit()
    return {"key_id": key, "order_id": remote["id"], "amount": int(charge_amount * 100), "currency": "INR", "student": {"name": student.name, "email": student.email}, "description": f"{invoice.term} (includes 18% GST)", "base_amount": base_amount, "gst_amount": gst_amount, "total_amount": charge_amount}


@router.post("/parent/fees/razorpay/verify")
def parent_verify_razorpay_payment(body: RazorpayVerifyIn, ctx=Depends(auth), s=Depends(db)):
    student = persona(s, ctx).get("student")
    order = s.query(D.RazorpayOrder).filter(D.RazorpayOrder.razorpay_order_id == body.razorpay_order_id, D.RazorpayOrder.invoice_id == body.invoice_id).first()
    if not student or not order or order.student_id != student.id: raise HTTPException(404, "Payment order not found")
    if order.status == "paid": return {"status": "paid"}
    _, secret = _razorpay_configured(); expected = hmac.new(secret.encode(), f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, body.razorpay_signature): raise HTTPException(400, "Payment signature verification failed")
    invoice = s.get(D.FeeInvoice, order.invoice_id); base_amount = min(round(float(order.amount or 0) / (1 + GST_RATE), 2), max(invoice.amount-invoice.paid, 0)); order.status = "paid"; order.razorpay_payment_id = body.razorpay_payment_id; order.paid_at = datetime.utcnow(); payment = D.Payment(id=uid(), tenant_id=TENANT, invoice_id=invoice.id, student_id=student.id, amount=base_amount, method="razorpay", reference=body.razorpay_payment_id, status="success"); s.add(payment); s.flush(); _settle_payment(s, payment, ctx["sub"]); s.commit()
    return {"status": invoice.status, **_invoice_display_amounts(invoice, order.amount)}
