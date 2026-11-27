import datetime as dt
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.models import AppointmentStatus, ApprovalAction, ApprovalStatus, Role, VisitType


class PatientLoginRequest(BaseModel):
    mobile: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)


class DoctorLoginRequest(BaseModel):
    doctor_id: str = Field(min_length=1, max_length=16)


class StaffLoginRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class AuthResponse(BaseModel):
    token: str
    role: Role
    patient_id: str | None = None
    doctor_id: str | None = None
    display_name: str


class ActorResponse(BaseModel):
    role: Role
    patient_id: str | None = None
    doctor_id: str | None = None
    display_name: str


class DoctorOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class PatientView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    mobile: str
    year_of_birth: int | None
    general_health: str | None = None
    allergies: str | None = None


class DoctorView(BaseModel):
    id: str
    name: str
    specialities: list[str]
    opd_days: list[str] | None = None


class AggregatedSlot(BaseModel):
    doctor_id: str
    doctor_name: str
    date: dt.date
    start_time: time
    speciality: str
    visit_type: VisitType


class AggregatedAvailability(BaseModel):
    slots: list[AggregatedSlot] = Field(default_factory=list)
    message: str
    searched_doctors: int = 0
    searched_days: int = 0


class UpcomingAppointmentItem(BaseModel):
    id: str
    doctor_id: str
    doctor_name: str
    speciality: str
    visit_type: VisitType
    date: dt.date
    start_time: time
    end_time: time
    status: AppointmentStatus
    approval_request_id: str | None = None
    approval_action: ApprovalAction | None = None
    approval_status: ApprovalStatus | None = None


class AppointmentRequest(BaseModel):
    doctor_id: str = Field(min_length=1, max_length=16)
    speciality: str = Field(min_length=1, max_length=80)
    visit_type: VisitType
    date: dt.date
    start_time: time
    reason: str = Field(min_length=1, max_length=300)


class StaffAppointmentRequest(AppointmentRequest):
    patient_id: str | None = Field(default=None, min_length=1, max_length=16)
    walk_in_name: str | None = Field(default=None, min_length=1, max_length=120)
    walk_in_mobile: str | None = Field(default=None, min_length=1, max_length=20)


class CompleteAppointmentRequest(BaseModel):
    doctor_note: str = Field(min_length=1, max_length=2000)


class RescheduleRequest(BaseModel):
    doctor_id: str = Field(min_length=1, max_length=16)
    date: dt.date
    start_time: time


class StaffApprovalRequestView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    patient_name: str | None = None
    appointment_id: str
    action: ApprovalAction
    status: ApprovalStatus
    target_doctor_id: str | None = None
    target_doctor_name: str | None = None
    target_date: dt.date | None = None
    target_start_time: dt.time | None = None
    replacement_appointment_id: str | None = None
    requested_at: datetime
    decided_at: datetime | None = None
    decided_by: str | None = None


class AppointmentView(BaseModel):
    id: str
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor_name: str
    speciality: str
    visit_type: VisitType
    date: dt.date
    start_time: time
    end_time: time
    status: AppointmentStatus
    created_at: datetime
    cancelled_at: datetime | None = None
    completed_at: datetime | None = None
    reason: str | None = None
    is_urgent: bool = False
    urgent_case_id: str | None = None
    approval_request_id: str | None = None
    approval_action: ApprovalAction | None = None
    approval_status: ApprovalStatus | None = None


class ToStaffResponse(BaseModel):
    result: str = "to_staff"
    reason_code: str = "INSIDE_2_HOURS"
    message: str
    appointment: AppointmentView | None = None
    approval_request: StaffApprovalRequestView


class UrgentCaseView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str | None = None
    patient_name: str | None = None
    patient_mobile: str | None = None
    reason_text: str
    category: str
    model_why: str | None = None
    created_at: datetime
    seen: bool = False
    seen_at: datetime | None = None
    origin: str = "booking"


class FactResponse(BaseModel):
    fact: str
    caveat: str


class DoctorSummaryResponse(BaseModel):
    appointment_id: str
    patient_id: str
    summary: str
    label: str
    fallback: bool = False


class PatientHistoryItem(BaseModel):
    id: str
    date: dt.date
    doctor_id: str
    doctor_name: str
    speciality: str
    visit_type: VisitType
    reason: str | None = None
    doctor_note: str | None = None
    status: AppointmentStatus


class SlotAvailabilityView(BaseModel):
    doctor_id: str
    date: dt.date
    visit_type: VisitType
    slots: list[time]
    message: str


class SearchDebugChunk(BaseModel):
    chunk_id: str
    source: str
    section: str
    text: str
    score: float | None = None
    score_kind: str


class SearchDebugResponse(BaseModel):
    query: str
    keyword: list[SearchDebugChunk]
    vector: list[SearchDebugChunk]
    hybrid: list[SearchDebugChunk]


class ChatHistoryItem(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=128)
    message: str | None = Field(default=None, min_length=1, max_length=500)
    confirm: bool | None = None


class ChatPendingAction(BaseModel):
    action: str = Field(pattern="^(book|cancel|reschedule)$")
    summary: str
    appointment_id: str | None = None
    doctor_id: str | None = None
    doctor_name: str | None = None
    date: dt.date | None = None
    start_time: dt.time | None = None
    speciality: str | None = None
    visit_type: VisitType | None = None


class ChatSource(BaseModel):
    file: str
    section: str


class ChatResponse(BaseModel):
    kind: str
    message: str
    sources: list[ChatSource] = Field(default_factory=list)
    urgent_case_id: str | None = None
    urgent_category: str | None = None
    response_type: str = "grounded"
    pending_action: ChatPendingAction | None = None
    approval_request_id: str | None = None
