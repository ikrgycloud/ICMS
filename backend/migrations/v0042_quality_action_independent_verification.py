"""Restore independent verification for corrective actions."""
from sqlalchemy import inspect, text

VERSION = "0042_quality_action_independent_verification"


def upgrade(engine):
    inspector = inspect(engine)
    if not inspector.has_table("corrective_actions"):
        return
    with engine.begin() as conn:
        # An owner may submit evidence but can never verify their own action.
        # Preserve the submitted evidence and return only invalid approvals to
        # the Dean's verification queue.
        conn.execute(text("UPDATE corrective_actions SET state = 'EVIDENCE_SUBMITTED', verified_by = '', verification_result = '' WHERE state = 'VERIFIED' AND owner_id <> '' AND verified_by = owner_id"))
        if inspector.has_table("academic_quality_reviews"):
            conn.execute(text("UPDATE academic_quality_reviews r SET state = 'ACTIONS_IN_PROGRESS' WHERE state <> 'CLOSED' AND EXISTS (SELECT 1 FROM corrective_actions a WHERE a.review_id = r.id AND a.state <> 'VERIFIED')"))


def downgrade(engine):
    return None
