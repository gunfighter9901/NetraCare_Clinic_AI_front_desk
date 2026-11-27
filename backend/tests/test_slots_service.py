from datetime import date, time

from sqlalchemy.orm import Session

from app.clock import FixedClock
from app.models import Appointment, AppointmentStatus, Role, VisitType
from app.services.appointments import cancel_appointment
from app.services.scheduling import find_slots

NOW = FixedClock(__import__("datetime").datetime(2026, 11, 2, 10, 0))


def test_slots_use_ten_minute_starts_and_respect_durations(seeded_db: Session) -> None:
    availability = find_slots(
        seeded_db,
        "D3",
        date(2026, 11, 4),
        VisitType.NEW,
        NOW,
    )
    assert availability.slots
    assert all(slot.minute % 10 == 0 for slot in availability.slots)
    assert time(12, 40) in availability.slots
    assert time(12, 50) not in availability.slots
    follow_up = find_slots(
        seeded_db,
        "D3",
        date(2026, 11, 4),
        VisitType.FOLLOW_UP,
        NOW,
    )
    assert time(12, 50) in follow_up.slots


def test_surgery_session_has_no_slots(seeded_db: Session) -> None:
    availability = find_slots(
        seeded_db,
        "D1",
        date(2026, 11, 5),
        VisitType.NEW,
        NOW,
    )
    assert all(slot.hour >= 14 for slot in availability.slots)
    assert time(9, 0) not in availability.slots
    assert time(12, 40) not in availability.slots


def test_booked_overlap_disappears_and_cancelled_slot_returns(seeded_db: Session) -> None:
    availability = find_slots(
        seeded_db,
        "D1",
        date(2026, 11, 3),
        VisitType.NEW,
        NOW,
    )
    assert time(9, 0) not in availability.slots
    assert time(9, 20) not in availability.slots
    assert time(9, 40) in availability.slots
    assert time(10, 0) in availability.slots

    cancellation = cancel_appointment(
        seeded_db,
        "A101",
        role=Role.STAFF,
        actor_patient_id=None,
        clock=NOW,
    )
    assert cancellation.allowed
    refreshed = find_slots(
        seeded_db,
        "D1",
        date(2026, 11, 3),
        VisitType.NEW,
        NOW,
    )
    assert time(9, 0) in refreshed.slots
    assert seeded_db.get(Appointment, "A101").status is AppointmentStatus.CANCELLED


def test_sunday_and_holiday_have_clear_no_slot_messages(seeded_db: Session) -> None:
    sunday = find_slots(seeded_db, "D1", date(2026, 11, 8), VisitType.NEW, NOW)
    holiday = find_slots(seeded_db, "D1", date(2026, 11, 9), VisitType.NEW, NOW)
    assert sunday.slots == holiday.slots == []
    assert sunday.message == "The clinic is closed on Sundays"
    assert holiday.message == "The clinic is closed on 2026-11-09 for Clinic holiday (Diwali week)"


def test_all_surgery_and_all_off_sessions_have_specific_messages(seeded_db: Session) -> None:
    surgery = find_slots(seeded_db, "D2", date(2026, 11, 3), VisitType.NEW, NOW)
    off = find_slots(seeded_db, "D2", date(2026, 11, 5), VisitType.NEW, NOW)
    assert surgery.slots == off.slots == []
    assert surgery.message == "Dr. Meera Iyer is in surgery during this session"
    assert off.message == "Dr. Meera Iyer is not at the clinic on Thursdays"
