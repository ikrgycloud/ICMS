from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from models import Base, Person, User, Delegation
import administration_models as AM
from administration_api import (RequirementIn, ActionIn, CategorizeIn, AssignIn, EvidenceIn, ClosureIn, FinanceReservationIn,
                                create_requirement, submit_requirement, validate, categorize, assign, accept,
                                evidence, ready, complete, close, get_requirement, update_execution, ExecutionIn,
                                delete_evidence, list_evidence, administration_report)
from administration_api import create_approval_policy, create_routing_rule, create_sla_policy, budget_review, approve, PolicyIn, RoutingRuleIn, SlaPolicyIn
from administration_api import dashboard, administration_alerts
from specialist_api import create_specialist_record, update_specialist_record, CreateIn, UpdateIn
from administration_jobs import process_slas, process_outbox, pause_sla, resume_sla, complete_sla, emit_outbox, claim_outbox_events
from evidence_policy import resolve_evidence_policy
from evidence_storage import EvidenceStorageAdapter
from administration_state import require_transition
from datetime import datetime, timedelta


def ctx(user, office, tenant="tenant-a"):
    return {"sub": user, "office_n": office, "tenant_id": tenant, "scope_level": "campus", "auth_level": "mfa"}


def setup_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    for ident, office in (("dean", 7), ("hod", 10), ("maintenance", 29), ("principal", 4)):
        session.add(Person(id=f"p-{ident}", tenant_id="tenant-a", name=ident, email="", contact=""))
        session.add(User(id=ident, tenant_id="tenant-a", person_id=f"p-{ident}", username=ident, password_hash="", office_n=office, role=ident, scope_level="campus"))
    session.commit()
    return session


def test_requirement_is_typed_scoped_and_closes_only_after_evidence():
    s = setup_db()
    create_approval_policy(PolicyIn(category="FACILITIES", approver_office_n=4), ctx("principal", 4), s)
    create_routing_rule(RoutingRuleIn(category="FACILITIES", responsible_office_n=29), ctx("dean", 7), s)
    create_sla_policy(SlaPolicyIn(category="FACILITIES", responsible_office_n=29, duration_hours=48), ctx("principal", 4), s)
    row = create_requirement(RequirementIn(title="Repair lab ventilation", category="FACILITIES", department_id="d1"), ctx("hod", 10), s)
    assert row["state"] == "DRAFT"
    row = submit_requirement(row["id"], ActionIn(expected_version=row["version"]), ctx("hod", 10), s)
    row = validate(row["id"], ActionIn(expected_version=row["version"]), ctx("dean", 7), s)
    row = categorize(row["id"], CategorizeIn(expected_version=row["version"], category="FACILITIES"), ctx("dean", 7), s)
    row = budget_review(row["id"], ActionIn(expected_version=row["version"]), ctx("dean", 7), s)
    row = approve(row["id"], ActionIn(expected_version=row["version"]), ctx("principal", 4), s)
    row = assign(row["id"], AssignIn(expected_version=row["version"], office_n=29, user_id="maintenance"), ctx("dean", 7), s)
    row = accept(row["id"], ActionIn(expected_version=row["version"]), ctx("maintenance", 29), s)
    with __import__("pytest").raises(HTTPException):
        ready(row["id"], ActionIn(expected_version=row["version"]), ctx("maintenance", 29), s)
    row = update_execution(row["id"], ExecutionIn(expected_version=row["version"], status="COMPLETED", completion_notes="Ventilation repaired"), ctx("maintenance", 29), s)
    s.add(AM.AdministrativeEvidence(id="verified-work-order", tenant_id="tenant-a", requirement_id=row["id"], evidence_type="WORK_ORDER", file_name="work-order.pdf", uploaded_by="maintenance", verification_status="VERIFIED")); s.commit()
    row=get_requirement(row["id"],ctx("dean",7),s)
    row = ready(row["id"], ActionIn(expected_version=row["version"]), ctx("maintenance", 29), s)
    row = complete(row["id"], ActionIn(expected_version=row["version"]), ctx("dean", 7), s)
    row = close(row["id"], ClosureIn(expected_version=row["version"], evidence_verified=True, execution_verified=True, budget_verified=True, reason="Verified"), ctx("dean", 7), s)
    assert row["state"] == "CLOSED"
    assert s.query(AM.AdministrativeTransition).filter_by(requirement_id=row["id"]).count() >= 8


def test_requirement_access_is_tenant_scoped():
    s = setup_db()
    row = create_requirement(RequirementIn(title="Need desks", category="ASSETS"), ctx("hod", 10), s)
    with __import__("pytest").raises(HTTPException) as error:
        get_requirement(row["id"], ctx("dean", 7, "tenant-b"), s)
    assert error.value.status_code == 404


def test_database_policy_drives_approval_then_data_rule_routes_work():
    s = setup_db()
    create_approval_policy(PolicyIn(category="PROCUREMENT", approver_office_n=4, min_amount=0), ctx("principal", 4), s)
    create_routing_rule(RoutingRuleIn(category="PROCUREMENT", responsible_office_n=32, sla_hours=48), ctx("dean", 7), s)
    create_sla_policy(SlaPolicyIn(category="PROCUREMENT", responsible_office_n=32, duration_hours=48),ctx("principal",4),s)
    row=create_requirement(RequirementIn(title="Network switches", category="PROCUREMENT", estimated_cost=50000),ctx("hod",10),s)
    row=submit_requirement(row["id"],ActionIn(expected_version=row["version"]),ctx("hod",10),s)
    row=validate(row["id"],ActionIn(expected_version=row["version"]),ctx("dean",7),s)
    row=categorize(row["id"],CategorizeIn(expected_version=row["version"],category="PROCUREMENT"),ctx("dean",7),s)
    row=budget_review(row["id"],ActionIn(expected_version=row["version"]),ctx("dean",7),s)
    assert row["state"] == "PENDING_APPROVAL"
    row=approve(row["id"],ActionIn(expected_version=row["version"],reason="Within approved policy"),ctx("principal",4),s)
    assert row["state"] == "ROUTED" and row["responsible_office_n"] == 32 and row["sla"] is not None


def test_facilities_office_owns_a_real_work_order_not_a_generic_asset():
    s=setup_db()
    create_approval_policy(PolicyIn(category="FACILITIES", approver_office_n=4),ctx("principal",4),s); create_routing_rule(RoutingRuleIn(category="FACILITIES", responsible_office_n=29),ctx("dean",7),s); create_sla_policy(SlaPolicyIn(category="FACILITIES", responsible_office_n=29,duration_hours=48),ctx("principal",4),s)
    row=create_requirement(RequirementIn(title="Repair access ramp",category="FACILITIES"),ctx("hod",10),s)
    row=submit_requirement(row["id"],ActionIn(expected_version=row["version"]),ctx("hod",10),s)
    row=validate(row["id"],ActionIn(expected_version=row["version"]),ctx("dean",7),s)
    row=categorize(row["id"],CategorizeIn(expected_version=row["version"],category="FACILITIES"),ctx("dean",7),s)
    row=budget_review(row["id"],ActionIn(expected_version=row["version"]),ctx("dean",7),s); row=approve(row["id"],ActionIn(expected_version=row["version"]),ctx("principal",4),s); row=assign(row["id"],AssignIn(expected_version=row["version"],office_n=29,user_id="maintenance"),ctx("dean",7),s)
    row=accept(row["id"],ActionIn(expected_version=row["version"]),ctx("maintenance",29),s)
    work=create_specialist_record(row["id"],CreateIn(),ctx("maintenance",29),s)
    assert work["type"] == "facility_work_orders"
    update_specialist_record(row["id"],UpdateIn(expected_version=row["version"],status="IN_PROGRESS",notes="Work started"),ctx("maintenance",29),s)
    row=get_requirement(row["id"],ctx("maintenance",29),s)
    result=update_specialist_record(row["id"],UpdateIn(expected_version=row["version"],status="COMPLETED",notes="Ramp repaired"),ctx("maintenance",29),s)
    assert result["requirement_state"] == "PENDING_EVIDENCE"


def test_sla_breach_is_idempotent_and_delivered_through_outbox():
    s=setup_db()
    row=create_requirement(RequirementIn(title="Urgent repair",category="FACILITIES"),ctx("hod",10),s)
    now=datetime.utcnow(); sla=AM.AdministrativeSla(id="sla1",tenant_id="tenant-a",requirement_id=row["id"],duration_hours=1,started_at=now-timedelta(hours=2),due_at=now-timedelta(hours=1))
    s.add(sla);s.commit()
    assert process_slas(s,now)==1
    assert s.get(AM.AdministrativeSla,"sla1").status=="BREACHED"
    assert process_slas(s,now)==0
    assert s.query(AM.AdministrativeOutboxEvent).count()==1
    assert process_outbox(s,datetime.utcnow())==1
    assert s.query(AM.AdministrativeOutboxEvent).one().status=="PROCESSED"


def test_sla_pause_resume_preserves_snapshot_and_excludes_hold_duration():
    s=setup_db(); row=create_requirement(RequirementIn(title="Held repair",category="FACILITIES"),ctx("hod",10),s)
    start=datetime.utcnow()-timedelta(minutes=30)
    sla=AM.AdministrativeSla(id="pause-sla",tenant_id="tenant-a",requirement_id=row["id"],duration_hours=1,
        started_at=start,due_at=start+timedelta(hours=1),original_due_at=start+timedelta(hours=1),approaching_percent=80,pause_allowed=True)
    s.add(sla);s.commit()
    held_at=start+timedelta(minutes=30); assert pause_sla(s,row["id"],"tenant-a",held_at)
    assert not pause_sla(s,row["id"],"tenant-a",held_at+timedelta(minutes=1))
    assert resume_sla(s,row["id"],"tenant-a",held_at+timedelta(hours=2))
    s.commit(); sla=s.get(AM.AdministrativeSla,"pause-sla")
    assert sla.status=="ACTIVE" and sla.paused_seconds==7200 and sla.due_at==start+timedelta(hours=3)
    assert process_slas(s,start+timedelta(hours=2,minutes=50))==1
    assert sla.status=="APPROACHING"


def test_sla_completion_is_idempotent_and_retains_prior_breach():
    s=setup_db(); row=create_requirement(RequirementIn(title="Late repair",category="FACILITIES"),ctx("hod",10),s)
    now=datetime.utcnow(); sla=AM.AdministrativeSla(id="complete-sla",tenant_id="tenant-a",requirement_id=row["id"],duration_hours=1,started_at=now-timedelta(hours=2),due_at=now-timedelta(hours=1),original_due_at=now-timedelta(hours=1))
    s.add(sla);s.commit(); assert process_slas(s,now)==1
    assert complete_sla(s,row["id"],"tenant-a",now+timedelta(minutes=1)); s.commit()
    assert s.get(AM.AdministrativeSla,"complete-sla").status=="COMPLETED"
    assert not complete_sla(s,row["id"],"tenant-a",now+timedelta(minutes=2))
    assert process_slas(s,now+timedelta(days=1))==0


def test_evidence_policy_is_category_aware_and_requires_completed_execution():
    s=setup_db()
    expected={"FACILITIES":"WORK_ORDER","WORKFORCE":"STAFFING","IT":"RESOLUTION","PROCUREMENT":"GOODS_RECEIPT","BUDGET":"FINANCE_DECISION","INVENTORY":"GOODS_RECEIPT"}
    for category, evidence_type in expected.items():
        row=create_requirement(RequirementIn(title=f"{category} evidence",category=category),ctx("hod",10),s)
        s.add(AM.AdministrativeExecution(id=f"exec-{category}",tenant_id="tenant-a",requirement_id=row["id"],owning_office_n=29,status="COMPLETED",updated_by="maintenance"))
        s.commit(); result=resolve_evidence_policy(s,s.get(AM.AdministrativeRequirement,row["id"]))
        assert not result["satisfied"] and result["missing"]
        s.add(AM.AdministrativeEvidence(id=f"ev-{category}",tenant_id="tenant-a",requirement_id=row["id"],evidence_type=evidence_type,uploaded_by="maintenance",verification_status="VERIFIED"));s.commit()
        assert resolve_evidence_policy(s,s.get(AM.AdministrativeRequirement,row["id"]))["satisfied"]


def test_evidence_policy_reports_execution_incomplete_before_evidence():
    s=setup_db(); row=create_requirement(RequirementIn(title="No execution",category="FACILITIES"),ctx("hod",10),s)
    result=resolve_evidence_policy(s,s.get(AM.AdministrativeRequirement,row["id"]))
    assert result["reason"]=="EXECUTION_INCOMPLETE" and result["missing"]==["EXECUTION"]


def test_local_evidence_storage_normalizes_filename_and_rejects_traversal(tmp_path):
    storage=EvidenceStorageAdapter(root=tmp_path)
    key, checksum=storage.put(b"approved evidence", "../../signed report?.pdf")
    assert ".." not in key and storage.get(key)==b"approved evidence"
    assert len(checksum)==64
    with __import__("pytest").raises(ValueError): storage.get("../../outside")


def test_dashboard_alert_read_model_uses_authoritative_scoped_state():
    s=setup_db()
    approval=create_requirement(RequirementIn(title="Approval needed",category="FACILITIES"),ctx("hod",10),s)
    routed=create_requirement(RequirementIn(title="Acceptance needed",category="FACILITIES"),ctx("hod",10),s)
    blocked=create_requirement(RequirementIn(title="Blocked repair",category="FACILITIES"),ctx("hod",10),s)
    s.get(AM.AdministrativeRequirement,approval["id"]).state="PENDING_APPROVAL"
    s.get(AM.AdministrativeRequirement,routed["id"]).state="ROUTED"
    blocked_row=s.get(AM.AdministrativeRequirement,blocked["id"]); blocked_row.state="IN_PROGRESS"; blocked_row.responsible_office_n=29
    s.add(AM.AdministrativeExecution(id="blocked-exec",tenant_id="tenant-a",requirement_id=blocked["id"],owning_office_n=29,status="ON_HOLD",updated_by="maintenance"));s.commit()
    result=dashboard(ctx=ctx("dean",7),s=s)
    assert result["kpis"]["pending_approval"]==1 and result["kpis"]["unaccepted_assignments"]==1
    assert result["financial"]["available"] is False
    alerts=administration_alerts(ctx=ctx("dean",7),s=s)["alerts"]
    assert {a["type"] for a in alerts}>={"PENDING_APPROVAL","UNACCEPTED_ASSIGNMENT","SPECIALIST_BLOCKED"}


def test_evidence_delete_retains_auditable_metadata_and_hides_content():
    s=setup_db(); row=create_requirement(RequirementIn(title="Delete evidence",category="FACILITIES"),ctx("hod",10),s)
    item=AM.AdministrativeEvidence(id="evidence-delete",tenant_id="tenant-a",requirement_id=row["id"],evidence_type="OTHER",uploaded_by="hod")
    s.add(item); s.commit()
    assert delete_evidence(item.id,ctx("hod",10),s)["ok"]
    assert s.get(AM.AdministrativeEvidence,item.id).deleted_by=="hod"
    assert list_evidence(row["id"],ctx("hod",10),s)["evidence"]==[]


def test_administration_reports_are_scoped_and_domain_unavailability_is_explicit():
    s=setup_db(); row=create_requirement(RequirementIn(title="Reportable repair",category="FACILITIES"),ctx("hod",10),s)
    report=administration_report("requirements",ctx=ctx("dean",7),s=s)
    assert report["available"] and any(item["id"]==row["id"] for item in report["items"])
    finance=administration_report("finance",ctx=ctx("dean",7),s=s)
    assert finance["available"] is False and finance["items"]==[]


def test_requirement_state_graph_rejects_invalid_stage_changes():
    import pytest
    require_transition("DRAFT", "SUBMITTED")
    with pytest.raises(HTTPException):
        require_transition("DRAFT", "CLOSED")
    with pytest.raises(HTTPException):
        require_transition("CLOSED", "IN_PROGRESS")


def test_active_scoped_delegation_can_approve_and_is_persisted():
    s=setup_db(); create_approval_policy(PolicyIn(category="FACILITIES",approver_office_n=4),ctx("principal",4),s); create_routing_rule(RoutingRuleIn(category="FACILITIES",responsible_office_n=29),ctx("dean",7),s); create_sla_policy(SlaPolicyIn(category="FACILITIES",responsible_office_n=29,duration_hours=48),ctx("principal",4),s)
    s.add(Delegation(id="delegation-1",tenant_id="tenant-a",from_user="principal",to_user="dean",authority="approve:administration",scope_ref='{"category":"FACILITIES"}',start=datetime.utcnow()-timedelta(hours=1),end=datetime.utcnow()+timedelta(hours=1),status="active")); s.commit()
    row=create_requirement(RequirementIn(title="Delegated repair",category="FACILITIES"),ctx("hod",10),s)
    row=submit_requirement(row["id"],ActionIn(expected_version=row["version"]),ctx("hod",10),s); row=validate(row["id"],ActionIn(expected_version=row["version"]),ctx("dean",7),s); row=categorize(row["id"],CategorizeIn(expected_version=row["version"],category="FACILITIES"),ctx("dean",7),s); row=budget_review(row["id"],ActionIn(expected_version=row["version"]),ctx("dean",7),s)
    row=approve(row["id"],ActionIn(expected_version=row["version"],reason="Delegated approval"),ctx("dean",7),s)
    approval=s.query(AM.AdministrativeApproval).filter_by(requirement_id=row["id"]).one()
    assert row["state"]=="ROUTED" and approval.delegation_id=="delegation-1" and approval.delegated_from_user_id=="principal"


def test_delegation_authority_matches_namespaced_action_tokens():
    from authority import authorize, DELEGATED
    delegation = {
        "status": "active",
        "authority": "approve:administration",
        "start": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
        "end": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "limit": None,
    }
    decision = authorize(
        ctx={"sub": "delegatee", "scope_level": "campus"},
        action="approve",
        resource="administration",
        rbac_authority=DELEGATED,
        active_delegation=delegation,
        target_scope_level="campus",
    )
    assert decision.outcome == "ALLOW"


def test_approval_rejection_is_audited_and_idempotent_evented():
    s=setup_db(); create_approval_policy(PolicyIn(category="FACILITIES",approver_office_n=4),ctx("principal",4),s)
    row=create_requirement(RequirementIn(title="Rejected repair",category="FACILITIES"),ctx("hod",10),s)
    row=submit_requirement(row["id"],ActionIn(expected_version=row["version"]),ctx("hod",10),s); row=validate(row["id"],ActionIn(expected_version=row["version"]),ctx("dean",7),s); row=categorize(row["id"],CategorizeIn(expected_version=row["version"],category="FACILITIES"),ctx("dean",7),s); row=budget_review(row["id"],ActionIn(expected_version=row["version"]),ctx("dean",7),s)
    from administration_api import reject_approval
    row=reject_approval(row["id"],ActionIn(expected_version=row["version"],reason="Insufficient justification"),ctx("principal",4),s)
    assert row["state"]=="REJECTED"
    assert s.query(AM.AdministrativeOutboxEvent).filter_by(event_type="ApprovalRejected").count()==1


def test_expired_or_wrong_scope_delegation_cannot_approve():
    s=setup_db(); create_approval_policy(PolicyIn(category="FACILITIES",approver_office_n=4),ctx("principal",4),s); create_routing_rule(RoutingRuleIn(category="FACILITIES",responsible_office_n=29),ctx("dean",7),s); create_sla_policy(SlaPolicyIn(category="FACILITIES",responsible_office_n=29,duration_hours=48),ctx("principal",4),s)
    s.add(Delegation(id="expired-delegation",tenant_id="tenant-a",from_user="principal",to_user="dean",authority="approve:administration",scope_ref='{"category":"PROCUREMENT"}',start=datetime.utcnow()-timedelta(days=2),end=datetime.utcnow()-timedelta(days=1),status="active")); s.commit()
    row=create_requirement(RequirementIn(title="Undelegated repair",category="FACILITIES"),ctx("hod",10),s); row=submit_requirement(row["id"],ActionIn(expected_version=row["version"]),ctx("hod",10),s); row=validate(row["id"],ActionIn(expected_version=row["version"]),ctx("dean",7),s); row=categorize(row["id"],CategorizeIn(expected_version=row["version"],category="FACILITIES"),ctx("dean",7),s); row=budget_review(row["id"],ActionIn(expected_version=row["version"]),ctx("dean",7),s)
    from administration_api import approve
    with __import__('pytest').raises(HTTPException): approve(row["id"],ActionIn(expected_version=row["version"],reason="Should be denied"),ctx("dean",7),s)


def test_finance_reservation_and_commitment_use_budget_line_without_overreservation():
    s=setup_db(); s.add(User(id="finance",tenant_id="tenant-a",person_id="p-principal",username="finance",password_hash="",office_n=22,role="finance",scope_level="campus")); budget=__import__('domain_models').BudgetLine(id="budget-1",tenant_id="tenant-a",category="Infrastructure",allocated=1000,spent=100,reserved=0,committed=0); s.add(budget); s.commit()
    from administration_api import reserve_finance, commit_finance
    row=create_requirement(RequirementIn(title="Finance-controlled repair",category="BUDGET",estimated_cost=500),ctx("hod",10),s); row["state"]="IN_EXECUTION"
    dbrow=s.get(AM.AdministrativeRequirement,row["id"]); dbrow.state="IN_EXECUTION"; dbrow.responsible_office_n=22; dbrow.assigned_user_id="finance"; dbrow.version=1; s.commit()
    result=reserve_finance(row["id"],FinanceReservationIn(expected_version=1,budget_line_id="budget-1"),ctx("finance",22),s)
    assert result["reserved"]==500 and result["available"]==400
    result=commit_finance(row["id"],ActionIn(expected_version=1),ctx("finance",22),s)
    assert result["committed"]==500 and result["reserved"]==0 and result["available"]==400


def test_budget_closure_requires_persisted_finance_commitment():
    s=setup_db(); row=create_requirement(RequirementIn(title="Budget closure",category="BUDGET"),ctx("hod",10),s); dbrow=s.get(AM.AdministrativeRequirement,row["id"]); dbrow.state="COMPLETED"; dbrow.version=1; s.commit()
    with __import__('pytest').raises(HTTPException) as error:
        close(row["id"],ClosureIn(expected_version=1,evidence_verified=True,execution_verified=True,budget_verified=True,reason="Close"),ctx("dean",7),s)
    assert error.value.status_code==409 and "FINANCE_COMMITMENT_REQUIRED" in str(error.value.detail)


def test_metadata_only_evidence_is_rejected_before_it_can_enter_closure_flow():
    s=setup_db(); row=create_requirement(RequirementIn(title="No metadata-only proof",category="FACILITIES"),ctx("hod",10),s)
    with __import__("pytest").raises(HTTPException) as error:
        evidence(row["id"],EvidenceIn(expected_version=row["version"],evidence_type="WORK_ORDER",file_name="claim.pdf"),ctx("dean",7),s)
    assert error.value.status_code==410
    assert s.query(AM.AdministrativeEvidence).count()==0


def test_outbox_lease_prevents_a_second_worker_from_claiming_an_event():
    s=setup_db()
    emit_outbox(s,"tenant-a","TestEvent","requirement-1",{"recipient":"hod","title":"test"},"lease-test")
    s.commit()
    now=datetime.utcnow()
    first=claim_outbox_events(s,now,worker_id="worker-a")
    assert len(first)==1
    assert claim_outbox_events(s,now,worker_id="worker-b")==[]
    event=s.get(AM.AdministrativeOutboxEvent,first[0]); event.lease_expires_at=now-timedelta(seconds=1); s.commit()
    assert claim_outbox_events(s,now,worker_id="worker-b")==first
    assert s.get(AM.AdministrativeOutboxEvent,first[0]).locked_by=="worker-b"


def test_evidence_storage_refuses_local_provider_in_production(monkeypatch,tmp_path):
    monkeypatch.setenv("ICMS_ENVIRONMENT","production")
    monkeypatch.setenv("EVIDENCE_STORAGE_PROVIDER","local")
    with __import__("pytest").raises(RuntimeError): EvidenceStorageAdapter(root=tmp_path)
