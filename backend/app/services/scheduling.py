from dataclasses import dataclass
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import ClinicClock
from app.models import Appointment, Doctor, Holiday, ScheduleStatus, VisitType, WeeklySchedule
from app.rules import BookingCandidate, evaluate_schedule_booking, session_for_start


@dataclass(frozen=True)
class SlotAvailability:
    doctor_id: str
    date: date
    visit_type: VisitType
    slots: list[time]
    message: str


@dataclass(frozen=True)
class AggregatedSlot:
    doctor_id: str
    doctor_name: str
    date: date
    start_time: time
    speciality: str
    visit_type: VisitType


@dataclass(frozen=True)
class AggregatedAvailability:
    slots: list[AggregatedSlot]
    message: str
    searched_doctors: int = 0
    searched_days: int = 0


def find_slots(
    db: Session,
    doctor_id: str,
    appointment_date: date,
    visit_type: VisitType,
    clock: ClinicClock,
    speciality: str | None = None,
) -> SlotAvailability:
    doctor = db.get(Doctor, doctor_id)
    if doctor is None:
        raise LookupError("Doctor not found")
    if speciality is None:
        speciality = doctor.specialities[0].speciality

    doctor_appointments = list(
        db.scalars(
            select(Appointment).where(
                Appointment.doctor_id == doctor_id, Appointment.date == appointment_date
            )
        ).all()
    )
    holiday = db.get(Holiday, appointment_date)
    now = clock.now()

    slots: list[time] = []
    session_ranges = (
        (9 * 60, 13 * 60),
        (14 * 60, 18 * 60),
    )
    for session_start, session_end in session_ranges:
        for start_minutes in range(session_start, session_end - visit_type.minutes + 1, 10):
            start_time = time(start_minutes // 60, start_minutes % 60)
            session = session_for_start(start_time)
            schedule = (
                db.get(
                    WeeklySchedule,
                    (doctor_id, appointment_date.strftime("%a"), session),
                )
                if session
                else None
            )
            candidate = BookingCandidate(
                patient_id="",
                doctor_id=doctor_id,
                speciality=speciality,
                visit_type=visit_type,
                date=appointment_date,
                start_time=start_time,
            )
            if evaluate_schedule_booking(
                candidate, doctor, schedule, holiday, doctor_appointments, now
            ).allowed:
                slots.append(start_time)

    if slots:
        message = f"Free slots for {doctor.name} on {appointment_date.isoformat()}"
    elif appointment_date.weekday() == 6:
        message = "The clinic is closed on Sundays"
    elif holiday is not None:
        message = f"The clinic is closed on {appointment_date.isoformat()} for {holiday.name}"
    else:
        weekday = appointment_date.strftime("%A")
        am_schedule = db.get(WeeklySchedule, (doctor_id, appointment_date.strftime("%a"), "AM"))
        pm_schedule = db.get(WeeklySchedule, (doctor_id, appointment_date.strftime("%a"), "PM"))
        statuses = {
            schedule.status for schedule in (am_schedule, pm_schedule) if schedule is not None
        }
        if statuses == {ScheduleStatus.OFF}:
            message = f"{doctor.name} is not at the clinic on {weekday}s"
        elif statuses == {ScheduleStatus.SURGERY}:
            message = f"{doctor.name} is in surgery during this session"
        elif statuses and ScheduleStatus.OPD not in statuses:
            message = f"{doctor.name} is not available at the clinic on {weekday}s"
        else:
            message = (
                f"No free slots for {doctor.name} on {appointment_date.isoformat()} "
                "within the booking window"
            )
    return SlotAvailability(
        doctor_id=doctor_id,
        date=appointment_date,
        visit_type=visit_type,
        slots=slots,
        message=message,
    )


def _doctors_covering(db: Session, speciality: str | None, doctor_id: str | None) -> list[Doctor]:
    if doctor_id:
        doctor = db.get(Doctor, doctor_id)
        if doctor is None:
            raise LookupError("Doctor not found")
        if speciality and speciality not in {s.speciality for s in doctor.specialities}:
            return []
        return [doctor]
    doctors = list(db.scalars(select(Doctor).order_by(Doctor.id)).all())
    if speciality:
        doctors = [d for d in doctors if speciality in {s.speciality for s in d.specialities}]
    return doctors


def search_availability(
    db: Session,
    *,
    visit_type: VisitType,
    clock: ClinicClock,
    doctor_id: str | None = None,
    speciality: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    session: str | None = None,
    limit: int = 10,
) -> AggregatedAvailability:
    from datetime import timedelta

    now = clock.now()
    today = now.date()
    window_end = today + timedelta(days=30)
    start = start_date or today
    end = end_date or window_end
    if start < today:
        start = today
    if end > window_end:
        end = window_end
    if end < start:
        return AggregatedAvailability(slots=[], message="No suitable availability in the requested range", searched_doctors=0, searched_days=0)

    doctors = _doctors_covering(db, speciality, doctor_id)
    if not doctors:
        return AggregatedAvailability(slots=[], message="No doctor covers the requested speciality", searched_doctors=0, searched_days=0)

    wanted_session = (session or "").upper() or None
    if wanted_session not in (None, "AM", "PM"):
        wanted_session = None

    collected: list[AggregatedSlot] = []
    days = (end - start).days + 1
    for single in (start + timedelta(days=i) for i in range(days)):
        for doctor in doctors:
            spec = speciality or doctor.specialities[0].speciality
            try:
                avail = find_slots(db, doctor.id, single, visit_type, clock, spec)
            except LookupError:
                continue
            for slot in avail.slots:
                slot_session = session_for_start(slot)
                if wanted_session and slot_session != wanted_session:
                    continue
                collected.append(
                    AggregatedSlot(
                        doctor_id=doctor.id,
                        doctor_name=doctor.name,
                        date=single,
                        start_time=slot,
                        speciality=spec,
                        visit_type=visit_type,
                    )
                )
    collected.sort(key=lambda s: (s.date, s.start_time.hour * 60 + s.start_time.minute, s.doctor_id))
    limited = collected[: max(0, limit or 10)]
    if limited:
        message = f"Found {len(limited)} free slot(s) in the requested range"
    else:
        # Derive a helpful diagnostic from the searched window.
        message = "No suitable availability in the requested range within the 30-day booking window"
    return AggregatedAvailability(
        slots=limited, message=message, searched_doctors=len(doctors), searched_days=days
    )


def opd_days_for_doctor(db: Session, doctor_id: str) -> list[str]:
    rows = list(
        db.scalars(select(WeeklySchedule).where(WeeklySchedule.doctor_id == doctor_id)).all()
    )
    days: list[str] = []
    for row in sorted(rows, key=lambda r: (r.day, r.session)):
        if row.status is ScheduleStatus.OPD:
            days.append(f"{row.day} {row.session}")
    return days
