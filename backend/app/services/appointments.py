from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import ClinicClock
from app.models import (
    Appointment,
    AppointmentStatus,
    ApprovalAction,
    ApprovalStatus,
    Doctor,
    Holiday,
    Patient,
    Role,
    StaffApprovalRequest,
    VisitType,
    WeeklySchedule,
)
from app.rules import (
    BookingCandidate,
    ReasonCode,
    RuleDecision,
    evaluate_booking,
    evaluate_cancellation,
    session_for_start,
)
from app.services.common import next_source_id


class EntityNotFound(LookupError):
    pass


class InvalidActor(ValueError):
    pass


@dataclass(frozen=True)
class BookingResult:
    allowed: bool
    appointment: Appointment | None = None
    reason_code: ReasonCode | None = None
    message: str | None = None

    @classmethod
    def success(cls, appointment: Appointment) -> BookingResult:
        return cls(allowed=True, appointment=appointment)

    @classmethod
    def refusal(cls, decision: RuleDecision) -> BookingResult:
        return cls(
            allowed=False,
            reason_code=decision.reason_code,
            message=decision.message,
        )


@dataclass(frozen=True)
class CancellationResult:
    allowed: bool
    appointment: Appointment | None = None
    reason_code: ReasonCode | None = None
    message: str | None = None
    to_staff: bool = False
    approval_request: StaffApprovalRequest | None = None

    @classmethod
    def success(cls, appointment: Appointment) -> CancellationResult:
        return cls(allowed=True, appointment=appointment)

    @classmethod
    def refusal(cls, decision: RuleDecision) -> CancellationResult:
        return cls(allowed=False, reason_code=decision.reason_code, message=decision.message)

    @classmethod
    def to_staff_result(
        cls, appointment: Appointment, request: StaffApprovalRequest
    ) -> CancellationResult:
        return cls(
            allowed=False,
            appointment=appointment,
            reason_code=ReasonCode.INSIDE_2_HOURS,
            message="Sent to Staff for approval. The appointment remains booked.",
            to_staff=True,
            approval_request=request,
        )


@dataclass(frozen=True)
class RescheduleResult:
    allowed: bool
    appointment: Appointment | None = None  # replacement when executed
    original: Appointment | None = None
    reason_code: ReasonCode | None = None
    message: str | None = None
    to_staff: bool = False
    approval_request: StaffApprovalRequest | None = None

    @classmethod
    def success(cls, original: Appointment, replacement: Appointment) -> RescheduleResult:
        return cls(allowed=True, appointment=replacement, original=original)

    @classmethod
    def refusal(cls, decision: RuleDecision, original: Appointment | None = None) -> RescheduleResult:
        return cls(
            allowed=False,
            original=original,
            reason_code=decision.reason_code,
            message=decision.message,
        )

    @classmethod
    def to_staff_result(
        cls, original: Appointment, request: StaffApprovalRequest
    ) -> RescheduleResult:
        return cls(
            allowed=False,
            original=original,
            reason_code=ReasonCode.INSIDE_2_HOURS,
            message="Sent to Staff for approval. The appointment remains booked.",
            to_staff=True,
            approval_request=request,
        )


class _RuleRefused(Exception):
    def __init__(self, decision: RuleDecision) -> None:
        self.decision = decision


def _resolve_patient(
    db: Session,
    candidate: BookingCandidate,
    role: Role,
    actor_patient_id: str | None,
    walk_in_name: str | None,
    walk_in_mobile: str | None,
) -> Patient:
    if role is Role.PATIENT:
        if not actor_patient_id:
            raise InvalidActor("Patient actor has no patient identity")
        patient = db.get(Patient, actor_patient_id)
        if patient is None:
            raise EntityNotFound("Patient not found")
        return patient

    if role is Role.STAFF:
        if walk_in_mobile or walk_in_name:
            mobile = (walk_in_mobile or "").strip()
            name = " ".join((walk_in_name or "").split())
            if not mobile or not name:
                raise InvalidActor("Walk-in mobile and name are required")
            existing = db.scalar(select(Patient).where(Patient.mobile == mobile))
            if existing is not None:
                if existing.name.casefold() != name.casefold():
                    raise InvalidActor("Mobile number already belongs to another patient")
                return existing
            patient = Patient(
                id=next_source_id(db, Patient, "P", 2),
                mobile=mobile,
                name=name,
                year_of_birth=None,
            )
            db.add(patient)
            db.flush()
            return patient
        if not candidate.patient_id:
            raise InvalidActor("Staff booking requires a patient")
        patient = db.get(Patient, candidate.patient_id)
        if patient is None:
            raise EntityNotFound("Patient not found")
        return patient

    raise InvalidActor("Only Patient and Staff can book appointments")


def _load_booking_context(
    db: Session, candidate: BookingCandidate
) -> tuple[Doctor, WeeklySchedule | None, Holiday | None, list[Appointment], list[Appointment]]:
    doctor = db.get(Doctor, candidate.doctor_id)
    if doctor is None:
        raise EntityNotFound("Doctor not found")
    session = session_for_start(candidate.start_time)
    schedule = (
        db.get(WeeklySchedule, (candidate.doctor_id, candidate.date.strftime("%a"), session))
        if session
        else None
    )
    holiday = db.get(Holiday, candidate.date)
    doctor_appointments = list(
        db.scalars(
            select(Appointment).where(
                Appointment.doctor_id == candidate.doctor_id,
                Appointment.date == candidate.date,
            )
        ).all()
    )
    patient_appointments = list(
        db.scalars(
            select(Appointment).where(Appointment.patient_id == candidate.patient_id)
        ).all()
    )
    return doctor, schedule, holiday, doctor_appointments, patient_appointments


def _get_pending_request(db: Session, appointment_id: str) -> StaffApprovalRequest | None:
    return db.scalar(
        select(StaffApprovalRequest).where(
            StaffApprovalRequest.appointment_id == appointment_id,
            StaffApprovalRequest.status == ApprovalStatus.PENDING,
        )
    )


def _create_pending_request_no_commit(
    db: Session,
    *,
    patient_id: str,
    appointment_id: str,
    action: ApprovalAction,
    clock: ClinicClock,
    target_doctor_id: str | None = None,
    target_date: date | None = None,
    target_start_time=None,
) -> StaffApprovalRequest:
    request = StaffApprovalRequest(
        id=next_source_id(db, StaffApprovalRequest, "SR", 3),
        patient_id=patient_id,
        appointment_id=appointment_id,
        action=action,
        status=ApprovalStatus.PENDING,
        target_doctor_id=target_doctor_id,
        target_date=target_date,
        target_start_time=target_start_time,
        requested_at=clock.now(),
    )
    db.add(request)
    db.flush()
    return request


def _apply_cancel_no_commit(appointment: Appointment, clock: ClinicClock) -> None:
    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancelled_at = clock.now()


def _build_replacement_no_commit(
    db: Session,
    original: Appointment,
    doctor_id: str,
    target_date: date,
    target_start_time,
    clock: ClinicClock,
) -> Appointment:
    from datetime import time as dtime

    start = target_start_time
    # Compute end from original visit type duration.
    minutes = original.visit_type.minutes if isinstance(original.visit_type, VisitType) else 20
    # original.visit_type may be enum already.
    try:
        visit = original.visit_type if isinstance(original.visit_type, VisitType) else VisitType(original.visit_type)
    except Exception:
        visit = VisitType.NEW
    end_minutes = start.hour * 60 + start.minute + visit.minutes
    end = dtime(end_minutes // 60, end_minutes % 60)
    replacement = Appointment(
        id=next_source_id(db, Appointment, "A", 3),
        patient_id=original.patient_id,
        doctor_id=doctor_id,
        speciality=original.speciality,
        visit_type=visit,
        date=target_date,
        start_time=start,
        end_time=end,
        status=AppointmentStatus.BOOKED,
        created_at=clock.now(),
        reason=original.reason,
        is_urgent=bool(original.is_urgent),
        urgent_case_id=original.urgent_case_id,
    )
    db.add(replacement)
    db.flush()
    return replacement


def _evaluate_reschedule_target(
    db: Session,
    original: Appointment,
    target_doctor_id: str,
    target_date: date,
    target_start_time,
    now: datetime,
) -> RuleDecision:
    candidate = BookingCandidate(
        patient_id=original.patient_id,
        doctor_id=target_doctor_id,
        speciality=original.speciality,
        visit_type=original.visit_type if isinstance(original.visit_type, VisitType) else VisitType(original.visit_type),
        date=target_date,
        start_time=target_start_time,
    )
    doctor, schedule, holiday, doctor_appointments, patient_appointments = _load_booking_context(
        db, candidate
    )
    # Exclude the original from overlap + active-speciality checks.
    doctor_appointments = [a for a in doctor_appointments if a.id != original.id]
    patient_appointments = [a for a in patient_appointments if a.id != original.id]
    return evaluate_booking(
        candidate, doctor, schedule, holiday, doctor_appointments, patient_appointments, now
    )


def book_appointment(
    db: Session,
    candidate: BookingCandidate,
    *,
    role: Role,
    actor_patient_id: str | None,
    clock: ClinicClock,
    walk_in_name: str | None = None,
    walk_in_mobile: str | None = None,
    reason: str | None = None,
    is_urgent: bool = False,
    urgent_case_id: str | None = None,
) -> BookingResult:
    try:
        patient = _resolve_patient(db, candidate, role, actor_patient_id, walk_in_name, walk_in_mobile)
        candidate = replace(candidate, patient_id=patient.id)
        doctor, schedule, holiday, doctor_appointments, patient_appointments = _load_booking_context(
            db, candidate
        )
        decision = evaluate_booking(
            candidate,
            doctor,
            schedule,
            holiday,
            doctor_appointments,
            patient_appointments,
            clock.now(),
        )
        if not decision.allowed:
            raise _RuleRefused(decision)
        appointment = Appointment(
            id=next_source_id(db, Appointment, "A", 3),
            patient_id=patient.id,
            doctor_id=doctor.id,
            speciality=candidate.speciality,
            visit_type=candidate.visit_type,
            date=candidate.date,
            start_time=candidate.start_time,
            end_time=candidate.end_time,
            status=AppointmentStatus.BOOKED,
            created_at=clock.now(),
            reason=reason,
            is_urgent=is_urgent,
            urgent_case_id=urgent_case_id,
        )
        db.add(appointment)
        db.commit()
        return BookingResult.success(appointment)
    except _RuleRefused as refused:
        db.rollback()
        return BookingResult.refusal(refused.decision)
    except Exception:
        db.rollback()
        raise


def cancel_appointment(
    db: Session,
    appointment_id: str,
    *,
    role: Role,
    actor_patient_id: str | None,
    clock: ClinicClock,
) -> CancellationResult:
    if role not in (Role.PATIENT, Role.STAFF):
        raise InvalidActor("Only Patient and Staff can cancel appointments")
    try:
        appointment = db.get(Appointment, appointment_id)
        if appointment is None:
            raise EntityNotFound("Appointment not found")
        decision = evaluate_cancellation(appointment, role, actor_patient_id, clock.now())
        if not decision.allowed:
            if (
                role is Role.PATIENT
                and decision.reason_code is ReasonCode.INSIDE_2_HOURS
                and appointment.status is AppointmentStatus.BOOKED
            ):
                existing = _get_pending_request(db, appointment.id)
                if existing is not None:
                    db.commit()
                    return CancellationResult.to_staff_result(appointment, existing)
                pending = _create_pending_request_no_commit(
                    db,
                    patient_id=appointment.patient_id,
                    appointment_id=appointment.id,
                    action=ApprovalAction.CANCEL,
                    clock=clock,
                )
                db.commit()
                db.refresh(appointment)
                db.refresh(pending)
                return CancellationResult.to_staff_result(appointment, pending)
            raise _RuleRefused(decision)
        _apply_cancel_no_commit(appointment, clock)
        db.commit()
        return CancellationResult.success(appointment)
    except _RuleRefused as refused:
        db.rollback()
        return CancellationResult.refusal(refused.decision)
    except Exception:
        db.rollback()
        raise


def reschedule_appointment(
    db: Session,
    appointment_id: str,
    *,
    role: Role,
    actor_patient_id: str | None,
    clock: ClinicClock,
    target_doctor_id: str,
    target_date: date,
    target_start_time,
) -> RescheduleResult:
    if role not in (Role.PATIENT, Role.STAFF):
        raise InvalidActor("Only Patient and Staff can reschedule appointments")
    try:
        original = db.get(Appointment, appointment_id)
        if original is None:
            raise EntityNotFound("Appointment not found")
        # Ownership check first (do not leak target details).
        if role is Role.PATIENT and original.patient_id != actor_patient_id:
            return RescheduleResult.refusal(
                RuleDecision.refuse(
                    ReasonCode.NOT_YOUR_APPOINTMENT,
                    "You cannot cancel another patient's appointment",
                ),
                original=None,
            )
        if original.status is not AppointmentStatus.BOOKED:
            return RescheduleResult.refusal(
                RuleDecision.refuse(ReasonCode.NOT_ACTIVE, "Only a booked appointment can be rescheduled"),
                original=original,
            )
        now = clock.now()
        if datetime.combine(original.date, original.start_time) < now:
            return RescheduleResult.refusal(
                RuleDecision.refuse(ReasonCode.NOT_ACTIVE, "Only a booked appointment can be rescheduled"),
                original=original,
            )
        target_decision = _evaluate_reschedule_target(
            db, original, target_doctor_id, target_date, target_start_time, now
        )
        if not target_decision.allowed:
            db.rollback()
            return RescheduleResult.refusal(target_decision, original=original)
        starts_at = datetime.combine(original.date, original.start_time)
        is_late = role is Role.PATIENT and starts_at - now < timedelta(hours=2)
        if is_late:
            existing = _get_pending_request(db, original.id)
            if existing is not None:
                db.commit()
                return RescheduleResult.to_staff_result(original, existing)
            pending = _create_pending_request_no_commit(
                db,
                patient_id=original.patient_id,
                appointment_id=original.id,
                action=ApprovalAction.RESCHEDULE,
                clock=clock,
                target_doctor_id=target_doctor_id,
                target_date=target_date,
                target_start_time=target_start_time,
            )
            db.commit()
            db.refresh(original)
            db.refresh(pending)
            return RescheduleResult.to_staff_result(original, pending)
        # Immediate atomic reschedule.
        _apply_cancel_no_commit(original, clock)
        replacement = _build_replacement_no_commit(
            db, original, target_doctor_id, target_date, target_start_time, clock
        )
        db.commit()
        db.refresh(original)
        db.refresh(replacement)
        return RescheduleResult.success(original, replacement)
    except (EntityNotFound, InvalidActor):
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def list_patient_appointments(db: Session, patient_id: str) -> list[Appointment]:
    return list(
        db.scalars(
            select(Appointment)
            .where(Appointment.patient_id == patient_id)
            .order_by(Appointment.date.desc(), Appointment.start_time.desc())
        ).all()
    )


def list_staff_appointments(
    db: Session, appointment_date: date | None = None, doctor_id: str | None = None
) -> list[Appointment]:
    query = select(Appointment).order_by(Appointment.date, Appointment.start_time, Appointment.id)
    if appointment_date is not None:
        query = query.where(Appointment.date == appointment_date)
    if doctor_id is not None:
        query = query.where(Appointment.doctor_id == doctor_id)
    return list(db.scalars(query).all())


def complete_appointment(
    db: Session,
    appointment_id: str,
    *,
    doctor_id: str,
    clock: ClinicClock,
    doctor_note: str | None = None,
) -> Appointment:
    note = (doctor_note or "").strip()
    if not note:
        raise InvalidActor("Doctor note is required")
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise EntityNotFound("Appointment not found")
    if appointment.doctor_id != doctor_id:
        raise InvalidActor("You can only complete your own appointments")
    if appointment.status is not AppointmentStatus.BOOKED:
        raise InvalidActor("Only a booked appointment can be completed")
    appointment.status = AppointmentStatus.COMPLETED
    appointment.completed_at = clock.now()
    appointment.doctor_note = note
    db.commit()
    return appointment


def list_patient_completed_history(db: Session, patient_id: str) -> list[Appointment]:
    return list(
        db.scalars(
            select(Appointment)
            .where(Appointment.patient_id == patient_id, Appointment.status == AppointmentStatus.COMPLETED)
            .order_by(Appointment.date.desc(), Appointment.start_time.desc(), Appointment.id.desc())
        ).all()
    )


def list_doctor_appointments(db: Session, doctor_id: str, appointment_date: date) -> list[Appointment]:
    return list(
        db.scalars(
            select(Appointment)
            .where(Appointment.doctor_id == doctor_id, Appointment.date == appointment_date)
            .order_by(Appointment.start_time, Appointment.id)
        ).all()
    )


def get_latest_approval_request(
    db: Session, appointment_id: str
) -> StaffApprovalRequest | None:
    return db.scalar(
        select(StaffApprovalRequest)
        .where(StaffApprovalRequest.appointment_id == appointment_id)
        .order_by(StaffApprovalRequest.requested_at.desc(), StaffApprovalRequest.id.desc())
    )


def get_latest_requests_map(
    db: Session, appointment_ids: list[str]
) -> dict[str, StaffApprovalRequest]:
    if not appointment_ids:
        return {}
    rows = list(
        db.scalars(
            select(StaffApprovalRequest)
            .where(StaffApprovalRequest.appointment_id.in_(appointment_ids))
            .order_by(StaffApprovalRequest.requested_at.desc(), StaffApprovalRequest.id.desc())
        ).all()
    )
    out: dict[str, StaffApprovalRequest] = {}
    for row in rows:
        if row.appointment_id not in out:
            out[row.appointment_id] = row
    return out


def list_upcoming_patient_items(db: Session, patient_id: str, clock: ClinicClock) -> list[dict]:
    from datetime import datetime as _dt

    now = clock.now()
    rows = list(
        db.scalars(
            select(Appointment)
            .where(Appointment.patient_id == patient_id, Appointment.status == AppointmentStatus.BOOKED)
            .order_by(Appointment.date, Appointment.start_time, Appointment.id)
        ).all()
    )
    upcoming = [a for a in rows if _dt.combine(a.date, a.start_time) >= now]
    latest = get_latest_requests_map(db, [a.id for a in upcoming])
    items: list[dict] = []
    for appt in upcoming:
        req = latest.get(appt.id)
        items.append(
            {
                "id": appt.id,
                "doctor_id": appt.doctor_id,
                "doctor_name": appt.doctor.name if appt.doctor else appt.doctor_id,
                "speciality": appt.speciality,
                "visit_type": appt.visit_type.value if isinstance(appt.visit_type, VisitType) else str(appt.visit_type),
                "date": appt.date.isoformat(),
                "start_time": appt.start_time.strftime("%H:%M:%S"),
                "end_time": appt.end_time.strftime("%H:%M:%S"),
                "status": appt.status.value if isinstance(appt.status, AppointmentStatus) else str(appt.status),
                "approval_request_id": req.id if req else None,
                "approval_action": req.action.value if req else None,
                "approval_status": req.status.value if req else None,
            }
        )
    return items


def list_doctors_with_opd(db: Session) -> list[dict]:
    from app.services.scheduling import opd_days_for_doctor

    doctors = list(db.scalars(select(Doctor).order_by(Doctor.id)).all())
    out: list[dict] = []
    for doctor in doctors:
        out.append(
            {
                "id": doctor.id,
                "name": doctor.name,
                "specialities": sorted([s.speciality for s in doctor.specialities]),
                "opd_days": opd_days_for_doctor(db, doctor.id),
            }
        )
    return out
