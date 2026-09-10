"""Permit Dean decisions on returned-and-resubmitted allocation proposals."""
import json

from sqlalchemy import text

VERSION = "0039_allocation_resubmission_policy"


def upgrade(engine):
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT allowed_transitions_json
            FROM governance_policies
            WHERE proposal_type = 'allocation'
        """)).first()
        if not row:
            return
        transitions = json.loads(row[0] or "{}")
        resubmitted = set(transitions.get("RESUBMITTED", []))
        resubmitted.update(["UNDER_REVIEW", "APPROVED", "REJECTED", "ESCALATED"])
        transitions["RESUBMITTED"] = sorted(resubmitted)
        returned = set(transitions.get("RETURNED", []))
        returned.add("RESUBMITTED")
        transitions["RETURNED"] = sorted(returned)
        conn.execute(text("""
            UPDATE governance_policies
            SET allowed_transitions_json = :transitions,
                updated_at = CURRENT_TIMESTAMP
            WHERE proposal_type = 'allocation'
        """), {"transitions": json.dumps(transitions)})


def downgrade(engine):
    return None
