# -*- coding: utf-8 -*-
"""
Data model (Document §12). Identity is separated from designation:
  Person -> User -> UserRole -> Role -> RolePermission -> Permission
with OrgScope, Delegation and ApprovalLimit composing effective authority.
Every table carries tenant_id (Document §6 multi-tenancy).
"""
from datetime import datetime
from sqlalchemy import (Column, Integer, String, Boolean, Float, DateTime, Text,
                        ForeignKey)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class OrgScope(Base):
    """The scope tree (Document §11) — global→university→campus→…→individual."""
    __tablename__ = "org_scopes"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    level = Column(String)           # one of SCOPE_LEVELS
    name = Column(String)
    parent_id = Column(String, ForeignKey("org_scopes.id"), nullable=True)


class Person(Base):
    __tablename__ = "persons"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    name = Column(String)
    email = Column(String)
    contact = Column(String)


class Designation(Base):
    """A person's designation is NOT a permission (Document design rule)."""
    __tablename__ = "designations"
    id = Column(String, primary_key=True)
    person_id = Column(String, ForeignKey("persons.id"))
    title = Column(String)
    employee_id = Column(String)


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    person_id = Column(String, ForeignKey("persons.id"))
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    status = Column(String, default="active")
    mfa_enabled = Column(Boolean, default=True)
    office_n = Column(Integer)          # primary office
    role = Column(String)               # primary role label (head role)
    scope_level = Column(String)        # resolved scope level
    scope_ref = Column(String, default="t_main")


class Role(Base):
    __tablename__ = "roles"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    office_n = Column(Integer)
    name = Column(String)
    category = Column(String)           # level name


class Permission(Base):
    __tablename__ = "permissions"
    id = Column(String, primary_key=True)
    resource = Column(String)
    action = Column(String)             # one of VERBS


class UserRole(Base):
    """Multi-role, time-bound (Document §12)."""
    __tablename__ = "user_roles"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    role_id = Column(String, ForeignKey("roles.id"))
    org_scope_id = Column(String)
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_to = Column(DateTime, nullable=True)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    id = Column(String, primary_key=True)
    role_id = Column(String)
    office_n = Column(Integer)
    action = Column(String)
    authority = Column(String)          # FULL/LIMITED/VIEW/... from RBAC matrix


class Delegation(Base):
    """Time-bound, scoped, revocable, audited (Document §2, §12)."""
    __tablename__ = "delegations"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    from_user = Column(String)
    to_user = Column(String)
    authority = Column(String)          # action or '*'
    scope_ref = Column(String)
    limit = Column(Float, nullable=True)
    start = Column(DateTime)
    end = Column(DateTime)
    status = Column(String, default="active")   # active/revoked/expired
    reason = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


<<<<<<< HEAD
class DelegationPolicy(Base):
    """Catalog of delegation subjects and their authority mapping."""
    __tablename__ = "delegation_policies"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    policy_key = Column(String, unique=True, index=True)
    policy_type = Column(String, index=True)
    subject = Column(String)
    authority = Column(String)
    action = Column(String, default="approve")
    resource_scope = Column(Text, default="")
    default_limit = Column(Float, nullable=True)
    delegated_to_type_default = Column(String, default="Individual")
    icon = Column(String, default="shield")
    sort_order = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class DelegationProfile(Base):
    """Presentation metadata for a concrete delegation grant."""
    __tablename__ = "delegation_profiles"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    delegation_id = Column(String, ForeignKey("delegations.id"), unique=True, index=True)
    policy_key = Column(String, index=True, default="")
    policy_type = Column(String, index=True, default="")
    subject = Column(String, default="")
    reference_code = Column(String, unique=True, index=True)
    delegated_to_type = Column(String, default="Individual")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class DelegationOption(Base):
    """DB-backed option catalog for delegation form controls."""
    __tablename__ = "delegation_options"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    group_key = Column(String, index=True)
    option_key = Column(String, index=True)
    label = Column(String)
    description = Column(Text, default="")
    sort_order = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class DelegationContext(Base):
    """Extended metadata for chairman delegation records."""
    __tablename__ = "delegation_contexts"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    delegation_id = Column(String, ForeignKey("delegations.id"), unique=True, index=True)
    policy_description = Column(Text, default="")
    scope_key = Column(String, default="")
    scope_label = Column(String, default="")
    access_key = Column(String, default="")
    access_label = Column(String, default="")
    review_frequency_key = Column(String, default="")
    review_frequency_label = Column(String, default="")
    notes = Column(Text, default="")
    attachment_name = Column(String, default="")
    attachment_mime_type = Column(String, default="")
    attachment_size = Column(Integer, nullable=True)
    attachment_data = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


=======
>>>>>>> 22ee34d (updated code to branch)
class ApprovalLimit(Base):
    __tablename__ = "approval_limits"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    scope_level = Column(String)
    process = Column(String)
    threshold = Column(Float)


class WorkflowInstance(Base):
    """A running approval workflow (Document §7, §10)."""
    __tablename__ = "workflow_instances"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    process_key = Column(String)
    label = Column(String)
    office_n = Column(Integer)
    title = Column(String)              # human description of the request
    state = Column(String, default="draft")
    amount = Column(Float, nullable=True)
    initiator_id = Column(String)
    initiator_name = Column(String)
    current_stage = Column(Integer, default=0)   # index into approval chain
    scope_level = Column(String)
    escalated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


<<<<<<< HEAD
class WorkflowProfile(Base):
    """Presentation metadata used by approval dashboards and request forms."""
    __tablename__ = "workflow_profiles"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    workflow_id = Column(String, ForeignKey("workflow_instances.id"), unique=True, index=True)
    semester_key = Column(String, index=True, default="")
    semester_label = Column(String, default="")
    category = Column(String, default="")
    reference_code = Column(String, unique=True, index=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


=======
>>>>>>> 22ee34d (updated code to branch)
class Approval(Base):
    """Each decision on a workflow (Document §10)."""
    __tablename__ = "approvals"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    workflow_id = Column(String, ForeignKey("workflow_instances.id"))
    actor_id = Column(String)
    actor_name = Column(String)
    stage = Column(Integer)
    stage_label = Column(String)
    decision = Column(String)           # ALLOW/DENY/RECOMMEND/ESCALATE
    authority = Column(String)
    reason = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    user_id = Column(String, index=True)
    severity = Column(String, default="info")   # info/action/critical
    title = Column(String)
    body = Column(String)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Append-only, hash-chained (Document §2, §12)."""
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, index=True)
    actor = Column(String)
    actor_name = Column(String)
    office_n = Column(Integer)
    action = Column(String)
    entity = Column(String)
    prev_state = Column(String, default="")
    new_state = Column(String, default="")
    reason = Column(String, default="")
    ip = Column(String, default="0.0.0.0")
    device = Column(String, default="web")
    auth_level = Column(String, default="mfa")
    prev_hash = Column(String)
    hash = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
