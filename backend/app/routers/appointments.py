from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.clock import ClinicClock, get_clock
from app.db import get_db
from app.dependencies import (
    require_any_role,
    require_doctor,
    require_patient,
    require_patient_or_staff,
)
from app.models import AuthSession, Role, VisitType
from app.routers.common import (
    appointment_view,
    approval_view,
    refusal_response,
    safe_booking_response,
    to_staff_response,
)
from app.rules import BookingCandidate
from app.schemas import (
    AppointmentRequest,
    AppointmentView,
    CompleteAppointmentRequest,
    RescheduleRequest,
    SlotAvailabilityView,
    StaffApprovalRequestView,
)
from app.services.appointments import (
    EntityNotFound,
    InvalidActor,
    cancel_appointment,
    complete_appointment,
    get_latest_requests_map,
    list_patient_appointments,
    reschedule_appointment,
)
from app.services.safety import safe_book_appointment
from app.services.scheduling import find_slots

router = APIRouter(tags=["appointments"])


def get_red_flag_checker():
    """Resolve the booking safety checker.

    When NETRACARE_STUB_SAFETY=1 (browser-test helper only, never production),
    return a deterministic non-urgent stub so legacy rule scripts run without
    live LLM calls. Otherwise return the live Iteration 2 chain.
    """
    import os

    if os.getenv("NETRACARE_STUB_SAFETY") == "1":
        from app.llm import RedFlagResult

        def _stub_non_urgent(_text: str) -> RedFlagResult:
            return RedFlagResult(red_flag=False, category="none", why="stubbed non-urgent")

        return _stub_non_urgent
    from app.llm import check_red_flags

    return check_red_flags


@router.get(
    "/slots",
    response_model=SlotAvailabilityView,
    summary="Find free slots",
    description="Returns 10-minute start times for a doctor, date, and visit type using the shared schedule rules.",
)
def available_slots(
    doctor_id: str,
    appointment_date: date,
    visit_type: VisitType,
    clock: ClinicClock = Depends(get_clock),
    speciality: str | None = None,
    db: Session = Depends(get_db),
    _session: AuthSession = Depends(require_any_role),
) -> SlotAvailabilityView:
    try:
        availability = find_slots(
            db,
            doctor_id,
            appointment_date,
            visit_type,
            clock,
            speciality,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return SlotAvailabilityView(
        doctor_id=availability.doctor_id,
        date=availability.date,
        visit_type=availability.visit_type,
        slots=availability.slots,
        message=availability.message,
    )


@router.post(
    "/appointments",
    summary="Book as a Patient",
    description="Books for the authenticated Patient only; refusals return a stable reason code.",
)
def create_appointment(
    payload: AppointmentRequest,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(require_patient),
    clock: ClinicClock = Depends(get_clock),
    red_flag_checker=Depends(get_red_flag_checker),
):
    candidate = BookingCandidate(
        patient_id=session.patient_id or "",
        doctor_id=payload.doctor_id,
        speciality=payload.speciality,
        visit_type=payload.visit_type,
        date=payload.date,
        start_time=payload.start_time,
    )
    try:
        result = safe_book_appointment(
            db,
            candidate,
            role=session.role,
            actor_patient_id=session.patient_id,
            clock=clock,
            reason=payload.reason,
            red_flag_checker=red_flag_checker,
        )
    except EntityNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except InvalidActor as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return safe_booking_response(result)


@router.get(
    "/appointments",
    response_model=list[AppointmentView],
    summary="List the Patient's appointments",
    description="Returns only appointments owned by the authenticated Patient.",
)
def my_appointments(
    db: Session = Depends(get_db),
    session: AuthSession = Depends(require_patient),
) -> list[AppointmentView]:
    appointments = list_patient_appointments(db, session.patient_id or "")
    latest = get_latest_requests_map(db, [a.id for a in appointments])
    return [appointment_view(appointment, approval=latest.get(appointment.id)) for appointment in appointments]


@router.post(
    "/appointments/{appointment_id}/cancel",
    summary="Cancel an appointment",
    description="Patient cancellation inside two hours creates a Staff approval request (HTTP 202 to_staff). Staff cancels directly.",
)
def cancel(
    appointment_id: str,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(require_patient_or_staff),
    clock: ClinicClock = Depends(get_clock),
):
    try:
        result = cancel_appointment(
            db,
            appointment_id,
            role=session.role,
            actor_patient_id=session.patient_id if session.role is Role.PATIENT else None,
            clock=clock,
        )
    except EntityNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if result.to_staff and result.approval_request is not None and result.appointment is not None:
        return to_staff_response(result.appointment, result.approval_request)
    if not result.allowed:
        return refusal_response(result)
    assert result.appointment is not None
    return appointment_view(result.appointment)


@router.post(
    "/appointments/{appointment_id}/reschedule",
    summary="Reschedule an appointment",
    description="Atomic cancel plus new booking. Late Patient requests create a Staff approval (HTTP 202 to_staff).",
)
def reschedule(
    appointment_id: str,
    payload: RescheduleRequest,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(require_patient_or_staff),
    clock: ClinicClock = Depends(get_clock),
):
    try:
        result = reschedule_appointment(
            db,
            appointment_id,
            role=session.role,
            actor_patient_id=session.patient_id if session.role is Role.PATIENT else None,
            clock=clock,
            target_doctor_id=payload.doctor_id,
            target_date=payload.date,
            target_start_time=payload.start_time,
        )
    except EntityNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except InvalidActor as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    if result.to_staff and result.approval_request is not None and result.original is not None:
        return to_staff_response(result.original, result.approval_request)
    if not result.allowed:
        return refusal_response(result)
    assert result.appointment is not None
    return appointment_view(result.appointment)


@router.post(
    "/appointments/{appointment_id}/complete",
    summary="Complete a visit",
    description="Marks one of the authenticated Doctor's booked appointments completed. A short note is required.",
)
def complete(
    appointment_id: str,
    payload: CompleteAppointmentRequest,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(require_doctor),
    clock: ClinicClock = Depends(get_clock),
):
    try:
        appointment = complete_appointment(
            db,
            appointment_id,
            doctor_id=session.doctor_id or "",
            clock=clock,
            doctor_note=payload.doctor_note,
        )
    except EntityNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except InvalidActor as error:
        msg = str(error)
        if "own appointments" in msg:
            status_code = 403
        elif "note" in msg.lower():
            status_code = 400
        else:
            status_code = 409
        raise HTTPException(status_code=status_code, detail=msg) from error
    return appointment_view(appointment)
