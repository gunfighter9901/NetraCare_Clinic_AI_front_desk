import csv
from datetime import datetime, time
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import (
    Appointment,
    AppointmentStatus,
    Doctor,
    DoctorSpeciality,
    Holiday,
    Patient,
    ScheduleStatus,
    VisitType,
    WeeklySchedule,
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_data_pack(db: Session, data_pack_path: Path) -> None:
    try:
        for row in read_csv(data_pack_path / "doctors.csv"):
            doctor = db.get(Doctor, row["doctor_id"])
            if doctor is None:
                doctor = Doctor(id=row["doctor_id"], name=row["name"])
                db.add(doctor)
            doctor.name = row["name"]
            doctor.specialities = [
                DoctorSpeciality(speciality=value.strip())
                for value in row["specialities"].split(";")
                if value.strip()
            ]
        db.flush()

        for row in read_csv(data_pack_path / "weekly_schedule.csv"):
            key = (row["doctor_id"], row["day"], row["session"])
            schedule = db.get(WeeklySchedule, key)
            if schedule is None:
                schedule = WeeklySchedule(
                    doctor_id=key[0], day=key[1], session=key[2], status=ScheduleStatus(row["status"])
                )
                db.add(schedule)
            else:
                schedule.status = ScheduleStatus(row["status"])

        for row in read_csv(data_pack_path / "holidays.csv"):
            holiday_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
            holiday = db.get(Holiday, holiday_date)
            if holiday is None:
                holiday = Holiday(date=holiday_date, name=row["name"])
                db.add(holiday)
            else:
                holiday.name = row["name"]

        for row in read_csv(data_pack_path / "patients.csv"):
            patient = db.get(Patient, row["patient_id"])
            if patient is None:
                patient = Patient(id=row["patient_id"], mobile=row["mobile"], name=row["name"])
                db.add(patient)
            patient.name = row["name"]
            patient.mobile = row["mobile"]
            patient.year_of_birth = int(row["year_of_birth"]) if row["year_of_birth"] else None
        db.commit()
    except Exception:
        db.rollback()
        raise


def load_seed_appointments(db: Session, path: Path) -> None:
    try:
        for row in read_csv(path):
            status = AppointmentStatus(row["status"])
            appointment_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
            start_time = time.fromisoformat(row["start_time"])
            end_time = time.fromisoformat(row["end_time"])
            starts_at = datetime.combine(appointment_date, start_time)
            ends_at = datetime.combine(appointment_date, end_time)
            appointment = db.get(Appointment, row["appointment_id"])
            if appointment is None:
                appointment = Appointment(
                    id=row["appointment_id"],
                    patient_id=row["patient_id"],
                    doctor_id=row["doctor_id"],
                    speciality=row["speciality"],
                    visit_type=VisitType(row["visit_type"]),
                    date=appointment_date,
                    start_time=start_time,
                    end_time=end_time,
                    status=status,
                    created_at=starts_at,
                    cancelled_at=ends_at if status is AppointmentStatus.CANCELLED else None,
                    completed_at=ends_at if status is AppointmentStatus.COMPLETED else None,
                )
                db.add(appointment)
        db.commit()
    except Exception:
        db.rollback()
        raise


def load_patient_profiles(db: Session, path: Path) -> int:
    try:
        count = 0
        for row in read_csv(path):
            patient = db.get(Patient, row["patient_id"])
            if patient is None:
                continue
            patient.general_health = row.get("general_health") or None
            patient.allergies = row.get("allergies") or None
            count += 1
        db.commit()
        return count
    except Exception:
        db.rollback()
        raise


def load_past_visits(db: Session, path: Path) -> int:
    try:
        count = 0
        for row in read_csv(path):
            appointment_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
            start_time = time.fromisoformat(row["start_time"])
            end_time = time.fromisoformat(row["end_time"])
            starts_at = datetime.combine(appointment_date, start_time)
            ends_at = datetime.combine(appointment_date, end_time)
            appointment = db.get(Appointment, row["visit_id"])
            if appointment is None:
                appointment = Appointment(
                    id=row["visit_id"],
                    patient_id=row["patient_id"],
                    doctor_id=row["doctor_id"],
                    speciality=row["speciality"],
                    visit_type=VisitType(row["visit_type"]),
                    date=appointment_date,
                    start_time=start_time,
                    end_time=end_time,
                    status=AppointmentStatus.COMPLETED,
                    created_at=starts_at,
                    completed_at=ends_at,
                    reason=row.get("reason"),
                    doctor_note=row.get("doctor_note"),
                    is_urgent=False,
                )
                db.add(appointment)
            else:
                appointment.patient_id = row["patient_id"]
                appointment.doctor_id = row["doctor_id"]
                appointment.speciality = row["speciality"]
                appointment.visit_type = VisitType(row["visit_type"])
                appointment.date = appointment_date
                appointment.start_time = start_time
                appointment.end_time = end_time
                appointment.status = AppointmentStatus.COMPLETED
                appointment.completed_at = ends_at
                appointment.reason = row.get("reason")
                appointment.doctor_note = row.get("doctor_note")
            count += 1
        db.commit()
        return count
    except Exception:
        db.rollback()
        raise


def load_data_pack_2(db: Session, data_pack_2_path: Path) -> dict[str, int]:
    profiles_path = data_pack_2_path / "patient_profiles.csv"
    visits_path = data_pack_2_path / "past_visits.csv"
    profiles = load_patient_profiles(db, profiles_path) if profiles_path.exists() else 0
    visits = load_past_visits(db, visits_path) if visits_path.exists() else 0
    return {"profiles": profiles, "past_visits": visits}


def initialize_database() -> dict[str, int]:
    from app.db import engine as default_engine
    from app.migrate_iteration2 import ensure_iteration2_schema
    from app.migrate_iteration3 import ensure_iteration3_schema
    from app.migrate_iteration4 import ensure_iteration4_schema

    settings = get_settings()
    init_db()
    ensure_iteration2_schema(default_engine)
    ensure_iteration3_schema(default_engine)
    ensure_iteration4_schema(default_engine)
    with SessionLocal() as db:
        load_data_pack(db, settings.data_pack_path)
        pack2_path = settings.data_pack_2_path
        try:
            if pack2_path.exists():
                load_data_pack_2(db, pack2_path)
        except Exception:
            pass
        return {
            "doctors": db.scalar(select(func.count()).select_from(Doctor)) or 0,
            "weekly_schedule": db.scalar(select(func.count()).select_from(WeeklySchedule)) or 0,
            "holidays": db.scalar(select(func.count()).select_from(Holiday)) or 0,
            "patients": db.scalar(select(func.count()).select_from(Patient)) or 0,
            "appointments": db.scalar(select(func.count()).select_from(Appointment)) or 0,
        }


if __name__ == "__main__":
    print(initialize_database())
