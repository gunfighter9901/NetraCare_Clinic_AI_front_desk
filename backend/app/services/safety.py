"""Booking safety orchestration: reason validation, red-flag check, urgent persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import ClinicClock
from app.llm import (
    EMERGENCY_MESSAGE,
    RED_FLAG_RETRY_MESSAGE,
    LLMCallFailedError,
    LLMUnavailableError,
    RedFlagResult,
    check_red_flags,
)
from app.models import Appointment, Patient, Role, UrgentCase, UrgentOrigin
from app.rules import BookingCandidate, ReasonCode
from app.services.appointments import book_appointment
from app.services.common import next_source_id


class InvalidReason(ValueError):
    pass


def validate_reason(reason: str | None) -> str:
    cleaned = (reason or "").strip()
    if not cleaned:
        raise InvalidReason("Reason is required")
    if len(cleaned) > 300:
        raise InvalidReason("Reason must be at most 300 characters")
    return cleaned


@dataclass(frozen=True)
class SafeBookingResult:
    allowed: bool
    appointment: Appointment | None = None
    red_flag: bool = False
    urgent_case: UrgentCase | None = None
    reason_code: ReasonCode | None = None
    message: str | None = None
    emergency: str | None = None
    check_failed: bool = False


def _urgent_snapshot(
    db: Session,
    role: Role,
    candidate: BookingCandidate,
    actor_patient_id: str | None,
    walk_in_name: str | None,
    walk_in_mobile: str | None,
) -> tuple[str | None, str | None, str | None]:
    if role is Role.PATIENT and actor_patient_id:
        patient = db.get(Patient, actor_patient_id)
        if patient is not None:
            return patient.id, patient.name, patient.mobile
        return actor_patient_id, None, None
    if role is Role.STAFF:
        if walk_in_mobile or walk_in_name:
            mobile = (walk_in_mobile or "").strip()
            name = " ".join((walk_in_name or "").split())
            existing = db.scalar(select(Patient).where(Patient.mobile == mobile)) if mobile else None
            if existing is not None:
                return existing.id, existing.name, existing.mobile
            return None, name or None, mobile or None
        if candidate.patient_id:
            patient = db.get(Patient, candidate.patient_id)
            if patient is not None:
                return patient.id, patient.name, patient.mobile
            return candidate.patient_id, None, None
    return None, None, None


def create_urgent_case(
    db: Session,
    *,
    patient_id: str | None,
    patient_name: str | None,
    patient_mobile: str | None,
    reason_text: str,
    category: str,
    model_why: str | None,
    now: datetime,
    origin: UrgentOrigin = UrgentOrigin.BOOKING,
) -> UrgentCase:
    urgent = UrgentCase(
        id=next_source_id(db, UrgentCase, "U", 3),
        patient_id=patient_id,
        patient_name=patient_name,
        patient_mobile=patient_mobile,
        reason_text=reason_text,
        category=category,
        model_why=model_why,
        created_at=now,
        seen=False,
        origin=origin,
    )
    db.add(urgent)
    db.commit()
    return urgent


def safe_book_appointment(
    db: Session,
    candidate: BookingCandidate,
    *,
    role: Role,
    actor_patient_id: str | None,
    clock: ClinicClock,
    reason: str | None,
    walk_in_name: str | None = None,
    walk_in_mobile: str | None = None,
    red_flag_checker=None,
) -> SafeBookingResult:
    if red_flag_checker is None:
        red_flag_checker = check_red_flags
    try:
        cleaned_reason = validate_reason(reason)
    except InvalidReason as error:
        return SafeBookingResult(
            allowed=False, reason_code=None, message=str(error), check_failed=False
        )
    try:
        red_result: RedFlagResult = red_flag_checker(cleaned_reason)
    except (LLMUnavailableError, LLMCallFailedError):
        return SafeBookingResult(
            allowed=False, message=RED_FLAG_RETRY_MESSAGE, check_failed=True
        )
    except Exception:
        return SafeBookingResult(
            allowed=False, message=RED_FLAG_RETRY_MESSAGE, check_failed=True
        )

    urgent: UrgentCase | None = None
    if red_result.red_flag:
        patient_id, patient_name, patient_mobile = _urgent_snapshot(
            db, role, candidate, actor_patient_id, walk_in_name, walk_in_mobile
        )
        urgent = create_urgent_case(
            db,
            patient_id=patient_id,
            patient_name=patient_name,
            patient_mobile=patient_mobile,
            reason_text=cleaned_reason,
            category=red_result.category,
            model_why=red_result.why,
            now=clock.now(),
        )

    result = book_appointment(
        db,
        candidate,
        role=role,
        actor_patient_id=actor_patient_id,
        clock=clock,
        walk_in_name=walk_in_name,
        walk_in_mobile=walk_in_mobile,
        reason=cleaned_reason,
        is_urgent=bool(red_result.red_flag),
        urgent_case_id=urgent.id if urgent else None,
    )
    if result.allowed:
        appointment = result.appointment
        # Link walk-in urgent case to the newly created patient.
        if urgent is not None and urgent.patient_id is None and appointment is not None:
            urgent.patient_id = appointment.patient_id
            if not urgent.patient_name:
                urgent.patient_name = appointment.patient.name
            if not urgent.patient_mobile:
                urgent.patient_mobile = appointment.patient.mobile
            db.add(urgent)
            db.commit()
            db.refresh(appointment)
        return SafeBookingResult(
            allowed=True,
            appointment=appointment,
            red_flag=True if red_result.red_flag else False,
            urgent_case=urgent,
            emergency=EMERGENCY_MESSAGE if red_result.red_flag else None,
        )
    return SafeBookingResult(
        allowed=False,
        appointment=None,
        red_flag=True if red_result.red_flag else False,
        urgent_case=urgent,
        reason_code=result.reason_code,
        message=result.message,
        emergency=EMERGENCY_MESSAGE if red_result.red_flag else None,
    )


def list_urgent_cases(db: Session, *, include_seen: bool = False):
    query = select(UrgentCase).order_by(UrgentCase.created_at.desc(), UrgentCase.id.desc())
    if not include_seen:
        query = query.where(UrgentCase.seen.is_(False))
    return list(db.scalars(query).all())


def mark_urgent_seen(db: Session, urgent_id: str, *, now: datetime) -> UrgentCase | None:
    urgent = db.get(UrgentCase, urgent_id)
    if urgent is None:
        return None
    urgent.seen = True
    urgent.seen_at = now
    db.commit()
    return urgent
