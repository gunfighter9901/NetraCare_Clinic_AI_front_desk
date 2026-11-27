import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.loader import load_data_pack
from app.models import AuthSession, Patient, Role
from app.services.auth import (
    AuthenticationError,
    login_doctor,
    login_patient,
    login_staff,
)


@pytest.fixture()
def auth_db(db: Session, data_pack_path):
    load_data_pack(db, data_pack_path)
    return db


def test_new_mobile_creates_patient_then_reuses_identity(auth_db: Session) -> None:
    first = login_patient(auth_db, "9999999999", "New Patient")
    second = login_patient(auth_db, "9999999999", "new patient")
    patient = auth_db.get(Patient, "P26")
    assert patient is not None
    assert patient.year_of_birth is None
    assert first.patient_id == second.patient_id == patient.id


def test_existing_mobile_name_mismatch_creates_no_session(auth_db: Session) -> None:
    before = auth_db.scalar(select(func.count()).select_from(AuthSession))
    with pytest.raises(AuthenticationError, match="do not match"):
        login_patient(auth_db, "9000000001", "Someone Else")
    assert auth_db.scalar(select(func.count()).select_from(AuthSession)) == before


def test_doctor_and_staff_login_validation(auth_db: Session) -> None:
    doctor = login_doctor(auth_db, "D1")
    staff = login_staff(auth_db, " Front Desk ")
    assert doctor.role is Role.DOCTOR and doctor.doctor_id == "D1"
    assert staff.role is Role.STAFF and staff.staff_name == "Front Desk"
    with pytest.raises(AuthenticationError):
        login_doctor(auth_db, "UNKNOWN")
    with pytest.raises(AuthenticationError):
        login_staff(auth_db, "   ")
