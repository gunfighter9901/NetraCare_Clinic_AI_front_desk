from datetime import date, datetime, time

from sqlalchemy.orm import Session

from app.clock import FixedClock
from app.models import Appointment, AppointmentStatus, Role, VisitType
from app.rules import ReasonCode
from app.services.appointments import cancel_appointment

NOW = FixedClock(datetime(2026, 11, 2, 10, 0))


def add_cutoff_appointment(db: Session) -> Appointment:
    appointment = Appointment(
        id="ACUT",
        patient_id="P21",
        doctor_id="D5",
        speciality="Paediatric",
        visit_type=VisitType.NEW,
        date=date(2026, 11, 2),
        start_time=time(12, 0),
        end_time=time(12, 20),
        status=AppointmentStatus.BOOKED,
        created_at=datetime(2026, 11, 1, 10, 0),
    )
    db.add(appointment)
    db.commit()
    return appointment


def test_patient_cancel_at_exact_two_hours_is_allowed(seeded_db: Session) -> None:
    add_cutoff_appointment(seeded_db)
    result = cancel_appointment(
        seeded_db,
        "ACUT",
        role=Role.PATIENT,
        actor_patient_id="P21",
        clock=NOW,
    )
    assert result.allowed
    assert result.appointment.status is AppointmentStatus.CANCELLED


def test_patient_cancel_inside_two_hours_and_staff_override(seeded_db: Session) -> None:
    patient_result = cancel_appointment(
        seeded_db,
        "A103",
        role=Role.PATIENT,
        actor_patient_id="P03",
        clock=NOW,
    )
    assert not patient_result.allowed
    assert patient_result.to_staff is True
    assert patient_result.reason_code is ReasonCode.INSIDE_2_HOURS
    assert patient_result.approval_request is not None
    assert seeded_db.get(Appointment, "A103").status is AppointmentStatus.BOOKED

    staff_result = cancel_appointment(
        seeded_db,
        "A103",
        role=Role.STAFF,
        actor_patient_id=None,
        clock=NOW,
    )
    assert staff_result.allowed
    assert staff_result.appointment.status is AppointmentStatus.CANCELLED
