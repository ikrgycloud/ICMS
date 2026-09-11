"""Front Office operational entities. Kept separate from global ICMS domains."""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey
from models import Base

class FrontDeskVisitor(Base):
    __tablename__ = "frontdesk_visitors"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    name = Column(String, nullable=False)
    contact = Column(String, default="")
    email = Column(String, default="")
    category = Column(String, default="General Visitor")
    purpose = Column(Text, default="")
    host_name = Column(String, default="")
    host_user_id = Column(String, default="")
    department = Column(String, default="")
    mode = Column(String, default="walk_in")
    reference = Column(String, unique=True, index=True)
    status = Column(String, default="ARRIVED")
    security_status = Column(String, default="PENDING")
    pass_number = Column(String, default="")
    expected_at = Column(DateTime, nullable=True)
    arrived_at = Column(DateTime, default=datetime.utcnow)
    checked_in_at = Column(DateTime, nullable=True)
    checked_out_at = Column(DateTime, nullable=True)
    created_by = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class FrontDeskAppointment(Base):
    __tablename__ = "frontdesk_appointments"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    reference = Column(String, unique=True, index=True)
    visitor_id = Column(String, ForeignKey("frontdesk_visitors.id"), nullable=True)
    visitor_name = Column(String, nullable=False)
    contact = Column(String, default="")
    host_name = Column(String, default="")
    host_user_id = Column(String, default="")
    department = Column(String, default="")
    purpose = Column(Text, default="")
    location = Column(String, default="")
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=True)
    status = Column(String, default="REQUESTED")
    notes = Column(Text, default="")
    created_by = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class FrontDeskTicket(Base):
    __tablename__ = "frontdesk_tickets"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    number = Column(String, unique=True, index=True)
    requester = Column(String, nullable=False)
    contact = Column(String, default="")
    source = Column(String, default="walk_in")
    category = Column(String, default="General")
    subject = Column(String, default="")
    description = Column(Text, default="")
    assigned_office = Column(String, default="")
    assigned_person = Column(String, default="")
    priority = Column(String, default="normal")
    status = Column(String, default="NEW")
    resolution = Column(Text, default="")
    created_by = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

class FrontDeskCall(Base):
    __tablename__ = "frontdesk_calls"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    caller = Column(String, default="")
    contact = Column(String, default="")
    purpose = Column(Text, default="")
    recipient = Column(String, default="")
    department = Column(String, default="")
    operator = Column(String, default="")
    outcome = Column(String, default="MESSAGE_TAKEN")
    message = Column(Text, default="")
    notes = Column(Text, default="")
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    status = Column(String, default="OPEN")
    created_at = Column(DateTime, default=datetime.utcnow)

class FrontDeskTicketUpdate(Base):
    __tablename__ = "frontdesk_ticket_updates"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    ticket_id = Column(String, ForeignKey("frontdesk_tickets.id"))
    actor = Column(String, default="")
    note = Column(Text, default="")
    status = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
