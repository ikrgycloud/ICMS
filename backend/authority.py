# -*- coding: utf-8 -*-
"""
ICMS Authority Engine — the one idea everything rests on (Document §2, §7).

Effective authority is COMPUTED PER REQUEST from independent, configurable factors:
    ROLE + PERMISSION + ORG-SCOPE + APPROVAL-LIMIT
  + DELEGATION + WORKFLOW-STATE + TIME-VALIDITY + AUTH-LEVEL
Every decision (ALLOW / DENY / RECOMMEND / ESCALATE) is audited (hash-chained).

Nothing here is hardcoded to a role — the engine reads config (roles, permissions,
scope tree, approval limits, delegations) and decides. Build once; all 40 offices inherit.
"""
from __future__ import annotations
import os
import hashlib
import hmac
import json
import time
import base64
from datetime import datetime, timezone
from typing import Optional

# ----------------------------------------------------------------------------
# Authority vocabulary (Document §2) — replaces vague Yes/No everywhere.
# ----------------------------------------------------------------------------
FULL = "Full"
LIMITED = "Limited"
VIEW = "View Only"
RECOMMEND = "Recommend"
DELEGATED = "Delegated"
CONDITIONAL = "Conditional"
NOT_ALLOWED = "Not Allowed"

# Permission verbs (Document §9 — 21 verbs stored in the permission catalog).
VERBS = [
    "view", "create", "edit", "delete", "approve", "reject", "submit", "verify",
    "review", "assign", "export", "print", "download", "upload", "configure",
    "publish", "lock", "unlock", "override", "audit", "delegate",
]

# Org-scope tree levels (Document §11), broad -> narrow.
SCOPE_LEVELS = [
    "global", "university", "campus", "faculty", "department",
    "program", "section", "individual",
]
SCOPE_RANK = {name: i for i, name in enumerate(SCOPE_LEVELS)}

# Decision outcomes (Document §7 step 13).
ALLOW = "ALLOW"
DENY = "DENY"
ESCALATE = "ESCALATE"
RECOMMEND_OUT = "RECOMMEND"

# ----------------------------------------------------------------------------
# JWT-ish token (self-contained, HS256). Short-lived; carries tenant + scope.
# ----------------------------------------------------------------------------
_SECRET = os.environ.get(
    "JWT_SECRET", "icms-authority-plane-secret-key-change-in-prod").encode()


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue_token(user_id: str, tenant_id: str, office_n: int, role: str,
                scope_level: str, scope_ref: str, auth_level: str,
                ttl: int = 8 * 3600) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "sub": user_id, "tenant_id": tenant_id, "office_n": office_n,
        "role": role, "scope_level": scope_level, "scope_ref": scope_ref,
        "auth_level": auth_level, "iat": now, "exp": now + ttl,
    }
    seg = _b64e(json.dumps(header).encode()) + "." + _b64e(json.dumps(payload).encode())
    sig = hmac.new(_SECRET, seg.encode(), hashlib.sha256).digest()
    return seg + "." + _b64e(sig)


def decode_token(token: str) -> dict:
    seg, sig = token.rsplit(".", 1)
    expected = hmac.new(_SECRET, seg.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64d(sig), expected):
        raise ValueError("bad signature")
    payload = json.loads(_b64d(seg.split(".", 1)[1]))
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("expired")
    return payload


# ----------------------------------------------------------------------------
# Password hashing (Argon2-style not available offline; salted sha256 stand-in).
# ----------------------------------------------------------------------------
def pwhash(password: str, salt: str = "icms") -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


# ----------------------------------------------------------------------------
# Hash-chained audit (Document §2, §12) — append-only, tamper-evident.
# ----------------------------------------------------------------------------
def audit_hash(prev_hash: str, record: dict) -> str:
    payload = prev_hash + json.dumps(record, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


# ----------------------------------------------------------------------------
# Scope resolution (Document §7 step 6, §11).
# A role acts over a subtree; an action on a target scope is in-scope iff the
# actor's scope is an ancestor-or-equal of the target's scope level.
# ----------------------------------------------------------------------------
def scope_covers(actor_level: str, target_level: str) -> bool:
    if actor_level not in SCOPE_RANK or target_level not in SCOPE_RANK:
        return False
    # Lower rank == broader scope. Actor covers target if actor is broader-or-equal.
    return SCOPE_RANK[actor_level] <= SCOPE_RANK[target_level]


# ----------------------------------------------------------------------------
# The authorize() gate (Document §7 steps 8-13). Every mutating endpoint calls this.
# ----------------------------------------------------------------------------
class Decision:
    def __init__(self, outcome: str, reason: str, authority: str = NOT_ALLOWED,
                 escalate_to: Optional[str] = None):
        self.outcome = outcome
        self.reason = reason
        self.authority = authority
        self.escalate_to = escalate_to

    def as_dict(self):
        return {
            "outcome": self.outcome, "reason": self.reason,
            "authority": self.authority, "escalate_to": self.escalate_to,
        }


def authorize(*, ctx: dict, action: str, resource: str,
              rbac_authority: str, workflow_state: Optional[str] = None,
              workflow_valid_states: Optional[list] = None,
              amount: Optional[float] = None, approval_limit: Optional[float] = None,
              requester_id: Optional[str] = None,
<<<<<<< HEAD
              active_delegation: Optional[object] = None,
=======
              active_delegation: Optional[dict] = None,
>>>>>>> 22ee34d (updated code to branch)
              target_scope_level: str = "individual",
              escalate_to: Optional[str] = None) -> Decision:
    """
    ctx: decoded token (actor identity, role, scope, auth_level).
    rbac_authority: the RBAC/ABAC verdict for (role x action x resource) — one of
                    FULL/LIMITED/VIEW/RECOMMEND/DELEGATED/CONDITIONAL/NOT_ALLOWED.
    """
<<<<<<< HEAD
    delegation_match = _matching_delegation(active_delegation, action, resource,
                                            target_scope_level, amount)
    effective_authority = DELEGATED if delegation_match and rbac_authority in (NOT_ALLOWED, VIEW) else rbac_authority

    # 8. Permission check (RBAC + ABAC).
    if effective_authority == NOT_ALLOWED:
        return Decision(DENY, f"Role has no '{action}' permission on {resource}", NOT_ALLOWED)

    # View-only roles can never mutate unless a valid delegation upgrades them.
    mutating = action not in ("view", "export", "print", "download", "audit")
    if effective_authority == VIEW and mutating:
=======
    # 8. Permission check (RBAC + ABAC).
    if rbac_authority == NOT_ALLOWED:
        return Decision(DENY, f"Role has no '{action}' permission on {resource}", NOT_ALLOWED)

    # View-only roles can never mutate.
    mutating = action not in ("view", "export", "print", "download", "audit")
    if rbac_authority == VIEW and mutating:
>>>>>>> 22ee34d (updated code to branch)
        return Decision(DENY, "View-only authority cannot perform this action", VIEW)

    # 6/scope. Scope check — actor must cover the target scope.
    if not scope_covers(ctx.get("scope_level", "individual"), target_scope_level):
        return Decision(
            DENY,
            f"Out of scope: {ctx.get('scope_level')} cannot act on {target_scope_level}",
<<<<<<< HEAD
            effective_authority,
        )

    # 10. Delegation check — DELEGATED authority requires an active, in-date grant.
    if effective_authority == DELEGATED:
        if not delegation_match:
            return Decision(DENY, "Delegated authority required but no active grant", DELEGATED)
=======
            rbac_authority,
        )

    # 10. Delegation check — DELEGATED authority requires an active, in-date grant.
    if rbac_authority == DELEGATED:
        if not active_delegation:
            return Decision(DENY, "Delegated authority required but no active grant", DELEGATED)
        if not _delegation_valid(active_delegation, action, target_scope_level, amount):
            return Decision(DENY, "Delegation expired, revoked, or out of scope/limit", DELEGATED)
>>>>>>> 22ee34d (updated code to branch)

    # 11. Workflow-state check — action must be valid for the entity's current state.
    if workflow_valid_states is not None and workflow_state is not None:
        if workflow_state not in workflow_valid_states:
            return Decision(
                DENY,
                f"Action '{action}' invalid for workflow state '{workflow_state}'",
<<<<<<< HEAD
                effective_authority,
=======
                rbac_authority,
>>>>>>> 22ee34d (updated code to branch)
            )

    # 12. Segregation of duties — requester != approver.
    if action in ("approve", "reject", "publish") and requester_id is not None:
        if requester_id == ctx.get("sub"):
            return Decision(DENY, "Segregation of duties: requester cannot approve own request",
<<<<<<< HEAD
                            effective_authority)
=======
                            rbac_authority)
>>>>>>> 22ee34d (updated code to branch)

    # 9. Approval-limit check — amount vs configured threshold for scope.
    if action == "approve" and amount is not None:
        if approval_limit is not None and amount > approval_limit:
            return Decision(
                ESCALATE,
                f"Amount {amount:,.0f} exceeds approval limit {approval_limit:,.0f} — auto-escalated",
<<<<<<< HEAD
                effective_authority, escalate_to=escalate_to,
            )

    # RECOMMEND authority never finalizes — it recommends upward.
    if effective_authority == RECOMMEND and action in ("approve", "publish"):
=======
                rbac_authority, escalate_to=escalate_to,
            )

    # RECOMMEND authority never finalizes — it recommends upward.
    if rbac_authority == RECOMMEND and action in ("approve", "publish"):
>>>>>>> 22ee34d (updated code to branch)
        return Decision(RECOMMEND_OUT, "Recommendation recorded; final approval required upward",
                        RECOMMEND, escalate_to=escalate_to)

    # CONDITIONAL authority allows but flags for review.
<<<<<<< HEAD
    if effective_authority == CONDITIONAL:
        return Decision(ALLOW, "Allowed conditionally (per exam/scope authority)", CONDITIONAL)

    # 13. Decision.
    return Decision(ALLOW, "Authorized", effective_authority)


def _matching_delegation(active_delegation: Optional[object], action: str, resource: str,
                         target_scope_level: str, amount: Optional[float]):
    if not active_delegation:
        return None
    candidates = active_delegation if isinstance(active_delegation, list) else [active_delegation]
    for delegation in candidates:
        if _delegation_valid(delegation, action, resource, target_scope_level, amount):
            return delegation
    return None


def _delegation_valid(d: dict, action: str, resource: str, target_scope_level: str,
=======
    if rbac_authority == CONDITIONAL:
        return Decision(ALLOW, "Allowed conditionally (per exam/scope authority)", CONDITIONAL)

    # 13. Decision.
    return Decision(ALLOW, "Authorized", rbac_authority)


def _delegation_valid(d: dict, action: str, target_scope_level: str,
>>>>>>> 22ee34d (updated code to branch)
                      amount: Optional[float]) -> bool:
    if d.get("status") != "active":
        return False
    now = datetime.now(timezone.utc)
    try:
        start = datetime.fromisoformat(d["start"]).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(d["end"]).replace(tzinfo=timezone.utc)
    except Exception:
        return False
    if not (start <= now <= end):
        return False
<<<<<<< HEAD
    if not _delegation_action_matches(d.get("action") or d.get("authority") or "*", action):
        return False
    if not _delegation_resource_matches(d.get("resource_scope") or "*", resource):
=======
    if d.get("authority") and action not in ("view",) and d["authority"] not in ("*", action):
>>>>>>> 22ee34d (updated code to branch)
        return False
    if d.get("limit") is not None and amount is not None and amount > float(d["limit"]):
        return False
    return True
<<<<<<< HEAD


def _delegation_action_matches(grant_action: str, action: str) -> bool:
    allowed = {
        "*": {"approve", "review", "reject", "escalate", "execute", "view", "audit", "publish"},
        "approve": {"approve", "review", "reject", "escalate"},
        "review": {"review", "escalate"},
        "view": {"view", "audit"},
    }
    key = str(grant_action or "*").strip().lower()
    if key in allowed:
        return action in allowed[key]
    return key == action


def _delegation_resource_matches(scope_raw: str, resource: str) -> bool:
    patterns = [part.strip() for part in str(scope_raw or "*").split(",") if part.strip()]
    if not patterns:
        return True
    for pattern in patterns:
        if pattern == "*":
            return True
        if pattern.endswith("*") and resource.startswith(pattern[:-1]):
            return True
        if resource == pattern:
            return True
    return False
=======
>>>>>>> 22ee34d (updated code to branch)
