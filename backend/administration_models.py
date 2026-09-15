"""Dean Administration bounded-domain persistence models.

These records are intentionally separate from the generic approval workflow:
they are the source of truth for school administrative work.
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, ForeignKey, UniqueConstraint, Index
from models import Base


class AdministrativePlan(Base):
    __tablename__ = "administrative_plans"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    school_id = Column(String, index=True, default="")
    department_id = Column(String, index=True, default="")
    title = Column(String, nullable=False)
    period_start = Column(String, default="")
    period_end = Column(String, default="")
    objectives = Column(Text, default="")
    state = Column(String, nullable=False, default="DRAFT", index=True)
    version = Column(Integer, nullable=False, default=1)
    created_by = Column(String, nullable=False, index=True)
    updated_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdministrativePlanActivity(Base):
    __tablename__ = "administrative_plan_activities"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    plan_id = Column(String, ForeignKey("administrative_plans.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    milestone = Column(String, default="")
    responsible_office_n = Column(Integer, nullable=True)
    due_at = Column(DateTime, nullable=True)
    status = Column(String, default="OPEN", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdministrativePlanTransition(Base):
    __tablename__ = "administrative_plan_transitions"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    plan_id = Column(String, ForeignKey("administrative_plans.id"), nullable=False, index=True)
    from_state = Column(String, default="")
    to_state = Column(String, nullable=False)
    actor_id = Column(String, nullable=False)
    reason = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdministrativeRequirement(Base):
    __tablename__ = "administrative_requirements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "reference_code", name="uq_admin_requirement_reference"),
        Index("ix_admin_requirement_queue", "tenant_id", "state", "responsible_office_n", "due_at"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    reference_code = Column(String, nullable=False)
    plan_id = Column(String, ForeignKey("administrative_plans.id"), nullable=True, index=True)
    school_id = Column(String, index=True, default="")
    department_id = Column(String, index=True, default="")
    source_office_n = Column(Integer, nullable=False)
    requester_id = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    subcategory = Column(String, default="")
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    justification = Column(Text, default="")
    quantity = Column(Integer, default=1)
    estimated_cost = Column(Float, default=0)
    priority = Column(String, default="MEDIUM", index=True)
    urgency = Column(String, default="NORMAL")
    required_by = Column(DateTime, nullable=True)
    due_at = Column(DateTime, nullable=True, index=True)
    budget_impact = Column(Float, default=0)
    resource_impact = Column(Text, default="")
    state = Column(String, nullable=False, default="DRAFT", index=True)
    responsible_office_n = Column(Integer, nullable=True, index=True)
    assigned_user_id = Column(String, nullable=True, index=True)
    consolidated_into_id = Column(String, nullable=True, index=True)
    version = Column(Integer, nullable=False, default=1)
    created_by = Column(String, nullable=False, index=True)
    updated_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdministrativeAssignment(Base):
    __tablename__ = "administrative_assignments"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    requirement_id = Column(String, ForeignKey("administrative_requirements.id"), nullable=False, index=True)
    office_n = Column(Integer, nullable=False, index=True)
    user_id = Column(String, nullable=True, index=True)
    status = Column(String, default="ASSIGNED", index=True)
    due_at = Column(DateTime, nullable=True)
    assigned_by = Column(String, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    previous_office_n = Column(Integer, nullable=True)
    previous_user_id = Column(String, nullable=True)
    reason = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdministrativeTransition(Base):
    __tablename__ = "administrative_transitions"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    requirement_id = Column(String, ForeignKey("administrative_requirements.id"), nullable=False, index=True)
    from_state = Column(String, default="")
    to_state = Column(String, nullable=False, index=True)
    actor_id = Column(String, nullable=False)
    actor_office_n = Column(Integer, nullable=False)
    reason = Column(Text, default="")
    version = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdministrativeComment(Base):
    __tablename__ = "administrative_comments"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    requirement_id = Column(String, ForeignKey("administrative_requirements.id"), nullable=False, index=True)
    body = Column(Text, nullable=False)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdministrativeEvidence(Base):
    __tablename__ = "administrative_evidence"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    requirement_id = Column(String, ForeignKey("administrative_requirements.id"), nullable=False, index=True)
    evidence_type = Column(String, nullable=False)
    description = Column(Text, default="")
    file_name = Column(String, default="")
    checksum = Column(String, default="")
    uploaded_by = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    content_type = Column(String, default="application/octet-stream")
    size_bytes = Column(Integer, default=0)
    storage_key = Column(String, default="", index=True)
    verification_status = Column(String, nullable=False, default="UPLOADED", index=True)
    verified_by = Column(String, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, default="")
    deleted_at = Column(DateTime, nullable=True, index=True)
    deleted_by = Column(String, nullable=True)


class AdministrativeEvidencePolicy(Base):
    """Scoped, declarative closure evidence policy; requirements are JSON types."""
    __tablename__ = "administrative_evidence_policies"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    school_id = Column(String, default="", index=True)
    department_id = Column(String, default="", index=True)
    category = Column(String, nullable=False, index=True)
    priority = Column(String, default="", index=True)
    responsible_office_n = Column(Integer, nullable=True, index=True)
    execution_type = Column(String, default="", index=True)
    required_types = Column(Text, nullable=False, default="[]")
    policy_priority = Column(Integer, nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdministrativeClosure(Base):
    __tablename__ = "administrative_closures"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    requirement_id = Column(String, ForeignKey("administrative_requirements.id"), nullable=False, unique=True, index=True)
    closure_reason = Column(Text, nullable=False)
    evidence_verified = Column(Boolean, default=False, nullable=False)
    budget_verified = Column(Boolean, default=False, nullable=False)
    execution_verified = Column(Boolean, default=False, nullable=False)
    closed_by = Column(String, nullable=False)
    closed_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdministrativeApprovalPolicy(Base):
    __tablename__ = "administrative_approval_policies"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    school_id = Column(String, default="", index=True)
    category = Column(String, nullable=False, index=True)
    min_amount = Column(Float, default=0)
    max_amount = Column(Float, nullable=True)
    approver_office_n = Column(Integer, nullable=False)
    escalate_to_office_n = Column(Integer, nullable=True)
    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    department_id = Column(String, default="", index=True)
    priority = Column(String, default="", index=True)
    policy_priority = Column(Integer, default=0, nullable=False)


class AdministrativeRoutingRule(Base):
    __tablename__ = "administrative_routing_rules"
    __table_args__ = (UniqueConstraint("tenant_id", "school_id", "category", name="uq_admin_routing_rule"),)
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    school_id = Column(String, nullable=False, default="", index=True)
    category = Column(String, nullable=False, index=True)
    responsible_office_n = Column(Integer, nullable=False)
    sla_hours = Column(Integer, nullable=False, default=72)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    department_id = Column(String, default="", index=True)
    priority = Column(String, default="", index=True)
    default_assignee_id = Column(String, nullable=True)


class AdministrativeApproval(Base):
    __tablename__ = "administrative_approvals"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    requirement_id = Column(String, ForeignKey("administrative_requirements.id"), nullable=False, index=True)
    policy_id = Column(String, ForeignKey("administrative_approval_policies.id"), nullable=True)
    approver_office_n = Column(Integer, nullable=False, index=True)
    decision = Column(String, nullable=False, index=True)
    actor_id = Column(String, nullable=False)
    delegated_from_user_id = Column(String, nullable=True, index=True)
    delegation_id = Column(String, nullable=True, index=True)
    reason = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdministrativeSla(Base):
    __tablename__ = "administrative_slas"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    requirement_id = Column(String, ForeignKey("administrative_requirements.id"), nullable=False, unique=True, index=True)
    routing_rule_id = Column(String, ForeignKey("administrative_routing_rules.id"), nullable=True)
    duration_hours = Column(Integer, nullable=False)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    due_at = Column(DateTime, nullable=False, index=True)
    paused_at = Column(DateTime, nullable=True)
    resumed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    breached_at = Column(DateTime, nullable=True)
    approaching_notified_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="ACTIVE", index=True)
    policy_id = Column(String, ForeignKey("administrative_sla_policies.id"), nullable=True)
    # Snapshots make an SLA reproducible even after its policy is edited or retired.
    original_due_at = Column(DateTime, nullable=True)
    approaching_percent = Column(Integer, nullable=False, default=80)
    pause_allowed = Column(Boolean, nullable=False, default=False)
    paused_seconds = Column(Integer, nullable=False, default=0)
    pause_count = Column(Integer, nullable=False, default=0)


class AdministrativeSlaPolicy(Base):
    __tablename__ = "administrative_sla_policies"
    id=Column(String,primary_key=True); tenant_id=Column(String,nullable=False,index=True)
    school_id=Column(String,default="",index=True); department_id=Column(String,default="",index=True)
    category=Column(String,nullable=False,index=True); priority=Column(String,default="",index=True)
    responsible_office_n=Column(Integer,nullable=True,index=True); duration_hours=Column(Integer,nullable=False)
    approaching_percent=Column(Integer,nullable=False,default=80); policy_priority=Column(Integer,nullable=False,default=0)
    active=Column(Boolean,nullable=False,default=True); created_at=Column(DateTime,default=datetime.utcnow)
    pause_allowed=Column(Boolean,nullable=False,default=False)


class AdministrativeOutboxEvent(Base):
    __tablename__ = "administrative_outbox_events"
    __table_args__=(UniqueConstraint("tenant_id","idempotency_key",name="uq_admin_outbox_idempotency"),)
    id=Column(String,primary_key=True); tenant_id=Column(String,nullable=False,index=True)
    event_type=Column(String,nullable=False,index=True); aggregate_type=Column(String,nullable=False); aggregate_id=Column(String,nullable=False,index=True)
    payload=Column(Text,default="{}"); idempotency_key=Column(String,nullable=False)
    status=Column(String,nullable=False,default="PENDING",index=True); attempt_count=Column(Integer,default=0); last_error=Column(Text,default="")
    processed_at=Column(DateTime,nullable=True); available_at=Column(DateTime,default=datetime.utcnow,index=True); created_at=Column(DateTime,default=datetime.utcnow)
    # A lease makes multiple worker instances safe: only the worker holding a
    # non-expired claim may attempt delivery.
    locked_by=Column(String,nullable=True,index=True)
    locked_at=Column(DateTime,nullable=True)
    lease_expires_at=Column(DateTime,nullable=True,index=True)


class AdministrativeExecution(Base):
    """A small integration boundary owned by the specialist office, not the Dean."""
    __tablename__ = "administrative_executions"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    requirement_id = Column(String, ForeignKey("administrative_requirements.id"), nullable=False, unique=True, index=True)
    owning_office_n = Column(Integer, nullable=False, index=True)
    external_reference = Column(String, default="")
    status = Column(String, nullable=False, default="OPEN", index=True)
    completion_notes = Column(Text, default="")
    updated_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdministrativeFinanceReservation(Base):
    __tablename__ = "administrative_finance_reservations"
    __table_args__ = (UniqueConstraint("tenant_id", "requirement_id", name="uq_admin_finance_reservation_requirement"),)
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    requirement_id = Column(String, ForeignKey("administrative_requirements.id"), nullable=False, index=True)
    budget_line_id = Column(String, ForeignKey("budget_lines.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="RESERVED", index=True)
    reserved_by = Column(String, nullable=False)
    reserved_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdministrativeFinanceCommitment(Base):
    __tablename__ = "administrative_finance_commitments"
    __table_args__ = (UniqueConstraint("tenant_id", "reservation_id", name="uq_admin_finance_commitment_reservation"),)
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    requirement_id = Column(String, ForeignKey("administrative_requirements.id"), nullable=False, index=True)
    reservation_id = Column(String, ForeignKey("administrative_finance_reservations.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="COMMITTED", index=True)
    committed_by = Column(String, nullable=False)
    committed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
