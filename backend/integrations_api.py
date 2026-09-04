# -*- coding: utf-8 -*-
"""
Integrations API — the external systems ICMS connects to (Document §4 stack,
§5 architecture: "Integration/API Management" appears as a primary module for
IT & System Administration offices).

We model each integration as a connector with a category, status, and the
office that owns it. Endpoints let owning offices view health and toggle a
connector (audited). Non-owning offices get read-only visibility.

These are representative connectors modeled on what large universities
(Yale, Harvard, IIT ERPs) actually run: SSO/identity, LMS, payments,
communications, library federation, biometric attendance, HR/payroll, BI.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import db, auth, write_audit
from database import office

router = APIRouter(prefix="/api/integrations")

# Static registry of connectors. status is dynamic (stored per-process here for
# the demo; in production this lives in the Config service).
CONNECTORS = [
    {"key": "sso_oidc", "name": "SSO / OIDC Identity", "category": "Identity",
     "vendor": "Okta / Azure AD", "owner_office": 28,
     "desc": "OAuth2/OIDC single sign-on with MFA for all staff and students.",
     "protocol": "OIDC + SAML 2.0"},
    {"key": "lms", "name": "Learning Management System", "category": "Academics",
     "vendor": "Canvas / Moodle", "owner_office": 27,
     "desc": "Course content, assignments and grade passback via LTI 1.3.",
     "protocol": "LTI 1.3 / REST"},
    {"key": "payments", "name": "Payment Gateway", "category": "Finance",
     "vendor": "Stripe / Razorpay", "owner_office": 22,
     "desc": "Online fee collection, receipts and reconciliation webhooks.",
     "protocol": "REST + Webhooks"},
    {"key": "comms", "name": "Email & SMS Gateway", "category": "Communications",
     "vendor": "SendGrid / Twilio", "owner_office": 27,
     "desc": "Transactional notifications: admissions, results, fee reminders.",
     "protocol": "SMTP / REST"},
    {"key": "library_fed", "name": "Library Federation", "category": "Library",
     "vendor": "OCLC / Z39.50", "owner_office": 19,
     "desc": "Union catalogue search and inter-library loan.",
     "protocol": "Z39.50 / SRU"},
    {"key": "biometric", "name": "Biometric Attendance", "category": "Operations",
     "vendor": "ZKTeco devices", "owner_office": 27,
     "desc": "Device-driven staff attendance feeding HR & payroll.",
     "protocol": "Device SDK / MQTT"},
    {"key": "payroll", "name": "HR & Payroll", "category": "HR",
     "vendor": "Workday / SAP SF", "owner_office": 24,
     "desc": "Employee lifecycle, appraisal and payroll runs.",
     "protocol": "SOAP / REST"},
    {"key": "erp_finance", "name": "Finance ERP", "category": "Finance",
     "vendor": "SAP / Oracle Fusion", "owner_office": 22,
     "desc": "General ledger, budgeting and procurement posting.",
     "protocol": "REST / IDoc"},
    {"key": "bi", "name": "Analytics & BI", "category": "Analytics",
     "vendor": "Power BI / Metabase", "owner_office": 28,
     "desc": "Executive dashboards and accreditation reporting.",
     "protocol": "JDBC / REST"},
    {"key": "video", "name": "Video Conferencing", "category": "Academics",
     "vendor": "Zoom / MS Teams", "owner_office": 27,
     "desc": "Scheduled online classes and viva; recordings to LMS.",
     "protocol": "REST / OAuth2"},
    {"key": "antiplag", "name": "Anti-Plagiarism", "category": "Academics",
     "vendor": "Turnitin", "owner_office": 16,
     "desc": "Similarity checks for assignments and theses.",
     "protocol": "REST / LTI"},
    {"key": "accreditation", "name": "Accreditation / Compliance", "category": "Governance",
     "vendor": "NAAC / NBA / ABET feeds", "owner_office": 9,
     "desc": "Outcome attainment and compliance evidence export.",
     "protocol": "CSV / REST"},
]

# in-memory status store (demo). key -> {enabled, last_sync, health}
_STATUS = {c["key"]: {"enabled": True, "health": "healthy",
                      "last_sync": datetime.utcnow().isoformat()}
           for c in CONNECTORS}
# a couple degraded/disabled for realism
_STATUS["biometric"]["health"] = "degraded"
_STATUS["antiplag"]["enabled"] = False
_STATUS["antiplag"]["health"] = "disabled"


def _can_manage(ctx, conn):
    # owning office, or IT/SysAdmin (27/28) may manage any connector
    return ctx["office_n"] in (conn["owner_office"], 27, 28)


@router.get("")
def list_integrations(ctx=Depends(auth), s=Depends(db)):
    items = []
    for c in CONNECTORS:
        st = _STATUS[c["key"]]
        items.append({**c, **st, "can_manage": _can_manage(ctx, c),
                      "owner_office_name": office(c["owner_office"]).get("name", "")})
    # summary
    healthy = sum(1 for k in _STATUS if _STATUS[k]["health"] == "healthy")
    return {"integrations": items,
            "summary": {"total": len(CONNECTORS), "healthy": healthy,
                        "categories": len(set(c["category"] for c in CONNECTORS))},
            "can_manage_any": any(_can_manage(ctx, c) for c in CONNECTORS)}


class ToggleIn(BaseModel):
    key: str


@router.post("/toggle")
def toggle_integration(body: ToggleIn, ctx=Depends(auth), s=Depends(db)):
    conn = next((c for c in CONNECTORS if c["key"] == body.key), None)
    if not conn:
        raise HTTPException(404, "Unknown connector")
    if not _can_manage(ctx, conn):
        raise HTTPException(403, "Only the owning office or IT/SysAdmin may manage this connector")
    st = _STATUS[body.key]
    st["enabled"] = not st["enabled"]
    st["health"] = "healthy" if st["enabled"] else "disabled"
    st["last_sync"] = datetime.utcnow().isoformat()
    write_audit(s, ctx["sub"], ctx.get("role", ""), ctx["office_n"],
                "integration.toggle", f"connector:{body.key}", "",
                "enabled" if st["enabled"] else "disabled",
                f"{conn['name']} {'enabled' if st['enabled'] else 'disabled'}")
    return {"key": body.key, **st}


@router.post("/sync")
def sync_integration(body: ToggleIn, ctx=Depends(auth), s=Depends(db)):
    conn = next((c for c in CONNECTORS if c["key"] == body.key), None)
    if not conn:
        raise HTTPException(404, "Unknown connector")
    if not _can_manage(ctx, conn):
        raise HTTPException(403, "Not authorized to sync this connector")
    st = _STATUS[body.key]
    st["last_sync"] = datetime.utcnow().isoformat()
    if st["enabled"]:
        st["health"] = "healthy"
    write_audit(s, ctx["sub"], ctx.get("role", ""), ctx["office_n"],
                "integration.sync", f"connector:{body.key}", "", "synced",
                f"Manual sync: {conn['name']}")
    return {"key": body.key, **st}
