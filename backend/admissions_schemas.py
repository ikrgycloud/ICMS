from pydantic import BaseModel, Field


class AdmissionActionIn(BaseModel):
    action: str
    expected_status_version: int = Field(ge=0)
    reason: str = ""


class LegacyAdmissionDecisionIn(BaseModel):
    application_id: str
    action: str
    expected_status_version: int | None = Field(default=None, ge=0)


class CycleIn(BaseModel):
    name: str
    academic_year: str
    campus: str = ""
    application_open_date: str | None = None
    application_close_date: str | None = None
    status: str = "DRAFT"
    configuration: dict = {}


class CycleProgramIn(BaseModel):
    program_id: str
    campus: str = ""
    application_fee: float = 0
    admission_fee: float = 0
    intake: int = 0
    entrance_required: bool = False
    counselling_required: bool = False
    active: bool = True


class ApplicantStartIn(BaseModel):
    cycle_program_id: str
    applicant_name: str
    email: str


class ApplicantProfileIn(BaseModel):
    applicant_name: str
    email: str
    phone: str = ""
    date_of_birth: str | None = None
    gender: str = ""
    profile: dict = {}
    expected_status_version: int = Field(ge=0)


class PreferenceIn(BaseModel):
    program_id: str
    expected_status_version: int = Field(ge=0)


class PreferenceOrderIn(BaseModel):
    preference_ids: list[str]
    expected_status_version: int = Field(ge=0)


class DocumentIn(BaseModel):
    requirement_id: str | None = None
    document_type: str
    storage_key: str
    file_name: str
    mime_type: str
    checksum: str = ""
    expected_status_version: int = Field(ge=0)


class ApplicantSubmitIn(BaseModel):
    expected_status_version: int = Field(ge=0)

class EligibilityRuleIn(BaseModel):
    cycle_id: str
    program_id: str | None = None
    quota_code: str = ""
    rule_key: str
    criteria: dict
    active: bool = True

class QuotaIn(BaseModel):
    cycle_id: str
    program_id: str | None = None
    code: str
    name: str
    category_code: str = ""
    description: str = ""
    priority: int = 0
    active: bool = True

class EligibilityEvaluateIn(BaseModel):
    expected_status_version: int = Field(ge=0)

class AssessmentIn(BaseModel):
    assessment_type: str
    score: float | None = None
    max_score: float | None = None
    percentile: float | None = None
    source: str = "staff"
    expected_status_version: int = Field(ge=0)

class CounsellingSessionIn(BaseModel):
    cycle_id: str
    campus: str = ""
    scheduled_at: str | None = None
    mode: str = "offline"
    location: str = ""

class CounsellingIn(BaseModel):
    session_id: str | None = None
    attendance_status: str = "attended"
    recommended_program_id: str | None = None
    recommended_quota_id: str | None = None
    preference_rank: int | None = None
    remarks: str = ""
    expected_status_version: int = Field(ge=0)

class SeatPoolIn(BaseModel):
    cycle_id: str
    campus: str
    program_id: str
    quota_id: str | None = None
    category_code: str = ""
    intake_key: str = ""
    capacity: int = Field(ge=0)
    status: str = "open"

class AllocationIn(BaseModel):
    seat_pool_id: str
    expected_status_version: int = Field(ge=0)
    round_no: int = Field(default=1, ge=1)

class OfferActionIn(BaseModel):
    expected_status_version: int = Field(ge=0)
    expiry_days: int = Field(default=7, ge=1, le=90)


class FeeResolutionIn(BaseModel):
    expected_status_version: int = Field(ge=0)
    fee_structure_id: str | None = None
    due_date: str | None = None


class ApplicantInvoiceIn(BaseModel):
    expected_status_version: int = Field(ge=0)
    due_date: str | None = None


class ApplicantPaymentIn(BaseModel):
    expected_status_version: int = Field(ge=0)
    amount: float = Field(gt=0)
    reference: str
    method: str = "challan"
    challan_id: str | None = None


class PaymentVerificationIn(BaseModel):
    expected_status_version: int = Field(ge=0)
    status: str = "VERIFIED"
    note: str = ""


class FinalAdmissionIn(BaseModel):
    expected_status_version: int = Field(ge=0)


class ConvertApplicantIn(BaseModel):
    expected_status_version: int = Field(ge=0)
