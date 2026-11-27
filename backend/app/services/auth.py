import secrets
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuthSession, Doctor, Patient, Role
from app.services.common import next_source_id


class AuthenticationError(ValueError):
    pass


def _session(
    db: Session,
    role: Role,
    *,
    patient_id: str | None = None,
    doctor_id: str | None = None,
    staff_name: str | None = None,
) -> AuthSession:
    session = AuthSession(
        token=secrets.token_urlsafe(32),
        role=role,
        patient_id=patient_id,
        doctor_id=doctor_id,
        staff_name=staff_name,
        created_at=datetime.now(),
    )
    db.add(session)
    db.commit()
    return session


def login_patient(db: Session, mobile: str, name: str) -> AuthSession:
    mobile = mobile.strip()
    name = " ".join(name.split())
    if not mobile or not name:
        raise AuthenticationError("Mobile number and name are required")
    patient = db.scalar(select(Patient).where(Patient.mobile == mobile))
    if patient is None:
        patient = Patient(
            id=next_source_id(db, Patient, "P", 2),
            mobile=mobile,
            name=name,
            year_of_birth=None,
        )
        db.add(patient)
        db.flush()
    elif patient.name.casefold() != name.casefold():
        db.rollback()
        raise AuthenticationError("Mobile number and name do not match")
    return _session(db, Role.PATIENT, patient_id=patient.id)


def login_doctor(db: Session, doctor_id: str) -> AuthSession:
    doctor = db.get(Doctor, doctor_id)
    if doctor is None:
        raise AuthenticationError("Please select a valid doctor")
    return _session(db, Role.DOCTOR, doctor_id=doctor.id)


def login_staff(db: Session, name: str) -> AuthSession:
    name = " ".join(name.split())
    if not name:
        raise AuthenticationError("Staff name is required")
    return _session(db, Role.STAFF, staff_name=name)


def resolve_session(db: Session, token: str | None) -> AuthSession | None:
    if not token:
        return None
    return db.get(AuthSession, token)


def logout(db: Session, token: str) -> None:
    session = db.get(AuthSession, token)
    if session is not None:
        db.delete(session)
        db.commit()
