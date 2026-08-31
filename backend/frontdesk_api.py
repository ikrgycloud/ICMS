from datetime import datetime, timedelta
import base64
import io
import os
import qrcode
import smtplib
from html import escape
from email.message import EmailMessage
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc
from core import db, auth, uid, write_audit
from database import TENANT
from frontdesk_models import FrontDeskVisitor, FrontDeskAppointment, FrontDeskTicket, FrontDeskCall, FrontDeskTicketUpdate

router = APIRouter(prefix="/api/frontdesk", tags=["Front Office"])
VISITOR_TRANSITIONS = {"PRE_REGISTERED":{"EXPECTED","CANCELLED"},"EXPECTED":{"ARRIVED","NO_SHOW","CANCELLED"},"ARRIVED":{"ID_VERIFIED","SECURITY_REVIEW","DECLINED"},"ID_VERIFIED":{"HOST_PENDING"},"HOST_PENDING":{"HOST_CONFIRMED","DECLINED","CANCELLED"},"HOST_CONFIRMED":{"PASS_ISSUED","DECLINED"},"PASS_ISSUED":{"CHECKED_IN","EXPIRED","CANCELLED"},"CHECKED_IN":{"CHECKED_OUT"},"SECURITY_REVIEW":{"PASS_ISSUED","CANCELLED"}}
VISITOR_STATES=set(VISITOR_TRANSITIONS)|{"CHECKED_OUT","DECLINED","NO_SHOW","EXPIRED","CANCELLED"}
APPOINTMENT_STATES={"REQUESTED","PENDING_HOST","CONSIDERED","RESCHEDULE_PROPOSED","RESCHEDULED","DECLINED","CANCELLED","ARRIVED","COMPLETED","NO_SHOW"}
TICKET_STATES={"NEW","TRIAGED","ROUTED","IN_PROGRESS","WAITING_FOR_CUSTOMER","WAITING_FOR_OFFICE","RESOLVED","CLOSED","REOPENED","ESCALATED"}
def only_frontdesk(ctx=Depends(auth)):
    if ctx["office_n"] != 35: raise HTTPException(403,"Front Office access required")
    return ctx
def out(row): return {c.name:getattr(row,c.name) for c in row.__table__.columns}
def log(s,ctx,action,entity,old="",new=""): write_audit(s,ctx["sub"],ctx.get("role","Front Office"),35,action,entity,old,new,"Front Office operation")

def seed_frontdesk(s):
    """Create database-backed Front Desk demo records only for empty tables."""
    now=datetime.utcnow()
    if not s.query(FrontDeskVisitor).first():
        s.add_all([
            FrontDeskVisitor(id="fdv_demo_01",tenant_id=TENANT,reference="VIS-DEMO-001",name="Aarav Mehta",email="aarav.mehta@example.com",contact="+91 98765 12001",category="Guest",purpose="Campus visit",host_name="Dr. R. Sharma",department="Academics",mode="pre_registered",status="HOST_PENDING",pass_number="PASS-DEMO-001",arrived_at=now-timedelta(minutes=20),created_by="front_office"),
            FrontDeskVisitor(id="fdv_demo_02",tenant_id=TENANT,reference="VIS-DEMO-002",name="Nisha Kapoor",email="nisha.kapoor@example.com",contact="+91 98765 12002",category="Parent",purpose="Student counselling",host_name="Student Affairs",department="Student Affairs",mode="walk_in",status="ARRIVED",pass_number="PASS-DEMO-002",arrived_at=now-timedelta(minutes=35),created_by="front_office"),
            FrontDeskVisitor(id="fdv_demo_03",tenant_id=TENANT,reference="VIS-DEMO-003",name="Kabir Malhotra",email="kabir.malhotra@example.com",contact="+91 98765 12003",category="Vendor",purpose="Facilities review",host_name="Facilities & Maintenance",department="Operations",mode="walk_in",status="CHECKED_OUT",pass_number="PASS-DEMO-003",arrived_at=now-timedelta(hours=2),checked_in_at=now-timedelta(hours=2),checked_out_at=now-timedelta(minutes=30),created_by="front_office"),
        ])
    if not s.query(FrontDeskAppointment).first():
        s.add_all([
            FrontDeskAppointment(id="fda_demo_01",tenant_id=TENANT,reference="APT-DEMO-001",visitor_name="Priya Iyer",contact="priya.iyer@example.com",host_name="Dr. R. Sharma",department="Academics",purpose="Programme enquiry",location="Admin Block",starts_at=now+timedelta(hours=1),ends_at=now+timedelta(hours=2),status="PENDING_HOST",created_by="front_office"),
            FrontDeskAppointment(id="fda_demo_02",tenant_id=TENANT,reference="APT-DEMO-002",visitor_name="Rohan Das",contact="rohan.das@example.com",host_name="Dean Student Affairs",department="Student Affairs",purpose="Student support meeting",location="Student Centre",starts_at=now+timedelta(hours=3),ends_at=now+timedelta(hours=4),status="REQUESTED",created_by="front_office"),
        ])
    if not s.query(FrontDeskTicket).first():
        s.add_all([
            FrontDeskTicket(id="fdt_demo_01",tenant_id=TENANT,number="TKT-DEMO-001",requester="Ananya Rao",contact="ananya.rao@example.com",category="Facilities",subject="Air conditioning in reception",description="Reception area cooling needs attention.",assigned_office="Facilities & Maintenance",priority="normal",status="ROUTED",created_by="front_office"),
            FrontDeskTicket(id="fdt_demo_02",tenant_id=TENANT,number="TKT-DEMO-002",requester="Vikram Singh",contact="+91 98765 12010",category="IT support",subject="Visitor Wi-Fi access",description="Guest network access required.",assigned_office="IT Management",priority="high",status="IN_PROGRESS",created_by="front_office"),
            FrontDeskTicket(id="fdt_demo_03",tenant_id=TENANT,number="TKT-DEMO-003",requester="Meera Patel",contact="meera.patel@example.com",category="Student Affairs",subject="Counselling appointment",description="Request for student support appointment.",assigned_office="Dean Student Affairs",priority="normal",status="NEW",created_by="front_office"),
        ])
    if not s.query(FrontDeskCall).first():
        s.add_all([
            FrontDeskCall(id="fdc_demo_01",tenant_id=TENANT,caller="Ananya Rao",contact="ananya.rao@example.com",recipient="Admissions Office",outcome="MESSAGE_TAKEN",message="Asked for admission brochure.",operator="Front Office",status="CLOSED",started_at=now-timedelta(minutes=50),ended_at=now-timedelta(minutes=47)),
            FrontDeskCall(id="fdc_demo_02",tenant_id=TENANT,caller="Vikram Singh",contact="+91 98765 43210",recipient="Registrar Office",outcome="TRANSFERRED",message="Transcript status enquiry.",operator="Front Office",status="CLOSED",started_at=now-timedelta(hours=1),ended_at=now-timedelta(minutes=57)),
            FrontDeskCall(id="fdc_demo_03",tenant_id=TENANT,caller="Meera Patel",contact="meera.patel@example.com",recipient="Student Services",outcome="CALLBACK_REQUESTED",message="Requested a student-services callback.",operator="Front Office",status="OPEN",started_at=now-timedelta(hours=2)),
        ])
    s.commit()

def qr_payload(row): return "ICMS-VISITOR:" + row.pass_number
def qr_image(row):
    code=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=10,border=4)
    code.add_data(qr_payload(row)); code.make(fit=True)
    return code.make_image(fill_color="#172b4d",back_color="white")
def email_qr(row):
    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    if not host or not row.email: return False
    buf = io.BytesIO(); qr_image(row).save(buf, format="PNG"); image_data=buf.getvalue()
    msg = EmailMessage(); msg["From"] = os.getenv("SMTP_FROM", "frontdesk@example.edu"); msg["To"] = row.email; msg["Subject"] = "Your visitor pass - " + row.reference
    msg.set_content("Hello " + row.name + ",\n\nYour visitor pass is ready. Present the QR code at the Front Desk. Reference: " + row.reference + ".")
    details="".join(f"<tr><td style='padding:8px 0;color:#64748b'>{label}</td><td style='padding:8px 0;text-align:right;color:#172b4d;font-weight:600'>{escape(str(value))}</td></tr>" for label,value in (("Visitor",row.name),("Reference",row.reference),("Visit type",row.mode.replace("_"," ").title()),("Purpose",row.purpose or "General visit")))
    msg.add_alternative(f"""<html><body style='margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#172b4d'><div style='max-width:560px;margin:28px auto;background:#ffffff;border-radius:18px;overflow:hidden;border:1px solid #dbe4ee'><div style='padding:28px 32px;background:#172b4d;color:#ffffff'><div style='font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:#bfdbfe'>Front Desk</div><h1 style='margin:8px 0 0;font-size:26px'>Your visitor pass</h1></div><div style='padding:30px 32px'><p style='margin-top:0'>Hello {escape(row.name)},</p><p>Your registration is complete. Show this QR code at the Front Desk for scan-based entry and exit.</p><div style='text-align:center;margin:26px 0;padding:20px;background:#f8fafc;border:1px solid #dbe4ee;border-radius:14px'><img src='cid:visitor-qr' width='220' height='220' alt='Visitor QR code' style='display:block;margin:auto'/><div style='margin-top:12px;font-family:monospace;font-size:13px;color:#334155'>{escape(row.reference)}</div></div><table role='presentation' width='100%' cellspacing='0' cellpadding='0'>{details}</table><p style='margin:24px 0 0;color:#64748b;font-size:13px;line-height:1.5'>Keep this pass private. The first scan for a pre-registered visit checks you in; the next scan checks you out.</p></div></div></body></html>""", subtype="html")
    msg.get_payload()[-1].add_related(image_data, maintype="image", subtype="png", cid="visitor-qr")
    msg.add_attachment(image_data, maintype="image", subtype="png", filename=row.reference + "-visitor-pass.png")
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as smtp:
        if os.getenv("SMTP_TLS", "true").lower() == "true": smtp.starttls()
        if os.getenv("SMTP_USERNAME"): smtp.login(os.getenv("SMTP_USERNAME"), os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(msg)
    return True
class VisitorIn(BaseModel):
    name:str; contact:str=""; email:str=""; category:str="General Visitor"; purpose:str=""; host_name:str=""; host_user_id:str=""; department:str=""; mode:str="walk_in"; expected_at:datetime|None=None
class VisitorUpdateIn(BaseModel):
    name:str; contact:str=""; email:str=""; category:str="General Visitor"; purpose:str=""; host_name:str=""; department:str=""; expected_at:datetime|None=None
class StatusIn(BaseModel): status:str
class AppointmentIn(BaseModel):
    visitor_name:str; contact:str=""; host_name:str=""; host_user_id:str=""; department:str=""; purpose:str=""; location:str=""; starts_at:datetime; ends_at:datetime|None=None; notes:str=""
class TicketIn(BaseModel):
    requester:str; contact:str=""; source:str="walk_in"; category:str="General"; subject:str=""; description:str=""; assigned_office:str=""; assigned_person:str=""; priority:str="normal"
class TicketUpdateIn(BaseModel): status:str|None=None; note:str=""; resolution:str=""
class CallIn(BaseModel): caller:str=""; contact:str=""; purpose:str=""; recipient:str=""; department:str=""; outcome:str="MESSAGE_TAKEN"; message:str=""; notes:str=""
@router.get("/dashboard")
def dashboard(ctx=Depends(only_frontdesk),s=Depends(db)):
    vs=s.query(FrontDeskVisitor).all(); aps=s.query(FrontDeskAppointment).all(); ts=s.query(FrontDeskTicket).all(); today=datetime.utcnow().date()
    return {"kpis":{"expected_visitors":sum(v.status in ("PRE_REGISTERED","EXPECTED") for v in vs),"checked_in":sum(v.status=="CHECKED_IN" for v in vs),"appointments_today":sum(a.starts_at.date()==today for a in aps),"enquiries":sum(t.status not in ("CLOSED","RESOLVED") for t in ts),"overdue_tickets":0},"visitors":[out(v) for v in vs if v.status=="HOST_PENDING"],"appointments":[out(a) for a in aps if a.starts_at.date()==today],"tickets":[out(t) for t in ts if t.status not in ("CLOSED","RESOLVED")],"charts":{"visitor_status":[{"label":label.replace("_"," ").title(),"value":sum(v.status==label for v in vs)} for label in ("HOST_PENDING","ARRIVED","CHECKED_IN","CHECKED_OUT")],"ticket_categories":[{"label":label,"value":sum(t.category==label for t in ts)} for label in ("Facilities","IT support","Student Affairs")]}}
@router.get("/visitors")
def visitors(status:str="",q:str="",ctx=Depends(only_frontdesk),s=Depends(db)):
    rows=s.query(FrontDeskVisitor).order_by(desc(FrontDeskVisitor.created_at)).all(); rows=[r for r in rows if (not status or r.status==status) and (not q or q.lower() in (r.name+r.reference+r.contact).lower())]; return {"visitors":[out(r) for r in rows]}
@router.post("/visitors")
def create_visitor(body:VisitorIn,ctx=Depends(only_frontdesk),s=Depends(db)):
    data=body.model_dump()
    if not data["name"].strip() or not data["email"].strip(): raise HTTPException(422,"Name and email are required")
    data["contact"]=""; data["host_name"]=""; data["status"]="PRE_REGISTERED" if data["mode"]=="pre_registered" else "ARRIVED"; data["pass_number"]="PASS-"+uid().upper()
    row=FrontDeskVisitor(id=uid(),tenant_id=TENANT,reference="VIS-"+uid().upper(),created_by=ctx["sub"],**data); s.add(row); s.commit()
    email_sent=False
    email_error=""
    try: email_sent=email_qr(row)
    except Exception as exc: email_error=str(exc)
    log(s,ctx,"frontdesk.visitor.create","visitor:"+row.id,"",row.status); result=out(row); result["email_sent"]=email_sent; result["email_error"]=email_error if not email_sent else ""; return result
@router.put("/visitors/{id}")
def update_visitor(id:str,body:VisitorUpdateIn,ctx=Depends(only_frontdesk),s=Depends(db)):
    row=s.get(FrontDeskVisitor,id)
    if not row: raise HTTPException(404,"Visitor not found")
    data=body.model_dump()
    if not data["name"].strip() or not data["email"].strip(): raise HTTPException(422,"Name and email are required")
    for field, value in data.items(): setattr(row,field,value)
    row.updated_at=datetime.utcnow(); s.commit()
    log(s,ctx,"frontdesk.visitor.update","visitor:"+id,"","Visitor details updated")
    return out(row)
@router.post("/visitors/{id}/status")
def visitor_status(id:str,body:StatusIn,ctx=Depends(only_frontdesk),s=Depends(db)):
    row=s.get(FrontDeskVisitor,id)
    if not row: raise HTTPException(404,"Visitor not found")
    if body.status not in VISITOR_STATES or body.status not in VISITOR_TRANSITIONS.get(row.status,set()): raise HTTPException(409,f"Invalid transition {row.status} -> {body.status}")
    old=row.status; row.status=body.status; now=datetime.utcnow(); row.updated_at=now
    if body.status=="CHECKED_IN": row.checked_in_at=now
    if body.status=="CHECKED_OUT": row.checked_out_at=now
    if body.status=="PASS_ISSUED": row.pass_number="PASS-"+uid().upper()
    s.commit(); log(s,ctx,"frontdesk.visitor.status","visitor:"+id,old,row.status); return out(row)

@router.delete("/visitors/{id}")
def delete_visitor(id:str,ctx=Depends(only_frontdesk),s=Depends(db)):
    row=s.get(FrontDeskVisitor,id)
    if not row: raise HTTPException(404,"Visitor not found")
    if row.status in ("CHECKED_IN","HOST_CONFIRMED","PASS_ISSUED"): raise HTTPException(409,"Close or cancel active visits before removing")
    old=row.status; s.delete(row); s.commit(); log(s,ctx,"frontdesk.visitor.delete","visitor:"+id,old,"DELETED"); return {"ok":True}

@router.get("/visitors/history")
def visitor_history(q:str="",ctx=Depends(only_frontdesk),s=Depends(db)):
    rows=s.query(FrontDeskVisitor).order_by(desc(FrontDeskVisitor.created_at)).all()
    if q: rows=[r for r in rows if q.lower() in (r.name+r.reference+r.host_name+r.pass_number).lower()]
    return {"visitors":[out(r) for r in rows]}

@router.post("/visitors/{id}/host-decision")
def host_decision(id:str,body:StatusIn,ctx=Depends(auth),s=Depends(db)):
    row=s.get(FrontDeskVisitor,id)
    if not row or row.host_user_id != ctx["sub"]: raise HTTPException(403,"Only the assigned host can decide this visit")
    if body.status not in ("HOST_CONFIRMED","DECLINED","CANCELLED"): raise HTTPException(400,"Invalid host decision")
    if body.status not in VISITOR_TRANSITIONS.get(row.status,set()): raise HTTPException(409,"Invalid visitor transition")
    old=row.status; row.status=body.status; row.updated_at=datetime.utcnow(); s.commit(); log(s,ctx,"frontdesk.visitor.host_decision","visitor:"+id,old,row.status); return out(row)

@router.post("/visitors/{id}/security")
def security_review(id:str,body:StatusIn,ctx=Depends(auth),s=Depends(db)):
    if ctx["office_n"] not in (34,35): raise HTTPException(403,"Security or Front Office access required")
    if ctx["office_n"] == 35 and body.status != "SECURITY_REVIEW": raise HTTPException(403,"Front Office cannot clear or override security")
    row=s.get(FrontDeskVisitor,id)
    if not row or body.status not in ("SECURITY_REVIEW","PASS_ISSUED","CANCELLED"): raise HTTPException(400,"Invalid security action")
    if body.status not in VISITOR_TRANSITIONS.get(row.status,set()): raise HTTPException(409,"Invalid security transition")
    old=row.status; row.status=body.status; row.security_status="CLEARED" if body.status=="PASS_ISSUED" else ("HELD" if body.status=="SECURITY_REVIEW" else "DENIED"); row.updated_at=datetime.utcnow()
    if body.status=="PASS_ISSUED": row.pass_number="PASS-"+uid().upper()
    s.commit(); log(s,ctx,"frontdesk.visitor.security","visitor:"+id,old,row.status); return out(row)

@router.get("/passes/{pass_number}/validate")
def validate_pass(pass_number:str,ctx=Depends(only_frontdesk),s=Depends(db)):
    row=s.query(FrontDeskVisitor).filter(FrontDeskVisitor.pass_number==pass_number).first()
    return {"valid":bool(row and row.status not in ("CANCELLED","DECLINED","NO_SHOW","EXPIRED","CHECKED_OUT")),"visitor":out(row) if row else None}

@router.post("/passes/{pass_number}/scan")
def scan_pass(pass_number:str,ctx=Depends(only_frontdesk),s=Depends(db)):
    row=s.query(FrontDeskVisitor).filter(FrontDeskVisitor.pass_number==pass_number).first()
    if not row: raise HTTPException(404,"Visitor pass not found")
    if row.status in ("CANCELLED","DECLINED","NO_SHOW","EXPIRED"): raise HTTPException(409,"This visitor pass is not active")
    if row.checked_out_at or row.status=="CHECKED_OUT": raise HTTPException(409,"This visitor has already checked out")
    old=row.status; now=datetime.utcnow()
    if row.mode=="pre_registered" and not row.checked_in_at:
        row.status="CHECKED_IN"; row.arrived_at=now; row.checked_in_at=now; action="CHECK_IN"; message="Visitor checked in and is now in campus"
    else:
        row.status="CHECKED_OUT"; row.checked_out_at=now; action="CHECK_OUT"; message="Visitor checked out and has left campus"
    row.updated_at=now; s.commit()
    log(s,ctx,"frontdesk.visitor.scan","visitor:"+row.id,old,row.status)
    return {"valid":True,"action":action,"message":message,"visitor":out(row)}

@router.get("/reports")
def reports(ctx=Depends(only_frontdesk),s=Depends(db)):
    vs=s.query(FrontDeskVisitor).all(); aps=s.query(FrontDeskAppointment).all(); ts=s.query(FrontDeskTicket).all(); cs=s.query(FrontDeskCall).all()
    return {"visitors_by_category":{c:sum(v.category==c for v in vs) for c in sorted({v.category for v in vs})},"visitors":len(vs),"checked_in":sum(v.status=="CHECKED_IN" for v in vs),"checked_out":sum(v.status=="CHECKED_OUT" for v in vs),"no_shows":sum(v.status=="NO_SHOW" for v in vs),"appointments":len(aps),"tickets":len(ts),"resolved_tickets":sum(t.status in ("RESOLVED","CLOSED") for t in ts),"calls":len(cs)}
@router.get("/visitors/{id}/qr")
def visitor_qr(id:str,ctx=Depends(only_frontdesk),s=Depends(db)):
    row=s.get(FrontDeskVisitor,id)
    if not row: raise HTTPException(404,"Visitor not found")
    image=qr_image(row)
    buf=io.BytesIO(); image.save(buf,format="PNG")
    return {"reference":row.reference,"pass_number":row.pass_number,"mime_type":"image/png","data_base64":base64.b64encode(buf.getvalue()).decode()}
@router.get("/appointments")
def appointments(status:str="",ctx=Depends(only_frontdesk),s=Depends(db)):
    rows=s.query(FrontDeskAppointment).order_by(desc(FrontDeskAppointment.starts_at)).all(); return {"appointments":[out(r) for r in rows if not status or r.status==status]}
@router.post("/appointments")
def create_appointment(body:AppointmentIn,ctx=Depends(only_frontdesk),s=Depends(db)):
    row=FrontDeskAppointment(id=uid(),tenant_id=TENANT,reference="APT-"+uid().upper(),status="PENDING_HOST",created_by=ctx["sub"],**body.model_dump()); s.add(row); s.commit(); log(s,ctx,"frontdesk.appointment.create","appointment:"+row.id,"","PENDING_HOST"); return out(row)
@router.post("/appointments/{id}/status")
def appointment_status(id:str,body:StatusIn,ctx=Depends(only_frontdesk),s=Depends(db)):
    row=s.get(FrontDeskAppointment,id)
    if not row or body.status not in APPOINTMENT_STATES: raise HTTPException(404 if not row else 400,"Appointment not found or invalid status")
    old=row.status; row.status=body.status; row.updated_at=datetime.utcnow(); s.commit(); log(s,ctx,"frontdesk.appointment.status","appointment:"+id,old,row.status); return out(row)
@router.get("/tickets")
def tickets(status:str="",ctx=Depends(only_frontdesk),s=Depends(db)):
    rows=s.query(FrontDeskTicket).order_by(desc(FrontDeskTicket.created_at)).all(); return {"tickets":[out(r) for r in rows if not status or r.status==status]}
@router.post("/tickets")
def create_ticket(body:TicketIn,ctx=Depends(only_frontdesk),s=Depends(db)):
    data=body.model_dump()
    routing={"Facilities":"Facilities & Maintenance","IT support":"IT Management","Student Affairs":"Dean Student Affairs"}
    data["assigned_office"]=routing.get(data["category"],"Front Desk")
    row=FrontDeskTicket(id=uid(),tenant_id=TENANT,number="TKT-"+uid().upper(),created_by=ctx["sub"],**data); s.add(row); s.commit(); log(s,ctx,"frontdesk.ticket.create","ticket:"+row.id,"","NEW"); return out(row)
@router.post("/tickets/{id}/update")
def update_ticket(id:str,body:TicketUpdateIn,ctx=Depends(only_frontdesk),s=Depends(db)):
    row=s.get(FrontDeskTicket,id)
    if not row or (body.status and body.status not in TICKET_STATES): raise HTTPException(404 if not row else 400,"Ticket not found or invalid status")
    old=row.status
    if body.status: row.status=body.status
    if body.resolution: row.resolution=body.resolution
    row.updated_at=datetime.utcnow(); row.closed_at=row.updated_at if row.status=="CLOSED" else row.closed_at
    s.add(FrontDeskTicketUpdate(id=uid(),tenant_id=TENANT,ticket_id=id,actor=ctx["sub"],note=body.note,status=row.status)); s.commit(); log(s,ctx,"frontdesk.ticket.update","ticket:"+id,old,row.status); return out(row)
@router.get("/calls")
def calls(ctx=Depends(only_frontdesk),s=Depends(db)): return {"calls":[out(r) for r in s.query(FrontDeskCall).order_by(desc(FrontDeskCall.created_at)).all()]}
@router.post("/calls")
def create_call(body:CallIn,ctx=Depends(only_frontdesk),s=Depends(db)):
    row=FrontDeskCall(id=uid(),tenant_id=TENANT,operator=ctx.get("role",ctx["sub"]),ended_at=datetime.utcnow(),status="CLOSED",**body.model_dump()); s.add(row); s.commit(); log(s,ctx,"frontdesk.call.create","call:"+row.id,"",row.outcome); return out(row)

@router.get("/directory")
def directory(ctx=Depends(only_frontdesk),s=Depends(db)):
    from models import Person
    return {"people":[{"id":p.id,"name":p.name,"email":p.email,"contact":p.contact} for p in s.query(Person).order_by(Person.name).all()]}

@router.get("/employees")
def employees(ctx=Depends(only_frontdesk),s=Depends(db)):
    from domain_models import StaffMember
    rows=s.query(StaffMember).order_by(StaffMember.name).all()
    return {"employees":[{"id":row.user_id or row.id,"name":row.name,"email":row.email,"contact":row.phone,"designation":row.designation,"campus":row.campus} for row in rows]}







