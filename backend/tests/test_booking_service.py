from datetime import date, time

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clock import FixedClock
from app.models import Appointment, Patient, Role, VisitType
from app.rules import BookingCandidate, ReasonCode
from app.services.appointments import book_appointment

NOW = FixedClock(__import__("datetime").datetime(2026, 11, 2, 10, 0))


def candidate(
    *,
    patient_id: str = "P17",
    doctor_id: str = "D1",
    speciality: str = "Cataract",
    visit_type: VisitType = VisitType.NEW,
    day: str = "2026-11-04",
    start: str = "09:00",
) -> BookingCandidate:
    return BookingCandidate(
        patient_id=patient_id,
        doctor_id=doctor_id,
        speciality=speciality,
        visit_type=visit_type,
        date=date.fromisoformat(day),
        start_time=time.fromisoformat(start),
    )


def appointment_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Appointment)) or 0


def test_patient_books_successfully_with_stable_id(seeded_db: Session) -> None:
    result = book_appointment(
        seeded_db,
        candidate(),
        role=Role.PATIENT,
        actor_patient_id="P17",
        clock=NOW,
    )
    assert result.allowed
    assert result.appointment.id == "A113"
    assert (result.appointment.patient_id, result.appointment.end_time) == ("P17", time(9, 20))
    assert appointment_count(seeded_db) == 47


def test_patient_identity_comes_from_actor_not_request(seeded_db: Session) -> None:
    result = book_appointment(
        seeded_db,
        candidate(patient_id="P02", speciality="General"),
        role=Role.PATIENT,
        actor_patient_id="P01",
        clock=NOW,
    )
    assert result.allowed
    assert result.appointment.patient_id == "P01"


@pytest.mark.parametrize("start", ["09:00", "09:10"])
def test_identical_and_partial_overlap_are_refused_without_writes(seeded_db: Session, start: str) -> None:
    result = book_appointment(
        seeded_db,
        candidate(start=start, day="2026-11-03"),
        role=Role.PATIENT,
        actor_patient_id="P17",
        clock=NOW,
    )
    assert not result.allowed
    assert result.reason_code is ReasonCode.DOUBLE_BOOKED
    assert appointment_count(seeded_db) == 46


def test_staff_receives_no_booking_rule_bypass(seeded_db: Session) -> None:
    staff_result = book_appointment(
        seeded_db,
        candidate(patient_id="P17", start="09:05"),
        role=Role.STAFF,
        actor_patient_id=None,
        clock=NOW,
    )
    patient_result = book_appointment(
        seeded_db,
        candidate(patient_id="P17", start="09:05"),
        role=Role.PATIENT,
        actor_patient_id="P17",
        clock=NOW,
    )
    assert not staff_result.allowed and not patient_result.allowed
    assert staff_result.reason_code is patient_result.reason_code is ReasonCode.INVALID_START_TIME
    assert appointment_count(seeded_db) == 46


def test_staff_walk_in_creates_patient_and_books(seeded_db: Session) -> None:
    result = book_appointment(
        seeded_db,
        candidate(patient_id="", speciality="General"),
        role=Role.STAFF,
        actor_patient_id=None,
        clock=NOW,
        walk_in_name="Walk In",
        walk_in_mobile="9999999999",
    )
    assert result.allowed
    patient = seeded_db.scalar(select(Patient).where(Patient.mobile == "9999999999"))
    assert patient is not None
    assert patient.id == "P26"
    assert patient.year_of_birth is None
    assert result.appointment.patient_id == patient.id


def test_failed_walk_in_rolls_back_patient_creation(seeded_db: Session) -> None:
    result = book_appointment(
        seeded_db,
        candidate(patient_id="", speciality="Glaucoma", doctor_id="D4"),
        role=Role.STAFF,
        actor_patient_id=None,
        clock=NOW,
        walk_in_name="Never Created",
        walk_in_mobile="8888888888",
    )
    assert not result.allowed
    assert result.reason_code is ReasonCode.SPECIALITY_MISMATCH
    assert seeded_db.scalar(select(Patient).where(Patient.mobile == "8888888888")) is None
    assert appointment_count(seeded_db) == 46
