"""Phase 2 cycle and applicant-draft services; no eligibility/allocation logic."""
import hashlib
import json
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException

from admissions_service import transition_application
from core import uid, write_audit
from database import TENANT
import domain_models as D


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_datetime(value):
    return datetime.fromisoformat(value) if value else None


def cycle_is_open(cycle, at=None):
    at = at or now_utc()
    return (cycle.status or "").upper() == "PUBLISHED" and (not cycle.opens_at or cycle.opens_at <= at) and (not cycle.closes_at or cycle.closes_at >= at)


def cycle_program_or_404(session, tenant_id, cycle_program_id, require_open=True):
    row = session.get(D.AdmissionCycleProgram, cycle_program_id)
    if not row or row.tenant_id != tenant_id or not row.active:
        raise HTTPException(404, "Active admission cycle programme not found")
    cycle = session.get(D.AdmissionCycle, row.cycle_id)
    if not cycle or cycle.tenant_id != tenant_id:
        raise HTTPException(404, "Admission cycle not found")
    if require_open and not cycle_is_open(cycle):
        raise HTTPException(409, "Admissions are not open for this cycle programme")
    return cycle, row


def _hash(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_access_token(session, application, purpose="applicant_access", expires_hours=72):
    raw = secrets.token_urlsafe(32)
    expires_at = now_utc().replace(microsecond=0)
    from datetime import timedelta
    expires_at += timedelta(hours=expires_hours)
    session.add(D.ApplicantAccessToken(id=uid(), tenant_id=application.tenant_id,
                application_id=application.id, token_hash=_hash(raw), purpose=purpose,
                expires_at=expires_at))
    return raw


def application_for_token(session, raw_token, application_id):
    if not raw_token:
        raise HTTPException(401, "Applicant access token required")
    token = (session.query(D.ApplicantAccessToken)
             .filter(D.ApplicantAccessToken.token_hash == _hash(raw_token)).first())
    if not token or token.application_id != application_id or token.purpose != "applicant_access":
        raise HTTPException(403, "Applicant token cannot access this application")
    if token.revoked_at or token.consumed_at or token.expires_at < now_utc():
        raise HTTPException(401, "Applicant access token is expired or revoked")
    application = session.get(D.Application, application_id)
    if not application or application.tenant_id != token.tenant_id:
        raise HTTPException(404, "Application not found")
    return application, token


def applicant_context(application, token):
    return {"sub": f"applicant-token:{token.id}", "tenant_id": application.tenant_id,
            "office_n": 0, "scope_level": "individual", "scope_ref": application.id,
            "auth_level": "token"}


def assert_editable(application):
    if application.current_status != "DRAFT":
        raise HTTPException(409, "Submitted applications are read-only until a future correction workflow reopens them")


def assert_version(application, expected):
    if application.status_version != expected:
        raise HTTPException(409, "Application changed; reload before saving")


def save_application(session, application, token, expected_version, changes, audit_action):
    assert_editable(application)
    assert_version(application, expected_version)
    for key, value in changes.items():
        setattr(application, key, value)
    application.status_version += 1
    write_audit(session, f"applicant-token:{token.id}", "Applicant", 0, audit_action,
                f"application:{application.id}", application.current_status, application.current_status,
                "Applicant draft update", "token", commit=False)
    session.commit()
    return application


def validate_submission(session, application):
    cycle, cycle_program = cycle_program_or_404(session, application.tenant_id, application.cycle_program_id, True)
    missing = []
    if not (application.applicant_name or "").strip(): missing.append("applicant_name")
    if not (application.email or "").strip(): missing.append("email")
    if not (application.phone or "").strip(): missing.append("phone")
    preferences = session.query(D.ApplicationPreference).filter_by(application_id=application.id).all()
    if not preferences: missing.append("at least one programme preference")
    required = (session.query(D.AdmissionDocumentRequirement)
                .filter(D.AdmissionDocumentRequirement.tenant_id == application.tenant_id,
                        D.AdmissionDocumentRequirement.cycle_id == cycle.id,
                        D.AdmissionDocumentRequirement.mandatory == True,
                        D.AdmissionDocumentRequirement.active == True).all())
    document_requirement_ids = {row.requirement_id for row in session.query(D.ApplicationDocument)
                                .filter(D.ApplicationDocument.application_id == application.id).all()}
    missing_docs = [row.document_type for row in required
                    if row.program_id in (None, "", cycle_program.program_id) and row.id not in document_requirement_ids]
    if missing_docs: missing.append("mandatory documents: " + ", ".join(missing_docs))
    if missing:
        raise HTTPException(422, {"message": "Application is incomplete", "missing": missing})


def submit_application(session, application, token, expected_version):
    assert_editable(application)
    assert_version(application, expected_version)
    validate_submission(session, application)
    application.submitted_at = now_utc()
    result = transition_application(session, applicant_context(application, token), application.id,
                                    "submit", expected_version, "Applicant submitted application",
                                    skip_capability=True)
    return result


def application_payload(session, application):
    cycle = session.get(D.AdmissionCycle, application.cycle_id) if application.cycle_id else None
    prefs = (session.query(D.ApplicationPreference).filter_by(application_id=application.id)
             .order_by(D.ApplicationPreference.preference_rank).all())
    programs = {p.id: p for p in session.query(D.Program).filter(D.Program.id.in_([x.program_id for x in prefs])).all()} if prefs else {}
    docs = session.query(D.ApplicationDocument).filter_by(application_id=application.id).all()
    history = (session.query(D.ApplicationStatusHistory).filter_by(application_id=application.id)
               .order_by(D.ApplicationStatusHistory.created_at).all())
    completeness = document_completeness(session, application)
    return {"id": application.id, "application_no": application.application_no,
            "applicant_name": application.applicant_name, "email": application.email, "phone": application.phone,
            "date_of_birth": application.date_of_birth.isoformat() if application.date_of_birth else None,
            "gender": application.gender, "profile": json.loads(application.profile_json or "{}"),
            "cycle": {"id": cycle.id, "name": cycle.name, "academic_year": cycle.academic_year} if cycle else None,
            "campus": application.campus, "current_status": application.current_status,
            "status": application.status, "status_version": application.status_version,
            "submitted_at": application.submitted_at.isoformat() if application.submitted_at else None,
            "preferences": [{"id": x.id, "program_id": x.program_id, "program": programs[x.program_id].name if x.program_id in programs else "", "rank": x.preference_rank} for x in prefs],
            "documents": [{"id": x.id, "requirement_id": x.requirement_id, "document_type": x.document_type,
                           "file_name": x.file_name, "mime_type": x.mime_type, "storage_key": x.storage_key,
                           "verification_status": x.verification_status} for x in docs],
            "document_completeness": completeness,
            "history": [{"from": x.from_status, "to": x.to_status, "action": x.action,
                         "at": x.created_at.isoformat(), "reason": x.reason} for x in history]}


def document_completeness(session, application):
    cycle_program = session.get(D.AdmissionCycleProgram, application.cycle_program_id)
    required = (session.query(D.AdmissionDocumentRequirement)
                .filter(D.AdmissionDocumentRequirement.tenant_id == application.tenant_id,
                        D.AdmissionDocumentRequirement.cycle_id == application.cycle_id,
                        D.AdmissionDocumentRequirement.mandatory == True,
                        D.AdmissionDocumentRequirement.active == True).all())
    applicable = [row for row in required if row.program_id in (None, "", cycle_program.program_id if cycle_program else None)]
    uploaded = {row.requirement_id for row in session.query(D.ApplicationDocument)
                .filter(D.ApplicationDocument.application_id == application.id).all()}
    missing = [row.document_type for row in applicable if row.id not in uploaded]
    return {"required": len(applicable), "uploaded": len(applicable) - len(missing), "missing": missing,
            "complete": not missing}
