from datetime import date, datetime, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.loader import load_data_pack, load_seed_appointments
from app.models import (
    Appointment,
    AppointmentStatus,
    Doctor,
    Holiday,
    Patient,
    VisitType,
    WeeklySchedule,
)


def counts(db: Session) -> tuple[int, int, int, int, int]:
    return tuple(
        db.scalar(select(func.count()).select_from(model)) or 0
        for model in (Doctor, WeeklySchedule, Holiday, Patient, Appointment)
    )


def test_main_loader_counts_and_empty_appointments(db: Session, data_pack_path) -> None:
    load_data_pack(db, data_pack_path)
    assert counts(db) == (5, 60, 30, 25, 0)
    asha = db.get(Patient, "P01")
    assert asha is not None
    assert (asha.name, asha.mobile, asha.year_of_birth) == ("Asha Verma", "9000000001", 1958)
    rao = db.get(Doctor, "D1")
    assert rao is not None
    assert {item.speciality for item in rao.specialities} == {"Cataract", "General"}
    assert db.get(WeeklySchedule, ("D1", "Thu", "AM")).status.value == "SURGERY"


def test_reloading_preserves_appointments_and_unique_reference_rows(db: Session, data_pack_path) -> None:
    load_data_pack(db, data_pack_path)
    appointment = Appointment(
        id="ATEST",
        patient_id="P01",
        doctor_id="D1",
        speciality="General",
        visit_type=VisitType.NEW,
        date=date(2026, 12, 1),
        start_time=time(9, 0),
        end_time=time(9, 20),
        status=AppointmentStatus.BOOKED,
        created_at=datetime(2026, 11, 2, 10, 0),
    )
    db.add(appointment)
    db.commit()

    load_data_pack(db, data_pack_path)

    assert counts(db) == (5, 60, 30, 25, 1)
    assert db.get(Appointment, "ATEST").status is AppointmentStatus.BOOKED


def test_seed_loader_is_separate(db: Session, data_pack_path) -> None:
    load_data_pack(db, data_pack_path)
    load_seed_appointments(db, data_pack_path / "stretch" / "appointments_seed.csv")
    assert counts(db) == (5, 60, 30, 25, 19)
    assert db.get(Appointment, "A001").status is AppointmentStatus.COMPLETED
    assert db.get(Appointment, "A090").status is AppointmentStatus.CANCELLED
