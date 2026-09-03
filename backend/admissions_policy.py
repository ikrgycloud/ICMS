"""Canonical admissions lifecycle policy for Phase 1.

Only named business actions are accepted.  Later phases can add prerequisites
without exposing a generic 'set status' operation to API clients.
"""

CANONICAL_STATES = {
    "DRAFT", "SUBMITTED", "REVIEW_IN_PROGRESS", "CORRECTION_REQUIRED", "RESUBMITTED",
    "DOCUMENT_VERIFIED", "ELIGIBILITY_PENDING", "ELIGIBLE", "INELIGIBLE",
    "ASSESSMENT_PENDING", "ASSESSMENT_QUALIFIED", "COUNSELLING_PENDING",
    "COUNSELLING_COMPLETED", "ALLOCATION_PENDING", "ALLOCATED", "WAITLISTED",
    "NOT_ALLOCATED", "OFFER_RECOMMENDATION_PENDING", "OFFER_APPROVAL_PENDING",
    "OFFERED", "OFFER_ACCEPTED", "OFFER_DECLINED", "OFFER_EXPIRED",
    "FEE_RESOLUTION_PENDING", "INVOICE_ISSUED", "PAYMENT_PENDING", "PAYMENT_RECORDED",
    "ACCOUNTS_VERIFIED", "FINANCE_CLEARED", "FINAL_APPROVAL_PENDING",
    "FINAL_APPROVED", "ENROLLED", "REJECTED", "WITHDRAWN", "CANCELLED",
    "READY_TO_ADMIT",
}

ACTION_TRANSITIONS = {
    "submit": ({"DRAFT"}, "SUBMITTED"),
    "start_review": ({"SUBMITTED", "RESUBMITTED"}, "REVIEW_IN_PROGRESS"),
    "request_correction": ({"REVIEW_IN_PROGRESS"}, "CORRECTION_REQUIRED"),
    "resubmit": ({"CORRECTION_REQUIRED"}, "RESUBMITTED"),
    # Submitted is permitted for the original verify endpoint, whose legacy
    # implementation had no separate review step. New clients use start_review.
    "complete_document_verification": ({"SUBMITTED", "RESUBMITTED", "REVIEW_IN_PROGRESS"}, "DOCUMENT_VERIFIED"),
    "start_eligibility": ({"DOCUMENT_VERIFIED"}, "ELIGIBILITY_PENDING"),
    "mark_eligible": ({"ELIGIBILITY_PENDING"}, "ELIGIBLE"),
    "mark_ineligible": ({"ELIGIBILITY_PENDING"}, "INELIGIBLE"),
    # Future phases will add the supporting records for these action paths.
    "start_assessment": ({"ELIGIBLE"}, "ASSESSMENT_PENDING"),
    "qualify_assessment": ({"ASSESSMENT_PENDING"}, "ASSESSMENT_QUALIFIED"),
    "assessment_not_qualified": ({"ASSESSMENT_PENDING"}, "NOT_ALLOCATED"),
    "start_counselling": ({"ASSESSMENT_QUALIFIED", "ELIGIBLE"}, "COUNSELLING_PENDING"),
    "complete_counselling": ({"COUNSELLING_PENDING"}, "COUNSELLING_COMPLETED"),
    "start_allocation": ({"ELIGIBLE", "ASSESSMENT_QUALIFIED", "COUNSELLING_COMPLETED"}, "ALLOCATION_PENDING"),
    "allocate": ({"ALLOCATION_PENDING", "WAITLISTED"}, "ALLOCATED"),
    "waitlist": ({"ALLOCATION_PENDING"}, "WAITLISTED"),
    "not_allocate": ({"ALLOCATION_PENDING", "WAITLISTED"}, "NOT_ALLOCATED"),
    "recommend_offer": ({"ALLOCATED"}, "OFFER_RECOMMENDATION_PENDING"),
    "approve_offer": ({"OFFER_RECOMMENDATION_PENDING"}, "OFFER_APPROVAL_PENDING"),
    "issue_offer": ({"OFFER_APPROVAL_PENDING"}, "OFFERED"),
    "accept_offer": ({"OFFERED"}, "OFFER_ACCEPTED"),
    "decline_offer": ({"OFFERED"}, "OFFER_DECLINED"),
    "expire_offer": ({"OFFERED"}, "OFFER_EXPIRED"),
    "start_fee_resolution": ({"OFFER_ACCEPTED"}, "FEE_RESOLUTION_PENDING"),
    "issue_invoice": ({"FEE_RESOLUTION_PENDING"}, "INVOICE_ISSUED"),
    "await_payment": ({"INVOICE_ISSUED"}, "PAYMENT_PENDING"),
    "record_payment": ({"PAYMENT_PENDING"}, "PAYMENT_RECORDED"),
    "verify_accounts": ({"PAYMENT_RECORDED"}, "ACCOUNTS_VERIFIED"),
    "clear_finance": ({"ACCOUNTS_VERIFIED"}, "FINANCE_CLEARED"),
    "request_final_approval": ({"FINANCE_CLEARED"}, "FINAL_APPROVAL_PENDING"),
    "approve_final": ({"FINAL_APPROVAL_PENDING"}, "FINAL_APPROVED"),
    "ready_to_admit": ({"FINAL_APPROVED"}, "READY_TO_ADMIT"),
    "enroll": ({"READY_TO_ADMIT"}, "ENROLLED"),
    "reject": (CANONICAL_STATES - {"ENROLLED", "REJECTED", "WITHDRAWN", "CANCELLED"}, "REJECTED"),
    "withdraw": (CANONICAL_STATES - {"ENROLLED", "REJECTED", "WITHDRAWN", "CANCELLED"}, "WITHDRAWN"),
    "cancel": (CANONICAL_STATES - {"ENROLLED", "REJECTED", "WITHDRAWN", "CANCELLED"}, "CANCELLED"),
}

ACTION_CAPABILITIES = {
    "submit": "submit", "start_review": "start_review", "request_correction": "request_correction",
    "resubmit": "resubmit", "complete_document_verification": "complete_document_verification",
    "start_eligibility": "evaluate_eligibility", "mark_eligible": "evaluate_eligibility",
    "mark_ineligible": "evaluate_eligibility", "allocate": "allocate", "waitlist": "allocate",
    "start_assessment": "record_assessment", "qualify_assessment": "record_assessment",
    "assessment_not_qualified": "record_assessment",
    "start_counselling": "record_counselling", "complete_counselling": "record_counselling",
    "start_allocation": "allocate_seat",
    "recommend_offer": "recommend_offer", "approve_offer": "approve_offer", "issue_offer": "issue_offer",
    "expire_offer": "issue_offer",
    "accept_offer": "accept_offer", "decline_offer": "accept_offer", "withdraw": "withdraw",
    "reject": "reject", "cancel": "reject",
}

LEGACY_STATUS = {
    "DOCUMENT_VERIFIED": "verified", "OFFERED": "offered", "ENROLLED": "admitted",
    "REJECTED": "rejected", "INELIGIBLE": "rejected", "OFFER_DECLINED": "rejected",
}


def legacy_status_for(state: str) -> str:
    return LEGACY_STATUS.get(state, "submitted")
