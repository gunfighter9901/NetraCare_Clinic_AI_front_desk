from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum

from app.models import (
    Appointment,
    AppointmentStatus,
    Doctor,
    Holiday,
    Role,
    ScheduleStatus,
    VisitType,
    WeeklySchedule,
)


class ReasonCode(str, Enum):
    INVALID_START_TIME = "INVALID_START_TIME"
    IN_PAST = "IN_PAST"
    BEYOND_30_DAYS = "BEYOND_30_DAYS"
    CLINIC_CLOSED = "CLINIC_CLOSED"
    HOLIDAY = "HOLIDAY"
    OUTSIDE_SESSION = "OUTSIDE_SESSION"
    ENDS_AFTER_SESSION = "ENDS_AFTER_SESSION"
    DOCTOR_OFF = "DOCTOR_OFF"
    SURGERY_SESSION = "SURGERY_SESSION"
    SPECIALITY_MISMATCH = "SPECIALITY_MISMATCH"
    DOUBLE_BOOKED = "DOUBLE_BOOKED"
    ACTIVE_BOOKING_EXISTS = "ACTIVE_BOOKING_EXISTS"
    NO_PREVIOUS_VISIT = "NO_PREVIOUS_VISIT"
    FOLLOW_UP_DIFFERENT_DOCTOR = "FOLLOW_UP_DIFFERENT_DOCTOR"
    INSIDE_2_HOURS = "INSIDE_2_HOURS"
    NOT_YOUR_APPOINTMENT = "NOT_YOUR_APPOINTMENT"
    NOT_ACTIVE = "NOT_ACTIVE"


@dataclass(frozen=True)
class RuleDecision:
    allowed: bool
    reason_code: ReasonCode | None = None
    message: str | None = None

    @classmethod
    def allow(cls) -> RuleDecision:
        return cls(allowed=True)

    @classmethod
    def refuse(cls, code: ReasonCode, message: str) -> RuleDecision:
        return cls(allowed=False, reason_code=code, message=message)


@dataclass(frozen=True)
class BookingCandidate:
    patient_id: str
    doctor_id: str
    speciality: str
    visit_type: VisitType
    date: date
    start_time: time

    @property
    def start_minutes(self) -> int:
        return self.start_time.hour * 60 + self.start_time.minute

    @property
    def end_minutes(self) -> int:
        return self.start_minutes + self.visit_type.minutes

    @property
    def end_time(self) -> time:
        return time(self.end_minutes // 60, self.end_minutes % 60)

    @property
    def starts_at(self) -> datetime:
        return datetime.combine(self.date, self.start_time)


def minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def session_for_start(start_time: time) -> str | None:
    start = minutes(start_time)
    if 9 * 60 <= start < 13 * 60:
        return "AM"
    if 14 * 60 <= start < 18 * 60:
        return "PM"
    return None


def intervals_overlap(
    first_start: time, first_end: time, second_start: time, second_end: time
) -> bool:
    return minutes(first_start) < minutes(second_end) and minutes(second_start) < minutes(first_end)


def evaluate_schedule_booking(
    candidate: BookingCandidate,
    doctor: Doctor,
    schedule: WeeklySchedule | None,
    holiday: Holiday | None,
    doctor_appointments: list[Appointment],
    now: datetime,
) -> RuleDecision:
    if candidate.start_time.minute % 10 or candidate.start_time.second or candidate.start_time.microsecond:
        return RuleDecision.refuse(
            ReasonCode.INVALID_START_TIME, "Start time must be on a 10-minute mark"
        )
    if candidate.starts_at < now:
        return RuleDecision.refuse(ReasonCode.IN_PAST, "Appointment cannot be booked in the past")
    if candidate.date > now.date() + timedelta(days=30):
        return RuleDecision.refuse(
            ReasonCode.BEYOND_30_DAYS, "Appointments can only be booked up to 30 days ahead"
        )
    if candidate.date.weekday() == 6:
        return RuleDecision.refuse(ReasonCode.CLINIC_CLOSED, "The clinic is closed on Sundays")
    if holiday is not None:
        return RuleDecision.refuse(
            ReasonCode.HOLIDAY, f"The clinic is closed on {holiday.date} for {holiday.name}"
        )

    session = session_for_start(candidate.start_time)
    if session is None:
        return RuleDecision.refuse(
            ReasonCode.OUTSIDE_SESSION,
            "Appointments must start between 9 AM and 1 PM or 2 PM and 6 PM",
        )
    session_end = 13 * 60 if session == "AM" else 18 * 60
    if candidate.end_minutes > session_end:
        return RuleDecision.refuse(
            ReasonCode.ENDS_AFTER_SESSION, "The appointment would end after the clinic session"
        )
    if schedule is None or schedule.status is ScheduleStatus.OFF:
        return RuleDecision.refuse(
            ReasonCode.DOCTOR_OFF,
            f"{doctor.name} is not at the clinic on {candidate.date.strftime('%A')}s",
        )
    if schedule.status is ScheduleStatus.SURGERY:
        return RuleDecision.refuse(
            ReasonCode.SURGERY_SESSION, f"{doctor.name} is in surgery during this session"
        )
    if candidate.speciality not in {item.speciality for item in doctor.specialities}:
        return RuleDecision.refuse(
            ReasonCode.SPECIALITY_MISMATCH, f"{doctor.name} does not cover {candidate.speciality}"
        )

    for existing in doctor_appointments:
        if (
            existing.status is AppointmentStatus.BOOKED
            and existing.date == candidate.date
            and intervals_overlap(
                candidate.start_time, candidate.end_time, existing.start_time, existing.end_time
            )
        ):
            return RuleDecision.refuse(
                ReasonCode.DOUBLE_BOOKED,
                f"{doctor.name} already has an appointment overlapping that time",
            )
    return RuleDecision.allow()


def evaluate_booking(
    candidate: BookingCandidate,
    doctor: Doctor,
    schedule: WeeklySchedule | None,
    holiday: Holiday | None,
    doctor_appointments: list[Appointment],
    patient_appointments: list[Appointment],
    now: datetime,
) -> RuleDecision:
    schedule_decision = evaluate_schedule_booking(
        candidate, doctor, schedule, holiday, doctor_appointments, now
    )
    if not schedule_decision.allowed:
        return schedule_decision

    if any(
        item.status is AppointmentStatus.BOOKED and item.speciality == candidate.speciality
        for item in patient_appointments
    ):
        return RuleDecision.refuse(
            ReasonCode.ACTIVE_BOOKING_EXISTS,
            f"Patient already has an active {candidate.speciality} appointment",
        )

    if candidate.visit_type is VisitType.FOLLOW_UP:
        completed = [
            item
            for item in patient_appointments
            if item.status is AppointmentStatus.COMPLETED
            and item.speciality == candidate.speciality
        ]
        if not completed:
            return RuleDecision.refuse(
                ReasonCode.NO_PREVIOUS_VISIT,
                "A follow-up requires a completed visit in this speciality",
            )
        latest = max(completed, key=lambda item: (item.date, item.start_time, item.id))
        if latest.doctor_id != candidate.doctor_id:
            doctor_name = latest.doctor.name if latest.doctor else latest.doctor_id
            return RuleDecision.refuse(
                ReasonCode.FOLLOW_UP_DIFFERENT_DOCTOR,
                f"Follow-up must be with {doctor_name}, who completed the last {candidate.speciality} visit",
            )

    return RuleDecision.allow()


def evaluate_cancellation(
    appointment: Appointment,
    actor_role: Role,
    actor_patient_id: str | None,
    now: datetime,
) -> RuleDecision:
    if actor_role is Role.PATIENT and appointment.patient_id != actor_patient_id:
        return RuleDecision.refuse(
            ReasonCode.NOT_YOUR_APPOINTMENT, "You cannot cancel another patient's appointment"
        )
    if appointment.status is not AppointmentStatus.BOOKED:
        return RuleDecision.refuse(
            ReasonCode.NOT_ACTIVE, "Only a booked appointment can be cancelled"
        )
    starts_at = datetime.combine(appointment.date, appointment.start_time)
    if actor_role is Role.PATIENT and starts_at - now < timedelta(hours=2):
        return RuleDecision.refuse(ReasonCode.INSIDE_2_HOURS, "Please contact Staff")
    return RuleDecision.allow()
