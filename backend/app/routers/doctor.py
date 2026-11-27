from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_doctor
from app.models import AuthSession
from app.routers.common import appointment_view
from app.schemas import AppointmentView, PatientHistoryItem
from app.services.appointments import list_doctor_appointments, list_patient_completed_history

router = APIRouter(prefix="/doctor", tags=["doctor"])


def history_item(appointment) -> PatientHistoryItem:
    return PatientHistoryItem(
        id=appointment.id,
        date=appointment.date,
        doctor_id=appointment.doctor_id,
        doctor_name=appointment.doctor.name if appointment.doctor else appointment.doctor_id,
        speciality=appointment.speciality,
        visit_type=appointment.visit_type,
        reason=appointment.reason,
        doctor_note=appointment.doctor_note,
        status=appointment.status,
    )


@router.get(
    "/appointments",
    response_model=list[AppointmentView],
    summary="List the Doctor's schedule",
    description="Returns only the authenticated Doctor's appointments for the chosen date.",
)
def doctor_schedule(
    appointment_date: date,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(require_doctor),
) -> list[AppointmentView]:
    appointments = list_doctor_appointments(db, session.doctor_id or "", appointment_date)
    return [appointment_view(appointment) for appointment in appointments]


@router.get(
    "/patients/{patient_id}/history",
    response_model=list[PatientHistoryItem],
    summary="Patient completed history",
    description="Doctor-only completed visits for a patient, newest first, with reasons and notes.",
)
def patient_history(
    patient_id: str,
    db: Session = Depends(get_db),
    _session: AuthSession = Depends(require_doctor),
) -> list[PatientHistoryItem]:
    history = list_patient_completed_history(db, patient_id)
    return [history_item(item) for item in history]
