"""Authoritative specialist execution records linked from Administration.

These are deliberately separate tables: a work order is not an IT ticket, and
neither is a procurement requisition or HR staffing action.
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from models import Base

class FacilityWorkOrder(Base):
    __tablename__ = "facility_work_orders"
    id=Column(String,primary_key=True); tenant_id=Column(String,nullable=False,index=True)
    requirement_id=Column(String,ForeignKey("administrative_requirements.id"),nullable=False,unique=True,index=True)
    technician_id=Column(String,nullable=True,index=True); priority=Column(String,nullable=False)
    status=Column(String,nullable=False,default="OPEN",index=True); due_at=Column(DateTime,nullable=True)
    completion_notes=Column(Text,default=""); created_by=Column(String,nullable=False); updated_by=Column(String,nullable=False)
    created_at=Column(DateTime,default=datetime.utcnow); updated_at=Column(DateTime,default=datetime.utcnow)

class ITServiceRequest(Base):
    __tablename__ = "it_service_requests"
    id=Column(String,primary_key=True); tenant_id=Column(String,nullable=False,index=True)
    requirement_id=Column(String,ForeignKey("administrative_requirements.id"),nullable=False,unique=True,index=True)
    assignee_id=Column(String,nullable=True,index=True); priority=Column(String,nullable=False); service_category=Column(String,default="")
    status=Column(String,nullable=False,default="OPEN",index=True); resolution_notes=Column(Text,default="")
    created_by=Column(String,nullable=False); updated_by=Column(String,nullable=False); created_at=Column(DateTime,default=datetime.utcnow); updated_at=Column(DateTime,default=datetime.utcnow)

class HRStaffingRequest(Base):
    __tablename__ = "hr_staffing_requests"
    id=Column(String,primary_key=True); tenant_id=Column(String,nullable=False,index=True)
    requirement_id=Column(String,ForeignKey("administrative_requirements.id"),nullable=False,unique=True,index=True)
    status=Column(String,nullable=False,default="OPEN",index=True); staffing_reference=Column(String,default="")
    completion_notes=Column(Text,default=""); created_by=Column(String,nullable=False); updated_by=Column(String,nullable=False)
    created_at=Column(DateTime,default=datetime.utcnow); updated_at=Column(DateTime,default=datetime.utcnow)

class ProcurementRequisition(Base):
    __tablename__ = "procurement_requisitions"
    id=Column(String,primary_key=True); tenant_id=Column(String,nullable=False,index=True)
    requirement_id=Column(String,ForeignKey("administrative_requirements.id"),nullable=False,unique=True,index=True)
    status=Column(String,nullable=False,default="DRAFT",index=True); requisition_no=Column(String,nullable=False,index=True)
    purchase_order_no=Column(String,default=""); receipt_reference=Column(String,default=""); asset_handoff_reference=Column(String,default="")
    created_by=Column(String,nullable=False); updated_by=Column(String,nullable=False); created_at=Column(DateTime,default=datetime.utcnow); updated_at=Column(DateTime,default=datetime.utcnow)
