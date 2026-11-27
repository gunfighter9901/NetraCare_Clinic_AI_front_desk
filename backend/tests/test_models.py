from datetime import date, datetime, time

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Appointment,
    AppointmentStatus,
    Doctor,
    DoctorSpeciality,
    Patient,
    Role,
    ScheduleStatus,
    VisitType,
    WeeklySchedule,
)


def add_patient(db: Session, patient_id: str = "PX1", mobile: str = "9111111111") -> Patient:
    patient = Patient(id=patient_id, name="Test Patient", mobile=mobile, year_of_birth=None)
    db.add(patient)
    return patient


def test_schema_relationships_nullable_birth_year_and_appointment_statuses(db: Session) -> None:
    doctor = Doctor(id="DX1", name="Dr. Test")
    doctor.specialities.append(DoctorSpeciality(speciality="General"))
    doctor.schedules.append(
        WeeklySchedule(day="Mon", session="AM", status=ScheduleStatus.OPD)
    )
    patient = add_patient(db)
    appointment = Appointment(
        id="AX1",
        patient=patient,
        doctor=doctor,
        speciality="General",
        visit_type=VisitType.NEW,
        date=date(2026, 11, 4),
        start_time=time(9, 0),
        end_time=time(9, 20),
        status=AppointmentStatus.BOOKED,
        created_at=datetime(2026, 11, 2, 10, 0),
    )
    db.add_all([doctor, appointment])
    db.commit()

    stored = db.scalar(select(Appointment).where(Appointment.id == "AX1"))
    assert stored is not None
    assert stored.patient.year_of_birth is None
    assert [item.speciality for item in stored.doctor.specialities] == ["General"]
    assert stored.doctor.schedules[0].status is ScheduleStatus.OPD
    assert stored.visit_type.minutes == 20
    assert stored.status is AppointmentStatus.BOOKED

    stored.status = AppointmentStatus.COMPLETED
    db.commit()
    assert stored.status is AppointmentStatus.COMPLETED
    assert Role.PATIENT.value == "patient"


def test_mobile_is_unique(db: Session) -> None:
    add_patient(db, "PX1")
    add_patient(db, "PX2")
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_weekly_schedule_composite_key(db: Session) -> None:
    db.add(Doctor(id="DX1", name="Dr. Test"))
    db.add(WeeklySchedule(doctor_id="DX1", day="Mon", session="AM", status=ScheduleStatus.OPD))
    db.flush()
    db.add(WeeklySchedule(doctor_id="DX1", day="Mon", session="AM", status=ScheduleStatus.OFF))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
